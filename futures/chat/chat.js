/* ============================================================
   BELUGACORD 2.5 — MODULE: CHAT
   Чат, DM, друзья, группы, сервера, сообщения, реакции, треды
   ============================================================ */

/* ============================================================
   СОСТОЯНИЕ МОДУЛЯ
   ============================================================ */
var currentServerId = null, currentChannelId = null, currentServerData = null;
var currentDMUser = null, currentGroupId = null, currentGroupData = null;
var currentChatType = 'none', currentChannelMode = 'public';
var unreadCounts = {}, currentTyping = {};
var msgCache = {}, pinnedMsgId = null, replyTo = null, draftKey = null;
var openTabs = [];
var STICKERS = [];
var MY_EMOJIS = ['😀','😂','🥰','😎','🤔','😴','🤯','🥳','😭','😡','👍','👎','❤️','🔥','⭐','✨','🎉','🎁','🐱','🐶','🍕','🍔','⚽','🎮','💎','🏆','💰','🎵','🌈','☀️','🌙','⚡'];
var QUICK_REACTIONS = ['👍','❤️','🔥','😂','😮','😢'];
var voiceMediaRecorder = null, voiceChunks = [], voiceStartTime = 0, voiceTimer = null;

/* ============================================================
   РОЛИ / БЕЙДЖИ
   ============================================================ */
function buildRoleBadge(m){
  if(!m) return '';
  if(m.is_scam) return '<span class="role-badge role-scam">SCAM</span>';
  if(m.role === 'owner') return '<span class="role-badge role-owner">Владелец</span>';
  if(m.is_admin) return '<span class="role-badge role-admin">Админ</span>';
  if(m.is_moderator) return '<span class="role-badge role-mod">Модер</span>';
  if(m.is_streamer) return '<span class="role-badge role-streamer">🎥 Стример</span>';
  if(m.is_beta_tester) return '<span class="role-badge role-beta">Бета</span>';
  return '<span class="role-badge role-user">Юзер</span>';
}
function buildPremiumBadge(m){
  if(!m || !m.is_premium) return '';
  return '<span class="premium-badge">💎</span>';
}
function buildTitleBadge(m){
  if(!m || !m.title) return '';
  return '<span class="title-badge">' + esc(m.title) + '</span>';
}

/* ============================================================
   ДРУЗЬЯ
   ============================================================ */
async function showFriends(){
  currentChatType = 'friends';
  currentDMUser = null;
  currentChannelId = null;
  currentGroupId = null;

  document.getElementById('chatWindowTitle').textContent = 'Друзья';
  document.getElementById('chatWindowAvatar').textContent = '👥';
  document.getElementById('chatMembersBtn').style.display = 'none';
  document.getElementById('chatCallBtn').style.display = 'none';
  var gcb = document.getElementById('chatGroupCallBtn');
  if(gcb) gcb.style.display = 'none';
  var ssb = document.getElementById('chatServerSettingsBtn');
  if(ssb) ssb.style.display = 'none';
  var gsb = document.getElementById('chatGroupSettingsBtn');
  if(gsb) gsb.style.display = 'none';
  var cmb = document.getElementById('chatChannelModeBtn');
  if(cmb) cmb.style.display = 'none';

  document.getElementById('messagesInner').innerHTML =
    '<div style="padding:20px">' +
      '<div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">' +
        '<button class="save-btn" style="margin:0;flex:1;min-width:130px" onclick="openUserSearch()">🔍 Поиск</button>' +
        '<button class="save-btn gray" style="margin:0;flex:1;min-width:130px" onclick="promptAddFriend()">➕ По нику</button>' +
      '</div>' +
      '<div id="friendsBodyList"><div style="text-align:center;color:var(--text-mute);padding:20px">Загрузка...</div></div>' +
    '</div>';

  var res = await api('/friends/list?token=' + encodeURIComponent(token));
  if(!res.ok){
    document.getElementById('friendsBodyList').innerHTML =
      '<div style="text-align:center;color:#f43f5e;padding:20px">Ошибка</div>';
    return;
  }
  var list = document.getElementById('friendsBodyList');
  var inc = res.data.filter(function(f){ return f.status === 'incoming'; });
  var out = res.data.filter(function(f){ return f.status === 'outgoing'; });
  var acc = res.data.filter(function(f){ return f.status === 'accepted'; });
  list.innerHTML = '';

  if(inc.length){
    var h1 = document.createElement('h3');
    h1.style.cssText = 'color:var(--accent);font-size:11px;text-transform:uppercase;font-weight:800;margin-bottom:10px';
    h1.textContent = '📩 Входящие (' + inc.length + ')';
    list.appendChild(h1);
    inc.forEach(function(f){
      var row = document.createElement('div');
      row.className = 'chat-item';
      var av = f.avatar ? '<img src="' + (f.gif_avatar || f.avatar) + '">' : f.username.charAt(0).toUpperCase();
      var ring = f.online ? '<div class="avatar-online-ring"></div>' : '';
      row.innerHTML =
        '<div class="avatar" style="position:relative">' + av + ring + '</div>' +
        '<div class="chat-item-info">' +
          '<div class="chat-item-name">' + esc(f.username) + buildRoleBadge(f) + buildPremiumBadge(f) + '</div>' +
          '<div class="chat-item-preview">хочет добавить</div>' +
        '</div>' +
        '<div style="display:flex">' +
          '<button class="save-btn green" style="margin:0;padding:6px 10px;width:auto;font-size:12px" onclick="event.stopPropagation();acceptFriend(' + f.request_id + ',this)">✓</button>' +
          '<button class="save-btn red" style="margin:0 0 0 4px;padding:6px 10px;width:auto;font-size:12px" onclick="event.stopPropagation();declineFriend(' + f.request_id + ',this)">✕</button>' +
        '</div>';
      list.appendChild(row);
    });
  }
  if(out.length){
    var h2 = document.createElement('h3');
    h2.style.cssText = 'color:var(--text-dim);font-size:11px;text-transform:uppercase;font-weight:800;margin:16px 0 10px';
    h2.textContent = '📤 Исходящие (' + out.length + ')';
    list.appendChild(h2);
    out.forEach(function(f){
      var row = document.createElement('div');
      row.className = 'chat-item';
      var av = f.avatar ? '<img src="' + f.avatar + '">' : f.username.charAt(0).toUpperCase();
      row.innerHTML =
        '<div class="avatar">' + av + '</div>' +
        '<div class="chat-item-info">' +
          '<div class="chat-item-name">' + esc(f.username) + '</div>' +
          '<div class="chat-item-preview">⏳</div>' +
        '</div>' +
        '<button class="save-btn gray" style="margin:0;padding:6px 10px;width:auto;font-size:11px" onclick="event.stopPropagation();cancelRequest(' + f.request_id + ',this)">✕</button>';
      list.appendChild(row);
    });
  }
  var h3 = document.createElement('h3');
  h3.style.cssText = 'color:var(--text-dim);font-size:11px;text-transform:uppercase;font-weight:800;margin:16px 0 10px';
  h3.textContent = 'Друзья (' + acc.length + ')';
  list.appendChild(h3);
  if(!acc.length){
    var em = document.createElement('div');
    em.style.cssText = 'padding:16px;text-align:center;color:var(--text-mute);font-size:13px';
    em.textContent = 'Пока никого 😢';
    list.appendChild(em);
  }
  acc.forEach(function(f){
    var row = document.createElement('div');
    row.className = 'chat-item';
    var avSrc = f.gif_avatar || f.avatar;
    var av = avSrc ? '<img src="' + avSrc + '">' : f.username.charAt(0).toUpperCase();
    var ring = f.online ? '<div class="avatar-online-ring' + (f.online_status === 'dnd' ? ' dnd' : '') + '"></div>' : '';
    var status = f.online ? (f.custom_status || (f.online_status === 'dnd' ? 'не беспокоить' : 'в сети')) : (f.last_seen ? timeAgo(f.last_seen) : 'не в сети');
    var timeHtml = f.last_message_at ? '<span class="chat-item-time">' + timeAgo(f.last_message_at) + '</span>' : '';
    var unread = unreadCounts[f.id] ? '<span class="user-badge-count">' + unreadCounts[f.id] + '</span>' : '';
    row.innerHTML =
      '<div class="avatar" style="position:relative">' + av + ring + unread + '</div>' +
      '<div class="chat-item-info">' +
        '<div class="chat-item-name">' + esc(f.username) + buildRoleBadge(f) + buildPremiumBadge(f) + '</div>' +
        '<div class="chat-item-preview"><span>' + esc(status) + '</span></div>' +
      '</div>' + timeHtml;
    row.onclick = function(){ openDM(f.id, f.username, avSrc); };
    list.appendChild(row);
  });

  if(window.innerWidth <= 768) mobileShow('chat');
}

async function acceptFriend(requestId, btn){
  if(btn){ btn.disabled = true; btn.textContent = '...'; }
  var res = await api('/friends/accept', {method:'POST', body:{token:token, request_id:requestId}});
  if(res.ok){ showNotice('✅ Принят'); setTimeout(showFriends, 300); }
  else { if(btn){ btn.disabled = false; btn.textContent = '✓'; } showNotice('❌ ' + res.error, 'error'); }
}
async function declineFriend(requestId, btn){
  if(btn){ btn.disabled = true; btn.textContent = '...'; }
  await api('/friends/decline', {method:'POST', body:{token:token, request_id:requestId}});
  setTimeout(showFriends, 300);
}
async function cancelRequest(requestId, btn){
  if(btn){ btn.disabled = true; btn.textContent = '...'; }
  await api('/friends/cancel', {method:'POST', body:{token:token, request_id:requestId}});
  setTimeout(showFriends, 300);
}
async function removeFriend(id, btn){
  if(!confirm('Удалить?')) return;
  if(btn){ btn.disabled = true; btn.textContent = '...'; }
  await api('/friends/remove', {method:'POST', body:{token:token, user_id:id}});
  showNotice('🗑️');
  setTimeout(showFriends, 300);
}
async function updateFriendsBadge(){
  if(!me) return;
  var res = await api('/friends/count?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var n = res.data.count || 0;
  var el = document.getElementById('friendsBadge');
  var deskIcon = document.querySelector('.desktop-icon[onclick="showFriends()"] .d-icon');
  if(n > 0){
    if(!el && deskIcon){
      el = document.createElement('div');
      el.id = 'friendsBadge';
      el.className = 'user-badge-count';
      deskIcon.appendChild(el);
    }
    if(el) el.textContent = n;
  } else if(el) el.remove();
}
function promptAddFriend(){
  var u = prompt('Ник:');
  if(!u) return;
  api('/friends/request', {method:'POST', body:{token:token, username:u.trim()}}).then(function(res){
    if(res.ok){ showNotice('👥'); showFriends(); }
    else showNotice('❌ ' + res.error, 'error');
  });
}

/* ============================================================
   ГРУППЫ
   ============================================================ */
async function loadGroups(){
  var res = await api('/groups/list?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var cont = document.getElementById('desktopIcons');
  if(!cont) return;
  Array.from(cont.querySelectorAll('.group-item')).forEach(function(el){ el.remove(); });
  res.data.forEach(function(g){
    var d = document.createElement('div');
    d.className = 'desktop-icon group-item';
    var iconSrc = g.gif_avatar || g.avatar;
    var iconStyle = iconSrc ? 'background-image:url(' + iconSrc + ');background-size:cover;' : '';
    var text = iconSrc ? '' : (g.name || '?').charAt(0).toUpperCase();
    d.innerHTML = '<div class="d-icon" style="' + iconStyle + '">' + text + '</div><div class="d-label">' + esc(g.name) + '</div>';
    d.onclick = function(){ openGroup(g.id, g.name); };
    cont.appendChild(d);
  });
}
function openCreateGroup(){
  document.getElementById('createGroupModal').classList.add('open');
  document.getElementById('newGroupName').value = '';
  document.getElementById('newGroupMembers').value = '';
  var hint = document.getElementById('groupLimitHint');
  if(hint) hint.textContent = BC.isPremium ? '💎 Лимит: 30' : '👥 Лимит: 10';
}
async function createGroup(){
  var name = document.getElementById('newGroupName').value.trim();
  var memStr = document.getElementById('newGroupMembers').value.trim();
  if(!name){ showNotice('⚠️ Название', 'warn'); return; }
  var members = [];
  if(memStr){
    memStr.split(',').forEach(function(x){
      var n = x.trim().replace(/^@/, '');
      if(n) members.push(n);
    });
  }
  var ids = [];
  for(var i = 0; i < members.length; i++){
    var sr = await api('/users/search?q=' + encodeURIComponent(members[i]) + '&token=' + encodeURIComponent(token));
    if(sr.ok){
      var u = sr.data.find(function(x){ return x.username.toLowerCase() === members[i].toLowerCase(); });
      if(u) ids.push(u.id);
    }
  }
  var res = await api('/groups/create', {method:'POST', body:{token:token, name:name, members:ids}});
  if(res.ok){
    showNotice('✅ Группа создана');
    document.getElementById('createGroupModal').classList.remove('open');
    loadGroups();
    openGroup(res.data.id, res.data.name);
  } else showNotice('❌ ' + res.error, 'error');
}

async function openGroup(id, name){
  openTab('group', id, name);
  await doOpenGroup(id, name);
}

async function doOpenGroup(id, name){
  currentGroupId = id;
  currentDMUser = null;
  currentChannelId = null;
  currentServerId = null;
  currentChatType = 'group';

  document.getElementById('chatWindowTitle').textContent = '👥 ' + name;
  document.getElementById('chatWindowAvatar').textContent = '👥';
  document.getElementById('chatMembersBtn').style.display = 'flex';
  document.getElementById('chatCallBtn').style.display = 'none';
  var gcb = document.getElementById('chatGroupCallBtn');
  if(gcb) gcb.style.display = BC.isPremium ? 'flex' : 'none';
  document.getElementById('chatServerSettingsBtn').style.display = 'none';
  var gsb = document.getElementById('chatGroupSettingsBtn');
  if(gsb) gsb.style.display = 'flex';
  var cmb = document.getElementById('chatChannelModeBtn');
  if(cmb) cmb.style.display = 'none';

  var res = await api('/groups/' + id + '?token=' + encodeURIComponent(token));
  if(res.ok) currentGroupData = res.data;

  var msgRes = await api('/groups/' + id + '/messages?token=' + encodeURIComponent(token));
  if(msgRes.ok){
    var inner = document.getElementById('messagesInner');
    inner.innerHTML = '';
    msgRes.data.forEach(function(m){ addMessage(m); });
    scrollBottom();
  }
  autoFocusInput();
  if(window.innerWidth <= 768) mobileShow('chat');
}

function openGroupSettings(){
  if(!currentGroupData){ showNotice('⚠️ Открой группу', 'warn'); return; }
  document.getElementById('groupNameInput').value = currentGroupData.name || '';
  document.getElementById('groupDescInput').value = currentGroupData.description || '';
  document.getElementById('groupAvatarInput').value = currentGroupData.avatar || '';
  document.getElementById('groupGifAvatarInput').value = currentGroupData.gif_avatar || '';
  document.getElementById('groupAddInput').value = '';
  document.getElementById('groupSettingsModal').classList.add('open');
}
async function saveGroupSettings(){
  var res = await api('/groups/update', {method:'POST', body:{
    token: token,
    group_id: currentGroupId,
    name: document.getElementById('groupNameInput').value,
    description: document.getElementById('groupDescInput').value,
    avatar: document.getElementById('groupAvatarInput').value,
    gif_avatar: document.getElementById('groupGifAvatarInput').value || null
  }});
  if(res.ok){
    showNotice('✅');
    loadGroups();
    setTimeout(function(){
      document.getElementById('groupSettingsModal').classList.remove('open');
    }, 900);
  } else showNotice('❌ ' + res.error, 'error');
}
async function groupAddMember(){
  var u = document.getElementById('groupAddInput').value.trim().replace(/^@/, '');
  if(!u) return;
  var res = await api('/groups/add_member', {method:'POST', body:{token:token, group_id:currentGroupId, username:u}});
  if(res.ok){ showNotice('✅ Добавлен'); document.getElementById('groupAddInput').value = ''; }
  else showNotice('❌ ' + res.error, 'error');
}
async function leaveGroup(){
  if(!confirm('Выйти?')) return;
  var res = await api('/groups/leave', {method:'POST', body:{token:token, group_id:currentGroupId}});
  if(res.ok){
    showNotice('🚪');
    document.getElementById('groupSettingsModal').classList.remove('open');
    currentGroupId = null;
    currentGroupData = null;
    loadGroups();
    showFriends();
  }
}
async function groupKick(uid){
  if(!confirm('Кикнуть?')) return;
  var res = await api('/groups/kick', {method:'POST', body:{token:token, group_id:currentGroupId, user_id:uid}});
  if(res.ok){ showNotice('👢'); document.getElementById('membersModal').classList.remove('open'); }
}

/* ============================================================
   СЕРВЕРА
   ============================================================ */
async function loadServers(){
  var res = await api('/servers/list?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var cont = document.getElementById('desktopIcons');
  if(!cont) return;
  Array.from(cont.querySelectorAll('.server-item')).forEach(function(el){ el.remove(); });
  res.data.forEach(function(s){
    var d = document.createElement('div');
    d.className = 'desktop-icon server-item';
    var iconStyle = s.avatar ? 'background-image:url(' + s.avatar + ');background-size:cover;' : '';
    var text = s.avatar ? '' : s.name.charAt(0).toUpperCase();
    d.innerHTML = '<div class="d-icon" style="' + iconStyle + '">' + text + '</div><div class="d-label">' + esc(s.name) + '</div>';
    d.onclick = function(){ openServer(s.id, s.name); };
    cont.appendChild(d);
  });
}

async function openServer(id, name){
  openTab('server', id, name);
  await loadServerContent(id, name);
}

async function loadServerContent(id, name){
  currentServerId = id;
  document.getElementById('chatWindowTitle').textContent = name;
  document.getElementById('chatWindowAvatar').textContent = '🏠';
  var ssb = document.getElementById('chatServerSettingsBtn');
  if(ssb) ssb.style.display = 'flex';
  var gsb = document.getElementById('chatGroupSettingsBtn');
  if(gsb) gsb.style.display = 'none';
  var cmb = document.getElementById('chatChannelModeBtn');
  if(cmb) cmb.style.display = 'none';
  document.getElementById('chatMembersBtn').style.display = 'flex';
  document.getElementById('chatCallBtn').style.display = 'none';
  var gcb = document.getElementById('chatGroupCallBtn');
  if(gcb) gcb.style.display = 'none';
  document.getElementById('messagesInner').innerHTML =
    '<div style="text-align:center;color:var(--text-mute);padding:60px 20px">Выбери канал 👈</div>';

  var res = await api('/servers/' + id + '?token=' + encodeURIComponent(token));
  if(res.ok) currentServerData = res.data;

  var chRes = await api('/servers/' + id + '/channels?token=' + encodeURIComponent(token));
  if(chRes.ok) renderChannelList(chRes.data);
}

function renderChannelList(channels){
  var c = document.getElementById('chatListBody');
  if(!c) return;
  c.innerHTML = '<div style="font-size:11px;text-transform:uppercase;color:var(--text-mute);font-weight:800;padding:12px 10px 6px">Каналы</div>';
  channels.forEach(function(ch){
    var d = document.createElement('div');
    d.className = 'chat-item' + (ch.id === currentChannelId ? ' active' : '');
    var timeHtml = ch.last_message_at ? '<span class="chat-item-time">' + timeAgo(ch.last_message_at) + '</span>' : '';
    var modeIcon = ch.mode === 'readonly' ? '📢' : (ch.mode === 'paid_reactions' ? '💰' : '#');
    d.innerHTML =
      '<div class="avatar">' + modeIcon + '</div>' +
      '<div class="chat-item-info">' +
        '<div class="chat-item-name">' + esc(ch.name) + '</div>' +
      '</div>' + timeHtml;
    d.onclick = function(){ openChannel(ch.id, ch.name, ch.mode); };
    c.appendChild(d);
  });
}

async function openChannel(id, name, mode){
  openTab('channel', id, name);
  await doOpenChannel(id, name, mode);
}

async function doOpenChannel(id, name, mode){
  currentChannelId = id;
  currentDMUser = null;
  currentGroupId = null;
  currentChatType = 'channel';
  currentChannelMode = mode || 'public';

  document.getElementById('chatWindowTitle').textContent = name;
  document.getElementById('chatWindowAvatar').textContent = (mode === 'readonly' ? '📢' : '#');
  document.getElementById('messagesInner').innerHTML = '';
  document.getElementById('chatMembersBtn').style.display = 'flex';
  document.getElementById('chatCallBtn').style.display = 'none';
  var gcb = document.getElementById('chatGroupCallBtn');
  if(gcb) gcb.style.display = 'none';
  var ssb = document.getElementById('chatServerSettingsBtn');
  if(ssb) ssb.style.display = 'flex';
  var gsb = document.getElementById('chatGroupSettingsBtn');
  if(gsb) gsb.style.display = 'none';
  var cmb = document.getElementById('chatChannelModeBtn');
  if(cmb) cmb.style.display = 'flex';

  var res = await api('/channels/' + id + '/messages?token=' + encodeURIComponent(token));
  if(res.ok){
    var msgs = res.data.messages || [];
    msgs.forEach(function(m){ addMessage(m); });
    renderPinned(res.data.pinned || []);
    scrollBottom();
  }
  autoFocusInput();
  if(window.innerWidth <= 768) mobileShow('chat');
}

function openServerSettings(){
  if(!currentServerData){ showNotice('⚠️ Открой сервер', 'warn'); return; }
  document.getElementById('serverNameInput').value = currentServerData.name || '';
  document.getElementById('serverDescInput').value = currentServerData.description || '';
  document.getElementById('serverInviteInput').value = currentServerData.invite_code || '';
  document.getElementById('serverSettingsModal').classList.add('open');
}
async function saveServerSettings(){
  var res = await api('/servers/update', {method:'POST', body:{
    token: token,
    server_id: currentServerId,
    name: document.getElementById('serverNameInput').value,
    description: document.getElementById('serverDescInput').value
  }});
  if(res.ok){
    showNotice('✅');
    loadServers();
    setTimeout(function(){ document.getElementById('serverSettingsModal').classList.remove('open'); }, 900);
  }
}
async function regenInvite(){
  var res = await api('/servers/regen_invite', {method:'POST', body:{token:token, server_id:currentServerId}});
  if(res.ok){
    document.getElementById('serverInviteInput').value = res.data.invite_code;
    showNotice('🔄');
  }
}
function copyInvite(){
  var i = document.getElementById('serverInviteInput');
  i.select();
  try { document.execCommand('copy'); showNotice('📋'); } catch(e){}
}
async function createChannelInline(){
  var name = document.getElementById('newChannelInput').value.trim();
  if(!name) return;
  var res = await api('/channels/create', {method:'POST', body:{token:token, server_id:currentServerId, name:name}});
  if(res.ok){
    showNotice('✅');
    document.getElementById('newChannelInput').value = '';
    var chRes = await api('/servers/' + currentServerId + '/channels?token=' + encodeURIComponent(token));
    if(chRes.ok) renderChannelList(chRes.data);
  }
}
async function deleteServer(){
  if(!confirm('УДАЛИТЬ?')) return;
  var res = await api('/servers/delete', {method:'POST', body:{token:token, server_id:currentServerId}});
  if(res.ok){
    document.getElementById('serverSettingsModal').classList.remove('open');
    currentServerId = null;
    loadServers();
    showFriends();
  }
}
async function leaveServer(){
  if(!confirm('Выйти?')) return;
  await api('/servers/leave', {method:'POST', body:{token:token, server_id:currentServerId}});
  document.getElementById('serverSettingsModal').classList.remove('open');
  currentServerId = null;
  loadServers();
  showFriends();
}

async function openMembers(){
  var url = null;
  if(currentServerId) url = '/servers/' + currentServerId + '/members?token=' + encodeURIComponent(token);
  else if(currentGroupId) url = '/groups/' + currentGroupId + '/members?token=' + encodeURIComponent(token);
  if(!url) return;
  var res = await api(url.replace('/api', ''));
  if(!res.ok) return;
  var list = document.getElementById('membersList');
  list.innerHTML = '';
  res.data.forEach(function(m){
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:12px;cursor:pointer';
    var avSrc = m.gif_avatar || m.avatar;
    var av = avSrc ? '<img src="' + avSrc + '" style="width:100%;height:100%;object-fit:cover">' : m.username.charAt(0).toUpperCase();
    row.innerHTML =
      '<div style="width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent-2));display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;overflow:hidden">' + av + '</div>' +
      '<div style="flex:1;display:flex;gap:4px;align-items:center;flex-wrap:wrap">' + esc(m.username) + buildRoleBadge(m) + buildPremiumBadge(m) + '</div>' +
      (currentGroupId ? '<button class="save-btn red" style="margin:0;width:auto;padding:6px 10px;font-size:11px" onclick="event.stopPropagation();groupKick(' + m.id + ')">👢</button>' : '');
    row.onclick = function(){
      document.getElementById('membersModal').classList.remove('open');
      viewProfile(m.id);
    };
    list.appendChild(row);
  });
  document.getElementById('membersModal').classList.add('open');
}

function openChannelMode(){
  document.getElementById('channelModeModal').classList.add('open');
  document.querySelectorAll('input[name="channelMode"]').forEach(function(r){
    r.checked = (r.value === currentChannelMode);
  });
}
async function saveChannelMode(){
  var mode = 'public';
  document.querySelectorAll('input[name="channelMode"]').forEach(function(r){
    if(r.checked) mode = r.value;
  });
  var res = await api('/channels/set_mode', {method:'POST', body:{token:token, channel_id:currentChannelId, mode:mode}});
  if(res.ok){
    currentChannelMode = mode;
    showNotice('✅ Режим: ' + mode);
    document.getElementById('channelModeModal').classList.remove('open');
  }
}

/* ============================================================
   ТАБЫ
   ============================================================ */
function renderServerTabs(){
  var c = document.getElementById('serverTabs');
  if(!c) return;
  c.innerHTML = '';
  if(!openTabs.length){ c.style.display = 'none'; return; }
  c.style.display = 'flex';
  openTabs.forEach(function(tab, i){
    var el = document.createElement('div');
    el.className = 'server-tab' + (tab.active ? ' active' : '');
    var icon = tab.type === 'server' ? '🏠' : (tab.type === 'channel' ? '#' : (tab.type === 'group' ? '👥' : '💬'));
    var closeBtn = tab.type !== 'server' ? '<span class="tab-close" onclick="event.stopPropagation();closeTab(' + i + ')">✕</span>' : '';
    el.innerHTML = '<span>' + icon + '</span><span>' + esc(tab.name) + '</span>' + closeBtn;
    el.onclick = function(){ activateTab(i); };
    c.appendChild(el);
  });
}
function openTab(type, id, name, avatar){
  for(var i = 0; i < openTabs.length; i++){
    if(openTabs[i].type === type && openTabs[i].id === id){ activateTab(i); return; }
  }
  openTabs.forEach(function(t){ t.active = false; });
  if(type === 'channel') openTabs = openTabs.filter(function(t){ return t.type !== 'channel'; });
  if(type === 'dm') openTabs = openTabs.filter(function(t){ return t.type !== 'dm'; });
  if(type === 'group') openTabs = openTabs.filter(function(t){ return t.type !== 'group'; });
  openTabs.push({type:type, id:id, name:name, avatar:avatar, active:true});
  renderServerTabs();
}
function activateTab(i){
  var tab = openTabs[i];
  if(!tab) return;
  openTabs.forEach(function(t){ t.active = false; });
  tab.active = true;
  renderServerTabs();
  if(tab.type === 'server') loadServerContent(tab.id, tab.name);
  else if(tab.type === 'channel') doOpenChannel(tab.id, tab.name);
  else if(tab.type === 'dm') doOpenDM(tab.id, tab.name, tab.avatar);
  else if(tab.type === 'group') doOpenGroup(tab.id, tab.name);
}
function closeTab(i){
  var tab = openTabs[i];
  if(!tab) return;
  var wasActive = tab.active;
  openTabs.splice(i, 1);
  if(wasActive && openTabs.length) activateTab(openTabs.length - 1);
  else if(!openTabs.length){ renderServerTabs(); showFriends(); }
  else renderServerTabs();
}

/* ============================================================
   DM
   ============================================================ */
async function openDM(userId, username, avatar){
  openTab('dm', userId, username, avatar);
  await doOpenDM(userId, username, avatar);
}
async function doOpenDM(userId, username, avatar){
  currentDMUser = {id:userId, username:username, avatar:avatar};
  currentChatType = 'dm';
  currentChannelId = null;
  currentGroupId = null;
  if(unreadCounts[userId]) delete unreadCounts[userId];

  var av = document.getElementById('chatWindowAvatar');
  if(avatar) av.innerHTML = '<img src="' + avatar + '" style="width:100%;height:100%;object-fit:cover;border-radius:inherit">';
  else av.textContent = username.charAt(0).toUpperCase();

  document.getElementById('chatWindowTitle').textContent = username;
  document.getElementById('messagesInner').innerHTML = '';
  document.getElementById('chatMembersBtn').style.display = 'none';
  document.getElementById('chatCallBtn').style.display = 'flex';
  var gcb = document.getElementById('chatGroupCallBtn');
  if(gcb) gcb.style.display = BC.isPremium ? 'flex' : 'none';
  document.getElementById('chatServerSettingsBtn').style.display = 'none';
  var gsb = document.getElementById('chatGroupSettingsBtn');
  if(gsb) gsb.style.display = 'none';
  var cmb = document.getElementById('chatChannelModeBtn');
  if(cmb) cmb.style.display = 'none';

  var res = await api('/dm/' + userId + '/messages?token=' + encodeURIComponent(token));
  if(res.ok){
    res.data.forEach(function(m){ addMessage(m); });
    scrollBottom();
  }
  autoFocusInput();
  if(window.innerWidth <= 768) mobileShow('chat');
}

/* ============================================================
   СООБЩЕНИЯ
   ============================================================ */
function buildMessageHTML(m){
  var pos = parsePos(m.avatar_pos);
  var uid = m.user_id || m.from_user || 0;
  var isOnline = uid !== me.id && (BC.onlineSet[uid] || m.online === true);
  var streamerCls = m.is_streamer ? ' streamer' : '';
  var avSrc = m.gif_avatar || m.avatar;
  var av;
  if(avSrc){
    av = '<div class="avatar' + (isOnline ? ' online' : '') + streamerCls + '" data-frame="' + (m.active_frame || '') + '" onclick="viewProfile(' + uid + ')"><img src="' + avSrc + '" style="object-position:' + pos.x + '% ' + pos.y + '%"></div>';
  } else {
    av = '<div class="avatar' + (isOnline ? ' online' : '') + streamerCls + '" data-frame="' + (m.active_frame || '') + '" onclick="viewProfile(' + uid + ')">' + (m.username || '?').charAt(0).toUpperCase() + '</div>';
  }
  var t = m.created_at ? new Date(m.created_at).toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'}) : '';
  var rb = buildRoleBadge(m) + buildPremiumBadge(m) + buildTitleBadge(m);
  var streamerAuthorCls = m.is_streamer ? ' streamer' : '';
  var name = '<span class="msg-author' + streamerAuthorCls + '" onclick="viewProfile(' + uid + ')">' + esc(m.username || '?') + '</span>' + rb;

  var fileHTML = '';
  if(m.file_url){
    var isV = /\.(mp4|webm|mov)$/i.test(m.file_url);
    var isA = /\.(mp3|wav|ogg|m4a)$/i.test(m.file_url);
    var isI = /\.(png|jpg|jpeg|gif|webp|svg)$/i.test(m.file_url);
    if(isV) fileHTML = '<video style="max-width:300px;max-height:200px;border-radius:12px;margin-top:8px" controls src="' + m.file_url + '"></video>';
    else if(isA) fileHTML = buildVoicePlayer(m.file_url);
    else if(isI) fileHTML = '<img style="max-width:300px;max-height:200px;border-radius:12px;margin-top:8px" src="' + m.file_url + '">';
    else fileHTML = '<a href="' + m.file_url + '" target="_blank" style="display:inline-block;padding:8px 12px;background:var(--bg-input);border:1px solid var(--border);border-radius:10px;margin-top:8px;color:var(--accent);text-decoration:none;font-weight:700;font-size:12px">📎 Скачать</a>';
  }

  var reactionsHTML = '';
  if(m.reactions){
    try {
      var r = typeof m.reactions === 'string' ? JSON.parse(m.reactions) : m.reactions;
      var keys = Object.keys(r);
      if(keys.length){
        reactionsHTML = '<div class="msg-reactions">';
        keys.forEach(function(k){
          if(r[k] && r[k].length){
            reactionsHTML += '<div class="reaction-pill' + (k.indexOf('custom:') === 0 ? ' paid' : '') + '" onclick="toggleReaction(' + m.id + ',\'' + k + '\')">' + renderReactionEmoji(k) + ' ' + r[k].length + '</div>';
          }
        });
        reactionsHTML += '</div>';
      }
    } catch(e){}
  }

  var replyHTML = '';
  if(m.reply_to){
    replyHTML = '<div class="msg-reply-quote" onclick="scrollToMsg(' + m.reply_to + ')">↪ Ответ на #' + m.reply_to + '</div>';
  }

  var editedHTML = m.edited ? ' <span class="msg-edited">(изменено)</span>' : '';

  var stickerHTML = '';
  if(m.sticker){
    var st = STICKERS.find(function(s){ return s.id === m.sticker; });
    if(st) stickerHTML = '<div class="msg-sticker">' + (st.image ? '<img src="' + st.image + '">' : st.emoji) + '</div>';
    else stickerHTML = '<div class="msg-sticker">' + m.sticker + '</div>';
  }

  var threadHTML = m.thread_count ? '<div class="msg-thread-badge" onclick="startThread(' + m.id + ')">🧵 ' + m.thread_count + ' ответов</div>' : '';
  var myMsg = uid === me.id;

  var actionsHTML = '<div class="msg-actions">' +
    '<button class="msg-action-btn" onclick="showQuickReactions(' + m.id + ',this)">😀</button>' +
    '<button class="msg-action-btn" onclick="startReply(' + m.id + ')">↪</button>' +
    '<button class="msg-action-btn" onclick="startThread(' + m.id + ')">🧵</button>' +
    (BC.isMod ? '<button class="msg-action-btn" onclick="pinMessage(' + m.id + ')">📌</button>' : '') +
    '<button class="msg-action-btn" onclick="saveMessage(' + m.id + ')">💾</button>' +
    (myMsg ? '<button class="msg-action-btn" onclick="editMessage(' + m.id + ')">✏️</button><button class="msg-action-btn" onclick="deleteMessage(' + m.id + ')">🗑️</button>' : '') +
    '</div>';

  var contentHTML = stickerHTML || ('<div class="msg-content effect-' + (m.effect || 'none') + '">' + linkify(markMentions(formatText(m.text || ''))) + '</div>');

  return av + '<div class="msg-body"><div class="msg-head">' + name + '<span class="msg-time">' + t + '</span>' + editedHTML + '</div>' + replyHTML + contentHTML + fileHTML + reactionsHTML + threadHTML + '</div>' + actionsHTML;
}

function renderReactionEmoji(k){
  if(k.indexOf('custom:') === 0){
    return '<img src="' + k.slice(7) + '" style="width:16px;height:16px;vertical-align:middle">';
  }
  return k;
}

function buildVoicePlayer(url){
  return '<div class="voice-player">' +
    '<button class="voice-play-btn" onclick="playVoiceMsg(this,\'' + url + '\')">▶</button>' +
    '<div class="voice-wave-mini">' + Array.from({length:20}).map(function(){ return '<span style="height:' + (4 + Math.random()*14) + 'px"></span>'; }).join('') + '</div>' +
    '<span>🎤</span>' +
  '</div>';
}

function playVoiceMsg(btn, url){
  var audio = new Audio(url);
  audio.play();
  btn.textContent = '⏸';
  audio.onended = function(){ btn.textContent = '▶'; };
}

function showQuickReactions(msgId, btn){
  document.querySelectorAll('.quick-reactions.show').forEach(function(q){ q.remove(); });
  var q = document.createElement('div');
  q.className = 'quick-reactions show';
  var rect = btn.getBoundingClientRect();
  q.style.left = Math.max(10, rect.left - 100) + 'px';
  q.style.top = (rect.bottom + 6) + 'px';
  QUICK_REACTIONS.forEach(function(e){
    var s = document.createElement('span');
    s.textContent = e;
    s.onclick = function(){ toggleReaction(msgId, e); q.remove(); };
    q.appendChild(s);
  });
  document.body.appendChild(q);
  setTimeout(function(){
    document.addEventListener('click', function(){ q.remove(); }, {once:true});
  }, 100);
}

function scrollBottom(){
  var c = document.getElementById('messagesBody');
  if(!c) return;
  setTimeout(function(){ c.scrollTop = c.scrollHeight; }, 10);
}
function isNearBottom(){
  var c = document.getElementById('messagesBody');
  if(!c) return true;
  return c.scrollHeight - c.scrollTop - c.clientHeight < 120;
}

function addMessage(m){
  var chat = document.getElementById('messagesInner');
  if(!chat) return;
  var stick = isNearBottom();
  var div = document.createElement('div');
  div.className = 'msg-row';
  div.id = 'msg-' + (m.id || m.temp_id);
  div.innerHTML = buildMessageHTML(m);
  chat.appendChild(div);
  msgCache[m.id] = m;
  if(stick) scrollBottom();
}

function scrollToMsg(id){
  var el = document.getElementById('msg-' + id);
  if(el){
    el.scrollIntoView({behavior:'smooth', block:'center'});
    el.style.background = 'rgba(217,70,239,0.2)';
    setTimeout(function(){ el.style.background = ''; }, 1500);
  }
}
function scrollToPinned(){ if(pinnedMsgId) scrollToMsg(pinnedMsgId); }
function renderPinned(pinned){
  var bar = document.getElementById('pinnedBar');
  if(!bar) return;
  if(!pinned || !pinned.length){ bar.classList.remove('show'); return; }
  var p = pinned[0];
  pinnedMsgId = p.id;
  bar.innerHTML = '📌 <b>' + esc(p.username) + ':</b> ' + esc((p.text || '').slice(0, 80));
  bar.classList.add('show');
}
function autoFocusInput(){
  var inp = document.getElementById('inp');
  if(inp && window.innerWidth > 768){
    setTimeout(function(){ inp.focus(); }, 100);
  }
}

function startReply(id){
  var m = msgCache[id];
  if(!m) return;
  replyTo = id;
  document.getElementById('replyBar').classList.add('show');
  document.getElementById('replyBarText').textContent = (m.username || '?') + ': ' + ((m.text || '').slice(0, 60));
  document.getElementById('inp').focus();
}
function cancelReply(){
  replyTo = null;
  var b = document.getElementById('replyBar');
  if(b) b.classList.remove('show');
}

/* ============================================================
   ОТПРАВКА
   ============================================================ */
function send(){
  var inp = document.getElementById('inp');
  var t = inp.value.trim();
  if(!t) return;
  if(currentChannelMode === 'readonly' && !BC.isMod){
    showNotice('📢 Только владелец пишет', 'warn');
    return;
  }
  var tempId = 'temp-' + Date.now();
  var fakeMsg = {
    id: tempId,
    user_id: me.id,
    username: me.username,
    avatar: me.avatar,
    gif_avatar: me.gif_avatar,
    text: t,
    created_at: new Date().toISOString(),
    is_admin: me.is_admin,
    is_moderator: me.is_moderator,
    is_beta_tester: me.is_beta_tester,
    is_streamer: me.is_streamer,
    role: me.role,
    is_scam: me.is_scam,
    is_premium: me.is_premium,
    active_frame: me.active_frame,
    title: me.title,
    reply_to: replyTo,
    effect: currentMsgEffect
  };
  var chat = document.getElementById('messagesInner');
  var div = document.createElement('div');
  div.className = 'msg-row pending';
  div.id = 'msg-' + tempId;
  div.innerHTML = buildMessageHTML(fakeMsg);
  chat.appendChild(div);
  scrollBottom();

  if(currentChatType === 'dm' && currentDMUser) wsSend({type:'dm', to_user:currentDMUser.id, text:t, temp_id:tempId});
  else if(currentChatType === 'group' && currentGroupId) wsSend({type:'group_msg', group_id:currentGroupId, text:t, temp_id:tempId});
  else if(currentChannelId) wsSend({type:'message', channel_id:currentChannelId, text:t, temp_id:tempId, reply_to:replyTo, effect:currentMsgEffect});

  inp.value = '';
  inp.style.height = 'auto';
  cancelReply();
  document.getElementById('charCounter').textContent = '0 / 2000';
}

async function editMessage(id){
  var el = document.getElementById('msg-' + id);
  if(!el) return;
  var content = el.querySelector('.msg-content');
  var old = content.textContent;
  var nw = prompt('Редакт:', old);
  if(nw === null || nw.trim() === '') return;
  var res = await api('/messages/edit', {method:'POST', body:{token:token, message_id:id, text:nw}});
  if(res.ok){
    content.innerHTML = linkify(markMentions(formatText(nw)));
    if(!el.querySelector('.msg-edited')){
      var h = el.querySelector('.msg-head');
      var sp = document.createElement('span');
      sp.className = 'msg-edited';
      sp.textContent = '(изменено)';
      h.appendChild(sp);
    }
    showNotice('✏️');
  }
}
async function deleteMessage(id){
  if(!confirm('Удалить?')) return;
  var res = await api('/messages/delete', {method:'POST', body:{token:token, message_id:id}});
  if(res.ok){
    var el = document.getElementById('msg-' + id);
    if(el) el.remove();
  }
}
async function pinMessage(id){
  var res = await api('/messages/pin', {method:'POST', body:{token:token, message_id:id}});
  if(res.ok){
    showNotice(res.data.pinned ? '📌' : '📌 Откреплено');
    if(currentChannelId){
      var rr = await api('/channels/' + currentChannelId + '/messages?token=' + encodeURIComponent(token));
      if(rr.ok) renderPinned(rr.data.pinned || []);
    }
  }
}
async function saveMessage(id){
  var res = await api('/messages/save', {method:'POST', body:{token:token, message_id:id}});
  if(res.ok) showNotice('💾 Сохранено');
}
async function toggleReaction(id, emoji){
  var res = await api('/messages/reaction', {method:'POST', body:{token:token, message_id:id, emoji:emoji}});
  if(res.ok && emoji === '🐱' && Math.random() < 0.3){
    var cat = document.createElement('div');
    cat.className = 'cat-jump';
    cat.textContent = '🐱';
    document.body.appendChild(cat);
    if(BC.catSound) BC.catSound();
    setTimeout(function(){ cat.remove(); }, 2500);
  }
}

/* ============================================================
   ФАЙЛЫ
   ============================================================ */
document.getElementById('fileInput').addEventListener('change', function(){
  uploadFile(this);
});

async function uploadFile(input){
  var f = input.files[0];
  if(!f) return;
  var fd = new FormData();
  fd.append('token', token);
  fd.append('file', f);
  try {
    var r = await fetch('/api/upload', {method:'POST', body:fd});
    var d = await r.json();
    if(d.url){
      if(currentChatType === 'dm' && currentDMUser) wsSend({type:'dm', to_user:currentDMUser.id, text:'', file_url:d.url});
      else if(currentChatType === 'group' && currentGroupId) wsSend({type:'group_msg', group_id:currentGroupId, text:'', file_url:d.url});
      else if(currentChannelId) wsSend({type:'message', channel_id:currentChannelId, text:'', file_url:d.url});
    }
  } catch(e){ showNotice('❌ Загрузка', 'error'); }
  input.value = '';
}

/* ============================================================
   ПИКЕРЫ
   ============================================================ */
document.getElementById('emojiBtn').onclick = function(){
  document.querySelectorAll('.emoji-picker').forEach(function(p){ p.remove(); });
  var p = document.createElement('div');
  p.className = 'emoji-picker';
  MY_EMOJIS.forEach(function(e){
    var s = document.createElement('span');
    s.textContent = e;
    s.onclick = function(){
      var inp = document.getElementById('inp');
      if(inp){ inp.value += e; p.remove(); inp.focus(); }
    };
    p.appendChild(s);
  });
  document.body.appendChild(p);
  setTimeout(function(){ document.addEventListener('click', function(){ p.remove(); }, {once:true}); }, 100);
};

document.getElementById('stickerBtn').onclick = async function(){
  document.querySelectorAll('.sticker-picker').forEach(function(p){ p.remove(); });
  if(!STICKERS.length){
    var sr = await api('/stickers/list');
    if(sr.ok) STICKERS = sr.data;
  }
  var p = document.createElement('div');
  p.className = 'sticker-picker';
  if(!STICKERS.length){
    p.innerHTML = '<div style="padding:20px;grid-column:1/-1;text-align:center;color:var(--text-mute);font-size:12px">Пока нет стикеров 😢</div>';
  } else {
    STICKERS.forEach(function(s){
      var el = document.createElement('div');
      el.className = 'sticker-item';
      el.innerHTML = s.image ? '<img src="' + s.image + '">' : s.emoji;
      el.onclick = function(){ sendSticker(s.id); p.remove(); };
      p.appendChild(el);
    });
  }
  document.body.appendChild(p);
  setTimeout(function(){ document.addEventListener('click', function(){ p.remove(); }, {once:true}); }, 100);
};

function sendSticker(id){
  var payload = {type:'sticker', sticker:id};
  if(currentChannelId) payload.channel_id = currentChannelId;
  else if(currentGroupId) payload.group_id = currentGroupId;
  else return;
  wsSend(payload);
}

document.getElementById('customReactBtn').onclick = async function(){
  document.querySelectorAll('.sticker-picker').forEach(function(p){ p.remove(); });
  var res = await api('/reactions/custom/list?token=' + encodeURIComponent(token));
  var p = document.createElement('div');
  p.className = 'sticker-picker';
  var list = (res.ok && res.data) || [];
  if(!list.length){
    p.innerHTML = '<div style="padding:20px;grid-column:1/-1;text-align:center;color:var(--text-mute);font-size:12px">Нет кастомных реакций 😢</div>';
  } else {
    list.forEach(function(c){
      var el = document.createElement('div');
      el.className = 'sticker-item';
      el.innerHTML = '<img src="' + c.url + '">';
      el.onclick = function(){
        var payload = {type:'sticker', sticker:'custom:' + c.url};
        if(currentChannelId) payload.channel_id = currentChannelId;
        else if(currentGroupId) payload.group_id = currentGroupId;
        wsSend(payload);
        p.remove();
      };
      p.appendChild(el);
    });
  }
  document.body.appendChild(p);
  setTimeout(function(){ document.addEventListener('click', function(){ p.remove(); }, {once:true}); }, 100);
};

/* ============================================================
   ГОЛОСОВЫЕ
   ============================================================ */
document.getElementById('voiceBtn').onclick = function(){
  if(!navigator.mediaDevices){ showNotice('❌ Микрофон недоступен', 'error'); return; }
  navigator.mediaDevices.getUserMedia({audio:true}).then(function(stream){
    voiceChunks = [];
    voiceMediaRecorder = new MediaRecorder(stream);
    voiceMediaRecorder.ondataavailable = function(e){ if(e.data.size > 0) voiceChunks.push(e.data); };
    voiceMediaRecorder.start();
    voiceStartTime = Date.now();
    document.getElementById('voiceRecordBar').classList.add('show');
    var wave = document.getElementById('voiceWave');
    wave.innerHTML = '';
    for(var i = 0; i < 15; i++){
      var sp = document.createElement('span');
      sp.style.animationDelay = (i * 0.05) + 's';
      wave.appendChild(sp);
    }
    voiceTimer = setInterval(function(){
      var s = Math.floor((Date.now() - voiceStartTime) / 1000);
      document.getElementById('voiceRecTimer').textContent = String(Math.floor(s/60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
    }, 200);
  }).catch(function(){ showNotice('❌ Микрофон недоступен', 'error'); });
};

document.getElementById('voiceSendBtn').onclick = function(){
  if(!voiceMediaRecorder) return;
  voiceMediaRecorder.onstop = async function(){
    if(voiceTimer) clearInterval(voiceTimer);
    document.getElementById('voiceRecordBar').classList.remove('show');
    var blob = new Blob(voiceChunks, {type:'audio/webm'});
    voiceChunks = [];
    var fd = new FormData();
    fd.append('token', token);
    fd.append('file', blob, 'voice.webm');
    try {
      var r = await fetch('/api/upload', {method:'POST', body:fd});
      var d = await r.json();
      if(d.url){
        if(currentChatType === 'dm' && currentDMUser) wsSend({type:'dm', to_user:currentDMUser.id, text:'', file_url:d.url});
        else if(currentChatType === 'group' && currentGroupId) wsSend({type:'group_msg', group_id:currentGroupId, text:'', file_url:d.url});
        else if(currentChannelId) wsSend({type:'message', channel_id:currentChannelId, text:'', file_url:d.url});
        showNotice('🎤 Отправлено');
      }
    } catch(e){ showNotice('❌', 'error'); }
    voiceMediaRecorder = null;
  };
  voiceMediaRecorder.stop();
};

/* ============================================================
   ТРЕДЫ
   ============================================================ */
var currentThreadRoot = null;
function startThread(msgId){
  currentThreadRoot = msgId;
  document.getElementById('threadModal').classList.add('open');
  loadThread(msgId);
}
async function loadThread(msgId){
  var root = msgCache[msgId];
  if(root){
    document.getElementById('threadRootMessage').innerHTML =
      '<div style="font-weight:800;margin-bottom:4px">' + esc(root.username) + '</div>' +
      '<div>' + linkify(markMentions(formatText(root.text || ''))) + '</div>';
  }
  var res = await api('/threads/' + msgId + '?token=' + encodeURIComponent(token));
  var c = document.getElementById('threadMessages');
  if(!res.ok || !res.data.length){
    c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:12px">Пока пусто</div>';
    return;
  }
  c.innerHTML = res.data.map(function(m){
    return '<div style="display:flex;gap:8px;padding:8px;background:var(--bg-input);border-radius:8px;margin-bottom:4px">' +
      '<div style="font-weight:800;font-size:12px">' + esc(m.username) + ':</div>' +
      '<div style="font-size:12px">' + esc(m.text) + '</div>' +
    '</div>';
  }).join('');
  c.scrollTop = c.scrollHeight;
}
function sendThreadReply(){
  var t = document.getElementById('threadInput').value.trim();
  if(!t || !currentThreadRoot) return;
  api('/threads/' + currentThreadRoot + '/reply', {method:'POST', body:{token:token, text:t}}).then(function(res){
    if(res.ok){
      document.getElementById('threadInput').value = '';
      loadThread(currentThreadRoot);
    }
  });
}

/* ============================================================
   WS-ОБРАБОТЧИКИ
   ============================================================ */
document.addEventListener('ws:any', function(e){
  var data = e.detail;
  var t = data.type;

  if(t === 'message'){
    if(data.temp_id){
      var el = document.getElementById('msg-' + data.temp_id);
      if(el) el.remove();
    }
    if(data.channel_id === currentChannelId){
      addMessage(data);
      if(BC.playMsgSound) BC.playMsgSound();
    }
  }
  else if(t === 'dm'){
    if(data.temp_id){
      var el2 = document.getElementById('msg-' + data.temp_id);
      if(el2) el2.remove();
    }
    if(currentDMUser && (data.from_user === currentDMUser.id || data.to_user === currentDMUser.id)){
      addMessage(data);
      if(data.from_user !== me.id && BC.playMsgSound) BC.playMsgSound();
    } else if(data.from_user !== me.id){
      unreadCounts[data.from_user] = (unreadCounts[data.from_user] || 0) + 1;
      showNotice('💬 ' + data.username + ': ' + (data.text || '📎'));
      if(BC.playMsgSound) BC.playMsgSound();
    }
  }
  else if(t === 'group_msg'){
    if(data.temp_id){
      var el3 = document.getElementById('msg-' + data.temp_id);
      if(el3) el3.remove();
    }
    if(currentGroupId && data.group_id === currentGroupId){
      addMessage(data);
      if(data.user_id !== me.id && BC.playMsgSound) BC.playMsgSound();
    }
  }
  else if(t === 'sticker'){
    if(data.channel_id && data.channel_id === currentChannelId){
      addMessage({id:'sticker-' + Date.now(), user_id:data.user_id, username:data.username, sticker:data.sticker, created_at:data.created_at});
    }
  }
  else if(t === 'message_deleted'){
    var el4 = document.getElementById('msg-' + data.id);
    if(el4) el4.remove();
  }
  else if(t === 'message_edited'){
    var el5 = document.getElementById('msg-' + data.id);
    if(el5){
      var ct = el5.querySelector('.msg-content');
      if(ct) ct.innerHTML = linkify(markMentions(formatText(data.text)));
    }
  }
  else if(t === 'reaction_update'){
    var el6 = document.getElementById('msg-' + data.id);
    if(el6){
      var r = el6.querySelector('.msg-reactions');
      if(!r){
        r = document.createElement('div');
        r.className = 'msg-reactions';
        el6.querySelector('.msg-body').appendChild(r);
      }
      r.innerHTML = '';
      var keys = Object.keys(data.reactions || {});
      keys.forEach(function(k){
        if(data.reactions[k] && data.reactions[k].length){
          var p = document.createElement('div');
          p.className = 'reaction-pill';
          p.textContent = k + ' ' + data.reactions[k].length;
          p.onclick = function(){ toggleReaction(data.id, k); };
          r.appendChild(p);
        }
      });
    }
  }
  else if(t === 'typing'){
    if(data.channel_id === currentChannelId) showTyping(data.username);
  }
  else if(t === 'typing_dm'){
    if(currentDMUser && data.from === currentDMUser.id) showTyping(data.username);
  }
  else if(t === 'online_list'){
    BC.onlineSet = {};
    (data.users || []).forEach(function(id){ BC.onlineSet[id] = true; });
  }
  else if(t === 'user_online'){
    BC.onlineSet[data.user_id] = true;
  }
  else if(t === 'user_offline'){
    delete BC.onlineSet[data.user_id];
  }
  else if(t === 'friend_accepted'){
    showNotice('👥 ' + data.username);
    if(currentChatType === 'friends') showFriends();
    updateFriendsBadge();
  }
  else if(t === 'friend_request'){
    showNotice('📩 ' + data.username);
    if(currentChatType === 'friends') showFriends();
    updateFriendsBadge();
  }
  else if(t === 'friend_declined' || t === 'friend_removed'){
    if(currentChatType === 'friends') showFriends();
  }
  else if(t === 'group_added'){
    showNotice('👥 ' + data.name);
    loadGroups();
  }
  else if(t === 'group_kicked'){
    showNotice('🚪 Кикнут', 'warn');
    if(currentGroupId === data.group_id){
      currentGroupId = null;
      loadGroups();
      showFriends();
    }
  }
  else if(t === 'sticker_added'){
    STICKERS = [];
  }
});

function showTyping(name){
  var el = document.getElementById('typingIndicator');
  if(!el) return;
  el.textContent = name + ' печатает...';
  clearTimeout(currentTyping.timer);
  currentTyping.timer = setTimeout(function(){ el.textContent = ''; }, 3000);
}

/* ============================================================
   INP EVENTS
   ============================================================ */
document.getElementById('inp').addEventListener('keydown', function(e){
  if(e.key === 'Enter' && !e.shiftKey){
    e.preventDefault();
    send();
  }
});
document.getElementById('inp').addEventListener('input', function(){
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
  document.getElementById('charCounter').textContent = this.value.length + ' / 2000';
  if(currentChatType === 'dm' && currentDMUser) wsSend({type:'typing_dm', to_user:currentDMUser.id});
  else if(currentChannelId) wsSend({type:'typing', channel_id:currentChannelId});
});

/* ============================================================
   CREATE MENU
   ============================================================ */
function openCreateMenu(){
  document.getElementById('createMenuModal').classList.add('open');
}
async function chooseCreate(type){
  document.getElementById('createMenuModal').classList.remove('open');
  if(type === 'server'){
    var n = prompt('Имя сервера:');
    if(!n) return;
    var res = await api('/servers/create', {method:'POST', body:{token:token, name:n}});
    if(res.ok){ showNotice('✅ Создан'); loadServers(); }
  } else if(type === 'group'){
    openCreateGroup();
  }
}

/* ============================================================
   ИНИЦИАЛИЗАЦИЯ
   ============================================================ */
document.addEventListener('user-entered', function(){
  loadGroups();
  loadServers();
  showFriends();
  updateFriendsBadge();
  setInterval(updateFriendsBadge, 30000);

  document.getElementById('chatListSearchInput').addEventListener('input', function(){
    var q = this.value.toLowerCase();
    document.querySelectorAll('.chat-item').forEach(function(i){
      var n = (i.querySelector('.chat-item-name') || {}).textContent || '';
      i.style.display = n.toLowerCase().indexOf(q) !== -1 ? 'flex' : 'none';
    });
  });
});

document.addEventListener('ws:any', function(){
  if(currentChatType === 'friends'){ /* обновление при желании */ }
});

// Экспортируем глобально
window.showFriends = showFriends;
window.openDM = openDM;
window.openGroup = openGroup;
window.openServer = openServer;
window.openChannel = openChannel;
window.openMembers = openMembers;
window.openServerSettings = openServerSettings;
window.openGroupSettings = openGroupSettings;
window.openChannelMode = openChannelMode;
window.saveChannelMode = saveChannelMode;
window.saveServerSettings = saveServerSettings;
window.saveGroupSettings = saveGroupSettings;
window.leaveServer = leaveServer;
window.leaveGroup = leaveGroup;
window.deleteServer = deleteServer;
window.regenInvite = regenInvite;
window.copyInvite = copyInvite;
window.createChannelInline = createChannelInline;
window.createGroup = createGroup;
window.openCreateGroup = openCreateGroup;
window.groupAddMember = groupAddMember;
window.groupKick = groupKick;
window.openCreateMenu = openCreateMenu;
window.chooseCreate = chooseCreate;
window.acceptFriend = acceptFriend;
window.declineFriend = declineFriend;
window.cancelRequest = cancelRequest;
window.removeFriend = removeFriend;
window.promptAddFriend = promptAddFriend;
window.startReply = startReply;
window.cancelReply = cancelReply;
window.editMessage = editMessage;
window.deleteMessage = deleteMessage;
window.pinMessage = pinMessage;
window.saveMessage = saveMessage;
window.toggleReaction = toggleReaction;
window.showQuickReactions = showQuickReactions;
window.scrollToMsg = scrollToMsg;
window.scrollToPinned = scrollToPinned;
window.startThread = startThread;
window.sendThreadReply = sendThreadReply;
window.playVoiceMsg = playVoiceMsg;
window.buildMessageHTML = buildMessageHTML;
window.addMessage = addMessage;
window.renderServerTabs = renderServerTabs;
window.closeTab = closeTab;
window.activateTab = activateTab;
window.autoFocusInput = autoFocusInput;
window.scrollBottom = scrollBottom;

console.log('[BC] features/chat loaded');
