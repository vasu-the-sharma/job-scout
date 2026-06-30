# Contributing to Career Pilot

Thanks for your interest. Career Pilot is a Claude Code-native tool, so contributions fall into a few clear categories.

## Ways to Contribute

### Skill improvements (`CLAUDE.md`)
The most impactful contributions. Each skill (`/search`, `/evaluate`, `/tailor`, etc.) is a workflow definition. Good improvements:
- Better token-budgeting strategies
- Improved scoring heuristics or prompting
- New skill modes (e.g., `/referral`, `/cold-email`, `/linkedin-message`)
- Platform-specific search improvements (Wellfound, Y Combinator jobs, Levels.fyi)

### Script improvements (`scripts/`)
- Better PDF styling in `resume_gen.py`
- Additional export formats in `tracker.py`
- Dashboard improvements in `dashboard.py`
- Additional scoring dimensions in `scorer.py`

### Platform coverage (`config/targets.yaml`)
Add new job platforms, career page URLs for target companies, or improve the search query patterns.

### Documentation
Improve setup instructions, add screenshots, write a guide for a specific use case (e.g., career change, first job hunt).

## Guidelines

**Keep it local-first.** Career Pilot's core value is that all data stays on your machine. Don't add dependencies on external APIs, cloud databases, or third-party services that require accounts.

**Keep it Claude Code-native.** The system is designed to run inside `claude`. Avoid adding a separate server, web UI, or daemon process.

**Don't break the token budget.** The `## Token Budget` section in `CLAUDE.md` exists for a reason — earlier versions of this system burned millions of tokens by fetching every job page during search. Any change to `/search` or `/scan` must stay snippet-first.

**No fabrication.** The resume generation rules are non-negotiable: never invent experience, skills, or metrics. Tailoring means reordering and re-emphasizing, not hallucinating.

## Development Setup

```bash
git clone https://github.com/<username>/career-pilot.git
cd career-pilot
pip install reportlab pyyaml --break-system-packages
cp config/profile.example.yaml config/profile.yaml
# Fill in profile.yaml, add your resume to resume/base_resume.md
python3 scripts/tracker.py init
claude
```

## Submitting Changes

1. Fork the repo and create a branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Test manually: run the relevant slash command in Claude Code and verify it works
4. Open a pull request with a clear description of what changed and why

For CLAUDE.md changes, include a sample interaction showing the before/after behavior if possible.

## Questions

Open an issue with the `question` label. No strict issue template — just describe what you're trying to do.
