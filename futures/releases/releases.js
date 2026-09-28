
/* ============================================================
   BELUGACORD 2.5 — MODULE: RELEASES
   Hot-swap обновлений: проверка версии, показ модалки, панель владельца
   ============================================================ */

var RELEASE_CHECK_INTERVAL = 30000; // 30 сек
var _releaseTimer = null;
var _lastRelease = null;

/* ============================================================
   ПРОВЕРКА ВЕРСИИ
   ============================================================ */
async function checkRelease(){
  try {
    var r = await fetch('/api/version');
    if(!r.ok) return;
    var d = await r.json();

    // Сохраняем состояние
    BC.flags.release = d;

    // Если релиз не активен — ничего не делаем
    if(!d.active){
      // Скрываем индикатор, если был
      var ind = document.getElementById('releaseIndicator');
      if(ind) ind.style.display = 'none';
      return;
    }

    // Если версия совпадает с той что юзер видел — не показываем модалку
    var seen = localStorage.getItem('bc_release_seen') || '';
    var applied = localStorage.getItem('bc_force_version') || '';
    if(d.target_version === seen || d.target_version === applied){
      // Показываем только маленький индикатор вверху, если ещё не применил
      if(d.target_version !== applied && !d.force){
        showReleaseIndicator();
      }
      return;
    }

    // Формируем релиз
    _lastRelease = {
      version: d.target_version || '2.5',
      notes: d.notes || '',
      force: !!d.force
    };

    // Если force=true — показываем модалку сразу и блокируем
    // Иначе — модалку, но с кнопкой «Позже»
    showReleaseModal(_lastRelease);

  } catch(e) {
    console.warn('[BC] release check failed', e);
  }
}

function showReleaseModal(rel){
  if(!rel) return;
  var m = document.getElementById('releaseModal');
  if(!m) return;

  document.getElementById('relTitle').textContent = 'Belugacord ' + esc(rel.version);
  document.getElementById('relNotes').textContent = rel.notes || 'Список изменений не указан';

  var laterBtn = document.getElementById('relLaterBtn');
  var forceMsg = document.getElementById('relForceMsg');
  if(rel.force){
    laterBtn.style.display = 'none';
    forceMsg.style.display = 'block';
  } else {
    laterBtn.style.display = 'block';
    forceMsg.style.display = 'none';
  }

  m.classList.add('open');
  // Скрываем маленький индикатор, если он был
  hideReleaseIndicator();
}

function applyRelease(){
  var rel = _lastRelease || (BC.flags.release ? {
    version: BC.flags.release.target_version,
    notes: BC.flags.release.notes,
    force: BC.flags.release.force
  } : null);

  if(!rel){ location.reload(); return; }

  // Сохраняем что юзер принял версию
  localStorage.setItem('bc_release_seen', rel.version);
  localStorage.setItem('bc_force_version', rel.version);

  // Небольшая анимация и reload
  var btn = document.getElementById('relApplyBtn');
  if(btn){
    btn.disabled = true;
    btn.textContent = '⏳ Обновляем...';
  }

  setTimeout(function(){
    location.reload();
  }, 500);
}

function dismissRelease(){
  var rel = _lastRelease;
  if(!rel){ return; }

  // Помечаем как «просмотрено» чтобы не показывать снова сразу
  localStorage.setItem('bc_release_seen', rel.version);

  // Закрываем модалку
  var m = document.getElementById('releaseModal');
  if(m) m.classList.remove('open');

  // Показываем маленький индикатор наверху — чтобы юзер мог вернуться
  showReleaseIndicator();
}

/* ============================================================
   МАЛЕНЬКИЙ ИНДИКАТОР СВЕРХУ
   ============================================================ */
function showReleaseIndicator(){
  var ind = document.getElementById('releaseIndicator');
  if(!ind) return;
  ind.style.display = 'block';
  setTimeout(function(){ ind.style.transform = 'translateX(-50%) translateY(0)'; }, 50);
}

function hideReleaseIndicator(){
  var ind = document.getElementById('releaseIndicator');
  if(!ind) return;
  ind.style.transform = 'translateX(-50%) translateY(-200px)';
  setTimeout(function(){ ind.style.display = 'none'; }, 400);
}

/* ============================================================
   ПАНЕЛЬ ВЛАДЕЛЬЦА
   ============================================================ */
async function openReleasesPanel(){
  document.getElementById('releasesPanelModal').classList.add('open');
  await loadReleasesPanel();
}

async function loadReleasesPanel(){
  var c = document.getElementById('releasesBody');
  c.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-mute)">Загрузка...</div>';

  var res = await api('/owner/release/info?token=' + encodeURIComponent(token));
  if(!res.ok){
    c.innerHTML = '<div style="color:#f43f5e;text-align:center;padding:20px">Ошибка: ' + res.error + '</div>';
    return;
  }
  var d = res.data;

  var onlineCount = Object.keys(BC.onlineSet || {}).length;
  var applied = 0;
  try {
    // Считаем сколько онлайн-юзеров уже на новой версии — грубо через бэк
    // (тут точной инфы нет, но показываем статус)
    applied = d.active ? '⏳ в процессе' : '—';
  } catch(e){}

  c.innerHTML =
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px">' +
      '<div style="background:var(--bg-input);border-radius:12px;padding:16px;text-align:center">' +
        '<div style="font-size:10px;color:var(--text-mute);text-transform:uppercase;letter-spacing:2px">Текущая</div>' +
        '<div style="font-size:28px;font-weight:900;color:var(--accent);margin-top:4px">' + esc(d.current_version || '2.4') + '</div>' +
      '</div>' +
      '<div style="background:var(--bg-input);border-radius:12px;padding:16px;text-align:center;' + (d.active ? 'border:2px solid #22c55e' : '') + '">' +
        '<div style="font-size:10px;color:var(--text-mute);text-transform:uppercase;letter-spacing:2px">Доступна</div>' +
        '<div style="font-size:28px;font-weight:900;color:' + (d.active ? '#22c55e' : 'var(--text-dim)') + ';margin-top:4px">' + esc(d.target_version || '2.5') + '</div>' +
      '</div>' +
    '</div>' +

    '<div style="background:var(--bg-input);border-radius:12px;padding:12px 16px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;font-size:13px">' +
      '<span style="color:var(--text-dim)">Статус</span>' +
      '<span style="font-weight:800;color:' + (d.active ? '#22c55e' : 'var(--text-mute)') + '">' + (d.active ? '🟢 АКТИВЕН' : '⚪ ВЫКЛЮЧЕН') + '</span>' +
    '</div>' +

    '<label class="label">Новая версия</label>' +
    '<input type="text" id="relVersionInput" class="input-field" value="' + esc(d.target_version || '2.5') + '" style="margin-bottom:12px">' +

    '<label class="label">Что нового (каждая строка — пункт)</label>' +
    '<textarea id="relNotesInput" class="input-field" style="min-height:160px;margin-bottom:12px;font-family:monospace;font-size:12px">' + esc(d.notes || '') + '</textarea>' +

    '<label style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--bg-input);border-radius:10px;margin-bottom:14px;cursor:pointer">' +
      '<input type="checkbox" id="relForceInput" style="width:20px;height:20px"' + (d.force ? ' checked' : '') + '>' +
      '<span style="font-size:13px">Принудительно (юзер не может отказаться)</span>' +
    '</label>' +

    '<button class="save-btn gold" onclick="releaseActivate()">🚀 Включить для всех</button>' +
    '<button class="save-btn gray" onclick="releaseDeactivate()" style="margin-top:8px"' + (d.active ? '' : ' disabled') + '>↩️ Откатить</button>' +
    '<button class="save-btn purple" onclick="releasePreview()" style="margin-top:8px">👁️ Показать себе</button>' +

    '<div style="margin-top:16px;padding:12px;background:var(--bg-input);border-radius:10px;font-size:11px;color:var(--text-mute);line-height:1.6">' +
      '💡 <b>Как работает:</b> нажми «Включить» — все онлайн-юзеры получат уведомление и смогут перейти на новую версию. Через сутки (или по кнопке) все остальные увидят то же.<br>' +
      '⚠️ <b>Force</b> — не даёт юзеру закрыть модалку без обновления. Только для срочных фиксов.' +
    '</div>';
}

async function releaseActivate(){
  var version = document.getElementById('relVersionInput').value.trim();
  var notes = document.getElementById('relNotesInput').value.trim();
  var force = document.getElementById('relForceInput').checked;

  if(!version){ showNotice('⚠️ Версия не указана', 'warn'); return; }
  if(!confirm('Активировать версию ' + version + ' для ВСЕХ юзеров?' + (force ? '\n\n⚠️ FORCE — юзеры не смогут отказаться!' : ''))) return;

  var res = await api('/owner/release/activate', {method:'POST', body:{
    token: token, version: version, notes: notes, force: force
  }});

  if(res.ok){
    showNotice('🚀 Релиз активирован');
    await loadReleasesPanel();
  } else {
    showNotice('❌ ' + res.error, 'error');
  }
}

async function releaseDeactivate(){
  if(!confirm('Откатить релиз? Юзеры больше не будут получать уведомление о новой версии.')) return;
  var res = await api('/owner/release/deactivate', {method:'POST', body:{token: token}});
  if(res.ok){
    showNotice('↩️ Откачено');
    await loadReleasesPanel();
  } else {
    showNotice('❌ ' + res.error, 'error');
  }
}

function releasePreview(){
  var version = document.getElementById('relVersionInput').value.trim();
  var notes = document.getElementById('relNotesInput').value.trim();
  var force = document.getElementById('relForceInput').checked;
  if(!version){ showNotice('⚠️ Версия не указана', 'warn'); return; }
  _lastRelease = {version: version, notes: notes, force: force};
  showReleaseModal(_lastRelease);
}

/* ============================================================
   WS: МГНОВЕННЫЙ СИГНАЛ О РЕЛИЗЕ
   ============================================================ */
document.addEventListener('ws:release_available', function(e){
  var d = e.detail;
  _lastRelease = {
    version: d.version,
    notes: d.notes || '',
    force: !!d.force
  };
  // Сразу показываем модалку всем онлайн — без ожидания 30 сек
  showReleaseModal(_lastRelease);
  if(BC.callRingSound) BC.callRingSound(); // звуковое привлечение
});

document.addEventListener('ws:release_cancelled', function(){
  var m = document.getElementById('releaseModal');
  if(m) m.classList.remove('open');
  hideReleaseIndicator();
});

/* ============================================================
   ИНИЦИАЛИЗАЦИЯ
   ============================================================ */
document.addEventListener('user-entered', function(){
  // Первая проверка через 5 сек после входа
  setTimeout(checkRelease, 5000);
  // Дальше каждые 30 сек
  if(_releaseTimer) clearInterval(_releaseTimer);
  _releaseTimer = setInterval(checkRelease, RELEASE_CHECK_INTERVAL);
});

// Проверка при входе/выходе из таба (браузер focus)
document.addEventListener('visibilitychange', function(){
  if(document.visibilityState === 'visible'){
    checkRelease();
  }
});

// Проверка сразу при загрузке страницы (до login — на случай если release force)
if(document.readyState !== 'loading'){
  setTimeout(checkRelease, 1000);
} else {
  document.addEventListener('DOMContentLoaded', function(){
    setTimeout(checkRelease, 1000);
  });
}

/* ============================================================
   ЭКСПОРТ
   ============================================================ */
window.checkRelease = checkRelease;
window.applyRelease = applyRelease;
window.dismissRelease = dismissRelease;
window.showReleaseModal = showReleaseModal;
window.showReleaseIndicator = showReleaseIndicator;
window.hideReleaseIndicator = hideReleaseIndicator;
window.openReleasesPanel = openReleasesPanel;
window.loadReleasesPanel = loadReleasesPanel;
window.releaseActivate = releaseActivate;
window.releaseDeactivate = releaseDeactivate;
window.releasePreview = releasePreview;

console.log('[BC] features/releases loaded');