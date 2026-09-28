// Behaviour of the V2 components: copy with feedback, keyboard
// shortcuts, ARIA tabs, sortable tables and their folded rows, segmented
// switches, confirmed forms, selects applied as they change and the
// algorithm lookup. Loaded as a module by v2/skeleton.html.

const COPIED_DELAY = 1400;
const TOAST_DELAY = 1600;

// Copy -----------------------------------------------------------------

let toastTimer = null;

export function notify(message) {
  const toast = document.querySelector('.toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('is-visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(
    () => toast.classList.remove('is-visible'), TOAST_DELAY,
  );
}

export async function copy(button) {
  const text = button.dataset.copy;
  try {
    await navigator.clipboard.writeText(text);
  } catch (error) {
    notify('Clipboard unavailable');
    console.debug('Clipboard unavailable', error);
    return;
  }
  const label = button.querySelector('.button-label');
  const moves = text.split(' ').filter(Boolean).length;
  button.classList.add('is-copied');
  label.textContent = 'Copied';
  notify(`${button.dataset.copyLabel} copied · ${moves} moves`);
  setTimeout(() => {
    button.classList.remove('is-copied');
    label.textContent = 'Copy';
  }, COPIED_DELAY);
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-copy]');
  if (button) copy(button);
});

// Keyboard -------------------------------------------------------------

// Flash an element reached by a shortcut or an anchor.
export function flash(element) {
  element.classList.remove('is-flashed');
  void element.offsetWidth;
  element.classList.add('is-flashed');
}

// Scroll to the next or previous numbered section.
function jump(offset) {
  const sections = Array.from(document.querySelectorAll('[data-section]'));
  if (!sections.length) return;
  const current = sections.findIndex(
    (section) => section.getBoundingClientRect().top > 8,
  );
  const base = current === -1 ? sections.length : current;
  const index = base + offset - (offset > 0 ? 0 : 1);
  const target = sections[Math.max(0, Math.min(sections.length - 1, index))];
  target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  flash(target);
}

function toggleHelp() {
  const help = document.querySelector('[data-help]');
  if (!help) return false;
  if (help.open) help.close();
  else help.showModal();
  return true;
}

// A copy button copies on its key; any other element carrying data-key
// is clicked on it; ? opens the help, j and k walk the sections.
document.addEventListener('keydown', (event) => {
  if (event.target.closest?.('input, textarea, select, [contenteditable]')) {
    return;
  }
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  if (document.querySelector('dialog[open]') && event.key !== '?') return;

  const copier = Array.from(document.querySelectorAll('[data-copy-key]'))
    .find((candidate) => candidate.dataset.copyKey === event.key);
  const switcher = Array.from(document.querySelectorAll('[data-segmented-key]'))
    .find((candidate) => candidate.dataset.segmentedKey === event.key);
  const target = Array.from(document.querySelectorAll('[data-key]'))
    .find((candidate) => candidate.dataset.key === event.key);
  const actions = {
    '?': toggleHelp,
    j: () => jump(1),
    k: () => jump(-1),
  };

  let handled = true;
  if (copier) copy(copier);
  else if (switcher) cycleSegmented(switcher);
  else if (target) target.click();
  else if (event.key in actions) handled = actions[event.key]() !== false;
  else handled = false;

  if (handled) event.preventDefault();
});

// Tabs -----------------------------------------------------------------

function selectTab(tab) {
  const list = tab.closest('[role="tablist"]');
  list.querySelectorAll('[role="tab"]').forEach((other) => {
    const selected = other === tab;
    other.setAttribute('aria-selected', String(selected));
    other.tabIndex = selected ? 0 : -1;
    document.getElementById(other.getAttribute('aria-controls'))
      .hidden = !selected;
  });
}

// An anchor pointing into a hidden panel selects that panel first.
function reveal() {
  if (!location.hash) return;
  let target = null;
  try {
    target = document.querySelector(decodeURIComponent(location.hash));
  } catch (error) {
    return;
  }
  if (!target) return;
  const panel = target.closest('[role="tabpanel"][hidden]');
  if (panel) {
    selectTab(document.getElementById(panel.getAttribute('aria-labelledby')));
    target.scrollIntoView({ block: 'start' });
  }
  flash(target);
}

window.addEventListener('hashchange', reveal);
reveal();

document.querySelectorAll('[data-tabs] [role="tablist"]').forEach((list) => {
  const tabs = Array.from(list.querySelectorAll('[role="tab"]'));
  list.addEventListener('click', (event) => {
    const tab = event.target.closest('[role="tab"]');
    if (tab) selectTab(tab);
  });
  list.addEventListener('keydown', (event) => {
    const index = tabs.indexOf(document.activeElement);
    if (index === -1) return;
    const moves = {
      ArrowRight: index + 1,
      ArrowLeft: index - 1,
      Home: 0,
      End: tabs.length - 1,
    };
    if (!(event.key in moves)) return;
    event.preventDefault();
    const target = tabs[(moves[event.key] + tabs.length) % tabs.length];
    target.focus();
    selectTab(target);
  });
});

// Sortable tables ------------------------------------------------------

function sortKey(cell, numeric) {
  const raw = cell?.dataset.sort ?? cell?.textContent.trim() ?? '';
  if (!numeric) return raw;
  const value = parseFloat(raw);
  return Number.isNaN(value) ? Infinity : value;
}

function sortTable(table, header) {
  const headers = Array.from(header.parentElement.children);
  const column = headers.indexOf(header);
  const numeric = header.hasAttribute('data-numeric');
  const ascending = header.getAttribute('aria-sort') !== 'ascending';
  headers.forEach((other) => other.removeAttribute('aria-sort'));
  header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');

  const body = table.tBodies[0];
  const rows = Array.from(body.rows);
  // Sorting ranks every row: the folded ones are shown first.
  if (body.querySelector('tr[data-revealable][hidden]')) {
    revealRows(table.closest('[id]').id);
  }
  rows.sort((a, b) => {
    const left = sortKey(a.cells[column], numeric);
    const right = sortKey(b.cells[column], numeric);
    const order = numeric
      ? left - right
      : String(left).localeCompare(String(right));
    return ascending ? order : -order;
  });
  body.append(...rows);
}

document.querySelectorAll('table[data-sortable]').forEach((table) => {
  table.tHead.addEventListener('click', (event) => {
    const button = event.target.closest('.table-sort');
    if (button) sortTable(table, button.closest('th'));
  });
});

// Folded rows ----------------------------------------------------------

// A button carrying data-reveal shows the rows folded away in the
// element of that id, then goes away.
function revealRows(id) {
  const holder = document.getElementById(id);
  if (!holder) return;
  holder.querySelectorAll('[data-revealable][hidden]').forEach((row) => {
    row.hidden = false;
  });
  document.querySelectorAll(`[data-reveal="${id}"]`).forEach((button) => {
    button.remove();
  });
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-reveal]');
  if (button) revealRows(button.dataset.reveal);
});

// Segmented switches ---------------------------------------------------

// A segmented switch writes its value in a data attribute of its target,
// named after the switch; the choice is remembered in this browser only,
// a convenience that may be lost.
function remember(name, value) {
  try {
    localStorage.setItem(`segmented:${name}`, value);
  } catch (error) {
    console.debug('Choice not remembered', error);
  }
}

function recall(name) {
  try {
    return localStorage.getItem(`segmented:${name}`);
  } catch (error) {
    return null;
  }
}

function applySegmented(group, option, save = true) {
  const name = group.dataset.segmented;
  group.querySelectorAll('[aria-pressed]').forEach((other) => {
    other.setAttribute('aria-pressed', String(other === option));
  });
  const target = document.querySelector(group.dataset.target);
  if (target) target.dataset[name] = option.value;
  if (save) remember(name, option.value);
}

function cycleSegmented(group) {
  const options = Array.from(group.querySelectorAll('[aria-pressed]'));
  const index = options.findIndex(
    (option) => option.getAttribute('aria-pressed') === 'true',
  );
  applySegmented(group, options[(index + 1) % options.length]);
}

document.querySelectorAll('[data-segmented]').forEach((group) => {
  const stored = recall(group.dataset.segmented);
  const option = Array.from(group.querySelectorAll('[aria-pressed]'))
    .find((candidate) => candidate.value === stored);
  if (option) applySegmented(group, option, false);
  group.addEventListener('click', (event) => {
    const chosen = event.target.closest('[aria-pressed]');
    if (chosen) applySegmented(group, chosen);
  });
});

// Confirmed forms -----------------------------------------------------

// A form carrying data-confirm asks its question in the confirmation
// dialog before it is sent; without the dialog it is sent as is.
document.addEventListener('submit', (event) => {
  const form = event.target.closest('form[data-confirm]');
  const dialog = document.querySelector('[data-confirm-dialog]');
  if (!form || !dialog) return;
  event.preventDefault();
  dialog.querySelector('[data-confirm-message]').textContent =
    form.dataset.confirm;
  dialog.returnValue = '';
  dialog.addEventListener('close', () => {
    if (dialog.returnValue === 'confirm') form.submit();
  }, { once: true });
  dialog.showModal();
});

// Forms applied as they change ----------------------------------------

// A select carrying data-autosubmit sends its form as soon as it
// changes; the submit button of the form stays for a page without JS.
document.querySelectorAll('select[data-autosubmit]').forEach((select) => {
  select.addEventListener('change', () => select.form.requestSubmit());
});

// Algorithm lookup ----------------------------------------------------

// / focuses the field, its label carrying the key; Enter opens the page
// of the algorithm typed.
document.querySelectorAll('[data-lookup]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const algorithm = form.querySelector('input').value.trim();
    if (algorithm) {
      window.location.href = `/algorithm/${encodeURIComponent(algorithm)}/`;
    }
  });
});
