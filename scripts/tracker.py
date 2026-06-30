#!/usr/bin/env python3
"""Career Pilot — Job Pipeline Tracker (SQLite)

Usage:
    python tracker.py init                          Initialize database
    python tracker.py add --title "..." --company "..." --url "..." [--platform ...] [--score ...]
    python tracker.py update <job_id> --status <status> [--notes "..."]
    python tracker.py list [--status <status>] [--min-score <n>]
    python tracker.py get <job_id>
    python tracker.py remove <job_id>
    python tracker.py stats
    python tracker.py export [--format csv|json]
"""

import sqlite3
import json
import os
import sys
import argparse
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "jobs" / "pipeline.db"

VALID_STATUSES = [
    "discovered", "evaluated", "tailored", "applied",
    "interviewing", "offered", "accepted", "rejected", "withdrawn"
]

STATUS_ICONS = {
    "discovered": "🔍",
    "evaluated": "📊",
    "tailored": "📝",
    "applied": "📨",
    "interviewing": "🎤",
    "offered": "🎉",
    "accepted": "✅",
    "rejected": "❌",
    "withdrawn": "🚫",
}


def get_db():
    """Get database connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT DEFAULT '',
            url TEXT DEFAULT '',
            platform TEXT DEFAULT '',
            posted_date TEXT DEFAULT '',
            description TEXT DEFAULT '',
            requirements TEXT DEFAULT '',
            salary_range TEXT DEFAULT '',
            fit_score REAL DEFAULT 0,
            score_breakdown TEXT DEFAULT '{}',
            status TEXT DEFAULT 'discovered',
            resume_path TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            applied_date TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(fit_score DESC);
        CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
        CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
    """)
    conn.commit()
    conn.close()
    print("✅ Database initialized at", DB_PATH)


def generate_id(company: str, title: str) -> str:
    """Generate a short, readable job ID."""
    slug = f"{company}-{title}".lower()
    slug = "".join(c if c.isalnum() else "-" for c in slug)[:40]
    short_hash = hashlib.md5(f"{company}{title}{datetime.now().isoformat()}".encode()).hexdigest()[:6]
    return f"{slug}-{short_hash}"


def add_job(title, company, url="", platform="", location="", score=0,
            score_breakdown=None, description="", requirements="",
            salary_range="", posted_date="", notes=""):
    """Add a new job to the pipeline."""
    conn = get_db()
    job_id = generate_id(company, title)

    # Check for duplicates by URL
    if url:
        existing = conn.execute("SELECT id FROM jobs WHERE url = ?", (url,)).fetchone()
        if existing:
            print(f"⚠️  Job already exists: {existing['id']}")
            conn.close()
            return existing["id"]

    conn.execute("""
        INSERT INTO jobs (id, title, company, url, platform, location,
                         fit_score, score_breakdown, description, requirements,
                         salary_range, posted_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id, title, company, url, platform, location,
        score, json.dumps(score_breakdown or {}),
        description, requirements, salary_range, posted_date, notes
    ))
    conn.commit()
    conn.close()
    print(f"✅ Added: [{job_id}] {company} — {title} (Score: {score})")
    return job_id


def update_job(job_id, **kwargs):
    """Update job fields."""
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        # Try partial match
        jobs = conn.execute("SELECT * FROM jobs WHERE id LIKE ?", (f"%{job_id}%",)).fetchall()
        if len(jobs) == 1:
            job_id = jobs[0]["id"]
        elif len(jobs) > 1:
            print(f"⚠️  Multiple matches for '{job_id}':")
            for j in jobs:
                print(f"   {j['id']} — {j['company']} {j['title']}")
            conn.close()
            return
        else:
            print(f"❌ Job not found: {job_id}")
            conn.close()
            return

    valid_fields = [
        "title", "company", "location", "url", "platform", "posted_date",
        "description", "requirements", "salary_range", "fit_score",
        "score_breakdown", "status", "resume_path", "notes", "applied_date"
    ]

    updates = []
    values = []
    for key, value in kwargs.items():
        if key in valid_fields and value is not None:
            if key == "status" and value not in VALID_STATUSES:
                print(f"❌ Invalid status: {value}. Valid: {', '.join(VALID_STATUSES)}")
                conn.close()
                return
            if key == "status" and value == "applied" and not kwargs.get("applied_date"):
                updates.append("applied_date = ?")
                values.append(datetime.now().strftime("%Y-%m-%d"))
            updates.append(f"{key} = ?")
            values.append(value)

    if not updates:
        print("⚠️  No valid fields to update")
        conn.close()
        return

    updates.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(job_id)

    conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    print(f"✅ Updated: {job_id}")


def list_jobs(status=None, min_score=None, limit=50):
    """List jobs with optional filters."""
    conn = get_db()
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if min_score is not None:
        query += " AND fit_score >= ?"
        params.append(min_score)

    query += " ORDER BY fit_score DESC, created_at DESC LIMIT ?"
    params.append(limit)

    jobs = conn.execute(query, params).fetchall()
    conn.close()

    if not jobs:
        print("📭 No jobs found matching criteria")
        return []

    # Print table
    print(f"\n{'Score':>5} │ {'Status':<13} │ {'Company':<18} │ {'Role':<30} │ {'Platform':<10}")
    print("──────┼───────────────┼────────────────────┼────────────────────────────────┼───────────")

    for job in jobs:
        icon = STATUS_ICONS.get(job["status"], "")
        score_str = f"{job['fit_score']:>3.0f}" if job["fit_score"] else "  -"
        print(f" {score_str}  │ {icon} {job['status']:<11} │ {job['company']:<18.18} │ {job['title']:<30.30} │ {job['platform']:<10}")

    print(f"\n📊 Total: {len(jobs)} jobs")
    return [dict(j) for j in jobs]


def get_job(job_id):
    """Get full details for a single job."""
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id = ? OR id LIKE ?",
                       (job_id, f"%{job_id}%")).fetchone()
    conn.close()

    if not job:
        print(f"❌ Job not found: {job_id}")
        return None

    icon = STATUS_ICONS.get(job["status"], "")
    score = job["fit_score"] or 0
    color = "🟢" if score >= 80 else "🟡" if score >= 60 else "🟠" if score >= 40 else "🔴"

    print(f"""
┌─────────────────────────────────────────────────────┐
│  {job['company']} — {job['title']:<38.38} │
│  {color} Score: {score:.0f}/100   {icon} Status: {job['status']:<20.20} │
├─────────────────────────────────────────────────────┤
│  📍 {job['location'] or 'Not specified':<48.48} │
│  🔗 {job['platform'] or 'Direct':<48.48} │
│  📅 Posted: {job['posted_date'] or 'Unknown':<38.38} │
│  📝 Applied: {job['applied_date'] or 'Not yet':<38.38} │
├─────────────────────────────────────────────────────┤
│  ID: {job['id']:<46.46} │
│  URL: {(job['url'] or 'N/A'):<45.45} │
│  Resume: {(job['resume_path'] or 'Not tailored'):<42.42} │
└─────────────────────────────────────────────────────┘""")

    if job["score_breakdown"]:
        try:
            breakdown = json.loads(job["score_breakdown"])
            if breakdown:
                print("\n  Score Breakdown:")
                for dim, val in breakdown.items():
                    bar = "█" * int(val) + "░" * (10 - int(val))
                    print(f"    {dim:<20} {bar} {val:.1f}/10")
        except json.JSONDecodeError:
            pass

    if job["notes"]:
        print(f"\n  📌 Notes: {job['notes']}")

    return dict(job)


def remove_job(job_id):
    """Remove a job from the pipeline."""
    conn = get_db()
    cursor = conn.execute("DELETE FROM jobs WHERE id = ? OR id LIKE ?",
                          (job_id, f"%{job_id}%"))
    conn.commit()
    if cursor.rowcount:
        print(f"🗑️  Removed: {job_id}")
    else:
        print(f"❌ Job not found: {job_id}")
    conn.close()


def show_stats():
    """Show pipeline statistics."""
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) as c FROM jobs").fetchone()["c"]
    if total == 0:
        print("📭 Pipeline is empty. Run /search to find jobs!")
        conn.close()
        return

    by_status = conn.execute(
        "SELECT status, COUNT(*) as c FROM jobs GROUP BY status ORDER BY c DESC"
    ).fetchall()

    avg_score = conn.execute(
        "SELECT AVG(fit_score) as avg, MAX(fit_score) as max, MIN(fit_score) as min "
        "FROM jobs WHERE fit_score > 0"
    ).fetchone()

    top = conn.execute(
        "SELECT company, title, fit_score FROM jobs ORDER BY fit_score DESC LIMIT 5"
    ).fetchall()

    recent = conn.execute(
        "SELECT COUNT(*) as c FROM jobs WHERE created_at >= datetime('now', '-7 days')"
    ).fetchone()["c"]

    applied = conn.execute(
        "SELECT COUNT(*) as c FROM jobs WHERE status IN ('applied', 'interviewing', 'offered')"
    ).fetchone()["c"]

    print(f"""
╔═══════════════════════════════════════════════════════╗
║  📊 Career Pilot — Pipeline Stats                     ║
╠═══════════════════════════════════════════════════════╣
║  Total Jobs: {total:<5}  │  Added This Week: {recent:<5}        ║
║  Active Applications: {applied:<5}                            ║
║  Avg Score: {avg_score['avg'] or 0:>5.1f}  │  Best: {avg_score['max'] or 0:>5.1f}  │  Lowest: {avg_score['min'] or 0:>5.1f} ║
╠═══════════════════════════════════════════════════════╣""")

    print("║  By Status:                                           ║")
    for row in by_status:
        icon = STATUS_ICONS.get(row["status"], "")
        bar_len = min(int(row["c"] / total * 30), 30)
        bar = "█" * bar_len
        print(f"║    {icon} {row['status']:<13} {bar:<30} {row['c']:>3} ║")

    print("╠═══════════════════════════════════════════════════════╣")
    print("║  🏆 Top Matches:                                      ║")
    for job in top:
        print(f"║    {job['fit_score']:>3.0f}  {job['company']:<15.15} — {job['title']:<25.25} ║")

    print("╚═══════════════════════════════════════════════════════╝")
    conn.close()


def export_jobs(fmt="csv"):
    """Export pipeline to CSV or JSON."""
    conn = get_db()
    jobs = conn.execute("SELECT * FROM jobs ORDER BY fit_score DESC").fetchall()
    conn.close()

    if not jobs:
        print("📭 No jobs to export")
        return

    out_dir = Path(__file__).parent.parent / "jobs"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt == "json":
        out_path = out_dir / f"pipeline_export_{timestamp}.json"
        data = [dict(j) for j in jobs]
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
    else:
        import csv
        out_path = out_dir / f"pipeline_export_{timestamp}.csv"
        with open(out_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(jobs[0].keys())
            for job in jobs:
                writer.writerow(dict(job).values())

    print(f"📤 Exported {len(jobs)} jobs to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Career Pilot Job Tracker")
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # init
    sub.add_parser("init", help="Initialize database")

    # add
    add_p = sub.add_parser("add", help="Add a job")
    add_p.add_argument("--title", required=True)
    add_p.add_argument("--company", required=True)
    add_p.add_argument("--url", default="")
    add_p.add_argument("--platform", default="")
    add_p.add_argument("--location", default="")
    add_p.add_argument("--score", type=float, default=0)
    add_p.add_argument("--description", default="")
    add_p.add_argument("--requirements", default="")
    add_p.add_argument("--salary", default="")
    add_p.add_argument("--posted", default="")
    add_p.add_argument("--notes", default="")

    # update
    upd_p = sub.add_parser("update", help="Update a job")
    upd_p.add_argument("job_id")
    upd_p.add_argument("--status", choices=VALID_STATUSES)
    upd_p.add_argument("--notes")
    upd_p.add_argument("--resume-path")
    upd_p.add_argument("--score", type=float)

    # list
    ls_p = sub.add_parser("list", help="List jobs")
    ls_p.add_argument("--status", choices=VALID_STATUSES)
    ls_p.add_argument("--min-score", type=float)
    ls_p.add_argument("--limit", type=int, default=50)

    # get
    get_p = sub.add_parser("get", help="Get job details")
    get_p.add_argument("job_id")

    # remove
    rm_p = sub.add_parser("remove", help="Remove a job")
    rm_p.add_argument("job_id")

    # stats
    sub.add_parser("stats", help="Pipeline statistics")

    # export
    exp_p = sub.add_parser("export", help="Export pipeline")
    exp_p.add_argument("--format", choices=["csv", "json"], default="csv")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Auto-init on first use
    if args.command != "init" and not DB_PATH.exists():
        init_db()

    if args.command == "init":
        init_db()
    elif args.command == "add":
        add_job(args.title, args.company, args.url, args.platform,
                args.location, args.score, description=args.description,
                requirements=args.requirements, salary_range=args.salary,
                posted_date=args.posted, notes=args.notes)
    elif args.command == "update":
        update_job(args.job_id, status=args.status, notes=args.notes,
                   resume_path=args.resume_path, fit_score=args.score)
    elif args.command == "list":
        list_jobs(args.status, args.min_score, args.limit)
    elif args.command == "get":
        get_job(args.job_id)
    elif args.command == "remove":
        remove_job(args.job_id)
    elif args.command == "stats":
        show_stats()
    elif args.command == "export":
        export_jobs(args.format)


if __name__ == "__main__":
    main()
