# Career Pilot

**AI-powered job search command center, built entirely inside Claude Code.**

Paste a job URL → get a fit score → generate a tailored resume → track your pipeline.
Everything runs in your terminal, on your laptop or phone, with all data staying local.

---

## What is this?

Career Pilot turns Claude Code into a personal job search assistant. You define your profile and target roles once. After that, a set of slash commands handles the full workflow: finding jobs, scoring them against your background, tailoring your resume, and tracking where every application stands.

The intelligence lives in `CLAUDE.md` — a skill definition file that Claude Code reads as instructions. The Python scripts handle the mechanical work: database operations, PDF generation, search URL construction, and the terminal dashboard. No external services, no subscriptions, no data leaves your machine except for web searches.

---

## Features

- **10-dimension fit scoring** — each job is scored on tech stack, experience level, domain fit, role scope, growth potential, location, company stage, compensation, culture signals, and application effort
- **ATS-optimized PDF resumes** — generated from markdown, no tables or columns, keyword-matched to the job description
- **Local SQLite pipeline** — full CRUD, status tracking, score history, export to CSV/JSON
- **Clickable HTML job list** — open in any browser, filter by score/status, one-click "Copy /tailor" to clipboard
- **Token-budgeted search** — snippet-first discovery, at most 5 web searches per `/search`, full-page fetch only on explicit `/evaluate` or `/tailor`
- **Indian job market aware** — Naukri, Instahyre, notice period conventions, CTC vs in-hand salary
- **Works on mobile** — Claude Code runs on iOS/Android; check your pipeline from anywhere

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/<your-username>/career-pilot.git
cd career-pilot

# 2. Install Python dependencies
pip install reportlab pyyaml --break-system-packages

# 3. Copy and fill in your profile
cp config/profile.example.yaml config/profile.yaml
# Edit config/profile.yaml with your details

# 4. Add your master resume
# Edit resume/base_resume.md with your real resume in markdown format

# 5. Initialize the database
python3 scripts/tracker.py init

# 6. Open with Claude Code
claude
```

Then type any command:

```
/search              # Find jobs across LinkedIn, Naukri, Instahyre
/evaluate <url>      # Score a job posting (0–100)
/tailor <job_id>     # Generate a tailored resume PDF
/apply <job_id>      # End-to-end: evaluate → tailor → open posting
/track               # View your pipeline dashboard
/joblist             # Generate a clickable HTML job list
/interview <job_id>  # STAR stories, likely questions, prep guide
/negotiate <job_id>  # Salary data, counter-offer template
/scan [company]      # Scan company career pages for new openings
/weekly              # Weekly pipeline report
/alert setup         # Set up the daily background alert (one-time)
/alert status        # Check if the alert is running and see last log
/alert test          # Run today's search right now
/setup               # Re-run onboarding wizard
```

---

## How It Works

The system is two layers:

**Layer 1 — Claude Code (the AI engine)**
`CLAUDE.md` defines 10 skill modes. When you type `/evaluate https://...`, Claude Code reads the skill definition and follows a precise workflow: fetch → extract → score → save → display. The skill file controls token budgeting, what to emphasize, and what to never do (fabricate experience, spray-and-pray).

**Layer 2 — Python scripts (the mechanical layer)**
These run locally with near-zero model cost:

| Script | Does |
|---|---|
| `tracker.py` | SQLite CRUD for the jobs pipeline |
| `scorer.py` | Programmatic fit scoring (tech stack, experience, location, compensation) |
| `resume_gen.py` | Markdown → ATS-optimized PDF via reportlab |
| `joblist.py` | Generates a self-contained HTML job list from the DB |
| `dashboard.py` | Terminal dashboard (full / compact / kanban views) |
| `search_urls.py` | Builds search URLs for LinkedIn, Naukri, Instahyre, Indeed, Wellfound |

---

## File Structure

```
career-pilot/
├── CLAUDE.md                    # Skill definitions — the brain of the system
├── README.md
├── CONTRIBUTING.md
├── LICENSE
│
├── config/
│   ├── profile.example.yaml     # Template — copy to profile.yaml and fill in
│   ├── profile.yaml             # Your profile (gitignored — stays local)
│   └── targets.yaml             # Target companies and platforms
│
├── resume/
│   └── base_resume.md           # Master resume in markdown (source of truth)
│
├── scripts/
│   ├── tracker.py               # SQLite job pipeline CRUD
│   ├── scorer.py                # 10-dimension fit scoring engine
│   ├── resume_gen.py            # Markdown → PDF generator (reportlab)
│   ├── search_urls.py           # Platform search URL builder
│   ├── dashboard.py             # Rich terminal dashboard
│   └── joblist.py               # Clickable HTML/Markdown job list generator
│
├── tailored/                    # Generated per-job resumes (gitignored)
│   └── *.md / *.pdf
│
└── jobs/                        # Runtime data (gitignored)
    ├── pipeline.db              # SQLite database
    ├── job_list.html            # Generated job list
    └── *.json                   # Cached job descriptions
```

---

## Scoring System

Every job is scored across 10 dimensions (0–10 each), producing a 0–100 composite:

| Dimension | Weight | What it measures |
|---|---|---|
| Tech Stack Match | 15% | Overlap between required tech and your skills |
| Experience Level | 15% | Years and seniority alignment |
| Domain Fit | 10% | Industry / domain relevance |
| Role Scope | 10% | IC vs lead vs manager alignment |
| Growth Potential | 10% | Learning opportunities, trajectory |
| Location/Remote | 10% | Location match or remote flexibility |
| Company Stage | 10% | Startup vs enterprise preference |
| Compensation | 10% | Salary range vs your expectations |
| Culture Signals | 5% | Work-life, values alignment from JD language |
| Application Effort | 5% | Ease of applying, referral possibility |

**Score bands:**
- 🟢 80–100 — Strong match. Apply immediately.
- 🟡 60–79 — Good match. Tailor and apply.
- 🟠 40–59 — Stretch. Review gaps before deciding.
- 🔴 0–39 — Weak match. Skip unless strategic.

The first four dimensions (tech stack, experience, location, compensation) are computed deterministically by `scorer.py` from the job data and your profile. The remaining six are assessed by Claude Code when it reads the full job description during `/evaluate`.

---

## Resume Generation

`resume_gen.py` converts any markdown resume to a clean PDF using reportlab:

- No tables, no columns, no images — ATS parsers handle these poorly
- Standard section headings (Experience, Skills, Education)
- Keywords from the job description are emphasized in the tailored version
- XYZ bullet format: "Accomplished [X] as measured by [Y], by doing [Z]"
- 1-page target (2 pages max for 10+ years)

```bash
# Generate PDF from your base resume
python3 scripts/resume_gen.py resume/base_resume.md

# Generate PDF from a tailored resume
python3 scripts/resume_gen.py tailored/company_role.md

# Preview the parsed structure without generating PDF
python3 scripts/resume_gen.py resume/base_resume.md --preview
```

---

## Pipeline & Tracker

All job data lives in `jobs/pipeline.db` (SQLite, auto-created on first use).

```bash
python3 scripts/tracker.py init                              # Initialize DB
python3 scripts/tracker.py add --title "..." --company "..."  # Add a job
python3 scripts/tracker.py list                              # List all jobs
python3 scripts/tracker.py list --min-score 75               # Filter by score
python3 scripts/tracker.py get <job_id>                      # Job details + score breakdown
python3 scripts/tracker.py update <job_id> --status applied  # Update status
python3 scripts/tracker.py stats                             # Pipeline statistics
python3 scripts/tracker.py export --format csv               # Export to CSV
```

**Status flow:** `discovered → evaluated → tailored → applied → interviewing → offered → accepted / rejected`

---

## Token Budget

A key design constraint: `/search` must stay under ~150K tokens and ~15 tool calls. The rules enforced in `CLAUDE.md`:

1. **Snippet-first** — during `/search`, score from search result snippets. Never fetch full job pages for the whole batch.
2. **Cap at 5 searches** — at most 5 `web_search` calls per `/search` run.
3. **Score locally** — `scorer.py` runs deterministically with near-zero model cost.
4. **No sub-agents per job** — one pass, inline, no spawning.
5. **Fetch on commit** — full `web_fetch` happens only when you explicitly run `/evaluate <url>` or `/tailor <id>`.
6. **Cache JDs** — fetched descriptions are saved to `jobs/<id>.json`; re-runs and `/tailor` read the cache.

---

## Setup Your Profile

Copy `config/profile.example.yaml` to `config/profile.yaml` and fill in:

```yaml
name: "Your Name"
email: "you@email.com"
location: "Your City, Country"

current_role:
  title: "Your Current Title"
  company: "Your Company"
  notice_period: "30 days"

target_roles:
  - "Senior Software Engineer"
  - "Tech Lead"

years_of_experience: 4
skills:
  primary: ["Python", "React", "TypeScript"]
  secondary: ["Docker", "Kubernetes", "PostgreSQL"]

preferences:
  remote_ok: true
  preferred_cities: ["Bengaluru", "Remote"]
  min_ctc_lakhs: 25
  expected_ctc_lakhs: 35
```

Edit `resume/base_resume.md` with your actual resume. This is the source of truth — `/tailor` reorders and re-emphasizes from it but never fabricates.

---

## Daily Job Alerts

Career Pilot can run a daily background search at 8:00 AM and email you when new strong matches are found — no Claude Code session required.

### One-time setup (5 minutes)

**1. Generate a Gmail App Password**

Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), click **Add app password**, name it `Career Pilot`, and copy the 16-character code.

**2. Configure the alert**

```bash
cp config/alert_config.example.yaml config/alert_config.yaml
# Edit config/alert_config.yaml — set your email and app_password
```

**3. Install the LaunchAgent**

```bash
bash scripts/setup_alert.sh
```

That's it. A macOS LaunchAgent fires `scripts/daily_alert.sh` at 8 AM, runs a five-query job search via the `claude` CLI, scores every result, adds new matches to `pipeline.db`, and emails you a digest if anything scores above your threshold.

### Manage the alert from Claude Code

```
/alert status     # Check if running, see last log output
/alert test       # Run the search right now (don't wait for 8 AM)
/alert pause      # Temporarily disable
/alert resume     # Re-enable
/alert threshold 80   # Only alert on 80+ scores
/alert uninstall  # Remove the LaunchAgent entirely
```

### What the email looks like

```
Subject: [Career Pilot] 🚨 JOB ALERT — 2 new match(es) · 2026-07-01

🚨 JOB ALERT — 2 new match(es) · 2026-07-01
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
85/100 🟢  Razorpay — Senior Backend Engineer
📍 Bengaluru · LinkedIn
🔗 https://linkedin.com/jobs/view/...
💡 Strong Python + Kafka match, growth-stage fintech, 4-6yr band fits perfectly.

78/100 🟡  Atlassian — Senior Software Engineer
📍 Bengaluru · Careers page
🔗 https://atlassian.com/company/careers/...
💡 Developer tools domain, TypeScript + React stack, Bengaluru office.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Open Career Pilot and run /evaluate <url> or /tailor <job_id> to act on these.
```

Tap the link → open Claude Code → `/tailor <job_id>`. Two touches to a tailored resume.

---

## Indian Job Market Features

- **Naukri.com** search integration with experience-range filters
- **Instahyre** support (startup-focused hiring platform)
- Notice period awareness in scoring and application notes (30/60/90 day conventions)
- CTC vs in-hand salary understanding in compensation scoring
- Indian startup ecosystem coverage (YC India, growth-stage companies)
- AmbitionBox and Glassdoor India salary data in `/negotiate`

---

## Requirements

- **Claude Code** — [install here](https://claude.ai/code)
- **Python 3.8+**
- **reportlab** — PDF generation: `pip install reportlab`
- **pyyaml** — YAML config parsing: `pip install pyyaml`

Both pip packages have fallback behavior if missing, but installing them is recommended for full functionality.

---

## Tips

1. **Update your base resume first.** Tailoring is only as good as the source material.
2. **Run `/search` to populate, `/joblist` to browse.** The HTML list is the fastest way to scan your pipeline.
3. **Score < 40 → skip.** The system will warn you. Spray-and-pray hurts response rates.
4. **Review tailored resumes before submitting.** Claude never fabricates, but you know your story best.
5. **Run `/weekly` every Friday** to catch stale applications that need a follow-up nudge.
6. **Works on phone.** Claude Code is available on mobile — check and update your pipeline from anywhere.

---

## License

MIT — use it, adapt it, make it yours. If you build something interesting on top of this, I'd love to know.
