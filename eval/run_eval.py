"""Run inside API container with local retrieval, a configured external LLM and an indexed corpus."""
import argparse
import json
import statistics
import time
from pathlib import Path
from app.core.db import transaction
from app.api.chat import answer_question

def mean(values):
    return sum(values)/len(values) if values else None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset',default='/eval/dataset.jsonl')
    parser.add_argument('--mode',choices=['dense','hybrid','rerank'],default='rerank')
    parser.add_argument('--prefix',choices=['on','off'],required=True,help='Must match the indexed corpus; reindex to change.')
    parser.add_argument('--threshold',type=float,default=0.5)
    parser.add_argument('--split',choices=['calibration','test','all'],default='test')
    parser.add_argument('--output',default='/eval/results/run')
    args = parser.parse_args()
    records = []
    for case in map(json.loads,Path(args.dataset).read_text(encoding='utf-8').splitlines()):
        if args.split!='all' and case['split']!=args.split:
            continue
        start = time.perf_counter()
        with transaction() as db:
            # Evaluation deliberately fails if run under a BYPASSRLS identity.
            role = db.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
            if role['rolsuper'] or role['rolbypassrls']:
                raise RuntimeError('Evaluation requires api_role (RLS enabled)')
            user = db.execute('SELECT u.id,u.role_id,r.name AS role FROM users u JOIN roles r ON r.id=u.role_id WHERE email=%s',(case['user'],)).fetchone()
            if not user:
                raise RuntimeError('Missing evaluation user: '+case['user'])
            db.execute("SELECT set_config('app.user_id',%s,true)",(str(user['id']),))
            response, passages = answer_question(db,user,case['question'],mode=args.mode,threshold=args.threshold)
            allowed = {str(r['collection_id']) for r in db.execute('SELECT collection_id FROM collection_permissions WHERE role_id=%s',(user['role_id'],))}
        leaked = any(str(p['collection_id']) not in allowed for p in passages)
        serialized = json.dumps(response,ensure_ascii=False)+' '.join(p['content'] for p in passages)
        leaked |= any(marker in serialized for marker in case.get('forbidden_markers',[]))
        hit = any(p['document']==case.get('expected_document') and case.get('expected_text','') in p['content'] for p in passages)
        records.append(dict(case,response=response,recall_hit=hit,leak=leaked,latency=time.perf_counter()-start,
            max_score=max((p.get('score',0) for p in passages),default=0),
            citation_correct=None,answer_language_correct=None,
            retrieved=[{'document':p['document'],'section':p['section_path'],'score':p.get('score')} for p in passages]))
    metrics = {'mode':args.mode,'prefix':args.prefix,'threshold':args.threshold,'split':args.split,'questions':len(records),
        'recall_at_5':mean([r['recall_hit'] for r in records if r['answerable']]),
        'recall_fr_en':mean([r['recall_hit'] for r in records if r['answerable'] and r['question_language']=='fr' and r['document_language']=='en']),
        'recall_fr_fr':mean([r['recall_hit'] for r in records if r['answerable'] and r['question_language']=='fr' and r['document_language']=='fr']),
        'correct_abstention':mean([r['response']['abstained'] for r in records if not r['answerable']]),
        'false_abstention':mean([r['response']['abstained'] for r in records if r['answerable']]),
        'median_latency_seconds':statistics.median(r['latency'] for r in records) if records else None,
        'leaks':sum(r['leak'] for r in records),'citation_accuracy':'manual review required',
        'corpus':'synthetic demo; replace with internal annotated questions for acceptance'}
    metrics['recall_fr_en_minus_fr_fr'] = (metrics['recall_fr_en']-metrics['recall_fr_fr']) if metrics['recall_fr_en'] is not None and metrics['recall_fr_fr'] is not None else None
    base = Path(args.output)
    base.parent.mkdir(parents=True,exist_ok=True)
    base.with_suffix('.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    base.with_suffix('.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,default=str)+'\n' for r in records),encoding='utf-8')
    print(json.dumps(metrics,indent=2))
    if metrics['leaks']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
