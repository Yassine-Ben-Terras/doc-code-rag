import shutil
import subprocess
import pytest
import pymupdf
from app.ingestion.parsers import parse_file


@pytest.fixture
def scan(tmp_path):
    with pymupdf.open() as document:
        page = document.new_page(width=600, height=250)
        page.insert_text((40, 70), 'Planify organise les emplois du temps.', fontsize=22)
        page.insert_text((40, 120), 'Students consult their weekly schedule.', fontsize=22)
        path = tmp_path / 'scan.png'
        page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(path)
    return path


needs_tesseract = pytest.mark.skipif(not shutil.which('tesseract'), reason='Run in backend Docker image with Tesseract')


@needs_tesseract
@pytest.mark.parametrize('extension', ['png', 'jpg', 'jpeg'])
def test_image_real_ocr(scan, tmp_path, extension):
    path = tmp_path / f'image.{extension}'
    pymupdf.Pixmap(scan).save(path)
    passages = list(parse_file(path, path.name))
    assert len(passages) == 1
    assert 'Planify' in passages[0].content
    assert 'weekly schedule' in passages[0].content
    assert passages[0].page == 1
    assert passages[0].section_path.endswith(' > OCR')


@needs_tesseract
def test_mixed_pdf_keeps_native_text_and_recognizes_scanned_page(scan, tmp_path):
    path = tmp_path / 'mixed.pdf'
    with pymupdf.open() as document:
        page = document.new_page(width=600, height=250)
        page.insert_text((40, 70), 'Native document introduction')
        page = document.new_page(width=600, height=250)
        page.insert_image(page.rect, filename=str(scan))
        assert not page.get_text().strip()
        document.save(path)
    passages = list(parse_file(path, path.name))
    assert len(passages) == 2
    assert passages[0].content == 'Native document introduction'
    assert not passages[0].section_path.endswith(' > OCR')
    assert 'Planify' in passages[1].content
    assert passages[1].page == 2
    assert passages[1].section_path.endswith(' > OCR')


def test_native_pdf_does_not_require_ocr(tmp_path, monkeypatch):
    def unexpected_ocr(page):
        raise AssertionError('Native text should bypass OCR')
    monkeypatch.setattr('app.ingestion.ocr.recognize_page', unexpected_ocr)
    path = tmp_path / 'native.pdf'
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((40, 70), 'Already searchable')
        document.save(path)
    assert list(parse_file(path, path.name))[0].content == 'Already searchable'


def test_ocr_timeout_is_safe_and_bounded(scan, monkeypatch):
    def timeout(command, **kwargs):
        assert kwargs['timeout'] == 120
        assert kwargs['env']['OMP_THREAD_LIMIT'] == '1'
        raise subprocess.TimeoutExpired(command, 120, output=b'private document text')
    monkeypatch.setattr('app.ingestion.ocr.subprocess.run', timeout)
    with pytest.raises(ValueError, match='OCR indisponible') as error:
        list(parse_file(scan, scan.name))
    assert 'private document text' not in str(error.value)
