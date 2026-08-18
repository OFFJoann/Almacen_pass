from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class UserInfo(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    mfa_enabled: bool
    security_score: float
    date_joined: Optional[datetime] = None
    last_login: Optional[datetime] = None
    created_at: datetime
    groups: List[str] = []


class UserRisk(BaseModel):
    user_id: str
    email: str
    total_entries: int
    weak_passwords_count: int
    compromised_count: int
    has_duplicates: bool
    avg_entropy: float
    total_risk_score: float
    robustness_pct: float


class UserDetail(UserInfo):
    total_entries: int = 0
    weak_passwords_count: int = 0
    compromised_count: int = 0
    has_duplicates: bool = False
    avg_entropy: float = 0.0
    total_risk_score: float = 0.0
    robustness_pct: float = 0.0


class GroupInfo(BaseModel):
    id: str
    name: str
    description: str = ''
    min_password_length: int
    trash_retention_days: int
    session_days: int
    allow_export: bool
    member_count: int = 0


class Overview(BaseModel):
    generated_at: datetime
    scope: str
    total_users: int
    active_users: int
    blocked_users: int
    total_passwords: int
    total_vaults: int
    total_secrets: int
    total_shares: int
    total_groups: int
    users_with_mfa: int
    mfa_percentage: float
    recent_logins_24h: int
    failed_logins_24h: int
    active_sessions: int
    logins_last_7d: int
    logins_last_30d: int
    total_audit_logs: int
    weak_passwords_count: int
    expired_passwords: int
    security_score: float
    general_risk: float
    general_risk_label: str
    avg_robustness: float
    avg_robustness_label: str
    darkweb_total: int


class DarkwebEntry(BaseModel):
    id: str
    name: str
    owner_email: str
    owner_name: str
    compromised_count: int
    compromised_checked_at: Optional[datetime] = None


class AuditLogEntry(BaseModel):
    id: str
    user_email: str
    action: str
    details: str
    result: str
    created_at: datetime
    ip_address: Optional[str] = None


class LoginAttempt(BaseModel):
    id: str
    user_email: str
    success: bool
    ip_address: Optional[str] = None
    country: Optional[str] = None
    login_at: datetime
    failure_reason: Optional[str] = None


class StorageStats(BaseModel):
    total_passwords: int
    total_vaults: int
    total_secrets: int
    total_shares: int
    total_groups: int


class ObsoleteEntry(BaseModel):
    id: str
    kind: str
    name: str
    owner_email: Optional[str] = None
    obsoleted_at: Optional[datetime] = None


class RiskSummary(BaseModel):
    general_risk: float
    general_risk_label: str
    avg_robustness: float
    avg_robustness_label: str
    users_at_high_risk: int
    users_with_duplicates: int
    users_with_weak: int
