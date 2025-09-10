#!/usr/bin/env python3
"""
Apply performance indexes to the Musically database
"""
import psycopg2
import sys
import time

DATABASE_URL = "postgresql://postgres:YourSecurePassword123!@musically-dev-postgres.ckl0kebdzjck.us-east-1.rds.amazonaws.com:5432/musically?sslmode=require"

# Read the SQL file
with open('add_performance_indexes.sql', 'r') as f:
    sql_content = f.read()

# Split SQL content into individual statements
statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip() and not stmt.strip().startswith('--')]

def apply_indexes():
    """Apply performance indexes to the database"""
    try:
        print("🔌 Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(autocommit=True)  # For CREATE INDEX CONCURRENTLY
        cur = conn.cursor()
        
        print("✅ Connected successfully!")
        print(f"📊 Applying {len(statements)} index statements...")
        
        success_count = 0
        skip_count = 0
        
        for i, statement in enumerate(statements, 1):
            if not statement:
                continue
                
            try:
                print(f"  {i:2d}. {statement[:60]}...")
                start_time = time.time()
                
                cur.execute(statement)
                
                end_time = time.time()
                print(f"     ✅ Success ({end_time - start_time:.2f}s)")
                success_count += 1
                
            except psycopg2.Error as e:
                error_msg = str(e).strip()
                if "already exists" in error_msg:
                    print(f"     ⏭️  Already exists")
                    skip_count += 1
                else:
                    print(f"     ❌ Error: {error_msg}")
        
        print(f"\n📈 Index creation summary:")
        print(f"   ✅ Created: {success_count}")
        print(f"   ⏭️  Skipped: {skip_count}")
        print(f"   📊 Total: {len(statements)}")
        
        # Get final index count
        cur.execute("""
            SELECT COUNT(*) as index_count 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND indexname LIKE 'idx_%'
        """)
        
        index_count = cur.fetchone()[0]
        print(f"   🎯 Total performance indexes: {index_count}")
        
        conn.close()
        print("\n🎉 Database optimization completed!")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    success = apply_indexes()
    sys.exit(0 if success else 1)