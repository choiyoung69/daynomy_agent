#!/usr/bin/env python3
"""Prepare checksummed, repository-local Kotlin/Dart runtimes for knowledge examples.

No global installation or target-app SDK setup. Versions apply to examples only.
"""
import hashlib
import base64
import json
from pathlib import Path
import platform
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".local/knowledge-sdks"


def download(url, target, expected, checksum_algorithm="sha256"):
    if not target.exists():
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "DAYNOMY-knowledge"}), timeout=60) as response:
            with target.with_suffix(target.suffix + ".partial").open("wb") as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
        target.with_suffix(target.suffix + ".partial").replace(target)
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if hashlib.new(checksum_algorithm, target.read_bytes()).hexdigest() != expected:
        raise ValueError(f"checksum mismatch: {target.name}")
    return {"url": url, "path": str(target.relative_to(ROOT)), "sha256": actual, "bytes": target.stat().st_size,
            "upstream_checksum_algorithm": checksum_algorithm, "upstream_checksum": expected}


def extract(archive, target):
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            if not (target / entry.filename).resolve().is_relative_to(target.resolve()):
                raise ValueError("archive path escape")
        bundle.extractall(target)
        for entry in bundle.infolist():
            path = target / entry.filename
            if path.is_file() and (entry.external_attr >> 16) & 0o111:
                path.chmod(0o755)


def text(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "DAYNOMY-knowledge"}), timeout=30) as response:
        return response.read().decode().strip()


def main():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("this pinned example bootstrap targets macOS arm64")
    DEST.mkdir(parents=True, exist_ok=True)
    records = []
    kotlin = DEST / "kotlin-compiler-2.4.21.zip"
    records.append(download("https://github.com/JetBrains/kotlin/releases/download/v2.4.21/kotlin-compiler-2.4.21.zip", kotlin,
                            "7cc140e76daf416a0424a5557f99afd7ca89ebd463ea1101261e3e01c33e75cd"))
    if not (DEST / "kotlin/kotlinc/bin/kotlinc").exists():
        extract(kotlin, DEST / "kotlin")
    dart = DEST / "dartsdk-macos-arm64-3.13.7.zip"
    dart_url = "https://storage.googleapis.com/dart-archive/channels/stable/release/3.13.7/sdk/dartsdk-macos-arm64-release.zip"
    records.append(download(dart_url, dart, text(dart_url + ".sha256sum").split()[0]))
    if not (DEST / "dart/dart-sdk/bin/dart").exists():
        extract(dart, DEST / "dart")
    for name in ("kotlinx-serialization-core-jvm", "kotlinx-serialization-json-jvm"):
        url = f"https://repo.maven.apache.org/maven2/org/jetbrains/kotlinx/{name}/1.12.0/{name}-1.12.0.jar"
        records.append(download(url, DEST / f"{name}-1.12.0.jar", text(url + ".sha1").split()[0], "sha1"))
    metadata = json.loads(text("https://registry.npmjs.org/typescript/6.0.2"))
    algorithm, encoded = metadata["dist"]["integrity"].split("-", 1)
    typescript = DEST / "typescript-6.0.2.tgz"
    records.append(download(metadata["dist"]["tarball"], typescript, base64.b64decode(encoded).hex(), algorithm))
    if not (DEST / "typescript/package/bin/tsc").exists():
        with tarfile.open(typescript) as archive:
            archive.extractall(DEST / "typescript", filter="data")
    manifest = {"scope": "isolated example runtimes, not application version selection", "artifacts": records}
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Prepared checksummed Kotlin 2.4.21 / Dart 3.13.7 example runtimes under .local/knowledge-sdks")


if __name__ == "__main__":
    main()
