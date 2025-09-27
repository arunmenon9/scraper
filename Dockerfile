FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY main.py web.py scraper.py parser.py ./
COPY .env.example .env

# Create directories for data
RUN mkdir -p data/raw_data data/uploads logs

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port for web interface
EXPOSE 8000

# Default command (can be overridden)
CMD ["python", "web.py"]