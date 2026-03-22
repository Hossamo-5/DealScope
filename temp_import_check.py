import os,sys,traceback
os.chdir('dealscope')
sys.path.insert(0,'.')
from importlib import import_module
try:
    import_module('bot.handlers.user')
    import_module('bot.handlers.user2')
    print('IMPORT_OK')
except Exception:
    traceback.print_exc()
    print('IMPORT_FAIL')
