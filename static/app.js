document.addEventListener("submit", function (event) {
  var form = event.target;
  if (!form.classList.contains("loading-form")) return;

  var button = form.querySelector('button[type="submit"]');
  if (!button || button.disabled) return;

  button.disabled = true;
  var loadingText = button.dataset.loadingText || "처리 중...";
  button.innerHTML = '<span class="spinner"></span>' + loadingText;
});
