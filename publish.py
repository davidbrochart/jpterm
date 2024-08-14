import subprocess
from pathlib import Path

import httpx
import tomllib


def run(cmd: str, cwd: str | None = None) -> list[str]:
    res = subprocess.run(cmd.split(), capture_output=True, cwd=cwd)
    return res.stdout.decode().splitlines()


pyproject = tomllib.load(open("pyproject.toml", "rb"))
jpterm_version = pyproject["project"]["version"]
for dependency in pyproject["project"]["dependencies"]:
    idx = dependency.find("==")
    version = dependency[idx + 2:].strip()
    package = dependency[:idx].strip()
    if package.startswith("txl"):
        response = httpx.get(f"https://pypi.org/pypi/{package}/json")
        releases = response.json()["releases"].keys()
        if version not in releases:
            print(f"Building {package}-{version}")
            package_dir = Path()
            dist_dir = "../dist"
            if package == "txl":
                package_dir /= package
            else:
                package_dir = package_dir / "plugins" / package[len("txl_"):]
                dist_dir = f"../{dist_dir}"
            run(f"hatch build {dist_dir}", cwd=str(package_dir))
            for path in Path("dist").iterdir():
                if f"{package}-{version}" in path.name:
                    break
            else:
                raise RuntimeError(
                    f"Wrong version for package {package}: did you forget to bump it to {version}?"
                )


print(f"Building jpterm-{jpterm_version}")
run("hatch build")
