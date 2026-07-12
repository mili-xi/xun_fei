const form = document.querySelector('#credential-form');
const statusView = document.querySelector('#status');
const localMode = document.querySelector('#local-mode');
const clearButton = document.querySelector('#clear');

function renderStatus(status) {
  statusView.textContent = JSON.stringify(status, null, 2);
}

async function refreshStatus() {
  renderStatus(await window.xunfeiSettings.getStatus());
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(form);
  const patch = Object.fromEntries(formData.entries());
  renderStatus(await window.xunfeiSettings.save(patch));
  form.reset();
});

localMode.addEventListener('click', async () => {
  renderStatus(await window.xunfeiSettings.continueLocal());
});

clearButton.addEventListener('click', async () => {
  renderStatus(await window.xunfeiSettings.clear());
  form.reset();
});

refreshStatus().catch((error) => {
  statusView.textContent = `设置加载失败：${error.message}`;
});
