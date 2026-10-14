// ═════ app.js — все спринты + перф-патчи ═════

let API = null;
let TRANSLATIONS = {};
let LANG_NAMES = {};
let currentLang = 'ru';
let currentTheme = 'dark';
let settings = {};
let trackItems = {};
let isPaused = false;
let lastDownloadFolder = '';

let previewTracks = [];
let previewSelected = new Set();
let previewFiltered = [];

const THEME_META = {
  dark:    { icon: '🌙', label: 'Dark',        swatch: ['#0f1117', '#4fc3d9', '#c77dff'] },
  sunset:  { icon: '🌅', label: 'Sunset',      swatch: ['#1a0f1a', '#ff8a5b', '#ff5c8a'] },
  emerald: { icon: '🌲', label: 'Emerald',     swatch: ['#0a1410', '#4ade80', '#34d399'] },
  amoled:  { icon: '⬛', label: 'AMOLED',      swatch: ['#000000', '#4fc3d9', '#c77dff'] },
  light:   { icon: '☀️', label: 'Light',       swatch: ['#f4f6fb', '#2563eb', '#9333ea'] },
  lunar:   { icon: '🌌', label: 'Lunar Blue',  swatch: ['#070f1c', '#4a9eff', '#2ee6a6'] },
  samurai: { icon: '🎴', label: 'Samurai Ink', swatch: ['#f5f0e6', '#e60012', '#2a9d5c'] },
  matte:   { icon: '🖤', label: 'Matte Black', swatch: ['#0b0b0d', '#a8b0c0', '#3ddc97'] },
  neonic:  { icon: '💜', label: 'Neonic',      swatch: ['#0a0a0a', '#9b5cff', '#7cffb2'] },
};
const THEMES = Object.keys(THEME_META);

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function t(key) {
  const dict = TRANSLATIONS[currentLang] || TRANSLATIONS['ru'] || {};
  return dict[key] ?? (TRANSLATIONS['ru'] ? TRANSLATIONS['ru'][key] : null) ?? key;
}

function applyI18n() {
  $$('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const val = t(key);
    if (val) el.textContent = val;
  });
  $$('[data-i18n-ph]').forEach(el => {
    const val = t(el.dataset.i18nPh);
    if (val) el.placeholder = val;
  });
  $$('[data-i18n-title]').forEach(el => {
    const val = t(el.dataset.i18nTitle);
    if (val) el.title = val;
  });
  updateSaveUrlBtn();
  updateLangLabel();
  if (typeof renderCalendar === 'function') renderCalendar();
}

// ═════ ЗВЁЗДЫ ═════
function initStars() {
  try {
    if (localStorage.getItem('ymd-stars-off') === '1') return;
  } catch (e) {}

  const container = document.getElementById('stars');
  if (!container) return;
  const COUNT = 12;
  const frag = document.createDocumentFragment();
  for (let i = 0; i < COUNT; i++) {
    const s = document.createElement('div');
    s.className = 'star';
    const size     = (Math.random() * 1.6 + 1).toFixed(2);
    const x        = (Math.random() * 100).toFixed(2);
    const y        = (Math.random() * 100).toFixed(2);
    const twDur    = (Math.random() * 4 + 3).toFixed(2);
    const twDelay  = (Math.random() * 6).toFixed(2);
    const drDur    = (Math.random() * 60 + 60).toFixed(1);
    const drDelay  = -(Math.random() * 60).toFixed(1);
    s.style.cssText = `
      left: ${x}%; top: ${y}%;
      width: ${size}px; height: ${size}px;
      --tw-dur: ${twDur}s; --tw-delay: ${twDelay}s;
      --dr-dur: ${drDur}s; --dr-delay: ${drDelay}s;
    `;
    frag.appendChild(s);
  }
  container.appendChild(frag);
}

window.disableStars = () => {
  try { localStorage.setItem('ymd-stars-off', '1'); } catch (e) {}
  const c = document.getElementById('stars');
  if (c) c.innerHTML = '';
};
window.enableStars = () => {
  try { localStorage.setItem('ymd-stars-off', '0'); } catch (e) {}
  const c = document.getElementById('stars');
  if (c) { c.innerHTML = ''; initStars(); }
};

// ═════ THEME ═════
function applyTheme(code, animate = true) {
  if (!THEMES.includes(code)) code = 'dark';
  currentTheme = code;
  if (animate) {
    document.documentElement.classList.add('theme-switching');
    setTimeout(() => document.documentElement.classList.remove('theme-switching'), 600);
  }
  document.documentElement.setAttribute('data-theme', code);
  try { localStorage.setItem('ymd-theme', code); } catch (e) {}
  const meta = THEME_META[code];
  if (meta) {
    const lbl = $('#theme-label');
    if (lbl) lbl.textContent = meta.label;
    const icon = $('#theme-btn .picker-icon');
    if (icon) icon.textContent = meta.icon;
  }
  $$('#theme-dropdown .picker-item').forEach(el => {
    el.classList.toggle('active', el.dataset.theme === code);
  });
}

function buildThemePicker() {
  const dd = $('#theme-dropdown');
  if (!dd) return;
  dd.innerHTML = '';
  for (const code of THEMES) {
    const m = THEME_META[code];
    const btn = document.createElement('button');
    btn.className = 'picker-item';
    btn.dataset.theme = code;
    btn.type = 'button';
    btn.innerHTML = `
      <span class="flag">${m.icon}</span>
      <span>${m.label}</span>
      <span class="swatches">${m.swatch.map(c => `<span class="swatch" style="background:${c}"></span>`).join('')}</span>
    `;
    btn.addEventListener('click', () => {
      applyTheme(code);
      closePicker('#theme-picker');
      saveSettings();
    });
    dd.appendChild(btn);
  }
}

// ═════ LANG ═════
function updateLangLabel() {
  const lbl = $('#lang-label');
  if (lbl) lbl.textContent = LANG_NAMES[currentLang] || currentLang;
  $$('#lang-dropdown .picker-item').forEach(el => {
    el.classList.toggle('active', el.dataset.lang === currentLang);
  });
}

function buildLangPicker() {
  const dd = $('#lang-dropdown');
  if (!dd) return;
  dd.innerHTML = '';
  for (const [code, name] of Object.entries(LANG_NAMES)) {
    const btn = document.createElement('button');
    btn.className = 'picker-item';
    btn.dataset.lang = code;
    btn.type = 'button';
    btn.innerHTML = `<span>${name}</span>`;
    btn.addEventListener('click', () => {
      switchLanguage(code);
      closePicker('#lang-picker');
    });
    dd.appendChild(btn);
  }
  updateLangLabel();
}

function switchLanguage(code) {
  if (code === currentLang) return;
  document.body.classList.add('lang-switching');
  setTimeout(() => {
    currentLang = code;
    try { localStorage.setItem('ymd-lang', code); } catch (e) {}
    document.documentElement.setAttribute('lang', code);
    applyI18n();
    document.body.classList.remove('lang-switching');
    saveSettings();
  }, 220);
}

// ═════ PICKER ═════
function openPicker(sel) {
  $$('.picker').forEach(p => { if ('#' + p.id !== sel) p.classList.remove('open'); });
  const el = $(sel);
  if (el) el.classList.add('open');
}
function closePicker(sel) {
  const el = $(sel);
  if (el) el.classList.remove('open');
}
function togglePicker(sel) {
  const el = $(sel);
  if (!el) return;
  if (el.classList.contains('open')) closePicker(sel);
  else openPicker(sel);
}

// ═════ ЧАСЫ + КАЛЕНДАРЬ ═════
const MONTHS = {
  ru: ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'],
  en: ['January','February','March','April','May','June','July','August','September','October','November','December'],
  uk: ['Січень','Лютий','Березень','Квітень','Травень','Червень','Липень','Серпень','Вересень','Жовтень','Листопад','Грудень'],
  de: ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'],
  fr: ['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre'],
  zh: ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'],
  ja: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
  ko: ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'],
};
const WEEKDAYS = {
  ru: ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'],
  en: ['Mo','Tu','We','Th','Fr','Sa','Su'],
  uk: ['Пн','Вт','Ср','Чт','Пт','Сб','Нд'],
  de: ['Mo','Di','Mi','Do','Fr','Sa','So'],
  fr: ['Lu','Ma','Me','Je','Ve','Sa','Di'],
  zh: ['一','二','三','四','五','六','日'],
  ja: ['月','火','水','木','金','土','日'],
  ko: ['월','화','수','목','금','토','일'],
};
const LANG_SHORT = {
  ru:'ru', en:'en', uk:'uk', be:'ru', kk:'ru', uz:'ru',
  tr:'en', ro:'en', de:'de', fr:'fr', it:'en',
  zh:'zh', ja:'ja', ko:'ko',
};

let calViewDate = new Date();

function _langShort() {
  return LANG_SHORT[currentLang] || 'ru';
}

function initClock() {
  const timeEl   = $('#clock-time');
  const dateEl   = $('#clock-date');
  const btn      = $('#clock-btn');
  const widget   = $('#clock-widget');
  const dropdown = $('#clock-dropdown');
  if (!btn || !widget) return;

  let lastHHMM = '';
  const update = () => {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const ss = String(now.getSeconds()).padStart(2, '0');
    if (timeEl) timeEl.textContent = `${hh}:${mm}:${ss}`;

    const hhmm = `${hh}:${mm}`;
    if (hhmm !== lastHHMM) {
      lastHHMM = hhmm;
      const ls = _langShort();
      const wd = WEEKDAYS[ls] || WEEKDAYS.ru;
      const mo = MONTHS[ls]   || MONTHS.ru;
      const weekday = wd[(now.getDay() + 6) % 7];
      if (dateEl) dateEl.textContent = `${weekday}, ${now.getDate()} ${mo[now.getMonth()]} ${now.getFullYear()}`;
    }
  };
  update();
  setInterval(update, 1000);

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    widget.classList.toggle('open');
  });
  if (dropdown) dropdown.addEventListener('click', (e) => e.stopPropagation());
  document.addEventListener('click', () => widget.classList.remove('open'));

  const prev = $('#cal-prev');
  const next = $('#cal-next');
  const todayBtn = $('#cal-today');
  if (prev) prev.addEventListener('click', () => {
    calViewDate = new Date(calViewDate.getFullYear(), calViewDate.getMonth() - 1, 1);
    renderCalendar();
  });
  if (next) next.addEventListener('click', () => {
    calViewDate = new Date(calViewDate.getFullYear(), calViewDate.getMonth() + 1, 1);
    renderCalendar();
  });
  if (todayBtn) todayBtn.addEventListener('click', () => {
    calViewDate = new Date();
    renderCalendar();
  });

  renderCalendar();
}

function renderCalendar() {
  const grid       = $('#cal-grid');
  const monthEl    = $('#cal-month');
  const weekdaysEl = $('#cal-weekdays');
  if (!grid || !monthEl) return;

  const ls = _langShort();
  const wd = WEEKDAYS[ls] || WEEKDAYS.ru;
  const mo = MONTHS[ls]   || MONTHS.ru;

  if (weekdaysEl) weekdaysEl.innerHTML = wd.map(d => `<span>${d}</span>`).join('');
  monthEl.textContent = `${mo[calViewDate.getMonth()]} ${calViewDate.getFullYear()}`;

  const y = calViewDate.getFullYear();
  const m = calViewDate.getMonth();
  const first = new Date(y, m, 1);
  const startWeekday = (first.getDay() + 6) % 7;
  const daysInMonth  = new Date(y, m + 1, 0).getDate();
  const prevMonthDays = new Date(y, m, 0).getDate();

  const today = new Date();
  const isToday = (d) =>
    d.getDate() === today.getDate() &&
    d.getMonth() === today.getMonth() &&
    d.getFullYear() === today.getFullYear();

  const cells = [];
  for (let i = startWeekday - 1; i >= 0; i--) {
    cells.push({ day: prevMonthDays - i, other: true });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, other: false, date: new Date(y, m, d) });
  }
  let nextDay = 1;
  while (cells.length < 42) {
    cells.push({ day: nextDay++, other: true });
  }

  grid.innerHTML = cells.map(c => {
    let cls = 'cal-day';
    if (c.other) cls += ' other';
    else if (isToday(c.date)) cls += ' today';
    return `<div class="${cls}">${c.day}</div>`;
  }).join('');
}

// ═════ STARTUP TOAST ═════
function showStartupToast(sum) {
  const { ok = 0, warn = 0, fail = 0 } = sum || {};

  let icon = '✅';
  let color = 'var(--success)';
  let text = `Готово: ${ok} проверок пройдено`;

  if (fail > 0) {
    icon = '❌';
    color = 'var(--danger)';
    text = `Ошибок: ${fail}, предупреждений: ${warn}`;
  } else if (warn > 0) {
    icon = '⚠️';
    color = 'var(--warn)';
    text = `Предупреждений: ${warn}, всё остальное — ОК`;
  }

  const toast = document.createElement('div');
  toast.className = 'startup-toast';
  toast.style.borderColor = color;
  toast.innerHTML = `
    <span class="emoji">${icon}</span>
    <span class="startup-toast-text">${text}</span>
    <button class="btn ghost tiny startup-toast-close">✕</button>
  `;
  document.body.appendChild(toast);

  requestAnimationFrame(() => toast.classList.add('visible'));

  const close = () => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 400);
  };
  toast.querySelector('.startup-toast-close').addEventListener('click', close);
  setTimeout(close, 6000);
}

// ═════ ADAPTIVE POLLING ═════
let _pollTimer = null;
let _pollInterval = 500;
const POLL_IDLE = 500;
const POLL_ACTIVE = 120;
const POLL_EMPTY_BACKOFF = 800;
let _emptyStreak = 0;

function startAdaptivePolling() {
  stopAdaptivePolling();
  const loop = async () => {
    if (!API) return;
    let events = [];
    try {
      events = await API.poll_events();
    } catch (e) {}

    if (events && events.length) {
      _emptyStreak = 0;
      for (const ev of events) await handleEvent(ev);
      _pollInterval = POLL_ACTIVE;
    } else {
      _emptyStreak++;
      if (_emptyStreak > 6) {
        _pollInterval = POLL_EMPTY_BACKOFF;
      } else if (_emptyStreak > 2) {
        _pollInterval = POLL_IDLE;
      }
    }

    _pollTimer = setTimeout(loop, _pollInterval);
  };
  loop();
}

function stopAdaptivePolling() {
  if (_pollTimer) {
    clearTimeout(_pollTimer);
    _pollTimer = null;
  }
}

function bumpPolling() {
  _emptyStreak = 0;
  _pollInterval = POLL_ACTIVE;
}

// ═════ INIT ═════
async function init() {
  initStars();
  try {
    const cachedTheme = localStorage.getItem('ymd-theme');
    if (cachedTheme) applyTheme(cachedTheme, false);
  } catch (e) {}

  if (!window.pywebview) {
    await new Promise(res => window.addEventListener('pywebviewready', res, { once: true }));
  }
  API = window.pywebview.api;

  const boot = await API.get_bootstrap();
  TRANSLATIONS = boot.translations || {};
  LANG_NAMES   = boot.lang_names || {};
  settings     = boot.settings || {};
  currentLang  = TRANSLATIONS[settings.lang] ? settings.lang : 'ru';

  const v = $('#version');
  if (v) v.textContent = 'v' + (boot.version || '2.0.0');

  buildThemePicker();
  buildLangPicker();
  applyTheme(settings.theme || currentTheme, false);
  initClock();

  loadSettings();
  bindUI();
  applyI18n();

  showPanel('settings');

  if (boot.history && boot.history.pending > 0) showResumeBanner(boot.history);
  if (boot.stats) renderStats(boot.stats);

  setTimeout(() => {
    try { API.run_startup_check(); } catch (e) {}
  }, 400);

  setTimeout(checkUpdates, 2000);
  startAdaptivePolling();
}

function showResumeBanner(hist) {
  const banner = $('#resume-banner');
  if (!banner) return;
  banner.classList.remove('hidden');
  const txt = $('#resume-text');
  if (txt) txt.textContent = `Найдена незавершённая загрузка: ${hist.pending} из ${hist.total} осталось`;
}
function hideResumeBanner() {
  const banner = $('#resume-banner');
  if (banner) banner.classList.add('hidden');
}

// ═════ ПАНЕЛИ ═════
function showPanel(which) {
  const s = document.getElementById('settings-block');
  const p = document.getElementById('preview-block');
  const r = document.getElementById('runtime-block');

  const collapse = (el, isCollapsed) => {
    if (!el) return;
    if (isCollapsed) el.classList.add('collapsed');
    else el.classList.remove('collapsed');
  };

  collapse(s, which !== 'settings');
  collapse(p, which !== 'preview');
  collapse(r, which !== 'runtime');
}

// ═════ UPDATES ═════
async function checkUpdates() {
  try {
    const info = await API.check_update();
    if (info && info.available) showUpdateBanner(info);
  } catch (e) {}
}
function showUpdateBanner(info) {
  const banner = $('#update-banner');
  if (!banner) return;
  $('#update-text').textContent = `Доступна новая версия v${info.version}`;
  banner.dataset.url = info.url || '';
  banner.classList.remove('hidden');
  setTimeout(() => banner.classList.add('visible'), 30);
}
function hideUpdateBanner() {
  const banner = $('#update-banner');
  if (!banner) return;
  banner.classList.remove('visible');
  setTimeout(() => banner.classList.add('hidden'), 400);
}

// ═════ STATS ═════
function renderStats(stats) {
  if (!stats) return;
  const total = $('#stats-total');
  const size  = $('#stats-size');
  const top   = $('#stats-top');
  if (total) total.textContent = `Скачано: ${stats.count || 0}`;
  if (size)  size.textContent  = stats.total_size_str || '0 Б';
  if (top) {
    const names = (stats.top_artists || []).slice(0, 3).map(a => a.artist).join(', ');
    top.textContent = names ? `Топ: ${names}` : '';
  }
}
async function refreshStats() {
  try {
    const s = await API.get_stats();
    renderStats(s);
  } catch (e) {}
}

// ═════ SETTINGS ═════
function loadSettings() {
  $('#token').value      = settings.token || '';
  $('#url').value        = settings.url || '';
  $('#path').value       = settings.path || '';
  $('#delay').value      = settings.delay ?? 2.0;
  $('#retries').value    = settings.retries ?? 6;
  $('#retry_base').value = settings.retry_base ?? 8;
  $('#quality').value    = settings.quality || 'auto';
  setMode(settings.mode || 'likes');

  const saveUrl = settings.save_url !== false;
  $('#btn-save-url').dataset.on = saveUrl ? '1' : '0';
  updateSaveUrlBtn();

  const cbLyr = $('#save-lyrics');
  if (cbLyr) cbLyr.checked = settings.save_lyrics !== false;

  const cbStruct = $('#folder-structure');
  if (cbStruct) cbStruct.checked = settings.folder_structure === true;
}

function gatherSettings() {
  return {
    token: $('#token').value.trim(),
    url: $('#btn-save-url').dataset.on === '1' ? $('#url').value.trim() : '',
    save_url: $('#btn-save-url').dataset.on === '1',
    path: $('#path').value.trim(),
    mode: getMode(),
    lang: currentLang,
    theme: currentTheme,
    quality: $('#quality').value,
    delay: parseFloat($('#delay').value) || 2.0,
    retries: parseInt($('#retries').value) || 6,
    retry_base: parseInt($('#retry_base').value) || 8,
    save_lyrics: $('#save-lyrics') ? $('#save-lyrics').checked : true,
    folder_structure: $('#folder-structure') ? $('#folder-structure').checked : false,
  };
}

async function saveSettings() {
  settings = gatherSettings();
  try { await API.save_settings(settings); } catch (e) {}
}

function setMode(mode) {
  $$('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
  $('#url').disabled = (mode === 'likes');
}
function getMode() {
  const a = document.querySelector('.mode-btn.active');
  return a ? a.dataset.mode : 'likes';
}
function updateSaveUrlBtn() {
  const btn = $('#btn-save-url');
  if (!btn) return;
  const on = btn.dataset.on === '1';
  btn.textContent = on ? '🔒' : '🔓';
  btn.style.color = on ? 'var(--success)' : 'var(--dim)';
}

// ═════ UI EVENTS ═════
function bindUI() {
  const themeBtn = $('#theme-btn');
  if (themeBtn) themeBtn.addEventListener('click', (e) => { e.stopPropagation(); togglePicker('#theme-picker'); });
  const langBtn = $('#lang-btn');
  if (langBtn) langBtn.addEventListener('click', (e) => { e.stopPropagation(); togglePicker('#lang-picker'); });

  document.addEventListener('click', () => {
    closePicker('#theme-picker');
    closePicker('#lang-picker');
  });
  $$('.picker-dropdown').forEach(dd => dd.addEventListener('click', (e) => e.stopPropagation()));

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closePicker('#theme-picker');
      closePicker('#lang-picker');
      const widget = $('#clock-widget');
      if (widget) widget.classList.remove('open');
      return;
    }
    if (e.ctrlKey && !e.shiftKey && e.key === 'Enter') {
      e.preventDefault();
      const btn = $('#btn-start');
      if (btn && !btn.disabled) btn.click();
      return;
    }
    if (e.ctrlKey && !e.shiftKey && (e.key === 'l' || e.key === 'L')) {
      e.preventDefault();
      clearLog(); appendLog('[i] Лог очищен');
      return;
    }
    if (e.ctrlKey && e.shiftKey && (e.key === 'p' || e.key === 'P')) {
      e.preventDefault();
      const btn = $('#btn-pause');
      if (btn && !btn.disabled) btn.click();
      return;
    }
    if (e.ctrlKey && e.shiftKey && (e.key === 'r' || e.key === 'R')) {
      e.preventDefault();
      openResetModal();
      return;
    }
  });

  document.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    document.body.classList.add('dragging-url');
  });
  document.addEventListener('dragleave', (e) => {
    if (e.target === document.documentElement || e.target === document.body) {
      document.body.classList.remove('dragging-url');
    }
  });
  document.addEventListener('drop', (e) => {
    e.preventDefault();
    document.body.classList.remove('dragging-url');
    const text = (e.dataTransfer.getData('text/uri-list') || e.dataTransfer.getData('text/plain') || '').trim();
    if (!text || !/^https?:\/\//i.test(text)) return;
    let detectedMode = null;
    if (/\/users\/[^/]+\/playlists\/\d+/.test(text) || /\/playlists?\//.test(text)) detectedMode = 'playlist';
    else if (/\/album\//.test(text)) detectedMode = 'album';
    else if (/\/track\//.test(text)) detectedMode = 'track';
    $('#url').value = text;
    if (detectedMode) setMode(detectedMode);
    saveSettings();
    appendLog(`[i] URL вставлен: ${text}`);
  });

  $$('.mode-btn').forEach(b => b.addEventListener('click', () => { setMode(b.dataset.mode); saveSettings(); }));

  const saveUrlBtn = $('#btn-save-url');
  if (saveUrlBtn) saveUrlBtn.addEventListener('click', () => {
    const on = saveUrlBtn.dataset.on === '1';
    saveUrlBtn.dataset.on = on ? '0' : '1';
    updateSaveUrlBtn(); saveSettings();
  });

  const cbLyr = $('#save-lyrics');
  if (cbLyr) cbLyr.addEventListener('change', saveSettings);

  const cbStruct = $('#folder-structure');
  if (cbStruct) cbStruct.addEventListener('change', saveSettings);

  const pasteBtn = $('#btn-paste');
  if (pasteBtn) pasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) { $('#url').value = text.trim(); saveSettings(); }
    } catch (e) { appendLog('[!] Не удалось вставить: ' + e.message); }
  });

  const browseBtn = $('#btn-browse');
  if (browseBtn) browseBtn.addEventListener('click', async () => {
    const folder = await API.pick_folder($('#path').value);
    if (folder) { $('#path').value = folder; saveSettings(); }
  });

  const loginBtn = $('#btn-login');
  if (loginBtn) loginBtn.addEventListener('click', async () => { await API.start_auth(); });

  const previewBtn = $('#btn-preview');
  if (previewBtn) previewBtn.addEventListener('click', async () => {
    await saveSettings();
    clearLog();
    setStatusDot(true);
    previewBtn.disabled = true;
    clearPreview();
    bumpPolling();
    const ok = await API.preview_tracks(gatherSettings());
    if (!ok) {
      previewBtn.disabled = false;
      setStatusDot(false);
      appendLog('[!] Не удалось запустить загрузку списка');
    }
  });

  const startBtn = $('#btn-start');
  if (startBtn) startBtn.addEventListener('click', async () => {
    await saveSettings();
    clearLog(); clearTracks(); setProgress(0, 0, '—');
    const cfg = { ...gatherSettings(), resume: false };
    const ok = await API.start_download(cfg);
    if (!ok) { appendLog('[!] Уже идёт другая операция'); return; }
    bumpPolling();
    startBtn.disabled = true;
    setDownloadingState(true);
    showPanel('runtime');
    hideResumeBanner();
  });

  const dlSelBtn = $('#btn-download-selected');
  if (dlSelBtn) dlSelBtn.addEventListener('click', async () => {
    const ids = Array.from(previewSelected);
    if (!ids.length) { appendLog('[!] Ничего не выбрано'); return; }
    await saveSettings();
    clearLog(); clearTracks(); setProgress(0, 0, '—');
    const cfg = { ...gatherSettings(), resume: false, selected_ids: ids };
    const ok = await API.start_download(cfg);
    if (!ok) { appendLog('[!] Уже идёт другая операция'); return; }
    bumpPolling();
    setDownloadingState(true);
    showPanel('runtime');
  });

  const backBtn = $('#btn-preview-back');
  if (backBtn) backBtn.addEventListener('click', async () => {
    await API.clear_preview();
    clearPreview();
    showPanel('settings');
  });

  const searchInput = $('#preview-search');
  if (searchInput) {
    let _searchTimer = null;
    searchInput.addEventListener('input', () => {
      if (_searchTimer) clearTimeout(_searchTimer);
      _searchTimer = setTimeout(() => renderPreviewList(), 180);
    });
  }

  const filterMode = $('#preview-filter-mode');
  if (filterMode) filterMode.addEventListener('change', () => renderPreviewList());

  const selAll = $('#btn-preview-all');
  if (selAll) selAll.addEventListener('click', () => {
    previewFiltered.forEach(t => previewSelected.add(t.id));
    renderPreviewList();
  });
  const selNone = $('#btn-preview-none');
  if (selNone) selNone.addEventListener('click', () => {
    previewFiltered.forEach(t => previewSelected.delete(t.id));
    renderPreviewList();
  });
  const selInv = $('#btn-preview-invert');
  if (selInv) selInv.addEventListener('click', () => {
    previewFiltered.forEach(t => {
      if (previewSelected.has(t.id)) previewSelected.delete(t.id);
      else previewSelected.add(t.id);
    });
    renderPreviewList();
  });

  const resumeBtn = $('#btn-resume');
  if (resumeBtn) resumeBtn.addEventListener('click', async () => {
    await saveSettings();
    clearLog(); clearTracks(); setProgress(0, 0, '—');
    const cfg = { ...gatherSettings(), resume: true };
    const ok = await API.start_download(cfg);
    if (!ok) { appendLog('[!] Уже идёт другая операция'); return; }
    bumpPolling();
    setDownloadingState(true);
    showPanel('runtime');
    hideResumeBanner();
  });

  const resumeDismiss = $('#btn-resume-dismiss');
  if (resumeDismiss) resumeDismiss.addEventListener('click', async () => {
    await API.clear_history();
    hideResumeBanner();
  });

  const pauseBtn = $('#btn-pause');
  if (pauseBtn) pauseBtn.addEventListener('click', async () => {
    if (isPaused) {
      await API.resume_download();
      isPaused = false;
      pauseBtn.textContent = '⏸ Пауза';
      appendLog('[i] Продолжаю...');
    } else {
      await API.pause_download();
      isPaused = true;
      pauseBtn.textContent = '▶ Продолжить';
      appendLog('[i] Пауза');
    }
  });

  const cancelBtn = $('#btn-cancel');
  if (cancelBtn) cancelBtn.addEventListener('click', async () => {
    await API.cancel_download();
    cancelBtn.disabled = true;
    appendLog('[i] Отмена запрошена...');
  });

  const openFolderBtn = $('#btn-open-folder');
  if (openFolderBtn) openFolderBtn.addEventListener('click', async () => {
    if (lastDownloadFolder) await API.open_folder(lastDownloadFolder);
  });

  const copyLogBtn = $('#btn-copy-log');
  if (copyLogBtn) copyLogBtn.addEventListener('click', async () => {
    const text = $('#log').innerText;
    try { await navigator.clipboard.writeText(text); appendLog('[i] Лог скопирован'); }
    catch (e) { appendLog('[!] Ошибка копирования: ' + e.message); }
  });

  // ── AUTH MODAL ──
  const authCopy = $('#auth-copy');
  if (authCopy) authCopy.addEventListener('click', () => {
    navigator.clipboard.writeText($('#auth-code').textContent).catch(() => {});
    $('#auth-status').textContent = t('auth_code_copied');
  });
  const authOpen = $('#auth-open');
  if (authOpen) authOpen.addEventListener('click', () => {
    const url = $('#auth-url').dataset.url;
    if (url) API.open_external(url);
    $('#auth-status').textContent = t('auth_waiting_confirm');
  });
  const authUrlLink = $('#auth-url');
  if (authUrlLink) authUrlLink.addEventListener('click', (e) => {
    e.preventDefault();
    const url = authUrlLink.dataset.url;
    if (url) API.open_external(url);
  });
  const authCancel = $('#auth-cancel');
  if (authCancel) authCancel.addEventListener('click', async () => {
    await API.cancel_auth(); hideAuthModal();
  });

  const updOpen = $('#btn-update-open');
  if (updOpen) updOpen.addEventListener('click', async () => {
    const url = $('#update-banner').dataset.url;
    if (url) await API.open_external(url);
  });
  const updClose = $('#btn-update-close');
  if (updClose) updClose.addEventListener('click', () => hideUpdateBanner());

  const statsRefresh = $('#stats-refresh');
  if (statsRefresh) statsRefresh.addEventListener('click', async () => {
    await refreshStats(); appendLog('[i] Статистика обновлена');
  });

  // RESET
  const resetBtn = $('#btn-reset');
  if (resetBtn) resetBtn.addEventListener('click', openResetModal);
  const resetCancel = $('#btn-reset-cancel');
  if (resetCancel) resetCancel.addEventListener('click', hideResetModal);
  const resetConfirm = $('#btn-reset-confirm');
  if (resetConfirm) resetConfirm.addEventListener('click', doReset);
  const resetBackdrop = $('#reset-modal');
  if (resetBackdrop) resetBackdrop.addEventListener('click', (e) => {
    if (e.target === resetBackdrop) hideResetModal();
  });

  // EXPORT / IMPORT
  const exportBtn = $('#btn-export');
  if (exportBtn) exportBtn.addEventListener('click', async () => {
    const res = await API.export_settings();
    if (res && res.ok) appendLog(`[OK] Настройки сохранены: ${res.path}`);
    else if (res && res.error !== 'cancelled') appendLog(`[!] Ошибка экспорта: ${res.error}`);
  });

  const importBtn = $('#btn-import');
  if (importBtn) importBtn.addEventListener('click', async () => {
    const res = await API.import_settings();
    if (res && res.ok) {
      appendLog('[OK] Настройки импортированы');
      settings = res.settings || {};
      loadSettings();
    } else if (res && res.error !== 'cancelled') {
      appendLog(`[!] Ошибка импорта: ${res.error}`);
    }
  });

  // TRAY
  const trayBtn = $('#btn-tray');
  if (trayBtn) trayBtn.addEventListener('click', async () => {
    await API.minimize_to_tray(true);
    appendLog('[i] Сворачиваю в трей');
    try {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.hide_window) {
        await window.pywebview.api.hide_window();
      } else {
        window.blur();
      }
    } catch (e) {}
  });

  // Валидация URL
  const urlInput = $('#url');
  if (urlInput) {
    const hint = document.createElement('div');
    hint.className = 'url-hint';
    hint.textContent = 'Поддерживаются ссылки music.yandex.ru (трек, альбом, плейлист)';
    urlInput.parentNode.insertBefore(hint, urlInput.nextSibling);

    const validateUrl = () => {
      const v = urlInput.value.trim();
      const mode = getMode();
      if (mode === 'likes' || !v) {
        urlInput.classList.remove('invalid');
        hint.classList.remove('visible');
        return true;
      }
      const ok = /^https?:\/\/music\.yandex\.[a-z]+\/(track|album|users)/i.test(v);
      if (!ok) {
        urlInput.classList.add('invalid');
        hint.classList.add('visible');
        return false;
      }
      urlInput.classList.remove('invalid');
      hint.classList.remove('visible');
      return true;
    };

    urlInput.addEventListener('input', validateUrl);
    urlInput.addEventListener('blur', validateUrl);
  }

  ['#token', '#url', '#path', '#delay', '#retries', '#retry_base', '#quality'].forEach(sel => {
    const el = $(sel);
    if (el) el.addEventListener('change', saveSettings);
  });
}

function setDownloadingState(active) {
  $('#btn-cancel').disabled = !active;
  $('#btn-pause').disabled = !active;
  $('#btn-open-folder').disabled = active;
  setStatusDot(active);
  if (active) bumpPolling();
}

// ═════ RESET ═════
function openResetModal() {
  ['reset-token','reset-stats','reset-logs','reset-history','reset-settings'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.checked = false;
  });
  const m = $('#reset-modal');
  if (m) m.classList.remove('hidden');
}
function hideResetModal() {
  const m = $('#reset-modal');
  if (m) m.classList.add('hidden');
}
async function doReset() {
  const kinds = [];
  if ($('#reset-token')?.checked)    kinds.push('token');
  if ($('#reset-stats')?.checked)    kinds.push('stats');
  if ($('#reset-logs')?.checked)     kinds.push('logs');
  if ($('#reset-history')?.checked)  kinds.push('history');
  if ($('#reset-settings')?.checked) kinds.push('settings');

  if (!kinds.length) { appendLog('[!] Ничего не выбрано'); return; }

  try {
    await API.reset_data(kinds);
    appendLog(`[OK] Сброшено: ${kinds.join(', ')}`);
  } catch (e) {
    appendLog(`[ERR] Ошибка сброса: ${e.message}`);
  }

  if (kinds.includes('token')) {
    const el = $('#token'); if (el) el.value = '';
  }
  if (kinds.includes('settings')) {
    settings = {};
    loadSettings();
    const el = $('#token'); if (el) el.value = '';
  }
  if (kinds.includes('stats')) {
    await refreshStats();
  }
  if (kinds.includes('history')) {
    hideResumeBanner();
  }

  hideResetModal();
}

// ═════ PREVIEW ═════
function clearPreview() {
  previewTracks = [];
  previewSelected = new Set();
  previewFiltered = [];
  const list = $('#preview-list');
  if (list) list.innerHTML = '<div class="preview-empty">Список пуст</div>';
  updateSelectionCounter();
}

function addPreviewBatch(items) {
  previewTracks.push(...items);
  items.forEach(it => previewSelected.add(it.id));
  renderPreviewList();
}

const PREVIEW_RENDER_LIMIT = 300;

function renderPreviewList() {
  const list = $('#preview-list');
  if (!list) return;

  const q = ($('#preview-search')?.value || '').trim().toLowerCase();
  const filterMode = $('#preview-filter-mode')?.value || 'all';

  previewFiltered = previewTracks.filter(t => {
    if (q) {
      const hay = (t.title + ' ' + t.artist + ' ' + t.album).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (filterMode === 'selected' && !previewSelected.has(t.id)) return false;
    if (filterMode === 'unselected' && previewSelected.has(t.id)) return false;
    return true;
  });

  previewFiltered.sort((a, b) => a.index - b.index);

  const visible = previewFiltered.slice(0, PREVIEW_RENDER_LIMIT);
  const truncated = previewFiltered.length > PREVIEW_RENDER_LIMIT;

  list.innerHTML = '';
  const frag = document.createDocumentFragment();

  for (const t of visible) {
    const item = document.createElement('div');
    item.className = 'preview-item';
    if (previewSelected.has(t.id)) item.classList.add('selected');

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'preview-check';
    cb.checked = previewSelected.has(t.id);
    cb.addEventListener('change', (e) => {
      e.stopPropagation();
      if (cb.checked) previewSelected.add(t.id);
      else previewSelected.delete(t.id);
      item.classList.toggle('selected', cb.checked);
      updateSelectionCounter();
    });

    const cover = document.createElement('div');
    cover.className = 'preview-cover';
    if (t.cover_url) {
      const img = document.createElement('img');
      img.src = t.cover_url;
      img.loading = 'lazy';
      img.onerror = () => { cover.innerHTML = '🎵'; };
      cover.appendChild(img);
    } else cover.textContent = '🎵';

    const info = document.createElement('div');
    info.className = 'preview-info';
    const nm = document.createElement('div');
    nm.className = 'preview-name';
    nm.textContent = t.title;
    nm.title = t.title;
    const sub = document.createElement('div');
    sub.className = 'preview-sub';
    sub.textContent = t.artist + (t.album ? ' — ' + t.album : '');
    sub.title = sub.textContent;
    info.append(nm, sub);

    const idx = document.createElement('div');
    idx.className = 'preview-idx';
    idx.textContent = `[${t.index}/${t.total}]`;

    item.append(cb, cover, info, idx);
    item.addEventListener('click', (e) => {
      if (e.target === cb) return;
      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event('change'));
    });
    frag.appendChild(item);
  }

  list.appendChild(frag);

  if (truncated) {
    const more = document.createElement('div');
    more.className = 'preview-empty';
    more.textContent = `… и ещё ${previewFiltered.length - PREVIEW_RENDER_LIMIT}. Уточните поиск.`;
    list.appendChild(more);
  }

  updateSelectionCounter();
}

function updateSelectionCounter() {
  const cnt = $('#preview-count');
  const btn = $('#btn-download-selected');
  const total = previewTracks.length;
  const sel = previewSelected.size;
  if (cnt) cnt.textContent = `${sel} / ${total}`;
  if (btn) {
    btn.disabled = sel === 0;
    btn.textContent = `🎵 Скачать выбранные (${sel})`;
  }
}

// ═════ LOG (batched) ═════
const _logQueue = [];
let _logRafPending = false;
const LOG_MAX_LINES = 800;

function appendLog(text) {
  _logQueue.push(text);
  if (!_logRafPending) {
    _logRafPending = true;
    requestAnimationFrame(_flushLogQueue);
  }
}

function _flushLogQueue() {
  _logRafPending = false;
  const log = $('#log');
  if (!log) { _logQueue.length = 0; return; }

  const frag = document.createDocumentFragment();
  for (const text of _logQueue) {
    const line = document.createElement('div');
    line.className = 'line';
    if (text.startsWith('[OK]')) line.classList.add('ok');
    else if (text.includes('[ERR]') || text.includes('[!]')) line.classList.add('err');
    else if (text.includes('429')) line.classList.add('warn');
    else if (text.startsWith('[i]')) line.classList.add('head');

    const urlRe = /(https?:\/\/[^\s]+)/g;
    if (urlRe.test(text)) {
      const parts = text.split(urlRe);
      parts.forEach(part => {
        if (/^https?:\/\//.test(part)) {
          const a = document.createElement('a');
          a.href = '#';
          a.textContent = part;
          a.title = 'Открыть в браузере';
          a.addEventListener('click', (e) => {
            e.preventDefault();
            try { API.open_external(part); } catch (err) {}
          });
          line.appendChild(a);
        } else if (part) {
          line.appendChild(document.createTextNode(part));
        }
      });
    } else {
      line.textContent = text;
    }
    frag.appendChild(line);
  }
  _logQueue.length = 0;

  log.appendChild(frag);

  const extra = log.childElementCount - LOG_MAX_LINES;
  if (extra > 0) {
    for (let i = 0; i < extra; i++) log.removeChild(log.firstChild);
  }

  const atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
  if (atBottom) log.scrollTop = log.scrollHeight;
}

function clearLog() {
  _logQueue.length = 0;
  const log = $('#log');
  if (log) log.innerHTML = '';
}

// ═════ TRACKS ═════
function clearTracks() {
  const t = $('#tracks');
  if (t) t.innerHTML = '<div class="empty emoji">🎵</div>';
  trackItems = {};
}
function addTrack(data) {
  const container = $('#tracks');
  if (!container) return;
  const empty = container.querySelector('.empty');
  if (empty) empty.remove();

  const item = document.createElement('div');
  item.className = 'track-item';
  const cover = document.createElement('div');
  cover.className = 'track-cover';
  if (data.cover_url) {
    const img = document.createElement('img');
    img.src = data.cover_url;
    img.loading = 'lazy';
    img.onerror = () => { cover.innerHTML = '<span class="emoji">🎵</span>'; };
    cover.appendChild(img);
  } else cover.innerHTML = '<span class="emoji">🎵</span>';

  const info = document.createElement('div');
  info.className = 'track-info';
  const idx = document.createElement('div');
  idx.className = 'track-idx'; idx.textContent = `[${data.index}/${data.total}]`;
  const name = document.createElement('div');
  name.className = 'track-name'; name.textContent = data.name; name.title = data.name;
  const status = document.createElement('div');
  status.className = 'track-status';
  status.innerHTML = '<span class="emoji">⬇</span> В очереди...';
  const bar = document.createElement('div');
  bar.className = 'track-bar';
  const barFill = document.createElement('div');
  barFill.className = 'track-bar-fill';
  bar.appendChild(barFill);

  info.append(idx, name, status, bar);
  item.append(cover, info);
  container.appendChild(item);
  trackItems[data.index] = { el: item, statusEl: status, barEl: barFill };
  container.scrollTop = container.scrollHeight;
}
function updateTrack(index, kind, text) {
  const rec = trackItems[index];
  if (!rec) return;
  rec.el.classList.remove('ok', 'fail', 'skip');
  if (kind) rec.el.classList.add(kind);
  rec.statusEl.textContent = text;
}
function updateTrackProgress(index, pct) {
  const rec = trackItems[index];
  if (!rec || !rec.barEl) return;
  rec.barEl.style.width = Math.max(0, Math.min(100, pct)) + '%';
}

// ═════ PROGRESS / STATUS ═════
let _lastProgressText = '';
function setProgress(cur, total, eta) {
  const bar = $('#progress-bar'), txt = $('#progress-text');
  if (!bar || !txt) return;
  if (!total || total <= 0) {
    bar.style.width = '0%'; bar.className = 'progress-bar'; txt.textContent = '— / —';
    _lastProgressText = '';
    return;
  }
  const pct = Math.min(100, Math.round(cur / total * 100));
  bar.style.width = pct + '%';
  bar.className = 'progress-bar';
  if (pct >= 100) bar.classList.add('done');
  else if (pct >= 85) bar.classList.add('warn');

  let text = `${pct}%   ${cur} / ${total}`;
  if (eta && eta !== '—') text += `   ⏱ ${eta}`;

  if (text !== _lastProgressText) {
    _lastProgressText = text;
    txt.textContent = text;
  }
}
function setStatus(text) { const el = $('#status-text'); if (el) el.textContent = text; }
function setStatusDot(busy) { const el = $('#status-dot'); if (el) el.classList.toggle('busy', !!busy); }

// ═════ AUTH MODAL ═════
function showAuthModal(code, url) {
  $('#auth-code').textContent = code;
  $('#auth-url').textContent = url;
  $('#auth-url').dataset.url = url;
  $('#auth-status').textContent = t('auth_waiting');
  $('#auth-modal').classList.remove('hidden');
}
function hideAuthModal() { $('#auth-modal').classList.add('hidden'); }

// ═════ EVENT HANDLER ═════
async function handleEvent(ev) {
  switch (ev.type) {
    case 'log': appendLog(ev.text); break;
    case 'status': setStatus(ev.text); break;
    case 'total': setProgress(0, ev.total, '—'); break;
    case 'progress': setProgress(ev.cur, ev.total, ev.eta); break;
    case 'track_start': addTrack(ev); break;
    case 'track_status': updateTrack(ev.index, ev.status, ev.text); break;
    case 'track_progress': updateTrackProgress(ev.index, ev.pct); break;

    case 'startup_step': {
      const icons = { ok: '✓', warn: '⚠', fail: '✗', info: 'ℹ' };
      const icon = icons[ev.status] || '•';
      const cls = ev.status === 'fail' ? '[ERR]'
                : ev.status === 'warn' ? '[!]'
                : ev.status === 'ok'   ? '[OK]'
                : '[i]';
      appendLog(`${cls} ${icon} ${ev.text}${ev.detail ? '  — ' + ev.detail : ''}`);
      break;
    }

    case 'startup_done': {
      showStartupToast(ev);
      if (ev.resume_ready && ev.history && ev.history.pending > 0) {
        showResumeBanner(ev.history);
      }
      break;
    }

    case 'preview_start':
      showPanel('preview');
      setStatus('Загрузка списка...');
      bumpPolling();
      break;
    case 'preview_batch':
      addPreviewBatch(ev.items || []);
      setStatus(`Загрузка списка: ${previewTracks.length}`);
      break;
    case 'preview_done':
      setStatusDot(false);
      $('#btn-preview').disabled = false;
      if (!ev.ok) {
        showPanel('settings');
        appendLog('[ERR] Не удалось загрузить список');
      } else {
        appendLog(`[OK] Загружено треков: ${ev.total}`);
        updateSelectionCounter();
      }
      break;

    case 'done':
      setDownloadingState(false);
      $('#btn-start').disabled = false;
      isPaused = false;
      const pb = $('#btn-pause');
      if (pb) pb.textContent = '⏸ Пауза';
      setStatus(t('status_done').replace('{ok}', ev.ok).replace('{fail}', ev.failed));
      if (ev.path) {
        lastDownloadFolder = ev.path;
        $('#btn-open-folder').disabled = false;
      }
      refreshStats();
      showPanel('settings');
      API.get_history().then(hist => {
        if (hist && hist.pending > 0) showResumeBanner(hist);
        else hideResumeBanner();
      }).catch(() => {});
      break;

    case 'auth_code':
      showAuthModal(ev.user_code, ev.url);
      appendLog(`[i] Код: ${ev.user_code}`);
      appendLog(`[i] Страница: ${ev.url}`);
      try {
        await navigator.clipboard.writeText(ev.user_code);
        $('#auth-status').textContent = '✓ Код скопирован в буфер обмена';
        appendLog('[i] Код автоматически скопирован');
      } catch (e) {}
      break;

    case 'auth_token':
      $('#token').value = ev.token;
      saveSettings();
      appendLog('[OK] Токен получен и сохранён');
      hideAuthModal();
      break;

    case 'auth_error':
      appendLog(`[ERR] ${ev.message}`);
      $('#auth-status').textContent = ev.message;
      setTimeout(hideAuthModal, 2000);
      break;
  }
}

// ═════ START ═════
init();
