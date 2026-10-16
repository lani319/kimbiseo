@echo off
chcp 65001 >nul
REM Edit URL / XPATH / OPEN time, then double-click. Close the browser window to exit.
set URL=https://example.com/event/123
set XPATH=//button[contains(@class,'btn-buy')]
set OPEN=2026-10-20 20:00:00

python -m buynow "%URL%" "%XPATH%" --at "%OPEN%" --lead 10 --text "BUY TICKET"
pause
