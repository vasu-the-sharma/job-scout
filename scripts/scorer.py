#!/usr/bin/env python3
"""Career Pilot — Job Fit Scorer

Scores job postings against user profile across 10 dimensions.
Designed to be called by Claude Code for automated scoring,
or standalone with a JSON job description file.

Usage:
    python scorer.py --job-file jobs/some_job.json
    python scorer.py --title "Sr SWE" --company "Stripe" --requirements "Python, React, 4+ years"
"""

import json
import sys
import argparse
import re
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

PROFILE_PATH = Path(__file__).parent.parent / "config" / "profile.yaml"

# Scoring dimensions with weights
DIMENSIONS = {
    "tech_stack_match":  {"weight": 0.15, "label": "Tech Stack Match"},
    "experience_level":  {"weight": 0.15, "label": "Experience Level"},
    "domain_fit":        {"weight": 0.10, "label": "Domain Fit"},
    "role_scope":        {"weight": 0.10, "label": "Role Scope"},
    "growth_potential":  {"weight": 0.10, "label": "Growth Potential"},
    "location_match":    {"weight": 0.10, "label": "Location/Remote"},
    "company_stage":     {"weight": 0.10, "label": "Company Stage"},
    "compensation":      {"weight": 0.10, "label": "Compensation"},
    "culture_signals":   {"weight": 0.05, "label": "Culture Signals"},
    "application_effort":{"weight": 0.05, "label": "Application Effort"},
}


def load_profile():
    """Load user profile from YAML config."""
    if not PROFILE_PATH.exists():
        print("⚠️  Profile not found. Run /setup first.", file=sys.stderr)
        return None

    if HAS_YAML:
        with open(PROFILE_PATH) as f:
            return yaml.safe_load(f)
    else:
        # Fallback: basic YAML parsing for simple cases
        profile = {}
        with open(PROFILE_PATH) as f:
            content = f.read()
        # Extract key fields with regex
        for field in ["name", "location", "years_of_experience", "seniority"]:
            match = re.search(rf'^{field}:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
            if match:
                val = match.group(1)
                profile[field] = int(val) if val.isdigit() else val

        # Extract skills lists
        skills_section = re.search(r'skills:\s*\n((?:\s+.+\n)+)', content)
        if skills_section:
            profile["skills"] = {
                "primary": re.findall(r'- "(.+?)"', skills_section.group(1)),
            }
        return profile


def extract_keywords(text):
    """Extract tech keywords from job description text."""
    if not text:
        return set()

    text_lower = text.lower()
    # Common tech keywords to look for
    tech_terms = {
        "python", "java", "javascript", "typescript", "c++", "c", "go", "golang",
        "rust", "ruby", "scala", "kotlin", "swift", "php",
        "react", "angular", "vue", "next.js", "node.js", "express",
        "spring boot", "spring", "django", "flask", "fastapi",
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "kafka", "rabbitmq", "aws", "gcp", "azure", "docker", "kubernetes",
        "terraform", "jenkins", "ci/cd", "git", "linux",
        "machine learning", "ml", "ai", "llm", "langchain", "rag",
        "microservices", "grpc", "rest", "graphql", "api",
        "compiler", "llvm", "clang",
    }
    found = set()
    for term in tech_terms:
        if term in text_lower:
            found.add(term)
    return found


def score_tech_stack(job_data, profile):
    """Score tech stack overlap (0-10)."""
    job_text = f"{job_data.get('requirements', '')} {job_data.get('description', '')}"
    job_keywords = extract_keywords(job_text)

    if not job_keywords:
        return 5.0  # Can't determine, neutral score

    all_skills = set()
    skills = profile.get("skills", {})
    for category in ["primary", "secondary", "tools"]:
        for skill in skills.get(category, []):
            all_skills.add(skill.lower())

    if not all_skills:
        return 5.0

    overlap = job_keywords & all_skills
    match_ratio = len(overlap) / len(job_keywords) if job_keywords else 0

    # Bonus for primary skill matches
    primary = set(s.lower() for s in skills.get("primary", []))
    primary_overlap = job_keywords & primary
    primary_bonus = min(len(primary_overlap) * 0.5, 2.0)

    score = min(match_ratio * 8 + primary_bonus, 10.0)
    return round(score, 1)


def score_experience_level(job_data, profile):
    """Score experience level match (0-10)."""
    user_years = profile.get("years_of_experience", 3)
    req_text = f"{job_data.get('requirements', '')} {job_data.get('description', '')}"

    # Try to extract years requirement
    year_patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)',
        r'(?:experience|exp)\s*(?:of\s+)?(\d+)\+?\s*(?:years?|yrs?)',
        r'(\d+)-(\d+)\s*(?:years?|yrs?)',
    ]

    min_years = None
    max_years = None
    for pattern in year_patterns:
        match = re.search(pattern, req_text.lower())
        if match:
            groups = match.groups()
            min_years = int(groups[0])
            max_years = int(groups[1]) if len(groups) > 1 and groups[1] else min_years + 3
            break

    if min_years is None:
        return 7.0  # Can't determine, slightly positive

    # Score based on fit
    if min_years <= user_years <= (max_years or min_years + 5):
        return 9.0  # Sweet spot
    elif user_years >= min_years:
        return 8.0  # Overqualified slightly
    elif user_years >= min_years - 1:
        return 6.0  # Slight stretch
    elif user_years >= min_years - 2:
        return 4.0  # Notable stretch
    else:
        return 2.0  # Significant gap

    return round(score, 1)


def score_location(job_data, profile):
    """Score location match (0-10)."""
    job_location = job_data.get("location", "").lower()
    prefs = profile.get("preferences", {})
    preferred = [c.lower() for c in prefs.get("preferred_cities", [])]
    remote_ok = prefs.get("remote_ok", True)

    if not job_location:
        return 6.0

    if "remote" in job_location:
        return 9.0 if remote_ok else 5.0

    for city in preferred:
        if city in job_location or job_location in city:
            return 9.0

    if "india" in job_location:
        return 6.0

    return 3.0  # Different country/city


def score_compensation(job_data, profile):
    """Score compensation match (0-10)."""
    salary = job_data.get("salary_range", "")
    if not salary:
        return 5.0  # Unknown, neutral

    prefs = profile.get("preferences", {})
    min_ctc = prefs.get("min_ctc_lakhs", 0)
    expected = prefs.get("expected_ctc_lakhs", 0)

    # Try to extract numbers from salary string
    numbers = re.findall(r'(\d+\.?\d*)', salary)
    if not numbers:
        return 5.0

    amounts = [float(n) for n in numbers]
    max_offered = max(amounts)

    # Normalize to lakhs if needed (heuristic)
    if max_offered > 1000:  # Likely in thousands (monthly)
        max_offered = max_offered * 12 / 100000  # Convert to lakhs annual

    if max_offered >= expected:
        return 9.0
    elif max_offered >= min_ctc:
        return 7.0
    elif max_offered >= min_ctc * 0.8:
        return 5.0
    else:
        return 3.0


def compute_score(job_data, profile=None):
    """Compute composite fit score across all dimensions.

    Args:
        job_data: dict with keys: title, company, description, requirements,
                  location, salary_range, etc.
        profile: user profile dict (loaded from YAML if not provided)

    Returns:
        dict with 'total' (0-100) and 'breakdown' (per-dimension scores)
    """
    if profile is None:
        profile = load_profile()
        if not profile:
            return {"total": 0, "breakdown": {}}

    breakdown = {}

    # Automated scoring for measurable dimensions
    breakdown["tech_stack_match"] = score_tech_stack(job_data, profile)
    breakdown["experience_level"] = score_experience_level(job_data, profile)
    breakdown["location_match"] = score_location(job_data, profile)
    breakdown["compensation"] = score_compensation(job_data, profile)

    # Heuristic scoring for softer dimensions
    # (Claude Code should override these with its own analysis)
    breakdown["domain_fit"] = job_data.get("domain_fit_score", 5.0)
    breakdown["role_scope"] = job_data.get("role_scope_score", 5.0)
    breakdown["growth_potential"] = job_data.get("growth_potential_score", 5.0)
    breakdown["company_stage"] = job_data.get("company_stage_score", 5.0)
    breakdown["culture_signals"] = job_data.get("culture_signals_score", 5.0)
    breakdown["application_effort"] = job_data.get("application_effort_score", 5.0)

    # Compute weighted total
    total = 0
    for dim, config in DIMENSIONS.items():
        score = breakdown.get(dim, 5.0)
        total += score * config["weight"] * 10  # Scale to 0-100

    total = min(round(total, 1), 100)
    breakdown_labeled = {
        DIMENSIONS[k]["label"]: v for k, v in breakdown.items()
    }

    return {"total": total, "breakdown": breakdown_labeled}


def print_scorecard(job_data, result):
    """Print a formatted scorecard."""
    total = result["total"]
    color = "🟢" if total >= 80 else "🟡" if total >= 60 else "🟠" if total >= 40 else "🔴"

    print(f"""
┌──────────────────────────────────────────────────┐
│  {job_data.get('company', '?')} — {job_data.get('title', '?'):<32.32}│
│  {color} Score: {total:.0f}/100                                │
├──────────────────────────────────────────────────┤""")

    for label, score in result["breakdown"].items():
        bar = "█" * int(score) + "░" * (10 - int(score))
        print(f"│  {label:<20} {bar} {score:>4.1f}/10  │")

    print(f"└──────────────────────────────────────────────────┘")

    if total >= 80:
        print("  → Strong match. Recommend: /tailor and /apply")
    elif total >= 60:
        print("  → Good match. Recommend: /evaluate deeper, then /tailor")
    elif total >= 40:
        print("  → Stretch role. Review gaps carefully before applying.")
    else:
        print("  → Weak match. Consider skipping unless strategic.")


def main():
    parser = argparse.ArgumentParser(description="Score job fit")
    parser.add_argument("--job-file", help="Path to JSON job description")
    parser.add_argument("--title", help="Job title")
    parser.add_argument("--company", help="Company name")
    parser.add_argument("--requirements", help="Requirements text")
    parser.add_argument("--description", help="Job description text")
    parser.add_argument("--location", default="")
    parser.add_argument("--salary", default="")
    parser.add_argument("--json-output", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.job_file:
        with open(args.job_file) as f:
            job_data = json.load(f)
    elif args.title and args.company:
        job_data = {
            "title": args.title,
            "company": args.company,
            "requirements": args.requirements or "",
            "description": args.description or "",
            "location": args.location,
            "salary_range": args.salary,
        }
    else:
        parser.print_help()
        return

    result = compute_score(job_data)

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print_scorecard(job_data, result)


if __name__ == "__main__":
    main()
