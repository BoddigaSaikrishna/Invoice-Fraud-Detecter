from typing import Dict, Any


class SummaryAgent:
    """Aggregates findings from other agents into an audit summary."""

    def run(self, findings: Dict[str, Any]) -> Dict:
        summary = {
            "total_invoices": findings.get("meta", {}).get("total", 0),
            "fraud_alerts": 0,
            "compliance_violations": 0,
            "high_risk_vendors": [],
            # avoid embedding the entire findings object to prevent circular references
            "details": {"meta": findings.get("meta", {})},
        }

        fraud = findings.get("fraud", {})
        summary["fraud_alerts"] = sum(len(v) for v in fraud.values() if isinstance(v, list))

        comp = findings.get("compliance", {})
        summary["compliance_violations"] = len(comp.get("violations", []))

        vendor_scores = findings.get("vendor", {}).get("vendor_scores", {})
        for v, s in vendor_scores.items():
            if s.get("score", 0) >= 70:
                summary["high_risk_vendors"].append({"vendor": v, "score": s.get("score")})

        return summary
