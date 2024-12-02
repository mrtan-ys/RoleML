from dataclasses import dataclass
import datetime
import re
import subprocess
import threading
import time
from typing import TypedDict, Generator, TYPE_CHECKING
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
        for role_name, raw_stat in container_raw_statistics.items():
            time_str = raw_stat["read"]
            # the time string from docker stats api has more than 6 digits after the dot
            # truncate it to 6 digits
            time_str_truncated = re.sub(r'(\.\d{6})\d+', r'\1', time_str)
            time = datetime.datetime.strptime(
                time_str_truncated, "%Y-%m-%dT%H:%M:%S.%f%z"
            )

            previous_role_raw_stats = self._pre_raw_stats.get(role_name)
            if previous_role_raw_stats is None:
                # 这里的precpu_stats是docker获取的上一秒的数据
                pre_cpu = raw_stat["precpu_stats"]["cpu_usage"]["total_usage"]
                pre_system = raw_stat["precpu_stats"]["system_cpu_usage"]
            else:
                # 使用自己保存的上一秒的数据
                pre_cpu = previous_role_raw_stats["cpu_stats"]["cpu_usage"][
                    "total_usage"
                ]
                pre_system = previous_role_raw_stats["cpu_stats"]["system_cpu_usage"]

            cpu_delta = raw_stat["cpu_stats"]["cpu_usage"]["total_usage"] - pre_cpu
            system_delta = raw_stat["cpu_stats"]["system_cpu_usage"] - pre_system
            cpu_percent = (
                cpu_delta / system_delta * (raw_stat["cpu_stats"]["online_cpus"]) * 100
            )  # percent，0-100*cpu核数

            memory_usage = raw_stat["memory_stats"]["usage"]  # byte
            net_rx = raw_stat["networks"]["eth0"]["rx_bytes"]  # byte
            net_tx = raw_stat["networks"]["eth0"]["tx_bytes"]  # byte

            refined_stats[role_name] = ContainerStats(
                time,
                cpu_percent,
                int(memory_usage),
                int(net_rx),
                int(net_tx),
            )

        # 保存上一秒的数据，用于计算cpu使用率
        self._pre_raw_stats = container_raw_statistics
        return refined_stats

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
