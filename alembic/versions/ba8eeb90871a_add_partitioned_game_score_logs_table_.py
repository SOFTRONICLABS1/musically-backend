"""Add partitioned game_score_logs table for gameplay logging

Revision ID: ba8eeb90871a
Revises: 5a98c2fac1ec
Create Date: 2025-09-12 13:17:41.527076

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ba8eeb90871a'
down_revision: Union[str, None] = '5a98c2fac1ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the partitioned parent table
    op.execute("""
        CREATE TABLE game_score_logs (
            id UUID DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
            content_id UUID NOT NULL REFERENCES content(id) ON DELETE CASCADE,
            score DECIMAL(10,2) NOT NULL,
            accuracy DECIMAL(5,2),
            attempts INTEGER NOT NULL DEFAULT 1,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            cycles INTEGER,
            level_config JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at);
    """)
    
    # Create indexes on the parent table
    op.execute("""
        CREATE INDEX idx_game_score_logs_user_id ON game_score_logs (user_id);
        CREATE INDEX idx_game_score_logs_game_id ON game_score_logs (game_id);
        CREATE INDEX idx_game_score_logs_content_id ON game_score_logs (content_id);
        CREATE INDEX idx_game_score_logs_created_at ON game_score_logs (created_at);
        CREATE INDEX idx_game_score_logs_user_created ON game_score_logs (user_id, created_at DESC);
        CREATE INDEX idx_game_score_logs_game_created ON game_score_logs (game_id, created_at DESC);
    """)
    
    # Create the current month partition
    op.execute("""
        CREATE TABLE game_score_logs_2025_09 PARTITION OF game_score_logs
            FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
    """)
    
    # Create next month partition  
    op.execute("""
        CREATE TABLE game_score_logs_2025_10 PARTITION OF game_score_logs
            FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
    """)
    
    # Create a function to automatically create future partitions
    op.execute("""
        CREATE OR REPLACE FUNCTION create_monthly_game_score_logs_partition(year INT, month INT)
        RETURNS VOID AS $$
        DECLARE
            start_date DATE;
            end_date DATE;
            partition_name TEXT;
        BEGIN
            start_date := make_date(year, month, 1);
            end_date := start_date + INTERVAL '1 month';
            partition_name := 'game_score_logs_' || year || '_' || lpad(month::text, 2, '0');
            
            EXECUTE format('CREATE TABLE %I PARTITION OF game_score_logs FOR VALUES FROM (%L) TO (%L)',
                          partition_name, start_date, end_date);
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create a trigger function to auto-create partitions
    op.execute("""
        CREATE OR REPLACE FUNCTION auto_create_game_score_logs_partition()
        RETURNS TRIGGER AS $$
        DECLARE
            partition_date DATE;
            year INT;
            month INT;
        BEGIN
            partition_date := date_trunc('month', NEW.created_at);
            year := extract(year from partition_date);
            month := extract(month from partition_date);
            
            BEGIN
                PERFORM create_monthly_game_score_logs_partition(year, month);
            EXCEPTION 
                WHEN duplicate_table THEN
                    -- Partition already exists, continue
                    NULL;
            END;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create the trigger
    op.execute("""
        CREATE TRIGGER trigger_auto_create_game_score_logs_partition
            BEFORE INSERT ON game_score_logs
            FOR EACH ROW EXECUTE FUNCTION auto_create_game_score_logs_partition();
    """)


def downgrade() -> None:
    # Drop the trigger first
    op.execute("DROP TRIGGER IF EXISTS trigger_auto_create_game_score_logs_partition ON game_score_logs;")
    
    # Drop the functions
    op.execute("DROP FUNCTION IF EXISTS auto_create_game_score_logs_partition();")
    op.execute("DROP FUNCTION IF EXISTS create_monthly_game_score_logs_partition(INT, INT);")
    
    # Drop the partitioned table (this will drop all partitions)
    op.execute("DROP TABLE IF EXISTS game_score_logs CASCADE;")
