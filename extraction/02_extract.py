"""
02_extract.py — Raw Text Extraction
Reads manifest.csv, extracts full text from each PDF page by page,
writes one JSON file per book into extraction/raw/.
Run this after reviewing manifest.csv and setting skip=True where needed.
"""

import csv
import json
import os
from pathlib import Path

import fitz  # PyMuPDF

MANIFEST = Path(__file__).parent / "manifest.csv"
RAW_DIR  = Path(__file__).parent / "raw"


def extract_book(row: dict) -> dict:
    """Extract all pages from a single PDF. Returns a dict with metadata + pages."""
    pdf_path = Path(row["path"])

    result = {
        "file":   row["file"],
        "folder": row["folder"],
        "pages":  [],
    }

    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        result["pages"].append({
            "page": page_num + 1,   # 1-based for human readability
            "text": text.strip(),
        })
    doc.close()

    return result


def main():
    if not MANIFEST.exists():
        print("ERROR: manifest.csv not found. Run 01_audit.py first.")
        return

    RAW_DIR.mkdir(exist_ok=True)

    with open(MANIFEST, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total    = 0
    skipped  = 0
    missing  = 0
    errors   = 0
    done     = 0

    for row in rows:
        total += 1
        pdf_path = Path(row["path"])

        # Skip if flagged in manifest
        if row["skip"].strip().lower() in ("true", "1", "yes"):
            print(f"  SKIP (manifest): {row['file']}")
            skipped += 1
            continue

        # Skip if file no longer exists on disk
        if not pdf_path.exists():
            print(f"  SKIP (missing):  {row['file']}")
            missing += 1
            continue

        out_name = pdf_path.stem + ".json"
        out_path = RAW_DIR / out_name

        print(f"  Extracting: {row['file']} ({row['pages']} pages)...")

        try:
            data = extract_book(row)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            done += 1
        except Exception as e:
            print(f"    ERROR: {e}")
            errors += 1

    print(f"\n=== Extraction complete ===")
    print(f"  Total in manifest : {total}")
    print(f"  Extracted         : {done}")
    print(f"  Skipped (flag)    : {skipped}")
    print(f"  Skipped (missing) : {missing}")
    print(f"  Errors            : {errors}")
    print(f"\nRaw JSON files written to: {RAW_DIR}")
    print("Review a few files, then run the 03_parse_*.py scripts.")


if __name__ == "__main__":
    main()
