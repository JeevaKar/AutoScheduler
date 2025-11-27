from datetime import datetime

def mark_event_time(time_blocks, start_time, end_time):
    # Convert military time "HH:MM" to indices for 15-minute blocks
    start_hour, start_minute = map(int, start_time.split(":"))
    end_hour, end_minute = map(int, end_time.split(":"))
    
    # Calculate the index for the start time
    start_index = start_hour * 4 + start_minute // 15
    
    # Calculate the index for the end time
    end_index = end_hour * 4 + end_minute // 15
    
    # If the event ends after midnight (wraps around to the next day)
    if end_index < start_index:
        end_index += 96  # Wrap around by adding 96 blocks
    
    # Mark the time blocks as 1 in the specified range
    for i in range(start_index, end_index):
        time_blocks[i % 96] = 1  # Use modulo to handle overflow (wrap around to the start)
    
    return time_blocks

def mark_time_blocks(time_blocks):
    # Get the current time
    current_time = datetime.now()
    
    # Get the current hour and minute
    current_hour = current_time.hour
    current_minute = current_time.minute
    
    # Calculate which 15-minute interval we are in
    current_block = (current_hour * 60 + current_minute) // 15
    
    # Mark the intervals up to and including the current one
    for i in range(current_block + 1):
        time_blocks[i] = 1
        
    return time_blocks