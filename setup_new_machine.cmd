@echo off
setlocal

rem Bootstrap the signed-in user's setup without changing global policy.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_new_machine.ps1" %*
exit /b %ERRORLEVEL%
