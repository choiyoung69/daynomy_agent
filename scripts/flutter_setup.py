#!/usr/bin/env python3
"""Install the pinned official macOS ARM64 Flutter SDK inside .local only."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = '3.47.8'
CHECKSUM = '6114edc2dae3636cfefb7e4456a4510399ee856e324149b34dbacb509e329d05'
URL = f'https://storage.googleapis.com/flutter_infra_release/releases/stable/macos/flutter_macos_arm64_{VERSION}-stable.zip'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        parser.error('this local installer is pinned to macOS ARM64; use the official archive for other hosts')
    setup = ROOT / '.local/flutter-setup'
    archive = setup / f'flutter_macos_arm64_{VERSION}-stable.zip'
    sdk = ROOT / '.local/flutter-sdk'
    setup.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        if args.check:
            parser.error('pinned archive missing')
        partial = archive.with_suffix('.partial')
        with urllib.request.urlopen(URL, timeout=90) as response, partial.open('wb') as target:
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
        partial.rename(archive)
    with archive.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != CHECKSUM:
        parser.error('official archive checksum mismatch; SDK was not extracted')
    if not (sdk / 'flutter/bin/flutter').exists():
        if args.check:
            parser.error('SDK not extracted')
        sdk.mkdir(parents=True, exist_ok=True)
        subprocess.run(['unzip', '-q', str(archive), '-d', str(sdk)], check=True)
    result = subprocess.run(['bash', str(ROOT / 'scripts/flutter.sh'), '--version', '--machine'],
                            capture_output=True, text=True, check=True, timeout=60)
    metadata = json.loads(result.stdout)
    if metadata['frameworkVersion'] != VERSION or metadata['dartSdkVersion'] != '3.13.7':
        parser.error('installed SDK differs from pinned version')
    metadata['archive_sha256'] = actual
    (setup / 'verified-sdk.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(f'Flutter {VERSION} / Dart 3.13.7: official SHA-256 and installed versions verified')


if __name__ == '__main__':
    main()
