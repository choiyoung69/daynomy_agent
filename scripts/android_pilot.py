#!/usr/bin/env python3
"""Dependency/slot/time ledger for root-dispatched desktop agents; not an agent launcher."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
GRAPH = {
    'spec.search': ('agent', []), 'spec.price': ('agent', []), 'spec.ui': ('check', []),
    'environment': ('check', []),
    'tests.api': ('agent', ['spec.search', 'spec.price', 'spec.ui']),
    'tests.integration': ('agent', ['spec.search', 'spec.price', 'spec.ui']),
    'red.api': ('check', ['tests.api', 'environment']),
    'red.integration': ('check', ['tests.integration', 'environment']),
    'implement.search': ('agent', ['red.api']), 'implement.price': ('agent', ['red.api']),
    'implement.integration': ('agent', ['red.integration']),
    'verify.local': ('check', ['implement.search', 'implement.price', 'implement.integration']),
    'verify.backend': ('check', ['verify.local']), 'verify.device': ('check', ['verify.local']),
    'review': ('agent', ['verify.local']),
    'final': ('check', ['verify.backend', 'verify.device', 'review']),
}

def now(): return datetime.now(timezone.utc).isoformat()
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def inside(name):
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT): raise ValueError('path outside repository')
    return path

def ready(state):
    return [key for key, task in state['tasks'].items() if task['status']=='queued' and
            all(state['tasks'][dep]['status']=='passed' for dep in task['deps'])]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',default='.local/android-pilot/state.json')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init');sub.add_parser('ready');sub.add_parser('summary');sub.add_parser('check-frozen')
    for command in ('start','finish','record'):
        p=sub.add_parser(command);p.add_argument('task',choices=GRAPH)
        p.add_argument('--actor',default='coordinator');p.add_argument('--model')
        if command!='start':
            p.add_argument('--status',choices=['passed','failed','blocked'],default='passed')
            p.add_argument('--evidence',action='append',required=True)
            p.add_argument('--knowledge-usage')
        if command=='record':
            p.add_argument('--started',required=True);p.add_argument('--finished',required=True)
    p=sub.add_parser('freeze');p.add_argument('name');p.add_argument('files',nargs='+')
    args=parser.parse_args();path=inside(args.state)
    if args.command=='init':
        if path.exists(): raise ValueError('run already exists; use a fresh --state')
        state={'measurement_start':'2026-10-28T08:05:15+00:00','created_at':now(),
               'dispatch':'root uses desktop subagent tools; this ledger does not launch agents or certify evidence semantics',
               'tasks':{key:dict(kind=kind,deps=deps,status='queued') for key,(kind,deps) in GRAPH.items()},
               'frozen':{},'events':[]}
    else: state=json.loads(path.read_text())
    if args.command in ('ready','summary'):
        if args.command=='ready': print(json.dumps(ready(state)));return 0
        print(json.dumps(state,ensure_ascii=False,indent=2));return 0
    if args.command=='check-frozen':
        # Explicit later revisions override current expectations; old hashes remain in history.
        expected={}
        for values in state['frozen'].values():expected.update(values)
        changed=[f for f,h in expected.items() if not inside(f).is_file() or digest(inside(f))!=h]
        if changed: raise ValueError('frozen criteria changed: '+', '.join(changed))
        print('PASS frozen criteria match');return 0
    if args.command=='freeze':
        if args.name in state['frozen']:raise ValueError('freeze label already used')
        state['frozen'][args.name]={str(inside(f).relative_to(ROOT)):digest(inside(f)) for f in args.files}
    if args.command in ('start','record'):
        if args.task not in ready(state):raise ValueError('dependencies incomplete or task already claimed')
        task=state['tasks'][args.task]
        if args.command=='start':
            limit=3 if task['kind']=='agent' else 1
            if sum(t['status']=='running' and t['kind']==task['kind'] for t in state['tasks'].values())>=limit:raise ValueError('no free slot')
        task.update(status='running',actor=args.actor,model=args.model,started_at=args.started if args.command=='record' else now())
        if args.task.startswith('implement.'):
            from android_knowledge import ensure
            name=args.task.split('.',1)[1]
            base=str(path.parent.relative_to(ROOT)/'knowledge-v1')
            manifest=ensure(name,base)
            task['knowledge_manifest']=manifest
            task['knowledge_enforcement']='required context generated before start'
    if args.command in ('finish','record'):
        task=state['tasks'][args.task]
        if task['status']!='running':raise ValueError('task is not running')
        if args.task=='final' and args.status=='passed':
            from android_knowledge import verify
            for name in ('search','price','integration'):
                previous=state['tasks']['implement.'+name]
                if not previous.get('knowledge_manifest') or not previous.get('knowledge_usage'):
                    raise ValueError('final acceptance missing required knowledge evidence: '+name)
                verify(previous['knowledge_manifest'],previous['knowledge_usage'],expected_task=name)
            expected={}
            for values in state['frozen'].values():expected.update(values)
            if any(not inside(f).is_file() or digest(inside(f))!=h for f,h in expected.items()):
                raise ValueError('final acceptance frozen criteria changed')
        if args.task.startswith('implement.') and args.status=='passed':
            from android_knowledge import verify
            manifest=task.get('knowledge_manifest')
            if not manifest:
                # Preserve that the first drafts predated this gate; do not rewrite history.
                manifest=str(path.parent.relative_to(ROOT)/'knowledge-v1'/args.task.split('.',1)[1]/'manifest.json')
                task['knowledge_manifest']=manifest
                task['knowledge_enforcement']='legacy initial draft; knowledge audit required before acceptance'
            if not args.knowledge_usage:raise ValueError('implementation acceptance requires --knowledge-usage')
            verify(manifest,args.knowledge_usage,expected_task=args.task.split('.',1)[1])
            task['knowledge_usage']=args.knowledge_usage
        evidence=[str(inside(f).relative_to(ROOT)) for f in args.evidence]
        if any(not inside(f).is_file() for f in evidence):raise ValueError('missing evidence')
        ended=args.finished if args.command=='record' else now()
        duration=(datetime.fromisoformat(ended)-datetime.fromisoformat(task['started_at'])).total_seconds()
        if duration<0:raise ValueError('negative duration')
        task.update(status=args.status,finished_at=ended,seconds=duration,evidence=evidence,
                    evidence_sha256={f:digest(inside(f)) for f in evidence},time_source='agent/coordinator reported interval' if args.command=='record' else 'ledger wall clock')
    state['events'].append({'at':now(),'action':args.command,'task':getattr(args,'task',None)})
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
    print(args.command,getattr(args,'task',getattr(args,'name','')), 'recorded')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,KeyError,OSError) as e:print('FAIL',str(e),file=sys.stderr);sys.exit(1)
