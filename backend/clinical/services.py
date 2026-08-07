"""Document helpers: text extraction from the psychologist's own uploaded
reports (never from published instruments — those are not in the system)."""


def extract_pdf_text(django_file, max_chars=200_000):
    """Extract text from an uploaded PDF using PyMuPDF. Returns '' for
    non-PDF or unreadable files — extraction is best-effort, never fatal."""
    try:
        import fitz  # PyMuPDF
        django_file.seek(0)
        data = django_file.read()
        django_file.seek(0)
        text_parts = []
        with fitz.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                text_parts.append(page.get_text())
                if sum(len(t) for t in text_parts) > max_chars:
                    break
        return ("\n".join(text_parts))[:max_chars].strip()
    except Exception:
        return ""
