[![Build Status](https://github.com/davidbrochart/jpterm/workflows/CI/badge.svg)](https://github.com/davidbrochart/jpterm/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# jpterm

`jpterm` is a terminal-based CLI and UI that allows to:
- access documents either locally, or remotely through a Jupyter server.
- execute Jupyter notebooks either interactively or in batch mode, locally or remotely.

## Command-line interface

Launch a Jupyter server:
```bash
# using jupyter-server:
jupyter server --ServerApp.token='' --ServerApp.password='' --ServerApp.disable_check_xsrf=True
# or
# using jupyverse:
jupyverse --authenticator.mode=noauth --port=8888
```

Execute a notebook through that server:
```bash
jpterm --use-server http://127.0.0.1:8888 --run Untitled.ipynb
```

## Terminal user interface

Just launch:
```bash
jpterm
```

And you will be presented with a file browser. You can click on a directory or on a file to show its
content.

You can also access a remote file system through a Jupyter server (see above to launch one):
```bash
jpterm --use-server http://127.0.0.1:8888
```
