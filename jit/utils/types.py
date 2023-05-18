"""
Define generic utility types that expand on the base types provided by Python.
"""
from types import TracebackType
from typing import Any, Dict, Tuple, Type

# Response from sys.exc_info():
#   https://docs.python.org/3/library/sys.html#sys.exc_info
ExcInfoType = Tuple[Type[BaseException], BaseException, TracebackType]

# A JSON-serializable `dict`
# TODO: Consider making this more specific
JsonDict = Dict[str, Any]
