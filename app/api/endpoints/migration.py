"""Database migration endpoints"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.database import get_db, engine, Base
from app.models.user import User, AuthUser, PasswordResetToken, Content
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Migration"])


@router.post("/create-schema")
async def create_schema(db: Session = Depends(get_db)):
    """Create all tables from SQLAlchemy models"""
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        # Verify tables were created
        result = db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        
        tables = [row[0] for row in result]
        
        return {
            "status": "success",
            "message": "Schema created successfully",
            "tables_created": tables
        }
    except Exception as e:
        logger.error(f"Error creating schema: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create schema: {str(e)}")


@router.post("/import-data")
async def import_data(migration_data: dict):
    """Import data from local database export"""
    db = next(get_db())
    
    try:
        imported_tables = []
        total_rows = 0
        
        # First, create the schema if needed
        Base.metadata.create_all(bind=engine)
        
        # Import data for each table
        for table_name, table_data in migration_data.get("tables", {}).items():
            if table_data["row_count"] == 0:
                continue
                
            rows_imported = 0
            
            for row in table_data["data"]:
                # Build INSERT query with ON CONFLICT DO NOTHING
                columns = list(row.keys())
                placeholders = [f":{col}" for col in columns]
                
                query = f"""
                    INSERT INTO {table_name} ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                    ON CONFLICT DO NOTHING
                """
                
                try:
                    db.execute(text(query), row)
                    rows_imported += 1
                except Exception as e:
                    logger.warning(f"Failed to insert row in {table_name}: {str(e)}")
                    continue
            
            db.commit()
            
            imported_tables.append({
                "table": table_name,
                "rows_imported": rows_imported,
                "rows_in_export": table_data["row_count"]
            })
            total_rows += rows_imported
            
        return {
            "status": "success",
            "message": f"Data imported successfully",
            "total_rows_imported": total_rows,
            "tables": imported_tables
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error importing data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import data: {str(e)}")
    finally:
        db.close()


@router.post("/execute-sql")
async def execute_sql(sql_commands: str, db: Session = Depends(get_db)):
    """Execute raw SQL commands (use with caution!)"""
    try:
        # Split by semicolons but be careful with strings
        commands = [cmd.strip() for cmd in sql_commands.split(';') if cmd.strip()]
        
        results = []
        for command in commands:
            if not command:
                continue
                
            try:
                result = db.execute(text(command))
                db.commit()
                
                # Try to get row count
                if hasattr(result, 'rowcount'):
                    results.append(f"Executed: {command[:50]}... ({result.rowcount} rows affected)")
                else:
                    results.append(f"Executed: {command[:50]}...")
                    
            except Exception as e:
                db.rollback()
                results.append(f"Failed: {command[:50]}... - Error: {str(e)}")
                
        return {
            "status": "success",
            "message": f"Executed {len(commands)} SQL commands",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error executing SQL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to execute SQL: {str(e)}")


@router.get("/compare-schemas")
async def compare_schemas(db: Session = Depends(get_db)):
    """Compare current Aurora schema with expected schema"""
    try:
        # Get current tables
        result = db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        current_tables = set(row[0] for row in result)
        
        # Expected tables from models
        expected_tables = {
            'users', 'auth_users', 'password_reset_tokens', 'content',
            'playlists', 'playlist_content', 'playlist_access',
            'creator_subscriptions', 'user_subscriptions',
            'reviews', 'game_sessions', 'note_attempts',
            'marketplace_listings', 'alembic_version'
        }
        
        missing_tables = expected_tables - current_tables
        extra_tables = current_tables - expected_tables
        
        # Get row counts for existing tables
        table_counts = {}
        for table in current_tables:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            table_counts[table] = result.fetchone()[0]
        
        return {
            "status": "success",
            "current_tables": list(current_tables),
            "expected_tables": list(expected_tables),
            "missing_tables": list(missing_tables),
            "extra_tables": list(extra_tables),
            "table_row_counts": table_counts
        }
        
    except Exception as e:
        logger.error(f"Error comparing schemas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to compare schemas: {str(e)}")