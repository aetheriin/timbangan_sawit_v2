@echo off
REM Pasang agen timbangan di PC jembatan (sekali saja). Butuh Python 3.8+ (centang "Add python.exe to PATH").
REM PC tanpa Python: pakai agen_timbang.exe (dibuat dengan buat_exe.bat di komputer lain).
cd /d "%~dp0"
if not exist venv\Scripts\python.exe python -m venv venv || (echo [X] Python belum terpasang & pause & exit /b 1)
venv\Scripts\python -m pip install pyserial requests python-dotenv || (pause & exit /b 1)
if not exist .env copy .env.contoh .env >nul & echo Isi file .env dulu (alamat server, JEMBATAN_ID, KIOSK_ID, KIOSK_TOKEN).
echo.
echo Selesai. Isi .env lalu jalankan jalankan.bat
pause
