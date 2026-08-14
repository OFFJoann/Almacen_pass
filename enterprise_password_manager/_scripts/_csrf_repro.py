import urllib.request
import urllib.parse
import http.cookiejar
import re

base = 'http://127.0.0.1:8001'
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# login web para obtener cookies reales
r = op.open(base + '/auth/login/')
html = r.read().decode()
m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
csrf = m.group(1)
data = urllib.parse.urlencode({'csrfmiddlewaretoken': csrf, 'username': 'admin@example.com', 'password': '123'}).encode()
req = urllib.request.Request(base + '/auth/login/', data=data, headers={
    'Content-Type': 'application/x-www-form-urlencoded',
    'Referer': base + '/auth/login/',
})
r = op.open(req)
cookies = {c.name: c.value for c in jar}
print('cookies:', list(cookies.keys()))
sid = cookies.get('sessionid')

# petición de la extensión: cookies de sesión + Origin de chrome-extension
cookie_str = '; '.join('%s=%s' % (c.name, c.value) for c in jar)
req2 = urllib.request.Request(base + '/api/auth/token/session/', data=b'{}', method='POST', headers={
    'Content-Type': 'application/json',
    'Origin': 'chrome-extension://gpjomcodnagicnamglhnghdgnedekbec',
    'X-Session-ID': sid,
    'Cookie': cookie_str,
})
try:
    r2 = urllib.request.urlopen(req2)
    print('OK', r2.status, r2.read().decode()[:200])
except urllib.error.HTTPError as e:
    body = e.read().decode()[:400]
    print('STATUS', e.code)
    print(body)
