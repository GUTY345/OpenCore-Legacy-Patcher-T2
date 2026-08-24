from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # Python 3.9 compatibility
    class StrEnum(str, Enum):
        pass
