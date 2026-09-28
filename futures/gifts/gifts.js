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

/* ============================================================
   АПГРЕЙДЕР 2.0 — СПИН
   ============================================================ */
async function doUpgradeSpin(){
  if(ugSpinning) return;
  if(!ugFromGift || !ugToGift){ showNotice('⚠️ Выбери подарки', 'warn'); return; }
  if(ugChance <= 0){ showNotice('⚠️ Шанс 0%', 'warn'); return; }

  ugSpinning = true;
  var btn = document.getElementById('ugSpinBtn');
  btn.disabled = true;
  btn.textContent = '🎰 Крутим...';

  var arrow = document.getElementById('ugArrow');
  // Стрелка снаружи круга бежит на 360° * 6 оборотов + рандом
  var spins = 5 + Math.random() * 3;
  var finalDeg = spins * 360 + Math.random() * 360;
  arrow.style.transform = 'translateX(-50%) rotate(' + finalDeg + 'deg)';

  // Отправляем запрос на сервер
  try {
    var res = await api('/gifts/upgrade_wheel', {method:'POST', body:{
      token: token,
      from_gift: ugFromGift,
      to_gift: ugToGift,
      multiplier: ugMultiplier,
      chance: ugChance
    }});

    setTimeout(function(){
      // Сброс стрелки
      arrow.style.transition = 'none';
      arrow.style.transform = 'translateX(-50%) rotate(0deg)';
      setTimeout(function(){ arrow.style.transition = ''; }, 50);

      if(!res.ok){
        showNotice('❌ ' + res.error, 'error');
        ugSpinning = false;
        btn.disabled = false;
        btn.textContent = '🎰 КРУТИТЬ';
        return;
      }

      var d = res.data;
      if(d.success){
        showNotice('🎉 УСПЕХ! Получил ' + d.got_name);
        if(BC.giftSound) BC.giftSound();
        BC.showConfetti();
        BC.showBalloons();
      } else {
        showNotice('😢 Не повезло · шанс был ' + d.chance.toFixed(1) + '%', 'warn');
      }

      // Обновляем инвентарь
      ugLoadInventory().then(function(){
        ugPopulateSelects();
        if(ugFromGift) document.getElementById('ugFromSelect').value = ugFromGift;
        ugRecalc();
      });
      loadCoins();

      ugSpinning = false;
      btn.disabled = false;
      btn.textContent = '🎰 КРУТИТЬ';
    }, 4200);
  } catch(e){
    setTimeout(function(){
      ugSpinning = false;
      btn.disabled = false;
      btn.textContent = '🎰 КРУТИТЬ';
      showNotice('❌ Сеть', 'error');
    }, 4200);
  }
}

/* ============================================================
   NFT
   ============================================================ */
function openNftMarket(){
  document.getElementById('nftMarketModal').classList.add('open');
  showNftTab('all');
}

function showNftTab(tab, ev){
  if(ev){
    document.querySelectorAll('#nftMarketModal .shop-tab-btn').forEach(function(b){ b.classList.remove('active'); });
    ev.target.classList.add('active');
  }
  var c = document.getElementById('nftTabContent');
  c.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">Загрузка...</div>';

  if(tab === 'all'){
    api('/nft/list').then(function(res){
      if(!res.ok || !res.data.length){
        c.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">🎨 Нет NFT</div>';
        return;
      }
      c.innerHTML = '<div class="nft-grid">' + res.data.map(function(n){
        return '<div class="nft-card" onclick="buyNft(' + n.id + ')">' +
          '<div class="nft-img">' + (n.image ? '<img src="' + n.image + '">' : n.emoji || '🎨') +
            '<div class="nft-rarity rarity-' + n.rarity + '">' + n.rarity + '</div>' +
          '</div>' +
          '<div class="nft-info">' +
            '<div class="nft-name">' + esc(n.name) + '</div>' +
            '<div class="nft-num">#' + n.number + ' / ' + n.total + '</div>' +
            '<div class="nft-price">' + n.price.toLocaleString('ru-RU') + ' 🏅</div>' +
          '</div>' +
        '</div>';
      }).join('') + '</div>';
    });
  }
  else if(tab === 'my'){
    api('/nft/my?token=' + encodeURIComponent(token)).then(function(res){
      if(!res.ok || !res.data.length){
        c.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">🎒 Пусто</div>';
        return;
      }
      c.innerHTML = '<div class="nft-grid">' + res.data.map(function(n){
        return '<div class="nft-card">' +
          '<div class="nft-img">' + (n.image ? '<img src="' + n.image + '">' : n.emoji || '🎨') +
            '<div class="nft-rarity rarity-' + n.rarity + '">' + n.rarity + '</div>' +
          '</div>' +
          '<div class="nft-info">' +
            '<div class="nft-name">' + esc(n.name) + '</div>' +
            '<div class="nft-num">#' + n.number + '</div>' +
            '<button class="save-btn gray" style="margin-top:6px;font-size:11px;padding:6px" onclick="sellNft(' + n.id + ')">💱 Продать</button>' +
          '</div>' +
        '</div>';
      }).join('') + '</div>';
    });
  }
  else if(tab === 'market'){
    api('/nft_market/list?token=' + encodeURIComponent(token)).then(function(res){
      if(!res.ok || !res.data.length){
        c.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">💱 Рынок пуст</div>';
        return;
      }
      c.innerHTML = '<div class="nft-grid">' + res.data.map(function(m){
        return '<div class="nft-card" onclick="buyNftMarket(' + m.id + ')">' +
          '<div class="nft-img">' + (m.image ? '<img src="' + m.image + '">' : m.emoji || '🎨') + '</div>' +
          '<div class="nft-info">' +
            '<div class="nft-name">' + esc(m.name) + '</div>' +
            '<div class="nft-num">#' + m.number + ' · от ' + esc(m.seller_name) + '</div>' +
            '<div class="nft-price">' + m.price.toLocaleString('ru-RU') + ' 🏅</div>' +
          '</div>' +
        '</div>';
      }).join('') + '</div>';
    });
  }
}

async function buyNft(id){
  if(!confirm('Купить NFT?')) return;
  var res = await api('/nft/buy', {method:'POST', body:{token:token, nft_id:id}});
  if(res.ok){
    showNotice('🎨 Получен #' + res.data.number);
    BC.showConfetti();
    loadCoins();
    showNftTab('my', {target: document.querySelector('#nftMarketModal .shop-tab-btn:nth-child(2)')});
  } else showNotice('❌ ' + res.error, 'error');
}

async function sellNft(itemId){
  if(!confirm('Продать за половину?')) return;
  var res = await api('/nft/sell', {method:'POST', body:{token:token, item_id:itemId}});
  if(res.ok){
    showNotice('💱 +' + res.data.got);
    loadCoins();
    showNftTab('my', {target: document.querySelector('#nftMarketModal .shop-tab-btn:nth-child(2)')});
  } else showNotice('❌ ' + res.error, 'error');
}

async function buyNftMarket(mid){
  if(!confirm('Купить с рынка?')) return;
  var res = await api('/nft_market/buy', {method:'POST', body:{token:token, market_id:mid}});
  if(res.ok){
    showNotice('🎨 Куплено');
    loadCoins();
    showNftTab('my', {target: document.querySelector('#nftMarketModal .shop-tab-btn:nth-child(2)')});
  } else showNotice('❌ ' + res.error, 'error');
}

/* ============================================================
   КЕЙСЫ
   ============================================================ */
async function openCases(){
  document.getElementById('casesModal').classList.add('open');
  var body = document.getElementById('casesBody');
  body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">Загрузка...</div>';
  var res = await api('/cases/list');
  if(!res.ok || !res.data.length){
    body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">🎁 Нет кейсов</div>';
    return;
  }
  body.innerHTML = res.data.map(function(c){
    return '<div class="case-tile" onclick="openCaseRoulette(' + c.id + ',\'' + esc(c.name) + '\')">' +
      '<div class="case-emoji">' + (c.image ? '<img src="' + c.image + '">' : (c.emoji || '🎁')) + '</div>' +
      '<div class="case-name">' + esc(c.name) + '</div>' +
      '<div class="case-price">' + c.price.toLocaleString('ru-RU') + ' 🏅</div>' +
      '<button class="case-open">Открыть</button>' +
    '</div>';
  }).join('');
}

async function openCaseRoulette(caseId, caseName){
  var pr = await api('/cases/' + caseId + '/prizes');
  if(!pr.ok || !pr.data.length){ showNotice('❌ Нет призов', 'error'); return; }

  var prizes = pr.data;
  var overlay = document.createElement('div');
  overlay.className = 'case-roulette open';
  overlay.id = 'caseRouletteOverlay';

  var items = '';
  for(var i = 0; i < 30; i++){
    var p = prizes[i % prizes.length];
    var em = p.item_image ? '<img src="' + p.item_image + '" style="width:44px;height:44px;object-fit:contain">' : (p.item_emoji || '🎁');
    items += '<div class="cr-item"><div class="cr-emoji">' + em + '</div><div class="cr-name">' + (p.item_name || ('🏅 ' + (p.coins_min || p.coins_max))) + '</div></div>';
  }

  overlay.innerHTML = '<div class="case-roulette-strip">' +
    '<div class="case-roulette-pointer"></div>' +
    '<div class="case-roulette-inner" id="caseRouletteInner">' + items + '</div>' +
    '</div>' +
    '<div class="case-roulette-result" id="caseRouletteResult">Крутим...</div>';

  document.body.appendChild(overlay);

  var inner = document.getElementById('caseRouletteInner');
  var itemWidth = 110;
  var targetIndex = Math.floor(30 * 0.7);
  var targetX = -(targetIndex * itemWidth) + 200 - inner.offsetWidth / 2;
  setTimeout(function(){ inner.style.transform = 'translateX(' + targetX + 'px)'; }, 50);

  var res = await api('/cases/open', {method:'POST', body:{token:token, case_id:caseId}});

  setTimeout(function(){
    var resEl = document.getElementById('caseRouletteResult');
    if(res.ok){
      resEl.textContent = '🎉 ' + res.data.prize;
      resEl.classList.add('show');
      if(BC.giftSound) BC.giftSound();
      BC.showConfetti();
      loadCoins();
    } else {
      resEl.textContent = '❌ ' + res.error;
      resEl.classList.add('show');
    }
    setTimeout(function(){ overlay.remove(); }, 2500);
  }, 4200);
}

/* ============================================================
   WS — обновление баланса
   ============================================================ */
document.addEventListener('ws:gift_received', function(e){
  var data = e.detail;
  var g = document.createElement('div');
  g.className = 'gift-received';
  g.innerHTML =
    '<div class="gift-big-emoji">' + (data.gift_image ? '<img src="' + data.gift_image + '">' : (data.gift_emoji || '🎁')) + '</div>' +
    '<div class="gift-text">' + esc(data.gift_name || 'Подарок') + ' от ' + esc(data.from_name || '?') + '</div>';
  document.body.appendChild(g);
  if(BC.giftSound) BC.giftSound();
  BC.showConfetti();
  setTimeout(function(){ g.remove(); }, 3500);
});

document.addEventListener('ws:coins_received', function(e){
  var data = e.detail;
  showNotice('💰 ' + data.from_name + ' → ' + data.amount + ' 🏅');
  loadCoins();
});

document.addEventListener('ws:nft_sold', function(){
  showNotice('💱 NFT продан');
  loadCoins();
});

/* ============================================================
   ЭКСПОРТ
   ============================================================ */
window.openShop = openShop;
window.showShopTab = showShopTab;
window.buyGift = buyGift;
window.openGiftSend = openGiftSend;
window.confirmSendGift = confirmSendGift;
window.requestCoins = requestCoins;
window.doTransfer = doTransfer;
window.openGiftsCollection = openGiftsCollection;
window.openUpgrader = openUpgrader;
window.openUpgraderWith = openUpgraderWith;
window.closeUpgrader = closeUpgrader;
window.ugRecalc = ugRecalc;
window.ugSetMult = ugSetMult;
window.ugSpin = ugSpin;
window.openNftMarket = openNftMarket;
window.showNftTab = showNftTab;
window.buyNft = buyNft;
window.sellNft = sellNft;
window.buyNftMarket = buyNftMarket;
window.openCases = openCases;
window.openCaseRoulette = openCaseRoulette;

console.log('[BC] features/gifts loaded');
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
