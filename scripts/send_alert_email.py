#!/usr/bin/env python3
"""Career Pilot — Alert Email Sender

Reads SMTP credentials from config/alert_config.yaml and sends
the daily job alert output as a plain-text email.

Usage:
    python3 scripts/send_alert_email.py "EMAIL BODY TEXT"
    echo "body" | python3 scripts/send_alert_email.py
"""

import sys
import smtplib
import textwrap
from email.mime.text import MIMEText
from pathlib import Path
from datetime import datetime

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


CONFIG_PATH = Path(__file__).parent.parent / "config" / "alert_config.yaml"


def load_config():
    if not CONFIG_PATH.exists():
        print(f"❌ Config not found: {CONFIG_PATH}", file=sys.stderr)
        print("   Run: bash scripts/setup_alert.sh", file=sys.stderr)
        sys.exit(1)

    if HAS_YAML:
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)

    # Fallback: parse minimal YAML manually
    config = {}
    with open(CONFIG_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or ":" not in line:
                continue
            key, _, val = line.partition(":")
            config[key.strip()] = val.strip().strip('"').strip("'")
    return config


def build_subject(body: str) -> str:
    for line in body.splitlines():
        if "🚨" in line or "JOB ALERT" in line:
            # Strip emoji clutter for email subject line
            clean = line.replace("🚨", "").replace("━", "").strip()
            return f"[Career Pilot] {clean}"
    return f"[Career Pilot] Daily Scan — {datetime.now().strftime('%b %d, %Y')}"


def send_email(body: str):
    config = load_config()

    sender = config.get("email", "")
    password = config.get("app_password", "")
    recipient = config.get("recipient", sender)
    smtp_host = config.get("smtp_host", "smtp.gmail.com")
    smtp_port = int(config.get("smtp_port", 587))

    if not sender or not password:
        print("❌ email or app_password missing in alert_config.yaml", file=sys.stderr)
        sys.exit(1)

    subject = build_subject(body)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"Career Pilot <{sender}>"
    msg["To"] = recipient

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)

    print(f"✅ Alert sent to {recipient} — {subject}")


def main():
    if len(sys.argv) > 1:
        body = sys.argv[1]
    elif not sys.stdin.isatty():
        body = sys.stdin.read()
    else:
        print("Usage: python3 send_alert_email.py 'BODY TEXT'", file=sys.stderr)
        sys.exit(1)

    send_email(body)


if __name__ == "__main__":
    main()
