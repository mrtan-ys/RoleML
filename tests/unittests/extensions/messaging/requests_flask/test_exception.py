import unittest

from roleml.core.messaging.exceptions import InvocationFailedError, InvocationAbortError
from roleml.core.messaging.types import Tags, Args, Payloads
from tests.unittests.extensions.messaging.requests_flask.base import RequestsFlaskMessagingTestCase


class RequestsFlaskMessagingExceptionTestCase(RequestsFlaskMessagingTestCase):

    def test_sender_error(self):
        def on_helloworld(_: str, _tags: Tags, _args: Args, _payloads: Payloads):
            raise InvocationAbortError('hello world!')

        self.provider.add_procedure('helloworld', on_helloworld)
        self.assertRaises(InvocationAbortError, self.invoker.invoke_procedure, self.profileB, 'helloworld')

    def test_receiver_error(self):
        def on_helloworld(_: str, _tags: Tags, _args: Args, _payloads: Payloads):
            raise RuntimeError('hello world! (if this exception is seen in the console, it is normal)')

        self.provider.add_procedure('helloworld', on_helloworld)
        self.assertRaises(InvocationFailedError, self.invoker.invoke_procedure, self.profileB, 'helloworld')


if __name__ == '__main__':
    unittest.main()
