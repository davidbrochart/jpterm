from typing import List, Optional

import typer
from asphalt.core.cli import run as asphalt_run

from .app import run


def main(configfiles: Optional[List[str]] = typer.Argument(None)):
    if configfiles:
        asphalt_run(configfiles)
    else:
        run()


def run_main():
    typer.run(main)


if __name__ == "__main__":
    run_main()
