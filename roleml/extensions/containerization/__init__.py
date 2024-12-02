import sys
import warnings

if sys.version_info < (3, 11):
    raise RuntimeError('Containerization mode requires Python 3.11 or higher')

warnings.warn('Containerization mode of RoleML is experimental.')
