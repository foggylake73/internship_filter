# Internship Filter

`internship_filter.py` pulls Summer 2027 internship listings from two public GitHub repositories, SimplifyJobs/Summer2027-Internships and vanshb03/Summer2027-Internships, and filters them to the US states you choose. No API keys are needed because it reads the public README files.

## Requirements

- Python 3
- `requests` and `beautifulsoup4` (`pip install requests beautifulsoup4`)

## Options

| Option | What it does |
|---|---|
| `--states` | One or more states, as abbreviations or full names (`CA NY`, or `California "New York"`) |
| `--include-remote` | Also include postings marked Remote |
| `--repo` | Which repo(s) to search: `simplify`, `vansh` or `both` (default `both`) |
| `--output` | Output format: `table` (default), `csv` or `txt` |
| `--outfile` | Base name for the output file (default `filtered_jobs`); the folder, timestamp and extension are added automatically |
| `--list-states` | Print all recognized state codes and names, then exit |

## Usage examples

Show all CA and NY jobs from both repos, printed to the terminal:

```
python3 internship_filter.py --states CA NY
```

Also match "Remote" postings:

```
python3 internship_filter.py --states TX --include-remote
```

Save results to a CSV file:

```
python3 internship_filter.py --states WA OR --output csv --outfile jobs
```

Save results to a text file:

```
python3 internship_filter.py --states VA MD DC --output txt --outfile va_md_dc
```

Only check one of the two repos:

```
python3 internship_filter.py --states MA --repo simplify
```

List every state abbreviation and name the script recognizes:

```
python3 internship_filter.py --list-states
```

Full state names also work, such as `--states California "New York"`. The script maps common city shorthands used in these lists (NYC, SF, LA, DC, Bay Area) to their states.

## Output files

CSV and txt files are saved in an `output` folder, which is created if it doesn't exist. The filename is the `--outfile` name plus the date and time, for example `output/va_md_dc_20261107_101001.csv`.

The CSV columns are Source, Category, Company, Role, Location, Matched States, Posted and Link.

## Notes

- "Washington, DC" matches DC only, not Washington state.
- Branches tried: SimplifyJobs `dev`, then `master`. vanshb03 `dev`, then `main`, then `master`.
