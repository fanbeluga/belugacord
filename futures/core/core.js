/* ============================================================
   BELUGACORD 2.5 — MODULE: CORE (part 1/2)
   Профиль, аватар, баннер, статус, стиль ника, email, changelog
   ============================================================ */

/* ============================================================
   СОСТОЯНИЕ МОДУЛЯ
   ============================================================ */
var avatarData = null, bannerData = null;
var pendingAvatar = null, pendingBanner = null;
var gifAvatarData = null, gifBannerData = null;
var avatarPos = {x:50, y:50}, bannerPos = {x:50, y:50};
var nicknameColor = null, nicknameGradient = null;
var tempNickColor = null, tempNickGradient = null;
var emailState = {step:'input', email:'', code:'', cooldown:0, timerId:null};

var NICK_COLORS = ['#ffd700','#d946ef','#22d3ee','#ec4899','#00ffaa','#ff8c00','#f43f5e','#ffffff'];
var NICK_GRADIENTS = [
  'linear-gradient(135deg,#d946ef,#8b5cf6)',
  'linear-gradient(135deg,#22d3ee,#06b6d4)',
  'linear-gradient(135deg,#f43f5e,#ec4899)',
  'linear-gradient(135deg,#ffd700,#ff8c00)',
  'linear-gradient(135deg,#22c55e,#16a34a)',
  'linear-gradient(135deg,#8b5cf6,#22d3ee)'
];

var LANGS = [
  {code:'ru', flag:'🇷🇺', name:'Русский'},
  {code:'be', flag:'🇧🇾', name:'Белорусский'},
  {code:'uk', flag:'🇺🇦', name:'Українська'},
  {code:'en', flag:'🇬🇧', name:'English'},
  {code:'zh', flag:'🇨🇳', name:'中文'},
  {code:'ja', flag:'🇯🇵', name:'日本語'},
  {code:'ko', flag:'🇰🇷', name:'한국어'},
  {code:'de', flag:'🇩🇪', name:'Deutsch'},
  {code:'es', flag:'🇪🇸', name:'Español'},
  {code:'fr', flag:'🇫🇷', name:'Français'}
];

var CHAT_SKINS = [
  {id:'default', name:'По умолчанию', bg:''},
  {id:'nebula', name:'🌌 Небула', bg:'linear-gradient(135deg,rgba(139,92,246,0.15),rgba(34,211,238,0.1))'},
  {id:'sunset', name:'🌅 Закат', bg:'linear-gradient(135deg,rgba(244,63,94,0.15),rgba(255,140,0,0.1))'},
  {id:'forest', name:'🌿 Лес', bg:'linear-gradient(135deg,rgba(34,197,94,0.15),rgba(34,211,238,0.1))'},
  {id:'royal', name:'👑 Роял', bg:'linear-gradient(135deg,rgba(255,215,0,0.15),rgba(139,92,246,0.1))'},
  {id:'cyber', name:'🤖 Кибер', bg:'linear-gradient(135deg,rgba(255,238,0,0.15),rgba(0,255,255,0.1))'}
];

var MSG_EFFECTS = [
  {id:'none', name:'Без эффекта'},
  {id:'glow', name:'✨ Свечение'},
  {id:'rainbow', name:'🌈 Радуга'},
  {id:'shake', name:'💥 Тряска'},
  {id:'pulse', name:'💓 Пульс'}
];

var ACHIEVEMENTS_CACHE = {};
var FRAMES_CACHE = [];
var currentMsgEffect = localStorage.getItem('belugacord_msg_effect') || 'none';
var currentChatSkin = localStorage.getItem('belugacord_chat_skin') || 'default';

/* ============================================================
   ПРОФИЛЬ
   ============================================================ */
function applyFrame(el, frameId){
  if(!el) return;
  el.removeAttribute('data-frame');
  if(!frameId || frameId === 'none') return;
  el.setAttribute('data-frame', frameId);
}

function renderProfile(){
  if(!me) return;

  var pn = document.getElementById('profileName');
  if(pn){
    pn.textContent = me.username;
    if(me.nickname_gradient){
      pn.style.background = me.nickname_gradient;
      pn.style.webkitBackgroundClip = 'text';
      pn.style.webkitTextFillColor = 'transparent';
      pn.style.color = '';
    } else if(me.nickname_color){
      pn.style.color = me.nickname_color;
      pn.style.background = '';
    } else {
      pn.style.color = '';
      pn.style.background = '';
    }
  }

  var ps = document.getElementById('profileStats');
  if(ps) ps.textContent = '📨 ' + (me.messages_count || 0) + ' · 📅 ' + (me.created_at ? new Date(me.created_at).toLocaleDateString('ru-RU') : '—');

  var pr = document.getElementById('profileRating');
  if(pr) pr.textContent = '⭐ Соц.рейтинг: ' + (me.social_rating || 0);

  var pprem = document.getElementById('profilePremium');
  if(pprem){
    if(me.is_premium){
      pprem.innerHTML = '<span class="premium-badge">💎 PREMIUM</span> <span style="font-size:11px;color:var(--text-mute)">до ' + new Date(me.premium_expires).toLocaleDateString('ru-RU') + '</span>';
    } else {
      pprem.innerHTML = '<button class="save-btn gold" style="margin:0;padding:8px 14px;font-size:12px;width:auto" onclick="closeProfile();openPremium()">💎 Купить премиум</button>';
    }
  }

  var bio = document.getElementById('bioInput');
  if(bio) bio.value = me.bio || '';
  var mi = document.getElementById('musicInput');
  if(mi) mi.value = me.fav_music || '';

  avatarData = me.avatar;
  bannerData = me.banner;
  gifAvatarData = me.gif_avatar;
  gifBannerData = me.gif_banner;
  avatarPos = parsePos(me.avatar_pos);
  bannerPos = parsePos(me.banner_pos);

  // Email баннер — показываем если email НЕ подтверждён
  var eb = document.getElementById('emailBanner');
  if(eb){
    if(!me.email || !me.email_verified){
      eb.style.display = 'flex';
    } else {
      eb.style.display = 'none';
    }
  }

  var bigAv = document.getElementById('avatarPreview');
  if(bigAv){
    var src = gifAvatarData || avatarData;
    if(src){
      bigAv.innerHTML = '<img src="' + src + '" style="object-position:' + avatarPos.x + '% ' + avatarPos.y + '%">';
    } else {
      bigAv.textContent = me.username.charAt(0).toUpperCase();
    }
    applyFrame(bigAv, me.active_frame);
    var badge = bigAv.querySelector('.gif-badge');
    if(badge) badge.remove();
    if(gifAvatarData){
      var b = document.createElement('span');
      b.className = 'gif-badge';
      b.textContent = 'GIF';
      bigAv.appendChild(b);
    }
  }

  var bn = document.getElementById('bannerPreview');
  if(bn){
    var oi = bn.querySelector('img');
    if(oi) oi.remove();
    var bsrc = gifBannerData || bannerData;
    if(bsrc){
      var img = document.createElement('img');
      img.src = bsrc;
      img.style.objectPosition = bannerPos.x + '% ' + bannerPos.y + '%';
      bn.insertBefore(img, bn.firstChild);
    }
  }
}

function openProfile(){
  renderProfile();
  document.getElementById('profileModal').classList.add('open');
}

function closeProfile(){
  document.getElementById('profileModal').classList.remove('open');
}

// Avatar / banner upload
document.getElementById('avatarInput').addEventListener('change', function(e){
  var f = e.target.files[0];
  if(!f) return;
  var r = new FileReader();
  r.onload = function(ev){
    pendingAvatar = ev.target.result;
    avatarData = pendingAvatar;
    gifAvatarData = null;
    avatarPos = {x:50, y:50};
    renderProfile();
  };
  r.readAsDataURL(f);
});

document.getElementById('bannerInput').addEventListener('change', function(e){
  var f = e.target.files[0];
  if(!f) return;
  var r = new FileReader();
  r.onload = function(ev){
    pendingBanner = ev.target.result;
    bannerData = pendingBanner;
    gifBannerData = null;
    bannerPos = {x:50, y:50};
    renderProfile();
  };
  r.readAsDataURL(f);
});

async function saveProfile(){
  var bio = document.getElementById('bioInput').value.trim();
  var music = document.getElementById('musicInput').value.trim();
  var payload = {
    token: token,
    avatar: pendingAvatar,
    banner: pendingBanner,
    avatar_pos: avatarPos.x + '% ' + avatarPos.y + '%',
    banner_pos: bannerPos.x + '% ' + bannerPos.y + '%',
    nickname_color: nicknameColor,
    nickname_gradient: nicknameGradient,
    bio: bio,
    fav_music: music
  };
  var res = await api('/update_profile', {method:'POST', body: payload});
  if(!res.ok){ showNotice('❌ ' + res.error, 'error'); return; }
  Object.assign(me, {
    avatar: avatarData, banner: bannerData,
    nickname_color: nicknameColor, nickname_gradient: nicknameGradient,
    bio: bio, fav_music: music
  });
  pendingAvatar = null;
  pendingBanner = null;
  closeProfile();
  showNotice('✅ Сохранено');
}

/* ============================================================
   СТАТУС
   ============================================================ */
function openStatusMenu(){
  document.getElementById('statusMenuModal').classList.add('open');
  document.getElementById('customStatusInput').value = (me && me.custom_status) || '';
}

async function setOnlineStatus(st){
  var res = await api('/user/status', {method:'POST', body:{
    token: token,
    online_status: st,
    custom_status: (me && me.custom_status) || ''
  }});
  if(res.ok){
    if(me) me.online_status = st;
    showNotice('✅ ' + st);
  }
}

async function saveCustomStatus(){
  var cs = document.getElementById('customStatusInput').value.trim();
  var res = await api('/user/status', {method:'POST', body:{
    token: token,
    online_status: (me && me.online_status) || 'online',
    custom_status: cs
  }});
  if(res.ok){
    if(me) me.custom_status = cs;
    showNotice('💭 Сохранено');
    document.getElementById('statusMenuModal').classList.remove('open');
  }
}

/* ============================================================
   СТИЛЬ НИКА
   ============================================================ */
function openNickStyle(){
  tempNickColor = nicknameColor || (me && me.nickname_color);
  tempNickGradient = nicknameGradient || (me && me.nickname_gradient);
  var preview = document.getElementById('nickPreview');
  preview.textContent = me.username;
  applyNickPreview(preview);
  var cg = document.getElementById('colorGrid');
  cg.innerHTML = NICK_COLORS.map(function(c){
    return '<div class="color-swatch' + (c === tempNickColor ? ' active' : '') + '" style="background:' + c + '" onclick="pickNickColor(\'' + c + '\',this)"></div>';
  }).join('');
  var gg = document.getElementById('gradientGrid');
  gg.innerHTML = NICK_GRADIENTS.map(function(g){
    return '<div class="color-swatch' + (g === tempNickGradient ? ' active' : '') + '" style="background:' + g + '" onclick="pickNickGradient(\'' + g + '\',this)"></div>';
  }).join('');
  document.getElementById('nickStyleModal').classList.add('open');
}

function applyNickPreview(el){
  el.style.background = '';
  el.style.webkitBackgroundClip = '';
  el.style.webkitTextFillColor = '';
  el.style.color = '';
  if(tempNickGradient){
    el.style.background = tempNickGradient;
    el.style.webkitBackgroundClip = 'text';
    el.style.webkitTextFillColor = 'transparent';
  } else if(tempNickColor){
    el.style.color = tempNickColor;
  }
}

function pickNickColor(c, el){
  tempNickColor = c;
  tempNickGradient = null;
  document.querySelectorAll('#colorGrid .color-swatch').forEach(function(s){ s.classList.remove('active'); });
  document.querySelectorAll('#gradientGrid .color-swatch').forEach(function(s){ s.classList.remove('active'); });
  if(el) el.classList.add('active');
  applyNickPreview(document.getElementById('nickPreview'));
}

function pickNickGradient(g, el){
  tempNickGradient = g;
  tempNickColor = null;
  document.querySelectorAll('#colorGrid .color-swatch').forEach(function(s){ s.classList.remove('active'); });
  document.querySelectorAll('#gradientGrid .color-swatch').forEach(function(s){ s.classList.remove('active'); });
  if(el) el.classList.add('active');
  applyNickPreview(document.getElementById('nickPreview'));
}

async function saveNickStyle(){
  nicknameColor = tempNickColor;
  nicknameGradient = tempNickGradient;
  var res = await api('/update_profile', {method:'POST', body:{
    token: token,
    nickname_color: nicknameColor,
    nickname_gradient: nicknameGradient
  }});
  if(res.ok){
    me.nickname_color = nicknameColor;
    me.nickname_gradient = nicknameGradient;
    renderProfile();
    document.getElementById('nickStyleModal').classList.remove('open');
    showNotice('🎨 Сохранено');
  }
}

async function resetNickStyle(){
  nicknameColor = null;
  nicknameGradient = null;
  var res = await api('/update_profile', {method:'POST', body:{
    token: token,
    nickname_color: null,
    nickname_gradient: null
  }});
  if(res.ok){
    me.nickname_color = null;
    me.nickname_gradient = null;
    renderProfile();
    document.getElementById('nickStyleModal').classList.remove('open');
    showNotice('🗑️ Сброшено');
  }
}

/* ============================================================
   EMAIL VERIFY
   ============================================================ */
function openEmailVerify(){
  emailState = {step:'input', email:(me && me.email) || '', code:'', cooldown:0, timerId:null};
  renderEmailModal();
  document.getElementById('emailVerifyModal').classList.add('open');
}

function closeEmailVerify(){
  if(emailState.timerId){ clearInterval(emailState.timerId); emailState.timerId = null; }
  document.getElementById('emailVerifyModal').classList.remove('open');
}

function renderEmailModal(){
  var body = document.getElementById('emailVerifyBody');
  var html = '';

  if(me && me.email_verified){
    html = '<div class="email-verify-card">' +
      '<div class="evc-title ok">✅ Почта подтверждена</div>' +
      '<div class="evc-desc">' + esc(me.email || '') + '</div>' +
      '</div>' +
      '<button class="save-btn gray" onclick="closeEmailVerify()">Закрыть</button>';
    body.innerHTML = html;
    return;
  }

  if(emailState.step === 'input'){
    html = '<div class="email-verify-card">' +
      '<div class="evc-title wait">📧 Введи email</div>' +
      '<div class="evc-desc">Мы отправим 6-значный код для подтверждения.</div>' +
      '</div>' +
      '<input type="email" id="evEmail" class="input-field" placeholder="your@email.com" value="' + esc(emailState.email) + '" style="margin-bottom:10px">' +
      '<div id="evStatus"></div>' +
      '<button class="save-btn green" id="evSendBtn" onclick="sendEmailCode()">📤 Отправить код</button>';
    body.innerHTML = html;
    return;
  }

  if(emailState.step === 'code'){
    html = '<div class="email-verify-card">' +
      '<div class="evc-title wait">📨 Введи код из письма</div>' +
      '<div class="evc-desc">Отправили на <b>' + esc(emailState.email) + '</b>. Проверь спам.</div>' +
      '</div>' +
      '<input type="text" class="email-code-input" id="evCode" maxlength="6" inputmode="numeric" pattern="[0-9]*" placeholder="000000" autocomplete="one-time-code">' +
      '<div id="evStatus"></div>' +
      '<button class="save-btn gold" id="evVerifyBtn" onclick="verifyEmailCode()">✅ Подтвердить</button>' +
      '<div class="email-timer" id="evTimer">Повторная отправка через 60с</div>' +
      '<button class="save-btn gray" onclick="resendEmailCode()" id="evResendBtn" disabled>🔄 Отправить ещё раз</button>' +
      '<button class="save-btn gray" onclick="openEmailVerify()" style="margin-top:6px">✏️ Другой email</button>';
    body.innerHTML = html;
    setTimeout(function(){
      var c = document.getElementById('evCode');
      if(c) c.focus();
    }, 100);
    startEmailCooldown();
    return;
  }
}

async function sendEmailCode(){
  var em = document.getElementById('evEmail').value.trim();
  var status = document.getElementById('evStatus');
  var btn = document.getElementById('evSendBtn');
  if(!em || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em)){
    status.innerHTML = '<div class="email-status-err">❌ Плохой email</div>';
    return;
  }
  btn.disabled = true;
  btn.textContent = 'Отправка...';
  status.innerHTML = '<div class="email-status-wait">⏳ Отправляем...</div>';
  var res = await api('/email/send_code', {method:'POST', body:{token:token, email:em}});
  if(!res.ok){
    status.innerHTML = '<div class="email-status-err">❌ ' + res.error + '</div>';
    btn.disabled = false;
    btn.textContent = '📤 Отправить код';
    return;
  }
  var d = res.data;
  emailState.step = 'code';
  emailState.email = em;
  if(d.sent){
    emailState.code = '';
    renderEmailModal();
  } else {
    emailState.code = d.code_hint || '';
    renderEmailModal();
    var st = document.getElementById('evStatus');
    if(st) st.innerHTML = '<div class="email-status-wait">⚠️ SMTP не настроен. Твой код: <b style="font-size:18px;letter-spacing:3px">' + d.code_hint + '</b></div>';
  }
  if(me){ me.email = em; me.email_verified = false; }
}

async function verifyEmailCode(){
  var code = document.getElementById('evCode').value.trim().replace(/\D/g, '');
  var status = document.getElementById('evStatus');
  var btn = document.getElementById('evVerifyBtn');
  if(code.length !== 6){
    status.innerHTML = '<div class="email-status-err">❌ 6 цифр нужно</div>';
    return;
  }
  btn.disabled = true;
  btn.textContent = 'Проверяем...';
  var res = await api('/email/verify', {method:'POST', body:{token:token, code:code}});
  if(!res.ok){
    status.innerHTML = '<div class="email-status-err">❌ ' + res.error + '</div>';
    btn.disabled = false;
    btn.textContent = '✅ Подтвердить';
    return;
  }
  status.innerHTML = '<div class="email-status-ok">✅ Подтверждено!</div>';
  if(me) me.email_verified = true;
  if(emailState.timerId){ clearInterval(emailState.timerId); emailState.timerId = null; }
  setTimeout(function(){
    emailState.step = 'input';
    renderEmailModal();
    renderProfile();
  }, 1200);
}

async function resendEmailCode(){
  if(emailState.cooldown > 0) return;
  var btn = document.getElementById('evResendBtn');
  if(btn){ btn.disabled = true; btn.textContent = 'Отправка...'; }
  var res = await api('/email/resend', {method:'POST', body:{token:token, email:emailState.email}});
  var st = document.getElementById('evStatus');
  if(!res.ok){
    if(st) st.innerHTML = '<div class="email-status-err">❌ ' + res.error + '</div>';
  } else {
    var d = res.data;
    if(d.sent){
      if(st) st.innerHTML = '<div class="email-status-ok">✅ Отправлено</div>';
    } else {
      emailState.code = d.code_hint;
      if(st) st.innerHTML = '<div class="email-status-wait">⚠️ Твой код: <b style="font-size:18px;letter-spacing:3px">' + d.code_hint + '</b></div>';
    }
    startEmailCooldown();
  }
}

function startEmailCooldown(){
  if(emailState.timerId) clearInterval(emailState.timerId);
  emailState.cooldown = 60;
  var timerEl = document.getElementById('evTimer');
  var btn = document.getElementById('evResendBtn');
  if(btn) btn.disabled = true;
  emailState.timerId = setInterval(function(){
    emailState.cooldown--;
    var t = document.getElementById('evTimer');
    var b = document.getElementById('evResendBtn');
    if(emailState.cooldown <= 0){
      clearInterval(emailState.timerId);
      emailState.timerId = null;
      if(t) t.textContent = 'Можно отправить снова';
      if(b) b.disabled = false;
      return;
    }
    if(t) t.textContent = 'Повторная отправка через ' + emailState.cooldown + 'с';
  }, 1000);
}

/* ============================================================
   CHANGELOG
   ============================================================ */
async function showChangelog(force){
  var seen = localStorage.getItem('belugacord_version');
  if(!force && seen === BC.version) return;
  var res = await api('/changelog');
  if(!res.ok) return;
  var d = res.data;
  var body = document.getElementById('changelogBody');
  var html = '';
  if(d.all){
    var versions = Object.keys(d.all).sort().reverse();
    versions.forEach(function(v){
      var ch = d.all[v];
      var isCur = v === d.current;
      html += '<div style="margin-bottom:16px">';
      html += '<div style="font-size:13px;font-weight:900;color:var(--accent);margin-bottom:8px">' + ch.title + (isCur ? ' <span class="changelog-badge">NEW</span>' : '') + '</div>';
      html += '<ul style="list-style:none;padding:0;margin:0">';
      ch.items.forEach(function(item){
        html += '<li style="padding:8px 12px;background:var(--bg-input);border-radius:8px;margin-bottom:4px;font-size:12px;line-height:1.4">' + esc(item) + '</li>';
      });
      html += '</ul></div>';
    });
  }
  body.innerHTML = html;
  document.getElementById('changelogModal').classList.add('open');
  localStorage.setItem('belugacord_version', BC.version);
}

/* ============================================================
   ЯЗЫК
   ============================================================ */
function openLanguage(){
  document.getElementById('languageModal').classList.add('open');
  renderLangGrid();
}

function renderLangGrid(){
  var c = document.getElementById('langGrid');
  var current = localStorage.getItem('belugacord_lang') || 'ru';
  c.innerHTML = LANGS.map(function(l){
    return '<div class="lang-card' + (current === l.code ? ' active' : '') + '" onclick="setLang(\'' + l.code + '\')">' +
      '<span class="lang-flag">' + l.flag + '</span>' +
      '<span class="lang-name">' + l.name + '</span>' +
    '</div>';
  }).join('');
}

function setLang(code){
  applyLang(code);
  renderLangGrid();
  var l = LANGS.find(function(x){ return x.code === code; });
  showNotice('🌐 ' + (l ? l.name : code));
}

/* ============================================================
   START MENU (рендер)
   ============================================================ */
function renderStartMenu(){
  var sm = document.getElementById('startMenu');
  if(!sm) return;

  var html = '';
  html += '<div class="start-menu-title">Профиль</div>';
  html += menuItem('👤', 'Мой профиль', 'openProfile()');
  html += menuItem('⚙️', 'Настройки', 'openSettings()');
  html += menuItem('🎨', 'Стиль ника', 'openNickStyle()');
  html += menuItem('🟢', 'Статус', 'openStatusMenu()', 'linear-gradient(135deg,#22c55e,#16a34a)');
  html += menuItem('🏆', 'Достижения', 'openAchievements()', 'linear-gradient(135deg,#ffd700,#22d3ee)');
  html += menuItem('📧', 'Подтвердить почту', 'openEmailVerify()', 'linear-gradient(135deg,#22c55e,#06b6d4)');

  html += '<div class="start-menu-title" style="margin-top:8px">Активность</div>';
  html += menuItem('📊', 'Уровни', 'openLevels()', 'linear-gradient(135deg,#22c55e,#22d3ee)');
  html += menuItem('💎', 'Премиум', 'openPremium()', 'linear-gradient(135deg,#ffd700,#d946ef)');
  html += menuItem('🖼️', 'Рамки', 'openFrames()', 'linear-gradient(135deg,#ec4899,#8b5cf6)');
  html += menuItem('👑', 'Титулы', 'openTitles()', 'linear-gradient(135deg,#8b5cf6,#22d3ee)');
  html += menuItem('🎭', 'Скины чата', 'openChatSkins()', 'linear-gradient(135deg,#f43f5e,#8b5cf6)');
  html += menuItem('✨', 'Эффекты', 'openMsgEffects()', 'linear-gradient(135deg,#ffd700,#f43f5e)');
  html += menuItem('🌐', 'Язык', 'openLanguage()', 'linear-gradient(135deg,#22d3ee,#22c55e)');
  html += menuItem('⚡', 'Команды', 'openCommands()', 'linear-gradient(135deg,#8b5cf6,#d946ef)');
  html += menuItem('💾', 'Сохранённые', 'openSavedMessages()', 'linear-gradient(135deg,#22c55e,#ffd700)');
  html += menuItem('📰', 'Что нового', 'showChangelog(true)', 'linear-gradient(135deg,#8b5cf6,#22d3ee)');

  html += '<div class="start-menu-title" style="margin-top:8px">Система</div>';
  html += menuItem('⏻', 'Выйти', 'logout()', 'linear-gradient(135deg,#f43f5e,#ec4899)');

  sm.innerHTML = html;
}

function menuItem(icon, label, action, bg){
  var style = bg ? ' style="background:' + bg + '"' : '';
  return '<div class="start-menu-item" onclick="' + action + ';toggleStartMenu()">' +
    '<div class="sm-icon"' + style + '>' + icon + '</div>' +
    '<div>' + label + '</div>' +
  '</div>';
}

/* ============================================================
   ИКОНКИ СТОЛА
   ============================================================ */
function renderDesktopIcons(){
  var cont = document.getElementById('desktopIcons');
  if(!cont) return;

  var icons = [
    {icon:'👥', label:'Друзья', action:'showFriends()', bg:''},
    {icon:'🔍', label:'Поиск', action:'openUserSearch()', bg:'linear-gradient(135deg,#22d3ee,#06b6d4)'},
    {icon:'➕', label:'Создать', action:'openCreateMenu()', bg:''},
    {icon:'🎮', label:'Игры', action:'openGamesMenu()', bg:''},
    {icon:'📸', label:'Сторис', action:'openStoriesFeed()', bg:'linear-gradient(135deg,#d946ef,#ec4899)'},
    {icon:'🛒', label:'Магазин', action:'openShop()', bg:'linear-gradient(135deg,#ffd700,#ff8c00)'},
    {icon:'🎨', label:'NFT', action:'openNftMarket()', bg:'linear-gradient(135deg,#8b5cf6,#d946ef)'},
    {icon:'🎁', label:'Кейсы', action:'openCases()', bg:'linear-gradient(135deg,#f43f5e,#ff8c00)'},
    {icon:'🎀', label:'Подарки', action:'openGiftsCollection()', bg:'linear-gradient(135deg,#ec4899,#f43f5e)'},
    {icon:'⬆️', label:'Апгрейд', action:'openUpgrader()', bg:'linear-gradient(135deg,#22c55e,#ffd700)'},
    {icon:'📦', label:'Сундук', action:'openChest()', bg:'linear-gradient(135deg,#ffd700,#d946ef)'},
    {icon:'🎟️', label:'Лотерея', action:'openLottery()', bg:'linear-gradient(135deg,#f43f5e,#ffd700)'},
    {icon:'🏦', label:'Банк', action:'openBank()', bg:'linear-gradient(135deg,#22c55e,#06b6d4)'},
    {icon:'🔨', label:'Аукцион', action:'openAuction()', bg:'linear-gradient(135deg,#8b5cf6,#f43f5e)'},
    {icon:'📋', label:'Квесты', action:'openQuests()', bg:'linear-gradient(135deg,#22d3ee,#8b5cf6)'},
    {icon:'🏆', label:'БП', action:'openBattlePass()', bg:'linear-gradient(135deg,#ffd700,#8b5cf6)'},
    {icon:'📊', label:'Уровни', action:'openLevels()', bg:'linear-gradient(135deg,#22c55e,#22d3ee)'},
    {icon:'💎', label:'Премиум', action:'openPremium()', bg:'linear-gradient(135deg,#ffd700,#d946ef)'},
    {icon:'🖼️', label:'Рамки', action:'openFrames()', bg:'linear-gradient(135deg,#ec4899,#8b5cf6)'},
    {icon:'👑', label:'Титулы', action:'openTitles()', bg:'linear-gradient(135deg,#8b5cf6,#22d3ee)'},
    {icon:'🎭', label:'Скины', action:'openChatSkins()', bg:'linear-gradient(135deg,#f43f5e,#8b5cf6)'},
    {icon:'✨', label:'Эффекты', action:'openMsgEffects()', bg:'linear-gradient(135deg,#ffd700,#f43f5e)'},
    {icon:'⚙️', label:'Настройки', action:'openSettings()', bg:''},
    {icon:'👤', label:'Профиль', action:'openProfile()', bg:''},
    {icon:'🌐', label:'Язык', action:'openLanguage()', bg:'linear-gradient(135deg,#22d3ee,#22c55e)'},
    {icon:'📰', label:'Что нового', action:'showChangelog(true)', bg:'linear-gradient(135deg,#8b5cf6,#22d3ee)'},
    {icon:'💾', label:'Сохранённые', action:'openSavedMessages()', bg:'linear-gradient(135deg,#22c55e,#ffd700)'},
    {icon:'⚡', label:'Команды', action:'openCommands()', bg:'linear-gradient(135deg,#8b5cf6,#d946ef)'},
    {icon:'📧', label:'Почта', action:'openEmailVerify()', bg:'linear-gradient(135deg,#22c55e,#06b6d4)'}
  ];

  var html = icons.map(function(i){
    var style = i.bg ? ' style="background:' + i.bg + '"' : '';
    return '<div class="desktop-icon" onclick="' + i.action + '">' +
      '<div class="d-icon"' + style + '>' + i.icon + '</div>' +
      '<div class="d-label">' + i.label + '</div>' +
    '</div>';
  }).join('');

  // Спец-иконки для админа/владельца
  if(BC.isOwner){
    html += '<div class="desktop-icon" onclick="openOwnerGui()"><div class="d-icon" style="background:var(--owner-grad)">👑</div><div class="d-label">БОГ-ГУИ</div></div>';
  }
  if(BC.isMod){
    html += '<div class="desktop-icon" onclick="openModPanel()"><div class="d-icon" style="background:linear-gradient(135deg,#22d3ee,#06b6d4)">🔧</div><div class="d-label">Модер</div></div>';
  }
  if(me && me.is_admin){
    html += '<div class="desktop-icon" onclick="openAdminLogin()"><div class="d-icon" style="background:linear-gradient(135deg,#ffd700,#ff8c00)">🛡️</div><div class="d-label">Админка</div></div>';
  }

  cont.innerHTML = html;
}

/* ============================================================
   НАСТРОЙКИ — ТЕМЫ И ИНТЕРФЕЙС
   ============================================================ */
function openSettings(){
  document.getElementById('settingsModal').classList.add('open');
  showSettingsTab('theme');
}

function showSettingsTab(tab, ev){
  document.querySelectorAll('#settingsModal .settings-tab').forEach(function(t){
    t.classList.remove('active');
  });
  if(ev) ev.target.classList.add('active');
  var c = document.getElementById('settingsContent');
  var cur = localStorage.getItem('belugacord_theme') || 'beluga';

  if(tab === 'theme'){
    var themes = [
      {id:'beluga', name:'🐱 Beluga', desc:'Фиолетово-розовый', preview:'linear-gradient(135deg,#d946ef,#8b5cf6)'},
      {id:'discord', name:'💬 Discord', desc:'Классика', preview:'linear-gradient(135deg,#5865f2,#2b2d31)'},
      {id:'white', name:'☀️ Белая', desc:'Минимализм', preview:'linear-gradient(135deg,#fff,#000)'},
      {id:'cyber', name:'🤖 Киберпанк', desc:'Жёлтый+циан', preview:'linear-gradient(135deg,#ffee00,#00ffff)'},
      {id:'retro', name:'📺 Ретро 95', desc:'Windows 95', preview:'linear-gradient(135deg,#c0c0c0,#000080)'},
      {id:'cs2', name:'🎯 CS 2', desc:'Тёмный+оранжевый', preview:'linear-gradient(135deg,#f0883e,#0d1117)'},
      {id:'cs16', name:'🔫 CS 1.6', desc:'Зелёно-чёрный', preview:'linear-gradient(135deg,#7cb342,#0a1206)'},
      {id:'minecraft', name:'⛏️ Minecraft', desc:'Зелёный', preview:'linear-gradient(135deg,#7cb342,#2d3d2d)'},
      {id:'neon', name:'🌟 Неон', desc:'Розовый неон', preview:'linear-gradient(135deg,#ff00ff,#00ffff)'},
      {id:'nature', name:'🌿 Природа', desc:'Зелёный', preview:'linear-gradient(135deg,#4ade80,#22c55e)'},
      {id:'sunset', name:'🌅 Закат', desc:'Оранжевый', preview:'linear-gradient(135deg,#ff6b35,#f7931e)'},
      {id:'ocean', name:'🌊 Океан', desc:'Синий', preview:'linear-gradient(135deg,#0ea5e9,#06b6d4)'},
      {id:'royal', name:'👑 Роял', desc:'Фиолетовый', preview:'linear-gradient(135deg,#a855f7,#9333ea)'}
    ];
    c.innerHTML = themes.map(function(t){
      return '<div style="display:flex;gap:12px;padding:14px;border-radius:12px;border:2px solid ' +
        (cur === t.id ? 'var(--accent)' : 'var(--border)') +
        ';background:var(--bg-input);cursor:pointer;margin-bottom:10px" onclick="setTheme(\'' + t.id + '\');showSettingsTab(\'theme\')">' +
        '<div style="width:56px;height:56px;border-radius:10px;background:' + t.preview + ';flex-shrink:0"></div>' +
        '<div style="flex:1">' +
          '<div style="color:var(--text);font-weight:800;font-size:14px">' + t.name + '</div>' +
          '<div style="color:var(--text-mute);font-size:12px">' + t.desc + '</div>' +
        '</div>' +
      '</div>';
    }).join('');
  }
  else if(tab === 'custom'){
    c.innerHTML = '<div style="text-align:center;padding:20px">Загрузка...</div>';
    api('/themes/list').then(function(res){
      if(!res.ok || !res.data.length){
        c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:30px">Пока нет кастомных тем 😢</div>';
        return;
      }
      window._customThemesCache = res.data;
      c.innerHTML = res.data.map(function(t){
        return '<div style="display:flex;gap:12px;padding:14px;border-radius:12px;border:1px solid var(--border);background:var(--bg-input);cursor:pointer;margin-bottom:10px" onclick="applyCustomThemeById(' + t.id + ')">' +
          '<div style="width:56px;height:56px;border-radius:10px;background:' + (t.vars['--accent'] || '#d946ef') + ';display:flex;align-items:center;justify-content:center;font-size:26px;flex-shrink:0">' + (t.emoji || '🎨') + '</div>' +
          '<div style="flex:1">' +
            '<div style="color:var(--text);font-weight:800;font-size:14px">' + esc(t.name) + '</div>' +
            '<div style="color:var(--text-mute);font-size:12px">Кастомная</div>' +
          '</div>' +
        '</div>';
      }).join('');
    });
  }
  else if(tab === 'ui'){
    var html = '<div class="shop-section-title" style="margin-top:8px">Шрифт</div>';
    html += '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px">';
    html += '<button class="save-btn gray" style="margin:0" onclick="setFont(\'\')">Стандарт</button>';
    html += '<button class="save-btn gray" style="margin:0" onclick="setFont(\'mono\')">Моно</button>';
    html += '<button class="save-btn gray" style="margin:0" onclick="setFont(\'serif\')">Сериф</button>';
    html += '<button class="save-btn gray" style="margin:0" onclick="setFont(\'comic\')">Комеди</button>';
    html += '</div>';
    html += '<div class="shop-section-title" style="margin-top:20px">Режимы</div>';
    html += '<label style="display:flex;align-items:center;gap:10px;padding:10px;background:var(--bg-input);border-radius:10px;margin-bottom:8px"><input type="checkbox" id="compactToggle" onchange="toggleCompact(this.checked)" style="width:20px;height:20px"' + (document.body.classList.contains('compact') ? ' checked' : '') + '><span>📐 Компактный режим</span></label>';
    html += '<div class="shop-section-title" style="margin-top:16px">Обои</div>';
    html += '<label for="wallpaperInput" style="display:flex;align-items:center;justify-content:center;padding:20px;background:var(--bg-input);border:2px dashed var(--border);border-radius:12px;cursor:pointer;font-size:13px">📷 Загрузить обои</label>';
    html += '<input type="file" id="wallpaperInput" accept="image/*" style="display:none" onchange="uploadWallpaper(this)">';
    html += '<button class="save-btn gray" style="margin-top:8px" onclick="clearWallpaper()">🗑️ Убрать обои</button>';
    c.innerHTML = html;
  }
  else if(tab === 'blocks'){
    c.innerHTML = '<div style="text-align:center;padding:20px">Загрузка...</div>';
    api('/blocks/list?token=' + encodeURIComponent(token)).then(function(res){
      if(!res.ok || !res.data.length){
        c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:30px">Никого в блоке 😇</div>';
        return;
      }
      c.innerHTML = res.data.map(function(u){
        return '<div style="display:flex;align-items:center;gap:12px;padding:10px;background:var(--bg-input);border-radius:10px;margin-bottom:6px">' +
          '<div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent-2));display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;overflow:hidden">' +
            (u.avatar ? '<img src="' + u.avatar + '" style="width:100%;height:100%;object-fit:cover">' : u.username.charAt(0).toUpperCase()) +
          '</div>' +
          '<div style="flex:1;font-weight:700;font-size:13px">' + esc(u.username) + '</div>' +
          '<button class="save-btn red" style="margin:0;width:auto;padding:6px 12px;font-size:11px" onclick="unblockUser(' + u.id + ')">Разблок</button>' +
        '</div>';
      }).join('');
    });
  }
}

function applyCustomThemeById(id){
  var list = window._customThemesCache || [];
  var t = list.find(function(x){ return x.id === id; });
  if(t) applyCustomTheme(t);
}

async function setFont(f){
  document.body.classList.remove('font-mono', 'font-serif', 'font-comic');
  if(f) document.body.classList.add('font-' + f);
  await api('/update_profile', {method:'POST', body:{token:token, font_choice:f}});
  if(me) me.font_choice = f;
  showSettingsTab('ui', {target: document.querySelector('[data-tab="ui"]')});
}

async function toggleCompact(on){
  document.body.classList.toggle('compact', on);
  await api('/update_profile', {method:'POST', body:{token:token, compact_mode:on}});
  if(me) me.compact_mode = on;
}

async function uploadWallpaper(inp){
  var f = inp.files[0];
  if(!f) return;
  var fd = new FormData();
  fd.append('token', token);
  fd.append('file', f);
  try {
    var r = await fetch('/api/upload', {method:'POST', body:fd});
    var d = await r.json();
    if(d.url){
      document.documentElement.style.setProperty('--custom-bg', 'url(' + d.url + ')');
      document.body.classList.add('custom-bg');
      await api('/update_profile', {method:'POST', body:{token:token, wallpaper:d.url}});
      if(me) me.wallpaper = d.url;
      showNotice('🖼️ Установлено');
    }
  } catch(e){}
  inp.value = '';
}

function clearWallpaper(){
  document.body.classList.remove('custom-bg');
  document.documentElement.style.setProperty('--custom-bg', 'none');
  api('/update_profile', {method:'POST', body:{token:token, wallpaper:null}});
  if(me) me.wallpaper = null;
  showNotice('🗑️ Убрано');
}

async function unblockUser(id){
  await api('/blocks/remove', {method:'POST', body:{token:token, user_id:id}});
  showSettingsTab('blocks', {target: document.querySelector('[data-tab="blocks"]')});
}

/* ============================================================
   ДОСТИЖЕНИЯ
   ============================================================ */
async function loadAchievementsCatalog(){
  var res = await api('/achievements/all');
  if(res.ok) ACHIEVEMENTS_CACHE = res.data;
}

async function openAchievements(){
  document.getElementById('achievementsModal').classList.add('open');
  var b = document.getElementById('achievementsBody');
  b.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">Загрузка...</div>';
  if(!Object.keys(ACHIEVEMENTS_CACHE).length) await loadAchievementsCatalog();
  var res = await api('/user/' + me.id);
  if(!res.ok){ b.innerHTML = '<div style="color:#f43f5e;text-align:center;padding:40px">Ошибка</div>'; return; }
  var u = res.data;
  var mine = u.achievements || [];
  var html = '<div style="text-align:center;margin-bottom:14px;color:var(--text-dim);font-size:13px">Открыто: ' + mine.length + ' / ' + Object.keys(ACHIEVEMENTS_CACHE).length + '</div>';
  html += '<div class="ach-grid">';
  Object.keys(ACHIEVEMENTS_CACHE).forEach(function(k){
    var a = ACHIEVEMENTS_CACHE[k];
    var has = mine.indexOf(k) !== -1;
    html += '<div class="ach-card' + (has ? '' : ' locked') + '">' +
      '<span class="ach-icon">' + a.emoji + '</span>' +
      '<div class="ach-name">' + esc(a.name) + '</div>' +
      '<div class="ach-desc">' + esc(a.desc) + '</div>' +
      (has ? '<div style="color:#22c55e;font-weight:900;margin-top:6px;font-size:11px">✓ +50🏅</div>' : '') +
    '</div>';
  });
  html += '</div>';
  b.innerHTML = html;
}

/* ============================================================
   ТОП БОГАЧЕЙ
   ============================================================ */
async function openLeaders(){
  document.getElementById('leadersModal').classList.add('open');
  var l = document.getElementById('leadersList');
  l.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">Загрузка...</div>';
  var res = await api('/coins/leaders');
  if(!res.ok || !res.data.length){
    l.innerHTML = '<div style="color:var(--text-mute);text-align:center;padding:40px">Пусто</div>';
    return;
  }
  l.innerHTML = res.data.map(function(u, i){
    var medal = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : '#' + (i + 1);
    return '<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:var(--bg-input);border-radius:10px;margin-bottom:6px">' +
      '<div style="font-size:18px;font-weight:900;color:#ffd700;min-width:36px">' + medal + '</div>' +
      '<div style="flex:1;font-weight:700">' + esc(u.username) + '</div>' +
      '<div style="color:#ffd700;font-weight:800">' + u.coins.toLocaleString('ru-RU') + ' 🏅</div>' +
    '</div>';
  }).join('');
}

/* ============================================================
   УРОВНИ
   ============================================================ */
async function openLevels(){
  document.getElementById('levelsModal').classList.add('open');
  var res = await api('/levels/me?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var d = res.data;
  var lvl = d.level || 1;
  var xp = d.xp || 0;
  var next = lvl * 100;
  document.getElementById('levelCircle').textContent = lvl;
  document.getElementById('levelName').textContent = 'Уровень ' + lvl;
  document.getElementById('levelProgressFill').style.width = Math.min(100, (xp / next) * 100) + '%';
  document.getElementById('levelXPText').textContent = xp + ' / ' + next + ' XP';

  var lr = await api('/levels/leaders');
  if(lr.ok){
    document.getElementById('levelLeaderboard').innerHTML =
      '<div class="shop-section-title">🏆 Топ по уровню</div>' +
      lr.data.slice(0, 10).map(function(u, i){
        var m = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : '#' + (i + 1);
        return '<div style="display:flex;gap:12px;padding:8px 12px;background:var(--bg-input);border-radius:8px;margin-bottom:4px">' +
          '<div style="min-width:32px;font-weight:900">' + m + '</div>' +
          '<div style="flex:1">' + esc(u.username) + '</div>' +
          '<div style="color:var(--gold);font-weight:900">Ур. ' + u.level + '</div>' +
        '</div>';
      }).join('');
  }
}

/* ============================================================
   ПРЕМИУМ
   ============================================================ */
async function openPremium(){
  document.getElementById('premiumModal').classList.add('open');
  var res = await api('/premium/status?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var d = res.data;
  var card = document.getElementById('premiumStatusCard');
  if(d.is_premium){
    card.innerHTML =
      '<div class="premium-card">' +
        '<span class="premium-crown">👑</span>' +
        '<div class="premium-tier-name">PREMIUM АКТИВЕН</div>' +
        '<div class="premium-expires">до ' + new Date(d.expires).toLocaleDateString('ru-RU') + '</div>' +
      '</div>';
  } else {
    card.innerHTML =
      '<div class="premium-card">' +
        '<span class="premium-crown">👑</span>' +
        '<div class="premium-tier-name">ПРЕМИУМ НЕ АКТИВЕН</div>' +
        '<div class="premium-expires">Оформи подписку</div>' +
      '</div>';
  }
}

async function buyPremium(plan){
  var res = await api('/premium/buy', {method:'POST', body:{token:token, plan:plan}});
  if(res.ok){
    showNotice('💎 Премиум до ' + new Date(res.data.premium_until).toLocaleDateString('ru-RU'));
    BC.showConfetti();
    BC.showBalloons();
    if(me) me.is_premium = true;
    document.getElementById('premiumModal').classList.remove('open');
  } else {
    showNotice('❌ ' + res.error, 'error');
  }
}

/* ============================================================
   РАМКИ
   ============================================================ */
async function openFrames(){
  document.getElementById('framesModal').classList.add('open');
  var c = document.getElementById('framesList');
  c.innerHTML = '<div style="text-align:center;padding:20px">Загрузка...</div>';
  var res = await api('/frames/list?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  FRAMES_CACHE = res.data;
  c.innerHTML = res.data.map(function(f){
    var active = me && me.active_frame === f.frame_id;
    return '<div class="title-card' + (active ? ' active' : '') + '" onclick="frameAction(\'' + f.frame_id + '\',' + f.owned + ',' + f.price_coins + ',' + f.price_kp + ')">' +
      '<div class="title-card-icon">' + f.emoji + '</div>' +
      '<div class="title-card-name">' + esc(f.name) + '</div>' +
      '<div style="font-size:10px;color:var(--gold);margin-top:4px">' +
        (f.owned ? (active ? '✓ НАДЕТО' : 'Куплено') : (f.price_coins + ' 🏅 / ' + f.price_kp + ' КП')) +
      '</div>' +
    '</div>';
  }).join('');
}

async function frameAction(fid, owned, priceCoins, priceKp){
  if(owned){
    var res = await api('/frames/set', {method:'POST', body:{token:token, frame_id:fid}});
    if(res.ok){
      if(me) me.active_frame = fid;
      showNotice('🎨 Надето');
      openFrames();
    }
  } else {
    if(!confirm('Купить за ' + (priceCoins || priceKp) + '?')) return;
    var method = priceCoins ? 'coins' : 'kp';
    var res2 = await api('/frames/buy', {method:'POST', body:{token:token, frame_id:fid, method:method}});
    if(res2.ok){ showNotice('🎨 Куплено'); openFrames(); }
    else showNotice('❌ ' + res2.error, 'error');
  }
}

/* ============================================================
   ТИТУЛЫ
   ============================================================ */
async function openTitles(){
  document.getElementById('titlesModal').classList.add('open');
  var c = document.getElementById('titlesGrid');
  c.innerHTML = '<div style="text-align:center;padding:20px">Загрузка...</div>';
  var res = await api('/titles/list?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  c.innerHTML = res.data.map(function(t){
    var active = me && me.title === t.name;
    return '<div class="title-card' + (active ? ' active' : '') + '" onclick="setTitle(\'' + esc(t.name) + '\')">' +
      '<div class="title-card-icon">' + t.emoji + '</div>' +
      '<div class="title-card-name">' + esc(t.name) + '</div>' +
    '</div>';
  }).join('');
}

async function setTitle(name){
  var res = await api('/titles/set', {method:'POST', body:{token:token, title:name}});
  if(res.ok){
    if(me) me.title = name;
    showNotice('👑 Установлен');
    openTitles();
  }
}

/* ============================================================
   СКИНЫ ЧАТА
   ============================================================ */
function openChatSkins(){
  document.getElementById('chatSkinModal').classList.add('open');
  renderChatSkins();
}

function renderChatSkins(){
  var c = document.getElementById('chatSkinsGrid');
  c.innerHTML = CHAT_SKINS.map(function(s){
    return '<div class="chat-skin' + (currentChatSkin === s.id ? ' active' : '') + '" style="background:' + (s.bg || 'var(--bg-input)') + '" onclick="selectChatSkin(\'' + s.id + '\')">' +
      '<div class="chat-skin-name">' + s.name + '</div>' +
    '</div>';
  }).join('');
}

function selectChatSkin(id){
  currentChatSkin = id;
  localStorage.setItem('belugacord_chat_skin', id);
  applyChatSkin();
  renderChatSkins();
}

function applyChatSkin(){
  var skin = CHAT_SKINS.find(function(s){ return s.id === currentChatSkin; });
  if(!skin) return;
  var cb = document.getElementById('messagesBody');
  if(cb){
    if(skin.bg) cb.style.background = skin.bg;
    else cb.style.background = '';
  }
}

/* ============================================================
   ЭФФЕКТЫ СООБЩЕНИЙ
   ============================================================ */
function openMsgEffects(){
  document.getElementById('msgEffectModal').classList.add('open');
  renderMsgEffects();
}

function renderMsgEffects(){
  var c = document.getElementById('msgEffectsGrid');
  c.innerHTML = MSG_EFFECTS.map(function(e){
    return '<div class="msg-effect' + (currentMsgEffect === e.id ? ' active' : '') + '" onclick="selectMsgEffect(\'' + e.id + '\')">' +
      '<div class="msg-effect-name">' + e.name + '</div>' +
    '</div>';
  }).join('');
}

function selectMsgEffect(id){
  currentMsgEffect = id;
  localStorage.setItem('belugacord_msg_effect', id);
  renderMsgEffects();
  showNotice('✨ Эффект выбран');
}

/* ============================================================
   КОМАНДЫ
   ============================================================ */
var _commandsCache = [];
async function openCommands(){
  document.getElementById('commandsModal').classList.add('open');
  var res = await api('/commands/list?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  _commandsCache = res.data;
  renderCommandsList(_commandsCache);
}

function renderCommandsList(list){
  var c = document.getElementById('commandsList');
  if(!list.length){
    c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:20px">Пусто</div>';
    return;
  }
  c.innerHTML = list.map(function(cmd){
    return '<div style="padding:10px;background:var(--bg-input);border-radius:10px;margin-bottom:6px;cursor:pointer" onclick="useCommand(\'' + esc(cmd.name) + '\')">' +
      '<div style="font-family:monospace;font-weight:800;color:var(--accent)">/' + esc(cmd.name) + '</div>' +
      '<div style="font-size:12px;color:var(--text-mute);margin-top:4px">' + esc(cmd.description || '') + '</div>' +
    '</div>';
  }).join('');
}

function filterCommands(q){
  if(!q){ renderCommandsList(_commandsCache); return; }
  renderCommandsList(_commandsCache.filter(function(c){
    return c.name.toLowerCase().indexOf(q.toLowerCase()) !== -1;
  }));
}

function useCommand(name){
  document.getElementById('commandsModal').classList.remove('open');
  var inp = document.getElementById('inp');
  if(inp){ inp.value = '/' + name + ' '; inp.focus(); }
}

/* ============================================================
   ПОИСК ЮЗЕРОВ
   ============================================================ */
var _userSearchTimer = null;
function openUserSearch(){
  document.getElementById('userSearchModal').classList.add('open');
  document.getElementById('userSearchInput').value = '';
  document.getElementById('userSearchResults').innerHTML = '';
  setTimeout(function(){
    document.getElementById('userSearchInput').focus();
  }, 100);
}

function doUserSearch(q){
  clearTimeout(_userSearchTimer);
  var c = document.getElementById('userSearchResults');
  if(q.trim().length < 2){ c.innerHTML = ''; return; }
  c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:20px">Поиск...</div>';
  _userSearchTimer = setTimeout(async function(){
    var res = await api('/users/search?q=' + encodeURIComponent(q) + '&token=' + encodeURIComponent(token));
    if(!res.ok || !res.data.length){
      c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:20px">Никого</div>';
      return;
    }
    c.innerHTML = '';
    res.data.forEach(function(u){
      var row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:10px;cursor:pointer;margin-bottom:4px;background:var(--bg-input)';
      var av = u.avatar
        ? '<img src="' + (u.gif_avatar || u.avatar) + '" style="width:100%;height:100%;object-fit:cover">'
        : u.username.charAt(0).toUpperCase();
      var st = u.online_status || 'online';
      var dot = '<span class="status-dot ' + (u.online ? (st === 'dnd' ? 'dnd' : 'online') : 'offline') + '"></span>';
      row.innerHTML =
        '<div style="width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent-2));display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;overflow:hidden;flex-shrink:0">' + av + '</div>' +
        '<div style="flex:1;min-width:0">' +
          '<div style="font-weight:700;font-size:13px;display:flex;gap:4px;align-items:center;flex-wrap:wrap">' + dot + esc(u.username) + '</div>' +
        '</div>';
      row.onclick = function(){ viewProfile(u.id); };
      c.appendChild(row);
    });
  }, 350);
}

/* ============================================================
   ЧУЖОЙ ПРОФИЛЬ
   ============================================================ */
async function viewProfile(userId){
  if(!userId) return;
  var res = await api('/user/' + userId);
  if(!res.ok) return;
  var u = res.data;

  var av = document.getElementById('viewAvatar');
  var pos = parsePos(u.avatar_pos);
  var avSrc = u.gif_avatar || u.avatar;
  if(avSrc){
    av.innerHTML = '<img src="' + avSrc + '" style="width:100%;height:100%;object-fit:cover;object-position:' + pos.x + '% ' + pos.y + '%">';
  } else {
    av.textContent = u.username.charAt(0).toUpperCase();
  }
  applyFrame(av, u.active_frame);

  var b = document.getElementById('viewBanner');
  var oi = b.querySelector('img');
  if(oi) oi.remove();
  var bsrc = u.gif_banner || u.banner;
  if(bsrc){
    var img = document.createElement('img');
    var bp = parsePos(u.banner_pos);
    img.src = bsrc;
    img.style.width = '100%';
    img.style.height = '100%';
    img.style.objectFit = 'cover';
    img.style.objectPosition = bp.x + '% ' + bp.y + '%';
    b.insertBefore(img, b.firstChild);
  }

  document.getElementById('viewName').textContent = u.username;
  var vn = document.getElementById('viewName');
  if(u.nickname_gradient){
    vn.style.background = u.nickname_gradient;
    vn.style.webkitBackgroundClip = 'text';
    vn.style.webkitTextFillColor = 'transparent';
  } else if(u.nickname_color){
    vn.style.color = u.nickname_color;
  }

  document.getElementById('viewStats').textContent = '📨 ' + (u.messages_count || 0) + ' · Ур. ' + (u.level || 1);
  document.getElementById('viewRating').textContent = '⭐ Соц.рейтинг: ' + (u.social_rating || 0);

  var badges = '';
  if(u.role === 'owner') badges += '<span class="role-badge role-owner">Владелец</span>';
  else if(u.is_admin) badges += '<span class="role-badge role-admin">Админ</span>';
  else if(u.is_moderator) badges += '<span class="role-badge role-mod">Модер</span>';
  if(u.is_scam) badges += '<span class="role-badge role-scam">SCAM</span>';
  if(u.is_premium) badges += '<span class="premium-badge">💎 PREMIUM</span>';
  if(u.title) badges += '<span class="title-badge">' + esc(u.title) + '</span>';
  document.getElementById('viewBadges').innerHTML = badges;

  var info = '';
  if(u.custom_status) info += '<div style="padding:10px 0;border-bottom:1px solid var(--border);font-size:13px">💭 ' + esc(u.custom_status) + '</div>';
  if(u.bio) info += '<div style="padding:10px 0;border-bottom:1px solid var(--border);font-size:13px"><b>Bio:</b> ' + esc(u.bio) + '</div>';
  if(u.fav_music) info += '<div style="padding:10px 0;border-bottom:1px solid var(--border);font-size:13px">🎵 ' + esc(u.fav_music) + '</div>';
  if(u.reputation !== undefined) info += '<div style="padding:10px 0;border-bottom:1px solid var(--border);font-size:13px">👍 Репутация: ' + u.reputation + '</div>';
  document.getElementById('viewInfo').innerHTML = info;

  var actions = document.getElementById('viewActions');
  actions.innerHTML = '';

  if(userId !== me.id){
    var mb = document.createElement('button');
    mb.className = 'save-btn green';
    mb.style.cssText = 'flex:1;min-width:100px';
    mb.textContent = '💬 Написать';
    mb.onclick = function(){
      document.getElementById('viewProfileModal').classList.remove('open');
      if(typeof openDM === 'function') openDM(userId, u.username, u.avatar);
    };
    actions.appendChild(mb);

    var rpBtn = document.createElement('button');
    rpBtn.className = 'save-btn gold';
    rpBtn.style.cssText = 'flex:1;min-width:100px';
    rpBtn.textContent = '👍 +Репа';
    rpBtn.onclick = function(){ giveRep(userId); };
    actions.appendChild(rpBtn);

    var rb = document.createElement('button');
    rb.className = 'save-btn red';
    rb.style.cssText = 'flex:1;min-width:100px';
    rb.textContent = '⚠️ Жалоба';
    rb.onclick = function(){
      var t = prompt('Причина:');
      if(!t) return;
      api('/reports/submit', {method:'POST', body:{token:token, target_id:userId, text:t}}).then(function(r){
        if(r.ok) showNotice('✅ Жалоба отправлена');
      });
    };
    actions.appendChild(rb);

    var blk = document.createElement('button');
    blk.className = 'save-btn gray';
    blk.style.cssText = 'flex:1;min-width:100px';
    blk.textContent = '🚫 Блок';
    blk.onclick = function(){ blockUser(userId); };
    actions.appendChild(blk);
  }

  document.getElementById('viewProfileModal').classList.add('open');
}

async function giveRep(userId){
  var res = await api('/rep/give', {method:'POST', body:{token:token, user_id:userId}});
  if(res.ok) showNotice('👍 +1');
  else showNotice('❌ ' + res.error, 'error');
}

async function blockUser(userId){
  if(!confirm('Заблокировать?')) return;
  var res = await api('/blocks/add', {method:'POST', body:{token:token, user_id:userId}});
  if(res.ok){
    showNotice('🚫');
    document.getElementById('viewProfileModal').classList.remove('open');
  }
}

/* ============================================================
   СОХРАНЁННЫЕ И ПОИСК ПО СООБЩЕНИЯМ
   ============================================================ */
async function openSavedMessages(){
  document.getElementById('savedMessagesModal').classList.add('open');
  var c = document.getElementById('savedMessagesList');
  c.innerHTML = '<div style="text-align:center;padding:20px">Загрузка...</div>';
  var res = await api('/messages/saved?token=' + encodeURIComponent(token));
  if(!res.ok || !res.data.length){
    c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:20px">Пусто</div>';
    return;
  }
  c.innerHTML = res.data.map(function(m){
    return '<div style="padding:10px;background:var(--bg-input);border-radius:10px;margin-bottom:6px">' +
      '<div style="font-weight:800;font-size:12px;color:var(--accent)">' + esc(m.username) + ' · ' + timeAgo(m.created_at) + '</div>' +
      '<div style="font-size:13px;margin-top:4px">' + esc(m.text || '') + '</div>' +
    '</div>';
  }).join('');
}

var _msgSearchTimer = null;
function openMsgSearch(){
  document.getElementById('msgSearchModal').classList.add('open');
  document.getElementById('msgSearchInput').value = '';
  document.getElementById('msgSearchResults').innerHTML = '';
}

function doMsgSearch(q){
  clearTimeout(_msgSearchTimer);
  var c = document.getElementById('msgSearchResults');
  if(q.trim().length < 2){ c.innerHTML = ''; return; }
  c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:20px">Поиск...</div>';
  _msgSearchTimer = setTimeout(async function(){
    var ch = (typeof currentChannelId !== 'undefined' && currentChannelId) || 0;
    var res = await api('/messages/search?q=' + encodeURIComponent(q) + '&channel_id=' + ch + '&token=' + encodeURIComponent(token));
    if(!res.ok || !res.data.length){
      c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:20px">Ничего</div>';
      return;
    }
    c.innerHTML = res.data.slice(0, 50).map(function(m){
      return '<div style="padding:10px;background:var(--bg-input);border-radius:10px;margin-bottom:6px;cursor:pointer">' +
        '<div style="font-weight:800;font-size:12px;color:var(--accent)">' + esc(m.username) + ' · ' + timeAgo(m.created_at) + '</div>' +
        '<div style="font-size:13px;margin-top:4px">' + esc(m.text || '') + '</div>' +
      '</div>';
    }).join('');
  }, 350);
}

/* ============================================================
   ИНИЦИАЛИЗАЦИЯ
   ============================================================ */
document.addEventListener('user-entered', function(){
  renderStartMenu();
  renderDesktopIcons();
  renderProfile();
  loadAchievementsCatalog();
  applyChatSkin();

  // Кнопки в интерфейсе
  var chatSearchBtn = document.getElementById('chatSearchBtn');
  if(chatSearchBtn) chatSearchBtn.onclick = openMsgSearch;
  var chatExportBtn = document.getElementById('chatExportBtn');
  if(chatExportBtn) chatExportBtn.onclick = function(){
    if(typeof exportChat === 'function') exportChat();
  };
  var chatListSearchBtn = document.getElementById('chatListSearchBtn');
  if(chatListSearchBtn) chatListSearchBtn.onclick = openMsgSearch;

  // Кнопки форматирования
  document.querySelectorAll('.format-btn').forEach(function(btn){
    btn.onclick = function(){
      var marker = btn.getAttribute('data-format');
      var inp = document.getElementById('inp');
      if(!inp || !marker) return;
      var s = inp.selectionStart, e = inp.selectionEnd, t = inp.value;
      if(s === e){
        inp.value = t.slice(0, s) + marker + marker + t.slice(e);
        inp.selectionStart = inp.selectionEnd = s + marker.length;
      } else {
        inp.value = t.slice(0, s) + marker + t.slice(s, e) + marker + t.slice(e);
        inp.selectionStart = s + marker.length;
        inp.selectionEnd = e + marker.length;
      }
      inp.focus();
    };
  });

  // Reply bar close
  var rbc = document.getElementById('replyBarClose');
  if(rbc) rbc.onclick = function(){
    var rb = document.getElementById('replyBar');
    if(rb) rb.classList.remove('show');
    if(typeof cancelReply === 'function') cancelReply();
  };

  // Логотип — 5 тапов на радужную тему
  var logo = document.getElementById('loginAvatar');
  if(logo){
    var logoClicks = 0, logoTimer = null;
    logo.onclick = function(){
      logoClicks++;
      clearTimeout(logoTimer);
      logoTimer = setTimeout(function(){ logoClicks = 0; }, 1000);
      if(logoClicks >= 5){
        logoClicks = 0;
        showNotice('🌈 Секретная тема!', 'warn');
        setTheme('rainbow');
      }
    };
  }
});

// Экспорт глобально
window.closeProfile = closeProfile;
window.openProfile = openProfile;
window.saveProfile = saveProfile;
window.openStatusMenu = openStatusMenu;
window.setOnlineStatus = setOnlineStatus;
window.saveCustomStatus = saveCustomStatus;
window.openNickStyle = openNickStyle;
window.pickNickColor = pickNickColor;
window.pickNickGradient = pickNickGradient;
window.saveNickStyle = saveNickStyle;
window.resetNickStyle = resetNickStyle;
window.openEmailVerify = openEmailVerify;
window.closeEmailVerify = closeEmailVerify;
window.sendEmailCode = sendEmailCode;
window.verifyEmailCode = verifyEmailCode;
window.resendEmailCode = resendEmailCode;
window.showChangelog = showChangelog;
window.openLanguage = openLanguage;
window.setLang = setLang;
window.openSettings = openSettings;
window.showSettingsTab = showSettingsTab;
window.applyCustomThemeById = applyCustomThemeById;
window.setFont = setFont;
window.toggleCompact = toggleCompact;
window.uploadWallpaper = uploadWallpaper;
window.clearWallpaper = clearWallpaper;
window.unblockUser = unblockUser;
window.openAchievements = openAchievements;
window.openLeaders = openLeaders;
window.openLevels = openLevels;
window.openPremium = openPremium;
window.buyPremium = buyPremium;
window.openFrames = openFrames;
window.frameAction = frameAction;
window.openTitles = openTitles;
window.setTitle = setTitle;
window.openChatSkins = openChatSkins;
window.selectChatSkin = selectChatSkin;
window.openMsgEffects = openMsgEffects;
window.selectMsgEffect = selectMsgEffect;
window.openCommands = openCommands;
window.filterCommands = filterCommands;
window.useCommand = useCommand;
window.openUserSearch = openUserSearch;
window.doUserSearch = doUserSearch;
window.viewProfile = viewProfile;
window.giveRep = giveRep;
window.blockUser = blockUser;
window.openSavedMessages = openSavedMessages;
window.openMsgSearch = openMsgSearch;
window.doMsgSearch = doMsgSearch;

console.log('[BC] features/core loaded');
