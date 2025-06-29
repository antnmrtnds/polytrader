@echo off
:loop
echo Starting place_order.py...
python place_order.py
echo Script crashed with exit code %errorlevel%. Restarting in 5 seconds...
timeout /t 5
goto loop 