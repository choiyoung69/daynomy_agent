#!/usr/bin/env python3
"""Read-only, bounded probe. Writes its own evidence; never installs/selects tools."""
import json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path
OUT=Path(__file__).resolve().parent
commands=[['xcode-select','-p'],['xcrun','--find','swift'],['swift','--version'],['xcodebuild','-version'],['xcrun','--sdk','iphoneos','--show-sdk-path'],['xcrun','--sdk','iphonesimulator','--show-sdk-path'],['xcrun','--find','simctl'],['mdfind','kMDItemCFBundleIdentifier == "com.apple.dt.Xcode"']]
report={'observed_at':datetime.now(timezone.utc).isoformat(),'commands':[], 'searches':[], 'classification':'iOS SDK/runtime unavailable; macOS Swift is separate evidence'}
for command in commands:
 p=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
 report['commands'].append({'argv':command,'exit_code':p.returncode,'output':p.stdout})
roots=[Path('/Applications'),Path.home()/'Applications',Path('/Library/Developer'),Path.home()/'Library/Developer',Path('/opt'),Path('/Volumes'),Path.home()/'Downloads',Path.home()/'develop']
for root in roots:
 found=[]
 if root.exists():
  for current,dirs,files in os.walk(root):
   depth=len(Path(current).relative_to(root).parts)
   dirs[:]=[d for d in dirs if d not in {'.git','node_modules','.gradle','.dart_tool','target','.local','Caches','Containers','DerivedData'} and not (d.endswith('.app') and 'xcode' not in d.lower())]
   for name in dirs+files:
    if name.startswith(('Xcode','iPhoneOS','iPhoneSimulator')) or name=='simctl':found.append(str(Path(current)/name))
   if depth>=4:dirs[:]=[]
 report['searches'].append({'root':str(root),'maximum_depth':4,'matches':found})
(OUT/'environment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'commands':len(commands),'xcodebuild_exit':report['commands'][3]['exit_code'],'classification':report['classification']}))
