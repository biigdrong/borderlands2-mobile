@echo off
rem Divinity Original Sin 2 Mobile (DM_GAME=dos2, org.dos2.port): build, sign and optionally install the APK (wraps tools\build_apk.ps1; see README-DOS2.md "Building").
rem   build.bat [-Install <adb serial>] [-Validation] [-Android10]
setlocal
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build_apk.ps1" %*
exit /b %ERRORLEVEL%
