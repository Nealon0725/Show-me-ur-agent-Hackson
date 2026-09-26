import io
import unittest
import zipfile

from tools.resume_reader import ResumeReadError, read_resume


def docx_bytes(paragraphs):
    body = ''.join(
        '<w:p><w:r><w:t>' + text + '</w:t></w:r></w:p>'
        for text in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + body + '</w:body></w:document>'
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('word/document.xml', document)
    return output.getvalue()


def pdf_bytes(text):
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    stream = f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode()
    objects.append(
        b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream'
    )
    content = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for index, item in enumerate(objects, 1):
        offsets.append(len(content))
        content += f'{index} 0 obj\n'.encode() + item + b'\nendobj\n'
    xref = len(content)
    content += f'xref\n0 {len(objects) + 1}\n'.encode() + b'0000000000 65535 f \n'
    for offset in offsets[1:]:
        content += f'{offset:010d} 00000 n \n'.encode()
    content += (
        f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
        f'startxref\n{xref}\n%%EOF\n'
    ).encode()
    return bytes(content)


class ResumeReaderTests(unittest.TestCase):
    def test_reads_docx_paragraphs_as_plain_text(self):
        content = docx_bytes(['Candidate A', 'Two years of accounting experience', 'Excel and Xero'])

        text = read_resume('candidate.docx', content)

        self.assertEqual(
            text,
            'Candidate A\nTwo years of accounting experience\nExcel and Xero',
        )

    def test_rejects_unsupported_file(self):
        with self.assertRaisesRegex(ResumeReadError, 'only PDF and DOCX'):
            read_resume('candidate.txt', b'Candidate resume text')

    def test_rejects_invalid_docx(self):
        with self.assertRaisesRegex(ResumeReadError, 'invalid or damaged'):
            read_resume('candidate.docx', b'not a zip file')

    def test_reads_text_pdf_and_flags_scanned_pdf(self):
        try:
            import pypdf  # noqa: F401
        except ImportError:
            self.skipTest('pypdf is installed from requirements.txt for PDF support')

        text = read_resume('candidate.pdf', pdf_bytes('Candidate has Excel and Xero experience'))
        self.assertIn('Excel and Xero', text)
        with self.assertRaisesRegex(ResumeReadError, 'scanned PDF'):
            read_resume('scanned.pdf', pdf_bytes(''))
