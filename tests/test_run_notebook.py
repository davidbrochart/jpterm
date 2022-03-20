import subprocess
from pathlib import Path


def test_run_notebook(start_jupyverse):
    log = Path("log.txt")
    if log.is_file():
        log.unlink()
    url = start_jupyverse
    cmd = ["jpterm", "--use-server", url, "--run", "tests/files/nb0.ipynb"]
    subprocess.call(cmd)
    assert log.is_file()
    text = log.read_text()
    assert text == "executed!"
