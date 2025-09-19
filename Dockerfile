# Use official Python image as base
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

EXPOSE 3978

# Start the application (adjust if your entrypoint is different)
CMD ["python", "src/main.py"]
