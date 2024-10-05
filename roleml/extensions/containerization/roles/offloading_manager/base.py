from enum import Enum
import threading
import time
from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import EventHandler, HandlerDecorator, Service, Task


class Migration:
    class Status(Enum):
        PENDING = 0
        # RECIEVED = 1
        # READY = 2
        STARTED = 3
        SUCCESS = 4
        FAILED = 5

    def __init__(self, src: str, role: str, dst: str):
        self.src = src
        self.role = role
        self.dst = dst
        self.status = Migration.Status.PENDING
        self.time_measured = {}

    def __repr__(self):
        return f"<Migration {self.role} {self.src} -> {self.dst} ({self.status.name})>"

    @property
    def role_instance(self):
        return RoleInstanceID(self.src, self.role)


class MigrationManager:
    def __init__(self):
        self.migrations: dict[RoleInstanceID, Migration] = {}

    def new_migration(self, src: str, role: str, dst: str):
        self.migrations[RoleInstanceID(src, role)] = Migration(src, role, dst)

    def get_migration(self, src: str, role: str):
        return self.migrations[RoleInstanceID(src, role)]

    def update_status(self, src: str, role: str, status: Migration.Status):
        self.migrations[RoleInstanceID(src, role)].status = status


class OffloadingManager(Role):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.migration_manager_lock = threading.Lock()
        self.migration_manager = MigrationManager()
        self.current_migrating_roles = []
        self.start_time = None

    @EventHandler("/", "contact-updated", expand=True)
    def on_contacts_updated(self, _, name: str):
        executor_id = RoleInstanceID(name, "offloading_executor")
        self.subscribe(
            executor_id,
            "offload-started",
            self.on_offload_started,
        )
        self.subscribe(
            executor_id,
            "offload-succeeded",
            self.on_offload_succeeded,
        )
        self.subscribe(
            executor_id,
            "offload-failed",
            self.on_offload_failed,
        )

    def _offload_impl(self, src_node: str, role: str, dst_node: str):
        self.call(
            RoleInstanceID(src_node, "actor"),
            "update-contacts",
            {
                "contacts": {
                    dst_node: self.ctx.contacts.get_actor_profile(dst_node).address
                }
            },
        )
        self.call(
            RoleInstanceID(dst_node, "actor"),
            "update-contacts",
            {
                "contacts": {
                    src_node: self.ctx.contacts.get_actor_profile(src_node).address
                }
            },
        )

        if src_node == dst_node:
            raise ValueError("src and dst cannot be the same")

        with self.migration_manager_lock:
            self.migration_manager.new_migration(src_node, role, dst_node)

        task = self.call_task(
            RoleInstanceID(src_node, "offloading_executor"),
            "offload",
            {
                "instance_name": role,
                "destination_actor_name": self.migration_manager.get_migration(
                    src_node, role
                ).dst,
            },
        )
        task.result()

    @Task("offload-roles", expand=True)
    def offload_roles(self, _, plan: dict[RoleInstanceID, str]):
        self.start_time = time.time()
        futures = []
        for role, dst in plan.items():
            self.current_migrating_roles.append(role)
            f = self.base.thread_manager.add_threaded_task(
                self._offload_impl, (role.actor_name, role.instance_name, dst)
            )
            futures.append(f)
        for f in futures:
            f.result()

    @HandlerDecorator(expand=True)
    def on_offload_started(
        self, _, source_actor_name: str, instance_name: str, destination_actor_name: str
    ):
        migration = self.migration_manager.get_migration(
            source_actor_name, instance_name
        )
        with self.migration_manager_lock:
            self.migration_manager.update_status(
                source_actor_name, instance_name, Migration.Status.STARTED
            )

    @HandlerDecorator(expand=True)
    def on_offload_succeeded(
        self,
        _,
        source_actor_name: str,
        instance_name: str,
        destination_actor_name: str,
        destination_actor_address: str,
        # timer: dict[str, float],
    ):
        # m = self.migration_manager.get_migration(source_actor_name, instance_name)
        # m.time_measured = timer
        with self.migration_manager_lock:
            self.migration_manager.update_status(
                source_actor_name, instance_name, Migration.Status.SUCCESS
            )
        # text = ""
        # for n, t in timer.items():
        #     text += f"{n}={t:.2f}s "

    @HandlerDecorator(expand=True)
    def on_offload_failed(
        self,
        _,
        source_actor_name: str,
        instance_name: str,
        destination_actor_name: str,
        error: str,
    ):
        with self.migration_manager_lock:
            self.migration_manager.update_status(
                source_actor_name, instance_name, Migration.Status.FAILED
            )
