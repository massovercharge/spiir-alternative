# ==============================================================================
# Stage 1: Build the frontend (React + Vite)
# ==============================================================================
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy package files and install dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy the rest of the frontend source code and build
COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Build the backend and serve the frontend
# ==============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    PENG_DATA_DIR=/data

WORKDIR /app

# Create non-root system user and group
RUN groupadd -g 1000 peng && \
    useradd -u 1000 -g peng -s /bin/bash -m peng

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy necessary files for the Python package installation
COPY pyproject.toml README.md ./
COPY backend/app /app/backend/app

# Install dependencies via uv
RUN uv pip install --system --no-cache -e .

# Create data directories with appropriate subdirectories
RUN mkdir -p /data/backups /data/kvitteringer /data/storebox-downloads /data/local_secrets /data/transactions \
             /app/data/backups /app/data/kvitteringer /app/data/storebox-downloads /app/data/local_secrets /app/data/transactions

# Copy backend application code
COPY backend/app /app/app

# Copy the built frontend static files from Stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Ensure proper file ownership for non-root execution
RUN chown -R peng:peng /data /app /home/peng

# Switch to non-root user
USER peng

# Expose the standard port
EXPOSE 8080

# Run the FastAPI server via Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers"]
