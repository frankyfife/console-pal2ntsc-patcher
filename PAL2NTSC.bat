@echo off
rem PAL2NTSC starten. Dateien oder Ordner koennen auch auf diese .bat
rem gezogen werden - sie landen dann direkt in der Liste.
setlocal
cd /d "%~dp0"
start "" pythonw "%~dp0PAL2NTSC.pyw" %*
