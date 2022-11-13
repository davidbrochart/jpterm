from typing import Any, Dict, List

from asphalt.core import Component, Context
from jupyter_ydoc import YNotebook
from txl.base import Notebook, NotebookFactory
from txl.hooks import register_component


class _Notebook(Notebook, YNotebook):
    """A collaborative notebook document."""
    pass


class NotebookFactoryComponent(Component):

    async def start(
        self,
        ctx: Context,
    ) -> None:
        def notebook_factory(nb_dict=None) -> Notebook:
            return _Notebook(nb_dict=nb_dict)
        ctx.add_resource(notebook_factory, name="notebook_factory", types=NotebookFactory)


c = register_component("notebook", NotebookFactoryComponent)
