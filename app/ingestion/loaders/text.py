import logfire


def parse_text(file_path: str) -> str:
    """Read a UTF-8 plain-text file."""
    with logfire.span("Text Parsing", filename=file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except Exception:
            logfire.exception("Text parse failed")
            raise
