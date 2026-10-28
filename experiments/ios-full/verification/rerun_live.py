import base64,hashlib,json,os,subprocess,uuid,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
PG=Path('/opt/homebrew/opt/postgresql@18/bin')
def sql(s):
 p=subprocess.run([str(PG/'psql'),'-X','-w','-A','-t','-v','ON_ERROR_STOP=1','-h','127.0.0.1','-p','55561','-U','pilot','-d','ios_full30_service_test'],input=s,capture_output=True,text=True,timeout=15)
 if p.returncode:raise RuntimeError('Isolated SQL failed; details withheld')
 return p.stdout.strip()
env=os.environ.copy();env['IOS_FIXTURE_BASE_URL']='http://127.0.0.1:18096'
sql("INSERT INTO members(id,provider,provider_id,email,nickname,role,status,created_at,updated_at) VALUES(970002,'GOOGLE','ios-admin-fixture','iosadmin@fixture.invalid','iosadminfixture','ADMIN','ACTIVE',now(),now()) ON CONFLICT(id) DO NOTHING;")
for member,prefix in [(970001,'IOS_FIXTURE_AUTH'),(970002,'IOS_FIXTURE_ADMIN')]:
 code=uuid.uuid4().hex+uuid.uuid4().hex;verifier=base64.urlsafe_b64encode(os.urandom(48)).rstrip(b'=').decode();challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
 sql("INSERT INTO mobile_auth_codes(code_hash,member_id,code_challenge,expires_at) VALUES('"+hashlib.sha256(code.encode()).hexdigest()+"',"+str(member)+",'"+challenge+"',now()+interval '60 seconds');")
 env[prefix+'_CODE']=code;env[prefix+'_VERIFIER']=verifier
before=int(sql('SELECT count(*) FROM feedbacks;'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'clients/ios/Sources/DaynomyCore').glob('*.swift')}
with (OUT/'full-live-final.log').open('w') as log:r=subprocess.run([str(OUT/'full-live')],env=env,stdout=log,stderr=log,timeout=60)
after=int(sql('SELECT count(*) FROM feedbacks;'))
report={'exit_code':r.returncode,'source_hashes':sources,'sources_unchanged_after':all(sha(ROOT/p)==h for p,h in sources.items()),'feedback_before':before,'feedback_after':after,'expected_delta':0,'note':'One feedback created then admin deleted; own isolated synthetic cluster only. No real provider.','fixture_binary_sha256':sha(ROOT/'.local/ios-full30-verifier-0936/daynomy-feedback')}
(OUT/'full-live-final-result.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(r.returncode)
