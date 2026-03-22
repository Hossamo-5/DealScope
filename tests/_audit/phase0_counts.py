import pathlib
import re

root = pathlib.Path('.')
py_files = [p for p in root.rglob('*.py') if not any(x in p.parts for x in ['.venv', '__pycache__', 'htmlcov'])]
vue_files = [p for p in root.rglob('*') if p.suffix in {'.vue', '.js', '.ts'} and 'dashboard-vue' in p.parts and 'node_modules' not in p.parts]
test_files = [p for p in root.rglob('test_*.py') if 'htmlcov' not in p.parts]

ad = pathlib.Path('admin/dashboard.py')
txt = ad.read_text(encoding='utf-8') if ad.exists() else ''
ep_count = len(re.findall(r'@app\.(?:get|post|put|delete|patch)\(', txt))

h_count = 0
for fp in [pathlib.Path('bot/handlers/user.py'), pathlib.Path('bot/handlers/user2.py'), pathlib.Path('bot/handlers/admin.py')]:
    if fp.exists():
        t = fp.read_text(encoding='utf-8')
        h_count += len(re.findall(r'@router\.(?:message|callback_query)\(', t))

m = pathlib.Path('db/models.py')
mt = m.read_text(encoding='utf-8') if m.exists() else ''
tbl_count = len(re.findall(r"__tablename__\s*=\s*['\"]", mt))

print(f'Python files: {len(py_files)}')
print(f'Vue/JS/TS files in dashboard-vue: {len(vue_files)}')
print(f'Test files: {len(test_files)}')
print(f'API endpoints (decorators count): {ep_count}')
print(f'Bot handlers (router decorators): {h_count}')
print(f'DB tables (__tablename__ count): {tbl_count}')
