#!/usr/bin/env python3
"""
SeaTides Materialized View Optimization Script
===============================================

Automates the diagnosis and optimization of slow SeaTides materialized view refreshes.

Usage:
    python optimize_seatides.py --diagnose          # Just show diagnosis
    python optimize_seatides.py --optimize          # Run full optimization
    python optimize_seatides.py --refresh           # Refresh view after optimization
    python optimize_seatides.py --monitor           # Monitor refresh progress
"""

import os
import sys
import time
import argparse
import json
from datetime import datetime
from typing import Dict, List, Tuple
from contextlib import contextmanager
from urllib.parse import urlparse

try:
    import psycopg2
    from psycopg2 import sql, connect
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

# Load environment variables from backend/.env if present
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    # dotenv not installed or file missing — script will fall back to existing env vars
    pass

# Configuration
class Config:
    """Database configuration from environment"""
    
    @staticmethod
    def get_db_config() -> Dict[str, str]:
        """Extract PostgreSQL connection details from DB_URI or environment"""
        db_uri = os.getenv('DB_URI')
        
        if db_uri:
            # Parse PostgreSQL URI
            parsed = urlparse(db_uri)
            return {
                'host': parsed.hostname or 'localhost',
                'port': parsed.port or 5432,
                'database': parsed.path.lstrip('/') or 'postgres',
                'user': parsed.username or 'postgres',
                'password': parsed.password or '',
            }
        else:
            # Fall back to individual env vars
            return {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'database': os.getenv('DB_NAME', 'postgres'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', ''),
            }

# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_status(message: str, status: str = 'INFO'):
    """Print formatted status message"""
    colors = {
        'OK': Colors.GREEN,
        'WARN': Colors.YELLOW,
        'ERROR': Colors.RED,
        'INFO': Colors.BLUE,
    }
    color = colors.get(status, Colors.BLUE)
    print(f"{color}[{status}]{Colors.RESET} {message}")

@contextmanager
def get_connection(autocommit=False):
    """PostgreSQL connection context manager"""
    config = Config.get_db_config()
    # Print masked connection info for debugging (don't print password)
    try:
        debug_info = {
            'host': config.get('host'),
            'port': config.get('port'),
            'database': config.get('database'),
            'user': config.get('user')
        }
        print_status(f"Using DB config: {json.dumps(debug_info)}", 'INFO')
    except Exception:
        pass
    conn = None
    try:
        conn = connect(**config)
        if autocommit:
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        yield conn
        if not autocommit:
            conn.commit()
    except Exception as e:
        if conn and not autocommit:
            conn.rollback()
        print_status(f"Connection error: {e}", 'ERROR')
        raise
    finally:
        if conn:
            conn.close()

class SeaTidesDiagnostic:
    """Diagnostic tools for SeaTides view"""
    
    @staticmethod
    def get_view_definition(conn) -> str:
        """Get the SeaTides view definition"""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pg_get_viewdef('public."SeaTides"'::regclass, true) as view_def
            """)
            result = cur.fetchone()
            return result[0] if result else "View not found"
    
    @staticmethod
    def check_indexes(conn) -> List[Dict]:
        """Check all indexes on critical tables"""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    tablename,
                    indexname,
                    indexdef,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                    idx_scan as times_used,
                    idx_tup_read as tuples_read
                FROM pg_indexes i
                LEFT JOIN pg_stat_user_indexes s ON i.indexname = s.indexrelname
                WHERE tablename IN ('SeaTides', 'Monitors_info2', 'Locations')
                ORDER BY tablename, indexname
            """)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    
    @staticmethod
    def check_table_sizes(conn) -> List[Dict]:
        """Check table sizes and row counts"""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    'Monitors_info2' as table_name,
                    pg_size_pretty(pg_total_relation_size('public."Monitors_info2"')) as total_size,
                    pg_size_pretty(pg_relation_size('public."Monitors_info2"')) as data_size,
                    (SELECT COUNT(*) FROM "Monitors_info2") as row_count
                UNION ALL
                SELECT 
                    'SeaTides',
                    pg_size_pretty(pg_total_relation_size('public."SeaTides"')),
                    pg_size_pretty(pg_relation_size('public."SeaTides"')),
                    (SELECT COUNT(*) FROM "SeaTides")
                UNION ALL
                SELECT 
                    'Locations',
                    pg_size_pretty(pg_total_relation_size('public."Locations"')),
                    pg_size_pretty(pg_relation_size('public."Locations"')),
                    (SELECT COUNT(*) FROM "Locations")
            """)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    
    @staticmethod
    def check_bloat(conn) -> List[Dict]:
        """Check for table bloat"""
        with conn.cursor() as cur:
            # pg_stat_user_tables uses column name 'relname' for the table name
            # Use quote_ident to ensure correctly quoted relation names
            cur.execute("""
                SELECT 
                    relname AS tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||quote_ident(relname))) as size,
                    n_dead_tup as dead_tuples,
                    n_live_tup as live_tuples,
                    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_ratio_percent
                FROM pg_stat_user_tables
                WHERE relname IN ('SeaTides', 'Monitors_info2', 'Locations')
                ORDER BY n_dead_tup DESC
            """)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    
    @staticmethod
    def check_missing_indexes(conn) -> List[str]:
        """Identify critical missing indexes"""
        missing_indexes = []
        
        with conn.cursor() as cur:
            # Check for date index
            cur.execute("""
                SELECT COUNT(*) FROM pg_indexes 
                WHERE tablename = 'Monitors_info2' 
                AND indexdef LIKE '%Tab_DateTime%'
            """)
            if cur.fetchone()[0] == 0:
                missing_indexes.append("Missing: idx_monitors_datetime")
            
            # Check for tag index
            cur.execute("""
                SELECT COUNT(*) FROM pg_indexes 
                WHERE tablename = 'Monitors_info2' 
                AND indexdef LIKE '%Tab_TabularTag%'
            """)
            if cur.fetchone()[0] == 0:
                missing_indexes.append("Missing: idx_monitors_tag")
            
            # Check composite index
            cur.execute("""
                SELECT COUNT(*) FROM pg_indexes 
                WHERE tablename = 'Monitors_info2' 
                AND indexdef LIKE '%Tab_TabularTag%Tab_DateTime%'
            """)
            if cur.fetchone()[0] == 0:
                missing_indexes.append("Missing: idx_monitors_tag_datetime (composite)")
            
            # Check SeaTides indexes
            cur.execute("""
                SELECT COUNT(*) FROM pg_indexes 
                WHERE tablename = 'SeaTides' 
                AND indexdef LIKE '%Date%Station%'
            """)
            if cur.fetchone()[0] == 0:
                missing_indexes.append("Missing: idx_seatides_date_station")
        
        return missing_indexes

class SeaTidesOptimizer:
    """Optimization operations for SeaTides"""
    
    @staticmethod
    def create_indexes(conn) -> Tuple[int, List[str]]:
        """Create all critical missing indexes"""
        indexes_created = 0
        messages = []

        index_definitions = [
            ("idx_monitors_info2_datetime",
             'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_info2_datetime ON "Monitors_info2" ("Tab_DateTime")'),

            ("idx_monitors_info2_tag",
             'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_info2_tag ON "Monitors_info2" ("Tab_TabularTag")'),

            ("idx_monitors_info2_tag_datetime",
             'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_info2_tag_datetime ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime")'),

            ("idx_monitors_value_notnull",
             'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_value_notnull ON "Monitors_info2" ("Tab_Value_mDepthC1", "Tab_DateTime") WHERE "Tab_Value_mDepthC1" IS NOT NULL'),

            ("idx_seatides_date",
             'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_date ON "SeaTides" ("Date")'),

            ("idx_seatides_station_date",
             'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_station_date ON "SeaTides" ("Station", "Date")'),

            ("idx_locations_tag",
             'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_locations_tag ON "Locations" ("Tab_TabularTag")'),
        ]

        with conn.cursor() as cur:
            for idx_name, idx_sql in index_definitions:
                try:
                    print_status(f"Creating index: {idx_name}...", 'INFO')
                    cur.execute(idx_sql)
                    print_status(f"[OK] Index created: {idx_name}", 'OK')
                    indexes_created += 1
                    messages.append(f"[OK] {idx_name}")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print_status(f"[OK] Index already exists: {idx_name}", 'OK')
                        messages.append(f"[OK] {idx_name} (already exists)")
                    else:
                        print_status(f"Failed to create {idx_name}: {e}", 'WARN')
                        messages.append(f"[FAIL] {idx_name}: {str(e)[:50]}")

        return indexes_created, messages
    
    @staticmethod
    def analyze_tables(conn) -> List[str]:
        """Update table statistics"""
        messages = []
        tables = ['Monitors_info2', 'SeaTides', 'Locations']
        
        with conn.cursor() as cur:
            for table in tables:
                try:
                    print_status(f"Analyzing {table}...", 'INFO')
                    cur.execute(f'ANALYZE "{table}"')
                    conn.commit()
                    print_status(f"✓ Analyzed: {table}", 'OK')
                    messages.append(f"✓ {table}")
                except Exception as e:
                    print_status(f"Failed to analyze {table}: {e}", 'WARN')
                    messages.append(f"✗ {table}: {str(e)[:50]}")
        
        return messages
    
    @staticmethod
    def vacuum_tables(conn) -> List[str]:
        """Run VACUUM ANALYZE on tables"""
        messages = []
        tables = ['Monitors_info2', 'SeaTides', 'Locations']
        
        with conn.cursor() as cur:
            for table in tables:
                try:
                    print_status(f"Vacuuming {table}...", 'INFO')
                    # Use simple VACUUM ANALYZE (no FULL to avoid locking)
                    cur.execute(f'VACUUM ANALYZE "{table}"')
                    conn.commit()
                    print_status(f"✓ Vacuumed: {table}", 'OK')
                    messages.append(f"✓ {table}")
                except Exception as e:
                    print_status(f"Failed to vacuum {table}: {e}", 'WARN')
                    messages.append(f"✗ {table}: {str(e)[:50]}")
        
        return messages
    
    @staticmethod
    def refresh_view(conn, concurrent: bool = False) -> Tuple[bool, float]:
        """Refresh the materialized view and measure time"""
        start_time = time.time()
        
        try:
            with conn.cursor() as cur:
                # Set memory for this session
                cur.execute('SET work_mem = \'512MB\'')
                cur.execute('SET maintenance_work_mem = \'1GB\'')
                
                if concurrent:
                    print_status("Refreshing SeaTides (CONCURRENT - non-blocking)...", 'INFO')
                    cur.execute('REFRESH MATERIALIZED VIEW CONCURRENTLY "SeaTides"')
                else:
                    print_status("Refreshing SeaTides (STANDARD)...", 'INFO')
                    cur.execute('REFRESH MATERIALIZED VIEW "SeaTides"')
                
                conn.commit()
                duration = time.time() - start_time
                
                minutes = duration / 60
                print_status(f"✓ Refresh completed in {duration:.1f}s ({minutes:.2f}m)", 'OK')
                return True, duration
                
        except Exception as e:
            duration = time.time() - start_time
            print_status(f"Refresh failed after {duration:.1f}s: {e}", 'ERROR')
            return False, duration

class SeaTidesMonitor:
    """Monitor refresh operations"""
    
    @staticmethod
    def monitor_refresh(conn, interval: int = 5):
        """Monitor an ongoing refresh operation"""
        print_status("Monitoring refresh... (Press Ctrl+C to stop)", 'INFO')
        
        try:
            while True:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            EXTRACT(EPOCH FROM (NOW() - query_start)) as seconds_running,
                            query,
                            state
                        FROM pg_stat_activity
                        WHERE query ILIKE '%REFRESH%MATERIALIZED%'
                        ORDER BY query_start
                    """)
                    
                    rows = cur.fetchall()
                    if not rows:
                        print_status("No refresh operation found", 'WARN')
                        break
                    
                    for seconds_running, query, state in rows:
                        minutes = seconds_running / 60
                        print(f"\r{Colors.BLUE}[MONITOR]{Colors.RESET} "
                              f"Running: {seconds_running:.0f}s ({minutes:.2f}m) - State: {state}", 
                              end='', flush=True)
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print_status("Monitoring stopped", 'INFO')

def diagnose(args):
    """Run diagnostic analysis"""
    print(f"\n{Colors.BOLD}=== SeaTides Materialized View Diagnostic ==={Colors.RESET}\n")
    
    try:
        with get_connection() as conn:
            # View definition
            print(f"{Colors.BOLD}1. View Definition:{Colors.RESET}")
            view_def = SeaTidesDiagnostic.get_view_definition(conn)
            print(view_def[:500] + "..." if len(view_def) > 500 else view_def)
            print()
            
            # Table sizes
            print(f"{Colors.BOLD}2. Table Sizes:{Colors.RESET}")
            sizes = SeaTidesDiagnostic.check_table_sizes(conn)
            for row in sizes:
                print(f"  {row['table_name']:20} {row['total_size']:>15} ({row['row_count']:>12} rows)")
            print()
            
            # Indexes
            print(f"{Colors.BOLD}3. Current Indexes:{Colors.RESET}")
            indexes = SeaTidesDiagnostic.check_indexes(conn)
            if indexes:
                for idx in indexes:
                    print(f"  {idx['tablename']:20} {idx['indexname']:30} (used {idx['times_used'] or 0:>5}x)")
            else:
                print("  No indexes found!")
            print()
            
            # Bloat
            print(f"{Colors.BOLD}4. Table Bloat:{Colors.RESET}")
            bloat = SeaTidesDiagnostic.check_bloat(conn)
            for row in bloat:
                status = Colors.GREEN if row['dead_ratio_percent'] < 10 else Colors.YELLOW if row['dead_ratio_percent'] < 20 else Colors.RED
                print(f"  {row['tablename']:20} {status}Dead: {row['dead_ratio_percent']:>5.1f}%{Colors.RESET} ({row['dead_tuples']:>10} tuples)")
            print()
            
            # Missing indexes
            print(f"{Colors.BOLD}5. Recommendations:{Colors.RESET}")
            missing = SeaTidesDiagnostic.check_missing_indexes(conn)
            if missing:
                print(f"  {Colors.RED}Missing indexes (critical!)::{Colors.RESET}")
                for msg in missing:
                    print(f"    ✗ {msg}")
            else:
                print(f"  {Colors.GREEN}✓ All critical indexes present{Colors.RESET}")
            print()
    
    except Exception as e:
        print_status(f"Diagnostic failed: {e}", 'ERROR')
        sys.exit(1)

def optimize(args):
    """Run full optimization"""
    print(f"\n{Colors.BOLD}=== SeaTides Optimization ==={Colors.RESET}\n")

    try:
        # Use autocommit for index creation
        with get_connection(autocommit=True) as conn:
            # Step 1: Create indexes
            print(f"\n{Colors.BOLD}Step 1: Creating Indexes{Colors.RESET}")
            count, messages = SeaTidesOptimizer.create_indexes(conn)
            print(f"  {Colors.GREEN}[OK] Created/verified {count} indexes{Colors.RESET}")

        # Use regular transaction for analyze and vacuum
        with get_connection() as conn:
            # Step 2: Analyze
            print(f"\n{Colors.BOLD}Step 2: Updating Statistics{Colors.RESET}")
            messages = SeaTidesOptimizer.analyze_tables(conn)
            print(f"  {Colors.GREEN}[OK] Analyzed tables{Colors.RESET}")

            # Step 3: Vacuum
            print(f"\n{Colors.BOLD}Step 3: Cleaning Up Bloat{Colors.RESET}")
            messages = SeaTidesOptimizer.vacuum_tables(conn)
            print(f"  {Colors.GREEN}[OK] Vacuumed tables{Colors.RESET}")

            print(f"\n{Colors.GREEN}{Colors.BOLD}[OK] Optimization Complete!{Colors.RESET}")
            print(f"\nNext step: Run '{Colors.BOLD}python optimize_seatides.py --refresh{Colors.RESET}' to test refresh time\n")

    except Exception as e:
        print_status(f"Optimization failed: {e}", 'ERROR')
        sys.exit(1)

def refresh(args):
    """Refresh the materialized view"""
    print(f"\n{Colors.BOLD}=== SeaTides Refresh ==={Colors.RESET}\n")
    
    try:
        with get_connection() as conn:
            success, duration = SeaTidesOptimizer.refresh_view(conn, concurrent=args.concurrent)
            
            if success:
                print(f"\n{Colors.GREEN}✓ Refresh successful!{Colors.RESET}")
                print(f"  Duration: {duration:.1f}s ({duration/60:.2f}m)")
                
                if args.concurrent:
                    print(f"  {Colors.BLUE}Note: Used CONCURRENT mode (non-blocking){Colors.RESET}")
            else:
                print(f"\n{Colors.RED}✗ Refresh failed{Colors.RESET}")
                sys.exit(1)
    
    except Exception as e:
        print_status(f"Refresh failed: {e}", 'ERROR')
        sys.exit(1)

def monitor(args):
    """Monitor refresh progress"""
    try:
        with get_connection() as conn:
            SeaTidesMonitor.monitor_refresh(conn)
    except Exception as e:
        print_status(f"Monitoring failed: {e}", 'ERROR')
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='SeaTides Materialized View Optimization Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python optimize_seatides.py --diagnose          # Show diagnosis
  python optimize_seatides.py --optimize          # Run optimization
  python optimize_seatides.py --refresh           # Refresh view
  python optimize_seatides.py --monitor           # Monitor refresh
        """
    )
    
    parser.add_argument('--diagnose', action='store_true', 
                       help='Run diagnostic analysis')
    parser.add_argument('--optimize', action='store_true',
                       help='Run full optimization')
    parser.add_argument('--refresh', action='store_true',
                       help='Refresh materialized view')
    parser.add_argument('--monitor', action='store_true',
                       help='Monitor refresh operation')
    parser.add_argument('--concurrent', action='store_true',
                       help='Use concurrent refresh (non-blocking)')
    
    args = parser.parse_args()
    
    if not any([args.diagnose, args.optimize, args.refresh, args.monitor]):
        parser.print_help()
        sys.exit(1)
    
    if args.diagnose:
        diagnose(args)
    elif args.optimize:
        optimize(args)
    elif args.refresh:
        refresh(args)
    elif args.monitor:
        monitor(args)

if __name__ == '__main__':
    main()
