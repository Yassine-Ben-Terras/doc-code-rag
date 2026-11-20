from dataclasses import dataclass
from pathlib import Path
import re

@dataclass
class Passage:
    content: str
    section_path: str
    page: int | None = None
    line_start: int | None = None
    line_end: int | None = None

def parse_file(path: Path, name: str):
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        import pymupdf
        with pymupdf.open(path) as doc:
            toc = doc.get_toc()
            for number, page in enumerate(doc, 1):
                headings = []
                for level, title, start in toc:
                    if start > number:
                        continue
                    headings = headings[:level-1]
                    headings.append(title)
                section = ' > '.join([name] + headings) if headings else f'{name} > p.{number}'
                text = page.get_text().strip()
                if not text:
                    from app.ingestion.ocr import recognize_page
                    text = recognize_page(page)
                    section += ' > OCR'
                if text:
                    yield Passage(text, section, page=number)
    elif suffix in {'.png', '.jpg', '.jpeg'}:
        import pymupdf
        from app.ingestion.ocr import recognize_page
        with pymupdf.open(path) as image:
            if text := recognize_page(image[0]):
                yield Passage(text, f'{name} > OCR', page=1)
    elif suffix == '.docx':
        from docx import Document
        doc = Document(path)
        headings, paragraphs = [], []
        for para in doc.paragraphs:
            match = re.match(r'Heading (\d+)', para.style.name or '')
            if match:
                if paragraphs:
                    yield Passage('\n\n'.join(paragraphs), ' > '.join([name]+headings))
                    paragraphs = []
                headings = headings[:int(match[1])-1] + [para.text]
            elif para.text.strip():
                paragraphs.append(para.text)
        if paragraphs:
            yield Passage('\n\n'.join(paragraphs), ' > '.join([name]+headings))
        # Table extraction is intentionally plain; complex layouts remain out of scope.
        for i, table in enumerate(doc.tables, 1):
            yield Passage('\n'.join(' | '.join(c.text for c in row.cells) for row in table.rows), f'{name} > Tableau {i}')
    else:
        text = path.read_text(encoding='utf-8-sig')
        if '\x00' in text:
            raise ValueError('Fichier binaire non pris en charge')
        if suffix != '.md':
            yield Passage(text, name)
            return
        headings, lines = [], []
        start, fence = 1, None
        for number, line in enumerate(text.splitlines(), 1):
            marker = re.match(r'^\s*(`{3,}|~{3,})', line)
            if marker:
                if fence is None:
                    fence = marker[1][0]
                elif fence == marker[1][0]:
                    fence = None
            match = re.match(r'^(#{1,6})\s+(.+)', line) if fence is None else None
            if match:
                if lines:
                    yield Passage('\n'.join(lines), ' > '.join([name]+headings), line_start=start, line_end=number-1)
                headings = headings[:len(match[1])-1] + [match[2].strip()]
                lines, start = [line], number
            else:
                lines.append(line)
        if lines:
            yield Passage('\n'.join(lines), ' > '.join([name]+headings), line_start=start, line_end=len(text.splitlines()))

def parse_code(path: Path, name: str):
    text = path.read_text(encoding='utf-8-sig')
    if '\x00' in text:
        return
    lines = text.splitlines()
    for start in range(0, len(lines), 50):
        end = min(start+60, len(lines))
        yield Passage('\n'.join(lines[start:end]), name, line_start=start+1, line_end=end)
        if end == len(lines):
            break
