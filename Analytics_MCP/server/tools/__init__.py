# from .basic_tools import *    # noqa
# from .math_tools import *     # noqa
# from .remote_tools import *   # noqa
# from . import remote_tools  # Ensure remote_tools is imported to register its tools
#from .test_inventory_tools import *  # noqa

# tools/__init__.py
# Intentionally empty: do NOT import submodules here.
# Registration happens only when modules are imported by the server loader.
__all__ = []  # optional; prevents wildcard surprises
