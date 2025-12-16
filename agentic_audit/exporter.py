import json
import csv
from pathlib import Path
from typing import Dict, Any


def _invoice_flags(report: Dict[str, Any]) -> Dict[str, Dict[str, bool]]:
    flags = {}
    fraud = report.get("fraud", {})
    # duplicates
    for d in fraud.get("duplicates", []):
        iid = d.get("invoice_id")
        flags.setdefault(iid, {})["duplicate"] = True

    # inflated
    for i in fraud.get("inflated", []):
        iid = i.get("invoice_id")
        flags.setdefault(iid, {})["inflated"] = True

    # fake vendors
    for f in fraud.get("fake_vendors", []):
        iid = f.get("invoice_id")
        flags.setdefault(iid, {})["fake_vendor"] = True

    # compliance
    for v in report.get("compliance", {}).get("violations", []):
        iid = v.get("invoice_id")
        flags.setdefault(iid, {})["compliance_violation"] = True

    return flags


def export_csv(report_path: str, out_path: str):
    p = Path(report_path)
    if not p.exists():
        raise FileNotFoundError(report_path)

    with p.open("r", encoding="utf-8") as f:
        report = json.load(f)

    flags = _invoice_flags(report)
    vendor_scores = report.get("vendor", {}).get("vendor_scores", {})

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["invoice_id", "vendor", "amount", "currency", "date", "items_count", "items_summary", "duplicate", "inflated", "fake_vendor", "compliance_violation", "vendor_score"]
    with out.open("w", newline='', encoding="utf-8") as csvf:
        writer = csv.DictWriter(csvf, fieldnames=fieldnames)
        writer.writeheader()
        for r in report.get("records", []):
            iid = r.get("invoice_id")
            items = r.get("items", []) or []
            items_summary = "; ".join([str(i.get("desc", "")) for i in items])
            v = r.get("vendor") or ""
            row = {
                "invoice_id": iid,
                "vendor": v,
                "amount": r.get("amount"),
                "currency": r.get("currency"),
                "date": r.get("date"),
                "items_count": len(items),
                "items_summary": items_summary,
                "duplicate": bool(flags.get(iid, {}).get("duplicate", False)),
                "inflated": bool(flags.get(iid, {}).get("inflated", False)),
                "fake_vendor": bool(flags.get(iid, {}).get("fake_vendor", False)),
                "compliance_violation": bool(flags.get(iid, {}).get("compliance_violation", False)),
                "vendor_score": vendor_scores.get(v, {}).get("score") if v else None,
            }
            writer.writerow(row)


def export_html(report_path: str, out_path: str):
    p = Path(report_path)
    if not p.exists():
        raise FileNotFoundError(report_path)

    with p.open("r", encoding="utf-8") as f:
        report = json.load(f)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    total = report.get("meta", {}).get("total", 0)
    fraud_alerts = report.get("summary", {}).get("fraud_alerts", 0)
    compliance_violations = report.get("summary", {}).get("compliance_violations", 0)

    high_risk = report.get("summary", {}).get("high_risk_vendors", [])

    html = [
        "<html>",
        "<head><meta charset=\"utf-8\"><title>Audit Report Summary</title></head>",
        "<body>",
        f"<h1>Audit Report Summary</h1>",
        f"<p>Total invoices: {total}</p>",
        f"<p>Fraud alerts: {fraud_alerts}</p>",
        f"<p>Compliance violations: {compliance_violations}</p>",
        "<h2>High Risk Vendors</h2>",
        "<ul>",
    ]

    for v in high_risk:
        html.append(f"<li>{v.get('vendor')} — score: {v.get('score')}</li>")

    html += ["</ul>", "<h2>Invoices</h2>", "<table border=1 cellpadding=4 cellspacing=0>", "<tr><th>Invoice</th><th>Vendor</th><th>Amount</th><th>Flags</th></tr>"]

    flags = _invoice_flags(report)
    for r in report.get("records", []):
        iid = r.get("invoice_id")
        v = r.get("vendor") or ""
        amt = r.get("amount")
        fflags = flags.get(iid, {})
        flag_list = ", ".join([k for k, vv in fflags.items() if vv]) if fflags else "-"
        html.append(f"<tr><td>{iid}</td><td>{v}</td><td>{amt}</td><td>{flag_list}</td></tr>")

    html += ["</table>", "</body>", "</html>"]

    out.write_text("\n".join(html), encoding="utf-8")
