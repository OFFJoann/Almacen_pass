import time
from apps.passwords.encryption import encrypt_field, encrypt_field_fast
from apps.passwords.models import PasswordEntry

def bench(label, n=3):
    t0 = time.time()
    for _ in range(n):
        encrypt_field('MiClaveSecreta123!')
    print('%-22s %.3f s/call' % (label, (time.time()-t0)/n), flush=True)

bench('encrypt_field (Argon2)')
bench('encrypt_field_fast (AES)')

pw = PasswordEntry()
t0 = time.time()
pw.set_password('MiClaveSecreta123!')
print('%-22s %.3f s' % ('set_password total', time.time()-t0), flush=True)
t0 = time.time()
pw.set_username('usuario@test.com')
pw.set_notes('nota de prueba')
print('%-22s %.3f s' % ('set_username+notes', time.time()-t0), flush=True)
