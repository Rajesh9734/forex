document.querySelectorAll('[data-sort]').forEach(select => {
  select.addEventListener('change', () => {
    const url = new URL(window.location.href);
    url.searchParams.set('sort', select.value);
    url.searchParams.delete('page');
    window.location.assign(url);
  });
});
document.querySelectorAll('form').forEach(form => {
  form.addEventListener('submit', () => {
    const button = form.querySelector('[data-busy-text]');
    if (button) {
      button.disabled = true;
      button.textContent = button.dataset.busyText;
    }
  });
});
document.addEventListener('click', event => {
  document.querySelectorAll('.export-menu[open]').forEach(menu => {
    if (!menu.contains(event.target)) menu.removeAttribute('open');
  });
});
