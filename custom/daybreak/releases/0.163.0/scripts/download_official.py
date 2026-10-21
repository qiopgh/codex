"""下载同版官方完整包并核对 Release 中的 SHA-256。"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request

root = Path("/home/debian/codex-build-0.163.0")
release = json.loads((root / "official-release.json").read_text())
assert release["tag_name"] == "rust-v0.163.0" and not release["prerelease"] and not release["draft"]
names = {"windows": "codex-package-x86_64-pc-windows-msvc.tar.gz", "linux": "codex-package-x86_64-unknown-linux-musl.tar.gz"}


def download(platform):
    asset = next(a for a in release["assets"] if a["name"] == names[platform])
    destination = root / "downloads" / asset["name"]
    if not destination.exists():
        urllib.request.urlretrieve(asset["browser_download_url"], destination)
    value = hashlib.sha256(destination.read_bytes()).hexdigest()
    assert "sha256:" + value == asset["digest"], asset["name"]
    official = root / "packages" / f"{platform}-official"
    official.mkdir(exist_ok=False)
    with tarfile.open(destination) as archive:
        archive.extractall(official, filter="data")
    assert (official / "codex-package.json").is_file(), official
    record = {"platform": platform, "name": asset["name"], "url": asset["browser_download_url"], "sha256": value, "size": destination.stat().st_size}
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record


with ThreadPoolExecutor(max_workers=2) as pool:
    records = list(pool.map(download, names))
(root / "official-packages.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
