import urllib.request
import urllib.error

req = urllib.request.Request(
    'http://127.0.0.1:8001/api/auth/token/session/',
    data=b'{}',
    method='POST',
    headers={
        'Content-Type': 'application/json',
        'Origin': 'chrome-extension://gpjomcodnagicnamglhnghdgnedekbec',
        'X-Session-ID': 'fake',
    },
)
try:
    r = urllib.request.urlopen(req)
    print('OK', r.status)
except urllib.error.HTTPError as e:
    print('STATUS', e.code)
    print(e.read().decode()[:400])
