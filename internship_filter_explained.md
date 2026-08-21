# `internship_filter.py` — Line-by-Line Explanation

## Lines 1–32: File header

```python
#!/usr/bin/env python3
```
Tells Unix-like systems (Mac/Linux) which program should run this file if you try to execute it directly (`./internship_filter.py`). Ignored on Windows and when you run it as `python3 internship_filter.py`.

```python
"""
internship_filter.py
...
"""
```
A triple-quoted string right at the top of a file is a **docstring** — Python treats it as the module's documentation. It's not executed as code; it just describes what the script does and shows usage examples. If someone runs `python3 internship_filter.py --help`, part of this text gets shown to them (via `epilog=__doc__` later in the file).

## Lines 34–51: Imports

```python
import argparse   # reads command-line flags like --states CA NY
import csv        # writes .csv files
import os         # makes folders, joins file paths
import re         # regex (pattern matching in text)
import sys        # lets us print errors and exit the program
from datetime import datetime          # gets the current date/time for filenames
from dataclasses import dataclass, field  # a shortcut for defining simple data containers
from typing import List, Optional      # type hints, just documentation for humans/editors
```

```python
try:
    import requests
except ImportError:
    sys.exit("This script requires the 'requests' package: pip install requests")
```
Tries to import the `requests` library (used to download web pages). If it's not installed, instead of crashing with a confusing Python traceback, it prints a clear message and stops immediately (`sys.exit`).

```python
try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("This script requires 'beautifulsoup4': pip install beautifulsoup4")
```
Same idea, but for `BeautifulSoup`, the library used to read HTML.

---

## Lines 58–89: State data

```python
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", ...
}
```
A dictionary (lookup table) mapping every 2-letter state code to its full name. Used throughout the script to check "is this a real state?" and to convert between the two forms.

```python
NAME_TO_ABBR = {v.lower(): k for k, v in US_STATES.items()}
```
Builds the *reverse* dictionary — full name (lowercase) → abbreviation — by looping through `US_STATES` and flipping each key/value pair. This is a "dict comprehension," a compact way to build a dictionary in one line.

```python
CITY_ALIASES = {
    "nyc": "NY",
    "new york city": "NY",
    ...
}
```
A small manual lookup table for city/region nicknames that show up in the job listings but aren't states themselves (e.g. "NYC" instead of "New York, NY").

---

## Lines 92–99: `normalize_state_query()`

Converts *your* typed input (from `--states`) into a clean 2-letter code.

```python
def normalize_state_query(raw: str) -> Optional[str]:
```
Defines a function named `normalize_state_query` that takes one text argument (`raw`) and returns either a string or `None` (that's what `Optional[str]` means).

```python
    key = raw.strip().strip(",").lower()
```
Cleans the input: removes leading/trailing whitespace, then removes leading/trailing commas, then lowercases everything — so `" CA, "` and `"ca"` end up as the same thing: `"ca"`.

```python
    if key.upper() in US_STATES:
        return key.upper()
```
If uppercasing the cleaned input matches a key in `US_STATES` (e.g. `"ca"` → `"CA"`), return that code directly.

```python
    if key in NAME_TO_ABBR:
        return NAME_TO_ABBR[key]
```
Otherwise, check if the cleaned input matches a full state name (e.g. `"california"`) in the reverse lookup table, and return its abbreviation.

```python
    return None
```
If neither matched, the input isn't a recognized state — return nothing.

---

## Lines 102–135: `extract_states_from_location()`

Looks at a location string from a job posting and figures out which state(s) it refers to.

```python
def extract_states_from_location(location_text: str) -> List[str]:
```
Takes one location string, returns a list of state codes found in it.

```python
    found = set()
```
A `set` is like a list but automatically ignores duplicates — perfect since a location could match "CA" twice via different rules and we only want it once.

```python
    text = location_text.strip()
    if not text:
        return []
```
Trims whitespace. If the string is empty after trimming, there's nothing to search — return an empty list immediately.

```python
    if re.search(r"\bremote\b", text, re.IGNORECASE):
        found.add("REMOTE")
```
`re.search` scans `text` for the word "remote" as a whole word (`\b` = word boundary, so it won't match "telecommute"), ignoring uppercase/lowercase. If found, adds the special marker `"REMOTE"` to the set.

```python
    for m in re.finditer(r",\s*([A-Z]{2})\b", text):
        code = m.group(1)
        if code in US_STATES:
            found.add(code)
```
`re.finditer` finds *every* match of the pattern in the text (not just the first). The pattern means: a comma, then optional whitespace, then exactly 2 capital letters, then a word boundary — i.e. the `"ST"` in `"Austin, TX"`. For each match, `m.group(1)` pulls out just the 2-letter part, and if it's a real state code, adds it to the set.

```python
    lower_text = text.lower()
    if not re.search(r"washington,?\s*d\.?c\.?", lower_text):
        for name, abbr in NAME_TO_ABBR.items():
            if re.search(r"\b" + re.escape(name) + r"\b", lower_text):
                found.add(abbr)
```
Lowercases the whole text once (for efficient comparison). Then, **only if the text doesn't read as "Washington, DC"** (in any spacing/punctuation variant, like "Washington DC" or "Washington, D.C."), it loops through every full state name and checks if it appears anywhere in the text as a whole word/phrase. `re.escape(name)` makes sure special regex characters in a state name (unlikely, but safe practice) are treated literally. If a match is found, add that state's abbreviation.

**Why the guard clause exists:** without it, a location like `"Washington, DC"` would trigger *two* matches — the earlier `"City, ST"` check correctly catches `", DC"` → `DC`, but this full-name check would *also* see the word "Washington" and incorrectly add `WA` (Washington the state), since "Washington" is a real state name that happens to also be the first word of the national capital's name. The guard skips this whole block when that specific phrase is present, so only `DC` gets matched, not `DC` + `WA`. Bare mentions of "Washington" without "DC" attached (e.g. a job actually located in Washington state) still get matched normally, since the guard only fires when "Washington" and "DC" appear together.

```python
    for alias, abbr in CITY_ALIASES.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", lower_text):
            found.add(abbr)
```
Same idea, but checking against the city nickname table instead.

```python
    return list(found)
```
Converts the `set` back into a `list` (sets don't have a guaranteed order, and the rest of the code expects a list) and returns it.

---

## Lines 142–152: The `Job` class

```python
@dataclass
class Job:
```
`@dataclass` is a decorator — a shortcut that auto-generates the boring boilerplate code (like `__init__`) for a class that's mainly just a container of named fields.

```python
    source: str
    category: str
    company: str
    role: str
    raw_location: str
```
Required fields every `Job` must have when created — the site it came from, category (if any), company name, role name, and the location as one combined string.

```python
    locations: List[str] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
```
Optional fields with default values. `field(default_factory=list)` means "if not given a value, start as an empty list" — this is the correct/safe way to default a dataclass field to a mutable type like a list.

```python
    link: str = ""
    posted: str = ""
```
Two more optional fields, defaulting to empty strings if not provided.

---

## Lines 159–172: `REPOS` — the two sites' info

```python
REPOS = {
    "simplify": {
        "name": "SimplifyJobs",
        "raw_url_template": "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/{branch}/README.md",
        "branches": ["dev", "master"],
    },
    "vansh": {
        "name": "vanshb03",
        "raw_url_template": "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/{branch}/README.md",
        "branches": ["dev", "main", "master"],
    },
}
```
A dictionary of dictionaries — one entry per repo, storing its display name, a URL template with a `{branch}` placeholder to fill in later, and the list of branch names to try, in priority order.

---

## Lines 175–188: `fetch_readme()`

```python
def fetch_readme(repo_key: str, timeout: int = 20) -> str:
```
Takes a repo key (`"simplify"` or `"vansh"`) and downloads its README, giving up after `timeout` seconds if the site doesn't respond.

```python
    repo = REPOS[repo_key]
    last_err = None
```
Looks up that repo's info in `REPOS`. `last_err` will remember the most recent error, in case every branch attempt fails and we need to report why.

```python
    for branch in repo["branches"]:
        url = repo["raw_url_template"].format(branch=branch)
```
Loops through each candidate branch name, filling it into the URL template (`{branch}` gets replaced).

```python
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200 and len(resp.text) > 500:
                return resp.text
```
Attempts to download that URL. `status_code == 200` means "success" in HTTP terms. The `len(resp.text) > 500` check is a sanity check — a real README is definitely longer than 500 characters, so this guards against silently accepting a GitHub error page. If both checks pass, immediately return the downloaded text and stop trying other branches.

```python
        except requests.RequestException as e:
            last_err = e
```
If the download itself fails (network error, timeout, etc.), remember the error and move on to try the next branch instead of crashing.

```python
    raise RuntimeError(
        f"Could not fetch README for {repo['name']} (tried branches {repo['branches']}): {last_err}"
    )
```
If every branch was tried and none worked, stop the program with a clear error message listing what was tried.

---

## Lines 195–262: `parse_simplify()`

Turns SimplifyJobs' raw README text into a list of `Job` objects.

```python
def parse_simplify(markdown_text: str) -> List[Job]:
    jobs: List[Job] = []
```
Starts an empty list that will be filled with `Job` objects and returned at the end.

```python
    section_pattern = re.compile(r"^##\s+[^\n]*?([A-Za-z][A-Za-z ,&/]+)\s*$", re.MULTILINE)
```
Pre-compiles a regex pattern for finding section headers like `## 💻 Software Engineering`. `re.compile` just makes it reusable/efficient. The pattern breaks down as: `^##\s+` (a line starting with `##` and a space), `[^\n]*?` (skip over any emoji/junk, non-greedily), then capture `([A-Za-z][A-Za-z ,&/]+)` — a letter followed by more letters/spaces/commas/ampersands/slashes (the actual category name), with `re.MULTILINE` making `^`/`$` match the start/end of *each line*, not just the whole string.

```python
    sections = []
    matches = list(section_pattern.finditer(markdown_text))
```
Finds every place in the text that matches a section header, and collects those matches into a list (`finditer` normally gives a lazy iterator; wrapping in `list()` lets us index into it).

```python
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)
        category = m.group(1).strip()
        sections.append((category, markdown_text[start:end]))
```
For each header match, figures out where that section's content starts (`m.end()`, right after the header) and ends (the start of the *next* header, or the end of the whole document if this is the last one). Slices out that chunk of text and stores it paired with its category name.

```python
    for category, chunk in sections:
        if "<table>" not in chunk:
            continue
```
Loops through each section. If a section doesn't contain an HTML table at all (skip sections that are just intro text), move on to the next.

```python
        soup = BeautifulSoup(chunk, "html.parser")
        for table in soup.find_all("table"):
```
Parses that chunk's HTML with BeautifulSoup, then loops through every `<table>` found in it (usually just one per section).

```python
            body = table.find("tbody") or table
```
Tries to find a `<tbody>` (table body) tag inside the table; if there isn't one, just uses the whole table instead. The `or` here means "use the left side if it's truthy/found, otherwise fall back to the right side."

```python
            last_company = ""
            for tr in body.find_all("tr"):
```
Tracks the most recently seen company name (for handling "↳" rows), then loops through every table row (`<tr>`).

```python
                cells = tr.find_all("td")
                if len(cells) < 5:
                    continue
```
Gets all the table cells (`<td>`) in this row. If there are fewer than 5 (not a real data row — maybe a header or malformed row), skip it.

```python
                company_cell, role_cell, loc_cell, app_cell, age_cell = cells[:5]
```
Unpacks the first 5 cells into named variables, in the order the table columns appear (Company, Role, Location, Application, Age).

```python
                company_text = company_cell.get_text(strip=True)
                if company_text in ("", "↳"):
                    company = last_company
                else:
                    company = company_text
                    last_company = company
```
Extracts the plain text from the company cell. If it's empty or just the "↳" arrow symbol (meaning "same as the row above"), reuse `last_company`. Otherwise, use this new company name and remember it for future rows.

```python
                role = role_cell.get_text(strip=True)
```
Simply extracts the plain text of the role cell.

```python
                details = loc_cell.find("details")
                if details:
                    loc_html = str(details)
                    loc_html = re.sub(r"<summary>.*?</summary>", "", loc_html, flags=re.DOTALL)
                    inner_soup = BeautifulSoup(loc_html, "html.parser")
                    raw_loc = inner_soup.get_text(separator="|", strip=True)
                else:
                    raw_loc = loc_cell.get_text(separator="|", strip=True)
```
Multi-location jobs are wrapped in a `<details>` (collapsible) HTML element with a `<summary>` like "8 locations". This block checks if that wrapper exists; if so, converts it back to a string, strips out the "N locations" summary text (so it doesn't get treated as a location itself), then re-parses and extracts the remaining text, using `|` as a separator between each `<br>`-separated location. If there's no `<details>` wrapper, it just extracts the cell's text directly, still using `|` as the separator.

```python
                individual_locs = [l.strip() for l in raw_loc.split("|") if l.strip()]
```
Splits that `|`-joined text back into a list of individual location strings, trimming whitespace from each and dropping any empty ones. This is a "list comprehension" — build a list by looping and filtering in one line.

```python
                link_tag = app_cell.find("a")
                link = link_tag["href"] if link_tag and link_tag.has_attr("href") else ""
```
Looks for a hyperlink (`<a>` tag) inside the "Application" cell. If found and it has an `href` attribute, grab that URL; otherwise default to an empty string.

```python
                age = age_cell.get_text(strip=True)
```
Extracts the plain text of the "posted X days ago" cell.

```python
                all_states = set()
                for loc in individual_locs:
                    all_states.update(extract_states_from_location(loc))
```
Starts an empty set, then for every individual location string in this row, runs `extract_states_from_location` on it and merges the results into the set (`.update()` adds all items from another collection).

```python
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
```
Builds a `Job` object with everything gathered from this row and adds it to the `jobs` list. `raw_location` joins all individual locations back into one comma-separated display string (or falls back to the original text if the list ended up empty). `sorted(all_states)` converts the set into an alphabetically sorted list.

```python
    return jobs
```
After all sections/tables/rows are processed, returns the complete list of `Job` objects.

---

## Lines 269–277: `split_md_row()`

A small helper used by `parse_vansh()`.

```python
def split_md_row(line: str) -> List[str]:
    """Split a markdown table row on unescaped pipes, trimming the ends."""
    line = line.strip()
```
Trims whitespace from the whole line first.

```python
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
```
A Markdown table row typically looks like `| cell1 | cell2 |`. This strips the leading and trailing `|` characters so we don't end up with an empty first/last cell after splitting.

```python
    return [c.strip() for c in line.split("|")]
```
Splits the remaining text on every `|` character, trims whitespace off each resulting piece, and returns the list of cells.

---

## Lines 280–347: `parse_vansh()`

Turns vanshb03's raw README text into a list of `Job` objects. Same end goal as `parse_simplify`, different starting format (one big Markdown table instead of multiple HTML tables).

```python
def parse_vansh(markdown_text: str) -> List[Job]:
    jobs: List[Job] = []
    lines = markdown_text.splitlines()
```
Starts an empty results list, and splits the whole README text into a list of individual lines.

```python
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("| Company") and "Location" in line:
            header_idx = i
            break
```
Searches line by line for the table's header row (something like `| Company | Role | Location | ... |`). `enumerate` gives both the index and the line text. Once found, remembers its line number and stops searching (`break`).

```python
    if header_idx is None:
        return jobs
```
If no header row was ever found (maybe the site changed format), return the empty list rather than crashing.

```python
    last_company = ""
    for line in lines[header_idx + 2:]:
```
Starts looping from *two* lines after the header — skipping the header itself and the separator row underneath it (the `|---|---|---|` line that Markdown tables always have).

```python
        if not line.strip().startswith("|"):
            if line.strip() == "":
                continue
            else:
                break
```
If a line doesn't start with `|`, it's either a blank line between rows (skip it and keep going) or it means the table has ended entirely (stop the loop with `break`).

```python
        cells = split_md_row(line)
        if len(cells) < 5:
            continue
```
Splits this row into cells using the helper from earlier. If there aren't at least 5 cells, it's not a valid data row — skip it.

```python
        company_raw, role_raw, loc_raw, app_raw, posted_raw = cells[:5]
```
Names the first 5 cells according to their column meaning.

```python
        company_soup = BeautifulSoup(company_raw, "html.parser")
        company_text = company_soup.get_text(strip=True)
        if company_text in ("", "↳"):
            company = last_company
        else:
            company = company_text
            last_company = company
```
Same "↳ means reuse the last company" logic as in `parse_simplify`, except this cell might contain raw HTML (like a link tag), so it's run through BeautifulSoup first to strip any tags and leave just the visible text.

```python
        role = BeautifulSoup(role_raw, "html.parser").get_text(strip=True)
```
Strips any HTML out of the role cell, keeping just the text.

```python
        details_match = re.search(r"<details>.*?</details>", loc_raw, re.DOTALL)
```
Checks whether this location cell contains a `<details>...</details>` block (used for multi-location listings), searching across multiple lines if needed (`re.DOTALL` makes `.` match newlines too).

```python
        if details_match:
            inner = details_match.group(0)
            inner = re.sub(r"<summary>.*?</summary>", "", inner, flags=re.DOTALL)
            inner = inner.replace("<details>", "").replace("</details>", "")
        else:
            inner = loc_raw
```
If a `<details>` block was found, grab that whole matched text, remove its `<summary>...</summary>` part (the "N locations" label), then strip the leftover `<details>`/`</details>` tags themselves. If there was no `<details>` block, just use the cell's raw text as-is.

```python
        inner = inner.replace("</br>", "|").replace("<br>", "|").replace("<br/>", "|")
```
Replaces every variant of an HTML line-break tag with a `|` character, so multiple locations that were visually separated by `<br>` tags become separable by splitting on `|` later.

```python
        inner_text = BeautifulSoup(inner, "html.parser").get_text(separator="|", strip=True)
```
Runs the remaining text through BeautifulSoup to strip out any other leftover HTML tags, using `|` as the separator between distinct text chunks (as a backup, in case any locations were separated by tags other than `<br>`).

```python
        individual_locs = [l.strip() for l in inner_text.split("|") if l.strip()]
```
Splits on `|` into the final list of individual, trimmed, non-empty location strings.

```python
        link_match = re.search(r'href="([^"]+)"', app_raw)
        link = link_match.group(1) if link_match else ""
```
Uses a regex to find an `href="..."` attribute inside the raw "Application" cell text, and pulls out just the URL between the quotes. If none is found, defaults to an empty string.

```python
        posted = BeautifulSoup(posted_raw, "html.parser").get_text(strip=True)
```
Strips HTML from the "posted" cell, keeping just the visible text.

```python
        all_states = set()
        for loc in individual_locs:
            all_states.update(extract_states_from_location(loc))
```
Same as in `parse_simplify` — collects every state mentioned across all this row's locations into one set.

```python
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
```
Builds a `Job` from everything gathered and adds it to the list. `category` is always `""` here since vanshb03's README doesn't split listings into categories the way SimplifyJobs does.

```python
    return jobs
```
Returns the finished list once every line has been processed.

---

## Lines 354–364: `filter_jobs()`

```python
def filter_jobs(jobs: List[Job], wanted_states: List[str], include_remote: bool) -> List[Job]:
    wanted = set(wanted_states)
```
Converts the list of states you asked for into a set (sets make "is X in here?" checks fast).

```python
    out = []
    for job in jobs:
        job_states = set(job.states)
```
Starts an empty results list, then for every job, turns its list of matched states into a set too.

```python
        if include_remote and "REMOTE" in job_states:
            out.append(job)
            continue
```
If you passed `--include-remote` and this job is tagged as remote, include it immediately and skip to the next job (`continue`) — no need to check states further.

```python
        if job_states & wanted:
            out.append(job)
```
The `&` operator between two sets gives their *intersection* — the states they have in common. If that intersection is non-empty (i.e., this job is located in at least one state you asked for), include the job.

```python
    return out
```
Returns the filtered list.

---

## Lines 367–387: `print_table()` and `format_table_lines()`

```python
def print_table(jobs: List[Job]) -> None:
    for line in format_table_lines(jobs):
        print(line)
```
Gets the formatted text lines from `format_table_lines` and prints each one to the terminal.

```python
def format_table_lines(jobs: List[Job]) -> List[str]:
    """Build the same lines print_table() prints, but as a list of strings
    so they can be sent to the terminal or a file."""
    lines = []
    if not jobs:
        lines.append("No matching jobs found.")
        return lines
```
Starts an empty list of text lines. If there are no jobs to show, add a single "no results" message and return early.

```python
    for job in jobs:
        cat = f" [{job.category}]" if job.category else ""
        states = ", ".join(job.states) if job.states else "?"
```
For each job: builds a `" [Category]"` string only if the job has a category (otherwise empty string), and joins the matched states into a comma-separated string (or `"?"` if somehow none were found).

```python
        lines.append(f"[{job.source}]{cat} {job.company} — {job.role}")
        lines.append(f"    Location(s): {job.raw_location}  (matched: {states})")
        lines.append(f"    Posted: {job.posted}    Apply: {job.link}")
        lines.append("")
```
Adds four lines per job: a header line (source, category, company, role), the location line, the posted-date/link line, and a blank line as a spacer between job entries.

```python
    lines.append(f"Total: {len(jobs)} matching job(s)")
    return lines
```
After all jobs are added, appends a final summary line and returns the complete list of text lines.

---

## Lines 390–394: `write_txt()`

```python
def write_txt(jobs: List[Job], path: str) -> None:
    lines = format_table_lines(jobs)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {len(jobs)} job(s) to {path}")
```
Reuses the same formatted lines as `print_table`, but instead of printing them, opens a file at `path` in write mode (`"w"` — creates it fresh or overwrites an existing one), joins all the lines with newline characters, writes that whole block of text at once, then confirms to the terminal that the file was written. The `with open(...) as f:` pattern automatically closes the file when done, even if something goes wrong partway through.

---

## Lines 397–406: `write_csv()`

```python
def write_csv(jobs: List[Job], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
```
Opens the file for writing (`newline=""` is required by Python's `csv` module to avoid extra blank lines on some systems), and wraps it in a `csv.writer` object that knows how to format rows properly (handling commas inside values, etc.).

```python
        writer.writerow(["Source", "Category", "Company", "Role", "Location", "Matched States", "Posted", "Link"])
```
Writes the header row — the column titles — as the first line of the CSV.

```python
        for job in jobs:
            writer.writerow([
                job.source, job.category, job.company, job.role,
                job.raw_location, ", ".join(job.states), job.posted, job.link,
            ])
```
For each job, writes one row with its fields in the same order as the header, converting the `states` list into a comma-joined string since a CSV cell holds plain text, not a list.

```python
    print(f"Wrote {len(jobs)} job(s) to {path}")
```
Confirms the file was written, once the `with` block closes and flushes the file to disk.

---

## Lines 413–477: `main()`

The function that actually runs when you launch the script.

```python
def main():
    parser = argparse.ArgumentParser(
        description="Filter Summer 2027 internship listings by US state.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
```
Creates an argument parser — the thing that reads and validates your `--states CA NY` style command-line flags. `epilog=__doc__` means the big docstring from the top of the file gets shown at the bottom of `--help` output. `RawDescriptionHelpFormatter` tells argparse not to auto-reformat/word-wrap that text.

```python
    parser.add_argument("--states", nargs="+", help="...")
```
Defines the `--states` flag. `nargs="+"` means "one or more values must follow" (so `--states CA NY TX` all get collected into a list).

```python
    parser.add_argument("--include-remote", action="store_true", help="...")
```
Defines `--include-remote` as a flag with no value needed — if present, `args.include_remote` becomes `True`; if absent, it defaults to `False`.

```python
    parser.add_argument("--repo", choices=["simplify", "vansh", "both"], default="both", help="...")
```
Defines `--repo`, restricted to one of three allowed values, defaulting to `"both"` if not specified.

```python
    parser.add_argument("--output", choices=["table", "csv", "txt"], default="table", help="...")
    parser.add_argument("--outfile", default="filtered_jobs", help="...")
    parser.add_argument("--list-states", action="store_true", help="...")
```
Similarly defines the output format flag, the base filename flag, and the "just list valid states and quit" flag.

```python
    args = parser.parse_args()
```
Actually reads whatever was typed on the command line and stores all the parsed values in `args` (so `args.states`, `args.repo`, etc. become accessible).

```python
    if args.list_states:
        for abbr, name in sorted(US_STATES.items()):
            print(f"{abbr}: {name}")
        return
```
If `--list-states` was passed, loop through every state (sorted alphabetically by abbreviation) and print it, then exit the function immediately (`return`) — nothing else in `main()` runs.

```python
    if not args.states:
        parser.error("--states is required (or use --list-states to see valid values)")
```
If `--states` wasn't provided at all, `parser.error(...)` prints an error message and exits the whole program (argparse's error method always exits).

```python
    wanted_states = []
    for s in args.states:
        code = normalize_state_query(s)
        if not code:
            print(f"Warning: '{s}' is not a recognized US state, skipping.", file=sys.stderr)
            continue
        wanted_states.append(code)
```
Builds a clean list of valid state codes from whatever you typed. For each input, tries to normalize it; if it doesn't resolve to a real state, prints a warning (to `stderr`, the "error output" stream, so it doesn't get mixed into actual results) and skips it; otherwise adds the valid code to the list.

```python
    if not wanted_states:
        sys.exit("No valid states given. Use --list-states to see valid values.")
```
If none of your inputs turned out to be valid states, stop the program with a clear message.

```python
    all_jobs: List[Job] = []

    if args.repo in ("simplify", "both"):
        print("Fetching SimplifyJobs/Summer2027-Internships...", file=sys.stderr)
        md = fetch_readme("simplify")
        all_jobs.extend(parse_simplify(md))
```
Starts an empty combined list. If you asked for the Simplify repo (or "both"), prints a status message, downloads its README, parses it into `Job` objects, and adds all of them into `all_jobs`.

```python
    if args.repo in ("vansh", "both"):
        print("Fetching vanshb03/Summer2027-Internships...", file=sys.stderr)
        md = fetch_readme("vansh")
        all_jobs.extend(parse_vansh(md))
```
Same thing for the vanshb03 repo, if requested.

```python
    print(f"Parsed {len(all_jobs)} total listings. Filtering for: {', '.join(wanted_states)}"
          + (" + Remote" if args.include_remote else ""), file=sys.stderr)
```
Prints a status line summarizing how many total listings were parsed and which states you're filtering for, adding "+ Remote" to that message if you passed `--include-remote`.

```python
    matched = filter_jobs(all_jobs, wanted_states, args.include_remote)
```
Runs the actual filtering, narrowing `all_jobs` down to just the ones matching your criteria.

```python
    if args.output in ("csv", "txt"):
        os.makedirs("output", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = args.output
        full_path = os.path.join("output", f"{args.outfile}_{timestamp}.{ext}")
```
If you asked for a file output, first makes sure an `output/` folder exists (`exist_ok=True` means "don't error if it's already there"), gets the current date/time formatted as `YYYYMMDD_HHMMSS`, and builds the full file path by combining the folder, your base filename, the timestamp, and the correct extension.

```python
        if args.output == "csv":
            write_csv(matched, full_path)
        else:
            write_txt(matched, full_path)
    else:
        print_table(matched)
```
Calls the matching writer function for the chosen format, or — if you didn't ask for a file at all — just prints the results to the terminal instead.

```python
if __name__ == "__main__":
    main()
```
A standard Python pattern: this block only runs `main()` if the file is being run directly (`python3 internship_filter.py`), not if it's imported as a module into some other script. `__name__` is a special variable Python sets automatically — it equals `"__main__"` only when the file is the one you executed.
