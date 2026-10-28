#!/usr/bin/env python3
"""Run independent numeric edges and read-only shared Rust HTTP integration."""
import hashlib,json,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 candidate=json.loads((OUT/'candidate-result.json').read_text())
 assert candidate['status']=='passed-host-and-loopback'
 assert all(sha(ROOT/p)==h for p,h in candidate['candidate_hashes'].items())
 sources=sorted((ROOT/'clients/ios/Sources/DaynomyCore').glob('*.swift'))
 report={'started_at':datetime.now(timezone.utc).isoformat(),'commands':[],'candidate_result_sha256':sha(OUT/'candidate-result.json')}
 def run(label,command):
  start=time.monotonic();p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=60)
  (OUT/(label+'.log')).write_text(p.stdout+p.stderr)
  report['commands'].append({'label':label,'argv':command,'exit_code':p.returncode,'seconds':time.monotonic()-start})
  (OUT/'supplemental-result.json').write_text(json.dumps(report,indent=2)+'\n')
  if p.returncode:raise RuntimeError(label+' failed')
  return p.stdout
 numeric=OUT/'numeric-edges'
 run('numeric-compile',['swiftc','-swift-version','6','-parse-as-library','-module-cache-path',str(OUT/'module-cache'),*map(str,sources),str(OUT/'NumericEdges.swift'),'-o',str(numeric)])
 report['numeric_binary_sha256']=sha(numeric)
 numeric_output=run('numeric-edges',[str(numeric)])
 assert 'NUMERIC EDGE ASSERTIONS 14' in numeric_output
 live=OUT/'live-http'
 assert sha(live)==candidate['binary_sha256']
 fixture=json.loads((ROOT/'.local/android-next-backend-01/result.json').read_text())
 assert fixture['status']=='serving'
 assert sha(ROOT/'.local/service-target/debug/daynomy-feedback')==fixture['binary_sha256']
 assert all(sha(ROOT/'app'/p)==fixture['source_hashes'][p] for p in ['src/api.rs','src/service_market.rs'])
 report['current_app_mismatches_before']=[p for p,h in fixture['source_hashes'].items() if not (ROOT/'app'/p).exists() or sha(ROOT/'app'/p)!=h]
 report['startup_full_source_hashes']=fixture['source_hashes']
 report['fixture_identity']='shared-fixture-identity.json'
 report['live_binary_sha256']=sha(live)
 output=run('rust-live',[str(live),'rust',fixture['base_url']])
 assert output.count('PASS ')==7
 after_fixture=json.loads((ROOT/'.local/android-next-backend-01/result.json').read_text())
 assert after_fixture['status']=='serving'
 assert after_fixture['source_hashes']==fixture['source_hashes']
 assert after_fixture['binary_sha256']==fixture['binary_sha256']==sha(ROOT/'.local/service-target/debug/daynomy-feedback')
 assert all(sha(ROOT/'app'/p)==after_fixture['source_hashes'][p] for p in ['src/api.rs','src/service_market.rs'])
 report['current_app_mismatches_after']=[p for p,h in after_fixture['source_hashes'].items() if not (ROOT/'app'/p).exists() or sha(ROOT/'app'/p)!=h]
 report['identity_scope']='serving fixture startup full-source manifest and matching binary; current market/api hashes unchanged; unrelated current tree differences explicitly recorded'
 report['fixture_identity_before_after_matches']=True
 report['fixture_state_after']='serving; shared reuse; no DB mutations or cleanup'
 assert all(sha(ROOT/p)==h for p,h in candidate['candidate_hashes'].items())
 report.update(status='passed',numeric_assertion_count=14,rust_assertion_count=7,finished_at=datetime.now(timezone.utc).isoformat())
 (OUT/'supplemental-result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
