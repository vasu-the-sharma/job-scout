#!/bin/bash
# Career Pilot — Daily Job Alert Runner
# Fires at 8:00 AM via macOS LaunchAgent.
# Searches, scores, tailors resumes, notifies all 4 channels.

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

THRESHOLD=$(python3 -c "
import yaml
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

MISSION: find new job postings from the last 24 hours, score them, add matches
≥${THRESHOLD} to the pipeline, generate a tailored resume for each match, then
output a structured alert. This output is captured by a shell script.

STEP 1 — Load existing pipeline (deduplication)
Run: python3 scripts/tracker.py list
Capture every company+title pair. Do NOT re-add anything already tracked.

STEP 2 — Run exactly 5 web searches (hard cap — snippet only, no web_fetch yet)
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
Keep only results where "total" >= ${THRESHOLD}.

STEP 4 — Deduplicate
Skip any result whose company+title already appears in the pipeline from Step 1.

STEP 5 — Add new matches to pipeline
For each genuinely new result scoring ≥${THRESHOLD}:
  python3 scripts/tracker.py add --title "TITLE" --company "COMPANY" \
    --url "URL" --platform "PLATFORM" --location "LOCATION" \
    --score SCORE --posted "${TODAY}" --notes "One-line from snippet"
Capture the job_id printed by tracker.py.

STEP 6 — Fetch full JD and generate tailored resume for each new match
For each new match (do this one at a time — max 1 web_fetch per job):
  a. web_fetch the job URL to extract the full job description
  b. Read resume/base_resume.md (the master resume)
  c. Generate a tailored resume:
     - Write a 2-line summary targeting this specific role
     - Reorder experience bullets so the most relevant ones come first
     - Adjust language and keywords to mirror the JD
     - Never fabricate — only reorder and re-emphasize what is true
  d. Create folder: applications/COMPANY/JOBID_${TODAY}/
  e. Save tailored resume as: applications/COMPANY/JOBID_${TODAY}/updated_resume.md
  f. Generate PDF: python3 scripts/resume_gen.py applications/COMPANY/JOBID_${TODAY}/updated_resume.md --output applications/COMPANY/JOBID_${TODAY}/updated_resume.pdf
  g. Update tracker: python3 scripts/tracker.py update JOB_ID --status tailored --resume-path applications/COMPANY/JOBID_${TODAY}/updated_resume.pdf

STEP 7 — Output (format exactly as shown — shell script parses this)

If new matches were found:

🚨 JOB ALERT — N new match(es) · ${TODAY}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE/100 EMOJI  COMPANY — TITLE
📍 LOCATION · PLATFORM
🔗 URL
💡 One sentence why this fits the profile.
📄 Resume tailored and attached.

[repeat for each match]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Open Career Pilot and run /apply <job_id> to submit.

Then on the very last line, output ONLY this (no extra text, just this line):
RESUME_PATHS:path/to/resume1.pdf|path/to/resume2.pdf

If no new matches above ${THRESHOLD}:
Output: ✅ Daily scan complete · ${TODAY} · No new matches above ${THRESHOLD}. Pipeline unchanged.
(No RESUME_PATHS line needed.)

RULES:
- Max 5 web_search calls. Max 1 web_fetch per confirmed match (Step 6 only).
- Score from snippets first; fetch full JD only for confirmed ≥${THRESHOLD} matches.
- Do not spawn sub-agents. Do not re-add jobs already in the pipeline.
- The RESUME_PATHS line must be the absolute last line of output, nothing after it.
ENDPROMPT
)

# ── Run claude ────────────────────────────────────────────────────────────────
log "Running claude -p …"
OUTPUT=$(claude -p "$PROMPT" 2>&1) || {
    log "❌ claude -p failed."
    exit 1
}
log "Claude run complete."
echo "$OUTPUT" >> "$LOG_FILE"

# ── Parse output ──────────────────────────────────────────────────────────────
# Extract RESUME_PATHS line (last line if present)
RESUME_PATHS_LINE=$(echo "$OUTPUT" | grep "^RESUME_PATHS:" | tail -1 || true)
RESUME_PATHS=$(echo "$RESUME_PATHS_LINE" | sed 's/RESUME_PATHS://' | tr '|' ' ')

# Strip RESUME_PATHS line from the notification body
NOTIFICATION_BODY=$(echo "$OUTPUT" | grep -v "^RESUME_PATHS:")

# ── Notify ────────────────────────────────────────────────────────────────────
if echo "$NOTIFICATION_BODY" | grep -q "🚨 JOB ALERT"; then
    MATCH_LINE=$(echo "$NOTIFICATION_BODY" | grep "🚨 JOB ALERT" | head -1)
    log "✅ New matches found: $MATCH_LINE"
    log "Resume paths: ${RESUME_PATHS:-none}"
    log "Sending notifications …"

    # Build resume args — pass each existing PDF path
    RESUME_ARGS=""
    for PDF in $RESUME_PATHS; do
        PDF_FULL="$PROJECT_DIR/$PDF"
        if [ -f "$PDF_FULL" ]; then
            RESUME_ARGS="$RESUME_ARGS $PDF_FULL"
        elif [ -f "$PDF" ]; then
            RESUME_ARGS="$RESUME_ARGS $PDF"
        fi
    done

    python3 scripts/send_alert_email.py "$NOTIFICATION_BODY" $RESUME_ARGS \
        && log "📣 All notifications sent." \
        || log "❌ Notification failed."
else
    log "✅ No new matches above ${THRESHOLD} today."
fi
