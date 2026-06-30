#!/usr/bin/env python3
"""Career Pilot — Clickable Job List Generator

Reads the pipeline DB and produces a single self-contained file where every
job is clickable and opens its application URL. Open it in any browser
(laptop or phone). No server, no build step.

Usage:
    python joblist.py                          # HTML -> jobs/job_list.html
    python joblist.py --output ~/Desktop/jobs.html
    python joblist.py --format md              # Markdown -> jobs/job_list.md
    python joblist.py --min-score 70           # Only jobs scoring >= 70
    python joblist.py --status discovered      # Filter by status
    python joblist.py --open                   # Generate and open in browser
"""

import sqlite3
import json
import html
import argparse
import webbrowser
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent.parent / "jobs" / "pipeline.db"

STATUS_LABELS = {
    "discovered": "Discovered",
    "evaluated": "Evaluated",
    "tailored": "Tailored",
    "applied": "Applied",
    "interviewing": "Interviewing",
    "offered": "Offered",
    "accepted": "Accepted",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}


def get_jobs(min_score=None, status=None):
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if min_score is not None:
        query += " AND fit_score >= ?"
        params.append(min_score)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY fit_score DESC, created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def score_band(score):
    if score >= 80:
        return "strong"
    if score >= 60:
        return "good"
    if score >= 40:
        return "stretch"
    return "weak"


def time_ago(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
        d = (datetime.now() - dt).days
        if d <= 0:
            return "today"
        if d == 1:
            return "1d ago"
        if d < 7:
            return f"{d}d ago"
        if d < 30:
            return f"{d // 7}w ago"
        return f"{d // 30}mo ago"
    except (ValueError, TypeError):
        return date_str[:10]


def render_html(jobs):
    total = len(jobs)
    scored = [j for j in jobs if j["fit_score"]]
    avg = sum(j["fit_score"] for j in scored) / len(scored) if scored else 0
    strong = len([j for j in jobs if j["fit_score"] >= 80])
    applied = len([j for j in jobs if j["status"] in ("applied", "interviewing", "offered")])
    generated = datetime.now().strftime("%d %b %Y, %H:%M")

    rows = []
    for j in jobs:
        score = j["fit_score"] or 0
        band = score_band(score)
        url = html.escape(j["url"] or "", quote=True)
        company = html.escape(j["company"] or "")
        title = html.escape(j["title"] or "")
        location = html.escape(j["location"] or "")
        platform = html.escape(j["platform"] or "direct")
        status = j["status"] or "discovered"
        status_label = STATUS_LABELS.get(status, status.title())
        posted = html.escape(time_ago(j.get("posted_date") or j.get("created_at", "")))
        job_id = html.escape(j["id"] or "", quote=True)
        has_url = bool(j["url"])

        open_cell = (
            f'<a class="open" href="{url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Open ↗</a>'
            if has_url else '<span class="nourl">no link</span>'
        )
        row_click = f'onclick="window.open(\'{url}\',\'_blank\')"' if has_url else ""

        rows.append(f"""
        <tr class="job" data-score="{score:.0f}" data-status="{status}" {row_click}>
          <td class="c-score"><span class="badge {band}">{score:.0f}</span></td>
          <td class="c-company">{company}<div class="loc">{location}</div></td>
          <td class="c-role">{title}</td>
          <td class="c-platform"><span class="plat">{platform}</span></td>
          <td class="c-status"><span class="pill s-{status}">{status_label}</span></td>
          <td class="c-posted">{posted}</td>
          <td class="c-actions">
            {open_cell}
            <button class="cmd" data-cmd="/tailor {job_id}" onclick="copyCmd(this, event)" title="Copy the Claude Code command to tailor your resume for this role">Copy /tailor</button>
          </td>
        </tr>""")

    rows_html = "".join(rows) if rows else (
        '<tr><td colspan="7" class="empty">No jobs yet. Run <code>/search</code> in Claude Code to populate your pipeline.</td></tr>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Career Pilot — Job List</title>
<style>
  :root {{
    --bg: #0e1320;
    --surface: #161d2e;
    --surface-2: #1d2738;
    --line: #28324a;
    --text: #e7ecf5;
    --muted: #8a96ad;
    --accent: #f0a868;
    --strong: #4ec9a5;
    --good: #5aa9e6;
    --stretch: #e8b04b;
    --weak: #c96a6a;
    --mono: 'SF Mono', 'JetBrains Mono', 'Fira Code', ui-monospace, Menlo, monospace;
    --sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font-family: var(--sans); line-height: 1.4;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 28px 20px 80px; }}

  header {{ margin-bottom: 22px; }}
  .title {{ display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }}
  .title h1 {{ font-size: 22px; margin: 0; letter-spacing: -0.02em; }}
  .title .gen {{ color: var(--muted); font-size: 12px; font-family: var(--mono); }}

  .stats {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }}
  .stat {{
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 10px; padding: 10px 14px; min-width: 96px;
  }}
  .stat .n {{ font-size: 20px; font-weight: 600; font-family: var(--mono); }}
  .stat .l {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }}
  .stat .n.accent {{ color: var(--accent); }}

  .filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 20px 0 12px; }}
  .filters button {{
    background: var(--surface); color: var(--muted); border: 1px solid var(--line);
    border-radius: 999px; padding: 6px 14px; font-size: 13px; cursor: pointer;
    font-family: var(--sans); transition: all .15s;
  }}
  .filters button:hover {{ color: var(--text); border-color: var(--muted); }}
  .filters button.active {{ background: var(--accent); color: #1a1205; border-color: var(--accent); font-weight: 600; }}

  table {{ width: 100%; border-collapse: collapse; }}
  thead th {{
    text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--muted); font-weight: 600; padding: 10px 12px; border-bottom: 1px solid var(--line);
    cursor: pointer; user-select: none;
  }}
  thead th:hover {{ color: var(--text); }}
  tbody tr.job {{ border-bottom: 1px solid var(--line); cursor: pointer; transition: background .12s; }}
  tbody tr.job:hover {{ background: var(--surface); }}
  td {{ padding: 12px; font-size: 14px; vertical-align: middle; }}

  .badge {{
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 38px; padding: 4px 8px; border-radius: 8px; font-family: var(--mono);
    font-weight: 600; font-size: 14px;
  }}
  .badge.strong  {{ background: rgba(78,201,165,.16);  color: var(--strong); }}
  .badge.good    {{ background: rgba(90,169,230,.16);  color: var(--good); }}
  .badge.stretch {{ background: rgba(232,176,75,.16);  color: var(--stretch); }}
  .badge.weak    {{ background: rgba(201,106,106,.16); color: var(--weak); }}

  .c-company {{ font-weight: 600; }}
  .loc {{ font-weight: 400; font-size: 12px; color: var(--muted); margin-top: 2px; }}
  .c-role {{ color: var(--text); }}
  .plat {{ font-family: var(--mono); font-size: 12px; color: var(--muted); }}
  .c-posted {{ color: var(--muted); font-size: 13px; white-space: nowrap; }}

  .pill {{ display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; border: 1px solid var(--line); color: var(--muted); }}
  .pill.s-applied, .pill.s-interviewing, .pill.s-offered {{ color: var(--strong); border-color: rgba(78,201,165,.4); }}
  .pill.s-tailored, .pill.s-evaluated {{ color: var(--good); border-color: rgba(90,169,230,.4); }}
  .pill.s-rejected, .pill.s-withdrawn {{ color: var(--weak); border-color: rgba(201,106,106,.35); }}

  .c-actions {{ white-space: nowrap; text-align: right; }}
  a.open {{ color: var(--accent); text-decoration: none; font-size: 13px; margin-right: 10px; }}
  a.open:hover {{ text-decoration: underline; }}
  .nourl {{ color: var(--muted); font-size: 12px; margin-right: 10px; }}
  button.cmd {{
    background: transparent; border: 1px solid var(--line); color: var(--muted);
    border-radius: 7px; padding: 4px 10px; font-size: 12px; cursor: pointer;
    font-family: var(--mono); transition: all .12s;
  }}
  button.cmd:hover {{ color: var(--text); border-color: var(--muted); }}
  button.cmd.copied {{ color: var(--strong); border-color: var(--strong); }}

  .empty {{ text-align: center; color: var(--muted); padding: 40px; }}
  .empty code {{ background: var(--surface); padding: 2px 6px; border-radius: 4px; font-family: var(--mono); }}

  .hint {{ margin-top: 18px; color: var(--muted); font-size: 13px; }}
  .hint code {{ background: var(--surface); padding: 2px 6px; border-radius: 4px; font-family: var(--mono); color: var(--text); }}

  @media (max-width: 680px) {{
    .c-platform, .c-posted, .loc {{ display: none; }}
    td, thead th {{ padding: 10px 8px; }}
    .c-actions {{ text-align: left; }}
    button.cmd {{ margin-top: 6px; }}
  }}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="title">
        <h1>🚀 Career Pilot — Job List</h1>
        <span class="gen">generated {generated}</span>
      </div>
      <div class="stats">
        <div class="stat"><div class="n">{total}</div><div class="l">Total</div></div>
        <div class="stat"><div class="n accent">{strong}</div><div class="l">Strong 80+</div></div>
        <div class="stat"><div class="n">{avg:.0f}</div><div class="l">Avg Score</div></div>
        <div class="stat"><div class="n">{applied}</div><div class="l">Applied</div></div>
      </div>
    </header>

    <div class="filters">
      <button class="active" data-filter="all" onclick="setFilter(this)">All</button>
      <button data-filter="strong" onclick="setFilter(this)">Strong (80+)</button>
      <button data-filter="good" onclick="setFilter(this)">Good (60+)</button>
      <button data-filter="applied" onclick="setFilter(this)">Applied</button>
      <button data-filter="discovered" onclick="setFilter(this)">Not yet reviewed</button>
    </div>

    <table id="jobs">
      <thead>
        <tr>
          <th onclick="sortBy(0,true)">Score</th>
          <th onclick="sortBy(1)">Company</th>
          <th onclick="sortBy(2)">Role</th>
          <th onclick="sortBy(3)">Platform</th>
          <th onclick="sortBy(4)">Status</th>
          <th onclick="sortBy(5)">Posted</th>
          <th></th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>

    <p class="hint">
      Click any row to open the posting. Hit <strong>Copy /tailor</strong>, then paste it into Claude Code to tailor your resume for that role.
    </p>
  </div>

<script>
  function setFilter(btn) {{
    document.querySelectorAll('.filters button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const f = btn.dataset.filter;
    document.querySelectorAll('tr.job').forEach(row => {{
      const score = parseInt(row.dataset.score || '0', 10);
      const status = row.dataset.status;
      let show = true;
      if (f === 'strong') show = score >= 80;
      else if (f === 'good') show = score >= 60;
      else if (f === 'applied') show = ['applied','interviewing','offered'].includes(status);
      else if (f === 'discovered') show = ['discovered','evaluated'].includes(status);
      row.style.display = show ? '' : 'none';
    }});
  }}

  let sortState = {{}};
  function sortBy(col, numeric) {{
    const tbody = document.querySelector('#jobs tbody');
    const rows = Array.from(tbody.querySelectorAll('tr.job'));
    const dir = sortState[col] === 'asc' ? 'desc' : 'asc';
    sortState = {{ [col]: dir }};
    rows.sort((a, b) => {{
      let x = a.children[col].innerText.trim();
      let y = b.children[col].innerText.trim();
      if (numeric) {{ x = parseFloat(x) || 0; y = parseFloat(y) || 0; }}
      if (x < y) return dir === 'asc' ? -1 : 1;
      if (x > y) return dir === 'asc' ? 1 : -1;
      return 0;
    }});
    rows.forEach(r => tbody.appendChild(r));
  }}

  function copyCmd(btn, e) {{
    e.stopPropagation();
    const cmd = btn.dataset.cmd;
    navigator.clipboard.writeText(cmd).then(() => {{
      const old = btn.innerText;
      btn.innerText = 'Copied ✓';
      btn.classList.add('copied');
      setTimeout(() => {{ btn.innerText = old; btn.classList.remove('copied'); }}, 1400);
    }});
  }}
</script>
</body>
</html>"""


def render_markdown(jobs):
    lines = [f"# Career Pilot — Job List", f"_Generated {datetime.now().strftime('%d %b %Y, %H:%M')}_", ""]
    lines.append(f"**{len(jobs)} jobs** | Click a link to open the posting. Copy the `/tailor` command into Claude Code to tailor your resume.\n")
    for j in jobs:
        score = j["fit_score"] or 0
        emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🟠" if score >= 40 else "🔴"
        lines.append(f"### {emoji} `{score:.0f}` — {j['company']} · {j['title']}")
        if j["url"]:
            lines.append(f"- **Apply:** [{j['url']}]({j['url']})")
        else:
            lines.append(f"- **Apply:** _(no link saved)_")
        meta = f"{j['platform'] or 'direct'} · {time_ago(j.get('posted_date') or j.get('created_at',''))} · {STATUS_LABELS.get(j['status'], j['status'])}"
        lines.append(f"- {meta}")
        lines.append(f"- **Tailor:** `/tailor {j['id']}`")
        if j.get("location"):
            lines.append(f"- 📍 {j['location']}")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate a clickable job list")
    parser.add_argument("--output", "-o", help="Output path")
    parser.add_argument("--format", choices=["html", "md"], default="html")
    parser.add_argument("--min-score", type=float)
    parser.add_argument("--status")
    parser.add_argument("--open", action="store_true", help="Open in browser after generating")
    args = parser.parse_args()

    jobs = get_jobs(min_score=args.min_score, status=args.status)

    out_dir = DB_PATH.parent
    if args.format == "md":
        content = render_markdown(jobs)
        out = Path(args.output) if args.output else out_dir / "job_list.md"
    else:
        content = render_html(jobs)
        out = Path(args.output) if args.output else out_dir / "job_list.html"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"✅ Job list written: {out}  ({len(jobs)} jobs)")

    if args.open:
        webbrowser.open(f"file://{out.resolve()}")
        print("🌐 Opened in browser")


if __name__ == "__main__":
    main()
