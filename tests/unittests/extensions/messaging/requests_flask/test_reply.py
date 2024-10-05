import unittest

from roleml.core.messaging.types import Tags, Args, Payloads
from tests.unittests.extensions.messaging.requests_flask.base import RequestsFlaskMessagingTestCase


class RequestsFlaskMessagingReplyingTestCase(RequestsFlaskMessagingTestCase):

    def test_reply_nothing(self):
        def on_helloworld(_sender: str, _tags: Tags, _args: Args, _payloads: Payloads):
            del _sender, _tags, _args, _payloads
            return None

        self.provider.add_procedure('helloworld', on_helloworld)
        res = self.invoker.invoke_procedure(self.profileB, 'helloworld')
        self.assertIsNone(res)

    def test_reply_json(self):
        return_value = {'a': 1, 'b': 2, 'c': 3.1415926, 'd': True, 'e': [6, 7, 8], 'f': {'g': 9, 'h': 10}}

        def on_helloworld(_sender: str, _tags: Tags, _args: Args, _payloads: Payloads):
            del _sender, _tags, _args, _payloads
            return return_value

        self.provider.add_procedure('helloworld', on_helloworld)
        res = self.invoker.invoke_procedure(self.profileB, 'helloworld')
        self.assertEqual(res, return_value)

    def test_return_bytes(self):
        return_value = b'i-am-a-bytes-object'

        def on_helloworld(_sender: str, _tags: Tags, _args: Args, _payloads: Payloads):
            del _sender, _tags, _args, _payloads
            return return_value

        self.provider.add_procedure('helloworld', on_helloworld)
        res = self.invoker.invoke_procedure(self.profileB, 'helloworld')
        self.assertEqual(res, return_value)

    def test_reply_object(self):
        err_message = 'I am an exception'

        def on_helloworld(_sender: str, _tags: Tags, _args: Args, _payloads: Payloads):
            del _sender, _tags, _args, _payloads
            return RuntimeError(err_message)    # we are returning, not raising

        self.provider.add_procedure('helloworld', on_helloworld)
        res = self.invoker.invoke_procedure(self.profileB, 'helloworld')
        self.assertEqual(type(res), RuntimeError)
        self.assertEqual(str(res), err_message)


if __name__ == '__main__':
    unittest.main()
