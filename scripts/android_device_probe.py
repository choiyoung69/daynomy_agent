#!/usr/bin/env python3
"""Actual emulator UI -> Rust/DB smoke flow; requires the disposable backend fixture."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial',default='emulator-5564')
    parser.add_argument('--base-url',default='http://10.0.2.2:18091/')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output
    if out.exists():raise ValueError('use a fresh output path')
    adb=shutil.which('adb') or str(Path.home()/'Library/Android/sdk/platform-tools/adb')
    command=[adb,'-s',args.serial]
    report={'scope':'actual API33 emulator Compose app -> existing Rust -> disposable PostgreSQL',
            'started_at':datetime.now(timezone.utc).isoformat(),'base_url':args.base_url,'checks':{},'status':'failed'}
    def run(*argv):return subprocess.run(command+list(argv),check=True,capture_output=True).stdout
    def tree():
        run('shell','uiautomator','dump','/sdcard/daynomy-pilot-window.xml')
        return ET.fromstring(run('exec-out','cat','/sdcard/daynomy-pilot-window.xml'))
    def wait_for(predicate):
        until=time.monotonic()+20
        while time.monotonic()<until:
            value=tree();matched=predicate(value)
            if matched is not None:return matched,value
            time.sleep(.3)
        raise RuntimeError('native UI assertion timeout')
    def tap(node):
        a,b,c,d=map(int,re.findall(r'\d+',node.attrib['bounds']))
        run('shell','input','tap',str((a+c)//2),str((b+d)//2))
    try:
        apk=ROOT/'clients/android/app/build/outputs/apk/debug/app-debug.apk'
        report['apk_sha256']=hashlib.sha256(apk.read_bytes()).hexdigest()
        # connectedDebugAndroidTest removes target/test packages during cleanup.
        run('install','-r',str(apk))
        run('shell','am','force-stop','org.daynomy.android')
        launched=run('shell','am','start','-W','-n','org.daynomy.android/.MainActivity','--es','base_url',args.base_url)
        if b'Error' in launched:raise RuntimeError('activity launch failed')
        field,_=wait_for(lambda t:next((n for n in t.iter('node') if n.attrib.get('class')=='android.widget.EditText'),None));tap(field)
        run('shell','input','text','005930')
        # Hide the software IME before inspecting results below the fold.
        run('shell','input','keyevent','4')
        node,_=wait_for(lambda t:next((n for n in t.iter('node') if '삼성전자' in n.attrib.get('text','')),None))
        report['checks']['real_stock_search_visible']=True
        tap(node)
        _,view=wait_for(lambda t:True if any('2026-10-23' in n.attrib.get('text','') for n in t.iter('node')) else None)
        texts=[n.attrib.get('text','') for n in view.iter('node')]
        report['checks']['latest_stored_date_visible']=any('2026-10-23' in t for t in texts)
        report['checks']['exact_quote_visible']=any('71000.125' in t for t in texts)
        report['checks']['decimal_autofilled_native_input']=any(n.attrib.get('class')=='android.widget.EditText' and n.attrib.get('text')=='71000.125' for n in view.iter('node'))
        image=out.with_suffix('.png');image.parent.mkdir(parents=True,exist_ok=True);image.write_bytes(run('exec-out','screencap','-p'))
        report['screenshot']={'path':str(image),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}
        report['status']='passed' if all(report['checks'].values()) else 'failed'
    except Exception as failure:
        report['failure_type']=type(failure).__name__
        raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
