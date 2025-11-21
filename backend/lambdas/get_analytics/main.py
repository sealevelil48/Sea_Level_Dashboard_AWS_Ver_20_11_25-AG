"""
Lambda handler for analytical queries using window functions
Provides server-side calculations for rolling averages, trendlines, and comparisons
"""

import json
import logging
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add paths for shared modules
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..', '..')
sys.path.insert(0, backend_dir)

try:
    from shared.database import engine
    from shared.window_functions import AnalyticalQueryBuilder
    DATABASE_AVAILABLE = True
    print("[OK] Database and window functions imported successfully")
except ImportError as e:
    print(f"[ERROR] Import error in get_analytics: {e}")
    DATABASE_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    """
    Lambda handler for analytical queries

    Query Parameters:
        analysis_type: Type of analysis ('rolling_avg', 'trendline', 'station_diff', 'lag_lead')
        station: Station name or 'All Stations'
        station1: First station for comparison
        station2: Second station for comparison
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        window_hours: Comma-separated list of hours for rolling averages (e.g., "3,6,24")
        period_days: Period in days for trendline (7, 30, 90, 365)
        lag_hours: Hours to lag/lead for time analysis (default 1)

    Returns:
        JSON response with analytical data
    """
    try:
        if not DATABASE_AVAILABLE or not engine:
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({"error": "Database not available"})
            }

        params = event.get('queryStringParameters') or {}

        analysis_type = params.get('analysis_type', 'rolling_avg')
        station = params.get('station')
        station1 = params.get('station1')
        station2 = params.get('station2')
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        # Parse window hours (default: 3, 6, 24)
        window_hours_param = params.get('window_hours', '3,6,24')
        try:
            window_hours = [int(h.strip()) for h in window_hours_param.split(',')]
        except:
            window_hours = [3, 6, 24]

        # Parse period days
        period_days = None
        if params.get('period_days'):
            try:
                period_days = int(params.get('period_days'))
            except:
                period_days = None

        # Parse lag hours
        lag_hours = 1
        if params.get('lag_hours'):
            try:
                lag_hours = int(params.get('lag_hours'))
            except:
                lag_hours = 1

        logger.info(f"[ANALYTICS REQUEST] Type: {analysis_type}, Station: {station}")

        # Initialize query builder
        query_builder = AnalyticalQueryBuilder(engine)

        # Execute appropriate analysis
        df = pd.DataFrame()

        if analysis_type == 'rolling_avg':
            df = query_builder.execute_rolling_averages(
                window_hours=window_hours,
                station=station,
                start_date=start_date,
                end_date=end_date
            )

        elif analysis_type == 'trendline':
            df = query_builder.execute_trendline(
                station=station,
                start_date=start_date,
                end_date=end_date,
                period_days=period_days
            )

        elif analysis_type == 'station_diff':
            if not station1 or not station2:
                return {
                    "statusCode": 400,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps({
                        "error": "station1 and station2 parameters required for station_diff analysis"
                    })
                }

            df = query_builder.execute_station_comparison(
                station1=station1,
                station2=station2,
                start_date=start_date,
                end_date=end_date
            )

        elif analysis_type == 'lag_lead':
            df = query_builder.execute_lag_lead_analysis(
                station=station,
                start_date=start_date,
                end_date=end_date,
                lag_hours=lag_hours
            )

        else:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "error": f"Unknown analysis_type: {analysis_type}",
                    "valid_types": ["rolling_avg", "trendline", "station_diff", "lag_lead"]
                })
            }

        if df.empty:
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({"message": "No data found"})
            }

        # Format datetime columns
        df_json = df.copy()
        for col in df_json.columns:
            if pd.api.types.is_datetime64_any_dtype(df_json[col]):
                df_json[col] = df_json[col].dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        # Clean numeric columns
        numeric_cols = df_json.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            df_json[col] = df_json[col].replace([np.inf, -np.inf], np.nan).fillna(0)

        response_data = df_json.to_dict('records')

        logger.info(f"[ANALYTICS RESPONSE] Returning {len(response_data)} records for {analysis_type}")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "X-Analysis-Type": analysis_type,
                "X-Record-Count": str(len(response_data))
            },
            "body": json.dumps(response_data, default=str)
        }

    except Exception as e:
        logger.error(f"[ANALYTICS ERROR] Error: {e}")
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
