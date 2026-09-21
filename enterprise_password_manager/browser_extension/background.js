// TICO BOX - background (service worker MV3)
const DEFAULT_SERVER_URL = 'https://ticobox.sociabpo.com';
const LEGACY_DEFAULT_SERVER_URL = 'https://ticobox.sociabpo.com';

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(['serverUrl']).then((s) => {
    let url = s.serverUrl;
    if (!url || url === LEGACY_DEFAULT_SERVER_URL) {
      url = DEFAULT_SERVER_URL;
      chrome.storage.sync.set({ serverUrl: url });
    }
  });
  updateStateIconFromStorage();
});

chrome.runtime.onStartup.addListener(() => {
  updateStateIconFromStorage();
});

function getServerUrl() {
  return chrome.storage.sync.get(['serverUrl']).then((s) => s.serverUrl || DEFAULT_SERVER_URL);
}

// ---------- Icono de estado conectado/desconectado ----------
// El usuario coloca dos imágenes en icons/: icon_conectado.png y icon_desconectado.png
// (o variantes por tamaño: icon_<estado>_16.png / _48 / _128.png).
// Si no existen, se conserva el icono por defecto del manifest.
const STATE_ICON_PREFIX = {
  on: 'icons/icon_conectado',
  off: 'icons/icon_desconectado',
};
const DEFAULT_ACTION_ICON = {
  '16': 'icons/icon_conectado_16.png',
  '48': 'icons/icon_conectado_48.png',
  '128': 'icons/icon_conectado_128.png',
};

async function resourceExists(path) {
  try {
    const r = await fetch(chrome.runtime.getURL(path));
    return r.ok;
  } catch (e) {
    return false;
  }
}

async function applyStateIcon(loggedIn) {
  const prefix = STATE_ICON_PREFIX[loggedIn ? 'on' : 'off'];
  // Prioriza variantes por tamaño (16/48/128) que Chrome necesita para la toolbar
  const dict = {};
  for (const size of ['16', '48', '128']) {
    if (await resourceExists(prefix + '_' + size + '.png')) dict[size] = prefix + '_' + size + '.png';
  }
  let selected = null;
  if (Object.keys(dict).length) {
    selected = dict;
  } else if (await resourceExists(prefix + '.png')) {
    selected = prefix + '.png';
  }
  try {
    await chrome.action.setIcon({ path: selected || DEFAULT_ACTION_ICON });
  } catch (e) { /* ignore */ }
}

async function updateStateIconFromStorage() {
  const s = await chrome.storage.local.get(['token']);
  await applyStateIcon(!!s.token);
}

function apiBase() {
  return getServerUrl().then((u) => u.replace(/\/+$/, '') + '/api');
}

async function getToken() {
  const s = await chrome.storage.local.get(['token']);
  return s.token || null;
}

function extractFieldError(data) {
  if (!data || typeof data !== 'object') return '';
  for (const key of Object.keys(data)) {
    const v = data[key];
    if (Array.isArray(v) && v.length) return key + ': ' + v[0];
    if (typeof v === 'object' && v !== null) {
      const nested = extractFieldError(v);
      if (nested) return nested;
    }
  }
  return '';
}

async function request(path, { method = 'GET', body = null, auth = true, headers = {} } = {}) {
  const base = await apiBase();
  const allHeaders = { ...headers };
  if (body !== null) allHeaders['Content-Type'] = 'application/json';
  const token = auth ? await getToken() : null;
  if (token) allHeaders['Authorization'] = 'Token ' + token;
  let res;
  try {
    res = await fetch(base + path, {
      method,
      headers: allHeaders,
      body: body !== null ? JSON.stringify(body) : undefined,
      credentials: 'omit',
    });
  } catch (e) {
    const err = new Error('No se pudo conectar con el servidor. Revisa la configuración.');
    err.network = true;
    throw err;
  }
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) {
    if (res.status === 401 && auth) {
      await chrome.storage.local.remove(['token', 'email', 'full_name', 'sessionId']);
    }
    const err = new Error(data.error || data.detail || extractFieldError(data) || 'Error ' + res.status + ' del servidor');
    err.status = res.status;
    throw err;
  }
  return data;
}

async function fetchAllEntries() {
  const entries = [];
  let relPath = '/passwords/entries/';
  while (relPath) {
    const data = await request(relPath);
    entries.push(...(data.results || []));
    if (data.next) {
      const u = new URL(data.next);
      relPath = u.pathname.replace(/^\/api/, '') + u.search;
    } else {
      relPath = null;
    }
  }
  return entries;
}

function hostOf(url) {
  try {
    return new URL(url).hostname;
  } catch (e) {
    return '';
  }
}

function originOf(url) {
  try {
    return new URL(url).origin;
  } catch (e) {
    return '';
  }
}

function matchesHost(entryUrl, hostname) {
  if (!entryUrl || !hostname) return false;
  const h = hostOf(entryUrl).toLowerCase();
  const base = hostname.replace(/^www\./, '').toLowerCase();
  return h === hostname.toLowerCase() || h === base || h.endsWith('.' + base);
}

// ---------- Acciones ----------
async function sessionLogin() {
  // Lee la cookie de sesión de la app web y la cambia por un token API.
  const serverUrl = await getServerUrl();
  const cookie = await chrome.cookies.get({ url: serverUrl, name: 'sessionid' });
  if (!cookie || !cookie.value) return { ok: false };
  const data = await request('/auth/token/session/', {
    method: 'POST',
    auth: false,
    headers: { 'X-Session-ID': cookie.value },
  });
  if (data.token) {
    await chrome.storage.local.set({
      token: data.token,
      email: data.email,
      full_name: data.full_name,
      sessionId: cookie.value,
    });
    await applyStateIcon(true);
    return { ok: true, email: data.email };
  }
  return { ok: false };
}

async function doLogout() {
  const s = await chrome.storage.local.get(['sessionId']);
  const headers = {};
  if (s.sessionId) headers['X-Session-ID'] = s.sessionId;
  try { await request('/auth/token/logout/', { method: 'POST', headers }); } catch (e) { /* ignore */ }
  await chrome.storage.local.remove(['token', 'email', 'full_name', 'sessionId']);
  await chrome.action.setBadgeText({ text: '' });
  await applyStateIcon(false);
  try { chrome.runtime.sendMessage({ type: 'sessionChanged', loggedIn: false }); } catch (e) { /* ignore */ }
  return { ok: true };
}

async function getStatus() {
  const s = await chrome.storage.local.get(['token', 'email', 'full_name']);
  const serverUrl = await getServerUrl();
  let result;
  if (!s.token) {
    try {
      const login = await sessionLogin();
      if (login.ok) result = { ok: true, loggedIn: true, email: login.email, serverUrl };
      else result = { ok: true, loggedIn: false, serverUrl };
    } catch (e) {
      result = { ok: true, loggedIn: false, serverError: e.message, serverUrl };
    }
  } else {
    // Valida que el token siga vigente en el servidor (el logout web lo revoca).
    try {
      await request('/auth/me/', { auth: true });
      result = { ok: true, loggedIn: true, email: s.email, fullName: s.full_name, serverUrl };
    } catch (e) {
      if (e.status === 401) {
        result = { ok: true, loggedIn: false, serverUrl };
      } else {
        result = { ok: true, loggedIn: true, email: s.email, fullName: s.full_name, serverUrl, serverError: e.message };
      }
    }
  }
  await applyStateIcon(!!result.loggedIn);
  return result;
}

// Comprueba periódicamente si la sesión web/token sigue vigente para
// cerrar sesión en la extensión cuando se cierra en la aplicación web.
async function checkSession() {
  const s = await chrome.storage.local.get(['token']);
  if (!s.token) {
    await applyStateIcon(false);
    return;
  }
  try {
    await request('/auth/me/', { auth: true });
    await applyStateIcon(true);
  } catch (e) {
    if (e.status === 401) {
      await doLogout();
      const tabs = await chrome.tabs.query({ url: '*://*/*' });
      for (const tab of tabs) {
        try { await chrome.tabs.sendMessage(tab.id, { type: 'sessionChanged', loggedIn: false }); } catch (e2) { /* ignore */ }
      }
    }
  }
}

chrome.alarms.create('sessionCheck', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'sessionCheck') checkSession();
});

async function getEntries(hostname) {
  const all = await fetchAllEntries();
  const matched = all.filter((e) => matchesHost(e.url, hostname) || !e.url);
  return { ok: true, matched, all };
}

async function getEntry(id) {
  const data = await request('/passwords/entries/' + id + '/');
  return { ok: true, entry: data };
}

async function saveEntry(entry, hostname, options) {
  const opts = options || {};
  const body = {
    name: entry.name,
    url: entry.url,
    username: entry.username,
    password: entry.password,
    notes: entry.notes || '',
  };
  // El guardado automático (detección en páginas) fusiona con la misma URL; el
  // "Añadir acceso" manual siempre crea un registro nuevo.
  if (opts.mergeByUrl) {
    const all = await fetchAllEntries();
    const sameUrl = all.find((e) => e.url && e.url.split('?')[0] === (entry.url || '').split('?')[0]);
    if (sameUrl) {
      const data = await request('/passwords/entries/' + sameUrl.id + '/', { method: 'PATCH', body });
      return { ok: true, updated: true, entry: data };
    }
  }
  const data = await request('/passwords/entries/', { method: 'POST', body });
  return { ok: true, updated: false, entry: data };
}

async function setTotp(id, secret, code) {
  const data = await request('/passwords/entries/' + id + '/verify_totp/', {
    method: 'POST',
    body: { secret: (secret || '').trim(), code: (code || '').trim() },
  });
  return { ok: true, entry: data };
}

async function removeTotp(id) {
  const data = await request('/passwords/entries/' + id + '/remove_totp/', { method: 'POST' });
  return { ok: true, entry: data };
}

// ---------- Cálculo TOTP (WebCrypto HMAC-SHA1) ----------
async function base32Decode(secret) {
  const b32 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const ch of (secret || '').toUpperCase()) {
    const v = b32.indexOf(ch);
    if (v < 0) return null;
    bits += v.toString(2).padStart(5, '0');
  }
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) {
    bytes.push(parseInt(bits.slice(i, i + 8), 2));
  }
  if (!bytes.length) return null;
  return new Uint8Array(bytes);
}

async function totpCodeFor(secret, counter) {
  const key = await base32Decode(secret);
  if (!key || !(crypto && crypto.subtle)) return null;
  const msg = new ArrayBuffer(8);
  new DataView(msg).setUint32(0, Math.floor(counter / 4294967296));
  new DataView(msg).setUint32(4, counter >>> 0);
  const cryptoKey = await crypto.subtle.importKey('raw', key, { name: 'HMAC', hash: 'SHA-1' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', cryptoKey, msg);
  const hmac = new Uint8Array(sig);
  const offset = hmac[hmac.length - 1] & 0x0f;
  const bin = ((hmac[offset] & 0x7f) << 24) | ((hmac[offset + 1] & 0xff) << 16) | ((hmac[offset + 2] & 0xff) << 8) | (hmac[offset + 3] & 0xff);
  return String(bin % 1000000).padStart(6, '0');
}

async function generateCurrentTotp(secret) {
  const step = 30;
  const now = Math.floor(Date.now() / 1000);
  for (let i = -1; i <= 1; i++) {
    const code = await totpCodeFor(secret, Math.floor(now / step) + i);
    if (code !== null) {
      return { ok: true, code, valid: i === 0 };
    }
  }
  return { ok: false, error: 'No se pudo calcular el código 2FA del secreto.' };
}

// ---------- Selección de código QR para 2FA ----------
async function sessionSet(obj) {
  try { if (chrome.storage && chrome.storage.session) return await chrome.storage.session.set(obj); } catch (e) { /* ignore */ }
  return chrome.storage.local.set(obj);
}

async function sessionGet(keys) {
  try { if (chrome.storage && chrome.storage.session) return await chrome.storage.session.get(keys); } catch (e) { /* ignore */ }
  return chrome.storage.local.get(keys);
}

async function sessionRemove(keys) {
  try { if (chrome.storage && chrome.storage.session) return await chrome.storage.session.remove(keys); } catch (e) { /* ignore */ }
  return chrome.storage.local.remove(keys);
}

async function startQrSelection(entryId, tabId) {
  let tab;
  try { tab = await chrome.tabs.get(tabId); } catch (e) { tab = null; }
  if (!tab || !/^https?:/.test(tab.url || '')) {
    throw new Error('El código QR debe estar visible en una pestaña web.');
  }
  await sessionSet({ pendingQrEntryId: entryId });
  let injected = false;
  try {
    const res = await chrome.tabs.sendMessage(tabId, { type: 'qrPing' });
    injected = !!(res && res.ok);
  } catch (e) {
    injected = false;
  }
  if (!injected) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['lib/jsqr.min.js', 'content/qrselect.js'],
    });
    injected = true;
  }
  if (injected) await chrome.tabs.sendMessage(tabId, { type: 'qrStart' });
  return { ok: true };
}

async function applyQrSecret(secret) {
  const s = await sessionGet(['pendingQrEntryId']);
  const entryId = s.pendingQrEntryId;
  if (!entryId) throw new Error('No hay una entrada pendiente para configurar el 2FA.');
  await sessionRemove(['pendingQrEntryId']);
  await sessionSet({ pendingQrSecret: secret, pendingQrEntryId: entryId });
  return { ok: true, pending: true, secret };
}

// Configura el 2FA automáticamente con el secreto escaneado, calculando el código localmente.
async function autoSetupTotp(entryId) {
  const s = await sessionGet(['pendingQrSecret', 'pendingQrEntryId']);
  if (!s.pendingQrSecret || s.pendingQrEntryId !== entryId) {
    throw new Error('No hay un QR pendiente para esta entrada.');
  }
  const secret = s.pendingQrSecret;
  const gen = await generateCurrentTotp(secret);
  if (!gen.ok) throw new Error(gen.error);
  const data = await request('/passwords/entries/' + entryId + '/verify_totp/', {
    method: 'POST',
    body: { secret, code: gen.code },
  });
  await clearPendingQr();
  return { ok: true, entry: data, code: gen.code };
}

async function getPendingQr() {
  const s = await sessionGet(['pendingQrSecret', 'pendingQrEntryId']);
  if (s.pendingQrSecret && s.pendingQrEntryId) {
    return { ok: true, secret: s.pendingQrSecret, entryId: s.pendingQrEntryId };
  }
  return { ok: true, secret: null };
}

async function clearPendingQr() {
  await sessionRemove(['pendingQrSecret', 'pendingQrEntryId']);
  return { ok: true };
}

async function setQrError(reason) {
  await sessionSet({ pendingQrError: reason || 'El código QR no es válido.' });
  return { ok: true };
}

async function getQrError() {
  const s = await sessionGet(['pendingQrError']);
  if (s.pendingQrError) return { ok: true, error: s.pendingQrError };
  return { ok: true, error: null };
}

async function clearQrError() {
  await sessionRemove(['pendingQrError']);
  return { ok: true };
}

// ---------- Guardado detectado ----------
// Detecta si ya hay un acceso guardado con el mismo sitio/host, el mismo
// usuario y la misma contraseña. Primero intenta el endpoint del servidor; si
// no está disponible (servidor sin actualizar), compara en el cliente
// consultando cada candidato del mismo hostname.
async function isDuplicateCredentials(data) {
  const wantHost = hostOf(data.url).replace(/^www\./, '').toLowerCase();
  const username = (data.username || '').trim().toLowerCase();
  const password = data.password || '';
  if (!wantHost || !password) return false;

  try {
    const res = await request('/passwords/entries/check_duplicate/', {
      method: 'POST',
      body: { url: data.url, username: data.username, password: data.password },
    });
    if (res && typeof res.duplicate === 'boolean') return res.duplicate;
  } catch (e) { /* endpoint no disponible: seguir con la comprobación local */ }

  try {
    const all = await fetchAllEntries();
    for (const e of all) {
      const host = hostOf(e.url).replace(/^www\./, '').toLowerCase();
      if (!host || host !== wantHost) continue;
      let detail;
      try { detail = await getEntry(e.id); } catch (err) { continue; }
      const entry = detail && detail.entry;
      if (!entry) continue;
      if (username && (entry.username || '').trim().toLowerCase() !== username) continue;
      if ((entry.password || '') === password) return true;
    }
  } catch (e) { /* si falla, se sigue preguntando */ }
  return false;
}

async function saveDetected(tabId, data) {
  if (!tabId) return { ok: true };

  // Solo preguntar si la extensión tiene una sesión activa iniciada.
  // Si no hay sesión (ni token ni sesión web de la que autenticarse),
  // no se pregunta nada al usuario.
  const status = await getStatus();
  if (!status || !status.loggedIn) {
    return { ok: true };
  }

  // No pedir guardar en la propia bóveda (misma URL/origen que el servidor).
  const serverUrl = await getServerUrl();
  let tabUrl = '';
  try {
    const tab = await chrome.tabs.get(tabId);
    tabUrl = tab.url || '';
  } catch (e) { /* ignore */ }
  const serverOrigin = originOf(serverUrl);
  const tabOrigin = originOf(tabUrl);
  if (serverOrigin && tabOrigin && serverOrigin === tabOrigin) {
    return { ok: true };
  }

  // Si ya existe un acceso con la misma URL/sitio, el mismo usuario y la misma
  // contraseña, no preguntar.
  if ((data.url || '').trim() && (data.password || '')) {
    if (await isDuplicateCredentials(data)) return { ok: true, skipped: true };
  }

  await chrome.storage.local.set({ pendingSave: { tabId, ...data } });
  await chrome.action.setBadgeText({ tabId, text: 'G' });
  await showSaveNotification(tabId, data);
  return { ok: true };
}

const SAVE_NOTIF_PREFIX = 'ticolvide-save-';

async function showSaveNotification(tabId, data) {
  try {
    const notifId = SAVE_NOTIF_PREFIX + tabId;
    await chrome.notifications.create(notifId, {
      type: 'basic',
      iconUrl: 'icons/icon_conectado_128.png',
      title: 'TICO BOX',
      message: '¿Guardar la contraseña de ' + (data.name || data.hostname || 'este sitio') + '?',
      buttons: [
        { title: 'Guardar' },
        { title: 'Descartar' },
      ],
      priority: 1,
      requireInteraction: true,
    });
  } catch (e) {
    console.error('No se pudo mostrar la notificación:', e);
  }
}

chrome.notifications.onButtonClicked.addListener(async (notifId, buttonIndex) => {
  if (!notifId || !notifId.startsWith(SAVE_NOTIF_PREFIX)) return;
  const tabId = Number(notifId.replace(SAVE_NOTIF_PREFIX, ''));
  const s = await chrome.storage.local.get(['pendingSave']);
  const p = s.pendingSave;
  if (p && p.tabId === tabId) {
    if (buttonIndex === 0) {
      // Abre el popup para que el usuario confirme/edite el nombre antes de guardar.
      try {
        await chrome.action.openPopup();
      } catch (e) {
        // Si no se puede abrir el popup, guarda directamente.
        try {
          await saveEntry({
            name: p.name,
            url: p.url,
            username: p.username,
            password: p.password,
            notes: p.notes || '',
          }, p.hostname, { mergeByUrl: true });
          await clearPendingSave(tabId);
        } catch (e2) { /* el error se verá al abrir la extensión */ }
      }
    } else {
      await clearPendingSave(tabId);
    }
  }
  try { await chrome.notifications.clear(notifId); } catch (e) { /* ignore */ }
});

async function getPendingSave(tabId) {
  const s = await chrome.storage.local.get(['pendingSave']);
  const p = s.pendingSave;
  if (p && p.tabId === tabId) return { ok: true, pending: p };
  return { ok: true, pending: null };
}

async function clearPendingSave(tabId) {
  const s = await chrome.storage.local.get(['pendingSave']);
  if (s.pendingSave && s.pendingSave.tabId === tabId) {
    await chrome.storage.local.remove(['pendingSave']);
    await chrome.action.setBadgeText({ tabId, text: '' });
  }
  try { await chrome.notifications.clear(SAVE_NOTIF_PREFIX + tabId); } catch (e) { /* ignore */ }
  return { ok: true };
}

// ---------- Relleno ----------
async function injectContent(tabId) {
  try {
    await chrome.tabs.sendMessage(tabId, { type: 'ping' });
    return true;
  } catch (e) {
    try {
      await chrome.scripting.executeScript({ target: { tabId }, files: ['content/content.js'] });
      return true;
    } catch (e2) {
      return false;
    }
  }
}

async function fillEntry(tabId, entryId) {
  const detail = await getEntry(entryId);
  const entry = detail.entry;
  const target = entry.url && /^https?:/i.test(entry.url) ? entry.url : '';
  if (target) {
    try {
      const tab = await chrome.tabs.get(tabId);
      const currentUrl = (tab.url || '').split('#')[0];
      if (currentUrl !== target.split('#')[0]) {
        await chrome.tabs.update(tabId, { url: target });
        await waitForTabLoad(tabId);
      }
    } catch (e) { /* ignore navigation errors */ }
  }
  const ok = await injectContent(tabId);
  if (!ok) throw new Error('No se pudo inyectar en la página.');
  await chrome.tabs.sendMessage(tabId, {
    type: 'fill',
    username: entry.username || '',
    password: entry.password || '',
    totp: entry.totp || '',
  });
  return { ok: true };
}

function waitForTabLoad(tabId) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }, 20000);
    function listener(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        clearTimeout(timer);
        resolve();
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

// ---------- Generador ----------
const GENERATOR_WORDS = [
  'alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf',
  'hotel', 'india', 'juliett', 'kilo', 'lima', 'mike', 'november',
  'oscar', 'papa', 'quebec', 'romeo', 'sierra', 'tango', 'uniform',
  'victor', 'whiskey', 'xray', 'yankee', 'zulu',
  'cloud', 'storm', 'river', 'mountain', 'forest', 'ocean', 'desert',
  'eagle', 'hawk', 'wolf', 'bear', 'falcon', 'phoenix', 'dragon',
  'ruby', 'sapphire', 'emerald', 'diamond', 'amber', 'jade', 'opal',
  'crimson', 'azure', 'golden', 'silver', 'bronze', 'ivory', 'violet',
];

function localGenerate(opts = {}) {
  if (opts.passphrase) {
    const n = Math.min(10, Math.max(2, opts.num_words || 4));
    const rnd = new Uint32Array(n);
    crypto.getRandomValues(rnd);
    const out = [];
    for (let i = 0; i < n; i++) out.push(GENERATOR_WORDS[rnd[i] % GENERATOR_WORDS.length]);
    return out.join('-');
  }
  const length = Math.min(128, Math.max(1, opts.length || 24));
  let sets = [];
  if (opts.upper !== false) sets.push('ABCDEFGHIJKLMNOPQRSTUVWXYZ');
  if (opts.lower !== false) sets.push('abcdefghijklmnopqrstuvwxyz');
  if (opts.digits !== false) sets.push('0123456789');
  if (opts.symbols !== false) sets.push('!@#$%^&*()-_=+[]{};:,.?');
  if (opts.exclude_similar) sets = sets.map((s) => [...s].filter((c) => !'il1Lo0O'.includes(c)).join(''));
  if (opts.exclude_ambiguous) sets = sets.map((s) => [...s].filter((c) => !'{}[]()/\\\'"`~,;:.<>'.includes(c)).join(''));
  let all = sets.join('');
  if (!all) all = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  const rnd = new Uint32Array(length);
  crypto.getRandomValues(rnd);
  const out = [];
  for (let i = 0; i < length; i++) {
    const pool = sets[i] && sets[i].length ? sets[i] : all;
    out.push(pool[rnd[i] % pool.length]);
  }
  return out.join('');
}

async function sharePassword(data) {
  const res = await request('/passwords/shared-passwords/', {
    method: 'POST',
    body: {
      password: data.password,
      days: data.days != null ? data.days : 7,
      max_uses: data.maxUses != null ? data.maxUses : 7,
    },
  });
  if (!res || res.status !== 'ok') {
    throw new Error((res && res.message) || 'No se pudo generar el enlace.');
  }
  return { ok: true, url: res.url, days: res.days, max_uses: res.max_uses, expires_at: res.expires_at };
}

async function generatePassword(opts = {}) {
  try {
    const base = await apiBase();
    const p = new URLSearchParams();
    p.set('length', String(opts.length || 24));
    p.set('upper', String(opts.upper !== false));
    p.set('lower', String(opts.lower !== false));
    p.set('digits', String(opts.digits !== false));
    p.set('symbols', String(opts.symbols !== false));
    p.set('exclude_similar', String(!!opts.exclude_similar));
    p.set('exclude_ambiguous', String(!!opts.exclude_ambiguous));
    p.set('passphrase', String(!!opts.passphrase));
    p.set('num_words', String(opts.num_words || 4));
    const data = await request('/passwords/generate/?' + p.toString());
    return { ok: true, password: data.password, entropy: data.entropy };
  } catch (e) {
    return { ok: true, password: localGenerate(opts), entropy: null };
  }
}

// ---------- Test de conexión ----------
async function testConnection() {
  try {
    await request('/auth/me/', { auth: true });
    return { ok: true, message: 'Conexión correcta y sesión activa.' };
  } catch (e) {
    if (e.status === 401) return { ok: true, message: 'Servidor alcanzable (sin sesión).' };
    if (e.status) return { ok: true, message: 'Servidor alcanzable.' };
    return { ok: false, message: e.message };
  }
}

// ---------- Enrutador de mensajes ----------
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handle(msg, sender)
    .then(sendResponse)
    .catch((e) => sendResponse({ ok: false, error: e.message }));
  return true;
});

async function handle(msg, sender) {
  const tabId = sender.tab ? sender.tab.id : null;
  const windowId = sender.tab ? sender.tab.windowId : null;
  switch (msg.type) {
    case 'logout': return doLogout();
    case 'getStatus': return getStatus();
    case 'getEntries': return getEntries(msg.hostname);
    case 'getEntry': return getEntry(msg.id);
    case 'saveEntry': return saveEntry(msg.entry, msg.hostname, msg.options);
    case 'setTotp': return setTotp(msg.id, msg.secret, msg.code);
    case 'removeTotp': return removeTotp(msg.id);
    case 'getPendingQr': return getPendingQr();
    case 'clearPendingQr': return clearPendingQr();
    case 'autoSetupTotp': return autoSetupTotp(msg.id);
    case 'selectQrForTotp': {
      const [active] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!active) throw new Error('No hay una pestaña activa.');
      await clearQrError();
      return startQrSelection(msg.entryId, active.id);
    }
    case 'qrCapture': {
      try {
        const dataUrl = await chrome.tabs.captureVisibleTab(windowId ? windowId : undefined, { format: 'png' });
        return { ok: true, dataUrl };
      } catch (e) {
        return { ok: false, error: 'No se pudo capturar la pestaña.' };
      }
    }
    case 'qrDecoded': return applyQrSecret(msg.secret);
    case 'qrFailed': return setQrError(msg.reason);
    case 'getQrError': return getQrError();
    case 'clearQrError': return clearQrError();
    case 'saveDetected': return saveDetected(tabId, msg.data);
    case 'getPendingSave': return getPendingSave(msg.tabId);
    case 'clearPendingSave': return clearPendingSave(msg.tabId);
    case 'fillEntry': return fillEntry(msg.tabId, msg.entryId);
    case 'openUrl':
      if (msg.url && /^https?:/i.test(msg.url)) await chrome.tabs.create({ url: msg.url });
      return { ok: true };
    case 'generatePassword': return generatePassword(msg.opts || {});
    case 'sharePassword': return sharePassword(msg.data || {});
    case 'testConnection': return testConnection();
    case 'getServerUrl': return { ok: true, serverUrl: await getServerUrl() };
    case 'setServerUrl': await chrome.storage.sync.set({ serverUrl: msg.serverUrl }); return { ok: true };
    default: throw new Error('Mensaje desconocido: ' + msg.type);
  }
}

// Aplica el icono de estado cada vez que el service worker se activa
// (recarga de la extensión, nuevo arranque del worker, etc.).
updateStateIconFromStorage();
