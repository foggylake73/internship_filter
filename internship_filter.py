#!/usr/bin/env python3
"""
internship_filter.py

Fetches Summer 2027 internship listings from:
  - https://github.com/SimplifyJobs/Summer2027-Internships
  - https://github.com/vanshb03/Summer2027-Internships

and filters them down to postings located in one or more US states you
specify. No API keys needed -- it just reads the public README.md files.

USAGE EXAMPLES
---------------
  # Show all CA and NY jobs from both repos, printed to the terminal
  python3 internship_filter.py --states CA NY

  # Also match "Remote" postings
  python3 internship_filter.py --states TX --include-remote

  # Save results to a CSV file instead of printing a table
  python3 internship_filter.py --states WA OR --output csv --outfile jobs.csv

  # Only check one of the two repos
  python3 internship_filter.py --states MA --repo simplify

  # See every state abbreviation/name this script understands
  python3 internship_filter.py --list-states

Full state names work too ("--states California 'New York'"), and a
handful of common city shorthands used in these lists (NYC, SF, LA, DC,
Bay Area) are automatically mapped to their state.
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import requests
except ImportError:
    sys.exit("This script requires the 'requests' package: pip install requests")

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("This script requires 'beautifulsoup4': pip install beautifulsoup4")


# --------------------------------------------------------------------------
# State name / abbreviation handling
# --------------------------------------------------------------------------

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}
NAME_TO_ABBR = {v.lower(): k for k, v in US_STATES.items()}

# Common shorthand city/region names used in these repos that imply a state.
# NOTE: "Washington, DC" is handled separately from "Washington" (the state).
CITY_ALIASES = {
    "nyc": "NY",
    "new york city": "NY",
    "sf": "CA",
    "san francisco": "CA",
    "la": "CA",
    "los angeles": "CA",
    "bay area": "CA",
    "silicon valley": "CA",
    "dc": "DC",
    "washington dc": "DC",
    "washington, d.c.": "DC",
}


def normalize_state_query(raw: str) -> Optional[str]:
    """Turn user input like 'ca', 'California', 'new york' into a 2-letter code."""
    key = raw.strip().strip(",").lower()
    if key.upper() in US_STATES:
        return key.upper()
    if key in NAME_TO_ABBR:
        return NAME_TO_ABBR[key]
    return None


def extract_states_from_location(location_text: str) -> List[str]:
    """
    Given a raw location string (possibly containing multiple locations
    separated by <br>/newlines), return the list of state abbreviations
    found in it. Handles 'City, ST', bare state names, 'Remote', and the
    city aliases above.
    """
    found = set()
    text = location_text.strip()

    if not text:
        return []

    if re.search(r"\bremote\b", text, re.IGNORECASE):
        found.add("REMOTE")

    # "City, ST" pattern (2 uppercase letters after a comma)
    for m in re.finditer(r",\s*([A-Z]{2})\b", text):
        code = m.group(1)
        if code in US_STATES:
            found.add(code)

    # Bare full state names anywhere in the text (e.g. "Washington")
    lower_text = text.lower()
    for name, abbr in NAME_TO_ABBR.items():
        if re.search(r"\b" + re.escape(name) + r"\b", lower_text):
            found.add(abbr)

    # Known city/region shorthands
    for alias, abbr in CITY_ALIASES.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", lower_text):
            found.add(abbr)

    return list(found)


# --------------------------------------------------------------------------
# Job data model
# --------------------------------------------------------------------------

@dataclass
class Job:
    source: str          # "SimplifyJobs" or "vanshb03"
    category: str        # e.g. "Software Engineering" (Simplify only, else "")
    company: str
    role: str
    raw_location: str
    locations: List[str] = field(default_factory=list)   # individual location strings
    states: List[str] = field(default_factory=list)      # matched state codes ("REMOTE" possible)
    link: str = ""
    posted: str = ""


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

REPOS = {
    "simplify": {
        "name": "SimplifyJobs",
        "raw_url_template": "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/{branch}/README.md",
        "branches": ["dev", "main", "master"],
    },
    "vansh": {
        "name": "vanshb03",
        "raw_url_template": "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/{branch}/README.md",
        "branches": ["main", "dev", "master"],
    },
}


def fetch_readme(repo_key: str, timeout: int = 20) -> str:
    repo = REPOS[repo_key]
    last_err = None
    for branch in repo["branches"]:
        url = repo["raw_url_template"].format(branch=branch)
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200 and len(resp.text) > 500:
                return resp.text
        except requests.RequestException as e:
            last_err = e
    raise RuntimeError(
        f"Could not fetch README for {repo['name']} (tried branches {repo['branches']}): {last_err}"
    )


# --------------------------------------------------------------------------
# Parsing: SimplifyJobs (HTML <table> blocks, one per category)
# --------------------------------------------------------------------------

def parse_simplify(markdown_text: str) -> List[Job]:
    jobs: List[Job] = []

    # Split the doc on category headers (## <emoji> Category Name) so we can
    # label each table with its category.
    section_pattern = re.compile(r"^##\s+[^\n]*?([A-Za-z][A-Za-z ,&/]+)\s*$", re.MULTILINE)
    sections = []
    matches = list(section_pattern.finditer(markdown_text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)
        category = m.group(1).strip()
        sections.append((category, markdown_text[start:end]))

    for category, chunk in sections:
        if "<table>" not in chunk:
            continue
        soup = BeautifulSoup(chunk, "html.parser")
        for table in soup.find_all("table"):
            body = table.find("tbody") or table
            last_company = ""
            for tr in body.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) < 5:
                    continue
                company_cell, role_cell, loc_cell, app_cell, age_cell = cells[:5]

                company_text = company_cell.get_text(strip=True)
                if company_text in ("", "↳"):
                    company = last_company
                else:
                    company = company_text
                    last_company = company

                role = role_cell.get_text(strip=True)

                # Location: <details> wraps multi-location lists with <br> separators
                details = loc_cell.find("details")
                if details:
                    loc_html = str(details)
                    loc_html = re.sub(r"<summary>.*?</summary>", "", loc_html, flags=re.DOTALL)
                    inner_soup = BeautifulSoup(loc_html, "html.parser")
                    raw_loc = inner_soup.get_text(separator="|", strip=True)
                else:
                    raw_loc = loc_cell.get_text(separator="|", strip=True)
                individual_locs = [l.strip() for l in raw_loc.split("|") if l.strip()]

                link_tag = app_cell.find("a")
                link = link_tag["href"] if link_tag and link_tag.has_attr("href") else ""

                age = age_cell.get_text(strip=True)

                all_states = set()
                for loc in individual_locs:
                    all_states.update(extract_states_from_location(loc))

                jobs.append(Job(
                    source="SimplifyJobs",
                    category=category,
                    company=company,
                    role=role,
                    raw_location=", ".join(individual_locs) if individual_locs else raw_loc,
                    locations=individual_locs,
                    states=sorted(all_states),
                    link=link,
                    posted=age,
                ))
    return jobs


# --------------------------------------------------------------------------
# Parsing: vanshb03 (single markdown pipe table, cells contain raw HTML)
# --------------------------------------------------------------------------

def split_md_row(line: str) -> List[str]:
    """Split a markdown table row on unescaped pipes, trimming the ends."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    # Cells never contain literal "|" in this repo's content, so a plain split is safe.
    return [c.strip() for c in line.split("|")]


def parse_vansh(markdown_text: str) -> List[Job]:
    jobs: List[Job] = []
    lines = markdown_text.splitlines()

    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("| Company") and "Location" in line:
            header_idx = i
            break
    if header_idx is None:
        return jobs

    last_company = ""
    for line in lines[header_idx + 2:]:  # skip header + separator row
        if not line.strip().startswith("|"):
            if line.strip() == "":
                continue
            else:
                break  # table ended
        cells = split_md_row(line)
        if len(cells) < 5:
            continue
        company_raw, role_raw, loc_raw, app_raw, posted_raw = cells[:5]

        company_soup = BeautifulSoup(company_raw, "html.parser")
        company_text = company_soup.get_text(strip=True)
        if company_text in ("", "↳"):
            company = last_company
        else:
            company = company_text
            last_company = company

        role = BeautifulSoup(role_raw, "html.parser").get_text(strip=True)

        # Location cell: may contain <details><summary>N locations</summary>City</br>City...</details>
        # or plain "City, ST</br>City2, ST2"
        details_match = re.search(r"<details>.*?</details>", loc_raw, re.DOTALL)
        if details_match:
            inner = details_match.group(0)
            inner = re.sub(r"<summary>.*?</summary>", "", inner, flags=re.DOTALL)
            inner = inner.replace("<details>", "").replace("</details>", "")
        else:
            inner = loc_raw
        inner = inner.replace("</br>", "|").replace("<br>", "|").replace("<br/>", "|")
        inner_text = BeautifulSoup(inner, "html.parser").get_text(separator="|", strip=True)
        individual_locs = [l.strip() for l in inner_text.split("|") if l.strip()]

        link_match = re.search(r'href="([^"]+)"', app_raw)
        link = link_match.group(1) if link_match else ""

        posted = BeautifulSoup(posted_raw, "html.parser").get_text(strip=True)

        all_states = set()
        for loc in individual_locs:
            all_states.update(extract_states_from_location(loc))

        jobs.append(Job(
            source="vanshb03",
            category="",
            company=company,
            role=role,
            raw_location=", ".join(individual_locs) if individual_locs else loc_raw,
            locations=individual_locs,
            states=sorted(all_states),
            link=link,
            posted=posted,
        ))
    return jobs


# --------------------------------------------------------------------------
# Filtering / output
# --------------------------------------------------------------------------

def filter_jobs(jobs: List[Job], wanted_states: List[str], include_remote: bool) -> List[Job]:
    wanted = set(wanted_states)
    out = []
    for job in jobs:
        job_states = set(job.states)
        if include_remote and "REMOTE" in job_states:
            out.append(job)
            continue
        if job_states & wanted:
            out.append(job)
    return out


def print_table(jobs: List[Job]) -> None:
    if not jobs:
        print("No matching jobs found.")
        return
    for job in jobs:
        cat = f" [{job.category}]" if job.category else ""
        states = ", ".join(job.states) if job.states else "?"
        print(f"[{job.source}]{cat} {job.company} — {job.role}")
        print(f"    Location(s): {job.raw_location}  (matched: {states})")
        print(f"    Posted: {job.posted}    Apply: {job.link}")
        print()
    print(f"Total: {len(jobs)} matching job(s)")


def write_csv(jobs: List[Job], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Source", "Category", "Company", "Role", "Location", "Matched States", "Posted", "Link"])
        for job in jobs:
            writer.writerow([
                job.source, job.category, job.company, job.role,
                job.raw_location, ", ".join(job.states), job.posted, job.link,
            ])
    print(f"Wrote {len(jobs)} job(s) to {path}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Filter Summer 2027 internship listings by US state.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--states", nargs="+", help="State abbreviations or names to filter by, e.g. CA NY 'New York'")
    parser.add_argument("--include-remote", action="store_true", help="Also include postings marked Remote")
    parser.add_argument("--repo", choices=["simplify", "vansh", "both"], default="both", help="Which repo(s) to search")
    parser.add_argument("--output", choices=["table", "csv"], default="table", help="Output format")
    parser.add_argument("--outfile", default="filtered_jobs.csv", help="CSV output path (used with --output csv)")
    parser.add_argument("--list-states", action="store_true", help="Print all recognized state codes/names and exit")
    args = parser.parse_args()

    if args.list_states:
        for abbr, name in sorted(US_STATES.items()):
            print(f"{abbr}: {name}")
        return

    if not args.states:
        parser.error("--states is required (or use --list-states to see valid values)")

    wanted_states = []
    for s in args.states:
        code = normalize_state_query(s)
        if not code:
            print(f"Warning: '{s}' is not a recognized US state, skipping.", file=sys.stderr)
            continue
        wanted_states.append(code)

    if not wanted_states:
        sys.exit("No valid states given. Use --list-states to see valid values.")

    all_jobs: List[Job] = []

    if args.repo in ("simplify", "both"):
        print("Fetching SimplifyJobs/Summer2027-Internships...", file=sys.stderr)
        md = fetch_readme("simplify")
        all_jobs.extend(parse_simplify(md))

    if args.repo in ("vansh", "both"):
        print("Fetching vanshb03/Summer2027-Internships...", file=sys.stderr)
        md = fetch_readme("vansh")
        all_jobs.extend(parse_vansh(md))

    print(f"Parsed {len(all_jobs)} total listings. Filtering for: {', '.join(wanted_states)}"
          + (" + Remote" if args.include_remote else ""), file=sys.stderr)

    matched = filter_jobs(all_jobs, wanted_states, args.include_remote)

    if args.output == "csv":
        write_csv(matched, args.outfile)
    else:
        print_table(matched)


if __name__ == "__main__":
    main()
