#!/usr/bin/env python3
"""Independent frozen-source host and loopback gate; never starts DB."""
import hashlib,json,re,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 freeze_path=ROOT/'experiments/ios-native/test-author/frozen-tests.json'
 frozen=json.loads(freeze_path.read_text()); paths=frozen['files']|frozen['source_evidence']
 supplemental_path=ROOT/'experiments/ios-native/test-author/supplemental-query-freeze.json'
 supplemental=json.loads(supplemental_path.read_text())
 assert supplemental['original_freeze_sha256']==sha(freeze_path)
 paths=paths|{supplemental['test_file']:supplemental['test_sha256']}|supplemental['source_evidence']
 expected=frozen['canonical_test_count']+supplemental['supplemental_test_count']
 assert expected==supplemental['canonical_total_test_count']
 assert sha(ROOT/supplemental['red']['log'])==supplemental['red']['log_sha256']
 mismatches=[p for p,h in paths.items() if sha(ROOT/p)!=h]
 if mismatches:raise RuntimeError('Frozen identity mismatch: '+','.join(mismatches))
 sources=sorted((ROOT/'clients/ios/Sources/DaynomyCore').glob('*.swift'))
 candidate={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'clients/ios').rglob('*') if p.is_file() and '.build' not in p.parts and not p.name.startswith('.')}
 report={'started_at':datetime.now(timezone.utc).isoformat(),'freeze_sha256':sha(freeze_path),'supplemental_freeze_sha256':sha(supplemental_path),'candidate_hashes':candidate,'commands':[],'scope':'macOS host assertions + real loopback HTTP; not iOS or canonical Swift Testing runtime'}
 def run(name,cmd):
  start=time.monotonic();p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=120)
  (OUT/(name+'.log')).write_text(p.stdout+p.stderr)
  report['commands'].append({'name':name,'argv':list(map(str,cmd)),'exit_code':p.returncode,'seconds':time.monotonic()-start})
  (OUT/'candidate-result.json').write_text(json.dumps(report,indent=2)+'\n')
  if p.returncode:raise RuntimeError(name+' failed')
  return p.stdout
 output=run('host-green',['python3',str(ROOT/'experiments/ios-native/test-author/run_host_tests.py')])
 count=len(re.findall(r'^RAN ',output,re.M))
 if count!=expected or f'HOST TESTS {expected}; FAILURES 0' not in output:raise RuntimeError('Missing host case output')
 report['host_case_count']=count
 binary=OUT/'live-http'
 run('live-compile',['swiftc','-swift-version','6','-parse-as-library','-module-cache-path',str(OUT/'module-cache'),*map(str,sources),str(OUT/'LiveHTTP.swift'),'-o',str(binary)])
 report['binary_sha256']=sha(binary)
 run('live-loopback',['python3',str(OUT/'loopback_verify.py'),'--binary',str(binary)])
 changed=[p for p,h in candidate.items() if sha(ROOT/p)!=h]
 if changed:raise RuntimeError('Candidate changed during run: '+','.join(changed))
 if any(sha(ROOT/p)!=h for p,h in paths.items()):raise RuntimeError('Frozen input changed during run')
 report.update(status='passed-host-and-loopback',finished_at=datetime.now(timezone.utc).isoformat())
 (OUT/'candidate-result.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'status':report['status'],'host_case_count':count,'binary_sha256':report['binary_sha256']}))
if __name__=='__main__':main()
