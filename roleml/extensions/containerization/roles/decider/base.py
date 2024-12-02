import threading
from typing import Literal, NamedTuple
from typing_extensions import override

import numpy as np

from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import EventHandler
from roleml.extensions.containerization.roles.decider.aco import AntColonyOptimizer
from roleml.extensions.containerization.roles.types import HostInfo
from roleml.shared.interfaces import Runnable


class ResourceVector(NamedTuple):
    cpu: float
    memory: float  # byte
    network_rx: float  # Kbps
    network_tx: float  # Kbps


ResourceType = Literal["cpu", "memory", "network"]


class OffloadingDecider(Role, Runnable):

    def __init__(
        self,
        decide_interval: int = 5 * 60,  # 5 minutes
        considered_resource_types: list[ResourceType] = ["cpu", "memory"],
        threshold_ratio: float = 0.95,
    ):
        super().__init__()
        self.decide_interval = decide_interval
        self.resource_types = considered_resource_types
        self.threshold = threshold_ratio
        assert decide_interval > 0, "decide_interval should be positive"
        assert (
            considered_resource_types
        ), "resource_types must not be empty, at least one resource type should be specified"
        assert "network" not in considered_resource_types, "network is not supported yet"
        assert 0 < threshold_ratio <= 1, "threshold_ratio should be in (0, 1]"

        self.lock = threading.RLock()
        self._stop_event = threading.Event()
        # Mbps，来源是conductor读取的配置文件
        self.network: dict[str, dict[str, float]] = {}

    @EventHandler("manager", "bandwidth_config_updated", expand=True)
    def on_bandwidth_config_updated(self, _, config: dict[str, dict[str, float]]):
        with self.lock:
            self.network = config

    @override
    def run(self):
        while not self._stop_event.is_set():
            if self._stop_event.wait(self.decide_interval):
                break

            self.logger.info("Start to make offload decision")
            infos: dict[str, HostInfo] = self.call("monitor", "get_all_host_info")
            targets = self.make_offload_decision(infos)
            if targets:
                self.logger.info(
                    f"Offload plan: {', '.join(f'{k} -> {v}' for k, v in targets.items())}"
                )
                # block until offload is done
                self.call_task(
                    "offloading_manager", "offload_roles", {"plan": targets}
                ).result()
            else:
                self.logger.info("No roles to offload")

    @override
    def stop(self):
        self._stop_event.set()

    def _is_resource_tyoe_available(self, resource_type: ResourceType) -> bool:
        return resource_type in self.resource_types

    def make_offload_decision(self, infos: dict[str, HostInfo]):
        roles: list[RoleInstanceID] = []
        for host_name, host_info in infos.items():
            roles += [
                RoleInstanceID(host_name, role_name)
                for role_name in self.find_roles_to_offload(host_info)
            ]

        if len(roles) == 0:
            return None

        self.logger.debug(f"Roles to offload: {roles}")

        role_demands: dict[RoleInstanceID, ResourceVector] = {}
        for role in roles:
            host_name, role_name = role.actor_name, role.instance_name
            host_info = infos[host_name]
            cpu = host_info["role_avg_1m"][role_name]["cpu"]
            memory = host_info["role_avg_1m"][role_name]["memory"]  # byte
            network_rx = host_info["role_avg_1m"][role_name]["bw_rx"]  # Kbps
            network_tx = host_info["role_avg_1m"][role_name]["bw_tx"]  # Kbps
            role_demands[role] = ResourceVector(
                cpu if self._is_resource_tyoe_available("cpu") else 0,
                memory if self._is_resource_tyoe_available("memory") else 0,
                network_rx if self._is_resource_tyoe_available("network") else 0,
                network_tx if self._is_resource_tyoe_available("network") else 0,
            )

        host_caps = {
            host_name: ResourceVector(
                host_info["cpu_max"] if self._is_resource_tyoe_available("cpu") else 999,
                host_info["memory_max"] if self._is_resource_tyoe_available("memory") else 999,  # byte
                host_info["bw_rx_max"] * 1000 if self._is_resource_tyoe_available("network") else 999,  # Mbps -> Kbps
                host_info["bw_tx_max"] * 1000 if self._is_resource_tyoe_available("network") else 999,  # Mbps -> Kbps
            )
            for host_name, host_info in infos.items()
        }

        host_useds = {}
        for host_name, host_info in infos.items():
            cpu = host_info["avg_1m"]["cpu"]
            memory = host_info["avg_1m"]["memory"]  # byte
            network_rx = 0  # Kbps
            network_tx = 0  # Kbps
            for role_name in host_info["roles"]:
                network_rx += host_info["role_avg_1m"][role_name]["bw_rx"]  # Kbps
                network_tx += host_info["role_avg_1m"][role_name]["bw_tx"]  # Kbps

            host_useds[host_name] = ResourceVector(
                cpu if self._is_resource_tyoe_available("cpu") else 0,
                memory if self._is_resource_tyoe_available("memory") else 0,
                network_rx if self._is_resource_tyoe_available("network") else 0,
                network_tx if self._is_resource_tyoe_available("network") else 0,
            )

        role_sizes = {
            role: int(
                infos[role.actor_name]["role_avg_1m"][role.instance_name][
                    "memory"
                ]  # byte
            )
            for role in roles
        }

        self.logger.debug(f"{role_demands=}, {role_sizes=}, {host_caps=}, {host_useds=}")

        targets = self.find_offload_target(
            role_demands, role_sizes, host_caps, host_useds
        )

        return targets

    def find_roles_to_offload(self, host_info: HostInfo) -> list[str]:
        cpu_avg = (
            host_info["avg_1m"]["cpu"] if self._is_resource_tyoe_available("cpu") else 0
        )
        cpu_max = host_info["cpu_max"]
        mem_avg = (
            host_info["avg_1m"]["memory"]
            if self._is_resource_tyoe_available("memory")
            else 0
        )
        mem_total = host_info["memory_max"]

        # TODO bandwidth is not considered here

        if (
            cpu_avg <= cpu_max * self.threshold
            and mem_avg <= mem_total * self.threshold
        ):
            return []

        # 在这里，我们将主机的CPU和内存使用情况视为一个二维向量，其中CPU使用率是X轴，内存使用率是Y轴。
        # 得出的向量的长度是主机的“过载程度”，越长表示主机越过载。
        # 然后，我们将每个角色的CPU和内存使用情况视为一个二维向量
        # 并将其投影到超出向量上。
        # 优先投影长度最长的角色，直到主机的“过载程度”降低到95%以下。

        cpu_excess = max(cpu_avg - cpu_max * self.threshold, 0)
        mem_excess = max(mem_avg - mem_total * self.threshold, 0)
        excess_length = (cpu_excess**2 + mem_excess**2) ** 0.5

        self.logger.debug(
            f"Host is overloaded: {cpu_excess=}, {mem_excess=}, {excess_length=} "
            f"({cpu_avg=}, {cpu_max=}, {mem_avg=}, {mem_total=}) "
            f"({cpu_max=}, {mem_total=})"
        )

        roles = []

        for role_name in host_info["roles"]:
            role_cpu_avg = host_info["role_avg_1m"][role_name]["cpu"]
            role_mem_avg = host_info["role_avg_1m"][role_name]["memory"]

            dotted = role_cpu_avg * cpu_excess + role_mem_avg * mem_excess
            project_lenth = dotted / excess_length

            roles.append((role_name, project_lenth, role_cpu_avg, role_mem_avg))
            self.logger.debug(
                f"Role {role_name}: {project_lenth=}, {role_cpu_avg=}, {role_mem_avg=}"
            )

        roles.sort(key=lambda x: x[1], reverse=True)
        self.logger.debug(f"Roles to offload: {roles}")

        to_offload = []
        while len(roles) > 0 and (cpu_excess > 0 or mem_excess > 0):
            role_name, _, role_cpu_avg, role_mem_avg = roles.pop(0)
            to_offload.append(role_name)
            cpu_excess -= role_cpu_avg
            mem_excess -= role_mem_avg
            self.logger.debug(
                f"Offload {role_name}: {cpu_excess=}, {mem_excess=}, {len(roles)=}"
            )

        return to_offload

    def find_offload_target(
        self,
        role_demands: dict[RoleInstanceID, ResourceVector],
        role_sizes: dict[RoleInstanceID, int],
        host_caps: dict[str, ResourceVector],
        host_useds: dict[str, ResourceVector],
    ) -> dict[RoleInstanceID, str]:
        roles = list(role_demands.keys())
        hosts_waiting_for_offload = [r.actor_name for r in roles]
        hosts = list(host_caps.keys())
        hosts = [h for h in hosts if h not in hosts_waiting_for_offload]

        self.logger.debug(
            f"{len(roles)} roles waiting for offload, {len(hosts)} hosts available"
        )

        role_demands_mat = np.array(
            [list(role_demands[role]) for role in roles], dtype=np.float64
        )
        host_caps_mat = np.array(
            [
                list(
                    host_caps[host]._replace(
                        cpu=host_caps[host].cpu * self.threshold,
                        memory=host_caps[host].memory * self.threshold,
                    )
                )
                for host in hosts
            ],
            dtype=np.float64,
        )
        host_useds_mat = np.array(
            [list(host_useds[host]) for host in hosts], dtype=np.float64
        )
        host_availables_mat = host_caps_mat - host_useds_mat

        trans_mat = np.zeros((len(roles), len(hosts)), dtype=np.float64)
        if not self.network:
            # 没有网络配置，假设所有角色都可以直接迁移到任何主机，且带宽都相等
            for i in range(len(roles)):
                size = role_sizes[roles[i]]
                for j in range(len(hosts)):
                    # 随便指定一个带宽，这里假设是10MB/s
                    trans_mat[i][j] = size / (10 * 1024**2)
        else:
            for i in range(len(roles)):
                size = role_sizes[roles[i]]
                src = roles[i].actor_name
                for j in range(len(hosts)):
                    dst = hosts[j]
                    if src == dst:
                        trans_mat[i][j] = float("inf")
                        continue
                    t = float("inf")
                    try:
                        if self.network[src][dst] == -1:
                            # 未指定带宽，使用双方的接入网络的协商速率的最小值
                            bw = (
                                min(
                                    host_caps[src].network_tx, host_caps[dst].network_rx
                                )
                                * 1000
                            )  # Kbps -> bps
                            t = size / (bw / 8)  # 把带宽转换成字节每秒
                        elif self.network[src][dst] > 0:
                            # 指定了带宽，且带宽大于0，使用指定的带宽
                            bw = self.network[src][dst] * 1000 * 1000  # Mbps -> bps
                            t = size / (bw / 8)  # 把带宽转换成字节每秒
                    except KeyError:
                        pass
                    trans_mat[i][j] = t

        role_src_mat = np.zeros(len(roles), dtype=np.int32)
        for i in range(len(roles)):
            role_src_mat[i] = len(hosts) + i

        aco = AntColonyOptimizer(
            role_demands_mat, host_availables_mat, trans_mat, role_src_mat
        )

        if len(hosts) * len(roles) < 30000:  # magic
            self.logger.debug("Use serial ACO")
            solution, cost = aco.ant_colony_optimization()
        else:
            self.logger.debug("Use parallel ACO")
            solution, cost = aco.ant_colony_optimization_parallel()

        if solution is None:
            raise RuntimeError("Cannot find a solution")

        result: dict[RoleInstanceID, str] = {}
        for i in range(solution.shape[0]):
            result[roles[i]] = hosts[solution[i]]

        return result

    def estimate_plan_time_cost(
        self,
        plan: dict[RoleInstanceID, str],
        role_sizes: dict[RoleInstanceID, int],
    ) -> float:
        link_loads = {}
        for role, dst in plan.items():
            if (role.actor_name, dst) not in link_loads:
                link_loads[(role.actor_name, dst)] = 0
            link_loads[(role.actor_name, dst)] += role_sizes[role]

        link_trans_time = {}
        for (src, dst), load in link_loads.items():
            bw = self.network[src][dst]
            time = load / bw
            link_trans_time[(src, dst)] = time

        return max(link_trans_time.values())
