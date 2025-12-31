# 📊 Monitoring Guide

[← Back to README](../README.md)

Complete guide to the monitoring stack: Prometheus, Grafana, alerting, and observability.

---

## Table of Contents

- [Overview](#overview)
- [Components](#components)
- [Prometheus](#prometheus)
- [Grafana](#grafana)
- [AlertManager](#alertmanager)
- [Additional Monitoring](#additional-monitoring)
- [Custom Dashboards](#custom-dashboards)
- [Alerting Rules](#alerting-rules)

---

## Overview

### Architecture

```mermaid
flowchart TB
    subgraph COLLECTION["📊 Data Collection"]
        NodeExporter["Node Exporter<br/>(System Metrics)"]
        cAdvisor["cAdvisor<br/>(Container Metrics)"]
        AppMetrics["App Exporters<br/>(Service Metrics)"]
    end

    subgraph STORAGE["💾 Storage"]
        Prometheus["Prometheus<br/>(Time Series DB)"]
    end

    subgraph VISUALIZATION["📈 Visualization"]
        Grafana["Grafana<br/>(Dashboards)"]
    end

    subgraph ALERTING["🚨 Alerting"]
        AlertManager["AlertManager"]
        Notifications["Notifications"]
    end

    NodeExporter -->|scrape| Prometheus
    cAdvisor -->|scrape| Prometheus
    AppMetrics -->|scrape| Prometheus
    Prometheus -->|query| Grafana
    Prometheus -->|alerts| AlertManager
    AlertManager -->|notify| Notifications

    style Prometheus fill:#e6522c,color:#fff
    style Grafana fill:#f46800,color:#fff
    style AlertManager fill:#9b59b6,color:#fff
```

### Access Points

| Service | URL | Default Credentials |
|:--------|:----|:--------------------|
| **Grafana** | `http://your-server:3000` | admin / admin |
| **Prometheus** | `http://your-server:9090` | None |
| **AlertManager** | `http://your-server:9093` | None |
| **Uptime Kuma** | `http://your-server:3001` | Create on first visit |

---

## Components

### Enabled by Default

| Component | Purpose | Port |
|:----------|:--------|:----:|
| **Prometheus** | Metrics storage & querying | 9090 |
| **Grafana** | Visualization & dashboards | 3000 |
| **AlertManager** | Alert routing | 9093 |
| **Node Exporter** | System metrics | 9100 |
| **cAdvisor** | Container metrics | 8081 |
| **Uptime Kuma** | Uptime monitoring | 3001 |

### Optional (via Profiles)

| Component | Purpose | Profile | Port |
|:----------|:--------|:--------|:----:|
| **Speedtest Tracker** | Internet speed history | `speedtest` | 8765 |
| **Scrutiny** | Disk S.M.A.R.T. health | `scrutiny` | 8082 |
| **Glances** | System resource monitor | `monitoring` | 61208 |

---

## Prometheus

### Data Flow

```mermaid
sequenceDiagram
    participant Targets as Scrape Targets
    participant Prometheus as Prometheus
    participant Storage as TSDB Storage
    participant Rules as Alert Rules
    participant AM as AlertManager

    loop Every 15s
        Prometheus->>Targets: HTTP GET /metrics
        Targets-->>Prometheus: Metrics data
        Prometheus->>Storage: Store time series
    end

    loop Every 15s
        Prometheus->>Rules: Evaluate rules
        Rules-->>Prometheus: Firing alerts
        Prometheus->>AM: Send alerts
    end
```

### Configuration

Location: `/opt/media-stack/data/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - /etc/prometheus/rules/*.yml

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
```

### Adding Scrape Targets

Add new targets to `prometheus.yml`:

```yaml
scrape_configs:
  # ... existing configs ...

  - job_name: 'your-service'
    static_configs:
      - targets: ['service-name:port']
    metrics_path: /metrics  # default
```

Reload Prometheus:
```bash
docker compose restart prometheus
```

### Useful PromQL Queries

```mermaid
mindmap
  root((PromQL Queries))
    System
      CPU Usage
      Memory Usage
      Disk Usage
      Network I/O
    Containers
      Container CPU
      Container Memory
      Container Status
    Custom
      Service Uptime
      Request Rates
      Error Rates
```

**CPU Usage:**
```promql
100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

**Memory Usage:**
```promql
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
```

**Disk Usage:**
```promql
(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100
```

**Container CPU:**
```promql
rate(container_cpu_usage_seconds_total{name!=""}[5m]) * 100
```

**Container Memory:**
```promql
container_memory_usage_bytes{name!=""}
```

### Data Retention

Default retention: 30 days

To change, edit compose file:
```yaml
prometheus:
  command:
    - '--storage.tsdb.retention.time=90d'
```

---

## Grafana

### Initial Setup

1. Access `http://your-server:3000`
2. Login: admin / admin
3. Change password when prompted
4. Explore pre-configured dashboards

### Pre-configured Dashboards

| Dashboard | Description |
|:----------|:------------|
| **Docker Overview** | Container status, resource usage |
| **System Metrics** | CPU, memory, disk, network |
| **Node Exporter Full** | Detailed system metrics |

### Dashboard Organization

```mermaid
graph TB
    subgraph GRAFANA["Grafana"]
        subgraph FOLDERS["📁 Dashboard Folders"]
            Infrastructure["Infrastructure"]
            Media["Media Services"]
            Custom["Custom"]
        end

        subgraph INFRA_DASH["Infrastructure Dashboards"]
            Docker["Docker Overview"]
            System["System Metrics"]
            Node["Node Exporter Full"]
        end

        subgraph MEDIA_DASH["Media Dashboards"]
            Plex["Plex Stats"]
            Immich["Immich Metrics"]
        end

        Infrastructure --> INFRA_DASH
        Media --> MEDIA_DASH
    end

    style GRAFANA fill:#f46800,color:#fff
```

### Adding Dashboards

#### From Grafana.com

1. Go to Dashboards → Import
2. Enter dashboard ID (e.g., `1860` for Node Exporter)
3. Select Prometheus data source
4. Click Import

**Recommended Dashboard IDs:**
- `1860` - Node Exporter Full
- `893` - Docker and System Monitoring
- `14282` - cAdvisor Container Metrics

#### Custom Dashboard

1. Go to Dashboards → New → New Dashboard
2. Add visualization
3. Select Prometheus data source
4. Enter PromQL query
5. Configure display options
6. Save dashboard

### Data Sources

Pre-configured:
- **Prometheus** - `http://prometheus:9090`

Add additional sources in Settings → Data Sources.

### Plugins

Installed by default:
- grafana-clock-panel
- grafana-simple-json-datasource
- grafana-piechart-panel

Add more in configuration:
```yaml
grafana:
  environment:
    GF_INSTALL_PLUGINS: grafana-worldmap-panel,grafana-polystat-panel
```

---

## AlertManager

### Alert Flow

```mermaid
flowchart LR
    subgraph PROMETHEUS["Prometheus"]
        Rules["Alert Rules"]
        Eval["Evaluation"]
    end

    subgraph ALERTMANAGER["AlertManager"]
        Route["Routing"]
        Group["Grouping"]
        Silence["Silencing"]
        Notify["Notification"]
    end

    subgraph RECEIVERS["Receivers"]
        Discord["Discord"]
        Slack["Slack"]
        Email["Email"]
        Webhook["Webhook"]
    end

    Rules --> Eval
    Eval -->|"Firing"| Route
    Route --> Group
    Group --> Silence
    Silence --> Notify
    Notify --> Discord
    Notify --> Slack
    Notify --> Email
    Notify --> Webhook

    style PROMETHEUS fill:#e6522c,color:#fff
    style ALERTMANAGER fill:#9b59b6,color:#fff
```

### Configuration

Location: `/opt/media-stack/data/alertmanager/config/alertmanager.yml`

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'default'

receivers:
  - name: 'default'
    # Configure your notification channels here
```

### Notification Channels

#### Discord

```yaml
receivers:
  - name: 'discord'
    discord_configs:
      - webhook_url: 'https://discord.com/api/webhooks/xxx/yyy'
```

#### Slack

```yaml
receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx/yyy/zzz'
        channel: '#alerts'
```

#### Email

```yaml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@example.com'
  smtp_auth_username: 'your@email.com'
  smtp_auth_password: 'app-password'

receivers:
  - name: 'email'
    email_configs:
      - to: 'admin@example.com'
```

### Silence Alerts

1. Go to AlertManager UI (`http://your-server:9093`)
2. Click "Silence"
3. Configure matchers and duration
4. Create silence

> [!TIP]
> Use silences during maintenance windows to prevent alert spam.

---

## Additional Monitoring

### Uptime Kuma

```mermaid
graph TB
    subgraph KUMA["Uptime Kuma"]
        direction TB
        HTTP["HTTP/HTTPS Monitors"]
        TCP["TCP Port Monitors"]
        Ping["Ping Monitors"]
        Docker["Docker Monitors"]
    end

    subgraph TARGETS["Monitor Targets"]
        Plex["Plex :32400"]
        Immich["Immich :2283"]
        Postgres["PostgreSQL :5432"]
        Services["Other Services"]
    end

    HTTP --> Plex
    HTTP --> Immich
    TCP --> Postgres
    HTTP --> Services

    style KUMA fill:#5cdd8b,color:#000
```

Self-hosted uptime monitoring:

1. Access `http://your-server:3001`
2. Create account
3. Add monitors:
   - HTTP(s) - web services
   - TCP - ports
   - Ping - servers
   - Docker - containers

**Monitor Examples:**
| Type | Target | Interval |
|:-----|:-------|:---------|
| HTTP | `http://plex:32400/web` | 60s |
| HTTP | `http://immich:2283` | 60s |
| TCP | `postgres:5432` | 30s |

### Speedtest Tracker

Internet speed monitoring:

```bash
# Enable profile
docker compose --profile speedtest up -d
```

Access: `http://your-server:8765`

Default login: admin@example.com / password

Features:
- Scheduled speed tests
- Historical graphs
- ISP tracking

### Scrutiny

Disk health monitoring:

```bash
# Enable profile
docker compose --profile scrutiny up -d
```

Access: `http://your-server:8082`

Monitors:
- S.M.A.R.T. attributes
- Temperature
- Reallocated sectors
- Failure prediction

> [!WARNING]
> Pay attention to Scrutiny warnings—disk failures can result in data loss!

### Glances

Real-time system monitor:

```bash
# Enable profile
docker compose --profile monitoring up -d
```

Access: `http://your-server:61208`

Shows:
- CPU, memory, disk, network
- Process list
- Docker containers
- Sensors

---

## Custom Dashboards

### Docker Container Dashboard

```mermaid
graph TB
    subgraph DASHBOARD["Docker Dashboard"]
        subgraph ROW1["Container Overview"]
            Running["Running Count"]
            Stopped["Stopped Count"]
            Health["Health Status"]
        end

        subgraph ROW2["Resource Usage"]
            CPU["CPU by Container"]
            Memory["Memory by Container"]
            Network["Network I/O"]
        end

        subgraph ROW3["Detailed Metrics"]
            CPUGraph["CPU Time Series"]
            MemGraph["Memory Time Series"]
        end
    end

    style DASHBOARD fill:#2c3e50,color:#fff
```

Create a dashboard showing all containers:

```json
{
  "panels": [
    {
      "title": "Container CPU Usage",
      "type": "timeseries",
      "targets": [
        {
          "expr": "rate(container_cpu_usage_seconds_total{name!=\"\"}[5m]) * 100",
          "legendFormat": "{{name}}"
        }
      ]
    },
    {
      "title": "Container Memory Usage",
      "type": "timeseries",
      "targets": [
        {
          "expr": "container_memory_usage_bytes{name!=\"\"} / 1024 / 1024",
          "legendFormat": "{{name}}"
        }
      ]
    }
  ]
}
```

### Media Server Dashboard

Monitor Plex/Jellyfin:

```promql
# Active streams (requires Tautulli exporter)
tautulli_current_streams

# Transcode count
tautulli_transcode_count

# Library size
tautulli_library_count
```

### System Health Dashboard

```promql
# Disk space remaining
node_filesystem_avail_bytes{mountpoint="/"}

# Memory available
node_memory_MemAvailable_bytes

# Network throughput
rate(node_network_receive_bytes_total[5m])
rate(node_network_transmit_bytes_total[5m])
```

---

## Alerting Rules

### Alert Severity Levels

```mermaid
graph LR
    subgraph SEVERITY["Alert Severity"]
        Info["ℹ️ Info"]
        Warning["⚠️ Warning"]
        Critical["🔴 Critical"]
    end

    Info -->|"No action needed"| Log["Log only"]
    Warning -->|"Investigate soon"| Notify["Notify team"]
    Critical -->|"Immediate action"| Page["Page on-call"]

    style Info fill:#3498db,color:#fff
    style Warning fill:#f39c12,color:#fff
    style Critical fill:#e74c3c,color:#fff
```

### Location

`/opt/media-stack/data/prometheus/rules/alerts.yml`

### Example Rules

```yaml
groups:
  - name: system
    rules:
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage detected"
          description: "CPU usage is above 80% for 5 minutes"

      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High memory usage detected"
          description: "Memory usage is above 90%"

      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 < 10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Low disk space"
          description: "Less than 10% disk space remaining"

  - name: containers
    rules:
      - alert: ContainerDown
        expr: absent(container_last_seen{name=~"plex|immich_server|grafana"})
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Critical container is down"
          description: "Container {{ $labels.name }} is not running"

      - alert: ContainerHighCPU
        expr: rate(container_cpu_usage_seconds_total{name!=""}[5m]) * 100 > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Container high CPU"
          description: "Container {{ $labels.name }} CPU usage is high"
```

### Reload Rules

```bash
# Prometheus will auto-reload, or force:
docker compose restart prometheus
```

---

## Maintenance

### View Metrics Storage

```bash
# Check Prometheus data size
du -sh /opt/media-stack/data/prometheus/

# Check retention
curl http://localhost:9090/api/v1/status/config | jq '.data.yaml' | grep retention
```

### Backup Dashboards

```bash
# Export all dashboards
for dashboard in $(curl -s http://admin:admin@localhost:3000/api/search | jq -r '.[].uid'); do
  curl -s "http://admin:admin@localhost:3000/api/dashboards/uid/$dashboard" | jq '.dashboard' > "dashboard_$dashboard.json"
done
```

### Clean Old Data

```bash
# Prometheus handles retention automatically
# To force cleanup, restart with lower retention temporarily
```

---

## Monitoring Checklist

### Daily
- [ ] Check Grafana dashboards for anomalies
- [ ] Review any triggered alerts

### Weekly
- [ ] Check Prometheus storage usage
- [ ] Review alert history
- [ ] Verify all scrape targets are up

### Monthly
- [ ] Update dashboards as needed
- [ ] Review and tune alert thresholds
- [ ] Backup custom dashboards

---

## Related Documentation

- [Architecture](architecture.md) - System design
- [Configuration](configuration.md) - Service configuration
- [Troubleshooting](troubleshooting.md) - Debugging issues

---

[← Back to README](../README.md)
