#!/usr/bin/env python3
"""Career Pilot — Alert Notifier

Channels:
  1. macOS notification  — always fires, text only
  2. ntfy.sh (iPhone)   — text only
  3. Telegram           — text message + PDF resume file(s)
  4. Gmail SMTP         — text + PDF resume attachment(s)

Usage:
    python3 scripts/send_alert_email.py "BODY" [/path/to/resume1.pdf ...]
    echo "body" | python3 scripts/send_alert_email.py [/path/to/resume.pdf ...]
"""

import sys
import json
import os
import subprocess
import smtplib
import urllib.request
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
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


def first_match_line(body: str) -> str:
    for line in body.splitlines():
        if "/100" in line and ("🟢" in line or "🟡" in line):
            return line.strip()
    return "New job matches found. Open Career Pilot."


# ── Channel 1: macOS notification (text only) ─────────────────────────────────

def notify_macos(subject: str, body: str, pdf_paths: list):
    note = " · Resume in email & Telegram." if pdf_paths else ""
    subtitle = first_match_line(body) + note
    script = (
        f'display notification "{subtitle}" '
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


# ── Channel 2: ntfy.sh iPhone push (text only) ────────────────────────────────

def notify_ntfy(subject: str, body: str, config: dict, pdf_paths: list):
    topic = config.get("ntfy_topic", "")
    if not topic:
        return False

    server = config.get("ntfy_server", "https://ntfy.sh")
    url = f"{server.rstrip('/')}/{topic}"
    note = " Resume attached in email & Telegram." if pdf_paths else ""
    preview = first_match_line(body) + note
    safe_subject = subject.encode("ascii", "ignore").decode()

    try:
        req = urllib.request.Request(
            url,
            data=preview.encode("utf-8"),
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


# ── Channel 3: Telegram (text + PDF file upload) ──────────────────────────────

def notify_telegram(body: str, config: dict, pdf_paths: list):
    token = str(config.get("telegram_token", "")).strip()
    chat_id = str(config.get("telegram_chat_id", "")).strip()
    if not token or not chat_id:
        return False

    # Send text message
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": body,
        "disable_web_page_preview": True,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print("✅ Telegram message sent.")
            else:
                print(f"⚠️  Telegram message error: {result}")
                return False
    except Exception as e:
        print(f"⚠️  Telegram message failed: {e}")
        return False

    # Send each PDF as a document via curl (multipart — simpler than urllib)
    for pdf in pdf_paths:
        if not os.path.isfile(pdf):
            print(f"⚠️  Resume PDF not found, skipping: {pdf}")
            continue
        company = Path(pdf).parent.parent.name
        caption = f"📄 Tailored resume — {company}"
        result = subprocess.run([
            "curl", "-s",
            "-F", f"chat_id={chat_id}",
            "-F", f"document=@{pdf}",
            "-F", f"caption={caption}",
            f"https://api.telegram.org/bot{token}/sendDocument",
        ], capture_output=True, text=True)
        try:
            resp_json = json.loads(result.stdout)
            if resp_json.get("ok"):
                print(f"✅ Telegram PDF sent: {Path(pdf).name}")
            else:
                print(f"⚠️  Telegram PDF error: {resp_json.get('description','')}")
        except Exception:
            print(f"⚠️  Telegram PDF upload failed for {Path(pdf).name}")

    return True


# ── Channel 4: Gmail SMTP (text + PDF attachment) ─────────────────────────────

def send_email(body: str, config: dict, pdf_paths: list):
    sender   = config.get("email", "")
    password = str(config.get("app_password", "")).replace(" ", "")
    recipient = config.get("recipient", sender)
    smtp_host = config.get("smtp_host", "smtp.gmail.com")
    smtp_port = int(config.get("smtp_port", 587))

    if not sender or not password or len(password) < 16:
        print("⚠️  Email skipped — app_password not set in alert_config.yaml.")
        return False

    subject = build_subject(body)

    if pdf_paths:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body, "plain", "utf-8"))
        for pdf in pdf_paths:
            if not os.path.isfile(pdf):
                print(f"⚠️  Resume PDF not found, skipping: {pdf}")
                continue
            with open(pdf, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{Path(pdf).name}"',
            )
            msg.attach(part)
            print(f"   📎 Attaching: {Path(pdf).name}")
    else:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body, "plain", "utf-8"))

    msg["Subject"] = subject
    msg["From"]    = f"Career Pilot <{sender}>"
    msg["To"]      = recipient

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        print(f"✅ Email sent to {recipient}" +
              (f" with {len(pdf_paths)} resume(s) attached." if pdf_paths else "."))
        return True
    except smtplib.SMTPAuthenticationError:
        print("⚠️  Email auth failed — check app_password in alert_config.yaml.")
        return False
    except Exception as e:
        print(f"⚠️  Email failed: {e}")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # First positional arg is the body; remaining args are PDF paths
    args = sys.argv[1:]

    if args:
        body = args[0]
        pdf_paths = [p for p in args[1:] if p.endswith(".pdf")]
    elif not sys.stdin.isatty():
        body = sys.stdin.read().strip()
        pdf_paths = []
    else:
        print("Usage: python3 send_alert_email.py 'BODY' [resume.pdf ...]",
              file=sys.stderr)
        sys.exit(1)

    # Filter to existing files only
    pdf_paths = [p for p in pdf_paths if os.path.isfile(p)]
    if pdf_paths:
        print(f"📄 {len(pdf_paths)} resume(s) will be attached to email & Telegram.")

    config  = load_config()
    subject = build_subject(body)

    notify_macos(subject, body, pdf_paths)
    notify_ntfy(subject, body, config, pdf_paths)
    notify_telegram(body, config, pdf_paths)
    send_email(body, config, pdf_paths)


if __name__ == "__main__":
    main()
