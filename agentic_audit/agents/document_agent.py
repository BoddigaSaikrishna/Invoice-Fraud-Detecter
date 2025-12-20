"""Document Understanding Agent with optional Google Vision (Gemini/Vertex) integration.

This agent normalizes invoice-like documents. If `USE_GEMINI` or
`ENABLE_GEMINI` environment variable is set and Google Cloud credentials
are available, it will attempt to run OCR via `google.cloud.vision`.
It falls back to local OCR using Pillow + pytesseract when Google Vision
is not available or not configured.
"""
from typing import List, Dict, Optional
import os
from pathlib import Path

try:
    from google.cloud import vision
    GCV_AVAILABLE = True
except Exception:
    GCV_AVAILABLE = False

try:
    from PIL import Image
    import pytesseract
    LOCAL_OCR_AVAILABLE = True
except Exception:
    LOCAL_OCR_AVAILABLE = False


def ocr_with_gcloud_image(file_path: str) -> Optional[str]:
    """Run Google Cloud Vision OCR on a local file and return extracted text."""
    if not GCV_AVAILABLE:
        return None
    try:
        client = vision.ImageAnnotatorClient()
        with open(file_path, "rb") as f:
            content = f.read()
        image = vision.Image(content=content)
        # Use DOCUMENT_TEXT_DETECTION for richer OCR
        resp = client.document_text_detection(image=image)
        if resp.error.message:
            print(f"[GCV] OCR error: {resp.error.message}")
            return None
        return resp.full_text_annotation.text if resp.full_text_annotation else None
    except Exception as e:
        print(f"[GCV] Exception during OCR: {e}")
        return None


def ocr_with_pytesseract(file_path: str) -> Optional[str]:
    """Run local OCR via Pillow + pytesseract."""
    if not LOCAL_OCR_AVAILABLE:
        return None
    try:
        img = Image.open(file_path)
        img = img.convert("RGB")
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        print(f"[LocalOCR] Exception: {e}")
        return None


class DocumentAgent:
    """Normalizes documents and optionally runs OCR on image/PDF files.

    Expected input: list of dicts. If a dict contains a `file_path` key,
    the agent will try to OCR that file (GCV first if enabled, then local OCR).
    If the dict already contains `invoice_id`/`vendor` fields, it will only
    normalize them.
    """

    def __init__(self):
        self.use_gemini = bool(os.environ.get("USE_GEMINI") or os.environ.get("ENABLE_GEMINI"))

    def _extract_text_from_file(self, file_path: str) -> Optional[str]:
        # Try Google Cloud Vision if requested and available
        if self.use_gemini and GCV_AVAILABLE:
            txt = ocr_with_gcloud_image(file_path)
            if txt:
                return txt

        # Fallback to local OCR
        txt = ocr_with_pytesseract(file_path)
        return txt

    def run(self, documents: List[Dict]) -> List[Dict]:
        normalized = []
        for d in documents:
            try:
                rec = {}
                # If a file path is provided, try OCR first when fields missing
                file_path = d.get("file_path") or d.get("image_path")
                extracted_text = None
                if file_path and (not d.get("vendor") or not d.get("invoice_id")):
                    p = str(Path(file_path))
                    extracted_text = self._extract_text_from_file(p)

                # Simple text parsing: reuse existing helper patterns if available
                # Fall back to using fields directly
                rec["invoice_id"] = d.get("invoice_id") or d.get("invoice_number")
                rec["vendor"] = d.get("vendor")
                rec["amount"] = float(d.get("amount", 0)) if d.get("amount") is not None else 0.0
                rec["currency"] = d.get("currency") or "USD"
                rec["date"] = d.get("date")
                rec["items"] = d.get("items", [])
                rec["raw"] = d

                # If OCR produced text and some fields missing, attempt lightweight parse
                if extracted_text:
                    # minimal parsing to fill vendor/invoice_id using regexes
                    import re
                    if not rec.get("invoice_id"):
                        m = re.search(r'Invoice\\s*#?:?\\s*([A-Z0-9\\-]+)', extracted_text, re.IGNORECASE)
                        if m:
                            rec["invoice_id"] = m.group(1)
                    if not rec.get("vendor"):
                        m2 = re.search(r'(?:Seller|Vendor|From|Company|Supplied by)\\s*[:\\n]\\s*([A-Za-z0-9\\s&.,-]{3,100})', extracted_text, re.IGNORECASE)
                        if m2:
                            rec["vendor"] = m2.group(1).strip()

                # Ensure defaults
                if not rec.get("invoice_id"):
                    import time
                    rec["invoice_id"] = f"INV-{int(time.time())}"
                if not rec.get("vendor"):
                    rec["vendor"] = "Unknown Vendor"

                normalized.append(rec)
            except Exception as e:
                print(f"[DocumentAgent] Error normalizing doc: {e}")
        return normalized
