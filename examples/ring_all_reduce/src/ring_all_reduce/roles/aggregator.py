from threading import Lock
from typing import Any, Optional, Callable

from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Service
from roleml.core.role.elements import Element


class AllReduceAggregator(Role):

    DEFAULT_COLLECT_CHANNEL = 'train'
    DEFAULT_APPLY_UPDATE_CHANNEL = 'apply-update'
    DEFAULT_SOURCE_RELATIONSHIP = 'source'

    split_op = Element(Callable)
    add_op = Element(Callable, default_impl=lambda a, b: a + b)
    divide_op = Element(Callable, default_impl=lambda a, count: a / count)
    recover_op = Element(Callable)

    def __init__(self, client_id: int = 0, num_clients: int = 0,
                 collect_channel: Optional[str] = None, apply_update_channel: Optional[str] = None,
                 source_relationship: Optional[str] = None):
        super().__init__()
        self.client_id: int = client_id
        self.num_clients: int = num_clients

        self.data_blocks: Any = None
        self.target_peer: Optional[RoleInstanceID] = None
        self.current_send_block_id: int = client_id

        self.data_lock = Lock()

        self.collect_channel = collect_channel or self.DEFAULT_COLLECT_CHANNEL
        self.apply_update_channel = apply_update_channel or self.DEFAULT_APPLY_UPDATE_CHANNEL
        self.source_relationship = source_relationship or self.DEFAULT_SOURCE_RELATIONSHIP

    @Service(expand=True)
    def scatter_reduce_initialize(self, _, **options):
        update = self.call_task(self.source_relationship, self.collect_channel, args=options).result()
        self.data_blocks = self.split_op()(update, self.num_clients)
        self.target_peer = list(self.ctx.relationships.get_relationship('peer-aggregator'))[0]
        self.current_send_block_id = self.client_id
        self.logger.info("scatter reduce phase initialize completed")

    @Service(expand=True)
    def accept_add(self, _, block_id: int, data: Any):
        with self.data_lock:
            self.data_blocks[block_id] = self.add_op()(self.data_blocks[block_id], data)

    @Service(expand=True)
    def scatter_reduce_step(self, _):
        self.call(self.target_peer, 'accept-add',   # type: ignore  # this Service should be called after initialize
                  payloads={'block_id': self.current_send_block_id,
                            'data': self.data_blocks[self.current_send_block_id]})
        self.current_send_block_id = ((self.current_send_block_id - 1) + self.num_clients) % self.num_clients

    @Service(expand=True)
    def all_gather_initialize(self, _):
        # self.target_peer = list(self.ctx.relationships.get_relationship('peer-aggregator'))[0]
        self.current_send_block_id = (self.client_id + 1) % self.num_clients
        self.logger.info("all gather phase initialize completed")

    @Service(expand=True)
    def accept_replace(self, _, block_id: int, data: Any):
        with self.data_lock:
            self.data_blocks[block_id] = data

    @Service(expand=True)
    def all_gather_step(self, _):
        self.call(self.target_peer, 'accept-replace',   # type: ignore  # this Service should be called after initialize
                  payloads={'block_id': self.current_send_block_id,
                            'data': self.data_blocks[self.current_send_block_id]})
        self.current_send_block_id = ((self.current_send_block_id - 1) + self.num_clients) % self.num_clients

    @Service(expand=True)
    def all_reduce_finished(self, _):
        for i in range(self.num_clients):
            self.data_blocks[i] = self.divide_op()(self.data_blocks[i], self.num_clients)
        recovered_update = self.recover_op()(self.data_blocks)
        self.call(self.source_relationship, self.apply_update_channel, payloads={'update': recovered_update})
