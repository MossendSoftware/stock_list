# stock-list — team toolkit
# Data pipeline (scrape -> JSON -> HTML), a local server, and terminal views.
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
scrape: ## Scrape the full Lightyear stock universe -> stocks.csv
	$(RUN) scrape.py

.PHONY: buckets
buckets: ## Split stocks.csv / stocks_simple.csv into market-cap buckets
	$(RUN) buckets.py stocks.csv buckets
	$(RUN) buckets.py stocks_simple.csv buckets_simple

.PHONY: money
money: ## Fetch broad-money series from FRED -> money_supply.json (needs FRED_API_KEY)
	$(RUN) fetch_money.py

.PHONY: index-data
index-data: ## Compute index real returns -> index_report.json
	$(RUN) index_report.py

.PHONY: country-data
country-data: ## Fetch country macro -> country_report.json (needs FRED_API_KEY)
	$(RUN) country_data.py

.PHONY: screener-scrape
screener-scrape: ## Capture FT financials for bucketed micro-caps (resumable; needs FT_COOKIE)
	$(RUN) tickr_scrape.py

.PHONY: refresh
refresh: scrape buckets money index-data country-data screener-scrape build ## Full refresh: re-scrape everything then rebuild HTML

# ── build (offline; render JSON -> HTML/PDF) ───────────────────────────────
.PHONY: report
report: ## Render the index-returns report -> results/index.html + PDF
	$(RUN) report_html.py
	$(RUN) report_pdf.py

.PHONY: country-report
country-report: ## Render country pages + charts -> country/*.html, country/img/*.png
	$(RUN) country_report.py

.PHONY: screener-render
screener-render: ## Render the micro-cap screener -> tickr/*.html
	$(RUN) tickr_render.py

.PHONY: build
build: report country-report screener-render ## Rebuild all HTML from existing JSON (no network)

# ── serve ──────────────────────────────────────────────────────────────────
.PHONY: serve
serve: ## Serve the dashboards locally (PORT=8000 by default)
	$(RUN) serve.py $(PORT)

# ── terminal views (read existing data; no network) ────────────────────────
.PHONY: indices
indices: ## Print the index real-returns table
	$(RUN) cli.py indices

.PHONY: countries
countries: ## Print the country macro overview (CODE=US for one country)
	$(RUN) cli.py countries $(CODE)

.PHONY: screener-table
screener-table: ## Print the screener table (FILTER=net-net SORT=cap LIMIT=20)
	$(RUN) cli.py screener $(if $(FILTER),--filter $(FILTER)) $(if $(SORT),--sort $(SORT)) $(if $(LIMIT),--limit $(LIMIT))

.PHONY: ticker
ticker: ## Print one ticker's signals (SYM=VYNE)
	$(RUN) cli.py ticker $(SYM)

.PHONY: plot-country
plot-country: ## ASCII chart: market cap vs money supply (CODE=US)
	$(RUN) cli.py plot country $(CODE)

.PHONY: plot-indices
plot-indices: ## ASCII bar chart of index return multiples (METRIC=m2|cpi|nominal)
	$(RUN) cli.py plot indices $(if $(METRIC),--metric $(METRIC))

# ── housekeeping ───────────────────────────────────────────────────────────
.PHONY: clean
clean: ## Remove generated HTML/PDF/chart output (keeps scraped JSON/CSV)
	rm -rf results/*.html country/*.html country/report/*.html country/img/*.png \
	       tickr/*.html index_report.pdf

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
