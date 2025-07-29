import subprocess
from pathlib import Path

import httpx
import toml


def run(cmd: str, cwd: str | None = None) -> list[str]:
    res = subprocess.run(cmd.split(), capture_output=True, cwd=cwd)
    return res.stdout.decode().splitlines()


Path("dist").mkdir(exist_ok=True)
pyproject = toml.load("pyproject.toml")
jpterm_version = pyproject["project"]["version"]
for dependency in pyproject["project"]["dependencies"]:
    idx = dependency.find("==")
    version = dependency[idx + 2:].strip()
    package = dependency[:idx].strip()
    if package == "txl":
        txl_version = version
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
            package_pyproject = toml.load(package_dir / "pyproject.toml")
            package_pyproject["project"]["version"] = version
            for idx, dependency in enumerate(package_pyproject["project"]["dependencies"]):
                if dependency.startswith("txl") and not dependency.startswith("txl_"):
                    package_pyproject["project"]["dependencies"][idx] = f"txl =={txl_version}"
                    with open(package_dir / "pyproject.toml", "w") as f:
                        toml.dump(package_pyproject, f)
                    break
            with open(package_dir / "pyproject.toml", "w") as f:
                toml.dump(package_pyproject, f)
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
