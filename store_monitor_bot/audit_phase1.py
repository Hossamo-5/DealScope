"""Phase 1: Static handler analysis"""
import re, sys
from pathlib import Path
sys.path.insert(0, '.')

files = {
    'user':  'bot/handlers/user.py',
    'user2': 'bot/handlers/user2.py',
    'admin': 'bot/handlers/admin.py',
}

contents = {}
for name, path in files.items():
    try:
        text = open(path, encoding='utf-8').read()
        contents[name] = text
        print(f'LOADED: {path} ({len(text)} chars)')
    except Exception as e:
        print(f'FAILED: {path} -> {e}')
        contents[name] = ''

kb_content = open('bot/keyboards/main.py', encoding='utf-8').read()

kb_buttons = re.findall(r'builder\.button\(text=(["\'{1,3}])(.*?)\1', kb_content)
# More robust: find ALL button texts including multiline
kb_texts_raw = re.findall(r'builder\.button\(\s*text\s*=\s*["\']([^"\']+)["\']', kb_content)
print(f'\nKEYBOARD BUTTONS ({len(kb_texts_raw)}):')
for i, btn in enumerate(kb_texts_raw, 1):
    print(f'  {i}. {repr(btn)}')

all_text_handlers = {}
all_callbacks = {}
all_commands = {}
for fname, content in contents.items():
    for m in re.finditer(r'F\.text\s*==\s*["\']([^"\']+)["\']', content):
        all_text_handlers[m.group(1)] = fname
    for m in re.finditer(r'F\.data\s*==\s*["\']([^"\']+)["\']', content):
        all_callbacks[m.group(1)] = fname
    for m in re.finditer(r'F\.data\.startswith\(["\']([^"\']+)["\']\)', content):
        all_callbacks[m.group(1) + '*'] = fname
    for m in re.finditer(r'Command\(["\']([^"\']+)["\']\)', content):
        all_commands[m.group(1)] = fname

print(f'\nTEXT_HANDLERS ({len(all_text_handlers)}):')
for k, v in sorted(all_text_handlers.items()):
    print(f'  {repr(k)} -> {v}')

print(f'\nCALLBACKS ({len(all_callbacks)}):')
for k, v in sorted(all_callbacks.items()):
    print(f'  {repr(k)} -> {v}')

print(f'\nCOMMANDS ({len(all_commands)}):')
for k, v in sorted(all_commands.items()):
    print(f'  {repr(k)} -> {v}')

print('\nBUTTON->HANDLER CHECK:')
# Only check main menu buttons (the ones in main_menu_keyboard)
main_menu_content = kb_content[kb_content.find('def main_menu_keyboard'):kb_content.find('\ndef ', kb_content.find('def main_menu_keyboard')+1)]
main_menu_buttons = re.findall(r'builder\.button\(\s*text\s*=\s*["\']([^"\']+)["\']', main_menu_content)
print(f'Main menu buttons: {main_menu_buttons}')
for btn in main_menu_buttons:
    if btn in all_text_handlers:
        print(f'OK: {repr(btn)} -> {all_text_handlers[btn]}')
    else:
        print(f'MISSING_HANDLER: {repr(btn)}')
