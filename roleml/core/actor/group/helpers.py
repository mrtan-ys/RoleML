from collections.abc import Iterable
from enum import Enum, auto

from roleml.core.role.types import Message, Args, Payloads

__all__ = ['ErrorHandlingStrategy', 'scatter_arg', 'scatter_payloads', 'scatter_args_and_payloads']


class ErrorHandlingStrategy(Enum):

    IGNORE = auto()
    """ Ignore the error; will not appear in the result or failed list. """

    RAISE_FIRST = auto()
    """ Raise an exception for the 1st error occurred. The exception will be wrapped to add procedure provider info. """

    RETRY = auto()
    """ Retry a request if it has failed. Note that if the request results in a SenderError, it will not be retried. """
    # TODO configurable max_retries in implementations

    KEEP = auto()
    """ In case of an error, treat the corresponding exception as the result. """


def scatter_arg(args_to_scatter: Iterable[Args], *, payloads=None):
    for args in args_to_scatter:
        yield Message(args, payloads or {})


def scatter_payloads(payloads_to_scatter: Iterable[Payloads], *, args=None):
    for payloads in payloads_to_scatter:
        yield Message(args or {}, payloads)


def scatter_args_and_payloads(args_to_scatter: Iterable[Args], payloads_to_scatter: Iterable[Payloads]):
    aps = zip(args_to_scatter, payloads_to_scatter)
    for args, payloads in aps:
        yield Message(args, payloads)
