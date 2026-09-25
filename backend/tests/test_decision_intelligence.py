import json
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.decision_intelligence import _sheet_brief, build_decision_brief

SOURCE = {'sheet_id': 1, 'sheet': 'Records', 'file': 'sample.csv'}
def analyze(rows):
    return _sheet_brief(rows, list(rows[0]) if rows else [], SOURCE)

def test_scope_and_production_snapshot():
    conn=sqlite3.connect(':memory:');conn.row_factory=sqlite3.Row
    conn.executescript('CREATE TABLE dataset_uploads(id INTEGER, original_name TEXT); CREATE TABLE sheets(id INTEGER,dataset_id INTEGER,name TEXT,columns_json TEXT); CREATE TABLE sheet_rows(sheet_id INTEGER,row_index INTEGER,data_json TEXT);')
    conn.execute('INSERT INTO dataset_uploads VALUES(1,?)',('fixture.csv',))
    for sid in (1,2):
        conn.execute('INSERT INTO sheets VALUES(?,?,?,?)',(sid,1,f'Sheet{sid}',json.dumps(['Region','Revenue'])))
        conn.executemany('INSERT INTO sheet_rows VALUES(?,?,?)',[(sid,i,json.dumps({'Region':'A' if i < 5 else 'B','Revenue':i*sid})) for i in range(10)])
    conn.execute("ALTER TABLE sheets ADD COLUMN profile_json TEXT DEFAULT '[]'")
    conn.execute('UPDATE sheets SET profile_json=?', (json.dumps([{'column': 'Revenue', 'display_name': 'Recognized revenue'}]),))
    before=build_decision_brief(conn,1)
    assert before['profiles'][0]['display_columns']['Revenue'] == 'Recognized revenue'
    assert all(c['metric_label'] == 'Recognized revenue' for c in before['profiles'][0]['comparisons'])
    assert before['profiles'][0]['comparisons'][0]['metric'] == 'Revenue'
    assert len(before['profiles'])==1
    conn.execute('UPDATE sheet_rows SET data_json=? WHERE sheet_id=2 AND row_index=0',(json.dumps({'Region':'B','Revenue':99999999}),))
    assert build_decision_brief(conn,1)['snapshot']==before['snapshot']
    conn.execute('UPDATE sheet_rows SET data_json=? WHERE sheet_id=1 AND row_index=0',(json.dumps({'Region':'A','Revenue':20}),))
    assert build_decision_brief(conn,1)['snapshot']!=before['snapshot']
    assert len(build_decision_brief(conn)['profiles'])==2

@pytest.mark.parametrize('column,domain',[('Revenue','Sales'),('Clicks','Marketing'),('Resolution hours','IT operations'),('Attendance','People operations'),('Weight','Business operations')])
def test_domains(column,domain):
    result=analyze([{'Region':'A' if i<10 else 'B',column:i} for i in range(20)])
    assert result['domain']==domain
    assert result['comparisons'][0]['metric']==column
    assert any(f['kind']=='comparison' for f in result['findings'])

def test_unknown_identity_and_small_groups():
    result=analyze([{'ID':f'{i:03}','Full Name':i,'Team':'A' if i<5 else 'B','Revenue':None if i==0 else i} for i in range(10)])
    assert all(c['metric'] not in ('ID','Full Name') for c in result['comparisons'])
    a=next(g for g in result['comparisons'][0]['groups'] if g['group']=='A')
    assert (a['value'],a['used_rows'],a['missing_rows'])==(2.5,4,1)
    assert not any(f['kind']=='comparison' for f in result['findings'])

def test_wide_years_and_missing():
    rows=[{'Department':'A','1st to 5th July 2025':1,'6th to 12th July 2025':2,'1st to 5th July 2026':4} for _ in range(10)]
    rows[0]['6th to 12th July 2025']=None
    result=analyze(rows)
    derived=[f for f in result['fields'] if f['role']=='derived_period_total']
    assert {f['column'].split(' · ')[0] for f in derived}=={'July 2025','July 2026'}
    assert any(f['kind']=='quality' and '2025' in f['metric'] for f in result['findings'])

def test_pairwise_correlation_guards():
    result=analyze([{'Spend':i,'Clicks':i*i,'Total Clicks':i*10} for i in range(20)])
    p=next(p for p in result['matrix']['pairs'] if p['x']=='Spend' and p['y']=='Clicks')
    assert p['coefficient']==1 and p['paired_rows']==20
    assert all(p['coefficient'] is None for p in result['matrix']['pairs'] if 'Total Clicks' in (p['x'],p['y']) and 'Clicks' in (p['x'],p['y']))
    assert analyze([{'Spend':i,'Clicks':i*i} for i in range(8)])['matrix']['pairs'][0]['coefficient'] is None

def test_monthly_means():
    rows=[{'Date':f'2026-07-{i+1:02}','Revenue':10} for i in range(10)]+[{'Date':f'2026-08-{i+1:02}','Revenue':30} for i in range(10)]
    result=analyze(rows)
    assert [(p['period'],p['value']) for p in result['trends'][0]['points']]==[('2026-07',10),('2026-08',30)]
    assert any(f['kind']=='movement' for f in result['findings'])

def test_empty_text_only_and_all_groups():
    assert analyze([])['findings']==[]
    assert analyze([{'Comment':f'text {i}'} for i in range(5)])['measures_analyzed']==0
    assert len(analyze([{'Department':f'D{i//5}','Attendance':i%7} for i in range(150)])['comparisons'][0]['groups'])==30

def test_repeated_ids_disclosed():
    result=analyze([{'ID':'001','Team':'A' if i<5 else 'B','Revenue':i} for i in range(10)])
    assert any('repeated identifiers' in l for l in result['limitations'])
    assert result['row_count']==10

def test_route_empty_missing_scope():
    client=TestClient(app)
    assert client.get('/api/analytics/decision-brief').json()['empty']
    assert client.get('/api/analytics/decision-brief?sheet_id=999').status_code==404

def test_ai_cannot_change_claims(monkeypatch):
    from app.routers import decision_brief as route
    findings=analyze([{'Region':'A' if i<10 else 'B','Revenue':i} for i in range(20)])['findings']
    monkeypatch.setattr(route,'decision_brief',lambda sid:{'snapshot':'test','findings':findings})
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'response':json.dumps({'finding_ids':['invented']})}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):return Response()
    monkeypatch.setattr(route.httpx,'Client',Client)
    result=route.prioritize(route.PrioritizeRequest(snapshot='test'))
    assert result['findings']==findings and 'unavailable' in result['ai_status']
    with pytest.raises(Exception) as err:route.prioritize(route.PrioritizeRequest(snapshot='stale'))
    assert err.value.status_code==409

def test_group_mix_reversal_is_detected():
    rows=[{'Region':group,'Spend':offset+i,'Clicks':offset+20-i} for group,offset in [('A',0),('B',100)] for i in range(20)]
    result=analyze(rows)
    assert any('Group mix reverses' in f['title'] for f in result['findings'])
    pair=result['matrix']['pairs'][0]
    assert pair['coefficient']>0
    assert all(g['coefficient']==-1 for g in pair['within_groups'])

def test_flag_is_dimension_not_performance_metric():
    result=analyze([{'Store':i//5,'Holiday Flag':i%2,'Weekly Sales':100+i} for i in range(20)])
    assert next(f for f in result['fields'] if f['column']=='Holiday Flag')['role']=='dimension'
    assert all(f['metric']!='Holiday Flag' for f in result['findings'])
