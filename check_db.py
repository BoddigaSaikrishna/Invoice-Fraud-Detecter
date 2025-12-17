"""Quick script to check database status"""
import sqlite3
from pathlib import Path

DB_PATH = Path("audit.db")

print("=" * 60)
print("DATABASE CONNECTION TEST")
print("=" * 60)

# Check if file exists
if DB_PATH.exists():
    print(f"✅ Database file exists: {DB_PATH.absolute()}")
    print(f"   Size: {DB_PATH.stat().st_size:,} bytes")
else:
    print("❌ Database file NOT found!")
    exit(1)

# Connect and check structure
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"\n✅ Database connection successful!")
    print(f"   Tables found: {[t[0] for t in tables]}")
    
    # Check reports table
    cursor.execute("SELECT COUNT(*) FROM reports")
    count = cursor.fetchone()[0]
    print(f"\n📊 Reports table:")
    print(f"   Total records: {count}")
    
    if count > 0:
        # Show recent reports
        cursor.execute("""
            SELECT id, created_at, total_invoices, fraud_alerts, 
                   compliance_violations, html_path 
            FROM reports 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        rows = cursor.fetchall()
        
        print(f"\n   Last 5 reports:")
        for row in rows:
            print(f"   • ID {row[0]}: {row[2]} invoices, {row[1]} alerts")
    else:
        print("   No reports recorded yet (upload an invoice to create one)")
    
    conn.close()
    print("\n" + "=" * 60)
    print("✅ DATABASE IS FULLY OPERATIONAL")
    print("=" * 60)
    
except sqlite3.Error as e:
    print(f"\n❌ Database error: {e}")
    exit(1)
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    exit(1)
