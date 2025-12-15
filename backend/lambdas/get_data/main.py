# backend/lambdas/get_data/main.py - ALWAYS RAW DATA VERSION
# MODIFIED: Always returns 1-minute interval data regardless of date range
# Previous version used dynamic aggregation based on date range
import json
import logging
import sys
import os
import pandas as pd
import numpy as np
import hashlib
from datetime import datetime, timedelta

# Add paths for shared modules
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..', '..')
sys.path.insert(0, backend_dir)

try:
    from shared.database import engine, M, L, S, db_manager
    from sqlalchemy import text
    DATABASE_AVAILABLE = True
    print("[OK] Database modules imported successfully for get_data")
except ImportError as e:
    print(f"[ERROR] Database import error in get_data: {e}")
    DATABASE_AVAILABLE = False

# Import Southern Baseline Rules for outlier detection
try:
    from shared.baseline_integration import BaselineIntegratedProcessor
    BASELINE_RULES_AVAILABLE = True
    print("[OK] Southern Baseline Rules imported successfully")
except ImportError as e:
    print(f"[WARNING] Southern Baseline Rules not available: {e}")
    BASELINE_RULES_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_numeric_data(df):
    """Clean numeric data by replacing inf/nan values"""
    numeric_columns = df.select_dtypes(include=[np.number]).columns
    
    for col in numeric_columns:
        df[col] = df[col].replace([np.inf, -np.inf], np.nan)
        
        if 'mDepth' in col or 'Value' in col:
            df[col] = df[col].interpolate(method='linear', limit_direction='both')
            df[col] = df[col].ffill().bfill()
            df[col] = df[col].fillna(0)
        else:
            df[col] = df[col].fillna(0)
    
    return df

def parse_date_parameter(date_str):
    """Parse date parameter and return properly formatted date string for SQL"""
    if not date_str:
        return None
    
    try:
        if 'T' in date_str:
            # Handle ISO datetime format - extract date part only to avoid timezone issues
            parsed_date = datetime.fromisoformat(date_str.replace('Z', ''))
            # Force to date only to avoid timezone conversion issues
            return parsed_date.date().strftime('%Y-%m-%d')
        else:
            # Simple date format: 2024-11-01
            parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
            return parsed_date.strftime('%Y-%m-%d')
    except Exception as e:
        logger.error(f"Error parsing date '{date_str}': {e}")
        return None

def calculate_aggregation_level(start_date, end_date):
    """
    MODIFIED: Always return raw 1-minute interval data regardless of date range.
    Previous behavior used smart aggregation based on date range.
    Now bypassed to always return raw data.
    """
    # Always return raw data - no aggregation
    return 'raw', None

def detect_anomalies(df):
    """
    Anomaly detection using Southern Baseline Rules when available,
    fallback to IQR method if not available
    """
    if 'Tab_Value_mDepthC1' not in df.columns or df.empty:
        return df

    # Use Southern Baseline Rules if available
    if BASELINE_RULES_AVAILABLE:
        try:
            logger.info(f"[BASELINE] Applying Southern Baseline Rules to {len(df)} records")
            processor = BaselineIntegratedProcessor()
            df_processed = processor.detect_anomalies_with_rules(df)

            # The processor sets 'anomaly' field based on 'Is_Outlier'
            # Verify anomaly field exists and log results
            if 'anomaly' in df_processed.columns:
                anomaly_count = sum(df_processed['anomaly'] == -1)
                if anomaly_count > 0:
                    logger.info(f"[BASELINE] Detected {anomaly_count} outliers using Southern Baseline Rules")
                    # Log some details
                    outliers = df_processed[df_processed['anomaly'] == -1]
                    for station in outliers['Station'].unique():
                        station_outliers = outliers[outliers['Station'] == station]
                        logger.info(f"  {station}: {len(station_outliers)} outliers")
            else:
                logger.warning("[BASELINE] No anomaly field in processed data, adding default")
                df_processed['anomaly'] = 0

            return df_processed

        except Exception as e:
            logger.error(f"[BASELINE] Error applying Southern Baseline Rules: {e}")
            logger.error(f"[BASELINE] Falling back to IQR method")
            import traceback
            logger.error(traceback.format_exc())
            # Fall through to IQR method

    # Fallback: Simple IQR method
    logger.info(f"[IQR] Using IQR method for anomaly detection")
    try:
        valid_values = df['Tab_Value_mDepthC1'].dropna()

        if len(valid_values) > 10:
            Q1 = valid_values.quantile(0.25)
            Q3 = valid_values.quantile(0.75)
            IQR = Q3 - Q1

            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            df['anomaly'] = np.where(
                (df['Tab_Value_mDepthC1'].notna()) &
                ((df['Tab_Value_mDepthC1'] < lower_bound) | (df['Tab_Value_mDepthC1'] > upper_bound)),
                -1, 0
            )

            anomaly_count = sum(df['anomaly'] == -1)
            if anomaly_count > 0:
                logger.info(f"[IQR] Detected {anomaly_count} anomalies")
        else:
            df['anomaly'] = 0
    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}")
        df['anomaly'] = 0

    return df

def clean_baseline_columns(df):
    """
    Remove internal baseline processing columns before sending to frontend.
    Keep only essential columns for frontend display.
    """
    # Columns added by Southern Baseline Rules that should be removed
    baseline_columns = [
        'Expected_Value', 'Baseline', 'Baseline_Sources', 'Baseline_Stations',
        'Deviation', 'Is_Outlier', 'Tolerance', 'Excluded_From_Baseline'
    ]

    # Remove these columns if they exist
    cols_to_drop = [col for col in baseline_columns if col in df.columns]
    if cols_to_drop:
        logger.info(f"[CLEANUP] Removing {len(cols_to_drop)} baseline columns: {cols_to_drop}")
        df = df.drop(columns=cols_to_drop)

    return df

def load_data_from_db_optimized(start_date=None, end_date=None, station=None,
                                data_source='default', show_anomalies=False):
    """
    MODIFIED: Always loads raw 1-minute interval data regardless of date range.
    Previous version used smart aggregation - now bypassed to always return raw data.
    """
    if not DATABASE_AVAILABLE or not engine:
        logger.warning("Database not available")
        return pd.DataFrame()
    
    parsed_start_date = parse_date_parameter(start_date)
    parsed_end_date = parse_date_parameter(end_date)
    
    agg_level, time_bucket = calculate_aggregation_level(parsed_start_date, parsed_end_date)
    
    logger.info(f"[AGG] Using aggregation level: {agg_level} for date range {parsed_start_date} to {parsed_end_date}")
    
    cache_params = {
        'start_date': parsed_start_date,
        'end_date': parsed_end_date,
        'station': station,
        'data_source': data_source,
        'aggregation': agg_level,
        'show_anomalies': show_anomalies
    }
    cache_key = f"data_cache:{hashlib.md5(json.dumps(cache_params, sort_keys=True).encode()).hexdigest()}"
    
    cache_ttl = 600 if agg_level != 'raw' else 120
    if db_manager and hasattr(db_manager, 'get_from_cache'):
        cached_data = db_manager.get_from_cache(cache_key)
        if cached_data:
            logger.info(f"[CACHE HIT] {len(cached_data)} rows (agg: {agg_level})")
            return pd.DataFrame(cached_data)
    
    params = {}
    
    # ============================================
    # TIDES DATA QUERY (FIXED)
    # ============================================
    if data_source == 'tides':
        if agg_level == 'raw':
            sql_query = '''
                SELECT "Date", "Station", "HighTide", "HighTideTime", "HighTideTemp", 
                       "LowTide", "LowTideTime", "LowTideTemp", "MeasurementCount"
                FROM "SeaTides"
                WHERE 1=1
            '''
        else:
            # Determine the period based on agg_level
            period = 'day' if agg_level == 'daily' else ('week' if agg_level == 'weekly' else 'day')
            sql_query = f'''
                SELECT 
                    DATE_TRUNC('{period}', "Date") as "Date",
                    "Station",
                    AVG("HighTide") as "HighTide",
                    NULL as "HighTideTime",
                    AVG("HighTideTemp") as "HighTideTemp",
                    AVG("LowTide") as "LowTide",
                    NULL as "LowTideTime",
                    AVG("LowTideTemp") as "LowTideTemp",
                    SUM("MeasurementCount") as "MeasurementCount"
                FROM "SeaTides"
                WHERE 1=1
            '''
        
        if station and station != 'All Stations':
            sql_query += ' AND "Station" = :station'
            params['station'] = station
        
        # FIXED: Use date comparison with explicit casting
        if parsed_start_date:
            sql_query += ' AND "Date" >= :start_date'
            params['start_date'] = parsed_start_date
        if parsed_end_date:
            sql_query += ' AND "Date" <= :end_date'
            params['end_date'] = parsed_end_date
        
        if agg_level != 'raw':
            sql_query += ' GROUP BY DATE_TRUNC(\'week\', "Date"), "Station"'
        
        sql_query += ' ORDER BY "Date" ASC'
    
    # ============================================
    # SEA LEVEL DATA QUERY (FIXED)
    # ============================================
    else:
        if agg_level == 'raw':
            sql_query = '''
                SELECT
                    m."Tab_DateTime",
                    l."Station",
                    CAST(m."Tab_Value_mDepthC1" AS FLOAT) as "Tab_Value_mDepthC1",
                    CAST(m."Tab_Value_monT2m" AS FLOAT) as "Tab_Value_monT2m"
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE 1=1
            '''
        elif agg_level == '5min':
            sql_query = '''
                SELECT
                    (DATE_TRUNC('hour', m."Tab_DateTime") +
                    INTERVAL '5 minutes' * FLOOR(EXTRACT(MINUTE FROM m."Tab_DateTime")::int / 5))::timestamp as "Tab_DateTime",
                    l."Station",
                    AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                    AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                    COUNT(*) as "RecordCount"
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE 1=1
            '''
        elif agg_level == '15min':
            sql_query = '''
                SELECT
                    (DATE_TRUNC('hour', m."Tab_DateTime") +
                    INTERVAL '15 minutes' * FLOOR(EXTRACT(MINUTE FROM m."Tab_DateTime")::int / 15))::timestamp as "Tab_DateTime",
                    l."Station",
                    AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                    AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                    COUNT(*) as "RecordCount"
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE 1=1
            '''
        elif agg_level == 'hourly':
            if time_bucket == '1 hour':
                sql_query = '''
                    SELECT 
                        DATE_TRUNC('hour', m."Tab_DateTime")::timestamp as "Tab_DateTime",
                        l."Station",
                        AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                        AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                        MIN(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Min_mDepthC1",
                        MAX(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Max_mDepthC1",
                        COUNT(*) as "RecordCount"
                    FROM "Monitors_info2" m
                    JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                    WHERE 1=1
                '''
            else:
                sql_query = '''
                    SELECT 
                        (DATE_TRUNC('hour', m."Tab_DateTime") + 
                        INTERVAL '3 hours' * FLOOR(EXTRACT(HOUR FROM m."Tab_DateTime")::int / 3))::timestamp as "Tab_DateTime",
                        l."Station",
                        AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                        AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                        MIN(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Min_mDepthC1",
                        MAX(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Max_mDepthC1",
                        COUNT(*) as "RecordCount"
                    FROM "Monitors_info2" m
                    JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                    WHERE 1=1
                '''
        elif agg_level == 'daily':
            sql_query = '''
                SELECT 
                    DATE_TRUNC('day', m."Tab_DateTime")::timestamp as "Tab_DateTime",
                    l."Station",
                    AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                    AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                    MIN(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Min_mDepthC1",
                    MAX(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Max_mDepthC1",
                    COUNT(*) as "RecordCount"
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE 1=1
            '''
        else:  # weekly
            sql_query = '''
                SELECT 
                    DATE_TRUNC('week', m."Tab_DateTime")::timestamp as "Tab_DateTime",
                    l."Station",
                    AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                    AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                    MIN(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Min_mDepthC1",
                    MAX(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Max_mDepthC1",
                    COUNT(*) as "RecordCount"
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE 1=1
            '''
        
        if station and station != 'All Stations':
            sql_query += ' AND l."Station" = :station'
            params['station'] = station
        
        # FIXED: Use DATE() function for date-only comparison (timezone-agnostic)
        if parsed_start_date:
            sql_query += ' AND DATE(m."Tab_DateTime") >= :start_date'
            params['start_date'] = parsed_start_date
        if parsed_end_date:
            sql_query += ' AND DATE(m."Tab_DateTime") <= :end_date'
            params['end_date'] = parsed_end_date
        
        # Add GROUP BY for aggregations
        if agg_level == '5min':
            sql_query += ''' GROUP BY DATE_TRUNC('hour', m."Tab_DateTime") +
                INTERVAL '5 minutes' * FLOOR(EXTRACT(MINUTE FROM m."Tab_DateTime")::int / 5), l."Station"'''
        elif agg_level == '15min':
            sql_query += ''' GROUP BY DATE_TRUNC('hour', m."Tab_DateTime") +
                INTERVAL '15 minutes' * FLOOR(EXTRACT(MINUTE FROM m."Tab_DateTime")::int / 15), l."Station"'''
        elif agg_level == 'hourly' and time_bucket == '3 hours':
            sql_query += ''' GROUP BY DATE_TRUNC('hour', m."Tab_DateTime") +
                INTERVAL '3 hours' * FLOOR(EXTRACT(HOUR FROM m."Tab_DateTime")::int / 3), l."Station"'''
        elif agg_level in ['hourly', 'daily', 'weekly']:
            period = 'hour' if agg_level == 'hourly' else ('day' if agg_level == 'daily' else 'week')
            sql_query += f' GROUP BY DATE_TRUNC(\'{period}\', m."Tab_DateTime"), l."Station"'

        sql_query += ' ORDER BY "Tab_DateTime" ASC'
    
    logger.info(f"[QUERY] Executing {agg_level} query")
    
    # ============================================
    # EXECUTE QUERY
    # ============================================
    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql_query), params)
            df = pd.DataFrame(result.fetchall())
            
            if not df.empty:
                df.columns = result.keys()
                df = clean_numeric_data(df)
                
                # Apply Southern Baseline Rules to all data when anomalies requested
                if show_anomalies:
                    df = detect_anomalies(df)
                else:
                    df['anomaly'] = 0
                
                df['aggregation_level'] = agg_level
                
                if db_manager and hasattr(db_manager, 'set_cache'):
                    try:
                        cache_data = df.to_dict('records')
                        db_manager.set_cache(cache_key, cache_data, ttl=cache_ttl)
                        logger.info(f"[CACHE SET] Cached {len(df)} rows (agg: {agg_level}, TTL: {cache_ttl}s)")
                    except Exception as cache_error:
                        logger.warning(f"Cache operation failed: {cache_error}")
            
            return df
            
    except Exception as e:
        logger.error(f"[DB ERROR] Database query failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return pd.DataFrame()

def load_data_batch_optimized(stations_list, start_date=None, end_date=None,
                              data_source='default', show_anomalies=False):
    """
    MODIFIED: Always loads raw 1-minute interval data for multiple stations.
    Previous version used smart aggregation - now bypassed to always return raw data.
    """
    if not DATABASE_AVAILABLE or not engine:
        logger.warning("Database not available")
        return pd.DataFrame()

    if not stations_list or len(stations_list) == 0:
        return pd.DataFrame()

    # Remove 'All Stations' if present
    stations_list = [s for s in stations_list if s != 'All Stations']
    if not stations_list:
        return pd.DataFrame()

    parsed_start_date = parse_date_parameter(start_date)
    parsed_end_date = parse_date_parameter(end_date)

    agg_level, time_bucket = calculate_aggregation_level(parsed_start_date, parsed_end_date)

    logger.info(f"[BATCH] Loading data for {len(stations_list)} stations with {agg_level} aggregation")

    # Build query based on aggregation level (same logic as single station)
    params = {
        'start_date': parsed_start_date,
        'end_date': parsed_end_date
    }

    if data_source == 'tides':
        # Tides batch query
        if agg_level == 'raw':
            sql_query = '''
                SELECT "Date", "Station", "HighTide", "HighTideTime", "HighTideTemp",
                       "LowTide", "LowTideTime", "LowTideTemp", "MeasurementCount"
                FROM "SeaTides"
                WHERE "Station" = ANY(:stations)
            '''
        else:
            period = 'day' if agg_level == 'daily' else ('week' if agg_level == 'weekly' else 'day')
            sql_query = f'''
                SELECT
                    DATE_TRUNC('{period}', "Date") as "Date",
                    "Station",
                    AVG("HighTide") as "HighTide",
                    NULL as "HighTideTime",
                    AVG("HighTideTemp") as "HighTideTemp",
                    AVG("LowTide") as "LowTide",
                    NULL as "LowTideTime",
                    AVG("LowTideTemp") as "LowTideTemp",
                    SUM("MeasurementCount") as "MeasurementCount"
                FROM "SeaTides"
                WHERE "Station" = ANY(:stations)
            '''

        params['stations'] = stations_list

        if parsed_start_date:
            sql_query += ' AND "Date" >= :start_date'
        if parsed_end_date:
            sql_query += ' AND "Date" <= :end_date'

        if agg_level != 'raw':
            sql_query += f' GROUP BY DATE_TRUNC(\'{period}\', "Date"), "Station"'

        sql_query += ' ORDER BY "Date" ASC'
    else:
        # Sea level batch query
        if agg_level == 'raw':
            sql_query = '''
                SELECT
                    m."Tab_DateTime",
                    l."Station",
                    CAST(m."Tab_Value_mDepthC1" AS FLOAT) as "Tab_Value_mDepthC1",
                    CAST(m."Tab_Value_monT2m" AS FLOAT) as "Tab_Value_monT2m"
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE l."Station" = ANY(:stations)
            '''
        elif agg_level == '5min':
            sql_query = '''
                SELECT
                    (DATE_TRUNC('hour', m."Tab_DateTime") +
                    INTERVAL '5 minutes' * FLOOR(EXTRACT(MINUTE FROM m."Tab_DateTime")::int / 5))::timestamp as "Tab_DateTime",
                    l."Station",
                    AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                    AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                    COUNT(*) as "RecordCount"
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE l."Station" = ANY(:stations)
            '''
        elif agg_level == '15min':
            sql_query = '''
                SELECT
                    (DATE_TRUNC('hour', m."Tab_DateTime") +
                    INTERVAL '15 minutes' * FLOOR(EXTRACT(MINUTE FROM m."Tab_DateTime")::int / 15))::timestamp as "Tab_DateTime",
                    l."Station",
                    AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                    AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                    COUNT(*) as "RecordCount"
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE l."Station" = ANY(:stations)
            '''
        elif agg_level == 'hourly':
            time_trunc = '1 hour' if time_bucket == '1 hour' else '3 hours'
            if time_bucket == '1 hour':
                sql_query = '''
                    SELECT
                        DATE_TRUNC('hour', m."Tab_DateTime")::timestamp as "Tab_DateTime",
                        l."Station",
                        AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                        AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                        COUNT(*) as "RecordCount"
                    FROM "Monitors_info2" m
                    JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                    WHERE l."Station" = ANY(:stations)
                '''
            else:
                sql_query = '''
                    SELECT
                        (DATE_TRUNC('hour', m."Tab_DateTime") +
                        INTERVAL '3 hours' * FLOOR(EXTRACT(HOUR FROM m."Tab_DateTime")::int / 3))::timestamp as "Tab_DateTime",
                        l."Station",
                        AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                        AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                        COUNT(*) as "RecordCount"
                    FROM "Monitors_info2" m
                    JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                    WHERE l."Station" = ANY(:stations)
                '''
        elif agg_level == 'daily':
            sql_query = '''
                SELECT
                    DATE_TRUNC('day', m."Tab_DateTime")::timestamp as "Tab_DateTime",
                    l."Station",
                    AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                    AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                    COUNT(*) as "RecordCount"
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE l."Station" = ANY(:stations)
            '''
        else:  # weekly
            sql_query = '''
                SELECT
                    DATE_TRUNC('week', m."Tab_DateTime")::timestamp as "Tab_DateTime",
                    l."Station",
                    AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
                    AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
                    COUNT(*) as "RecordCount"
                FROM "Monitors_info2" m
                JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
                WHERE l."Station" = ANY(:stations)
            '''

        params['stations'] = stations_list

        if parsed_start_date:
            sql_query += ' AND DATE(m."Tab_DateTime") >= :start_date'
        if parsed_end_date:
            sql_query += ' AND DATE(m."Tab_DateTime") <= :end_date'

        # Add GROUP BY for aggregations
        if agg_level == '5min':
            sql_query += ''' GROUP BY DATE_TRUNC('hour', m."Tab_DateTime") +
                INTERVAL '5 minutes' * FLOOR(EXTRACT(MINUTE FROM m."Tab_DateTime")::int / 5), l."Station"'''
        elif agg_level == '15min':
            sql_query += ''' GROUP BY DATE_TRUNC('hour', m."Tab_DateTime") +
                INTERVAL '15 minutes' * FLOOR(EXTRACT(MINUTE FROM m."Tab_DateTime")::int / 15), l."Station"'''
        elif agg_level == 'hourly' and time_bucket == '3 hours':
            sql_query += ''' GROUP BY DATE_TRUNC('hour', m."Tab_DateTime") +
                INTERVAL '3 hours' * FLOOR(EXTRACT(HOUR FROM m."Tab_DateTime")::int / 3), l."Station"'''
        elif agg_level in ['hourly', 'daily', 'weekly']:
            period = 'hour' if agg_level == 'hourly' else ('day' if agg_level == 'daily' else 'week')
            sql_query += f' GROUP BY DATE_TRUNC(\'{period}\', m."Tab_DateTime"), l."Station"'

        sql_query += ' ORDER BY "Tab_DateTime" ASC'

    logger.info(f"[BATCH QUERY] Executing for {len(stations_list)} stations")

    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql_query), params)
            df = pd.DataFrame(result.fetchall())

            if not df.empty:
                df.columns = result.keys()
                df = clean_numeric_data(df)

                # Apply Southern Baseline Rules to all data when anomalies requested
                if show_anomalies:
                    df = detect_anomalies(df)
                else:
                    df['anomaly'] = 0

                df['aggregation_level'] = agg_level

            logger.info(f"[BATCH] Loaded {len(df)} records for {len(stations_list)} stations")
            return df

    except Exception as e:
        logger.error(f"[BATCH ERROR] Database query failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return pd.DataFrame()

def lambda_handler_batch(event, context):
    """Lambda handler for batch data requests (multiple stations)"""
    try:
        params = event.get('queryStringParameters') or {}

        # Get stations list (comma-separated or array)
        stations_param = params.get('stations', '')
        if isinstance(stations_param, str):
            stations_list = [s.strip() for s in stations_param.split(',') if s.strip()]
        else:
            stations_list = stations_param

        start_date = params.get('start_date')
        end_date = params.get('end_date')
        data_source = params.get('data_source', 'default')
        show_anomalies = params.get('show_anomalies', 'false').lower() == 'true'
        # Performance Optimization P4: include_outliers parameter to merge outliers with data endpoint
        include_outliers = params.get('include_outliers', 'false').lower() == 'true'

        logger.info(f"[BATCH REQUEST] Stations: {stations_list}, range={start_date} to {end_date}")

        df = load_data_batch_optimized(
            stations_list=stations_list,
            start_date=start_date,
            end_date=end_date,
            data_source=data_source,
            show_anomalies=show_anomalies or include_outliers  # Include if either is true
        )

        if df.empty:
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({"message": "No data found"})
            }

        agg_level = df['aggregation_level'].iloc[0] if 'aggregation_level' in df.columns else 'raw'

        if 'aggregation_level' in df.columns:
            df = df.drop(columns=['aggregation_level'])

        # Clean up baseline processing columns (keep only anomaly field)
        df = clean_baseline_columns(df)

        df_json = df.copy()

        # Format datetime columns
        for col in df_json.columns:
            if pd.api.types.is_datetime64_any_dtype(df_json[col]):
                if data_source == 'tides' and col == 'Date':
                    df_json[col] = df_json[col].dt.strftime('%d/%m/%Y')
                elif col in ['HighTideTime', 'LowTideTime'] or (col.endswith('Time') and col != 'Tab_DateTime'):
                    df_json[col] = df_json[col].dt.strftime('%H:%M')
                else:
                    df_json[col] = df_json[col].dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        numeric_cols = df_json.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            df_json[col] = df_json[col].replace([np.inf, -np.inf], np.nan).fillna(0)

        response_data = df_json.to_dict('records')

        logger.info(f"[BATCH RESPONSE] Returning {len(response_data)} records for {len(stations_list)} stations (agg: {agg_level})")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "X-Aggregation-Level": agg_level,
                "X-Record-Count": str(len(response_data)),
                "X-Stations-Count": str(len(stations_list))
            },
            "body": json.dumps(response_data, default=str)
        }

    except Exception as e:
        logger.error(f"[BATCH ERROR] Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": str(e)})
        }

def lambda_handler(event, context):
    """Lambda handler with optimized data loading"""
    try:
        params = event.get('queryStringParameters') or {}
        station = params.get('station')
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        data_source = params.get('data_source', 'default')
        show_anomalies = params.get('show_anomalies', 'false').lower() == 'true'
        # Performance Optimization P4: include_outliers parameter to merge outliers with data endpoint
        include_outliers = params.get('include_outliers', 'false').lower() == 'true'

        logger.info(f"[REQUEST] Data request: station={station}, range={start_date} to {end_date}")

        df = load_data_from_db_optimized(
            start_date=start_date,
            end_date=end_date,
            station=station,
            data_source=data_source,
            show_anomalies=show_anomalies or include_outliers  # Include if either is true
        )

        if df.empty:
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({"message": "No data found"})
            }

        agg_level = df['aggregation_level'].iloc[0] if 'aggregation_level' in df.columns else 'raw'

        if 'aggregation_level' in df.columns:
            df = df.drop(columns=['aggregation_level'])

        # Clean up baseline processing columns (keep only anomaly field)
        df = clean_baseline_columns(df)

        df_json = df.copy()

        # FIXED: Proper datetime formatting that doesn't break Tab_DateTime
        for col in df_json.columns:
            if pd.api.types.is_datetime64_any_dtype(df_json[col]):
                if data_source == 'tides' and col == 'Date':
                    # Format tide dates as DD/MM/YYYY only
                    df_json[col] = df_json[col].dt.strftime('%d/%m/%Y')
                elif col in ['HighTideTime', 'LowTideTime'] or (col.endswith('Time') and col != 'Tab_DateTime'):
                    # Format tide time columns as HH:MM only (but NOT Tab_DateTime!)
                    df_json[col] = df_json[col].dt.strftime('%H:%M')
                else:
                    # Format all other datetime columns (including Tab_DateTime) as full ISO format
                    df_json[col] = df_json[col].dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        numeric_cols = df_json.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            df_json[col] = df_json[col].replace([np.inf, -np.inf], np.nan).fillna(0)

        response_data = df_json.to_dict('records')

        if response_data:
            first_date = response_data[0].get('Tab_DateTime') or response_data[0].get('Date', 'N/A')
            last_date = response_data[-1].get('Tab_DateTime') or response_data[-1].get('Date', 'N/A')
            logger.info(f"[RESPONSE] Returning {len(response_data)} records (agg: {agg_level}) from {first_date} to {last_date}")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "X-Aggregation-Level": agg_level,
                "X-Record-Count": str(len(response_data))
            },
            "body": json.dumps(response_data, default=str)
        }

    except Exception as e:
        logger.error(f"[ERROR] Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": str(e)})
        }