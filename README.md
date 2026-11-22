[![Build Status](https://github.com/davidbrochart/jpterm/workflows/test/badge.svg)](https://github.com/davidbrochart/jpterm/actions)

# jpterm

Jpterm is the successor of [nbterm](https://github.com/davidbrochart/nbterm).

It aims to be the equivalent of [JupyterLab](https://jupyterlab.readthedocs.io) in the terminal, using the [Anytext](https://github.com/davidbrochart/anytext) framework.

At startup, jpterm enables Anytext’s Textual import alias so existing Textual plugins share the same app and widget classes.

For more details, see the [documentation](https://davidbrochart.github.io/jpterm).

## CLI

The CLI uses Cyclopts. Run `jpterm` without a subcommand to open the TUI, or use:

```sh
jpterm show notebook.ipynb
jpterm show notebook.ipynb --cell CELL_ID --json
jpterm write notes.txt --source 'hello'
jpterm execute notebook.ipynb --kernel python3
jpterm kernel list
jpterm --server http://localhost:8000 show notebook.ipynb
```

Global options include `--server`, `--backend`, `--collaborative`,
`--experimental`, and repeatable `--set KEY=VALUE`. Each command has `--help`.
The same command tree is used when running inside Anyshell.

## Anyshell integration

Install the optional Anyshell integration to register jpterm’s document commands
and interactive interface. From this checkout:

```sh
uv run --extra anyshell anyshell
```

Enter `jpterm` to open the full TUI in the current pane. Press `Ctrl+Q` to return
to the shell (`q` also works from the launcher); `Ctrl+W` closes the current document tab.
You can also use `jpterm show PATH`, `jpterm write PATH --source TEXT`, or
`jpterm execute NOTEBOOK`. Text can also be piped into
`jpterm write PATH --stdin`. `--cell CELL_ID` selects a notebook cell, and
`--kernel NAME` selects an execution kernel. Paths follow the shell pane's
working directory within its local workspace. Global options such as `--server`
and `--set` work in both hosts.
Local commands require a local filesystem; remote paths refer to the server.

Direct terminal output uses jpterm's highlighted editor layout. Pipes,
redirections, and Python assignments receive raw text lines or notebook/cell
dictionaries. Notebook execution may start a Jupyter kernel process; the
adapter itself runs in-process. It requires Anyshell 0.6.0 or newer for external
command plugins, interactive views, and `stdout.is_terminal`.

The command definitions live in a shared Cyclopts tree in `jpterm.cli`.
The small `jpterm.anyshell` adapter registers that same tree through the
`anyshell.commands` entry-point group; there is no second set of command options.
Custom hosts can call
`jpterm.anyshell.register(session)` directly.

## Embeddable interface

`txl_jpterm.main.JptermView` contains the header, file browser, tabbed main area,
and footer. The standalone `Jpterm` app is a host for this widget. View actions
and CSS belong to the widget, so separate instances keep their focus, tabs,
and browser visibility independent.

A host supplies components from the jpterm services and mounts the view:

```python
from txl_jpterm.main import JptermView

view = JptermView(header, footer, main_area)
view.start(launcher, file_browser)
await host.mount(view)
await view.closed.wait()
await view.remove()
```

The host owns the plugin services for the lifetime of the view. `q` signals
`JptermView.Closed` and sets `view.closed`; it does not exit the host app.
Standalone jpterm handles that message by exiting. Anyshell hosts this same widget in a pane and owns its services for that visit.
`jpterm.view.open_view` reuses the host app and terminal driver; it starts no
second application loop. Closing or interrupting the view stops its service graph.
