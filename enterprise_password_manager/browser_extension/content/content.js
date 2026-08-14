// TICOlvidé - content script (autofill + save detection)
(() => {
  if (window.__TICOLVIDE_CONTENT__) return;
  window.__TICOLVIDE_CONTENT__ = true;

  const HOSTNAME = location.hostname;
  let widget = null;
  let lastPasswordInput = null;
  let lastUsernameInput = null;

  // ---------- Detección de campos ----------
  function scoreUsernameInput(input) {
    const id = (input.id || '').toLowerCase();
    const name = (input.name || '').toLowerCase();
    const ac = (input.getAttribute('autocomplete') || '').toLowerCase();
    let score = 0;
    if (input.type === 'email') score += 1;
    if (/user|email|login|account|identif|correo|usuario/.test(id)) score += 2;
    if (/user|email|login|account|identif|correo|usuario/.test(name)) score += 2;
    if (ac.includes('username') || ac.includes('email')) score += 1;
    return score;
  }

  function findUsernameInput(passwordInput) {
    const form = passwordInput.closest('form');
    const candidates = [];
    if (form) {
      form.querySelectorAll('input').forEach((i) => {
        if (i === passwordInput || i.type === 'password' || i.type === 'hidden') return;
        if (['text', 'email', 'tel', 'number'].includes(i.type) && i.offsetParent !== null) {
          candidates.push(i);
        }
      });
    }
    candidates.sort((a, b) => scoreUsernameInput(b) - scoreUsernameInput(a));
    return candidates[0] || null;
  }

  function findPasswordInputs() {
    return Array.from(document.querySelectorAll('input[type="password"]')).filter((i) => i.offsetParent !== null);
  }

  // ---------- Relleno ----------
  function setNativeValue(el, value) {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) desc.set.call(el, value);
    else el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function findOtpInput() {
    const inputs = Array.from(document.querySelectorAll('input')).filter((i) => i.offsetParent !== null);
    return inputs.find((i) => {
      const ac = (i.getAttribute('autocomplete') || '').toLowerCase();
      if (ac.includes('one-time-code')) return true;
      if (i.type === 'hidden' || i.type === 'password') return false;
      const hay = ((i.id || '') + ' ' + (i.name || '') + ' ' + (i.placeholder || '') + ' ' + (i.className || '')).toLowerCase();
      return /(otp|totp|mfa|2fa|verification|verif|code|token|pin|authenticator|one[\s_-]?time)/.test(hay) &&
        ['text', 'tel', 'number', 'email'].includes(i.type);
    });
  }

  function fillFields(username, password, totp) {
    const pwd = lastPasswordInput || findPasswordInputs()[0];
    if (!pwd) return false;
    const user = lastUsernameInput || findUsernameInput(pwd);
    if (password) setNativeValue(pwd, password);
    if (username && user) setNativeValue(user, username);
    if (totp) {
      const otp = findOtpInput();
      if (otp) setNativeValue(otp, totp);
    }
    try { pwd.focus(); } catch (e) { /* ignore */ }
    return true;
  }

  // ---------- Widget flotante ----------
  function ensureWidget() {
    if (widget) return widget;
    const host = document.createElement('div');
    host.className = 'ticolvide-widget';
    const btn = document.createElement('button');
    btn.className = 'ticolvide-widget-btn';
    btn.type = 'button';
    btn.title = 'TICOlvidé';
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M18 8h-1V6a5 5 0 0 0-10 0v2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2zm-6 9a2 2 0 1 1 0-4 2 2 0 0 1 0 4zm3-9H9V6a3 3 0 0 1 6 0z"/></svg>';
    const list = document.createElement('div');
    list.className = 'ticolvide-widget-list';
    list.hidden = true;
    host.appendChild(btn);
    host.appendChild(list);

    const style = document.createElement('style');
    style.textContent = `
      .ticolvide-widget { position: fixed; right: 16px; bottom: 16px; z-index: 2147483000; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }
      .ticolvide-widget-btn { width: 44px; height: 44px; border-radius: 50%; border: none; cursor: pointer;
        background: #1a237e; color: #fff; box-shadow: 0 2px 10px rgba(0,0,0,.35); display: flex; align-items: center; justify-content: center; }
      .ticolvide-widget-btn:hover { background: #283593; }
      .ticolvide-widget-list { position: absolute; right: 0; bottom: 52px; width: 320px; max-height: 320px; overflow: auto;
        background: #fff; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,.25); color: #212121; }
      .ticolvide-widget-list h6 { margin: 0; padding: 10px 12px; font-size: 12px; text-transform: uppercase; color: #757575; border-bottom: 1px solid #eee; }
      .ticolvide-item { display: block; width: 100%; text-align: left; border: none; background: none; padding: 9px 12px;
        cursor: pointer; border-bottom: 1px solid #f5f5f5; font-size: 13px; color: #212121; }
      .ticolvide-item:hover { background: #e8eaf6; }
      .ticolvide-item .t-name { font-weight: 600; }
      .ticolvide-item .t-user { display: block; color: #757575; font-size: 11px; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .ticolvide-empty { padding: 16px; text-align: center; color: #9e9e9e; font-size: 12px; }
      .ticolvide-err { padding: 16px; text-align: center; color: #c62828; font-size: 12px; }
    `;
    document.documentElement.appendChild(style);

    btn.addEventListener('click', async () => {
      if (!list.hidden) { list.hidden = true; return; }
      list.hidden = false;
      list.innerHTML = '<div class="ticolvide-empty">Cargando…</div>';
      try {
        const res = await chrome.runtime.sendMessage({ type: 'getEntries', hostname: HOSTNAME });
        if (!res || !res.ok) throw new Error((res && res.error) || 'Error');
        const entries = (res.matched || []).filter((e) => e.url);
        list.innerHTML = '';
        const title = document.createElement('h6');
        title.textContent = 'Accesos para ' + HOSTNAME;
        list.appendChild(title);
        if (!entries.length) {
          const d = document.createElement('div');
          d.className = 'ticolvide-empty';
          d.textContent = 'No hay accesos guardados para este sitio.';
          list.appendChild(d);
        }
        for (const entry of entries) {
          const b = document.createElement('button');
          b.type = 'button';
          b.className = 'ticolvide-item';
          const name = document.createElement('span');
          name.className = 't-name';
          name.textContent = entry.name || entry.url;
          b.appendChild(name);
          if (entry.shared_by_email) {
            const badge = document.createElement('span');
            badge.style.cssText = 'float:right;font-size:10px;color:#1a237e;background:#e8eaf6;border-radius:8px;padding:1px 6px;';
            badge.textContent = 'Compartido';
            b.appendChild(badge);
          }
          b.addEventListener('click', async () => {
            list.hidden = true;
            try {
              const d = await chrome.runtime.sendMessage({ type: 'getEntry', id: entry.id });
              if (!d || !d.ok) throw new Error('Error');
              fillFields(d.entry.username || '', d.entry.password || '');
            } catch (e) {
              list.hidden = false;
              list.innerHTML = '<div class="ticolvide-err">No se pudo completar el autocompletado.</div>';
            }
          });
          list.appendChild(b);
        }
      } catch (e) {
        list.innerHTML = '<div class="ticolvide-err">' + (e.message || 'Error de conexión') + '</div>';
      }
    });

    document.addEventListener('click', (ev) => {
      if (!host.contains(ev.target)) list.hidden = true;
    });

    widget = host;
    document.documentElement.appendChild(host);
    return widget;
  }

  function showWidget(pwdInput) {
    ensureWidget().style.display = 'flex';
  }

  // ---------- Detección de guardado ----------
  function captureForm(form, passwordInput) {
    const usernameInput = findUsernameInput(passwordInput);
    const username = usernameInput && usernameInput.value ? usernameInput.value : '';
    const password = passwordInput.value;
    if (!password) return null;
    const siteName = HOSTNAME.replace(/^www\./, '').split('.')[0] || HOSTNAME;
    return {
      url: location.href.split('#')[0],
      hostname: HOSTNAME,
      username,
      password,
      name: siteName.charAt(0).toUpperCase() + siteName.slice(1),
    };
  }

  document.addEventListener('submit', (ev) => {
    const form = ev.target;
    if (!(form instanceof HTMLFormElement)) return;
    const pwd = form.querySelector('input[type="password"]');
    if (!pwd) return;
    const data = captureForm(form, pwd);
    if (data) {
      chrome.runtime.sendMessage({ type: 'saveDetected', data }).catch(() => {});
    }
  }, true);

  // ---------- Mensajes ----------
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'ping') { sendResponse({ ok: true }); return; }
    if (msg.type === 'fill') {
      const ok = fillFields(msg.username, msg.password, msg.totp);
      sendResponse({ ok });
      return;
    }
  });

  document.addEventListener('focusin', (ev) => {
    if (ev.target instanceof HTMLInputElement && ev.target.type === 'password') {
      lastPasswordInput = ev.target;
      lastUsernameInput = findUsernameInput(ev.target);
      showWidget(ev.target);
    }
  }, true);
})();
