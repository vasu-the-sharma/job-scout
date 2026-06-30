#!/bin/bash
# Career Pilot — Remove Daily Alert LaunchAgent
# Usage: bash scripts/uninstall_alert.sh

PLIST_DST="$HOME/Library/LaunchAgents/com.careerpilot.daily.plist"

if [ -f "$PLIST_DST" ]; then
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    rm "$PLIST_DST"
    echo "✅ LaunchAgent removed. Daily alert is off."
else
    echo "ℹ️  LaunchAgent not installed — nothing to remove."
fi
