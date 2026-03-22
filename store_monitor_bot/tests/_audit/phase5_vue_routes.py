import re
with open('dashboard-vue/src/router/index.js', encoding='utf-8') as f:
    router_content = f.read()
paths = re.findall(r"path:\s*['\"]([^'\"]+)['\"]", router_content)
print('Existing routes:')
for p in paths:
    print(f'  {p}')
required_routes = ['/login','/','/dashboard','/opportunities','/users','/users/:telegram_id','/support','/support/team','/stores','/store-requests','/health','/settings','/notifications','/menu-builder','/groups','/id-resolver','/bots']
missing=[r for r in required_routes if not any(r.replace(':telegram_id',':id') in p or p in r for p in paths)]
if missing:
    print('MISSING ROUTES:')
    for r in missing:
        print(f'  MISS {r}')
else:
    print('All required routes present')
