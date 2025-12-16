from typing import List, Dict, Any


class FraudAgent:
    """Detects simple fraud patterns: duplicates, inflated prices, fake vendors.

    This is a lightweight rule-based proxy for more advanced ML agents.
    """

    def run(self, records: List[Dict[str, Any]]) -> Dict:
        findings = {"duplicates": [], "inflated": [], "fake_vendors": []}
        seen_ids = {}
        amounts = [r.get("amount", 0) for r in records]
        avg = sum(amounts) / len(amounts) if amounts else 0

        for r in records:
            inv = r.get("invoice_id")
            if inv:
                if inv in seen_ids:
                    findings["duplicates"].append({"invoice_id": inv, "first": dict(seen_ids[inv]), "duplicate": dict(r)})
                else:
                    # store a copy to avoid keeping references to the original record objects
                    seen_ids[inv] = dict(r)

            amt = r.get("amount", 0)
            if avg and amt > avg * 4:
                findings["inflated"].append({"invoice_id": inv, "amount": amt, "avg": avg})

            vendor = (r.get("vendor") or "").lower()
            if vendor and ("unknown" in vendor or "test" in vendor or len(vendor) < 3):
                findings["fake_vendors"].append({"invoice_id": inv, "vendor": r.get("vendor")})

        return findings
