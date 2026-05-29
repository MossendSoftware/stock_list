# stock-list — team toolkit
# Data pipeline (scrape -> data/ JSON -> output/ HTML), a local server, and
# terminal views. Layout: src/ code, data/ inputs, output/ generated (gitignored).
# Scrape targets need a .env with FRED_API_KEY and FT_COOKIE. See README.

PORT ?= 8000
RUN  := uv run

.DEFAULT_GOAL := help

# ── setup ────────────────────────────────────────────────────────────────
.PHONY: install
install: ## Sync dependencies into the uv venv
	uv sync

# ── data refresh (network; scrapes need .env secrets) ──────────────────────
.PHONY: scrape
scrape: ## Scrape the full Lightyear stock universe -> data/stocks.csv
	$(RUN) src/scrape.py

.PHONY: buckets
buckets: ## Split stocks.csv / stocks_simple.csv into market-cap buckets
	$(RUN) src/buckets.py data/stocks.csv data/buckets
	$(RUN) src/buckets.py data/stocks_simple.csv data/buckets_simple

.PHONY: money
money: ## Fetch broad-money series from FRED -> data/money_supply.json (needs FRED_API_KEY)
	$(RUN) src/fetch_money.py

.PHONY: index-data
index-data: ## Compute index real returns -> data/index_report.json
	$(RUN) src/index_report.py

.PHONY: country-data
country-data: ## Fetch country macro -> data/country_report.json (needs FRED_API_KEY)
	$(RUN) src/country_data.py

.PHONY: screener-scrape
screener-scrape: ## Capture FT financials for bucketed micro-caps (resumable; needs FT_COOKIE)
	$(RUN) src/tickr_scrape.py

.PHONY: refresh
refresh: scrape buckets money index-data country-data screener-scrape build ## Full refresh: re-scrape everything then rebuild HTML

# ── build (offline; render data/ JSON -> output/ HTML/PDF) ─────────────────
.PHONY: report
report: ## Render the index-returns report -> output/results/index.html + PDF
	$(RUN) src/report_html.py
	$(RUN) src/report_pdf.py

.PHONY: country-report
country-report: ## Render country pages + charts -> output/country/
	$(RUN) src/country_report.py

.PHONY: screener-render
screener-render: ## Render the micro-cap screener -> output/tickr/
	$(RUN) src/tickr_render.py

.PHONY: build
build: report country-report screener-render ## Rebuild all HTML from existing JSON (no network)

# ── serve ──────────────────────────────────────────────────────────────────
.PHONY: serve
serve: ## Serve the dashboards locally (PORT=8000 by default)
	$(RUN) src/serve.py $(PORT)

# ── terminal views (read existing data; no network) ────────────────────────
.PHONY: indices
indices: ## Print the index real-returns table
	$(RUN) src/cli.py indices

.PHONY: countries
countries: ## Print the country macro overview (CODE=US for one country)
	$(RUN) src/cli.py countries $(CODE)

.PHONY: screener-table
screener-table: ## Print the screener table (FILTER=net-net SORT=cap LIMIT=20)
	$(RUN) src/cli.py screener $(if $(FILTER),--filter $(FILTER)) $(if $(SORT),--sort $(SORT)) $(if $(LIMIT),--limit $(LIMIT))

.PHONY: ticker
ticker: ## Print one ticker's signals (SYM=VYNE)
	$(RUN) src/cli.py ticker $(SYM)

.PHONY: plot-country
plot-country: ## ASCII chart per country (CODE=US METRIC=cap-money|cap-gdp)
	$(RUN) src/cli.py plot country $(CODE) $(if $(METRIC),--metric $(METRIC))

.PHONY: plot-indices
plot-indices: ## ASCII bar chart of index return multiples (METRIC=m2|cpi|nominal)
	$(RUN) src/cli.py plot indices $(if $(METRIC),--metric $(METRIC))

.PHONY: real-return
real-return: ## Real return of an equity between two dates (SYM=COST FROM=2015 TO=2026 [REGION=US])
	$(RUN) src/cli.py real-return $(SYM) $(FROM) $(TO) $(if $(REGION),--region $(REGION))

# ── housekeeping ───────────────────────────────────────────────────────────
.PHONY: clean
clean: ## Remove generated output/ (keeps committed data/)
	rm -rf output

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
