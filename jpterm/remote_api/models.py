from pydantic import BaseModel


class KernelName(BaseModel):
    name: str


class CreateSession(BaseModel):
    kernel: KernelName
    name: str
    path: str
    type: str


class Kernel(BaseModel):
    id: str
    name: str
    last_activity: str
    execution_state: str
    connections: int


class Notebook(BaseModel):
    path: str
    name: str


class Session(BaseModel):
    id: str
    path: str
    name: str
    type: str
    kernel: Kernel
    notebook: Notebook
