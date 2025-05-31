import subprocess

def get_bpm_at_time(fumen_data_item, time_sec, default_bpm=120):
    """
    Finds the BPM active at or immediately before a given time_sec in a fumen.
    fumen_data_item is one item from the processed_fumens_data list.
    """
    active_bpm = None
    all_events = []
    if 'note_events' in fumen_data_item: all_events.extend(fumen_data_item['note_events'])
    if 'timing_events_at_commas' in fumen_data_item: all_events.extend(fumen_data_item['timing_events_at_commas'])
    all_events.sort(key=lambda x: (x.get('time', 0), 1 if x.get('notes_content_raw', '') == "" else 0))

    for event in all_events:
        event_time = event.get('time', 0)
        bpm_at_event = event.get('current_bpm_at_event')
        if event_time <= time_sec:
            if bpm_at_event is not None: active_bpm = bpm_at_event
        else: break 
    
    if active_bpm is None:
        if all_events and all_events[0].get('current_bpm_at_event') is not None:
            return all_events[0]['current_bpm_at_event']
        return default_bpm
    return active_bpm

def snap_to_grid(time_sec, bpm, beats_per_whole_note=4, subdivisions=256):
    """
    Snaps a given time_sec to the nearest grid point based on BPM.
    """
    if not isinstance(bpm, (int, float)) or bpm <= 0:
        print(f"Warning (snap_to_grid): Invalid BPM ({bpm}, type: {type(bpm)}). Returning original time: {time_sec}")
        return time_sec
    beat_duration_sec = 60.0 / bpm
    subdivisions_per_beat = subdivisions / beats_per_whole_note
    smallest_grid_sec = beat_duration_sec / subdivisions_per_beat
    if smallest_grid_sec <= 1e-9: 
        print(f"Warning (snap_to_grid): Grid step too small for BPM {bpm}. Returning original time: {time_sec}")
        return time_sec
    return round(time_sec / smallest_grid_sec) * smallest_grid_sec

def get_audio_duration(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                           'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', path],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return float(result.stdout)
