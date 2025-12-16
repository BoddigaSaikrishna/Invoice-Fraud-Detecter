from typing import List, Dict


class ComplianceAgent:
    """Simple compliance checks against mock government rules.

    Rules here are illustrative: max single payment, required fields, allowed categories.
    """

    MAX_SINGLE_PAYMENT = 100000.0
    REQUIRED_FIELDS = ["invoice_id", "vendor", "amount", "date"]

    def run(self, records: List[Dict]) -> Dict:
        violations = []
        for r in records:
            missing = [f for f in self.REQUIRED_FIELDS if not r.get(f)]
            if missing:
                violations.append({"invoice_id": r.get("invoice_id"), "missing_fields": missing})

            amt = r.get("amount", 0)
            if amt > self.MAX_SINGLE_PAYMENT:
                violations.append({"invoice_id": r.get("invoice_id"), "violation": "exceeds_max_single_payment", "amount": amt})

        return {"violations": violations}
