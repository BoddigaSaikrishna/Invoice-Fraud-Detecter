"""CLI to export the latest report to CSV and/or HTML."""
import argparse
from pathlib import Path
from agentic_audit import exporter


def main():
    p = argparse.ArgumentParser(description="Export agentic_audit report to CSV/HTML")
    p.add_argument("--report", help="Path to report JSON", default="agentic_audit/last_report.json")
    p.add_argument("--outdir", help="Output directory", default="exports")
    p.add_argument("--csv", help="CSV filename (relative to outdir)", default="report.csv")
    p.add_argument("--html", help="HTML filename (relative to outdir)", default="report.html")
    args = p.parse_args()

    report = Path(args.report)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    csv_path = outdir / args.csv
    html_path = outdir / args.html

    print(f"Exporting {report} -> {csv_path}, {html_path}")
    exporter.export_csv(str(report), str(csv_path))
    exporter.export_html(str(report), str(html_path))
    print("Export complete.")


if __name__ == '__main__':
    main()
