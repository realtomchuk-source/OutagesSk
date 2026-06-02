const app = document.getElementById('app');

async function sha256(str) {
    const encoder = new TextEncoder();
    const data = encoder.encode(str);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

function escapeHtml(str) {
    if (!str) return '';
    return str.toString().replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function login() {
    app.innerHTML = `
        <div class="card">
            <h2>Вхід до адмінки</h2>
            <div class="auth-form">
                <input type="password" id="passInput" placeholder="Пароль">
                <button class="btn btn-primary" onclick="checkPassword()">Увійти</button>
            </div>
            <p id="errorMsg" style="color:red; display:none;">Невірний пароль</p>
        </div>`;
}

window.checkPassword = async function() {
    const pass = document.getElementById('passInput').value;
    const hash = await sha256(pass);
    if (typeof ADMIN_HASH !== 'undefined' && hash === ADMIN_HASH) {
        showDashboard();
    } else {
        document.getElementById('errorMsg').style.display = 'block';
    }
}

async function showDashboard() {
    app.innerHTML = `
        <div class="card">
            <h2>Адмінка – Starokostiantyniv Outage Monitor</h2>
            <div id="dashboardWidgets"></div>
            <div class="tabs">
                <button class="tab active" onclick="switchTab('feed')">Стрічка</button>
                <button class="tab" onclick="switchTab('telegram')">Telegram</button>
                <button class="tab" onclick="switchTab('analytics')">Аналітика</button>
                <button class="tab" onclick="switchTab('streets')">Вулиці (Словник)</button>
                <button class="tab" onclick="switchTab('archive')">Архів</button>
                <button class="tab" onclick="switchTab('raw')">Сирі дані</button>
            </div>
            <div id="tabContent"></div>
        </div>
        <div id="statusArea"></div>`;
    await loadData();
    if (!window.autoRefresh) {
        window.autoRefresh = setInterval(loadData, 300000);
    }
}

let currentTab = 'feed';
let messages = [];
let updateLog = [];
let rawOutages = [];
let archiveOutages = [];
let officialStreets = [];

window.loadData = async function() {
    try {
        const msgResp = await fetch(`data/messages.json?t=${Date.now()}`);
        if (msgResp.ok) messages = await msgResp.json();

        const logResp = await fetch(`data/update_log.json?t=${Date.now()}`);
        if (logResp.ok) updateLog = await logResp.json();

        const rawResp = await fetch(`data/outages_snapshot.json?t=${Date.now()}`);
        if (rawResp.ok) rawOutages = await rawResp.json();

        try {
            const archResp = await fetch(`data/archive.json?t=${Date.now()}`);
            if (archResp.ok) archiveOutages = await archResp.json();
        } catch(e) {}
        
        try {
            const anResp = await fetch(`data/analytics.json?t=${Date.now()}`);
            if (anResp.ok) window.analyticsData = await anResp.json();
        } catch(e) {}
        
        try {
            const offResp = await fetch(`data/official_streets.json?t=${Date.now()}`);
            if (offResp.ok) officialStreets = await offResp.json();
        } catch(e) {}

        renderDashboard();
        renderTab(currentTab);
        renderStatus();
    } catch (err) {
        console.error(err);
        document.getElementById('statusArea').innerHTML = '<div class="status-bar status-error">⚠️ Помилка завантаження даних</div>';
    }
}

function renderDashboard() {
    let lastUpdate = '-';
    if (updateLog.length > 0) {
        lastUpdate = updateLog[updateLog.length - 1].timestamp;
    }
    
    let activePlanned = rawOutages.filter(r => r.type && r.type.includes('Планові')).length;
    let activeEmergency = rawOutages.filter(r => r.type && r.type.includes('Аварійні')).length;
    let settlements = new Set(rawOutages.map(r => r.settlement)).size;

    document.getElementById('dashboardWidgets').innerHTML = `
        <div class="dashboard-widgets">
            <div class="widget">
                <div class="widget-title">Останнє оновлення</div>
                <div class="widget-value">${escapeHtml(lastUpdate)}</div>
            </div>
            <div class="widget">
                <div class="widget-title">Планових відключень (записів)</div>
                <div class="widget-value warning">${activePlanned}</div>
            </div>
            <div class="widget">
                <div class="widget-title">Аварійних відключень (записів)</div>
                <div class="widget-value danger">${activeEmergency}</div>
            </div>
            <div class="widget">
                <div class="widget-title">Населених пунктів</div>
                <div class="widget-value">${settlements}</div>
            </div>
        </div>
    `;

    // Аналітика перенесена в окрему вкладку
}

window.switchTab = function(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(t => {
        t.classList.toggle('active', t.textContent.toLowerCase().includes(tab) || 
                                     (tab === 'raw' && t.textContent === 'Сирі дані') || 
                                     (tab === 'feed' && t.textContent === 'Стрічка') ||
                                     (tab === 'telegram' && t.textContent === 'Telegram') ||
                                     (tab === 'analytics' && t.textContent === 'Аналітика') ||
                                     (tab === 'streets' && t.textContent.includes('Вулиці')) ||
                                     (tab === 'archive' && t.textContent === 'Архів'));
    });
    renderTab(tab);
}

function renderTab(tab) {
    const container = document.getElementById('tabContent');
    if (!container) return;
    if (tab === 'feed') renderFeed(container);
    else if (tab === 'telegram') renderTelegram(container);
    else if (tab === 'analytics') renderAnalytics(container);
    else if (tab === 'streets') renderStreets(container);
    else if (tab === 'archive') renderArchive(container);
    else if (tab === 'raw') renderRaw(container);
}

function getFeedContent(type) {
    const msg = messages.find(m => m.type === type);
    return msg ? msg.content : 'Дані відсутні';
}

function renderFeed(container) {
    let todayStr = getFeedContent('feed_today');
    let tomorrowStr = getFeedContent('feed_tomorrow');

    container.innerHTML = `
        <h3>Стрічка (Ковзне вікно)</h3>
        
        <h4 style="margin-top:20px;">Стрічка на сьогодні</h4>
        <div class="ticker-wrapper"><div class="ticker-marquee js-ticker">${escapeHtml(todayStr)}</div></div>
        <textarea class="feed-textarea" readonly>${escapeHtml(todayStr)}</textarea>
        <button class="btn btn-primary" onclick="copyToClipboard(this.previousElementSibling.value)">📋 Копіювати текст</button>

        <h4 style="margin-top:30px;">Стрічка на завтра</h4>
        <div class="ticker-wrapper"><div class="ticker-marquee js-ticker">${escapeHtml(tomorrowStr)}</div></div>
        <textarea class="feed-textarea" readonly>${escapeHtml(tomorrowStr)}</textarea>
        <button class="btn btn-primary" onclick="copyToClipboard(this.previousElementSibling.value)">📋 Копіювати текст</button>
    `;
    
    // Анімація для стрічки
    document.querySelectorAll('.js-ticker').forEach(ticker => {
        ticker.innerHTML += " &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; " + ticker.innerHTML;
        let pos = 0;
        function step() {
            if (!document.body.contains(ticker)) return;
            pos += 1;
            if (pos >= ticker.scrollWidth / 2) pos = 0;
            ticker.scrollLeft = pos;
            requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    });
}

function renderTelegram(container) {
    // В Telegram вкладці показуємо тільки актуальні 4 пости.
    let html = '<h3>Telegram-пости (Тільки найновіші)</h3><div class="tg-grid">';
    
    const types = [
        { id: 'tg_planned', title: 'Планові', dateOffset: 0 },
        { id: 'tg_emergency', title: 'Аварійні', dateOffset: 0 },
        { id: 'tg_planned', title: 'Планові', dateOffset: 1 },
        { id: 'tg_emergency', title: 'Аварійні', dateOffset: 1 }
    ];

    types.forEach(t => {
        let d = new Date();
        d.setDate(d.getDate() + t.dateOffset);
        let dbDateStr = d.toLocaleDateString('en-CA'); // YYYY-MM-DD
        
        let label = t.dateOffset === 0 ? "СЬОГОДНІ" : "ЗАВТРА";
        
        // Знаходимо повідомлення
        let msg = messages.find(m => m.type === t.id && m.date === dbDateStr);
        let content = msg ? msg.content : "Очікування генерації або немає відключень.";
        
        html += `
            <div class="tg-card">
                <h4>${label}: ${t.title}</h4>
                <div class="post-body">${escapeHtml(content)}</div>
                <button class="btn btn-primary" onclick="copyToClipboard(this.previousElementSibling.innerText)">📋 Копіювати</button>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

function renderArchive(container) {
    container.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3>Комплексний Архів</h3>
            <div>
                <span style="font-size:14px;">Оберіть дату: </span>
                <input type="date" id="archiveDate" onchange="showArchived()" style="padding: 8px; border-radius: 4px; border: 1px solid var(--border); background: var(--bg); color: var(--text);">
            </div>
        </div>
        <div id="archiveResult" style="margin-top:20px;">
            <p class="empty" style="text-align:center; padding: 40px 0;">Оберіть дату для перегляду архіву.</p>
        </div>`;
}

window.showArchived = function() {
    const dateStr = document.getElementById('archiveDate').value; // YYYY-MM-DD
    const resultDiv = document.getElementById('archiveResult');
    if (!dateStr) { 
        resultDiv.innerHTML = '<p class="empty" style="text-align:center; padding: 40px 0;">Оберіть дату для перегляду архіву.</p>'; 
        return; 
    }
    
    // Формати дати для пошуку
    const [year, month, day] = dateStr.split('-');
    const dateDotStr = `${day}.${month}.${year}`;
    
    // 1. Пошук Telegram-постів та Стрічки
    const relevantMsgs = messages.filter(m => m.date === dateStr);
    const tgMsgs = relevantMsgs.filter(m => m.type.startsWith('tg_'));
    const feedMsgs = relevantMsgs.filter(m => m.type.startsWith('feed_'));
    
    // 2. Пошук Сирих даних в архіві
    // archiveOutages містять start_datetime у форматі "DD.MM.YYYY HH:MM"
    const relevantRaw = archiveOutages.filter(r => {
        if (!r.start_datetime) return false;
        return r.start_datetime.startsWith(dateDotStr);
    });

    if (tgMsgs.length === 0 && feedMsgs.length === 0 && relevantRaw.length === 0) {
        resultDiv.innerHTML = '<p class="empty" style="text-align:center; padding: 40px 0;">За обрану дату ('+dateDotStr+') даних в архіві не знайдено.</p>';
        return;
    }
    
    let html = '';
    
    // Блок Telegram
    html += '<h4 style="margin-bottom:15px; color:var(--primary); border-bottom:1px solid var(--border); padding-bottom:5px;">📱 Опубліковано в Telegram</h4>';
    if (tgMsgs.length > 0) {
        html += '<div class="tg-grid" style="margin-bottom:30px;">';
        tgMsgs.forEach(m => {
            let typeName = "Невідомо";
            if (m.type === 'tg_planned') typeName = 'Планові';
            if (m.type === 'tg_emergency') typeName = 'Аварійні';
            html += `
                <div class="tg-card">
                    <h5 style="margin-bottom:10px;">${typeName}</h5>
                    <div class="post-body" style="font-size:13px;">${escapeHtml(m.content)}</div>
                    <button class="btn btn-primary" style="font-size:12px; padding:6px 12px;" onclick="copyToClipboard(this.previousElementSibling.innerText)">📋 Копіювати</button>
                </div>
            `;
        });
        html += '</div>';
    } else {
        html += '<p class="empty" style="margin-bottom:30px;">Telegram-пости відсутні.</p>';
    }

    // Блок Стрічка
    html += '<h4 style="margin-bottom:15px; color:var(--primary); border-bottom:1px solid var(--border); padding-bottom:5px;">🌐 Тексти для Стрічки сайту</h4>';
    if (feedMsgs.length > 0) {
        html += '<div style="margin-bottom:30px;">';
        feedMsgs.forEach(m => {
            let lbl = m.type === 'feed_today' ? 'Стрічка на поточний день' : 'Стрічка на наступний день';
            html += `
                <div style="margin-bottom:15px; padding:15px; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius);">
                    <h5 style="margin-bottom:8px;">${lbl}</h5>
                    <div style="font-family:monospace; font-size:13px; color:var(--text); white-space:pre-wrap;">${escapeHtml(m.content)}</div>
                </div>
            `;
        });
        html += '</div>';
    } else {
        html += '<p class="empty" style="margin-bottom:30px;">Тексти стрічки відсутні.</p>';
    }

    // Блок Сирі дані
    html += '<h4 style="margin-bottom:15px; color:var(--primary); border-bottom:1px solid var(--border); padding-bottom:5px;">📊 Фактичні відключення (Сирі дані з архіву)</h4>';
    if (relevantRaw.length > 0) {
        html += `
        <div class="raw-table-container">
            <table class="raw-table">
                <thead>
                    <tr>
                        <th style="width: 15%;">Населений пункт</th>
                        <th style="width: 15%;">Вид робіт</th>
                        <th style="width: 15%;">Час</th>
                        <th style="width: 55%;">Вулиці та Будинки</th>
                    </tr>
                </thead>
                <tbody>`;
                
        relevantRaw.forEach(rec => {
            let dtStart = rec.start_datetime || "";
            let dtEnd = rec.end_datetime || "";
            if (dtStart.length >= 5 && !dtStart.includes(" ")) dtStart = dtStart.slice(0, -5) + " " + dtStart.slice(-5);
            if (dtEnd.length >= 5 && !dtEnd.includes(" ")) dtEnd = dtEnd.slice(0, -5) + " " + dtEnd.slice(-5);
            
            let streetsHtml = '<i>Немає даних</i>';
            if (rec.streets_detailed && rec.streets_detailed.length > 0) {
                streetsHtml = rec.streets_detailed.map(s => {
                    let housesStr = s.houses ? ` <span class="house-numbers">(буд. ${escapeHtml(s.houses)})</span>` : '';
                    return `<div class="street-item"><strong>${escapeHtml(s.name)}</strong>${housesStr}</div>`;
                }).join('');
            } else if (rec.streets && rec.streets.length > 0) {
                streetsHtml = rec.streets.map(s => `<div class="street-item"><strong>${escapeHtml(s)}</strong></div>`).join('');
            }
                
            let typeStyle = rec.type && rec.type.includes('Аварійні') ? 'color: var(--danger); font-weight: bold;' : 'color: var(--warning); font-weight: bold;';

            html += `<tr>
                <td><strong>${escapeHtml(rec.settlement || 'Невідомо')}</strong></td>
                <td style="${typeStyle}">${escapeHtml(rec.type || 'Невідомо')}</td>
                <td>${escapeHtml(dtStart)} - ${escapeHtml(dtEnd)}</td>
                <td>${streetsHtml}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    } else {
        html += '<p class="empty">Фактичних записів про відключення на цю дату немає в архіві.</p>';
    }

    resultDiv.innerHTML = html;
}

function renderRaw(container) {
    let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 15px;">
            <h3>Сирі дані з парсера</h3>
            <button class="btn btn-primary" onclick="loadData()">🔄 Оновити</button>
        </div>`;
    
    if (rawOutages.length === 0) {
        html += '<p class="empty">Немає зібраних даних.</p>';
    } else {
        html += `
        <div class="raw-table-container">
            <table class="raw-table">
                <thead>
                    <tr>
                        <th style="width: 15%;">Населений пункт</th>
                        <th style="width: 15%;">Вид робіт</th>
                        <th style="width: 15%;">Час</th>
                        <th style="width: 55%;">Вулиці та Будинки</th>
                    </tr>
                </thead>
                <tbody>`;
                
        rawOutages.forEach(rec => {
            let dtStart = rec.start_datetime || "";
            let dtEnd = rec.end_datetime || "";
            if (dtStart.length >= 5 && !dtStart.includes(" ")) dtStart = dtStart.slice(0, -5) + " " + dtStart.slice(-5);
            if (dtEnd.length >= 5 && !dtEnd.includes(" ")) dtEnd = dtEnd.slice(0, -5) + " " + dtEnd.slice(-5);
            
            let streetsHtml = '<i>Немає даних</i>';
            if (rec.streets_detailed && rec.streets_detailed.length > 0) {
                streetsHtml = rec.streets_detailed.map(s => {
                    let housesStr = s.houses ? ` <span class="house-numbers">(буд. ${escapeHtml(s.houses)})</span>` : '';
                    return `<div class="street-item"><strong>${escapeHtml(s.name)}</strong>${housesStr}</div>`;
                }).join('');
            } else if (rec.streets && rec.streets.length > 0) {
                streetsHtml = rec.streets.map(s => `<div class="street-item"><strong>${escapeHtml(s)}</strong></div>`).join('');
            }
                
            let typeStyle = rec.type && rec.type.includes('Аварійні') ? 'color: var(--danger); font-weight: bold;' : 'color: var(--warning); font-weight: bold;';

            html += `<tr>
                <td><strong>${escapeHtml(rec.settlement || 'Невідомо')}</strong></td>
                <td style="${typeStyle}">${escapeHtml(rec.type || 'Невідомо')}</td>
                <td>${escapeHtml(dtStart)} - ${escapeHtml(dtEnd)}</td>
                <td>${streetsHtml}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }
    container.innerHTML = html;
}

function renderAnalytics(container) {
    if (window.analyticsData && window.analyticsData.content) {
        container.innerHTML = `
            <h3>🤖 Щотижнева аналітика від ШІ</h3>
            <div style="margin-top: 20px; padding: 20px; background: var(--bg); border: 1px solid var(--primary); border-radius: var(--radius);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 10px;">
                    <span style="font-size:12px; color:#888;">Сформовано: ${escapeHtml(window.analyticsData.date)}</span>
                </div>
                <div style="font-size:14px; line-height:1.6; white-space:pre-wrap;">${escapeHtml(window.analyticsData.content)}</div>
                <button class="btn btn-primary" style="margin-top:15px;" onclick="copyToClipboard(this.previousElementSibling.innerText)">📋 Копіювати для Telegram</button>
            </div>
            <p style="margin-top: 20px; font-size: 13px; color: #666;">
                <i>* Візуалізація та розширена аналітика знаходяться в процесі розробки.</i>
            </p>
        `;
    } else {
        container.innerHTML = `<h3>Аналітика</h3><p class="empty">Немає даних для аналітики або звіт ще не сформований.</p>`;
    }
}

function renderStreets(container) {
    let allStreets = new Set();
    archiveOutages.forEach(rec => {
        if (rec.streets_detailed) {
            rec.streets_detailed.forEach(s => allStreets.add(s.name.trim()));
        } else if (rec.streets) {
            rec.streets.forEach(s => allStreets.add(s.trim()));
        }
    });

    let streetsArray = Array.from(allStreets).sort();
    
    // Розділяємо на офіційні та сумнівні
    let official = [];
    let doubtful = [];
    
    if (officialStreets && officialStreets.length > 0) {
        streetsArray.forEach(street => {
            if (officialStreets.includes(street)) {
                official.push(street);
            } else {
                doubtful.push(street);
            }
        });
    } else {
        // Якщо довідник не завантажився або порожній, всі йдуть в сумнівні
        doubtful = streetsArray;
    }
    
    let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 15px;">
            <h3>Словник вулиць (${streetsArray.length} знайдено)</h3>
            <input type="text" id="streetSearch" placeholder="Пошук вулиці..." onkeyup="filterStreets()" style="padding: 8px; border-radius: 4px; border: 1px solid var(--border); background: var(--bg); color: var(--text); width: 250px;">
        </div>
        <p style="font-size: 13px; color: #888; margin-bottom: 20px;">
            Увага! Щоб перевести вулицю в "Сумнівні", видаліть її з файлу <code>data/official_streets.json</code> на GitHub.
        </p>
    `;

    if (streetsArray.length === 0) {
        html += '<p class="empty">Немає зібраних даних про вулиці (архів порожній).</p>';
    } else {
        html += `<div style="display: flex; gap: 20px; align-items: flex-start;">`;
        
        // Блок Офіційних
        html += `<div style="flex: 1; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg); padding: 15px;">
            <h4 style="margin-top: 0; color: #28a745;">✅ Офіційні вулиці (${official.length})</h4>
            <ul class="streets-list" style="list-style-type: none; padding: 0; max-height: 500px; overflow-y: auto;">`;
        official.forEach(street => {
            html += `<li style="padding: 8px 10px; border-bottom: 1px solid var(--border); font-size: 14px;">${escapeHtml(street)}</li>`;
        });
        html += `</ul></div>`;
        
        // Блок Сумнівних
        html += `<div style="flex: 1; border: 1px solid var(--danger); border-radius: var(--radius); background: #fff5f5; padding: 15px;">
            <h4 style="margin-top: 0; color: var(--danger);">⚠️ Сумнівні вулиці (${doubtful.length})</h4>
            <ul class="streets-list" style="list-style-type: none; padding: 0; max-height: 500px; overflow-y: auto;">`;
        if (doubtful.length === 0) {
            html += `<p style="font-size:13px; color:#666;">Немає сумнівних вулиць. Усі вулиці є в довіднику.</p>`;
        } else {
            doubtful.forEach(street => {
                html += `<li style="padding: 8px 10px; border-bottom: 1px solid #ffdcdc; font-size: 14px; color: var(--danger);"><strong>${escapeHtml(street)}</strong></li>`;
            });
        }
        html += `</ul></div>`;
        
        html += `</div>`;
    }
    
    // Додаємо скрипт для пошуку в window
    if (!window.filterStreets) {
        window.filterStreets = function() {
            let input = document.getElementById("streetSearch").value.toLowerCase();
            let lis = document.querySelectorAll(".streets-list li");
            lis.forEach(li => {
                let txtValue = li.textContent || li.innerText;
                if (txtValue.toLowerCase().indexOf(input) > -1) {
                    li.style.display = "";
                } else {
                    li.style.display = "none";
                }
            });
        };
    }

    container.innerHTML = html;
}

function renderStatus() {
    const area = document.getElementById('statusArea');
    if (!area) return;
    if (updateLog.length === 0) {
        area.innerHTML = '<div class="status-bar status-ok">🟢 Немає даних логу.</div>';
        return;
    }
    const last = updateLog[updateLog.length - 1];
    let statusClass = 'status-ok';
    let icon = '🟢';
    let text = 'Система працює.';
    if (last.status === 'html_structure_error' || last.status === 'http_error') {
        statusClass = 'status-error';
        icon = '🔴';
        text = `Помилка: ${escapeHtml(last.message || last.status)}.`;
    } else {
        text = `Остання перевірка: ${escapeHtml(last.timestamp)}.`;
    }
    area.innerHTML = `<div class="status-bar ${statusClass}">${icon} ${text}</div>`;
}

window.copyToClipboard = function(text) {
    navigator.clipboard.writeText(text).then(() => alert('Скопійовано!'));
}

// Запуск
if (typeof ADMIN_HASH === 'undefined') {
    app.innerHTML = '<p style="color:red;">Помилка: auth_config.js не налаштовано. Запустіть formatter.py для ініціалізації.</p>';
} else {
    login();
}
document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && document.getElementById('passInput')) {
        checkPassword();
    }
});
