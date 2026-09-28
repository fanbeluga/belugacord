/* ============================================================
   BELUGACORD 2.5 — MODULE: ADMIN (part 1/2)
   БОГ-меню, логины, статистика
   ============================================================ */

var adminVerified = false;
var ownerVerified = false;
var _usersCache = [];
var _promoCache = [];
var _selectedUsers = {};

/* ============================================================
   ЛОГИН ВЛАДЕЛЬЦА
   ============================================================ */
function openOwnerGui(){
  if(BC.isOwner){
    // Если уже владелец — сразу ГУИ без пароля, если уже проверяли
    if(ownerVerified){
      document.getElementById('ownerGuiModal').classList.add('open');
      loadOwnerStats();
      showOwnerSec('users');
      return;
    }
  }
  document.getElementById('ownerLoginModal').classList.add('open');
}

async function verifyOwner(){
  var p = document.getElementById('ownerPassword').value;
  var res = await api('/owner/verify', {method:'POST', body:{token:token, password:p}});
  if(!res.ok){
    document.getElementById('ownerError').textContent = res.error;
    return;
  }
  ownerVerified = true;
  document.getElementById('ownerLoginModal').classList.remove('open');
  document.getElementById('ownerGuiModal').classList.add('open');
  loadOwnerStats();
  showOwnerSec('users');
}

async function loadOwnerStats(){
  var res = await api('/owner/stats?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var s = res.data;
  var el = document.getElementById('ownerStats');
  el.innerHTML =
    statCard(s.users || 0, 'ЮЗЕРОВ', 'var(--accent)') +
    statCard(s.online || 0, 'ОНЛАЙН', '#22d3ee') +
    statCard(s.messages || 0, 'СООБЩ', 'var(--accent)') +
    statCard(s.coins || 0, '🏅', '#ffd700') +
    statCard(s.nfts || 0, 'NFT', '#8b5cf6') +
    statCard(s.gifts || 0, '🎀', '#ec4899') +
    statCard(s.groups || 0, 'ГРУПП', '#22c55e');
}
function statCard(value, label, color){
  return '<div style="background:var(--bg-input);border-radius:10px;padding:8px;text-align:center">' +
    '<div style="color:' + color + ';font-size:18px;font-weight:900">' + value + '</div>' +
    '<div style="color:var(--text-mute);font-size:9px">' + label + '</div>' +
  '</div>';
}

/* ============================================================
   БОГ-ГУИ — СЕКЦИИ
   ============================================================ */
function showOwnerSec(sec, ev){
  if(ev){
    var p = ev.target.parentNode;
    if(p) p.querySelectorAll('.shop-tab-btn').forEach(function(b){ b.classList.remove('active'); });
    ev.target.classList.add('active');
  }
  var b = document.getElementById('ownerBody');
  var cards = [];

  if(sec === 'users'){
    cards = [
      ['📋', 'Список юзеров', 'openUsersList'],
      ['🎁', 'Промо-панель', 'openPromoPanel'],
      ['👁️', 'Читать чат', 'ownerReadChat'],
      ['✍️', 'Писать от лица', 'ownerWriteAs'],
      ['✏️', 'Сменить ник', 'ownerChangeNick'],
      ['📧', 'Сбросить пароль', 'ownerResetPass'],
      ['🔨', 'Мут', 'ownerMute'],
      ['🗑️', 'Удалить все', 'ownerDeleteAll'],
      ['🏅', 'Легенда', 'ownerLegend'],
      ['✏️', 'Масс. переим.', 'ownerMassRename'],
      ['🚪', 'Force logout', 'ownerForceLogout'],
      ['🎥', 'Стример вкл/выкл', 'ownerToggleStreamer'],
      ['🎭', 'SCAM вкл/выкл', 'ownerToggleScam']
    ];
  }
  else if(sec === 'economy'){
    cards = [
      ['🏅', 'Выдать бекоины', 'ownerGiveCoins'],
      ['💸', 'Забрать', 'ownerTakeCoins'],
      ['🎁', 'Раздать всем', 'ownerGiveAll'],
      ['💰', 'Заявки', 'ownerCoinRequests'],
      ['💎', 'Premium', 'ownerGivePremium'],
      ['🧪', 'Бета', 'ownerToggleBeta'],
      ['👑', 'Админка+', 'ownerGrantAdmin'],
      ['🎭', 'Админка-', 'ownerRevokeAdmin']
    ];
  }
  else if(sec === 'nft'){ cards = [['➕', 'Создать NFT', 'openNftCreate'], ['📋', 'Список NFT', 'ownerListNfts']]; }
  else if(sec === 'gifts'){ cards = [['➕', 'Создать подарок', 'openGiftCreate'], ['📋', 'Список', 'ownerListGifts']]; }
  else if(sec === 'cases'){ cards = [['➕', 'Создать кейс', 'openCaseCreate'], ['📋', 'Список', 'ownerListCases']]; }
  else if(sec === 'bp'){ cards = [['🏆', 'Редактор БП', 'openBpEditor']]; }
  else if(sec === 'events'){ cards = [['🎉', 'Создать ивент', 'openCreateEvent'], ['📋', 'Активные', 'listEvents']]; }
  else if(sec === 'abuse'){
    cards = [
      ['👥', 'Список онлайн', 'abuseShowOnline'],
      ['🎁', 'Рандом подарок', 'abuseRandomGift'],
      ['🎨', 'Рандом NFT', 'abuseRandomNft'],
      ['🏅', 'Рандом бекоины', 'abuseRandomCoins'],
      ['🤝', 'Кооп', 'openCoopModal'],
      ['📢', 'Анонс', 'ownerAnnounce']
    ];
  }
  else if(sec === 'troll'){
    cards = [
      ['😈', 'Troll-меню', 'openTrollMenu'],
      ['🌩️', 'Шторм', 'ownerStorm'],
      ['🎊', 'Конфетти', 'ownerEvent_confetti'],
      ['🎈', 'Шарики', 'ownerEvent_balloons'],
      ['🐱', 'Кошачий', 'ownerEvent_cat_mode'],
      ['💣', 'Кнопка судьбы', 'ownerSuddness'],
      ['💀', 'Самоуничтожение', 'ownerSelfDestruct'],
      ['✏️', 'Масс. цвет ника', 'ownerMassColor']
    ];
  }
  else if(sec === 'releases'){ cards = [['🚀', 'Релизы', 'openReleasesPanel']]; }
  else if(sec === 'system'){
    cards = [
      ['🔄', 'Очистка БД', 'ownerCleanDB'],
      ['📊', 'Бэкап', 'ownerBackup']
    ];
  }

  b.innerHTML = '<div class="owner-section-grid">' + cards.map(function(c){
    return '<div class="owner-card" data-fn="' + c[2] + '"><span class="oc-icon">' + c[0] + '</span><div class="oc-name">' + c[1] + '</div></div>';
  }).join('') + '</div>';

  // ВАЖНО: используем addEventListener, а не onclick из строки
  b.querySelectorAll('.owner-card').forEach(function(card){
    card.addEventListener('click', function(){
      var fn = card.getAttribute('data-fn');
      if(typeof window[fn] === 'function'){
        try { window[fn](); }
        catch(e){ showNotice('❌ ' + e.message, 'error'); console.error(e); }
      } else {
        showNotice('❌ Функция не найдена: ' + fn, 'error');
      }
    });
  });
}

/* ============================================================
   ДЕЙСТВИЯ ЮЗЕРОВ (используются в owner GUI)
   ============================================================ */
function ownerGetUser(cb){
  var u = prompt('Ник:');
  if(!u) return;
  cb(u.trim());
}

async function ownerReadChat(){
  ownerGetUser(async function(u){
    var res = await api('/owner/read_chat', {method:'POST', body:{token:token, username:u}});
    if(res.ok){
      var msg = (res.data.messages || []).slice(0, 30).map(function(m){ return m.from + ': ' + m.text; }).join('\n');
      alert(msg || 'Пусто');
    } else alert('Ошибка: ' + res.error);
  });
}

function ownerWriteAs(){
  ownerGetUser(async function(u){
    var t = prompt('Текст:');
    if(!t) return;
    var res = await api('/owner/write_as', {method:'POST', body:{token:token, username:u, text:t}});
    if(res.ok) showNotice('✍️');
  });
}

function ownerChangeNick(){
  ownerGetUser(async function(u){
    var n = prompt('Новый ник:');
    if(!n) return;
    var res = await api('/owner/change_nick', {method:'POST', body:{token:token, username:u, new_nick:n}});
    if(res.ok) showNotice('✏️');
  });
}

function ownerResetPass(){
  ownerGetUser(async function(u){
    if(!confirm('Сбросить?')) return;
    var res = await api('/owner/reset_pass', {method:'POST', body:{token:token, username:u}});
    if(res.ok && res.data.new_password) alert('Новый пароль: ' + res.data.new_password);
  });
}

function ownerMute(){
  ownerGetUser(async function(u){
    var m = prompt('Минут:', '60');
    if(!m) return;
    var res = await api('/owner/mute', {method:'POST', body:{token:token, username:u, minutes:parseInt(m)}});
    if(res.ok) showNotice('🔇');
  });
}

function ownerDeleteAll(){
  ownerGetUser(async function(u){
    if(!confirm('Удалить сообщения ' + u + '?')) return;
    var res = await api('/owner/delete_all_msgs', {method:'POST', body:{token:token, username:u}});
    if(res.ok) showNotice('🗑️');
  });
}

function ownerLegend(){
  ownerGetUser(async function(u){
    var res = await api('/owner/legend', {method:'POST', body:{token:token, username:u}});
    if(res.ok) showNotice('🏅');
  });
}

function ownerMassRename(){
  var pre = prompt('Префикс:', '') || '';
  var suf = prompt('Суффикс:', '') || '';
  if(!pre && !suf) return;
  if(!confirm('Переименовать всех?')) return;
  api('/owner/mass_rename', {method:'POST', body:{token:token, prefix:pre, suffix:suf}}).then(function(res){
    if(res.ok) showNotice('✏️ ' + res.data.count);
  });
}

function ownerForceLogout(){
  ownerGetUser(async function(u){
    var sr = await api('/users/search?q=' + encodeURIComponent(u) + '&token=' + encodeURIComponent(token));
    if(!sr.ok || !sr.data.length) return;
    var res = await api('/owner/force_logout', {method:'POST', body:{token:token, user_id:sr.data[0].id}});
    if(res.ok) showNotice('🚪');
  });
}

function ownerToggleStreamer(){
  ownerGetUser(async function(u){
    var res = await api('/owner/toggle_streamer', {method:'POST', body:{token:token, username:u}});
    if(res.ok) showNotice(res.data.is_streamer ? '🎥 Вкл' : '❌ Выкл');
  });
}

function ownerToggleScam(){
  ownerGetUser(async function(u){
    var res = await api('/owner/toggle_scam', {method:'POST', body:{token:token, username:u}});
    if(res.ok) showNotice(res.data.is_scam ? '🎭 SCAM выдан' : '❌ SCAM снят');
  });
}

/* ============================================================
   ЭКОНОМИКА ВЛАДЕЛЬЦА
   ============================================================ */
function ownerGiveCoins(){
  ownerGetUser(function(u){
    var a = parseInt(prompt('Сколько?', '100'));
    if(!a) return;
    api('/owner/give_coins', {method:'POST', body:{token:token, username:u, amount:a}}).then(function(res){
      if(res.ok) showNotice('🏅 +' + a);
    });
  });
}
function ownerTakeCoins(){
  ownerGetUser(function(u){
    var a = parseInt(prompt('Забрать?', '100'));
    if(!a) return;
    api('/owner/take_coins', {method:'POST', body:{token:token, username:u, amount:a}}).then(function(res){
      if(res.ok) showNotice('💸');
    });
  });
}
function ownerGiveAll(){
  var a = parseInt(prompt('Всем?', '10'));
  if(!a) return;
  if(!confirm('Раздать ' + a + '?')) return;
  api('/owner/give_all', {method:'POST', body:{token:token, amount:a}}).then(function(res){
    if(res.ok) showNotice('🎁');
  });
}
function ownerCoinRequests(){
  api('/admin/coin_requests?token=' + encodeURIComponent(token)).then(function(res){
    if(!res.ok || !res.data.length) return alert('Нет');
    var msg = res.data.map(function(r){ return r.username + ': ' + r.coins + ' (id:' + r.id + ')'; }).join('\n');
    var id = prompt('Заявки:\n' + msg + '\n\nID:');
    if(!id) return;
    api('/admin/coin_resolve', {method:'POST', body:{token:token, request_id:parseInt(id), action:'approve'}}).then(function(){
      showNotice('✅');
    });
  });
}
function ownerGivePremium(){
  ownerGetUser(function(u){
    var t = prompt('premium/pro:', 'premium');
    if(!t) return;
    api('/owner/give_premium', {method:'POST', body:{token:token, username:u, tier:t}}).then(function(res){
      if(res.ok) showNotice('💎');
    });
  });
}
function ownerToggleBeta(){
  ownerGetUser(function(u){
    api('/owner/toggle_beta', {method:'POST', body:{token:token, username:u}}).then(function(res){
      if(res.ok) showNotice('🧪');
    });
  });
}
function ownerGrantAdmin(){
  ownerGetUser(function(u){
    api('/owner/grant_admin', {method:'POST', body:{token:token, username:u}}).then(function(res){
      if(res.ok) showNotice('👑');
    });
  });
}
function ownerRevokeAdmin(){
  ownerGetUser(function(u){
    api('/owner/revoke_admin', {method:'POST', body:{token:token, username:u}}).then(function(res){
      if(res.ok) showNotice('🎭');
    });
  });
}

/* ============================================================
   ТРОЛЛЬ-ФУНКЦИИ
   ============================================================ */
function openTrollMenu(){
  var uname = prompt('Ник:');
  if(!uname) return;
  var kind = prompt('Что: shake / flip / invert / rain', 'shake');
  if(!kind) return;
  var dur = parseInt(prompt('Секунд:', '10')) || 10;
  api('/users/search?q=' + encodeURIComponent(uname) + '&token=' + encodeURIComponent(token)).then(function(sr){
    if(!sr.ok || !sr.data.length){ showNotice('❌ Не найден', 'error'); return; }
    api('/owner/troll_user', {method:'POST', body:{token:token, user_id:sr.data[0].id, kind:kind, duration:dur}}).then(function(res){
      if(res.ok) showNotice('😈');
    });
  });
}
function ownerStorm(){
  var d = parseInt(prompt('Секунд:', '30')) || 30;
  api('/owner/storm', {method:'POST', body:{token:token, duration:d}}).then(function(res){
    if(res.ok) showNotice('🌩️');
  });
}
function ownerEvent_confetti(){
  api('/owner/troll', {method:'POST', body:{token:token, troll:'confetti'}}).then(function(res){
    if(res.ok){ showNotice('🎊'); BC.showConfetti(); }
  });
}
function ownerEvent_balloons(){
  api('/owner/troll', {method:'POST', body:{token:token, troll:'balloons'}}).then(function(res){
    if(res.ok){ showNotice('🎈'); BC.showBalloons(); }
  });
}
function ownerEvent_cat_mode(){
  api('/owner/troll', {method:'POST', body:{token:token, troll:'cat_mode'}}).then(function(res){
    if(res.ok) showNotice('🐱');
  });
}
function ownerSuddness(){
  if(!confirm('💣?')) return;
  api('/owner/suddness', {method:'POST', body:{token:token}}).then(function(res){
    if(res.ok) showNotice('💣 ' + res.data.event);
  });
}
function ownerMassColor(){
  var c = prompt('Цвет (hex):', '#ff00ff');
  if(!c) return;
  if(!confirm('Покрасить всех?')) return;
  api('/owner/mass_color', {method:'POST', body:{token:token, color:c}}).then(function(res){
    if(res.ok) showNotice('🎨');
  });
}
function ownerSelfDestruct(){
  if(!currentChannelId){ alert('Открой канал'); return; }
  if(!confirm('💀 УДАЛИТЬ ВСЕ СООБЩЕНИЯ КАНАЛА?')) return;
  api('/owner/self_destruct', {method:'POST', body:{token:token, channel_id:currentChannelId}}).then(function(res){
    if(res.ok){
      document.getElementById('messagesInner').innerHTML = '';
      showNotice('💀');
    }
  });
}
function ownerAnnounce(){
  var t = prompt('Текст:');
  if(!t) return;
  api('/owner/announce', {method:'POST', body:{token:token, text:t}}).then(function(res){
    if(res.ok) showNotice('📢');
  });
}

/* ============================================================
   СИСТЕМА
   ============================================================ */
function ownerCleanDB(){
  if(!confirm('Очистить старые сообщения (>30 дней)?')) return;
  api('/owner/clean_db', {method:'POST', body:{token:token}}).then(function(res){
    if(res.ok) showNotice('🔄');
  });
}
async function ownerBackup(){
  try {
    var r = await fetch('/api/owner/backup?token=' + encodeURIComponent(token));
    if(!r.ok) throw new Error();
    var b = await r.blob();
    var url = URL.createObjectURL(b);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'belugacord_backup_' + Date.now() + '.json';
    a.click();
    showNotice('📊 Скачан');
  } catch(e){ showNotice('❌', 'error'); }
}

/* ============================================================
   АДМИН-ПАНЕЛЬ
   ============================================================ */
function openAdminLogin(){
  document.getElementById('adminLoginModal').classList.add('open');
}
function openAdminPassSetup(){
  document.getElementById('adminLoginModal').classList.remove('open');
  document.getElementById('adminPassSetupModal').classList.add('open');
}
async function saveAdminPassword(){
  var p1 = document.getElementById('newAdminPass').value;
  var p2 = document.getElementById('newAdminPass2').value;
  if(p1.length < 4){ showNotice('⚠️ Мин 4', 'warn'); return; }
  if(p1 !== p2){ showNotice('⚠️ Не совпадают', 'warn'); return; }
  var res = await api('/admin/set_password', {method:'POST', body:{token:token, password:p1}});
  if(res.ok){
    showNotice('✅ Установлен');
    setTimeout(function(){ document.getElementById('adminPassSetupModal').classList.remove('open'); }, 1000);
  }
}
async function verifyAdmin(){
  var p = document.getElementById('adminPassword').value;
  var res = await api('/admin/verify', {method:'POST', body:{token:token, password:p}});
  if(!res.ok){
    document.getElementById('adminError').textContent = res.error;
    return;
  }
  adminVerified = true;
  document.getElementById('adminLoginModal').classList.remove('open');
  document.getElementById('adminModal').classList.add('open');
  loadAdminStats();
  showAdminTab('users');
}
async function loadAdminStats(){
  var res = await api('/admin/stats?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var s = res.data;
  var el = document.getElementById('adminStats');
  el.innerHTML =
    statCard(s.users || 0, 'ЮЗЕРОВ', 'var(--accent)') +
    statCard(s.servers || 0, 'СЕРВЕРОВ', 'var(--accent)') +
    statCard(s.messages || 0, 'СООБЩ', 'var(--accent)') +
    statCard(s.online || 0, 'ОНЛАЙН', '#22d3ee');
}
async function showAdminTab(tab, btn){
  document.querySelectorAll('.admin-tab').forEach(function(t){ t.classList.remove('active'); });
  if(btn) btn.classList.add('active');
  if(tab === 'reports') return renderAdminReports();
  if(tab === 'logs') return renderAdminLogs();
  return renderAdminUsers();
}
async function renderAdminUsers(){
  var res = await api('/admin/users?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var body = document.getElementById('adminBody');
  body.innerHTML = '';
  res.data.forEach(function(u){
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:10px;padding:12px;border-radius:10px;margin-bottom:6px;background:var(--bg-input);flex-wrap:wrap';
    var badges = '';
    if(u.is_admin) badges += '<span class="role-badge role-admin">Админ</span>';
    else if(u.is_moderator) badges += '<span class="role-badge role-mod">Модер</span>';
    else if(u.is_beta_tester) badges += '<span class="role-badge role-beta">Бета</span>';
    else badges += '<span class="role-badge role-user">Юзер</span>';
    if(u.is_banned) badges += '<span style="background:#f43f5e;color:#fff;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:800">BAN</span>';
    if(u.is_scam) badges += '<span class="role-badge role-scam">SCAM</span>';

    var actions = '';
    if(adminVerified && BC.isOwner){
      actions = u.is_banned
        ? '<button class="save-btn green" style="margin:0;width:auto;padding:6px 10px;font-size:11px" onclick="adminAction(' + u.id + ',\'unban\')">Разбан</button>'
        : '<button class="save-btn red" style="margin:0;width:auto;padding:6px 10px;font-size:11px" onclick="adminBan(' + u.id + ')">Бан</button>';
    }
    row.innerHTML =
      '<div style="font-weight:800;min-width:120px">' + esc(u.username) + '</div>' +
      '<div style="display:flex;gap:4px;flex-wrap:wrap;flex:1">' + badges + '</div>' +
      '<div>' + actions + '</div>';
    body.appendChild(row);
  });
}
async function adminBan(id){
  var r = prompt('Причина:', '') || '';
  var res = await api('/admin/action', {method:'POST', body:{token:token, target_id:id, action:'ban', reason:r}});
  if(res.ok) showAdminTab('users');
}
async function adminAction(id, action){
  var res = await api('/admin/action', {method:'POST', body:{token:token, target_id:id, action:action}});
  if(res.ok) showAdminTab('users');
}
async function renderAdminReports(){
  var b = document.getElementById('adminBody');
  b.innerHTML = '<div style="text-align:center;padding:40px">Загрузка...</div>';
  var res = await api('/admin/reports?token=' + encodeURIComponent(token));
  if(!res.ok || !res.data.length){
    b.innerHTML = '<div style="color:var(--text-mute);text-align:center;padding:40px">Нет жалоб</div>';
    return;
  }
  b.innerHTML = res.data.map(function(rep){
    return '<div style="padding:14px;border-radius:12px;margin-bottom:10px;background:var(--bg-input)">' +
      '<div style="font-weight:800">👤 ' + esc(rep.target_username || '?') + '</div>' +
      '<div style="font-size:13px;background:rgba(0,0,0,0.2);padding:10px;border-radius:8px;margin-top:6px">' + esc(rep.text) + '</div>' +
    '</div>';
  }).join('');
}
async function renderAdminLogs(){
  var b = document.getElementById('adminBody');
  b.innerHTML = '<div style="text-align:center;padding:40px">Загрузка...</div>';
  var res = await api('/admin/logs?token=' + encodeURIComponent(token));
  if(!res.ok || !res.data.length){
    b.innerHTML = '<div style="color:var(--text-mute);text-align:center;padding:40px">Пусто</div>';
    return;
  }
  b.innerHTML = res.data.map(function(l){
    return '<div style="padding:10px;border-radius:8px;background:var(--bg-input);margin-bottom:6px;font-size:12px">' +
      '<div style="color:var(--text-mute);font-size:10px">' + new Date(l.created_at).toLocaleString('ru-RU') + ' — ' + esc(l.admin_name || '?') + '</div>' +
      '<div>' + esc(l.action) + '</div>' +
    '</div>';
  }).join('');
}

/* ============================================================
   ЭКСПОРТ
   ============================================================ */
window.openOwnerGui = openOwnerGui;
window.verifyOwner = verifyOwner;
window.showOwnerSec = showOwnerSec;
window.openUsersList = openUsersList;
window.openPromoPanel = openPromoPanel;
window.openAdminLogin = openAdminLogin;
window.openAdminPassSetup = openAdminPassSetup;
window.saveAdminPassword = saveAdminPassword;
window.verifyAdmin = verifyAdmin;
window.showAdminTab = showAdminTab;
window.adminBan = adminBan;
window.adminAction = adminAction;

// Owner actions
window.ownerReadChat = ownerReadChat;
window.ownerWriteAs = ownerWriteAs;
window.ownerChangeNick = ownerChangeNick;
window.ownerResetPass = ownerResetPass;
window.ownerMute = ownerMute;
window.ownerDeleteAll = ownerDeleteAll;
window.ownerLegend = ownerLegend;
window.ownerMassRename = ownerMassRename;
window.ownerForceLogout = ownerForceLogout;
window.ownerToggleStreamer = ownerToggleStreamer;
window.ownerToggleScam = ownerToggleScam;
window.ownerGiveCoins = ownerGiveCoins;
window.ownerTakeCoins = ownerTakeCoins;
window.ownerGiveAll = ownerGiveAll;
window.ownerCoinRequests = ownerCoinRequests;
window.ownerGivePremium = ownerGivePremium;
window.ownerToggleBeta = ownerToggleBeta;
window.ownerGrantAdmin = ownerGrantAdmin;
window.ownerRevokeAdmin = ownerRevokeAdmin;
window.openTrollMenu = openTrollMenu;
window.ownerStorm = ownerStorm;
window.ownerEvent_confetti = ownerEvent_confetti;
window.ownerEvent_balloons = ownerEvent_balloons;
window.ownerEvent_cat_mode = ownerEvent_cat_mode;
window.ownerSuddness = ownerSuddness;
window.ownerMassColor = ownerMassColor;
window.ownerSelfDestruct = ownerSelfDestruct;
window.ownerAnnounce = ownerAnnounce;
window.ownerCleanDB = ownerCleanDB;
window.ownerBackup = ownerBackup;

/* ============================================================
   СПИСОК ЮЗЕРОВ (полный)
   ============================================================ */
async function openUsersList(){
  document.getElementById('usersListModal').classList.add('open');
  document.getElementById('usersListBody').innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">Загрузка...</div>';
  var res = await api('/owner/users_full?token=' + encodeURIComponent(token));
  if(!res.ok){
    document.getElementById('usersListBody').innerHTML = '<div style="text-align:center;color:#f43f5e;padding:40px">Ошибка: ' + res.error + '</div>';
    return;
  }
  _usersCache = res.data;
  _selectedUsers = {};
  document.getElementById('usersListCount').textContent = 'Всего: ' + _usersCache.length;
  filterUsersList();
}

function filterUsersList(){
  var q = (document.getElementById('usersSearchInput').value || '').toLowerCase().trim();
  var filter = document.getElementById('usersFilterSelect').value;

  var filtered = _usersCache.filter(function(u){
    // Поиск
    if(q){
      var inName = (u.username || '').toLowerCase().indexOf(q) !== -1;
      var inEmail = (u.email || '').toLowerCase().indexOf(q) !== -1;
      if(!inName && !inEmail) return false;
    }
    // Фильтры
    if(filter === 'online' && !u.online) return false;
    if(filter === 'banned' && !u.is_banned) return false;
    if(filter === 'scam' && !u.is_scam) return false;
    if(filter === 'premium' && !u.is_premium) return false;
    if(filter === 'promo' && !u.referred_by) return false;
    return true;
  });

  renderUsersTable(filtered);
  updateSelectedCount();
}

function renderUsersTable(users){
  var c = document.getElementById('usersListBody');
  if(!users.length){
    c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:40px">Никого не найдено</div>';
    return;
  }

  var html = '<div style="display:grid;grid-template-columns:36px 60px 1fr 1fr 90px 100px 80px 60px;gap:6px;padding:8px 10px;background:var(--bg-header);border-radius:10px;font-size:11px;font-weight:800;color:var(--text-mute);text-transform:uppercase;position:sticky;top:0;z-index:2">' +
    '<div><input type="checkbox" onchange="usersSelectAll(this.checked)" style="width:18px;height:18px;cursor:pointer"></div>' +
    '<div>ID</div>' +
    '<div>Ник</div>' +
    '<div>Email</div>' +
    '<div>Дата</div>' +
    '<div>Статус</div>' +
    '<div>🏅</div>' +
    '<div></div>' +
  '</div>';

  users.forEach(function(u){
    var badges = '';
    if(u.is_banned) badges += '🔨';
    if(u.is_scam) badges += '🎭';
    if(u.is_premium) badges += '💎';
    if(u.is_admin) badges += '👑';
    else if(u.is_moderator) badges += '🛡️';
    if(u.online) badges += '🟢';
    if(u.referred_by) badges += '🎁';

    var dateStr = u.created_at ? new Date(u.created_at).toLocaleDateString('ru-RU', {day:'2-digit', month:'2-digit', year:'2-digit'}) : '—';
    var checked = _selectedUsers[u.id] ? 'checked' : '';

    html += '<div style="display:grid;grid-template-columns:36px 60px 1fr 1fr 90px 100px 80px 60px;gap:6px;padding:8px 10px;background:var(--bg-input);border-radius:8px;margin-bottom:4px;font-size:12px;align-items:center" data-uid="' + u.id + '">' +
      '<div><input type="checkbox" ' + checked + ' onchange="userToggleSelect(' + u.id + ',this.checked)" style="width:18px;height:18px;cursor:pointer"></div>' +
      '<div style="color:var(--text-mute);font-family:monospace">' + u.id + '</div>' +
      '<div style="font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer" onclick="viewProfile(' + u.id + ')">' + esc(u.username) + '</div>' +
      '<div style="color:var(--text-mute);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(u.email || '—') + '</div>' +
      '<div style="color:var(--text-mute);font-size:11px">' + dateStr + '</div>' +
      '<div style="font-size:14px;letter-spacing:2px">' + badges + '</div>' +
      '<div style="color:var(--gold);font-weight:900">' + (u.coins || 0).toLocaleString('ru-RU') + '</div>' +
      '<div><button class="save-btn gray" style="margin:0;width:auto;padding:4px 8px;font-size:10px" onclick="openUserCard(' + u.id + ')">⋯</button></div>' +
    '</div>';
  });

  c.innerHTML = html;
}

function usersSelectAll(checked){
  var filter = document.getElementById('usersFilterSelect').value;
  var q = (document.getElementById('usersSearchInput').value || '').toLowerCase().trim();
  _usersCache.forEach(function(u){
    var match = true;
    if(q && (u.username || '').toLowerCase().indexOf(q) === -1 && (u.email || '').toLowerCase().indexOf(q) === -1) match = false;
    if(filter === 'online' && !u.online) match = false;
    if(filter === 'banned' && !u.is_banned) match = false;
    if(filter === 'scam' && !u.is_scam) match = false;
    if(filter === 'premium' && !u.is_premium) match = false;
    if(filter === 'promo' && !u.referred_by) match = false;
    if(match) _selectedUsers[u.id] = checked;
  });
  filterUsersList();
}

function userToggleSelect(uid, checked){
  if(checked) _selectedUsers[uid] = true;
  else delete _selectedUsers[uid];
  updateSelectedCount();
}

function updateSelectedCount(){
  var n = Object.keys(_selectedUsers).length;
  document.getElementById('usersSelectedCount').textContent = n;
  var bar = document.getElementById('usersMassActions');
  if(n > 0) bar.style.display = 'flex';
  else bar.style.display = 'none';
}

async function massAction(action){
  var ids = Object.keys(_selectedUsers).map(function(x){ return parseInt(x); });
  if(!ids.length){ showNotice('⚠️ Никого не выбрано', 'warn'); return; }

  if(action === 'clear'){
    _selectedUsers = {};
    filterUsersList();
    return;
  }

  var labels = {ban:'Забанить', unban:'Разбанить', scam:'Выдать SCAM', premium:'Выдать Premium 30д'};
  if(!confirm(labels[action] + ' ' + ids.length + ' юзеров?')) return;

  var res = await api('/owner/mass_action', {method:'POST', body:{token:token, action:action, user_ids:ids}});
  if(res.ok){
    showNotice('✅ Обновлено: ' + res.data.updated);
    _selectedUsers = {};
    openUsersList();
  } else showNotice('❌ ' + res.error, 'error');
}

function exportUsersCsv(){
  var filter = document.getElementById('usersFilterSelect').value;
  var q = (document.getElementById('usersSearchInput').value || '').toLowerCase().trim();
  var rows = _usersCache.filter(function(u){
    if(q && (u.username || '').toLowerCase().indexOf(q) === -1 && (u.email || '').toLowerCase().indexOf(q) === -1) return false;
    if(filter === 'online' && !u.online) return false;
    if(filter === 'banned' && !u.is_banned) return false;
    if(filter === 'scam' && !u.is_scam) return false;
    if(filter === 'premium' && !u.is_premium) return false;
    if(filter === 'promo' && !u.referred_by) return false;
    return true;
  });

  var csv = 'id,username,email,created_at,online,is_banned,is_scam,is_premium,coins,referred_by\n';
  rows.forEach(function(u){
    csv += [u.id, u.username, u.email || '', u.created_at || '', u.online ? 'yes' : 'no', u.is_banned ? 'yes' : 'no', u.is_scam ? 'yes' : 'no', u.is_premium ? 'yes' : 'no', u.coins || 0, u.referred_by || ''].map(function(v){
      return '"' + String(v).replace(/"/g, '""') + '"';
    }).join(',') + '\n';
  });

  var blob = new Blob([csv], {type:'text/csv;charset=utf-8'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'users_' + Date.now() + '.csv';
  a.click();
  showNotice('📊 Скачан');
}

/* ============================================================
   КАРТОЧКА ЮЗЕРА
   ============================================================ */
async function openUserCard(uid){
  var u = _usersCache.find(function(x){ return x.id === uid; });
  if(!u) return;

  document.querySelectorAll('#userCardModal').forEach(function(m){
    if(!document.getElementById(m.id)) return;
  });

  var m = document.getElementById('userCardModal');
  var body = document.getElementById('userCardBody');

  body.innerHTML =
    '<div style="text-align:center;margin-bottom:16px">' +
      '<div style="width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent-2));display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:32px;margin:0 auto 10px">' +
        (u.avatar ? '<img src="' + u.avatar + '" style="width:100%;height:100%;object-fit:cover;border-radius:50%">' : u.username.charAt(0).toUpperCase()) +
      '</div>' +
      '<div style="font-size:20px;font-weight:900">' + esc(u.username) + '</div>' +
      '<div style="font-size:11px;color:var(--text-mute);font-family:monospace;margin-top:4px">ID: ' + u.id + '</div>' +
    '</div>' +
    '<div style="background:var(--bg-input);border-radius:12px;padding:14px;margin-bottom:14px;font-size:13px;line-height:1.9">' +
      '<div><b>Email:</b> ' + esc(u.email || '—') + (u.email_verified ? ' ✅' : ' ⚠️') + '</div>' +
      '<div><b>Дата рег:</b> ' + (u.created_at ? new Date(u.created_at).toLocaleString('ru-RU') : '—') + '</div>' +
      '<div><b>Last seen:</b> ' + (u.last_seen ? new Date(u.last_seen).toLocaleString('ru-RU') : '—') + '</div>' +
      '<div><b>Баланс:</b> ' + (u.coins || 0).toLocaleString('ru-RU') + ' 🏅</div>' +
      '<div><b>Сообщений:</b> ' + (u.messages_count || 0) + '</div>' +
      '<div><b>Роль:</b> ' + (u.role || 'user') + '</div>' +
      (u.referred_by ? '<div><b>🎁 Реферал:</b> ' + esc(u.referred_by) + '</div>' : '') +
    '</div>' +
    '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px">' +
      '<button class="save-btn green" style="margin:0" onclick="cardAction(' + u.id + ',\'unban\')">✅ Разбан</button>' +
      '<button class="save-btn red" style="margin:0" onclick="cardAction(' + u.id + ',\'ban\')">🔨 Бан</button>' +
      '<button class="save-btn red" style="margin:0" onclick="cardAction(' + u.id + ',\'toggle_scam\')">🎭 SCAM вкл/выкл</button>' +
      '<button class="save-btn gold" style="margin:0" onclick="cardAction(' + u.id + ',\'give_premium\')">💎 Premium 30д</button>' +
      '<button class="save-btn gray" style="margin:0" onclick="cardAction(' + u.id + ',\'force_logout\')">🚪 Force logout</button>' +
      '<button class="save-btn gray" style="margin:0" onclick="cardResetPass(' + u.id + ')">🔑 Сбросить пароль</button>' +
    '</div>';

  document.getElementById('userCardModal').classList.add('open');
}

async function cardAction(uid, action){
  if(action === 'force_logout'){
    await api('/owner/force_logout', {method:'POST', body:{token:token, user_id:uid}});
    showNotice('🚪');
    return;
  }
  if(action === 'ban'){
    var r = prompt('Причина:', '');
    await api('/owner/user_action', {method:'POST', body:{token:token, user_id:uid, action:'ban', reason:r}});
    showNotice('🔨');
    openUsersList();
    return;
  }
  var res = await api('/owner/user_action', {method:'POST', body:{token:token, user_id:uid, action:action}});
  if(res.ok){ showNotice('✅'); openUsersList(); }
  else showNotice('❌ ' + res.error, 'error');
}

async function cardResetPass(uid){
  if(!confirm('Сбросить пароль?')) return;
  var sr = await api('/owner/reset_pass_by_id', {method:'POST', body:{token:token, user_id:uid}});
  if(sr.ok && sr.data.new_password) alert('Новый пароль: ' + sr.data.new_password);
}

/* ============================================================
   ПРОМО-ПАНЕЛЬ
   ============================================================ */
async function openPromoPanel(){
  document.getElementById('promoPanelModal').classList.add('open');
  document.getElementById('promoListBody').innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">Загрузка...</div>';
  var res = await api('/owner/promo_list?token=' + encodeURIComponent(token));
  if(!res.ok){
    document.getElementById('promoListBody').innerHTML = '<div style="text-align:center;color:#f43f5e;padding:40px">Ошибка: ' + res.error + '</div>';
    return;
  }
  _promoCache = res.data;
  _selectedUsers = {};
  document.getElementById('promoTotalCount').textContent = _promoCache.length;
  renderPromoList();
}

function renderPromoList(){
  var c = document.getElementById('promoListBody');
  if(!_promoCache.length){
    c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:40px">🎁 Пока никто не зарегался по промо-ссылке</div>';
    return;
  }
  var html = '<div style="display:grid;grid-template-columns:36px 60px 1fr 1fr 100px 80px;gap:8px;padding:8px 10px;background:var(--bg-header);border-radius:10px;font-size:11px;font-weight:800;color:var(--text-mute);text-transform:uppercase;margin-bottom:8px">' +
    '<div><input type="checkbox" onchange="promoToggleAll(this.checked)" style="width:18px;height:18px;cursor:pointer"></div>' +
    '<div>ID</div>' +
    '<div>Ник</div>' +
    '<div>Email</div>' +
    '<div>Дата</div>' +
    '<div>Premium</div>' +
  '</div>';

  _promoCache.forEach(function(u){
    var checked = _selectedUsers[u.id] ? 'checked' : '';
    var dateStr = u.created_at ? new Date(u.created_at).toLocaleString('ru-RU', {day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'}) : '—';
    html += '<div style="display:grid;grid-template-columns:36px 60px 1fr 1fr 100px 80px;gap:8px;padding:8px 10px;background:var(--bg-input);border-radius:8px;margin-bottom:4px;font-size:12px;align-items:center">' +
      '<div><input type="checkbox" ' + checked + ' onchange="promoToggleSelect(' + u.id + ',this.checked)" style="width:18px;height:18px;cursor:pointer"></div>' +
      '<div style="color:var(--text-mute);font-family:monospace">' + u.id + '</div>' +
      '<div style="font-weight:800;cursor:pointer" onclick="viewProfile(' + u.id + ')">' + esc(u.username) + '</div>' +
      '<div style="color:var(--text-mute);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(u.email || '—') + '</div>' +
      '<div style="color:var(--text-mute);font-size:11px">' + dateStr + '</div>' +
      '<div style="font-size:14px">' + (u.is_premium ? '💎' : '—') + '</div>' +
    '</div>';
  });

  c.innerHTML = html;
  updatePromoSelectedInfo();
}

function promoToggleAll(checked){
  _promoCache.forEach(function(u){ if(checked) _selectedUsers[u.id] = true; else delete _selectedUsers[u.id]; });
  renderPromoList();
}

function promoToggleSelect(uid, checked){
  if(checked) _selectedUsers[uid] = true;
  else delete _selectedUsers[uid];
  updatePromoSelectedInfo();
}

function updatePromoSelectedInfo(){
  var n = Object.keys(_selectedUsers).length;
  var info = document.getElementById('promoSelectedInfo');
  if(n > 0){
    info.style.display = 'block';
    info.textContent = '✓ Выбрано: ' + n + ' юзеров';
  } else info.style.display = 'none';
}

function promoSelectRandom(n){
  _selectedUsers = {};
  var pool = _promoCache.slice();
  pool.sort(function(){ return Math.random() - 0.5; });
  var take = pool.slice(0, n);
  take.forEach(function(u){ _selectedUsers[u.id] = true; });
  renderPromoList();
  showNotice('🎲 Выбрано ' + take.length);
}

async function promoGivePremiumSelected(){
  var ids = Object.keys(_selectedUsers).map(function(x){ return parseInt(x); });
  if(!ids.length){ showNotice('⚠️ Никого не выбрано', 'warn'); return; }
  if(!confirm('Выдать Premium 30 дней ' + ids.length + ' юзерам?')) return;
  var res = await api('/owner/promo_give_premium', {method:'POST', body:{token:token, user_ids:ids}});
  if(res.ok){
    showNotice('💎 Выдано: ' + res.data.updated);
    _selectedUsers = {};
    openPromoPanel();
  } else showNotice('❌ ' + res.error, 'error');
}

function copyPromoLink(){
  var url = 'https://belugacord.onrender.com/fanchipromo';
  try {
    navigator.clipboard.writeText(url);
    showNotice('📋 ' + url);
  } catch(e){
    prompt('Скопируй:', url);
  }
}

function exportPromoCsv(){
  if(!_promoCache.length){ showNotice('⚠️ Пусто', 'warn'); return; }
  var csv = 'id,username,email,created_at,is_premium\n';
  _promoCache.forEach(function(u){
    csv += [u.id, u.username, u.email || '', u.created_at || '', u.is_premium ? 'yes' : 'no'].map(function(v){
      return '"' + String(v).replace(/"/g, '""') + '"';
    }).join(',') + '\n';
  });
  var blob = new Blob([csv], {type:'text/csv;charset=utf-8'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'promo_' + Date.now() + '.csv';
  a.click();
  showNotice('📊 Скачан');
}

/* ============================================================
   РЕДАКТОР БП
   ============================================================ */
function openBpEditor(){
  document.getElementById('bpEditorModal').classList.add('open');
  showBpEditorTab('season');
}

function showBpEditorTab(tab, ev){
  if(ev){
    document.querySelectorAll('#bpEditorModal .shop-tab-btn').forEach(function(b){ b.classList.remove('active'); });
    ev.target.classList.add('active');
  }
  var c = document.getElementById('bpEditorBody');
  if(tab === 'season') loadBpEditorSeason(c);
  else if(tab === 'quests') loadBpEditorQuests(c);
  else if(tab === 'rewards') loadBpEditorRewards(c);
}

async function loadBpEditorSeason(c){
  c.innerHTML = '<div style="text-align:center;padding:20px">Загрузка...</div>';
  var res = await api('/bp/admin/info?token=' + encodeURIComponent(token));
  if(!res.ok){ c.innerHTML = '<div style="color:#f43f5e;padding:20px;text-align:center">Ошибка</div>'; return; }
  var d = res.data;
  c.innerHTML =
    '<label class="label">Название</label>' +
    '<input type="text" id="bpAdminName" class="input-field" value="' + esc(d.name || '') + '" style="margin-bottom:8px">' +
    '<label class="label">Описание</label>' +
    '<textarea id="bpAdminDesc" class="input-field" style="margin-bottom:8px">' + esc(d.description || '') + '</textarea>' +
    '<label class="label">Эмодзи</label>' +
    '<input type="text" id="bpAdminEmoji" class="input-field" value="' + esc(d.emoji || '🏆') + '" maxlength="4" style="text-align:center;margin-bottom:12px">' +
    '<div style="display:flex;gap:8px;margin-top:12px">' +
      '<button class="save-btn green" style="margin:0;flex:1" onclick="saveBpAdmin()">💾 Сохранить</button>' +
      '<button class="save-btn gold" style="margin:0;flex:1" onclick="startBpSeason()">🟢 Начать</button>' +
    '</div>' +
    '<button class="save-btn red" onclick="endBpSeason()" style="margin-top:8px">🔴 Завершить</button>';
}

async function saveBpAdmin(){
  var name = document.getElementById('bpAdminName').value.trim();
  var desc = document.getElementById('bpAdminDesc').value.trim();
  var emoji = document.getElementById('bpAdminEmoji').value.trim();
  var res = await api('/bp/admin/save', {method:'POST', body:{token:token, name:name, description:desc, emoji:emoji}});
  if(res.ok){ showNotice('💾'); loadBpEditorSeason(document.getElementById('bpEditorBody')); }
}
async function startBpSeason(){
  if(!confirm('Начать сезон?')) return;
  var res = await api('/bp/admin/start', {method:'POST', body:{token:token}});
  if(res.ok){ showNotice('🟢'); loadBpEditorSeason(document.getElementById('bpEditorBody')); }
}
async function endBpSeason(){
  if(!confirm('Завершить сезон?')) return;
  var res = await api('/bp/admin/end', {method:'POST', body:{token:token}});
  if(res.ok){ showNotice('🔴'); loadBpEditorSeason(document.getElementById('bpEditorBody')); }
}

async function loadBpEditorQuests(c){
  c.innerHTML = '<div style="text-align:center;padding:20px">Загрузка...</div>';
  var res = await api('/bp/admin/quests?token=' + encodeURIComponent(token));
  if(!res.ok){ c.innerHTML = 'Ошибка'; return; }
  var quests = res.data;
  var html = '<button class="save-btn green" onclick="addBpQuest()" style="margin-bottom:12px">➕ Добавить задание</button>';
  if(!quests.length){
    html += '<div style="text-align:center;color:var(--text-mute);padding:20px">Пока нет заданий</div>';
  } else {
    quests.forEach(function(q){
      html += '<div style="padding:12px;background:var(--bg-input);border-radius:10px;margin-bottom:8px">' +
        '<div style="display:flex;justify-content:space-between;align-items:center">' +
          '<div style="flex:1"><div style="font-weight:800">' + esc(q.name) + '</div>' +
          '<div style="font-size:11px;color:var(--text-mute)">Цель: ' + q.goal + ' · +' + q.xp_reward + ' XP</div></div>' +
          '<button class="save-btn red" style="margin:0;width:auto;padding:6px 12px;font-size:11px" onclick="deleteBpQuest(' + q.id + ')">🗑️</button>' +
        '</div>' +
      '</div>';
    });
  }
  c.innerHTML = html;
}

async function addBpQuest(){
  var name = prompt('Название:');
  if(!name) return;
  var desc = prompt('Описание:', '') || '';
  var goal = parseInt(prompt('Цель:', '10')) || 10;
  var xp = parseInt(prompt('XP:', '100')) || 100;
  var res = await api('/bp/admin/quests/add', {method:'POST', body:{token:token, name:name, description:desc, goal:goal, xp_reward:xp}});
  if(res.ok){ showNotice('✅'); loadBpEditorQuests(document.getElementById('bpEditorBody')); }
}

async function deleteBpQuest(id){
  if(!confirm('Удалить?')) return;
  var res = await api('/bp/admin/quests/delete', {method:'POST', body:{token:token, quest_id:id}});
  if(res.ok){ showNotice('🗑️'); loadBpEditorQuests(document.getElementById('bpEditorBody')); }
}

async function loadBpEditorRewards(c){
  c.innerHTML = '<div style="text-align:center;padding:20px">Загрузка...</div>';
  var res = await api('/bp/admin/rewards?token=' + encodeURIComponent(token));
  if(!res.ok){ c.innerHTML = 'Ошибка'; return; }
  var rewards = res.data;
  var html = '<button class="save-btn green" onclick="addBpReward()" style="margin-bottom:12px">➕ Добавить награду</button>';
  if(!rewards.length){
    html += '<div style="text-align:center;color:var(--text-mute);padding:20px">Пока нет наград</div>';
  } else {
    rewards.forEach(function(r){
      html += '<div style="display:flex;gap:12px;padding:12px;background:var(--bg-input);border-radius:10px;margin-bottom:8px;align-items:center">' +
        '<div style="width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#ffd700,#ff8c00);display:flex;align-items:center;justify-content:center;font-weight:900;color:#1a0a2e">' + r.level + '</div>' +
        '<div style="flex:1;font-weight:800">' + esc(r.reward) + '</div>' +
        '<button class="save-btn red" style="margin:0;width:auto;padding:6px 12px;font-size:11px" onclick="deleteBpReward(' + r.id + ')">🗑️</button>' +
      '</div>';
    });
  }
  c.innerHTML = html;
}

async function addBpReward(){
  var level = parseInt(prompt('Уровень:', '1'));
  if(!level) return;
  var reward = prompt('Награда (текст):');
  if(!reward) return;
  var res = await api('/bp/admin/rewards/add', {method:'POST', body:{token:token, level:level, reward:reward}});
  if(res.ok){ showNotice('✅'); loadBpEditorRewards(document.getElementById('bpEditorBody')); }
}

async function deleteBpReward(id){
  if(!confirm('Удалить?')) return;
  var res = await api('/bp/admin/rewards/delete', {method:'POST', body:{token:token, reward_id:id}});
  if(res.ok){ showNotice('🗑️'); loadBpEditorRewards(document.getElementById('bpEditorBody')); }
}

/* ============================================================
   РЕЛИЗЫ (hot-swap)
   ============================================================ */
async function openReleasesPanel(){
  document.getElementById('releasesPanelModal').classList.add('open');
  var c = document.getElementById('releasesBody');
  c.innerHTML = '<div style="text-align:center;padding:20px">Загрузка...</div>';
  var res = await api('/owner/release/info?token=' + encodeURIComponent(token));
  if(!res.ok){ c.innerHTML = 'Ошибка'; return; }
  var d = res.data;
  c.innerHTML =
    '<div style="background:var(--bg-input);border-radius:12px;padding:16px;margin-bottom:14px;text-align:center">' +
      '<div style="font-size:11px;color:var(--text-mute);text-transform:uppercase;letter-spacing:2px">Текущая версия</div>' +
      '<div style="font-size:32px;font-weight:900;color:var(--accent);margin-top:4px">' + esc(d.current_version || '2.4') + '</div>' +
    '</div>' +
    '<label class="label">Новая версия</label>' +
    '<input type="text" id="relVersion" class="input-field" value="' + esc(d.target_version || '2.5') + '" style="margin-bottom:8px">' +
    '<label class="label">Что нового (каждая строка — пункт)</label>' +
    '<textarea id="relNotes" class="input-field" style="min-height:140px;margin-bottom:8px">' + esc(d.notes || '') + '</textarea>' +
    '<label style="display:flex;align-items:center;gap:10px;padding:10px;background:var(--bg-input);border-radius:10px;margin-bottom:12px">' +
      '<input type="checkbox" id="relForce" style="width:20px;height:20px"' + (d.force ? ' checked' : '') + '>' +
      '<span>Принудительно (юзер не может отказаться)</span>' +
    '</label>' +
    '<button class="save-btn gold" onclick="activateRelease()">🚀 Включить для всех</button>' +
    '<button class="save-btn gray" onclick="deactivateRelease()" style="margin-top:8px">↩️ Откатить</button>' +
    '<button class="save-btn purple" onclick="previewRelease()" style="margin-top:8px">👁️ Показать себе</button>';
}

async function activateRelease(){
  var version = document.getElementById('relVersion').value.trim();
  var notes = document.getElementById('relNotes').value.trim();
  var force = document.getElementById('relForce').checked;
  if(!version){ showNotice('⚠️ Версия', 'warn'); return; }
  if(!confirm('Активировать ' + version + ' для ВСЕХ юзеров?')) return;
  var res = await api('/owner/release/activate', {method:'POST', body:{token:token, version:version, notes:notes, force:force}});
  if(res.ok){ showNotice('🚀 Активировано'); openReleasesPanel(); }
  else showNotice('❌ ' + res.error, 'error');
}

async function deactivateRelease(){
  if(!confirm('Откатить для всех?')) return;
  var res = await api('/owner/release/deactivate', {method:'POST', body:{token:token}});
  if(res.ok){ showNotice('↩️ Откачено'); openReleasesPanel(); }
}

async function previewRelease(){
  var version = document.getElementById('relVersion').value.trim();
  var notes = document.getElementById('relNotes').value.trim();
  var force = document.getElementById('relForce').checked;
  if(typeof showReleaseModal === 'function'){
    showReleaseModal({version:version, notes:notes, force:force});
  } else {
    alert('Версия ' + version + '\n\n' + notes);
  }
}

/* ============================================================
   КООП-АБЬЮЗ
   ============================================================ */
var _coopSelected = null;
async function openCoopModal(){
  document.getElementById('abusePanelModal').classList.remove('open');
  document.getElementById('coopModal').classList.add('open');
  var res = await api('/abuse/online?token=' + encodeURIComponent(token));
  var c = document.getElementById('coopOnlineList');
  if(!res.ok || !res.data.users || !res.data.users.length){
    c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:12px">Никого онлайн</div>';
    return;
  }
  c.innerHTML = res.data.users.map(function(u){
    return '<div style="display:flex;gap:10px;padding:8px;background:var(--bg-input);border-radius:8px;margin-bottom:4px;cursor:pointer" onclick="selectCoopUser(' + u.id + ',\'' + esc(u.username) + '\')">' +
      '<div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent-2));display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;overflow:hidden">' +
        (u.avatar ? '<img src="' + u.avatar + '" style="width:100%;height:100%;object-fit:cover">' : u.username.charAt(0).toUpperCase()) +
      '</div>' +
      '<div style="font-weight:700">' + esc(u.username) + '</div>' +
    '</div>';
  }).join('');
}

function selectCoopUser(id, name){
  _coopSelected = {id:id, name:name};
  document.getElementById('coopSelectedBox').style.display = 'block';
  document.getElementById('coopSelectedName').textContent = name;
}

async function grantCoop(){
  if(!_coopSelected){ showNotice('⚠️ Выбери', 'warn'); return; }
  var minutes = parseInt(document.getElementById('coopMinutes').value) || 60;
  var res = await api('/abuse/coop_start', {method:'POST', body:{
    token: token,
    username: _coopSelected.name,
    minutes: minutes
  }});
  if(res.ok) showNotice('🚀 Выдан');
  else showNotice('❌ ' + res.error, 'error');
}

/* ============================================================
   АБЬЮЗ-ПАНЕЛЬ
   ============================================================ */
async function openAbusePanel(){
  document.getElementById('abusePanelModal').classList.add('open');
  var res = await api('/abuse/access?token=' + encodeURIComponent(token));
  var acc = res.data;
  if(!acc.access){
    document.getElementById('abuseCards').innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">❌ Нет доступа</div>';
    return;
  }
  var cards = [];
  if(acc.owner){
    cards = [
      ['👥', 'Онлайн', 'abuseShowOnline'],
      ['🎁', 'Подарок', 'abuseRandomGift'],
      ['🎨', 'NFT', 'abuseRandomNft'],
      ['🏅', 'Бекоины', 'abuseRandomCoins'],
      ['🤝', 'Кооп', 'openCoopModal'],
      ['📢', 'Анонс', 'ownerAnnounce']
    ];
  } else {
    if(acc.can_online) cards.push(['👥', 'Онлайн', 'abuseShowOnline']);
    if(acc.can_gift) cards.push(['🎁', 'Подарок', 'abuseRandomGift']);
    if(acc.can_nft) cards.push(['🎨', 'NFT', 'abuseRandomNft']);
    if(acc.can_coins) cards.push(['🏅', 'Бекоины', 'abuseRandomCoins']);
  }
  var c = document.getElementById('abuseCards');
  c.innerHTML = cards.map(function(x){
    return '<div class="owner-card" data-fn="' + x[2] + '"><span class="oc-icon">' + x[0] + '</span><div class="oc-name">' + x[1] + '</div></div>';
  }).join('');
  c.querySelectorAll('.owner-card').forEach(function(card){
    card.addEventListener('click', function(){
      var fn = card.getAttribute('data-fn');
      if(typeof window[fn] === 'function') window[fn]();
    });
  });
}

async function abuseShowOnline(){
  var res = await api('/abuse/online?token=' + encodeURIComponent(token));
  if(!res.ok || !res.data.users.length){ alert('Никого'); return; }
  alert('Онлайн:\n' + res.data.users.map(function(u){ return u.username; }).join('\n'));
}
async function abuseRandomGift(){
  var res = await api('/abuse/random_gift', {method:'POST', body:{token:token}});
  if(res.ok) showNotice('🎁 ' + res.data.target);
  else showNotice('❌ ' + res.error, 'error');
}
async function abuseRandomNft(){
  var res = await api('/abuse/random_nft', {method:'POST', body:{token:token}});
  if(res.ok) showNotice('🎨 ' + res.data.target);
  else showNotice('❌ ' + res.error, 'error');
}
async function abuseRandomCoins(){
  var res = await api('/abuse/random_coins', {method:'POST', body:{token:token}});
  if(res.ok) showNotice('🏅 ' + res.data.target + ' → ' + res.data.amount);
  else showNotice('❌ ' + res.error, 'error');
}

/* ============================================================
   ИВЕНТЫ
   ============================================================ */
function openCreateEvent(){
  var m = document.createElement('div');
  m.className = 'modal-overlay open';
  m.id = 'eventCreateInline';
  m.innerHTML = '<div class="modal" style="max-width:500px">' +
    '<button class="close-btn" onclick="document.getElementById(\'eventCreateInline\').remove()">✕</button>' +
    '<div style="padding:28px 24px">' +
      '<h2 style="text-align:center;font-size:20px;margin-bottom:16px">🎉 Создать ивент</h2>' +
      '<input type="text" id="eventName" class="input-field" placeholder="Название" style="margin-bottom:10px">' +
      '<input type="text" id="eventDesc" class="input-field" placeholder="Описание" style="margin-bottom:10px">' +
      '<input type="text" id="eventEmoji" class="input-field" placeholder="🎉" maxlength="4" value="🎉" style="text-align:center;margin-bottom:10px">' +
      '<select id="eventType" class="input-field" style="margin-bottom:10px"><option value="coins_x">💰 Множитель бекоинов</option><option value="xp_x">📊 Множитель XP</option></select>' +
      '<input type="number" id="eventMultiplier" class="input-field" placeholder="Множитель" value="10" style="margin-bottom:10px">' +
      '<input type="number" id="eventDuration" class="input-field" placeholder="Минут" value="10" style="margin-bottom:10px">' +
      '<button class="save-btn green" onclick="createEvent()">🚀 Запустить</button>' +
    '</div>' +
  '</div>';
  document.body.appendChild(m);
}
async function createEvent(){
  var name = document.getElementById('eventName').value.trim();
  var desc = document.getElementById('eventDesc').value.trim();
  var emoji = document.getElementById('eventEmoji').value.trim();
  var type = document.getElementById('eventType').value;
  var mult = parseInt(document.getElementById('eventMultiplier').value);
  var dur = parseInt(document.getElementById('eventDuration').value);
  if(!name || !mult || !dur){ showNotice('⚠️', 'warn'); return; }
  var res = await api('/owner/events/create', {method:'POST', body:{token:token, name:name, description:desc, emoji:emoji, event_type:type, multiplier:mult, duration_minutes:dur}});
  if(res.ok){ showNotice('🎉 Запущен'); document.getElementById('eventCreateInline').remove(); }
}
async function listEvents(){
  var res = await api('/owner/events/list?token=' + encodeURIComponent(token));
  if(!res.ok || !res.data.length){ alert('Нет активных ивентов'); return; }
  alert('Активные ивенты:\n' + res.data.map(function(e){ return '#' + e.id + ' ' + e.name + ' ×' + e.multiplier; }).join('\n'));
}

/* ============================================================
   ЭКСПОРТ
   ============================================================ */
window.openUsersList = openUsersList;
window.filterUsersList = filterUsersList;
window.usersSelectAll = usersSelectAll;
window.userToggleSelect = userToggleSelect;
window.massAction = massAction;
window.exportUsersCsv = exportUsersCsv;
window.openUserCard = openUserCard;
window.cardAction = cardAction;
window.cardResetPass = cardResetPass;
window.openPromoPanel = openPromoPanel;
window.promoToggleAll = promoToggleAll;
window.promoToggleSelect = promoToggleSelect;
window.promoSelectRandom = promoSelectRandom;
window.promoGivePremiumSelected = promoGivePremiumSelected;
window.copyPromoLink = copyPromoLink;
window.exportPromoCsv = exportPromoCsv;
window.openBpEditor = openBpEditor;
window.showBpEditorTab = showBpEditorTab;
window.saveBpAdmin = saveBpAdmin;
window.startBpSeason = startBpSeason;
window.endBpSeason = endBpSeason;
window.addBpQuest = addBpQuest;
window.deleteBpQuest = deleteBpQuest;
window.addBpReward = addBpReward;
window.deleteBpReward = deleteBpReward;
window.openReleasesPanel = openReleasesPanel;
window.activateRelease = activateRelease;
window.deactivateRelease = deactivateRelease;
window.previewRelease = previewRelease;
window.openCoopModal = openCoopModal;
window.selectCoopUser = selectCoopUser;
window.grantCoop = grantCoop;
window.openAbusePanel = openAbusePanel;
window.abuseShowOnline = abuseShowOnline;
window.abuseRandomGift = abuseRandomGift;
window.abuseRandomNft = abuseRandomNft;
window.abuseRandomCoins = abuseRandomCoins;
window.openCreateEvent = openCreateEvent;
window.createEvent = createEvent;
window.listEvents = listEvents;

console.log('[BC] features/admin loaded (part 2/2)');
