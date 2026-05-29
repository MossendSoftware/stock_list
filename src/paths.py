"""Project paths, anchored to the repo root so scripts work from any CWD.

  data/   committed inputs + scraped data (stocks, JSON reports, tickr/data)
  output/ generated HTML/PDF/charts (gitignored; rebuild with `make build`)
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
ENV = ROOT / ".env"
