Gemini / Vertex Integration Notes

This project supports optional integration with Google Cloud Vision (Gemini Vision / Vertex AI OCR).

Configuration
- To enable Google Cloud Vision OCR, set one of the environment variables:
  - `USE_GEMINI=1` or `ENABLE_GEMINI=1`

- Google credentials: point `GOOGLE_APPLICATION_CREDENTIALS` at a service account JSON file with Vision API permissions.

Behavior
- When enabled, `DocumentAgent` will attempt to use `google.cloud.vision`'s
  `document_text_detection` for OCR.
- If Google Vision is not available or returns no text, the agent falls back
  to local OCR using `Pillow` + `pytesseract`.

Notes
- This integration requires adding `google-cloud-vision` and optionally
  `google-cloud-aiplatform` to your environment. These are listed in
  `agentic_audit/requirements.txt` as optional dependencies.
- For production Vertex AI / Gemini model inference (beyond OCR), additional
  code using `google.cloud.aiplatform` is required; this file only implements
  OCR via Vision and a safe local fallback.

Security
- Keep service account credentials secure and do not commit them to the
  repository. Use environment variables or secret management in cloud CI.

Testing
- To test locally without GCP, ensure Tesseract is installed and run with
  `USE_GEMINI` unset so the local OCR path is used.
