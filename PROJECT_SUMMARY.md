# Agentic AI Government Audit & Fraud Prevention System

## Overview

This is a **production-grade prototype** of an Agentic AI system for automating government financial auditing, fraud detection, and compliance monitoring. It demonstrates multi-agent collaboration powered by rule-based heuristics and designed for integration with **Gemini Vision + Vertex AI** for OCR and ML inference.

## Architecture

### Core Components

```
agentic_audit/
├── agents/                 # Specialized AI agents
│   ├── base.py            # Base agent interface
│   ├── document_agent.py   # Parses & normalizes invoices (OCR ready)
│   ├── fraud_agent.py      # Detects duplicates, inflated prices, fake vendors
│   ├── compliance_agent.py # Checks financial regulations
│   ├── vendor_agent.py     # Risk scores vendors
│   └── summary_agent.py    # Aggregates findings into audit report
├── pipeline.py            # Orchestrates agent workflow
├── exporter.py            # Exports to CSV/HTML
├── runner.py              # CLI entry point
└── tools/
    ├── export_report.py   # Export CLI
    ├── serve_report.py    # Simple HTTP server for preview
    └── simple_dashboard.py # Flask web UI (optional)
```

## Quick Start

### 1. Setup
```bash
cd C:\Users\bsaik\Desktop\HYD
python -m venv venv
venv\Scripts\activate.bat
pip install -r agentic_audit/requirements.txt
```

### 2. Run Audit Pipeline
```bash
python -m agentic_audit.runner
```
Produces: `agentic_audit/last_report.json`

### 3. Export Results
```bash
python -m agentic_audit.tools.export_report --outdir exports
```
Produces: `exports/report.csv`, `exports/report.html`

### 4. Preview Report
```bash
python -m agentic_audit.tools.serve_report --outdir exports
# Open: http://localhost:8000/report.html
```

## How It Works

### The Audit Pipeline

```
Input Invoices (JSON)
         ↓
   [Document Agent]
   - Normalizes fields
   - Validates structure
         ↓
   Records (standardized)
         ↓
    ┌────┴────┬────────┬──────────┐
    ↓         ↓        ↓          ↓
 [Fraud]  [Compliance] [Vendor] [Summary]
    ↓         ↓        ↓          ↓
 Findings    Rules    Scores    Report
    └────┬────┴────┬──────────┘
         ↓
    Audit Report (JSON/CSV/HTML)
```

### Agents & Detections

#### **Document Agent**
- Reads invoice JSON (single object or array)
- Normalizes field names: `invoice_number` → `invoice_id`
- Validates required fields: `invoice_id`, `vendor`, `amount`, `date`
- **Future:** Integrate Gemini Vision for PDF/image OCR

#### **Fraud Agent**
Detects:
- **Duplicate Invoices**: Same ID appearing multiple times
- **Inflated Prices**: Amounts > 4× average transaction
- **Fake Vendors**: Vendor names with suspicious keywords ("Unknown", "Test", too short)

#### **Compliance Agent**
Checks:
- **Max Single Payment**: Individual transactions > $100,000
- **Required Fields**: All mandatory fields present
- **Allowed Vendors**: (extensible rule set)

#### **Vendor Agent**
Scores vendors 0–100 based on:
- Transaction count (frequency)
- Average transaction amount
- Risk heuristic: high-value + low-frequency = higher risk

#### **Summary Agent**
Aggregates findings and highlights:
- Total invoices processed
- Fraud alerts (suspicious items flagged)
- Compliance violations
- High-risk vendors (score ≥ 70)

## Sample Input & Output

### Input: `sample_data/invoice1.json`
```json
[
  {
    "invoice_id": "INV-0001",
    "vendor": "Acme Supplies Ltd",
    "amount": 1200.50,
    "currency": "USD",
    "date": "2025-11-01",
    "items": [{"desc": "Office chairs", "qty": 10, "unit_price": 120.05}]
  },
  {
    "invoice_id": "INV-0002",
    "vendor": "Trusted Services",
    "amount": 50000.00,
    "currency": "USD",
    "date": "2025-11-05",
    "items": [{"desc": "Consulting", "qty": 1, "unit_price": 50000}]
  },
  {
    "invoice_id": "INV-0002",  // DUPLICATE!
    "vendor": "Trusted Services",
    "amount": 50000.00,
    "currency": "USD",
    "date": "2025-11-05",
    "items": [{"desc": "Consulting duplicate", "qty": 1, "unit_price": 50000}]
  },
  {
    "invoice_id": "INV-0003",
    "vendor": "Test",  // FAKE VENDOR!
    "amount": 1000000.00,  // EXCEEDS MAX!
    "currency": "USD",
    "date": "2025-11-10",
    "items": [{"desc": "Equipment", "qty": 1, "unit_price": 1000000}]
  }
]
```

### Output: `exports/report.csv`
```
invoice_id,vendor,amount,currency,date,items_count,duplicate,inflated,fake_vendor,compliance_violation,vendor_score
INV-0001,Acme Supplies Ltd,1200.5,USD,2025-11-01,1,False,False,False,False,55
INV-0002,Trusted Services,50000.0,USD,2025-11-05,1,True,False,False,False,100
INV-0002,Trusted Services,50000.0,USD,2025-11-05,1,True,False,False,False,100
INV-0003,Test,1000000.0,USD,2025-11-10,1,False,False,True,True,100
```

### Output: `agentic_audit/last_report.json` (Summary)
```json
{
  "meta": {"total": 4},
  "summary": {
    "total_invoices": 4,
    "fraud_alerts": 2,
    "compliance_violations": 1,
    "high_risk_vendors": [
      {"vendor": "Trusted Services", "score": 100},
      {"vendor": "Test", "score": 100}
    ]
  },
  "fraud": {
    "duplicates": [{"invoice_id": "INV-0002", ...}],
    "inflated": [],
    "fake_vendors": [{"invoice_id": "INV-0003", "vendor": "Test"}]
  },
  "compliance": {
    "violations": [{"invoice_id": "INV-0003", "violation": "exceeds_max_single_payment", "amount": 1000000}]
  },
  "vendor": {
    "vendor_scores": {
      "Acme Supplies Ltd": {"score": 55, "count": 1, "total_amount": 1200.5},
      "Trusted Services": {"score": 100, "count": 2, "total_amount": 100000.0},
      "Test": {"score": 100, "count": 1, "total_amount": 1000000.0}
    }
  }
}
```

## Next Steps: Integration & Enhancement

### 1. **Gemini Vision OCR**
Replace `document_agent.py` stub to:
```python
from google.cloud import vision
# Parse PDFs, scanned receipts, handwritten invoices
```

### 2. **Vertex AI ML Models**
Enhance fraud detection:
```python
from google.cloud import aiplatform
# Train custom models on historical fraud patterns
```

### 3. **Advanced Rules**
- Fuzzy vendor matching (detect near-duplicates)
- Regex-based vendor validation
- Geographic/currency anomaly detection
- Time-series analysis for spending patterns

### 4. **Real-time Alerts**
- Slack/email notifications for high-risk transactions
- Dashboard with live filtering & drill-down
- Audit trail & evidence preservation

### 5. **Scale to Production**
- Deploy on Cloud Run or App Engine
- Use Firestore for report history
- Implement multi-tenancy for multiple governments
- Add authentication & RBAC

## File Structure

```
HYD/
├── agentic_audit/
│   ├── agents/
│   │   ├── base.py
│   │   ├── document_agent.py
│   │   ├── fraud_agent.py
│   │   ├── compliance_agent.py
│   │   ├── vendor_agent.py
│   │   └── summary_agent.py
│   ├── tools/
│   │   ├── export_report.py
│   │   ├── serve_report.py
│   │   └── simple_dashboard.py
│   ├── sample_data/
│   │   └── invoice1.json
│   ├── pipeline.py
│   ├── exporter.py
│   ├── runner.py
│   ├── last_report.json (generated)
│   ├── __init__.py
│   └── requirements.txt
├── exports/
│   ├── report.csv (generated)
│   ├── report.html (generated)
│   └── report-{timestamp}.* (archived)
├── run.ps1 (Windows automation)
├── run.sh (Linux/Mac automation)
└── README.md (this file)
```

## Requirements

```
pandas>=2.0.0
Flask>=2.0.0
google-cloud-vision>=3.0.0  (optional, for OCR)
google-cloud-aiplatform>=1.20.0  (optional, for ML)
```

Install with:
```bash
pip install -r agentic_audit/requirements.txt
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Python not found | Install Python 3.9+ and add to PATH |
| Flask import errors | `pip install Flask==2.0.0` or higher |
| File not found | Ensure you're running from project root |
| Upload fails | Check file is valid JSON and path exists |
| Port 5000 in use | Change port in `simple_dashboard.py` or use `--port 8080` |

## Design Philosophy

✅ **Modular**: Each agent is independent & testable  
✅ **Extensible**: Add new agents/rules without touching others  
✅ **Transparent**: All findings are explainable & auditable  
✅ **Scalable**: Pipeline handles 1000s of invoices  
✅ **Production-Ready**: Error handling, logging, JSON serialization  

## License & Attribution

This system demonstrates an Agentic AI architecture for financial auditing. It is designed as a prototype for government transparency and fraud prevention.

---

**Built for:** Government Financial Audit & Fraud Prevention  
**Status:** Prototype (Ready for Gemini/Vertex AI Integration)  
**Last Updated:** December 15, 2025
