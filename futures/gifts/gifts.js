/* ============================================================
   BELUGACORD 2.5 — MODULE: GIFTS (part 1/2)
   Подарки, апгрейдер 2.0, магазин
   ============================================================ */

var ALL_GIFTS = [
  {id:'rose', name:'Роза', emoji:'🌹', price:15},
  {id:'bear', name:'Мишка', emoji:'🧸', price:25},
  {id:'cake', name:'Торт', emoji:'🎂', price:50},
  {id:'diamond', name:'Алмаз', emoji:'💎', price:100},
  {id:'crown', name:'Корона', emoji:'👑', price:500},
  {id:'dragon', name:'Дракон', emoji:'🐉', price:1000},
  {id:'legend', name:'Легендарка', emoji:'💠', price:5000},
  {id:'alien', name:'Инопланетянин', emoji:'👽', price:10000},
  {id:'galaxy', name:'Галактика', emoji:'🌌', price:100000},
  {id:'goldcat', name:'Золотой Белуга', emoji:'🐱', price:1000000},
  {id:'universe', name:'Мультивселенная', emoji:'💫', price:1000000000}
];
var myCoins = 0, myRating = 0;

async function loadAllGifts(){
  var res = await api('/gifts/all');
  if(res.ok && res.data.length){
    ALL_GIFTS = res.data.map(function(g){
      return {id:g.gift_id, name:g.name, emoji:g.emoji, image:g.image, price:g.price};
    });
  }
}

async function loadCoins(){
  var res = await api('/coins/balance?token=' + encodeURIComponent(token));
  if(res.ok){
    myCoins = res.data.coins || 0;
    myRating = res.data.social_rating || 0;
  }
}

/* ============================================================
   МАГАЗИН
   ============================================================ */
async function openShop(){
  if(!me) return;
  document.getElementById('shopModal').classList.add('open');
  await loadCoins();
  document.getElementById('shopBalance').textContent = myCoins.toLocaleString('ru-RU');
  document.getElementById('shopRating').textContent = '⭐ Соц.рейтинг: ' + (myRating || 0).toLocaleString('ru-RU');
  showShopTab('gifts');
}

function showShopTab(tab){
  document.querySelectorAll('#shopModal .shop-tab-btn').forEach(function(b){
    b.classList.toggle('active', b.dataset.tab === tab);
  });
  var c = document.getElementById('shopTabContent');

  if(tab === 'gifts'){
    c.innerHTML = '<div class="gift-grid">' + ALL_GIFTS.map(function(g){
      return '<div class="gift-tile" onclick="buyGift(\'' + g.id + '\')">' +
        '<div class="gift-emoji">' + (g.image ? '<img src="' + g.image + '">' : g.emoji) + '</div>' +
        '<div class="gift-name">' + esc(g.name) + '</div>' +
        '<div class="gift-price">' + g.price.toLocaleString('ru-RU') + ' 🏅</div>' +
      '</div>';
    }).join('') + '</div>';
  }
  else if(tab === 'coins'){
    c.innerHTML = '<div style="text-align:center;color:var(--text-dim);font-size:13px;padding:20px">Купить бекоины можно через заявку у владельца.</div>' +
      '<button class="save-btn gold" onclick="requestCoins()">💸 Заявка на бекоины</button>';
  }
  else if(tab === 'transfer'){
    c.innerHTML = '<label class="label">Кому (ник)</label>' +
      '<input type="text" id="transferTo" class="input-field" placeholder="Ник друга" style="margin-bottom:10px">' +
      '<label class="label">Сумма</label>' +
      '<input type="number" id="transferAmount" class="input-field" placeholder="0">' +
      '<button class="save-btn green" onclick="doTransfer()">💸 Перевести</button>';
  }
}

async function buyGift(giftId){
  var g = ALL_GIFTS.find(function(x){ return x.id === giftId; });
  if(!g) return;
  if((myCoins || 0) < g.price){ showNotice('❌ Не хватает бекоинов', 'error'); return; }
  document.getElementById('shopModal').classList.remove('open');
  openGiftSend(giftId);
}

function openGiftSend(giftId){
  var g = ALL_GIFTS.find(function(x){ return x.id === giftId; });
  if(!g) return;
  document.querySelectorAll('#giftSendModal').forEach(function(m){ m.remove(); });
  var m = document.createElement('div');
  m.className = 'modal-overlay open';
  m.id = 'giftSendModal';
  m.innerHTML = '<div class="modal" style="max-width:440px">' +
    '<button class="close-btn" onclick="document.getElementById(\'giftSendModal\').remove()">✕</button>' +
    '<div style="padding:28px 24px;text-align:center">' +
      '<div style="font-size:80px;margin-bottom:10px">' + (g.image ? '<img src="' + g.image + '" style="max-width:80px;max-height:80px">' : g.emoji) + '</div>' +
      '<h2 style="font-size:22px;margin-bottom:6px">' + esc(g.name) + '</h2>' +
      '<div style="color:var(--gold);font-weight:900;font-size:18px;margin-bottom:16px">' + g.price.toLocaleString('ru-RU') + ' 🏅</div>' +
      '<label class="label" style="text-align:left">Кому (ник)</label>' +
      '<input type="text" id="giftToUser" class="input-field" placeholder="Ник" style="margin-bottom:14px">' +
      '<button class="save-btn gold" onclick="confirmSendGift(\'' + giftId + '\')">🎁 Отправить</button>' +
    '</div>' +
  '</div>';
  document.body.appendChild(m);
}

async function confirmSendGift(giftId){
  var uname = document.getElementById('giftToUser').value.trim();
  if(!uname){ showNotice('⚠️ Введи ник', 'warn'); return; }
  var sr = await api('/users/search?q=' + encodeURIComponent(uname) + '&token=' + encodeURIComponent(token));
  if(!sr.ok || !sr.data.length){ showNotice('❌ Юзер не найден', 'error'); return; }
  var target = sr.data.find(function(u){ return u.username.toLowerCase() === uname.toLowerCase(); }) || sr.data[0];
  var res = await api('/gifts/send', {method:'POST', body:{token:token, gift:giftId, to_user:target.id}});
  if(res.ok){
    showNotice('🎁 Отправлено');
    document.getElementById('giftSendModal').remove();
    if(BC.giftSound) BC.giftSound();
    BC.showConfetti();
    loadCoins();
  } else showNotice('❌ ' + res.error, 'error');
}

function requestCoins(){
  var c = prompt('Сколько бекоинов?', '100');
  if(!c) return;
  api('/coins/request', {method:'POST', body:{token:token, coins:parseInt(c), price:0}}).then(function(res){
    if(res.ok) showNotice('💸 Заявка отправлена');
  });
}

async function doTransfer(){
  var uname = document.getElementById('transferTo').value.trim();
  var amt = parseInt(document.getElementById('transferAmount').value);
  if(!uname || !amt || amt <= 0){ showNotice('⚠️ Заполни', 'warn'); return; }
  var sr = await api('/users/search?q=' + encodeURIComponent(uname) + '&token=' + encodeURIComponent(token));
  if(!sr.ok || !sr.data.length){ showNotice('❌ Не найден', 'error'); return; }
  var target = sr.data[0];
  var res = await api('/coins/transfer', {method:'POST', body:{token:token, to_user:target.id, amount:amt}});
  if(res.ok){
    showNotice('💸 ' + res.data.to);
    document.getElementById('shopModal').classList.remove('open');
    loadCoins();
  } else showNotice('❌ ' + res.error, 'error');
}

/* ============================================================
   МОИ ПОДАРКИ
   ============================================================ */
async function openGiftsCollection(){
  document.getElementById('giftsModal').classList.add('open');
  var list = document.getElementById('myGiftsList');
  list.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-mute)">Загрузка...</div>';
  var res = await api('/gifts/list/' + me.id);
  if(!res.ok){ list.innerHTML = '<div style="text-align:center;padding:20px;color:#f43f5e">Ошибка</div>'; return; }
  var myGifts = res.data.gifts || [];
  if(!myGifts.length){
    list.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">🎀 Пока ни одного подарка 😢</div>';
    return;
  }
  var counts = {};
  myGifts.forEach(function(g){ counts[g.gift] = (counts[g.gift] || 0) + 1; });
  list.innerHTML = '<div class="gift-grid">' + Object.keys(counts).map(function(gid){
    var g = ALL_GIFTS.find(function(x){ return x.id === gid; });
    var cnt = counts[gid];
    if(!g) return '';
    return '<div class="gift-tile" onclick="openUpgraderWith(\'' + gid + '\')">' +
      '<div class="gift-emoji">' + (g.image ? '<img src="' + g.image + '">' : g.emoji) + '</div>' +
      '<div class="gift-name">' + esc(g.name) + (cnt > 1 ? ' ×' + cnt : '') + '</div>' +
      '<div class="gift-price">' + g.price.toLocaleString('ru-RU') + ' 🏅</div>' +
    '</div>';
  }).join('') + '</div>';
}

/* ============================================================
   АПГРЕЙДЕР 2.0 — состояние
   ============================================================ */
var ugFromGift = null, ugToGift = null, ugMultiplier = 2, ugChance = 75, ugInventory = [];
var ugSpinning = false;

async function openUpgrader(){
  ugFromGift = null;
  ugToGift = null;
  ugMultiplier = 2;
  ugSpinning = false;
  document.getElementById('upgraderModal').classList.add('open');
  await ugLoadInventory();
  ugPopulateSelects();
  ugSetMult(2, null, true);
  ugDrawCircle(75);
}

async function openUpgraderWith(giftId){
  document.getElementById('giftsModal').classList.remove('open');
  document.getElementById('upgraderModal').classList.add('open');
  ugFromGift = giftId;
  ugToGift = null;
  ugMultiplier = 2;
  ugSpinning = false;
  await ugLoadInventory();
  ugPopulateSelects();
  if(giftId) document.getElementById('ugFromSelect').value = giftId;
  ugRecalc();
}

function closeUpgrader(){
  document.getElementById('upgraderModal').classList.remove('open');
}

async function ugLoadInventory(){
  var res = await api('/gifts/list/' + me.id);
  if(res.ok){
    var gifts = res.data.gifts || [];
    var counts = {};
    gifts.forEach(function(g){ counts[g.gift] = (counts[g.gift] || 0) + 1; });
    ugInventory = Object.keys(counts).map(function(gid){
      var g = ALL_GIFTS.find(function(x){ return x.id === gid; });
      return g ? {id:gid, name:g.name, emoji:g.emoji, image:g.image, price:g.price, count:counts[gid]} : null;
    }).filter(Boolean);
  } else ugInventory = [];
}

function ugPopulateSelects(){
  var fs = document.getElementById('ugFromSelect');
  var ts = document.getElementById('ugToSelect');

  if(!ugInventory.length){
    fs.innerHTML = '<option value="">— Нет подарков —</option>';
  } else {
    fs.innerHTML = '<option value="">— Выбери —</option>' + ugInventory.map(function(g){
      return '<option value="' + g.id + '">' + g.emoji + ' ' + g.name + (g.count > 1 ? ' ×' + g.count : '') + ' (' + g.price.toLocaleString('ru-RU') + '🏅)</option>';
    }).join('');
  }
  if(ugFromGift){
    fs.value = ugFromGift;
  }

  ts.innerHTML = '<option value="">— Выбери —</option>' + ALL_GIFTS.map(function(g){
    return '<option value="' + g.id + '">' + g.emoji + ' ' + g.name + ' (' + g.price.toLocaleString('ru-RU') + '🏅)</option>';
  }).join('');
  if(ugToGift) ts.value = ugToGift;
}

function ugSetMult(m, ev, silent){
  ugMultiplier = m;
  document.querySelectorAll('.ug-mult-btn').forEach(function(b){
    b.classList.toggle('active', parseInt(b.dataset.mult) === m);
    b.style.background = parseInt(b.dataset.mult) === m ? 'linear-gradient(135deg,var(--accent),var(--accent-2))' : '';
    b.style.color = parseInt(b.dataset.mult) === m ? '#fff' : '';
  });
  if(!silent) ugRecalc();
}

function ugRecalc(){
  ugFromGift = document.getElementById('ugFromSelect').value || null;
  ugToGift = document.getElementById('ugToSelect').value || null;

  var chanceEl = document.getElementById('ugChanceDisplay');
  var spinBtn = document.getElementById('ugSpinBtn');

  if(!ugFromGift || !ugToGift){
    chanceEl.textContent = 'Выбери подарки';
    spinBtn.disabled = true;
    ugChance = 0;
    ugDrawCircle(0);
    return;
  }

  var fromG = ALL_GIFTS.find(function(x){ return x.id === ugFromGift; });
  var toG = ALL_GIFTS.find(function(x){ return x.id === ugToGift; });
  if(!fromG || !toG) return;

  // Шанс по множителю
  var chanceMap = {2:75, 4:50, 6:25, 8:12.5};
  ugChance = chanceMap[ugMultiplier] || 75;

  // Проверка: подходит ли цель под множитель
  var targetPrice = fromG.price * ugMultiplier;
  var closest = null, minDiff = Infinity;
  ALL_GIFTS.forEach(function(g){
    var diff = Math.abs(g.price - targetPrice);
    if(diff < minDiff){ minDiff = diff; closest = g; }
  });

  chanceEl.innerHTML = '🎯 Шанс: <b>' + ugChance + '%</b> · Хочу ×' + ugMultiplier + ' = ' + (closest ? closest.emoji + ' ' + closest.name : '—');

  if(ugChance > 0 && ugChance <= 100) spinBtn.disabled = false;
  else spinBtn.disabled = true;

  ugDrawCircle(ugChance);
}

function ugDrawCircle(chance){
  var svg = document.getElementById('ugCircleSvg');
  if(!svg) return;

  var cx = 100, cy = 100, r = 80;
  // Зелёная часть СНИЗУ (от 90° до 90° + chance%)
  // В SVG углы: 0° = 3 часа, по часовой. Начало снизу = 90°.
  var startAngle = 90; // внизу
  var greenDeg = (chance / 100) * 360;
  var endAngle = startAngle + greenDeg;

  function polar(cx, cy, r, deg){
    var rad = (deg - 90) * Math.PI / 180;
    return {x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad)};
  }
  function arcPath(cx, cy, r, a1, a2){
    var p1 = polar(cx, cy, r, a1);
    var p2 = polar(cx, cy, r, a2);
    var large = (a2 - a1) > 180 ? 1 : 0;
    return 'M ' + p1.x + ' ' + p1.y + ' A ' + r + ' ' + r + ' 0 ' + large + ' 1 ' + p2.x + ' ' + p2.y;
  }

  var html = '';

  // Серая часть (100% круг)
  html += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="#3a3a4a" stroke-width="18"/>';

  // Зелёная часть (chance%)
  if(chance > 0 && chance < 100){
    html += '<path d="' + arcPath(cx, cy, r, startAngle, endAngle) + '" stroke="#22c55e" stroke-width="18" fill="none" stroke-linecap="butt"/>';
  } else if(chance >= 100){
    html += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="#22c55e" stroke-width="18"/>';
  }

  // Центральный лейбл
  html += '<text x="' + cx + '" y="' + (cy + 8) + '" text-anchor="middle" fill="' + (chance > 0 ? '#ffd700' : '#666') + '" font-size="32" font-weight="900">' + Math.round(chance) + '%</text>';

  svg.innerHTML = html;
}

/* Спин (часть 2/2 продолжение) */
function ugSpin(){
  // Реализация в части 2/2
  if(typeof doUpgradeSpin === 'function') doUpgradeSpin();
}
