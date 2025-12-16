"""Simple runner for the Agentic Audit pipeline."""
import json
from pathlib import Path
from .pipeline import Pipeline


def load_sample(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main(sample_file: str = None):
    base = Path(__file__).resolve().parent
    if sample_file:
        p = Path(sample_file)
    else:
        p = base / "sample_data" / "invoice1.json"

    documents = load_sample(p)
    pipe = Pipeline()
    report = pipe.run(documents)
    out = base / "last_report.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Report written to: {out}")


if __name__ == "__main__":
    main()
