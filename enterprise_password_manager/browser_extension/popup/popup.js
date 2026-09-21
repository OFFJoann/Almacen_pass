// TICO BOX - popup
const $ = (id) => document.getElementById(id);

let currentTab = null;
let currentHostname = '';
let activeTab = 'all';
let matchedEntries = [];
let allEntries = [];
let listRings = [];
let listRingsTimer = null;
let theme = 'light';

async function loadTheme() {
  try {
    const s = await chrome.storage.local.get('theme');
    theme = s.theme || 'light';
  } catch (e) { theme = 'light'; }
  applyTheme();
}

function applyTheme() {
  document.documentElement.dataset.theme = theme;
}

async function toggleTheme() {
  theme = theme === 'light' ? 'dark' : 'light';
  applyTheme();
  try { await chrome.storage.local.set({ theme }); } catch (e) { /* ignore */ }
}

function send(msg) {
  return chrome.runtime.sendMessage(msg).catch((e) => ({ ok: false, error: e.message }));
}

async function copyToClipboard(text) {
  if (!text) return false;
  const legacy = () => {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      ta.setSelectionRange(0, text.length);
      const ok = document.execCommand('copy');
      ta.remove();
      return ok;
    } catch (e) {
      return false;
    }
  };
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) { /* fallback */ }
  return legacy();
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
  await loadTheme();
  document.querySelectorAll('.theme-btn').forEach((b) => b.addEventListener('click', toggleTheme));
  currentTab = await getActiveTab();
  if (currentTab && currentTab.url && /^https?:/.test(currentTab.url)) {
    currentHostname = new URL(currentTab.url).hostname;
  }
  const status = await send({ type: 'getStatus' });
  if (status.ok && status.loggedIn) {
    $('userEmail').textContent = status.email;
    showView('main');
    await loadMain();
    const qrErr = await send({ type: 'getQrError' });
    if (qrErr.ok && qrErr.error) {
      showQrError(qrErr.error);
      await send({ type: 'clearQrError' });
    }
    await autoConfigurePendingQr();
    if (!listRingsTimer) listRingsTimer = setInterval(tickListRings, 1000);
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
  const showingAll = activeTab === 'all';
  const base = showingAll ? allEntries : matchedEntries;
  const list = q ? base.filter((e) => (e.name || '').toLowerCase().includes(q) || (e.url || '').includes(q)) : base;
  const box = $('entriesList');
  box.innerHTML = '';
  listRings = [];
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

    const isShared = !!entry.shared_by_email;

    if (entry.has_totp) {
      const ringBtn = document.createElement('button');
      ringBtn.className = 'row-totp';
      ringBtn.title = 'Ver código 2FA';
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', '18');
      svg.setAttribute('height', '18');
      svg.setAttribute('viewBox', '0 0 18 18');
      const bg = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      bg.setAttribute('class', 'rt-bg');
      bg.setAttribute('cx', '9');
      bg.setAttribute('cy', '9');
      bg.setAttribute('r', '7');
      const fg = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      fg.setAttribute('class', 'rt-fg');
      fg.setAttribute('cx', '9');
      fg.setAttribute('cy', '9');
      fg.setAttribute('r', '7');
      svg.appendChild(bg);
      svg.appendChild(fg);
      const ringWrap = document.createElement('span');
      ringWrap.className = 'rt-ring';
      ringWrap.appendChild(svg);
      const code = document.createElement('span');
      code.className = 'rt-code';
      code.textContent = entry.totp || '';
      ringBtn.appendChild(ringWrap);
      ringBtn.appendChild(code);
      acts.appendChild(ringBtn);
      listRings.push({ id: entry.id, fg, deadline: (Math.floor(Date.now() / 1000 / 30) + 1) * 30 });

      const actions = document.createElement('div');
      actions.className = 'entry-totp-actions';
      actions.hidden = true;

      const copyBtn = document.createElement('button');
      copyBtn.className = 'btn ghost small';
      copyBtn.textContent = 'Copiar 2FA';
      copyBtn.addEventListener('click', async (ev) => {
        ev.stopPropagation();
        const res = await send({ type: 'getEntry', id: entry.id });
        const text = (res.ok && res.entry && res.entry.totp) || code.textContent || '';
        if (text && /^\d{6}$/.test(text)) {
          const copied = await copyToClipboard(text);
          copyBtn.textContent = copied ? '¡Copiado!' : 'No se pudo copiar';
          setTimeout(() => { copyBtn.textContent = 'Copiar 2FA'; }, 1500);
        } else {
          copyBtn.textContent = 'Sin código';
          setTimeout(() => { copyBtn.textContent = 'Copiar 2FA'; }, 1500);
        }
      });
      actions.appendChild(copyBtn);

      if (!isShared) {
        const reconfBtn = document.createElement('button');
        reconfBtn.className = 'btn ghost small';
        reconfBtn.textContent = 'Re-configurar';
        reconfBtn.addEventListener('click', async (ev) => {
          ev.stopPropagation();
          setError('mainError', null);
          const res = await send({ type: 'selectQrForTotp', entryId: entry.id });
          if (res.ok) window.close();
          else setError('mainError', res.error || 'No se pudo iniciar la selección del QR.');
        });
        actions.appendChild(reconfBtn);
      }

      ringBtn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        actions.hidden = !actions.hidden;
      });
      row.appendChild(actions);
    } else if (!isShared) {
      const totpBtn = document.createElement('button');
      totpBtn.className = 'icon-btn';
      totpBtn.title = 'Configurar 2FA';
      totpBtn.innerHTML = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M12 1 3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>';
      totpBtn.addEventListener('click', async () => {
        setError('mainError', null);
        const res = await send({ type: 'selectQrForTotp', entryId: entry.id });
        if (res.ok) window.close();
        else setError('mainError', res.error || 'No se pudo iniciar la selección del QR.');
      });
      acts.appendChild(totpBtn);
    }

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
      if (res.ok && res.entry.username) await copyToClipboard(res.entry.username);
      else setError('mainError', 'No hay usuario que copiar.');
    });
    acts.appendChild(copyUserBtn);

    const copyPwdBtn = document.createElement('button');
    copyPwdBtn.className = 'icon-btn';
    copyPwdBtn.title = 'Copiar contraseña';
    copyPwdBtn.innerHTML = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M18 8h-1V6a5 5 0 0 0-10 0v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2zm-6 9a2 2 0 1 1 0-4 2 2 0 0 1 0 4zm3-9H9V6a3 3 0 0 1 6 0z"/></svg>';
    copyPwdBtn.addEventListener('click', async () => {
      const res = await send({ type: 'getEntry', id: entry.id });
      if (res.ok && res.entry.password) await copyToClipboard(res.entry.password);
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
  const res = await send({ type: 'getServerUrl' });
  if (res.ok && res.serverUrl) {
    chrome.tabs.create({ url: res.serverUrl + '/auth/login/' });
  }
  showView('login');
});

// Si la sesión web o el token se invalidan (logout en la web), el background
// avisa para refrescar el popup de inmediato en lugar de quedar con el correo viejo.
chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === 'sessionChanged' && msg.loggedIn === false) {
    showView('login');
  }
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

$('newCancelBtn').addEventListener('click', () => {
  $('newForm').hidden = true;
  $('newToggleBtn').textContent = '+ Añadir acceso';
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
  const url = (entry.url || '').trim();
  if (url && !/^https?:\/\//i.test(url)) {
    entry.url = 'https://' + url;
  }
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

function shareModalOpen(password) {
  $('sharePassword').value = password || '';
  $('shareDays').value = '7';
  $('shareMaxUses').value = '7';
  $('shareBody').hidden = false;
  $('shareResult').hidden = true;
  $('shareError').hidden = true;
  $('shareModal').hidden = false;
  $('sharePassword').focus();
}

function shareModalClose() {
  $('shareModal').hidden = true;
}

function shareResetToBody() {
  $('shareBody').hidden = false;
  $('shareResult').hidden = true;
  $('shareError').hidden = true;
  $('shareGenBtn').disabled = false;
  $('shareGenBtn').textContent = 'Generar enlace';
}

$('genShareBtn').addEventListener('click', () => {
  shareModalOpen($('genOutput').value);
});

$('shareCloseBtn').addEventListener('click', shareModalClose);
$('shareDoneBtn').addEventListener('click', shareModalClose);
$('shareAnotherBtn').addEventListener('click', () => {
  shareResetToBody();
  $('sharePassword').value = $('genOutput').value;
  $('sharePassword').focus();
});

$('shareGenBtn').addEventListener('click', async () => {
  const password = $('sharePassword').value;
  if (!password) { $('sharePassword').focus(); return; }
  const days = Math.min(7, Math.max(1, parseInt($('shareDays').value, 10) || 7));
  const maxUses = Math.min(7, Math.max(1, parseInt($('shareMaxUses').value, 10) || 7));
  const btn = $('shareGenBtn');
  btn.disabled = true;
  btn.textContent = 'Generando…';
  setError('shareError', null);
  const res = await send({ type: 'sharePassword', data: { password, days, maxUses } });
  btn.disabled = false;
  btn.textContent = 'Generar enlace';
  if (res.ok && res.url) {
    $('shareUrl').value = res.url;
    $('shareResultDays').textContent = res.days;
    $('shareResultUses').textContent = res.max_uses;
    $('shareResultExpires').textContent = res.expires_at;
    $('shareBody').hidden = true;
    $('shareResult').hidden = false;
  } else {
    setError('shareError', res.error || 'No se pudo generar el enlace.');
  }
});

$('shareCopyBtn').addEventListener('click', async () => {
  const ok = await copyToClipboard($('shareUrl').value);
  const btn = $('shareCopyBtn');
  btn.innerHTML = ok
    ? '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg>'
    : $('shareCopyBtn').innerHTML;
  setTimeout(() => {
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M16 1H4a2 2 0 0 0-2 2v14h2V3h12V1zm3 4H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H8V7h11v14z"/></svg>';
  }, 2000);
});

$('genCopyBtn').addEventListener('click', async () => {
  const val = $('genOutput').value;
  if (val) await copyToClipboard(val);
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
let totpShared = false;

function closeTotpPanel() {
  $('totpPanel').hidden = true;
  $('totpRing').hidden = true;
  if (totpTimer) { clearInterval(totpTimer); totpTimer = null; }
  totpEntryId = null;
  totpShared = false;
  $('totpSecret').parentElement.hidden = false;
  $('totpVerifyCode').parentElement.hidden = false;
  $('totpSaveBtn').hidden = false;
  $('totpQrBtn').hidden = false;
}

function showQrError(msg) {
  $('errorModalMsg').textContent = msg;
  $('errorModal').hidden = false;
}

async function refreshTotpPanel() {
  if (!totpEntryId) return;
  const res = await send({ type: 'getEntry', id: totpEntryId });
  if (res.ok && res.entry) {
    const has = !!res.entry.has_totp;
    $('totpCode').textContent = has ? res.entry.totp || '—' : 'Sin 2FA configurado';
    $('totpRing').hidden = !has;
    if (!totpShared) {
      $('totpStatus').textContent = has
        ? 'Código actual de 6 dígitos.'
        : 'Introduce la clave secreta y el código de verificación de tu app.';
    } else if (!has) {
      $('totpStatus').textContent = 'Registro compartido: el 2FA solo puede gestionarlo su propietario.';
    }
    $('totpRemoveBtn').hidden = !has || totpShared;
    if (has) {
      const step = 30;
      const nowS = Math.floor(Date.now() / 1000);
      if (!totpDeadline || totpDeadline <= nowS) totpDeadline = (Math.floor(nowS / step) + 1) * step;
      updateTotpRing();
    }
  }
}

// Anillo de cuenta regresiva de 30s (volumen completo -> vacío como un reloj).
// Al agotarse la ventana actual refresca el código desde el servidor.
let totpDeadline = 0;
function updateTotpRing() {
  const arc = $('totpRingArc');
  if (!arc) return;
  const nowS = Math.floor(Date.now() / 1000);
  const step = 30;
  const remaining = totpDeadline - nowS;
  const C = 75.4;
  arc.style.strokeDashoffset = String(C * remaining / step);
  if (remaining <= 0) {
    totpDeadline = (Math.floor(nowS / step) + 1) * step;
    refreshTotpPanel();
  }
}

// Anillos de código en la lista de entradas: se vacían como un reloj y al agotarse la
// ventana actual solo se actualizan los códigos desde el servidor (sin reabrir ningún panel).
async function tickListRings() {
  const step = 30;
  const nowS = Math.floor(Date.now() / 1000);
  let changed = false;
  for (const ring of listRings) {
    if (!ring.fg.isConnected) continue;
    const remaining = ring.deadline - nowS;
    const C = Math.round(2 * Math.PI * 7 * 100) / 100;
    ring.fg.style.strokeDasharray = String(C);
    ring.fg.style.strokeDashoffset = String(C * remaining / step);
    if (remaining <= 0) {
      ring.deadline = (Math.floor(nowS / step) + 1) * step;
      changed = true;
    }
  }
  if (changed) await loadEntriesSilently();
}

async function loadEntriesSilently() {
  const res = await send({ type: 'getEntries', hostname: currentHostname });
  if (!res.ok) return;
  const pool = (res.all && res.all.length ? res.all : []).concat(res.matched || []);
  for (const ring of listRings) {
    const entry = pool.find((e) => String(e.id) === String(ring.id));
    if (entry && ring.fg.isConnected) {
      const codeEl = ring.fg.closest('.row-totp').querySelector('.rt-code');
      if (codeEl) codeEl.textContent = entry.totp || '';
    }
  }
}

async function openTotpPanel(entryId, name, isShared) {
  totpEntryId = entryId;
  $('totpEntryName').textContent = name;
  $('totpSecret').value = '';
  $('totpVerifyCode').value = '';
  $('totpPanel').hidden = false;
  $('totpRing').hidden = true;
  totpShared = !!isShared;
  $('totpSecret').parentElement.hidden = totpShared;
  $('totpVerifyCode').parentElement.hidden = totpShared;
  $('totpSaveBtn').hidden = totpShared;
  $('totpQrBtn').hidden = totpShared;
  if (totpShared) {
    $('totpStatus').textContent = 'Registro compartido: el 2FA solo puede gestionarlo su propietario.';
    $('totpRemoveBtn').hidden = true;
  }
  const pending = await send({ type: 'getPendingQr' });
  if (pending.ok && pending.secret && pending.entryId === entryId) {
    $('totpSecret').value = pending.secret;
    $('totpStatus').textContent = 'QR leído. Verificando automáticamente…';
    const auto = await send({ type: 'autoSetupTotp', id: entryId });
    if (auto.ok) {
      $('totpStatus').textContent = '2FA configurado correctamente.';
      await refreshTotpPanel();
      renderList();
    } else {
      $('totpStatus').textContent = 'QR leído, pero el código no coincidió. Reintenta o escribe el secreto y el código manualmente.';
      showQrError(auto.error || 'El código 2FA no coincidió con el servidor.');
    }
  }
  await refreshTotpPanel();
  if (totpTimer) clearInterval(totpTimer);
  totpTimer = setInterval(updateTotpRing, 1000);
}

$('totpCloseBtn').addEventListener('click', closeTotpPanel);
$('totpRefreshBtn').addEventListener('click', refreshTotpPanel);

// Si al reabrir la extensión hay un QR escaneado sin configurar, lo configura en silencio
// (sin abrir el módulo 2FA) y refresca la lista para que aparezca la bolita en la fila.
async function autoConfigurePendingQr() {
  const pending = await send({ type: 'getPendingQr' });
  if (!pending.ok || !pending.secret || !pending.entryId) return;
  const res = await send({ type: 'autoSetupTotp', id: pending.entryId });
  if (res.ok) {
    await loadMain();
  } else {
    showQrError(res.error || 'El código 2FA no coincidió con el servidor.');
  }
}

$('totpCopyBtn').addEventListener('click', async () => {
  const code = $('totpCode').textContent;
  if (code && /^\d{6}$/.test(code)) await copyToClipboard(code);
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

$('errorModalOk').addEventListener('click', () => {
  $('errorModal').hidden = true;
  send({ type: 'clearQrError' });
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
