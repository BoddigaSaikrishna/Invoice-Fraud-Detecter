from typing import List, Dict


class VendorAgent:
    """Evaluates vendors and provides a risk score based on history.

    This is a placeholder for a system that would use transaction history,
    external data, and ML models to score vendors.
    """

    def run(self, records: List[Dict]) -> Dict:
        by_vendor = {}
        for r in records:
            v = r.get("vendor") or "<unknown>"
            entry = by_vendor.setdefault(v, {"count": 0, "total_amount": 0.0})
            entry["count"] += 1
            entry["total_amount"] += float(r.get("amount", 0))

        scores = {}
        for v, s in by_vendor.items():
            avg = s["total_amount"] / s["count"] if s["count"] else 0
            # Simple heuristic: higher average and fewer transactions => higher risk
            score = min(100, int((avg / 10000.0) * 50 + max(0, 50 - s["count"])))
            scores[v] = {"score": score, "count": s["count"], "total_amount": s["total_amount"]}

        return {"vendor_scores": scores}
