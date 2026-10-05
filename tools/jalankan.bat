@echo off
REM Menjalankan aplikasi (waitress) dari venv. Tutup jendela ini = aplikasi berhenti.
cd /d "%~dp0.."
venv\Scripts\python serve.py
pause
