"""Text-only document processing; no Odoo paths or legacy application imports."""
from io import BytesIO
from pathlib import Path
import zipfile

SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".csv", ".log", ".html", ".htm", ".xlsx", ".xls"}


def extract_text(filename, content, max_chars=1_000_000):
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError("Unsupported document format")
    if suffix in {".docx", ".xlsx"}:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 100_000_000:
                raise ValueError("Expanded document is too large")
    def pieces():
        if suffix == ".pdf":
            from pypdf import PdfReader
            for page in PdfReader(BytesIO(content)).pages:
                yield page.extract_text() or ""
        elif suffix == ".docx":
            from docx import Document
            doc = Document(BytesIO(content))
            for paragraph in doc.paragraphs:
                yield paragraph.text
            for table in doc.tables:
                for row in table.rows:
                    yield " | ".join(cell.text for cell in row.cells)
        elif suffix == ".xlsx":
            from openpyxl import load_workbook
            book = load_workbook(BytesIO(content), read_only=True, data_only=True)
            try:
                for sheet in book:
                    yield sheet.title
                    for row in sheet.iter_rows(values_only=True):
                        yield " | ".join("" if cell is None else str(cell) for cell in row)
            finally:
                book.close()
        elif suffix == ".xls":
            import xlrd
            book = xlrd.open_workbook(file_contents=content, on_demand=True)
            try:
                for sheet in book.sheets():
                    yield sheet.name
                    for i in range(sheet.nrows):
                        yield " | ".join(str(v) for v in sheet.row_values(i))
            finally:
                book.release_resources()
        elif suffix in {".html", ".htm"}:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["script", "style"]):
                tag.decompose()
            yield soup.get_text("\n", strip=True)
        else:
            yield content.decode("utf-8-sig")
    parts, count = [], 0
    for piece in pieces():
        count += len(piece) + 1
        if count > max_chars:
            raise ValueError("Extracted text exceeds the configured limit")
        parts.append(piece)
    text = "\n".join(parts).replace("\x00", "").strip()
    if not text:
        raise ValueError("No text found; scanned documents require OCR outside this service")
    return text


def chunks(text, size=3000, overlap=300, maximum=500):
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Invalid chunk settings")
    output = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        output.append(text[start:end])
        if len(output) > maximum:
            raise ValueError("Too many chunks; split the document")
        if end == len(text):
            break
        start = end - overlap
    return output
