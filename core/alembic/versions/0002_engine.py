"""engine: scoring, deep analysis, evidence chain, graph, reports, hits

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

NOW = sa.text('now()')

APPEND_ONLY = """
CREATE OR REPLACE FUNCTION evidence_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'evidence is append-only';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER evidence_no_update BEFORE UPDATE OR DELETE ON evidence
  FOR EACH ROW EXECUTE FUNCTION evidence_append_only();
"""


def upgrade() -> None:
    with op.batch_alter_table('checks') as t:
        t.add_column(sa.Column('host', sa.String(), nullable=True))
        t.add_column(sa.Column('domain', sa.String(), nullable=True))
        t.add_column(sa.Column('brand_id', sa.String(), nullable=True))
        t.add_column(sa.Column('sources', sa.JSON(), nullable=True))
        t.add_column(sa.Column('features', sa.JSON(), nullable=True))
        t.add_column(sa.Column('chain', sa.JSON(), nullable=True))
        t.add_column(sa.Column('preview', sa.JSON(), nullable=True))
        t.add_column(sa.Column('deep_status', sa.String(), nullable=True))
        t.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), server_default=NOW, nullable=False))
    op.create_index(op.f('ix_checks_host'), 'checks', ['host'])
    op.create_index(op.f('ix_checks_domain'), 'checks', ['domain'])
    op.create_index(op.f('ix_checks_campaign_id'), 'checks', ['campaign_id'])
    op.create_index(op.f('ix_checks_created_at'), 'checks', ['created_at'])

    op.add_column('domains', sa.Column('source', sa.String(), server_default='seed', nullable=False))

    op.add_column('verdicts', sa.Column('reasons', sa.JSON(), nullable=True))

    op.add_column('evidence', sa.Column('seq', sa.BigInteger(), nullable=False))
    op.add_column('evidence', sa.Column('domain', sa.String(), nullable=True))
    op.create_unique_constraint(op.f('uq_evidence_seq'), 'evidence', ['seq'])
    op.create_index(op.f('ix_evidence_domain'), 'evidence', ['domain'])
    op.execute(APPEND_ONLY)

    op.add_column('artifacts', sa.Column('kind', sa.String(), server_default='file', nullable=False))

    op.add_column('entities', sa.Column('first_seen', sa.DateTime(timezone=True), server_default=NOW, nullable=False))

    with op.batch_alter_table('campaigns') as t:
        t.add_column(sa.Column('name', sa.String(), nullable=True))
        t.add_column(sa.Column('domain_count', sa.Integer(), server_default='0', nullable=False))
        t.add_column(sa.Column('confirmed_count', sa.Integer(), server_default='0', nullable=False))
        t.add_column(sa.Column('summary', sa.Text(), nullable=True))
        t.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), server_default=NOW, nullable=False))

    op.create_unique_constraint(op.f('uq_edges_src_id_dst_id'), 'edges', ['src_id', 'dst_id'])

    with op.batch_alter_table('watchlist') as t:
        t.add_column(sa.Column('url', sa.Text(), nullable=True))
        t.add_column(sa.Column('reason', sa.String(), nullable=True))
        t.add_column(sa.Column('brand_id', sa.String(), nullable=True))
        t.add_column(sa.Column('last_status', sa.String(), nullable=True))
        t.add_column(sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True))
        t.add_column(sa.Column('offline_since', sa.DateTime(timezone=True), nullable=True))
        t.add_column(sa.Column('checks_done', sa.Integer(), server_default='0', nullable=False))

    op.add_column('reviews', sa.Column('note', sa.Text(), nullable=True))

    op.create_table('feed_entries',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('domain', sa.String(), nullable=False),
    sa.Column('brand_id', sa.String(), nullable=True),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('first_seen', sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source', 'url')
    )
    op.create_index(op.f('ix_feed_entries_source'), 'feed_entries', ['source'])
    op.create_index(op.f('ix_feed_entries_domain'), 'feed_entries', ['domain'])

    op.create_table('reports',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('check_id', sa.String(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('domain', sa.String(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('push_token', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    sa.ForeignKeyConstraint(['check_id'], ['checks.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_check_id'), 'reports', ['check_id'])
    op.create_index(op.f('ix_reports_domain'), 'reports', ['domain'])

    op.create_table('hits',
    sa.Column('domain', sa.String(), nullable=False),
    sa.Column('channel', sa.String(), nullable=False),
    sa.Column('count', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    sa.PrimaryKeyConstraint('domain', 'channel')
    )

    op.create_table('model_state',
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    op.drop_table('model_state')
    op.drop_table('hits')
    op.drop_index(op.f('ix_reports_domain'), table_name='reports')
    op.drop_index(op.f('ix_reports_check_id'), table_name='reports')
    op.drop_table('reports')
    op.drop_index(op.f('ix_feed_entries_domain'), table_name='feed_entries')
    op.drop_index(op.f('ix_feed_entries_source'), table_name='feed_entries')
    op.drop_table('feed_entries')
    op.drop_column('reviews', 'note')
    for column in ('checks_done', 'offline_since', 'last_checked_at', 'last_status', 'brand_id', 'reason', 'url'):
        op.drop_column('watchlist', column)
    op.drop_constraint(op.f('uq_edges_src_id_dst_id'), 'edges', type_='unique')
    for column in ('updated_at', 'summary', 'confirmed_count', 'domain_count', 'name'):
        op.drop_column('campaigns', column)
    op.drop_column('entities', 'first_seen')
    op.drop_column('artifacts', 'kind')
    op.execute("DROP TRIGGER IF EXISTS evidence_no_update ON evidence; DROP FUNCTION IF EXISTS evidence_append_only();")
    op.drop_index(op.f('ix_evidence_domain'), table_name='evidence')
    op.drop_constraint(op.f('uq_evidence_seq'), 'evidence', type_='unique')
    op.drop_column('evidence', 'domain')
    op.drop_column('evidence', 'seq')
    op.drop_column('verdicts', 'reasons')
    op.drop_column('domains', 'source')
    op.drop_index(op.f('ix_checks_created_at'), table_name='checks')
    op.drop_index(op.f('ix_checks_campaign_id'), table_name='checks')
    op.drop_index(op.f('ix_checks_domain'), table_name='checks')
    op.drop_index(op.f('ix_checks_host'), table_name='checks')
    for column in ('updated_at', 'deep_status', 'preview', 'chain', 'features', 'sources', 'brand_id', 'domain', 'host'):
        op.drop_column('checks', column)
