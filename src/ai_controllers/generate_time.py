# src/ai_controllers/generate_time.py
from datetime import datetime, timedelta
import pytz

def generate_minute_timestamps(start_date: str, end_date: str, timezone_str: str = 'Asia/Kolkata') -> list[datetime]:
    """
    Generates a list of datetime objects at one-minute intervals within a specified date range and timezone.
    """
    try:
        timezone = pytz.timezone(timezone_str)
        start_time_naive = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
        end_time_naive = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
        start_time_aware = timezone.localize(start_time_naive)
        end_time_aware = timezone.localize(end_time_naive)
    except ValueError:
        print("Error: Invalid date format. Please use 'YYYY-MM-DD HH:MM:SS'.")
        return []
    except pytz.UnknownTimeZoneError:
        print(f"Error: Unknown timezone '{timezone_str}'.")
        return []

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
    start = "2024-06-10 14:00:00"
    end = "2024-06-10 14:10:00"
    
    timestamp_list = generate_minute_timestamps(start, end)
    
    if timestamp_list:
        print(f"Generated {len(timestamp_list)} timestamps from {start} to {end}:")
        for ts in timestamp_list:
            print(ts.isoformat())