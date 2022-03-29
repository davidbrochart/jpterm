import asyncio
import subprocess
import sys
from pathlib import Path

import pytest
from jpterm.notebook import Notebook


NB_DIR = Path() / "tests" / "files"


async def run_nb(api, path: Path):
    nb = Notebook(api=api, path=path)
    await nb.open()
    await nb.run_all()
    await nb.close()
    return nb


@pytest.mark.skipif(
    sys.platform.startswith("win") and sys.version_info < (3, 8),
    reason="ipykernel issue",
)
def test_run_notebook_remotely_cli(start_jupyverse):
    log = Path("log.txt")
    if log.is_file():
        log.unlink()
    url = start_jupyverse
    cmd = ["jpterm", "--use-server", url, "--run", str(NB_DIR / "nb0.ipynb")]
    subprocess.call(cmd)
    assert log.is_file()
    text = log.read_text()
    assert text == "Cell 1 executed!"


@pytest.mark.skipif(
    sys.platform.startswith("win") and sys.version_info < (3, 8),
    reason="ipykernel issue",
)
def test_run_notebook_remotely(start_jupyverse):
    url = start_jupyverse
    from jpterm.remote_api import API

    api = API(url)

    nb = asyncio.run(run_nb(api, NB_DIR / "nb0.ipynb"))
    assert nb.cells[1].json["outputs"][0]["text"][0] == "Cell 2 executed!\n"
