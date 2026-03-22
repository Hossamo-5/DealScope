modules = [
    'main', 'config.settings', 'db.models',
    'db.crud', 'admin.dashboard', 'auth.security',
    'core.monitor', 'core.connectors.amazon',
    'core.connectors.generic',
    'core.connectors.ai_scraper',
    'bot.handlers.user', 'bot.handlers.user2',
    'bot.handlers.admin', 'bot.keyboards.main',
    'utils.bot_registry', 'utils.url_validator',
]
for m in modules:
    try:
        __import__(m)
        print(f'OK {m}')
    except Exception as e:
        print(f'ERR {m}: {e}')
