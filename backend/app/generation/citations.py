import re

# Same message for absent and forbidden information, bilingual without revealing scope.
ABSTENTION = "Je ne trouve pas d'information suffisante dans les sources disponibles. / I could not find sufficient information in the available sources."

def abstain():
    return {'answer': ABSTENTION, 'abstained': True, 'sources': []}

def build_response(answer, passages):
    if not answer or 'NO_ANSWER' in answer:
        return abstain()
    numbers = list(dict.fromkeys(int(n) for n in re.findall(r'\[(\d+)\]', answer)))
    valid = [n for n in numbers if 1 <= n <= len(passages)]
    if not valid:
        return abstain()
    answer = re.sub(r'\[(\d+)\]', lambda m: m[0] if int(m[1]) in valid else '', answer)
    sources = []
    for n in valid:
        passage = passages[n-1]
        sources.append({'n': n, 'document': passage['document'], 'section': passage['section_path'],
                        'page': passage['page'], 'lines': f"{passage['line_start']}-{passage['line_end']}" if passage['line_start'] is not None else None,
                        'excerpt': passage['content']})
    return {'answer': answer, 'abstained': False, 'sources': sources}
