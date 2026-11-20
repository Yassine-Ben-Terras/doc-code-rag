"""Bounded, local OCR. Document bytes and recognized text are never logged."""
import os
import subprocess


def recognize_page(page):
    import pymupdf
    # Keep rasterization bounded on CPU machines, including oversized images.
    scale = min(150 / 72, 3000 / max(page.rect.width, page.rect.height))
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale),
                             colorspace=pymupdf.csRGB, alpha=False)
    env = os.environ.copy()
    env['OMP_THREAD_LIMIT'] = '1'
    try:
        result = subprocess.run(
            ['tesseract', 'stdin', 'stdout', '-l', 'fra+eng', '--dpi', '150'],
            input=pixmap.tobytes('png'), stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=env, timeout=120, check=True)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('OCR indisponible ou délai dépassé : vérifier Tesseract et les langues fra/eng.') from None
    return result.stdout.decode('utf-8').strip()
