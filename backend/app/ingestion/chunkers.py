import re
from dataclasses import replace

def chunk_passage(passage, target=1600, overlap=200):
    """Approx. 400 tokens / 50 overlap, preserving paragraph boundaries when possible.

    Character budget is an explicit heuristic (4 chars/token); provenance is sliced
    from original text so line ranges never point outside the cited fragment.
    """
    if target <= overlap or overlap < 0:
        raise ValueError('Invalid chunk budget')
    text = passage.content
    start = 0
    while start < len(text):
        end = min(start + target, len(text))
        if end < len(text):
            boundaries = [m.end() for m in re.finditer(r'\n\s*\n', text[start:end])]
            if boundaries and boundaries[-1] > target // 2:
                end = start + boundaries[-1]
            else:
                boundary = text.rfind(' ', start + target // 2, end)
                if boundary != -1:
                    end = boundary + 1
        content = text[start:end]
        if content.strip():
            first = passage.line_start
            if first is not None:
                first += text[:start].count('\n')
            yield replace(passage, content=content, line_start=first,
                          line_end=first + content.rstrip('\n').count('\n') if first is not None else None)
        if end == len(text):
            break
        next_start = max(start + 1, end - overlap)
        # Avoid beginning in the middle of a word.
        while next_start < end and next_start > 0 and not text[next_start-1].isspace():
            next_start += 1
        start = next_start
