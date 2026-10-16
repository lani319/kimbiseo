@echo off
chcp 65001 >nul
REM Edit URL / XPATH / OPEN, then double-click. Close the browser window to exit.
set URL=https://example.com/event/123
set XPATH=//button[contains(@class,'btn-buy')]
set OPEN=2026-10-20 20:00:00

REM Use the bundled buynow.exe if present (no Python needed), else the installed package.
if exist "%~dp0buynow.exe" (
  "%~dp0buynow.exe" "%URL%" "%XPATH%" --at "%OPEN%" --lead 10 --text "BUY TICKET"
) else (
  python -m buynow "%URL%" "%XPATH%" --at "%OPEN%" --lead 10 --text "BUY TICKET"
)
pause
