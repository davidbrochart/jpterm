Once jpterm has been installed, it can be launched from the command line. You can show the help message like so:

```
$ jpterm --help

 Usage: jpterm [OPTIONS] [COMMAND] [ARGS]...

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────╮
│ --server                            TEXT  The URL to the Jupyter server.                       │
│ --backend                           TEXT  The name of the event loop to use (asyncio or trio). │
│ --collaborative/--no-collaborative        Collaborative mode (with a server).                  │
│ --experimental/--no-experimental          Experimental mode (with Jupyverse).                  │
│ --set                               TEXT  Set configuration.                                   │
│ --help                                    Show this message and exit.                          │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────╮
│ logo             Show the jpterm logo.                                                         │
│ show             Show document PATH inline using its registered editor.                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────╯
```

The easiest way to launch jpterm is simply by entering `jpterm` and hitting *Enter*. Jpterm will run locally on your machine, without needing a Jupyter server. This is the TUI mode (Text User Interface), where jpterm takes control of your terminal and runs as a full-screen application. There is also a [CLI](CLI.md) mode (Command Line Interface).

In local mode, opening a notebook reuses its running jpterm kernel when one
exists. For example, you can prepare a persistent kernel with
`jpterm kernel start notebook.ipynb`, then open that notebook in the TUI.

Press `Ctrl+W` to close the active tab. If a document has unsaved changes,
choose **Cancel** to keep editing or **Discard changes** to close it without
saving. You can cancel, press `Ctrl+S` to save, then close the tab.

Closing a notebook tab leaves its kernel running until it is stopped explicitly
or cleaned up when the TUI exits.

On exit, the TUI shuts down local notebook kernels it started itself. Kernels
that were already running remain available after the TUI exits. Use
`jpterm kernel stop notebook.ipynb` to stop a persistent kernel explicitly. Avoid simultaneous execution or saves
from the TUI and CLI for the same notebook; they are not coordinated.

Jpterm can also run as a client to a Jupyter server, just like when you use JupyterLab. While JupyterLab is a Web client that runs in the browser, jpterm runs in the terminal. The two main Jupyter servers are [jupyter-server](https://github.com/jupyter-server/jupyter_server) and [jupyverse](https://github.com/jupyter-server/jupyverse). You can install and launch them like so:

```bash
# Install jupyter-server (through JupyterLab):
pip install jupyterlab
pip install jupyter-collaboration
# Launch it:
jupyter lab --ServerApp.token='' --ServerApp.password='' --ServerApp.disable_check_xsrf=True --no-browser --port=8000

# Or install jupyverse:
pip install "jupyverse[jupyterlab,noauth,collaboration]"
# Launch it:
jupyverse
```

Then pass the URL of the Jupyter server to jpterm through the `--server` option:

```bash
jpterm --server http://127.0.0.1:8000
```
