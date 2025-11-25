# Minimal Alpine-based Dockerfile for MeshCore MCP Server
FROM python:3.11-alpine

# Install build dependencies (needed for some Python packages)
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir -e .

# Expose default port
EXPOSE 8000

# Default command (can be overridden)
ENTRYPOINT ["python", "-m", "meshcore_api"]
CMD ["--serial-port", "/dev/ttyUSB0", "--api-port", "8080"]

LABEL org.opencontainers.image.source="https://github.com/ipnet-mesh/meshcore-api"
LABEL org.opencontainers.image.description="MeshCore Companion Node API Server"
