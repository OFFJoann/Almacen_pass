// TICOlvidé - Selección de código QR con el mouse para configurar 2FA
(() => {
  if (window.__TICOLVIDE_QRSELECT__) return;
  window.__TICOLVIDE_QRSELECT__ = true;

  let overlay = null;
  let rectEl = null;
  let hintEl = null;
  let cancelBtn = null;
  let startPoint = null;
  let selecting = false;

  function addStyle() {
    const style = document.createElement('style');
    style.textContent = `
      .ticolvide-qr-overlay { position: fixed; inset: 0; z-index: 2147483647; background: rgba(0,0,0,.35); cursor: crosshair; }
      .ticolvide-qr-hint { position: fixed; top: 14px; left: 50%; transform: translateX(-50%); background: #1a237e; color: #fff; padding: 10px 16px; border-radius: 8px; font-size: 13px; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; z-index: 2147483647; box-shadow: 0 2px 12px rgba(0,0,0,.4); white-space: nowrap; }
      .ticolvide-qr-rect { position: fixed; border: 2px dashed #4caf50; background: transparent; z-index: 2147483647; pointer-events: none; }
      .ticolvide-qr-toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); padding: 10px 16px; border-radius: 8px; color: #fff; font-size: 13px; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; z-index: 2147483647; box-shadow: 0 2px 12px rgba(0,0,0,.4); max-width: 80%; text-align: center; }
      .ticolvide-qr-cancel { position: fixed; bottom: 24px; right: 24px; z-index: 2147483647; background: #fff; color: #c62828; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px 14px; font-size: 12px; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.2); }
    `;
    document.documentElement.appendChild(style);
  }

  function showToast(text, ok) {
    const t = document.createElement('div');
    t.className = 'ticolvide-qr-toast';
    t.style.background = ok ? '#2e7d32' : '#c62828';
    t.textContent = text;
    document.documentElement.appendChild(t);
    setTimeout(() => t.remove(), 4000);
  }

  function cleanup() {
    if (overlay) { overlay.remove(); overlay = null; }
    if (rectEl) { rectEl.remove(); rectEl = null; }
    if (hintEl) { hintEl.remove(); hintEl = null; }
    if (cancelBtn) { cancelBtn.remove(); cancelBtn = null; }
    startPoint = null;
    selecting = false;
  }

  function resetRect() {
    if (rectEl) rectEl.style.display = 'none';
    startPoint = null;
  }

  function startSelection() {
    if (overlay) return;
    addStyle();

    overlay = document.createElement('div');
    overlay.className = 'ticolvide-qr-overlay';

    hintEl = document.createElement('div');
    hintEl.className = 'ticolvide-qr-hint';
    hintEl.textContent = 'Arrastra el mouse para seleccionar el código QR';

    rectEl = document.createElement('div');
    rectEl.className = 'ticolvide-qr-rect';
    rectEl.style.display = 'none';

    cancelBtn = document.createElement('button');
    cancelBtn.className = 'ticolvide-qr-cancel';
    cancelBtn.textContent = 'Cancelar';
    cancelBtn.type = 'button';

    document.documentElement.appendChild(overlay);
    document.documentElement.appendChild(hintEl);
    document.documentElement.appendChild(rectEl);
    document.documentElement.appendChild(cancelBtn);

    const onDown = (ev) => {
      startPoint = { x: ev.clientX, y: ev.clientY };
      selecting = true;
      rectEl.style.left = startPoint.x + 'px';
      rectEl.style.top = startPoint.y + 'px';
      rectEl.style.width = '0px';
      rectEl.style.height = '0px';
      rectEl.style.display = 'block';
    };

    const onMove = (ev) => {
      if (!selecting || !startPoint) return;
      const x = Math.min(startPoint.x, ev.clientX);
      const y = Math.min(startPoint.y, ev.clientY);
      rectEl.style.left = x + 'px';
      rectEl.style.top = y + 'px';
      rectEl.style.width = Math.abs(ev.clientX - startPoint.x) + 'px';
      rectEl.style.height = Math.abs(ev.clientY - startPoint.y) + 'px';
    };

    const onUp = (ev) => {
      if (!selecting) return;
      selecting = false;
      const x = Math.min(startPoint.x, ev.clientX);
      const y = Math.min(startPoint.y, ev.clientY);
      const w = Math.abs(ev.clientX - startPoint.x);
      const h = Math.abs(ev.clientY - startPoint.y);
      if (w < 20 || h < 20) {
        showToast('Selección demasiado pequeña. Arrastra sobre el código QR.', false);
        resetRect();
        return;
      }
      overlay.style.display = 'none';
      if (hintEl) hintEl.textContent = 'Leyendo código QR…';
      decodeRegion({ x, y, width: w, height: h });
    };

    overlay.addEventListener('mousedown', onDown);
    overlay.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    cancelBtn.addEventListener('click', cleanup);
    window.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') cleanup(); }, { once: true });
  }

  function parseSecret(text) {
    const t = (text || '').trim();
    if (!t) return null;
    if (/^otpauth:\/\//i.test(t)) {
      try {
        const u = new URL(t);
        const secret = u.searchParams.get('secret');
        if (secret) return secret.replace(/\s+/g, '').toUpperCase();
      } catch (e) { /* ignore */ }
      return null;
    }
    return t.replace(/\s+/g, '').toUpperCase();
  }

  function findIntersectingImage(rect) {
    for (const img of document.images) {
      const b = img.getBoundingClientRect();
      if (b.width < 10 || b.height < 10) continue;
      const intersects = !(b.right < rect.x || b.left > rect.x + rect.width || b.bottom < rect.y || b.top > rect.y + rect.height);
      if (intersects) return img;
    }
    return null;
  }

  async function decodeImageElement(img) {
    const c = document.createElement('canvas');
    c.width = img.naturalWidth || img.width;
    c.height = img.naturalHeight || img.height;
    const ctx = c.getContext('2d');
    ctx.drawImage(img, 0, 0);
    const imageData = ctx.getImageData(0, 0, c.width, c.height);
    const result = jsQR(imageData.data, imageData.width, imageData.height, { inversionAttempts: 'attemptBoth' });
    return result && result.data ? result.data : null;
  }

  function decodeRegion(rect) {
    const img = findIntersectingImage(rect);
    if (img) {
      decodeImageElement(img)
        .then((text) => {
          if (text) { finish(text); return; }
          screenshotDecode(rect);
        })
        .catch(() => screenshotDecode(rect));
      return;
    }
    screenshotDecode(rect);
  }

  function screenshotDecode(rect) {
    chrome.runtime.sendMessage({ type: 'qrCapture' })
      .then((res) => {
        if (!res || !res.ok || !res.dataUrl) {
          showToast((res && res.error) || 'No se pudo capturar la pantalla.', false);
          cleanup();
          return;
        }
        const image = new Image();
        image.onload = () => {
          try {
            const scaleX = image.naturalWidth / window.innerWidth;
            const scaleY = image.naturalHeight / window.innerHeight;
            const cw = Math.max(1, Math.round(rect.width * scaleX));
            const ch = Math.max(1, Math.round(rect.height * scaleY));
            const c = document.createElement('canvas');
            c.width = cw;
            c.height = ch;
            const ctx = c.getContext('2d');
            ctx.drawImage(image, rect.x * scaleX, rect.y * scaleY, cw, ch, 0, 0, cw, ch);
            const imageData = ctx.getImageData(0, 0, cw, ch);
            const result = jsQR(imageData.data, imageData.width, imageData.height, { inversionAttempts: 'attemptBoth' });
            if (result && result.data) { finish(result.data); return; }
            showToast('No se detectó un código QR en la selección. Intenta de nuevo.', false);
          } catch (e) {
            showToast('Error al leer el código QR.', false);
          }
          cleanup();
        };
        image.onerror = () => { showToast('Error al procesar la captura.', false); cleanup(); };
        image.src = res.dataUrl;
      })
      .catch(() => {
        showToast('Error al capturar la pantalla.', false);
        cleanup();
      });
  }

  async function finish(text) {
    const secret = parseSecret(text);
    if (!secret) {
      showToast('El código seleccionado no contiene una clave 2FA válida.', false);
      cleanup();
      return;
    }
    const r = await chrome.runtime.sendMessage({ type: 'qrDecoded', secret }).catch(() => ({ ok: false, error: 'Sin respuesta del servidor.' }));
    showToast(r && r.ok ? 'QR leído. Reabre la extensión y confirma el código de verificación.' : (r && r.error) || 'No se pudo guardar el 2FA.', r && r.ok);
    cleanup();
  }

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'qrPing') { sendResponse({ ok: true }); return; }
    if (msg.type === 'qrStart') {
      startSelection();
      sendResponse({ ok: true });
      return;
    }
  });
})();
