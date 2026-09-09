#!/usr/bin/env bash
# Deterministic build of the anonymized TMLR submission PDF.
set -euo pipefail
cd "$(dirname "$0")"
export SOURCE_DATE_EPOCH=1451606400
export FORCE_SOURCE_DATE=1
rm -f main_tmlr.aux main_tmlr.bbl main_tmlr.blg main_tmlr.log main_tmlr.out main_tmlr.pdf
pdflatex -interaction=nonstopmode -halt-on-error main_tmlr.tex >/dev/null
bibtex main_tmlr >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error main_tmlr.tex >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error main_tmlr.tex >/dev/null
pages=$(grep -aoE 'Output written on main_tmlr\.pdf \(([0-9]+) page' main_tmlr.log | grep -oE '[0-9]+' | head -1)
echo "main_tmlr.pdf: ${pages} pages, $(wc -c < main_tmlr.pdf) bytes, sha256 $(shasum -a 256 main_tmlr.pdf | cut -d' ' -f1)"
grep -aE 'Overfull \\hbox \([0-9]{3,}|Warning: Citation|Warning: Reference|undefined' main_tmlr.log || echo "no big-overfull / undefined-cite / undefined-ref warnings"
