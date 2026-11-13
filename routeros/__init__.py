"""routeros -- an interpreter for the RouterOS scripting language.

Run/parse real RouterOS scripts on a plain host, against a pluggable
``DeviceModel``. See :func:`routeros.launcher.load_file` /
:func:`routeros.launcher.load_source` and the ``examples/`` scripts.
"""

from .launcher import Script, load_file, load_source  # noqa: F401
from .parser import parse  # noqa: F401
from .values import NOTHING, ROArray, Time  # noqa: F401
