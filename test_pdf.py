# pyrefly: ignore [missing-import]
import fitz
import sys
doc = fitz.open(r"C:\Users\Atharva Avhad\.gemini\antigravity-ide\brain\145d117c-ddf0-4ba6-80bb-6bf85f810675\.user_uploaded\media_1791207981210.pdf")
print("Pages:", doc.page_count)
for i in range(min(5, doc.page_count)):
    print(f"--- Page {i} ---")
    print(repr(doc[i].get_text()))
