#!/bin/bash
# Start the IoT Traffic Physics engine in the background
python iot_sensor.py &

# Start the FastAPI Server in the foreground
python main.py
