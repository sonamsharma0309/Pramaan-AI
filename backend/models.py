"""SQLAlchemy 2.0 table definitions (Core). Alembic's initial migration builds from this metadata.

Timestamps are stored as ISO-like strings so the same code runs on SQLite and PostgreSQL.
"""
import sqlalchemy as sa

metadata = sa.MetaData()
NOW = sa.text("CURRENT_TIMESTAMP")


def _id():
    return sa.Column("id", sa.Integer, primary_key=True, autoincrement=True)


def _ts(name="created_at"):
    return sa.Column(name, sa.String(40), server_default=NOW)


orgs = sa.Table("orgs", metadata, _id(), sa.Column("name", sa.String(160), nullable=False), sa.Column("invite_code", sa.String(24), unique=True), _ts())

users = sa.Table(
    "users", metadata, _id(),
    sa.Column("name", sa.String(120), nullable=False), sa.Column("email", sa.String(254), nullable=False, unique=True),
    sa.Column("password_hash", sa.String(200)), sa.Column("org", sa.String(160), server_default=""),
    sa.Column("org_id", sa.Integer, sa.ForeignKey("orgs.id", ondelete="SET NULL")),
    sa.Column("role", sa.String(20), server_default="patient"), sa.Column("auth_provider", sa.String(20), server_default="password"),
    sa.Column("failed_attempts", sa.Integer, server_default="0"), sa.Column("locked_until", sa.Float, server_default="0"),
    sa.Column("email_verified", sa.Integer, server_default="1"),
    sa.Column("totp_secret", sa.String(64)), sa.Column("totp_enabled", sa.Integer, server_default="0"),
    sa.Column("theme", sa.String(10), server_default="light"),
    _ts(), sa.Column("last_login", sa.String(40)),
)
revoked_tokens = sa.Table("revoked_tokens", metadata, sa.Column("jti", sa.String(64), primary_key=True), sa.Column("exp", sa.Float))
refresh_tokens = sa.Table(
    "refresh_tokens", metadata, _id(), sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
    sa.Column("family", sa.String(40), index=True), sa.Column("token_hash", sa.String(64), unique=True),
    sa.Column("expires", sa.Float), sa.Column("revoked", sa.Integer, server_default="0"), sa.Column("replaced_by", sa.String(64)), _ts(),
)
claims = sa.Table(
    "claims", metadata, _id(), sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("claim_no", sa.String(60)), sa.Column("patient_name", sa.String(120)), sa.Column("payer", sa.String(120)),
    sa.Column("procedure_code", sa.String(20)), sa.Column("procedure_desc", sa.String(200)), sa.Column("diagnosis", sa.String(200)),
    sa.Column("billed_amount", sa.Float, server_default="0"), sa.Column("denied_amount", sa.Float, server_default="0"),
    sa.Column("denial_code", sa.String(10)), sa.Column("denial_reason", sa.String(600)), sa.Column("remark_code", sa.String(20)),
    sa.Column("denial_category", sa.String(40)), sa.Column("group_code", sa.String(4)),
    sa.Column("service_date", sa.String(20)), sa.Column("denied_on", sa.String(20)), sa.Column("status", sa.String(20), server_default="denied"),
    sa.Column("ehr_notes", sa.Text, server_default=""), sa.Column("source", sa.String(20), server_default="manual"), _ts(),
)
policies = sa.Table(
    "policies", metadata, _id(), sa.Column("user_id", sa.Integer), sa.Column("org_id", sa.Integer, sa.ForeignKey("orgs.id", ondelete="CASCADE"), index=True),
    sa.Column("payer", sa.String(120), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("content", sa.Text, nullable=False), _ts(),
)
appeals = sa.Table(
    "appeals", metadata, _id(), sa.Column("claim_id", sa.Integer, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
    sa.Column("user_id", sa.Integer, nullable=False, index=True), sa.Column("letter", sa.Text), sa.Column("analysis", sa.Text),
    sa.Column("win_probability", sa.Float), sa.Column("model_kind", sa.String(20), server_default="synthetic"),
    sa.Column("engine", sa.String(60)), sa.Column("gen_seconds", sa.Float), sa.Column("status", sa.String(20), server_default="drafted"),
    sa.Column("outcome", sa.String(20)), sa.Column("recovered_amount", sa.Float, server_default="0"), _ts(), _ts("updated_at"),
)
claim_events = sa.Table("claim_events", metadata, _id(), sa.Column("claim_id", sa.Integer, sa.ForeignKey("claims.id", ondelete="CASCADE"), index=True),
                        sa.Column("event", sa.String(40)), sa.Column("detail", sa.String(300)), _ts())
audit_log = sa.Table("audit_log", metadata, _id(), sa.Column("user_id", sa.Integer), sa.Column("action", sa.String(60), index=True),
                     sa.Column("detail", sa.String(400)), sa.Column("ip", sa.String(60)), sa.Column("request_id", sa.String(20)), _ts())
notifications = sa.Table("notifications", metadata, _id(), sa.Column("user_id", sa.Integer, index=True), sa.Column("kind", sa.String(30)),
                         sa.Column("ref", sa.String(60)), sa.Column("title", sa.String(160)), sa.Column("body", sa.String(400)),
                         sa.Column("link", sa.String(120)), sa.Column("is_read", sa.Integer, server_default="0"), _ts())
contact_messages = sa.Table("contact_messages", metadata, _id(), sa.Column("name", sa.String(120)), sa.Column("email", sa.String(254)),
                            sa.Column("kind", sa.String(30)), sa.Column("message", sa.Text), sa.Column("emailed", sa.Integer, server_default="0"), _ts())
icd_cache = sa.Table("icd_cache", metadata, sa.Column("q", sa.String(120), primary_key=True), sa.Column("payload", sa.Text), sa.Column("ts", sa.Float))
