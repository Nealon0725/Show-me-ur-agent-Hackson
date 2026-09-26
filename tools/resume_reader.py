"""Extract plain text from resume files without changing their contents."""

import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree


MAX_FILE_BYTES = 5 * 1024 * 1024
SUPPORTED_EXTENSIONS = {'.pdf', '.docx'}
WORD_NAMESPACE = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


class ResumeReadError(ValueError):
    """Raised when a resume cannot be safely converted to plain text."""


def read_resume(filename, content):
    """Return text from one PDF or DOCX resume supplied as bytes."""
    if not isinstance(filename, str) or not filename.strip():
        raise ResumeReadError('The resume filename is missing.')
    if not isinstance(content, bytes):
        raise ResumeReadError('The resume content must be bytes.')
    if not content:
        raise ResumeReadError(f'{filename}: the file is empty.')
    if len(content) > MAX_FILE_BYTES:
        raise ResumeReadError(f'{filename}: the file is larger than 5 MB.')

    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ResumeReadError(f'{filename}: only PDF and DOCX files are supported.')
    text = _read_pdf(content, filename) if extension == '.pdf' else _read_docx(content, filename)
    text = _normalise(text)
    if len(text) < 20:
        if extension == '.pdf':
            raise ResumeReadError(
                f'{filename}: no readable text was found. It may be a scanned PDF; '
                'please use a text-based PDF or paste the text manually.'
            )
        raise ResumeReadError(f'{filename}: no readable resume text was found.')
    return text


def _read_pdf(content, filename):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ResumeReadError(
            'PDF support is not installed. Run: python3 -m pip install -r requirements.txt'
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(content))
        return '\n\n'.join((page.extract_text() or '') for page in reader.pages)
    except Exception as exc:
        raise ResumeReadError(f'{filename}: the PDF could not be read.') from exc


def _read_docx(content, filename):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            document_info = archive.getinfo('word/document.xml')
            if document_info.file_size > 10 * 1024 * 1024:
                raise ResumeReadError(f'{filename}: the DOCX document content is too large.')
            xml = archive.read('word/document.xml')
    except ResumeReadError:
        raise
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ResumeReadError(f'{filename}: the DOCX file is invalid or damaged.') from exc

    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ResumeReadError(f'{filename}: the DOCX document content is invalid.') from exc

    ns = {'w': WORD_NAMESPACE}
    paragraphs = []
    for paragraph in root.findall('.//w:p', ns):
        pieces = []
        for node in paragraph.iter():
            if node.tag == f'{{{WORD_NAMESPACE}}}t' and node.text:
                pieces.append(node.text)
            elif node.tag == f'{{{WORD_NAMESPACE}}}tab':
                pieces.append('\t')
            elif node.tag in {f'{{{WORD_NAMESPACE}}}br', f'{{{WORD_NAMESPACE}}}cr'}:
                pieces.append('\n')
        line = ''.join(pieces).strip()
        if line:
            paragraphs.append(line)
    return '\n'.join(paragraphs)


def _normalise(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\x00', '')
    return '\n'.join(line.rstrip() for line in text.splitlines()).strip()
