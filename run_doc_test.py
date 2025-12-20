#!/usr/bin/env python
"""Quick test for agentic_audit.agents.document_agent.DocumentAgent
- Tests JSON normalization path
- Creates a synthetic image and tests local OCR (pytesseract) fallback
"""
import json
from pathlib import Path
from agentic_audit.agents.document_agent import DocumentAgent

print('Loading sample JSON...')
SAMPLE = Path('sample_invoice.json')
if SAMPLE.exists():
    docs = json.loads(SAMPLE.read_text(encoding='utf-8'))
else:
    docs = [{
        'invoice_number': 'INV-TEST-1',
        'vendor': 'Acme Office Supplies',
        'amount': 123.45,
        'date': '2025-12-20'
    }]

agent = DocumentAgent()
print('USE_GEMINI=', agent.use_gemini)
print('Running normalization on JSON docs...')
out = agent.run(docs)
print('Normalized:', json.dumps(out, indent=2)[:1000])

# Create a synthetic image containing vendor text to test local OCR
print('\nCreating synthetic image for OCR test...')
try:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (600, 200), color=(255,255,255))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.load_default()
    except Exception:
        f = None
    text = 'Invoice # INV-IMG-1\nVendor: Synthetic Vendor Co\nAmount: $99.99'
    d.text((10,10), text, fill=(0,0,0), font=f)
    tmp = Path('exports') / 'test_ocr.png'
    tmp.parent.mkdir(exist_ok=True)
    img.save(tmp)
    print('Saved test image to', tmp)

    print('Running DocumentAgent on image path (will attempt GCV then local OCR)...')
    docs_img = [{'file_path': str(tmp)}]
    out_img = agent.run(docs_img)
    print('Result:', out_img)
except Exception as e:
    print('Image OCR test skipped:', e)

print('\nDone')
