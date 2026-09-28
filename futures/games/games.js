/* BELUGACORD 2.5 — MODULE: GAMES */

var GAME_NAMES = {
  penguin:'🐧 Пингвин', minesweeper:'💣 Сапёр', snake:'🐍 Змейка',
  '2048':'🔢 2048', flappy:'🐦 Flappy', tetris:'🧱 Тетрис',
  memory:'🧠 Memory', reaction:'⚡ Реакция', tictactoe:'❌⭕ Крестики',
  rps:'✊ КНБ', battleship:'🚢 Морской бой', duel:'⚔️ Дуэль', freedoom:'💀 DOOM'
};

async function submitGameScore(game, score){
  await api('/games/submit', {method:'POST', body:{token:token, game:game, score:score}});
}

/* ============================================================
   МЕНЮ ИГР
   ============================================================ */
async function openGamesMenu(){
  document.getElementById('gamesMenuModal').classList.add('open');
  var tr = await api('/games/tournament');
  var b = document.getElementById('tournamentBanner');
  if(tr.ok && tr.data.game){
    b.style.display = 'block';
    b.innerHTML = '🏆 ТУРНИР: ' + GAME_NAMES[tr.data.game];
  } else b.style.display = 'none';

  var t3 = await api('/games/top3');
  if(t3.ok){
    var c = document.getElementById('top3Games');
    var html = '', cnt = 0;
    Object.keys(t3.data).forEach(function(g){
      if(t3.data[g] && t3.data[g].length && cnt < 3){
        html += '<div class="shop-section-title">' + GAME_NAMES[g] + '</div>';
        html += t3.data[g].map(function(x, i){
          var m = i === 0 ? '🥇' : i === 1 ? '🥈' : '🥉';
          return '<div style="display:flex;gap:10px;padding:6px 10px;background:var(--bg-input);border-radius:8px;margin-bottom:4px;font-size:12px">' +
            '<div>' + m + '</div>' +
            '<div style="flex:1">' + esc(x.username) + '</div>' +
            '<div style="color:var(--gold);font-weight:900">' + x.score + '</div>' +
          '</div>';
        }).join('');
        cnt++;
      }
    });
    c.innerHTML = html;
  }
}

/* ============================================================
   КРЕСТИКИ-НОЛИКИ
   ============================================================ */
var tttBoard = [], tttPlayer = 'X', tttDone = false;
function openTicTacToe(){
  document.getElementById('tictactoeModal').classList.add('open');
  startTicTacToe();
}
function startTicTacToe(){
  tttBoard = Array(9).fill('');
  tttPlayer = 'X';
  tttDone = false;
  document.getElementById('tttStatus').textContent = 'Твой ход';
  tttRender();
}
function tttRender(){
  var b = document.getElementById('tttBoard');
  b.innerHTML = tttBoard.map(function(v, i){
    return '<div class="game-cell' + (v === 'X' ? ' x' : v === 'O' ? ' o' : '') + '" onclick="tttClick(' + i + ')">' + v + '</div>';
  }).join('');
}
function tttClick(i){
  if(tttBoard[i] || tttDone || tttPlayer !== 'X') return;
  tttBoard[i] = 'X';
  tttRender();
  if(tttCheck('X')){ tttDone = true; document.getElementById('tttStatus').textContent = '🎉 Ты победил!'; submitGameScore('tictactoe', 1); return; }
  if(tttBoard.every(function(v){ return v; })){ tttDone = true; document.getElementById('tttStatus').textContent = 'Ничья'; return; }
  tttPlayer = 'O';
  document.getElementById('tttStatus').textContent = 'Бот думает...';
  setTimeout(tttBot, 500);
}
function tttBot(){
  var empty = tttBoard.map(function(v, i){ return v ? null : i; }).filter(function(v){ return v !== null; });
  if(!empty.length) return;
  var best = empty[Math.floor(Math.random() * empty.length)];
  for(var i = 0; i < empty.length; i++){
    var t = tttBoard.slice(); t[empty[i]] = 'O';
    if(tttCheckArr(t, 'O')){ best = empty[i]; break; }
  }
  for(var i = 0; i < empty.length; i++){
    var t = tttBoard.slice(); t[empty[i]] = 'X';
    if(tttCheckArr(t, 'X')){ best = empty[i]; break; }
  }
  tttBoard[best] = 'O';
  tttRender();
  if(tttCheck('O')){ tttDone = true; document.getElementById('tttStatus').textContent = '😢 Бот победил'; return; }
  if(tttBoard.every(function(v){ return v; })){ tttDone = true; document.getElementById('tttStatus').textContent = 'Ничья'; return; }
  tttPlayer = 'X';
  document.getElementById('tttStatus').textContent = 'Твой ход';
}
function tttCheck(p){ return tttCheckArr(tttBoard, p); }
function tttCheckArr(b, p){
  var lines = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
  return lines.some(function(l){ return b[l[0]] === p && b[l[1]] === p && b[l[2]] === p; });
}

/* ============================================================
   КНБ
   ============================================================ */
function openRps(){
  document.getElementById('rpsModal').classList.add('open');
  document.getElementById('rpsResult').textContent = '';
}
function playRps(choice){
  var opts = ['rock','paper','scissors'];
  var bot = opts[Math.floor(Math.random() * 3)];
  var map = {rock:'✊', paper:'✋', scissors:'✌️'};
  var r = '';
  if(choice === bot) r = '🤝 Ничья! ' + map[choice];
  else if((choice === 'rock' && bot === 'scissors') || (choice === 'paper' && bot === 'rock') || (choice === 'scissors' && bot === 'paper')){
    r = '🎉 Победа! ' + map[choice] + ' vs ' + map[bot];
    submitGameScore('rps', 1);
  } else r = '😢 Проигрыш. ' + map[choice] + ' vs ' + map[bot];
  document.getElementById('rpsResult').textContent = r;
}

/* ============================================================
   МОРСКОЙ БОЙ
   ============================================================ */
var bsMine, bsEnemy, bsTurn;
function openBattleship(){
  document.getElementById('battleshipModal').classList.add('open');
  startBattleship();
}
function startBattleship(){
  bsMine = Array(100).fill(0);
  bsEnemy = Array(100).fill(0);
  bsTurn = 'me';
  var sizes = [4,3,3,2,2,2,1,1,1,1];
  sizes.forEach(function(s){
    var placed = false;
    while(!placed){
      var dir = Math.random() < 0.5 ? 'h' : 'v';
      var x = Math.floor(Math.random() * 10), y = Math.floor(Math.random() * 10);
      var fits = true;
      for(var i = 0; i < s; i++){
        var nx = dir === 'h' ? x + i : x;
        var ny = dir === 'h' ? y : y + i;
        if(nx >= 10 || ny >= 10 || bsEnemy[ny*10+nx]){ fits = false; break; }
      }
      if(fits){
        for(var i = 0; i < s; i++){
          var nx = dir === 'h' ? x + i : x;
          var ny = dir === 'h' ? y : y + i;
          bsEnemy[ny*10+nx] = 1;
        }
        placed = true;
      }
    }
  });
  var cnt = 0;
  while(cnt < 20){
    var x = Math.floor(Math.random() * 10), y = Math.floor(Math.random() * 10);
    if(!bsMine[y*10+x]){ bsMine[y*10+x] = 1; cnt++; }
  }
  bsRender();
  document.getElementById('bsStatus').textContent = 'Стреляй!';
}
function bsRender(){
  var m = document.getElementById('bsMine');
  var e = document.getElementById('bsEnemy');
  if(!m || !e) return;
  m.innerHTML = ''; e.innerHTML = '';
  for(var i = 0; i < 100; i++){
    var cm = document.createElement('div');
    cm.className = 'battleship-cell' + (bsMine[i] === 2 ? ' hit' : bsMine[i] === 3 ? ' miss' : bsMine[i] === 1 ? ' ship' : '');
    m.appendChild(cm);
    var ce = document.createElement('div');
    ce.className = 'battleship-cell' + (bsEnemy[i] === 2 ? ' hit' : bsEnemy[i] === 3 ? ' miss' : '');
    ce.onclick = (function(idx){ return function(){ bsShoot(idx); }; })(i);
    e.appendChild(ce);
  }
}
function bsShoot(i){
  if(bsEnemy[i] === 2 || bsEnemy[i] === 3 || bsTurn !== 'me') return;
  if(bsEnemy[i] === 1){ bsEnemy[i] = 2; document.getElementById('bsStatus').textContent = '🎯 Попал!'; }
  else { bsEnemy[i] = 3; document.getElementById('bsStatus').textContent = 'Промах'; bsTurn = 'bot'; setTimeout(bsBotShoot, 800); }
  bsRender();
  if(bsEnemy.every(function(v){ return v !== 1; })){ document.getElementById('bsStatus').textContent = '🎉 Победа!'; submitGameScore('battleship', 1); }
}
function bsBotShoot(){
  var targets = [];
  for(var i = 0; i < 100; i++) if(bsMine[i] === 1) targets.push(i);
  if(!targets.length){ document.getElementById('bsStatus').textContent = '😢 Победа бота'; return; }
  var idx = targets[Math.floor(Math.random() * targets.length)];
  bsMine[idx] = 2;
  bsTurn = 'me';
  bsRender();
  document.getElementById('bsStatus').textContent = 'Твой ход';
  if(bsMine.every(function(v){ return v !== 1; })) document.getElementById('bsStatus').textContent = '😢 Победа бота';
}

/* ============================================================
   ДУЭЛЬ
   ============================================================ */
function openDuel(){
  document.getElementById('duelModal').classList.add('open');
  document.getElementById('duelResult').textContent = '';
}
function fireDuel(){
  var res = document.getElementById('duelResult');
  if(Math.random() < 0.5){
    res.innerHTML = '🎉 <span style="color:#22c55e">Победа!</span>';
    BC.showConfetti();
    submitGameScore('duel', 1);
  } else res.innerHTML = '😢 <span style="color:#f43f5e">Проигрыш</span>';
}

/* ============================================================
   ЗМЕЙКА
   ============================================================ */
var snakeCtx, snakeInterval, snakeScore = 0, snakeBody, snakeDir, snakeFood, snakeBest = 0;
function openSnake(){
  document.getElementById('snakeModal').classList.add('open');
  var c = document.getElementById('snakeCanvas');
  snakeCtx = c.getContext('2d');
  snakeBest = parseInt(localStorage.getItem('snake_best') || '0');
  document.getElementById('snakeBest').textContent = snakeBest;
}
function startSnake(){
  if(snakeInterval) clearInterval(snakeInterval);
  snakeBody = [{x:10,y:10},{x:9,y:10},{x:8,y:10}];
  snakeDir = {x:1,y:0};
  snakeScore = 0;
  document.getElementById('snakeScore').textContent = 0;
  snakeFood = {x:15,y:15};
  snakeInterval = setInterval(snakeStep, 100);
}
function snakeStep(){
  var head = {x:snakeBody[0].x+snakeDir.x, y:snakeBody[0].y+snakeDir.y};
  if(head.x < 0 || head.x >= 20 || head.y < 0 || head.y >= 20) return snakeEnd();
  for(var i = 0; i < snakeBody.length; i++){
    if(snakeBody[i].x === head.x && snakeBody[i].y === head.y) return snakeEnd();
  }
  snakeBody.unshift(head);
  if(head.x === snakeFood.x && head.y === snakeFood.y){
    snakeScore += 10;
    document.getElementById('snakeScore').textContent = snakeScore;
    snakeFood = {x:Math.floor(Math.random() * 20), y:Math.floor(Math.random() * 20)};
  } else snakeBody.pop();
  snakeCtx.fillStyle = '#000';
  snakeCtx.fillRect(0, 0, 400, 400);
  snakeCtx.fillStyle = '#d946ef';
  snakeBody.forEach(function(p){ snakeCtx.fillRect(p.x*20, p.y*20, 18, 18); });
  snakeCtx.fillStyle = '#ffd700';
  snakeCtx.fillRect(snakeFood.x*20, snakeFood.y*20, 18, 18);
}
function snakeEnd(){
  clearInterval(snakeInterval);
  snakeInterval = null;
  if(snakeScore > snakeBest){
    snakeBest = snakeScore;
    localStorage.setItem('snake_best', snakeBest);
    document.getElementById('snakeBest').textContent = snakeBest;
    submitGameScore('snake', snakeScore);
  }
  showNotice('🐍 Игра: ' + snakeScore);
}
document.addEventListener('keydown', function(e){
  if(document.getElementById('snakeModal').classList.contains('open')){
    if(e.key === 'ArrowUp' || e.key === 'w'){ if(snakeDir.y !== 1){ snakeDir = {x:0,y:-1}; e.preventDefault(); } }
    else if(e.key === 'ArrowDown' || e.key === 's'){ if(snakeDir.y !== -1){ snakeDir = {x:0,y:1}; e.preventDefault(); } }
    else if(e.key === 'ArrowLeft' || e.key === 'a'){ if(snakeDir.x !== 1){ snakeDir = {x:-1,y:0}; e.preventDefault(); } }
    else if(e.key === 'ArrowRight' || e.key === 'd'){ if(snakeDir.x !== -1){ snakeDir = {x:1,y:0}; e.preventDefault(); } }
  }
});

/* ============================================================
   FLAPPY
   ============================================================ */
var flappyCtx, flappyInterval, flappyBirdY, flappyVel, flappyPipes, flappyScore = 0;
function openFlappy(){
  document.getElementById('flappyModal').classList.add('open');
  var c = document.getElementById('flappyCanvas');
  flappyCtx = c.getContext('2d');
}
function startFlappy(){
  if(flappyInterval) clearInterval(flappyInterval);
  flappyBirdY = 250;
  flappyVel = 0;
  flappyPipes = [];
  flappyScore = 0;
  document.getElementById('flappyScore').textContent = 0;
  flappyInterval = setInterval(flappyTick, 30);
}
function flappyTick(){
  flappyVel += 0.5;
  flappyBirdY += flappyVel;
  if(flappyBirdY > 480 || flappyBirdY < 0) return flappyEnd();
  flappyPipes.forEach(function(p){ p.x -= 3; });
  flappyPipes = flappyPipes.filter(function(p){ return p.x > -60; });
  if(!flappyPipes.length || flappyPipes[flappyPipes.length-1].x < 250){
    flappyPipes.push({x:400, gapY:100 + Math.random() * 200, gapH:130, passed:false});
  }
  flappyPipes.forEach(function(p){
    if(!p.passed && p.x + 50 < 80){ p.passed = true; flappyScore++; document.getElementById('flappyScore').textContent = flappyScore; }
  });
  flappyPipes.forEach(function(p){
    if(80 > p.x && 80 < p.x + 50 && (flappyBirdY < p.gapY || flappyBirdY > p.gapY + p.gapH)) return flappyEnd();
  });
  flappyCtx.fillStyle = '#0a0a2a';
  flappyCtx.fillRect(0, 0, 400, 500);
  flappyCtx.fillStyle = '#22c55e';
  flappyPipes.forEach(function(p){
    flappyCtx.fillRect(p.x, 0, 50, p.gapY);
    flappyCtx.fillRect(p.x, p.gapY + p.gapH, 50, 500 - p.gapY - p.gapH);
  });
  flappyCtx.fillStyle = '#ffd700';
  flappyCtx.beginPath();
  flappyCtx.arc(80, flappyBirdY, 15, 0, Math.PI * 2);
  flappyCtx.fill();
}
function flappyEnd(){
  clearInterval(flappyInterval);
  flappyInterval = null;
  if(flappyScore > 0) submitGameScore('flappy', flappyScore);
  showNotice('🐦 Flappy: ' + flappyScore);
}
document.addEventListener('keydown', function(e){
  if(document.getElementById('flappyModal').classList.contains('open') && e.key === ' '){
    flappyVel = -7;
    e.preventDefault();
  }
});
document.addEventListener('click', function(e){
  if(document.getElementById('flappyModal').classList.contains('open') && e.target.id === 'flappyCanvas'){
    flappyVel = -7;
  }
});

/* ============================================================
   ТЕТРИС
   ============================================================ */
var tetrisCtx, tetrisInterval, tetrisScore = 0, tetrisLines = 0, tetrisField, tetrisPiece, tetrisPos, tetrisPieceColor;
var TETRIS_SHAPES = [[[1,1,1,1]], [[1,1],[1,1]], [[0,1,0],[1,1,1]], [[1,0,0],[1,1,1]], [[0,0,1],[1,1,1]], [[1,1,0],[0,1,1]], [[0,1,1],[1,1,0]]];
var TETRIS_COLORS = ['#22d3ee','#ffd700','#8b5cf6','#f43f5e','#22c55e','#ff8c00','#ec4899'];
function openTetris(){
  document.getElementById('tetrisModal').classList.add('open');
  var c = document.getElementById('tetrisCanvas');
  tetrisCtx = c.getContext('2d');
}
function startTetris(){
  if(tetrisInterval) clearInterval(tetrisInterval);
  tetrisField = Array(20).fill(null).map(function(){ return Array(10).fill(0); });
  tetrisScore = 0;
  tetrisLines = 0;
  document.getElementById('tetrisScore').textContent = 0;
  document.getElementById('tetrisLines').textContent = 0;
  tetrisSpawn();
  tetrisInterval = setInterval(tetrisTick, 500);
}
function tetrisSpawn(){
  tetrisPiece = TETRIS_SHAPES[Math.floor(Math.random() * TETRIS_SHAPES.length)];
  tetrisPieceColor = TETRIS_COLORS[Math.floor(Math.random() * TETRIS_COLORS.length)];
  tetrisPos = {x:Math.floor((10 - tetrisPiece[0].length) / 2), y:0};
}
function tetrisTick(){
  tetrisPos.y++;
  if(tetrisCollide()){ tetrisPos.y--; tetrisLock(); }
}
function tetrisCollide(){
  for(var y = 0; y < tetrisPiece.length; y++){
    for(var x = 0; x < tetrisPiece[y].length; x++){
      if(!tetrisPiece[y][x]) continue;
      var ny = tetrisPos.y + y, nx = tetrisPos.x + x;
      if(nx < 0 || nx >= 10 || ny >= 20) return true;
      if(ny >= 0 && tetrisField[ny][nx]) return true;
    }
  }
  return false;
}
function tetrisLock(){
  tetrisPiece.forEach(function(row, y){
    row.forEach(function(v, x){
      if(v){
        var ny = tetrisPos.y + y;
        if(ny >= 0) tetrisField[ny][tetrisPos.x + x] = tetrisPieceColor;
      }
    });
  });
  var cleared = 0;
  for(var y = 19; y >= 0; y--){
    if(tetrisField[y].every(function(v){ return v; })){
      tetrisField.splice(y, 1);
      tetrisField.unshift(Array(10).fill(0));
      cleared++;
      y++;
    }
  }
  if(cleared){
    tetrisLines += cleared;
    tetrisScore += cleared * 100;
    document.getElementById('tetrisScore').textContent = tetrisScore;
    document.getElementById('tetrisLines').textContent = tetrisLines;
  }
  tetrisSpawn();
  tetrisDraw();
  if(tetrisCollide()){
    clearInterval(tetrisInterval);
    tetrisInterval = null;
    if(tetrisScore > 0) submitGameScore('tetris', tetrisScore);
    showNotice('🧱 Игра: ' + tetrisScore);
  }
}
function tetrisDraw(){
  tetrisCtx.fillStyle = '#000';
  tetrisCtx.fillRect(0, 0, 300, 500);
  tetrisField.forEach(function(row, y){
    row.forEach(function(v, x){
      if(v){ tetrisCtx.fillStyle = v; tetrisCtx.fillRect(x*30, y*25, 28, 23); }
    });
  });
  if(tetrisPiece){
    tetrisPiece.forEach(function(row, y){
      row.forEach(function(v, x){
        if(v){ tetrisCtx.fillStyle = tetrisPieceColor; tetrisCtx.fillRect((tetrisPos.x + x)*30, (tetrisPos.y + y)*25, 28, 23); }
      });
    });
  }
}
document.addEventListener('keydown', function(e){
  if(document.getElementById('tetrisModal').classList.contains('open') && tetrisPiece){
    if(e.key === 'ArrowLeft'){ tetrisPos.x--; if(tetrisCollide()) tetrisPos.x++; tetrisDraw(); e.preventDefault(); }
    else if(e.key === 'ArrowRight'){ tetrisPos.x++; if(tetrisCollide()) tetrisPos.x--; tetrisDraw(); e.preventDefault(); }
    else if(e.key === 'ArrowDown'){ tetrisPos.y++; if(tetrisCollide()){ tetrisPos.y--; tetrisLock(); } tetrisDraw(); e.preventDefault(); }
    else if(e.key === 'ArrowUp'){
      var rotated = tetrisPiece[0].map(function(_, i){ return tetrisPiece.map(function(r){ return r[i]; }).reverse(); });
      var old = tetrisPiece;
      tetrisPiece = rotated;
      if(tetrisCollide()) tetrisPiece = old;
      tetrisDraw();
      e.preventDefault();
    }
  }
});

/* ============================================================
   2048
   ============================================================ */
var g2048Grid, g2048Score = 0;
function open2048(){
  document.getElementById('game2048Modal').classList.add('open');
}
function start2048(){
  g2048Grid = Array(4).fill(null).map(function(){ return Array(4).fill(0); });
  g2048Score = 0;
  document.getElementById('g2048Score').textContent = 0;
  g2048Spawn(); g2048Spawn();
  g2048Render();
}
function g2048Spawn(){
  var empties = [];
  for(var y = 0; y < 4; y++) for(var x = 0; x < 4; x++) if(!g2048Grid[y][x]) empties.push({x:x, y:y});
  if(!empties.length) return;
  var e = empties[Math.floor(Math.random() * empties.length)];
  g2048Grid[e.y][e.x] = Math.random() < 0.9 ? 2 : 4;
}
function g2048Render(){
  var b = document.getElementById('g2048Board');
  b.style.cssText = 'display:grid;grid-template-columns:repeat(4,1fr);gap:8px;background:var(--bg-input);padding:10px;border-radius:12px;max-width:400px;margin:0 auto';
  var colors = {2:'#3a3a5a',4:'#4a4a7a',8:'#8b5cf6',16:'#d946ef',32:'#f43f5e',64:'#ff8c00',128:'#ffd700',256:'#22d3ee',512:'#22c55e',1024:'#06b6d4',2048:'#ec4899'};
  b.innerHTML = g2048Grid.map(function(row){
    return row.map(function(v){
      return '<div style="aspect-ratio:1;background:' + (colors[v] || '#1a1a2a') + ';border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:' + (v >= 100 ? '18' : '24') + 'px;font-weight:900;color:' + (v <= 4 ? '#888' : '#fff') + '">' + (v || '') + '</div>';
    }).join('');
  }).join('');
}
function g2048Move(dir){
  var moved = false;
  var grid = g2048Grid.map(function(r){ return r.slice(); });
  for(var i = 0; i < 4; i++){
    var line = [];
    for(var j = 0; j < 4; j++){
      var y, x;
      if(dir === 'left'){ y = i; x = j; }
      else if(dir === 'right'){ y = i; x = 3 - j; }
      else if(dir === 'up'){ y = j; x = i; }
      else { y = 3 - j; x = i; }
      if(grid[y][x]) line.push(grid[y][x]);
    }
    var merged = [];
    for(var k = 0; k < line.length; k++){
      if(line[k] === line[k+1]){ merged.push(line[k] * 2); g2048Score += line[k] * 2; k++; }
      else merged.push(line[k]);
    }
    while(merged.length < 4) merged.push(0);
    for(var j2 = 0; j2 < 4; j2++){
      var y2, x2;
      if(dir === 'left'){ y2 = i; x2 = j2; }
      else if(dir === 'right'){ y2 = i; x2 = 3 - j2; }
      else if(dir === 'up'){ y2 = j2; x2 = i; }
      else { y2 = 3 - j2; x2 = i; }
      if(g2048Grid[y2][x2] !== merged[j2]) moved = true;
      g2048Grid[y2][x2] = merged[j2];
    }
  }
  if(moved){ g2048Spawn(); g2048Render(); document.getElementById('g2048Score').textContent = g2048Score; }
}
document.addEventListener('keydown', function(e){
  if(!document.getElementById('game2048Modal').classList.contains('open')) return;
  if(e.key === 'ArrowLeft'){ g2048Move('left'); e.preventDefault(); }
  else if(e.key === 'ArrowRight'){ g2048Move('right'); e.preventDefault(); }
  else if(e.key === 'ArrowUp'){ g2048Move('up'); e.preventDefault(); }
  else if(e.key === 'ArrowDown'){ g2048Move('down'); e.preventDefault(); }
});

/* ============================================================
   MEMORY
   ============================================================ */
var memCards = [], memFlipped = [], memMoves = 0, memFound = 0;
function openMemory(){
  document.getElementById('memoryModal').classList.add('open');
}
function startMemory(){
  var emojis = ['🍕','🍔','⚽','🎮','💎','🏆','🌹','🐱'];
  memCards = emojis.concat(emojis).sort(function(){ return Math.random() - 0.5; });
  memFlipped = [];
  memMoves = 0;
  memFound = 0;
  document.getElementById('memoryMoves').textContent = 0;
  document.getElementById('memoryFound').textContent = 0;
  memRender(true);
  setTimeout(function(){ memRender(false); }, 3000);
}
function memRender(showAll){
  var b = document.getElementById('memoryBoard');
  b.style.cssText = 'display:grid;grid-template-columns:repeat(4,1fr);gap:8px;max-width:400px;margin:0 auto';
  b.innerHTML = memCards.map(function(c, i){
    var open = showAll || memFlipped.indexOf(i) !== -1;
    return '<div style="aspect-ratio:1;background:' + (open ? 'var(--accent)' : 'var(--bg-input)') + ';border:2px solid var(--border);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:32px;cursor:pointer" onclick="memClick(' + i + ')">' + (open ? c : '?') + '</div>';
  }).join('');
}
function memClick(i){
  if(memFlipped.indexOf(i) !== -1) return;
  if(memFlipped.length >= 2) return;
  memFlipped.push(i);
  memRender(false);
  if(memFlipped.length === 2){
    memMoves++;
    document.getElementById('memoryMoves').textContent = memMoves;
    var a = memFlipped[0], b = memFlipped[1];
    if(memCards[a] === memCards[b]){
      memFound++;
      document.getElementById('memoryFound').textContent = memFound;
      memFlipped = [];
      if(memFound === 8){
        showNotice('🧠 Победа!');
        submitGameScore('memory', Math.max(0, 100 - memMoves));
      }
    } else setTimeout(function(){ memFlipped = []; memRender(false); }, 800);
  }
}

/* ============================================================
   РЕАКЦИЯ
   ============================================================ */
var reactState = 'idle', reactStart = 0, reactBest = parseInt(localStorage.getItem('reaction_best') || '0');
function openReaction(){
  document.getElementById('reactionModal').classList.add('open');
  document.getElementById('reactionBest').textContent = reactBest || '—';
  reactState = 'idle';
  var area = document.getElementById('reactionArea');
  area.style.background = 'var(--bg-input)';
  area.textContent = 'Нажми, чтобы начать';
}
document.addEventListener('click', function(e){
  if(e.target.id !== 'reactionArea') return;
  var area = document.getElementById('reactionArea');
  if(reactState === 'idle'){
    reactState = 'wait';
    area.style.background = '#f43f5e';
    area.textContent = 'Жди зелёный...';
    var delay = 1000 + Math.random() * 3000;
    setTimeout(function(){
      if(reactState === 'wait'){
        reactState = 'go';
        area.style.background = '#22c55e';
        area.textContent = 'ЖМИ!';
        reactStart = Date.now();
      }
    }, delay);
  } else if(reactState === 'wait'){
    reactState = 'idle';
    area.style.background = 'var(--bg-input)';
    area.textContent = 'Рано! Нажми ещё раз';
  } else if(reactState === 'go'){
    var ms = Date.now() - reactStart;
    reactState = 'idle';
    area.style.background = 'var(--bg-input)';
    area.textContent = ms + ' мс';
    if(!reactBest || ms < reactBest){
      reactBest = ms;
      localStorage.setItem('reaction_best', ms);
      document.getElementById('reactionBest').textContent = ms;
      submitGameScore('reaction', Math.max(0, 1000 - ms));
      showNotice('⚡ ' + ms + ' мс!');
    }
  }
});

/* ============================================================
   САПЁР
   ============================================================ */
var minesGrid, minesFlags = 0, minesTime = 0, minesInterval;
function openMinesweeper(){
  document.getElementById('minesweeperModal').classList.add('open');
}
function startMinesweeper(){
  minesGrid = [];
  for(var y = 0; y < 10; y++){
    minesGrid.push([]);
    for(var x = 0; x < 10; x++) minesGrid[y].push({mine:false, revealed:false, flag:false, count:0});
  }
  for(var i = 0; i < 10; i++){
    var my = Math.floor(Math.random() * 10);
    var mx = Math.floor(Math.random() * 10);
    if(!minesGrid[my][mx].mine) minesGrid[my][mx].mine = true;
    else i--;
  }
  for(var y = 0; y < 10; y++) for(var x = 0; x < 10; x++){
    var c = 0;
    for(var dy = -1; dy <= 1; dy++) for(var dx = -1; dx <= 1; dx++){
      var ny = y + dy, nx = x + dx;
      if(ny >= 0 && ny < 10 && nx >= 0 && nx < 10 && minesGrid[ny][nx].mine) c++;
    }
    minesGrid[y][x].count = c;
  }
  minesFlags = 0;
  minesTime = 0;
  document.getElementById('minesFlags').textContent = 0;
  document.getElementById('minesTime').textContent = 0;
  if(minesInterval) clearInterval(minesInterval);
  minesInterval = setInterval(function(){ minesTime++; document.getElementById('minesTime').textContent = minesTime; }, 1000);
  minesRender();
}
function minesRender(){
  var b = document.getElementById('minesweeperBoard');
  b.style.cssText = 'display:inline-grid;grid-template-columns:repeat(10,32px);gap:2px;background:var(--bg-input);padding:8px;border-radius:12px';
  b.innerHTML = minesGrid.map(function(row, y){
    return row.map(function(c, x){
      var txt = '';
      if(c.revealed){ if(c.mine) txt = '💣'; else if(c.count) txt = c.count; }
      else if(c.flag) txt = '🚩';
      return '<div class="battleship-cell" style="background:' + (c.revealed ? (c.mine ? '#dc2626' : '#2a2a3a') : '#1e40af') + ';display:flex;align-items:center;justify-content:center;font-weight:900;color:#fff;font-size:14px" onclick="minesClick(' + x + ',' + y + ')" oncontextmenu="event.preventDefault();minesFlag(' + x + ',' + y + ')">' + txt + '</div>';
    }).join('');
  }).join('');
}
function minesClick(x, y){
  var c = minesGrid[y][x];
  if(c.revealed || c.flag) return;
  if(c.mine){ c.revealed = true; minesRender(); clearInterval(minesInterval); showNotice('💣 БАХ!', 'error'); return; }
  c.revealed = true;
  if(c.count === 0){
    for(var dy = -1; dy <= 1; dy++) for(var dx = -1; dx <= 1; dx++){
      var ny = y + dy, nx = x + dx;
      if(ny >= 0 && ny < 10 && nx >= 0 && nx < 10 && !minesGrid[ny][nx].revealed) minesClick(nx, ny);
    }
  }
  minesRender();
}
function minesFlag(x, y){
  var c = minesGrid[y][x];
  if(c.revealed) return;
  c.flag = !c.flag;
  minesFlags += c.flag ? 1 : -1;
  document.getElementById('minesFlags').textContent = minesFlags;
  minesRender();
}

/* ============================================================
   ПИНГВИН 3D
   ============================================================ */
var penguin3DInterval, penguin3DScore;
function openPenguin3D(){ document.getElementById('penguin3dModal').classList.add('open'); }
function startPenguin3D(){
  var area = document.getElementById('penguin3dArea');
  penguin3DScore = 0;
  var platforms = [{x:0,y:350,w:200},{x:250,y:300,w:100},{x:120,y:230,w:130},{x:280,y:170,w:100},{x:60,y:110,w:130},{x:230,y:50,w:170}];
  var py = 320, vy = 0, onGround = false, currentX = 50;
  var keys = {};
  document.onkeydown = function(e){ keys[e.key] = true; };
  document.onkeyup = function(e){ keys[e.key] = false; };
  area.innerHTML = '<div id="penguinSprite" style="position:absolute;font-size:40px;left:50px;top:320px;transition:left 0.05s,top 0.05s">🐧</div><div id="penguinScore" style="position:absolute;top:10px;left:10px;color:#fff;font-weight:900;font-size:16px">Очки: 0</div>';
  if(penguin3DInterval) clearInterval(penguin3DInterval);
  penguin3DInterval = setInterval(function(){
    vy += 0.6;
    py += vy;
    onGround = false;
    for(var i = 0; i < platforms.length; i++){
      var p = platforms[i];
      if(currentX + 30 > p.x && currentX < p.x + p.w && py > p.y - 5 && py < p.y + 10 && vy >= 0){
        py = p.y - 40;
        vy = 0;
        onGround = true;
        if(p.y < penguin3DScore * 50 + 300){
          penguin3DScore++;
          document.getElementById('penguinScore').textContent = 'Очки: ' + penguin3DScore;
        }
      }
    }
    if(currentX > 200 || currentX < 0) currentX = 50;
    if(currentX + 30 > 200) currentX = 170;
    if(keys['ArrowRight'] || keys['d']) currentX += 2;
    if(keys['ArrowLeft'] || keys['a']) currentX -= 2;
    if((keys['ArrowUp'] || keys['w'] || keys[' ']) && onGround) vy = -10;
    py = Math.max(0, Math.min(380, py));
    var sp = document.getElementById('penguinSprite');
    if(sp){ sp.style.left = currentX + 'px'; sp.style.top = py + 'px'; }
  }, 30);
}

/* ============================================================
   DOOM / ITCH
   ============================================================ */
function openDoom(){
  document.getElementById('gamesMenuModal').classList.remove('open');
  document.getElementById('doomModal').classList.add('open');
  var embed = document.getElementById('doomEmbed');
  if(!embed) return;
  embed.innerHTML = '<iframe src="https://dos.zone/doom-dec-1993/" style="width:100%;height:100%;border:none" allowfullscreen allow="autoplay; gamepad; fullscreen"></iframe>';
}
function openItch(){
  document.getElementById('gamesMenuModal').classList.remove('open');
  document.getElementById('itchModal').classList.add('open');
  api('/itch/list').then(function(res){
    var list = document.getElementById('itchGameList');
    if(!res.ok){ list.innerHTML = '<div style="text-align:center;color:var(--text-mute);padding:20px">Не настроено</div>'; return; }
    list.innerHTML = (res.data.games || []).map(function(g){
      return '<div class="game-tile-2" style="margin-bottom:8px" onclick="playItch(\'' + esc(g.url) + '\')"><div style="font-size:32px">' + g.emoji + '</div><div style="font-size:12px;font-weight:800;margin-top:6px">' + esc(g.name) + '</div></div>';
    }).join('') || '<div style="text-align:center;color:var(--text-mute);padding:20px">Пусто</div>';
  });
}
function playItch(url){
  var e = document.getElementById('itchEmbed');
  if(!e) return;
  e.style.display = 'block';
  e.innerHTML = '<iframe src="' + url + '" style="width:100%;height:100%;border:none"></iframe>';
}

/* ============================================================
   ТУРНИР
   ============================================================ */
async function openTournament(){
  document.getElementById('gamesMenuModal').classList.remove('open');
  document.getElementById('tournamentModal').classList.add('open');
  loadTournament();
}
async function loadTournament(){
  var tr = await api('/games/tournament');
  if(!tr.ok) return;
  var d = tr.data;
  var g = document.getElementById('tournamentGames');
  g.innerHTML = Object.keys(GAME_NAMES).map(function(k){
    return '<button class="save-btn gray tournament-game' + (d.game === k ? ' active' : '') + '" style="margin:0" onclick="setTournament(\'' + k + '\')">' + GAME_NAMES[k] + '</button>';
  }).join('');
  if(d.game){
    document.getElementById('tournamentStatus').textContent = '🏆 ' + GAME_NAMES[d.game];
    var lr = await api('/games/leaders?game=' + d.game);
    if(lr.ok){
      document.getElementById('tournamentLeaders').innerHTML = lr.data.slice(0, 10).map(function(x, i){
        var m = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : '#' + (i+1);
        return '<div style="display:flex;gap:12px;padding:8px 12px;background:var(--bg-input);border-radius:8px;margin-bottom:4px">' +
          '<div style="min-width:32px;font-weight:900">' + m + '</div>' +
          '<div style="flex:1">' + esc(x.username) + '</div>' +
          '<div style="color:var(--gold);font-weight:900">' + x.score + '</div>' +
        '</div>';
      }).join('') || '<div style="text-align:center;color:var(--text-mute)">Пока никто</div>';
    }
  } else {
    document.getElementById('tournamentStatus').textContent = 'Не активен';
    document.getElementById('tournamentLeaders').innerHTML = '';
  }
}
async function setTournament(game){
  if(!BC.isOwner) return;
  var res = await api('/games/tournament_set', {method:'POST', body:{token:token, game:game}});
  if(res.ok){ showNotice('🏆'); loadTournament(); }
}
async function resetTournament(){
  if(!BC.isOwner) return;
  var tr = await api('/games/tournament');
  if(!tr.ok || !tr.data.game) return;
  if(!confirm('Сбросить?')) return;
  await api('/games/tournament_reset', {method:'POST', body:{token:token, game:tr.data.game}});
  loadTournament();
}
async function clearTournament(){
  if(!BC.isOwner) return;
  await api('/games/tournament_set', {method:'POST', body:{token:token, game:null}});
  loadTournament();
}
async function openGamesLeaders(){
  document.getElementById('gamesMenuModal').classList.remove('open');
  document.getElementById('gamesLeadersModal').classList.add('open');
  var b = document.getElementById('gamesLeadersBody');
  b.innerHTML = '<div style="text-align:center;padding:40px">Загрузка...</div>';
  var h = '';
  for(var k in GAME_NAMES){
    var res = await api('/games/leaders?game=' + k);
    if(res.ok && res.data.length){
      h += '<div class="shop-section-title">' + GAME_NAMES[k] + '</div>';
      h += res.data.slice(0, 3).map(function(x, i){
        var m = i === 0 ? '🥇' : i === 1 ? '🥈' : '🥉';
        return '<div style="display:flex;gap:10px;padding:8px 12px;background:var(--bg-input);border-radius:8px;margin-bottom:4px;font-size:13px">' +
          '<div>' + m + '</div>' +
          '<div style="flex:1">' + esc(x.username) + '</div>' +
          '<div style="color:var(--gold);font-weight:900">' + x.score + '</div>' +
        '</div>';
      }).join('');
    }
  }
  b.innerHTML = h || '<div style="text-align:center;color:var(--text-mute);padding:40px">Пусто</div>';
}

/* ============================================================
   ЭКСПОРТ
   ============================================================ */
window.openGamesMenu = openGamesMenu;
window.openTicTacToe = openTicTacToe;
window.startTicTacToe = startTicTacToe;
window.tttClick = tttClick;
window.openRps = openRps;
window.playRps = playRps;
window.openBattleship = openBattleship;
window.startBattleship = startBattleship;
window.bsShoot = bsShoot;
window.openDuel = openDuel;
window.fireDuel = fireDuel;
window.openSnake = openSnake;
window.startSnake = startSnake;
window.openFlappy = openFlappy;
window.startFlappy = startFlappy;
window.openTetris = openTetris;
window.startTetris = startTetris;
window.open2048 = open2048;
window.start2048 = start2048;
window.openMemory = openMemory;
window.startMemory = startMemory;
window.memClick = memClick;
window.openReaction = openReaction;
window.openMinesweeper = openMinesweeper;
window.startMinesweeper = startMinesweeper;
window.minesClick = minesClick;
window.minesFlag = minesFlag;
window.openPenguin3D = openPenguin3D;
window.startPenguin3D = startPenguin3D;
window.openDoom = openDoom;
window.openItch = openItch;
window.playItch = playItch;
window.openTournament = openTournament;
window.setTournament = setTournament;
window.resetTournament = resetTournament;
window.clearTournament = clearTournament;
window.openGamesLeaders = openGamesLeaders;

console.log('[BC] features/games loaded');
