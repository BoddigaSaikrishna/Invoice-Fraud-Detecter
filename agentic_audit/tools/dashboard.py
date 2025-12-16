"""Simple Flask dashboard to upload invoices and view audit reports."""
import json
import time
from pathlib import Path
from flask import Flask, request, redirect, url_for, send_from_directory
from flask import render_template_string

from agentic_audit.pipeline import Pipeline
from agentic_audit import exporter


APP = Flask(__name__)

EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)


INDEX_HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Agentic Audit Dashboard</title>
<style>body{font-family:sans-serif;margin:20px;}h1{color:#333;}form{margin:20px 0;}input[type=file]{padding:5px;}input[type=submit]{padding:8px 15px;background:#007bff;color:white;border:none;cursor:pointer;}ul{list-style:none;padding:0;}li{padding:5px 0;}</style>
</head>
<body>
<h1>Agentic Audit Dashboard</h1>
<h2>Upload Invoice(s) for Fraud Check</h2>
<form action="/upload" method="post" enctype="multipart/form-data">
  <input type="file" name="file" accept="application/json"> 
  <input type="submit" value="Upload and Scan">
</form>
<h2>Recent Reports</h2>
<ul>
{% for f in files %}
  <li><a href="/reports/{{ f }}">{{ f }}</a></li>
{% endfor %}
</ul>
</body>
</html>
"""


@APP.route("/")
def index():
    files = sorted([p.name for p in EXPORT_DIR.iterdir() if p.is_file() and p.suffix in ('.html', '.csv', '.json')])
    return render_template_string(INDEX_HTML, files=files)


@APP.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f:
        return "No file uploaded", 400

    try:
        data = json.load(f.stream)
    except Exception as e:
        return f"Failed to parse JSON: {e}", 400

    # normalize to list of documents
    docs = data if isinstance(data, list) else [data]

    pipe = Pipeline()
    report = pipe.run(docs)

    ts = int(time.time())
    base = f"report-{ts}"
    json_path = EXPORT_DIR / f"{base}.json"
    csv_path = EXPORT_DIR / f"{base}.csv"
    html_path = EXPORT_DIR / f"{base}.html"

    # write json report
    with json_path.open("w", encoding="utf-8") as jf:
        json.dump(report, jf, indent=2)

    # produce exports
    exporter.export_csv(str(json_path), str(csv_path))
    exporter.export_html(str(json_path), str(html_path))

    # also update last_report.json
    last_path = Path(__file__).resolve().parent.parent / "last_report.json"
    with last_path.open("w", encoding="utf-8") as lf:
        json.dump(report, lf, indent=2)

    return redirect(url_for('report_file', filename=html_path.name))


@APP.route('/reports/<path:filename>')
def report_file(filename):
    # serve files from exports directory
    return send_from_directory(str(EXPORT_DIR.resolve()), filename)


def create_app():
    return APP


if __name__ == '__main__':
    APP.run(host='0.0.0.0', port=5000, debug=True)
