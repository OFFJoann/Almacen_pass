// TICOlvidé - popup
const $ = (id) => document.getElementById(id);

let currentTab = null;
let currentHostname = '';
let activeTab = 'site';
let matchedEntries = [];
let allEntries = [];

function send(msg) {
  return chrome.runtime.sendMessage(msg).catch((e) => ({ ok: false, error: e.message }));
}

function showView(name) {
  ['login', 'main'].forEach((v) => ($('view-' + v).hidden = v !== name));
}

function setError(el, msg) {
  const e = $(el);
  if (msg) { e.textContent = msg; e.hidden = false; }
  else e.hidden = true;
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

// ---------- Inicialización ----------
async function init() {
  currentTab = await getActiveTab();
  if (currentTab && currentTab.url && /^https?:/.test(currentTab.url)) {
    currentHostname = new URL(currentTab.url).hostname;
  }
  const status = await send({ type: 'getStatus' });
  if (status.ok && status.loggedIn) {
    $('userEmail').textContent = status.email;
    showView('main');
    await loadMain();
    return;
  }
  // Sin sesión detectada: redirige automáticamente a la página de inicio de sesión.
  if (status.serverUrl) {
    chrome.tabs.create({ url: status.serverUrl + '/auth/login/' });
    window.close();
    return;
  }
  if (status.serverError) {
    showView('login');
    setError('loginError', status.serverError);
    return;
  }
  showView('login');
}

async function loadMain() {
  await loadPending();
  const res = await send({ type: 'getEntries', hostname: currentHostname });
  if (res.ok) {
    matchedEntries = res.matched || [];
    allEntries = res.all || [];
  } else {
    setError('mainError', res.error || 'Error al consultar la bóveda.');
  }
  $('siteLabel').textContent = currentHostname ? 'Accesos para ' + currentHostname : 'No estás en un sitio web.';
  renderList();
}

async function loadPending() {
  if (!currentTab) return;
  const res = await send({ type: 'getPendingSave', tabId: currentTab.id });
  if (res.ok && res.pending) {
    $('pendingCard').hidden = false;
    $('pendingName').value = res.pending.name || res.pending.hostname || '';
    $('pendingUsername').value = res.pending.username || '';
    $('pendingPassword').value = res.pending.password || '';
  } else {
    $('pendingCard').hidden = true;
  }
}

function renderList() {
  const q = $('searchInput').value.trim().toLowerCase();
  const showingAll = activeTab === 'all' || !currentHostname;
  const base = showingAll ? allEntries : matchedEntries;
  const list = q ? base.filter((e) => (e.name || '').toLowerCase().includes(q) || (e.url || '').includes(q)) : base;
  const box = $('entriesList');
  box.innerHTML = '';
  if (!list.length) {
    $('noEntries').textContent = showingAll ? 'Tu bóveda está vacía.' : 'No hay accesos para este sitio.';
    $('noEntries').hidden = false;
    return;
  }
  $('noEntries').hidden = true;
  for (const entry of list) {
    const row = document.createElement('div');
    row.className = 'entry';

    const info = document.createElement('div');
    info.className = 'info';
    const name = document.createElement('div');
    name.className = 'e-name';
    name.textContent = entry.name || entry.url || 'Sin nombre';
    info.appendChild(name);
    const meta = document.createElement('div');
    meta.className = 'e-user';
    meta.textContent = entry.url || '';
    if (entry.shared_by_email) {
      const badge = document.createElement('span');
      badge.className = 'e-shared';
      badge.textContent = 'Compartido · ' + entry.shared_by_email;
      meta.appendChild(badge);
    }
    if (entry.has_totp) {
      const badge = document.createElement('span');
      badge.className = 'e-shared';
      badge.textContent = '2FA';
      meta.appendChild(badge);
    }
    info.appendChild(meta);
    row.appendChild(info);

    const acts = document.createElement('div');
    acts.className = 'acts';

    const totpBtn = document.createElement('button');
    totpBtn.className = 'icon-btn';
    totpBtn.title = entry.has_totp ? 'Ver código 2FA' : 'Configurar 2FA';
    totpBtn.innerHTML = entry.has_totp
      ? '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="#1a237e" d="M12 1 3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/></svg>'
      : '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M12 1 3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>';
    totpBtn.addEventListener('click', () => openTotpPanel(entry.id, entry.name || entry.url || 'Acceso'));
    acts.appendChild(totpBtn);

    const fillBtn = document.createElement('button');
    fillBtn.className = 'icon-btn';
    fillBtn.title = 'Autocompletar';
    fillBtn.innerHTML = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.9 9.5h-2.1A6 6 0 1 1 12 6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>';
    fillBtn.addEventListener('click', async () => {
      setError('mainError', null);
      if (!currentTab) return;
      const res = await send({ type: 'fillEntry', tabId: currentTab.id, entryId: entry.id });
      if (res.ok) window.close();
      else setError('mainError', res.error || 'No se pudo autocompletar.');
    });
    acts.appendChild(fillBtn);

    const copyUserBtn = document.createElement('button');
    copyUserBtn.className = 'icon-btn';
    copyUserBtn.title = 'Copiar usuario';
    copyUserBtn.innerHTML = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm0 2c-3.31 0-8 1.67-8 5v1h16v-1c0-3.33-4.69-5-8-5z"/></svg>';
    copyUserBtn.addEventListener('click', async () => {
      const res = await send({ type: 'getEntry', id: entry.id });
      if (res.ok && res.entry.username) await navigator.clipboard.writeText(res.entry.username);
      else setError('mainError', 'No hay usuario que copiar.');
    });
    acts.appendChild(copyUserBtn);

    const copyPwdBtn = document.createElement('button');
    copyPwdBtn.className = 'icon-btn';
    copyPwdBtn.title = 'Copiar contraseña';
    copyPwdBtn.innerHTML = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M18 8h-1V6a5 5 0 0 0-10 0v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2zm-6 9a2 2 0 1 1 0-4 2 2 0 0 1 0 4zm3-9H9V6a3 3 0 0 1 6 0z"/></svg>';
    copyPwdBtn.addEventListener('click', async () => {
      const res = await send({ type: 'getEntry', id: entry.id });
      if (res.ok && res.entry.password) await navigator.clipboard.writeText(res.entry.password);
      else setError('mainError', 'No hay contraseña que copiar.');
    });
    acts.appendChild(copyPwdBtn);

    row.appendChild(acts);
    box.appendChild(row);
  }
}

// ---------- Sesión ----------
$('loginBtn').addEventListener('click', async () => {
  setError('loginError', null);
  const status = await send({ type: 'getStatus' });
  if (status.serverError) { setError('loginError', status.serverError); return; }
  chrome.tabs.create({ url: status.serverUrl + '/auth/login/' });
});

$('logoutBtn').addEventListener('click', async () => {
  await send({ type: 'logout' });
  showView('login');
});

$('homeBtn').addEventListener('click', async () => {
  const res = await send({ type: 'getServerUrl' });
  if (!res.ok || !res.serverUrl) {
    setError('mainError', 'No hay un servidor configurado.');
    return;
  }
  await send({ type: 'openUrl', url: res.serverUrl + '/vault/' });
});

// ---------- Guardar ----------
$('pendingSaveBtn').addEventListener('click', async () => {
  await saveNew({
    name: $('pendingName').value.trim() || 'Acceso',
    url: currentTab ? currentTab.url : '',
    username: $('pendingUsername').value,
    password: $('pendingPassword').value,
  });
  if (currentTab) await send({ type: 'clearPendingSave', tabId: currentTab.id });
  $('pendingCard').hidden = true;
});

$('pendingDiscardBtn').addEventListener('click', async () => {
  if (currentTab) await send({ type: 'clearPendingSave', tabId: currentTab.id });
  $('pendingCard').hidden = true;
});

$('newToggleBtn').addEventListener('click', () => {
  const f = $('newForm');
  f.hidden = !f.hidden;
  if (!f.hidden) {
    $('newName').value = currentHostname ? currentHostname.replace(/^www\./, '').split('.')[0] : '';
    $('newUrl').value = currentTab ? currentTab.url : '';
  }
});

$('generateBtn').addEventListener('click', async () => {
  const res = await send({ type: 'generatePassword', opts: { length: 20 } });
  if (res.ok) $('newPassword').value = res.password;
});

$('newForm').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  await saveNew({
    name: $('newName').value || 'Acceso',
    url: $('newUrl').value,
    username: $('newUsername').value,
    password: $('newPassword').value,
  });
  $('newForm').hidden = true;
  $('newToggleBtn').textContent = '+ Añadir acceso';
  await loadMain();
});

async function saveNew(entry) {
  setError('mainError', null);
  if (!entry.password) { setError('mainError', 'La contraseña no puede estar vacía.'); return; }
  const res = await send({ type: 'saveEntry', entry, hostname: currentHostname });
  if (res.ok) {
    $('pendingPassword').value = '';
    await loadMain();
  } else {
    setError('mainError', res.error || 'No se pudo guardar.');
  }
}

// ---------- Generador de contraseñas ----------
function genOpts() {
  return {
    length: parseInt($('genLength').value, 10) || 24,
    upper: $('genUpper').checked,
    lower: $('genLower').checked,
    digits: $('genDigits').checked,
    symbols: $('genSymbols').checked,
    exclude_similar: $('genExcludeSimilar').checked,
    passphrase: $('genPassphrase').checked,
    num_words: parseInt($('genWords').value, 10) || 4,
  };
}

async function refreshGenerator() {
  const res = await send({ type: 'generatePassword', opts: genOpts() });
  if (res.ok) {
    $('genOutput').value = res.password;
    $('genEntropy').textContent = res.entropy != null ? 'Entropía: ' + res.entropy + ' bits' : '';
  } else {
    $('genEntropy').textContent = res.error || 'No se pudo generar.';
  }
}

function toggleGenPanel(open) {
  const p = $('genPanel');
  p.hidden = !open;
  if (open) refreshGenerator();
}

$('genBtn').addEventListener('click', () => toggleGenPanel($('genPanel').hidden));
$('genCloseBtn').addEventListener('click', () => toggleGenPanel(false));

function setGenDisabled(passphrase) {
  ['genUpper', 'genLower', 'genDigits', 'genSymbols', 'genExcludeSimilar'].forEach((id) => ($(id).disabled = passphrase));
  $('genLength').disabled = passphrase;
  $('genWords').disabled = !passphrase;
}

$('genPassphrase').addEventListener('change', () => {
  setGenDisabled($('genPassphrase').checked);
  refreshGenerator();
});

['genLength', 'genWords'].forEach((id) => {
  $(id).addEventListener('input', () => {
    $(id === 'genLength' ? 'genLengthVal' : 'genWordsVal').textContent = $(id).value;
    refreshGenerator();
  });
});

['genUpper', 'genLower', 'genDigits', 'genSymbols', 'genExcludeSimilar'].forEach((id) => {
  $(id).addEventListener('change', refreshGenerator);
});

$('genRegenBtn').addEventListener('click', refreshGenerator);

$('genCopyBtn').addEventListener('click', async () => {
  const val = $('genOutput').value;
  if (val) await navigator.clipboard.writeText(val);
});

$('genUseBtn').addEventListener('click', () => {
  $('newPassword').value = $('genOutput').value;
  $('newForm').hidden = false;
  $('newToggleBtn').textContent = 'Ocultar formulario';
  toggleGenPanel(false);
});

// ---------- Panel 2FA ----------
let totpEntryId = null;
let totpTimer = null;

function closeTotpPanel() {
  $('totpPanel').hidden = true;
  if (totpTimer) { clearInterval(totpTimer); totpTimer = null; }
  totpEntryId = null;
}

async function refreshTotpPanel() {
  if (!totpEntryId) return;
  const res = await send({ type: 'getEntry', id: totpEntryId });
  if (res.ok && res.entry) {
    const has = !!res.entry.has_totp;
    $('totpCode').textContent = has ? res.entry.totp || '—' : 'Sin 2FA configurado';
    $('totpStatus').textContent = has
      ? 'Código actual de 6 dígitos.'
      : 'Introduce la clave secreta y el código de verificación de tu app.';
    $('totpRemoveBtn').hidden = !has;
  }
}

async function openTotpPanel(entryId, name) {
  totpEntryId = entryId;
  $('totpEntryName').textContent = name;
  $('totpSecret').value = '';
  $('totpVerifyCode').value = '';
  $('totpPanel').hidden = false;
  const pending = await send({ type: 'getPendingQr' });
  if (pending.ok && pending.secret && pending.entryId === entryId) {
    $('totpSecret').value = pending.secret;
    $('totpStatus').textContent = 'QR leído. Introduce el código de 6 dígitos de tu app para confirmar.';
  }
  await refreshTotpPanel();
  if (totpTimer) clearInterval(totpTimer);
  totpTimer = setInterval(refreshTotpPanel, 30000);
}

$('totpCloseBtn').addEventListener('click', closeTotpPanel);
$('totpRefreshBtn').addEventListener('click', refreshTotpPanel);

$('totpCopyBtn').addEventListener('click', async () => {
  const code = $('totpCode').textContent;
  if (code && /^\d{6}$/.test(code)) await navigator.clipboard.writeText(code);
});

$('totpSaveBtn').addEventListener('click', async () => {
  if (!totpEntryId) return;
  setError('mainError', null);
  const secret = $('totpSecret').value.trim();
  const code = $('totpVerifyCode').value.trim();
  if (!secret || !code) {
    setError('mainError', 'Introduce la clave secreta y el código de verificación.');
    return;
  }
  const res = await send({ type: 'setTotp', id: totpEntryId, secret, code });
  if (res.ok) {
    $('totpSecret').value = '';
    $('totpVerifyCode').value = '';
    await send({ type: 'clearPendingQr' });
    await refreshTotpPanel();
    renderList();
  } else {
    setError('mainError', res.error || 'El código no coincide. El 2FA no fue configurado.');
  }
});

$('totpRemoveBtn').addEventListener('click', async () => {
  if (!totpEntryId) return;
  setError('mainError', null);
  const res = await send({ type: 'removeTotp', id: totpEntryId });
  if (res.ok) {
    await refreshTotpPanel();
    renderList();
  } else {
    setError('mainError', res.error || 'No se pudo quitar el 2FA.');
  }
});

$('totpQrBtn').addEventListener('click', async () => {
  if (!totpEntryId) return;
  setError('mainError', null);
  const res = await send({ type: 'selectQrForTotp', entryId: totpEntryId });
  if (res.ok) window.close();
  else setError('mainError', res.error || 'No se pudo iniciar la selección del QR.');
});

// ---------- Pestañas, búsqueda y opciones ----------
function switchTab(name) {
  activeTab = name;
  document.querySelectorAll('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
  renderList();
}

$('tabs').addEventListener('click', (ev) => {
  const btn = ev.target.closest('.tab');
  if (btn) switchTab(btn.dataset.tab);
});

$('searchInput').addEventListener('input', renderList);

function openOptions() {
  chrome.runtime.openOptionsPage();
}

$('openOptionsBtn').addEventListener('click', openOptions);
$('openOptions2Btn').addEventListener('click', openOptions);

init();
