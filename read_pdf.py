import subprocess
import sys

# Install required library if not present
try:
    import pdfplumber
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber"])
    import pdfplumber

pdf_path = r"C:\dev\Budget\Atmos\Mid-Tex Weather Normalization Adjustment (WNA) Report - 2024.pdf"

print(f"Reading: {pdf_path}\n")
print("=" * 80)

with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages, 1):
        print(f"\n--- Page {i} ---\n")
        text = page.extract_text()
        if text:
            print(text)

        # Extract tables if present
        tables = page.extract_tables()
        if tables:
            print(f"\n[Tables found on page {i}]")
            for j, table in enumerate(tables, 1):
                print(f"\nTable {j}:")
                for row in table:
                    print(" | ".join(str(cell) if cell else "" for cell in row))

print("\n" + "=" * 80)
print("PDF extraction complete.")
