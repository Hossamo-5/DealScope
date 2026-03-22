import sys
sys.path.insert(0, '.')
from admin.dashboard import app

routes = {}
for route in app.routes:
    if hasattr(route, 'methods'):
        for method in route.methods:
            routes[f'{method} {route.path}'] = True

required = [
    'POST /auth/login','POST /auth/refresh','POST /auth/logout','GET /auth/me','POST /auth/change-password','POST /auth/seed',
    'GET /api/stats','GET /api/health',
    'GET /api/opportunities','POST /api/opportunities/{opportunity_id}/approve','POST /api/opportunities/{opportunity_id}/reject','POST /api/opportunities/{opportunity_id}/postpone','POST /api/opportunities/manual',
    'GET /api/users','GET /api/users/{telegram_id}/profile','GET /api/users/{telegram_id}/activity','POST /api/users/{telegram_id}/upgrade','POST /api/users/{telegram_id}/ban','POST /api/users/{telegram_id}/unban','POST /api/users/{telegram_id}/send-message',
    'GET /api/support/tickets','GET /api/support/tickets/{ticket_id}','POST /api/support/tickets/{ticket_id}/reply','POST /api/support/tickets/{ticket_id}/assign','POST /api/support/tickets/{ticket_id}/resolve','POST /api/support/tickets/{ticket_id}/close','GET /api/support/team','POST /api/support/team','GET /api/support/stats',
    'GET /api/notifications','POST /api/notifications/{notification_id}/read','POST /api/notifications/read-all',
    'GET /api/settings/{category}','POST /api/settings/{category}','GET /api/settings/system/info','POST /api/settings/system/restart-monitor','POST /api/settings/system/clear-cache','GET /api/settings/system/export/{type}','POST /api/settings/test-ai-scraper',
    'GET /api/bot-menu','POST /api/bot-menu','PUT /api/bot-menu/{button_id}','DELETE /api/bot-menu/{button_id}','POST /api/bot-menu/reorder','POST /api/bot-menu/publish','POST /api/bot-menu/test-connection',
    'GET /api/groups','POST /api/groups','PUT /api/groups/{group_id}','DELETE /api/groups/{group_id}','POST /api/groups/{group_id}/test','POST /api/groups/{group_id}/verify','GET /api/bots','POST /api/bots','PUT /api/bots/{bot_id}','DELETE /api/bots/{bot_id}','POST /api/bots/{bot_id}/test','POST /api/bots/{bot_id}/toggle',
    'POST /api/telegram/resolve','POST /api/bot-menu/test-connection',
    'GET /api/store-requests','POST /api/store-requests/{request_id}/approve','POST /api/store-requests/{request_id}/reject',
    'GET /api/stores','POST /api/stores',
    'GET /api/dashboard/live',
    'POST /api/broadcast',
]

missing=[]
for ep in required:
    req_method, req_path = ep.split(' ', 1)
    path_parts = req_path.split('/')[1:]
    found=False
    for route_key in routes:
        method, route_path = route_key.split(' ',1)
        route_parts = route_path.split('/')[1:]
        if method == req_method and len(path_parts) == len(route_parts):
            found=True
            break
    if not found:
        missing.append(ep)

print(f'Total discovered routes: {len(routes)}')
if missing:
    print(f'MISSING {len(missing)} ENDPOINTS:')
    for e in missing:
        print(f'  MISS {e}')
else:
    print(f'All {len(required)} endpoints present OK')
