# app/ingestion/loaders/html.py

from bs4 import BeautifulSoup
import logfire


def parse_html(file_path: str) -> str:
    """Extract readable text from an HTML file."""
    with logfire.span("HTML Parsing", filename=file_path):
        try:
            with open(file_path, "rb") as f:
                content = f.read()

            soup = BeautifulSoup(content, "html.parser")

            for tag in soup(["script", "style", "meta", "noscript"]):
                tag.decompose()

            text = soup.get_text(separator="\n")
            return "\n".join(
                line.strip() for line in text.splitlines() if line.strip()
            )

        except Exception:
            logfire.error("HTML parse failed", filename=file_path)
            raise
# app/ingestion/loaders/html.py

from bs4 import BeautifulSoup
import logfire


def parse_html(file_path: str) -> str:
    """Extract readable text from an HTML file."""
    with logfire.span("HTML Parsing", filename=file_path):
        try:
            with open(file_path, "rb") as f:
                content = f.read()

            soup = BeautifulSoup(content, "html.parser")

            for tag in soup(["script", "style", "meta", "noscript"]):
                tag.decompose()

            text = soup.get_text(separator="\n")
            return "\n".join(
                line.strip() for line in text.splitlines() if line.strip()
            )

        except Exception:
            logfire.error("HTML parse failed", filename=file_path)
            raise
