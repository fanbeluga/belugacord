/* BELUGACORD 2.5 — MODULE: ECONOMY */

/* ============================================================
   СУНДУК
   ============================================================ */
async function openChest(){
  document.getElementById('chestModal').classList.add('open');
  var res = await api('/chest/status?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var d = res.data;
  document.getElementById('chestStreak').textContent = '🔥 Streak: ' + (d.streak || 0) + ' дней';
  var btn = document.getElementById('chestOpenBtn');
  if(d.available){
    btn.disabled = false;
    btn.textContent = '🎁 Открыть сундук';
    document.getElementById('chestTimer').textContent = '✅ Доступно!';
  } else {
    btn.disabled = true;
    btn.textContent = '⏳ Рано';
    var h = Math.floor(d.next_in / 3600), m = Math.floor((d.next_in % 3600) / 60), s = d.next_in % 60;
    document.getElementById('chestTimer').textContent = String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
  }
}
async function openChestAction(){
  var res = await api('/chest/open', {method:'POST', body:{token:token}});
  if(res.ok){
    var d = res.data;
    if(d.type === 'premium'){
      showNotice('💎 ПРЕМИУМ на ' + d.days + ' дней!');
      BC.showConfetti();
      BC.showBalloons();
    } else {
      showNotice('🏅 +' + d.amount + ' бекоинов');
      BC.showConfetti();
    }
    loadCoins();
    openChest();
  } else showNotice('❌ ' + res.error, 'error');
}

/* ============================================================
   ЛОТЕРЕЯ
   ============================================================ */
async function openLottery(){
  document.getElementById('lotteryModal').classList.add('open');
  var res = await api('/lottery/status?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var d = res.data;
  document.getElementById('lotteryJackpot').textContent = (d.jackpot || 0).toLocaleString('ru-RU') + ' 🏅';
  document.getElementById('lotteryTickets').textContent = d.tickets || 0;
  document.getElementById('lotteryPlayers').textContent = d.players || 0;
  var next = d.next_in || 3600;
  document.getElementById('lotteryTimer').textContent = String(Math.floor(next/60)).padStart(2,'0') + ':' + String(next % 60).padStart(2,'0');
  var hist = document.getElementById('lotteryHistory');
  hist.innerHTML = (d.history || []).map(function(h){
    return '<div style="padding:6px 10px;background:var(--bg-input);border-radius:8px;margin-bottom:4px;font-size:11px"><b>' + esc(h.winner) + '</b> выиграл ' + h.amount.toLocaleString('ru-RU') + ' 🏅</div>';
  }).join('') || '<div style="text-align:center;color:var(--text-mute);font-size:11px">Пока никто</div>';
}
async function buyLotteryTicket(){
  var res = await api('/lottery/buy', {method:'POST', body:{token:token}});
  if(res.ok){ showNotice('🎟️ Куплен'); loadCoins(); openLottery(); }
  else showNotice('❌ ' + res.error, 'error');
}

/* ============================================================
   БАНК
   ============================================================ */
async function openBank(){
  document.getElementById('bankModal').classList.add('open');
  var res = await api('/bank/status?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  document.getElementById('bankDeposit').textContent = (res.data.deposit || 0).toLocaleString('ru-RU') + ' 🏅';
  document.getElementById('bankInterest').textContent = (res.data.interest || 0).toLocaleString('ru-RU') + ' 🏅';
}
async function bankDeposit(){
  var amt = parseInt(document.getElementById('bankAmount').value);
  if(!amt || amt <= 0){ showNotice('⚠️', 'warn'); return; }
  var res = await api('/bank/deposit', {method:'POST', body:{token:token, amount:amt}});
  if(res.ok){ showNotice('💰 Положено'); loadCoins(); openBank(); }
  else showNotice('❌ ' + res.error, 'error');
}
async function bankWithdraw(){
  if(!confirm('Забрать всё?')) return;
  var res = await api('/bank/withdraw', {method:'POST', body:{token:token}});
  if(res.ok){ showNotice('💸 +' + res.data.got); loadCoins(); openBank(); }
  else showNotice('❌ ' + res.error, 'error');
}

/* ============================================================
   АУКЦИОН
   ============================================================ */
async function openAuction(){
  document.getElementById('auctionModal').classList.add('open');
  var res = await api('/auction/list?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var d = res.data;
  var cur = document.getElementById('auctionCurrent');
  if(!d.current){
    cur.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-mute)">🔨 Нет активных лотов</div>';
    return;
  }
  cur.innerHTML = '<div class="shop-header">' +
    '<div style="font-size:60px">' + (d.current.emoji || '🔨') + '</div>' +
    '<div style="font-weight:900;font-size:18px;margin:10px 0">' + esc(d.current.name) + '</div>' +
    '<div style="color:var(--gold);font-weight:900;font-size:24px">' + (d.current.price || 0).toLocaleString('ru-RU') + ' 🏅</div>' +
    '<div style="font-size:11px;color:var(--text-mute);margin:6px 0">Лидер: ' + esc(d.current.leader || '—') + ' · ⏰ ' + d.current.timer + 'с</div>' +
    '<input type="number" id="auctionBidAmount" class="input-field" placeholder="Ставка" style="margin-bottom:8px">' +
    '<button class="save-btn gold" onclick="doAuctionBid()">💰 Поставить</button>' +
  '</div>';
}
async function doAuctionBid(){
  var amt = parseInt(document.getElementById('auctionBidAmount').value);
  if(!amt){ showNotice('⚠️', 'warn'); return; }
  var res = await api('/auction/bid', {method:'POST', body:{token:token, amount:amt}});
  if(res.ok){ showNotice('💰 Ставка принята'); loadCoins(); openAuction(); }
  else showNotice('❌ ' + res.error, 'error');
}

/* ============================================================
   КВЕСТЫ
   ============================================================ */
async function openQuests(){
  document.getElementById('questsModal').classList.add('open');
  var res = await api('/quests/list?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  document.getElementById('questKpTotal').textContent = (res.data.quest_points || 0).toLocaleString('ru-RU');
  var list = document.getElementById('questsList');
  list.innerHTML = (res.data.quests || []).map(function(q){
    var pct = Math.min(100, (q.progress / q.goal) * 100);
    return '<div class="quest-card' + (q.claimed ? ' done' : '') + '">' +
      '<div class="quest-emoji">' + q.emoji + '</div>' +
      '<div class="quest-body">' +
        '<div class="quest-name">' + esc(q.name) + '</div>' +
        '<div class="quest-desc">' + esc(q.desc) + '</div>' +
        '<div class="quest-progress-bar"><div class="quest-progress-fill" style="width:' + pct + '%"></div></div>' +
      '</div>' +
      '<div class="quest-reward">' + (q.claimed ? '<span class="quest-claimed-badge">✓</span>' : '+' + q.reward_kp + ' КП') + '</div>' +
    '</div>';
  }).join('');
}
function openQuestExchange(){
  document.getElementById('questsModal').classList.remove('open');
  document.getElementById('questExchangeModal').classList.add('open');
}
async function exchangeKp(plan){
  var res = await api('/quests/exchange', {method:'POST', body:{token:token, plan:plan}});
  if(res.ok){
    showNotice('💎 +' + res.data.days + ' дней премиума!');
    document.getElementById('questExchangeModal').classList.remove('open');
    if(me) me.is_premium = true;
  } else showNotice('❌ ' + res.error, 'error');
}

/* ============================================================
   ЕЖЕДНЕВНЫЙ БОНУС
   ============================================================ */
async function claimDailyBonus(){
  var res = await api('/daily/bonus', {method:'POST', body:{token:token}});
  if(res.ok){
    showNotice('🏅 +' + res.data.amount + (res.data.premium ? ' (×3)' : ''));
    BC.showConfetti();
    loadCoins();
    document.getElementById('dailyBonusModal').classList.remove('open');
  } else showNotice('❌ ' + res.error, 'error');
}

/* ============================================================
   БОЕВОЙ ПРОПУСК
   ============================================================ */
async function openBattlePass(){
  document.getElementById('battlePassModal').classList.add('open');
  var res = await api('/bp/current?token=' + encodeURIComponent(token));
  if(!res.ok) return;
  var d = res.data;
  if(!d.active){
    document.getElementById('bpTitle').textContent = '🏆 Сезон не активен';
    document.getElementById('bpDescription').textContent = '';
    document.getElementById('bpContent').innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-mute)">Ждём старта</div>';
    return;
  }
  document.getElementById('bpTitle').textContent = d.emoji + ' ' + d.name;
  document.getElementById('bpDescription').textContent = d.description || '';
  document.getElementById('bpLevel').textContent = 'Ур. ' + d.my_level;
  document.getElementById('bpXP').textContent = d.my_xp + ' / ' + (d.my_level * 1000);
  document.getElementById('bpProgressFill').style.width = Math.min(100, (d.my_xp / (d.my_level * 1000)) * 100) + '%';
  showBpTab('quests');
}
function showBpTab(tab, ev){
  if(ev){
    document.querySelectorAll('#battlePassModal .shop-tab-btn').forEach(function(b){ b.classList.remove('active'); });
    ev.target.classList.add('active');
  }
  var c = document.getElementById('bpContent');
  api('/bp/current?token=' + encodeURIComponent(token)).then(function(res){
    if(!res.ok) return;
    var d = res.data;
    if(tab === 'quests'){
      c.innerHTML = (d.quests || []).map(function(q){
        return '<div class="quest-card">' +
          '<div class="quest-emoji">📋</div>' +
          '<div class="quest-body">' +
            '<div class="quest-name">' + esc(q.name) + '</div>' +
            '<div class="quest-desc">' + esc(q.desc) + '</div>' +
          '</div>' +
          '<div class="quest-reward">+' + q.xp_reward + ' XP</div>' +
        '</div>';
      }).join('') || '<div style="text-align:center;color:var(--text-mute)">Пусто</div>';
    } else {
      c.innerHTML = (d.rewards || []).map(function(r){
        return '<div class="bp-reward-card' + (r.unlocked ? ' unlocked' : '') + '">' +
          '<div class="bp-reward-level">' + r.level + '</div>' +
          '<div style="flex:1;font-weight:800">' + esc(r.reward) + '</div>' +
          (r.unlocked ? '<button class="save-btn gold" style="margin:0;width:auto;padding:6px 12px;font-size:11px" onclick="claimBpReward(' + r.level + ')">Забрать</button>' : '') +
        '</div>';
      }).join('');
    }
  });
}
async function claimBpReward(level){
  var res = await api('/bp/claim', {method:'POST', body:{token:token, level:level}});
  if(res.ok){
    showNotice('🎁 Получено');
    showBpTab('rewards', {target: document.querySelector('#battlePassModal .shop-tab-btn:nth-child(2)')});
  } else showNotice('❌ ' + res.error, 'error');
}

/* ============================================================
   WS-обработчики
   ============================================================ */
document.addEventListener('ws:coins_approved', function(e){
  showNotice('🎉 +' + e.detail.amount);
  loadCoins();
});
document.addEventListener('ws:coins_rejected', function(){
  showNotice('❌', 'error');
});

/* ============================================================
   ЭКСПОРТ
   ============================================================ */
window.openChest = openChest;
window.openChestAction = openChestAction;
window.openLottery = openLottery;
window.buyLotteryTicket = buyLotteryTicket;
window.openBank = openBank;
window.bankDeposit = bankDeposit;
window.bankWithdraw = bankWithdraw;
window.openAuction = openAuction;
window.doAuctionBid = doAuctionBid;
window.openQuests = openQuests;
window.openQuestExchange = openQuestExchange;
window.exchangeKp = exchangeKp;
window.claimDailyBonus = claimDailyBonus;
window.openBattlePass = openBattlePass;
window.showBpTab = showBpTab;
window.claimBpReward = claimBpReward;

console.log('[BC] features/economy loaded');
