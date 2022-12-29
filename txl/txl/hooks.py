from enum import Enum
from typing import Any, Dict, Tuple

import pluggy
from asphalt.core import Component


class HookType(Enum):
    COMPONENT = "txl_component"


@pluggy.HookspecMarker(HookType.COMPONENT.value)
def component() -> Tuple[str, type[Component], Dict[str, Any]]:
    pass


def register_component(name: str, component: type[Component], **config: Dict[str, Any]):
    def callback() -> Tuple[str, type[Component], Dict[str, Any], str]:
        return name, component, config

    return pluggy.HookimplMarker(HookType.COMPONENT.value)(
        function=callback, specname="component"
    )
