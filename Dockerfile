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

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy necessary files for the Python package installation
COPY pyproject.toml README.md ./
COPY backend/app /app/backend/app

# Install dependencies via uv
RUN uv pip install --system --no-cache -e .

# Create the data directory (for SQLite)
RUN mkdir -p /data

# Copy backend application code
COPY backend/app /app/app

# Copy the built frontend static files from Stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Expose the standard port
EXPOSE 8080

# Run the FastAPI server via Uvicorn
CMD ["sh", "-c", "uvicorn app.api:app --host 0.0.0.0 --port $PORT --proxy-headers"]
