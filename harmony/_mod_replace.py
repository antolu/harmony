def replace_modname(obj: object, name: str) -> None:
    if hasattr(obj, "__module__"):
        obj.__module__ = name
