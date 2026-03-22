import asyncio, sys
sys.path.insert(0, 'dealscope')

async def test():
    from bot.keyboards.main import main_menu_keyboard
    kb = main_menu_keyboard()
    
    support_text = None
    for row in kb.keyboard:
        for btn in row:
            if 'دعم' in btn.text:
                support_text = btn.text
                break
        if support_text:
            break
    
    if not support_text:
        print('❌ No support button in keyboard!')
        return
    
    print(f'✅ Support button text: {repr(support_text)}')
    
    # Check catch-all routing
    user_handler = open(
        'dealscope/bot/handlers/user.py',
        encoding='utf-8'
    ).read()
    
    if 'الدعم الفني' in user_handler:
        print('✅ Catch-all routes support button')
    else:
        print('❌ Catch-all does NOT route support!')
    
    # Check support_menu exists
    u2 = open(
        'dealscope/bot/handlers/user2.py',
        encoding='utf-8'
    ).read()
    
    if 'async def support_menu' in u2:
        print('✅ support_menu function exists')
    else:
        print('❌ support_menu NOT FOUND!')
    
    if 'SupportTicketStates' in u2:
        print('✅ FSM states defined')
    else:
        print('❌ FSM states MISSING!')
    
    if 'ticket_number' in u2 and 'session.commit' in u2:
        print('✅ Ticket creation code exists')
    else:
        print('❌ Ticket creation INCOMPLETE!')
    
    print('\nTo test in Telegram:')
    print('1. Restart bot: python main.py')
    print('2. Send /start to bot')
    print('3. Tap support button')
    print('4. Watch logs for: SUPPORT MENU CALLED')

asyncio.run(test())
