@echo off
REM Membuat agen_timbang.exe (satu file, tidak butuh Python di PC jembatan).
REM Jalankan di komputer yang punya Python (mis. laptop server), lalu salin agen_timbang.exe + .env + jalankan.bat ke PC jembatan.
cd /d "%~dp0"
if not exist venv\Scripts\python.exe python -m venv venv
venv\Scripts\python -m pip install pyserial requests python-dotenv pyinstaller || (pause & exit /b 1)
venv\Scripts\pyinstaller --onefile --console --name agen_timbang agen_timbang.py || (pause & exit /b 1)
copy /y dist\agen_timbang.exe . >nul
echo.
echo Selesai: agen_timbang.exe ada di folder ini.
pause
