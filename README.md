[![Build Status](https://github.com/davidbrochart/jpterm/workflows/CI/badge.svg)](https://github.com/davidbrochart/jpterm/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


# jpterm

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
