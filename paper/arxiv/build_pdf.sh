#!/usr/bin/env bash
# Deterministic manuscript build. Produces a byte-reproducible main.pdf
# (fixed PDF /CreationDate and /ModDate via SOURCE_DATE_EPOCH) on the same
# TeX Live. Run gen_tables.py first so generated/* is current.
#
#   uv run python paper/arxiv/gen_tables.py
#   bash paper/arxiv/build_pdf.sh
#   uv run python paper/arxiv/audit_numbers.py
#   uv run python paper/arxiv/build_arxiv_tar.py
set -euo pipefail
cd "$(dirname "$0")"

export SOURCE_DATE_EPOCH=1451606400   # 2016-01-01T00:00:00Z, fixed
export FORCE_SOURCE_DATE=1

rm -f main.aux main.bbl main.blg main.log main.out main.pdf
pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null
bibtex main >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null

pages=$(grep -oE 'Output written on main\.pdf \([0-9]+ pages' main.log | grep -oE '[0-9]+' | head -1)
echo "main.pdf: ${pages} pages, $(wc -c < main.pdf) bytes, sha256 $(shasum -a 256 main.pdf | cut -d' ' -f1)"
grep -E 'Overfull \\hbox|Warning: Citation|Warning: Reference|undefined' main.log || echo "no overfull/undefined warnings"
