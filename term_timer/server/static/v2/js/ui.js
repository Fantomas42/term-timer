// Behaviour of the V2 components: copy with feedback, ARIA tabs and
// sortable tables. Loaded as a module by v2/skeleton.html.

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

// A copy button with a key hint copies on that key.
document.addEventListener('keydown', (event) => {
  if (event.target.closest?.('input, textarea, select, [contenteditable]')) {
    return;
  }
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  const button = Array.from(document.querySelectorAll('[data-copy-key]'))
    .find((candidate) => candidate.dataset.copyKey === event.key);
  if (button) {
    event.preventDefault();
    copy(button);
  }
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
