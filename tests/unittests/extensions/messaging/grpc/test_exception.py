import unittest

from roleml.core.messaging.exceptions import InvocationFailedError, InvocationAbortError
from roleml.core.messaging.types import Tags, Args, Payloads
from tests.unittests.extensions.messaging.grpc.base import GRPCMessagingTestCase


class GRPCMessagingExceptionTestCase(GRPCMessagingTestCase):

    def test_sender_error(self):
        def on_helloworld(_: str, _tags: Tags, _args: Args, _payloads: Payloads):
            raise InvocationAbortError('hello world!')

        self.componentB.add_procedure('helloworld', on_helloworld)
        self.assertRaises(InvocationAbortError, self.componentA.invoke_procedure, self.profileB, 'helloworld')

    def test_receiver_error(self):
        def on_helloworld(_: str, _tags: Tags, _args: Args, _payloads: Payloads):
            raise RuntimeError('hello world! (if this exception is seen in the console, it is normal)')

        self.componentB.add_procedure('helloworld', on_helloworld)
        self.assertRaises(InvocationFailedError, self.componentA.invoke_procedure, self.profileB, 'helloworld')


if __name__ == '__main__':
    unittest.main()
