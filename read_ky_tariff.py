import pdfplumber

pdf_path = r"C:\dev\Budget\Atmos\Kentucky Tariff - November 2025.pdf"
output_path = r"C:\dev\Budget\Atmos\ky_tariff_extracted.txt"

print(f"Reading: {pdf_path}")
print("This may take a moment for a large PDF...")

with open(output_path, "w", encoding="utf-8") as out_file:
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"Total pages: {total_pages}")

        for i, page in enumerate(pdf.pages, 1):
            if i % 50 == 0:
                print(f"Processing page {i}/{total_pages}...")

            out_file.write(f"\n--- Page {i} ---\n\n")

            text = page.extract_text()
            if text:
                out_file.write(text + "\n")

            # Extract tables if present
            tables = page.extract_tables()
            if tables:
                out_file.write(f"\n[Tables found on page {i}]\n")
                for j, table in enumerate(tables, 1):
                    out_file.write(f"\nTable {j}:\n")
                    for row in table:
                        out_file.write(" | ".join(str(cell) if cell else "" for cell in row) + "\n")

print(f"\nExtraction complete!")
print(f"Output saved to: {output_path}")
print(f"\nNow searching for WNA-related content...")

# Search for relevant terms
search_terms = ["WNA", "Weather Normalization", "HSF", "Heat Sensitivity",
                "Base Load", "BL", "Heating Degree", "HDD", "G-1", "Residential"]

with open(output_path, "r", encoding="utf-8") as f:
    content = f.read()
    lines = content.split("\n")

print("\n" + "=" * 70)
print("KEY FINDINGS:")
print("=" * 70)

for term in search_terms:
    matches = [i for i, line in enumerate(lines) if term.lower() in line.lower()]
    if matches:
        print(f"\n'{term}' found on {len(matches)} lines")
        # Show first few matches with context
        for idx in matches[:3]:
            start = max(0, idx - 1)
            end = min(len(lines), idx + 2)
            print(f"  Line {idx}: {lines[idx][:100]}...")
