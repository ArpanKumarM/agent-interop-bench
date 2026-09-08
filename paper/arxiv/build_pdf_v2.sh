#!/usr/bin/env bash
# Deterministic v2 manuscript build. Byte-reproducible main_v2.pdf on the
# same TeX Live (fixed PDF /CreationDate and /ModDate via SOURCE_DATE_EPOCH).
#
#   bash paper/arxiv/build_pdf_v2.sh
#   uv run python paper/arxiv/audit_phase8_numbers.py   # numeric + gate audit
set -euo pipefail
cd "$(dirname "$0")"

export SOURCE_DATE_EPOCH=1451606400   # 2016-01-01T00:00:00Z, fixed
export FORCE_SOURCE_DATE=1

rm -f main_v2.aux main_v2.bbl main_v2.blg main_v2.log main_v2.out main_v2.pdf
pdflatex -interaction=nonstopmode -halt-on-error main_v2.tex >/dev/null
bibtex main_v2 >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error main_v2.tex >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error main_v2.tex >/dev/null

pages=$(grep -aoE 'Output written on main_v2.pdf .[0-9]+ pages' main_v2.log | grep -oE '[0-9]+ pages' | grep -oE '[0-9]+')
echo "main_v2.pdf: ${pages} pages, $(wc -c < main_v2.pdf) bytes, sha256 $(shasum -a 256 main_v2.pdf | cut -d' ' -f1)"
grep -aE 'Overfull \\hbox|Warning: Citation|Warning: Reference|undefined' main_v2.log \
  || echo "no overfull/undefined warnings"
