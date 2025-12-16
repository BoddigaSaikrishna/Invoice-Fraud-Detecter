# Agentic Audit — Government Audit & Fraud Prevention (Prototype)

This repository contains a minimal, local prototype of an Agentic AI Government Audit
and Fraud Prevention system. It demonstrates a pipeline of lightweight agents:

- DocumentAgent: normalize parsed documents
- FraudAgent: duplicate & inflated price heuristics
- ComplianceAgent: rule checks against simple thresholds
- VendorAgent: basic vendor risk scoring
- SummaryAgent: aggregates findings into an audit summary

This is a scaffold and does not call real Gemini/Vertex AI services. Replace
stubs with real API integrations when ready.

Quick start

1. Create an environment and install dependencies:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2. Run the sample pipeline:

```bash
python -m agentic_audit.runner
```

3. Output: `agentic_audit/last_report.json`

Exporting report

You can export the last run to CSV and HTML using the included CLI:

```bash
python -m agentic_audit.tools.export_report --report agentic_audit/last_report.json --outdir exports
```

This writes `exports/report.csv` and `exports/report.html`.

Quick preview

You can preview the exported HTML report locally with a tiny HTTP server:

```bash
# from the project root, with your venv active
python -m agentic_audit.tools.serve_report --outdir exports
```

This opens `http://localhost:8000/report.html` in your default browser.

Dashboard (upload + scan)

Start the dashboard to upload invoice JSON files and run fraud/compliance checks:

```bash
# with your venv active
python -m agentic_audit.tools.dashboard
```

Open http://127.0.0.1:5000 in your browser. Upload a JSON invoice (single object or an array of invoices) and the dashboard will run the pipeline and produce exports in `exports/`.

Next steps

- Add real Gemini Vision OCR calls in `agents/document_agent.py`.
- Replace rule-based heuristics with ML models (Vertex AI) in `agents/fraud_agent.py` and `agents/vendor_agent.py`.
- Add a web dashboard and alerting hooks for officers.
