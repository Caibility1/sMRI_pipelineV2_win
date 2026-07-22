@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0smri_presurf_recon.ps1" %*
exit /b %ERRORLEVEL%
