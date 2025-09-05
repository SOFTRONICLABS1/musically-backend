from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from typing import Dict, List, Any
import logging

from app.db.database import engine, Base
from app.models.user import User, AuthUser, PasswordResetToken, Content, Follow, ContentLike

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Service to validate database schema against application models"""
    
    @staticmethod
    def get_expected_tables() -> Dict[str, Any]:
        """Get all expected tables from SQLAlchemy models"""
        expected_tables = {}
        
        # Get all table names and columns from SQLAlchemy models
        for table_name, table in Base.metadata.tables.items():
            columns = {}
            for column in table.columns:
                columns[column.name] = {
                    "type": str(column.type),
                    "nullable": column.nullable,
                    "primary_key": column.primary_key,
                    "foreign_key": bool(column.foreign_keys),
                    "unique": column.unique or False,
                    "default": column.default is not None
                }
            
            indexes = []
            for index in table.indexes:
                indexes.append({
                    "name": index.name,
                    "columns": [c.name for c in index.columns],
                    "unique": index.unique
                })
            
            expected_tables[table_name] = {
                "columns": columns,
                "indexes": indexes
            }
        
        return expected_tables
    
    @staticmethod
    def get_actual_tables(db: Session) -> Dict[str, Any]:
        """Get actual tables from the database"""
        actual_tables = {}
        inspector = inspect(engine)
        
        for table_name in inspector.get_table_names():
            columns = {}
            for column in inspector.get_columns(table_name):
                columns[column['name']] = {
                    "type": str(column['type']),
                    "nullable": column['nullable'],
                    "primary_key": column.get('primary_key', False),
                    "default": column['default'] is not None
                }
            
            # Get primary keys
            pk_constraint = inspector.get_pk_constraint(table_name)
            for pk_column in pk_constraint.get('constrained_columns', []):
                if pk_column in columns:
                    columns[pk_column]['primary_key'] = True
            
            # Get foreign keys
            foreign_keys = inspector.get_foreign_keys(table_name)
            for fk in foreign_keys:
                for fk_column in fk.get('constrained_columns', []):
                    if fk_column in columns:
                        columns[fk_column]['foreign_key'] = True
            
            # Get unique constraints
            unique_constraints = inspector.get_unique_constraints(table_name)
            for constraint in unique_constraints:
                for unique_column in constraint.get('column_names', []):
                    if unique_column in columns:
                        columns[unique_column]['unique'] = True
            
            # Get indexes
            indexes = []
            for index in inspector.get_indexes(table_name):
                indexes.append({
                    "name": index['name'],
                    "columns": index['column_names'],
                    "unique": index.get('unique', False)
                })
            
            actual_tables[table_name] = {
                "columns": columns,
                "indexes": indexes
            }
        
        return actual_tables
    
    @staticmethod
    def validate_schema(db: Session) -> Dict[str, Any]:
        """Validate database schema against application models"""
        try:
            expected_tables = SchemaValidator.get_expected_tables()
            actual_tables = SchemaValidator.get_actual_tables(db)
            
            validation_result = {
                "is_valid": True,
                "missing_tables": [],
                "extra_tables": [],
                "table_issues": {},
                "migration_status": None,
                "recommendations": []
            }
            
            # Check for missing tables
            for table_name in expected_tables:
                if table_name not in actual_tables:
                    validation_result["missing_tables"].append(table_name)
                    validation_result["is_valid"] = False
            
            # Check for extra tables (in DB but not in models)
            for table_name in actual_tables:
                if table_name not in expected_tables and table_name != 'alembic_version':
                    validation_result["extra_tables"].append(table_name)
            
            # Check each table's structure
            for table_name in expected_tables:
                if table_name in actual_tables:
                    table_issues = SchemaValidator._validate_table_structure(
                        table_name,
                        expected_tables[table_name],
                        actual_tables[table_name]
                    )
                    if table_issues:
                        validation_result["table_issues"][table_name] = table_issues
                        validation_result["is_valid"] = False
            
            # Check Alembic migration status
            try:
                result = db.execute(text("SELECT version_num FROM alembic_version"))
                current_revision = result.scalar()
                validation_result["migration_status"] = {
                    "current_revision": current_revision,
                    "has_migrations": True
                }
                
                # Check if specific migrations are applied
                expected_revisions = [
                    "554c75177662",  # signup_username migration
                    "d46e7dd4403b",  # profile fields migration
                    "add_social_features"  # social features migration
                ]
                
                if current_revision not in expected_revisions[-1:]:
                    validation_result["recommendations"].append(
                        "Database migrations may be outdated. Run 'alembic upgrade head' to apply latest migrations."
                    )
                    validation_result["is_valid"] = False
                    
            except Exception as e:
                validation_result["migration_status"] = {
                    "has_migrations": False,
                    "error": str(e)
                }
                validation_result["recommendations"].append(
                    "No migration history found. Initialize with 'alembic stamp head' if tables are up to date."
                )
            
            # Generate recommendations
            if validation_result["missing_tables"]:
                if "follows" in validation_result["missing_tables"] or "content_likes" in validation_result["missing_tables"]:
                    validation_result["recommendations"].append(
                        "Social features tables are missing. Run 'alembic upgrade head' to create them."
                    )
                else:
                    validation_result["recommendations"].append(
                        f"Missing tables detected: {', '.join(validation_result['missing_tables'])}. Run migrations to create them."
                    )
            
            if validation_result["table_issues"]:
                validation_result["recommendations"].append(
                    "Table structure mismatches detected. Review the issues and create appropriate migrations."
                )
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Schema validation error: {e}")
            return {
                "is_valid": False,
                "error": str(e),
                "recommendations": ["Failed to validate schema. Check database connection and permissions."]
            }
    
    @staticmethod
    def _validate_table_structure(
        table_name: str,
        expected: Dict[str, Any],
        actual: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Validate individual table structure"""
        issues = {
            "missing_columns": [],
            "extra_columns": [],
            "column_mismatches": []
        }
        
        expected_columns = expected["columns"]
        actual_columns = actual["columns"]
        
        # Check for missing columns
        for col_name in expected_columns:
            if col_name not in actual_columns:
                issues["missing_columns"].append(col_name)
        
        # Check for extra columns
        for col_name in actual_columns:
            if col_name not in expected_columns:
                issues["extra_columns"].append(col_name)
        
        # Check column properties
        for col_name in expected_columns:
            if col_name in actual_columns:
                expected_col = expected_columns[col_name]
                actual_col = actual_columns[col_name]
                
                mismatches = []
                
                # Check nullable
                if expected_col["nullable"] != actual_col["nullable"]:
                    mismatches.append(f"nullable: expected={expected_col['nullable']}, actual={actual_col['nullable']}")
                
                # Check primary key
                if expected_col["primary_key"] != actual_col.get("primary_key", False):
                    mismatches.append(f"primary_key: expected={expected_col['primary_key']}, actual={actual_col.get('primary_key', False)}")
                
                if mismatches:
                    issues["column_mismatches"].append({
                        "column": col_name,
                        "mismatches": mismatches
                    })
        
        # Remove empty issue categories
        issues = {k: v for k, v in issues.items() if v}
        
        return issues if issues else {}
    
    @staticmethod
    def get_pending_migrations(db: Session) -> List[str]:
        """Get list of pending migrations"""
        try:
            # This would integrate with Alembic to check pending migrations
            # For now, return a simple check
            result = db.execute(text("SELECT version_num FROM alembic_version"))
            current_revision = result.scalar()
            
            # Define the expected latest revision
            latest_revision = "add_social_features"
            
            if current_revision != latest_revision:
                return [latest_revision]
            
            return []
            
        except Exception as e:
            logger.error(f"Error checking pending migrations: {e}")
            return []