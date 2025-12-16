"""Simple Flask dashboard to upload invoices and view audit reports."""
import json
import time
import traceback
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
<style>
body{font-family:sans-serif;margin:20px;background:#f5f5f5;}
.container{max-width:800px;margin:0 auto;background:white;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
h1{color:#333;}
form{margin:20px 0;padding:15px;background:#f9f9f9;border:1px solid #ddd;border-radius:4px;}
input[type=file]{padding:8px;margin-right:10px;border:1px solid #ddd;border-radius:4px;}
input[type=submit]{padding:8px 20px;background:#007bff;color:white;border:none;cursor:pointer;border-radius:4px;}
input[type=submit]:hover{background:#0056b3;}
ul{list-style:none;padding:0;}
li{padding:8px 0;border-bottom:1px solid #eee;}
li a{color:#007bff;text-decoration:none;}
li a:hover{text-decoration:underline;}
.alert{padding:10px;margin:10px 0;border-radius:4px;}
.alert-success{background:#d4edda;color:#155724;border:1px solid #c3e6cb;}
.alert-error{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;}
</style>
</head>
<body>
<div class="container">
<h1>Agentic Audit Dashboard</h1>
<p><small>Upload invoice JSON files for automated fraud detection and compliance checking</small></p>

<h2>Upload Invoice(s)</h2>
<form action="/upload" method="post" enctype="multipart/form-data">
  <input type="file" name="file" accept="application/json" required> 
  <input type="submit" value="Upload and Scan">
</form>

<h2>Recent Reports</h2>
{% if files %}
<ul>
{% for f in files %}
  <li><a href="/reports/{{ f }}">{{ f }}</a></li>
{% endfor %}
</ul>
{% else %}
<p><em>No reports yet. Upload an invoice to get started.</em></p>
{% endif %}
</div>
</body>
</html>
"""

@APP.route("/")
def index():
    try:
        files = sorted([p.name for p in EXPORT_DIR.iterdir() if p.is_file() and p.suffix in ('.html', '.csv', '.json')], reverse=True)
    except:
        files = []
    return render_template_string(INDEX_HTML, files=files)

@APP.route("/test")
def test():
    return f"<h1>Dashboard is working!</h1><p>Exports directory: <code>{EXPORT_DIR.resolve()}</code></p>", 200

@APP.route("/upload", methods=["POST"])
def upload():
    try:
        f = request.files.get("file")
        if not f or f.filename == '':
            return render_template_string("""
                <h1>Error</h1>
                <div class='alert alert-error'>No file selected</div>
                <a href='/'>← Back to Dashboard</a>
            """), 400

        try:
            content = f.read().decode('utf-8')
            data = json.loads(content)
        except json.JSONDecodeError as je:
            return render_template_string("""
                <h1>JSON Parse Error</h1>
                <div class='alert alert-error'><strong>Error:</strong> {{ error }}</div>
                <a href='/'>← Back to Dashboard</a>
            """, error=str(je)), 400
        except Exception as e:
            return render_template_string("""
                <h1>File Read Error</h1>
                <div class='alert alert-error'><strong>Error:</strong> {{ error }}</div>
                <a href='/'>← Back to Dashboard</a>
            """, error=str(e)), 400

        # normalize to list of documents
        docs = data if isinstance(data, list) else [data]
        
        # run pipeline
        pipe = Pipeline()
        report = pipe.run(docs)

        # create report files
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
        
    except Exception as e:
        tb = traceback.format_exc()
        return render_template_string("""
            <h1>Upload Error</h1>
            <div class='alert alert-error'>
                <strong>Error:</strong> {{ error }}
            </div>
            <h3>Traceback:</h3>
            <pre style='background:#f5f5f5;padding:10px;overflow-x:auto;'>{{ traceback }}</pre>
            <a href='/'>← Back to Dashboard</a>
        """, error=str(e), traceback=tb), 500

@APP.route('/reports/<path:filename>')
def report_file(filename):
    try:
        return send_from_directory(str(EXPORT_DIR.resolve()), filename)
    except Exception as e:
        return render_template_string("""
            <h1>File Not Found</h1>
            <p>Could not find: <code>{{ filename }}</code></p>
            <p>{{ error }}</p>
            <a href='/'>← Back to Dashboard</a>
        """, filename=filename, error=str(e)), 404

def create_app():
    return APP

if __name__ == '__main__':
    APP.run(host='127.0.0.1', port=5000, debug=True)
