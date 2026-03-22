"""Phase 3: Dashboard API audit"""
import re, sys
sys.path.insert(0, '.')

try:
    from admin.dashboard import app
    routes_found = {}
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            for method in (route.methods or []):
                if method not in ('HEAD', 'OPTIONS'):
                    routes_found[f'{method} {route.path}'] = True

    print('='*60)
    print('ALL REGISTERED ROUTES:')
    print('='*60)
    for r in sorted(routes_found.keys()):
        print(f'  {r}')

    required_apis = [
        ('POST', '/auth/login'),
        ('POST', '/auth/logout'),
        ('GET',  '/auth/me'),
        ('GET',  '/api/stats'),
        ('GET',  '/api/health'),
        ('GET',  '/api/opportunities'),
        ('POST', '/api/opportunities/{opportunity_id}/approve'),
        ('POST', '/api/opportunities/{opportunity_id}/reject'),
        ('GET',  '/api/users'),
        ('POST', '/api/users/{telegram_id}/upgrade'),
        ('POST', '/api/users/{telegram_id}/ban'),
        ('POST', '/api/users/{telegram_id}/unban'),
        ('POST', '/api/users/{telegram_id}/send-message'),
        ('GET',  '/api/support/tickets'),
        ('GET',  '/api/support/tickets/{ticket_id}'),
        ('POST', '/api/support/tickets/{ticket_id}/reply'),
        ('POST', '/api/support/tickets/{ticket_id}/resolve'),
        ('GET',  '/api/support/team'),
        ('GET',  '/api/support/stats'),
        ('GET',  '/api/notifications'),
        ('POST', '/api/notifications/read-all'),
        ('GET',  '/api/settings/{category}'),
        ('POST', '/api/settings/{category}'),
        ('GET',  '/api/bot-menu'),
        ('POST', '/api/bot-menu'),
        ('POST', '/api/bot-menu/publish'),
        ('POST', '/api/bot-menu/test-connection'),
        ('POST', '/api/telegram/resolve'),
        ('GET',  '/api/groups'),
        ('POST', '/api/groups'),
        ('GET',  '/api/store-requests'),
        ('POST', '/api/broadcast'),
        ('GET',  '/api/dashboard/live'),
    ]

    print('\n' + '='*60)
    print('API AUDIT:')
    print('='*60)
    missing_apis = []
    for method, path in required_apis:
        found = False
        for rkey in routes_found:
            rm, rp = rkey.split(' ', 1)
            if rm != method:
                continue
            rn = re.sub(r'\{[^}]+\}', '{x}', rp)
            en = re.sub(r'\{[^}]+\}', '{x}', path)
            if rn == en:
                found = True
                break
        status = 'OK:      ' if found else 'MISSING: '
        print(f'{status}{method} {path}')
        if not found:
            missing_apis.append(f'{method} {path}')

    print(f'\nMissing APIs: {len(missing_apis)}')
    for api in missing_apis:
        print(f'  MISSING: {api}')

except Exception as e:
    import traceback
    print(f'IMPORT_FAIL: admin.dashboard -> {e}')
    traceback.print_exc()
