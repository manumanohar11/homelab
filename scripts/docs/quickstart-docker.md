# Quickstart Guide: Docker

This guide covers running nettest in Docker containers.

## Prerequisites

- Docker installed and running
- Docker Compose (optional, for monitoring setup)

## Building the Image

Clone the repository and build:

```bash
git clone https://github.com/manumanohar11/nettest.git
cd nettest/nettest
docker build -t nettest .
```

## Running nettest

### Basic Usage

Run a quick test:

```bash
docker run --rm --cap-add NET_RAW nettest --profile quick
```

Run a full diagnostic:

```bash
docker run --rm --cap-add NET_RAW nettest --profile full
```

Note: `--cap-add NET_RAW` is required for ICMP ping operations.

### Test Video Services

```bash
docker run --rm --cap-add NET_RAW nettest --video-services
```

### Generate Reports

Save HTML report to host:

```bash
docker run --rm --cap-add NET_RAW -v $(pwd)/output:/output nettest \
    --profile full --format html --output /output/report.html
```

Save JSON results:

```bash
docker run --rm --cap-add NET_RAW -v $(pwd)/output:/output nettest \
    --profile full --format json --output /output/results.json
```

## Custom Configuration

Mount a configuration file:

```bash
docker run --rm --cap-add NET_RAW \
    -v $(pwd)/nettest.yml:/config/nettest.yml \
    nettest --profile full
```

## Continuous Monitoring

### With Prometheus Metrics

Run nettest with Prometheus endpoint:

```bash
docker run -d --name nettest-monitor \
    --cap-add NET_RAW \
    -p 9101:9101 \
    nettest --monitor --prometheus-port 9101 --interval 60
```

Access metrics at `http://localhost:9101/metrics`.

### Docker Compose Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  nettest:
    build: ./nettest
    container_name: nettest-monitor
    cap_add:
      - NET_RAW
    ports:
      - "9101:9101"
    volumes:
      - ./config/nettest.yml:/config/nettest.yml:ro
      - ./output:/output
      - nettest-data:/data
    environment:
      - NETTEST_CONFIG=/config/nettest.yml
    command: ["--monitor", "--prometheus-port", "9101", "--interval", "60"]
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    restart: unless-stopped

volumes:
  nettest-data:
  prometheus-data:
  grafana-data:
```

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 60s

scrape_configs:
  - job_name: 'nettest'
    static_configs:
      - targets: ['nettest:9101']
```

Start the stack:

```bash
docker compose up -d
```

## Troubleshooting

### Ping fails with "Operation not permitted"

Ensure `--cap-add NET_RAW` is included:

```bash
docker run --rm --cap-add NET_RAW nettest --profile quick
```

### DNS resolution fails

Use host network mode if container DNS is problematic:

```bash
docker run --rm --network host nettest --profile quick
```

### speedtest-cli connection issues

The container may need internet access through your firewall. Test connectivity:

```bash
docker run --rm nettest curl -I https://www.speedtest.net
```

### Config file not found

Verify the volume mount path is correct:

```bash
docker run --rm -v /absolute/path/to/nettest.yml:/config/nettest.yml nettest --help
```

### Permission denied on output directory

Ensure the output directory is writable:

```bash
mkdir -p output && chmod 777 output
docker run --rm --cap-add NET_RAW -v $(pwd)/output:/output nettest \
    --format html --output /output/report.html
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NETTEST_CONFIG` | Path to configuration file | `/config/nettest.yml` |
| `PYTHONUNBUFFERED` | Unbuffered output | `1` |

## Next Steps

- See the main [README](../README.md) for full documentation
- Configure Grafana dashboards for visualization
- Set up alerting with Prometheus Alertmanager
