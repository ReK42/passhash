"""Generate password hashes based on various standards."""
from typing import Any

__all__ = []


def export(defn: Any) -> None:  # noqa: ANN401
    """Module-level export decorator."""
    globals()[defn.__name__] = defn
    __all__.append(defn.__name__)  # noqa: PYI056
    return defn


__copyright__ = "Copyright (c) 2022 Ryan Kozak"
from passhash._version import __version__
from passhash.passhash import ALGORITHMS, main
