When jpterm is invoked with a command, it runs as a CLI in your terminal without taking control, inlining potential outputs below the command.

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
