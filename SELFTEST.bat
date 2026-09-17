@echo off
cd /d "%~dp0"
python -c "import os,android_cleaner as a; a.init_db(); print('ADB:',a.find_adb()); ap=a.find_aapt2(); print('AAPT2:',ap); assert ap and os.path.isfile(ap),'AAPT2 missing - run SETUP.bat'; print('Resolver prerequisites: OK')"
pause
