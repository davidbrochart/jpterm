When jpterm is invoked with a command, it runs as a CLI in your terminal without taking control of it, inlining potential outputs below the command.

Use the `show` command to display the (rich) content of a file:

```bash
# Without a server:
jpterm show path/to/file

# With a server:
jpterm --server http://127.0.0.1:8000 show path/to/file
```

By "rich content" we mean that for instance, a Python file will be rendered with Python syntax highlighting, a Jupyter notebook will be rendered with a nice view of cells, etc.

If you pass `--json` then the content will not be represented as a rich output but as JSON. This can be useful for passing the output to another tool:

```bash
jpterm show path/to/notebook --json | jq -r '.cells[0].source'
```

Use `--cell CELL_ID` to show a single notebook cell, including its saved outputs:

```bash
jpterm show notebook.ipynb --cell CELL_ID
jpterm show notebook.ipynb --cell CELL_ID --json
```

To display IDs use `--show-cell-ids`:

```bash
jpterm show notebook.ipynb --show-cell-ids
```

This also works with `--cell CELL_ID`. JSON output already includes cell IDs.

Use `write` to create or replace a text file:

```bash
jpterm write script.py --source 'print("hello")'
cat script.py | jpterm write another.py --stdin
```

For notebooks, specify `--cell CELL_ID` to replace a cell's source:

```bash
jpterm write notebook.ipynb --cell CELL_ID --source 'print("hello")'
cat script.py | jpterm write notebook.ipynb --cell CELL_ID --stdin
jpterm --server http://127.0.0.1:8000 write notebook.ipynb --cell CELL_ID --source 'print(42)'
```

Provide exactly one of `--source` or `--stdin`; `--source ''` clears the content.
When a code cell's source changes, its saved outputs and execution count are cleared.
Other cells are preserved, and no cells are executed. Writing a whole notebook without
`--cell` is not supported.

Use `execute` to run a notebook locally or on a Jupyter server.
Add `--cell CELL_ID` to run only one code cell:

```bash
jpterm execute notebook.ipynb
jpterm execute notebook.ipynb --cell CELL_ID
jpterm --server http://127.0.0.1:8000 execute notebook.ipynb
jpterm --server http://127.0.0.1:8000 execute notebook.ipynb --cell CELL_ID
jpterm --server http://127.0.0.1:8000 execute notebook.ipynb --cell CELL_ID --json
```

Local execution starts a detached kernel in the notebook's directory and reuses
it on later calls. Each notebook's resolved absolute path identifies its kernel.
The local TUI also reuses this session. It leaves an existing kernel running on
exit, and shuts down kernels it started itself.
Avoid simultaneous jpterm calls for the same notebook; execution and notebook
saves are not coordinated between CLI processes.

Manage detached local kernels with:

```bash
jpterm kernel start notebook.ipynb
jpterm kernel list
jpterm kernel list --json
jpterm kernel stop notebook.ipynb
```

Add `--server` to manage notebook kernels on a Jupyter server:

```bash
jpterm --server http://127.0.0.1:8000 kernel start notebook.ipynb
jpterm --server http://127.0.0.1:8000 kernel list
jpterm --server http://127.0.0.1:8000 kernel list --json
jpterm --server http://127.0.0.1:8000 kernel stop notebook.ipynb
```

`kernel start` uses the notebook's kernelspec (or `--kernel NAME` for a new
kernel) and waits until the kernel is ready. It reuses an existing live kernel
without executing cells or saving the notebook. `execute` still starts a kernel
automatically when needed.

Remote listing shows notebook sessions, including those started by other clients.
Paths are relative to the server's root. Remote `stop` deletes the matching
notebook session and lets the server manage kernel shutdown. Both backends
support `--json` for listing; remote entries include kernel and session IDs,
while local entries include the kernel or launcher PID.

With `--server`, execution reuses the notebook's session, creating
one with the notebook's kernelspec (or `--kernel NAME`) when needed. The kernel
stays running so variables and imports persist between calls. Without `--cell`,
code cells execute in notebook order.
Execution stops at the first cell error and returns a nonzero exit status.

For a server with real-time collaboration enabled, add `--collaborative` before
the command to read and write the live shared document:

```bash
jpterm --server http://127.0.0.1:8000 --collaborative show notebook.ipynb --show-cell-ids
jpterm --server http://127.0.0.1:8000 --collaborative write notebook.ipynb --cell CELL_ID --source 'print(42)'
cat script.py | jpterm --server http://127.0.0.1:8000 --collaborative write script.py --stdin
```

Collaborative commands wait for the initial synchronization before reading or
editing. Writes update the shared CRDT. Saving to disk follows
the server's autosave policy.

For Jupyverse, install the collaboration plugins in the server environment:

```bash
pip install 'jupyverse[jupyterlab,noauth,collaboration]'
jupyverse --timeout 10
```
