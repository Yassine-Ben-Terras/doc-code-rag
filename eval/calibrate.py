"""Choose a threshold using calibration predictions only; report rather than overwrite configuration."""
import json
import sys
from pathlib import Path

rows = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding='utf-8').splitlines()]
if not rows or any(r['split']!='calibration' for r in rows):
    raise SystemExit('Use calibration split only; test data must remain held out.')
results = []
for step in range(101):
    threshold = step/100
    positives = [r for r in rows if r['answerable']]
    negatives = [r for r in rows if not r['answerable']]
    if not positives or not negatives:
        raise SystemExit('Calibration needs answerable and unanswerable examples.')
    sensitivity = sum(r['max_score']>=threshold for r in positives)/len(positives)
    specificity = sum(r['max_score']<threshold for r in negatives)/len(negatives)
    results.append({'threshold':threshold,'balanced_accuracy':(sensitivity+specificity)/2,'accept_answerable':sensitivity,'reject_unanswerable':specificity})
print(json.dumps(max(results,key=lambda r:(r['balanced_accuracy'],r['reject_unanswerable'])),indent=2))
