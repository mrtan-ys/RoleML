from datetime import datetime
import itertools
from threading import RLock

from roleml.core.role.base import Role
from roleml.core.role.channels import Service
from roleml.extensions.containerization.controller.roles.prober.base import HostStatsRecord, RoleStatsRecord
from roleml.extensions.containerization.roles.types import AvgStats, HostInfo, HostStatsRecordWithDelta, RoleStatsRecordWithDelta
from roleml.extensions.containerization.roles.monitor.model import (
    session,
    HostStatsModel,
    RoleStatsModel,
)


class ResourceMonitor(Role):

    def __init__(self):
        super().__init__()
        self.mutex = RLock()

    @Service("update_stats", expand=True)
    def update_stats(
        self,
        source: str,
        role_stats: list[RoleStatsRecord],
        host_stats: list[HostStatsRecord],
    ):
        with self.mutex:
            host_latest = (
                session.query(HostStatsModel)
                .order_by(HostStatsModel.time.desc())
                .first()
            )
            if host_latest is None:
                host_latest = HostStatsModel(
                    time=0,
                    cpu_percent=0,
                    cpu_total=0,
                    memory_usage=0,
                    memory_total=0,
                    name="",
                    delta_cpu_percent=0,
                    delta_memory_usage=0,
                )

            host_stats.sort(key=lambda x: x["time"])
            new_host_stats = []
            for host_stat in host_stats:
                if host_stat["time"] <= host_latest.time:
                    continue
                model = HostStatsModel(
                    time=host_stat["time"],
                    cpu_percent=host_stat["cpu_percent"],
                    cpu_total=host_stat["cpu_total"],
                    memory_usage=host_stat["memory_usage"],  # in bytes
                    memory_total=host_stat["memory_total"],  # in bytes
                    nic_speed=host_stat["nic_speed"],  # in Mbps
                    name=host_stat["name"],
                    delta_cpu_percent=host_stat["cpu_percent"]
                    - host_latest.cpu_percent,
                    delta_memory_usage=host_stat["memory_usage"]
                    - host_latest.memory_usage,
                )
                new_host_stats.append(model)
                host_latest = model
            session.add_all(new_host_stats)

            grouped_role_stats = itertools.groupby(
                role_stats, lambda x: (x["name"], x["host"])
            )
            for (name, host), group in grouped_role_stats:
                role_latest = (
                    session.query(RoleStatsModel)
                    .filter(RoleStatsModel.name == name)
                    .filter(RoleStatsModel.host == host)
                    .order_by(RoleStatsModel.time.desc())
                    .first()
                )
                if role_latest is None:
                    role_latest = RoleStatsModel(
                        time=0,
                        cpu_percent=0,
                        memory_usage=0,
                        net_rx=0,
                        net_tx=0,
                        bw_rx=0,
                        bw_tx=0,
                        name="",
                        host="",
                        delta_cpu_percent=0,
                        delta_memory_usage=0,
                        # delta_net_rx=0,
                        # delta_net_tx=0,
                    )

                group = list(group)
                group.sort(key=lambda x: x["time"])
                new_role_stats = []
                for role_stat in group:
                    if role_stat["time"] <= role_latest.time:
                        continue
                    model = RoleStatsModel(
                        time=role_stat["time"],
                        cpu_percent=role_stat["cpu_percent"],
                        memory_usage=role_stat["memory_usage"],  # in bytes
                        net_rx=role_stat["net_rx"],  # in bytes
                        net_tx=role_stat["net_tx"],  # in bytes
                        bw_rx=role_stat["bw_rx"],  # in Kbps
                        bw_tx=role_stat["bw_tx"],  # in Kbps
                        name=role_stat["name"],
                        host=role_stat["host"],
                        delta_cpu_percent=role_stat["cpu_percent"]
                        - role_latest.cpu_percent,
                        delta_memory_usage=role_stat["memory_usage"]
                        - role_latest.memory_usage,
                        # delta_net_rx=role_stat["net_rx"] - role_latest.net_rx,
                        # delta_net_tx=role_stat["net_tx"] - role_latest.net_tx,
                    )
                    new_role_stats.append(model)
                    role_latest = model
                session.add_all(new_role_stats)

            session.commit()

    @Service("get_actor_host_stats", expand=True)
    def get_actor_host_stats(self, _, name: str) -> list[HostStatsRecordWithDelta]:
        with self.mutex:
            q = (
                session.query(HostStatsModel)
                .filter(HostStatsModel.name == name)
                .order_by(HostStatsModel.time.desc())
                .all()
            )
            return [host_stats_model_to_record(x) for x in q]

    @Service("get_all_host_latest_stats", expand=True)
    def get_all_host_latest_stats(self, _) -> dict[str, HostStatsRecordWithDelta]:
        with self.mutex:
            q = (
                session.query(HostStatsModel)
                .group_by(HostStatsModel.name)
                .order_by(HostStatsModel.time.desc())
                .all()
            )
            return {str(x.name): host_stats_model_to_record(x) for x in q}

    @Service("get_all_host_info", expand=True)
    def get_all_host_info(self, _) -> dict[str, HostInfo]:
        ret: dict[str, HostInfo] = {}
        with self.mutex:
            host_names = session.query(HostStatsModel.name).distinct().all()
            host_names = [str(x[0]) for x in host_names]

            for host_name in host_names:

                def get_xmin_avg(xmin: int) -> AvgStats:
                    avg_stats: AvgStats = AvgStats(cpu=0, memory=0, bw_rx=0, bw_tx=0)
                    recent = (
                        session.query(HostStatsModel)
                        .filter(HostStatsModel.name == host_name)
                        .filter(
                            HostStatsModel.time > datetime.now().timestamp() - xmin * 60
                        )
                        .order_by(HostStatsModel.time.desc())
                        .all()
                    )

                    if len(recent) == 0:
                        return avg_stats

                    avg_stats["cpu"] = sum([x.cpu_percent for x in recent]) / len(
                        recent
                    )
                    avg_stats["memory"] = sum([x.memory_usage for x in recent]) / len(
                        recent
                    )  # type: ignore

                    return avg_stats

                host_avg_1min = get_xmin_avg(1)
                host_avg_5min = get_xmin_avg(5)
                host_avg_15min = get_xmin_avg(15)

                host_lts = (
                    session.query(HostStatsModel)
                    .filter(HostStatsModel.name == host_name)
                    .order_by(HostStatsModel.time.desc())
                    .first()
                )
                host_cpu_max: float = host_lts.cpu_total
                host_memory_max: float = host_lts.memory_total
                host_bw_rx_max: float = host_lts.nic_speed
                host_bw_tx_max: float = host_lts.nic_speed

                role_avg_1min: dict[str, AvgStats] = {}
                role_avg_5min: dict[str, AvgStats] = {}
                role_avg_15min: dict[str, AvgStats] = {}

                roles = (
                    session.query(RoleStatsModel.name)
                    .filter(RoleStatsModel.host == host_name)
                    .distinct()
                    .all()
                )
                roles = [str(x[0]) for x in roles]
                for role in roles:

                    def get_xmin_avg(xmin: int) -> AvgStats:
                        avg_stats: AvgStats = AvgStats(
                            cpu=0, memory=0, bw_rx=0, bw_tx=0
                        )
                        recent = (
                            session.query(RoleStatsModel)
                            .filter(RoleStatsModel.name == role)
                            .filter(RoleStatsModel.host == host_name)
                            .filter(
                                RoleStatsModel.time
                                > datetime.now().timestamp() - xmin * 60
                            )
                            .order_by(RoleStatsModel.time.desc())
                            .all()
                        )

                        if len(recent) == 0:
                            return avg_stats

                        avg_stats["cpu"] = sum([x.cpu_percent for x in recent]) / len(recent)  # type: ignore
                        avg_stats["memory"] = sum(
                            [x.memory_usage for x in recent]
                        ) / len(
                            recent
                        )  # type: ignore
                        avg_stats["bw_rx"] = sum([x.bw_rx for x in recent]) / len(recent)  # type: ignore
                        avg_stats["bw_tx"] = sum([x.bw_tx for x in recent]) / len(recent)  # type: ignore

                        return avg_stats

                    role_avg_1min[role] = get_xmin_avg(1)
                    role_avg_5min[role] = get_xmin_avg(5)
                    role_avg_15min[role] = get_xmin_avg(15)

                ret[host_name] = HostInfo(
                    avg_1m=host_avg_1min,
                    avg_5m=host_avg_5min,
                    avg_15m=host_avg_15min,
                    cpu_max=host_cpu_max,
                    memory_max=host_memory_max,
                    bw_rx_max=host_bw_rx_max,
                    bw_tx_max=host_bw_tx_max,
                    role_avg_1m=role_avg_1min,
                    role_avg_5m=role_avg_5min,
                    role_avg_15m=role_avg_15min,
                    roles=roles,
                )

        return ret

    @Service("get_actor_role_stats", expand=True)
    def get_actor_role_stats(self, _, name: str, role: str) -> list[RoleStatsRecordWithDelta]:
        with self.mutex:
            q = (
                session.query(RoleStatsModel)
                .filter(RoleStatsModel.name == name)
                .filter(RoleStatsModel.role == role)
                .order_by(RoleStatsModel.time.desc())
                .all()
            )
            return [role_stats_model_to_record(x) for x in q]

    @Service("get_actor_role_names", expand=True)
    def get_actor_role_names(self, _, name: str) -> list[str]:
        with self.mutex:
            q = (
                session.query(RoleStatsModel.role)
                .filter(RoleStatsModel.name == name)
                .distinct()
                .all()
            )
            return [str(x[0]) for x in q]

    @Service("get_actor_names", expand=True)
    def get_actor_names(self, _) -> list[str]:
        with self.mutex:
            q = session.query(HostStatsModel.name).distinct().all()
            return [str(x[0]) for x in q]


def host_stats_model_to_record(model: HostStatsModel) -> HostStatsRecordWithDelta:
    return {
        "time": model.time,
        "cpu_percent": model.cpu_percent,
        "cpu_total": model.cpu_total,
        "memory_usage": model.memory_usage,
        "memory_total": model.memory_total,
        "name": model.name,
        "nic_speed": model.nic_speed,
        "delta_cpu_percent": model.delta_cpu_percent,
        "delta_memory_usage": model.delta_memory_usage,
    }  # type: ignore


def role_stats_model_to_record(model: RoleStatsModel) -> RoleStatsRecordWithDelta:
    return {
        "time": model.time,
        "cpu_percent": model.cpu_percent,
        "memory_usage": model.memory_usage,
        "net_rx": model.net_rx,
        "net_tx": model.net_tx,
        "bw_rx": model.bw_rx,
        "bw_tx": model.bw_tx,
        "name": model.name,
        "host": model.host,
        "delta_cpu_percent": model.delta_cpu_percent,
        "delta_memory_usage": model.delta_memory_usage,
        # "delta_net_rx": model.delta_net_rx,
        # "delta_net_tx": model.delta_net_tx,
    }  # type: ignore
