"""Evaluate only teacher-as-policy evidence against explicit acceptance rules."""

def evaluate_gate(rows, criteria):
    if not criteria:
        raise ValueError('at least one gate criterion is required')
    results=[]
    for criterion in criteria:
        matches=[r for r in rows if r['phase']=='teacher' and r['metric']==criterion.metric
                 and r['dimension']==criterion.dimension and not r.get('category')
                 and (criterion.group=='*' or str(r['group'])==criterion.group)]
        if not matches:
            results.append({**criterion.model_dump(),'status':'inconclusive','value':None,
                            'known':0,'unknown':0,'trajectory_paths':[], 'reason':'no matching teacher group'})
        seen=set()
        for row in matches:
            if row['group'] in seen:
                raise ValueError('duplicate teacher metric group')
            seen.add(row['group'])
            known,unknown=row['known'],row['unknown']
            fraction=unknown/(known+unknown) if known+unknown else 1.0
            enough=row['value'] is not None and known>=criterion.min_known and fraction<=criterion.max_unknown_fraction
            if not enough:
                status,reason='inconclusive','missing measurement or insufficient known evidence'
            else:
                meets=row['value']>=criterion.threshold if criterion.direction=='min' else row['value']<=criterion.threshold
                status,reason=('passed','threshold met') if meets else ('failed','threshold missed')
            results.append({**criterion.model_dump(),'group':str(row['group']),'status':status,'reason':reason,
                            'value':row['value'],'known':known,'unknown':unknown,'unknown_fraction':fraction,
                            'trajectory_paths':list(row['trajectory_paths'])})
    statuses={r['status'] for r in results}
    status='failed' if 'failed' in statuses else 'inconclusive' if 'inconclusive' in statuses else 'passed'
    return dict(status=status,criteria=results)
