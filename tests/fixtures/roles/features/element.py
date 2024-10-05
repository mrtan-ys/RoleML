from roleml.core.role.base import Role
from roleml.core.role.channels import Service
from roleml.core.role.elements import Element


class DataHolder(Role):

    data = Element(object)

    @Service
    def get_data(self, caller, args, payloads):     # noqa: unused arguments
        return self.data()


class DataFetcher(Role):

    def do_get_data(self):
        return self.call('data-holder', 'get-data')
