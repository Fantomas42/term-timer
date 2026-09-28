// The cube renderer turns its cube on the chosen axis: every angle is a
// /cube/ image, the one of the page with its rotation replaced, loaded
// before it is shown so that the animation never blinks.
const stage = document.querySelector('[data-cube-render]');

function mount() {
  const image = stage.querySelector('img');
  const angleOutput = stage.querySelector('[data-cube-render-angle]');
  const controls = document.querySelector('[data-cube-render-controls]');
  const axis = controls.querySelector('[data-cube-render-axis]');
  const slider = controls.querySelector('[data-cube-render-slider]');
  const speed = controls.querySelector('[data-cube-render-speed]');
  const play = controls.querySelector('[data-cube-render-play]');
  const playLabel = play.querySelector('[data-cube-render-play-label]');
  const base = new URL(image.src, location.href);

  let angle = 45;
  let playing = false;
  let timer = null;
  let loader = null;

  // Each letter of the axis turns by the angle; a part after | is a
  // fixed tilt (y|x-34: turned on y, seen from a little above).
  function rotation(value) {
    const [turning, fixed = ''] = axis.value.split('|');
    return Array.from(turning, (letter) => letter + value).join('') + fixed;
  }

  function url(value) {
    const address = new URL(base);
    address.searchParams.set('rotation', rotation(value));
    return address.pathname + address.search;
  }

  function show(value, then) {
    const target = url(value);
    if (loader) loader.onload = null;
    loader = new Image();
    loader.onload = () => {
      angle = value;
      image.src = target;
      slider.value = String(value);
      angleOutput.value = `${value}°`;
      if (then) then();
    };
    loader.onerror = () => {
      if (then) then();
    };
    loader.src = target;
  }

  function step() {
    if (!playing) return;
    show((angle + 1) % 360, () => {
      if (playing) timer = setTimeout(step, Number(speed.value));
    });
  }

  function setPlaying(value) {
    playing = value;
    clearTimeout(timer);
    play.setAttribute('aria-pressed', String(playing));
    playLabel.textContent = playing ? 'Pause' : 'Play';
    if (playing) step();
  }

  play.addEventListener('click', () => setPlaying(!playing));
  slider.addEventListener('input', () => {
    setPlaying(false);
    show(Number(slider.value));
  });
  axis.addEventListener('change', () => show(angle));

  controls.hidden = false;
}

if (stage) mount();
