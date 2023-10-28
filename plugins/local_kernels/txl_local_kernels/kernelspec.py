import os
import sys

from .paths import jupyter_data_dir

if os.name == "nt":
    programdata = os.environ.get("PROGRAMDATA", None)
    if programdata:
        SYSTEM_JUPYTER_PATH = [os.path.join(programdata, "jupyter")]
    else:  # PROGRAMDATA is not defined by default on XP
        SYSTEM_JUPYTER_PATH = [os.path.join(sys.prefix, "share", "jupyter")]
else:
    SYSTEM_JUPYTER_PATH = [
        "/usr/local/share/jupyter",
        "/usr/share/jupyter",
    ]

ENV_JUPYTER_PATH = [os.path.join(sys.prefix, "share", "jupyter")]


def jupyter_path(*subdirs):
    paths = []
    # highest priority is env
    if os.environ.get("JUPYTER_PATH"):
        paths.extend(p.rstrip(os.sep) for p in os.environ["JUPYTER_PATH"].split(os.pathsep))
    # then user dir
    paths.append(jupyter_data_dir())
    # then sys.prefix
    for p in ENV_JUPYTER_PATH:
        if p not in SYSTEM_JUPYTER_PATH:
            paths.append(p)
    # finally, system
    paths.extend(SYSTEM_JUPYTER_PATH)

    # add subdir, if requested
    if subdirs:
        paths = [os.path.join(p, *subdirs) for p in paths]
    return paths


def kernelspec_dirs():
    return jupyter_path("kernels")


def _is_kernel_dir(path):
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, "kernel.json"))


def _list_kernels_in(kernel_dir):
    if kernel_dir is None or not os.path.isdir(kernel_dir):
        return {}
    kernels = {}
    for f in os.listdir(kernel_dir):
        path = os.path.join(kernel_dir, f)
        if _is_kernel_dir(path):
            key = f.lower()
            kernels[key] = path
    return kernels


def find_kernelspec(kernel_name):
    d = {}
    for kernel_dir in kernelspec_dirs():
        kernels = _list_kernels_in(kernel_dir)
        for kname, spec in kernels.items():
            if kname not in d:
                d[kname] = os.path.join(spec, "kernel.json")
    return d.get(kernel_name, "")
