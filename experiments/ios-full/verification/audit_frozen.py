import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
records=[]
for rel in ['experiments/ios-native/test-author/frozen-tests.json','experiments/ios-native/test-author/supplemental-query-freeze.json','experiments/ios-full/test-author/bundle-1-freeze.json','experiments/ios-full/test-author/bundle-2-freeze.json','experiments/ios-full/test-author/holding-adjustment-freeze.json','experiments/ios-full/test-author/multipart-freeze.json']:
 p=ROOT/rel;m=json.loads(p.read_text());checks=[]
 for path,expected in m.get('files',{}).items():
  actual=ROOT/path
  if path=='clients/ios/UITests/DaynomyIOSUITests.swift':actual=ROOT/'experiments/ios-full/test-author/DaynomyIOSUITests-v1.swift'
  checks.append({'path':path,'checked_path':str(actual.relative_to(ROOT)),'matches':sha(actual)==expected})
 records.append({'manifest':rel,'manifest_sha256':sha(p),'checks':checks})
m=json.loads((ROOT/'experiments/ios-full/test-author/UI-v2-freeze.json').read_text())
ui={key:sha(ROOT/m[key+'_source'])==m[key+'_sha256'] for key in ['original','updated','additional']}
methods=[]
for p in sorted((ROOT/'clients/ios/Tests/DaynomyCoreTests').glob('*.swift')):
 text=p.read_text()
 for block in re.finditer(r'struct (\w+Tests).*?(?=struct \w+Tests|\Z)',text,re.S):
  methods.extend(block.group(1)+'.'+name for name in re.findall(r'@Test func (\w+)\(',block.group(0)))
report={'manifests':records,'ui_revision_checks':ui,'method_count':len(methods),'methods':methods,'all_frozen_files_match':all(c['matches'] for r in records for c in r['checks']) and all(ui.values()),'runner_audit':{'source_hash':sha(ROOT/'experiments/ios-full/test-author/run_host_tests.py'),'semantics':'Each currently authored @Test func in each Tests struct invoked once; body macro substitutions preserve Bool expectation, optional require, MarketError throw equality and Issue.record failure counts. Uncaught throws counted. Nonzero exit on any failure; zero tests rejected. No parameterized cases in current source. Runs serially on MainActor, not Swift Testing runtime, iOS SDK or UI execution.','canonical_framework_runtime':'blocked: CLT lib_TestingInterop.dylib absent'}}
(OUT/'frozen-runner-review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'all_frozen_files_match':report['all_frozen_files_match'],'method_count':len(methods)}))
if not report['all_frozen_files_match']:raise SystemExit(1)
