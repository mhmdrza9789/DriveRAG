import logfire
from pypdf import PdfReader


def parse_pdf(file_path: str) -> str:
    """Extract text from a text-based PDF, preserving page order."""
    with logfire.span("PDF Parsing (local)", filename=file_path):
        try:
            reader = PdfReader(file_path)
            page_texts: list[str] = []

            for page in reader.pages:
                page_texts.append(page.extract_text() or "")

            blank_indices = [
                i for i, text in enumerate(page_texts) if not text.strip()
            ]

            if blank_indices:
                try:
                    import pdfplumber

                    with pdfplumber.open(file_path) as pdf:
                        for i in blank_indices:
                            fallback_text = pdf.pages[i].extract_text() or ""
                            if fallback_text.strip():
                                page_texts[i] = fallback_text

                except Exception:
                    logfire.exception("pdfplumber fallback failed")

            full_text = "\n".join(
                text for text in page_texts if text.strip()
            )

            if not full_text:
                logfire.warning(
                    "No text extracted; this PDF may require OCR",
                    filename=file_path,
                )
            else:
                logfire.info(
                    "PDF text extracted",
                    filename=file_path,
                    pages=len(page_texts),
                    characters=len(full_text),
                    blank_pages=sum(not text.strip() for text in page_texts),
                )

            return full_text

        except Exception:
            logfire.exception("PDF parse failed", filename=file_path)
            raise


# import logfire
# import pymupdf


# def parse_pdf(file_path: str) -> str:
#     """Extract PDF text in page order; OCR pages with no extracted text."""
#     with logfire.span("PDF Parsing", filename=file_path):
#         try:
#             page_texts: list[str] = []

#             with pymupdf.open(file_path) as doc:
#                 for page_num, page in enumerate(doc, start=1):
#                     text = page.get_text("text", sort=True)

#                     if not text.strip():
#                         logfire.info("Trying OCR", page=page_num)
#                         textpage = page.get_textpage_ocr(
#                             language="eng+fas",
#                             dpi=200,
#                             full=True,
#                             tessdata=C:\Program Files\Tesseract-OCR
#                         )
#                         text = page.get_text(
#                             "text", textpage=textpage, sort=True
#                         )

#                     page_texts.append(text)

#             full_text = "\n".join(text for text in page_texts if text.strip())
#             logfire.info(
#                 "PDF parsing finished",
#                 pages=len(page_texts),
#                 characters=len(full_text),
#             )
#             return full_text

#         except Exception:
#             logfire.exception("PDF parse failed", filename=file_path)
#             raise
