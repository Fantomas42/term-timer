// Solve page: the comment edited in place.

const comment = document.querySelector('[data-comment]');

if (comment) {
  const display = comment.querySelector('[data-comment-edit]');
  const form = comment.querySelector('form');
  const input = form.querySelector('textarea');

  display.addEventListener('click', () => {
    display.hidden = true;
    form.hidden = false;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  });

  // Cancel is a reset: the textarea gets its saved comment back.
  form.addEventListener('reset', () => {
    form.hidden = true;
    display.hidden = false;
    display.focus();
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      form.reset();
    } else if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
}
