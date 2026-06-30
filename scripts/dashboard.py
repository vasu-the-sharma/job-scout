#!/usr/bin/env python3
"""Career Pilot — Terminal Dashboard

Displays a rich terminal dashboard of the job pipeline.
Falls back to basic ASCII if 'rich' is not installed.

Usage:
    python dashboard.py              # Full dashboard
    python dashboard.py --compact    # Compact one-liner per job
    python dashboard.py --kanban     # Kanban-style board
"""

import sqlite3
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent.parent / "jobs" / "pipeline.db"

STATUS_ORDER = [
    "interviewing", "offered", "applied", "tailored",
    "evaluated", "discovered", "accepted", "rejected", "withdrawn"
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

SCORE_COLORS = {
    "green": (80, 101),
    "yellow": (60, 80),
    "orange": (40, 60),
    "red": (0, 40),
}


def get_jobs():
    """Fetch all jobs from database."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    jobs = conn.execute(
        "SELECT * FROM jobs ORDER BY fit_score DESC"
    ).fetchall()
    conn.close()
    return [dict(j) for j in jobs]


def score_indicator(score):
    """Return score with color indicator."""
    if score >= 80:
        return f"🟢 {score:.0f}"
    elif score >= 60:
        return f"🟡 {score:.0f}"
    elif score >= 40:
        return f"🟠 {score:.0f}"
    else:
        return f"🔴 {score:.0f}"


def time_ago(date_str):
    """Convert date string to 'X days ago' format."""
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        delta = datetime.now() - dt.replace(tzinfo=None)
        if delta.days == 0:
            return "today"
        elif delta.days == 1:
            return "1d ago"
        elif delta.days < 7:
            return f"{delta.days}d ago"
        elif delta.days < 30:
            return f"{delta.days // 7}w ago"
        else:
            return f"{delta.days // 30}mo ago"
    except (ValueError, TypeError):
        return date_str[:10] if date_str else ""


def dashboard_full(jobs):
    """Print full dashboard view."""
    if not jobs:
        print("""
╔═══════════════════════════════════════════════════════════╗
║                  🚀 Career Pilot                          ║
║                                                           ║
║   Pipeline is empty!                                      ║
║   Run /search to find jobs or /evaluate <url> to start.   ║
╚═══════════════════════════════════════════════════════════╝
        """)
        return

    # Stats
    total = len(jobs)
    active = [j for j in jobs if j["status"] not in ("rejected", "withdrawn", "accepted")]
    avg_score = sum(j["fit_score"] for j in jobs if j["fit_score"]) / max(len([j for j in jobs if j["fit_score"]]), 1)
    this_week = [j for j in jobs if j.get("created_at", "") >= (datetime.now() - timedelta(days=7)).isoformat()]
    applied_count = len([j for j in jobs if j["status"] in ("applied", "interviewing", "offered")])

    print(f"""
╔═════════════════════════════════════════════════════════════════════╗
║  🚀 Career Pilot Dashboard                                         ║
╠═════════════════════════════════════════════════════════════════════╣
║  📦 Pipeline: {total} total  │  🎯 Active: {len(active)}  │  📨 Applied: {applied_count:<5}        ║
║  📊 Avg Score: {avg_score:>5.1f}    │  📅 This Week: {len(this_week):<5}                          ║
╠═════════════════════════════════════════════════════════════════════╣""")

    # Group by status
    by_status = {}
    for job in jobs:
        status = job["status"]
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(job)

    for status in STATUS_ORDER:
        if status not in by_status:
            continue
        group = by_status[status]
        icon = STATUS_ICONS.get(status, "")
        print(f"║                                                                     ║")
        print(f"║  {icon} {status.upper()} ({len(group)})                                              ║"[:72] + "║")
        print(f"║  {'─' * 65}  ║")

        for job in group[:10]:  # Cap at 10 per status
            score = score_indicator(job["fit_score"]) if job["fit_score"] else "   -"
            company = job["company"][:16]
            title = job["title"][:28]
            when = time_ago(job.get("applied_date") or job.get("created_at", ""))
            platform = job.get("platform", "")[:8]
            line = f"║    {score:<8} {company:<17} {title:<29} {platform:<8} {when:<7} ║"
            print(line[:72] + "║")

    print(f"╠═════════════════════════════════════════════════════════════════════╣")

    # Top recommendations
    unevaluated = [j for j in jobs if j["status"] == "discovered"]
    high_score_unapplied = [j for j in jobs if j["fit_score"] >= 75 and j["status"] in ("evaluated", "tailored")]

    if high_score_unapplied:
        print(f"║  💡 RECOMMENDED NEXT ACTIONS                                        ║")
        for job in high_score_unapplied[:3]:
            print(f"║    → Apply to {job['company']} ({job['title'][:25]}) — Score: {job['fit_score']:.0f}     ║"[:72] + "║")

    if unevaluated:
        print(f"║    → {len(unevaluated)} jobs need evaluation — run /evaluate                    ║"[:72] + "║")

    stale = [j for j in jobs if j["status"] == "applied"
             and j.get("applied_date")
             and j["applied_date"] < (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")]
    if stale:
        print(f"║    → {len(stale)} applications need follow-up (>14 days)                  ║"[:72] + "║")

    print(f"╚═════════════════════════════════════════════════════════════════════╝")


def dashboard_compact(jobs):
    """Print compact one-line-per-job view."""
    if not jobs:
        print("📭 Empty pipeline")
        return

    print(f"\n{'#':>3} {'Score':>5} {'Status':<13} {'Company':<18} {'Role':<32} {'Platform':<10} {'Added':<8}")
    print("─" * 95)

    for i, job in enumerate(jobs, 1):
        score = f"{job['fit_score']:>3.0f}" if job["fit_score"] else "  -"
        icon = STATUS_ICONS.get(job["status"], "")
        when = time_ago(job.get("created_at", ""))
        print(f"{i:>3} {score:>5} {icon} {job['status']:<11} {job['company']:<18.18} {job['title']:<32.32} {job.get('platform', ''):<10.10} {when:<8}")

    print(f"\n📊 {len(jobs)} jobs | Avg score: {sum(j['fit_score'] for j in jobs if j['fit_score']) / max(len([j for j in jobs if j['fit_score']]), 1):.0f}")


def dashboard_kanban(jobs):
    """Print kanban-style board."""
    if not jobs:
        print("📭 Empty pipeline")
        return

    columns = {
        "🔍 DISCOVER": [j for j in jobs if j["status"] in ("discovered", "evaluated")],
        "📝 PREPARE":  [j for j in jobs if j["status"] == "tailored"],
        "📨 APPLIED":  [j for j in jobs if j["status"] == "applied"],
        "🎤 ACTIVE":   [j for j in jobs if j["status"] in ("interviewing", "offered")],
        "✅ DONE":     [j for j in jobs if j["status"] in ("accepted", "rejected", "withdrawn")],
    }

    max_rows = max(len(v) for v in columns.values()) if columns else 0

    # Header
    print()
    for col_name in columns:
        count = len(columns[col_name])
        print(f"  {col_name} ({count})", end="")
        padding = 22 - len(f"  {col_name} ({count})")
        print(" " * max(padding, 1), end="│")
    print()
    print("─" * (23 * len(columns)))

    # Rows
    for row in range(min(max_rows, 15)):
        for col_name, col_jobs in columns.items():
            if row < len(col_jobs):
                job = col_jobs[row]
                score = f"{job['fit_score']:.0f}" if job["fit_score"] else "-"
                cell = f"  {score:>3} {job['company'][:12]}"
                print(f"{cell:<22}", end="│")
            else:
                print(f"{'':22}", end="│")
        print()

    print()


def main():
    parser = argparse.ArgumentParser(description="Career Pilot Dashboard")
    parser.add_argument("--compact", action="store_true", help="Compact view")
    parser.add_argument("--kanban", action="store_true", help="Kanban board")
    args = parser.parse_args()

    jobs = get_jobs()

    if args.compact:
        dashboard_compact(jobs)
    elif args.kanban:
        dashboard_kanban(jobs)
    else:
        dashboard_full(jobs)


if __name__ == "__main__":
    main()
