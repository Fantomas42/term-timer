// A scramble followed move by move, the phone set beside the cube. A
// cursor walks the chips: Space, a tap on the stage or the Next button
// moves it on, Backspace back, a tap on a chip jumps to it. The giant
// move is the one to do now; the cube images show the state reached
// after the moves done (the target before the first one). A horizontal
// swipe changes scramble. The series remembers, in this browser only,
// the scrambles seen and those scrambled to the end; the screen is kept
// on while the page is shown, where the browser allows it.
import { flash, notify } from './ui.js';

const STORAGE_PREFIX = 'scramble:';
// Moves shown after the one to do.
const AHEAD = 3;
// A swipe is a horizontal move of at least this many pixels, clearly
// more horizontal than vertical, so that scrolling never changes page.
const SWIPE_DISTANCE = 70;
const SWIPE_RATIO = 2;

const root = document.querySelector('[data-scramble]');

// Memory of the series -----------------------------------------------

function load(key) {
  try {
    return JSON.parse(localStorage.getItem(key)) || {};
  } catch (error) {
    console.debug('Series not recalled', error);
    return {};
  }
}

function save(key, data) {
  try {
    localStorage.setItem(key, JSON.stringify(data));
  } catch (error) {
    console.debug('Series not remembered', error);
  }
}

function remember(key, index, kind) {
  const data = load(key);
  const list = new Set(data[kind] || []);
  list.add(index);
  data[kind] = Array.from(list).sort((a, b) => a - b);
  data.last = index;
  data.at = Date.now();
  save(key, data);
  return data;
}

function paintSeries(data) {
  const seen = new Set(data.seen || []);
  const done = new Set(data.done || []);
  root.querySelectorAll('[data-series-index]').forEach((link) => {
    const index = Number(link.dataset.seriesIndex);
    link.toggleAttribute('data-seen', seen.has(index));
    link.toggleAttribute('data-done', done.has(index));
  });
}

// Screen kept on ------------------------------------------------------

// The Wake Lock API only exists in a secure context (https or
// localhost): on a phone opening the computer's network address it is
// missing, and the indicator stays hidden.
let wakeLock = null;

async function keepAwake(indicator) {
  if (!('wakeLock' in navigator) || document.visibilityState !== 'visible') {
    return;
  }
  try {
    wakeLock = await navigator.wakeLock.request('screen');
    indicator.hidden = false;
    wakeLock.addEventListener('release', () => {
      indicator.hidden = true;
    });
  } catch (error) {
    console.debug('Screen not kept on', error);
  }
}

// Cursor --------------------------------------------------------------

function mount() {
  const key = STORAGE_PREFIX + root.dataset.series;
  const index = Number(root.dataset.index);
  const stage = root.querySelector('[data-scramble-stage]');
  const alg = root.querySelector('[data-scramble-moves] .alg');
  const chips = Array.from(alg.querySelectorAll('.alg-move'));
  const moves = chips.map((chip) => chip.textContent.trim());
  const now = root.querySelector('[data-scramble-now]');
  const after = root.querySelector('[data-scramble-after]');
  const label = root.querySelector('[data-scramble-label]');
  const caption = root.querySelector('[data-scramble-caption]');
  const controls = root.querySelector('[data-scramble-controls]');
  const primary = controls.querySelector('[data-primary] span');
  const images = Array.from(root.querySelectorAll('.scramble-cube-view img'));
  const targets = images.map((image) => image.src);

  let cursor = 0;
  let request = 0;
  let finished = false;

  // The cube after the first moves: the URL of the image of the whole
  // scramble, its algorithm cut. The next image is loaded before it
  // replaces the shown one, so that the cube never blinks.
  function showCube(count) {
    request += 1;
    const ticket = request;
    images.forEach((image, i) => {
      let url = targets[i];
      if (count > 0 && count < moves.length) {
        const address = new URL(targets[i], location.href);
        address.searchParams.set('algo', moves.slice(0, count).join(' '));
        url = address.pathname + address.search;
      }
      const loader = new Image();
      loader.onload = () => {
        if (ticket === request) image.src = url;
      };
      loader.src = url;
    });
  }

  function render(moved) {
    const total = moves.length;
    const done = cursor >= total;
    root.style.setProperty('--progress', String(cursor / total));
    root.toggleAttribute('data-done', done);

    chips.forEach((chip, i) => {
      if (i < cursor) chip.dataset.state = 'done';
      else if (i === cursor) chip.dataset.state = 'current';
      else delete chip.dataset.state;
    });

    if (done) {
      label.textContent = `Scrambled · ${total} moves`;
      now.textContent = '✓';
      after.textContent = '';
      caption.textContent = 'Scrambled: check your cube against it';
      primary.textContent = root.dataset.next ? 'Next scramble' : 'Done';
    } else {
      label.textContent = cursor === 0
        ? `First move · ${total} to go`
        : `Move ${cursor + 1} of ${total}`;
      now.textContent = moves[cursor];
      after.textContent = moves.slice(cursor + 1, cursor + 1 + AHEAD)
        .join(' ');
      caption.textContent = cursor === 0
        ? 'Target: after the whole scramble'
        : `After move ${cursor}`;
      primary.textContent = 'Next move';
    }

    if (moved) {
      now.classList.remove('is-ticked');
      void now.offsetWidth;
      now.classList.add('is-ticked');
      showCube(cursor);
    }

    if (done && !finished) {
      finished = true;
      paintSeries(remember(key, index, 'done'));
      flash(stage);
      notify(root.dataset.next
        ? 'Scrambled · Space for the next scramble'
        : 'Scrambled · last of the series');
    }
  }

  function go(position) {
    const bounded = Math.max(0, Math.min(moves.length, position));
    if (bounded === cursor) return;
    cursor = bounded;
    render(true);
  }

  function next() {
    if (cursor >= moves.length) {
      if (root.dataset.next) location.href = root.dataset.next;
      return;
    }
    go(cursor + 1);
  }

  const actions = {
    next,
    previous: () => go(cursor - 1),
    restart: () => go(0),
  };

  // A tap on a chip jumps to it; on the rest of the stage, next move.
  // Buttons and links of the stage keep their own job.
  stage.addEventListener('click', (event) => {
    const action = event.target.closest('[data-scramble-action]');
    if (action) {
      actions[action.dataset.scrambleAction]();
      return;
    }
    if (event.target.closest('button, a, input')) return;
    const chip = event.target.closest('.alg-move');
    if (chip) go(chips.indexOf(chip));
    else next();
  });

  document.addEventListener('keydown', (event) => {
    if (event.target.closest?.('input, textarea, select, [contenteditable]')) {
      return;
    }
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (document.querySelector('dialog[open]')) return;

    const keys = {
      ' ': next,
      Backspace: actions.previous,
      r: actions.restart,
    };
    if (!(event.key in keys)) return;
    // Space on a focused button clicks it already.
    if (event.key === ' ' && event.target.closest?.('button, a')) return;
    event.preventDefault();
    keys[event.key]();
  });

  // Swipe -------------------------------------------------------------

  let touch = null;
  root.addEventListener('touchstart', (event) => {
    if (event.touches.length !== 1) {
      touch = null;
      return;
    }
    touch = { x: event.touches[0].clientX, y: event.touches[0].clientY };
  }, { passive: true });

  root.addEventListener('touchend', (event) => {
    if (!touch) return;
    const dx = event.changedTouches[0].clientX - touch.x;
    const dy = event.changedTouches[0].clientY - touch.y;
    touch = null;
    if (Math.abs(dx) < SWIPE_DISTANCE) return;
    if (Math.abs(dx) < SWIPE_RATIO * Math.abs(dy)) return;
    const target = dx < 0 ? root.dataset.next : root.dataset.previous;
    if (target) location.href = target;
  });

  alg.dataset.cursor = '';
  stage.dataset.live = '';
  controls.hidden = false;
  root.querySelector('[data-scramble-hint]').hidden = false;
  render(false);

  paintSeries(remember(key, index, 'seen'));

  const indicator = root.querySelector('[data-scramble-wake]');
  keepAwake(indicator);
  // A hidden page loses its lock: it is taken again when shown.
  document.addEventListener('visibilitychange', () => {
    if (wakeLock && !wakeLock.released) return;
    keepAwake(indicator);
  });
}

if (root) mount();

// Home of the series --------------------------------------------------

const RESUME_COUNT = 8;
const MINUTE = 60 * 1000;

function ago(timestamp) {
  const minutes = Math.round((Date.now() - timestamp) / MINUTE);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? 'yesterday' : `${days} days ago`;
}

// The series of this browser, the last one played first.
function recalled() {
  const series = [];
  try {
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (!key.startsWith(STORAGE_PREFIX)) continue;
      const [cube, seed] = key.slice(STORAGE_PREFIX.length).split(':');
      const data = load(key);
      if (cube && seed && data.last) series.push({ cube, seed, ...data });
    }
  } catch (error) {
    console.debug('Series not recalled', error);
  }
  return series.sort((a, b) => (b.at || 0) - (a.at || 0))
    .slice(0, RESUME_COUNT);
}

function mountResume(home) {
  const holder = home.querySelector('[data-scramble-resume]');
  const list = home.querySelector('[data-scramble-resume-list]');
  const template = home.querySelector('[data-scramble-resume-item]');
  const total = Number(home.dataset.total);
  const series = recalled();
  if (!series.length) return;

  series.forEach((entry) => {
    const item = template.content.cloneNode(true);
    const link = item.querySelector('a');
    const done = (entry.done || []).length;
    link.href = `/scramble/${entry.cube}/${entry.seed}/${entry.last}/`;
    link.style.setProperty('--done', String(done / total));
    const fields = {
      seed: entry.seed,
      cube: `${entry.cube}x${entry.cube}`,
      at: entry.at ? ago(entry.at) : '',
      last: `#${entry.last}`,
      done: `${done} of ${total} scrambled`,
    };
    item.querySelectorAll('[data-field]').forEach((field) => {
      field.textContent = fields[field.dataset.field];
    });
    list.append(item);
  });
  holder.hidden = false;
}

// The command follows the form: size and seed as they are typed.
function mountForm(home) {
  const form = home.querySelector('form');
  const input = form.querySelector('[data-alphabet]');
  const dice = form.querySelector('[data-scramble-dice]');
  const code = form.querySelector('.command-text');
  const copier = form.querySelector('.command [data-copy]');

  function syncCommand() {
    const size = form.querySelector('input[name="c"]:checked')?.value;
    const text = `term-timer scramble -c ${size} -r ${input.value.trim()}`;
    code.lastChild.textContent = ` ${text}`;
    copier.dataset.copy = text;
  }

  function roll() {
    const alphabet = input.dataset.alphabet;
    const draws = crypto.getRandomValues(
      new Uint32Array(Number(input.dataset.length)),
    );
    input.value = Array.from(draws, (draw) => alphabet[draw % alphabet.length])
      .join('');
    dice.classList.remove('is-rolling');
    void dice.offsetWidth;
    dice.classList.add('is-rolling');
    syncCommand();
  }

  dice.hidden = false;
  dice.addEventListener('click', roll);
  form.addEventListener('input', syncCommand);
  form.addEventListener('change', syncCommand);
}

const home = document.querySelector('[data-scramble-home]');
if (home) {
  mountForm(home);
  mountResume(home);
}
