import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# Фікс для Windows консолі (щоб коректно відображалися українські літери)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

SOURCE_URL = "https://hoe.com.ua/page/pogodinni-vidkljuchennja"
DATA_DIR = os.path.join("data", "gpv")
TODAY_FILE = os.path.join(DATA_DIR, "today.json")
TOMORROW_FILE = os.path.join(DATA_DIR, "tomorrow.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

HISTORY_RETENTION_DAYS = 39
SLOTS_COUNT = 48
DEFAULT_ON_GRID = "1" * SLOTS_COUNT

ALL_QUEUES = [
    "1.1", "1.2",
    "2.1", "2.2",
    "3.1", "3.2",
    "4.1", "4.2",
    "5.1", "5.2",
    "6.1", "6.2",
]

UA_MONTHS = {
    "січня": 1,
    "лютого": 2,
    "березня": 3,
    "квітня": 4,
    "травня": 5,
    "червня": 6,
    "липня": 7,
    "серпня": 8,
    "вересня": 9,
    "жовтня": 10,
    "листопада": 11,
    "грудня": 12,
}


def _last_sunday(year: int, month: int) -> int:
    """Повертає день місяця для останньої неділі вказаного місяця."""
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    last_day = next_month - timedelta(days=1)
    # weekday(): Monday=0 ... Sunday=6
    offset = (last_day.weekday() + 1) % 7
    return (last_day - timedelta(days=offset)).day


def get_kyiv_now() -> datetime:
    """Повертає поточний час у часовому поясі Europe/Kyiv (з tzinfo)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Kyiv"))
    except Exception:
        # Надійний розрахунок UTC+2 / UTC+3 (DST для України) без залежності від tzdata
        utc_now = datetime.now(timezone.utc)
        year = utc_now.year
        dst_start = datetime(year, 3, _last_sunday(year, 3), 1, 0, tzinfo=timezone.utc)
        dst_end = datetime(year, 10, _last_sunday(year, 10), 1, 0, tzinfo=timezone.utc)
        offset_hours = 3 if (dst_start <= utc_now < dst_end) else 2
        kyiv_tz = timezone(timedelta(hours=offset_hours))
        return utc_now.astimezone(kyiv_tz)


def load_json_safe(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_atomic(path: str, data: dict) -> bool:
    """Записує JSON на диск лише тоді, коли вміст дійсно змінився."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new_content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                old_content = f.read()
            if old_content == new_content:
                return False
        except Exception:
            pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


def compute_queues_hash(queues: dict, is_canceled: bool = False) -> str:
    payload = json.dumps({"canceled": is_canceled, "queues": queues}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def intervals_to_grid48(intervals_list: list) -> str:
    """
    Перетворює список кортежів (h1, m1, h2, m2) у 48-символьний рядок з '1' та '0'.
    Крок = 30 хвилин:
      '1' - електроенергія є
      '0' - відключення
    """
    slots = ["1"] * SLOTS_COUNT
    for h1, m1, h2, m2 in intervals_list:
        start_idx = h1 * 2 + (1 if m1 >= 30 else 0)
        if h2 == 24 or (h2 == 0 and m2 == 0 and (h1 > 0 or m1 > 0)):
            end_idx = SLOTS_COUNT
        else:
            end_idx = h2 * 2 + (1 if m2 >= 30 else 0)

        start_idx = max(0, min(SLOTS_COUNT, start_idx))
        end_idx = max(0, min(SLOTS_COUNT, end_idx))

        for idx in range(start_idx, end_idx):
            slots[idx] = "0"

    return "".join(slots)


def resolve_target_date(day: int, month: int, explicit_year: int | None, ref_dt: datetime) -> str:
    if explicit_year:
        year = explicit_year
    else:
        year = ref_dt.year
        if ref_dt.month == 12 and month == 1:
            year += 1
        elif ref_dt.month == 1 and month == 12:
            year -= 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def extract_date_from_text(text: str, ref_dt: datetime) -> str | None:
    """Шукає дату українською мовою ('на 8 листопада', '8 листопада 2026') або DD.MM.YYYY."""
    months_pattern = "|".join(UA_MONTHS.keys())
    m = re.search(
        rf"(?<!\d)(\d{{1,2}})\s+({months_pattern})(?:\s+(\d{{4}}))?",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        day = int(m.group(1))
        month_name = m.group(2).lower()
        month = UA_MONTHS[month_name]
        year = int(m.group(3)) if m.group(3) else None
        try:
            return resolve_target_date(day, month, year, ref_dt)
        except ValueError:
            pass

    m_num = re.search(r"(?<!\d)(\d{2})\.(\d{2})(?:\.(\d{4}))?(?!\d)", text)
    if m_num:
        day = int(m_num.group(1))
        month = int(m_num.group(2))
        year = int(m_num.group(3)) if m_num.group(3) else None
        if 1 <= day <= 31 and 1 <= month <= 12:
            try:
                return resolve_target_date(day, month, year, ref_dt)
            except ValueError:
                pass
    return None


def parse_single_block(raw_block_text: str, ref_dt: datetime) -> dict | None:
    """
    Парсить один інформаційний блок між <hr /> на сторінці погодинних відключень.
    Повертає словник з датою, заголовком, типом блоку та розкладом по підчергах,
    або None, якщо блок є довідковим/статичним.
    """
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw_block_text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return None

    full_text = "\n".join(lines)

    # Відсікаємо статичні блоки з таблицями РЕМів та довідкою
    if "Файли співставлення адрес" in full_text or "Перевірити чергу" in full_text:
        if "Підчерга" not in full_text and "підчерга" not in full_text:
            return None

    target_date = extract_date_from_text(full_text, ref_dt)
    if not target_date:
        return None

    # Виділяємо шапку повідомлення (рядки до першої згадки 'Підчерга' або 'Години відсутності')
    header_lines = []
    for line in lines:
        if re.match(r"^(?:Підчерга|Черга)\s*[1-6]\.[12]", line, flags=re.IGNORECASE):
            break
        if re.match(r"^Години відсутності електроенергії\s*:?$", line, flags=re.IGNORECASE):
            continue
        header_lines.append(line)

    header_text = " ".join(header_lines).strip()
    if not header_text:
        header_text = lines[0]

    lower_header = header_text.lower()
    is_canceled = any(
        kw in lower_header
        for kw in ["скасовано", "не застосовуватимуться", "не будуть застосовані", "відключень не планується"]
    )
    is_update = any(
        kw in lower_header
        for kw in ["оновлено", "оновлення", "змінено", "зміни", "скориговано", "додатково", "увага"]
    )

    # Шукаємо рядки підчерг: Підчерга 1.1 – 03:00-06:00; 12:00-16:00.
    parsed_queues = {}
    queue_pattern = re.compile(
        r"(?:Підчерга|Черга)\s*([1-6]\.[12])\s*[–—\-:]+\s*([^\n]+)",
        flags=re.IGNORECASE,
    )
    interval_pattern = re.compile(r"(\d{1,2})[:.](\d{2})\s*[–—\-]+\s*(\d{1,2})[:.](\d{2})")

    for match in queue_pattern.finditer(full_text):
        q_id = match.group(1)
        rest = match.group(2).strip()
        intervals = []
        for im in interval_pattern.finditer(rest):
            h1, m1, h2, m2 = int(im.group(1)), int(im.group(2)), int(im.group(3)), int(im.group(4))
            intervals.append((h1, m1, h2, m2))
        parsed_queues[q_id] = intervals_to_grid48(intervals)

    if not parsed_queues and not is_canceled:
        return None

    return {
        "date": target_date,
        "header_text": header_text,
        "is_update": is_update,
        "is_canceled": is_canceled,
        "queues": parsed_queues,
    }


def parse_gpv_html(html_content: str, ref_dt: datetime) -> dict[str, list[dict]]:
    """
    Розбирає HTML сторінки ГПВ та повертає словник { "YYYY-MM-DD": [block_oldest, ..., block_newest] }.
    На сайті найновіше повідомлення знаходиться зверху, тому для кожної дати ми розвертаємо
    список блоків у хронологічний порядок (від старішого до новішого).
    """
    soup = BeautifulSoup(html_content, "html.parser")
    post_div = soup.select_one("div.content-main div.post") or soup.find("div", class_="post")
    if not post_div:
        raise ValueError("Не знайдено контейнер <div class='post'> на сторінці ГПВ.")

    # Замінюємо <hr> на маркер розбиття блоків, а <br> та блокові теги — на переноси рядків
    for hr in post_div.find_all("hr"):
        hr.replace_with("\n===GPV_BLOCK_SPLIT===\n")
    for br in post_div.find_all("br"):
        br.replace_with("\n")
    for tag in post_div.find_all(["p", "div", "li", "h1", "h2", "h3", "h4"]):
        tag.append("\n")

    raw_text = post_div.get_text()
    raw_chunks = raw_text.split("===GPV_BLOCK_SPLIT===")

    blocks_by_date: dict[str, list[dict]] = {}
    for chunk in raw_chunks:
        parsed = parse_single_block(chunk, ref_dt)
        if parsed:
            d = parsed["date"]
            blocks_by_date.setdefault(d, []).append(parsed)

    # На сторінці верхній блок — найсвіжіший. Розвертаємо, щоб застосовувати від першого до останнього
    for d in blocks_by_date:
        blocks_by_date[d].reverse()

    return blocks_by_date


def fetch_gpv_html(url: str = SOURCE_URL) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip",
        "Connection": "close",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw_bytes = resp.read()
        if resp.info().get("Content-Encoding") == "gzip" or raw_bytes[:2] == b"\x1f\x8b":
            raw_bytes = gzip.decompress(raw_bytes)
        return raw_bytes.decode("utf-8", errors="replace")


def format_header_message(target_date: str, status: str, source_header: str, updated_iso: str) -> str:
    """Формує лаконічне інформативне повідомлення у шапці вихідного JSON."""
    dd_mm = f"{target_date[8:10]}.{target_date[5:7]}"
    try:
        dt = datetime.fromisoformat(updated_iso)
        time_str = dt.strftime("%H:%M")
    except Exception:
        time_str = ""

    clean_header = (source_header or "").strip().rstrip(".")
    if status == "waiting":
        return f"Графік погодинних відключень на {dd_mm} ще не оприлюднено. Попередньо: відключень не прогнозується."
    if status == "canceled":
        base = clean_header or f"Погодинні відключення на {dd_mm} скасовано"
        return f"{base}. (відповідно до змін станом на {time_str})" if time_str else f"{base}."
    if status == "updated":
        base = clean_header or f"Оновлено графік ГПВ на {dd_mm}"
        return f"{base}. (відповідно до змін станом на {time_str})" if time_str else f"{base}."

    # status == "initial"
    base = clean_header or f"Графік ГПВ на {dd_mm}"
    return f"{base}. (станом на {time_str})" if time_str else f"{base}."


def build_day_state(
    target_date: str,
    chronological_blocks: list[dict],
    history_days: dict,
    now_iso: str,
) -> dict:
    """
    Оновлює історію за вказану дату (target_date) на основі розпарсених блоків зі сторінки
    та повертає лаконічний словник для today.json або tomorrow.json.
    """
    day_hist = history_days.get(target_date, {
        "first_seen_at": None,
        "last_updated_at": None,
        "status": "waiting",
        "source_header": "",
        "queues": {q: DEFAULT_ON_GRID for q in ALL_QUEUES},
        "revisions": [],
    })

    if not chronological_blocks:
        # Якщо на поточній сторінці немає блоків за цю дату:
        # 1) якщо в історії вже був збережений графік за цю дату — зберігаємо його актуальність
        if day_hist.get("revisions"):
            status = day_hist["status"]
            updated_at = day_hist["last_updated_at"] or now_iso
            source_header = day_hist.get("source_header", "")
            queues = day_hist["queues"]
            return {
                "date": target_date,
                "updated_at": updated_at,
                "status": status,
                "message": format_header_message(target_date, status, source_header, updated_at),
                "queues": queues,
            }
        # 2) інакше графік ще не оприлюднено (режим очікування)
        existing_waiting_time = day_hist.get("last_updated_at") or now_iso
        day_hist["last_updated_at"] = existing_waiting_time
        history_days[target_date] = day_hist
        queues = {q: DEFAULT_ON_GRID for q in ALL_QUEUES}
        return {
            "date": target_date,
            "updated_at": existing_waiting_time,
            "status": "waiting",
            "message": format_header_message(target_date, "waiting", "", existing_waiting_time),
            "queues": queues,
        }

    # Якщо блоки за цю дату є на сторінці — послідовно накладаємо їх від старішого до новішого
    base_queues = dict(day_hist.get("queues") or {q: DEFAULT_ON_GRID for q in ALL_QUEUES})
    revisions: list[dict] = list(day_hist.get("revisions") or [])

    # Обчислюємо послідовність знімків зі сторінки (від старішого блоку до найновішого)
    page_snapshots = []
    running_queues = dict(base_queues) if revisions else {q: DEFAULT_ON_GRID for q in ALL_QUEUES}

    for idx, block in enumerate(chronological_blocks):
        if block["is_canceled"]:
            snap_queues = {q: DEFAULT_ON_GRID for q in ALL_QUEUES}
            snap_status = "canceled"
        else:
            if len(block["queues"]) == len(ALL_QUEUES):
                snap_queues = {q: block["queues"][q] for q in ALL_QUEUES}
            else:
                snap_queues = dict(running_queues)
                for q, grid in block["queues"].items():
                    snap_queues[q] = grid

            if idx > 0 or block["is_update"]:
                snap_status = "updated"
            else:
                snap_status = "initial"

        snap_hash = compute_queues_hash(snap_queues, block["is_canceled"])
        running_queues = snap_queues
        page_snapshots.append({
            "status": snap_status,
            "is_canceled": block["is_canceled"],
            "header_text": block["header_text"],
            "queues_hash": snap_hash,
            "queues": snap_queues,
        })

    if not revisions:
        # Перша поява цієї дати: записуємо всі унікальні ревізії зі сторінки по черзі
        for snap in page_snapshots:
            if not revisions or revisions[-1]["queues_hash"] != snap["queues_hash"]:
                rev_status = snap["status"]
                if len(revisions) > 0 and rev_status == "initial":
                    rev_status = "updated"
                revisions.append({
                    "revision": len(revisions) + 1,
                    "detected_at": now_iso,
                    "status": rev_status,
                    "source_header": snap["header_text"],
                    "queues_hash": snap["queues_hash"],
                    "queues": snap["queues"],
                })
        day_hist["first_seen_at"] = now_iso
        day_hist["last_updated_at"] = now_iso
    else:
        # Дата вже відслідковується: перевіряємо, чи змінився фінальний (верхній на сторінці) стан
        final_snap = page_snapshots[-1]
        if final_snap["queues_hash"] != revisions[-1]["queues_hash"]:
            rev_status = "canceled" if final_snap["is_canceled"] else "updated"
            revisions.append({
                "revision": len(revisions) + 1,
                "detected_at": now_iso,
                "status": rev_status,
                "source_header": final_snap["header_text"],
                "queues_hash": final_snap["queues_hash"],
                "queues": final_snap["queues"],
            })
            day_hist["last_updated_at"] = now_iso
        else:
            revisions[-1]["source_header"] = final_snap["header_text"]

    latest_rev = revisions[-1]
    final_status = "canceled" if latest_rev["status"] == "canceled" else (
        "updated" if (len(revisions) > 1 or latest_rev["status"] == "updated") else "initial"
    )
    latest_rev["status"] = final_status
    current_queues = latest_rev["queues"]

    day_hist["status"] = final_status
    day_hist["source_header"] = latest_rev["source_header"]
    day_hist["queues"] = current_queues
    day_hist["revisions"] = revisions
    if not day_hist.get("last_updated_at"):
        day_hist["last_updated_at"] = now_iso

    history_days[target_date] = day_hist

    updated_at = day_hist["last_updated_at"]
    return {
        "date": target_date,
        "updated_at": updated_at,
        "status": final_status,
        "message": format_header_message(target_date, final_status, day_hist["source_header"], updated_at),
        "queues": current_queues,
    }


def prune_history(history_days: dict, today_dt: datetime) -> dict:
    """Зберігає історію лише за останні HISTORY_RETENTION_DAYS (39 днів)."""
    cutoff_date = (today_dt.date() - timedelta(days=HISTORY_RETENTION_DAYS)).isoformat()
    return {
        d: val
        for d, val in sorted(history_days.items())
        if d >= cutoff_date
    }


def should_skip_by_schedule(now_kyiv: datetime, force: bool = False) -> bool:
    """
    Економія ресурсів при запусках за розкладом:
    1. Якщо файли today.json / tomorrow.json ще не існують або їх дата застаріла (настала нова доба) -> НЕ пропускаємо.
    2. У вечірній активний період (19:00–23:59), коли cron запускає скрипт кожні 15 хвилин:
       - якщо графік на завтра ще НЕ з'явився (status == 'waiting'), перевіряємо сайт кожні 15 хв;
       - щойно графік на завтра вже знайдено (status != 'waiting'), пропускаємо проміжні запуски (:15, :30, :45)
         і перевіряємо сайт лише раз на годину (на початку години, хвилини 00..10).
    3. У нічний час (01:00–06:59 за Києвом) дозволяємо перевірку лише у вікні 05:00 (раз на 5 годин після 00:05).
    """
    if force:
        return False

    today_str = now_kyiv.strftime("%Y-%m-%d")
    tomorrow_str = (now_kyiv + timedelta(days=1)).strftime("%Y-%m-%d")

    today_data = load_json_safe(TODAY_FILE, None)
    tomorrow_data = load_json_safe(TOMORROW_FILE, None)

    if not today_data or not tomorrow_data:
        return False
    if today_data.get("date") != today_str or tomorrow_data.get("date") != tomorrow_str:
        return False

    hour = now_kyiv.hour
    minute = now_kyiv.minute

    # Нічний режим (00:00-06:59): працюємо о 00:00..00:19 (ротація доби) та о 05:00..05:19 (раз на 5 годин)
    if hour == 0 and minute >= 20:
        print(f"[SMART-SKIP] Нічний режим ({now_kyiv.strftime('%H:%M')}). Ротацію доби вже виконано.")
        return True
    if 1 <= hour <= 6 and (hour != 5 or minute >= 20):
        print(f"[SMART-SKIP] Нічний режим ({now_kyiv.strftime('%H:%M')}). Перевірку пропущено для економії ресурсів.")
        return True

    # Денний режим (07:00-18:59): 1 раз на годину (на початку години)
    if 7 <= hour <= 18 and minute >= 12:
        print(f"[SMART-SKIP] Денний погодинний режим ({now_kyiv.strftime('%H:%M')}). Проміжний запуск пропущено.")
        return True

    # Вечірній режим (19:00-23:59): кожні 15 хв до появи графіка на завтра, потім — 1 раз на годину
    if 19 <= hour <= 23 and minute >= 12:
        if tomorrow_data.get("status") != "waiting":
            print(
                f"[SMART-SKIP] Графік на завтра ({tomorrow_str}) вже опубліковано "
                f"(status='{tomorrow_data.get('status')}'). Перехід у погодинний режим."
            )
            return True

    return False


def run_collector(force: bool = False, html_path: str | None = None) -> int:
    now_kyiv = get_kyiv_now()
    now_iso = now_kyiv.isoformat(timespec="seconds")
    today_str = now_kyiv.strftime("%Y-%m-%d")
    tomorrow_str = (now_kyiv + timedelta(days=1)).strftime("%Y-%m-%d")

    if not html_path and should_skip_by_schedule(now_kyiv, force=force):
        return 0

    if html_path:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        print(f"[GPV] Завантажено локальний HTML: {html_path}")
    else:
        print(f"[GPV] Запит до {SOURCE_URL} ({now_kyiv.strftime('%d.%m.%Y %H:%M:%S')})...")
        html_content = fetch_gpv_html(SOURCE_URL)

    blocks_by_date = parse_gpv_html(html_content, now_kyiv)
    found_dates = sorted(blocks_by_date.keys())
    print(f"[GPV] Знайдено дати на сторінці: {found_dates}")

    history_doc = load_json_safe(HISTORY_FILE, {"retention_days": HISTORY_RETENTION_DAYS, "days": {}})
    history_days = history_doc.get("days", {})

    # Оновлюємо в історії всі інші дати зі сторінки (крім today та tomorrow, які формуються нижче)
    for d in found_dates:
        if d not in (today_str, tomorrow_str):
            build_day_state(d, blocks_by_date[d], history_days, now_iso)

    # Формуємо цільові стани на сьогодні та завтра
    today_payload = build_day_state(
        today_str,
        blocks_by_date.get(today_str, []),
        history_days,
        now_iso,
    )
    tomorrow_payload = build_day_state(
        tomorrow_str,
        blocks_by_date.get(tomorrow_str, []),
        history_days,
        now_iso,
    )

    # Очищуємо історію старше 39 днів
    history_days = prune_history(history_days, now_kyiv)
    history_doc = {
        "retention_days": HISTORY_RETENTION_DAYS,
        "days": history_days,
    }

    changed_today = save_json_atomic(TODAY_FILE, today_payload)
    changed_tomorrow = save_json_atomic(TOMORROW_FILE, tomorrow_payload)
    changed_history = save_json_atomic(HISTORY_FILE, history_doc)

    if changed_today or changed_tomorrow or changed_history:
        print(
            f"[GPV] Оновлено файли: today={changed_today} (status={today_payload['status']}), "
            f"tomorrow={changed_tomorrow} (status={tomorrow_payload['status']}), history={changed_history}"
        )
    else:
        print("[GPV] Змін немає. Файли актуальні.")

    return 0


def main():
    parser = argparse.ArgumentParser(description="Парсер графіків погодинних відключень (ГПВ) Хмельницькобленерго")
    parser.add_argument("--force", action="store_true", help="Ігнорувати обмеження розкладу та виконати перевірку")
    parser.add_argument("--html-file", type=str, default=None, help="Шлях до локального HTML-файлу для тестування")
    args = parser.parse_args()

    try:
        sys.exit(run_collector(force=args.force, html_path=args.html_file))
    except Exception as exc:
        print(f"[GPV ERROR] Помилка виконання парсера ГПВ: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
