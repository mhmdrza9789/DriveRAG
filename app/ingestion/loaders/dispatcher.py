from pathlib import Path

from .html import parse_html
from .office import parse_office
from .pdf import parse_pdf
from .spreadsheet import parse_spreadsheet
from .text import parse_text


def parse_file(path: str | Path) -> str:
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return parse_pdf(str(path))

    if ext in {".html", ".htm"}:
        return parse_html(str(path))

    if ext in {".txt", ".md", ".log"}:
        return parse_text(str(path))

    if ext in {".docx", ".pptx"}:
        return parse_office(str(path))

    if ext in {".xlsx", ".xls"}:
        return parse_spreadsheet(str(path))

    raise ValueError(f"Unsupported file type: {path}")
