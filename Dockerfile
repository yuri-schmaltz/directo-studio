FROM python:3.11-slim

WORKDIR /app

# Pre-install third-party dependencies for caching
RUN pip install --no-cache-dir fastapi uvicorn click httpx websockets streamlit

# Copy metadata and source code for the package install
COPY pyproject.toml README.md /app/
COPY directo /app/directo

# Install the package in editable mode
RUN pip install --no-cache-dir -e .

# Copy the rest of the application files
COPY . /app

CMD ["python", "-m", "directo.platform.cli", "--db-dir", "/data", "server", "--host", "0.0.0.0", "--port", "8000"]
