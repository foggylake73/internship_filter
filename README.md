# Internship Filter

internship_filter.py

Fetches Summer 2027 internship listings from:
  - https://github.com/SimplifyJobs/Summer2027-Internships
  - https://github.com/vanshb03/Summer2027-Internships

and filters them down to postings located in one or more US states you
specify. No API keys needed -- it just reads the public README.md files.

USAGE EXAMPLES
---------------
  ### Show all CA and NY jobs from both repos, printed to the terminal
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
