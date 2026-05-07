"""add model settings and embed job type

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-07
"""

from __future__ import annotations

from alembic import op

down_revision = "0003"
revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_type")
    op.execute(
        "ALTER TABLE jobs ADD CONSTRAINT ck_jobs_type "
        "CHECK (type IN ('crawl', 'index', 'embed'))"
    )
    op.execute("""
        INSERT INTO service_configs (key, value, description, is_configured)
        VALUES
          ('embedding_provider', 'ollama', 'Provider for embedding model: ollama or litellm', true),
          ('embedding_model', 'ollama/qwen3-embedding:0.6b', 'litellm model string for embeddings', true),
          ('reranker_provider', 'ollama', 'Provider for reranker model: ollama or litellm', true),
          ('reranker_model', 'ollama/bge-reranker-v2-m3', 'litellm model string for reranking', true),
          ('llm_provider', 'litellm', 'Provider for LLM: ollama or litellm', true),
          ('llm_model', 'gemini/gemini-3-flash-preview', 'litellm model string for LLM', true),
          ('embedding_model_changed_since_last_embed', 'false',
           'Set true when embedding model changes, cleared on successful embed job', true)
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_type")
    op.execute(
        "ALTER TABLE jobs ADD CONSTRAINT ck_jobs_type "
        "CHECK (type IN ('crawl', 'index'))"
    )
    op.execute(
        "DELETE FROM service_configs WHERE key IN ("
        "'embedding_provider', 'embedding_model', 'reranker_provider', "
        "'reranker_model', 'llm_provider', 'llm_model', "
        "'embedding_model_changed_since_last_embed')"
    )
