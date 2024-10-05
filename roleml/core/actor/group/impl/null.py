from roleml.core.actor.group.base import CollectiveImplementor


class CollectiveImplementorDisabled(CollectiveImplementor):
    call = None         # type: ignore
    call_task = None    # type: ignore
