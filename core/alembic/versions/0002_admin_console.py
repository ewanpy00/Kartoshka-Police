"""admin console: reports, audit log, takedowns, campaign and watchlist columns

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def timestamp(name: str, **kwargs) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kwargs)


def upgrade() -> None:
    op.add_column('checks', sa.Column('domain', sa.String(), nullable=True))
    op.create_index(op.f('ix_checks_domain'), 'checks', ['domain'], unique=False)

    op.add_column('evidence', sa.Column('seq', sa.BigInteger(), sa.Identity(), nullable=False))
    op.execute(
        "UPDATE evidence SET seq = ordered.n FROM "
        "(SELECT id, row_number() OVER (ORDER BY created_at, id) AS n FROM evidence) AS ordered "
        "WHERE evidence.id = ordered.id"
    )
    next_seq = op.get_bind().execute(sa.text("SELECT coalesce(max(seq), 0) + 1 FROM evidence")).scalar_one()
    op.execute(f"ALTER TABLE evidence ALTER COLUMN seq RESTART WITH {next_seq}")
    op.create_unique_constraint('uq_evidence_seq', 'evidence', ['seq'])

    op.add_column('domains', sa.Column('confirmed_by', sa.String(), nullable=True))

    op.add_column('reviews', sa.Column('domain', sa.String(), nullable=True))
    op.add_column('reviews', sa.Column('reason', sa.Text(), nullable=True))
    op.create_index(op.f('ix_reviews_domain'), 'reviews', ['domain'], unique=False)

    op.create_table('reports',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('domain', sa.String(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('check_id', sa.String(), nullable=True),
    timestamp('created_at', server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['check_id'], ['checks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_domain'), 'reports', ['domain'], unique=False)

    op.create_table('audit_log',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('target', sa.String(), nullable=False),
    sa.Column('before', sa.JSON(), nullable=True),
    sa.Column('after', sa.JSON(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    timestamp('created_at', server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    op.add_column('campaigns', sa.Column('name', sa.String(), nullable=True))
    op.add_column('campaigns', timestamp('last_activity_at', nullable=True))

    op.add_column('entities', sa.Column('domain_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('entities', sa.Column('campaign_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_entities_campaign_id', 'entities', 'campaigns', ['campaign_id'], ['id'])

    op.add_column('edges', sa.Column('strength', sa.String(), server_default='weak', nullable=False))

    for name in ('gsb_first_hit_at', 'vt_first_hit_at', 'gsb_last_clean_at', 'vt_last_clean_at', 'vt_checked_at'):
        op.add_column('watchlist', timestamp(name, nullable=True))

    op.create_table('takedown_packs',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('recipient_kind', sa.String(), nullable=False),
    sa.Column('recipient', sa.String(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('zip', sa.LargeBinary(), nullable=False),
    timestamp('generated_at', server_default=sa.text('now()'), nullable=False),
    sa.Column('generated_by', sa.String(), nullable=False),
    timestamp('sent_at', nullable=True),
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


def downgrade() -> None:
    op.drop_index(op.f('ix_takedown_requests_pack_id'), table_name='takedown_requests')
    op.drop_table('takedown_requests')
    op.drop_table('takedown_packs')
    for name in ('vt_checked_at', 'vt_last_clean_at', 'gsb_last_clean_at', 'vt_first_hit_at', 'gsb_first_hit_at'):
        op.drop_column('watchlist', name)
    op.drop_column('edges', 'strength')
    op.drop_constraint('fk_entities_campaign_id', 'entities', type_='foreignkey')
    op.drop_column('entities', 'campaign_id')
    op.drop_column('entities', 'domain_count')
    op.drop_column('campaigns', 'last_activity_at')
    op.drop_column('campaigns', 'name')
    op.drop_table('audit_log')
    op.drop_index(op.f('ix_reports_domain'), table_name='reports')
    op.drop_table('reports')
    op.drop_index(op.f('ix_reviews_domain'), table_name='reviews')
    op.drop_column('reviews', 'reason')
    op.drop_column('reviews', 'domain')
    op.drop_column('domains', 'confirmed_by')
    op.drop_constraint('uq_evidence_seq', 'evidence', type_='unique')
    op.drop_column('evidence', 'seq')
    op.drop_index(op.f('ix_checks_domain'), table_name='checks')
    op.drop_column('checks', 'domain')
