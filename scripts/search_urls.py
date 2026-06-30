#!/usr/bin/env python3
"""Career Pilot — Search URL Generator

Generates search URLs for Indian job platforms based on profile.
Claude Code uses these URLs with web_fetch to scrape job listings.

Usage:
    python search_urls.py                    # All platforms, default queries
    python search_urls.py --platform naukri  # Specific platform
    python search_urls.py --role "SDE Lead"  # Custom role
    python search_urls.py --json             # Output as JSON
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlencode

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

PROFILE_PATH = Path(__file__).parent.parent / "config" / "profile.yaml"
TARGETS_PATH = Path(__file__).parent.parent / "config" / "targets.yaml"


def load_yaml(path):
    """Load YAML file."""
    if not path.exists():
        return {}
    if HAS_YAML:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    # Minimal fallback
    return {}


def generate_linkedin_urls(roles, locations, skills):
    """Generate LinkedIn job search URLs."""
    urls = []
    for role in roles:
        for location in locations:
            params = {
                "keywords": role,
                "location": location,
                "f_TPR": "r604800",     # Past week
                "sortBy": "DD",          # Most recent
                "f_E": "3,4",           # Mid-senior + Director
            }
            url = f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"
            urls.append({
                "platform": "linkedin",
                "url": url,
                "role": role,
                "location": location,
                "search_query": f"{role} {location} site:linkedin.com/jobs past week",
            })
    return urls


def generate_naukri_urls(roles, locations, experience_range="3-8"):
    """Generate Naukri.com search URLs."""
    urls = []
    location_map = {
        "Bengaluru": "bangalore",
        "Bangalore": "bangalore",
        "Hyderabad": "hyderabad",
        "Pune": "pune",
        "Mumbai": "mumbai",
        "Delhi NCR": "delhi-ncr",
        "Remote India": "",
    }

    for role in roles:
        slug = role.lower().replace(" ", "-")
        for location in locations:
            naukri_loc = location_map.get(location, location.lower().replace(" ", "-"))
            if naukri_loc:
                url = f"https://www.naukri.com/{slug}-jobs-in-{naukri_loc}?experience={experience_range}&jobAge=7"
            else:
                url = f"https://www.naukri.com/{slug}-jobs?experience={experience_range}&jobAge=7"

            urls.append({
                "platform": "naukri",
                "url": url,
                "role": role,
                "location": location,
                "search_query": f"{role} {location} site:naukri.com past week",
            })
    return urls


def generate_instahyre_urls(roles, locations):
    """Generate Instahyre search URLs."""
    urls = []
    for role in roles:
        for location in locations:
            search_query = f"{role} {location} site:instahyre.com"
            urls.append({
                "platform": "instahyre",
                "url": f"https://www.instahyre.com/search-jobs/?q={quote(role)}&location={quote(location)}",
                "role": role,
                "location": location,
                "search_query": search_query,
            })
    return urls


def generate_indeed_urls(roles, locations):
    """Generate Indeed India search URLs."""
    urls = []
    for role in roles:
        for location in locations:
            params = {
                "q": role,
                "l": location,
                "fromage": "7",      # Last 7 days
                "sort": "date",
            }
            url = f"https://in.indeed.com/jobs?{urlencode(params)}"
            urls.append({
                "platform": "indeed",
                "url": url,
                "role": role,
                "location": location,
                "search_query": f"{role} {location} site:in.indeed.com past week",
            })
    return urls


def generate_wellfound_urls(roles):
    """Generate Wellfound (AngelList) search URLs."""
    urls = []
    for role in roles:
        slug = role.lower().replace(" ", "-")
        urls.append({
            "platform": "wellfound",
            "url": f"https://wellfound.com/role/r/{slug}",
            "role": role,
            "location": "India",
            "search_query": f"{role} India startup site:wellfound.com",
        })
    return urls


def generate_web_search_queries(roles, locations, skills):
    """Generate optimized web search queries for Claude Code to use."""
    queries = []

    # Platform-specific searches
    for role in roles:
        for location in locations[:2]:  # Top 2 locations
            queries.append(f'"{role}" "{location}" site:linkedin.com/jobs')
            queries.append(f'{role} {location} site:naukri.com')

    # Skill-based searches
    top_skills = skills[:3]
    for skill_combo in [" ".join(top_skills[:2]), " ".join(top_skills[1:3])]:
        queries.append(f'senior engineer {skill_combo} India hiring 2026')

    # Company career page searches
    queries.append(f'site:lever.co OR site:greenhouse.io "{roles[0]}" India')
    queries.append(f'site:jobs.ashbyhq.com "{roles[0]}" Bengaluru')

    return queries


def main():
    parser = argparse.ArgumentParser(description="Generate job search URLs")
    parser.add_argument("--platform", choices=["linkedin", "naukri", "instahyre", "indeed", "wellfound", "all"],
                       default="all")
    parser.add_argument("--role", help="Override role to search for")
    parser.add_argument("--location", help="Override location")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--queries-only", action="store_true", help="Only output web search queries")

    args = parser.parse_args()

    # Load profile
    profile = load_yaml(PROFILE_PATH)
    targets = load_yaml(TARGETS_PATH)

    # Determine search parameters
    roles = [args.role] if args.role else profile.get("target_roles", ["Senior Software Engineer"])
    locations = [args.location] if args.location else (
        profile.get("preferences", {}).get("preferred_cities", ["Bengaluru"])
    )
    skills_data = profile.get("skills", {})
    skills = skills_data.get("primary", []) + skills_data.get("secondary", [])[:3]
    experience = str(profile.get("years_of_experience", 4))

    # Generate URLs
    all_urls = []
    platform = args.platform

    if platform in ("linkedin", "all"):
        all_urls.extend(generate_linkedin_urls(roles, locations, skills))
    if platform in ("naukri", "all"):
        all_urls.extend(generate_naukri_urls(roles, locations, f"{max(int(experience)-1, 0)}-{int(experience)+4}"))
    if platform in ("instahyre", "all"):
        all_urls.extend(generate_instahyre_urls(roles, locations))
    if platform in ("indeed", "all"):
        all_urls.extend(generate_indeed_urls(roles, locations))
    if platform in ("wellfound", "all"):
        all_urls.extend(generate_wellfound_urls(roles))

    # Web search queries
    search_queries = generate_web_search_queries(roles, locations, [s for s in skills if isinstance(s, str)])

    if args.queries_only:
        if args.json:
            print(json.dumps(search_queries, indent=2))
        else:
            print("\n🔍 Web Search Queries for Claude Code:\n")
            for i, q in enumerate(search_queries, 1):
                print(f"  {i:>2}. {q}")
        return

    if args.json:
        output = {
            "urls": all_urls,
            "search_queries": search_queries,
            "params": {
                "roles": roles,
                "locations": locations,
                "experience": experience,
            }
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n🔗 Generated {len(all_urls)} search URLs across platforms:\n")

        current_platform = None
        for item in all_urls:
            if item["platform"] != current_platform:
                current_platform = item["platform"]
                print(f"\n  📍 {current_platform.upper()}")
                print(f"  {'─' * 50}")

            print(f"    {item['role']} | {item['location']}")
            print(f"    URL: {item['url'][:80]}...")
            print(f"    Search: {item['search_query']}")
            print()

        print(f"\n🔍 Web Search Queries ({len(search_queries)}):\n")
        for i, q in enumerate(search_queries, 1):
            print(f"  {i:>2}. {q}")

        print(f"\n💡 Claude Code: Use these search queries with web_search,")
        print(f"   then web_fetch the result URLs to extract job details.")


if __name__ == "__main__":
    main()
