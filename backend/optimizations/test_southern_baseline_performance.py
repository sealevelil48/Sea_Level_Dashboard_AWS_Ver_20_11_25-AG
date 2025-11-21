"""
Performance Testing Script for Southern Baseline Rules
======================================================
Tests both Python-based and SQL-optimized implementations
Generates performance comparison reports

Usage:
    python test_southern_baseline_performance.py

Requirements:
    - Database connection configured in .env
    - Indexes created (run database_indexes.sql first)
    - Materialized view created (run southern_baseline_optimized.sql first)
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
import statistics

# Add parent directory to path for imports
backend_root = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_root))

from dotenv import load_dotenv
load_dotenv(backend_root / '.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_python_implementation(db_manager, start_date, end_date, iterations=3):
    """Test Python-based Southern Baseline Rules implementation"""
    from shared.baseline_integration import get_outliers_api
    from shared.data_processing import load_data_from_db

    times = []
    results = None

    for i in range(iterations):
        logger.info(f"Python test iteration {i+1}/{iterations}")
        start_time = time.time()

        try:
            # Load data
            df = load_data_from_db(start_date, end_date, "All Stations")

            if df is not None and not df.empty:
                # Process with Python
                results = get_outliers_api(df)
                duration = time.time() - start_time
                times.append(duration)
                logger.info(f"  Completed in {duration:.3f}s")
            else:
                logger.warning("No data returned")
                return None

        except Exception as e:
            logger.error(f"Error in Python test: {e}")
            return None

    if times:
        return {
            'implementation': 'Python',
            'iterations': iterations,
            'min_time': min(times),
            'max_time': max(times),
            'avg_time': statistics.mean(times),
            'median_time': statistics.median(times),
            'total_records': results.get('total_records', 0) if results else 0,
            'outliers_detected': results.get('outliers_detected', 0) if results else 0
        }
    return None


def test_sql_implementation(db_manager, start_date, end_date, use_cache=True, iterations=3):
    """Test SQL-optimized Southern Baseline Rules implementation"""
    from shared.southern_baseline_api import SouthernBaselineAPI

    times = []
    results = None

    api = SouthernBaselineAPI(db_manager)

    for i in range(iterations):
        logger.info(f"SQL test iteration {i+1}/{iterations} (cache={use_cache})")
        start_time = time.time()

        try:
            results = api.get_outliers(
                start_date=start_date,
                end_date=end_date,
                station="All Stations",
                use_cache=use_cache
            )

            duration = time.time() - start_time
            times.append(duration)
            logger.info(f"  Completed in {duration:.3f}s")

        except Exception as e:
            logger.error(f"Error in SQL test: {e}")
            return None

    if times:
        return {
            'implementation': f'SQL (cache={use_cache})',
            'iterations': iterations,
            'min_time': min(times),
            'max_time': max(times),
            'avg_time': statistics.mean(times),
            'median_time': statistics.median(times),
            'total_records': results.get('total_records', 0) if results else 0,
            'outliers_detected': results.get('outliers_detected', 0) if results else 0,
            'used_cache': results.get('performance', {}).get('used_cache', False) if results else False
        }
    return None


def run_performance_tests():
    """Run comprehensive performance tests"""
    print("=" * 80)
    print("SOUTHERN BASELINE RULES - PERFORMANCE TEST")
    print("=" * 80)
    print()

    # Initialize database connection
    try:
        from shared.database import db_manager
        if not db_manager or not db_manager.engine:
            print("[ERROR] Database connection not available")
            print("Please configure DB_URI in .env file")
            return
    except Exception as e:
        print(f"[ERROR] Failed to import database manager: {e}")
        return

    print("[OK] Database connected")
    print()

    # Test scenarios with different date ranges
    test_scenarios = [
        {
            'name': '7-day range',
            'days': 7,
            'description': 'Recent data (typical dashboard view)'
        },
        {
            'name': '30-day range',
            'days': 30,
            'description': 'Monthly view (cache enabled)'
        },
        {
            'name': '90-day range',
            'days': 90,
            'description': 'Quarterly view (no cache)'
        }
    ]

    all_results = []

    for scenario in test_scenarios:
        print("-" * 80)
        print(f"Test Scenario: {scenario['name']}")
        print(f"Description: {scenario['description']}")
        print("-" * 80)

        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=scenario['days'])).strftime('%Y-%m-%d')

        print(f"Date range: {start_date} to {end_date}")
        print()

        # Test 1: Python implementation
        print("Testing Python implementation...")
        python_result = test_python_implementation(db_manager, start_date, end_date, iterations=3)

        if python_result:
            all_results.append(python_result)
            print(f"  Average time: {python_result['avg_time']:.3f}s")
            print(f"  Records: {python_result['total_records']}")
            print(f"  Outliers: {python_result['outliers_detected']}")
        else:
            print("  [FAILED]")

        print()

        # Test 2: SQL implementation with cache (if applicable)
        use_cache = scenario['days'] <= 30

        print(f"Testing SQL implementation (cache={use_cache})...")
        sql_result = test_sql_implementation(db_manager, start_date, end_date, use_cache=use_cache, iterations=3)

        if sql_result:
            all_results.append(sql_result)
            print(f"  Average time: {sql_result['avg_time']:.3f}s")
            print(f"  Records: {sql_result['total_records']}")
            print(f"  Outliers: {sql_result['outliers_detected']}")
            print(f"  Used cache: {sql_result['used_cache']}")

            # Calculate speedup
            if python_result:
                speedup = python_result['avg_time'] / sql_result['avg_time']
                improvement = (1 - sql_result['avg_time'] / python_result['avg_time']) * 100
                print(f"  Speedup: {speedup:.1f}x faster ({improvement:.1f}% improvement)")
        else:
            print("  [FAILED]")

        print()

    # Summary Report
    print("=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)
    print()

    if all_results:
        print(f"{'Implementation':<30} {'Avg Time':<15} {'Min Time':<15} {'Max Time':<15}")
        print("-" * 80)

        for result in all_results:
            print(f"{result['implementation']:<30} "
                  f"{result['avg_time']:<15.3f} "
                  f"{result['min_time']:<15.3f} "
                  f"{result['max_time']:<15.3f}")

        print()

        # Calculate overall improvement
        python_results = [r for r in all_results if r['implementation'] == 'Python']
        sql_results = [r for r in all_results if 'SQL' in r['implementation']]

        if python_results and sql_results:
            avg_python = statistics.mean([r['avg_time'] for r in python_results])
            avg_sql = statistics.mean([r['avg_time'] for r in sql_results])
            overall_speedup = avg_python / avg_sql
            overall_improvement = (1 - avg_sql / avg_python) * 100

            print(f"Overall Performance Improvement:")
            print(f"  Python average:  {avg_python:.3f}s")
            print(f"  SQL average:     {avg_sql:.3f}s")
            print(f"  Speedup:         {overall_speedup:.1f}x faster")
            print(f"  Improvement:     {overall_improvement:.1f}%")

    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


def refresh_materialized_view():
    """Refresh the materialized view before testing"""
    try:
        from shared.database import db_manager
        from shared.southern_baseline_api import SouthernBaselineAPI

        if not db_manager or not db_manager.engine:
            print("[ERROR] Database connection not available")
            return False

        print("Refreshing materialized view cache...")
        api = SouthernBaselineAPI(db_manager)
        result = api.refresh_cache()

        if result.get('success'):
            print(f"[OK] Cache refreshed in {result.get('refresh_time_seconds', 0):.3f}s")
            return True
        else:
            print(f"[ERROR] Failed to refresh cache: {result.get('error')}")
            return False

    except Exception as e:
        print(f"[ERROR] Exception refreshing cache: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SOUTHERN BASELINE RULES - PERFORMANCE TEST SUITE")
    print("=" * 80)
    print()

    # Step 1: Refresh cache
    print("Step 1: Refreshing materialized view cache...")
    if refresh_materialized_view():
        print()
    else:
        print("[WARN] Cache refresh failed, continuing anyway...")
        print()

    # Step 2: Run performance tests
    print("Step 2: Running performance tests...")
    print()

    try:
        run_performance_tests()
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Test cancelled by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
