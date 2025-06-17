# scripts/generate_time.py
from datetime import datetime, timedelta
import pytz
from typing import List

def generate_minute_timestamps(start_date: str, end_date: str, timezone_str: str = 'Asia/Kolkata') -> List[datetime]:
    """
    Generates a list of datetime objects at one-minute intervals within a
    specified date range and timezone. This function is preserved from the original codebase.
    """
    try:
        # Create a timezone object from the provided string.
        timezone = pytz.timezone(timezone_str)
        
        # Parse the input date strings into "naive" datetime objects.
        start_time_naive = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
        end_time_naive = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')

        # Localize the naive datetimes, making them "aware" of their timezone. This is best practice.
        start_time_aware = timezone.localize(start_time_naive)
        end_time_aware = timezone.localize(end_time_naive)
    except ValueError:
        print("Error: Invalid date format. Please use 'YYYY-MM-DD HH:MM:SS'.")
        return []
    except pytz.UnknownTimeZoneError:
        print(f"Error: Unknown timezone '{timezone_str}'.")
        return []

    # A logical check to ensure the date range is valid.
    if start_time_aware > end_time_aware:
        print("Error: Start date cannot be after the end date.")
        return []

    timestamps = []
    current_time = start_time_aware
    while current_time <= end_time_aware:
        timestamps.append(current_time)
        current_time += timedelta(minutes=1)
    
    return timestamps

if __name__ == "__main__":
    # Provides a clear example of how to use this script from the command line.
    print("--- Timestamp Generation Utility ---")
    start_example = "2024-06-15 10:00:00"
    end_example = "2024-06-15 10:05:00"
    
    timestamp_list = generate_minute_timestamps(start_example, end_example)
    
    if timestamp_list:
        print(f"\nGenerated {len(timestamp_list)} timestamps from {start_example} to {end_example}:")
        for ts in timestamp_list:
            # .isoformat() is a standard, unambiguous way to print datetime objects.
            print(ts.isoformat())

    # Example of an error being handled gracefully.
    print("\n--- Testing Error Handling ---")
    generate_minute_timestamps("15-06-2024 10:00:00", end_example)