#!/usr/bin/env python3
"""
Enhanced API Performance Module
================================

Additional performance optimizations:
1. Request batching and aggregation
2. Response compression (gzip)
3. Smart query optimization
4. Connection pooling
5. Rate limiting
6. Response streaming for large datasets

Integration with FastAPI server for maximum performance.
"""

import json
import gzip
import time
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

from fastapi import Response, Request
from fastapi.responses import StreamingResponse
import asyncio

logger = logging.getLogger(__name__)

# ============================================================================
# OPTIMIZATION 1: Response Compression Middleware
# ============================================================================

class CompressionMiddleware:
    """Automatic gzip compression for large responses"""

    def __init__(self, min_size_bytes: int = 1024):
        self.min_size_bytes = min_size_bytes

    async def compress_response(self, response_body: bytes, accept_encoding: str) -> Union[bytes, Response]:
        """Compress response if client accepts gzip and response is large enough"""

        if 'gzip' in accept_encoding and len(response_body) >= self.min_size_bytes:
            compressed = gzip.compress(response_body)

            # Only compress if it reduces size by at least 10%
            if len(compressed) < len(response_body) * 0.9:
                logger.info(
                    f"Compressed response: {len(response_body)} -> {len(compressed)} bytes "
                    f"({(1 - len(compressed)/len(response_body))*100:.1f}% reduction)"
                )
                return Response(
                    content=compressed,
                    headers={'Content-Encoding': 'gzip'},
                    media_type='application/json'
                )

        return response_body


# ============================================================================
# OPTIMIZATION 2: Request Batching
# ============================================================================

class RequestBatcher:
    """Batch multiple API requests into single database query"""

    def __init__(self):
        self.pending_requests = defaultdict(list)
        self.batch_delay = 0.05  # 50ms batching window
        self.batch_timers = {}

    async def add_request(self, request_type: str, params: Dict, callback):
        """Add request to batch queue"""

        request_key = f"{request_type}:{json.dumps(params, sort_keys=True)}"

        # If identical request exists, reuse result
        if request_key in self.pending_requests:
            self.pending_requests[request_key].append(callback)
            return

        self.pending_requests[request_key] = [callback]

        # Start batch timer if not already running
        if request_type not in self.batch_timers:
            self.batch_timers[request_type] = asyncio.create_task(
                self._process_batch_after_delay(request_type)
            )

    async def _process_batch_after_delay(self, request_type: str):
        """Process batched requests after delay"""
        await asyncio.sleep(self.batch_delay)

        # Collect all pending requests of this type
        requests_to_process = [
            (key, callbacks) for key, callbacks in self.pending_requests.items()
            if key.startswith(f"{request_type}:")
        ]

        # Clear pending requests
        for key, _ in requests_to_process:
            del self.pending_requests[key]

        # Process batch
        await self._execute_batch(request_type, requests_to_process)

        # Clear timer
        if request_type in self.batch_timers:
            del self.batch_timers[request_type]

    async def _execute_batch(self, request_type: str, requests: List):
        """Execute batched requests"""
        logger.info(f"Processing batch of {len(requests)} {request_type} requests")

        # Implement batch execution logic here
        # This would call optimized bulk query methods

        for request_key, callbacks in requests:
            # Execute request and call all callbacks with result
            try:
                # Mock result - replace with actual batch query
                result = {"status": "success", "data": []}

                for callback in callbacks:
                    callback(result)

            except Exception as e:
                logger.error(f"Batch request failed: {e}")
                for callback in callbacks:
                    callback({"status": "error", "error": str(e)})


# ============================================================================
# OPTIMIZATION 3: Response Streaming for Large Datasets
# ============================================================================

class StreamingResponseBuilder:
    """Stream large responses instead of buffering entire response in memory"""

    @staticmethod
    async def stream_json_array(items: List[Dict], chunk_size: int = 100):
        """Stream JSON array in chunks"""

        async def generate():
            yield b'['

            for i, item in enumerate(items):
                if i > 0:
                    yield b','

                yield json.dumps(item, default=str).encode('utf-8')

                # Yield control every chunk_size items
                if (i + 1) % chunk_size == 0:
                    await asyncio.sleep(0)

            yield b']'

        return StreamingResponse(
            generate(),
            media_type='application/json',
            headers={'X-Stream-Mode': 'chunked'}
        )

    @staticmethod
    async def stream_csv(data: List[Dict], headers: List[str]):
        """Stream CSV data"""

        async def generate():
            # Header row
            yield ','.join(headers).encode('utf-8') + b'\n'

            # Data rows
            for row in data:
                csv_row = ','.join(str(row.get(h, '')) for h in headers)
                yield csv_row.encode('utf-8') + b'\n'

                await asyncio.sleep(0)  # Yield control

        return StreamingResponse(
            generate(),
            media_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="data.csv"'}
        )


# ============================================================================
# OPTIMIZATION 4: Query Result Caching with Smart Invalidation
# ============================================================================

class SmartQueryCache:
    """Intelligent caching with automatic invalidation"""

    def __init__(self):
        self.cache = {}
        self.dependencies = defaultdict(set)  # Track cache dependencies
        self.access_counts = defaultdict(int)
        self.last_access = {}

    def get(self, key: str) -> Optional[Any]:
        """Get from cache and update access stats"""
        if key in self.cache:
            entry = self.cache[key]

            # Check if expired
            if time.time() > entry['expires_at']:
                del self.cache[key]
                return None

            # Update access stats
            self.access_counts[key] += 1
            self.last_access[key] = time.time()

            return entry['value']

        return None

    def set(self, key: str, value: Any, ttl: int = 300, dependencies: List[str] = None):
        """Set cache with dependencies"""
        self.cache[key] = {
            'value': value,
            'expires_at': time.time() + ttl,
            'created_at': time.time()
        }

        # Track dependencies
        if dependencies:
            for dep in dependencies:
                self.dependencies[dep].add(key)

    def invalidate(self, pattern: str):
        """Invalidate cache entries by pattern"""
        keys_to_delete = []

        # Direct pattern match
        for key in self.cache.keys():
            if pattern in key:
                keys_to_delete.append(key)

        # Dependency-based invalidation
        if pattern in self.dependencies:
            keys_to_delete.extend(self.dependencies[pattern])
            del self.dependencies[pattern]

        # Delete all matched keys
        for key in keys_to_delete:
            if key in self.cache:
                del self.cache[key]
                logger.info(f"Invalidated cache: {key}")

        return len(keys_to_delete)

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_size = sum(
            len(json.dumps(entry['value'], default=str))
            for entry in self.cache.values()
        )

        return {
            'total_entries': len(self.cache),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / 1024 / 1024, 2),
            'most_accessed': sorted(
                self.access_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }


# ============================================================================
# OPTIMIZATION 5: Database Query Optimizer
# ============================================================================

class QueryOptimizer:
    """Optimize SQL queries automatically"""

    @staticmethod
    def add_query_hints(query: str, hints: Dict[str, Any]) -> str:
        """Add PostgreSQL query hints"""

        optimizations = []

        # Add indexes hint
        if hints.get('use_index'):
            index_name = hints['use_index']
            optimizations.append(f"/*+ IndexScan({index_name}) */")

        # Add join order hint
        if hints.get('join_order'):
            order = hints['join_order']
            optimizations.append(f"/*+ Leading({order}) */")

        # Add parallel execution hint
        if hints.get('parallel', False):
            optimizations.append("/*+ Parallel */")

        if optimizations:
            hint_str = ' '.join(optimizations)
            return f"{hint_str} {query}"

        return query

    @staticmethod
    def optimize_date_range_query(table: str, date_column: str, start: str, end: str) -> str:
        """Generate optimized date range query"""

        return f"""
            SELECT *
            FROM "{table}"
            WHERE "{date_column}" BETWEEN '{start}' AND '{end}'
            ORDER BY "{date_column}" DESC
            LIMIT 15000
        """

    @staticmethod
    def add_pagination(query: str, page: int = 1, per_page: int = 100) -> str:
        """Add efficient pagination"""
        offset = (page - 1) * per_page

        return f"""
            {query}
            LIMIT {per_page}
            OFFSET {offset}
        """


# ============================================================================
# OPTIMIZATION 6: Connection Pool Manager
# ============================================================================

class ConnectionPoolManager:
    """Manage database connection pool"""

    def __init__(self, engine):
        self.engine = engine
        self.pool_stats = {
            'active_connections': 0,
            'idle_connections': 0,
            'total_checkouts': 0,
            'total_checkins': 0
        }

    def get_pool_status(self) -> Dict:
        """Get connection pool status"""

        pool = self.engine.pool

        return {
            'pool_size': pool.size(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'total_connections': pool.size() + pool.overflow(),
            'stats': self.pool_stats
        }

    def optimize_pool_size(self, target_utilization: float = 0.7):
        """Suggest optimal pool size based on usage"""

        status = self.get_pool_status()
        current_size = status['pool_size']
        checked_out = status['checked_out']

        utilization = checked_out / current_size if current_size > 0 else 0

        if utilization > target_utilization:
            suggested_size = int(current_size * (utilization / target_utilization))
            return {
                'current_size': current_size,
                'utilization': f"{utilization*100:.1f}%",
                'suggested_size': suggested_size,
                'action': 'increase'
            }
        elif utilization < target_utilization * 0.5:
            suggested_size = max(5, int(current_size * 0.75))
            return {
                'current_size': current_size,
                'utilization': f"{utilization*100:.1f}%",
                'suggested_size': suggested_size,
                'action': 'decrease'
            }

        return {
            'current_size': current_size,
            'utilization': f"{utilization*100:.1f}%",
            'suggested_size': current_size,
            'action': 'optimal'
        }


# ============================================================================
# OPTIMIZATION 7: Rate Limiting
# ============================================================================

class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, rate: int = 100, per: int = 60):
        """
        Args:
            rate: Maximum requests
            per: Time period in seconds
        """
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.time()

    async def check_rate_limit(self, client_id: str) -> bool:
        """Check if request is allowed"""

        current = time.time()
        time_passed = current - self.last_check
        self.last_check = current

        self.allowance += time_passed * (self.rate / self.per)

        if self.allowance > self.rate:
            self.allowance = self.rate

        if self.allowance < 1.0:
            logger.warning(f"Rate limit exceeded for {client_id}")
            return False

        self.allowance -= 1.0
        return True


# ============================================================================
# OPTIMIZATION 8: Performance Metrics Collector
# ============================================================================

class PerformanceMetricsCollector:
    """Collect and analyze API performance metrics"""

    def __init__(self):
        self.request_times = []
        self.endpoint_metrics = defaultdict(lambda: {
            'count': 0,
            'total_time': 0,
            'min_time': float('inf'),
            'max_time': 0,
            'errors': 0
        })

    def record_request(self, endpoint: str, duration: float, success: bool = True):
        """Record request metrics"""

        metrics = self.endpoint_metrics[endpoint]
        metrics['count'] += 1
        metrics['total_time'] += duration
        metrics['min_time'] = min(metrics['min_time'], duration)
        metrics['max_time'] = max(metrics['max_time'], duration)

        if not success:
            metrics['errors'] += 1

        # Keep last 1000 request times
        self.request_times.append({
            'endpoint': endpoint,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            'success': success
        })

        if len(self.request_times) > 1000:
            self.request_times.pop(0)

    def get_metrics(self) -> Dict:
        """Get aggregated metrics"""

        endpoint_stats = {}

        for endpoint, metrics in self.endpoint_metrics.items():
            if metrics['count'] > 0:
                avg_time = metrics['total_time'] / metrics['count']
                error_rate = (metrics['errors'] / metrics['count']) * 100

                endpoint_stats[endpoint] = {
                    'requests': metrics['count'],
                    'avg_time_ms': round(avg_time * 1000, 2),
                    'min_time_ms': round(metrics['min_time'] * 1000, 2),
                    'max_time_ms': round(metrics['max_time'] * 1000, 2),
                    'error_rate': f"{error_rate:.2f}%",
                    'errors': metrics['errors']
                }

        # Get recent slow requests
        slow_requests = [
            req for req in self.request_times
            if req['duration'] > 1.0  # >1 second
        ]

        return {
            'endpoints': endpoint_stats,
            'total_requests': len(self.request_times),
            'slow_requests_count': len(slow_requests),
            'slow_requests': slow_requests[-10:]  # Last 10 slow requests
        }

    def reset(self):
        """Reset all metrics"""
        self.request_times = []
        self.endpoint_metrics.clear()


# ============================================================================
# Decorator for Performance Tracking
# ============================================================================

metrics_collector = PerformanceMetricsCollector()

def track_performance(endpoint_name: str):
    """Decorator to track endpoint performance"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                metrics_collector.record_request(endpoint_name, duration, success)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                metrics_collector.record_request(endpoint_name, duration, success)

        # Return appropriate wrapper
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# ============================================================================
# Usage Example
# ============================================================================

if __name__ == '__main__':
    # Example: Performance tracking
    @track_performance('test_endpoint')
    def test_function():
        time.sleep(0.1)
        return {"data": "test"}

    test_function()

    print("Metrics:", metrics_collector.get_metrics())
