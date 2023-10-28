import glob
import os
import sys
import tempfile
import uuid
from typing import Dict, List


def _expand_path(s):
    if os.name == "nt":
        i = str(uuid.uuid4())
        s = s.replace("$\\", i)
    s = os.path.expandvars(os.path.expanduser(s))
    if os.name == "nt":
        s = s.replace(i, "$\\")
    return s


def _filefind(filename, path_dirs=()):
    filename = filename.strip('"').strip("'")
    if os.path.isabs(filename) and os.path.isfile(filename):
        return filename

    path_dirs = path_dirs or ("",)

    for path in path_dirs:
        if path == ".":
            path = os.getcwd()
        testname = _expand_path(os.path.join(path, filename))
        if os.path.isfile(testname):
            return os.path.abspath(testname)

    raise IOError(f"File {filename} does not exist in any of the search paths: {path_dirs}")


def get_home_dir():
    home = os.path.expanduser("~")
    home = os.path.realpath(home)
    return home


_dtemps: Dict = {}


def _mkdtemp_once(name):
    if name in _dtemps:
        return _dtemps[name]
    d = _dtemps[name] = tempfile.mkdtemp(prefix=name + "-")
    return d


def jupyter_config_dir():
    if os.environ.get("JUPYTER_NO_CONFIG"):
        return _mkdtemp_once("jupyter-clean-cfg")
    if "JUPYTER_CONFIG_DIR" in os.environ:
        return os.environ.env["JUPYTER_CONFIG_DIR"]
    home = get_home_dir()
    return os.path.join(home, ".jupyter")


def jupyter_data_dir():
    if "JUPYTER_DATA_DIR" in os.environ:
        return os.environ["JUPYTER_DATA_DIR"]

    home = get_home_dir()

    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Jupyter")
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA", None)
        if appdata:
            return os.path.join(appdata, "jupyter")
        else:
            return os.path.join(jupyter_config_dir(), "data")
    else:
        xdg = os.environ.get("XDG_DATA_HOME", None)
        if not xdg:
            xdg = os.path.join(home, ".local", "share")
        return os.path.join(xdg, "jupyter")


def jupyter_runtime_dir():
    if "JUPYTER_RUNTIME_DIR" in os.environ:
        return os.environ("JUPYTER_RUNTIME_DIR")
    return os.path.join(jupyter_data_dir(), "runtime")


def find_connection_file(
    filename: str = "kernel-*.json",
    paths: List[str] = [],
) -> str:
    if not paths:
        paths = [".", jupyter_runtime_dir()]

    path = _filefind(filename, paths)
    if path:
        return path

    if "*" in filename:
        pat = filename
    else:
        pat = f"*{filename}*"

    matches = []
    for p in paths:
        matches.extend(glob.glob(os.path.join(p, pat)))

    matches = [os.path.abspath(m) for m in matches]
    if not matches:
        raise IOError(f"Could not find {filename} in {paths}")
    elif len(matches) == 1:
        return matches[0]
    else:
        return sorted(matches, key=lambda f: os.stat(f).st_atime)[-1]
