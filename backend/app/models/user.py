from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    # 存储配置
    storage_type = Column(String, default="local")
    storage_config = Column(String)       # JSON字符串存FTP/S3配置
    storage_used_bytes = Column(BigInteger, default=0)

    # 报表设置
    report_email = Column(String)
    weekly_report = Column(Boolean, default=False)
    monthly_report = Column(Boolean, default=False)