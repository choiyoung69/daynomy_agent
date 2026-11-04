"""Compose existing disposable Rust/DB fixture with an ephemeral local OIDC provider.
No production credentials, source edits, or original server. Run from repository root.
"""
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone
import argparse
import uuid
root=Path.cwd()
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',default='.local/webview-manual-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
parser.add_argument('--private-db',action='store_true',help='Use disposable private PostgreSQL on 55449; fail if that port is busy')
args=parser.parse_args()
output=Path(args.output).resolve()
if not output.is_relative_to(root/'.local') or output.exists():
    parser.error('--output must be a new directory under repository .local')
if args.private_db:
    import socket
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1',55449))==0:
            parser.error('private test DB port 55449 is already in use; leave the existing process untouched')
sys.path.insert(0,str(root/'scripts'))
import android_backend_fixture as runtime
import service_auth_provider_acceptance as oidc
original_clean=runtime.clean_env
oidc.REDIRECT='http://127.0.0.1:18082/login/oauth2/code/google'
with oidc.start_mock() as provider:
    runtime.clean_env=lambda: {**original_clean(),**provider.environment,
        'APP_CORS_ALLOWED_ORIGIN':'http://127.0.0.1:18082',
        'SUCCESS_REDIRECT_URI':'/','FAILURE_REDIRECT_URI':'/login?error=oauth'}
    metadata={'started_at':datetime.now(timezone.utc).isoformat(),'base_url':provider.base_url,
        'control_url':provider.control_url,'callback':oidc.REDIRECT,
        'mode':'ephemeral local OIDC test provider; not real Google authentication',
        'helper_source_sha256':hashlib.sha256((root/'scripts/android_backend_fixture.py').read_bytes()).hexdigest()}
    (root/'experiments/webview/full/runtime/oidc.json').write_text(json.dumps(metadata,indent=2)+'\n')
    sys.argv=[sys.argv[0],'--output',str(output),'--discovery']
    if args.private_db:
        sys.argv += ['--core30','--http-port','18091']
    raise SystemExit(runtime.main())
