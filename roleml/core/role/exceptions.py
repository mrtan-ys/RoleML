class NoSuchRoleError(RuntimeError):
    pass


class RoleInteractionError(Exception):
    pass


class HandlerError(RoleInteractionError):
    pass


class CallerError(RoleInteractionError):
    pass


class ChannelNotFoundError(RoleInteractionError):
    pass


class TaskResultTimeoutError(RoleInteractionError):
    pass


class NoSuchEventError(RoleInteractionError):
    pass


class InternalError(RoleInteractionError):
    pass
