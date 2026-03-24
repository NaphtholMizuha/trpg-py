from trpg_py.errors import StatePathError
from trpg_py.store.core import read, split_path, write


def get_path(state: object, path: str) -> object:
    return read(state, path)


def has_path(state: object, path: str) -> bool:
    try:
        read(state, path)
    except StatePathError:
        return False
    return True


def set_path(state: object, path: str, value: object) -> None:
    write(state, path, value)


__all__ = ["get_path", "has_path", "set_path", "split_path"]
