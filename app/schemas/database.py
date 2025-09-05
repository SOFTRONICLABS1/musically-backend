from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class TableIssue(BaseModel):
    missing_columns: List[str] = []
    extra_columns: List[str] = []
    column_mismatches: List[Dict[str, Any]] = []


class MigrationStatus(BaseModel):
    current_revision: Optional[str] = None
    has_migrations: bool
    error: Optional[str] = None


class SchemaValidationResponse(BaseModel):
    is_valid: bool
    missing_tables: List[str] = []
    extra_tables: List[str] = []
    table_issues: Dict[str, Any] = {}
    migration_status: Optional[MigrationStatus] = None
    recommendations: List[str] = []
    error: Optional[str] = None


class DatabaseHealthResponse(BaseModel):
    is_healthy: bool
    database_connected: bool
    tables_count: int
    migration_status: Optional[MigrationStatus] = None
    error: Optional[str] = None