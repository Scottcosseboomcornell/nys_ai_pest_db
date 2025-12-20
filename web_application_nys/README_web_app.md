# NYSPAD (New York State) Pesticide Label Web Application

This folder contains the **New York State (NYS)** pesticide label web application.

It is intentionally separate from `web_application_old/` (which targets the federal/EPA label dataset).

## What this app does (current)

- **Homepage** (`/`) with a link into the NYS pesticide database
- **NYS Pesticide Database UI** (`/nys-pesticide-database`)
- **JSON-backed API** reading pesticide records from this repo’s `altered_json/` directory

## Data source

By default, the app loads JSON files from:

- `../altered_json` (relative to `web_application_nys/`)

You can override the JSON directory with an environment variable:

- `NYS_OUTPUT_JSON_DIR=/absolute/or/relative/path/to/output_json`

An example environment file is provided at `env.example`.

## Local development

### 1) Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Run the dev server (auto-reload)

```bash
python run_dev.py
```

Then open:
- `http://127.0.0.1:5051/`
- `http://127.0.0.1:5051/nys-pesticide-database`

## API endpoints (current)

- `GET /api/health` - basic health + record count
- `GET /api/stats` - dataset stats
- `GET /api/pesticides?page=1&per_page=50` - paginated list
- `GET /api/search?q=<query>&type=both` - simple search
- `GET /api/pesticide/<epa_reg_no>` - details by EPA registration number (from JSON content)

Search `type` values:
- `epa_reg_no`
- `trade_Name`
- `active_ingredient`
- `company`
- `both`

## Long-term “commercial-ready” direction (later)

This repo will likely add these once the product shape stabilizes:

- Gunicorn workers + process manager
- Reverse proxy + HTTPS (Nginx or AWS ALB)
- Authentication/authorization (if needed)
- Rate limiting, caching, background jobs
- Monitoring + error tracking (structured logs, Sentry)

For now, this folder is optimized for fast local iteration and correctness.


#######
Features immediately desired for the web_applicaiton_nys
- DONE: Filtering by crop target typ and target 
- DONE: search filtering
- DONE: info page with details about the data and applicaiton
- DONE: able to click on pesticides in the tables to see the modal view with more details on rates, and pesticide safety details 

Medium-term features
- DONE: Users can access the pdfs of the labels


Long-term features
- User login and backend hosting by supabase
- User data table of their crops, blocks, and varieties and acreage for each and projected harvest dates
- Users can select pesticides from the search and filtering and make plans for applications according the pesticide rates, REI, and PHI
    - user crop information will be used to caluclate the amounts of product needed and water needed to treat their crop
- User application data will be stored in another table that will be an application log, showing the date and time of planned applications, selected rate, amount of product, amount of water, and rei, and notes
    - ability to export as excel or pdf
- label viewer tool that finds the location in the label where the datapoints were retrieved and scrolls to that page of the label for easy double checking

Features not committed to:
- Users can download the filtered pesticide tables, and the information from the modal views
