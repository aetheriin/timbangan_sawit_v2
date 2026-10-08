@echo off
REM Cari baudrate / data bits / parity indikator: deteksi.bat COM3
cd /d "%~dp0"
if "%1"=="" (set /p PORT=Port COM indikator, mis. COM3: ) else (set PORT=%1)
if exist agen_timbang.exe (agen_timbang.exe --deteksi %PORT%) else (venv\Scripts\python agen_timbang.py --deteksi %PORT%)
pause
