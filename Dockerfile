# Production container for Agentic Audit Dashboard
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps (for pdfplumber)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg-dev \
    libpng-dev \
    libxml2 \
    libxslt1.1 \
    libffi8 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY agentic_audit/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . /app

# Create exports dir
RUN mkdir -p /app/exports

EXPOSE 8000

# Start via Waitress serving the Flask app object
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "agentic_audit.tools.simple_dashboard:app"]
