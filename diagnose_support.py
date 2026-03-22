import re, sys
sys.path.insert(0, '.')

print('=' * 60)
print('SUPPORT SYSTEM DIAGNOSTIC')
print('=' * 60)

# ── 1. Keyboard button ────────────────────────
print('\n[1] KEYBOARD BUTTON:')
try:
    kb = open('bot/keyboards/main.py', encoding='utf-8').read()
    
    # Find ALL button texts
    buttons = re.findall(r'text=[\"\']([^\"\']+)[\"\']', kb)
    support_btns = [b for b in buttons if 'دعم' in b]
    
    if support_btns:
        for btn in support_btns:
            print(f'  Found: {repr(btn)}')
            print(f'  Hex:   {btn.encode("utf-8").hex()}')
    else:
        print('  ❌ NO SUPPORT BUTTON!')
        print('  All buttons:')
        for b in buttons:
            print(f'    {repr(b)}')
except Exception as e:
    print(f'  ❌ Error: {e}')

# ── 2. HANDLER ────────────────────────────────
print('\n[2] HANDLER IN user2.py:')
try:
    u2 = open('bot/handlers/user2.py', encoding='utf-8').read()
    
    # Check various handler patterns
    patterns = [
        (r'F\.text\s*==\s*[\"\']([^\"\']*دعم[^\"\']*)', 'F.text =='),
        (r'F\.text\.contains\([\"\']([^\"\']*دعم[^\"\']*)', 'F.text.contains'),
        (r'lambda.*دعم', 'lambda'),
    ]
    
    found_handler = None
    for pattern, ptype in patterns:
        matches = re.findall(pattern, u2)
        if matches:
            for m in matches:
                print(f'  {ptype}: {repr(m)}')
                if ptype == 'F.text ==' or ptype == 'F.text.contains':
                    print(f'  Hex: {m.encode("utf-8").hex()}')
                found_handler = m
    
    if 'BTN_SUPPORT' in u2:
        print('  Uses BTN_SUPPORT constant')
        try:
            from bot.constants import BTN_SUPPORT
            print(f'  Value: {repr(BTN_SUPPORT)}')
            print(f'  Hex:   {BTN_SUPPORT.encode("utf-8").hex()}')
            found_handler = BTN_SUPPORT
        except Exception as e:
            print(f'  ❌ Import error: {e}')
    
    if not found_handler and 'الدعم الفني' not in u2:
        print('  ❌ NO SUPPORT HANDLER AT ALL!')

except Exception as e:
    print(f'  ❌ Error: {e}')

# ── 3. Compare ────────────────────────────────
print('\n[3] MATCH CHECK:')
try:
    kb = open('bot/keyboards/main.py', encoding='utf-8').read()
    u2 = open('bot/handlers/user2.py', encoding='utf-8').read()
    
    # Get keyboard text
    kb_buttons = re.findall(r'text=[\"\']([^\"\']+)[\"\']', kb)
    kb_support = [b for b in kb_buttons if 'دعم' in b]
    
    # Get handler text
    h_support = re.findall(
        r'F\.text\s*==\s*[\"\']([^\"\']+)[\"\']', u2
    )
    h_support = [h for h in h_support if 'دعم' in h]
    
    if kb_support and h_support:
        kb_t = kb_support[0]
        h_t = h_support[0]
        
        if kb_t == h_t:
            print(f'  ✅ EXACT MATCH: {repr(kb_t)}')
        else:
            print(f'  ❌ MISMATCH!')
            print(f'  KB:      {repr(kb_t)}')
            print(f'  Handler: {repr(h_t)}')
            print(f'  KB hex:  {kb_t.encode("utf-8").hex()}')
            print(f'  H  hex:  {h_t.encode("utf-8").hex()}')
            
            # Character by character diff
            print('\n  Character differences:')
            for i, (c1, c2) in enumerate(
                zip(kb_t, h_t)
            ):
                if c1 != c2:
                    print(
                        f'    pos {i}: '
                        f'KB={repr(c1)}({ord(c1)}) '
                        f'H={repr(c2)}({ord(c2)})'
                    )
    elif kb_support and not h_support:
        print(f'  ❌ Handler uses different matching method')
        print(f'  KB button: {repr(kb_support[0])}')
        print('  Check if using lambda or contains')
    elif not kb_support:
        print('  ❌ No support button in keyboard')
        
except Exception as e:
    print(f'  Error: {e}')

# ── 4. FSM States ─────────────────────────────
print('\n[4] FSM STATES:')
u2 = open('bot/handlers/user2.py', encoding='utf-8').read()
checks = {
    'SupportTicketStates': 'States class',
    'choosing_department': 'Department state',
    'writing_message': 'Writing state',
    'support_create_ticket': 'Create ticket func',
    'SupportTicket': 'DB model used',
    'ticket_number': 'Ticket number gen',
    'session.commit': 'DB save',
}
for key, desc in checks.items():
    found = key in u2
    print(f'  {"✅" if found else "❌"} {desc}')

# ── 5. DB Models ──────────────────────────────
print('\n[5] DATABASE:')
try:
    from db.models import SupportTicket, SupportMessage
    print(f'  ✅ SupportTicket: {SupportTicket.__tablename__}')
    print(f'  ✅ SupportMessage: {SupportMessage.__tablename__}')
    
    # Check columns
    cols = [c.name for c in SupportTicket.__table__.columns]
    required = ['ticket_number', 'user_id', 'status', 
                'department', 'subject']
    for col in required:
        print(f'  {"✅" if col in cols else "❌"} column: {col}')
except Exception as e:
    print(f'  ❌ DB Error: {e}')

# ── 6. Router ─────────────────────────────────
print('\n[6] ROUTER:')
try:
    from bot.handlers.user2 import router
    print('  ✅ router imported successfully')
except Exception as e:
    print(f'  ❌ Import FAILED: {e}')
    import traceback
    traceback.print_exc()

# ── 7. Summary ────────────────────────────────
print('\n' + '=' * 60)
print('SUMMARY - Run this in bot to test:')
print('  Send /start then tap support button')
print('  Watch log for: SUPPORT HANDLER CALLED')
print('=' * 60)
