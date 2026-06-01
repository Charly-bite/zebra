@echo off
echo Adding firewall rule for Zebra Label Editor (port 5005)...
netsh advfirewall firewall add rule name="Zebra Label Editor" dir=in action=allow protocol=TCP localport=5005
if %errorlevel%==0 (
    echo.
    echo SUCCESS! Port 5005 is now open.
    echo Other computers can access: http://192.168.2.172:5005
) else (
    echo.
    echo FAILED! Make sure you right-click and "Run as Administrator"
)
echo.
pause
