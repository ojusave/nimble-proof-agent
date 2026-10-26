"""Local résumé parsing. Original file and text stay in the local data directory."""
import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree
from pypdf import PdfReader

MAX_FILE = 3 * 1024 * 1024
MAX_TEXT = 18000


def parse_resume(filename: str, content: bytes) -> str:
    if not content or len(content) > MAX_FILE:
        raise ValueError('Upload a résumé smaller than 3 MB.')
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == '.pdf':
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise ValueError('Upload an unencrypted PDF.')
            if len(reader.pages) > 10:
                raise ValueError('Use a résumé of 10 pages or fewer.')
            text = '\n'.join((page.extract_text() or '') for page in reader.pages)
        elif suffix == '.docx':
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                info = archive.getinfo('word/document.xml')
                if info.file_size > 2_000_000:
                    raise ValueError('Document content is too large.')
                xml = archive.read(info)
                if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
                    raise ValueError('Unsupported document XML.')
                root = ElementTree.fromstring(xml)
                text = '\n'.join(''.join(p.itertext()) for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))
        elif suffix == '.txt':
            text = content.decode('utf-8-sig')
        else:
            raise ValueError('Use a PDF, DOCX, or UTF-8 TXT résumé.')
    except ValueError:
        raise
    except Exception:
        raise ValueError('Could not read this résumé. Try exporting it as a text-based PDF or TXT.') from None
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text).strip()
    if len(text) < 80:
        raise ValueError('Not enough readable text. Scanned PDFs need OCR first; try DOCX or TXT.')
    if len(text) > MAX_TEXT:
        raise ValueError('Résumé text exceeds 18,000 characters. Upload a shorter version.')
    return text


from core.text import professional_text
