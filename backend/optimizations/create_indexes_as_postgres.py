#!/usr/bin/env python3
"""
Create critical indexes using postgres superuser
Run this with: python create_indexes_as_postgres.py
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import time
import getpass

# Database configuration - using postgres superuser
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'Test2-SeaLevels_Restored',
    'user': 'postgres',
    'password': None  # Will prompt
}

# Critical indexes to create
INDEXES = [
    {
        'name': 'idx_monitors_tag_datetime',
        'sql': '''CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_tag_datetime
                  ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime")''',
        'description': 'JOIN performance (MOST CRITICAL!)'
    },
    {
        'name': 'idx_monitors_datetime_value',
        'sql': '''CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_datetime_value
                  ON "Monitors_info2" ("Tab_DateTime", "Tab_Value_mDepthC1")
                  WHERE "Tab_Value_mDepthC1" IS NOT NULL''',
        'description': 'Filter non-NULL values'
    },
    {
        'name': 'idx_seatides_date_station',
        'sql': '''CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_date_station
                  ON "SeaTides" ("Date", "Station")''',
        'description': 'SeaTides query performance'
    },
    {
        'name': 'idx_locations_tag',
        'sql': '''CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_locations_tag
                  ON "Locations" ("Tab_TabularTag")''',
        'description': 'Locations JOIN'
    }
]

def create_indexes():
    """Create all critical indexes"""
    print("\n" + "="*60)
    print("CREATING CRITICAL INDEXES FOR SEATIDES OPTIMIZATION")
    print("="*60 + "\n")

    # Prompt for postgres password
    print("Enter postgres user password:")
    DB_CONFIG['password'] = getpass.getpass()

    try:
        # Connect with autocommit for CONCURRENT index creation
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        try:
            # Set memory parameters
            print("\n[INFO] Setting memory parameters...")
            cur.execute("SET work_mem = '512MB'")
            cur.execute("SET maintenance_work_mem = '1GB'")
            print("[OK] Memory configured\n")

            # Create each index
            for i, index in enumerate(INDEXES, 1):
                print(f"[{i}/{len(INDEXES)}] Creating index: {index['name']}")
                print(f"      Purpose: {index['description']}")
                print(f"      This may take 5-10 minutes...")

                start_time = time.time()

                try:
                    cur.execute(index['sql'])
                    elapsed = time.time() - start_time
                    minutes = elapsed / 60
                    print(f"      [OK] Created in {elapsed:.1f} seconds ({minutes:.2f} minutes)\n")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"      [OK] Already exists\n")
                    else:
                        print(f"      [ERROR] Failed: {e}\n")

            # Analyze tables
            print("\n" + "="*60)
            print("UPDATING TABLE STATISTICS")
            print("="*60 + "\n")

            tables = ['Monitors_info2', 'SeaTides', 'Locations']
            for table in tables:
                print(f"Analyzing {table}...")
                try:
                    cur.execute(f'ANALYZE "{table}"')
                    print(f"[OK] {table} analyzed\n")
                except Exception as e:
                    print(f"[ERROR] Failed to analyze {table}: {e}\n")

            print("\n" + "="*60)
            print("OPTIMIZATION COMPLETE!")
            print("="*60)
            print("\nNext step: Test the refresh time with:")
            print('  REFRESH MATERIALIZED VIEW "SeaTides";')
            print("\nExpected improvement: 17+ hours -> 5-30 minutes\n")

        finally:
            cur.close()
            conn.close()

    except psycopg2.OperationalError as e:
        print(f"\n[ERROR] Connection failed: {e}")
        print("\nMake sure you have the correct postgres password.")
        print("If you don't have postgres access, use pgAdmin to run the SQL manually.\n")

if __name__ == '__main__':
    create_indexes()
