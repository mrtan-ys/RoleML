from typing import Literal, ParamSpec, TypeVar

from roleml import LOG_LEVEL_INTERNAL

__all__ = ['T', 'Key', 'Value', 'LogLevel', 'LOG_LEVEL_INTERNAL']


T = TypeVar('T')
Key = TypeVar('Key')
Value = TypeVar('Value')

P = ParamSpec('P')

LogLevel = Literal['DISABLED', 'INTERNAL', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
