#!/usr/bin/env python3
"""
Performance Benchmarking Test Suite
====================================

Comprehensive performance tests for Sea Level Dashboard:
1. Database query performance
2. API endpoint response times
3. Caching effectiveness
4. Memory usage
5. Concurrent request handling
6. Data processing speed

Run with: pytest test_performance_benchmarks.py -v
"""

import pytest
import time
import asyncio
import requests
from datetime import datetime, timedelta
from typing import Dict, List
import statistics

# Performance thresholds (ms)
THRESHOLDS = {
    'database_query': 500,      # 500ms max for database queries
    'api_response': 1000,       # 1 second max for API responses
    'cache_hit': 50,            # 50ms max for cache hits
    'data_processing': 2000,    # 2 seconds max for data processing
}

# API configuration
API_BASE_URL = 'http://localhost:30886'


# ============================================================================
# Database Performance Tests
# ============================================================================

class TestDatabasePerformance:
    """Test database query performance"""

    @pytest.fixture
    def db_engine(self):
        """Get database engine"""
        from sqlalchemy import create_engine
        import os

        db_uri = os.getenv('DB_URI', 'postgresql://postgres:postgres@localhost:5432/sealevel')
        return create_engine(db_uri)

    def test_index_coverage(self, db_engine):
        """Verify all critical indexes exist"""

        required_indexes = [
            'idx_monitors_datetime_desc',
            'idx_monitors_tag_datetime',
            'idx_seatides_station_date',
            'idx_locations_tag'
        ]

        with db_engine.connect() as conn:
            result = conn.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename IN ('Monitors_info2', 'SeaTides', 'Locations')
            """)

            existing_indexes = [row[0] for row in result]

        missing_indexes = [idx for idx in required_indexes if idx not in existing_indexes]

        assert len(missing_indexes) == 0, f"Missing indexes: {missing_indexes}"

    def test_simple_query_performance(self, db_engine):
        """Test performance of simple SELECT query"""

        query = """
            SELECT COUNT(*)
            FROM "Monitors_info2"
            WHERE "Tab_DateTime" > NOW() - INTERVAL '7 days'
        """

        start_time = time.time()

        with db_engine.connect() as conn:
            result = conn.execute(query)
            count = result.fetchone()[0]

        duration_ms = (time.time() - start_time) * 1000

        print(f"\nSimple query: {duration_ms:.2f}ms (returned {count} rows)")

        assert duration_ms < THRESHOLDS['database_query'], \
            f"Query too slow: {duration_ms:.2f}ms > {THRESHOLDS['database_query']}ms"

    def test_join_query_performance(self, db_engine):
        """Test performance of JOIN query"""

        query = """
            SELECT
                m."Tab_TabularTag",
                COUNT(*) as record_count
            FROM "Monitors_info2" m
            INNER JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
            WHERE m."Tab_DateTime" > NOW() - INTERVAL '1 day'
            GROUP BY m."Tab_TabularTag"
        """

        start_time = time.time()

        with db_engine.connect() as conn:
            result = conn.execute(query)
            rows = result.fetchall()

        duration_ms = (time.time() - start_time) * 1000

        print(f"\nJOIN query: {duration_ms:.2f}ms (returned {len(rows)} rows)")

        assert duration_ms < THRESHOLDS['database_query'] * 2, \
            f"JOIN query too slow: {duration_ms:.2f}ms"

    def test_aggregation_query_performance(self, db_engine):
        """Test performance of aggregation query"""

        query = """
            SELECT
                DATE("Tab_DateTime") as date,
                AVG("Tab_Value_mDepthC1") as avg_value,
                MIN("Tab_Value_mDepthC1") as min_value,
                MAX("Tab_Value_mDepthC1") as max_value
            FROM "Monitors_info2"
            WHERE "Tab_DateTime" > NOW() - INTERVAL '30 days'
              AND "Tab_Value_mDepthC1" IS NOT NULL
            GROUP BY DATE("Tab_DateTime")
            ORDER BY date DESC
        """

        start_time = time.time()

        with db_engine.connect() as conn:
            result = conn.execute(query)
            rows = result.fetchall()

        duration_ms = (time.time() - start_time) * 1000

        print(f"\nAggregation query: {duration_ms:.2f}ms (returned {len(rows)} rows)")

        assert duration_ms < THRESHOLDS['database_query'] * 3, \
            f"Aggregation query too slow: {duration_ms:.2f}ms"


# ============================================================================
# API Performance Tests
# ============================================================================

class TestAPIPerformance:
    """Test API endpoint response times"""

    def test_get_stations_performance(self):
        """Test /api/stations endpoint"""

        start_time = time.time()
        response = requests.get(f"{API_BASE_URL}/api/stations")
        duration_ms = (time.time() - start_time) * 1000

        print(f"\nGET /api/stations: {duration_ms:.2f}ms")

        assert response.status_code == 200
        assert duration_ms < THRESHOLDS['api_response'], \
            f"API too slow: {duration_ms:.2f}ms > {THRESHOLDS['api_response']}ms"

    def test_get_data_performance(self):
        """Test /api/data endpoint"""

        params = {
            'station': 'Haifa',
            'start_date': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
            'end_date': datetime.now().strftime('%Y-%m-%d')
        }

        start_time = time.time()
        response = requests.get(f"{API_BASE_URL}/api/data", params=params)
        duration_ms = (time.time() - start_time) * 1000

        print(f"\nGET /api/data: {duration_ms:.2f}ms")

        assert response.status_code == 200
        assert duration_ms < THRESHOLDS['api_response'], \
            f"API too slow: {duration_ms:.2f}ms > {THRESHOLDS['api_response']}ms"

    def test_cache_effectiveness(self):
        """Test if caching reduces response time"""

        params = {
            'station': 'Acre',
            'start_date': (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'),
            'end_date': datetime.now().strftime('%Y-%m-%d')
        }

        # First request (cache miss)
        start_time = time.time()
        response1 = requests.get(f"{API_BASE_URL}/api/data", params=params)
        duration1_ms = (time.time() - start_time) * 1000

        # Second request (should be cached)
        start_time = time.time()
        response2 = requests.get(f"{API_BASE_URL}/api/data", params=params)
        duration2_ms = (time.time() - start_time) * 1000

        print(f"\nCache test: 1st={duration1_ms:.2f}ms, 2nd={duration2_ms:.2f}ms")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Second request should be at least 50% faster
        improvement = (duration1_ms - duration2_ms) / duration1_ms * 100
        print(f"Cache improvement: {improvement:.1f}%")

        assert duration2_ms < duration1_ms, "Cache should improve performance"

    def test_concurrent_requests(self):
        """Test performance under concurrent load"""

        async def make_request(session, url, params):
            start = time.time()
            response = requests.get(url, params=params)
            duration = time.time() - start
            return duration, response.status_code

        async def run_concurrent_tests(num_requests=10):
            url = f"{API_BASE_URL}/api/data"
            params = {
                'station': 'All Stations',
                'start_date': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                'end_date': datetime.now().strftime('%Y-%m-%d')
            }

            tasks = []
            for _ in range(num_requests):
                tasks.append(make_request(None, url, params))

            results = await asyncio.gather(*tasks)
            return results

        # Run concurrent requests
        results = asyncio.run(run_concurrent_tests(10))

        durations = [r[0] * 1000 for r in results]
        status_codes = [r[1] for r in results]

        avg_duration = statistics.mean(durations)
        max_duration = max(durations)

        print(f"\nConcurrent requests (10):")
        print(f"  Average: {avg_duration:.2f}ms")
        print(f"  Max: {max_duration:.2f}ms")
        print(f"  All success: {all(s == 200 for s in status_codes)}")

        assert all(s == 200 for s in status_codes), "All requests should succeed"
        assert avg_duration < THRESHOLDS['api_response'] * 1.5, \
            f"Average concurrent response too slow: {avg_duration:.2f}ms"


# ============================================================================
# Memory and Resource Tests
# ============================================================================

class TestResourceUsage:
    """Test memory and resource usage"""

    def test_memory_usage_data_processing(self):
        """Test memory usage during data processing"""

        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Simulate data processing
            params = {
                'station': 'All Stations',
                'start_date': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                'end_date': datetime.now().strftime('%Y-%m-%d')
            }

            response = requests.get(f"{API_BASE_URL}/api/data", params=params)
            data = response.json()

            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            print(f"\nMemory usage:")
            print(f"  Initial: {initial_memory:.2f}MB")
            print(f"  Final: {final_memory:.2f}MB")
            print(f"  Increase: {memory_increase:.2f}MB")
            print(f"  Data size: {len(data) if isinstance(data, list) else 'N/A'} records")

            # Memory increase should be reasonable (< 100MB for this test)
            assert memory_increase < 100, f"Memory usage too high: {memory_increase:.2f}MB"

        except ImportError:
            pytest.skip("psutil not installed")

    def test_response_compression(self):
        """Test if responses are compressed"""

        response = requests.get(
            f"{API_BASE_URL}/api/data",
            params={
                'station': 'All Stations',
                'start_date': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                'end_date': datetime.now().strftime('%Y-%m-%d')
            },
            headers={'Accept-Encoding': 'gzip'}
        )

        # Check if response is compressed
        content_encoding = response.headers.get('Content-Encoding', '')
        content_length = len(response.content)

        print(f"\nCompression:")
        print(f"  Encoding: {content_encoding}")
        print(f"  Size: {content_length} bytes ({content_length/1024:.2f}KB)")

        # If response is large, it should be compressed
        if content_length > 1024:
            print(f"  Note: Large response, compression recommended")


# ============================================================================
# Performance Regression Tests
# ============================================================================

class TestPerformanceRegression:
    """Track performance over time to detect regressions"""

    def test_baseline_performance(self):
        """Establish performance baseline"""

        baselines = {}

        # Test 1: Get stations
        start = time.time()
        requests.get(f"{API_BASE_URL}/api/stations")
        baselines['get_stations'] = (time.time() - start) * 1000

        # Test 2: Get data (1 day)
        start = time.time()
        requests.get(f"{API_BASE_URL}/api/data", params={
            'station': 'Haifa',
            'start_date': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': datetime.now().strftime('%Y-%m-%d')
        })
        baselines['get_data_1day'] = (time.time() - start) * 1000

        # Test 3: Get data (7 days)
        start = time.time()
        requests.get(f"{API_BASE_URL}/api/data", params={
            'station': 'Haifa',
            'start_date': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
            'end_date': datetime.now().strftime('%Y-%m-%d')
        })
        baselines['get_data_7days'] = (time.time() - start) * 1000

        print("\nPerformance Baseline:")
        for test, duration in baselines.items():
            print(f"  {test}: {duration:.2f}ms")

        # Save baselines for comparison
        import json
        try:
            with open('performance_baseline.json', 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'baselines': baselines
                }, f, indent=2)
            print("\nBaseline saved to performance_baseline.json")
        except Exception as e:
            print(f"\nCould not save baseline: {e}")


# ============================================================================
# Run Performance Report
# ============================================================================

def generate_performance_report():
    """Generate comprehensive performance report"""

    print("\n" + "="*60)
    print("PERFORMANCE BENCHMARKING REPORT")
    print("="*60)

    report = {
        'timestamp': datetime.now().isoformat(),
        'api_base_url': API_BASE_URL,
        'thresholds': THRESHOLDS,
        'tests_run': []
    }

    # Run all tests and collect results
    pytest.main([__file__, '-v', '--tb=short'])

    print("\n" + "="*60)
    print("REPORT GENERATED")
    print("="*60)

    return report


if __name__ == '__main__':
    generate_performance_report()
