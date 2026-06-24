const app = document.getElementById('app');

const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:';
const API_BASE = (window.location.protocol === 'file:') ? 'http://localhost:8000' : '';

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

function formatDateISO(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function formatDateTimeParts(ts) {
    if (!ts) return { date: '-', time: '-', full: '-' };
    const m = ts.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
    if (m) {
        const [, year, month, day, hour, minute] = m;
        return {
            date: `${day}.${month}`,
            time: `${hour}:${minute}`,
            full: `${day}.${month}.${year} о ${hour}:${minute}`
        };
    }
    try {
        const d = new Date(ts);
        if (isNaN(d.getTime())) return { date: ts, time: ts, full: ts };
        const dateStr = String(d.getDate()).padStart(2, '0') + '.' + String(d.getMonth() + 1).padStart(2, '0');
        const timeStr = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
        const year = d.getFullYear();
        return {
            date: dateStr,
            time: timeStr,
            full: `${dateStr}.${year} о ${timeStr}`
        };
    } catch (e) {
        return { date: ts, time: ts, full: ts };
    }
}

async function commitFileToGitHub(filePath, content, commitMessage) {
    if (isLocalhost) {
        try {
            const response = await fetch(`${API_BASE}/api/save`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ filePath, content })
            });
            const resData = await response.json();
            if (response.ok && resData.status === 'ok') {
                alert(`✅ Зміни успішно збережено локально у файл: ${filePath}`);
                return true;
            } else {
                throw new Error(resData.message || 'Unknown error');
            }
        } catch (err) {
            console.error('Local save failed, falling back to clipboard + GitHub:', err);
            fallbackSaveToClipboard(filePath, content);
            return false;
        }
    } else {
        const token = localStorage.getItem('github_pat_token');
        if (token) {
            try {
                const refUrl = `https://api.github.com/repos/realtomchuk-source/OutagesSk/contents/${filePath}`;
                const getResp = await fetch(refUrl, {
                    headers: { 'Authorization': `token ${token}` }
                });
                let sha = '';
                if (getResp.ok) {
                    const fileData = await getResp.json();
                    sha = fileData.sha;
                } else if (getResp.status !== 404) {
                    throw new Error(`Failed to get file SHA (status ${getResp.status})`);
                }
                
                const utf8Bytes = new TextEncoder().encode(content);
                let binString = '';
                for (let i = 0; i < utf8Bytes.length; i++) {
                    binString += String.fromCharCode(utf8Bytes[i]);
                }
                const b64Content = btoa(binString);

                const putBody = {
                    message: commitMessage || `Оновлення ${filePath}`,
                    content: b64Content
                };
                if (sha) {
                    putBody.sha = sha;
                }

                const putResp = await fetch(refUrl, {
                    method: 'PUT',
                    headers: {
                        'Authorization': `token ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(putBody)
                });
                
                if (putResp.ok) {
                    alert(`✅ Зміни успішно опубліковано на GitHub через API!`);
                    return true;
                } else {
                    const errData = await putResp.json();
                    throw new Error(errData.message || `API error ${putResp.status}`);
                }
            } catch (err) {
                console.error('GitHub API save failed, falling back to clipboard:', err);
                alert('Помилка збереження через API: ' + err.message + '\n\nПереходимо до резервного копіювання в буфер.');
                fallbackSaveToClipboard(filePath, content);
                return false;
            }
        } else {
            fallbackSaveToClipboard(filePath, content);
            return false;
        }
    }
}

function fallbackSaveToClipboard(filePath, content) {
    navigator.clipboard.writeText(content).then(() => {
        alert(`✅ Дані скопійовано в буфер обміну!\n\nВставте їх у файл ${filePath} на GitHub.`);
        window.open(`https://github.com/realtomchuk-source/OutagesSk/edit/main/${filePath}`, '_blank');
    }).catch(err => {
        alert('Помилка копіювання в буфер: ' + err);
    });
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

window.savePatToken = function() {
    const val = document.getElementById('patTokenInput').value.trim();
    if (val) {
        localStorage.setItem('github_pat_token', val);
        alert('✅ GitHub PAT Token збережено!');
    } else {
        localStorage.removeItem('github_pat_token');
        alert('ℹ️ GitHub PAT Token видалено з пам\'яті.');
    }
};

window.showPatInstructions = function() {
    const modalOverlay = document.createElement('div');
    modalOverlay.className = 'feed-modal-overlay';
    modalOverlay.id = 'patInstructionsModal';
    modalOverlay.innerHTML = `
        <div class="feed-modal" style="max-width: 500px;">
            <div class="feed-modal-header">
                <h3>Як налаштувати GitHub PAT Token?</h3>
                <button class="feed-modal-close" onclick="window.closePatInstructions()">&times;</button>
            </div>
            <div class="feed-modal-body" style="font-size: 14px; line-height: 1.5; max-height: 400px; overflow-y: auto;">
                <p>Personal Access Token (PAT) необхідний для прямої публікації змін у файлах на GitHub з адмін-панелі без використання ручного копіювання в буфер обміну.</p>
                <ol style="padding-left: 20px; margin-top: 10px;">
                    <li>Перейдіть на сторінку створення токенів: <br><a href="https://github.com/settings/tokens/new" target="_blank" style="color:#007bff; font-weight:bold;">GitHub -> Personal Access Tokens (Classic)</a></li>
                    <li>Вкажіть назву (наприклад, <code>Outages-Admin</code>).</li>
                    <li>Виберіть термін дії (Expiration) на ваш розсуд (наприклад, 90 днів).</li>
                    <li>У списку дозволів (Scopes) обов'язково позначте галочку <strong>repo</strong> (повний контроль репозиторіїв).</li>
                    <li>Прокрутіть сторінку до самого низу і натисніть кнопку <strong>Generate token</strong>.</li>
                    <li>Скопіюйте згенерований токен (він починається з <code>ghp_</code>). <em>Увага: ви більше не зможете його побачити на GitHub після закриття сторінки!</em></li>
                    <li>Вставте скопійований токен у поле <strong>GitHub Token</strong> в адмінці та натисніть <strong>Зберегти</strong>.</li>
                </ol>
            </div>
            <div class="feed-modal-footer">
                <button class="btn btn-primary" onclick="window.closePatInstructions()">Зрозуміло</button>
            </div>
        </div>
    `;
    document.body.appendChild(modalOverlay);
};

window.closePatInstructions = function() {
    const modal = document.getElementById('patInstructionsModal');
    if (modal) modal.remove();
};

window.gitPublishToGitHub = async function() {
    const btn = document.querySelector('button[onclick="window.gitPublishToGitHub()"]');
    const oldText = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ Публікація...';
    }
    try {
        const response = await fetch(`${API_BASE}/api/git_push`, { method: 'POST' });
        const data = await response.json();
        if (response.ok && data.status === 'ok') {
            alert('✅ Зміни успішно закоммічено та відправлено на GitHub!');
        } else {
            alert('❌ Помилка публікації: ' + (data.message || 'Unknown error'));
        }
    } catch (err) {
        alert('❌ Помилка з\'єднання з локальним сервером: ' + err);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = oldText;
        }
    }
};

async function showDashboard() {
    const tokenVal = localStorage.getItem('github_pat_token') || '';
    const tokenInputHtml = `
        <div style="display:flex; align-items:center; gap:5px; font-size:13px; background: rgba(0,0,0,0.02); padding: 5px 10px; border-radius: 4px; border: 1px solid var(--border);">
            <label style="font-weight:bold; color:var(--text);">GitHub Token:</label>
            <input type="password" id="patTokenInput" value="${escapeHtml(tokenVal)}" placeholder="ghp_..." style="padding: 4px 6px; border: 1px solid var(--border); border-radius: 3px; width: 120px; font-size: 12px; background:var(--bg); color:var(--text);">
            <button onclick="window.savePatToken()" style="padding: 4px 8px; font-size:12px; border-radius: 3px; cursor:pointer;" class="btn">Зберегти</button>
            <button onclick="window.showPatInstructions()" style="background:none; border:none; cursor:pointer; font-size:16px;" title="Інструкція">ℹ️</button>
        </div>
    `;

    const publishBtn = isLocalhost ? `
        <button class="btn btn-primary" onclick="window.gitPublishToGitHub()" style="background-color: #17a2b8; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; cursor: pointer; color: white;">🚀 Опублікувати на GitHub</button>
    ` : '';

    app.innerHTML = `
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:15px; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 15px;">
                <h2 style="margin:0;">Адмінка – Starokostiantyniv Outage Monitor</h2>
                <div style="display:flex; align-items:center; gap:15px; flex-wrap:wrap;">
                    ${tokenInputHtml}
                    ${publishBtn}
                </div>
            </div>
            <div id="dashboardWidgets"></div>
            <div class="tabs">
                <button class="tab active" onclick="switchTab('feed')">Стрічка</button>
                <button class="tab" onclick="switchTab('telegram')">Telegram</button>
                <button class="tab" onclick="switchTab('analytics')">Аналітика</button>
                <button class="tab" onclick="switchTab('streets')">Вулиці (Словник)</button>
                <button class="tab" onclick="switchTab('archive')">Архів відключень</button>
                <button class="tab" onclick="switchTab('msg_archive')">Архів повідомлень</button>
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
let officialStreets = {};
window.streetCorrections = {};
window.addressChangelog = [];
let selectedSettlement = "м. Старокостянтинів";
window.selectedStreet = "";
window.showRawJson = false;

function migrateStreetsStructure(raw) {
    if (Array.isArray(raw)) {
        const migrated = { "м. Старокостянтинів": {} };
        raw.forEach(street => {
            migrated["м. Старокостянтинів"][street] = {
                type: street.toLowerCase().includes("пров") ? "провулок" : "вулиця",
                houses: [],
                blacklist: []
            };
        });
        return migrated;
    }
    for (const sett in raw) {
        for (const str in raw[sett]) {
            if (!raw[sett][str].houses) {
                raw[sett][str].houses = [];
            } else {
                // Видаляємо дублікати та зайві пробіли
                raw[sett][str].houses = Array.from(new Set(raw[sett][str].houses.map(h => String(h).trim()).filter(h => h.length > 0)));
            }
            if (!raw[sett][str].blacklist) {
                raw[sett][str].blacklist = [];
            } else {
                // Також чистимо чорний список
                raw[sett][str].blacklist = Array.from(new Set(raw[sett][str].blacklist.map(h => String(h).trim()).filter(h => h.length > 0)));
            }
        }
    }
    return raw;
}

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
            if (offResp.ok) {
                const rawOff = await offResp.json();
                officialStreets = migrateStreetsStructure(rawOff);
            }
        } catch(e) {}

        try {
            const feedResp = await fetch(`data/feed.json?t=${Date.now()}`);
            if (feedResp.ok) {
                feedData = await feedResp.json();
            } else {
                console.error(`Failed to fetch feed.json: ${feedResp.status} ${feedResp.statusText}`);
            }
        } catch(e) {
            console.error("Error loading feed.json:", e);
        }

        try {
            const corrResp = await fetch(`data/street_corrections.json?t=${Date.now()}`);
            if (corrResp.ok) {
                window.streetCorrections = await corrResp.json();
            } else {
                window.streetCorrections = {};
            }
        } catch(e) { window.streetCorrections = {}; }

        try {
            const changeResp = await fetch(`data/address_changelog.json?t=${Date.now()}`);
            if (changeResp.ok) {
                window.addressChangelog = await changeResp.json();
            } else {
                window.addressChangelog = [];
            }
        } catch(e) { window.addressChangelog = []; }

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
        lastUpdate = formatDateTimeParts(updateLog[updateLog.length - 1].timestamp).full;
    }
    
    let activePlanned = rawOutages.filter(r => r.type && r.type.includes('Планові')).length;
    let activeEmergency = rawOutages.filter(r => r.type && r.type.includes('Аварійні')).length;
    let settlements = new Set(rawOutages.map(r => r.settlement)).size;

    document.getElementById('dashboardWidgets').innerHTML = `
        <div class="dashboard-widgets">
            <div class="widget">
                <div class="widget-title">Останнє оновлення</div>
                <div class="widget-value" style="font-size:14px; padding-top:6px;">${escapeHtml(lastUpdate)}</div>
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
                <div class="widget-title">Населених пунктів под впливом</div>
                <div class="widget-value info">${settlements}</div>
            </div>
        </div>`;
}

window.switchTab = function(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(t => {
        t.classList.toggle('active', 
            (tab === 'feed' && t.textContent.includes('Стрічка')) ||
            (tab === 'telegram' && t.textContent === 'Telegram') ||
            (tab === 'analytics' && t.textContent === 'Аналітика') ||
            (tab === 'streets' && t.textContent.includes('Вулиці')) ||
            (tab === 'archive' && t.textContent.includes('Архів відключень')) ||
            (tab === 'msg_archive' && t.textContent.includes('Архів повідомлень')) ||
            (tab === 'raw' && t.textContent.includes('Сирі дані'))
        );
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
    else if (tab === 'msg_archive') renderMsgArchive(container);
    else if (tab === 'raw') renderRaw(container);
}

function getFeedContent(type) {
    const msg = messages.find(m => m.type === type);
    return msg ? msg.content : 'Дані відсутні';
}

function renderFeed(container) {
    const todayStr = feedData.current_feed || 'Дані відсутні';
    
    const tomorrowDateStr = formatDateISO(new Date(Date.now() + 86400000));
    const tomorrowDayObj = feedData.days && feedData.days.find(d => d.date === tomorrowDateStr);
    const tomorrowStr = tomorrowDayObj ? tomorrowDayObj.actual_content : 'Дані відсутні';

    const todayStr_local = formatDateISO(new Date());

    let html = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 15px;">
            <div>
                <h4 style="margin-bottom: 8px;">Стрічка новин на сьогодні (Актуальна)</h4>
                <textarea class="feed-textarea" style="height: 120px;" readonly>${escapeHtml(todayStr)}</textarea>
                <div style="display: flex; gap: 10px; margin-top: 8px; align-items: center; justify-content: space-between;">
                    <div style="display: flex; gap: 10px;">
                        <button class="btn btn-primary" onclick="copyToClipboard(this.parentElement.parentElement.previousElementSibling.value)">📋 Копіювати текст</button>
                        <button class="btn btn-secondary" style="background:#007bff; color:white; border:none;" onclick="window.openFeedDayDetails('${todayStr_local}')">✏️ Редагувати</button>
                    </div>
                    <span style="font-size: 13px; color: var(--secondary-text);">Символів: <strong>${todayStr.length}</strong></span>
                </div>
            </div>
            <div>
                <h4 style="margin-bottom: 8px;">Стрічка новин на завтра (Планова)</h4>
                <textarea class="feed-textarea" style="height: 120px;" readonly>${escapeHtml(tomorrowStr)}</textarea>
                <div style="display: flex; gap: 10px; margin-top: 8px; align-items: center; justify-content: space-between;">
                    <button class="btn btn-primary" onclick="copyToClipboard(this.parentElement.previousElementSibling.value)">📋 Копіювати текст</button>
                    <span style="font-size: 13px; color: var(--secondary-text);">Символів: <strong>${tomorrowStr.length}</strong></span>
                </div>
            </div>
        </div>

        <h4 class="feed-section-title">Тижнева сітка стрічки новин (7 днів)</h4>
        <p style="font-size: 13px; color: var(--secondary-text); margin-bottom: 15px;">
            Натисніть на картку будь-якого дня, щоб переглянути повний текст, історію змін або внести ручні правки.
        </p>
        <div class="feed-grid">
    `;

    const daysOfWeek = ['Неділя', 'Понеділок', 'Вівторок', 'Середа', 'Четвер', 'П’ятниця', 'Субота'];
    
    if (feedData.days && feedData.days.length > 0) {
        feedData.days.forEach(day => {
            const dateObj = new Date(day.date);
            const weekday = daysOfWeek[dateObj.getDay()];
            const formattedDate = dateObj.toLocaleDateString('uk-UA', { day: 'numeric', month: 'long' });
            
            let statusText = "Немає відключень";
            let badgeClass = "badge-success";
            
            if (day.actual_content.includes("Немає даних")) {
                statusText = "Немає даних";
                badgeClass = "badge-secondary";
            } else if (day.actual_content.includes("Планові") || day.actual_content.includes("Аварійні")) {
                statusText = "Є відключення";
                badgeClass = "badge-danger";
            }
            
            const historyCount = day.history ? day.history.length : 0;
            const cleanContent = day.actual_content;
            const baselineInfo = day.baseline_created_at ? `<span class="feed-card-baseline" title="Стартова база сформована" style="color:var(--success-color); font-size:12px; font-weight:bold; margin-left: 8px;">⏱ База: ${escapeHtml(day.baseline_created_at)}</span>` : '';
            
            html += `
                <div class="feed-card" onclick="window.openFeedDayDetails('${day.date}')">
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
                    <div class="feed-card-footer" style="display:flex; justify-content:space-between; align-items:center;">
                        <span>Дата: ${day.date} ${baselineInfo}</span>
                        <span class="feed-card-changes">${historyCount} верс.</span>
                    </div>
                </div>
            `;
        });
    } else {
        html += `<div class="empty" style="grid-column: 1/-1; padding: 20px; text-align: center;">Дані тижневої сітки відсутні. Спробуйте запустити парсер.</div>`;
    }

    html += `</div>`;

    const anomaliesThisWeek = feedData.anomalies_log ? feedData.anomalies_log.length : 0;
    const todayDayObj = feedData.days && feedData.days.find(d => d.date === todayStr_local);
    const baselineTimeStr = todayDayObj && todayDayObj.baseline_created_at ? todayDayObj.baseline_created_at : 'немає даних';
    
    html += `
        <h4 class="feed-section-title">Аналітика раптових змін (Аномалій) за тиждень</h4>
        <div class="dashboard-widgets" style="margin-top: 10px;">
            <div class="widget">
                <div class="widget-title">Раптові зміни протягом доби</div>
                <div class="widget-value ${anomaliesThisWeek > 0 ? 'warning' : ''}">${anomaliesThisWeek}</div>
            </div>
            <div class="widget" style="grid-column: span 3;">
                <div class="widget-title">Статус телеметрії</div>
                <div class="widget-value" style="font-size: 14px; margin-top: 8px; font-weight: normal; text-align: left; line-height: 1.4;">
                    Останнє оновлення стрічки: <strong>${feedData.last_updated ? new Date(feedData.last_updated).toLocaleString('uk-UA') : 'Невідомо'}</strong>.<br>
                    Стартова база на сьогодні сформована о: <strong>${escapeHtml(baselineTimeStr)}</strong> (в проміжку 23:00-01:00).<br>
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

    if (!window.openFeedDayDetails) {
        window.openFeedDayDetails = function(dateStr) {
            let day = feedData.days.find(d => d.date === dateStr);
            if (!day) {
                day = {
                    date: dateStr,
                    planned_content: "",
                    actual_content: "Немає даних",
                    history: []
                };
                feedData.days.push(day);
                feedData.days.sort((a, b) => a.date.localeCompare(b.date));
            }

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

            const baselineText = day.baseline_created_at ? 
                `<div style="font-size: 13px; color: var(--success-color); margin-top: 5px; font-weight: bold; background: rgba(40,167,69,0.1); padding: 8px; border-radius: 4px; border: 1px solid rgba(40,167,69,0.2);">⏱ Стартову базу для цієї доби сформовано о ${escapeHtml(day.baseline_created_at)} (в проміжку 23:00-01:00)</div>` : 
                `<div style="font-size: 13px; color: var(--secondary-text); margin-top: 5px; font-style: italic; background: rgba(0,0,0,0.02); padding: 8px; border-radius: 4px; border: 1px solid rgba(0,0,0,0.05);">⏱ Стартову базу для цієї доби не сформовано у перехідному вікні (23:00-01:00)</div>`;

            const isToday = day.date === todayStr_local;
            const textareaReadonly = isToday ? '' : 'readonly';
            const textareaStyle = isToday ? '' : 'background: rgba(0,0,0,0.03); cursor: not-allowed;';
            
            const saveBtnHtml = isToday ? 
                `<button class="btn btn-primary" onclick="window.saveFeedDayChanges('${day.date}')">💾 Зберегти зміни</button>` : '';
            
            const cancelButtonText = isToday ? 'Скасувати' : 'Закрити';

            modalOverlay.innerHTML = `
                <div class="feed-modal">
                    <div class="feed-modal-header">
                        <h3>Стрічка: ${escapeHtml(formattedDate)} ${isToday ? '' : '(Архів/План)'}</h3>
                        <button class="feed-modal-close" onclick="window.closeFeedModal()">&times;</button>
                    </div>
                    <div class="feed-modal-body">
                        ${baselineText}
                        <label style="font-size: 13px; font-weight: bold; display: block; margin-top: 12px; margin-bottom: 6px;">${isToday ? 'Редагувати текст стрічки:' : 'Перегляд вмісту стрічки (Редагування заблоковано):'}</label>
                        <textarea id="editFeedText" class="feed-textarea" ${textareaReadonly} style="height: 110px; margin-bottom: 12px; font-family: sans-serif; ${textareaStyle}">${escapeHtml(day.actual_content)}</textarea>
                        
                        <div class="feed-history-title">Історія версій та авто-оновлень дня:</div>
                        <div class="feed-history-list">
                            ${historyHtml}
                        </div>
                    </div>
                    <div class="feed-modal-footer">
                        <button class="btn" style="background:#ccc; color:#333;" onclick="window.closeFeedModal()">${cancelButtonText}</button>
                        ${saveBtnHtml}
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

            day.actual_content = newText;
            if (!day.history) day.history = [];
            
            day.history.push({
                timestamp: new Date().toISOString(),
                content: newText,
                is_anomaly: false,
                is_manual_edit: true
            });

            const todayDateStr = formatDateISO(new Date());
            const tomorrowDateStr = formatDateISO(new Date(Date.now() + 86400000));
            
            let todayObj = feedData.days.find(d => d.date === todayDateStr);
            let tomorrowObj = feedData.days.find(d => d.date === tomorrowDateStr);
            
            let todayText = todayObj && todayObj.actual_content ? todayObj.actual_content.replace(/^\[СЬОГОДНІ\]\s*/, "").replace(/\s*\(Оновлено о \d{2}:\d{2}\)/g, "").trim() : "";
            let tomorrowText = tomorrowObj && tomorrowObj.actual_content ? tomorrowObj.actual_content.replace(/\s*\(Оновлено о \d{2}:\d{2}\)/g, "").trim() : "";
            
            let todayHasOutages = todayText && !todayText.includes("Інформація про відключення відсутня") && !todayText.includes("Дані відсутні") && !todayText.includes("Немає даних");
            let tomorrowHasOutages = tomorrowText && !tomorrowText.includes("Інформація про відключення відсутня") && !tomorrowText.includes("Дані відсутні") && !tomorrowText.includes("Немає даних");
            
            let combinedFeed = "";
            if (!todayHasOutages && !tomorrowHasOutages) {
                combinedFeed = "Інформація про відключення на сьогодні та завтра відсутня.";
            } else if (!todayHasOutages && tomorrowHasOutages) {
                combinedFeed = `Інформація про відключення на сьогодні відсутня. | ${tomorrowText}`;
            } else if (todayHasOutages && !tomorrowHasOutages) {
                combinedFeed = `${todayText} | [ЗАВТРА] Інформація про відключення відсутня.`;
            } else {
                combinedFeed = `${todayText} | ${tomorrowText}`;
            }
            
            let anomalyTimestamps = [];
            [todayObj, tomorrowObj].forEach(dObj => {
                if (dObj && dObj.history) {
                    dObj.history.forEach(h => {
                        if (h.is_anomaly || h.is_manual_edit) {
                            anomalyTimestamps.push(h.timestamp);
                        }
                    });
                }
            });
            
            let updateTimeStr = "";
            if (anomalyTimestamps.length > 0) {
                let latestTs = anomalyTimestamps.reduce((max, ts) => ts > max ? ts : max, anomalyTimestamps[0]);
                try {
                    let d = new Date(latestTs);
                    let hh = String(d.getHours()).padStart(2, '0');
                    let mm = String(d.getMinutes()).padStart(2, '0');
                    updateTimeStr = `${hh}:${mm}`;
                } catch(e) {}
            }
            
            if (updateTimeStr) {
                feedData.current_feed = `(Оновлено о ${updateTimeStr}) ${combinedFeed}`;
            } else {
                feedData.current_feed = combinedFeed;
            }
            feedData.last_updated = new Date().toISOString();

            const jsonStr = JSON.stringify(feedData, null, 2);
            commitFileToGitHub("data/feed.json", jsonStr, "Оновлення стрічки відключень вручну з адмінки").then(() => {
                window.closeFeedModal();
                renderFeed(document.getElementById('tabContent'));
            });
        };
    }
}

function renderTelegram(container) {
    let html = '<h3>Telegram-пости (Тільки найновіші)</h3><div class="tg-grid">';
    
    const types = [
        { id: 'tg_planned', title: 'Планові', dateOffset: 0 },
        { id: 'tg_emergency', title: 'Аварійні', dateOffset: 0 },
        { id: 'tg_planned', title: 'Планові', dateOffset: 1 },
        { id: 'tg_emergency', title: 'Аварійні', dateOffset: 1 }
    ];

    types.forEach((t, idx) => {
        let d = new Date();
        d.setDate(d.getDate() + t.dateOffset);
        let dbDateStr = formatDateISO(d);
        
        let label = t.dateOffset === 0 ? "СЬОГОДНІ" : "ЗАВТРА";
        
        // Знаходимо всі відповідні повідомлення та сортуємо їх за ID
        let relevantMsgs = messages.filter(m => m.type === t.id && m.date === dbDateStr);
        relevantMsgs.sort((a, b) => a.id.localeCompare(b.id));
        
        if (relevantMsgs.length === 0) {
            const elementId = `tg-post-${dbDateStr}-${t.id}-${idx}-empty`;
            html += `
                <div class="tg-card">
                    <h4>${label}: ${t.title}</h4>
                    <div class="post-body" id="${elementId}">Очікування генерації або немає відключень.</div>
                </div>
            `;
        } else {
            relevantMsgs.forEach((msg, partIdx) => {
                let content = msg.content;
                let partLabel = label;
                if (relevantMsgs.length > 1) {
                    partLabel += ` (Частина ${partIdx + 1})`;
                }
                
                const elementId = `tg-post-${msg.id}-${idx}-${partIdx}`;
                
                let editBtn = '';
                if (t.dateOffset === 0) {
                    editBtn = `
                        <button class="btn btn-secondary" onclick="window.openEditTelegramModal('${msg.id}', '${partLabel}: ${t.title}')" style="background:#007bff; color:white; border:none; margin-left:10px;">✏️ Редагувати</button>
                    `;
                }

                let cardStyle = '';
                let updatedBadge = '';
                let updatedNote = '';
                if (msg.is_updated) {
                    const upTime = formatDateTimeParts(msg.updated_at).time;
                    cardStyle = 'border: 2px dashed #ff9800; background: rgba(255, 152, 0, 0.03);';
                    updatedBadge = `<span style="font-size: 11px; font-weight: bold; background: #ff9800; color: white; padding: 2px 6px; border-radius: 4px; margin-left: 8px;">⚠️ Змінено о ${upTime}</span>`;
                    updatedNote = `<div style="font-size: 11px; color: #d97706; font-weight: bold; margin-bottom: 10px;">⚠️ Ця частина містить зміни. Рекомендується опублікувати її повторно!</div>`;
                }

                html += `
                    <div class="tg-card" style="${cardStyle}">
                        <h4 style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; color: var(--primary); border-bottom: 1px solid var(--border); padding-bottom: 5px;">
                            <span style="display: flex; align-items: center; flex-wrap: wrap; gap: 5px;">
                                <span>${partLabel}: ${t.title}</span>
                                ${updatedBadge}
                            </span>
                            <span style="font-size: 11px; font-weight: normal; background: rgba(128,128,128,0.1); padding: 2px 6px; border-radius: 4px; color: var(--secondary-text);">${content.length} симв.</span>
                        </h4>
                        ${updatedNote}
                        <div class="post-body" id="${elementId}">${escapeHtml(content)}</div>
                        <div style="display:flex; gap:10px; margin-top:10px; align-items:center;">
                            <button class="btn btn-primary" onclick="copyToClipboard(document.getElementById('${elementId}').innerText)">📋 Копіювати</button>
                            ${editBtn}
                        </div>
                    </div>
                `;
            });
        }
    });
    
    html += '</div>';
    container.innerHTML = html;

    if (!window.openEditTelegramModal) {
        window.openEditTelegramModal = function(msgId, titleText) {
            const msg = messages.find(m => m.id === msgId);
            if (!msg) return;

            const modalOverlay = document.createElement('div');
            modalOverlay.className = 'feed-modal-overlay';
            modalOverlay.id = 'tgEditModal';

            modalOverlay.innerHTML = `
                <div class="feed-modal">
                    <div class="feed-modal-header">
                        <h3>Редагувати Telegram-пост: ${escapeHtml(titleText)}</h3>
                        <button class="feed-modal-close" onclick="window.closeTgModal()">&times;</button>
                    </div>
                    <div class="feed-modal-body">
                        <label style="font-size: 13px; font-weight: bold; display: block; margin-bottom: 6px;">Вміст поста:</label>
                        <textarea id="editTgText" class="feed-textarea" style="height: 250px; margin-bottom: 6px; font-family: sans-serif;" oninput="document.getElementById('editTgCharCount').innerText = 'Символів: ' + this.value.length + ' / 4000 (Telegram limit)'">${escapeHtml(msg.content)}</textarea>
                        <div id="editTgCharCount" style="font-size: 12px; color: var(--secondary-text); margin-bottom: 12px;">Символів: ${msg.content.length} / 4000 (Telegram limit)</div>
                    </div>
                    <div class="feed-modal-footer">
                        <button class="btn" style="background:#ccc; color:#333;" onclick="window.closeTgModal()">Скасувати</button>
                        <button class="btn btn-primary" onclick="window.saveTelegramMessageChanges('${msgId}')">💾 Зберегти зміни</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modalOverlay);
        };
    }

    if (!window.closeTgModal) {
        window.closeTgModal = function() {
            const modal = document.getElementById('tgEditModal');
            if (modal) modal.remove();
        };
    }

    if (!window.saveTelegramMessageChanges) {
        window.saveTelegramMessageChanges = function(msgId) {
            const newContent = document.getElementById('editTgText').value.trim();
            if (!newContent) {
                alert('Вміст не може бути порожнім!');
                return;
            }
            const msg = messages.find(m => m.id === msgId);
            if (msg) {
                msg.content = newContent;
                const jsonStr = JSON.stringify(messages, null, 2);
                commitFileToGitHub("data/messages.json", jsonStr, "Редагування Telegram-посту вручну з адмінки").then(() => {
                    window.closeTgModal();
                    renderTelegram(document.getElementById('tabContent'));
                });
            }
        };
    }
}

function renderAnalytics(container) {
    if (window.analyticsData && window.analyticsData.content) {
        let isEditable = false;
        if (window.analyticsData.date) {
            try {
                const parsedDate = new Date(window.analyticsData.date.replace(" ", "T"));
                const diffMs = Date.now() - parsedDate.getTime();
                const diffHours = diffMs / (1000 * 60 * 60);
                isEditable = diffHours <= 24;
            } catch(e) {
                console.error("Error parsing analytics date", e);
            }
        }
        
        const editButtonHtml = isEditable ? 
            `<button class="btn btn-secondary" onclick="window.openEditAnalyticsModal()">✏️ Редагувати</button>` : 
            `<button class="btn btn-secondary" disabled style="background:#ccc; color:#666; cursor:not-allowed; border:none;" title="Редагування доступне лише протягом 24 годин після створення">✏️ Редагувати (Час вичерпано)</button>`;

        container.innerHTML = `
            <h3>🤖 Щотижнева аналітика від ШІ</h3>
            <div style="margin-top: 20px; padding: 20px; background: var(--bg); border: 1px solid var(--primary); border-radius: var(--radius);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 10px;">
                    <span style="font-size:12px; color:#888;">Сформовано: ${escapeHtml(window.analyticsData.date)}</span>
                </div>
                <div style="font-size:14px; line-height:1.6; white-space:pre-wrap;">${escapeHtml(window.analyticsData.content)}</div>
                <div style="margin-top: 15px; display: flex; gap: 10px;">
                    <button class="btn btn-primary" onclick="copyToClipboard(this.parentElement.previousElementSibling.innerText)">📋 Копіювати для Telegram</button>
                    ${editButtonHtml}
                </div>
            </div>
            <p style="margin-top: 20px; font-size: 13px; color: #666;">
                <i>* Візуалізація та розширена аналітика знаходяться в процесі розробки.</i>
            </p>
        `;
    } else {
        container.innerHTML = `
            <h3>🤖 Щотижнева аналітика від ШІ</h3>
            <p class="empty">Немає даних для аналітики або звіт ще не сформований.</p>
            <div style="margin-top: 15px;">
                <button class="btn btn-secondary" onclick="window.openEditAnalyticsModal()">✏️ Створити/Редагувати</button>
            </div>
        `;
    }

    if (!window.openEditAnalyticsModal) {
        window.openEditAnalyticsModal = function() {
            const modalOverlay = document.createElement('div');
            modalOverlay.className = 'feed-modal-overlay';
            modalOverlay.id = 'analyticsEditModal';
            const oldContent = (window.analyticsData && window.analyticsData.content) ? window.analyticsData.content : '';

            modalOverlay.innerHTML = `
                <div class="feed-modal">
                    <div class="feed-modal-header">
                        <h3>Редагувати аналітику</h3>
                        <button class="feed-modal-close" onclick="window.closeAnalyticsModal()">&times;</button>
                    </div>
                    <div class="feed-modal-body">
                        <label style="font-size: 13px; font-weight: bold; display: block; margin-bottom: 6px;">Вміст звіту аналітики:</label>
                        <textarea id="editAnalyticsText" class="feed-textarea" style="height: 300px; margin-bottom: 12px; font-family: sans-serif;">${escapeHtml(oldContent)}</textarea>
                    </div>
                    <div class="feed-modal-footer">
                        <button class="btn" style="background:#ccc; color:#333;" onclick="window.closeAnalyticsModal()">Скасувати</button>
                        <button class="btn btn-primary" onclick="window.saveAnalyticsChanges()">💾 Зберегти зміни</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modalOverlay);
        };
    }

    if (!window.closeAnalyticsModal) {
        window.closeAnalyticsModal = function() {
            const modal = document.getElementById('analyticsEditModal');
            if (modal) modal.remove();
        };
    }

    if (!window.saveAnalyticsChanges) {
        window.saveAnalyticsChanges = function() {
            const newContent = document.getElementById('editAnalyticsText').value.trim();
            if (!newContent) {
                alert('Вміст не може бути порожнім!');
                return;
            }
            if (!window.analyticsData) {
                window.analyticsData = { date: formatDateISO(new Date()) };
            }
            window.analyticsData.content = newContent;
            const jsonStr = JSON.stringify(window.analyticsData, null, 2);
            commitFileToGitHub("data/analytics.json", jsonStr, "Редагування тижневої аналітики вручну з адмінки").then(() => {
                window.closeAnalyticsModal();
                renderAnalytics(document.getElementById('tabContent'));
            });
        };
    }
}

function expandHouseRanges(housesStr) {
    if (!housesStr) return [];
    const parts = housesStr.split(/,/).map(p => p.trim());
    const expanded = new Set();
    parts.forEach(part => {
        const partLower = part.toLowerCase();
        if (partLower.includes("опора") || partLower.includes("будка") || partLower.includes("гараж") || partLower.includes("блок") || partLower.includes("каб") || partLower.includes("оп")) {
            return;
        }
        const match = part.match(/^(\d+)-(\d+)$/);
        if (match) {
            let start = parseInt(match[1]);
            let end = parseInt(match[2]);
            if (start > end) {
                const temp = start;
                start = end;
                end = temp;
            }
            if (end - start <= 50) {
                for (let i = start; i <= end; i++) {
                    expanded.add(String(i));
                }
            } else {
                expanded.add(part);
            }
        } else {
            const cleaned = part.replace(/[^\d/a-zA-Zа-яА-Я\-]/g, '');
            if (cleaned) {
                expanded.add(cleaned);
            }
        }
    });
    return Array.from(expanded).sort((a, b) => {
        const aNum = parseInt(a.match(/\d+/) || 0);
        const bNum = parseInt(b.match(/\d+/) || 0);
        if (aNum !== bNum) return aNum - bNum;
        return a.localeCompare(b);
    });
}

function getStreetDictKey(settlement) {
    if (!settlement) return "м. Старокостянтинів";
    settlement = settlement.trim();
    if (settlement === "Пісочниця") return "Пісочниця";
    if (settlement === "Старокостянтинів" || settlement === "м. Старокостянтинів") {
        return "м. Старокостянтинів";
    }
    if (settlement.startsWith("с. ")) return settlement;
    return "с. " + settlement;
}

function getDoubtfulHousesForStreet(settlement, street) {
    const housesFound = new Set();
    archiveOutages.forEach(rec => {
        if (rec.settlement && getStreetDictKey(rec.settlement) === settlement) {
            if (rec.streets_detailed) {
                rec.streets_detailed.forEach(s => {
                    if (s.name && s.name.trim() === street) {
                        const expanded = expandHouseRanges(s.houses);
                        expanded.forEach(h => housesFound.add(h));
                    }
                });
            }
        }
    });
    
    const streetData = officialStreets[settlement]?.[street] || {};
    const official = streetData.houses || [];
    const blacklist = streetData.blacklist || [];
    
    const doubtful = Array.from(housesFound).filter(h => !official.includes(h) && !blacklist.includes(h));
    
    return doubtful.sort((a, b) => {
        const aNum = parseInt(a.match(/\d+/) || 0);
        const bNum = parseInt(b.match(/\d+/) || 0);
        if (aNum !== bNum) return aNum - bNum;
        return a.localeCompare(b);
    });
}

async function logAddressAction(actionType, oldName, newName, housesList) {
    if (!window.addressChangelog) window.addressChangelog = [];
    const entry = {
        timestamp: new Date().toISOString(),
        action: actionType,
        settlement: selectedSettlement,
        old_name: oldName,
        new_name: newName || "",
        houses: housesList || []
    };
    window.addressChangelog.push(entry);
    const changelogStr = JSON.stringify(window.addressChangelog, null, 2);
    await commitFileToGitHub("data/address_changelog.json", changelogStr, `Запис у журнал адрес: ${actionType} для ${oldName}`);
}

function renderStreets(container) {
    let allSettlements = ["м. Старокостянтинів"];
    
    const villages = new Set();
    for (const key in officialStreets) {
        if (key !== "м. Старокостянтинів" && key !== "Пісочниця") {
            villages.add(key.replace(/^с\.\s*/, ""));
        }
    }
    archiveOutages.forEach(rec => {
        if (rec.settlement) {
            const name = rec.settlement.trim();
            if (name !== "Старокостянтинів" && name !== "м. Старокостянтинів" && name !== "Пісочниця") {
                villages.add(name.replace(/^с\.\s*/, ""));
            }
        }
    });
    
    Array.from(villages).sort().forEach(v => allSettlements.push("с. " + v));
    allSettlements.push("Пісочниця");

    let optionsHtml = allSettlements.map(s => {
        const selected = s === selectedSettlement ? "selected" : "";
        return `<option value="${escapeHtml(s)}" ${selected}>${escapeHtml(s)}</option>`;
    }).join("");

    let settlementData = officialStreets[selectedSettlement] || {};
    let official = Object.keys(settlementData).sort();
    
    let allSettlementStreets = new Set();
    archiveOutages.forEach(rec => {
        if (rec.settlement && getStreetDictKey(rec.settlement) === selectedSettlement) {
            if (rec.streets_detailed) {
                rec.streets_detailed.forEach(s => {
                    if (s.name) allSettlementStreets.add(s.name.trim());
                });
            } else if (rec.streets) {
                rec.streets.forEach(s => allSettlementStreets.add(s.trim()));
            }
        }
    });

    let doubtful = Array.from(allSettlementStreets).filter(s => !settlementData[s]).sort();

    if (window.selectedStreet && !settlementData[window.selectedStreet]) {
        window.selectedStreet = "";
    }

    let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 15px; flex-wrap: wrap; gap: 10px;">
            <h3>Словник адрес громади</h3>
            <div style="display:flex; gap: 10px; align-items:center; flex-wrap: wrap;">
                <label for="settlementSelect" style="font-weight: bold; font-size: 14px;">Населений пункт:</label>
                <select id="settlementSelect" onchange="window.changeSettlement(this.value)" style="padding: 8px; border-radius: 4px; border: 1px solid var(--border); background: var(--bg); color: var(--text); min-width: 200px;">
                    ${optionsHtml}
                </select>
                <input type="text" id="streetSearch" placeholder="Пошук вулиці..." onkeyup="window.filterStreets()" style="padding: 8px; border-radius: 4px; border: 1px solid var(--border); background: var(--bg); color: var(--text); width: 180px;">
                <button class="btn btn-primary" onclick="window.saveStreetsToGitHub()" style="background-color: #28a745;">💾 Зберегти зміни</button>
                <button class="btn btn-primary" onclick="window.exportStreetsCSV()" style="background-color: #17a2b8;">📥 Експортувати в CSV</button>
            </div>
        </div>
        
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 15px;">
            <p style="font-size: 13px; color: var(--secondary-text); margin: 0;">
                Керуйте списком офіційних адрес для обраного населеного пункту: <strong>${escapeHtml(selectedSettlement)}</strong>.
            </p>
            <button class="btn btn-primary" onclick="window.addNewStreet()" style="font-size:12px; padding: 6px 12px; background: #007bff;">➕ Додати вулицю вручну</button>
        </div>
        
        <div style="display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; width: 100%;">
    `;

    html += `
        <div style="flex: 1; min-width: 300px; display:flex; flex-direction:column; gap: 15px;">
            <div style="border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg); padding: 15px;">
                <h4 style="margin-top: 0; color: #28a745; border-bottom: 1px solid var(--border); padding-bottom: 8px;">✅ Офіційні вулиці (${official.length})</h4>
                <ul class="streets-list" style="list-style-type: none; padding: 0; max-height: 350px; overflow-y: auto; margin: 0;">`;
    if (official.length === 0) {
        html += `<p style="font-size:13px; color:var(--secondary-text); font-style:italic;">Немає офіційних вулиць для цього пункту.</p>`;
    } else {
        official.forEach(street => {
            const isSelected = street === window.selectedStreet;
            const bgStyle = isSelected ? 'background: rgba(40,167,69,0.08); border: 1px solid #28a745;' : 'border-bottom: 1px solid var(--border);';
            const fontStyle = isSelected ? 'font-weight: bold; color: #28a745;' : '';
            html += `
                <li style="display:flex; justify-content:space-between; align-items:center; padding: 8px 10px; margin-bottom: 4px; border-radius: 4px; ${bgStyle} cursor:pointer;" onclick="window.selectStreet('${escapeHtml(street).replace(/'/g, "\\'")}')">
                    <span style="${fontStyle}">${escapeHtml(street)}</span>
                    <div style="display:flex; gap: 5px;" onclick="event.stopPropagation();">
                        <button onclick="window.moveStreetSettlement('${escapeHtml(street).replace(/'/g, "\\'")}')" style="background:transparent; border:none; cursor:pointer; font-size:14px;" title="Перенести в інший н.п.">🚚</button>
                        <button onclick="window.editStreetName('${escapeHtml(street).replace(/'/g, "\\'")}')" style="background:transparent; border:none; cursor:pointer; font-size:14px;" title="Редагувати назву">✏️</button>
                        <button onclick="window.deleteStreet('${escapeHtml(street).replace(/'/g, "\\'")}')" style="background:transparent; border:none; cursor:pointer; font-size:14px;" title="Перенести в сумнівні">❌</button>
                    </div>
                </li>`;
        });
    }
    html += `</ul></div>`;

    html += `
            <div style="border: 1px solid var(--danger); border-radius: var(--radius); background: rgba(220,53,69,0.02); padding: 15px;">
                <h4 style="margin-top: 0; color: var(--danger); border-bottom: 1px solid rgba(220,53,69,0.1); padding-bottom: 8px;">⚠️ Сумнівні вулиці (${doubtful.length})</h4>
                <ul class="streets-list" style="list-style-type: none; padding: 0; max-height: 250px; overflow-y: auto; margin: 0;">`;
    if (doubtful.length === 0) {
        html += `<p style="font-size:13px; color:var(--secondary-text); font-style:italic;">Немає виявлених сумнівних вулиць.</p>`;
    } else {
        doubtful.forEach(street => {
            let origSettSuffix = "";
            if (selectedSettlement === "Пісочниця") {
                const origSetts = new Set();
                archiveOutages.forEach(rec => {
                    if (rec.settlement === "Пісочниця") {
                        const hasStreet = (rec.streets || []).map(s => s.trim()).includes(street) || 
                                          (rec.streets_detailed || []).some(sd => sd.name && sd.name.trim() === street);
                        if (hasStreet && rec.original_settlement) {
                            origSetts.add(rec.original_settlement);
                        }
                    }
                });
                if (origSetts.size > 0) {
                    origSettSuffix = ` <span style="font-size:11px; font-weight:normal; opacity:0.75; display:block; margin-top:2px; color:var(--text);">(ориг: ${escapeHtml(Array.from(origSetts).join(", "))})</span>`;
                }
            }
            html += `
                <li style="display:flex; justify-content:space-between; align-items:center; padding: 8px 10px; border-bottom: 1px solid rgba(220,53,69,0.05); font-size: 14px; color: var(--danger);">
                    <strong style="max-width: 50%; word-break: break-all;">${escapeHtml(street)}${origSettSuffix}</strong>
                    <div style="display:flex; gap: 5px;">
                        <button onclick="window.whitelistStreet('${escapeHtml(street).replace(/'/g, "\\'")}')" class="btn" style="padding:4px 8px; font-size:12px; background:#28a745; border:none; color:#fff; cursor:pointer;" title="Обілити (✓)">✓</button>
                        <button onclick="window.editDoubtfulStreet('${escapeHtml(street).replace(/'/g, "\\'")}')" class="btn" style="padding:4px 8px; font-size:12px; background:#007bff; border:none; color:#fff; cursor:pointer;" title="Редагувати (✏️)">✏️</button>
                        <button onclick="window.moveStreetSettlement('${escapeHtml(street).replace(/'/g, "\\'")}')" class="btn" style="padding:4px 8px; font-size:12px; background:#e67e22; border:none; color:#fff; cursor:pointer;" title="Перенести в інший н.п. (🚚)">🚚</button>
                        <button onclick="window.hideDoubtfulStreet('${escapeHtml(street).replace(/'/g, "\\'")}')" class="btn" style="padding:4px 8px; font-size:12px; background:#17a2b8; border:none; color:#fff; cursor:pointer;" title="Приховати з публікацій (👁️)">👁️</button>
                        <button onclick="window.deleteDoubtfulStreet('${escapeHtml(street).replace(/'/g, "\\'")}')" class="btn" style="padding:4px 8px; font-size:12px; background:#e74c3c; border:none; color:#fff; cursor:pointer;" title="Видалити (🗑️)">🗑️</button>
                    </div>
                </li>`;
        });
    }
    html += `</ul></div></div>`;

    html += `
        <div style="flex: 1.2; min-width: 320px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg); padding: 15px; display: flex; flex-direction: column; gap: 15px; min-height: 500px;">
    `;

    if (window.selectedStreet) {
        const currentStreet = window.selectedStreet;
        let officialHouses = settlementData[currentStreet].houses || [];
        officialHouses.sort((a, b) => {
            const aNum = parseInt(a.match(/\d+/) || 0);
            const bNum = parseInt(b.match(/\d+/) || 0);
            if (aNum !== bNum) return aNum - bNum;
            return a.localeCompare(b);
        });

        const doubtfulHouses = getDoubtfulHousesForStreet(selectedSettlement, currentStreet);

        html += `
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 5px;">
                <h4 style="margin: 0; color: var(--primary);">🏘️ Будинки: ${escapeHtml(currentStreet)}</h4>
                <span style="font-size: 12px; padding: 2px 8px; background: var(--border); border-radius: 12px; color: var(--text); font-weight: bold;">${settlementData[currentStreet].type || 'вулиця'}</span>
            </div>
            
            <div style="display:flex; gap: 8px;">
                <input type="text" id="newHouseInput" placeholder="Номер будинку (напр. '15а')" style="padding: 8px; border-radius: 4px; border: 1px solid var(--border); background: var(--bg); color: var(--text); flex: 1;">
                <button class="btn btn-primary" onclick="window.addHouse()" style="background:#007bff; border:none; padding:8px 15px; color:#fff; cursor:pointer; border-radius:4px;">➕ Додати</button>
            </div>

            <div>
                <h5 style="margin: 0 0 8px 0; color:#28a745;">✅ Офіційні номери (${officialHouses.length})</h5>
                <div style="border: 1px solid var(--border); border-radius: 4px; padding: 10px; background: rgba(0,0,0,0.01); max-height: 250px; overflow-y: auto; display:flex; flex-wrap:wrap; gap:6px; align-content: flex-start;">`;
        if (officialHouses.length === 0) {
            html += `<span style="font-size:12px; color:var(--secondary-text); font-style:italic; width: 100%;">Немає доданих будинків. Будуть діяти всі будинки (маркер *).</span>`;
        } else {
            officialHouses.forEach(h => {
                html += `
                    <span style="display:inline-flex; align-items:center; padding: 4px 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 4px; font-size: 13px; font-weight: 500;">
                        ${escapeHtml(h)}
                        <span onclick="window.editOfficialHouse('${escapeHtml(h).replace(/'/g, "\\'")}')" style="margin-left: 6px; cursor: pointer; color: var(--primary); font-weight: bold; font-size: 12px;" title="Редагувати">✏️</span>
                        <span onclick="window.deleteHouse('${escapeHtml(h).replace(/'/g, "\\'")}')" style="margin-left: 6px; cursor: pointer; color: var(--danger); font-weight: bold; font-size: 12px;" title="Видалити">✕</span>
                    </span>`;
            });
        }
        html += `</div></div>`;

        html += `
            <div>
                <h5 style="margin: 0 0 8px 0; color:var(--danger);">⚠️ Виявлені в архіві (${doubtfulHouses.length})</h5>
                <div style="border: 1px solid var(--danger); border-radius: 4px; padding: 10px; background: rgba(220,53,69,0.01); max-height: 200px; overflow-y: auto; display:flex; flex-wrap:wrap; gap:6px; align-content: flex-start;">`;
        if (doubtfulHouses.length === 0) {
            html += `<span style="font-size:12px; color:var(--secondary-text); font-style:italic; width: 100%;">Немає нових сумнівних будинків для цієї вулиці.</span>`;
        } else {
            doubtfulHouses.forEach(h => {
                html += `
                    <span style="display:inline-flex; align-items:center; padding: 4px 8px; background: var(--bg); border: 1px solid var(--danger); border-radius: 4px; font-size: 13px; color: var(--danger);">
                        ${escapeHtml(h)}
                        <span onclick="window.whitelistHouse('${escapeHtml(h).replace(/'/g, "\\'")}')" style="margin-left: 8px; cursor: pointer; color: #28a745; font-weight: bold; font-size: 14px;" title="Обілити (✓)">✓</span>
                        <span onclick="window.editDoubtfulHouse('${escapeHtml(h).replace(/'/g, "\\'")}')" style="margin-left: 8px; cursor: pointer; color: var(--primary); font-weight: bold; font-size: 12px;" title="Редагувати (✏️)">✏️</span>
                        <span onclick="window.ignoreDoubtfulHouse('${escapeHtml(h).replace(/'/g, "\\'")}')" style="margin-left: 8px; cursor: pointer; color: var(--danger); font-weight: bold; font-size: 12px;" title="Ігнорувати / Видалити (🗑️)">🗑️</span>
                    </span>`;
            });
        }
        html += `</div></div>`;

    } else {
        html += `
            <div style="flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; color: var(--secondary-text);">
                <span style="font-size: 40px; margin-bottom: 10px;">👈</span>
                <p style="font-size:13px; font-style:italic; margin:0;">Оберіть вулицю зі списку офіційних ліворуч,<br>щоб редагувати або обілити номери будинків.</p>
            </div>`;
    }

    html += `</div></div>`;

    const activeRules = window.streetCorrections?.[selectedSettlement] || {};
    const rulesKeys = Object.keys(activeRules).sort();
    
    let rulesRows = "";
    if (rulesKeys.length === 0) {
        rulesRows = `<tr><td colspan="5" class="empty" style="text-align:center; padding: 10px;">Правила автокорекції відсутні.</td></tr>`;
    } else {
        rulesKeys.forEach(k => {
            const r = activeRules[k];
            let actionText = "";
            let targetText = "-";
            if (r.action === "delete") {
                actionText = `<span class="badge badge-danger">Видаляти/Ігнорувати</span>`;
            } else if (r.action === "rename") {
                actionText = `<span class="badge badge-warning">Перейменовувати</span>`;
                targetText = `<strong>${escapeHtml(r.target)}</strong>`;
            } else if (r.action === "move_to_settlement") {
                actionText = `<span class="badge" style="background: rgba(52, 152, 219, 0.15); color: #2980b9; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">Переносити в н.п.</span>`;
                targetText = `<strong>${escapeHtml(Array.isArray(r.target_settlements) ? r.target_settlements.join(", ") : (r.target_settlements || r.target_settlement || ""))}</strong>`;
            } else if (r.action === "hide") {
                actionText = `<span class="badge badge-secondary" style="background:#7f8c8d; color:#fff;">Приховано з публ.</span>`;
            } else if (r.action === "unverified") {
                actionText = `<span class="badge" style="background: rgba(127, 140, 141, 0.15); color: #7f8c8d; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">Неверифікована (ШІ checked)</span>`;
            }
            const dateStr = r.timestamp ? new Date(r.timestamp).toLocaleString('uk-UA') : "-";
            const aiBadge = r.auto ? ` <span style="background: rgba(155, 89, 182, 0.15); color: #8e44ad; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-left: 5px;" title="Створено автоматично ШІ">🤖 ШІ</span>` : "";
            
            rulesRows += `
                <tr style="border-bottom: 1px solid var(--border);">
                    <td style="padding: 10px; font-weight: bold; color: var(--danger);">${escapeHtml(k)}${aiBadge}</td>
                    <td style="padding: 10px;">${actionText}</td>
                    <td style="padding: 10px;">${targetText}</td>
                    <td style="padding: 10px; font-size: 12px; color: #888;">${escapeHtml(dateStr)}</td>
                    <td style="padding: 10px; text-align: center;">
                        <button onclick="window.deleteCorrectionRule('${escapeHtml(k).replace(/'/g, "\\'")}')" class="btn" style="padding: 4px 8px; background: #e74c3c; color: #fff; font-size:12px; border:none; cursor:pointer;" title="Видалити правило">🗑️ Видалити</button>
                    </td>
                </tr>
            `;
        });
    }

    const changelog = window.addressChangelog || [];
    const settlementChangelog = changelog.filter(c => c.settlement === selectedSettlement).reverse().slice(0, 15);
    
    let logRows = "";
    if (settlementChangelog.length === 0) {
        logRows = `<tr><td colspan="4" class="empty" style="text-align:center; padding: 10px;">Історія змін відсутня.</td></tr>`;
    } else {
        settlementChangelog.forEach(c => {
            let actionLabel = "";
            let details = "";
            const time = new Date(c.timestamp).toLocaleString('uk-UA');
            
            if (c.action === 'rename_doubtful') {
                actionLabel = `<span class="badge badge-warning" style="background:#f39c12; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Перейм. сумнівну</span>`;
                details = `Змінено з <strong>${escapeHtml(c.old_name)}</strong> на <strong>${escapeHtml(c.new_name)}</strong>.`;
            } else if (c.action === 'hide_doubtful') {
                actionLabel = `<span class="badge badge-secondary" style="background:#7f8c8d; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Приховано з публ.</span>`;
                details = `Приховано з публікацій <strong>${escapeHtml(c.old_name)}</strong>.`;
            } else if (c.action === 'delete_doubtful') {
                actionLabel = `<span class="badge badge-danger" style="background:#e74c3c; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Видалено сумнівну</span>`;
                details = `Вилучено з архіву <strong>${escapeHtml(c.old_name)}</strong>.`;
            } else if (c.action === 'move_to_doubtful') {
                actionLabel = `<span class="badge badge-secondary" style="background:#7f8c8d; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Перенесено в сумнівні</span>`;
                details = `Офіційну <strong>${escapeHtml(c.old_name)}</strong> вилучено з білого списку.`;
            } else if (c.action === 'rename_official') {
                actionLabel = `<span class="badge badge-primary" style="background:#3498db; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Перейм. офіційну</span>`;
                details = `Офіційну <strong>${escapeHtml(c.old_name)}</strong> перейменовано на <strong>${escapeHtml(c.new_name)}</strong>.`;
            } else if (c.action === 'delete_rule') {
                actionLabel = `<span class="badge badge-info" style="background:#2c3e50; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Видалено правило</span>`;
                details = `Скасовано автокорекцію для <strong>${escapeHtml(c.old_name)}</strong>.`;
            } else if (c.action === 'move_settlement') {
                actionLabel = `<span class="badge badge-info" style="background:#17a2b8; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Перенесено н.п.</span>`;
                details = `Вулицю <strong>${escapeHtml(c.old_name)}</strong> перенесено з <strong>${escapeHtml(c.settlement)}</strong> в <strong>${escapeHtml(c.new_name)}</strong>.`;
            } else if (c.action === 'whitelist_street') {
                actionLabel = `<span class="badge badge-success" style="background:#2ecc71; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Обілено вулицю</span>`;
                details = `Додано сумнівну <strong>${escapeHtml(c.old_name)}</strong> в офіційні.`;
            } else if (c.action === 'add_official_street') {
                actionLabel = `<span class="badge badge-primary" style="background:#3498db; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Додано вулицю</span>`;
                details = `Створено офіційну <strong>${escapeHtml(c.old_name)}</strong> вручну.`;
            } else if (c.action === 'add_house') {
                actionLabel = `<span class="badge badge-success" style="background:#2ecc71; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Додано будинок</span>`;
                details = `Вулиця <strong>${escapeHtml(c.old_name)}</strong>: додано новий номер.`;
            } else if (c.action === 'delete_house') {
                actionLabel = `<span class="badge badge-danger" style="background:#e74c3c; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Видалено будинок</span>`;
                details = `Вулиця <strong>${escapeHtml(c.old_name)}</strong>: вилучено номер.`;
            } else if (c.action === 'whitelist_house') {
                actionLabel = `<span class="badge badge-success" style="background:#2ecc71; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Обілено будинок</span>`;
                details = `Вулиця <strong>${escapeHtml(c.old_name)}</strong>: обілено виявлений номер.`;
            } else if (c.action === 'edit_official_house') {
                actionLabel = `<span class="badge badge-warning" style="background:#f39c12; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Змінено будинок</span>`;
                details = `Вулиця <strong>${escapeHtml(c.old_name)}</strong>: змінено ${escapeHtml(c.new_name)}.`;
            } else if (c.action === 'correct_doubtful_house') {
                actionLabel = `<span class="badge badge-warning" style="background:#f39c12; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Виправлено будинок</span>`;
                details = `Вулиця <strong>${escapeHtml(c.old_name)}</strong>: виправлено ${escapeHtml(c.new_name)}.`;
            } else if (c.action === 'ignore_doubtful_house') {
                actionLabel = `<span class="badge badge-secondary" style="background:#7f8c8d; color:#fff; padding:3px 8px; border-radius:3px; font-size:11px;">Ігноровано будинок</span>`;
                details = `Вулиця <strong>${escapeHtml(c.old_name)}</strong>: занесено в чорний список.`;
            }
            
            let housesHtml = "-";
            if (c.houses && c.houses.length > 0) {
                const housesText = c.houses.join(", ");
                housesHtml = `
                    <details style="cursor: pointer;">
                        <summary style="color: var(--primary); font-weight: 500; font-size: 12px; user-select: none; outline: none;">Показати (${c.houses.length})</summary>
                        <div style="margin-top: 5px; max-height: 90px; overflow-y: auto; font-size: 12px; color: var(--secondary-text); word-break: break-all; line-height: 1.4; border: 1px solid var(--border); padding: 5px; border-radius: 4px; background: rgba(0,0,0,0.01);">
                            ${escapeHtml(housesText)}
                        </div>
                    </details>
                `;
            }
            
            logRows += `
                <tr style="border-bottom: 1px solid var(--border); font-size: 13px;">
                    <td style="padding: 8px; color: #888; white-space:nowrap; vertical-align: top;">${escapeHtml(time)}</td>
                    <td style="padding: 8px; vertical-align: top;">${actionLabel}</td>
                    <td style="padding: 8px; vertical-align: top;">${details}</td>
                    <td style="padding: 8px; max-width: 250px; vertical-align: top;">${housesHtml}</td>
                </tr>
            `;
        });
    }

    html += `
        </div>
        
        <h4 style="margin: 30px 0 10px 0; color: var(--primary); border-bottom: 2px solid var(--border); padding-bottom: 8px;">⚙️ Правила автокорекції назв обленерго (${rulesKeys.length} правил)</h4>
        <p style="font-size: 13px; color: var(--secondary-text); margin-bottom: 15px;">
            Ці правила автоматично застосовуються парсером "на льоту". При отриманні нових даних з сайту обленерго, помилкові назви будуть автоматично замінюватись на правильні або ігноруватись.
        </p>
        
        <div style="border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg); overflow-x: auto; margin-bottom: 20px; width: 100%;">
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                <thead>
                    <tr style="background: rgba(0,0,0,0.02); border-bottom: 1px solid var(--border);">
                        <th style="padding: 10px;">Помилкова назва обленерго</th>
                        <th style="padding: 10px;">Дія</th>
                        <th style="padding: 10px;">Правильна цільова назва</th>
                        <th style="padding: 10px;">Створено</th>
                        <th style="padding: 10px; text-align: center;">Дія</th>
                    </tr>
                </thead>
                <tbody>
                    ${rulesRows}
                </tbody>
            </table>
        </div>
        
        <h4 style="margin: 25px 0 10px 0; color: var(--primary); border-bottom: 2px solid var(--border); padding-bottom: 8px;">📜 Історія змін адрес (останні 15 дій)</h4>
        <div style="border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg); overflow-x: auto; width: 100%;">
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                <thead>
                    <tr style="background: rgba(0,0,0,0.02); border-bottom: 1px solid var(--border);">
                        <th style="padding: 8px;">Дата та час</th>
                        <th style="padding: 8px;">Тип дії</th>
                        <th style="padding: 8px;">Опис змін</th>
                        <th style="padding: 8px;">Зачеплені будинки</th>
                    </tr>
                </thead>
                <tbody>
                    ${logRows}
                </tbody>
            </table>
        </div>
    `;

    container.innerHTML = html;

    if (!window.changeSettlement) {
        window.changeSettlement = function(val) {
            selectedSettlement = val;
            window.selectedStreet = "";
            renderStreets(document.getElementById('tabContent'));
        };
    }

    if (!window.selectStreet) {
        window.selectStreet = function(street) {
            window.selectedStreet = street;
            renderStreets(document.getElementById('tabContent'));
        };
    }

    if (!window.addNewStreet) {
        window.addNewStreet = async function() {
            const streetName = prompt(`Додавання вулиці для: ${selectedSettlement}\n\nВведіть назву вулиці (наприклад, 'вул. Шевченка'):`);
            if (streetName && streetName.trim()) {
                const nameClean = streetName.trim();
                if (!officialStreets[selectedSettlement]) {
                    officialStreets[selectedSettlement] = {};
                }
                if (officialStreets[selectedSettlement][nameClean]) {
                    alert('Ця вулиця вже є у списку!');
                    return;
                }
                officialStreets[selectedSettlement][nameClean] = {
                    type: nameClean.toLowerCase().includes("пров") ? "провулок" : "вулиця",
                    houses: [],
                    blacklist: []
                };
                window.selectedStreet = nameClean;
                
                const jsonStr = JSON.stringify(officialStreets, null, 2);
                await commitFileToGitHub("data/official_streets.json", jsonStr, `Додавання нової офіційної вулиці ${nameClean} вручну`);
                await logAddressAction('add_official_street', nameClean, "", []);
                
                renderStreets(document.getElementById('tabContent'));
            }
        };
    }

    if (!window.editStreetName) {
        window.editStreetName = async function(street) {
            const newName = prompt(`Редагування назви офіційної вулиці у: ${selectedSettlement}\n\nВведіть нову назву для '${street}':`, street);
            if (newName && newName.trim() && newName.trim() !== street) {
                const nameClean = newName.trim();
                if (!officialStreets[selectedSettlement]) return;
                
                const houses = officialStreets[selectedSettlement][street]?.houses || [];

                officialStreets[selectedSettlement][nameClean] = officialStreets[selectedSettlement][street];
                delete officialStreets[selectedSettlement][street];
                if (window.selectedStreet === street) {
                    window.selectedStreet = nameClean;
                }
                
                const jsonStr = JSON.stringify(officialStreets, null, 2);
                await commitFileToGitHub("data/official_streets.json", jsonStr, `Перейменування офіційної вулиці ${street} на ${nameClean}`);

                let renamedCount = 0;
                archiveOutages.forEach(rec => {
                    let recSett = rec.settlement || "м. Старокостянтинів";
                    if (getStreetDictKey(recSett) === selectedSettlement) {
                        if (rec.streets) {
                            rec.streets = rec.streets.map(s => s.trim() === street ? nameClean : s);
                        }
                        if (rec.streets_detailed) {
                            rec.streets_detailed.forEach(s_det => {
                                if (s_det.name && s_det.name.trim() === street) {
                                    s_det.name = nameClean;
                                    renamedCount++;
                                }
                            });
                        }
                    }
                });
                
                if (renamedCount > 0) {
                    const archiveStr = JSON.stringify(archiveOutages, null, 2);
                    await commitFileToGitHub("data/archive.json", archiveStr, `Оновлення назви вулиці ${street} на ${nameClean} в архіві`);
                }

                let rawRenamed = 0;
                rawOutages.forEach(rec => {
                    let recSett = rec.settlement || "м. Старокостянтинів";
                    if (getStreetDictKey(recSett) === selectedSettlement) {
                        if (rec.streets) {
                            rec.streets = rec.streets.map(s => s.trim() === street ? nameClean : s);
                        }
                        if (rec.streets_detailed) {
                            rec.streets_detailed.forEach(s_det => {
                                if (s_det.name && s_det.name.trim() === street) {
                                    s_det.name = nameClean;
                                    rawRenamed++;
                                }
                            });
                        }
                    }
                });
                if (rawRenamed > 0) {
                    const rawStr = JSON.stringify(rawOutages, null, 2);
                    await commitFileToGitHub("data/outages_snapshot.json", rawStr, `Оновлення назви вулиці ${street} на ${nameClean} в активних відключеннях`);
                }

                await logAddressAction('rename_official', street, nameClean, houses);

                renderStreets(document.getElementById('tabContent'));
            }
        };
    }

    if (!window.moveStreetSettlement) {
        window.moveStreetSettlement = async function(street) {
            let settlements = Object.keys(officialStreets).filter(s => s !== selectedSettlement).sort();
            let promptMsg = `Перенесення офіційної вулиці '${street}' з '${selectedSettlement}' в інші населені пункти.\n\n` +
                            `Введіть назви через кому або їх номери зі списку через кому (наприклад: 28, 63):\n` +
                            settlements.map((s, idx) => `${idx + 1}. ${s}`).join("\n");
            let targetInput = prompt(promptMsg);
            if (!targetInput) return;
            
            // Розпарсимо список населених пунктів, розділених комою
            let targets = targetInput.split(',')
                .map(t => t.trim())
                .filter(t => t.length > 0)
                .map(t => {
                    const targetIdx = parseInt(t) - 1;
                    if (!isNaN(targetIdx) && targetIdx >= 0 && targetIdx < settlements.length) {
                        return settlements[targetIdx];
                    }
                    // Пошук найближчого співпадіння за назвою
                    const found = settlements.find(s => s.toLowerCase().includes(t.toLowerCase()));
                    return found || t;
                });
                
            if (targets.length === 0) {
                alert("Не обрано жодного правильного населеного пункту!");
                return;
            }
            
            // Валідуємо, що всі обрані н.п. існують в базі
            for (let t of targets) {
                if (!officialStreets[t]) {
                    alert(`Населений пункт '${t}' не знайдено в базі!`);
                    return;
                }
            }
            
            const targetsStr = targets.join(", ");
            let confirmMsg = `Ви впевнені, що хочете перенести вулицю '${street}' з '${selectedSettlement}' в:\n` +
                             `[ ${targetsStr} ]?\n\n` +
                             `Це прибере її з '${selectedSettlement}', додасть до офіційних словників обраних н.п. та налаштує правило автоматичного вибору (трирівнева логіка).`;
            
            if (confirm(confirmMsg)) {
                const houses = getDoubtfulHousesForStreet(selectedSettlement, street);
                const streetData = (officialStreets[selectedSettlement] && officialStreets[selectedSettlement][street]) || { type: "вулиця", houses: houses, blacklist: [] };
                
                // 1. Оновлюємо офіційні словники
                if (officialStreets[selectedSettlement]) {
                    delete officialStreets[selectedSettlement][street];
                }
                for (let t of targets) {
                    if (!officialStreets[t][street]) {
                        officialStreets[t][street] = JSON.parse(JSON.stringify(streetData));
                    } else {
                        // Об'єднуємо будинки
                        const existingHouses = new Set(officialStreets[t][street].houses || []);
                        (streetData.houses || []).forEach(h => existingHouses.add(h));
                        officialStreets[t][street].houses = Array.from(existingHouses);
                    }
                }
                
                if (window.selectedStreet === street) {
                    window.selectedStreet = "";
                }
                
                const jsonStr = JSON.stringify(officialStreets, null, 2);
                await commitFileToGitHub("data/official_streets.json", jsonStr, `Перенесення вулиці ${street} з ${selectedSettlement} в [${targetsStr}]`);
                
                // 2. Створюємо правило в street_corrections.json
                if (!window.streetCorrections) window.streetCorrections = {};
                if (!window.streetCorrections[selectedSettlement]) window.streetCorrections[selectedSettlement] = {};
                window.streetCorrections[selectedSettlement][street] = {
                    action: "move_to_settlement",
                    target_settlements: targets,
                    target_street: street,
                    timestamp: new Date().toISOString()
                };
                const correctionsStr = JSON.stringify(window.streetCorrections, null, 2);
                await commitFileToGitHub("data/street_corrections.json", correctionsStr, `Правило перенесення вулиці: ${street} з ${selectedSettlement} -> [${targetsStr}]`);
                
                // 3. Допоміжна функція для трирівневого розподілу на стороні клієнта
                function routeRecordForTargets(rec) {
                    const sDet = (rec.streets_detailed || []).find(s => s.name && s.name.trim() === street);
                    const housesStr = sDet ? sDet.houses || "" : "";
                    const expandedHouses = expandHouseRanges(housesStr);
                    
                    // Рівень 1: Співпадіння будинків
                    let candMatches = {};
                    let anyMatch = false;
                    targets.forEach(t => {
                        candMatches[t] = new Set();
                        const offHouses = officialStreets[t]?.[street]?.houses || [];
                        expandedHouses.forEach(h => {
                            if (offHouses.includes(h)) {
                                candMatches[t].add(h);
                                anyMatch = true;
                            }
                        });
                    });
                    
                    if (anyMatch) {
                        // Збираємо список кандидатів, які отримали хоча б одне співпадіння
                        let activeCands = targets.filter(t => candMatches[t].size > 0);
                        let assignedHouses = {};
                        targets.forEach(t => assignedHouses[t] = []);
                        
                        expandedHouses.forEach(h => {
                            let matchedCands = targets.filter(t => candMatches[t].has(h));
                            if (matchedCands.length > 0) {
                                matchedCands.forEach(t => assignedHouses[t].push(h));
                            } else {
                                // Будинки, що не співпали, йдуть до всіх активних кандидатів
                                activeCands.forEach(t => assignedHouses[t].push(h));
                            }
                        });
                        
                        let results = [];
                        targets.forEach(t => {
                            if (assignedHouses[t].length > 0) {
                                let targetRec = JSON.parse(JSON.stringify(rec));
                                targetRec.settlement = t;
                                targetRec.streets = (targetRec.streets || []).filter(s => s.trim() === street);
                                targetRec.streets_detailed = [{
                                    name: street,
                                    houses: assignedHouses[t].join(", ")
                                }];
                                results.push(targetRec);
                            }
                        });
                        return results;
                    }
                    
                    // Рівень 2: Сусідство (інші вулиці в події)
                    let votes = {};
                    targets.forEach(t => votes[t] = 0);
                    const otherStreets = (rec.streets || []).filter(s => s.trim() !== street);
                    otherStreets.forEach(otherS => {
                        targets.forEach(t => {
                            if (officialStreets[t]?.[otherS]) {
                                votes[t]++;
                            }
                        });
                    });
                    
                    let maxVotes = 0;
                    let bestCands = [];
                    targets.forEach(t => {
                        if (votes[t] > maxVotes) {
                            maxVotes = votes[t];
                            bestCands = [t];
                        } else if (votes[t] === maxVotes && maxVotes > 0) {
                            bestCands.push(t);
                        }
                    });
                    
                    if (bestCands.length > 0) {
                        let results = [];
                        bestCands.forEach(t => {
                            let targetRec = JSON.parse(JSON.stringify(rec));
                            targetRec.settlement = t;
                            targetRec.streets = (targetRec.streets || []).filter(s => s.trim() === street);
                            targetRec.streets_detailed = (targetRec.streets_detailed || []).filter(s => s.name && s.name.trim() === street);
                            results.push(targetRec);
                        });
                        return results;
                    }
                    
                    // Рівень 3: Fallback (дублюємо на всіх кандидатів)
                    let results = [];
                    targets.forEach(t => {
                        let targetRec = JSON.parse(JSON.stringify(rec));
                        targetRec.settlement = t;
                        targetRec.streets = (targetRec.streets || []).filter(s => s.trim() === street);
                        targetRec.streets_detailed = (targetRec.streets_detailed || []).filter(s => s.name && s.name.trim() === street);
                        results.push(targetRec);
                    });
                    return results;
                }
                
                // 4. Оновлюємо archive.json
                let archiveChanged = false;
                let newArchive = [];
                archiveOutages.forEach(rec => {
                    let recSett = rec.settlement || "м. Старокостянтинів";
                    if (getStreetDictKey(recSett) === selectedSettlement) {
                        let hasTargetStreet = false;
                        let streets = rec.streets || [];
                        let streetsDetailed = rec.streets_detailed || [];
                        if (streets.some(s => s.trim() === street) || 
                            streetsDetailed.some(s => s.name && s.name.trim() === street)) {
                            hasTargetStreet = true;
                        }
                        
                        if (hasTargetStreet) {
                            archiveChanged = true;
                            // Отримуємо розподілені/продубльовані записи
                            const routed = routeRecordForTargets(rec);
                            routed.forEach(r => newArchive.push(r));
                            
                            // Залишок у початковому записі
                            let remainingRec = JSON.parse(JSON.stringify(rec));
                            remainingRec.streets = (remainingRec.streets || []).filter(s => s.trim() !== street);
                            remainingRec.streets_detailed = (remainingRec.streets_detailed || []).filter(s => !s.name || s.name.trim() !== street);
                            if (remainingRec.streets.length > 0 || remainingRec.streets_detailed.length > 0) {
                                newArchive.push(remainingRec);
                            }
                        } else {
                            newArchive.push(rec);
                        }
                    } else {
                        newArchive.push(rec);
                    }
                });
                if (archiveChanged) {
                    archiveOutages = newArchive;
                    const archiveStr = JSON.stringify(archiveOutages, null, 2);
                    await commitFileToGitHub("data/archive.json", archiveStr, `Оновлення приналежності вулиці ${street} в архіві (розподілено між [${targetsStr}])`);
                }
                
                // 5. Оновлюємо outages_snapshot.json
                let rawChanged = false;
                let newRaw = [];
                rawOutages.forEach(rec => {
                    let recSett = rec.settlement || "м. Старокостянтинів";
                    if (getStreetDictKey(recSett) === selectedSettlement) {
                        let hasTargetStreet = false;
                        let streets = rec.streets || [];
                        let streetsDetailed = rec.streets_detailed || [];
                        if (streets.some(s => s.trim() === street) || 
                            streetsDetailed.some(s => s.name && s.name.trim() === street)) {
                            hasTargetStreet = true;
                        }
                        
                        if (hasTargetStreet) {
                            rawChanged = true;
                            // Отримуємо розподілені/продубльовані записи
                            const routed = routeRecordForTargets(rec);
                            routed.forEach(r => newRaw.push(r));
                            
                            // Залишок у початковому записі
                            let remainingRec = JSON.parse(JSON.stringify(rec));
                            remainingRec.streets = (remainingRec.streets || []).filter(s => s.trim() !== street);
                            remainingRec.streets_detailed = (remainingRec.streets_detailed || []).filter(s => !s.name || s.name.trim() !== street);
                            if (remainingRec.streets.length > 0 || remainingRec.streets_detailed.length > 0) {
                                newRaw.push(remainingRec);
                            }
                        } else {
                            newRaw.push(rec);
                        }
                    } else {
                        newRaw.push(rec);
                    }
                });
                if (rawChanged) {
                    rawOutages = newRaw;
                    const rawStr = JSON.stringify(rawOutages, null, 2);
                    await commitFileToGitHub("data/outages_snapshot.json", rawStr, `Оновлення приналежності вулиці ${street} в активних відключеннях (розподілено між [${targetsStr}])`);
                }
                
                // 6. Логуємо подію
                await logAddressAction('move_settlement', street, targetsStr, streetData.houses);
                
                renderStreets(document.getElementById('tabContent'));
            }
        };
    }

    if (!window.deleteStreet) {
        window.deleteStreet = async function(street) {
            if (confirm(`Перенести офіційну вулицю '${street}' в розділ сумнівних?\n(Вона буде видалена з офіційного словника, але згадки в архіві залишаться)`)) {
                if (officialStreets[selectedSettlement]) {
                    const streetData = officialStreets[selectedSettlement][street];
                    const houses = streetData ? (streetData.houses || []) : [];
                    
                    delete officialStreets[selectedSettlement][street];
                    if (window.selectedStreet === street) {
                        window.selectedStreet = "";
                    }
                    
                    const jsonStr = JSON.stringify(officialStreets, null, 2);
                    await commitFileToGitHub("data/official_streets.json", jsonStr, `Перенесення вулиці ${street} в сумнівні`);
                    
                    await logAddressAction('move_to_doubtful', street, "", houses);
                    
                    renderStreets(document.getElementById('tabContent'));
                }
            }
        };
    }

    if (!window.whitelistStreet) {
        window.whitelistStreet = async function(street) {
            if (selectedSettlement === "Пісочниця") {
                alert("Для верифікації сумнівної вулиці з Пісочниці, будь ласка, спочатку перенесіть її до правильного населеного пункту за допомогою кнопки 🚚.");
                return;
            }
            if (!officialStreets[selectedSettlement]) {
                officialStreets[selectedSettlement] = {};
            }
            
            const doubtfulHouses = getDoubtfulHousesForStreet(selectedSettlement, street);
            
            officialStreets[selectedSettlement][street] = {
                type: street.toLowerCase().includes("пров") ? "провулок" : "вулиця",
                houses: doubtfulHouses,
                blacklist: []
            };
            
            const jsonStr = JSON.stringify(officialStreets, null, 2);
            await commitFileToGitHub("data/official_streets.json", jsonStr, `Додавання вулиці ${street} до офіційних словників з обіленими будинками`);
            await logAddressAction('whitelist_street', street, "", doubtfulHouses);
            
            renderStreets(document.getElementById('tabContent'));
        };
    }

    if (!window.editDoubtfulStreet) {
        window.editDoubtfulStreet = async function(street) {
            const newName = prompt(`Редагування назви сумнівної вулиці '${street}' для ${selectedSettlement}.\n\nВведіть правильну (нову) назву вулиці:`, street);
            if (newName && newName.trim() && newName.trim() !== street) {
                const nameClean = newName.trim();
                const doubtfulHouses = getDoubtfulHousesForStreet(selectedSettlement, street);
                
                if (!window.streetCorrections) window.streetCorrections = {};
                if (!window.streetCorrections[selectedSettlement]) window.streetCorrections[selectedSettlement] = {};
                window.streetCorrections[selectedSettlement][street] = {
                    action: "rename",
                    target: nameClean,
                    timestamp: new Date().toISOString()
                };
                const correctionsStr = JSON.stringify(window.streetCorrections, null, 2);
                await commitFileToGitHub("data/street_corrections.json", correctionsStr, `Створення правила автокорекції: ${street} -> ${nameClean}`);

                let renamedCount = 0;
                archiveOutages.forEach(rec => {
                    let recSett = rec.settlement || "м. Старокостянтинів";
                    if (getStreetDictKey(recSett) === selectedSettlement) {
                        if (rec.streets) {
                            rec.streets = rec.streets.map(s => s.trim() === street ? nameClean : s);
                        }
                        if (rec.streets_detailed) {
                            rec.streets_detailed.forEach(s_det => {
                                if (s_det.name && s_det.name.trim() === street) {
                                    s_det.name = nameClean;
                                    renamedCount++;
                                }
                            });
                        }
                    }
                });
                
                if (renamedCount > 0) {
                    const archiveStr = JSON.stringify(archiveOutages, null, 2);
                    await commitFileToGitHub("data/archive.json", archiveStr, `Оновлення назви вулиці з ${street} на ${nameClean} в архіві`);
                }

                let rawRenamed = 0;
                rawOutages.forEach(rec => {
                    let recSett = rec.settlement || "м. Старокостянтинів";
                    if (getStreetDictKey(recSett) === selectedSettlement) {
                        if (rec.streets) {
                            rec.streets = rec.streets.map(s => s.trim() === street ? nameClean : s);
                        }
                        if (rec.streets_detailed) {
                            rec.streets_detailed.forEach(s_det => {
                                if (s_det.name && s_det.name.trim() === street) {
                                    s_det.name = nameClean;
                                    rawRenamed++;
                                }
                            });
                        }
                    }
                });
                if (rawRenamed > 0) {
                    const rawStr = JSON.stringify(rawOutages, null, 2);
                    await commitFileToGitHub("data/outages_snapshot.json", rawStr, `Оновлення назви вулиці з ${street} на ${nameClean} в активних відключеннях`);
                }

                await logAddressAction('rename_doubtful', street, nameClean, doubtfulHouses);
                renderStreets(document.getElementById('tabContent'));
            }
        };
    }

    if (!window.deleteDoubtfulStreet) {
        window.deleteDoubtfulStreet = async function(street) {
            const doubtfulHouses = getDoubtfulHousesForStreet(selectedSettlement, street);
            if (confirm(`Повністю видалити сумнівну вулицю '${street}'?\n(Це прибере її та пов'язані з нею будинки ${JSON.stringify(doubtfulHouses)} з архіву відключень, а також створить правило ігнорування)`)) {
                
                if (!window.streetCorrections) window.streetCorrections = {};
                if (!window.streetCorrections[selectedSettlement]) window.streetCorrections[selectedSettlement] = {};
                window.streetCorrections[selectedSettlement][street] = {
                    action: "delete",
                    timestamp: new Date().toISOString()
                };
                const correctionsStr = JSON.stringify(window.streetCorrections, null, 2);
                await commitFileToGitHub("data/street_corrections.json", correctionsStr, `Створення правила ігнорування для ${street}`);

                let changedArchive = false;
                archiveOutages.forEach(rec => {
                    let recSett = rec.settlement || "м. Старокостянтинів";
                    if (getStreetDictKey(recSett) === selectedSettlement) {
                        if (rec.streets) {
                            const len = rec.streets.length;
                            rec.streets = rec.streets.filter(s => s.trim() !== street);
                            if (rec.streets.length !== len) changedArchive = true;
                        }
                        if (rec.streets_detailed) {
                            const len = rec.streets_detailed.length;
                            rec.streets_detailed = rec.streets_detailed.filter(s_det => !s_det.name || s_det.name.trim() !== street);
                            if (rec.streets_detailed.length !== len) changedArchive = true;
                        }
                    }
                });
                if (changedArchive) {
                    const archiveStr = JSON.stringify(archiveOutages, null, 2);
                    await commitFileToGitHub("data/archive.json", archiveStr, `Видалення вулиці ${street} та її будинків з архіву`);
                }

                let changedRaw = false;
                rawOutages.forEach(rec => {
                    let recSett = rec.settlement || "м. Старокостянтинів";
                    if (getStreetDictKey(recSett) === selectedSettlement) {
                        if (rec.streets) {
                            const len = rec.streets.length;
                            rec.streets = rec.streets.filter(s => s.trim() !== street);
                            if (rec.streets.length !== len) changedRaw = true;
                        }
                        if (rec.streets_detailed) {
                            const len = rec.streets_detailed.length;
                            rec.streets_detailed = rec.streets_detailed.filter(s_det => !s_det.name || s_det.name.trim() !== street);
                            if (rec.streets_detailed.length !== len) changedRaw = true;
                        }
                    }
                });
                if (changedRaw) {
                    const rawStr = JSON.stringify(rawOutages, null, 2);
                    await commitFileToGitHub("data/outages_snapshot.json", rawStr, `Видалення вулиці ${street} з активних відключень`);
                }

                await logAddressAction('delete_doubtful', street, "", doubtfulHouses);
                renderStreets(document.getElementById('tabContent'));
            }
        };
    }

    if (!window.hideDoubtfulStreet) {
        window.hideDoubtfulStreet = async function(street) {
            const doubtfulHouses = getDoubtfulHousesForStreet(selectedSettlement, street);
            if (confirm(`Приховати сумнівну вулицю '${street}' з публікацій?\n(Вона залишиться в базі даних та архіві, але не буде відображатися в Telegram та новинах)`)) {
                
                if (!window.streetCorrections) window.streetCorrections = {};
                if (!window.streetCorrections[selectedSettlement]) window.streetCorrections[selectedSettlement] = {};
                window.streetCorrections[selectedSettlement][street] = {
                    action: "hide",
                    timestamp: new Date().toISOString()
                };
                const correctionsStr = JSON.stringify(window.streetCorrections, null, 2);
                await commitFileToGitHub("data/street_corrections.json", correctionsStr, `Створення правила приховування для ${street}`);

                await logAddressAction('hide_doubtful', street, "", doubtfulHouses);
                renderStreets(document.getElementById('tabContent'));
            }
        };
    }

    if (!window.deleteCorrectionRule) {
        window.deleteCorrectionRule = async function(street) {
            if (confirm(`Видалити правило автокорекції для '${street}'?`)) {
                if (window.streetCorrections && window.streetCorrections[selectedSettlement]) {
                    const oldRule = window.streetCorrections[selectedSettlement][street];
                    delete window.streetCorrections[selectedSettlement][street];
                    
                    const correctionsStr = JSON.stringify(window.streetCorrections, null, 2);
                    await commitFileToGitHub("data/street_corrections.json", correctionsStr, `Видалення правила автокорекції для ${street}`);
                    
                    await logAddressAction('delete_rule', street, oldRule ? oldRule.target : "", []);
                    renderStreets(document.getElementById('tabContent'));
                }
            }
        };
    }

    if (!window.addHouse) {
        window.addHouse = async function() {
            const val = document.getElementById('newHouseInput').value.trim();
            if (!val) return;
            const currentStreet = window.selectedStreet;
            if (!currentStreet || !officialStreets[selectedSettlement][currentStreet]) return;
            
            let houses = officialStreets[selectedSettlement][currentStreet].houses || [];
            if (houses.includes(val)) {
                alert('Цей будинок вже є у списку!');
                return;
            }
            houses.push(val);
            // Нормалізуємо та об'єднуємо
            houses = Array.from(new Set(houses.map(h => h.trim()).filter(h => h.length > 0)));
            officialStreets[selectedSettlement][currentStreet].houses = houses;
            
            const jsonStr = JSON.stringify(officialStreets, null, 2);
            await commitFileToGitHub("data/official_streets.json", jsonStr, `Додавання будинку ${val} на ${currentStreet}`);
            await logAddressAction('add_house', currentStreet, "", [val]);
            
            renderStreets(document.getElementById('tabContent'));
        };
    }

    if (!window.deleteHouse) {
        window.deleteHouse = async function(houseNum) {
            const currentStreet = window.selectedStreet;
            if (!currentStreet || !officialStreets[selectedSettlement][currentStreet]) return;
            
            if (confirm(`Видалити будинок ${houseNum} зі списку для ${currentStreet}?`)) {
                let houses = officialStreets[selectedSettlement][currentStreet].houses || [];
                houses = houses.filter(h => h !== houseNum);
                officialStreets[selectedSettlement][currentStreet].houses = houses;
                
                const jsonStr = JSON.stringify(officialStreets, null, 2);
                await commitFileToGitHub("data/official_streets.json", jsonStr, `Вилучення будинку ${houseNum} з ${currentStreet}`);
                await logAddressAction('delete_house', currentStreet, "", [houseNum]);
                
                renderStreets(document.getElementById('tabContent'));
            }
        };
    }

    if (!window.whitelistHouse) {
        window.whitelistHouse = async function(houseNum) {
            const currentStreet = window.selectedStreet;
            if (!currentStreet || !officialStreets[selectedSettlement][currentStreet]) return;
            
            let houses = officialStreets[selectedSettlement][currentStreet].houses || [];
            if (!houses.includes(houseNum)) {
                houses.push(houseNum);
            }
            // Нормалізуємо та об'єднуємо
            houses = Array.from(new Set(houses.map(h => h.trim()).filter(h => h.length > 0)));
            officialStreets[selectedSettlement][currentStreet].houses = houses;
            
            const jsonStr = JSON.stringify(officialStreets, null, 2);
            await commitFileToGitHub("data/official_streets.json", jsonStr, `Обілення будинку ${houseNum} на ${currentStreet}`);
            await logAddressAction('whitelist_house', currentStreet, "", [houseNum]);
            
            renderStreets(document.getElementById('tabContent'));
        };
    }

    if (!window.editOfficialHouse) {
        window.editOfficialHouse = async function(houseNum) {
            const currentStreet = window.selectedStreet;
            if (!currentStreet || !officialStreets[selectedSettlement]?.[currentStreet]) return;

            const newNum = prompt(`Редагувати офіційний номер будинку '${houseNum}' для ${currentStreet}:`, houseNum);
            if (newNum && newNum.trim() && newNum.trim() !== houseNum) {
                const cleanedNum = newNum.trim();
                let houses = officialStreets[selectedSettlement][currentStreet].houses || [];
                const idx = houses.indexOf(houseNum);
                if (idx > -1) {
                    houses[idx] = cleanedNum;
                } else {
                    houses.push(cleanedNum);
                }
                // Нормалізуємо та об'єднуємо (видаляємо можливі дублікати після перейменування)
                houses = Array.from(new Set(houses.map(h => h.trim()).filter(h => h.length > 0)));
                officialStreets[selectedSettlement][currentStreet].houses = houses;
                
                const jsonStr = JSON.stringify(officialStreets, null, 2);
                await commitFileToGitHub("data/official_streets.json", jsonStr, `Редагування будинку на ${currentStreet}: ${houseNum} -> ${cleanedNum}`);
                await logAddressAction('edit_official_house', currentStreet, `${houseNum} -> ${cleanedNum}`, [cleanedNum]);
                
                renderStreets(document.getElementById('tabContent'));
            }
        };
    }

    if (!window.editDoubtfulHouse) {
        window.editDoubtfulHouse = async function(houseNum) {
            const currentStreet = window.selectedStreet;
            if (!currentStreet || !officialStreets[selectedSettlement]?.[currentStreet]) return;

            const newNum = prompt(`Виправити помилковий номер '${houseNum}' на правильний:`, houseNum);
            if (newNum && newNum.trim() && newNum.trim() !== houseNum) {
                const cleanedNum = newNum.trim();
                
                if (!officialStreets[selectedSettlement][currentStreet].blacklist) {
                    officialStreets[selectedSettlement][currentStreet].blacklist = [];
                }
                if (!officialStreets[selectedSettlement][currentStreet].blacklist.includes(houseNum)) {
                    officialStreets[selectedSettlement][currentStreet].blacklist.push(houseNum);
                }

                if (!officialStreets[selectedSettlement][currentStreet].houses) {
                    officialStreets[selectedSettlement][currentStreet].houses = [];
                }
                if (!officialStreets[selectedSettlement][currentStreet].houses.includes(cleanedNum)) {
                    officialStreets[selectedSettlement][currentStreet].houses.push(cleanedNum);
                }
                
                // Нормалізуємо та об'єднуємо
                let houses = officialStreets[selectedSettlement][currentStreet].houses || [];
                houses = Array.from(new Set(houses.map(h => h.trim()).filter(h => h.length > 0)));
                officialStreets[selectedSettlement][currentStreet].houses = houses;
                
                const jsonStr = JSON.stringify(officialStreets, null, 2);
                await commitFileToGitHub("data/official_streets.json", jsonStr, `Виправлення сумнівного будинку на ${currentStreet}: ${houseNum} -> ${cleanedNum}`);
                await logAddressAction('correct_doubtful_house', currentStreet, `${houseNum} -> ${cleanedNum}`, [cleanedNum]);

                renderStreets(document.getElementById('tabContent'));
            }
        };
    }

    if (!window.ignoreDoubtfulHouse) {
        window.ignoreDoubtfulHouse = async function(houseNum) {
            const currentStreet = window.selectedStreet;
            if (!currentStreet || !officialStreets[selectedSettlement]?.[currentStreet]) return;

            if (confirm(`Занести номер '${houseNum}' до чорного списку для ${currentStreet}?\nВін буде ігноруватись і зникне з виявлених сумнівних будинків.`)) {
                if (!officialStreets[selectedSettlement][currentStreet].blacklist) {
                    officialStreets[selectedSettlement][currentStreet].blacklist = [];
                }
                if (!officialStreets[selectedSettlement][currentStreet].blacklist.includes(houseNum)) {
                    officialStreets[selectedSettlement][currentStreet].blacklist.push(houseNum);
                }
                
                const jsonStr = JSON.stringify(officialStreets, null, 2);
                await commitFileToGitHub("data/official_streets.json", jsonStr, `Ігнорування будинку ${houseNum} на ${currentStreet}`);
                await logAddressAction('ignore_doubtful_house', currentStreet, "", [houseNum]);
                
                renderStreets(document.getElementById('tabContent'));
            }
        };
    }

    if (!window.saveStreetsToGitHub) {
        window.saveStreetsToGitHub = function() {
            const jsonStr = JSON.stringify(officialStreets, null, 2);
            commitFileToGitHub("data/official_streets.json", jsonStr, `Оновлення словника адрес для ${selectedSettlement} вручну`);
        };
    }

    if (!window.exportStreetsCSV) {
        window.exportStreetsCSV = function() {
            let csvContent = "\uFEFF";
            csvContent += "Населений пункт,Вулиця,Тип,Будинки\n";
            for (const settlement in officialStreets) {
                for (const street in officialStreets[settlement]) {
                    const data = officialStreets[settlement][street];
                    const housesStr = (data.houses || []).join("; ");
                    csvContent += `"${settlement.replace(/"/g, '""')}","${street.replace(/"/g, '""')}","${(data.type || 'вулиця').replace(/"/g, '""')}","${housesStr.replace(/"/g, '""')}"\n`;
                }
            }
            const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
            const link = document.createElement("a");
            const url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            const dateStr = formatDateISO(new Date());
            link.setAttribute("download", `official_streets_${dateStr}.csv`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        };
    }

    if (!window.filterStreets) {
        window.filterStreets = function() {
            let input = document.getElementById("streetSearch").value.toLowerCase();
            let lis = document.querySelectorAll(".streets-list li");
            lis.forEach(li => {
                let txtValue = li.textContent || li.innerText;
                txtValue = txtValue.replace('✅ Обілити', '').replace('✏️', '').replace('🗑️', '');
                if (txtValue.toLowerCase().indexOf(input) > -1) {
                    li.style.display = "";
                } else {
                    li.style.display = "none";
                }
            });
        };
    }
}

function renderArchive(container) {
    let html = `<h3>Архів подій відключень (${archiveOutages.length} записів)</h3>`;
    if (archiveOutages.length === 0) {
        html += '<p class="empty">Архів порожній.</p>';
    } else {
        html += `<div style="overflow-x:auto;">
            <table class="archive-table" style="width:100%; border-collapse:collapse; margin-top:10px;">
                <thead>
                    <tr style="background:var(--border); text-align:left;">
                        <th style="padding:10px; border-bottom:1px solid var(--border);">Населений пункт</th>
                        <th style="padding:10px; border-bottom:1px solid var(--border);">Тип</th>
                        <th style="padding:10px; border-bottom:1px solid var(--border);">Початок</th>
                        <th style="padding:10px; border-bottom:1px solid var(--border);">Кінець</th>
                        <th style="padding:10px; border-bottom:1px solid var(--border);">Вулиці та будинки</th>
                    </tr>
                </thead>
                <tbody>`;
        [...archiveOutages].reverse().forEach(rec => {
            let streetsHtml = '';
            if (rec.streets_detailed && rec.streets_detailed.length > 0) {
                streetsHtml = rec.streets_detailed.map(s => `<strong>${escapeHtml(s.name)}</strong>: ${escapeHtml(s.houses)}`).join('<br>');
            } else if (rec.streets && rec.streets.length > 0) {
                streetsHtml = rec.streets.map(s => `<strong>${escapeHtml(s)}</strong>`).join(', ');
            } else {
                streetsHtml = '<span style="color:#888;">не вказано</span>';
            }
            
            const startStr = rec.start_datetime ? formatDateTimeParts(rec.start_datetime).full : '-';
            const endStr = rec.end_datetime ? formatDateTimeParts(rec.end_datetime).full : '-';

            html += `<tr style="border-bottom: 1px solid var(--border);">
                <td style="padding:10px;">${escapeHtml(rec.settlement || 'Старокостянтинів')}</td>
                <td style="padding:10px;"><span class="badge ${rec.type && rec.type.includes('Аварійні') ? 'badge-danger' : 'badge-warning'}">${escapeHtml(rec.type || 'Планові')}</span></td>
                <td style="padding:10px; font-size:13px;">${escapeHtml(startStr)}</td>
                <td style="padding:10px; font-size:13px;">${escapeHtml(endStr)}</td>
                <td style="padding:10px; font-size:13px; max-width:400px; word-break:break-all;">${streetsHtml}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }
    container.innerHTML = html;
}

window.toggleRawView = function() {
    window.showRawJson = !window.showRawJson;
    const container = document.getElementById('tabContent');
    if (container) renderRaw(container);
}

function renderRaw(container) {
    let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:15px;">
            <h3 style="margin:0;">Поточний знімок відключень (${rawOutages.length} активних записів)</h3>
            <div style="display:flex; gap:10px;">
                <button class="btn btn-secondary" onclick="window.toggleRawView()">
                    ${window.showRawJson ? '📋 Показати Таблицю' : '⚙️ Показати RAW JSON'}
                </button>
                <button class="btn btn-primary" onclick="loadData()">🔄 Оновити</button>
            </div>
        </div>
    `;
    
    if (rawOutages.length === 0) {
        html += '<p class="empty">Немає активних відключень у знімку.</p>';
    } else if (window.showRawJson) {
        html += `<pre style="background:var(--border); padding:15px; border-radius:var(--radius); overflow:auto; max-height:500px; font-size:12px; color:var(--text);">${escapeHtml(JSON.stringify(rawOutages, null, 2))}</pre>`;
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
                    let housesStr = s.houses ? ` <span class="house-numbers" style="color:var(--secondary-text); font-size: 11px;">(буд. ${escapeHtml(s.houses)})</span>` : '';
                    return `<div class="street-item" style="margin-bottom: 5px;"><strong>${escapeHtml(s.name)}</strong>${housesStr}</div>`;
                }).join('');
            } else if (rec.streets && rec.streets.length > 0) {
                streetsHtml = rec.streets.map(s => `<div class="street-item" style="margin-bottom: 5px;"><strong>${escapeHtml(s)}</strong></div>`).join('');
            }
                
            let typeStyle = rec.type && rec.type.includes('Аварійні') ? 'color: var(--danger); font-weight: bold;' : 'color: var(--warning); font-weight: bold;';

            html += `<tr>
                <td><strong>${escapeHtml(rec.settlement || 'Невідомо')}</strong></td>
                <td style="${typeStyle}">${escapeHtml(rec.type || 'Невідомо')}</td>
                <td style="font-size:13px; white-space:nowrap;">${escapeHtml(dtStart)}<br>${escapeHtml(dtEnd)}</td>
                <td style="font-size:13px;">${streetsHtml}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }
    container.innerHTML = html;
}

function formatDateUkrainian(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length === 3) {
        return `${parts[2]}.${parts[1]}.${parts[0]}`;
    }
    return dateStr;
}

function renderMsgArchive(container) {
    container.innerHTML = `
        <h3>Архів повідомлень та публікацій</h3>
        <p style="font-size: 13px; color: var(--secondary-text); margin-bottom: 15px;">
            Оберіть дату, щоб переглянути згенеровані тексти стрічки новин, Telegram-постів та історію їх формування.
        </p>
        <div style="margin-bottom: 20px; display: flex; align-items: center; gap: 10px;">
            <label for="msgArchiveDate" style="font-weight: bold;">Оберіть дату:</label>
            <input type="date" id="msgArchiveDate" class="input" style="padding: 6px 12px; border-radius: 4px; border: 1px solid var(--border); background: var(--bg); color: var(--text);" onchange="window.showArchivedMessages()">
        </div>
        <div id="msgArchiveResult"></div>
    `;
}

window.showArchivedMessages = function() {
    const dateStr = document.getElementById('msgArchiveDate').value;
    const resultDiv = document.getElementById('msgArchiveResult');
    if (!dateStr) { resultDiv.innerHTML = ''; return; }
    
    const relevant = messages.filter(m => m.date === dateStr);
    const dayObj = feedData.days && feedData.days.find(d => d.date === dateStr);
    
    if (relevant.length === 0 && !dayObj) {
        resultDiv.innerHTML = '<p class="empty">На цю дату публікацій не знайдено в архіві.</p>';
        return;
    }
    
    const feedToday = relevant.find(m => m.type === 'feed_today');
    const feedTomorrow = relevant.find(m => m.type === 'feed_tomorrow');
    const tgPlanneds = relevant.filter(m => m.type === 'tg_planned').sort((a, b) => a.id.localeCompare(b.id));
    const tgEmergencies = relevant.filter(m => m.type === 'tg_emergency').sort((a, b) => a.id.localeCompare(b.id));
    
    let html = `
        <div style="margin-top: 20px; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 15px;">
            <h4 style="margin:0;">Результати формування для дати: ${escapeHtml(formatDateUkrainian(dateStr))}</h4>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 15px;">
            <div>
                <h5 style="margin-bottom: 10px; color: var(--primary); font-size: 14px;">🌐 Стрічка новин на цей день</h5>
                <div style="padding:15px; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius); margin-bottom: 15px;">
                    <h6 style="margin: 0 0 8px 0; font-size: 13px;">Актуальний текст стрічки (на сьогодні):</h6>
                    <textarea class="feed-textarea" style="height: 150px; font-size:12px; width: 100%; font-family: sans-serif; resize: vertical;" readonly>${escapeHtml(feedToday ? feedToday.content : (dayObj ? dayObj.actual_content : 'Дані відсутні'))}</textarea>
                    ${feedToday || (dayObj && dayObj.actual_content) ? `
                    <div style="margin-top: 8px;">
                        <button class="btn btn-primary" style="padding: 4px 10px; font-size: 12px;" onclick="copyToClipboard(this.parentElement.previousElementSibling.value)">📋 Копіювати текст</button>
                    </div>` : ''}
                </div>
                
                <div style="padding:15px; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius);">
                    <h6 style="margin: 0 0 8px 0; font-size: 13px;">Плановий текст стрічки (на завтра):</h6>
                    <textarea class="feed-textarea" style="height: 120px; font-size:12px; width: 100%; font-family: sans-serif; resize: vertical;" readonly>${escapeHtml(feedTomorrow ? feedTomorrow.content : (dayObj ? dayObj.planned_content : 'Дані відсутні'))}</textarea>
                    ${feedTomorrow || (dayObj && dayObj.planned_content) ? `
                    <div style="margin-top: 8px;">
                        <button class="btn btn-primary" style="padding: 4px 10px; font-size: 12px;" onclick="copyToClipboard(this.parentElement.previousElementSibling.value)">📋 Копіювати текст</button>
                    </div>` : ''}
                </div>
            </div>
            
            <div>
                <h5 style="margin-bottom: 10px; color: var(--primary); font-size: 14px;">✈️ Telegram-повідомлення</h5>
                
                <!-- Planned Telegram Messages -->
                ${tgPlanneds.length === 0 ? `
                <div style="padding:15px; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius); margin-bottom: 15px;">
                    <h6 style="margin: 0 0 8px 0; font-size: 13px;">🟡 Планові відключення:</h6>
                    <textarea class="feed-textarea" style="height: 120px; font-size:12px; font-family: monospace; width: 100%; resize: vertical;" readonly>Дані відсутні</textarea>
                </div>
                ` : tgPlanneds.map((msg, partIdx) => {
                    const label = tgPlanneds.length > 1 ? `🟡 Планові відключення (Частина ${partIdx + 1}):` : `🟡 Планові відключення:`;
                    return `
                    <div style="padding:15px; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius); margin-bottom: 15px;">
                        <h6 style="margin: 0 0 8px 0; font-size: 13px; display:flex; justify-content:space-between; align-items: center;">
                            <span>${label}</span>
                            ${msg.created_at ? `<span style="font-weight:normal; font-size:10px; color:var(--secondary-text);">Створено: ${formatDateTimeParts(msg.created_at).time}</span>` : ''}
                        </h6>
                        <textarea class="feed-textarea" style="height: 120px; font-size:12px; font-family: monospace; width: 100%; resize: vertical;" readonly>${escapeHtml(msg.content)}</textarea>
                        <div style="margin-top: 8px;">
                            <button class="btn btn-primary" style="padding: 4px 10px; font-size: 12px;" onclick="copyToClipboard(this.parentElement.previousElementSibling.value)">📋 Копіювати текст</button>
                        </div>
                    </div>
                    `;
                }).join('')}
                
                <!-- Emergency Telegram Messages -->
                ${tgEmergencies.length === 0 ? `
                <div style="padding:15px; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius);">
                    <h6 style="margin: 0 0 8px 0; font-size: 13px;">🔴 Аварійні відключення:</h6>
                    <textarea class="feed-textarea" style="height: 120px; font-size:12px; font-family: monospace; width: 100%; resize: vertical;" readonly>Дані відсутні</textarea>
                </div>
                ` : tgEmergencies.map((msg, partIdx) => {
                    const label = tgEmergencies.length > 1 ? `🔴 Аварійні відключення (Частина ${partIdx + 1}):` : `🔴 Аварійні відключення:`;
                    return `
                    <div style="padding:15px; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius); margin-bottom: ${partIdx < tgEmergencies.length - 1 ? '15px' : '0'};">
                        <h6 style="margin: 0 0 8px 0; font-size: 13px; display:flex; justify-content:space-between; align-items: center;">
                            <span>${label}</span>
                            ${msg.created_at ? `<span style="font-weight:normal; font-size:10px; color:var(--secondary-text);">Створено: ${formatDateTimeParts(msg.created_at).time}</span>` : ''}
                        </h6>
                        <textarea class="feed-textarea" style="height: 120px; font-size:12px; font-family: monospace; width: 100%; resize: vertical;" readonly>${escapeHtml(msg.content)}</textarea>
                        <div style="margin-top: 8px;">
                            <button class="btn btn-primary" style="padding: 4px 10px; font-size: 12px;" onclick="copyToClipboard(this.parentElement.previousElementSibling.value)">📋 Копіювати text</button>
                        </div>
                    </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
    
    if (dayObj && dayObj.history && dayObj.history.length > 0) {
        html += `
            <div style="margin-top: 25px;">
                <h5 style="margin-bottom: 10px; color: var(--primary); font-size: 14px;">⏱️ Історія оновлень стрічки протягом дня (${dayObj.history.length})</h5>
                <div style="max-height: 350px; overflow-y: auto; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg); padding: 10px; display: flex; flex-direction: column; gap: 10px;">
        `;
        
        [...dayObj.history].reverse().forEach((version, idx) => {
            const timeStr = formatDateTimeParts(version.timestamp).full;
            const isAnomalyLabel = version.is_anomaly ? ' <span class="badge badge-danger" style="padding: 2px 5px; font-size: 9px; margin-left:5px;">Аномалія</span>' : '';
            html += `
                <div style="padding: 10px; background: rgba(0,0,0,0.01); border: 1px solid var(--border); border-radius: 4px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px; font-weight:bold; font-size: 12px; color:var(--secondary-text);">
                        <span>Версія від ${escapeHtml(timeStr)}${isAnomalyLabel}</span>
                        <button class="btn btn-secondary" style="padding: 2px 8px; font-size: 11px;" onclick="copyToClipboard(this.parentElement.parentElement.querySelector('pre').textContent)">📋 Копіювати версію</button>
                    </div>
                    <pre style="white-space: pre-wrap; font-size: 12px; margin: 0; background: var(--border); padding: 8px; border-radius: 4px; color: var(--text); font-family: sans-serif; max-height: 120px; overflow-y: auto;">${escapeHtml(version.content)}</pre>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    }
    
    resultDiv.innerHTML = html;
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
    
    if (last.status === 'html_structure_error' || last.status === 'http_error' || last.status === 'error' || last.status === 'structure_error') {
        statusClass = 'status-error';
        icon = '🔴';
        text = `Помилка: ${escapeHtml(last.message || last.status)}.`;
    } else if (last.status === 'warning') {
        statusClass = 'status-warning';
        icon = '⚠️';
        text = `Попередження: ${escapeHtml(last.message || last.status)}.`;
    } else {
        const timeStr = last.timestamp ? formatDateTimeParts(last.timestamp).full : 'Невідомо';
        text = `Остання перевірка: ${escapeHtml(timeStr)} (${escapeHtml(last.message || 'успішно')}).`;
    }
    area.innerHTML = `<div class="status-bar ${statusClass}">${icon} ${text}</div>`;
}

window.copyToClipboard = function(text) {
    navigator.clipboard.writeText(text).then(() => alert('Скопійовано!'));
}

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
