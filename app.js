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
let feedData = { current_feed: "", last_updated: "", days: [], anomalies_log: [] };
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

        try {
            const feedResp = await fetch(`data/feed.json?t=${Date.now()}`);
            if (feedResp.ok) feedData = await feedResp.json();
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
    // 1. Отримуємо актуальні дані для поточного дня та наступного
    const todayStr = feedData.current_feed || 'Дані відсутні';
    
    // Для завтра шукаємо в масиві days
    const tomorrowDateStr = new Date(Date.now() + 86400000).toLocaleDateString('en-CA');
    const tomorrowDayObj = feedData.days && feedData.days.find(d => d.date === tomorrowDateStr);
    const tomorrowStr = tomorrowDayObj ? tomorrowDayObj.actual_content : 'Дані відсутні';

    let html = `
        <h3>Стрічка новин (Актуальна)</h3>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 15px;">
            <div>
                <h4 style="margin-bottom: 8px;">Стрічка на сьогодні (Актуальна)</h4>
                <textarea class="feed-textarea" style="height: 120px;" readonly>${escapeHtml(todayStr)}</textarea>
                <button class="btn btn-primary" onclick="copyToClipboard(this.previousElementSibling.value)">📋 Копіювати текст</button>
            </div>
            <div>
                <h4 style="margin-bottom: 8px;">Стрічка на завтра (Планова)</h4>
                <textarea class="feed-textarea" style="height: 120px;" readonly>${escapeHtml(tomorrowStr)}</textarea>
                <button class="btn btn-primary" onclick="copyToClipboard(this.previousElementSibling.value)">📋 Копіювати текст</button>
            </div>
        </div>

        <h4 class="feed-section-title">Тижнева сітка стрічки новин (7 днів)</h4>
        <p style="font-size: 13px; color: var(--secondary-text); margin-bottom: 15px;">
            Натисніть на картку будь-якого дня, щоб переглянути повний текст, історію змін або внести ручні правки.
        </p>
        <div class="feed-grid">
    `;

    // 2. Будуємо 7 карток
    const daysOfWeek = ['Неділя', 'Понеділок', 'Вівторок', 'Середа', 'Четвер', 'П’ятниця', 'Субота'];
    const todayStr_local = new Date().toLocaleDateString('en-CA');
    
    if (feedData.days && feedData.days.length > 0) {
        feedData.days.forEach(day => {
            const dateObj = new Date(day.date);
            const weekday = daysOfWeek[dateObj.getDay()];
            const formattedDate = dateObj.toLocaleDateString('uk-UA', { day: 'numeric', month: 'long' });
            
            // Визначаємо статус
            let statusText = "Немає відключень";
            let badgeClass = "badge-success";
            
            if (day.actual_content.includes("Немає даних")) {
                statusText = "Немає даних";
                badgeClass = "badge-secondary";
            } else if (day.actual_content.includes("Планові знеструмлення") || day.actual_content.includes("Аварійні знеструмлення")) {
                statusText = "Є відключення";
                badgeClass = "badge-danger";
            }
            
            const historyCount = day.history ? day.history.length : 0;
            const cleanContent = day.actual_content;
            
            html += `
                <div class="feed-card" onclick="openFeedDayDetails('${day.date}')">
                    <div>
                        <div class="feed-card-header">
                            <div>
                                <div class="feed-card-title">${escapeHtml(weekday)}</div>
                                <div class="feed-card-subtitle">${escapeHtml(formattedDate)}</div>
                            </div>
                            <span class="feed-card-badge ${badgeClass}">${statusText}</span>
                        </div>
                        <div class="feed-card-body">${escapeHtml(cleanContent)}</div>
                    </div>
                    <div class="feed-card-footer">
                        <span>Дата: ${day.date}</span>
                        <span class="feed-card-changes">${historyCount} верс.</span>
                    </div>
                </div>
            `;
        });
    } else {
        html += `<div class="empty" style="grid-column: 1/-1; padding: 20px; text-align: center;">Дані тижневої сітки відсутні. Спробуйте запустити парсер.</div>`;
    }

    html += `</div>`;

    // 3. Блок статистики аномалій
    const anomaliesThisWeek = feedData.anomalies_log ? feedData.anomalies_log.length : 0;
    html += `
        <h4 class="feed-section-title">Аналітика раптових змін (Аномалій) за тиждень</h4>
        <div class="dashboard-widgets" style="margin-top: 10px;">
            <div class="widget">
                <div class="widget-title">Раптові зміни протягом доби</div>
                <div class="widget-value ${anomaliesThisWeek > 0 ? 'warning' : ''}">${anomaliesThisWeek}</div>
            </div>
            <div class="widget" style="grid-column: span 2;">
                <div class="widget-title">Статус телеметрії</div>
                <div class="widget-value" style="font-size: 16px; margin-top: 10px; font-weight: normal; text-align: left;">
                    Останнє оновлення стрічки: <strong>${feedData.last_updated ? new Date(feedData.last_updated).toLocaleString('uk-UA') : 'Невідомо'}</strong>.<br>
                    Стрічка оновлюється автоматично кожні 2 години на GitHub Actions.
                </div>
            </div>
        </div>
    `;

    if (feedData.anomalies_log && feedData.anomalies_log.length > 0) {
        html += `
            <h5>Журнал раптових змін (Останні оновлення):</h5>
            <div class="anomalies-list">
        `;
        // Показуємо останні 10 логів
        [...feedData.anomalies_log].reverse().slice(0, 10).forEach(log => {
            const logTime = new Date(log.timestamp).toLocaleString('uk-UA');
            const oldText = log.old_text || '';
            const newText = log.new_text || '';
            html += `
                <div class="anomaly-log-item">
                    <div class="anomaly-log-meta">📅 Дата події: ${log.date} | ⏱ Зафіксовано: ${logTime}</div>
                    <div class="anomaly-log-diff">
                        <div class="diff-old">Було: ${escapeHtml(oldText)}</div>
                        <div class="diff-new">Стало: ${escapeHtml(newText)}</div>
                    </div>
                </div>
            `;
        });
        html += `</div>`;
    } else {
        html += `<p style="font-size: 13px; color: var(--secondary-text); font-style: italic; margin-top: 10px;">Аномальних (раптових) змін у стрічці протягом тижня не зафіксовано. Обленерго працює за планом.</p>`;
    }

    container.innerHTML = html;

    // 4. Оголошуємо функції відкриття деталей дня в глобальній області
    if (!window.openFeedDayDetails) {
        window.openFeedDayDetails = function(dateStr) {
            const day = feedData.days.find(d => d.date === dateStr);
            if (!day) return;

            const modalOverlay = document.createElement('div');
            modalOverlay.className = 'feed-modal-overlay';
            modalOverlay.id = 'feedDayModal';

            const dateObj = new Date(day.date);
            const formattedDate = dateObj.toLocaleDateString('uk-UA', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

            let historyHtml = '';
            if (day.history && day.history.length > 0) {
                [...day.history].reverse().forEach(h => {
                    const time = new Date(h.timestamp).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
                    const date = new Date(h.timestamp).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit' });
                    let badge = '';
                    if (h.is_anomaly) badge = '<span class="feed-history-badge">Аномалія</span>';
                    if (h.is_manual_edit) badge = '<span class="feed-history-badge manual">Вручну</span>';
                    
                    historyHtml += `
                        <div class="feed-history-item">
                            <div class="feed-history-meta">
                                <span>📅 ${date} о ${time}</span>
                                ${badge}
                            </div>
                            <div>${escapeHtml(h.content)}</div>
                        </div>
                    `;
                });
            } else {
                historyHtml = '<div style="font-size: 13px; color: var(--secondary-text); font-style: italic;">Історія змін відсутня.</div>';
            }

            modalOverlay.innerHTML = `
                <div class="feed-modal">
                    <div class="feed-modal-header">
                        <h3>Стрічка: ${escapeHtml(formattedDate)}</h3>
                        <button class="feed-modal-close" onclick="closeFeedModal()">&times;</button>
                    </div>
                    <div class="feed-modal-body">
                        <label style="font-size: 13px; font-weight: bold; display: block; margin-bottom: 6px;">Редагувати текст стрічки:</label>
                        <textarea id="editFeedText" class="feed-textarea" style="height: 110px; margin-bottom: 12px; font-family: sans-serif;">${escapeHtml(day.actual_content)}</textarea>
                        
                        <div class="feed-history-title">Історія версій та авто-оновлень дня:</div>
                        <div class="feed-history-list">
                            ${historyHtml}
                        </div>
                    </div>
                    <div class="feed-modal-footer">
                        <button class="btn" style="background:#ccc; color:#333;" onclick="closeFeedModal()">Скасувати</button>
                        <button class="btn btn-primary" onclick="saveFeedDayChanges('${day.date}')">💾 Зберегти зміни на GitHub</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modalOverlay);
        };
    }

    if (!window.closeFeedModal) {
        window.closeFeedModal = function() {
            const modal = document.getElementById('feedDayModal');
            if (modal) modal.remove();
        };
    }

    if (!window.saveFeedDayChanges) {
        window.saveFeedDayChanges = function(dateStr) {
            const newText = document.getElementById('editFeedText').value.trim();
            if (!newText) {
                alert('Текст не може бути порожнім!');
                return;
            }

            const day = feedData.days.find(d => d.date === dateStr);
            if (!day) return;

            // Зберігаємо нову версію
            day.actual_content = newText;
            if (!day.history) day.history = [];
            
            day.history.push({
                timestamp: new Date().toISOString(),
                content: newText,
                is_anomaly: false,
                is_manual_edit: true
            });

            // Динамічно оновлюємо головну стрічку, якщо редагували Сьогодні чи Завтра
            const todayDateStr = new Date().toLocaleDateString('en-CA');
            const tomorrowDateStr = new Date(Date.now() + 86400000).toLocaleDateString('en-CA');
            
            let todayObj = feedData.days.find(d => d.date === todayDateStr);
            let tomorrowObj = feedData.days.find(d => d.date === tomorrowDateStr);
            
            let currentParts = [];
            if (todayObj && todayObj.actual_content) {
                let cleanToday = todayObj.actual_content.replace(/^\[СЬОГОДНІ\]\s*/, "");
                currentParts.push(cleanToday);
            }
            if (tomorrowObj && tomorrowObj.actual_content) currentParts.push(tomorrowObj.actual_content);
            
            feedData.current_feed = currentParts.join(" | ");
            feedData.last_updated = new Date().toISOString();

            // Копіюємо JSON в буфер і пропонуємо користувачу зберегти його на GitHub
            const jsonStr = JSON.stringify(feedData, null, 2);
            navigator.clipboard.writeText(jsonStr).then(() => {
                alert('✅ Дані оновлено та новий файл feed.json скопійовано в буфер обміну!\n\nЗараз відкриється сторінка редагування на GitHub.\nВставте туди скопійований текст (Ctrl+V) і натисніть "Commit changes".');
                closeFeedModal();
                window.open('https://github.com/realtomchuk-source/OutagesSk/edit/main/data/feed.json', '_blank');
                // Перемальовуємо поточну вкладку
                renderFeed(document.getElementById('tabContent'));
            }).catch(err => {
                alert('Помилка копіювання в буфер: ' + err);
            });
        };
    }
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
            <div>
                <input type="text" id="streetSearch" placeholder="Пошук вулиці..." onkeyup="filterStreets()" style="padding: 8px; border-radius: 4px; border: 1px solid var(--border); background: var(--bg); color: var(--text); width: 250px; margin-right: 10px;">
                <button class="btn btn-primary" onclick="saveStreetsToGitHub()" style="background-color: #28a745;">💾 Зберегти зміни на GitHub</button>
            </div>
        </div>
        <p style="font-size: 13px; color: #888; margin-bottom: 20px;">
            Керуйте списком прямо тут. Натисніть "Обілити", щоб перенести вулицю до офіційного словника. Потім обов'язково натисніть "Зберегти зміни".
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
            html += `<li style="display:flex; justify-content:space-between; align-items:center; padding: 8px 10px; border-bottom: 1px solid var(--border); font-size: 14px;">
                <span>${escapeHtml(street)}</span>
                <button onclick="toggleStreetStatus('${escapeHtml(street).replace(/'/g, "\\'")}', false)" style="background:transparent; border:none; cursor:pointer; font-size:16px;" title="В сумнівні">❌</button>
            </li>`;
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
                html += `<li style="display:flex; justify-content:space-between; align-items:center; padding: 8px 10px; border-bottom: 1px solid #ffdcdc; font-size: 14px; color: var(--danger);">
                    <strong>${escapeHtml(street)}</strong>
                    <button onclick="toggleStreetStatus('${escapeHtml(street).replace(/'/g, "\\'")}', true)" class="btn" style="padding:4px 8px; font-size:12px; background:var(--bg); border:1px solid #ccc; color:#333;">✅ Обілити</button>
                </li>`;
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
                // Видаляємо текст кнопок при пошуку
                txtValue = txtValue.replace('✅ Обілити', '').replace('❌', '');
                if (txtValue.toLowerCase().indexOf(input) > -1) {
                    li.style.display = "";
                } else {
                    li.style.display = "none";
                }
            });
        };
    }

    if (!window.toggleStreetStatus) {
        window.toggleStreetStatus = function(street, toOfficial) {
            if (toOfficial) {
                if (!officialStreets.includes(street)) {
                    officialStreets.push(street);
                }
            } else {
                officialStreets = officialStreets.filter(s => s !== street);
            }
            officialStreets.sort();
            renderStreets(document.getElementById('tabContent'));
        };
    }

    if (!window.saveStreetsToGitHub) {
        window.saveStreetsToGitHub = function() {
            const jsonStr = JSON.stringify(officialStreets, null, 2);
            navigator.clipboard.writeText(jsonStr).then(() => {
                alert('✅ Новий словник скопійовано в буфер обміну!\n\nЗараз відкриється сторінка редагування на GitHub.\nВставте туди скопійований текст (Ctrl+V) і натисніть "Commit changes".');
                window.open('https://github.com/realtomchuk-source/OutagesSk/edit/main/data/official_streets.json', '_blank');
            }).catch(err => {
                alert('Помилка копіювання: ' + err);
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
