#!/usr/bin/env python
"""Upload invoice file to dashboard for testing"""
import requests
import sys
from pathlib import Path

# Configuration
DASHBOARD_URL = "http://127.0.0.1:5000/upload"
DEFAULT_FILE = Path("sample_invoice.json")

def upload_file(filepath):
    """Upload file to dashboard"""
    file_path = Path(filepath)
    
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return False
    
    print(f"Uploading: {file_path}")
    print(f"File size: {file_path.stat().st_size} bytes")
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(DASHBOARD_URL, files=files)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{response.text[:500]}")
        
        if response.status_code == 200:
            print("\n✓ Upload successful!")
            # Find generated report in response
            if 'download' in response.text:
                print("Report generated - check browser at http://127.0.0.1:5000")
            return True
        else:
            print(f"\n✗ Upload failed!")
            return False
            
    except requests.exceptions.ConnectionError:
        print("Error: Cannot connect to dashboard at http://127.0.0.1:5000")
        print("Make sure dashboard is running: venv\\Scripts\\python -m agentic_audit.tools.simple_dashboard")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    # Get filename from command line or use default
    filename = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_FILE)
    
    success = upload_file(filename)
    sys.exit(0 if success else 1)
