"""
01_audit.py — PDF Audit Script
Walks all PDFs in books/core/ and books/lost-omens/
Detects text vs scanned, estimates page count, outputs manifest.csv
Review manifest.csv before proceeding to extraction.
"""

import csv
import os
from pathlib import Path

import fitz  # PyMuPDF

BOOKS_DIR = Path(__file__).parent.parent / "books"
OUTPUT = Path(__file__).parent / "manifest.csv"

FOLDERS = {
    "core":       BOOKS_DIR / "core",
    "lost-omens": BOOKS_DIR / "lost-omens",
}

# Pages to sample for text detection
SAMPLE_PAGES = 5
# Minimum avg chars/page to consider a PDF text-based (not scanned)
TEXT_THRESHOLD = 150


def classify_pdf(pdf_path: Path) -> dict:
    result = {
        "file":       pdf_path.name,
        "folder":     pdf_path.parent.name,
        "path":       str(pdf_path),
        "pages":      0,
        "type":       "unknown",
        "avg_chars":  0,
        "skip":       False,
        "skip_reason": "",
        "notes":      "",
    }

    try:
        doc = fitz.open(pdf_path)
        result["pages"] = len(doc)

        # Sample up to SAMPLE_PAGES evenly spread through the doc
        total = len(doc)
        indices = [int(i * total / SAMPLE_PAGES) for i in range(SAMPLE_PAGES)]
        char_counts = []

        for i in indices:
            page = doc[i]
            text = page.get_text()
            char_counts.append(len(text.strip()))

        avg = sum(char_counts) / len(char_counts) if char_counts else 0
        result["avg_chars"] = round(avg)
        result["type"] = "text" if avg >= TEXT_THRESHOLD else "scanned"
        doc.close()

    except Exception as e:
        result["type"] = "error"
        result["notes"] = str(e)
        result["skip"] = True
        result["skip_reason"] = "open_error"

    return result


def main():
    rows = []

    for folder_key, folder_path in FOLDERS.items():
        if not folder_path.exists():
            print(f"WARNING: folder not found: {folder_path}")
            continue

        pdfs = sorted(folder_path.glob("*.pdf")) + sorted(folder_path.glob("*.PDF"))

        for pdf in pdfs:
            print(f"  Auditing: {pdf.name}")
            row = classify_pdf(pdf)
            rows.append(row)

    # Write manifest
    fieldnames = ["file", "folder", "pages", "type", "avg_chars", "skip", "skip_reason", "notes", "path"]
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    total   = len(rows)
    text    = sum(1 for r in rows if r["type"] == "text")
    scanned = sum(1 for r in rows if r["type"] == "scanned")
    errors  = sum(1 for r in rows if r["type"] == "error")

    print(f"\n=== Audit complete ===")
    print(f"  Total PDFs : {total}")
    print(f"  Text-based : {text}")
    print(f"  Scanned    : {scanned}")
    print(f"  Errors     : {errors}")
    print(f"\nManifest written to: {OUTPUT}")
    print("Review manifest.csv before running 02_extract.py")
    print("Set skip=True for any PDFs you want to exclude.")


if __name__ == "__main__":
    main()
