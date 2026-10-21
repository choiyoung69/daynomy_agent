#!/usr/bin/env python3
"""Build an isolated Rust snapshot and run independent suites on disposable DBs."""
import argparse
from contextlib import ExitStack
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from agent_workflow import clean_env, digest, dump, stop_group
from admin_feedback_gate import _deadline_gate_lock as deadline_gate_lock
import run_comparison as spring

ROOT=Path(__file__).resolve().parents[1]
PG=Path('/opt/homebrew/opt/postgresql@18/bin')


def run(output,suites,timeout=900,mock_ai=False,mock_auth=False,mock_fx=False,standalone_schema=False,mock_sync=False,mock_media=False,mock_social=False,mock_schedule=False,source=None,criteria_source=None,mutant=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    candidate=output/'candidate';shutil.copytree(Path(source or ROOT/'app'),candidate,ignore=shutil.ignore_patterns('target'))
    injection=None
    if mutant:
        changes={
            'analysis-v1-cache':('src/service_analysis.rs','let cache = if v1 {','let cache = if false {'),
            'analysis-unsupported-date':('src/service_analysis.rs','if !supported_dates(&issue, &evidence_text) {','if false && !supported_dates(&issue, &evidence_text) {'),
            'csrf-bypass':('src/main.rs','if unsafe_method && !guest_analysis && !csrf::valid(&headers) {','if false && unsafe_method && !guest_analysis && !csrf::valid(&headers) {'),
        }
        path,old,new=changes[mutant];path=candidate/path;original=path.read_text()
        if original.count(old)!=1:raise ValueError('Fault injection anchor must occur exactly once')
        before=digest(path);path.write_text(original.replace(old,new));injection={'name':mutant,'file':str(path.relative_to(candidate)),'before_sha256':before,'after_sha256':digest(path)}
    criteria=output/'criteria';criteria.mkdir()
    for checker in Path(criteria_source or ROOT/'scripts').glob('*.py'):shutil.copyfile(checker,criteria/checker.name)
    sys.path.insert(0,str(criteria))
    started=time.monotonic();deadline=started+timeout
    report={'status':'running','commands':[],'suites':{},'source_hashes':{str(p.relative_to(candidate)):digest(p) for p in candidate.rglob('*') if p.is_file()},'report':str(output/'result.json')}
    report['criteria_hashes']={p.name:digest(p) for p in criteria.glob('*.py')}
    if injection:report['deliberate_fault_injection']=injection
    env=clean_env();env.update(CARGO_HOME=str(ROOT/'.local/cargo'),CARGO_NET_OFFLINE='true',CARGO_TARGET_DIR=str(output/'target'))
    processes=[];created=False;started_db=False
    db='daynomy_'+uuid.uuid4().hex[:10]+'_service_test'
    def save():dump(output/'result.json',report)
    def command(name,args,environment=None,cwd=ROOT,allow_failure=False,input=None):
        before=time.monotonic()
        with (output/(name+'.log')).open('w') as log:
            process=subprocess.Popen(args,stdin=subprocess.PIPE if input else subprocess.DEVNULL,stdout=log,stderr=log,env=environment or env,cwd=cwd,start_new_session=True,text=True)
            try:process.communicate(input,timeout=15 if name in ('database-drop','database-stop') else max(.1,deadline-time.monotonic()))
            finally:stop_group(process)
        code=process.returncode;report['commands'].append({'name':name,'exit_code':code,'seconds':round(time.monotonic()-before,3)});save()
        if code and not allow_failure:raise RuntimeError(name+' failed')
        return code
    previous_local,previous_names=spring.LOCAL,spring.DB_NAMES
    try:
        command('build',['cargo','build','--locked','--offline'],cwd=candidate)
        binary=output/'target/debug/daynomy-feedback';report['binary_sha256']=digest(binary)
        with deadline_gate_lock(deadline):
            started_db=subprocess.run([str(PG/'pg_ctl'),'-D',str(ROOT/'.local/pgdata'),'status'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
            try:
                command('database-start',['bash','scripts/local-db.sh','start'])
                command('database-create',[str(PG/'createdb'),'-h','127.0.0.1','-p','55439','-U','pilot',db]);created=True
                if standalone_schema:
                    migration_env={**env,'PATH':str(PG)+':'+env['PATH'],'DATABASE_URL':'postgresql://pilot@127.0.0.1:55439/'+db}
                    for label in ('initialize','repeat'):
                        command('rust-schema-'+label,[sys.executable,str(criteria/'service_migrate.py'),'--app',str(candidate)],migration_env)
                    report['schema_provisioner']='Rust SQL migrations; Java/Flyway disabled; repeated migration checked'
                manifest=json.loads((ROOT/'.local/comparison/source-snapshot.json').read_text());spring.verify_source(manifest)
                with tempfile.TemporaryDirectory(prefix='daynomy-service-gate-') as temporary, ExitStack() as resources:
                    temp=Path(temporary);spring.LOCAL=temp;spring.DB_NAMES=(db,'unused_test');spring.write_config()
                    props=temp/'application-comparison.properties';props.write_text(props.read_text()+'\njwt.issuer=daynomy\n')
                    if standalone_schema:props.write_text(props.read_text()+'\nspring.flyway.enabled=false\n')
                    key=base64.b64encode(os.urandom(32));secret_file=temp/'fixture-key';secret_file.write_bytes(key);secret_file.chmod(0o600)
                    java=subprocess.check_output(['/usr/libexec/java_home','-v','21'],text=True).strip()
                    javaenv=spring.spring_env(java);javaenv['JWT_SECRET']=key.decode()
                    original=spring.start([java+'/bin/java','-jar',str(ROOT/'.local/spring-reference/build/libs/daynomy-0.0.1-SNAPSHOT.jar')],javaenv,spring.COPY,'original');processes.append(original);spring.ready(original,18082)
                    for migration in sorted((candidate/'migrations').glob('*.sql')):
                        if standalone_schema or migration.name.startswith('001'):continue
                        pgenv={**env,'PGHOST':'127.0.0.1','PGPORT':'55439','PGUSER':'pilot','PGDATABASE':db}
                        command('migration-'+migration.stem,[str(PG/'psql'),'-X','-w','-v','ON_ERROR_STOP=1'],pgenv,input=migration.read_text())
                    runtime={**env,'DATABASE_URL':'postgresql://pilot@127.0.0.1:55439/'+db,'PORT':'18086','APP_TIMEZONE':'Asia/Seoul','JWT_SECRET':key.decode(),'JWT_ISSUER':'daynomy','COOKIE_SECURE':'false'}
                    provider=None
                    if mock_ai:
                        from service_analysis_acceptance import start_mock
                        provider=resources.enter_context(start_mock());runtime.update(provider.environment)
                        report['provider_fixture']='isolated_loopback_only'
                    auth_provider=None
                    if mock_auth:
                        from service_auth_provider_acceptance import start_mock as auth_mock
                        auth_provider=resources.enter_context(auth_mock());runtime.update(auth_provider.environment)
                        runtime['FAILURE_REDIRECT_URI']='/fixture-failure'
                        report['oidc_fixture']='isolated_loopback_ephemeral_rsa_only'
                    fx_provider=None
                    if mock_fx:
                        from service_fx_acceptance import start_mock as fx_mock
                        fx_provider=resources.enter_context(fx_mock());runtime.update(fx_provider.environment)
                        report['fx_fixture']='isolated_loopback_only'
                    sync_provider=None
                    if mock_sync:
                        from service_sync_acceptance import start_mock as sync_mock
                        sync_provider=resources.enter_context(sync_mock());runtime.update(sync_provider.environment)
                        report['sync_fixture']='isolated_loopback_only'
                    media_provider=None
                    if mock_media:
                        from service_media_acceptance import start_mock as media_mock
                        media_provider=resources.enter_context(media_mock());runtime.update(media_provider.environment)
                        report['media_fixture']='isolated_loopback_only_independent_sigv4_validation'
                    social_provider=None
                    if mock_social:
                        from service_social_acceptance import start_mock as social_mock
                        social_provider=resources.enter_context(social_mock());runtime.update(social_provider.environment)
                        report['social_fixture']='isolated_loopback_only'
                    schedule_provider=None
                    if mock_schedule:
                        from service_schedule_acceptance import start_mock as schedule_mock
                        schedule_provider=resources.enter_context(schedule_mock());runtime.update(schedule_provider.environment)
                        report['schedule_fixture']='isolated_loopback_only_signed_cli_jobs'
                    with (temp/'rust.log').open('w') as log:rust=subprocess.Popen([str(binary)],env=runtime,stdout=log,stderr=log,start_new_session=True)
                    processes.append(rust);spring.ready(rust,18086)
                    checkenv={**runtime,'PATH':str(PG)+':'+runtime['PATH']}
                    for suite in suites:
                        script={'public':'service_acceptance.py','core':'service_core_acceptance.py','binding':'service_binding_acceptance.py'}.get(suite,suite+'.py')
                        for label,port in ([('spring',18082),('rust',18086)] if suite in ('public','service_calendar_acceptance') else [('rust',18086)]):
                            name=label+'-'+suite;destination=output/(name+'.json')
                            args=[sys.executable,str(criteria/script),'--base-url','http://127.0.0.1:'+str(port),'--database',runtime['DATABASE_URL'],'--output',str(destination)]
                            if suite not in ('public','binding'):args+=['--jwt-secret-file',str(secret_file)]
                            if suite=='binding':args+=['--reference-url','http://127.0.0.1:18082']
                            if suite=='service_analysis_acceptance' and provider is not None:args+=['--mock-control-url',provider.control_url]
                            if suite=='service_auth_provider_acceptance' and auth_provider is not None:
                                args+=['--mock-control-url',auth_provider.control_url,'--failure-status','302','--failure-redirect','/fixture-failure']
                            if suite=='service_fx_acceptance' and fx_provider is not None:args+=['--mock-control-url',fx_provider.control_url]
                            if suite=='service_sync_acceptance' and sync_provider is not None:args+=['--mock-control-url',sync_provider.control_url]
                            if suite=='service_media_acceptance' and media_provider is not None:args+=['--mock-control-url',media_provider.control_url]
                            if suite=='service_social_acceptance' and social_provider is not None:args+=['--mock-control-url',social_provider.control_url]
                            if suite=='service_schedule_acceptance' and schedule_provider is not None:
                                args=[sys.executable,str(criteria/script),'--binary',str(binary),'--database',runtime['DATABASE_URL'],'--output',str(destination),'--mock-control-url',schedule_provider.control_url]
                            code=command(name,args,checkenv,allow_failure=True)
                            result=json.loads(destination.read_text()) if destination.is_file() else {'status':'missing_result'}
                            report['suites'][name]={'exit_code':code,'passed':result.get('passed',0),'failed':result.get('failed',1),'report':str(destination)};save()
                    spring.verify_source(manifest)
                    if any(digest(candidate/p)!=h for p,h in report['source_hashes'].items()) or digest(binary)!=report['binary_sha256']:raise ValueError('Candidate changed during checks')
                    if any(digest(criteria/p)!=h for p,h in report['criteria_hashes'].items()):raise ValueError('Frozen test criteria changed during checks')
                    report['status']='passed' if all(r['exit_code']==0 and r['failed']==0 for r in report['suites'].values()) else 'failed'
            finally:
                for process in reversed(processes):
                    if process is not processes[0]:stop_group(process)
                    else:spring.stop(process)
                cleanup_errors=[]
                for name,args in ([('database-drop',[str(PG/'dropdb'),'--force','-h','127.0.0.1','-p','55439','-U','pilot',db])] if created else [])+([('database-stop',['bash','scripts/local-db.sh','stop'])] if started_db else []):
                    try:command(name,args)
                    except Exception:cleanup_errors.append(name)
                if cleanup_errors:raise RuntimeError('Cleanup failed: '+','.join(cleanup_errors))
    except Exception as exc:report.update(status='blocked',reason=type(exc).__name__+':'+str(exc))
    finally:
        spring.LOCAL,spring.DB_NAMES=previous_local,previous_names
        if sys.path and sys.path[0]==str(criteria):sys.path.pop(0)
        report['seconds']=round(time.monotonic()-started,3);save()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--suites',nargs='+',default=['public','core']);parser.add_argument('--timeout',type=float,default=900);parser.add_argument('--mock-ai',action='store_true')
    parser.add_argument('--mock-auth',action='store_true')
    parser.add_argument('--mock-fx',action='store_true')
    parser.add_argument('--standalone-schema',action='store_true')
    parser.add_argument('--mock-sync',action='store_true')
    parser.add_argument('--mock-media',action='store_true')
    parser.add_argument('--mock-social',action='store_true')
    parser.add_argument('--mock-schedule',action='store_true')
    parser.add_argument('--source',type=Path,help='Previously frozen app source; copied, never edited in place')
    parser.add_argument('--criteria-source',type=Path,help='Previously frozen Python checker directory')
    parser.add_argument('--mutant',choices=('analysis-v1-cache','analysis-unsupported-date','csrf-bypass'),help='Inject a deliberate defect only inside the isolated candidate')
    args=parser.parse_args()
    if sum((args.mock_ai,args.mock_media,args.mock_social))>1:parser.error('Use one AI provider fixture per gate; their response contracts differ')
    if sum((args.mock_fx,args.mock_sync,args.mock_schedule))>1:parser.error('Use one market-data provider fixture per gate')
    result=run(args.output,args.suites,args.timeout,args.mock_ai,args.mock_auth,args.mock_fx,args.standalone_schema,args.mock_sync,args.mock_media,args.mock_social,args.mock_schedule,args.source,args.criteria_source,args.mutant)
    print(json.dumps({k:result[k] for k in ('status','seconds','suites')}));sys.exit(0 if result['status']=='passed' else 1)
