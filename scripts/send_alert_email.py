#!/usr/bin/env python3
"""Career Pilot — Alert Notifier

Sends job alerts via all configured channels:
  1. macOS system notification  (always fires, zero config)
  2. iPhone push via ntfy.sh    (free, needs ntfy app + topic in config)
  3. Telegram bot               (free, needs telegram_token + telegram_chat_id)
  4. Gmail SMTP                 (needs App Password in config)

Usage:
    python3 scripts/send_alert_email.py "ALERT BODY"
    echo "body" | python3 scripts/send_alert_email.py
"""

import sys
import json
import subprocess
import smtplib
import urllib.request
import urllib.parse
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


# ── Channel 1: macOS notification ─────────────────────────────────────────────

def notify_macos(subject: str, body: str):
    subtitle = ""
    for line in body.splitlines():
        if "/100" in line and ("🟢" in line or "🟡" in line):
            subtitle = line.strip()
            break
    script = (
        f'display notification "{subtitle or "New job matches found."}" '
        f'with title "Career Pilot 🚀" '
        f'subtitle "{subject}"'
    )
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        print("✅ macOS notification sent.")
        return True
    except Exception as e:
        print(f"⚠️  macOS notification failed: {e}")
        return False


# ── Channel 2: iPhone push via ntfy.sh ────────────────────────────────────────

def notify_ntfy(subject: str, body: str, config: dict):
    """
    Free iPhone push notifications via ntfy.sh.
    Setup: install 'ntfy' app on iPhone → subscribe to your topic.
    Config keys: ntfy_topic (required), ntfy_server (optional, default ntfy.sh)
    """
    topic = config.get("ntfy_topic", "")
    if not topic:
        return False

    server = config.get("ntfy_server", "https://ntfy.sh")
    url = f"{server.rstrip('/')}/{topic}"

    # Extract top match line for a punchy notification body
    preview = ""
    for line in body.splitlines():
        if "/100" in line and ("🟢" in line or "🟡" in line):
            preview = line.strip()
            break

    try:
        # Strip non-latin chars from headers; body goes as UTF-8 in the payload
        safe_subject = subject.encode("ascii", "ignore").decode()
        req = urllib.request.Request(
            url,
            data=(preview or "New job matches found. Open Career Pilot.").encode("utf-8"),
            headers={
                "Title": safe_subject,
                "Priority": "high",
                "Tags": "briefcase,rocket",
                "Content-Type": "text/plain; charset=utf-8",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print(f"✅ iPhone push sent (ntfy.sh/{topic}).")
                return True
    except Exception as e:
        print(f"⚠️  ntfy push failed: {e}")
    return False


# ── Channel 3: Telegram bot ───────────────────────────────────────────────────

def notify_telegram(body: str, config: dict):
    """
    Free Telegram notifications via Bot API.
    Setup: create a bot via @BotFather, send /start to it, then store
    telegram_token and telegram_chat_id in alert_config.yaml.
    """
    token = str(config.get("telegram_token", "")).strip()
    chat_id = str(config.get("telegram_chat_id", "")).strip()

    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": body,
        "parse_mode": "",          # plain text — emojis render natively
        "disable_web_page_preview": True,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print("✅ Telegram notification sent.")
                return True
            else:
                print(f"⚠️  Telegram error: {result}")
    except Exception as e:
        print(f"⚠️  Telegram failed: {e}")
    return False


# ── Channel 4: Gmail SMTP ──────────────────────────────────────────────────────

def send_email(body: str, config: dict):
    sender = config.get("email", "")
    password = str(config.get("app_password", "")).replace(" ", "")
    recipient = config.get("recipient", sender)
    smtp_host = config.get("smtp_host", "smtp.gmail.com")
    smtp_port = int(config.get("smtp_port", 587))

    if not sender or not password or len(password) < 16:
        print("⚠️  Email skipped — app_password not set in alert_config.yaml.")
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
        print(f"✅ Email sent to {recipient}.")
        return True
    except smtplib.SMTPAuthenticationError:
        print("⚠️  Email auth failed — check app_password in alert_config.yaml.")
        return False
    except Exception as e:
        print(f"⚠️  Email failed: {e}")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────

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

    notify_macos(subject, body)
    notify_ntfy(subject, body, config)
    notify_telegram(body, config)
    send_email(body, config)


if __name__ == "__main__":
    main()
