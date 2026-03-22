# كيفية تشغيل البوت

## المشكلة الشائعة: تعارض النسخ
إذا ظهرت رسالة "Conflict" افعل التالي:
1. أغلق كل نوافذ PowerShell/Terminal
2. افتح Task Manager (Ctrl+Shift+Esc)
3. ابحث عن python.exe وأغلق كل النسخ
4. انتظر 5 ثواني
5. شغّل البوت من جديد

## التشغيل الصحيح

### Windows:
انقر مرتين على: start_bot.bat

### أو من PowerShell:
```powershell
cd C:\Path\To\dealscope\dealscope
..\.venv\Scripts\python.exe main.py
```

## للتأكد من النجاح:
ابحث عن هذه الرسائل في الـ console:
- ✅ Database ready
- ✅ All handlers registered  
- Run polling for bot @the_c_b_i_bot

## لوحة الإدارة:
افتح المتصفح: http://localhost:8000
