"""以同版官方完整包为底，组装定制程序与全部配套文件并记录来源、架构和校验值。"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import zipfile


ROOT = Path("/home/debian/codex-build-0.163.0-r2")
VERSION = "0.163.0"
COMMIT = "83086188ae0614bd882818ff1aa23f3194962012"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("platform", choices=["linux", "windows"])
    args = parser.parse_args()
    platform = args.platform
    name = f"codex-{VERSION}-openai-r2-{platform}-x86_64"
    official = ROOT / "packages" / f"{platform}-official"
    destination = ROOT / "dist" / name
    if destination.exists():
        raise RuntimeError(f"目标已存在，请核对后处理：{destination}")
    if platform == "linux":
        replacements = {"bin/codex": ROOT / "codex-linux-x86_64"}
        official_target = "x86_64-unknown-linux-musl"
        target = "x86_64-unknown-linux-gnu"
    else:
        compiled = ROOT / "windows-compiled"
        replacements = {"bin/codex.exe": compiled / "codex.exe"}
        for helper in ("codex-command-runner.exe", "codex-windows-sandbox-setup.exe", "codex-windows-sandbox-service.exe"):
            replacements["codex-resources/" + helper] = compiled / helper
        official_target = "x86_64-pc-windows-msvc"
        target = "x86_64-pc-windows-gnu"
    for path in replacements.values():
        assert path.is_file(), path
    shutil.copytree(official, destination, symlinks=True)
    for relative, source in replacements.items():
        shutil.copy2(source, destination / relative)
    manifest = json.loads((destination / "codex-package.json").read_text())
    manifest["target"] = target
    (destination / "codex-package.json").write_text(json.dumps(manifest, indent=2) + "\n")
    runtime_dlls = []
    if platform == "windows":
        imports = set()
        for relative in replacements:
            output = subprocess.check_output(["x86_64-w64-mingw32-objdump", "-p", str(destination / relative)], text=True)
            imports.update(re.findall(r"DLL Name: (\S+)", output))
        dll_candidates = list(Path("/usr").glob("lib/gcc/x86_64-w64-mingw32/*/*.dll"))
        dll_candidates += list(Path("/usr/x86_64-w64-mingw32").glob("lib/*.dll"))
        handled = set()
        while imports - handled:
            dll = sorted(imports - handled)[0]
            handled.add(dll)
            if not dll.lower().startswith(("libgcc", "libstdc++", "libwinpthread", "libssp")):
                continue
            found = [path for path in dll_candidates if path.name.lower() == dll.lower()]
            assert found, f"缺少运行库：{dll}"
            found.sort(key=lambda path: ("posix" not in str(path), str(path)))
            source = found[0]
            for relative in ("bin", "codex-resources"):
                shutil.copy2(source, destination / relative / dll)
            runtime_dlls.append(dll)
            output = subprocess.check_output(["x86_64-w64-mingw32-objdump", "-p", str(source)], text=True)
            imports.update(re.findall(r"DLL Name: (\S+)", output))
    entries = []
    for path in sorted(destination.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(destination).as_posix()
        origin = "本机编译" if relative in replacements else "同版官方配套包"
        if path.name in runtime_dlls:
            origin = "GNU Windows 运行库"
        if relative == "codex-package.json":
            origin = "按定制主程序架构更新的包布局元数据"
        if origin == "同版官方配套包":
            assert sha256(path) == sha256(official / relative), relative
        entries.append({"path": relative, "size": path.stat().st_size, "sha256": sha256(path), "origin": origin})
    official_package = next(item for item in json.loads((ROOT / "official-packages.json").read_text()) if item["platform"] == platform)
    details = {"official_package": official_package, "version": VERSION, "patch": "openai-r2", "source_commit": COMMIT,
               "official_source_commit": COMMIT,
               "source_patch_sha256": sha256(ROOT / "codex-0.163.0-openai-r2.patch"),
               "customizations": ["小写 openai 接受完整自定义 provider 定义"],
               "daybreak_uses_official_implementation": True,
               "main_target": target, "official_helpers_target": official_target,
               "rust": "1.95.0", "runtime_dlls": runtime_dlls,
               "notes": "主程序及列出的沙箱程序为定制构建，其余资源保持同版官方原始字节。",
               "files": entries}
    (destination / "custom-build.json").write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n")
    if platform == "linux":
        archive = ROOT / "dist" / (name + ".tar.gz")
        with tarfile.open(archive, "w:gz", compresslevel=6) as output:
            output.add(destination, arcname=name)
    else:
        archive = ROOT / "dist" / (name + ".zip")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            for path in sorted(destination.rglob("*")):
                if path.is_file():
                    output.write(path, name + "/" + path.relative_to(destination).as_posix())
    result = {"directory": str(destination), "archive": str(archive), "sha256": sha256(archive),
              "files": len(entries), "runtime_dlls": runtime_dlls}
    (ROOT / (platform + "-package.json")).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
