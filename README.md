> ⚠️ **This application was generated with AI.**

# Berlin VHS Explorer

A client-side course browser for Berlin's [Volkshochschule (VHS)](https://www.vhsit.berlin.de/) open data feed.

A Python script downloads the official VHS course feed (JSON) and builds it into a SQLite database. A static HTML page then loads that database directly in the browser (via [sql.js](https://sql.js.org/), SQLite compiled to WebAssembly) and lets you filter/search courses — by district, keyword, date range, price, and available seats — with no backend server required.

A GitHub Actions workflow refreshes the database daily and deploys the page to GitHub Pages.

## Project structure

- `src/sqlite_builder.py` — downloads the VHS open data feed and builds `vhs_courses.db`
- `src/index.html` — the static client-side explorer UI (reads the SQLite DB in-browser)
- `docs/` — the published version of the site (served via GitHub Pages: `index.html` + `vhs_courses.db`)
- `.github/workflows/update_data.yml` — scheduled job that rebuilds the DB and deploys `docs/` to GitHub Pages

## Most important commands

**Rebuild the SQLite database from the live feed** (requires `pandas`):

```bash
pip install pandas
python src/sqlite_builder.py
```

**Serve the site locally** to browse the DB in your browser:

```bash
cd docs   # or: cd src
python -m http.server 8000
# then open http://localhost:8000
```

**Manually trigger the deploy pipeline** on GitHub (instead of waiting for the daily cron):

```bash
gh workflow run update_data.yml
```
