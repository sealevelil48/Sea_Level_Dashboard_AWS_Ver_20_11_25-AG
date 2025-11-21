#!/usr/bin/env python3
"""
Performance Optimization Implementation
=======================================

Comprehensive performance improvements for Sea Level Dashboard:
1. Database query optimization with indexes
2. Response caching layer
3. Query batching and pagination
4. Data compression
5. Connection pooling optimization

This module implements the top priority optimizations identified in the audit.
"""

import os
import sys
import time
import json
import gzip
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from functools import wraps
from contextlib import contextmanager

# Performance monitoring
logger = logging.getLogger(__name__)

# ============================================================================
# OPTIMIZATION 1: Database Query Optimization
# ============================================================================

class DatabaseOptimizer:
    """Optimize database queries and index management"""

    def __init__(self, engine):
        self.engine = engine
        self.query_cache = {}
        self.cache_ttl = 300  # 5 minutes

    def create_performance_indexes(self):
        """Create all performance-critical indexes"""

        indexes = [
            # Monitors_info2 indexes for faster queries
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_datetime_desc ON "Monitors_info2" ("Tab_DateTime" DESC)',
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_tag_datetime ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime")',
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_value_notnull ON "Monitors_info2" ("Tab_Value_mDepthC1") WHERE "Tab_Value_mDepthC1" IS NOT NULL',

            # SeaTides indexes
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_station_date ON "SeaTides" ("Station", "Date")',
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_date_desc ON "SeaTides" ("Date" DESC)',

            # Locations index
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_locations_tag ON "Locations" ("Tab_TabularTag")',
        ]

        results = []
        with self.engine.connect() as conn:
            for idx_sql in indexes:
                try:
                    logger.info(f"Creating index: {idx_sql[:80]}...")
                    conn.execute(idx_sql)
                    conn.commit()
                    results.append({"status": "success", "sql": idx_sql})
                except Exception as e:
                    logger.warning(f"Index creation skipped: {e}")
                    results.append({"status": "skipped", "sql": idx_sql, "error": str(e)})

        return results

    def optimize_query_with_limit(self, query: str, limit: int = 15000) -> str:
        """Add LIMIT clause to queries if not present"""
        if "LIMIT" not in query.upper():
            query = f"{query} LIMIT {limit}"
        return query

    def get_query_plan(self, query: str) -> Dict:
        """Get EXPLAIN ANALYZE for a query"""
        with self.engine.connect() as conn:
            result = conn.execute(f"EXPLAIN ANALYZE {query}")
            return {"plan": [row[0] for row in result]}


# ============================================================================
# OPTIMIZATION 2: Enhanced Caching Layer with Redis Support
# ============================================================================

class PerformanceCache:
    """High-performance caching with TTL and automatic cleanup"""

    def __init__(self, redis_client=None, default_ttl=300):
        self.redis_client = redis_client
        self.memory_cache = {}
        self.default_ttl = default_ttl
        self.max_memory_cache_size = 1000

        # Performance metrics
        self.hits = 0
        self.misses = 0
        self.total_requests = 0

    def _cleanup_expired(self):
        """Remove expired cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, data in self.memory_cache.items()
            if current_time > data['expires_at']
        ]
        for key in expired_keys:
            del self.memory_cache[key]

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (Redis first, then memory)"""
        self.total_requests += 1

        # Try Redis first
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value:
                    self.hits += 1
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Redis get error: {e}")

        # Fallback to memory cache
        self._cleanup_expired()
        if key in self.memory_cache:
            data = self.memory_cache[key]
            if time.time() <= data['expires_at']:
                self.hits += 1
                return data['value']
            else:
                del self.memory_cache[key]

        self.misses += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache (both Redis and memory)"""
        ttl = ttl or self.default_ttl

        # Set in Redis
        if self.redis_client:
            try:
                self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(value, default=str)
                )
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        # Set in memory cache
        self._cleanup_expired()
        if len(self.memory_cache) >= self.max_memory_cache_size:
            # Remove oldest 20% of entries
            sorted_items = sorted(
                self.memory_cache.items(),
                key=lambda x: x[1]['created_at']
            )
            for k, _ in sorted_items[:int(self.max_memory_cache_size * 0.2)]:
                del self.memory_cache[k]

        self.memory_cache[key] = {
            'value': value,
            'created_at': time.time(),
            'expires_at': time.time() + ttl
        }

    def delete(self, key: str):
        """Delete key from cache"""
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception:
                pass

        if key in self.memory_cache:
            del self.memory_cache[key]

    def clear(self):
        """Clear all cache"""
        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception:
                pass

        self.memory_cache.clear()

    def get_metrics(self) -> Dict:
        """Get cache performance metrics"""
        hit_rate = (self.hits / self.total_requests * 100) if self.total_requests > 0 else 0

        return {
            'total_requests': self.total_requests,
            'cache_hits': self.hits,
            'cache_misses': self.misses,
            'hit_rate': f"{hit_rate:.2f}%",
            'memory_cache_size': len(self.memory_cache),
            'redis_enabled': self.redis_client is not None
        }


# ============================================================================
# OPTIMIZATION 3: Response Compression
# ============================================================================

def compress_response(data: Dict) -> bytes:
    """Compress JSON response with gzip"""
    json_str = json.dumps(data, default=str)
    return gzip.compress(json_str.encode('utf-8'))


def decompress_response(compressed_data: bytes) -> Dict:
    """Decompress gzip JSON response"""
    json_str = gzip.decompress(compressed_data).decode('utf-8')
    return json.loads(json_str)


# ============================================================================
# OPTIMIZATION 4: Query Batching
# ============================================================================

class QueryBatcher:
    """Batch multiple queries into single database roundtrip"""

    def __init__(self, engine):
        self.engine = engine

    def batch_station_data(self, stations: List[str], start_date: str, end_date: str) -> Dict:
        """Fetch data for multiple stations in single query"""

        from sqlalchemy import text

        query = text("""
            SELECT
                "Tab_TabularTag" as station,
                "Tab_DateTime" as timestamp,
                "Tab_Value_mDepthC1" as value,
                "Tab_TempC1" as temperature
            FROM "Monitors_info2"
            WHERE "Tab_TabularTag" = ANY(:stations)
              AND "Tab_DateTime" BETWEEN :start_date AND :end_date
              AND "Tab_Value_mDepthC1" IS NOT NULL
            ORDER BY "Tab_DateTime" DESC
            LIMIT 50000
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {
                'stations': stations,
                'start_date': start_date,
                'end_date': end_date
            })

            # Group by station
            data_by_station = {}
            for row in result:
                station = row.station
                if station not in data_by_station:
                    data_by_station[station] = []

                data_by_station[station].append({
                    'timestamp': row.timestamp.isoformat() if row.timestamp else None,
                    'value': float(row.value) if row.value else None,
                    'temperature': float(row.temperature) if row.temperature else None
                })

        return data_by_station


# ============================================================================
# OPTIMIZATION 5: Connection Pool Optimization
# ============================================================================

def optimize_connection_pool(engine):
    """Configure optimal connection pool settings"""

    # SQLAlchemy connection pool settings
    pool_config = {
        'pool_size': 20,           # Increase base pool size
        'max_overflow': 10,        # Allow 10 additional connections
        'pool_timeout': 30,        # Connection timeout
        'pool_recycle': 3600,      # Recycle connections every hour
        'pool_pre_ping': True,     # Test connections before use
    }

    logger.info(f"Optimized connection pool: {pool_config}")
    return pool_config


# ============================================================================
# OPTIMIZATION 6: Performance Monitoring Decorator
# ============================================================================

def monitor_performance(func):
    """Decorator to monitor function performance"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = 0

        try:
            import psutil
            process = psutil.Process()
            start_memory = process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            pass

        result = func(*args, **kwargs)

        duration = time.time() - start_time

        try:
            import psutil
            process = psutil.Process()
            end_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = end_memory - start_memory

            logger.info(
                f"[PERF] {func.__name__}: {duration*1000:.2f}ms, "
                f"Memory: {memory_used:.2f}MB"
            )
        except ImportError:
            logger.info(f"[PERF] {func.__name__}: {duration*1000:.2f}ms")

        return result

    return wrapper


# ============================================================================
# OPTIMIZATION 7: Data Pagination Helper
# ============================================================================

class PaginationHelper:
    """Efficient pagination for large datasets"""

    @staticmethod
    def paginate_query(query: str, page: int = 1, per_page: int = 100) -> str:
        """Add pagination to SQL query"""
        offset = (page - 1) * per_page
        return f"{query} LIMIT {per_page} OFFSET {offset}"

    @staticmethod
    def paginate_list(data: List, page: int = 1, per_page: int = 100) -> Dict:
        """Paginate a Python list"""
        total = len(data)
        total_pages = (total + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page

        return {
            'data': data[start:end],
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }


# ============================================================================
# OPTIMIZATION 8: Slow Query Detection
# ============================================================================

class SlowQueryDetector:
    """Detect and log slow database queries"""

    def __init__(self, threshold_ms: float = 1000):
        self.threshold_ms = threshold_ms
        self.slow_queries = []

    @contextmanager
    def track_query(self, query_name: str):
        """Context manager to track query execution time"""
        start_time = time.time()

        try:
            yield
        finally:
            duration = (time.time() - start_time) * 1000

            if duration > self.threshold_ms:
                self.slow_queries.append({
                    'query': query_name,
                    'duration_ms': duration,
                    'timestamp': datetime.now().isoformat()
                })
                logger.warning(
                    f"[SLOW QUERY] {query_name} took {duration:.2f}ms "
                    f"(threshold: {self.threshold_ms}ms)"
                )

    def get_slow_queries(self) -> List[Dict]:
        """Get list of slow queries"""
        return self.slow_queries

    def reset(self):
        """Reset slow query tracking"""
        self.slow_queries = []


# ============================================================================
# Performance Testing Utilities
# ============================================================================

class PerformanceBenchmark:
    """Benchmark database and API performance"""

    def __init__(self, engine):
        self.engine = engine
        self.results = {}

    def benchmark_query(self, query_name: str, query: str, iterations: int = 10) -> Dict:
        """Benchmark a SQL query"""
        from sqlalchemy import text

        times = []

        for i in range(iterations):
            start = time.time()

            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                rows = result.fetchall()

            duration = time.time() - start
            times.append(duration * 1000)  # Convert to ms

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        benchmark_result = {
            'query_name': query_name,
            'iterations': iterations,
            'avg_time_ms': round(avg_time, 2),
            'min_time_ms': round(min_time, 2),
            'max_time_ms': round(max_time, 2),
            'row_count': len(rows) if 'rows' in locals() else 0
        }

        self.results[query_name] = benchmark_result
        logger.info(f"Benchmark: {query_name} - Avg: {avg_time:.2f}ms")

        return benchmark_result

    def get_all_results(self) -> Dict:
        """Get all benchmark results"""
        return self.results


# ============================================================================
# Usage Examples
# ============================================================================

def example_usage():
    """Example usage of performance optimizations"""

    # Example 1: Database optimization
    from sqlalchemy import create_engine
    engine = create_engine('postgresql://user:pass@localhost/db')

    optimizer = DatabaseOptimizer(engine)
    optimizer.create_performance_indexes()

    # Example 2: Caching
    cache = PerformanceCache(default_ttl=300)
    cache.set('stations', ['Haifa', 'Acre', 'Ashdod'])
    stations = cache.get('stations')
    print(f"Cache metrics: {cache.get_metrics()}")

    # Example 3: Query batching
    batcher = QueryBatcher(engine)
    data = batcher.batch_station_data(
        ['Haifa', 'Acre'],
        '2025-11-01',
        '2025-11-20'
    )

    # Example 4: Performance monitoring
    @monitor_performance
    def expensive_operation():
        time.sleep(0.1)
        return "done"

    expensive_operation()

    # Example 5: Slow query detection
    detector = SlowQueryDetector(threshold_ms=500)
    with detector.track_query("test_query"):
        time.sleep(0.6)

    print(f"Slow queries: {detector.get_slow_queries()}")


if __name__ == '__main__':
    example_usage()
