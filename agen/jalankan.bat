@echo off
REM Menjalankan agen timbangan. Biarkan jendela ini terbuka selama timbangan dipakai.
cd /d "%~dp0"
title Agen Timbangan
if exist agen_timbang.exe (agen_timbang.exe) else (venv\Scripts\python agen_timbang.py)
pause
