"""Notification channels for sending alerts."""

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional

from .thresholds import ThresholdViolation, format_violations_summary


@dataclass
class AlertChannel:
    """Configuration for an alert notification channel."""
    type: str  # "webhook", "email"
    config: Dict[str, Any]  # Channel-specific configuration
    enabled: bool = True


def send_alert(
    violations: List[ThresholdViolation],
    channels: List[AlertChannel],
    hostname: Optional[str] = None,
) -> Dict[str, bool]:
    """
    Send alert notifications for threshold violations.

    Args:
        violations: List of threshold violations
        channels: List of configured alert channels
        hostname: Hostname to include in alerts

    Returns:
        Dict mapping channel type to success status
    """
    if not violations:
        return {}

    results = {}

    for channel in channels:
        if not channel.enabled:
            continue

        try:
            if channel.type == "webhook":
                success = _send_webhook_alert(violations, channel.config, hostname)
            elif channel.type == "email":
                success = _send_email_alert(violations, channel.config, hostname)
            else:
                success = False

            results[channel.type] = success
        except Exception:
            results[channel.type] = False

    return results


def _send_webhook_alert(
    violations: List[ThresholdViolation],
    config: Dict[str, Any],
    hostname: Optional[str] = None,
) -> bool:
    """
    Send alert via webhook (generic, Slack, Discord).

    Config options:
    - url: Webhook URL (required)
    - format: "generic", "slack", "discord" (default: "generic")
    """
    url = config.get("url")
    if not url:
        return False

    format_type = config.get("format", "generic")
    timestamp = datetime.now().isoformat()

    critical_count = len([v for v in violations if v.severity == "critical"])
    warning_count = len([v for v in violations if v.severity == "warning"])

    if format_type == "slack":
        payload = _format_slack_payload(violations, hostname, timestamp)
    elif format_type == "discord":
        payload = _format_discord_payload(violations, hostname, timestamp)
    else:
        payload = _format_generic_payload(violations, hostname, timestamp)

    try:
        data = json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status < 400
    except (urllib.error.URLError, urllib.error.HTTPError):
        return False


def _format_generic_payload(
    violations: List[ThresholdViolation],
    hostname: Optional[str],
    timestamp: str,
) -> Dict[str, Any]:
    """Format payload for generic webhook."""
    critical = [v for v in violations if v.severity == "critical"]
    warnings = [v for v in violations if v.severity == "warning"]

    return {
        "timestamp": timestamp,
        "hostname": hostname or "unknown",
        "alert_type": "network_test",
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "summary": format_violations_summary(violations),
        "violations": [
            {
                "metric": v.metric,
                "target": v.target,
                "value": v.value,
                "threshold": v.threshold,
                "severity": v.severity,
                "message": v.message,
            }
            for v in violations
        ]
    }


def _format_slack_payload(
    violations: List[ThresholdViolation],
    hostname: Optional[str],
    timestamp: str,
) -> Dict[str, Any]:
    """Format payload for Slack webhook."""
    critical = [v for v in violations if v.severity == "critical"]
    warnings = [v for v in violations if v.severity == "warning"]

    color = "#dc3545" if critical else "#ffc107"
    title = f"Network Alert - {hostname or 'Unknown Host'}"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title,
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{len(critical)} critical*, *{len(warnings)} warning* violations detected"
            }
        }
    ]

    # Add violations as bullet points
    violation_text = ""
    if critical:
        violation_text += "*Critical:*\n"
        for v in critical[:5]:  # Limit to 5
            violation_text += f"• {v.message}\n"

    if warnings:
        violation_text += "*Warning:*\n"
        for v in warnings[:5]:
            violation_text += f"• {v.message}\n"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": violation_text
        }
    })

    return {
        "attachments": [
            {
                "color": color,
                "blocks": blocks
            }
        ]
    }


def _format_discord_payload(
    violations: List[ThresholdViolation],
    hostname: Optional[str],
    timestamp: str,
) -> Dict[str, Any]:
    """Format payload for Discord webhook."""
    critical = [v for v in violations if v.severity == "critical"]
    warnings = [v for v in violations if v.severity == "warning"]

    color = 0xdc3545 if critical else 0xffc107

    description = f"**{len(critical)} critical**, **{len(warnings)} warning** violations"

    fields = []
    if critical:
        fields.append({
            "name": "Critical",
            "value": "\n".join(f"• {v.message}" for v in critical[:5]),
            "inline": False
        })

    if warnings:
        fields.append({
            "name": "Warning",
            "value": "\n".join(f"• {v.message}" for v in warnings[:5]),
            "inline": False
        })

    return {
        "embeds": [
            {
                "title": f"Network Alert - {hostname or 'Unknown'}",
                "description": description,
                "color": color,
                "fields": fields,
                "timestamp": timestamp,
            }
        ]
    }


def _send_email_alert(
    violations: List[ThresholdViolation],
    config: Dict[str, Any],
    hostname: Optional[str] = None,
) -> bool:
    """
    Send alert via email using SMTP.

    Config options:
    - smtp_host: SMTP server hostname (required)
    - smtp_port: SMTP server port (default: 587)
    - username: SMTP username (optional)
    - password: SMTP password (optional)
    - from_addr: From email address (required)
    - to: List of recipient email addresses (required)
    - use_tls: Use TLS (default: True)
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = config.get("smtp_host")
    smtp_port = config.get("smtp_port", 587)
    username = config.get("username")
    password = config.get("password")
    from_addr = config.get("from_addr")
    to_addrs = config.get("to", [])
    use_tls = config.get("use_tls", True)

    if not smtp_host or not from_addr or not to_addrs:
        return False

    critical = [v for v in violations if v.severity == "critical"]
    warnings = [v for v in violations if v.severity == "warning"]

    subject = f"[{'CRITICAL' if critical else 'WARNING'}] Network Alert - {hostname or 'Unknown'}"

    body = f"""Network Test Alert
===================

Host: {hostname or 'Unknown'}
Time: {datetime.now().isoformat()}

{format_violations_summary(violations)}

---
This is an automated alert from nettest.
"""

    msg = MIMEMultipart()
    msg['From'] = from_addr
    msg['To'] = ', '.join(to_addrs)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)

        if username and password:
            server.login(username, password)

        server.sendmail(from_addr, to_addrs, msg.as_string())
        server.quit()
        return True

    except Exception:
        return False


def parse_alert_channels(config: Dict[str, Any]) -> List[AlertChannel]:
    """
    Parse alert channel configuration from config dict.

    Args:
        config: Full configuration dict

    Returns:
        List of AlertChannel objects
    """
    alerts_config = config.get("alerts", {})
    if not alerts_config.get("enabled", False):
        return []

    channels = []
    for channel_config in alerts_config.get("channels", []):
        channel_type = channel_config.get("type")
        if not channel_type:
            continue

        channels.append(AlertChannel(
            type=channel_type,
            config=channel_config,
            enabled=channel_config.get("enabled", True)
        ))

    return channels
