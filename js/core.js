/* ============================================================
   BELUGACORD 2.5 — CORE.JS
   Ядро: состояние, WS, авторизация, утилиты, загрузчик модулей
   ============================================================ */

var BC = window.BC = {
  version: '2.5',
  token: localStorage.getItem('belugacord_token') || '',
  me: null,
  ws: null,
  wsReconnectDelay: 1000,
  offlineQueue: [],
  onlineSet: {},
  userStatuses: {},
  flags: {},
  cache: {}
};

var token = BC.token;
var me = null;
var ws = null;

var MODULES = [
  'releases',
  'chat',
  'social',
  'gifts',
  'economy',
  'admin',
  'calls',
  'games'
];

/* ============================================================
   УТИЛИТЫ
   ============================================================ */
function esc(s){
  return String(s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}
function linkify(t){
  var e = esc(t || '');
  return e.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
}
function markMentions(t){
  if(!t) return t;
  return t.replace(/@([A-Za-z0-9_]{2,32})/g, '<span class="mention">@$1</span>');
}
function formatText(t){
  if(!t) return '';
  var e = esc(t);
  e = e.replace(/\|\|(.+?)\|\|/g, '<span class="spoiler" onclick="this.classList.toggle(\'revealed\')">$1</span>');
  e = e.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  e = e.replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, '<i>$1</i>');
  e = e.replace(/~~(.+?)~~/g, '<s>$1</s>');
  e = e.replace(/`([^`]+?)`/g, '<code>$1</code>');
  e = e.replace(/(^|\n)&gt; (.+?)(?=\n|$)/g, '$1<blockquote>$2</blockquote>');
  return e;
}
function parsePos(s){
  if(!s) return {x:50, y:50};
  var p = String(s).split(' ');
  return {x: parseFloat(p[0]) || 50, y: parseFloat(p[1]) || 50};
}
function timeAgo(iso){
  if(!iso) return 'давно';
  var d = new Date(iso);
  var s = Math.floor((Date.now() - d.getTime()) / 1000);
  if(s < 60) return 'только что';
  if(s < 3600) return Math.floor(s / 60) + ' мин назад';
  if(s < 10800) return Math.floor(s / 3600) + ' ч назад';
  var hh = String(d.getHours()).padStart(2, '0');
  var mm = String(d.getMinutes()).padStart(2, '0');
  var today = new Date();
  if(d.toDateString() === today.toDateString()) return 'сегодня в ' + hh + ':' + mm;
  return d.toLocaleDateString('ru-RU', {day:'2-digit', month:'2-digit'}) + ' ' + hh + ':' + mm;
}
function showNotice(text, type){
  document.querySelectorAll('.shop-notice').forEach(function(n){ n.remove(); });
  var n = document.createElement('div');
  n.className = 'shop-notice' + (type === 'error' ? ' error' : (type === 'warn' ? ' warn' : (type === 'info' ? ' info' : '')));
  n.textContent = text;
  document.body.appendChild(n);
  setTimeout(function(){ n.classList.add('show'); }, 50);
  setTimeout(function(){
    n.classList.remove('show');
    setTimeout(function(){ n.remove(); }, 500);
  }, 3500);
}
function playBeep(f, d, v){
  try {
    var c = new (window.AudioContext || window.webkitAudioContext)();
    var o = c.createOscillator();
    var g = c.createGain();
    o.frequency.value = f;
    o.connect(g);
    g.connect(c.destination);
    g.gain.setValueAtTime(v, c.currentTime);
    g.gain.exponentialRampToValueAtTime(0.01, c.currentTime + d);
    o.start();
    o.stop(c.currentTime + d);
  } catch(e) {}
}
function playMsgSound(){ playBeep(880, 0.08, 0.15); }
function catSound(){ playBeep(1200, 0.1, 0.2); setTimeout(function(){ playBeep(800, 0.1, 0.15); }, 100); }
function giftSound(){
  playBeep(523, 0.15, 0.4);
  setTimeout(function(){ playBeep(659, 0.15, 0.4); }, 150);
  setTimeout(function(){ playBeep(784, 0.3, 0.5); }, 300);
}
function callRingSound(){ playBeep(900, 0.4, 0.2); setTimeout(function(){ playBeep(1100, 0.4, 0.2); }, 500); }
function callEndSound(){ playBeep(600, 0.2, 0.2); setTimeout(function(){ playBeep(400, 0.4, 0.2); }, 250); }

function updateClock(){
  var n = new Date();
  var t = n.toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'});
  var d = n.toLocaleDateString('ru-RU', {day:'numeric', month:'long'});
  var sd = n.toLocaleDateString('ru-RU', {day:'2-digit', month:'2-digit'});
  var e;
  e = document.getElementById('loginTime'); if(e) e.textContent = t;
  e = document.getElementById('taskbarTime'); if(e) e.textContent = t;
  e = document.getElementById('loginDate'); if(e) e.textContent = d;
  e = document.getElementById('taskbarDate'); if(e) e.textContent = sd;
}
setInterval(updateClock, 1000);
updateClock();

/* ============================================================
   ЗАГРУЗЧИК МОДУЛЕЙ
   ============================================================ */
async function loadModule(name){
  try {
    var htmlRes = await fetch('/futures/' + name + '/' + name + '.html');
    if(htmlRes.ok) {
      var html = await htmlRes.text();
      var container = document.getElementById('features-modals');
      if(container) container.insertAdjacentHTML('beforeend', html);
    }
    await new Promise(function(resolve){
      var s = document.createElement('script');
      s.src = '/futures/' + name + '/' + name + '.js';
      s.onload = resolve;
      s.onerror = function(){ console.warn('[BC] module not loaded:', name); resolve(); };
      document.body.appendChild(s);
    });
    console.log('[BC] module loaded:', name);
  } catch(e) {
    console.error('[BC] module error:', name, e);
  }
}

async function loadAllModules(){
  for(var i = 0; i < MODULES.length; i++){
    await loadModule(MODULES[i]);
  }
  console.log('[BC] all modules loaded');
  document.dispatchEvent(new Event('modules-loaded'));
}

/* ============================================================
   API
   ============================================================ */
async function api(path, options){
  options = options || {};
  options.headers = options.headers || {};
  var url = '/api' + path;
  if(options.body && typeof options.body === 'object'){
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  try {
    var r = await fetch(url, options);
    var data = await r.json().catch(function(){ return {}; });
    if(!r.ok) return {ok: false, error: data.detail || 'Ошибка', status: r.status};
    return {ok: true, data: data};
  } catch(e) {
    return {ok: false, error: 'Сеть', status: 0};
  }
}

/* ============================================================
   WEBSOCKET
   ============================================================ */
function connectWS(){
  var proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
  ws = BC.ws = new WebSocket(proto + location.host + '/ws?token=' + encodeURIComponent(BC.token));
  ws.onopen = function(){
    BC.wsReconnectDelay = 1000;
    var c = document.getElementById('connStatus');
    if(c) c.classList.remove('show');
    while(BC.offlineQueue.length){
      try { ws.send(BC.offlineQueue.shift()); } catch(e){ break; }
    }
  };
  ws.onmessage = function(event){
    var data;
    try { data = JSON.parse(event.data); } catch(e){ return; }
    handleWsMessage(data);
  };
  ws.onclose = function(){
    var c = document.getElementById('connStatus');
    if(c) c.classList.add('show');
    setTimeout(function(){
      BC.wsReconnectDelay = Math.min(BC.wsReconnectDelay * 1.5, 10000);
      connectWS();
    }, BC.wsReconnectDelay);
  };
  ws.onerror = function(){ try { ws.close(); } catch(e){} };
}
function wsSend(payload){
  var j = JSON.stringify(payload);
  if(ws && ws.readyState === WebSocket.OPEN){
    ws.send(j);
  } else {
    BC.offlineQueue.push(j);
    var c = document.getElementById('connStatus');
    if(c) c.classList.add('show');
  }
}
var wsSendSafe = wsSend;
function handleWsMessage(data){
  document.dispatchEvent(new CustomEvent('ws:' + data.type, {detail: data}));
  document.dispatchEvent(new CustomEvent('ws:any', {detail: data}));
}

/* ============================================================
   АВТОРИЗАЦИЯ
   ============================================================ */
var authMode = 'login';
function switchTab(mode){
  authMode = mode;
  document.getElementById('tabLogin').classList.toggle('active', mode === 'login');
  document.getElementById('tabRegister').classList.toggle('active', mode === 'register');
  document.getElementById('authError').textContent = '';
  document.getElementById('authEmail').style.display = mode === 'register' ? 'block' : 'none';
  document.getElementById('authBtn').textContent = mode === 'login' ? 'Войти →' : 'Создать →';
}
var checkTimer = null;
function checkUsername(){
  var val = document.getElementById('authUsername').value.trim();
  var s = document.getElementById('usernameStatus');
  if(authMode !== 'register' || val.length < 2){ s.textContent = ''; return; }
  clearTimeout(checkTimer);
  checkTimer = setTimeout(function(){
    fetch('/api/check_username?username=' + encodeURIComponent(val))
      .then(function(r){ return r.json(); })
      .then(function(d){
        s.textContent = d.available ? '✓ Свободен' : '✕ Занят';
        s.className = 'win-login-status ' + (d.available ? 'ok' : 'bad');
      })
      .catch(function(){});
  }, 400);
}
async function submitAuth(){
  var u = document.getElementById('authUsername').value.trim();
  var p = document.getElementById('authPassword').value;
  var em = document.getElementById('authEmail').value.trim();
  var err = document.getElementById('authError');
  err.textContent = '';
  if(!u || !p){ err.textContent = 'Заполни поля'; return; }
  var urlParams = new URLSearchParams(location.search);
  var promo = urlParams.get('promo') || localStorage.getItem('bc_referrer') || '';
  var url = authMode === 'login' ? '/api/login' : '/api/register';
  var body = {username: u, password: p, email: em};
  if(authMode === 'register' && promo) body.referrer = promo;
  try {
    var r = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    var d = await r.json();
    if(!r.ok){ err.textContent = d.detail || 'Ошибка'; return; }
    BC.token = d.token;
    token = d.token;
    localStorage.setItem('belugacord_token', d.token);
    BC.me = d.user;
    me = d.user;
    localStorage.removeItem('bc_referrer');
    enterApp();
  } catch(e) {
    err.textContent = 'Ошибка соединения';
  }
}
function logout(){
  localStorage.removeItem('belugacord_token');
  BC.token = '';
  BC.me = null;
  token = '';
  me = null;
  if(ws){ try { ws.close(); } catch(e){} }
  document.getElementById('app').style.display = 'none';
  document.getElementById('authScreen').style.display = 'flex';
}

/* ============================================================
   BOOT
   ============================================================ */
async function boot(){
  var savedTheme = localStorage.getItem('belugacord_theme');
  if(savedTheme && savedTheme.indexOf('custom:') === 0){
    try {
      var t = JSON.parse(localStorage.getItem('belugacord_custom_theme') || 'null');
      if(t) applyCustomTheme(t);
    } catch(e){}
  } else if(savedTheme && savedTheme !== 'beluga'){
    document.body.classList.add('theme-' + savedTheme);
  }
  var urlParams = new URLSearchParams(location.search);
  var promo = urlParams.get('promo');
  if(promo) localStorage.setItem('bc_referrer', promo);
  await loadAllModules();
  if(BC.token){
    try {
      var r = await fetch('/api/me?token=' + encodeURIComponent(BC.token));
      if(r.ok){
        BC.me = await r.json();
        me = BC.me;
        enterApp();
        return;
      }
    } catch(e){}
    BC.token = '';
    token = '';
    localStorage.removeItem('belugacord_token');
  }
  document.getElementById('loadingScreen').style.display = 'none';
  document.getElementById('authScreen').style.display = 'flex';
}
async function enterApp(){
  document.getElementById('loadingScreen').style.display = 'none';
  document.getElementById('authScreen').style.display = 'none';
  document.getElementById('app').style.display = 'block';
  var _uname = (me.username || '').toLowerCase();
  var _role = (me.role || '').toLowerCase();
  BC.isOwner = _role === 'owner' || _uname === '_fan_beluga_';
  BC.isMod = me.is_moderator === true || me.is_admin === true || BC.isOwner;
  BC.isPremium = !!me.is_premium;
  applyUserPrefs(me);
  applyLang(localStorage.getItem('belugacord_lang') || 'ru');
  connectWS();
  document.dispatchEvent(new Event('user-entered'));
  setupHotkeys();
  setupDragDrop();
  if('Notification' in window && Notification.permission === 'default'){
    var nb = document.getElementById('notifPermBanner');
    if(nb) nb.classList.add('show');
  }
  if('serviceWorker' in navigator){
    try { navigator.serviceWorker.register('/sw.js').catch(function(){}); } catch(e){}
  }
  setTimeout(function(){
    document.dispatchEvent(new Event('show-changelog'));
  }, 800);
}
function applyUserPrefs(u){
  if(u && u.compact_mode) document.body.classList.add('compact');
  else document.body.classList.remove('compact');
  if(u && u.font_choice) document.body.classList.add('font-' + u.font_choice);
  else document.body.classList.remove('font-mono', 'font-serif', 'font-comic');
  if(u && u.wallpaper){
    document.documentElement.style.setProperty('--custom-bg', 'url(' + u.wallpaper + ')');
    document.body.classList.add('custom-bg');
  } else {
    document.body.classList.remove('custom-bg');
  }
}
function applyLang(code){
  BC.lang = code;
  localStorage.setItem('belugacord_lang', code);
  document.documentElement.lang = code;
}

/* ============================================================
   ТЕМЫ
   ============================================================ */
function setTheme(t){
  localStorage.removeItem('belugacord_custom_theme');
  document.body.classList.remove('custom-bg');
  ['discord','white','cyber','retro','cs2','cs16','minecraft','neon','nature','sunset','ocean','royal','rainbow'].forEach(function(n){
    document.body.classList.remove('theme-' + n);
  });
  if(t !== 'beluga') document.body.classList.add('theme-' + t);
  localStorage.setItem('belugacord_theme', t);
}
function applyCustomTheme(t){
  ['discord','white','cyber','retro','cs2','cs16','minecraft','neon','nature','sunset','ocean','royal','rainbow'].forEach(function(n){
    document.body.classList.remove('theme-' + n);
  });
  var vars = t.vars || {};
  Object.keys(vars).forEach(function(k){
    document.documentElement.style.setProperty(k, vars[k]);
  });
  if(t.border_radius) document.documentElement.style.setProperty('--radius', t.border_radius);
  if(t.bg_image){
    document.documentElement.style.setProperty('--custom-bg', 'url(' + t.bg_image + ')');
    document.body.classList.add('custom-bg');
  } else {
    document.body.classList.remove('custom-bg');
  }
  localStorage.setItem('belugacord_theme', 'custom:' + (t.name || 'custom'));
  localStorage.setItem('belugacord_custom_theme', JSON.stringify(t));
}

/* ============================================================
   ХОТКЕИ
   ============================================================ */
function setupHotkeys(){
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape'){
      document.querySelectorAll('.modal-overlay.open').forEach(function(m){
        if(m.id !== 'emailVerifyModal' && m.id !== 'storiesModal' && m.id !== 'releaseModal'){
          m.classList.remove('open');
        }
      });
      document.querySelectorAll('.quick-reactions.show').forEach(function(q){ q.remove(); });
      document.querySelectorAll('.sticker-picker').forEach(function(q){ q.remove(); });
    }
    if(e.ctrlKey && e.key === 'k'){ e.preventDefault(); document.dispatchEvent(new Event('open-user-search')); }
    if(e.ctrlKey && e.key === 'f'){ e.preventDefault(); document.dispatchEvent(new Event('open-msg-search')); }
  });
}
function mobileShow(view, ev){
  if(ev){
    var p = ev.target.parentNode;
    if(p) p.querySelectorAll('.mobile-tab').forEach(function(t){ t.classList.remove('active'); });
    ev.target.classList.add('active');
  }
  var d = document.getElementById('desktopCol');
  var c = document.getElementById('chatListCol');
  var ch = document.getElementById('chatWindowCol');
  d.classList.remove('mobile-active');
  c.classList.remove('mobile-active');
  ch.classList.remove('mobile-active');
  if(view === 'desktop') d.classList.add('mobile-active');
  else if(view === 'chats') c.classList.add('mobile-active');
  else ch.classList.add('mobile-active');
}
function toggleStartMenu(){
  document.getElementById('startMenu').classList.toggle('open');
}
document.addEventListener('click', function(e){
  var sm = document.getElementById('startMenu');
  if(!sm) return;
  var tb = e.target.closest('.tb-start');
  if(!tb && !sm.contains(e.target) && sm.classList.contains('open')){
    sm.classList.remove('open');
  }
});
async function requestNotifPerm(){
  try {
    var p = await Notification.requestPermission();
    if(p === 'granted') showNotice('🔔 Включено');
    var nb = document.getElementById('notifPermBanner');
    if(nb) nb.classList.remove('show');
  } catch(e){}
}
function setupDragDrop(){
  var el = document.getElementById('app');
  if(!el) return;
  el.addEventListener('dragover', function(e){
    e.preventDefault();
    var d = document.getElementById('dropOverlay');
    if(d) d.classList.add('show');
  });
  el.addEventListener('dragleave', function(e){
    if(!el.contains(e.relatedTarget)){
      var d = document.getElementById('dropOverlay');
      if(d) d.classList.remove('show');
    }
  });
  el.addEventListener('drop', function(e){
    e.preventDefault();
    var d = document.getElementById('dropOverlay');
    if(d) d.classList.remove('show');
    var f = e.dataTransfer.files[0];
    if(f) document.dispatchEvent(new CustomEvent('drop-file', {detail: f}));
  });
}

/* ============================================================
   КОНФЕТТИ / ШАРИКИ
   ============================================================ */
function showConfetti(){
  for(var i = 0; i < 50; i++){
    setTimeout(function(){
      var c = document.createElement('div');
      c.className = 'confetti-piece';
      c.textContent = ['🎉','🎊','✨','⭐','🎁'][Math.floor(Math.random() * 5)];
      c.style.left = Math.random() * 100 + '%';
      c.style.animationDuration = (2 + Math.random() * 2) + 's';
      document.body.appendChild(c);
      setTimeout(function(){ c.remove(); }, 4000);
    }, i * 50);
  }
}
function showBalloons(){
  for(var i = 0; i < 15; i++){
    setTimeout(function(){
      var b = document.createElement('div');
      b.className = 'balloon';
      b.textContent = '🎈';
      b.style.left = Math.random() * 100 + '%';
      b.style.animationDuration = (3 + Math.random() * 3) + 's';
      document.body.appendChild(b);
      setTimeout(function(){ b.remove(); }, 6000);
    }, i * 200);
  }
}

/* ============================================================
   EXPORT
   ============================================================ */
BC.api = api;
BC.showNotice = showNotice;
BC.wsSend = wsSend;
BC.esc = esc;
BC.linkify = linkify;
BC.markMentions = markMentions;
BC.formatText = formatText;
BC.timeAgo = timeAgo;
BC.parsePos = parsePos;
BC.playBeep = playBeep;
BC.playMsgSound = playMsgSound;
BC.catSound = catSound;
BC.giftSound = giftSound;
BC.callRingSound = callRingSound;
BC.callEndSound = callEndSound;
BC.showConfetti = showConfetti;
BC.showBalloons = showBalloons;

window.switchTab = switchTab;
window.submitAuth = submitAuth;
window.logout = logout;
window.checkUsername = checkUsername;
window.mobileShow = mobileShow;
window.toggleStartMenu = toggleStartMenu;
window.requestNotifPerm = requestNotifPerm;
window.setTheme = setTheme;
window.applyCustomTheme = applyCustomTheme;
window.applyLang = applyLang;
window.showNotice = showNotice;
window.esc = esc;

if(document.readyState !== 'loading'){
  boot();
} else {
  document.addEventListener('DOMContentLoaded', boot);
}

console.log('[BC] core.js loaded, version 2.5');