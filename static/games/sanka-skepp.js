/* Sänka skepp – spelfortva.com
   Vanilla JS, inga ramverk och inga externa anrop.
   Struktur: spelmotor (Board) och dator-AI (AI) är fria från DOM, så att ett
   onlineläge (två enheter) kan läggas till senare som en ny spelartyp. */
(function () {
  'use strict';

  var N = 10, COLS = 'ABCDEFGHIJ';
  var FLEET = [
    { name: 'Hangarfartyg', def: 'hangarfartyget', poss: 'ditt', len: 5 },
    { name: 'Slagskepp', def: 'slagskeppet', poss: 'ditt', len: 4 },
    { name: 'Kryssare', def: 'kryssaren', poss: 'din', len: 3 },
    { name: 'Ubåt', def: 'ubåten', poss: 'din', len: 3 },
    { name: 'Jagare', def: 'jagaren', poss: 'din', len: 2 }
  ];

  function coord(i) { return COLS[i % N] + (((i / N) | 0) + 1); }
  function rnd(n) { return Math.floor(Math.random() * n); }
  function step(i, dx, dy) {
    var x = i % N + dx, y = ((i / N) | 0) + dy;
    return x < 0 || y < 0 || x >= N || y >= N ? -1 : y * N + x;
  }
  var D4 = [[0, -1], [-1, 0], [1, 0], [0, 1]];
  var D8 = D4.concat([[-1, -1], [1, -1], [-1, 1], [1, 1]]);
  function around(i, diag) {
    var r = [];
    (diag ? D8 : D4).forEach(function (d) { var j = step(i, d[0], d[1]); if (j >= 0) r.push(j); });
    return r;
  }
  function cellsFor(len, i, horiz) {
    if (i < 0) return null;
    var c = [];
    for (var k = 0; k < len; k++) {
      var j = horiz ? step(i, k, 0) : step(i, 0, k);
      if (j < 0) return null;
      c.push(j);
    }
    return c;
  }

  /* ---------- Spelmotor ---------- */
  // shots: 0 = ej beskjuten, 1 = miss, 2 = träff, 3 = sänkt
  function Board() {
    this.owner = new Int8Array(N * N).fill(-1);
    this.shots = new Int8Array(N * N);
    this.ships = FLEET.map(function () { return null; });
  }
  Board.prototype.canPlace = function (f, i, horiz, noTouch) {
    var c = cellsFor(FLEET[f].len, i, horiz), o = this.owner;
    if (!c) return null;
    var taken = function (j) { return o[j] !== -1 && o[j] !== f; };
    var bad = c.some(function (j) { return taken(j) || (noTouch && around(j, true).some(taken)); });
    return bad ? null : c;
  };
  Board.prototype.place = function (f, cells, horiz) {
    this.remove(f);
    var o = this.owner;
    cells.forEach(function (j) { o[j] = f; });
    this.ships[f] = { cells: cells, horiz: horiz, hits: 0 };
  };
  Board.prototype.remove = function (f) {
    var s = this.ships[f], o = this.owner;
    if (!s) return;
    s.cells.forEach(function (j) { o[j] = -1; });
    this.ships[f] = null;
  };
  Board.prototype.clear = function () { for (var f = 0; f < FLEET.length; f++) this.remove(f); };
  Board.prototype.allPlaced = function () { return this.ships.every(Boolean); };
  Board.prototype.randomize = function (noTouch) {
    for (var tries = 0; tries < 500; tries++) {
      this.clear();
      var ok = true;
      for (var f = 0; f < FLEET.length && ok; f++) {
        ok = false;
        for (var t = 0; t < 400; t++) {
          var h = Math.random() < 0.5, c = this.canPlace(f, rnd(N * N), h, noTouch);
          if (c) { this.place(f, c, h); ok = true; break; }
        }
      }
      if (ok) return true;
    }
    return false;
  };
  Board.prototype.fire = function (i) {
    if (this.shots[i]) return null;
    var f = this.owner[i];
    if (f === -1) { this.shots[i] = 1; return { res: 'miss', i: i }; }
    var s = this.ships[f], sh = this.shots;
    s.hits++;
    sh[i] = 2;
    if (s.hits < FLEET[f].len) return { res: 'hit', i: i };
    s.cells.forEach(function (j) { sh[j] = 3; });
    return { res: 'sunk', i: i, f: f, cells: s.cells.slice() };
  };
  Board.prototype.isSunk = function (f) { var s = this.ships[f]; return !!s && s.hits === FLEET[f].len; };
  Board.prototype.allSunk = function () {
    for (var f = 0; f < FLEET.length; f++) if (!this.isSunk(f)) return false;
    return true;
  };

  /* ---------- Dator-AI ---------- */
  // view: 0 = okänd, 1 = miss eller säkert tom, 2 = träff, 3 = sänkt
  function AI(level, noTouch) {
    this.level = level;
    this.noTouch = noTouch;
    this.view = new Int8Array(N * N);
    this.left = FLEET.map(function (s) { return s.len; });
  }
  AI.prototype.learn = function (r) {
    var v = this.view;
    if (r.res === 'miss') v[r.i] = 1;
    else if (r.res === 'hit') v[r.i] = 2;
    else {
      r.cells.forEach(function (j) { v[j] = 3; });
      this.left.splice(this.left.indexOf(FLEET[r.f].len), 1);
      // Får skeppen inte nudda varandra kan rutorna runt ett sänkt skepp inte innehålla något
      if (this.noTouch) r.cells.forEach(function (j) { around(j, true).forEach(function (k) { if (!v[k]) v[k] = 1; }); });
    }
  };
  AI.prototype.pick = function (list) { return list.length ? list[rnd(list.length)] : -1; };
  AI.prototype.unknown = function () {
    var r = [];
    for (var i = 0; i < N * N; i++) if (!this.view[i]) r.push(i);
    return r;
  };
  // Jaga och sikta: efter en träff, följ linjen om två träffar ligger i rad, annars prova grannrutorna
  AI.prototype.target = function () {
    var v = this.view, line = [], near = [];
    for (var h = 0; h < N * N; h++) {
      if (v[h] !== 2) continue;
      [[1, 0], [0, 1]].forEach(function (d) {
        var a = step(h, d[0], d[1]), b = step(h, -d[0], -d[1]);
        if ((a >= 0 && v[a] === 2) || (b >= 0 && v[b] === 2)) {
          [1, -1].forEach(function (sg) {
            var j = h;
            while (j >= 0 && v[j] === 2) j = step(j, d[0] * sg, d[1] * sg);
            if (j >= 0 && !v[j] && line.indexOf(j) < 0) line.push(j);
          });
        }
      });
      around(h).forEach(function (j) { if (!v[j] && near.indexOf(j) < 0) near.push(j); });
    }
    return line.length ? this.pick(line) : this.pick(near);
  };
  // Sannolikhet: räkna hur många möjliga skeppslägen som täcker varje ruta
  AI.prototype.density = function () {
    var v = this.view, score = new Float64Array(N * N), hunting = true, i, k;
    for (i = 0; i < N * N; i++) if (v[i] === 2) { hunting = false; break; }
    this.left.forEach(function (len) {
      for (var s = 0; s < N * N; s++) {
        for (var o = 0; o < 2; o++) {
          var c = cellsFor(len, s, o === 0);
          if (!c) continue;
          var hits = 0, blocked = false;
          for (k = 0; k < len; k++) {
            var x = v[c[k]];
            if (x === 1 || x === 3) { blocked = true; break; }
            if (x === 2) hits++;
          }
          if (blocked || (!hunting && !hits)) continue;
          var w = hunting ? 1 : Math.pow(6, hits);
          for (k = 0; k < len; k++) if (!v[c[k]]) score[c[k]] += w;
        }
      }
    });
    var minLen = Math.min.apply(null, this.left), cands = [];
    for (i = 0; i < N * N; i++) {
      if (!score[i]) continue;
      // Paritet: varje skepp täcker minst en ruta där (x + y) är delbart med minsta skeppslängden
      if (hunting && ((i % N) + ((i / N) | 0)) % minLen !== 0) continue;
      cands.push(i);
    }
    if (!cands.length) for (i = 0; i < N * N; i++) if (score[i]) cands.push(i);
    var max = 0, best = [];
    cands.forEach(function (j) {
      if (score[j] > max) { max = score[j]; best = [j]; } else if (score[j] === max) best.push(j);
    });
    return this.pick(best);
  };
  AI.prototype.next = function () {
    var i = -1;
    if (this.level === 'hard') i = this.density();
    if (i < 0 && this.level !== 'easy') i = this.target();
    if (i < 0) i = this.pick(this.unknown());
    return i;
  };

  if (typeof module === 'object' && module.exports) {
    module.exports = { Board: Board, AI: AI, FLEET: FLEET, N: N, coord: coord };
    return;
  }

  /* ---------- Gränssnitt ---------- */
  var app = document.getElementById('sanka-skepp');
  if (!app) return;

  var KEY = 'spft-sanka-skepp';
  var LEVELS = { easy: 'Lätt', normal: 'Normal', hard: 'Svår' };
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { saved = {}; }
  function cleanName(s, def) { s = typeof s === 'string' ? s.trim().slice(0, 20) : ''; return s || def; }

  var S = {
    mode: saved.mode === 'pvp' ? 'pvp' : 'ai',
    level: LEVELS[saved.level] ? saved.level : 'normal',
    names: [cleanName(saved.names && saved.names[0], 'Spelare 1'), cleanName(saved.names && saved.names[1], 'Spelare 2')],
    noTouch: saved.noTouch === undefined ? true : !!saved.noTouch, // nya besökare: skepp får inte nudda
    again: !!saved.again, sound: false,
    boards: null, stats: null, turn: 0, over: false, ai: null, gid: 0
  };
  var P = null; // placeringsläge
  var B = null; // stridsläge
  var statusEl = null;
  var started = false; // första renderingen ska inte läsa layout eller flytta sidan

  function store() {
    try {
      localStorage.setItem(KEY, JSON.stringify({ mode: S.mode, level: S.level, names: S.names, noTouch: S.noTouch, again: S.again }));
    } catch (e) { /* lagring är frivillig */ }
  }
  function track(name, params) {
    // Skickas bara om GA4 finns på sidan och besökaren har gett samtycke
    try { if (typeof window.gtag === 'function' && window.spftAnalyticsConsent === true) window.gtag('event', name, params || {}); } catch (e) { /* ignorera */ }
  }

  var actx = null;
  var SOUNDS = { miss: [240, 0.12, 'sine'], hit: [520, 0.16, 'square'], sunk: [180, 0.45, 'sawtooth'], win: [660, 0.6, 'triangle'] };
  function beep(type) {
    if (!S.sound) return;
    try {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)();
      var p = SOUNDS[type], o = actx.createOscillator(), g = actx.createGain(), t = actx.currentTime;
      o.type = p[2];
      o.frequency.setValueAtTime(p[0], t);
      if (type === 'sunk') o.frequency.exponentialRampToValueAtTime(60, t + p[1]);
      if (type === 'win') o.frequency.exponentialRampToValueAtTime(990, t + p[1]);
      g.gain.setValueAtTime(0.07, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + p[1]);
      o.connect(g); g.connect(actx.destination);
      o.start(t); o.stop(t + p[1]);
    } catch (e) { /* ljud är frivilligt */ }
  }

  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    });
    (kids || []).forEach(function (c) { if (c) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return el;
  }
  function btn(text, onclick, cls) { return h('button', { type: 'button', class: 'ss-btn' + (cls ? ' ' + cls : ''), text: text, onclick: onclick }); }
  function show(nodes, focusEl) {
    app.textContent = '';
    nodes.forEach(function (n) { if (n) app.appendChild(n); });
    if (started && app.getBoundingClientRect().top < 0) app.scrollIntoView({ block: 'start' });
    started = true;
    if (focusEl) focusEl.focus({ preventScroll: true });
  }
  function status(text) {
    statusEl = h('p', { class: 'ss-status', role: 'status', 'aria-live': 'polite', text: text || '' });
    return statusEl;
  }
  function say(text) { if (statusEl) statusEl.textContent = text; }

  function toolbar(onSetup) {
    var snd = h('button', { type: 'button', class: 'ss-btn ss-small', 'aria-pressed': String(S.sound) });
    var label = function () { snd.textContent = S.sound ? '🔊 Ljud: på' : '🔈 Ljud: av'; snd.setAttribute('aria-pressed', String(S.sound)); };
    label();
    snd.addEventListener('click', function () { S.sound = !S.sound; label(); if (S.sound) beep('hit'); });
    return h('div', { class: 'ss-bar' }, [snd, onSetup ? null : btn('Nytt spel', setupScreen, 'ss-small')]);
  }

  /* Bräde med etiketter A–J och 1–10. Interaktiva rutor är knappar med rörlig tabindex (piltangenter). */
  function grid(label, interactive, onCell) {
    var el = h('div', { class: 'ss-grid', role: 'group', 'aria-label': label });
    el.appendChild(h('span', { class: 'ss-lab', 'aria-hidden': 'true' }));
    for (var x = 0; x < N; x++) el.appendChild(h('span', { class: 'ss-lab', 'aria-hidden': 'true', text: COLS[x] }));
    var cells = [];
    for (var y = 0; y < N; y++) {
      el.appendChild(h('span', { class: 'ss-lab', 'aria-hidden': 'true', text: String(y + 1) }));
      for (x = 0; x < N; x++) {
        var c = interactive
          ? h('button', { type: 'button', class: 'ss-cell', 'data-i': y * N + x, tabindex: '-1' })
          : h('span', { class: 'ss-cell', role: 'img', 'data-i': y * N + x });
        cells.push(c);
        el.appendChild(c);
      }
    }
    var g = { el: el, cells: cells, cur: 0, onMove: null };
    if (interactive) {
      cells[0].tabIndex = 0;
      el.addEventListener('click', function (e) {
        var c = e.target.closest('.ss-cell');
        if (!c) return;
        setCur(g, +c.dataset.i);
        onCell(+c.dataset.i);
      });
      el.addEventListener('keydown', function (e) {
        var d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
        if (!d) return;
        e.preventDefault();
        var j = step(g.cur, d[0], d[1]);
        if (j < 0) return;
        setCur(g, j);
        cells[j].focus();
        if (g.onMove) g.onMove(j);
      });
    }
    return g;
  }
  function setCur(g, i) { g.cells[g.cur].tabIndex = -1; g.cur = i; g.cells[i].tabIndex = 0; }

  // view: 'own' (egna skepp syns), 'target' (bara skott syns), 'reveal' (allt syns, slutet)
  function paint(g, board, view, last) {
    for (var i = 0; i < N * N; i++) {
      var c = g.cells[i], s = board.shots[i], f = board.owner[i], cls = 'ss-cell', txt = '', lab;
      var shipVisible = f >= 0 && (view !== 'target' || s === 3);
      if (shipVisible) cls += ' ship';
      if (s === 1) { cls += ' miss'; txt = '✕'; lab = 'miss'; }
      else if (s === 2) { cls += ' hit'; txt = '●'; lab = view === 'target' ? 'träff' : 'träff på ' + FLEET[f].name.toLowerCase(); }
      else if (s === 3) { cls += ' sunk'; txt = '●'; lab = 'sänkt ' + FLEET[f].name.toLowerCase(); }
      else lab = view === 'target' ? 'ej beskjuten' : (shipVisible ? FLEET[f].name.toLowerCase() : 'vatten');
      if (i === last) cls += s === 3 ? ' ss-sinkanim' : ' ss-pop';
      c.className = cls;
      c.textContent = txt;
      c.setAttribute('aria-label', coord(i) + ', ' + lab);
    }
  }

  /* ---------- Startskärm ---------- */
  function setupScreen() {
    P = null; B = null; S.gid++;
    var radio = function (val, text) {
      return h('label', null, [h('input', { type: 'radio', name: 'ss-mode', value: val, checked: S.mode === val }), text]);
    };
    var n1 = h('input', { type: 'text', id: 'ss-n1', maxlength: '20', autocomplete: 'off', value: S.names[0] });
    var n2 = h('input', { type: 'text', id: 'ss-n2', maxlength: '20', autocomplete: 'off', value: S.names[1] });
    var lvl = h('select', { id: 'ss-lvl' }, Object.keys(LEVELS).map(function (k) {
      return h('option', { value: k, selected: S.level === k, text: LEVELS[k] });
    }));
    var n1lab = h('span', { text: '' });
    var f2 = h('label', { for: 'ss-n2' }, ['Namn spelare 2', n2]);
    var fl = h('label', { for: 'ss-lvl' }, ['Svårighetsgrad', lvl]);
    var chk = function (key, text) {
      var i = h('input', { type: 'checkbox', checked: S[key] });
      i.addEventListener('change', function () { S[key] = i.checked; });
      return h('label', null, [i, text]);
    };
    var sync = function () {
      var pvp = form.querySelector('input[name=ss-mode]:checked').value === 'pvp';
      f2.hidden = !pvp;
      fl.hidden = pvp;
      n1lab.textContent = pvp ? 'Namn spelare 1' : 'Ditt namn';
    };
    var form = h('form', { class: 'ss-setup', novalidate: true }, [
      h('fieldset', null, [h('legend', { text: 'Välj spelläge' }), h('div', { class: 'ss-seg' }, [
        radio('pvp', 'Två spelare – samma enhet'), radio('ai', 'Mot datorn')])]),
      h('div', { class: 'ss-fields' }, [h('label', { for: 'ss-n1' }, [n1lab, n1]), f2, fl]),
      h('div', { class: 'ss-opts' }, [chk('noTouch', 'Skepp får inte nudda varandra'), chk('again', 'Skjut igen vid träff'), chk('sound', 'Ljud')]),
      h('button', { type: 'submit', class: 'ss-btn ss-primary ss-big', text: 'Starta spelet' })
    ]);
    form.addEventListener('change', sync);
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      S.mode = form.querySelector('input[name=ss-mode]:checked').value;
      S.level = lvl.value;
      S.names = [cleanName(n1.value, 'Spelare 1'), cleanName(n2.value, 'Spelare 2')];
      store();
      track('game_start', { mode: S.mode === 'ai' ? 'computer' : 'same_device', difficulty: S.mode === 'ai' ? S.level : 'none' });
      newGame();
    });
    sync();
    show([h('div', { class: 'ss-h', role: 'heading', 'aria-level': '3', text: 'Nytt spel' }), form]);
  }

  function newGame() {
    S.gid++;
    S.boards = [new Board(), new Board()];
    S.stats = [{ shots: 0, hits: 0 }, { shots: 0, hits: 0 }];
    S.over = false;
    S.turn = 0;
    S.ai = null;
    placementScreen(0);
  }

  /* ---------- Placering ---------- */
  function placementScreen(p) {
    var board = S.boards[p];
    P = { p: p, board: board, sel: 0, horiz: true, offset: 0, hover: -1, drag: null, dragEnd: 0 };
    var list = h('div', { class: 'ss-ships', role: 'group', 'aria-label': 'Skepp att placera' });
    P.shipBtns = FLEET.map(function (s, f) {
      var b = h('button', { type: 'button', class: 'ss-btn ss-small ss-ship' });
      b.addEventListener('click', function () {
        if (Date.now() - P.dragEnd < 400) return;
        selectShip(f, 0, true);
        say(FLEET[f].name + ' vald – tryck på brädet där skeppet ska ligga.');
      });
      b.addEventListener('pointerdown', function (e) {
        if (e.button) return;
        P.drag = { f: f, list: true, moved: false };
      });
      list.appendChild(b);
      return b;
    });
    P.rot = btn('', rotate);
    P.done = btn('Klar', finishPlacement, 'ss-primary');
    var g = grid('Ditt bräde', true, function (i) {
      if (Date.now() - P.dragEnd < 400) return;
      var f = board.owner[i];
      if (f >= 0) {
        P.horiz = board.ships[f].horiz;
        selectShip(f, board.ships[f].cells.indexOf(i), true);
        P.hover = i;
        refresh();
        say(FLEET[f].name + ' upplyft – tryck där skeppet ska ligga, eller tryck Rotera.');
        return;
      }
      tryPlace(i);
    });
    g.el.classList.add('ss-place');
    g.onMove = function (i) { P.hover = i; refresh(); };
    g.el.addEventListener('pointerover', function (e) {
      var c = e.target.closest && e.target.closest('.ss-cell');
      if (c && !P.drag) { P.hover = +c.dataset.i; refresh(); }
    });
    g.el.addEventListener('pointerleave', function () { if (!P.drag) { P.hover = -1; refresh(); } });
    g.el.addEventListener('focusin', function (e) { if (e.target.dataset.i) { P.hover = +e.target.dataset.i; refresh(); } });
    g.el.addEventListener('pointerdown', function (e) {
      var c = e.target.closest('.ss-cell');
      if (!c || e.button) return;
      var i = +c.dataset.i, f = board.owner[i];
      if (f >= 0) P.drag = { f: f, from: i, moved: false, k: board.ships[f].cells.indexOf(i), cells: board.ships[f].cells, horiz: board.ships[f].horiz };
    });
    P.grid = g;
    var who = S.mode === 'ai' ? 'Placera din flotta' : 'Placera din flotta, ' + S.names[p];
    show([
      toolbar(),
      h('div', { class: 'ss-h', role: 'heading', 'aria-level': '3', text: who }),
      h('p', { class: 'ss-help', text: 'Välj ett skepp och tryck på brädet, eller dra skeppet dit. Tryck på ett placerat skepp för att flytta det. R roterar.' }),
      status(''),
      h('div', { class: 'ss-place-layout' }, [
        g.el,
        h('div', null, [list, h('div', { class: 'ss-controls' }, [P.rot, btn('Slumpa', randomPlace), btn('Rensa', clearPlace), P.done])])
      ])
    ]);
    say('Placera ' + FLEET[0].name.toLowerCase() + ' (5 rutor).');
    refresh();
  }
  function nextUnplaced() { for (var f = 0; f < FLEET.length; f++) if (!P.board.ships[f]) return f; return -1; }
  function selectShip(f, k, lift) {
    if (lift && P.board.ships[f]) { P.horiz = P.board.ships[f].horiz; P.board.remove(f); }
    P.sel = f;
    P.offset = k;
    refresh();
  }
  function previewCells() {
    if (P.sel < 0 || P.hover < 0) return { cells: [], ok: false };
    var len = FLEET[P.sel].len, cells = [];
    for (var k = 0; k < len; k++) {
      var j = P.horiz ? step(P.hover, k - P.offset, 0) : step(P.hover, 0, k - P.offset);
      if (j >= 0) cells.push(j);
    }
    var ok = cells.length === len && !!P.board.canPlace(P.sel, cells[0], P.horiz, S.noTouch);
    return { cells: cells, ok: ok };
  }
  function tryPlace(i) {
    if (P.sel < 0) { say('Alla skepp är placerade. Tryck på ett skepp för att flytta det, eller tryck Klar.'); return false; }
    P.hover = i;
    var pv = previewCells();
    if (!pv.ok) {
      say(S.noTouch ? 'Skeppet får inte plats där – det går utanför brädet, krockar eller nuddar ett annat skepp.' : 'Skeppet får inte plats där – det går utanför brädet eller krockar med ett annat skepp.');
      refresh();
      return false;
    }
    var f = P.sel;
    P.board.place(f, pv.cells, P.horiz);
    P.sel = nextUnplaced();
    P.offset = 0;
    say(FLEET[f].name + ' placerad på ' + coord(pv.cells[0]) + '–' + coord(pv.cells[pv.cells.length - 1]) + '.' +
      (P.sel >= 0 ? ' Nu: ' + FLEET[P.sel].name.toLowerCase() + ' (' + FLEET[P.sel].len + ' rutor).' : ' Alla skepp är placerade – tryck Klar.'));
    refresh();
    return true;
  }
  function rotate() {
    if (!P) return;
    P.horiz = !P.horiz;
    say('Skeppen placeras nu ' + (P.horiz ? 'vågrätt.' : 'lodrätt.'));
    refresh();
  }
  function randomPlace() {
    P.board.randomize(S.noTouch);
    P.sel = -1;
    say('Flottan placerades slumpvis. Tryck Klar eller flytta skeppen.');
    refresh();
  }
  function clearPlace() {
    P.board.clear();
    P.sel = 0; P.offset = 0;
    say('Brädet är tomt. Placera ' + FLEET[0].name.toLowerCase() + ' (5 rutor).');
    refresh();
  }
  function refresh() {
    if (!P) return;
    paint(P.grid, P.board, 'own');
    var pv = previewCells();
    pv.cells.forEach(function (j) { P.grid.cells[j].classList.add(pv.ok ? 'prev' : 'prev-bad'); });
    P.shipBtns.forEach(function (b, f) {
      var placed = !!P.board.ships[f];
      b.textContent = (placed ? '✓ ' : '') + FLEET[f].name + ' (' + FLEET[f].len + ')';
      b.classList.toggle('placed', placed);
      b.setAttribute('aria-pressed', String(P.sel === f));
    });
    P.rot.textContent = 'Rotera: ' + (P.horiz ? 'vågrätt ⇄' : 'lodrätt ⇅');
    P.done.disabled = !P.board.allPlaced();
  }
  function cellAt(e) {
    var el = document.elementFromPoint(e.clientX, e.clientY);
    var c = el && el.closest ? el.closest('.ss-place .ss-cell') : null;
    return c ? +c.dataset.i : -1;
  }
  document.addEventListener('pointermove', function (e) {
    if (!P || !P.drag) return;
    var d = P.drag, i = cellAt(e);
    if (!d.moved) {
      if (d.list ? i < 0 : i === d.from) return;
      d.moved = true;
      if (d.list) selectShip(d.f, 0, true);
      else { P.board.remove(d.f); P.sel = d.f; P.offset = d.k; P.horiz = d.horiz; }
    }
    P.hover = i;
    refresh();
  });
  function endDrag(e, cancel) {
    if (!P || !P.drag) return;
    var d = P.drag;
    P.drag = null;
    if (!d.moved) return;
    P.dragEnd = Date.now();
    var i = cancel ? -1 : cellAt(e);
    if (i >= 0 && tryPlace(i)) return;
    if (!d.list) { P.board.place(d.f, d.cells, d.horiz); P.sel = nextUnplaced(); P.offset = 0; }
    P.hover = -1;
    refresh();
  }
  document.addEventListener('pointerup', function (e) { endDrag(e, false); });
  document.addEventListener('pointercancel', function (e) { endDrag(e, true); });
  document.addEventListener('keydown', function (e) {
    if (!P || (e.key !== 'r' && e.key !== 'R') || e.ctrlKey || e.metaKey || e.altKey) return;
    if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
    e.preventDefault();
    rotate();
  });

  function finishPlacement() {
    if (!P.board.allPlaced()) return;
    var p = P.p;
    P = null;
    if (S.mode === 'ai') {
      S.boards[1].randomize(S.noTouch);
      S.ai = new AI(S.level, S.noTouch);
      battleScreen();
    } else if (p === 0) {
      handover(1, function () { placementScreen(1); }, 'Nu ska ' + S.names[1] + ' placera sin flotta. ' + S.names[0] + ', titta bort!');
    } else {
      handover(0, battleScreen, 'Flottorna är på plats. ' + S.names[0] + ' börjar skjuta.');
    }
  }

  /* ---------- Överlämning (döljer alla bräden) ---------- */
  function handover(p, next, note) {
    B = null;
    var ready = btn('Jag är redo', next, 'ss-primary ss-big');
    show([h('div', { class: 'ss-handover' }, [
      h('p', { class: 'ss-hand-icon', 'aria-hidden': 'true', text: '⇄' }),
      h('div', { class: 'ss-h', role: 'heading', 'aria-level': '3', text: 'Ge enheten till ' + S.names[p] }),
      h('p', { text: note || 'Titta inte på skärmen förrän det är din tur.' }),
      ready
    ])], ready);
  }

  /* ---------- Strid ---------- */
  function fleetList(board, isEnemy) {
    var ul = h('ul', { class: 'ss-fleet', 'aria-label': isEnemy ? 'Motståndarens skepp' : 'Dina skepp' });
    FLEET.forEach(function (s, f) {
      var gone = board.isSunk(f);
      ul.appendChild(h('li', { class: gone ? 'gone' : '', text: s.name + ' (' + s.len + ')' + (gone ? ' – sänkt' : '') }));
    });
    return ul;
  }
  function panel(title, g, board, isEnemy) {
    var wrap = h('div', { class: 'ss-panel' + (isEnemy ? ' ss-enemy' : '') }, [h('h3', { text: title }), g.el]);
    var fl = fleetList(board, isEnemy);
    wrap.appendChild(fl);
    return { el: wrap, fleet: fl, board: board, isEnemy: isEnemy };
  }
  function turnText() {
    return S.mode === 'ai' ? 'Din tur – skjut på motståndarens bräde.' : 'Din tur, ' + S.names[B.me] + ' – skjut på motståndarens bräde.';
  }
  function battleScreen() {
    var me = S.mode === 'ai' ? 0 : S.turn, opp = 1 - me;
    B = { me: me, opp: opp, locked: false, gid: S.gid };
    B.tg = grid('Motståndarens bräde', true, shoot);
    B.own = grid('Din flotta', false);
    B.tp = panel(S.mode === 'ai' ? 'Datorns hav – skjut här' : S.names[opp] + 's hav – skjut här', B.tg, S.boards[opp], true);
    B.op = panel(S.mode === 'ai' ? 'Din flotta' : 'Din flotta (' + S.names[me] + ')', B.own, S.boards[me], false);
    B.actions = h('div', { class: 'ss-controls ss-center' });
    show([toolbar(), status(turnText()), h('div', { class: 'ss-boards' }, [B.tp.el, B.op.el]), B.actions], B.tg.cells[B.tg.cur]);
    repaint();
  }
  function repaint(lastTarget, lastOwn) {
    paint(B.tg, S.boards[B.opp], S.over ? 'reveal' : 'target', lastTarget);
    paint(B.own, S.boards[B.me], 'own', lastOwn);
    [B.tp, B.op].forEach(function (pn) { var nf = fleetList(pn.board, pn.isEnemy); pn.el.replaceChild(nf, pn.fleet); pn.fleet = nf; });
  }
  function resultText(r, who) {
    if (r.res === 'miss') return coord(r.i) + ': Miss.';
    if (r.res === 'hit') return coord(r.i) + ': Träff!';
    return coord(r.i) + ': Sänkt! ' + who + ' sänkte ' + FLEET[r.f].def + '.';
  }
  function shoot(i) {
    if (!B || S.over || B.locked) return;
    var me = B.me, opp = B.opp, r = S.boards[opp].fire(i);
    if (!r) { say(coord(i) + ': där har du redan skjutit. Välj en annan ruta.'); return; }
    S.stats[me].shots++;
    if (r.res !== 'miss') S.stats[me].hits++;
    beep(r.res);
    repaint(i);
    var txt = resultText(r, S.mode === 'ai' ? 'Du' : S.names[me]);
    if (S.boards[opp].allSunk()) { endGame(me); return; }
    if (r.res !== 'miss' && S.again) { say(txt + ' Skjut igen.'); return; }
    B.locked = true;
    if (S.mode === 'ai') {
      say(txt + ' Datorn siktar …');
      var gid = B.gid;
      setTimeout(function () { aiTurn(gid); }, 750);
    } else {
      say(txt);
      var pass = btn('Lämna över till ' + S.names[opp], function () {
        S.turn = opp;
        handover(opp, battleScreen);
      }, 'ss-primary ss-big');
      B.actions.appendChild(pass);
      pass.focus({ preventScroll: true });
    }
  }
  function aiTurn(gid) {
    if (!B || S.over || gid !== S.gid) return;
    var i = S.ai.next(), r = S.boards[0].fire(i);
    S.ai.learn(r);
    S.stats[1].shots++;
    if (r.res !== 'miss') S.stats[1].hits++;
    beep(r.res);
    repaint(-1, i);
    var txt = 'Datorn sköt på ' + coord(i) + ' – ' + (r.res === 'miss' ? 'miss.' : r.res === 'hit' ? 'träff!' :
      'och sänkte ' + FLEET[r.f].poss + ' ' + FLEET[r.f].name.toLowerCase() + '!');
    if (S.boards[0].allSunk()) { endGame(1); return; }
    if (r.res !== 'miss' && S.again) {
      say(txt + ' Datorn skjuter igen …');
      setTimeout(function () { aiTurn(gid); }, 750);
      return;
    }
    B.locked = false;
    say(txt + ' Din tur – skjut på motståndarens bräde.');
  }

  /* ---------- Slut ---------- */
  function pct(s) { return s.shots ? Math.round(100 * s.hits / s.shots) : 0; }
  function endGame(w) {
    S.over = true;
    S.gid++;
    var aiWon = S.mode === 'ai' && w === 1;
    beep(aiWon ? 'sunk' : 'win');
    track('game_end', { winner: S.mode === 'ai' ? (aiWon ? 'computer' : 'player') : 'player_' + (w + 1), shots: S.stats[w].shots });
    var title = aiWon ? 'Datorn vann! Bättre lycka nästa gång.' : 'Grattis, ' + (S.mode === 'ai' && S.names[0] === 'Spelare 1' ? 'du' : S.names[w]) + ' vann!';
    var stats = [0, 1].map(function (p) {
      var s = S.stats[p], name = S.mode === 'ai' ? (p === 0 ? 'Du' : 'Datorn') : S.names[p];
      return h('p', { class: 'ss-stats', text: name + ': ' + s.shots + ' skott · ' + s.hits + ' träffar · träffsäkerhet ' + pct(s) + ' %' });
    });
    var again = btn('Spela igen', function () { track('game_start', { mode: S.mode === 'ai' ? 'computer' : 'same_device', difficulty: S.mode === 'ai' ? S.level : 'none' }); newGame(); }, 'ss-primary ss-big');
    var share = btn('Dela spelet', function () {
      track('share_click', { method: navigator.share ? 'native' : 'copy' });
      var url = location.href.split('#')[0], text = 'Spela Sänka skepp gratis för två';
      if (navigator.share) { navigator.share({ title: document.title, text: text, url: url }).catch(function () {}); return; }
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { say('Länken är kopierad – skicka den till en vän!'); }, function () { say('Kopiera länken: ' + url); });
      else say('Kopiera länken: ' + url);
    });
    // Visa båda flottorna öppet
    var g0 = grid(S.mode === 'ai' ? 'Din flotta' : S.names[0] + 's flotta', false);
    var g1 = grid(S.mode === 'ai' ? 'Datorns flotta' : S.names[1] + 's flotta', false);
    paint(g0, S.boards[0], 'reveal');
    paint(g1, S.boards[1], 'reveal');
    var p0 = panel(S.mode === 'ai' ? 'Din flotta' : S.names[0] + 's flotta', g0, S.boards[0], false);
    var p1 = panel(S.mode === 'ai' ? 'Datorns flotta' : S.names[1] + 's flotta', g1, S.boards[1], true);
    B = null;
    show([
      toolbar(),
      h('div', { class: 'ss-end' }, [h('div', { class: 'ss-h ss-end-title', role: 'heading', 'aria-level': '3', text: title })].concat(stats, [h('div', { class: 'ss-controls ss-center' }, [again, share, btn('Ändra inställningar', setupScreen)])])),
      status(''),
      h('div', { class: 'ss-boards' }, [p1.el, p0.el])
    ], again);
  }

  setupScreen();
})();
