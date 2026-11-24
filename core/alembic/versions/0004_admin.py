"""admin dashboard: takedown requests, audit log, review reason, graph exclusion (delta on 0003)

Drops what the admin-console migration created and the merged models do not have: takedown_packs,
watchlist.gsb_first_hit_at / vt_first_hit_at, reviews.domain (+ index), entities.campaign_id.
First-hit times live on domains.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = '0004'
down_revision = '0003'
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
    # takedown: 0002's pack/request pair becomes one request table.
    op.drop_index(op.f('ix_takedown_requests_pack_id'), table_name='takedown_requests')
    op.drop_table('takedown_requests')
    op.drop_table('takedown_packs')
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

    # audit_log: rebuilt with target_kind and indexes.
    op.drop_table('audit_log')
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

    op.alter_column('reviews', 'reason', existing_type=sa.Text(), type_=sa.String(), existing_nullable=True)
    op.drop_index(op.f('ix_reviews_domain'), table_name='reviews')
    op.drop_column('reviews', 'domain')

    op.drop_constraint('fk_entities_campaign_id', 'entities', type_='foreignkey')
    op.drop_column('entities', 'campaign_id')

    op.add_column('edges', sa.Column('excluded', sa.Boolean(), server_default=sa.false(), nullable=False))

    op.add_column('domains', sa.Column('gsb_first_hit_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('domains', sa.Column('vt_first_hit_at', sa.DateTime(timezone=True), nullable=True))
    op.drop_column('watchlist', 'gsb_first_hit_at')
    op.drop_column('watchlist', 'vt_first_hit_at')

    # Existing edges: count domains per entity once; new edges keep it current.
    op.execute(
        "UPDATE entities SET domain_count = sub.n FROM "
        "(SELECT dst_id, count(*) AS n FROM edges GROUP BY dst_id) AS sub WHERE entities.id = sub.dst_id"
    )

    # Last, after every data-changing statement.
    op.execute(AUDIT_APPEND_ONLY)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log; DROP FUNCTION IF EXISTS audit_log_append_only();")
    op.add_column('watchlist', sa.Column('vt_first_hit_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('watchlist', sa.Column('gsb_first_hit_at', sa.DateTime(timezone=True), nullable=True))
    op.drop_column('domains', 'vt_first_hit_at')
    op.drop_column('domains', 'gsb_first_hit_at')
    op.drop_column('edges', 'excluded')
    op.add_column('entities', sa.Column('campaign_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_entities_campaign_id', 'entities', 'campaigns', ['campaign_id'], ['id'])
    op.add_column('reviews', sa.Column('domain', sa.String(), nullable=True))
    op.create_index(op.f('ix_reviews_domain'), 'reviews', ['domain'], unique=False)
    op.alter_column('reviews', 'reason', existing_type=sa.String(), type_=sa.Text(), existing_nullable=True)
    op.drop_index('ix_audit_log_target', table_name='audit_log')
    op.drop_index('ix_audit_log_action', table_name='audit_log')
    op.drop_table('audit_log')
    op.create_table('audit_log',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('target', sa.String(), nullable=False),
    sa.Column('before', sa.JSON(), nullable=True),
    sa.Column('after', sa.JSON(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_index('ix_takedown_requests_status', table_name='takedown_requests')
    op.drop_index('ix_takedown_requests_domain', table_name='takedown_requests')
    op.drop_table('takedown_requests')
    op.create_table('takedown_packs',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('recipient_kind', sa.String(), nullable=False),
    sa.Column('recipient', sa.String(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('zip', sa.LargeBinary(), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('generated_by', sa.String(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sent_by', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('takedown_requests',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('pack_id', sa.String(), nullable=False),
    sa.Column('domain', sa.String(), nullable=False),
    sa.Column('evidence_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ),
    sa.ForeignKeyConstraint(['pack_id'], ['takedown_packs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_takedown_requests_pack_id'), 'takedown_requests', ['pack_id'], unique=False)
