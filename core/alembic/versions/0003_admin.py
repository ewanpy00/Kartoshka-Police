"""admin dashboard: takedown requests, audit log, review reason, graph strength

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

AUDIT_APPEND_ONLY = """
CREATE OR REPLACE FUNCTION audit_log_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER audit_log_no_update BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
"""


def upgrade() -> None:
    op.create_table(
        'takedown_requests',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('domain', sa.String(), nullable=False),
        sa.Column('campaign_id', sa.String(), nullable=True),
        sa.Column('recipient_kind', sa.String(), nullable=False),
        sa.Column('recipient', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('pack_sha256', sa.String(64), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_by', sa.String(), nullable=True),
        sa.Column('offline_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('offline_reason', sa.String(), nullable=True),
        sa.Column('checks_offline', sa.Integer(), server_default='0', nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
    )
    op.create_index('ix_takedown_requests_domain', 'takedown_requests', ['domain'])
    op.create_index('ix_takedown_requests_status', 'takedown_requests', ['status'])

    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('actor', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('target_kind', sa.String(), nullable=False),
        sa.Column('target', sa.String(), nullable=False),
        sa.Column('before', sa.JSON(), nullable=True),
        sa.Column('after', sa.JSON(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])
    op.create_index('ix_audit_log_target', 'audit_log', ['target'])
    op.execute(AUDIT_APPEND_ONLY)

    op.add_column('reviews', sa.Column('reason', sa.String(), nullable=True))
    op.add_column('entities', sa.Column('domain_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('edges', sa.Column('strength', sa.String(), server_default='weak', nullable=False))
    op.add_column('edges', sa.Column('excluded', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('campaigns', sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('domains', sa.Column('gsb_first_hit_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('domains', sa.Column('vt_first_hit_at', sa.DateTime(timezone=True), nullable=True))
    # Existing edges: count domains per entity once; new edges keep it current.
    op.execute(
        "UPDATE entities SET domain_count = sub.n FROM "
        "(SELECT dst_id, count(*) AS n FROM edges GROUP BY dst_id) AS sub WHERE entities.id = sub.dst_id"
    )


def downgrade() -> None:
    op.drop_column('domains', 'vt_first_hit_at')
    op.drop_column('domains', 'gsb_first_hit_at')
    op.drop_column('campaigns', 'last_activity_at')
    op.drop_column('edges', 'excluded')
    op.drop_column('edges', 'strength')
    op.drop_column('entities', 'domain_count')
    op.drop_column('reviews', 'reason')
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log; DROP FUNCTION IF EXISTS audit_log_append_only();")
    op.drop_index('ix_audit_log_target', table_name='audit_log')
    op.drop_index('ix_audit_log_action', table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_index('ix_takedown_requests_status', table_name='takedown_requests')
    op.drop_index('ix_takedown_requests_domain', table_name='takedown_requests')
    op.drop_table('takedown_requests')
