# Use official lightweight Python image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies (optional but good for most Python libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port (default FastAPI/uvicorn port)
EXPOSE 8000

# Run the FastAPI app with uvicorn (adjust app.main:app to your file:app variable)
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
