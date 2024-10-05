import unittest

from roleml.core.messaging.types import Tags, Args, Payloads
from tests.unittests.extensions.messaging.requests_flask.base import RequestsFlaskMessagingTestCase


class RequestsFlaskMessagingSendingTestCase(RequestsFlaskMessagingTestCase):

    def test_sending_nothing(self):
        def on_helloworld(sender: str, _tags: Tags, args: Args, payloads: Payloads):
            self.assertEqual(sender, self.profileA.name)
            self.assertEqual(args, {})
            self.assertEqual(payloads, {})

        self.provider.add_procedure('helloworld', on_helloworld)
        self.invoker.invoke_procedure(self.profileB, 'helloworld', {}, {})

    def test_sending_args(self):
        args = {'a': 'Hello World!', 'b': 1234567, 'c': 3.1415926, 'd': True, 'e': [1, 2, 3]}

        def on_helloworld(sender: str, _tags: Tags, _args: Args, _payloads: Payloads):
            self.assertEqual(sender, self.profileA.name)
            self.assertEqual(_args, args)
            self.assertEqual(_payloads, {})
            # return msg

        self.provider.add_procedure('helloworld', on_helloworld)
        self.invoker.invoke_procedure(self.profileB, 'helloworld', args=args)

    def test_sending_tags(self):
        tags = {'a': 'Hello World!'}

        def on_helloworld(_: str, _tags: Tags, _args: Args, _payloads: Payloads):
            self.assertEqual(_tags['a'], tags['a'])

        self.provider.add_procedure('helloworld', on_helloworld)
        self.invoker.invoke_procedure(self.profileB, 'helloworld', tags=tags)

    def test_sending_bytes_via_payloads(self):
        payloads = {'a': b'Hello World!', 'b': b'1234567', 'c': b'3.1415926', 'd': b'True', 'e': b'[1, 2, 3]'}

        def on_helloworld(sender: str, _tags: Tags, _args: Args, _payloads: Payloads):
            self.assertEqual(sender, self.profileA.name)
            self.assertEqual(_args, {})
            self.assertEqual(_payloads, payloads)
            # return msg

        self.provider.add_procedure('helloworld', on_helloworld)
        self.invoker.invoke_procedure(self.profileB, 'helloworld', payloads=payloads)

    def test_sending_bytes_via_args(self):
        args = {'a': b'Hello World!'}

        def on_helloworld(_sender: str, _tags: Tags, _args: Args, _payloads: Payloads):
            self.assertEqual(_args, args)
            self.assertEqual(_payloads, {})
            # return msg

        self.provider.add_procedure('helloworld', on_helloworld)
        self.invoker.invoke_procedure(self.profileB, 'helloworld', args=args)

    def test_sending_objects(self):
        payloads = {'a': {'x': 44, 'y': 16}, 'b': 1 + 2j}

        def on_helloworld(_sender: str, _tags: Tags, _args: Args, _payloads: Payloads):
            del _sender, _tags, _args
            self.assertDictEqual(_payloads, payloads)

        self.provider.add_procedure('helloworld', on_helloworld)
        self.invoker.invoke_procedure(self.profileB, 'helloworld', payloads=payloads)


if __name__ == '__main__':
    unittest.main()
