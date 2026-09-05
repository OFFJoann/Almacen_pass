import re, subprocess, tempfile, os

BASE = r'C:\Users\johan.duque\Documents\Almacen_pass\enterprise_password_manager\templates\passwords\vault.html'
src = open(BASE, encoding='utf-8').read()
scripts = re.findall(r'<script>(.*?)</script>', src, re.S)
js = '\n'.join(scripts)
js = re.sub(r"\{% url '[a-z_]+:[a-z_]+' %\}", "'/vault/'", js)
js = re.sub(r"\{%\s*(?:if|endif|for|endfor|else)\s+[^%]*%\}", '', js)
js = re.sub(r"\{\{[^}]*\}\}", "'0'", js)
js = re.sub(r"\{%[^%]*%\}", '', js)
fd, path = tempfile.mkstemp(suffix='.js')
os.write(fd, js.encode('utf-8'))
os.close(fd)
r = subprocess.run(['node', '--check', path], capture_output=True, text=True)
print('STDOUT:', r.stdout)
print('STDERR:', r.stderr)
print('EXIT:', r.returncode)
os.unlink(path)