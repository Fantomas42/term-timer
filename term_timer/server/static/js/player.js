// 3D players of the pages: every [data-player] slot plays the
// algorithm of its JSON data block (PlayerData). The TwistyPlayer
// control bar cannot be themed (closed shadow DOM, hardcoded greys), so
// it is replaced by our own controls; the TwistyAlgViewer shadow DOM is
// open and gets a stylesheet reading the theme custom properties. Moves
// without measured timings are paced evenly, so that the controls step
// move by move either way. With a step index, a [data-step] link seeks
// the player to that step.
import { Alg, Move, Pause } from 'https://cdn.cubing.net/v0/js/cubing/alg';
import {
  TwistyAlgViewer,
  TwistyPlayer,
} from 'https://cdn.cubing.net/v0/js/cubing/twisty';

// Duration of a move without measured timings, in milliseconds.
const PACE = 450;

// Custom properties cross the shadow boundary: the viewer follows the
// theme without a single colour in here.
const VIEWER_CSS = `
:host {
  display: block;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--step--1);
  line-height: 1.9;
}

.wrapper {
  display: block;
}

a:hover {
  background: none;
  color: var(--text);
}

twisty-alg-leaf-elem.twisty-alg-line-comment {
  color: var(--text-faint);
  font-size: 0.9em;
  opacity: 1;
}

twisty-alg-leaf-elem.twisty-alg-pause {
  color: var(--warn);
}

.current-move {
  margin: 0 -0.15em;
  padding: 0 0.15em;
  border-radius: 0;
  background: var(--accent);
  color: var(--accent-ink);
}
`;

function evenTiming(count) {
  return Array.from({ length: count }, (_, i) => [i * PACE, (i + 1) * PACE]);
}

function mount(slot) {
  const data = JSON.parse(
    document.getElementById(slot.dataset.player).textContent,
  );
  const parsed = Alg.fromString(data.alg);
  const leaves = Array.from(parsed.childAlgNodes())
    .filter((node) => node.is(Move) || node.is(Pause));
  const timing = data.timing?.length ? data.timing : evenTiming(leaves.length);
  const timed = leaves.length === timing.length;

  const player = new TwistyPlayer({
    alg: parsed,
    experimentalSetupAlg: data.setup,
    experimentalSetupAnchor: data.anchor || 'start',
    puzzle: data.puzzle,
    viewerLink: 'none',
    background: 'none',
    hintFacelets: 'none',
    controlPanel: 'none',
  });

  if (timed) {
    player.experimentalModel.animationTimelineLeavesRequest.set(
      leaves.map((leaf, i) => ({
        animLeaf: leaf,
        start: timing[i][0],
        end: timing[i][1],
      })),
    );
  } else {
    console.debug('Player timing mismatch', leaves.length, timing.length);
  }

  const viewer = new TwistyAlgViewer({ twistyPlayer: player });
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(VIEWER_CSS);
  if (typeof viewer.addCSS === 'function') {
    viewer.addCSS(sheet);
  } else {
    console.debug('TwistyAlgViewer.addCSS is gone: the viewer is unstyled');
  }

  const controls = slot.querySelector('[data-player-controls]');
  slot.prepend(player);
  controls.after(viewer);
  controls.hidden = false;

  // Controls ------------------------------------------------------------

  const model = player.experimentalModel;
  const play = controls.querySelector('[data-player-action="play"]');
  const scrub = controls.querySelector('[data-player-action="scrub"]');
  const time = controls.querySelector('[data-player-action="time"]');
  let timestamp = 0;

  // Index of the last move finished at the current timestamp, -1 before
  // the first one.
  function currentIndex() {
    let index = -1;
    timing.forEach(([_start, end], i) => {
      if (end <= timestamp) index = i;
    });
    return index;
  }

  function seekMove(index) {
    if (!timed) return;
    player.pause();
    if (index < 0) {
      player.jumpToStart();
      return;
    }
    const last = Math.min(index, timing.length - 1);
    model.timestampRequest.set(timing[last][1]);
  }

  controls.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-player-action]');
    if (!button) return;
    const actions = {
      start: () => player.jumpToStart(),
      previous: () => seekMove(currentIndex() - 1),
      next: () => seekMove(currentIndex() + 1),
      play: () => player.togglePlay(),
    };
    actions[button.dataset.playerAction]();
  });

  scrub.addEventListener('input', () => {
    player.pause();
    model.timestampRequest.set(Number(scrub.value));
  });

  model.detailedTimelineInfo.addFreshListener((info) => {
    timestamp = info.timestamp;
    scrub.min = String(info.timeRange.start);
    scrub.max = String(info.timeRange.end);
    scrub.value = String(info.timestamp);
    time.value = (info.timestamp / 1000).toFixed(2);
  });

  model.playingInfo.addFreshListener((info) => {
    play.setAttribute('aria-pressed', String(info.playing));
    play.setAttribute('aria-label', info.playing ? 'Pause' : 'Play');
    play.textContent = info.playing ? '❚❚' : '▶';
  });

  // Steps ---------------------------------------------------------------

  if (!data.index || !Object.keys(data.index).length) return;

  document.addEventListener('click', (event) => {
    const link = event.target.closest('[data-step]');
    if (!link) return;
    const index = data.index[link.dataset.step];
    if (index === undefined) return;
    viewer.jumpToIndex(Math.max(0, index - 1), false);
    const box = slot.getBoundingClientRect();
    if (box.top < 0 || box.bottom > innerHeight) {
      event.preventDefault();
      slot.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
}

document.querySelectorAll('[data-player]').forEach(mount);
