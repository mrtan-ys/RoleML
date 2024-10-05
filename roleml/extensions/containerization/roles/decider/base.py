from threading import RLock
import threading
import time
from typing import NamedTuple
from typing_extensions import override

import numpy as np
from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import EventHandler, Service
from roleml.extensions.containerization.roles.decider.aco import AntColonyOptimizer
from roleml.extensions.containerization.roles.types import HostInfo
from roleml.shared.interfaces import Runnable


class ResourceVector(NamedTuple):
    cpu: float
    memory: float  # byte
    network_rx: float  # Kbps
    network_tx: float  # Kbps


class OffloadingDecider(Role, Runnable):

    def __init__(self):
        super().__init__()
        self.lock = RLock()
        self.network: dict[str, dict[str, float]] = (
            {}
        )  # Mbps，来源是conductor读取的配置文件

        self._stop_event = threading.Event()

    @EventHandler("manager", "bandwidth_config_updated", expand=True)
    def on_bandwidth_config_updated(self, _, config: dict[str, dict[str, float]]):
        with self.lock:
            self.network = config

    @override
    def run(self):
        while not self._stop_event.is_set():
            INTERVAL = 5 * 60  # TODO make this configurable
            if self._stop_event.wait(INTERVAL):
                break

            infos: dict[str, HostInfo] = self.call("monitor", "get_all_host_info")
            self.network = self.call("manager", "get_bandwidth_config")
            # with open("host_info.json", "w") as f:
            #     json.dump(infos, f, indent=2)
            targets = self.make_offload_decision(infos)
            if targets:
                # the service doesn't block
                self.call("offload_manager", "offload_roles", {"plan": targets})

    @override
    def stop(self):
        self._stop_event.set()

    def make_offload_decision(self, infos: dict[str, HostInfo]):
        roles: list[RoleInstanceID] = []
        for host_name, host_info in infos.items():
            roles += [
                RoleInstanceID(host_name, role_name)
                for role_name in self.find_roles_to_offload(host_info)
            ]

        if len(roles) == 0:
            return None

        role_demands: dict[RoleInstanceID, ResourceVector] = {}
        for role in roles:
            host_name, role_name = role.actor_name, role.instance_name
            host_info = infos[host_name]
            cpu = host_info["role_avg_1m"][role_name]["cpu"]
            memory = host_info["role_avg_1m"][role_name]["memory"]  # byte
            network_rx = host_info["role_avg_1m"][role_name]["bw_rx"]  # Kbps
            network_tx = host_info["role_avg_1m"][role_name]["bw_tx"]  # Kbps
            role_demands[role] = ResourceVector(cpu, memory, network_rx, network_tx)

        host_caps = {
            host_name: ResourceVector(
                host_info["cpu_max"],
                host_info["memory_max"],  # byte
                host_info["bw_rx_max"] * 1000,  # Mbps -> Kbps
                host_info["bw_tx_max"] * 1000,  # Mbps -> Kbps
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

            host_useds[host_name] = ResourceVector(cpu, memory, network_rx, network_tx)

        role_sizes = {
            role: int(
                infos[role.actor_name]["role_avg_1m"][role.instance_name][
                    "memory"
                ]  # byte
            )
            for role in roles
        }

        targets = self.find_offload_target(
            role_demands, role_sizes, host_caps, host_useds
        )
        time_estimates = self.estimate_plan_time_cost(targets, role_sizes)
        self.logger.debug(
            f"蚁群Offload targets: {targets} estimated time: {time_estimates}"
        )

        return targets

    def find_roles_to_offload(self, host_info: HostInfo) -> list[str]:
        cpu_avg = host_info["avg_1m"]["cpu"]
        cpu_max = host_info["cpu_max"]
        mem_avg = host_info["avg_1m"]["memory"]
        mem_total = host_info["memory_max"]

        if cpu_avg <= cpu_max * 0.95 and mem_avg <= mem_total * 0.95:
            return []

        # 在这里，我们将主机的CPU和内存使用情况视为一个二维向量，其中CPU使用率是X轴，内存使用率是Y轴。
        # 得出的向量的长度是主机的“过载程度”，越长表示主机越过载。
        # 然后，我们将每个角色的CPU和内存使用情况视为一个二维向量
        # 并将其投影到超出向量上。
        # 优先投影长度最长的角色，直到主机的“过载程度”降低到95%以下。

        cpu_excess = max(cpu_avg - cpu_max * 0.95, 0)
        mem_excess = max(mem_avg - mem_total * 0.95, 0)
        excess_length = (cpu_excess**2 + mem_excess**2) ** 0.5

        roles = []

        for role_name in host_info["roles"]:
            role_cpu_avg = host_info["role_avg_1m"][role_name]["cpu"]
            role_mem_avg = host_info["role_avg_1m"][role_name]["memory"]

            dotted = role_cpu_avg * cpu_excess + role_mem_avg * mem_excess
            project_lenth = dotted / excess_length

            roles.append((role_name, project_lenth, role_cpu_avg, role_mem_avg))

        roles.sort(key=lambda x: x[1], reverse=True)

        to_offload = []
        while len(roles) > 0 and cpu_excess > 0 or mem_excess > 0:
            role_name, _, role_cpu_avg, role_mem_avg = roles.pop()
            to_offload.append(role_name)
            cpu_excess -= role_cpu_avg
            mem_excess -= role_mem_avg

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

        self.logger.debug(f"{len(roles)} roles, {len(hosts)} hosts")

        role_demands_mat = np.array(
            [list(role_demands[role]) for role in roles], dtype=np.float64
        )
        host_caps_mat = np.array(
            [
                list(
                    host_caps[host]._replace(
                        cpu=95, memory=host_caps[host].memory * 0.95
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
        for i in range(len(roles)):
            size = role_sizes[roles[i]]
            src = roles[i].actor_name
            for j in range(len(hosts)):
                dst = hosts[j]
                t = float("inf")
                if src != dst:
                    if src in self.network and dst in self.network[src]:
                        if (
                            self.network[src][dst] == -1
                        ):  # 未指定带宽，使用双方的接入网络的协商速率的最小值
                            bw = (
                                min(
                                    host_caps[src].network_tx, host_caps[dst].network_rx
                                )
                                * 1000
                            )  # Kbps -> bps
                            t = size / (bw / 8)  # 把带宽转换成字节每秒
                        elif (
                            self.network[src][dst] > 0
                        ):  # 指定了带宽，且带宽大于0，使用指定的带宽
                            bw = self.network[src][dst] * 1000 * 1000  # Mbps -> bps
                            t = size / (bw / 8)  # 把带宽转换成字节每秒
                trans_mat[i][j] = t

        role_src_mat = np.zeros(len(roles), dtype=np.int32)
        for i in range(len(roles)):
            role_src_mat[i] = len(hosts) + i

        aco = AntColonyOptimizer(
            role_demands_mat, host_availables_mat, trans_mat, role_src_mat
        )

        if len(hosts) * len(roles) < 30000:
            solution, cost = aco.ant_colony_optimization()
        else:
            self.logger.debug("Use parallel ACO")
            solution, cost = aco.ant_colony_optimization_parallel()

        # logger.debug("Use parallel ACO")
        # solution, cost = aco.ant_colony_optimization_parallel()
        # aco = AntColonyOptimizer(
        #     role_demands_mat, host_availables_mat, trans_mat, role_src_mat
        # )
        # solution, cost = aco.ant_colony_optimization()

        if solution is None:
            # aco = AntColonyOptimizer(
            #     role_demands_mat, host_availables_mat, trans_mat, role_src_mat
            # )
            # solution, cost = aco.ant_colony_optimization()
            raise Exception("Cannot find a solution")

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
