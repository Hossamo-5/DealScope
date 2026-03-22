import re, sys
from pathlib import Path
sys.path.insert(0, '.')

files = {'user': 'bot/handlers/user.py', 'user2': 'bot/handlers/user2.py', 'admin': 'bot/handlers/admin.py'}

contents = {}
for name, path in files.items():
    try:
        text = open(path, encoding='utf-8').read()
        contents[name] = text
        print('LOADED: ' + path + ' (' + str(len(text)) + ' chars)')
    except Exception as e:
        print('FAILED: ' + path + ' -> ' + str(e))
        contents[name] = ''

kb_content = open('bot/keyboards/main.py', encoding='utf-8').read()

QD = chr(34); SQ = chr(39)
pat_btn = r'builder\.button\(text=([' + QD + SQ + r']{1,3})(.*?)\1'
kb_buttons = re.findall(pat_btn, kb_content)
kb_texts = [b[1] for b in kb_buttons]
print('KEYBOARD BUTTONS (' + str(len(kb_texts)) + '):')
for i, btn in enumerate(kb_texts, 1):
    print('  ' + str(i) + '. ' + repr(btn))

all_text_handlers = {}
all_callbacks = {}
all_commands = {}
for fname, content in contents.items():
    pat1 = r'F\.text\s*==\s*([' + QD + SQ + r']{1,3})(.*?)\1'
    for m in re.finditer(pat1, content):
        all_text_handlers[m.group(2)] = fname
    pat2 = r'F\.data\s*==\s*([' + QD + SQ + r']{1,3})(.*?)\1'
    for m in re.finditer(pat2, content):
        all_callbacks[m.group(2)] = fname
    pat3 = r'F\.data\.startswith\(([' + QD + SQ + r']{1,3})(.*?)\1\)'
    for m in re.finditer(pat3, content):
        all_callbacks[m.group(2) + '*'] = fname
    pat4 = r'Command\(([' + QD + SQ + r']{1,3})(.*?)\1\)'
    for m in re.finditer(pat4, content):
        all_commands[m.group(2)] = fname

print('TEXT HANDLERS (' + str(len(all_text_handlers)) + '):')
for k,v in all_text_handlers.items():
    print('  ' + repr(k) + ' -> ' + v)
print('CALLBACKS (' + str(len(all_callbacks)) + '):')
for k,v in all_callbacks.items():
    print('  ' + repr(k) + ' -> ' + v)
print('COMMANDS (' + str(len(all_commands)) + '):')
for k,v in all_commands.items():
    print('  ' + repr(k) + ' -> ' + v)

print('BUTTON->HANDLER MAPPING:')
for btn in kb_texts:
    if btn in all_text_handlers:
        print('OK: ' + repr(btn) + ' -> ' + all_text_handlers[btn])
    else:
        print('MISSING_HANDLER: ' + repr(btn))
