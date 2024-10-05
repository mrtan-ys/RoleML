class MessagingError(Exception):
    pass


class ProcedureInvokerError(MessagingError):
    pass    # corresponds to 4xx or message unsent


class InvalidInvokerError(ProcedureInvokerError):
    pass    # corresponds to 401


class ProcedureNotFoundError(ProcedureInvokerError):
    pass    # corresponds to 404


class InvocationRefusedError(ProcedureInvokerError):
    pass    # corresponds to 412


class InvocationAbortError(ProcedureInvokerError):
    pass    # corresponds to 400


class InvocationRedirectError(ProcedureInvokerError):
    pass    # corresponds to 3xx


class InvocationFailedError(MessagingError):
    pass    # corresponds to 5xx


class MsgConnectionError(MessagingError):
    pass


class HandshakeError(MessagingError):
    pass


class HandwaveError(MessagingError):
    pass
