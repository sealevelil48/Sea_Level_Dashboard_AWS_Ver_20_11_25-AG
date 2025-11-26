# Python Docstrings Examples

This document provides comprehensive docstring examples for key Python functions in the Sea Level Dashboard backend application, following Google-style docstring format.

## Table of Contents

- [API Endpoints (local_server.py)](#api-endpoints-local_serverpy)
- [Lambda Handlers](#lambda-handlers)
- [Database Module](#database-module)
- [Data Processing](#data-processing)
- [Utility Functions](#utility-functions)

---

## API Endpoints (local_server.py)

### Health Check Endpoint

```python
@app.get("/api/health")
async def health_check():
    """Perform system health check and return status information.

    Checks the health of the database connection, Redis cache, and returns
    performance metrics if available.

    Returns:
        dict: Health status information containing:
            - status (str): Overall health status ('healthy' or 'unhealthy')
            - timestamp (str): ISO format timestamp
            - platform (str): Operating system platform
            - python_version (str): Python version information
            - database (str): Database connection status
            - cache (dict, optional): Redis cache status and metrics
            - metrics (dict, optional): Performance metrics from database manager

    Example:
        >>> response = await health_check()
        >>> print(response['status'])
        'healthy'
        >>> print(response['database'])
        'connected'

    Note:
        This endpoint is useful for monitoring and health checking by
        load balancers and orchestration systems.
    """
    # Implementation details...
```

### Get Stations Endpoint

```python
@app.get("/api/stations")
async def get_stations():
    """Retrieve list of all monitoring stations.

    Fetches available sea level monitoring stations from the database.
    Returns a fallback list if database is unavailable.

    Returns:
        dict: Response containing:
            - stations (list[str]): List of station names
            - database_available (bool): Whether database connection is active
            - error (str, optional): Error message if request failed

    Example:
        >>> response = await get_stations()
        >>> print(response['stations'])
        ['Acre', 'Yafo', 'Ashkelon', 'Eilat', 'All Stations']

    Raises:
        Exception: Logs error and returns fallback stations if database fails
    """
    # Implementation details...
```

### Get Data Endpoint

```python
@app.get("/api/data")
async def get_data(
    station: str = "All Stations",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    data_source: str = "default",
    limit: int = 15000
):
    """Fetch historical sea level data with pagination and caching.

    Retrieves time-series data for sea level measurements with optional
    filtering by station, date range, and data source. Implements caching
    and pagination for performance.

    Args:
        station (str, optional): Station name or "All Stations".
            Defaults to "All Stations".
        start_date (str, optional): Start date in YYYY-MM-DD format.
            Defaults to 7 days ago if not specified.
        end_date (str, optional): End date in YYYY-MM-DD format.
            Defaults to today if not specified.
        data_source (str, optional): Data source type. Defaults to "default".
        limit (int, optional): Maximum number of records to return.
            Defaults to 15000.

    Returns:
        JSONResponse: Array of data records, each containing:
            - Station (str): Station name
            - Tab_DateTime (str): ISO format timestamp
            - Tab_Value (float): Sea level value in meters
            - Tab_Temp (float, optional): Temperature in Celsius

    Raises:
        HTTPException: If date format is invalid (400)
        HTTPException: If date range exceeds 365 days (400)
        HTTPException: If start_date is after end_date (400)
        HTTPException: If station not found (404)
        HTTPException: For internal server errors (500)

    Example:
        >>> # Get last 7 days of data for Acre
        >>> data = await get_data(
        ...     station="Acre",
        ...     start_date="2025-01-01",
        ...     end_date="2025-01-07"
        ... )
        >>> print(len(data))
        1680  # 7 days * 24 hours * 10 measurements/hour

    Note:
        - Response includes X-Response-Time and X-Cache headers
        - Cached responses expire after 120 seconds
        - Date validation ensures YYYY-MM-DD format
        - Maximum date range is 365 days
    """
    # Implementation details...
```

### Get Outliers Endpoint

```python
@app.get("/api/outliers")
async def get_outliers(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    station: str = "All Stations"
):
    """Detect anomalies using Enhanced Southern Baseline Rules.

    Applies the Southern Baseline outlier detection algorithm to identify
    anomalous sea level measurements. Returns detailed validation statistics
    and outlier information.

    Args:
        start_date (str, optional): Start date for analysis (YYYY-MM-DD).
            Defaults to 7 days ago.
        end_date (str, optional): End date for analysis (YYYY-MM-DD).
            Defaults to today.
        station (str, optional): Station name or "All Stations".
            Defaults to "All Stations".

    Returns:
        JSONResponse: Outlier detection results containing:
            - outliers (list[dict]): List of detected outliers with:
                - Station (str): Station name
                - Tab_DateTime (str): Timestamp of outlier
                - Tab_Value (float): Measured value
                - expected_value (float): Expected value from baseline
                - deviation (float): Difference from expected
                - rule_violated (str): Which baseline rule was violated
            - total_records (int): Total records analyzed
            - outliers_detected (int): Number of outliers found
            - outlier_percentage (float): Percentage of data flagged
            - validation (dict): Validation statistics:
                - total_validations (int): Number of validations performed
                - total_exclusions (int): Records excluded by rules
                - exclusion_rate (float): Percentage excluded
                - baseline_calculations (int): Baseline calculations performed
            - processing_time_seconds (float): Time taken to process
            - timestamp (str): ISO timestamp of analysis

    Raises:
        HTTPException: If baseline API not available (503)
        HTTPException: If processing times out (408)
        HTTPException: For internal server errors (500)

    Example:
        >>> result = await get_outliers(
        ...     station="Acre",
        ...     start_date="2025-01-01",
        ...     end_date="2025-01-31"
        ... )
        >>> print(f"Found {result['outliers_detected']} outliers")
        >>> print(f"Outlier rate: {result['outlier_percentage']:.2f}%")
        Found 23 outliers
        Outlier rate: 1.37%

    Note:
        - Processing limited to 5000 records for performance
        - Timeout set to 30 seconds for large datasets
        - Supports filtering by station after detection
        - Returns empty result with status 200 if no data found
    """
    # Implementation details...
```

### Get Predictions Endpoint

```python
@app.get("/api/predictions")
async def get_predictions(
    stations: Optional[str] = None,
    station: Optional[str] = None,
    model: str = "kalman",
    steps: int = 240,
    forecast_hours: Optional[int] = None
):
    """Generate sea level predictions using specified forecasting model.

    Produces time-series forecasts for sea level measurements using either
    Kalman Filter or Prophet models. Supports multiple stations and
    configurable forecast horizons.

    Args:
        stations (str, optional): Comma-separated list of station names.
        station (str, optional): Single station name (alternative to stations).
        model (str, optional): Forecasting model to use. Options:
            - "kalman": Kalman Filter (fast, short-term accuracy)
            - "prophet": Facebook Prophet (seasonal patterns, long-term)
            Defaults to "kalman".
        steps (int, optional): Number of 6-minute forecast steps.
            Defaults to 240 (24 hours).
        forecast_hours (int, optional): Alternative to steps, specified in hours.
            If provided, overrides steps parameter.

    Returns:
        JSONResponse: Predictions by station containing:
            - <station_name> (dict): Predictions for each station:
                - timestamps (list[str]): ISO format forecast timestamps
                - values (list[float]): Predicted sea level values
                - confidence_lower (list[float]): Lower confidence bound
                - confidence_upper (list[float]): Upper confidence bound
                - model_used (str): Name of model used
                - forecast_horizon_hours (int): Forecast duration
            - metadata (dict): Prediction metadata:
                - generated_at (str): Timestamp of generation
                - model_parameters (dict): Model configuration used

    Raises:
        HTTPException: If no station parameter provided (400)
        HTTPException: If model name invalid (400)
        HTTPException: For internal server errors (500)

    Example:
        >>> # Get 48-hour forecast for Acre using Kalman filter
        >>> predictions = await get_predictions(
        ...     stations="Acre",
        ...     model="kalman",
        ...     forecast_hours=48
        ... )
        >>> acre_forecast = predictions['Acre']
        >>> print(f"Forecast: {len(acre_forecast['values'])} points")
        Forecast: 480 points

        >>> # Multi-station Prophet forecast
        >>> predictions = await get_predictions(
        ...     stations="Acre,Yafo,Eilat",
        ...     model="prophet",
        ...     forecast_hours=168  # 7 days
        ... )

    Note:
        - Kalman Filter: Best for 24-72 hour forecasts, low latency
        - Prophet: Best for weekly/seasonal forecasts, captures trends
        - Steps parameter: 1 step = 6 minutes (10 steps/hour)
        - Supports both 'stations' and 'station' parameters
    """
    # Implementation details...
```

---

## Lambda Handlers

### Get Stations Lambda

```python
def lambda_handler(event: dict, context: Optional[Any] = None) -> dict:
    """Lambda handler for retrieving monitoring station list.

    AWS Lambda function that queries the database for available monitoring
    stations and returns them in a standardized format.

    Args:
        event (dict): Lambda event object containing:
            - httpMethod (str): HTTP method (should be 'GET')
            - path (str): Request path
            - queryStringParameters (dict, optional): Query parameters
        context (Any, optional): Lambda context object (unused)

    Returns:
        dict: Lambda response object containing:
            - statusCode (int): HTTP status code (200, 500)
            - headers (dict): Response headers
            - body (str): JSON string of response data:
                - stations (list[str]): List of station names
                - count (int): Number of stations
                - database_available (bool): Database status

    Example:
        >>> event = {
        ...     'httpMethod': 'GET',
        ...     'path': '/stations',
        ...     'queryStringParameters': {}
        ... }
        >>> response = lambda_handler(event, None)
        >>> import json
        >>> data = json.loads(response['body'])
        >>> print(data['stations'])
        ['Acre', 'Haifa', 'Ashdod', 'Ashkelon', 'Yafo', 'Eilat']

    Raises:
        Returns error response (not exception) with statusCode 500

    Note:
        - Includes database connection pooling
        - Falls back to default station list if database unavailable
        - Logs all database errors for monitoring
    """
    # Implementation details...
```

### Get Data Lambda

```python
def lambda_handler_batch(event: dict, context: Optional[Any] = None) -> dict:
    """Batch lambda handler for retrieving data for multiple stations.

    Optimized Lambda function for fetching sea level data for multiple
    stations in a single request, reducing network overhead.

    Args:
        event (dict): Lambda event object containing:
            - httpMethod (str): HTTP method ('GET')
            - path (str): Request path ('/data/batch')
            - queryStringParameters (dict): Query parameters:
                - stations (str): Comma-separated station names
                - start_date (str): Start date (YYYY-MM-DD)
                - end_date (str): End date (YYYY-MM-DD)
                - data_source (str, optional): Data source type
                - show_anomalies (str, optional): 'true' or 'false'
                - include_outliers (str, optional): 'true' or 'false'
        context (Any, optional): Lambda context object

    Returns:
        dict: Lambda response with batch data:
            - statusCode (int): HTTP status code
            - headers (dict): Response headers including cache control
            - body (str): JSON array of data records for all stations

    Example:
        >>> event = {
        ...     'httpMethod': 'GET',
        ...     'path': '/data/batch',
        ...     'queryStringParameters': {
        ...         'stations': 'Acre,Yafo,Eilat',
        ...         'start_date': '2025-01-01',
        ...         'end_date': '2025-01-07'
        ...     }
        ... }
        >>> response = lambda_handler_batch(event, None)
        >>> data = json.loads(response['body'])
        >>> # Data contains records from all 3 stations
        >>> len(data)  # Total records across all stations
        5040

    Note:
        - Uses single database query for all stations (performance)
        - Implements database connection pooling
        - Returns combined dataset (not grouped by station)
        - Supports anomaly detection flags
        - Includes response compression for large datasets
    """
    # Implementation details...
```

---

## Database Module

### Database Manager Class

```python
class DatabaseManager:
    """Manages database connections and caching for the Sea Level Dashboard.

    Provides a unified interface for database operations with connection pooling,
    Redis caching, and performance monitoring.

    Attributes:
        engine (Engine): SQLAlchemy database engine
        SessionLocal (sessionmaker): Session factory for creating DB sessions
        _redis_client (Redis, optional): Redis client for caching
        _query_count (int): Number of queries executed
        _cache_hits (int): Number of cache hits
        _cache_misses (int): Number of cache misses

    Example:
        >>> db_manager = DatabaseManager(
        ...     database_url="postgresql://user:pass@localhost/sealevel",
        ...     redis_url="redis://localhost:6379/0"
        ... )
        >>>
        >>> # Use in context manager
        >>> with db_manager.get_session() as session:
        ...     stations = session.query(L.Station).distinct().all()
        ...
        >>> # Check health
        >>> if db_manager.health_check():
        ...     print("Database is healthy")
        ...
        >>> # Get performance metrics
        >>> metrics = db_manager.get_metrics()
        >>> print(f"Cache hit rate: {metrics['cache_hit_rate']}")

    Note:
        - Automatically handles connection pooling
        - Thread-safe for concurrent access
        - Implements automatic reconnection on failure
        - Caches frequently accessed queries
    """

    def __init__(
        self,
        database_url: str,
        redis_url: Optional[str] = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30
    ):
        """Initialize DatabaseManager with connection pooling.

        Args:
            database_url (str): PostgreSQL connection string
            redis_url (str, optional): Redis connection string for caching
            pool_size (int, optional): Number of persistent connections.
                Defaults to 10.
            max_overflow (int, optional): Max overflow connections beyond pool.
                Defaults to 20.
            pool_timeout (int, optional): Timeout for getting connection from pool.
                Defaults to 30 seconds.

        Raises:
            ValueError: If database_url is invalid
            RuntimeError: If database connection fails
        """
        # Implementation details...

    def get_session(self) -> Generator:
        """Get a database session with automatic cleanup.

        Context manager that provides a database session and ensures
        proper cleanup even if an exception occurs.

        Yields:
            Session: SQLAlchemy database session

        Example:
            >>> with db_manager.get_session() as session:
            ...     result = session.query(L).filter(L.Station == 'Acre').all()
            ...     # Session automatically committed and closed

        Raises:
            SQLAlchemyError: If database operation fails
        """
        # Implementation details...

    def health_check(self) -> bool:
        """Check database connectivity.

        Performs a simple query to verify the database is accessible
        and responding.

        Returns:
            bool: True if database is healthy, False otherwise

        Example:
            >>> if db_manager.health_check():
            ...     print("Database OK")
            ... else:
            ...     print("Database DOWN - alerting team")
        """
        # Implementation details...

    def get_metrics(self) -> dict:
        """Get performance metrics for monitoring.

        Returns statistics about database usage, cache performance,
        and connection pool status.

        Returns:
            dict: Performance metrics containing:
                - query_count (int): Total queries executed
                - cache_hits (int): Number of cache hits
                - cache_misses (int): Number of cache misses
                - cache_hit_rate (str): Cache hit percentage
                - pool_size (int): Current connection pool size
                - pool_checked_out (int): Connections currently in use
                - pool_overflow (int): Overflow connections created

        Example:
            >>> metrics = db_manager.get_metrics()
            >>> print(f"Queries: {metrics['query_count']}")
            >>> print(f"Cache efficiency: {metrics['cache_hit_rate']}")
            Queries: 1523
            Cache efficiency: 78.5%
        """
        # Implementation details...
```

### Data Loading Function

```python
def load_data_from_db(
    start_date: str,
    end_date: str,
    station: str = "All Stations",
    limit: int = 15000
) -> Optional[pd.DataFrame]:
    """Load sea level data from database into pandas DataFrame.

    Queries the database for sea level measurements within the specified
    date range and station filter, returning results as a DataFrame.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        station (str, optional): Station name or "All Stations".
            Defaults to "All Stations".
        limit (int, optional): Maximum number of records. Defaults to 15000.

    Returns:
        pd.DataFrame or None: DataFrame with columns:
            - Station (str): Station name
            - Tab_DateTime (datetime): Measurement timestamp
            - Tab_Value (float): Sea level in meters
            - Tab_Temp (float, optional): Temperature in Celsius
        Returns None if no data found or error occurs.

    Raises:
        ValueError: If date format is invalid
        DatabaseError: If database query fails (logged, not raised)

    Example:
        >>> df = load_data_from_db(
        ...     start_date='2025-01-01',
        ...     end_date='2025-01-07',
        ...     station='Acre'
        ... )
        >>> print(df.shape)
        (1680, 4)
        >>> print(df['Tab_Value'].mean())
        1.234

        >>> # Load all stations
        >>> df_all = load_data_from_db(
        ...     start_date='2025-01-01',
        ...     end_date='2025-01-01',
        ...     station='All Stations'
        ... )
        >>> print(df_all['Station'].unique())
        ['Acre' 'Haifa' 'Ashdod' 'Ashkelon' 'Yafo' 'Eilat']

    Note:
        - Automatically sorts by timestamp
        - Converts timestamp strings to datetime objects
        - Handles NULL values appropriately
        - Uses database indexes for performance
    """
    # Implementation details...
```

---

## Data Processing

### Baseline Integration

```python
def get_outliers_api(df: pd.DataFrame) -> dict:
    """Detect outliers using Enhanced Southern Baseline Rules.

    Applies the Southern Baseline outlier detection algorithm with enhanced
    validation statistics. Identifies anomalous sea level measurements based
    on statistical deviation from expected values.

    Args:
        df (pd.DataFrame): Input data with columns:
            - Station (str): Station name
            - Tab_DateTime (datetime): Timestamp
            - Tab_Value (float): Measured sea level value
            - Tab_Temp (float, optional): Temperature

    Returns:
        dict: Outlier detection results:
            - outliers (list[dict]): Detected outliers, each containing:
                - Station (str): Station name
                - Tab_DateTime (str): ISO timestamp
                - Tab_Value (float): Measured value
                - expected_value (float): Expected value from baseline
                - deviation (float): Deviation from expected
                - rule_violated (str): Rule that flagged this outlier
                - confidence (float): Confidence score (0-1)
            - total_records (int): Total records analyzed
            - outliers_detected (int): Number of outliers found
            - outlier_percentage (float): Percentage flagged as outliers
            - validation (dict): Validation statistics:
                - total_validations (int): Validations performed
                - total_exclusions (int): Records excluded by rules
                - exclusion_rate (float): Exclusion percentage
                - baseline_calculations (int): Baseline calcs performed
            - timestamp (str): ISO timestamp of analysis

    Example:
        >>> import pandas as pd
        >>> df = load_data_from_db('2025-01-01', '2025-01-07', 'Acre')
        >>> result = get_outliers_api(df)
        >>>
        >>> print(f"Analyzed {result['total_records']} records")
        >>> print(f"Found {result['outliers_detected']} outliers")
        >>> print(f"Outlier rate: {result['outlier_percentage']:.2f}%")
        Analyzed 1680 records
        Found 23 outliers
        Outlier rate: 1.37%
        >>>
        >>> # Examine first outlier
        >>> outlier = result['outliers'][0]
        >>> print(f"Timestamp: {outlier['Tab_DateTime']}")
        >>> print(f"Measured: {outlier['Tab_Value']:.3f}m")
        >>> print(f"Expected: {outlier['expected_value']:.3f}m")
        >>> print(f"Deviation: {outlier['deviation']:.3f}m")

    Note:
        - Uses statistical thresholds based on historical data
        - Accounts for tidal patterns and seasonal variations
        - Validates data quality before analysis
        - Performance: ~0.1-2 seconds for 7 days of data
    """
    # Implementation details...
```

### Corrections API

```python
def get_corrections_api(df: pd.DataFrame) -> dict:
    """Generate correction suggestions for detected outliers.

    Analyzes outliers and provides suggested corrected values based on
    interpolation, neighboring stations, and historical patterns.

    Args:
        df (pd.DataFrame): Data with outliers (must include all stations)

    Returns:
        dict: Correction suggestions:
            - suggestions (list[dict]): Correction recommendations:
                - station (str): Station name
                - timestamp (str): Timestamp of outlier
                - original_value (float): Measured value
                - suggested_value (float): Recommended correction
                - confidence (float): Confidence in suggestion (0-1)
                - method (str): Method used for correction:
                    - 'interpolation': Time-based interpolation
                    - 'station_baseline': Based on other stations
                    - 'historical_average': Historical pattern match
                - neighbors (list[dict], optional): Supporting data from
                    neighboring stations
            - total_suggestions (int): Number of corrections suggested
            - timestamp (str): ISO timestamp of analysis

    Example:
        >>> df = load_data_from_db('2025-01-01', '2025-01-07', 'All Stations')
        >>> corrections = get_corrections_api(df)
        >>>
        >>> for suggestion in corrections['suggestions']:
        ...     print(f"{suggestion['station']} @ {suggestion['timestamp']}")
        ...     print(f"  Original: {suggestion['original_value']:.3f}m")
        ...     print(f"  Suggested: {suggestion['suggested_value']:.3f}m")
        ...     print(f"  Method: {suggestion['method']}")
        ...     print(f"  Confidence: {suggestion['confidence']:.2f}")
        Acre @ 2025-01-03T14:30:00
          Original: 2.456m
          Suggested: 1.234m
          Method: station_baseline
          Confidence: 0.92

    Note:
        - Requires data from all stations for accurate baseline
        - Higher confidence for interpolation method (temporal continuity)
        - Lower confidence for historical average (pattern matching)
        - Does not modify original data, only provides suggestions
    """
    # Implementation details...
```

---

## Utility Functions

### Date Utilities

```python
def parse_date_param(date_str: Optional[str], default_days_ago: int = 7) -> str:
    """Parse and validate date parameter with default fallback.

    Args:
        date_str (str, optional): Date string in YYYY-MM-DD format
        default_days_ago (int, optional): Days before today for default.
            Defaults to 7.

    Returns:
        str: Validated date string in YYYY-MM-DD format

    Raises:
        ValueError: If date format is invalid

    Example:
        >>> parse_date_param('2025-01-15')
        '2025-01-15'
        >>> parse_date_param(None, default_days_ago=30)
        '2024-12-26'  # Assuming today is 2025-01-25
        >>> parse_date_param('invalid-date')
        ValueError: Invalid date format. Use YYYY-MM-DD
    """
    # Implementation details...
```

### Logging Utilities

```python
def sanitize_log_input(input_str: str, max_length: int = 100) -> str:
    """Sanitize user input for safe logging.

    Removes newlines and control characters that could cause log injection
    attacks or log corruption.

    Args:
        input_str (str): Input string to sanitize
        max_length (int, optional): Maximum allowed length. Defaults to 100.

    Returns:
        str: Sanitized string safe for logging

    Example:
        >>> # Prevent log injection
        >>> user_input = "Acre\\nFAKE LOG: User logged in"
        >>> safe_input = sanitize_log_input(user_input)
        >>> logger.info(f"Station selected: {safe_input}")
        # Logs: "Station selected: AcreFAKE LOG: User logged in"
        # (newline removed, preventing fake log entry)

        >>> # Truncate long inputs
        >>> long_input = "A" * 200
        >>> sanitize_log_input(long_input, max_length=50)
        'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    """
    # Implementation details...
```

---

## Complete Function Example

Here's a complete, production-ready example with comprehensive docstring:

```python
def calculate_tidal_prediction(
    station: str,
    historical_data: pd.DataFrame,
    forecast_hours: int = 24,
    model_type: str = "kalman",
    confidence_level: float = 0.95
) -> dict:
    """Calculate tidal predictions using specified forecasting model.

    Generates time-series predictions for sea level based on historical
    patterns, astronomical tide calculations, and machine learning models.
    Provides confidence intervals based on historical forecast accuracy.

    Args:
        station (str): Name of monitoring station (e.g., 'Acre', 'Yafo')
        historical_data (pd.DataFrame): Historical measurements with columns:
            - Tab_DateTime (datetime): Timestamps
            - Tab_Value (float): Sea level values in meters
            Minimum 7 days of data recommended for accuracy.
        forecast_hours (int, optional): Forecast horizon in hours.
            Range: 1-168 (1 week). Defaults to 24.
        model_type (str, optional): Forecasting algorithm. Options:
            - 'kalman': Kalman Filter (best for 24-72 hours)
            - 'prophet': Facebook Prophet (best for weekly forecasts)
            - 'arima': ARIMA model (balanced approach)
            Defaults to 'kalman'.
        confidence_level (float, optional): Confidence level for intervals.
            Range: 0.80-0.99. Defaults to 0.95 (95% confidence).

    Returns:
        dict: Prediction results containing:
            - predictions (list[dict]): Forecast points, each with:
                - timestamp (str): ISO format forecast timestamp
                - value (float): Predicted sea level in meters
                - confidence_lower (float): Lower confidence bound
                - confidence_upper (float): Upper confidence bound
            - metadata (dict): Prediction metadata:
                - station (str): Station name
                - model_used (str): Model type used
                - forecast_horizon_hours (int): Forecast duration
                - confidence_level (float): Confidence level
                - generated_at (str): ISO timestamp of generation
                - model_accuracy (dict): Historical accuracy metrics:
                    - mape (float): Mean Absolute Percentage Error
                    - rmse (float): Root Mean Squared Error
                    - r2_score (float): R² score
            - warnings (list[str], optional): Any warnings during calculation

    Raises:
        ValueError: If forecast_hours out of range (1-168)
        ValueError: If confidence_level out of range (0.80-0.99)
        ValueError: If model_type not recognized
        ValueError: If insufficient historical data provided
        RuntimeError: If model fitting fails

    Example:
        >>> import pandas as pd
        >>> from datetime import datetime, timedelta
        >>>
        >>> # Load historical data
        >>> df = load_data_from_db(
        ...     start_date='2025-01-01',
        ...     end_date='2025-01-14',
        ...     station='Acre'
        ... )
        >>>
        >>> # Generate 48-hour forecast
        >>> forecast = calculate_tidal_prediction(
        ...     station='Acre',
        ...     historical_data=df,
        ...     forecast_hours=48,
        ...     model_type='kalman',
        ...     confidence_level=0.95
        ... )
        >>>
        >>> # Display results
        >>> print(f"Model: {forecast['metadata']['model_used']}")
        >>> print(f"Accuracy (MAPE): {forecast['metadata']['model_accuracy']['mape']:.2f}%")
        >>> print(f"Forecast points: {len(forecast['predictions'])}")
        Model: kalman
        Accuracy (MAPE): 2.34%
        Forecast points: 480
        >>>
        >>> # Plot first prediction
        >>> first_pred = forecast['predictions'][0]
        >>> print(f"Time: {first_pred['timestamp']}")
        >>> print(f"Predicted: {first_pred['value']:.3f}m")
        >>> print(f"95% CI: [{first_pred['confidence_lower']:.3f}, "
        ...       f"{first_pred['confidence_upper']:.3f}]")
        Time: 2025-01-15T00:00:00
        Predicted: 1.234m
        95% CI: [1.187, 1.281]
        >>>
        >>> # Compare models
        >>> for model in ['kalman', 'prophet', 'arima']:
        ...     forecast = calculate_tidal_prediction(
        ...         station='Acre',
        ...         historical_data=df,
        ...         forecast_hours=24,
        ...         model_type=model
        ...     )
        ...     mape = forecast['metadata']['model_accuracy']['mape']
        ...     print(f"{model.upper()}: MAPE = {mape:.2f}%")
        KALMAN: MAPE = 2.34%
        PROPHET: MAPE = 3.12%
        ARIMA: MAPE = 2.89%

    Note:
        Performance characteristics:
        - Kalman Filter: ~0.5 seconds for 48-hour forecast
        - Prophet: ~3-5 seconds (model fitting overhead)
        - ARIMA: ~2-3 seconds

        Model selection guidelines:
        - Kalman: Best for short-term (24-72h), real-time updates
        - Prophet: Best for seasonal patterns, weekly forecasts
        - ARIMA: Balanced for most use cases

        Confidence intervals are calculated using:
        - Historical forecast errors (backtesting)
        - Model-specific uncertainty estimates
        - Wider intervals for longer horizons

    References:
        - Kalman, R. E. (1960). "A New Approach to Linear Filtering"
        - Taylor & Letham (2017). "Forecasting at Scale" (Prophet)
        - Box & Jenkins (1970). "Time Series Analysis" (ARIMA)
    """
    # Implementation would go here
    pass
```

---

## Summary

These docstring examples follow Google-style Python docstrings and include:

1. **One-line summary**: Brief description of function purpose
2. **Detailed description**: Extended explanation of functionality
3. **Args**: All parameters with types and descriptions
4. **Returns**: Return type and structure documentation
5. **Raises**: All possible exceptions
6. **Examples**: Practical usage examples with expected output
7. **Note**: Additional context, performance notes, best practices
8. **References**: Academic or technical references (where applicable)

To apply these to your codebase:

1. Add docstrings to all public functions and classes
2. Use type hints in function signatures
3. Keep examples up-to-date with actual API
4. Generate documentation with Sphinx:
   ```bash
   pip install sphinx
   sphinx-apidoc -o docs/ backend/
   cd docs/
   make html
   ```

This provides comprehensive, maintainable documentation that helps developers understand and use your code effectively.
