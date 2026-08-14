// TICOlvidé - options
const serverInput = document.getElementById('serverUrl');
const msg = document.getElementById('msg');
const saved = document.getElementById('saved');

function send(msgData) {
  return chrome.runtime.sendMessage(msgData).catch((e) => ({ ok: false, error: e.message }));
}

async function init() {
  const res = await send({ type: 'getServerUrl' });
  if (res.ok) serverInput.value = res.serverUrl;
}

function show(txt, ok) {
  msg.textContent = txt;
  msg.className = 'msg ' + (ok ? 'ok' : 'err');
}

document.getElementById('saveBtn').addEventListener('click', async () => {
  const url = serverInput.value.trim().replace(/\/+$/, '');
  if (!/^https?:\/\//.test(url)) {
    show('La URL debe comenzar con http:// o https://', false);
    return;
  }
  const res = await send({ type: 'setServerUrl', serverUrl: url });
  if (res.ok) {
    show('Configuración guardada.', true);
    saved.style.display = 'block';
    setTimeout(() => (saved.style.display = 'none'), 2500);
  } else {
    show(res.error || 'Error al guardar.', false);
  }
});

document.getElementById('testBtn').addEventListener('click', async () => {
  show('Probando conexión…', true);
  const res = await send({ type: 'testConnection' });
  show(res.message, res.ok);
});

init();
