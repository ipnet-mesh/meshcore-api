# syntax=docker/dockerfile:1
# Minimal Alpine-based Dockerfile for MeshCore MCP Server
FROM python:3.11-alpine

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package with pip cache mount (BuildKit feature)
# This caches downloaded packages across builds for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e .

# Expose default port
EXPOSE 8080

# Default command (can be overridden)
ENTRYPOINT ["meshcore_api"]
CMD ["--serial-port", "/dev/ttyUSB0", "--api-port", "8080"]

LABEL org.opencontainers.image.source="https://github.com/ipnet-mesh/meshcore-api"
LABEL org.opencontainers.image.description="MeshCore Companion Node API Server"
