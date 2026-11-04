from pathlib import Path
import subprocess,json
pg='/opt/homebrew/opt/postgresql@18/bin/psql'
args=[pg,'-X','-w','-h','127.0.0.1','-p','55459','-U','pilot','-At']
r=subprocess.run(args+['-d','postgres','-c',"SELECT datname FROM pg_database WHERE datname LIKE 'daynomy_android_%_test'"],capture_output=True,text=True,check=True)
db=r.stdout.strip();assert '\n' not in db and db
queries={
 'feedback_exact_one_insert':("SELECT count(*) FROM feedbacks WHERE content='React Native independent synthetic verification'",'1'),
 'member_holding_quantity':("SELECT h.quantity FROM portfolio_holdings h JOIN portfolios p ON p.id=h.portfolio_id WHERE p.member_id=930001 AND h.asset_id=910001",'2'),
 'member_ledger_buy_count':("SELECT count(*) FROM portfolio_holding_histories h JOIN portfolios p ON p.id=h.portfolio_id WHERE p.member_id=930001 AND h.change_type='BUY'",'1'),
 'prior_independent_admin_probe_session_only':("SELECT count(*) FROM refresh_tokens WHERE member_id=930001",'1')}
result=[]
for name,(sql,expected) in queries.items():
 r=subprocess.run(args+['-d',db,'-c',sql],capture_output=True,text=True)
 result.append({'name':name,'exit_code':r.returncode,'value':r.stdout.strip(),'expected':expected,'pass':r.returncode==0 and r.stdout.strip()==expected})
Path(__file__).with_name('db-effects.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0 if all(r['pass'] for r in result) else 1)
