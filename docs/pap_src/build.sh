#!/bin/sh
# Regenerates docs/pap_diagrams.pdf from the .dot sources in this folder.
# Requires graphviz (dot) and pypdf (pip install pypdf).
set -e
cd "$(dirname "$0")"

dot -Tpdf -o visitor_flow.pdf visitor_flow.dot
dot -Tpdf -o technical_flow.pdf technical_flow.dot

python3 - << 'PY'
from pypdf import PdfWriter, PdfReader
w = PdfWriter()
for f in ["visitor_flow.pdf", "technical_flow.pdf"]:
    for p in PdfReader(f).pages:
        w.add_page(p)
with open("../pap_diagrams.pdf", "wb") as out:
    w.write(out)
PY

rm -f visitor_flow.pdf technical_flow.pdf
echo "Wrote ../pap_diagrams.pdf"
