@echo off
REM ===================================================================
REM  Unduh semua paket library ke folder paket_offline (+-280 MB), supaya
REM  laptop / PC lain bisa memasang TANPA internet: salin folder proyek
REM  beserta paket_offline, lalu jalankan tools\pasang_windows.bat.
REM  Jalankan di komputer Windows yang punya internet + Python 3.11 64-bit.
REM ===================================================================
cd /d "%~dp0.."
set PY=python
where py >nul 2>nul && py -3.11 -c "" >nul 2>nul && set PY=py -3.11
%PY% -m pip download -r requirements.txt -d paket_offline || (pause & exit /b 1)
%PY% -m pip download --no-deps face-recognition==1.3.0 -d paket_offline || (pause & exit /b 1)
%PY% -m pip download setuptools wheel pip -d paket_offline || (pause & exit /b 1)
echo.
echo Selesai: folder paket_offline siap disalin bersama folder proyek.
pause
