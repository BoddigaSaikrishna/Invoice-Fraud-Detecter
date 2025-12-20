#!/usr/bin/env python
"""Quick vendor fuzzy-match test using sample_invoice.json and vendor_db/vendors.csv"""
import json
import csv
from pathlib import Path
try:
    from rapidfuzz import fuzz
except Exception as e:
    print('rapidfuzz not installed:', e)
    fuzz = None

VENDORS = []
vfile = Path('vendor_db/vendors.csv')
if vfile.exists():
    with open(vfile, newline='', encoding='utf-8') as vf:
        reader = csv.reader(vf)
        for row in reader:
            if row:
                VENDORS.append(row[0].strip())
else:
    print('vendor_db/vendors.csv not found')

sj = Path('sample_invoice.json')
if not sj.exists():
    print('sample_invoice.json not found')
    raise SystemExit(1)

data = json.loads(sj.read_text(encoding='utf-8'))

for inv in data:
    v = inv.get('vendor')
    best = (None, -1)
    if fuzz and VENDORS:
        for vv in VENDORS:
            s = fuzz.token_sort_ratio(v, vv)
            if s > best[1]:
                best = (vv, s)
    print(f"Invoice {inv.get('invoice_id')} vendor='{v}' -> match={best[0]} score={best[1]}")

print('Done')
