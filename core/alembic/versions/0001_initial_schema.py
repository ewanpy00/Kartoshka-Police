"""initial schema

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('campaigns',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('brand_id', sa.String(), nullable=True),
    sa.Column('first_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('checks',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('final_url', sa.Text(), nullable=True),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('mode', sa.String(), nullable=False),
    sa.Column('verdict', sa.String(), nullable=False),
    sa.Column('score', sa.Integer(), nullable=False),
    sa.Column('stage', sa.String(), nullable=False),
    sa.Column('brand', sa.String(), nullable=True),
    sa.Column('safe_action', sa.JSON(), nullable=True),
    sa.Column('reasons', sa.JSON(), nullable=False),
    sa.Column('campaign_id', sa.String(), nullable=True),
    sa.Column('evidence_id', sa.String(), nullable=True),
    sa.Column('internal_requests_blocked', sa.Integer(), nullable=True),
    sa.Column('navigation_blocked', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('domains',
    sa.Column('domain', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('brand_id', sa.String(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('domain')
    )
    op.create_index(op.f('ix_domains_status'), 'domains', ['status'], unique=False)
    op.create_index(op.f('ix_domains_updated_at'), 'domains', ['updated_at'], unique=False)
    op.create_table('entities',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('kind', 'value')
    )
    op.create_table('watchlist',
    sa.Column('domain', sa.String(), nullable=False),
    sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('next_check_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('domain')
    )
    op.create_table('evidence',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('check_id', sa.String(), nullable=False),
    sa.Column('prev_hash', sa.String(length=64), nullable=True),
    sa.Column('hash', sa.String(length=64), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['check_id'], ['checks.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('hash')
    )
    op.create_index(op.f('ix_evidence_check_id'), 'evidence', ['check_id'], unique=False)
    op.create_table('verdicts',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('check_id', sa.String(), nullable=False),
    sa.Column('verdict', sa.String(), nullable=False),
    sa.Column('score', sa.Integer(), nullable=False),
    sa.Column('stage', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['check_id'], ['checks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verdicts_check_id'), 'verdicts', ['check_id'], unique=False)
    op.create_table('artifacts',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('evidence_id', sa.String(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('path', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_artifacts_evidence_id'), 'artifacts', ['evidence_id'], unique=False)
    op.create_table('edges',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('src_id', sa.BigInteger(), nullable=False),
    sa.Column('dst_id', sa.BigInteger(), nullable=False),
    sa.Column('evidence_id', sa.String(), nullable=True),
    sa.Column('campaign_id', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['dst_id'], ['entities.id'], ),
    sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ),
    sa.ForeignKeyConstraint(['src_id'], ['entities.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_edges_dst_id'), 'edges', ['dst_id'], unique=False)
    op.create_index(op.f('ix_edges_src_id'), 'edges', ['src_id'], unique=False)
    op.create_table('reviews',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('evidence_id', sa.String(), nullable=False),
    sa.Column('decision', sa.String(), nullable=False),
    sa.Column('reviewer', sa.String(), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reviews_evidence_id'), 'reviews', ['evidence_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reviews_evidence_id'), table_name='reviews')
    op.drop_table('reviews')
    op.drop_index(op.f('ix_edges_src_id'), table_name='edges')
    op.drop_index(op.f('ix_edges_dst_id'), table_name='edges')
    op.drop_table('edges')
    op.drop_index(op.f('ix_artifacts_evidence_id'), table_name='artifacts')
    op.drop_table('artifacts')
    op.drop_index(op.f('ix_verdicts_check_id'), table_name='verdicts')
    op.drop_table('verdicts')
    op.drop_index(op.f('ix_evidence_check_id'), table_name='evidence')
    op.drop_table('evidence')
    op.drop_table('watchlist')
    op.drop_table('entities')
    op.drop_index(op.f('ix_domains_updated_at'), table_name='domains')
    op.drop_index(op.f('ix_domains_status'), table_name='domains')
    op.drop_table('domains')
    op.drop_table('checks')
    op.drop_table('campaigns')
