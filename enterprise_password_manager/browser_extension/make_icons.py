import struct, zlib, os

OUT = os.path.join(os.path.dirname(__file__), 'icons')

def rounded_rect(x, y, w, h, r):
    def inside(px, py):
        dx = min(max(px - x, 0), w)
        dy = min(max(py - y, 0), h)
        if min(w, h) <= 2 * r:
            return True
        cx = x + min(r, w / 2)
        cy = y + min(r, h / 2)
        near_corner_x = px < cx or px > x + w - min(r, w / 2)
        near_corner_y = py < cy or py > y + h - min(r, h / 2)
        if not (near_corner_x and near_corner_y):
            return True
        # corner circle centers
        cxs = [x + r, x + w - r - 1]
        cys = [y + r, y + h - r - 1]
        best = min(((px - cx) ** 2 + (py - cy) ** 2) for cx in cxs for cy in cys)
        return best <= r * r
    return inside

def in_lock(px, py, S):
    # cuerpo
    body = rounded_rect(0.26 * S, 0.40 * S, 0.48 * S, 0.44 * S, 0.10 * S)
    if body(px, py):
        return True
    # candado (anillo)
    ring = rounded_rect(0.34 * S, 0.24 * S, 0.32 * S, 0.28 * S, 0.12 * S)
    hole = rounded_rect(0.42 * S, 0.31 * S, 0.16 * S, 0.21 * S, 0.06 * S)
    if ring(px, py) and not hole(px, py):
        return True
    return False

def in_keyhole(px, py, S):
    cx = 0.5 * S
    cy = 0.56 * S
    # ojo
    if (px - cx) ** 2 + (py - cy) ** 2 <= (0.07 * S) ** 2:
        return True
    # cola
    if abs(px - cx) <= 0.03 * S and 0.56 * S <= py <= 0.72 * S:
        return True
    return False

def bg_color(px, py, S):
    rect = rounded_rect(0.05 * S, 0.05 * S, 0.90 * S, 0.90 * S, 0.22 * S)
    if rect(px, py):
        return (26, 35, 126, 255)
    return (0, 0, 0, 0)

def make_png(size):
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            r, g, b, a = bg_color(x, y, size)
            if in_keyhole(x, y, size):
                r, g, b, a = 26, 35, 126, 255
            elif in_lock(x, y, size):
                r, g, b, a = 255, 255, 255, 255
            row += bytes((r, g, b, a))
        rows.append(bytes(row))
    raw = b''.join(rows)

    def chunk(typ, data):
        c = struct.pack('>I', len(data)) + typ + data
        return c + struct.pack('>I', zlib.crc32(typ + data) & 0xffffffff)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    idat = zlib.compress(raw, 9)
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')

os.makedirs(OUT, exist_ok=True)
for s in (16, 48, 128):
    path = os.path.join(OUT, 'icon%d.png' % s)
    with open(path, 'wb') as f:
        f.write(make_png(s))
    print('wrote', path, os.path.getsize(path), 'bytes')
