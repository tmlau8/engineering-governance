"""Install pinned local Grafana/Infinity dependencies; no global installation."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import urllib.request

from manage import GRAFANA, RUNTIME

VERSION = "13.3.0"
PLUGIN_VERSION = "4.1.5"
ARCHIVE_SHA256 = "8c640b5632c7336b2bebfa1b879b6e674631980fdf3b21ca0bc4337e7ef83457"
URL = "https://dl.grafana.com/grafana/release/13.3.0/grafana_13.3.0_40412481033_darwin_arm64.tar.gz"
MAX_ARCHIVE = 512 * 1024 * 1024


def install():
    if sys.version_info < (3, 12):
        raise ValueError("INSTALL_REQUIRES_PYTHON_3_12_FOR_SAFE_TAR_FILTER")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("PILOT_INSTALLER_SUPPORTS_MACOS_ARM64_ONLY")
    os.umask(0o077)
    if RUNTIME.is_symlink():
        raise ValueError("RUNTIME_SYMLINK_FORBIDDEN")
    software = RUNTIME / "software"
    software.mkdir(parents=True, exist_ok=True, mode=0o700)
    archive = software / "grafana-13.3.0-darwin-arm64.tar.gz"
    if not archive.exists():
        temporary = archive.with_suffix(".download")
        try:
            with urllib.request.urlopen(URL, timeout=60) as source, temporary.open("wb") as target:
                size = 0
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_ARCHIVE:
                        raise ValueError("ARCHIVE_TOO_LARGE")
                    target.write(chunk)
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    digest = hashlib.sha256()
    with archive.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != ARCHIVE_SHA256:
        raise ValueError("GRAFANA_CHECKSUM_MISMATCH")
    if not (GRAFANA / "bin/grafana").is_file():
        with tarfile.open(archive) as package:
            if sum(m.size for m in package.getmembers()) > 2 * 1024**3:
                raise ValueError("UNPACKED_ARCHIVE_TOO_LARGE")
            package.extractall(software, filter="data")
    plugin = software / "plugins/yesoreyeram-infinity-datasource/plugin.json"
    installed = json.loads(plugin.read_text()).get("info", {}).get("version") if plugin.exists() else None
    if installed != PLUGIN_VERSION:
        result = subprocess.run([str(GRAFANA / "bin/grafana"), "cli", "--homepath", str(GRAFANA), "--pluginsDir", str(software / "plugins"), "plugins", "install", "yesoreyeram-infinity-datasource", PLUGIN_VERSION], capture_output=True, timeout=180)
        if result.returncode:
            raise ValueError("INFINITY_INSTALL_FAILED")
    print("Grafana 13.3.0 archive checksum verified; Infinity 4.1.5 installed locally.")


if __name__ == "__main__":
    install()
