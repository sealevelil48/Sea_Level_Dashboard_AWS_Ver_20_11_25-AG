"""
Unified Database Manager
Consolidates database.py, database_optimized.py, database_production.py, and database_backup.py

This single module provides all database functionality with feature flags
for different deployment environments (development, production, AWS)
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import contextmanager

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime, Index
from sqlalchemy import select, and_, func, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.types import TypeDecorator, UserDefinedType
from sqlalchemy.exc import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)

# ============================================================================
# CUSTOM TYPES
# ============================================================================

class PointType(TypeDecorator):
    """
    Custom type for PostGIS POINT geometry
    Handles conversion between Python tuples and PostGIS point format
    """
    impl = UserDefinedType
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(String(255))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (tuple, list)) and len(value) == 2:
            return f"POINT({value[0]} {value[1]})"
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str) and value.startswith('POINT'):
            coords = value.replace('POINT(', '').replace(')', '').split()
            return (float(coords[0]), float(coords[1]))
        return value


# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """
    Unified database manager with:
    - Connection pooling
    - Redis caching
    - Query optimization
    - Health monitoring
    - Multi-environment support
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        enable_cache: bool = True,
        enable_pooling: bool = True,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        redis_url: Optional[str] = None,
        cache_ttl: int = 300  # 5 minutes default
    ):
        """
        Initialize database manager

        Args:
            database_url: Database connection string (falls back to env vars)
            enable_cache: Enable Redis caching
            enable_pooling: Enable connection pooling
            pool_size: Number of connections in pool
            max_overflow: Maximum overflow connections
            pool_timeout: Timeout for getting connection from pool
            redis_url: Redis connection string
            cache_ttl: Default cache TTL in seconds
        """
        self.database_url = database_url or self._get_database_url_from_env()
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self.redis_client = None
        self.engine = None
        self.Session = None
        self.metadata = MetaData()
        self.M = None  # Main sea level table
        self.L = None  # Lookup/reference table
        self.connected = False

        # Metrics tracking
        self.metrics = {
            'queries_executed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0,
            'last_query_time': None
        }

        # Initialize Redis cache if enabled
        if enable_cache:
            self._initialize_cache(redis_url)

        # Initialize database engine
        self._initialize_engine(enable_pooling, pool_size, max_overflow, pool_timeout)

    def _get_database_url_from_env(self) -> str:
        """Construct database URL from environment variables"""
        # Try direct DATABASE_URL first
        if os.getenv('DATABASE_URL'):
            return os.getenv('DATABASE_URL')

        # Construct from components
        db_type = os.getenv('DB_TYPE', 'postgresql')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'sea_level_db')
        db_user = os.getenv('DB_USER', 'postgres')
        db_pass = os.getenv('DB_PASSWORD', '')

        return f"{db_type}://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    def _initialize_cache(self, redis_url: Optional[str]):
        """Initialize Redis cache"""
        try:
            import redis
            redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info(f"[OK] Redis cache initialized: {redis_url}")
        except Exception as e:
            logger.warning(f"[WARN] Redis cache unavailable: {e}")
            self.enable_cache = False
            self.redis_client = None

    def _initialize_engine(self, enable_pooling: bool, pool_size: int,
                          max_overflow: int, pool_timeout: int):
        """Initialize SQLAlchemy engine with pooling"""
        try:
            engine_kwargs = {
                'echo': False,
                'future': True
            }

            if enable_pooling:
                engine_kwargs.update({
                    'poolclass': QueuePool,
                    'pool_size': pool_size,
                    'max_overflow': max_overflow,
                    'pool_timeout': pool_timeout,
                    'pool_pre_ping': True,  # Verify connections before use
                    'pool_recycle': 3600    # Recycle connections after 1 hour
                })
            else:
                engine_kwargs['poolclass'] = NullPool

            self.engine = create_engine(self.database_url, **engine_kwargs)

            # Create session factory
            session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
            self.Session = scoped_session(session_factory)

            # Load table metadata
            self._load_tables()

            self.connected = True
            logger.info(f"[OK] Database engine initialized with pooling={enable_pooling}")

        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize database: {e}")
            self.connected = False
            raise

    def _load_tables(self):
        """Load table definitions from database"""
        try:
            # Reflect existing tables
            self.metadata.reflect(bind=self.engine)

            # Get main sea level table
            table_name = os.getenv('DB_TABLE', 'M')
            if table_name in self.metadata.tables:
                self.M = self.metadata.tables[table_name]
                logger.info(f"[OK] Loaded table: {table_name}")
            else:
                logger.warning(f"[WARN] Table {table_name} not found in database")

            # Get lookup table if exists
            lookup_table = os.getenv('DB_LOOKUP_TABLE', 'L')
            if lookup_table in self.metadata.tables:
                self.L = self.metadata.tables[lookup_table]
                logger.info(f"[OK] Loaded lookup table: {lookup_table}")

        except Exception as e:
            logger.error(f"[ERROR] Failed to load tables: {e}")

    # ========================================================================
    # CACHE OPERATIONS
    # ========================================================================

    def get_from_cache(self, key: str) -> Optional[str]:
        """Get value from cache"""
        if not self.enable_cache or not self.redis_client:
            return None

        try:
            value = self.redis_client.get(key)
            if value:
                self.metrics['cache_hits'] += 1
                logger.debug(f"[CACHE HIT] {key}")
            else:
                self.metrics['cache_misses'] += 1
            return value
        except Exception as e:
            logger.warning(f"[CACHE ERROR] Failed to get {key}: {e}")
            return None

    def set_cache(self, key: str, value: str, ttl: Optional[int] = None):
        """Set value in cache with TTL"""
        if not self.enable_cache or not self.redis_client:
            return

        try:
            ttl = ttl or self.cache_ttl
            self.redis_client.setex(key, ttl, value)
            logger.debug(f"[CACHE SET] {key} (TTL: {ttl}s)")
        except Exception as e:
            logger.warning(f"[CACHE ERROR] Failed to set {key}: {e}")

    def invalidate_cache(self, pattern: str = "*"):
        """Invalidate cache entries matching pattern"""
        if not self.enable_cache or not self.redis_client:
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"[CACHE] Invalidated {deleted} keys matching {pattern}")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"[CACHE ERROR] Failed to invalidate {pattern}: {e}")
            return 0

    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================

    @contextmanager
    def get_session(self):
        """Context manager for database sessions"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"[DB ERROR] Session failed: {e}")
            self.metrics['errors'] += 1
            raise
        finally:
            session.close()

    def execute_query(self, query, params: Optional[Dict] = None) -> list:
        """Execute SQL query and return results"""
        self.metrics['queries_executed'] += 1
        self.metrics['last_query_time'] = datetime.now()

        try:
            with self.engine.connect() as conn:
                if params:
                    result = conn.execute(text(query), params)
                else:
                    result = conn.execute(text(query))
                return result.fetchall()
        except Exception as e:
            logger.error(f"[DB ERROR] Query failed: {e}")
            self.metrics['errors'] += 1
            raise

    # ========================================================================
    # HEALTH & MONITORING
    # ========================================================================

    def check_health(self) -> Dict[str, Any]:
        """Check database health and return status"""
        health = {
            'database': 'unknown',
            'cache': 'unknown',
            'connected': self.connected,
            'metrics': self.metrics.copy()
        }

        # Check database
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            health['database'] = 'healthy'
        except Exception as e:
            health['database'] = f'unhealthy: {str(e)}'
            logger.error(f"[HEALTH] Database check failed: {e}")

        # Check cache
        if self.enable_cache and self.redis_client:
            try:
                self.redis_client.ping()
                health['cache'] = 'healthy'
            except Exception as e:
                health['cache'] = f'unhealthy: {str(e)}'
        else:
            health['cache'] = 'disabled'

        return health

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        metrics = self.metrics.copy()

        # Add cache hit rate
        total_cache_requests = metrics['cache_hits'] + metrics['cache_misses']
        if total_cache_requests > 0:
            metrics['cache_hit_rate'] = metrics['cache_hits'] / total_cache_requests
        else:
            metrics['cache_hit_rate'] = 0.0

        return metrics

    def close(self):
        """Close all connections"""
        if self.Session:
            self.Session.remove()
        if self.engine:
            self.engine.dispose()
        if self.redis_client:
            self.redis_client.close()
        self.connected = False
        logger.info("[OK] Database connections closed")


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create global database manager instance
db_manager = DatabaseManager(
    enable_cache=os.getenv('ENABLE_CACHE', 'true').lower() == 'true',
    enable_pooling=os.getenv('ENABLE_POOLING', 'true').lower() == 'true',
    pool_size=int(os.getenv('DB_POOL_SIZE', '10')),
    max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '20'))
)

logger.info("[OK] Global database manager initialized")
