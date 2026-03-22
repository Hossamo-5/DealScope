import re

handler_files = [
    'bot/handlers/user.py',
    'bot/handlers/user2.py',
    'bot/handlers/admin.py',
]

all_handlers = set()
all_callbacks = set()

for filepath in handler_files:
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    text_handlers = re.findall(r'F\.text == [\"\'](.*?)[\"\']\)', content)
    all_handlers.update(text_handlers)

    callbacks = re.findall(r'F\.data == [\"\'](.*?)[\"\']\)', content)
    all_callbacks.update(callbacks)

    commands = re.findall(r'Command\([\"\'](.*?)[\"\']\)', content)
    print(f'{filepath}: {len(commands)} commands, {len(text_handlers)} text handlers')

required_text = [
    '➕ إضافة منتج', '📦 منتجاتي',
    '📂 مراقبة فئة', '🏪 مراقبة متجر',
    '🔥 أفضل العروض', '📊 التقارير',
    '💳 الاشتراك', '⚙️ الإعدادات',
    '❓ المساعدة', '🏬 طلب إضافة متجر',
    '🎧 الدعم الفني',
]

missing_text = [t for t in required_text if t not in all_handlers]
if missing_text:
    print('MISSING TEXT HANDLERS:')
    for h in missing_text:
        print(f'  MISS {h}')
else:
    print(f'All {len(required_text)} text handlers OK')

required_callbacks = [
    'go_home', 'add_product',
    'product_start_monitoring',
    'support_new', 'upgrade_plan',
    'compare_plans', 'settings_mute',
    'admin_opportunities', 'admin_users',
    'admin_broadcast',
]
missing_cb = [c for c in required_callbacks if c not in all_callbacks]
if missing_cb:
    print('MISSING CALLBACKS:')
    for c in missing_cb:
        print(f'  MISS {c}')
else:
    print('All required callbacks OK')
