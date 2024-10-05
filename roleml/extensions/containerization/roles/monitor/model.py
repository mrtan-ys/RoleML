from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Float,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()


class HostStatsModel(Base):
    __tablename__ = "host_stats"
    id = Column(Integer, primary_key=True)
    time = Column(Float)
    cpu_percent = Column(Float)
    cpu_total = Column(Float)
    memory_usage = Column(Integer) # in bytes
    memory_total = Column(Integer) # in bytes
    nic_speed = Column(Integer) # in Mbps
    name = Column(String)
    delta_cpu_percent = Column(Float)
    delta_memory_usage = Column(Integer)


class RoleStatsModel(Base):
    __tablename__ = "role_stats"
    id = Column(Integer, primary_key=True)
    time = Column(Float)
    cpu_percent = Column(Float)
    memory_usage = Column(Integer) # bytes
    net_rx = Column(Integer) # bytes
    net_tx = Column(Integer) # bytes
    bw_rx = Column(Float) # Kbps
    bw_tx = Column(Float) # Kbps
    name = Column(String)
    host = Column(String)
    delta_cpu_percent = Column(Float)
    delta_memory_usage = Column(Integer)
    # delta_net_rx = Column(Integer)
    # delta_net_tx = Column(Integer)


engine = create_engine(
    "sqlite:///:memory:",
    # "sqlite:////home/liwh/roleml.db",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()
