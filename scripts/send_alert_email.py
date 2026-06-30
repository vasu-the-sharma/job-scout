#!/usr/bin/env python3
"""Career Pilot — Alert Notifier

Sends job alert via:
  1. macOS system notification (always works, no config)
  2. Gmail SMTP (optional — needs App Password in alert_config.yaml)

Usage:
    python3 scripts/send_alert_email.py "ALERT BODY"
    echo "body" | python3 scripts/send_alert_email.py
"""

import sys
import subprocess
import smtplib
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
        return {}
    if HAS_YAML:
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
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
        if "JOB ALERT" in line or "🚨" in line:
            clean = line.replace("🚨", "").replace("━", "").strip()
            return f"[Career Pilot] {clean}"
    return f"[Career Pilot] Daily Scan — {datetime.now().strftime('%b %d, %Y')}"


def notify_macos(subject: str, body: str):
    """Fire a macOS notification banner — works with no config."""
    # Extract first match line for the subtitle
    subtitle = ""
    for line in body.splitlines():
        if "/100" in line and ("🟢" in line or "🟡" in line):
            subtitle = line.strip()
            break

    script = f'''
    display notification "{subtitle or 'New job matches found. Open Career Pilot.'}" ¬
        with title "Career Pilot 🚀" ¬
        subtitle "{subject}"
    '''
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        print("✅ macOS notification sent.")
        return True
    except Exception as e:
        print(f"⚠️  macOS notification failed: {e}")
        return False


def send_email(body: str, config: dict):
    """Send via Gmail SMTP. Returns True on success, False on failure."""
    sender = config.get("email", "")
    password = str(config.get("app_password", "")).replace(" ", "")
    recipient = config.get("recipient", sender)
    smtp_host = config.get("smtp_host", "smtp.gmail.com")
    smtp_port = int(config.get("smtp_port", 587))

    if not sender or not password or len(password) < 16:
        print("⚠️  Email skipped — app_password not configured in alert_config.yaml.")
        return False

    subject = build_subject(body)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"Career Pilot <{sender}>"
    msg["To"] = recipient

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        print(f"✅ Email sent to {recipient} — {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("⚠️  Email auth failed. To fix:")
        print("   1. Enable 2-Step Verification: myaccount.google.com/security")
        print("   2. Generate App Password: myaccount.google.com/apppasswords")
        print("   3. Update app_password in config/alert_config.yaml")
        return False
    except Exception as e:
        print(f"⚠️  Email failed: {e}")
        return False


def main():
    if len(sys.argv) > 1:
        body = sys.argv[1]
    elif not sys.stdin.isatty():
        body = sys.stdin.read().strip()
    else:
        print("Usage: python3 send_alert_email.py 'BODY TEXT'", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    subject = build_subject(body)

    # Always fire macOS notification
    notify_macos(subject, body)

    # Try email — non-fatal if it fails
    send_email(body, config)


if __name__ == "__main__":
    main()
