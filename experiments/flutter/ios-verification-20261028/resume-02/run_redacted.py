#!/usr/bin/env python3
"""Preserve actual Flutter command status without persisting VM service credentials."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--log', required=True)
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command
if command and command[0] == '--':
    command = command[1:]
if not command:
    parser.error('command required')
log = Path(args.log)
log.parent.mkdir(parents=True, exist_ok=True)
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
# Debug-service URLs contain transient auth paths; keep neither those nor websocket variants.
url = re.compile(r"(?:https?|wss?)://(?:127\.0\.0\.1|localhost|\[::1\]):[0-9]+/[^\s\"<>]+")
with log.open('w') as output:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    try:
        for line in process.stdout:
            output.write(url.sub('<local-debug-or-api-url-redacted>', line))
            output.flush()
        status = process.wait()
    except KeyboardInterrupt:
        process.terminate()
        status = process.wait(timeout=30)
log.with_suffix(log.suffix + '.result.json').write_text(json.dumps({
    'started_at': started,
    'finished_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'exit': status,
    'debug_url_paths_redacted': True,
}, indent=2) + '\n')
sys.exit(status if status >= 0 else 128 - status)
