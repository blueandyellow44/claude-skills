# Dossier: output pipeline

Load this at the BUILD step, once the content is final.

1. Write the dossier as one self-contained HTML file using `references/visual-design.md`. Inline all CSS. No external images except the org logo if you fetched it.
2. Render it to PDF with the polished-pdf skill's renderer in this plugin:
   `python3 ../polished-pdf/scripts/render_pdf.py <dossier.html> <dossier.pdf> --ground "#ffffff"`. It needs Playwright with Chromium (or system Chrome) and PyMuPDF, and it writes page thumbnails for the visual check.
3. Look at every rendered page. Check for text overflow, a card split across pages, an orphaned header, and anything below 10pt. Fix the HTML and render again.
4. Save the PDF where the user asked, or next to the HTML, and tell them the path.
