"""Document Understanding Agent (stubbed)."""
from typing import List, Dict


class DocumentAgent:
    """Parses document-like inputs into structured transaction records.

    In production this would call Gemini Vision / OCR + parsers. Here we
    accept already-structured JSON and normalize fields.
    """

    def run(self, documents: List[Dict]) -> List[Dict]:
        normalized = []
        for d in documents:
            rec = {
                "invoice_id": d.get("invoice_id") or d.get("invoice_number"),
                "vendor": d.get("vendor"),
                "amount": float(d.get("amount", 0)),
                "currency": d.get("currency", "USD"),
                "date": d.get("date"),
                "items": d.get("items", []),
                "raw": d,
            }
            normalized.append(rec)
        return normalized
