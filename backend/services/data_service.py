"""
Data Service Layer
Separates business logic from route handlers and database access

This service handles:
- Data fetching and transformation
- Anomaly detection orchestration
- Statistics calculation
- Baseline integration
- Caching strategy
"""

import logging
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd

from models.database import db_manager
from repositories.sea_level_repository import SeaLevelRepository
from services.anomaly_service import AnomalyService
from utils.validators.data_validators import validate_date_range, validate_station

logger = logging.getLogger(__name__)


class DataService:
    """
    Business logic service for sea level data operations
    """

    def __init__(self):
        self.repository = SeaLevelRepository(db_manager)
        self.anomaly_service = AnomalyService()
        self.cache_ttl = 300  # 5 minutes

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def get_sea_level_data(
        self,
        station: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_source: str = 'default',
        include_outliers: bool = False,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get sea level data for a station with optional anomaly detection

        Args:
            station: Station name
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            data_source: Data source type ('default', 'tides', etc.)
            include_outliers: Include anomaly/outlier detection
            use_cache: Use cache if available

        Returns:
            List of sea level data points as dictionaries
        """
        # Validate inputs
        validate_station(station)
        start_date, end_date = validate_date_range(start_date, end_date)

        # Check cache
        if use_cache:
            cache_key = self._generate_cache_key(
                station, start_date, end_date, data_source, include_outliers
            )
            cached_data = db_manager.get_from_cache(cache_key)
            if cached_data:
                logger.info(f"[CACHE HIT] Station: {station}")
                return pd.read_json(cached_data, orient='records').to_dict('records')

        # Fetch from database
        df = self.repository.get_data_by_station(
            station=station,
            start_date=start_date,
            end_date=end_date,
            data_source=data_source
        )

        if df.empty:
            logger.warning(f"[DATA] No data found for station: {station}")
            return []

        # Apply anomaly detection if requested
        if include_outliers:
            df = self.anomaly_service.detect_anomalies(df, station)

        # Convert to records
        records = df.to_dict('records')

        # Cache result
        if use_cache and records:
            db_manager.set_cache(cache_key, df.to_json(orient='records'), self.cache_ttl)

        logger.info(f"[DATA] Retrieved {len(records)} records for {station}")
        return records

    def get_batch_data(
        self,
        stations: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_source: str = 'default',
        include_outliers: bool = False,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get sea level data for multiple stations in parallel

        Args:
            stations: List of station names
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            data_source: Data source type
            include_outliers: Include anomaly/outlier detection
            use_cache: Use cache if available

        Returns:
            Combined list of data points from all stations
        """
        if not stations:
            return []

        # Validate inputs
        start_date, end_date = validate_date_range(start_date, end_date)

        # Check if we can use optimized batch query
        if len(stations) > 1 and not include_outliers:
            return self._batch_query_optimized(
                stations, start_date, end_date, data_source, use_cache
            )

        # Fall back to parallel individual queries
        all_data = []
        for station in stations:
            try:
                station_data = self.get_sea_level_data(
                    station=station,
                    start_date=start_date,
                    end_date=end_date,
                    data_source=data_source,
                    include_outliers=include_outliers,
                    use_cache=use_cache
                )
                all_data.extend(station_data)
            except Exception as e:
                logger.error(f"[DATA] Failed to fetch {station}: {e}")
                continue

        logger.info(f"[DATA] Batch query: {len(all_data)} records from {len(stations)} stations")
        return all_data

    def get_latest_readings(
        self,
        station: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get latest sea level readings

        Args:
            station: Optional station filter
            limit: Maximum number of records

        Returns:
            List of latest readings
        """
        df = self.repository.get_latest_readings(station=station, limit=limit)

        if df.empty:
            return []

        return df.to_dict('records')

    def calculate_statistics(
        self,
        station: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate statistics for a station

        Args:
            station: Station name
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            Dictionary with calculated statistics
        """
        # Get data
        data = self.get_sea_level_data(
            station=station,
            start_date=start_date,
            end_date=end_date,
            use_cache=True
        )

        if not data:
            return {
                'current_level': None,
                '24h_change': None,
                'avg_temp': None,
                'anomalies': 0,
                'min_level': None,
                'max_level': None,
                'mean_level': None
            }

        df = pd.DataFrame(data)

        # Calculate statistics
        stats = {
            'current_level': self._get_current_level(df),
            '24h_change': self._calculate_24h_change(df),
            'avg_temp': self._calculate_avg_temp(df),
            'anomalies': int((df['anomaly'] == -1).sum()) if 'anomaly' in df.columns else 0,
            'min_level': float(df['Tab_Value_mDepthC1'].min()),
            'max_level': float(df['Tab_Value_mDepthC1'].max()),
            'mean_level': float(df['Tab_Value_mDepthC1'].mean()),
            'std_dev': float(df['Tab_Value_mDepthC1'].std()),
            'data_points': len(df)
        }

        return stats

    # ========================================================================
    # PRIVATE HELPERS
    # ========================================================================

    def _generate_cache_key(
        self,
        station: str,
        start_date: str,
        end_date: str,
        data_source: str,
        include_outliers: bool
    ) -> str:
        """Generate deterministic cache key"""
        key_parts = f"{station}_{start_date}_{end_date}_{data_source}_{include_outliers}"
        hash_key = hashlib.md5(key_parts.encode()).hexdigest()
        return f"data:{hash_key}"

    def _batch_query_optimized(
        self,
        stations: List[str],
        start_date: str,
        end_date: str,
        data_source: str,
        use_cache: bool
    ) -> List[Dict[str, Any]]:
        """
        Optimized batch query for multiple stations
        Uses single database query instead of multiple
        """
        # Check cache
        if use_cache:
            cache_key = self._generate_cache_key(
                ','.join(sorted(stations)), start_date, end_date, data_source, False
            )
            cached_data = db_manager.get_from_cache(cache_key)
            if cached_data:
                logger.info(f"[CACHE HIT] Batch query for {len(stations)} stations")
                return pd.read_json(cached_data, orient='records').to_dict('records')

        # Single database query
        df = self.repository.get_data_by_stations(
            stations=stations,
            start_date=start_date,
            end_date=end_date,
            data_source=data_source
        )

        if df.empty:
            return []

        records = df.to_dict('records')

        # Cache result
        if use_cache and records:
            db_manager.set_cache(cache_key, df.to_json(orient='records'), self.cache_ttl)

        return records

    def _get_current_level(self, df: pd.DataFrame) -> Optional[float]:
        """Get current (latest) sea level reading"""
        if df.empty:
            return None

        # Sort by datetime and get latest
        df_sorted = df.sort_values('Tab_DateTime', ascending=False)
        latest_value = df_sorted.iloc[0]['Tab_Value_mDepthC1']

        return float(latest_value) if pd.notna(latest_value) else None

    def _calculate_24h_change(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate 24-hour change in sea level"""
        if df.empty or len(df) < 2:
            return None

        # Sort by datetime
        df_sorted = df.sort_values('Tab_DateTime')

        # Get latest reading
        latest = df_sorted.iloc[-1]
        latest_time = pd.to_datetime(latest['Tab_DateTime'])
        latest_level = latest['Tab_Value_mDepthC1']

        # Find reading ~24 hours ago (within 2 hour tolerance)
        target_time = latest_time - timedelta(hours=24)
        tolerance = timedelta(hours=2)

        df_sorted['time_diff'] = abs(
            pd.to_datetime(df_sorted['Tab_DateTime']) - target_time
        )

        nearby = df_sorted[df_sorted['time_diff'] <= tolerance]

        if nearby.empty:
            return None

        # Get closest reading
        closest = nearby.nsmallest(1, 'time_diff').iloc[0]
        past_level = closest['Tab_Value_mDepthC1']

        if pd.isna(latest_level) or pd.isna(past_level):
            return None

        return float(latest_level - past_level)

    def _calculate_avg_temp(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate average temperature"""
        if df.empty or 'Tab_Value_monT2m' not in df.columns:
            return None

        temps = df['Tab_Value_monT2m'].dropna()

        if temps.empty:
            return None

        return float(temps.mean())


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

data_service = DataService()
