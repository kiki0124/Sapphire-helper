# Use a lightweight base image
FROM python:3.11-slim

# PYTHONDONTWRITEBYTECODE=1: Prevents Python from writing .pyc files to save space on disk.
# PYTHONUNBUFFERED=1: Ensures Python output is unbuffered so it will be displayed on console in real-time.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create and set the working directory
WORKDIR /app

# Create the database directory for our database (if the directory already exists, it will not be created again)
RUN mkdir -p /database

# Copy the requirements file first for caching
COPY requirements.txt .

# Install only the required packages (aiocache is not in requirements.txt and witout it the bot will not work)
RUN pip install --no-cache-dir -r requirements.txt aiocache

# Copy the rest of the bot code
COPY . .

# Command to run the bot
CMD ["python", "main.py"]
