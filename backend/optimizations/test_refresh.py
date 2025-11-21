#!/usr/bin/env python3
"""
Test SeaTides materialized view refresh with timing
"""
import psycopg2
import time
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'Test2-SeaLevels_Restored',
    'user': 'SeaLevel',
    'password': 'SeLvl123321'
}

def test_refresh():
    """Test the materialized view refresh with timing"""
    print("\n" + "="*60)
    print("TESTING SEATIDES MATERIALIZED VIEW REFRESH")
    print("="*60 + "\n")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # Set optimal memory parameters
        print("[INFO] Setting memory parameters...")
        cur.execute("SET work_mem = '512MB'")
        cur.execute("SET maintenance_work_mem = '1GB'")
        print("[OK] Memory configured\n")

        # Start the refresh
        print("[INFO] Starting materialized view refresh...")
        print(f"[INFO] Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        print("=" * 60)
        print("REFRESHING... (this may take 5-30 minutes)")
        print("=" * 60 + "\n")

        start_time = time.time()

        cur.execute('REFRESH MATERIALIZED VIEW "SeaTides"')
        conn.commit()

        elapsed = time.time() - start_time
        minutes = elapsed / 60
        hours = minutes / 60

        print("\n" + "="*60)
        print("REFRESH COMPLETE!")
        print("="*60)
        print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nTotal time: {elapsed:.1f} seconds")
        print(f"           {minutes:.2f} minutes")
        print(f"           {hours:.2f} hours")

        # Compare with previous time
        print("\n" + "="*60)
        print("PERFORMANCE COMPARISON")
        print("="*60)
        print(f"Before optimization: 17+ hours (17 hr 37 min)")
        print(f"After optimization:  {minutes:.2f} minutes ({hours:.2f} hours)")

        if hours < 1:
            improvement = (17.62 * 60) / minutes  # 17.62 hours = 17h37m
            print(f"\nImprovement: {improvement:.0f}x FASTER!")
            print("\nSUCCESS! The optimization worked perfectly!")
        else:
            print(f"\nStill slow. May need additional optimization.")

        print("\n")

    except Exception as e:
        elapsed = time.time() - start_time
        minutes = elapsed / 60
        print(f"\n[ERROR] Refresh failed after {minutes:.2f} minutes: {e}\n")
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    test_refresh()
