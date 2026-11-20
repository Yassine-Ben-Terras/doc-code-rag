"""Combine measured runs; never fill unmeasured cells with assumed numbers."""
import argparse
import json
from pathlib import Path

def percent(value):
    return f'{100*value:.1f} %' if isinstance(value,(float,int)) else 'non mesuré'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('runs',nargs='+',help='Metric .json files produced by run_eval.py')
    parser.add_argument('--output',default='eval/results/report.md')
    args=parser.parse_args()
    lines=['# Rapport d’évaluation mesurée','',
           'Les résultats concernent uniquement le corpus, le modèle et le matériel effectivement testés.', '',
           '| Configuration | Préfixe | Recall@5 | FR→EN | FR→FR | Abstention correcte | Fuites | Latence p50 |',
           '|---|---|---|---|---|---|---|---|']
    review_lines=[]
    for name in args.runs:
        path=Path(name)
        run=json.loads(path.read_text(encoding='utf-8'))
        latency=run['median_latency_seconds']
        lines.append(f"| {run['mode']} | {run['prefix']} | {percent(run['recall_at_5'])} | {percent(run['recall_fr_en'])} | {percent(run['recall_fr_fr'])} | {percent(run['correct_abstention'])} | {run['leaks']} | {latency:.2f} s |" if latency is not None else '| Jeu vide | — | — | — | — | — | — | — |')
        reviews=[json.loads(line) for line in path.with_suffix('.jsonl').read_text(encoding='utf-8').splitlines()]
        answered=[r for r in reviews if not r['response']['abstained']]
        reviewed=[r for r in answered if isinstance(r.get('citation_correct'),bool)]
        if reviewed:
            review_lines.append(f"Citations ({path.stem}) : {percent(sum(r['citation_correct'] for r in reviewed)/len(reviewed))}, {len(reviewed)}/{len(answered)} réponses vérifiées manuellement.")
    lines.extend(['']+review_lines)
    lines.extend(['','Une réussite des tests de non-fuite ne constitue pas une mesure de Recall@5 ou une preuve de fidélité sémantique des citations.',
                  'Comparer les quatre configurations sur le même jeu de test, après calibration sur le sous-ensemble séparé.'])
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(output)

if __name__=='__main__':
    main()
