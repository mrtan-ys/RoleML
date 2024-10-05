from pathlib import Path
from roleml.core.context import ActorProfile, RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Event, EventHandler, HandlerDecorator, Service, Task
from roleml.core.role.exceptions import CallerError, HandlerError, NoSuchRoleError
from roleml.core.status import Status
from roleml.extensions.containerization.controller.helpers.docker import DockerService
import roleml.extensions.containerization.controller.impl as containerization_controller


class OffloadingExecutor(Role):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # TODO 检查self.base的类型是否是NodeController。下面这行代码在初始化时会报错
        # assert isinstance(self.base, containerization_controller.NodeController)
        self.base: containerization_controller.NodeController  # make type hinting happy

    @property
    def _temp_dir(self):
        return self.base.containerization_config.temp_dir

    @Task("offload", expand=True)
    def offload(self, _, instance_name: str, destination_actor_name: str):
        try:
            ctrl = self.base.role_status_manager.ctrl(instance_name)
        except NoSuchRoleError:
            raise AssertionError(f"role {instance_name} not found")

        self.logger.info(f"Offloading role {instance_name} to {destination_actor_name}")

        # block calls to/from the role
        self.logger.info(f"Pausing role {instance_name}")
        try:
            ctrl.pause()
        except Exception as e:
            # the status of the role automatically rolls back to READY
            self.logger.exception(f"Error pausing role {instance_name}: {e}")
            raise HandlerError(f"Error pausing role {instance_name}: {e}") from e

        self.offload_started_event.emit(
            {
                "source_actor_name": self.base.profile.name,
                "instance_name": instance_name,
                "destination_actor_name": destination_actor_name,
            }
        )

        self.logger.info(f"Checkpointing role {instance_name}")
        ckpt_save_dir = Path(self._temp_dir) / "checkpoints"
        ckpt_tar_path = self.base.container_manager.checkpoint_container(
            instance_name, ckpt_save_dir
        )

        try:
            self.logger.info(f"Sending checkpoint to {destination_actor_name}")
            with open(ckpt_tar_path, "rb") as f:
                restore_task = self.call_task(
                    RoleInstanceID(
                        destination_actor_name, self.name
                    ),  # call the destination executor
                    "restore",
                    {
                        "instance_name": instance_name,
                        "contacts": list(
                            filter(
                                lambda x: not x.name.startswith(f"{self.profile.name}_"),
                                self.base.ctx.contacts.all_actors(),
                            )
                        ),
                    },
                    # the grpc component does not support streaming file transfer yet.
                    # So we have to read the whole file into memory and send it as a byte string.
                    {"checkpoint": f.read()},  # TODO may be memory-consuming
                )
            # the invocation returns after the checkpoint is restored
            restore_task.result()  # wait for the restore task to finish
            self.logger.info(
                f"Container {instance_name} restored on {destination_actor_name}"
            )

        except Exception as e:
            if isinstance(e, CallerError):
                self.logger.exception(
                    f"Error sending checkpoint to {destination_actor_name}: {e}"
                )
            else:
                self.logger.exception(
                    f"Error restoring container {instance_name} on {destination_actor_name}: {e}"
                )
            self.offload_failed_event.emit(
                {
                    "source_actor_name": self.base.profile.name,
                    "instance_name": instance_name,
                    "destination_actor_name": destination_actor_name,
                    "error": str(e),
                }
            )
            self.logger.info(f"Restoring container {instance_name} locally")
            self.base.container_manager.restore_container(instance_name, ckpt_tar_path)
            ctrl.ready()
            Path(ckpt_tar_path).unlink()  # remove the checkpoint
            return

        Path(ckpt_tar_path).unlink()  # remove the checkpoint
        desination_actor_profile = self.base.ctx.contacts.get_actor_profile(
            destination_actor_name
        )

        # the blocked calls will be redirected to the destination actor
        # after they are released.
        # so we need to notify other actor about the offload first
        # to let them handle the redirection correctly.

        # first,
        # notify other actors about the offload
        # let them update their contacts and instance IDs
        to_notify = [*self.base.ctx.contacts.all_actors()]
        for profile in to_notify:
            if profile.name == self.profile.name:
                continue
            if profile.name.startswith(f"{self.profile.name}_"):
                continue
            try:
                self.call(
                    RoleInstanceID(profile.name, "offloading_executor"),
                    "notify-offload-succeeded",
                    {
                        "source_actor_name": self.base.profile.name,
                        "instance_name": instance_name,
                        "destination_actor_name": destination_actor_name,
                        "destination_actor_address": desination_actor_profile.address,
                    },
                )
            except CallerError as e:
                # TODO 这样识别错误肯定是不好的，但CallerError确实缺乏信息，需要一种更好的跨节点错误传递方式。
                if "offloading_executor does not exist" in str(e):
                    self.logger.debug(
                        f"Offloading executor not found on {profile.name}. Skipping."
                    )
                else:
                    self.logger.error(
                        f"Error notifying {profile.name} about offload: {e}"
                    )

        self._update_instance_id_impl(
            self.base.profile.name,
            instance_name,
            destination_actor_name,
        )

        # then,
        # mark the role as offloaded and remove the container
        # and release the blocked calls.
        ctrl.terminate_as_offloaded(desination_actor_profile)

        self.offload_succeeded_event.emit(
            {
                "source_actor_name": self.base.profile.name,
                "instance_name": instance_name,
                "destination_actor_name": destination_actor_name,
                "destination_actor_address": desination_actor_profile.address,
            }
        )
        self.logger.info(f"Role {instance_name} offloaded to {destination_actor_name}")

    @Task("restore", expand=True)
    def restore(
        self, sender: RoleInstanceID, instance_name: str, contacts: list[ActorProfile], checkpoint: bytes
    ):
        for contact in contacts:
            if contact.name != self.base.profile.name:
                self.base.ctx.contacts.add_contact(contact)

        self.logger.info(f"Restoring role {instance_name}")
        ckpt_save_path = (
            Path(self._temp_dir) / "received_checkpoints" / f"{instance_name}.tar.gz"
        )
        ckpt_save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ckpt_save_path, "wb") as f:
            f.write(checkpoint)
        self.logger.info(f"Checkpoint saved to file")
        self.logger.info(f"Restoring container for role {instance_name}")
        self.base.container_manager.restore_container(instance_name, ckpt_save_path)

        ctrl = self.base.role_status_manager.add_role(instance_name)
        ctrl._transfer_status(Status.DECLARED, False, slient=True)

        try:
            self.call(
                self.base.get_containerized_role_id(instance_name),
                "change-controller",
                {
                    # see `change_controller` in runtime/impl.py
                    "new_profile": ActorProfile(
                        self.base.profile.name,
                        self.base.container_manager._convert_loopback_to_host(
                            self.base.ctx.profile.address
                        ),
                    ),
                    "old_profile": ActorProfile(
                        sender.actor_name,
                        self.ctx.contacts.get_actor_profile(sender.actor_name).address,
                    ),
                },
            )

            self.logger.info(f"Resuming role {instance_name}")
            ctrl._transfer_status(Status.PAUSED, False, slient=True)
            ctrl.ready(ignore_callback_error=False)

            ckpt_save_path.unlink()  # remove the checkpoint
            self.logger.info(f"Role {instance_name} restored")
        except:
            self.logger.exception(f"Error updating role status {instance_name}")
            ctrl.terminate()
            raise

    offload_started_event = Event("offload-started")
    offload_succeeded_event = Event("offload-succeeded")
    offload_failed_event = Event("offload-failed")

    @Service("notify-offload-succeeded", expand=True)
    def _on_other_node_offload_succeeded(
        self,
        _,
        source_actor_name: str,
        instance_name: str,
        destination_actor_name: str,
        destination_actor_address: str,
    ):
        self.ctx.contacts.add_contact(
            ActorProfile(destination_actor_name, destination_actor_address)
        )

        self._update_instance_id_impl(
            source_actor_name,
            instance_name,
            destination_actor_name,
        )

        self.logger.info(
            f"Received offload succeeded event from {source_actor_name} for role {instance_name} to {destination_actor_name}. "
            "Contacts and instance ID updated."
        )

    def _update_instance_id_impl(
        self,
        source_actor_name: str,
        instance_name: str,
        destination_actor_name: str,
    ):
        old_instance_id = RoleInstanceID(source_actor_name, instance_name)
        new_instance_id = RoleInstanceID(destination_actor_name, instance_name)
        self.base.update_instance_id(old_instance_id, new_instance_id)

        for containerized_role in self.base.container_manager.containerized_roles:
            if containerized_role == instance_name and self.base.profile.name == source_actor_name:
                continue
            self.call(
                self.base.get_containerized_role_id(containerized_role),
                "update-instance-id",
                {
                    "old_instance_id": old_instance_id,
                    "new_instance_id": new_instance_id,
                },
            )
