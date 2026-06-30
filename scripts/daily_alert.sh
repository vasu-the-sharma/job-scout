#!/bin/bash
# Career Pilot — Daily Job Alert Runner
# Runs via macOS LaunchAgent at 8:00 AM IST.
# Calls the claude CLI, checks for new matches ≥ threshold, sends email if found.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$PROJECT_DIR/jobs/alert.log"
CONFIG_FILE="$PROJECT_DIR/config/alert_config.yaml"
TODAY=$(date +%Y-%m-%d)

cd "$PROJECT_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# ── Preflight ─────────────────────────────────────────────────────────────────
if ! command -v claude &>/dev/null; then
    log "❌ 'claude' CLI not found. Is Claude Code installed and in PATH?"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    log "❌ config/alert_config.yaml not found. Run: bash scripts/setup_alert.sh"
    exit 1
fi

# Read threshold from config (default 75)
THRESHOLD=$(python3 -c "
import yaml, sys
with open('$CONFIG_FILE') as f:
    c = yaml.safe_load(f)
print(c.get('score_threshold', 75))
" 2>/dev/null || echo "75")

log "🔍 Starting daily alert scan (threshold: ${THRESHOLD}+) …"

# ── Build prompt ──────────────────────────────────────────────────────────────
PROMPT=$(cat <<ENDPROMPT
You are Career Pilot's daily job alert agent. Today is ${TODAY}.

Working directory: ${PROJECT_DIR}
Run ALL python3 commands from that exact directory.

MISSION: find new job postings from the last 24 hours, score them against the
user's profile, add matches scoring ≥${THRESHOLD} to the pipeline, and output a
tight alert summary. This output is captured by a shell script and emailed if
matches are found — so format matters.

STEP 1 — Load existing pipeline (for deduplication)
Run: python3 scripts/tracker.py list
Capture every company+title pair. Do NOT re-add anything already tracked.

STEP 2 — Run exactly 5 web searches (hard cap — no more, no web_fetch)
Extract from each snippet: title, company, URL, platform, location, requirements.

Queries:
1. "senior software engineer" Python React TypeScript Bengaluru site:linkedin.com/jobs ${TODAY:0:4}
2. "SDE lead" OR "senior backend engineer" Java "Spring Boot" India site:naukri.com ${TODAY:0:4}
3. "senior engineer" LLM OR RAG OR "generative AI" OR "AI platform" Bengaluru India ${TODAY:0:4}
4. "tech lead" OR "senior software engineer" "full stack" Bengaluru site:instahyre.com ${TODAY:0:4}
5. "senior software engineer" OR "SDE lead" Rippling OR Razorpay OR Atlassian OR PhonePe OR Swiggy Bengaluru ${TODAY:0:4}

STEP 3 — Score each result via scorer.py
For each result run:
  python3 scripts/scorer.py --title "TITLE" --company "COMPANY" \
    --requirements "SNIPPET_TEXT" --location "LOCATION" --json-output
Parse the JSON. Keep only "total" >= ${THRESHOLD}.

STEP 4 — Deduplicate
Skip any result whose company+title already appears in the pipeline from Step 1.

STEP 5 — Add new matches to pipeline
For each new result scoring ≥${THRESHOLD}:
  python3 scripts/tracker.py add --title "TITLE" --company "COMPANY" \
    --url "URL" --platform "PLATFORM" --location "LOCATION" \
    --score SCORE --posted "${TODAY}" --notes "One-line from snippet"

STEP 6 — Output (this is captured and emailed — format exactly as shown)

If new matches found:

🚨 JOB ALERT — N new match(es) · ${TODAY}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE/100 EMOJI  COMPANY — TITLE
📍 LOCATION · PLATFORM
🔗 URL
💡 One sentence why this fits the profile.

[repeat for each match]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Open Career Pilot and run /evaluate <url> or /tailor <job_id> to act on these.

If no new matches:

✅ Daily scan complete · ${TODAY} · No new matches above ${THRESHOLD}. Pipeline unchanged.

RULES:
- Max 5 web_search calls. Zero web_fetch calls during this run.
- Score from snippets only. Do not spawn sub-agents.
- Do not re-score or re-add jobs already in the pipeline.
ENDPROMPT
)

# ── Run claude ────────────────────────────────────────────────────────────────
log "Running claude -p …"
OUTPUT=$(claude -p "$PROMPT" 2>&1) || {
    log "❌ claude -p failed. Exit code: $?"
    exit 1
}

log "Claude run complete."
echo "$OUTPUT" >> "$LOG_FILE"

# ── Check for matches ─────────────────────────────────────────────────────────
if echo "$OUTPUT" | grep -q "🚨 JOB ALERT"; then
    MATCH_LINE=$(echo "$OUTPUT" | grep "🚨 JOB ALERT" | head -1)
    log "✅ New matches found: $MATCH_LINE"
    log "Sending alert email …"
    python3 scripts/send_alert_email.py "$OUTPUT" && log "📧 Email sent." || log "❌ Email failed."
else
    log "✅ No new matches above ${THRESHOLD} today."
fi
