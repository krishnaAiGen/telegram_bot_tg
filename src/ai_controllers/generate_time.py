#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Oct 27 18:49:28 2024

@author: krishnayadav
"""

from datetime import datetime, timedelta
import pytz

def generate_minute_timestamps(start_date, end_date):
    """
    Generates a list of timestamps at one-minute intervals within the specified range.

    Args:
        start_date (str): Start date in 'YYYY-MM-DD HH:MM:SS' format.
        end_date (str): End date in 'YYYY-MM-DD HH:MM:SS' format.

    Returns:
        list: List of datetime objects at one-minute intervals.
    """
    # Define timezone
    timezone = pytz.timezone('Asia/Kolkata')
    
    # Parse input dates
    start_time = timezone.localize(datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S'))
    end_time = timezone.localize(datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S'))
    
    # Generate list of timestamps
    timestamps = []
    current_time = start_time
    while current_time <= end_time:
        timestamps.append(current_time)
        current_time += timedelta(minutes=1)
    
    return timestamps
