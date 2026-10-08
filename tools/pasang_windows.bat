@echo off
REM ===================================================================
REM  Pasang library aplikasi ke folder venv (sekali per komputer).
REM  Butuh: Python 3.10 / 3.11 64-bit (centang "Add python.exe to PATH" saat instal).
REM  Tidak perlu CMake / Visual Studio: dlib memakai paket jadi "dlib-bin".
REM  Bila ada folder paket_offline (dari tools\unduh_paket_offline.bat),
REM  pemasangan tidak butuh internet.
REM ===================================================================
cd /d "%~dp0.."
set PY=python
where py >nul 2>nul && py -3.11 -c "" >nul 2>nul && set PY=py -3.11
if "%PY%"=="python" where py >nul 2>nul && py -3.10 -c "" >nul 2>nul && set PY=py -3.10
%PY% -c "import sys,struct; sys.exit(0 if sys.version_info[:2] in ((3,10),(3,11)) and struct.calcsize('P')==8 else 1)"
if errorlevel 1 (
    echo [X] Butuh Python 3.10 / 3.11 64-bit. Unduh: https://www.python.org/downloads/release/python-3119/
    pause
    exit /b 1
)
if not exist venv\Scripts\python.exe (
    echo Membuat venv...
    %PY% -m venv venv || (pause & exit /b 1)
)
set SUMBER=
if exist paket_offline set SUMBER=--no-index --find-links paket_offline
if "%SUMBER%"=="" venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\python -m pip install %SUMBER% -r requirements.txt || (echo [X] Gagal memasang library & pause & exit /b 1)
venv\Scripts\python -m pip install %SUMBER% --no-deps face-recognition==1.3.0 || (pause & exit /b 1)
echo.
venv\Scripts\python tools\cek_lingkungan.py
pause
