"""
Window Functions and CTEs for Sea Level Dashboard
Moves client-side calculations to database for better performance

This module provides:
1. Rolling averages (3h, 6h, 24h) using window functions
2. Trendline calculations using linear regression
3. Station comparisons and differences
4. Reusable CTEs for common patterns
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import text
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class WindowFunctionQueries:
    """SQL queries using window functions for analytical calculations"""

    @staticmethod
    def get_rolling_averages_query(
        window_hours: List[int] = [3, 6, 24],
        station: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """
        Generate SQL query for rolling averages using window functions

        Args:
            window_hours: List of window sizes in hours [3, 6, 24]
            station: Optional station name filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            SQL query string with window functions
        """

        # Build window calculations for each period
        window_calculations = []
        for hours in window_hours:
            # Convert hours to minutes for ROWS window
            minutes = hours * 60
            window_calculations.append(f"""
                AVG("Tab_Value_mDepthC1") OVER (
                    PARTITION BY l."Station"
                    ORDER BY m."Tab_DateTime"
                    ROWS BETWEEN {minutes} PRECEDING AND CURRENT ROW
                ) as "rolling_avg_{hours}h"
            """)

        window_clauses = ",\n                ".join(window_calculations)

        query = f"""
            WITH base_data AS (
                SELECT
                    m."Tab_DateTime",
                    l."Station",
                    CAST(m."Tab_Value_mDepthC1" AS FLOAT) as "Tab_Value_mDepthC1",
                    CAST(m."Tab_Value_monT2m" AS FLOAT) as "Tab_Value_monT2m",
                    ROW_NUMBER() OVER (PARTITION BY l."Station" ORDER BY m."Tab_DateTime") as row_num
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE 1=1
        """

        # Add filters
        if station and station != 'All Stations':
            query += f'\n                    AND l."Station" = :station'

        if start_date:
            query += f'\n                    AND DATE(m."Tab_DateTime") >= :start_date'

        if end_date:
            query += f'\n                    AND DATE(m."Tab_DateTime") <= :end_date'

        query += f"""
            )
            SELECT
                "Tab_DateTime",
                "Station",
                "Tab_Value_mDepthC1",
                "Tab_Value_monT2m",
                {window_clauses}
            FROM base_data
            ORDER BY "Station", "Tab_DateTime"
        """

        return query

    @staticmethod
    def get_trendline_query(
        station: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period_days: Optional[int] = None
    ) -> str:
        """
        Generate SQL query for linear regression trendline using window functions

        Args:
            station: Optional station name filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            period_days: Optional period for trendline (7, 30, 90, 365)

        Returns:
            SQL query string with linear regression
        """

        query = """
            WITH base_data AS (
                SELECT
                    m."Tab_DateTime",
                    l."Station",
                    CAST(m."Tab_Value_mDepthC1" AS FLOAT) as value,
                    ROW_NUMBER() OVER (PARTITION BY l."Station" ORDER BY m."Tab_DateTime") - 1 as x_index
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE 1=1
        """

        # Add filters
        if station and station != 'All Stations':
            query += '\n                    AND l."Station" = :station'

        if start_date:
            query += '\n                    AND DATE(m."Tab_DateTime") >= :start_date'

        if end_date:
            query += '\n                    AND DATE(m."Tab_DateTime") <= :end_date'

        if period_days:
            query += f'\n                    AND m."Tab_DateTime" >= NOW() - INTERVAL \'{period_days} days\''

        query += """
            ),
            regression_stats AS (
                SELECT
                    "Station",
                    COUNT(*) as n,
                    SUM(x_index) as sum_x,
                    SUM(value) as sum_y,
                    SUM(x_index * value) as sum_xy,
                    SUM(x_index * x_index) as sum_xx
                FROM base_data
                GROUP BY "Station"
            )
            SELECT
                bd."Tab_DateTime",
                bd."Station",
                bd.value as "Tab_Value_mDepthC1",
                bd.x_index,
                -- Calculate slope and intercept using window functions
                ((rs.n * rs.sum_xy - rs.sum_x * rs.sum_y) /
                 NULLIF(rs.n * rs.sum_xx - rs.sum_x * rs.sum_x, 0)) as slope,
                ((rs.sum_y - ((rs.n * rs.sum_xy - rs.sum_x * rs.sum_y) /
                 NULLIF(rs.n * rs.sum_xx - rs.sum_x * rs.sum_x, 0)) * rs.sum_x) / rs.n) as intercept,
                -- Calculate trendline value for each point
                ((rs.n * rs.sum_xy - rs.sum_x * rs.sum_y) /
                 NULLIF(rs.n * rs.sum_xx - rs.sum_x * rs.sum_x, 0)) * bd.x_index +
                ((rs.sum_y - ((rs.n * rs.sum_xy - rs.sum_x * rs.sum_y) /
                 NULLIF(rs.n * rs.sum_xx - rs.sum_x * rs.sum_x, 0)) * rs.sum_x) / rs.n) as trendline_value
            FROM base_data bd
            JOIN regression_stats rs ON bd."Station" = rs."Station"
            ORDER BY bd."Station", bd."Tab_DateTime"
        """

        return query

    @staticmethod
    def get_station_differences_query(
        station1: str,
        station2: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """
        Generate SQL query for station-to-station differences using window functions

        Args:
            station1: First station name
            station2: Second station name
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            SQL query string with station comparisons
        """

        query = """
            WITH station1_data AS (
                SELECT
                    m."Tab_DateTime",
                    l."Station" as station1,
                    CAST(m."Tab_Value_mDepthC1" AS FLOAT) as value1
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE l."Station" = :station1
        """

        if start_date:
            query += '\n                    AND DATE(m."Tab_DateTime") >= :start_date'

        if end_date:
            query += '\n                    AND DATE(m."Tab_DateTime") <= :end_date'

        query += """
            ),
            station2_data AS (
                SELECT
                    m."Tab_DateTime",
                    l."Station" as station2,
                    CAST(m."Tab_Value_mDepthC1" AS FLOAT) as value2
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE l."Station" = :station2
        """

        if start_date:
            query += '\n                    AND DATE(m."Tab_DateTime") >= :start_date'

        if end_date:
            query += '\n                    AND DATE(m."Tab_DateTime") <= :end_date'

        query += """
            )
            SELECT
                s1."Tab_DateTime",
                s1.station1,
                s2.station2,
                s1.value1,
                s2.value2,
                (s2.value2 - s1.value1) as difference,
                ((s2.value2 - s1.value1) / NULLIF(s1.value1, 0) * 100) as percent_difference,
                -- Rolling average of difference over 6 hours (360 minutes)
                AVG(s2.value2 - s1.value1) OVER (
                    ORDER BY s1."Tab_DateTime"
                    ROWS BETWEEN 360 PRECEDING AND CURRENT ROW
                ) as rolling_avg_diff_6h
            FROM station1_data s1
            JOIN station2_data s2 ON s1."Tab_DateTime" = s2."Tab_DateTime"
            ORDER BY s1."Tab_DateTime"
        """

        return query

    @staticmethod
    def get_lag_lead_analysis_query(
        station: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        lag_hours: int = 1
    ) -> str:
        """
        Generate SQL query using LAG/LEAD for time-series analysis

        Args:
            station: Optional station name filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            lag_hours: Number of hours to lag/lead (default 1)

        Returns:
            SQL query string with LAG/LEAD window functions
        """

        # Convert hours to minutes
        lag_minutes = lag_hours * 60

        query = f"""
            WITH base_data AS (
                SELECT
                    m."Tab_DateTime",
                    l."Station",
                    CAST(m."Tab_Value_mDepthC1" AS FLOAT) as current_value,
                    -- Previous value (lag)
                    LAG(CAST(m."Tab_Value_mDepthC1" AS FLOAT), {lag_minutes}) OVER (
                        PARTITION BY l."Station"
                        ORDER BY m."Tab_DateTime"
                    ) as previous_value,
                    -- Next value (lead)
                    LEAD(CAST(m."Tab_Value_mDepthC1" AS FLOAT), {lag_minutes}) OVER (
                        PARTITION BY l."Station"
                        ORDER BY m."Tab_DateTime"
                    ) as next_value,
                    -- Previous timestamp
                    LAG(m."Tab_DateTime", {lag_minutes}) OVER (
                        PARTITION BY l."Station"
                        ORDER BY m."Tab_DateTime"
                    ) as previous_timestamp
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE 1=1
        """

        # Add filters
        if station and station != 'All Stations':
            query += f'\n                    AND l."Station" = :station'

        if start_date:
            query += f'\n                    AND DATE(m."Tab_DateTime") >= :start_date'

        if end_date:
            query += f'\n                    AND DATE(m."Tab_DateTime") <= :end_date'

        query += f"""
            )
            SELECT
                "Tab_DateTime",
                "Station",
                current_value,
                previous_value,
                next_value,
                previous_timestamp,
                -- Calculate change from previous
                (current_value - previous_value) as change_from_previous,
                -- Calculate rate of change (per hour)
                CASE
                    WHEN previous_timestamp IS NOT NULL
                    THEN (current_value - previous_value) /
                         NULLIF(EXTRACT(EPOCH FROM ("Tab_DateTime" - previous_timestamp)) / 3600, 0)
                    ELSE NULL
                END as rate_of_change_per_hour,
                -- Calculate acceleration (second derivative)
                (current_value - previous_value) - (previous_value - LAG(previous_value, 1) OVER (
                    PARTITION BY "Station"
                    ORDER BY "Tab_DateTime"
                )) as acceleration
            FROM base_data
            ORDER BY "Station", "Tab_DateTime"
        """

        return query


class CommonCTEs:
    """Reusable Common Table Expressions for frequent patterns"""

    @staticmethod
    def get_base_data_cte(
        station: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """
        Standard base data CTE with common filters

        Returns:
            SQL CTE string for base data selection
        """
        cte = """
            WITH base_data AS (
                SELECT
                    m."Tab_DateTime",
                    l."Station",
                    l."Tab_TabularTag",
                    CAST(m."Tab_Value_mDepthC1" AS FLOAT) as "Tab_Value_mDepthC1",
                    CAST(m."Tab_Value_monT2m" AS FLOAT) as "Tab_Value_monT2m",
                    ROW_NUMBER() OVER (PARTITION BY l."Station" ORDER BY m."Tab_DateTime") as row_num
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE m."Tab_Value_mDepthC1" IS NOT NULL
        """

        if station and station != 'All Stations':
            cte += '\n                    AND l."Station" = :station'

        if start_date:
            cte += '\n                    AND DATE(m."Tab_DateTime") >= :start_date'

        if end_date:
            cte += '\n                    AND DATE(m."Tab_DateTime") <= :end_date'

        cte += '\n            )'

        return cte

    @staticmethod
    def get_statistics_cte() -> str:
        """
        CTE for statistical calculations per station

        Returns:
            SQL CTE string for statistics
        """
        return """
            statistics AS (
                SELECT
                    "Station",
                    COUNT(*) as record_count,
                    AVG("Tab_Value_mDepthC1") as mean_value,
                    STDDEV("Tab_Value_mDepthC1") as stddev_value,
                    MIN("Tab_Value_mDepthC1") as min_value,
                    MAX("Tab_Value_mDepthC1") as max_value,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY "Tab_Value_mDepthC1") as q1,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY "Tab_Value_mDepthC1") as median,
                    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY "Tab_Value_mDepthC1") as q3
                FROM base_data
                GROUP BY "Station"
            )
        """

    @staticmethod
    def get_outliers_cte() -> str:
        """
        CTE for outlier detection using IQR method

        Returns:
            SQL CTE string for outlier detection
        """
        return """
            outliers AS (
                SELECT
                    bd.*,
                    s.q1,
                    s.q3,
                    (s.q3 - s.q1) as iqr,
                    CASE
                        WHEN bd."Tab_Value_mDepthC1" < (s.q1 - 1.5 * (s.q3 - s.q1))
                             OR bd."Tab_Value_mDepthC1" > (s.q3 + 1.5 * (s.q3 - s.q1))
                        THEN TRUE
                        ELSE FALSE
                    END as is_outlier
                FROM base_data bd
                JOIN statistics s ON bd."Station" = s."Station"
            )
        """

    @staticmethod
    def get_time_buckets_cte(bucket_size: str = '1 hour') -> str:
        """
        CTE for time-based aggregation buckets

        Args:
            bucket_size: Bucket size ('1 hour', '6 hours', '1 day')

        Returns:
            SQL CTE string for time bucketing
        """
        if bucket_size == '1 hour':
            trunc_expr = "DATE_TRUNC('hour', \"Tab_DateTime\")"
        elif bucket_size == '6 hours':
            trunc_expr = """DATE_TRUNC('hour', "Tab_DateTime") +
                           INTERVAL '6 hours' * FLOOR(EXTRACT(HOUR FROM "Tab_DateTime")::int / 6)"""
        elif bucket_size == '1 day':
            trunc_expr = "DATE_TRUNC('day', \"Tab_DateTime\")"
        else:
            trunc_expr = "DATE_TRUNC('hour', \"Tab_DateTime\")"

        return f"""
            time_buckets AS (
                SELECT
                    {trunc_expr}::timestamp as bucket_time,
                    "Station",
                    AVG("Tab_Value_mDepthC1") as avg_value,
                    MIN("Tab_Value_mDepthC1") as min_value,
                    MAX("Tab_Value_mDepthC1") as max_value,
                    COUNT(*) as record_count
                FROM base_data
                GROUP BY {trunc_expr}, "Station"
            )
        """


class AnalyticalQueryBuilder:
    """Build complex analytical queries combining window functions and CTEs"""

    def __init__(self, engine):
        """
        Initialize with database engine

        Args:
            engine: SQLAlchemy engine instance
        """
        self.engine = engine
        self.window_funcs = WindowFunctionQueries()
        self.ctes = CommonCTEs()

    def execute_rolling_averages(
        self,
        window_hours: List[int] = [3, 6, 24],
        station: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Execute rolling averages query and return DataFrame

        Args:
            window_hours: List of window sizes in hours
            station: Optional station name filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            pandas DataFrame with rolling averages
        """
        query = self.window_funcs.get_rolling_averages_query(
            window_hours=window_hours,
            station=station,
            start_date=start_date,
            end_date=end_date
        )

        params = {}
        if station and station != 'All Stations':
            params['station'] = station
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params)
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                logger.info(f"[WINDOW FUNC] Rolling averages calculated: {len(df)} rows")
                return df
        except Exception as e:
            logger.error(f"[ERROR] Rolling averages query failed: {e}")
            return pd.DataFrame()

    def execute_trendline(
        self,
        station: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period_days: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Execute trendline query and return DataFrame

        Args:
            station: Optional station name filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            period_days: Optional period for trendline

        Returns:
            pandas DataFrame with trendline calculations
        """
        query = self.window_funcs.get_trendline_query(
            station=station,
            start_date=start_date,
            end_date=end_date,
            period_days=period_days
        )

        params = {}
        if station and station != 'All Stations':
            params['station'] = station
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params)
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                logger.info(f"[WINDOW FUNC] Trendline calculated: {len(df)} rows")
                return df
        except Exception as e:
            logger.error(f"[ERROR] Trendline query failed: {e}")
            return pd.DataFrame()

    def execute_station_comparison(
        self,
        station1: str,
        station2: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Execute station comparison query and return DataFrame

        Args:
            station1: First station name
            station2: Second station name
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            pandas DataFrame with station comparisons
        """
        query = self.window_funcs.get_station_differences_query(
            station1=station1,
            station2=station2,
            start_date=start_date,
            end_date=end_date
        )

        params = {
            'station1': station1,
            'station2': station2
        }
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params)
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                logger.info(f"[WINDOW FUNC] Station comparison calculated: {len(df)} rows")
                return df
        except Exception as e:
            logger.error(f"[ERROR] Station comparison query failed: {e}")
            return pd.DataFrame()

    def execute_lag_lead_analysis(
        self,
        station: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        lag_hours: int = 1
    ) -> pd.DataFrame:
        """
        Execute LAG/LEAD analysis query and return DataFrame

        Args:
            station: Optional station name filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            lag_hours: Number of hours to lag/lead

        Returns:
            pandas DataFrame with lag/lead analysis
        """
        query = self.window_funcs.get_lag_lead_analysis_query(
            station=station,
            start_date=start_date,
            end_date=end_date,
            lag_hours=lag_hours
        )

        params = {}
        if station and station != 'All Stations':
            params['station'] = station
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params)
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                logger.info(f"[WINDOW FUNC] Lag/Lead analysis calculated: {len(df)} rows")
                return df
        except Exception as e:
            logger.error(f"[ERROR] Lag/Lead analysis query failed: {e}")
            return pd.DataFrame()
