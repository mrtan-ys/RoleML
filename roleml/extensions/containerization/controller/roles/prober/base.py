from dataclasses import dataclass
import datetime
import re
import subprocess
import threading
import time
from typing import Any, TypedDict, Generator, TYPE_CHECKING
from typing_extensions import override

import psutil

from roleml.core.context import ActorNotFoundError
from roleml.core.role.base import Role
from roleml.shared.interfaces import Runnable

if TYPE_CHECKING:
    import roleml.extensions.containerization.controller.impl as containerization_controller


@dataclass
class ContainerStats:
    time: datetime.datetime
    cpu_percent: float
    memory_usage: int
    net_rx: int
    net_tx: int


@dataclass
class HostStats:
    time: datetime.datetime
    cpu_percent: float
    cpu_total: float
    memory_usage: int  # bytes
    memory_total: int  # bytes
    nic_speed: int  # Mbps


class RoleStatsRecord(TypedDict):
    time: float  # timestamp
    cpu_percent: float
    memory_usage: int  # bytes
    net_rx: int  # bytes
    bw_rx: float  # Kbps
    net_tx: int
    bw_tx: float  # Kbps
    name: str
    host: str


class HostStatsRecord(TypedDict):
    time: float  # timestamp
    cpu_percent: float
    cpu_total: float
    memory_usage: int  # bytes
    memory_total: int  # bytes
    nic_speed: int  # Mbps
    name: str


class ResourceProber(Role, Runnable):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # TODO 检查self.base的类型是否是NodeController。下面这行代码在初始化时会报错
        # assert isinstance(self.base, containerization_controller.NodeController)
        self.base: containerization_controller.NodeController # make type hinting happy
        
        self._mutex = threading.Lock()
        self._role_stats_buffer: list[RoleStatsRecord] = []
        self._host_stats_buffer: list[HostStatsRecord] = []

        self._latest_role_stats: dict[str, RoleStatsRecord] = {}

        # 用于存储每个角色的docker stats api返回的生成器
        self._docker_stats_generators: dict[str, Generator] = {}
        # 用于存储每个角色上一次采集的原始数据，用于计算CPU利用率
        self._pre_raw_stats: dict[str, dict] = {}

        self._stop_report_loop_event = threading.Event()
        self._stop_collect_loop = False

    def _report_stats_loop(self):
        while not self._stop_report_loop_event.is_set():
            # 10s interval
            # TODO interval should be configurable
            if self._stop_report_loop_event.wait(10):
                break

            role_stats, host_stats = self._get_stats_and_clear_buffer()
            if len(self.ctx.relationships.get_relationship_view("monitor")) > 0:
                try:
                    self.call(
                        "monitor",
                        "update_stats",
                        args=None,
                        payloads={"role_stats": role_stats, "host_stats": host_stats},
                    )
                except ActorNotFoundError:
                    self.logger.debug("Monitor not found, skipped stats update")
                except Exception as e:
                    self.logger.exception(e)
            else:
                self.logger.debug("Monitor not found, skipped stats update")

    def _stat_collection_loop(self):
        while not self._stop_collect_loop:
            t = time.time()
            try:
                self._collect_stats_to_buffer()
            except Exception as e:
                self.logger.error(f"Error collecting stats: {type(e)} - {e}")
                # 预期采集频率为1秒钟一次，
                # 正常情况下每次采集角色数据都会被阻塞1秒钟，所以可以借助这个阻塞时间来控制采集频率。
                # 这里的sleep是为了避免采集角色出现错误时，未按照预期中的阻塞1秒钟，导致采集频率过高。
                time.sleep(max(0, 1 - (time.time() - t)))

    @override
    def run(self):
        f1 = self.base.thread_manager.add_threaded_task(self._stat_collection_loop)
        f2 = self.base.thread_manager.add_threaded_task(self._report_stats_loop)
        f1.result()
        f2.result()

    @override
    def stop(self):
        self._stop_report_loop_event.set()
        self._stop_collect_loop = True

    def _get_stats_and_clear_buffer(self):
        with self._mutex:
            role_stats = self._role_stats_buffer
            host_stats = self._host_stats_buffer
            self._role_stats_buffer = []
            self._host_stats_buffer = []

        return role_stats, host_stats

    def _collect_stats_to_buffer(self):
        containers_stats = self._gather_roles_stats()
        host_stats = self._collect_host_stats()

        with self._mutex:
            for role, stats in containers_stats.items():
                lts_stat = self._latest_role_stats.get(role)
                time_prev = 0.0
                net_rx_prev = 0
                net_tx_prev = 0
                if lts_stat is not None:
                    net_rx_prev = lts_stat["net_rx"]
                    net_tx_prev = lts_stat["net_tx"]
                    time_prev = lts_stat["time"]

                d_time = stats.time.timestamp() - time_prev
                d_net_rx = stats.net_rx - net_rx_prev
                d_net_tx = stats.net_tx - net_tx_prev

                self._role_stats_buffer.append(
                    RoleStatsRecord(
                        time=stats.time.timestamp(),
                        cpu_percent=stats.cpu_percent,
                        memory_usage=stats.memory_usage,
                        net_rx=stats.net_rx,
                        bw_rx=d_net_rx / d_time * 8 / 1000,
                        net_tx=stats.net_tx,
                        bw_tx=d_net_tx / d_time * 8 / 1000,
                        name=role,
                        host=self.base.profile.name,
                    )
                )

            self._host_stats_buffer.append(
                HostStatsRecord(
                    time=host_stats.time.timestamp(),
                    cpu_percent=host_stats.cpu_percent,
                    cpu_total=host_stats.cpu_total,
                    memory_usage=host_stats.memory_usage,
                    memory_total=host_stats.memory_total,
                    nic_speed=host_stats.nic_speed,
                    name=self.base.profile.name,
                )
            )
            if len(self._host_stats_buffer) > 100: # max buffer size
                self._host_stats_buffer.pop(0)

    def _gather_roles_stats(self):
        """
        This function uses docker-py to get container stats.
        The generator returned by docker-py's API fetches data every second internally.
        Therefore, if called consecutively, there will be a 1-second blocking time.
        """
        role_containers = {
            instance_name: container
            for instance_name, container in self.base.container_manager.containers
            if container.status == "running"
        }

        # 保存正在工作的角色的stats generator
        generators = {}
        for role_name, role_container in role_containers.items():
            generators[role_name] = self._docker_stats_generators.get(role_name)
            # 新的角色，需要新建一个generator
            if generators[role_name] is None:
                generators[role_name] = role_container.get_stats_stream()
        self._docker_stats_generators = generators  # 把消失的角色的generator丢掉

        container_raw_statistics = {}  # raw stats collected from docker stats api
        for role_name, stats_generator in self._docker_stats_generators.items():
            try:
                container_raw_statistics[role_name] = next(stats_generator)
            except StopIteration:
                continue
            except Exception as e:
                self.logger.error(f"Error getting stats for role {role_name}: {e}")
                continue

        refined_stats: dict[str, ContainerStats] = {}
        previous_raw_stats: dict[str, dict] = {}
        for role_name, raw_stat in container_raw_statistics.items():
            previous_role_raw_stats = self._pre_raw_stats.get(role_name)
            stats, usable_as_previous = self._parse_container_stats(
                role_name, raw_stat, previous_role_raw_stats
            )
            if usable_as_previous:
                previous_raw_stats[role_name] = raw_stat
            if stats is not None:
                refined_stats[role_name] = stats

        # 保存上一秒的数据，用于计算cpu使用率
        self._pre_raw_stats = previous_raw_stats
        return refined_stats

    def _parse_container_stats(
        self,
        role_name: str,
        raw_stat: dict[str, Any],
        previous_raw_stat: dict[str, Any] | None,
    ) -> tuple[ContainerStats | None, bool]:
        time = self._parse_docker_timestamp(raw_stat.get("read", ""))
        if time is None:
            return None, False

        cpu_stats = raw_stat.get("cpu_stats", {})
        cpu_usage = cpu_stats.get("cpu_usage", {})
        cpu_total = cpu_usage.get("total_usage")
        system_cpu = cpu_stats.get("system_cpu_usage")
        if cpu_total is None or system_cpu is None:
            self.logger.debug(
                f"Skipping stats for role {role_name}: incomplete cpu_stats"
            )
            return None, False

        if previous_raw_stat is None:
            precpu_stats = raw_stat.get("precpu_stats", {})
            precpu_usage = precpu_stats.get("cpu_usage", {})
            pre_cpu = precpu_usage.get("total_usage")
            pre_system = precpu_stats.get("system_cpu_usage")
        else:
            previous_cpu_stats = previous_raw_stat.get("cpu_stats", {})
            previous_cpu_usage = previous_cpu_stats.get("cpu_usage", {})
            pre_cpu = previous_cpu_usage.get("total_usage")
            pre_system = previous_cpu_stats.get("system_cpu_usage")

        if pre_cpu is None or pre_system is None:
            # Keep this complete sample as the next baseline, but do not emit a
            # CPU percentage until a second sample is available.
            return None, True

        cpu_delta = cpu_total - pre_cpu
        system_delta = system_cpu - pre_system
        if cpu_delta < 0 or system_delta <= 0:
            return None, True

        online_cpus = cpu_stats.get("online_cpus")
        if online_cpus is None:
            online_cpus = len(cpu_usage.get("percpu_usage", []) or []) or 1
        cpu_percent = cpu_delta / system_delta * online_cpus * 100

        memory_usage = raw_stat.get("memory_stats", {}).get("usage")
        if memory_usage is None:
            self.logger.debug(
                f"Skipping stats for role {role_name}: incomplete memory_stats"
            )
            return None, True

        networks = raw_stat.get("networks") or {}
        net_rx = sum(int(net.get("rx_bytes", 0)) for net in networks.values())
        net_tx = sum(int(net.get("tx_bytes", 0)) for net in networks.values())

        return (
            ContainerStats(
                time,
                cpu_percent,
                int(memory_usage),
                int(net_rx),
                int(net_tx),
            ),
            True,
        )

    def _parse_docker_timestamp(self, time_str: str) -> datetime.datetime | None:
        if not time_str or time_str.startswith("0001-01-01T00:00:00"):
            return None
        # Docker may emit nanosecond precision and may use trailing Z.
        time_str = time_str.replace("Z", "+00:00")
        time_str = re.sub(r"(\.\d{6})\d+", r"\1", time_str)
        try:
            return datetime.datetime.fromisoformat(time_str)
        except ValueError:
            self.logger.debug(f"Skipping stats with invalid timestamp: {time_str}")
            return None

    def _collect_host_stats(self):
        cpu_count = psutil.cpu_count()
        cpu_percent = sum(psutil.cpu_percent(percpu=True))  # type: ignore
        memory_usage = psutil.virtual_memory().used  # byte
        memory_total = psutil.virtual_memory().total  # byte

        get_nic_speed_cmd = r"cat /sys/class/net/$(ip -o -4 route show to default | awk '{print $5}')/speed"
        nic_speed = (
            subprocess.check_output(get_nic_speed_cmd, shell=True)
            .decode("utf-8")
            .strip()
        )
        nic_speed = int(nic_speed)  # Mbps

        return HostStats(
            datetime.datetime.now(),
            cpu_percent,
            100 * cpu_count,
            int(memory_usage),
            int(memory_total),
            nic_speed,
        )
