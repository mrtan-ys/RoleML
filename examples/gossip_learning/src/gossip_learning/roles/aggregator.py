import random
from threading import Lock
from typing import Any

from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Service, Event
from roleml.core.role.elements import Element, ConstructStrategy
from roleml.shared.collections.merger import ValueMerger, CumulativeValueMerger


class GossipAggregator(Role):

    def __init__(self):
        super().__init__()
        self.gossip_lock = Lock()
        self.count = 0

    buffer = Element(
        ValueMerger, default_constructor=CumulativeValueMerger, default_construct_strategy=ConstructStrategy.ONCE_EAGER)

    gossip_accepted = Event()

    @Service(expand=True)
    def accept_gossip(self, source: RoleInstanceID, data: Any):
        with self.gossip_lock:
            self.buffer().push(data)
            self.count += 1
            self.logger.info(f'gossip accepted from {source.actor_name}')
            self.gossip_accepted.emit(args={'source_name': source.actor_name})

    @Service(expand=True)
    def get_data(self, _):
        with self.gossip_lock:
            data = self.buffer().merge()
            count = self.count
            self.buffer.reset()
            self.count = 0
            return data, count

    @Service(expand=True)
    def propagate_gossip(self, _, data: Any):
        selected_peer = self.select_peer()
        self.logger.info(f'propagating gossip to peer {selected_peer.actor_name}')
        self.call(selected_peer, 'accept-gossip', payloads={'data': data})

    def select_peer(self) -> RoleInstanceID:
        peers = list(self.ctx.relationships.get_relationship('peer'))
        return random.sample(peers, k=1)[0]
