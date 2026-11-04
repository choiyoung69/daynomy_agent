#!/usr/bin/env python3
"""Run fixed tests against disposable source copies, never editing product files."""
import hashlib, json, os, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
APP=ROOT/'clients/flutter'
OUT=Path(__file__).resolve().parent
hashes=lambda paths:{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
original=hashes(list((APP/'lib').rglob('*.dart'))+list((APP/'test').rglob('*.dart')))
fixture=OUT/'knowledge/contracts/stock-search-price.json'
fixture.parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile(ROOT/'knowledge/contracts/stock-search-price.json',fixture)
mutations=[('duplicate-json-key','src/exact_json.dart','if (out.containsKey(key)) fail();','/* injected duplicate key acceptance */','test/exact_json_test.dart'),('retry-write-on-401','src/api.dart',"method == 'GET'", "method != 'OPTIONS'",'test/api_client_test.dart')]
results=[]
for name,file,before,after,test in mutations:
    candidate=OUT/'mutations-02'/name
    candidate.mkdir(parents=True,exist_ok=False)
    shutil.copytree(APP/'lib',candidate/'lib')
    shutil.copytree(APP/'test',candidate/'test')
    (candidate/'.dart_tool').mkdir()
    
    for generated in ['package_config.json','package_graph.json']:
        shutil.copyfile(APP/'.dart_tool'/generated,candidate/'.dart_tool'/generated)
    for p in ['pubspec.yaml','pubspec.lock']:
        shutil.copyfile(APP/p,candidate/p)
    target=candidate/'lib'/file
    source=target.read_text()
    assert source.count(before)==1
    target.write_text(source.replace(before,after))
    with (OUT/f'mutation-02-{name}.log').open('w') as log:
        result=subprocess.run(['bash',str(ROOT/'scripts/flutter.sh'),'test','--no-pub',test,'--reporter','expanded'],cwd=candidate,stdout=log,stderr=log,timeout=180)
    results.append(dict(name=name,exit_code=result.returncode,mutation={'path':file,'before':before,'after':after},test=test))
assert hashes([ROOT/p for p in original])==original
report={'results':results,'original_criteria_and_lib_unchanged':True,'original_hashes':original}
(OUT/'mutations-02.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['results','original_criteria_and_lib_unchanged']}))
