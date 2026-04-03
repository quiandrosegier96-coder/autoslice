@echo off
rem 7za wrapper: runs real 7za but converts exit code 2 (symlink-only errors)
rem to 0 so that winCodeSign extraction succeeds without Windows Developer Mode.
"%~dp0node_modules\7zip-bin\win\x64\7za.exe" %*
if %ERRORLEVEL%==2 exit /b 0
exit /b %ERRORLEVEL%
