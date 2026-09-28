/* ============================================================
   BELUGACORD 2.5 — MODULE: SOCIAL
   Сторис + звонки (1v1 + групповые)
   ============================================================ */

/* ============================================================
   СТОРИС
   ============================================================ */
var currentStoryList = [], currentStoryIndex = 0, storyTimer = null, storyBg = '#d946ef';

function openStoriesFeed(){
  document.getElementById('storiesFeedModal').classList.add('open');
  loadStoriesFeed();
}

async function loadStoriesFeed(){
  var res = await api('/stories/list?token=' + encodeURIComponent(token));
  var c = document.getElementById('storiesFeedList');
  if(!res.ok || !res.data.length){
    c.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:20px">Нет сторис 😢</div>';
    return;
  }
  currentStoryList = res.data;
  c.innerHTML = res.data.map(function(s, i){
    return '<div style="display:flex;align-items:center;gap:12px;padding:10px;background:var(--bg-input);border-radius:12px;margin-bottom:6px;cursor:pointer" onclick="openStoryViewer(' + i + ')">' +
      '<div style="width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent-2));overflow:hidden">' +
        '<img src="' + (s.avatar || '') + '" style="width:100%;height:100%;object-fit:cover">' +
      '</div>' +
      '<div style="flex:1">' +
        '<div style="font-weight:800">' + esc(s.username) + '</div>' +
        '<div style="font-size:11px;color:var(--text-mute)">' + timeAgo(s.created_at) + '</div>' +
      '</div>' +
    '</div>';
  }).join('');
}

function openStoryViewer(i){
  currentStoryIndex = i;
  document.getElementById('storiesFeedModal').classList.remove('open');
  document.getElementById('storiesModal').classList.add('open');
  showStory();
}

function showStory(){
  var s = currentStoryList[currentStoryIndex];
  if(!s){ closeStories(); return; }
  document.getElementById('storyName').textContent = s.username;
  document.getElementById('storyTime').textContent = timeAgo(s.created_at);
  var av = document.getElementById('storyAvatar');
  if(s.avatar) av.innerHTML = '<img src="' + s.avatar + '">';
  else av.textContent = s.username.charAt(0).toUpperCase();

  var img = document.getElementById('storyImage');
  var txt = document.getElementById('storyText');
  if(s.image){ img.src = s.image; img.style.display = 'block'; }
  else img.style.display = 'none';
  txt.textContent = s.text || '';
  document.getElementById('storyContent').style.background = s.bg_color || '#000';

  var r = document.getElementById('storyReactions');
  r.innerHTML = ['❤️','🔥','😂','😮','😢'].map(function(e){
    return '<span onclick="reactStory(\'' + e + '\')">' + e + '</span>';
  }).join('');

  var fill = document.getElementById('storyProgressFill');
  fill.style.width = '0%';
  if(storyTimer) clearInterval(storyTimer);
  var start = Date.now();
  storyTimer = setInterval(function(){
    var pct = Math.min(100, ((Date.now() - start) / 5000) * 100);
    fill.style.width = pct + '%';
    if(pct >= 100){ clearInterval(storyTimer); nextStory(); }
  }, 100);
}

function nextStory(){
  if(currentStoryIndex < currentStoryList.length - 1){ currentStoryIndex++; showStory(); }
  else closeStories();
}
function prevStory(){
  if(currentStoryIndex > 0){ currentStoryIndex--; showStory(); }
}
function closeStories(){
  if(storyTimer) clearInterval(storyTimer);
  document.getElementById('storiesModal').classList.remove('open');
}
function reactStory(emoji){
  var s = currentStoryList[currentStoryIndex];
  if(!s) return;
  api('/stories/react', {method:'POST', body:{token:token, story_id:s.id, emoji:emoji}});
}
function sendStoryReply(){
  var t = document.getElementById('storyReplyInput').value.trim();
  var s = currentStoryList[currentStoryIndex];
  if(!t || !s) return;
  api('/stories/reply', {method:'POST', body:{token:token, story_id:s.id, text:t}}).then(function(res){
    if(res.ok){ showNotice('📤'); document.getElementById('storyReplyInput').value = ''; }
  });
}
function openCreateStory(){
  document.getElementById('createStoryModal').classList.add('open');
  document.getElementById('storiesFeedModal').classList.remove('open');
}
function pickStoryBg(c){ storyBg = c; }

async function publishStory(){
  var url = document.getElementById('storyImageUrl').value.trim();
  var txt = document.getElementById('storyTextInput').value.trim();
  var f = document.getElementById('storyImageFile').files[0];
  var imageUrl = url;
  if(f){
    var fd = new FormData();
    fd.append('token', token);
    fd.append('file', f);
    try {
      var r = await fetch('/api/upload', {method:'POST', body:fd});
      var d = await r.json();
      imageUrl = d.url;
    } catch(e){}
  }
  if(!imageUrl && !txt){ showNotice('⚠️ Пусто', 'warn'); return; }
  var res = await api('/stories/create', {method:'POST', body:{token:token, image:imageUrl, text:txt, bg_color:storyBg}});
  if(res.ok){
    showNotice('📸 Опубликовано');
    document.getElementById('createStoryModal').classList.remove('open');
  }
}

/* ============================================================
   ЗВОНКИ — WebRTC
   ============================================================ */
var callPC = null, callLocalStream = null, callScreenStream = null;
var callTarget = null, callType = null, callTimer = null, callSeconds = 0;
var micOn = true, camOn = false, shareOn = false;
var pendingOffer = null, pendingFrom = null, pendingFromName = null, pendingFromAvatar = null;
var callRemoteAudioEl = null;
var groupCallRoom = null, groupCallLocalStream = null, groupCallMuted = false;

var CALL_ICE = {iceServers:[
  {urls:'stun:stun.l.google.com:19302'},
  {urls:'stun:stun1.l.google.com:19302'},
  {urls:'turn:openrelay.metered.ca:80', username:'openrelayproject', credential:'openrelayproject'},
  {urls:'turn:openrelay.metered.ca:443', username:'openrelayproject', credential:'openrelayproject'}
]};

function ensureRemoteAudio(){
  if(!callRemoteAudioEl){
    callRemoteAudioEl = document.createElement('audio');
    callRemoteAudioEl.autoplay = true;
    callRemoteAudioEl.setAttribute('playsinline', '');
    callRemoteAudioEl.volume = 1.0;
    document.body.appendChild(callRemoteAudioEl);
  }
  return callRemoteAudioEl;
}

function attachRemoteStream(stream){
  var audio = ensureRemoteAudio();
  audio.srcObject = stream;
  audio.play().catch(function(){});
  if(stream.getVideoTracks().length > 0){
    var v = document.getElementById('callRemoteVideo');
    if(v){
      v.srcObject = stream;
      v.play().catch(function(){});
      document.getElementById('callBannerVideo').classList.add('show');
    }
  }
}

async function enumerateDevices(){
  try {
    var list = await navigator.mediaDevices.enumerateDevices();
    var mics = list.filter(function(d){ return d.kind === 'audioinput'; });
    var spk = list.filter(function(d){ return d.kind === 'audiooutput'; });
    var cams = list.filter(function(d){ return d.kind === 'videoinput'; });
    var mSel = document.getElementById('micSelect');
    var sSel = document.getElementById('speakerSelect');
    var cSel = document.getElementById('camSelect');
    if(mSel) mSel.innerHTML = mics.map(function(d, i){ return '<option value="' + d.deviceId + '">' + (d.label || ('Мик ' + (i+1))) + '</option>'; }).join('');
    if(sSel) sSel.innerHTML = spk.length ? spk.map(function(d, i){ return '<option value="' + d.deviceId + '">' + (d.label || ('Дин ' + (i+1))) + '</option>'; }).join('') : '<option>По умолчанию</option>';
    if(cSel) cSel.innerHTML = cams.map(function(d, i){ return '<option value="' + d.deviceId + '">' + (d.label || ('Кам ' + (i+1))) + '</option>'; }).join('');
  } catch(e){}
}

function renderCallBannerControls(){
  var c = document.getElementById('callBannerControls');
  if(!c) return;
  var html = '';
  if(callType === 'incoming'){
    html = '<button class="call-btn green" onclick="acceptCall()">📞</button><button class="call-btn red" onclick="declineCall()">📵</button>';
  } else if(callType === 'outgoing'){
    html = '<button class="call-btn" onclick="toggleMic()">🎤</button><button class="call-btn" onclick="toggleCam()">📷</button><button class="call-btn red" onclick="endCall()">📵</button>';
  } else if(callType === 'active'){
    html = '<button class="call-btn' + (micOn ? ' active' : '') + '" id="btnMic" onclick="toggleMic()">🎤</button>' +
      '<button class="call-btn' + (camOn ? ' active' : '') + '" id="btnCam" onclick="toggleCam()">📷</button>' +
      '<button class="call-btn' + (shareOn ? ' active' : '') + '" id="btnShare" onclick="toggleShare()">🖥️</button>' +
      '<button class="call-btn" onclick="toggleDeviceMenuInline()">🎛️</button>' +
      '<button class="call-btn red" onclick="endCall()">📵</button>';
  }
  c.innerHTML = html;
}

function toggleDeviceMenuInline(){
  var m = document.getElementById('callDeviceMenuInline');
  m.classList.toggle('show');
  if(m.classList.contains('show')) enumerateDevices();
}

function showCallBanner(){ document.getElementById('callBanner').classList.add('show'); }
function hideCallBanner(){
  document.getElementById('callBanner').classList.remove('show');
  document.getElementById('callDeviceMenuInline').classList.remove('show');
}

function setCallBannerAvatar(av, url, username){
  if(!av) return;
  if(url) av.innerHTML = '<img src="' + url + '">';
  else av.textContent = (username || '?').charAt(0).toUpperCase();
}

async function startCallDM(){
  if(!currentDMUser){ showNotice('⚠️ Открой DM', 'warn'); return; }
  callTarget = {id:currentDMUser.id, username:currentDMUser.username, avatar:currentDMUser.avatar};
  callType = 'outgoing';
  var cbh = document.getElementById('callBannerHeader');
  cbh.innerHTML = '<div class="call-banner-avatar ringing" id="callBannerAvatar">?</div>' +
    '<div class="call-banner-info"><div class="call-banner-name" id="callBannerName">' + esc(callTarget.username) + '</div>' +
    '<div class="call-banner-status" id="callBannerStatus">Исходящий...</div></div>';
  setCallBannerAvatar(document.getElementById('callBannerAvatar'), callTarget.avatar, callTarget.username);
  renderCallBannerControls();
  showCallBanner();
  document.getElementById('callBanner').classList.add('calling');
  try {
    callLocalStream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true, noiseSuppression:true}, video:false});
    callPC = new RTCPeerConnection(CALL_ICE);
    callLocalStream.getTracks().forEach(function(t){ callPC.addTrack(t, callLocalStream); });
    callPC.onicecandidate = function(e){ if(e.candidate) wsSend({type:'call_ice', to:callTarget.id, candidate:e.candidate}); };
    callPC.ontrack = function(e){ attachRemoteStream(e.streams[0]); };
    var off = await callPC.createOffer({offerToReceiveAudio:true, offerToReceiveVideo:true});
    await callPC.setLocalDescription(off);
    wsSend({type:'call_offer', to:callTarget.id, sdp:off});
    if(BC.callRingSound) BC.callRingSound();
  } catch(e){
    showNotice('❌ Нет микрофона', 'error');
    cleanupCall();
  }
}

async function acceptCall(){
  if(!pendingOffer) return;
  callTarget = {id:pendingFrom, username:pendingFromName, avatar:pendingFromAvatar};
  callType = 'active';
  document.getElementById('callBanner').classList.remove('incoming');
  renderCallBannerControls();
  showCallBanner();
  try {
    callLocalStream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true, noiseSuppression:true}, video:false});
    callPC = new RTCPeerConnection(CALL_ICE);
    callLocalStream.getTracks().forEach(function(t){ callPC.addTrack(t, callLocalStream); });
    callPC.onicecandidate = function(e){ if(e.candidate) wsSend({type:'call_ice', to:callTarget.id, candidate:e.candidate}); };
    callPC.ontrack = function(e){ attachRemoteStream(e.streams[0]); };
    await callPC.setRemoteDescription(new RTCSessionDescription(pendingOffer));
    var ans = await callPC.createAnswer();
    await callPC.setLocalDescription(ans);
    wsSend({type:'call_answer', to:callTarget.id, sdp:ans});
    startCallTimer();
    pendingOffer = null;
  } catch(e){ showNotice('❌', 'error'); cleanupCall(); }
}

function declineCall(){
  if(callTarget) wsSend({type:'call_decline', to:callTarget.id});
  cleanupCall();
}
function endCall(){
  if(callTarget) wsSend({type:'call_end', to:callTarget.id});
  cleanupCall();
}

function cleanupCall(){
  if(BC.callEndSound) BC.callEndSound();
  if(callRemoteAudioEl){ try { callRemoteAudioEl.pause(); callRemoteAudioEl.srcObject = null; } catch(e){} }
  if(callTimer){ clearInterval(callTimer); callTimer = null; }
  if(callPC){ try { callPC.close(); } catch(e){} callPC = null; }
  if(callLocalStream){ callLocalStream.getTracks().forEach(function(t){ t.stop(); }); callLocalStream = null; }
  if(callScreenStream){ callScreenStream.getTracks().forEach(function(t){ t.stop(); }); callScreenStream = null; }
  callSeconds = 0;
  micOn = true; camOn = false; shareOn = false;
  callTarget = null; callType = null; pendingOffer = null;
  hideCallBanner();
  document.getElementById('callBanner').classList.remove('calling', 'incoming');
  document.getElementById('callBannerVideo').classList.remove('show');
}

function startCallTimer(){
  callSeconds = 0;
  if(callTimer) clearInterval(callTimer);
  callTimer = setInterval(function(){
    callSeconds++;
    var m = Math.floor(callSeconds / 60), s = callSeconds % 60;
    var el = document.getElementById('callBannerTimer');
    if(el) el.textContent = (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }, 1000);
}

async function toggleMic(){
  if(!callLocalStream) return;
  micOn = !micOn;
  callLocalStream.getAudioTracks().forEach(function(t){ t.enabled = micOn; });
  var b = document.getElementById('btnMic');
  if(b) b.classList.toggle('active', micOn);
}

async function toggleCam(){
  if(camOn){
    if(callLocalStream){
      callLocalStream.getVideoTracks().forEach(function(t){ t.stop(); callLocalStream.removeTrack(t); });
    }
    camOn = false;
    var b = document.getElementById('btnCam');
    if(b) b.classList.remove('active');
    return;
  }
  try {
    var stream = await navigator.mediaDevices.getUserMedia({video:true});
    camOn = true;
    var vt = stream.getVideoTracks()[0];
    if(callLocalStream) callLocalStream.addTrack(vt);
    if(callPC) callPC.addTrack(vt, callLocalStream || stream);
    var b = document.getElementById('btnCam');
    if(b) b.classList.add('active');
  } catch(e){}
}

async function toggleShare(){
  if(shareOn){
    if(callScreenStream){
      callScreenStream.getTracks().forEach(function(t){ t.stop(); callScreenStream.removeTrack(t); });
    }
    shareOn = false;
    var b = document.getElementById('btnShare');
    if(b) b.classList.remove('active');
    return;
  }
  try {
    var stream = await navigator.mediaDevices.getDisplayMedia({video:true, audio:true});
    shareOn = true;
    callScreenStream = stream;
    var vt = stream.getVideoTracks()[0];
    var at = stream.getAudioTracks()[0];
    if(callPC){
      callPC.addTrack(vt, stream);
      if(at) callPC.addTrack(at, stream);
    }
    var b = document.getElementById('btnShare');
    if(b) b.classList.add('active');
    vt.onended = function(){ if(shareOn) toggleShare(); };
  } catch(e){}
}

/* ============================================================
   ГРУППОВОЙ ЗВОНОК
   ============================================================ */
async function startGroupCallFromChat(){
  if(!BC.isPremium){ showNotice('💎 Только премиум', 'warn'); return; }
  if(!currentDMUser && !currentGroupId){ showNotice('⚠️ Открой чат', 'warn'); return; }
  var res = await api('/calls/group/create', {method:'POST', body:{token:token}});
  if(!res.ok){ showNotice('❌ ' + res.error, 'error'); return; }
  if(currentDMUser) wsSend({type:'dm', to_user:currentDMUser.id, text:'📞 Групповой звонок! Код: ' + res.data.room_code});
  joinGroupCall(res.data.room_id, res.data.room_code);
}

async function joinGroupCall(roomId, roomCode){
  groupCallRoom = {id:roomId, code:roomCode};
  document.getElementById('groupCallModal').classList.add('open');
  document.getElementById('groupCallCode').textContent = 'Код: ' + roomCode;
  try {
    groupCallLocalStream = await navigator.mediaDevices.getUserMedia({audio:true, video:false});
  } catch(e){ showNotice('❌ Нет микрофона', 'error'); return; }
  renderGroupCallTiles([{id:me.id, username:me.username, avatar:me.avatar, self:true}]);
  renderGroupCallControls();
  var r = await api('/calls/group/state?room_code=' + roomCode + '&token=' + encodeURIComponent(token));
  if(r.ok && r.data.participants) updateGroupCallParticipants(r.data.participants);
}

function renderGroupCallTiles(participants){
  var grid = document.getElementById('groupCallGrid');
  if(!grid) return;
  document.getElementById('groupCallCount').textContent = participants.length + '/30';
  grid.innerHTML = participants.map(function(p){
    var avSrc = p.avatar;
    var inner = avSrc ? '<img src="' + avSrc + '" style="width:80px;height:80px;border-radius:50%;object-fit:cover">' : (p.username || '?').charAt(0).toUpperCase();
    return '<div style="aspect-ratio:1;background:#000;border-radius:12px;position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center">' +
      '<div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;font-size:44px;font-weight:900;color:#fff">' + inner + '</div>' +
      '<div style="position:absolute;bottom:6px;left:6px;background:rgba(0,0,0,0.7);color:#fff;padding:3px 8px;border-radius:6px;font-size:10px;font-weight:700">' + esc(p.username) + (p.self ? ' (ты)' : '') + '</div>' +
    '</div>';
  }).join('');
}

function updateGroupCallParticipants(list){
  var withSelf = [{id:me.id, username:me.username, avatar:me.avatar, self:true}];
  list.forEach(function(p){ if(p.id !== me.id) withSelf.push({id:p.id, username:p.username, avatar:p.avatar}); });
  renderGroupCallTiles(withSelf);
}

function renderGroupCallControls(){
  var c = document.getElementById('groupCallControls');
  if(!c) return;
  c.innerHTML =
    '<button class="call-btn' + (groupCallMuted ? ' red' : ' active') + '" onclick="toggleGroupMic()">' + (groupCallMuted ? '🔇' : '🎤') + '</button>' +
    '<button class="call-btn red" onclick="closeGroupCall()">📵</button>';
}

function toggleGroupMic(){
  groupCallMuted = !groupCallMuted;
  if(groupCallLocalStream){
    groupCallLocalStream.getAudioTracks().forEach(function(t){ t.enabled = !groupCallMuted; });
  }
  renderGroupCallControls();
}

async function closeGroupCall(){
  if(groupCallRoom){
    await api('/calls/group/leave', {method:'POST', body:{token:token, room_code:groupCallRoom.code}});
  }
  if(groupCallLocalStream){
    groupCallLocalStream.getTracks().forEach(function(t){ t.stop(); });
    groupCallLocalStream = null;
  }
  groupCallRoom = null;
  document.getElementById('groupCallModal').classList.remove('open');
}

/* ============================================================
   WS ОБРАБОТЧИКИ ЗВОНКОВ
   ============================================================ */
document.addEventListener('ws:call_offer', function(e){
  var data = e.detail;
  pendingOffer = data.sdp;
  pendingFrom = data.from;
  pendingFromName = data.username;
  pendingFromAvatar = data.avatar;
  callType = 'incoming';
  var cbh = document.getElementById('callBannerHeader');
  cbh.innerHTML = '<div class="call-banner-avatar ringing" id="callBannerAvatar">?</div>' +
    '<div class="call-banner-info"><div class="call-banner-name" id="callBannerName">' + esc(data.username || '?') + '</div>' +
    '<div class="call-banner-status" id="callBannerStatus">Звонит вам...</div></div>';
  setCallBannerAvatar(document.getElementById('callBannerAvatar'), data.avatar, data.username);
  renderCallBannerControls();
  showCallBanner();
  document.getElementById('callBanner').classList.add('incoming');
  if(BC.callRingSound) BC.callRingSound();
});

document.addEventListener('ws:call_answer', function(e){
  var data = e.detail;
  if(callPC && callType === 'outgoing'){
    callPC.setRemoteDescription(new RTCSessionDescription(data.sdp)).then(function(){
      callType = 'active';
      renderCallBannerControls();
      startCallTimer();
      document.getElementById('callBanner').classList.remove('calling');
    });
  }
});

document.addEventListener('ws:call_ice', function(e){
  var data = e.detail;
  if(callPC && data.candidate) callPC.addIceCandidate(new RTCIceCandidate(data.candidate)).catch(function(){});
});

document.addEventListener('ws:call_decline', function(){
  showNotice('📵 Отклонён', 'warn');
  cleanupCall();
});

document.addEventListener('ws:call_end', function(){
  showNotice('📵 Завершён', 'warn');
  cleanupCall();
});

/* ============================================================
   ЭКСПОРТ
   ============================================================ */
window.openStoriesFeed = openStoriesFeed;
window.openStoryViewer = openStoryViewer;
window.nextStory = nextStory;
window.prevStory = prevStory;
window.closeStories = closeStories;
window.reactStory = reactStory;
window.sendStoryReply = sendStoryReply;
window.openCreateStory = openCreateStory;
window.pickStoryBg = pickStoryBg;
window.publishStory = publishStory;
window.startCallDM = startCallDM;
window.acceptCall = acceptCall;
window.declineCall = declineCall;
window.endCall = endCall;
window.toggleMic = toggleMic;
window.toggleCam = toggleCam;
window.toggleShare = toggleShare;
window.toggleDeviceMenuInline = toggleDeviceMenuInline;
window.startGroupCallFromChat = startGroupCallFromChat;
window.joinGroupCall = joinGroupCall;
window.toggleGroupMic = toggleGroupMic;
window.closeGroupCall = closeGroupCall;

console.log('[BC] features/social loaded');
