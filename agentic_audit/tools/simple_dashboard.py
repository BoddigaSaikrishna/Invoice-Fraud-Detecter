"""Minimal Flask dashboard for uploading and scanning invoices."""
import json
import time
import re
import os
import sqlite3
from functools import wraps
from pathlib import Path
from flask import Flask, request, render_template_string, redirect, send_file, session, url_for

from agentic_audit.pipeline import Pipeline
from agentic_audit import exporter

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    import pandas as pd
    PANDAS_SUPPORT = True
except ImportError:
    PANDAS_SUPPORT = False

try:
    from docx import Document
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False

app = Flask(__name__)
EXPORT_DIR = Path("exports").resolve()
EXPORT_DIR.mkdir(exist_ok=True)
DB_PATH = Path("audit.db")

# Simple session-based auth
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-prod")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

def login_required(fn):
        @wraps(fn)
        def _wrapped(*args, **kwargs):
                if not session.get("user"):
                        nxt = request.path
                        return redirect(url_for("login", next=nxt))
                return fn(*args, **kwargs)
        return _wrapped

LOGIN_HTML = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Login - Audit Dashboard</title>
    <style>
        body { font-family: Segoe UI, Arial, sans-serif; background: #f5f7fb; display: grid; place-items: center; height: 100vh; margin: 0; }
        .card { width: 360px; background: white; padding: 24px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
        h1 { margin: 0 0 12px; font-size: 1.4rem; }
        p { margin: 0 0 16px; color: #666; font-size: 0.95rem; }
        label { display: block; font-weight: 600; margin: 12px 0 6px; }
        input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 1rem; }
        input:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102,126,234,0.12); }
        button { width: 100%; margin-top: 16px; padding: 12px; border: none; border-radius: 8px; background: linear-gradient(135deg,#667eea,#764ba2); color: #fff; font-weight: 700; cursor: pointer; }
        .hint { margin-top: 12px; color: #999; font-size: 0.85rem; }
        .error { color: #b00020; background: #fdecef; padding: 10px; border-radius: 8px; margin-bottom: 10px; }
    </style>
    <script>function fill(){document.getElementById('u').value='admin';document.getElementById('p').value='admin123';}</script>
</head>
<body>
    <div class=\"card\">
        <h1>🔐 Audit Dashboard Login</h1>
        <p>Enter your credentials to continue.</p>
        {% if error %}<div class=\"error\">{{ error }}</div>{% endif %}
        <form method=\"post\">
            <label>Username</label>
            <input id=\"u\" name=\"username\" placeholder=\"admin\" required>
            <label>Password</label>
            <input id=\"p\" type=\"password\" name=\"password\" placeholder=\"••••••••\" required>
            <button type=\"submit\">Sign in</button>
        </form>
        <div class=\"hint\">Default: admin / admin123 <button onclick=\"fill()\" style=\"margin-left:6px;padding:4px 8px;border:none;border-radius:6px;background:#edf1ff;color:#334;cursor:pointer;\">Fill</button></div>
    </div>
</body>
</html>
"""

def extract_invoice_from_pdf(pdf_path):
    """Extract invoice data from PDF using pdfplumber"""
    if not PDF_SUPPORT:
        return None
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"
            
            # Parse invoice details from text
            invoice_data = parse_invoice_text(full_text)
            return invoice_data
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return None

def parse_invoice_text(text):
    """Extract structured invoice data from unstructured text"""
    invoice = {
        "invoice_id": None,
        "vendor": None,
        "amount": None,
        "date": None,
        "description": "Uploaded invoice"
    }
    
    # Try to find invoice number
    patterns = [
        r'Invoice\s*#?:?\s*([A-Z0-9\-]+)',
        r'Order\s*#?:?\s*([A-Z0-9\-]+)',
        r'Order ID\s*:?\s*([A-Z0-9\-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            invoice["invoice_id"] = match.group(1)
            break
    
    if not invoice["invoice_id"]:
        invoice["invoice_id"] = f"INV-{int(time.time())}"
    
    # Try to find amount/total
    amount_patterns = [
        r'(?:Total|Amount|Grand Total|Price)\s*[:\s]*[₹\$]?\s*([\d,]+\.?\d*)',
        r'([\d,]+\.?\d*)\s*(?:INR|USD|\$|₹)',
    ]
    for pattern in amount_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                invoice["amount"] = float(amount_str)
                break
            except:
                pass
    
    if not invoice["amount"]:
        invoice["amount"] = 0.0
    
    # Try to find vendor/seller
    vendor_patterns = [
        r'(?:Seller|Vendor|From|Company|Supplied by)\s*[:\n]\s*([A-Za-z\s&]+)',
        r'(?:Bill to|Sold by)\s*[:\n]\s*([A-Za-z\s&]+)',
    ]
    for pattern in vendor_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            vendor = match.group(1).strip()
            if len(vendor) > 3 and len(vendor) < 100:
                invoice["vendor"] = vendor
                break
    
    if not invoice["vendor"]:
        invoice["vendor"] = "Unknown Vendor"
    
    # Try to find date
    date_pattern = r'(?:Date|Order Date|Invoice Date)\s*[:\n]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})'
    match = re.search(date_pattern, text, re.IGNORECASE)
    if match:
        invoice["date"] = match.group(1)
    else:
        from datetime import datetime
        invoice["date"] = datetime.now().strftime("%Y-%m-%d")
    
    return invoice


# --- Simple SQLite helpers ---
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        # Reports table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at INTEGER,
                total_invoices INTEGER,
                fraud_alerts INTEGER,
                compliance_violations INTEGER,
                html_path TEXT,
                json_path TEXT,
                csv_path TEXT
            )
            """
        )
        # Users table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
            """
        )
SIGNUP_HTML = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Sign Up - Audit Dashboard</title>
    <style>
        body { font-family: Segoe UI, Arial, sans-serif; background: #f5f7fb; display: grid; place-items: center; height: 100vh; margin: 0; }
        .card { width: 360px; background: white; padding: 24px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
        h1 { margin: 0 0 12px; font-size: 1.4rem; }
        p { margin: 0 0 16px; color: #666; font-size: 0.95rem; }
        label { display: block; font-weight: 600; margin: 12px 0 6px; }
        input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 1rem; }
        input:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102,126,234,0.12); }
        button { width: 100%; margin-top: 16px; padding: 12px; border: none; border-radius: 8px; background: linear-gradient(135deg,#667eea,#764ba2); color: #fff; font-weight: 700; cursor: pointer; }
        .hint { margin-top: 12px; color: #999; font-size: 0.85rem; }
        .error { color: #b00020; background: #fdecef; padding: 10px; border-radius: 8px; margin-bottom: 10px; }
        .success { color: #22543d; background: #e6ffed; padding: 10px; border-radius: 8px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class=\"card\">
        <h1>📝 Sign Up</h1>
        <p>Create a new account to use the dashboard.</p>
        {% if error %}<div class=\"error\">{{ error }}</div>{% endif %}
        {% if success %}<div class=\"success\">{{ success }}</div>{% endif %}
        <form method=\"post\">
            <label>Username</label>
            <input name=\"username\" placeholder=\"Choose a username\" required>
            <label>Password</label>
            <input type=\"password\" name=\"password\" placeholder=\"Create a password\" required>
            <button type=\"submit\">Sign up</button>
        </form>
        <div class=\"hint\">Already have an account? <a href=\"/login\">Login</a></div>
    </div>
</body>
</html>
"""
# --- Signup route ---
@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    success = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            error = "Username and password are required."
        else:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                success = "Account created! You can now <a href='/login'>login</a>."
            except sqlite3.IntegrityError:
                error = "Username already exists. Please choose another."
            except Exception as e:
                error = f"Error: {e}"
    return render_template_string(SIGNUP_HTML, error=error, success=success)


def record_report(report, html_file, json_file, csv_file):
    total_invoices = len(report.get("invoices", [])) if isinstance(report, dict) else 0
    fraud_alerts = len(report.get("fraud_alerts", [])) if isinstance(report, dict) else 0
    compliance_violations = len(report.get("compliance_violations", [])) if isinstance(report, dict) else 0
    # Store only the filenames in the DB for privacy/security
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO reports (created_at, total_invoices, fraud_alerts, compliance_violations, html_path, json_path, csv_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                total_invoices,
                fraud_alerts,
                compliance_violations,
                os.path.basename(str(html_file)),
                os.path.basename(str(json_file)),
                os.path.basename(str(csv_file)),
            ),
        )


def fetch_reports(limit=10):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT html_path FROM reports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    # Only return the filename, not the full path, for security
    basenames = []
    for r in rows:
        if not r:
            continue
        val = r[0] or ""
        # Handle any path separators (Windows or POSIX)
        basenames.append(os.path.basename(val))
    return basenames

# Initialize DB at import time (Flask 3+ removed before_first_request)
init_db()

# --- Multi-format file parsers ---
def extract_from_txt(file_content):
    """Extract invoice data from plain text"""
    lines = file_content.split('\n')
    full_text = ' '.join(lines)
    return parse_invoice_text(full_text)

def extract_from_csv(file_path):
    """Extract invoice data from CSV"""
    if not PANDAS_SUPPORT:
        return None
    
    try:
        df = pd.read_csv(file_path)
        
        # Try to find relevant columns
        invoice_data = {
            "invoice_id": None,
            "vendor": None,
            "amount": None,
            "date": None,
            "description": "CSV invoice"
        }
        
        # Map common CSV column names
        for col in df.columns:
            col_lower = col.lower()
            if 'invoice' in col_lower or 'order' in col_lower or 'id' in col_lower:
                if df[col].notna().any():
                    invoice_data["invoice_id"] = str(df[col].iloc[0])
            elif 'vendor' in col_lower or 'seller' in col_lower or 'company' in col_lower:
                if df[col].notna().any():
                    invoice_data["vendor"] = str(df[col].iloc[0])
            elif 'amount' in col_lower or 'total' in col_lower or 'price' in col_lower:
                if df[col].notna().any():
                    try:
                        invoice_data["amount"] = float(df[col].iloc[0])
                    except:
                        pass
            elif 'date' in col_lower:
                if df[col].notna().any():
                    invoice_data["date"] = str(df[col].iloc[0])
        
        # Set defaults
        if not invoice_data["invoice_id"]:
            invoice_data["invoice_id"] = f"INV-{int(time.time())}"
        if not invoice_data["vendor"]:
            invoice_data["vendor"] = "Unknown Vendor"
        if not invoice_data["amount"]:
            invoice_data["amount"] = 0.0
        if not invoice_data["date"]:
            from datetime import datetime
            invoice_data["date"] = datetime.now().strftime("%Y-%m-%d")
        
        return invoice_data
    except Exception as e:
        print(f"CSV extraction error: {e}")
        return None

def extract_from_xlsx(file_path):
    """Extract invoice data from Excel"""
    if not PANDAS_SUPPORT:
        return None
    
    try:
        df = pd.read_excel(file_path)
        
        invoice_data = {
            "invoice_id": None,
            "vendor": None,
            "amount": None,
            "date": None,
            "description": "Excel invoice"
        }
        
        # Map common Excel column names
        for col in df.columns:
            col_lower = col.lower()
            if 'invoice' in col_lower or 'order' in col_lower or 'id' in col_lower:
                if df[col].notna().any():
                    invoice_data["invoice_id"] = str(df[col].iloc[0])
            elif 'vendor' in col_lower or 'seller' in col_lower or 'company' in col_lower:
                if df[col].notna().any():
                    invoice_data["vendor"] = str(df[col].iloc[0])
            elif 'amount' in col_lower or 'total' in col_lower or 'price' in col_lower:
                if df[col].notna().any():
                    try:
                        invoice_data["amount"] = float(df[col].iloc[0])
                    except:
                        pass
            elif 'date' in col_lower:
                if df[col].notna().any():
                    invoice_data["date"] = str(df[col].iloc[0])
        
        # Set defaults
        if not invoice_data["invoice_id"]:
            invoice_data["invoice_id"] = f"INV-{int(time.time())}"
        if not invoice_data["vendor"]:
            invoice_data["vendor"] = "Unknown Vendor"
        if not invoice_data["amount"]:
            invoice_data["amount"] = 0.0
        if not invoice_data["date"]:
            from datetime import datetime
            invoice_data["date"] = datetime.now().strftime("%Y-%m-%d")
        
        return invoice_data
    except Exception as e:
        print(f"Excel extraction error: {e}")
        return None

def extract_from_docx(file_path):
    """Extract invoice data from Word document"""
    if not DOCX_SUPPORT:
        return None
    
    try:
        doc = Document(file_path)
        full_text = '\n'.join([para.text for para in doc.paragraphs])
        return parse_invoice_text(full_text)
    except Exception as e:
        print(f"DOCX extraction error: {e}")
        return None

def process_file(file, filename):
    """Process any file type and extract invoice data"""
    docs = []
    
    # PDF
    if filename.lower().endswith('.pdf'):
        if not PDF_SUPPORT:
            return None, "PDF support not installed. Run: pip install pdfplumber"
        
        temp_file = Path("/tmp") / filename if Path("/tmp").exists() else Path("exports") / filename
        file.save(str(temp_file))
        invoice_data = extract_invoice_from_pdf(str(temp_file))
        try:
            temp_file.unlink()
        except:
            pass
        
        if not invoice_data:
            return None, "Could not extract invoice data from PDF"
        docs = [invoice_data]
    
    # JSON
    elif filename.lower().endswith('.json'):
        try:
            raw_data = file.read()
            data = None
            
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    content = raw_data.decode(encoding)
                    data = json.loads(content)
                    break
                except:
                    continue
            
            if data is None:
                return None, "Failed to parse JSON. Ensure file is valid UTF-8 JSON"
            
            docs = data if isinstance(data, list) else [data]
        except Exception as e:
            return None, f"JSON parse error: {str(e)}"
    
    # TXT
    elif filename.lower().endswith('.txt'):
        try:
            content = file.read().decode('utf-8', errors='ignore')
            invoice_data = extract_from_txt(content)
            if invoice_data:
                docs = [invoice_data]
            else:
                return None, "Could not extract invoice data from text"
        except Exception as e:
            return None, f"Text parse error: {str(e)}"
    
    # CSV
    elif filename.lower().endswith('.csv'):
        if not PANDAS_SUPPORT:
            return None, "CSV support requires pandas. Run: pip install pandas"
        
        try:
            temp_file = Path("exports") / filename
            file.save(str(temp_file))
            invoice_data = extract_from_csv(str(temp_file))
            try:
                temp_file.unlink()
            except:
                pass
            
            if invoice_data:
                docs = [invoice_data]
            else:
                return None, "Could not extract invoice data from CSV"
        except Exception as e:
            return None, f"CSV parse error: {str(e)}"
    
    # XLSX/XLS
    elif filename.lower().endswith(('.xlsx', '.xls')):
        if not PANDAS_SUPPORT:
            return None, "Excel support requires pandas. Run: pip install pandas openpyxl"
        
        try:
            temp_file = Path("exports") / filename
            file.save(str(temp_file))
            invoice_data = extract_from_xlsx(str(temp_file))
            try:
                temp_file.unlink()
            except:
                pass
            
            if invoice_data:
                docs = [invoice_data]
            else:
                return None, "Could not extract invoice data from Excel"
        except Exception as e:
            return None, f"Excel parse error: {str(e)}"
    
    # DOCX
    elif filename.lower().endswith('.docx'):
        if not DOCX_SUPPORT:
            return None, "DOCX support requires python-docx. Run: pip install python-docx"
        
        try:
            temp_file = Path("exports") / filename
            file.save(str(temp_file))
            invoice_data = extract_from_docx(str(temp_file))
            try:
                temp_file.unlink()
            except:
                pass
            
            if invoice_data:
                docs = [invoice_data]
            else:
                return None, "Could not extract invoice data from document"
        except Exception as e:
            return None, f"DOCX parse error: {str(e)}"
    
    else:
        return None, f"Unsupported file type: {filename}. Supported: PDF, JSON, TXT, CSV, XLSX, XLS, DOCX"
    
    return docs, None

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Government Audit & Fraud Prevention System</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
            min-height: 100vh;
            padding: 20px;
            position: relative;
            overflow-x: hidden;
        }
        
        body::before {
            content: '';
            position: fixed;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 1px, transparent 1px);
            background-size: 50px 50px;
            animation: drift 60s linear infinite;
            pointer-events: none;
        }
        
        @keyframes drift {
            0% { transform: translate(0, 0); }
            100% { transform: translate(50px, 50px); }
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 50px;
            padding: 30px 20px;
            position: relative;
            animation: fadeInDown 0.8s ease;
        }
        
        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-30px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .header h1 {
            font-size: 3rem;
            font-weight: 800;
            margin-bottom: 15px;
            text-shadow: 0 4px 20px rgba(0,0,0,0.3);
            letter-spacing: -1px;
        }
        
        .header p {
            font-size: 1.2rem;
            opacity: 0.95;
            font-weight: 300;
            letter-spacing: 0.5px;
        }
        
        .account-bar {
            position: absolute;
            top: 20px;
            right: 25px;
            background: rgba(255,255,255,0.25);
            color: #fff;
            padding: 10px 18px;
            border-radius: 50px;
            font-size: 0.9rem;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.3);
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            animation: slideInRight 0.6s ease;
        }
        
        @keyframes slideInRight {
            from { opacity: 0; transform: translateX(30px); }
            to { opacity: 1; transform: translateX(0); }
        }
        
        .account-bar a { 
            color: #fff; 
            text-decoration: none; 
            margin-left: 10px; 
            cursor: pointer;
            padding: 4px 10px;
            background: rgba(255,255,255,0.2);
            border-radius: 20px;
            transition: all 0.3s;
        }
        
        .account-bar a:hover {
            background: rgba(255,255,255,0.35);
            transform: scale(1.05);
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            position: relative;
            z-index: 1;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 28px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.2);
            border: 1px solid rgba(255,255,255,0.5);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            animation: fadeInUp 0.6s ease;
        }
        
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(40px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .card:hover {
            transform: translateY(-8px);
            box-shadow: 0 30px 80px rgba(0,0,0,0.25);
        }
        
        .card h2 {
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 25px;
            color: #2d3748;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .icon {
            font-size: 1.5rem;
        }
        
        .upload-zone {
            border: 3px dashed #cbd5e0;
            border-radius: 16px;
            padding: 50px;
            text-align: center;
            background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
            transition: all 0.4s ease;
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }
        
        .upload-zone::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(102,126,234,0.1) 0%, transparent 70%);
            opacity: 0;
            transition: opacity 0.4s;
        }
        
        .upload-zone:hover::before {
            opacity: 1;
        }
        
        .upload-zone:hover {
            border-color: #667eea;
            background: linear-gradient(135deg, #edf2f7 0%, #e6fffa 100%);
            transform: scale(1.02);
            box-shadow: 0 10px 30px rgba(102,126,234,0.2);
        }
        
        .upload-zone.dragover {
            border-color: #667eea;
            background: linear-gradient(135deg, #e6fffa 0%, #b2f5ea 100%);
            transform: scale(1.03);
            box-shadow: 0 15px 40px rgba(102,126,234,0.3);
        }
        
        input[type="file"] {
            display: none;
        }
        
        .file-label {
            display: block;
            cursor: pointer;
        }
        
        .file-label .upload-icon {
            font-size: 4rem;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: float 3s ease-in-out infinite;
        }
        
        @keyframes float {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }
        
        .file-label p {
            font-size: 1.15rem;
            color: #4a5568;
            margin-bottom: 10px;
            font-weight: 500;
        }
        
        .file-label small {
            color: #a0aec0;
            font-size: 0.9rem;
        }
        
        .selected-file {
            margin-top: 16px;
            padding: 12px;
            background: #e8f5e9;
            border-radius: 8px;
            color: #2e7d32;
            font-weight: 600;
        }
        
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 16px 36px;
            font-size: 1.05rem;
            font-weight: 600;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            width: 100%;
            margin-top: 20px;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
            letter-spacing: 0.5px;
            position: relative;
            overflow: hidden;
        }
        
        button::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: rgba(255,255,255,0.2);
            transform: translate(-50%, -50%);
            transition: width 0.6s, height 0.6s;
        }
        
        button:hover::before {
            width: 300px;
            height: 300px;
        }
        
        button:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(102, 126, 234, 0.4);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        button:disabled {
            background: linear-gradient(135deg, #cbd5e0, #a0aec0);
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .reports-grid {
            display: grid;
            gap: 16px;
        }
        
        .report-item {
            padding: 20px 24px;
            background: linear-gradient(135deg, #ffffff 0%, #f7fafc 100%);
            border-radius: 18px;
            border-left: 5px solid #667eea;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 32px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        
        .report-item:hover {
            background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
            transform: translateX(8px);
            box-shadow: 0 8px 20px rgba(102,126,234,0.15);
            border-left-color: #764ba2;
        }
        
        /* Only make non-view anchors take the flexible space */
        .report-item a:not(.view-btn) {
            color: #2d3748;
            text-decoration: none;
            font-weight: 600;
            flex: 1;
            font-size: 0.95rem;
        }
        /* Make the filename area truncate instead of forcing layout */
        .report-item span {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            display: inline-block;
        }
        
        .report-badge {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 6px 14px;
            border-radius: 14px;
            font-size: 0.85rem;
            font-weight: 600;
            box-shadow: 0 4px 10px rgba(102,126,234,0.3);
            transition: all 0.3s;
        }
        /* Make view button styles specific to report items to avoid conflicts */
        .report-item .view-btn {
            min-width: 0;
            width: auto;
            display: inline-block;
            text-align: center;
            margin-left: 8px;
            margin-right: 0;
            padding: 2px 6px !important;
            font-size: 0.72em !important;
            line-height: 1.0 !important;
            height: 24px !important;
            flex: 0 0 84px !important;
            width: 84px !important;
            border-radius: 0.5rem;
            background: #667eea;
            color: #fff;
            border: none;
            box-shadow: none;
            font-weight: 500;
            transition: background 0.2s;
        }
        .view-btn:hover {
            background: #5a67d8;
            color: #fff;
        }

        /* Spinner/animation size reduction */
        .spinner-border, .spinner-grow {
            width: 0.8rem !important;
            height: 0.8rem !important;
            border-width: 0.10em !important;
        }
        
        .report-badge:hover {
            transform: scale(1.05);
            box-shadow: 0 6px 15px rgba(102,126,234,0.4);
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        
        .empty-state-icon {
            font-size: 4rem;
            margin-bottom: 16px;
            opacity: 0.3;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 24px;
            border-radius: 12px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        .stat-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }
        
        .tab-btn {
            background: rgba(255,255,255,0.9);
            border: none;
            padding: 14px 28px;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 600;
            font-size: 1rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            color: #4a5568;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .tab-btn:hover {
            background: rgba(255,255,255,1);
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        }
        
        .tab-btn.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 8px 25px rgba(102,126,234,0.4);
            transform: translateY(-2px);
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 10px;
            font-weight: 600;
            color: #2d3748;
            font-size: 0.95rem;
            letter-spacing: 0.3px;
        }
        
        .form-group input {
            width: 100%;
            padding: 14px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 10px;
            font-size: 1rem;
            font-family: inherit;
            transition: all 0.3s ease;
            background: #f7fafc;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
            background: #ffffff;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
            transform: translateY(-1px);
        }
        
        .hint {
            margin-top: 12px;
            color: #718096;
            font-size: 0.9rem;
            text-align: center;
        }
        
        @media (max-width: 768px) {
            .header h1 { font-size: 2rem; }
            .header p { font-size: 1rem; }
            .card { padding: 24px; }
            .stats { grid-template-columns: 1fr; }
            .account-bar {
                position: relative;
                top: 0;
                right: 0;
                margin-bottom: 20px;
                text-align: center;
            }
            button { padding: 12px 24px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="account-bar">
            <span id="userDisplay">Not signed in</span>
            <a href="#" id="logoutLink" style="display:none;">Logout</a>
        </div>
        <h1>🔍 Government Audit & Fraud Prevention</h1>
        <p>AI-Powered Invoice Analysis System</p>
    </div>
    
    <div class="container">
        <!-- Tabs -->
        <div style="display: flex; gap: 10px; margin-bottom: 20px;">
            <button onclick="showTab(event, 'login')" class="tab-btn active" id="loginTabBtn">🔐 Login</button>
            <button onclick="showTab(event, 'upload')" class="tab-btn" id="uploadTabBtn" style="display:none;">📤 Upload File</button>
            <button onclick="showTab(event, 'create')" class="tab-btn" id="createTabBtn" style="display:none;">✏️ Create Invoice</button>
        </div>

        <!-- Login Tab (frontend only) -->
        <div id="login-tab" class="card">
            <h2><span class="icon">🔐</span> Login</h2>
            <form id="loginForm">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" id="loginUser" placeholder="admin" required>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" id="loginPass" placeholder="••••••••" required>
                </div>
                <button type="submit" class="btn">Sign in</button>
                <p class="hint" id="loginHint">Frontend-only demo login. No server auth.</p>
            </form>
        </div>
        
        <!-- Upload Tab -->
        <div id="upload-tab" class="card" style="display:none;">
            <h2><span class="icon">📤</span> Upload Invoice for Fraud Check</h2>
            <form method="post" action="/upload" enctype="multipart/form-data" id="uploadForm">
                <div class="upload-zone" id="dropZone">
                    <label for="fileInput" class="file-label">
                        <div class="upload-icon">📁</div>
                        <p>Click to browse or drag & drop your invoice file</p>
                        <small>Accepts: PDF, JSON, TXT, CSV, XLSX, DOCX</small>
                    </label>
                    <input type="file" name="file" id="fileInput" accept=".pdf,.json,.txt,.csv,.xlsx,.xls,.docx" required>
                    <div id="fileName" class="selected-file" style="display:none;"></div>
                </div>
                <button type="submit" id="submitBtn" disabled>🚀 Analyze Invoice</button>
            </form>
        </div>
        
        <!-- Create Tab -->
        <div id="create-tab" class="card" style="display:none;">
            <h2><span class="icon">✏️</span> Create & Analyze Invoice</h2>
            <form method="post" action="/create-invoice" id="createForm">
                <div class="form-group">
                    <label>Invoice Number</label>
                    <input type="text" name="invoice_number" placeholder="e.g., INV-2025-001" required>
                </div>
                <div class="form-group">
                    <label>Vendor Name</label>
                    <input type="text" name="vendor_name" placeholder="e.g., Acme Corporation" required>
                </div>
                <div class="form-group">
                    <label>Amount</label>
                    <input type="number" name="amount" placeholder="e.g., 5000.00" step="0.01" required>
                </div>
                <div class="form-group">
                    <label>Date (YYYY-MM-DD)</label>
                    <input type="date" name="date" required>
                </div>
                <div class="form-group">
                    <label>Description</label>
                    <input type="text" name="description" placeholder="Invoice description" required>
                </div>
                <button type="submit" class="btn">🚀 Create & Analyze</button>
            </form>
        </div>
        
        <div class="card" id="reportsCard" style="display:none;">
            <h2><span class="icon">📊</span> Recent Audit Reports</h2>
            {% if reports %}
            <div class="reports-grid">
            {% for report in reports %}
                <div class="report-item">
                    <span style="font-weight:bold; margin-right:10px;">{{ loop.index }}.</span>
                    <span style="flex:1;">{{ report }}</span>
                    <a href="/download/{{ report }}" class="view-btn" style="text-decoration:none;">View</a>
                </div>
            {% endfor %}
            </div>
            {% else %}
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <p>No reports yet. Upload an invoice to get started!</p>
            </div>
            {% endif %}
        </div>
    </div>
    
    <script>
        function showTab(event, tabName) {
            // Hide all tabs
            document.getElementById('login-tab').style.display = 'none';
            document.getElementById('upload-tab').style.display = 'none';
            document.getElementById('create-tab').style.display = 'none';
            
            // Show selected tab
            document.getElementById(tabName + '-tab').style.display = 'block';
            
            // Update button styles
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            if (event && event.currentTarget) {
                event.currentTarget.classList.add('active');
            } else if (event && event.target) {
                event.target.classList.add('active');
            }
        }
        
        const fileInput = document.getElementById('fileInput');
        const fileName = document.getElementById('fileName');
        const submitBtn = document.getElementById('submitBtn');
        const dropZone = document.getElementById('dropZone');
        const loginForm = document.getElementById('loginForm');
        const loginHint = document.getElementById('loginHint');
        const loginUser = document.getElementById('loginUser');
        const loginPass = document.getElementById('loginPass');
        const userDisplay = document.getElementById('userDisplay');
        const logoutLink = document.getElementById('logoutLink');
        const uploadTabBtn = document.getElementById('uploadTabBtn');
        const createTabBtn = document.getElementById('createTabBtn');
        const loginTabBtn = document.getElementById('loginTabBtn');
        const reportsCard = document.getElementById('reportsCard');

        function isLoggedIn(){ return !!localStorage.getItem('auditUser'); }
        function setAuthUI(){
            const user = localStorage.getItem('auditUser');
            if(isLoggedIn()){
                if(loginHint) loginHint.textContent = 'Signed in as ' + user + '. You can upload now.';
                if(userDisplay) userDisplay.textContent = 'Logged in as ' + user;
                if(logoutLink) logoutLink.style.display = 'inline';
                // Show upload and create tabs
                if(uploadTabBtn) uploadTabBtn.style.display = 'inline-block';
                if(createTabBtn) createTabBtn.style.display = 'inline-block';
                if(loginTabBtn) loginTabBtn.style.display = 'none';
                // Show reports card
                if(reportsCard) reportsCard.style.display = 'block';
                // Switch to upload tab for convenience
                showTab({currentTarget: uploadTabBtn}, 'upload');
            } else {
                if(loginHint) loginHint.textContent = 'Frontend-only demo login. No server auth.';
                if(userDisplay) userDisplay.textContent = 'Not signed in';
                if(logoutLink) logoutLink.style.display = 'none';
                // Hide upload and create tabs
                if(uploadTabBtn) uploadTabBtn.style.display = 'none';
                if(createTabBtn) createTabBtn.style.display = 'none';
                if(loginTabBtn) loginTabBtn.style.display = 'inline-block';
                // Hide reports card
                if(reportsCard) reportsCard.style.display = 'none';
                // Stay on login tab
                showTab({currentTarget: loginTabBtn}, 'login');
            }
        }

        if(loginForm){
            loginForm.addEventListener('submit', function(e){
                e.preventDefault();
                const u = (loginUser.value || '').trim();
                if(!u){ alert('Enter username'); return; }
                localStorage.setItem('auditUser', u);
                setAuthUI();
            });
        }

        if(logoutLink){
            logoutLink.addEventListener('click', function(e){
                e.preventDefault();
                localStorage.removeItem('auditUser');
                setAuthUI();
            });
        }

        // Initialize auth UI on load
        setAuthUI();
        
        fileInput.addEventListener('change', function(e) {
            if (this.files.length > 0) {
                fileName.textContent = '✓ ' + this.files[0].name;
                fileName.style.display = 'block';
                submitBtn.disabled = false;
            }
        });
        
        // Drag & drop
        dropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', function(e) {
            this.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('dragover');
            
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                fileName.textContent = '✓ ' + e.dataTransfer.files[0].name;
                fileName.style.display = 'block';
                submitBtn.disabled = false;
            }
        });
    </script>
</body>
</html>
"""

    # ...existing code...
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "")
        # Check DB for user
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT password FROM users WHERE username=?", (u,)).fetchone()
        if row and row[0] == p:
            session["user"] = u
            nxt = request.args.get("next") or url_for("index")
            return redirect(nxt)
        elif u == ADMIN_USER and p == ADMIN_PASSWORD:
            session["user"] = u
            nxt = request.args.get("next") or url_for("index")
            return redirect(nxt)
        else:
            error = "Invalid username or password"
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/")
def index():
    try:
        reports = fetch_reports(10)
        # If fewer than 10 in DB, fill with recent files from exports folder
        if len(reports) < 10:
            existing = set([Path(r).name for r in reports])
            files = [f.name for f in sorted(EXPORT_DIR.glob("report-*.html"), reverse=True)]
            for f in files:
                if f not in existing:
                    reports.append(f)
                if len(reports) >= 10:
                    break
        # Always ensure only filenames (no paths)
        reports = [Path(r).name for r in reports]
    except Exception as e:
        print(f"Error fetching reports: {e}")
        reports = []
    return render_template_string(HTML, reports=reports)

@app.route("/upload", methods=["POST"])
def upload():
    try:
        if "file" not in request.files:
            return "<h1>Error</h1><p>No file in request</p><a href='/'>Back</a>", 400
        
        file = request.files["file"]
        if file.filename == "":
            return "<h1>Error</h1><p>No file selected</p><a href='/'>Back</a>", 400
        
        # Process file using multi-format handler
        docs, error = process_file(file, file.filename)
        
        if error:
            return f"<h1>Error</h1><p>{error}</p><a href='/'>Back</a>", 400
        
        if not docs:
            return "<h1>Error</h1><p>Could not extract any invoice data from file</p><a href='/'>Back</a>", 400
        
        print(f"Processed {file.filename}: Extracted {len(docs)} document(s)")
        
        # Run pipeline
        pipe = Pipeline()
        report = pipe.run(docs)
        
        # Save reports
        ts = int(time.time())
        base = f"report-{ts}"
        
        json_file = EXPORT_DIR / f"{base}.json"
        csv_file = EXPORT_DIR / f"{base}.csv"
        html_file = EXPORT_DIR / f"{base}.html"
        
        with open(json_file, "w") as f:
            json.dump(report, f, indent=2)
        
        exporter.export_csv(str(json_file), str(csv_file))
        exporter.export_html(str(json_file), str(html_file))
        record_report(report, html_file, json_file, csv_file)
        
        # Redirect to report
        return redirect(f"/download/{html_file.name}")
    
    except Exception as e:
        print(f"Upload error: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p><a href='/'>Back</a>", 500

@app.route("/download/<filename>")
def download(filename):
    try:
        file_path = EXPORT_DIR / filename
        if not file_path.exists():
            return "File not found", 404
        return send_file(file_path, as_attachment=False)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/create-invoice", methods=["POST"])
def create_invoice():
    """Create invoice from form data and process"""
    try:
        # Extract form data
        invoice_data = {
            "invoice_id": request.form.get("invoice_number"),
            "vendor": request.form.get("vendor_name"),
            "amount": float(request.form.get("amount")),
            "date": request.form.get("date"),
            "description": request.form.get("description")
        }
        
        # Create document object
        docs = [invoice_data]
        
        # Run pipeline
        pipe = Pipeline()
        report = pipe.run(docs)
        
        # Save reports
        ts = int(time.time())
        base = f"report-{ts}"
        
        json_file = EXPORT_DIR / f"{base}.json"
        csv_file = EXPORT_DIR / f"{base}.csv"
        html_file = EXPORT_DIR / f"{base}.html"
        
        with open(json_file, "w") as f:
            json.dump(report, f, indent=2)
        
        exporter.export_csv(str(json_file), str(csv_file))
        exporter.export_html(str(json_file), str(html_file))
        record_report(report, html_file, json_file, csv_file)
        
        # Redirect to report
        return redirect(f"/download/{html_file.name}")
    
    except Exception as e:
        return f"<h1>Error</h1><p>Failed to create invoice: {str(e)}</p><a href='/'>Back</a>", 500

if __name__ == "__main__":
    print(f"Starting dashboard on http://127.0.0.1:5000")
    print(f"Exports directory: {EXPORT_DIR}")
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)
