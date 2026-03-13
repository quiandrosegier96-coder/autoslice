@echo off
netsh advfirewall firewall add rule name="AutoSlice Backend" dir=in action=allow protocol=TCP localport=8000
echo Firewall regel toegevoegd voor poort 8000!
pause
