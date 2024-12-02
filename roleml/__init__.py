__version__ = '0.3.0'

LOG_LEVEL_INTERNAL = 5
""" This level should only be used when customizing RoleML. """
# hint: do not import from here; import from roleml.shared.types instead

import logging  # noqa: E402
logging.addLevelName(LOG_LEVEL_INTERNAL, 'INTERNAL')
