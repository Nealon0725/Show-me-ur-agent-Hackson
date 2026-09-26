"""Local document ingestion. Original files and extracted text stay in SQLite."""
import base64
import io
import re
import sqlite3
import uuid
import zipfile
from contextlib import closing
from pathlib import Path
from xml.etree import ElementTree

MAX_BYTES = 10 * 1024 * 1024


def extract_text(name, content):
    if not content or len(content) > MAX_BYTES:
        raise ValueError('文件为空或超过 10 MB。')
    suffix = Path(name).suffix.lower()
    if suffix == '.txt':
        text = None
        for encoding in ('utf-8-sig', 'utf-16' if content[:2] in (b'\xff\xfe', b'\xfe\xff') else 'gb18030'):
            try:
                text = content.decode(encoding)
                break
            except UnicodeError:
                pass
        if text is None or '\x00' in text:
            raise ValueError('无法读取 TXT 编码，请另存为 UTF-8。')
    elif suffix == '.pdf':
        from pypdf import PdfReader
        if not content.startswith(b'%PDF-'):
            raise ValueError('不是有效的 PDF 文件。')
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted and not reader.decrypt(''):
                raise ValueError('PDF 已加密，请先移除密码。')
            if len(reader.pages) > 50:
                raise ValueError('简历 PDF 最多支持 50 页。')
            pages = [page.extract_text() or '' for page in reader.pages]
            if any(len(re.sub(r'\s', '', page)) < 10 for page in pages):
                raise ValueError('PDF 含无法提取文字的页面，可能是扫描件。请上传带文字层的 PDF、DOCX 或 TXT。')
            text = '\n\n'.join(pages)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError('PDF 读取失败，请重新导出后上传。') from exc
    elif suffix == '.docx':
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 30 * 1024 * 1024:
                    raise ValueError('DOCX 解压内容过大。')
                xml = archive.read('word/document.xml')
                if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
                    raise ValueError('不支持此 DOCX 内容。')
                root = ElementTree.fromstring(xml)
                ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                text = '\n'.join(''.join(p.itertext()) for p in root.iter(ns + 'p'))
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
            raise ValueError('不是有效的 DOCX 文件，请重新导出。') from exc
    else:
        raise ValueError('仅支持 PDF、DOCX 和 TXT 文件。')
    text = text.strip()
    if not text or len(text) > 50000:
        raise ValueError('提取文字为空或超过 50,000 字符，请检查文件。')
    return text


class Documents:
    def __init__(self, path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, job_id TEXT, name TEXT, content BLOB, text TEXT)')

    def add(self, payload):
        name = payload.get('name')
        if not isinstance(name, str) or not 1 <= len(name) <= 255:
            raise ValueError('文件名无效。')
        try:
            content = base64.b64decode(payload.get('content', ''), validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('文件内容无效。') from exc
        text = extract_text(name, content)
        doc_id = 'UP-' + uuid.uuid4().hex
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO documents VALUES (?, ?, ?, ?, ?)', (doc_id, payload['job_id'], name, content, text))
        return self.get(doc_id)

    def get(self, doc_id, binary=False):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT id,job_id,name,content,text FROM documents WHERE id=?', (doc_id,)).fetchone()
        if row is None:
            raise KeyError(doc_id)
        if binary:
            return row[2], row[3]
        return {'id': row[0], 'jobId': row[1], 'name': Path(row[2]).stem, 'uploadName': row[2], 'uploadSize': len(row[3]),
                'text': row[4], 'pdf': '/api/uploads/' + row[0] if row[2].lower().endswith('.pdf') else None,
                'download': '/api/uploads/' + row[0], 'synthetic': False, 'role': 'Uploaded résumé', 'skills': [],
                'months': None, 'education': '', 'experience': [], 'project': '', 'certifications': '',
                'criteria': [], 'label': 'pending', 'email': ''}

    def list(self):
        with closing(sqlite3.connect(self.path)) as db:
            ids = [r[0] for r in db.execute('SELECT id FROM documents ORDER BY rowid')]
        return [self.get(doc_id) for doc_id in ids]
