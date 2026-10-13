"""记录两个平台实际架构、系统库要求及 Windows 导入表。"""

from pathlib import Path
import re
import subprocess

root = Path("/home/debian/codex-build-0.162.1")
linux = root / "codex-linux-x86_64"
windows = sorted((root / "windows-compiled").glob("*.exe"))
lines = ["两个平台的实际二进制检查：", subprocess.check_output(["file", str(linux), *map(str, windows)], text=True)]
obj = subprocess.check_output(["objdump", "-T", str(linux)], text=True)
versions = sorted(set(re.findall(r"GLIBC_([0-9]+\.[0-9]+)", obj)), key=lambda value: tuple(map(int, value.split("."))))
lines += ["Linux 最高 glibc 符号版本要求：GLIBC_" + versions[-1], subprocess.check_output(["ldd", str(linux)], text=True)]
for path in windows:
    imports = subprocess.check_output(["x86_64-w64-mingw32-objdump", "-p", str(path)], text=True)
    lines += [str(path), "\n".join(line for line in imports.splitlines() if "DLL Name:" in line)]
(root / "binary-inspection.txt").write_text("\n".join(lines) + "\n")
print("已记录实际 ELF／PE x86_64 架构、glibc 要求和 Windows 导入 DLL。")
