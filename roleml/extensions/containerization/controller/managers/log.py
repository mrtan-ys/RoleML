import logging
from typing_extensions import override

from roleml.core.actor.manager.bases import BaseManager
from roleml.core.messaging.types import Args, Payloads, Tags
from roleml.core.role.base import Role


LOG_EMIT_CHANNEL = "LOG_EMIT"


class LogManager(BaseManager):

    @override
    def initialize(self):
        self.procedure_provider.add_procedure(LOG_EMIT_CHANNEL, self._on_log_emit)
        self.logger = logging.getLogger('roleml.managers.log')
    
    def _on_log_emit(self, sender: str, tags: Tags, args: Args, _: Payloads):
        try:
            instance_name = tags["instance_name"]
        except KeyError:
            raise AssertionError("instance_name is required")
        
        log_dict = {**args}
        log_dict.pop("processName", None)
        log_record = logging.makeLogRecord(log_dict)
        logger = logging.getLogger(f"roleml.containerized_roles.{instance_name}")
        log_record.name = f"{logger.name}[{log_record.name}]"
        logger.handle(log_record)

    @override
    def add_role(self, role: Role):
        pass
