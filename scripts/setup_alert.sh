#!/bin/bash
# Career Pilot — One-time Daily Alert Setup
# Installs the macOS LaunchAgent that fires daily_alert.sh at 8:00 AM local time.
#
# Usage: bash scripts/setup_alert.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_TEMPLATE="$PROJECT_DIR/launchagents/com.careerpilot.daily.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.careerpilot.daily.plist"
CONFIG_EXAMPLE="$PROJECT_DIR/config/alert_config.example.yaml"
CONFIG_FILE="$PROJECT_DIR/config/alert_config.yaml"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   Career Pilot — Daily Alert Setup               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Check prerequisites ───────────────────────────────────────────────────────
if ! command -v claude &>/dev/null; then
    echo "❌  'claude' CLI not found."
    echo "    Install Claude Code: https://claude.ai/code"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "❌  python3 not found."
    exit 1
fi

CLAUDE_PATH=$(command -v claude)
echo "✅  claude CLI found: $CLAUDE_PATH"

# ── Config file ───────────────────────────────────────────────────────────────
if [ ! -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
    echo ""
    echo "📋  Config file created: config/alert_config.yaml"
    echo ""
    echo "    Before the alert will work, open that file and set:"
    echo "    1. email: your Gmail address"
    echo "    2. app_password: your Gmail App Password"
    echo "       → https://myaccount.google.com/apppasswords"
    echo "       → Click 'Add app password', name it 'Career Pilot'"
    echo ""
else
    echo "✅  Config file already exists: config/alert_config.yaml"
fi

# ── Install LaunchAgent ───────────────────────────────────────────────────────
mkdir -p "$HOME/Library/LaunchAgents"

# Stamp the real paths into the plist
sed \
    -e "s|CAREER_PILOT_DIR|$PROJECT_DIR|g" \
    -e "s|USER_HOME|$HOME|g" \
    "$PLIST_TEMPLATE" > "$PLIST_DST"

# Unload first if already loaded (silent)
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "✅  LaunchAgent installed and loaded."
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Daily alert set for 8:00 AM (local time)        ║"
echo "║  Alerts emailed when new matches ≥ 75 found.     ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  To test immediately:                            ║"
echo "║    bash scripts/daily_alert.sh                   ║"
echo "║                                                  ║"
echo "║  To send a test email:                           ║"
echo "║    echo 'test' | python3 scripts/send_alert_email.py"
echo "║                                                  ║"
echo "║  To uninstall:                                   ║"
echo "║    bash scripts/uninstall_alert.sh               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
