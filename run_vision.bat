@echo off
title Synapse City - Indian Traffic Vision Sensor
echo ========================================================
echo   Synapse City: Real Indian Traffic Vision Sensor
echo   Powered by YOLOv8 + OpenCV + PyTorch DQN
echo ========================================================
echo.
echo Checking Python environment...
set PYTHONIOENCODING=utf-8
python vision_sensor.py %*
pause
