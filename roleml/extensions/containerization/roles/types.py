


from typing_extensions import TypedDict

from roleml.extensions.containerization.controller.roles.prober.base import HostStatsRecord, RoleStatsRecord


class HostStatsRecordWithDelta(HostStatsRecord):
    delta_cpu_percent: float
    delta_memory_usage: int


class RoleStatsRecordWithDelta(RoleStatsRecord):
    delta_cpu_percent: float
    delta_memory_usage: int
    # delta_net_rx: int
    # delta_net_tx: int


class AvgStats(TypedDict):
    cpu: float
    memory: float # bytes
    bw_rx: float # Kbps (仅Role才用了这个)
    bw_tx: float # Kbps (仅Role才用了这个)


class HostInfo(TypedDict):
    cpu_max: float # 核心数*100%
    memory_max: float # bytes
    bw_rx_max: float # Mbps
    bw_tx_max: float # Mbps

    avg_1m: AvgStats
    avg_5m: AvgStats
    avg_15m: AvgStats

    roles: list[str]
    role_avg_1m: dict[str, AvgStats]
    role_avg_5m: dict[str, AvgStats]
    role_avg_15m: dict[str, AvgStats]
