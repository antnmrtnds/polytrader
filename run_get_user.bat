@echo off
:loop
echo Starting get_user.py...
python get_user.py
echo Script crashed with exit code %errorlevel%. Restarting in 5 seconds...
timeout /t 5
goto loop
