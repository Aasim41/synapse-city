FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Make start script executable
RUN chmod +x start.sh

# Run both the FastAPI backend and the IoT sensor
CMD ["./start.sh"]
