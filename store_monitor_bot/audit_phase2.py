"""Phase 2+: Callback audit, DB check, import check"""
import re, sys, asyncio
from pathlib import Path
sys.path.insert(0, '.')

# Read all handler files
contents = {}
for name, path in [
    ('user', 'bot/handlers/user.py'),
    ('user2', 'bot/handlers/user2.py'),
    ('admin', 'bot/handlers/admin.py'),
]:
    try:
        contents[name] = open(path, encoding='utf-8').read()
    except Exception as e:
        print(f'FAILED to load {path}: {e}')
        contents[name] = ''

all_content = '\n'.join(contents.values())

required_callbacks = {
    'go_home':                 'Return to main menu',
    'add_product':             'Start add product flow',
    'product_start_monitoring':'Save product to DB',
    'product_pause':           'Pause monitoring',
    'product_resume':          'Resume monitoring',
    'product_delete':          'Delete product',
    'alert_toggle':            'Toggle alert type',
    'alert_save':              'Save alert settings',
    'product_detail':          'Show product details',
    'show_price_history':      'Show price history',
    'deal_detail':             'Show deal details',
    'watch_from_deal':         'Add deal to watchlist',
    'support_new':             'New support ticket',
    'support_dept':            'Select department',
    'support_view':            'View existing ticket',
    'support_cancel':          'Cancel support',
    'support_back':            'Back in support',
    'help:quickstart':         'Help quickstart',
    'help:add_product':        'Help add product',
    'help:alerts':             'Help alerts',
    'help:plans':              'Help plans',
    'help:faq':                'Help FAQ',
    'help:main':               'Help main menu',
    'help:restart_onboarding': 'Restart onboarding',
    'upgrade_plan':            'Show upgrade options',
    'plan_info':               'Show plan details',
    'compare_plans':           'Compare all plans',
    'settings_mute':           'Toggle mute',
    'onboarding_next':         'Next onboarding step',
    'onboarding_start':        'Start using bot',
    'admin_opportunities':     'Admin: view opportunities',
    'admin_users':             'Admin: view users',
    'admin_broadcast':         'Admin: broadcast',
    'opp_approve':             'Approve opportunity',
    'opp_reject':              'Reject opportunity',
    'opp_postpone':            'Postpone opportunity',
    'quick_reply':             'Admin quick reply',
    'store_req_approve':       'Approve store request',
    'store_req_reject':        'Reject store request',
}

print('='*60)
print('CALLBACK AUDIT')
print('='*60)

missing = []
for cb, description in required_callbacks.items():
    cb_prefix = cb.split(':')[0]
    found = (
        f"'{cb}'" in all_content or
        f'"{cb}"' in all_content or
        f"data == '{cb}'" in all_content or
        f'data == "{cb}"' in all_content or
        f"startswith('{cb_prefix}')" in all_content or
        f'startswith("{cb_prefix}")' in all_content or
        cb in all_content
    )
    if found:
        print(f'OK:      {cb:<35} {description}')
    else:
        print(f'MISSING: {cb:<35} {description}')
        missing.append((cb, description))

print(f'\nMissing callbacks: {len(missing)}')
for cb, desc in missing:
    print(f'  MISSING: {cb}: {desc}')

# Check imports
print('\n' + '='*60)
print('IMPORT CHECK')
print('='*60)

checks = {
    'utils.bot_registry':            ['get_bot', 'set_bot'],
    'db.crud':                       ['create_admin_notification', 'get_user_open_tickets'],
    'bot.middleware.activity_tracker':['ActivityTrackerMiddleware'],
    'utils.url_validator':           ['URLValidator'],
}

for module, functions in checks.items():
    try:
        mod = __import__(module, fromlist=functions)
        for func in functions:
            if hasattr(mod, func):
                print(f'OK: {module}.{func}')
            else:
                print(f'MISSING: {module}.{func}')
    except Exception as e:
        print(f'IMPORT_FAIL: {module} -> {e}')

# Check .env
print('\n' + '='*60)
print('ENV CHECK')
print('='*60)
env_path = Path('.env')
if env_path.exists():
    env = env_path.read_text(encoding='utf-8')
    for key in ['BOT_TOKEN', 'DATABASE_URL', 'ADMIN_GROUP_ID', 'ADMIN_USER_IDS', 'REDIS_URL']:
        m = re.search(rf'^{key}=(.+)', env, re.MULTILINE)
        if m:
            val = m.group(1).strip()
            masked = val[:6] + '...' if len(val) > 6 else val
            print(f'SET: {key}={masked}')
        else:
            print(f'MISSING: {key}')
else:
    print('NO .env FILE FOUND')
