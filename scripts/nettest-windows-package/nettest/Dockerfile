# Network Testing Tool Docker Image
#
# Build: docker build -t nettest .
# Run:   docker run --rm --cap-add NET_RAW nettest --profile quick
#
# For monitoring mode with Prometheus metrics:
#   docker run -d --cap-add NET_RAW -p 9101:9101 nettest --monitor --prometheus-port 9101

FROM python:3.12-slim

LABEL maintainer="Network Testing Tool" \
      description="Comprehensive network testing and diagnostics tool" \
      version="2.0.0"

# Install network testing tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    dnsutils \
    mtr-tiny \
    curl \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    pip install --no-cache-dir speedtest-cli && \
    rm /tmp/requirements.txt

# Set up application directory
WORKDIR /app

# Copy package files into nettest package directory
COPY __init__.py __main__.py cli.py config.py diagnostics.py models.py ./nettest/
COPY tests/ ./nettest/tests/
COPY output/ ./nettest/output/
COPY tui/ ./nettest/tui/
COPY alerts/ ./nettest/alerts/
COPY utils/ ./nettest/utils/

# Create directories for config, output, and data
RUN mkdir -p /config /output /data

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Default config search path
ENV NETTEST_CONFIG=/config/nettest.yml

# Volumes for persistence
VOLUME ["/config", "/output", "/data"]

# Entry point
ENTRYPOINT ["python", "-m", "nettest"]

# Default command (show help)
CMD ["--help"]
