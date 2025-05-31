from copy import deepcopy
import math

from . import util


def crop(self, crop_start_sec, crop_end_sec, difficulty_indices=None):
    """
    Crops the loaded Simai chart.
    Modifies self.chart_data.
    Event times in the input JSON are assumed to be absolute from the original audio start (0.0s).
    Args:
        crop_start_sec (float): Desired start time for cropping (absolute seconds from original audio).
        crop_end_sec (float): Desired end time for cropping (absolute seconds from original audio).
        difficulty_indices (list, optional): Indices (0-6) of difficulties to crop. None for all.
    Returns:
        self for chaining.
    """
    if not self.chart_data:
        print("错误：裁剪前请先加载谱面数据。")
        return self

    temp_chart_data = deepcopy(self.chart_data)
    original_fumens_list = temp_chart_data.get('fumens_data', [])
    original_levels = temp_chart_data['metadata'].get('levels', [""] * 7)

    chart_wide_bpm_fallback_val = temp_chart_data['metadata'].get('wholebpm')
    if not isinstance(chart_wide_bpm_fallback_val, (int, float)) or chart_wide_bpm_fallback_val <= 0:
        chart_wide_bpm_fallback_val = 120.0

    indices_to_process = difficulty_indices
    if indices_to_process is None:
        indices_to_process = []
        if original_fumens_list:
            for i, fumen in enumerate(original_fumens_list):
                has_events = fumen and (fumen.get('note_events') or fumen.get('timing_events_at_commas'))
                has_level = i < len(original_levels) and original_levels[i]
                if has_events or has_level:
                    indices_to_process.append(i)
            if not indices_to_process and original_fumens_list:
                indices_to_process = list(range(len(original_fumens_list)))
        elif len(original_levels) > 0:
            indices_to_process = [i for i, lv in enumerate(original_levels) if lv]

    actual_snapped_audio_crop_start_time = crop_start_sec
    if indices_to_process:
        bpm_calc_fumen_idx = -1
        if original_fumens_list:
            for idx_check in indices_to_process:
                if 0 <= idx_check < len(original_fumens_list) and original_fumens_list[idx_check]:
                    bpm_calc_fumen_idx = idx_check
                    break

        if bpm_calc_fumen_idx != -1 and original_fumens_list:
            fumen_for_bpm_calc = original_fumens_list[bpm_calc_fumen_idx]
            bpm_at_desired_crop_start = util.get_bpm_at_time(fumen_for_bpm_calc, crop_start_sec,
                                                             chart_wide_bpm_fallback_val)
            actual_snapped_audio_crop_start_time = util.snap_to_grid(crop_start_sec, bpm_at_desired_crop_start)
        else:
            actual_snapped_audio_crop_start_time = util.snap_to_grid(crop_start_sec, chart_wide_bpm_fallback_val)
    else:
        actual_snapped_audio_crop_start_time = util.snap_to_grid(crop_start_sec, chart_wide_bpm_fallback_val)

    original_metadata_first_offset = temp_chart_data['metadata'].get('first_offset_sec', 0.0)
    new_metadata_first_offset = original_metadata_first_offset - actual_snapped_audio_crop_start_time

    if new_metadata_first_offset < -1e-6:
        bpm_at_actual_audio_crop_start = chart_wide_bpm_fallback_val
        fumen_for_bpm_at_actual_start = None
        if original_fumens_list and indices_to_process:
            for f_idx in indices_to_process:
                if 0 <= f_idx < len(original_fumens_list) and original_fumens_list[f_idx] and \
                        (original_fumens_list[f_idx].get('note_events') or original_fumens_list[f_idx].get(
                            'timing_events_at_commas')):
                    fumen_for_bpm_at_actual_start = original_fumens_list[f_idx]
                    break
        if not fumen_for_bpm_at_actual_start and original_fumens_list:
            for f_data in original_fumens_list:
                if f_data and (f_data.get('note_events') or f_data.get('timing_events_at_commas')):
                    fumen_for_bpm_at_actual_start = f_data
                    break

        if fumen_for_bpm_at_actual_start:
            bpm_at_actual_audio_crop_start = util.get_bpm_at_time(fumen_for_bpm_at_actual_start,
                                                                  actual_snapped_audio_crop_start_time,
                                                                  chart_wide_bpm_fallback_val)

        if bpm_at_actual_audio_crop_start > 0:
            beat_duration = 60.0 / bpm_at_actual_audio_crop_start
            time_from_orig_chart_zero_to_actual_audio_start = actual_snapped_audio_crop_start_time - original_metadata_first_offset

            if beat_duration > 1e-9:
                offset_within_beat = time_from_orig_chart_zero_to_actual_audio_start % beat_duration
                if math.isclose(offset_within_beat, 0.0, abs_tol=1e-6) or \
                        math.isclose(offset_within_beat, beat_duration, abs_tol=1e-6):
                    new_metadata_first_offset = 0.0
                else:
                    new_metadata_first_offset = beat_duration - offset_within_beat
            else:
                new_metadata_first_offset = 0.0
        else:
            new_metadata_first_offset = 0.0

    if new_metadata_first_offset < 0: new_metadata_first_offset = 0.0
    temp_chart_data['metadata']['first_offset_sec'] = new_metadata_first_offset

    max_fumens_count = 0
    if original_fumens_list: max_fumens_count = len(original_fumens_list)
    if original_levels: max_fumens_count = max(max_fumens_count, len(original_levels))
    max_fumens_count = max(max_fumens_count, 7)

    new_fumens_data_slots = [None] * max_fumens_count

    if original_fumens_list:
        for fumen_idx_orig in range(len(original_fumens_list)):
            fumen_item_original = original_fumens_list[fumen_idx_orig]
            if not fumen_item_original:
                continue

            current_level_info = original_levels[fumen_idx_orig] if fumen_idx_orig < len(original_levels) else ""

            if fumen_idx_orig in indices_to_process:
                bpm_at_fumen_desired_crop_end = util.get_bpm_at_time(fumen_item_original, crop_end_sec,
                                                                     chart_wide_bpm_fallback_val)
                actual_snapped_fumen_crop_end_time = util.snap_to_grid(crop_end_sec, bpm_at_fumen_desired_crop_end)

                cropped_audio_duration_for_fumen = actual_snapped_fumen_crop_end_time - actual_snapped_audio_crop_start_time
                if cropped_audio_duration_for_fumen < 0: cropped_audio_duration_for_fumen = 0

                processed_fumen_obj = {
                    "difficulty_index": fumen_idx_orig,
                    "level_info": current_level_info,
                    "note_events": [],
                    "timing_events_at_commas": [],
                    **{k: v for k, v in fumen_item_original.items() if
                       k not in ['note_events', 'timing_events_at_commas', 'difficulty_index', 'level_info']}
                }

                if cropped_audio_duration_for_fumen > 1e-6:
                    for event_type_key in ['note_events', 'timing_events_at_commas']:
                        for event in fumen_item_original.get(event_type_key, []):
                            original_event_time = event.get('time', 0)
                            new_event_time_in_cropped_segment = original_event_time - actual_snapped_audio_crop_start_time

                            if new_event_time_in_cropped_segment >= -1e-6 and \
                                    new_event_time_in_cropped_segment < cropped_audio_duration_for_fumen - 1e-6:

                                final_event_time = max(0.0, new_event_time_in_cropped_segment)
                                new_event_copy = deepcopy(event)
                                new_event_copy['time'] = final_event_time

                                if event_type_key == 'note_events' and 'notes' in new_event_copy:
                                    for note_obj in new_event_copy['notes']:
                                        if 'hold_time' in note_obj:
                                            original_hold_end_abs = original_event_time + note_obj['hold_time']
                                            new_hold_end_rel_to_crop_start = original_hold_end_abs - actual_snapped_audio_crop_start_time
                                            note_obj['hold_time'] = max(0,
                                                                        new_hold_end_rel_to_crop_start - final_event_time)

                                        if 'slide_time' in note_obj:
                                            original_slide_start_abs = original_event_time
                                            if 'slide_start_time_offset' in note_obj:
                                                original_slide_start_abs += note_obj['slide_start_time_offset']

                                            original_slide_end_abs = original_slide_start_abs + note_obj['slide_time']

                                            new_slide_start_rel_to_crop_start = original_slide_start_abs - actual_snapped_audio_crop_start_time
                                            new_slide_end_rel_to_crop_start = original_slide_end_abs - actual_snapped_audio_crop_start_time

                                            if 'slide_start_time_offset' in note_obj:
                                                note_obj['slide_start_time_offset'] = max(0,
                                                                                          new_slide_start_rel_to_crop_start - final_event_time)

                                            current_note_new_slide_start_time = final_event_time + note_obj.get(
                                                'slide_start_time_offset', 0.0)
                                            note_obj['slide_time'] = max(0,
                                                                         new_slide_end_rel_to_crop_start - current_note_new_slide_start_time)

                                processed_fumen_obj[event_type_key].append(new_event_copy)

                new_fumens_data_slots[fumen_idx_orig] = processed_fumen_obj

    final_structured_fumens = []
    for i in range(max_fumens_count):
        level_info_for_slot = original_levels[i] if i < len(original_levels) else ""

        if i < len(new_fumens_data_slots) and new_fumens_data_slots[i] is not None:
            final_structured_fumens.append(new_fumens_data_slots[i])
        elif original_fumens_list and i < len(original_fumens_list) and original_fumens_list[i] is not None and not (
                i in indices_to_process):
            original_fumen_to_keep = deepcopy(original_fumens_list[i])
            original_fumen_to_keep.setdefault("difficulty_index", i)
            original_fumen_to_keep.setdefault("level_info", level_info_for_slot)
            original_fumen_to_keep.setdefault("note_events", [])
            original_fumen_to_keep.setdefault("timing_events_at_commas", [])
            final_structured_fumens.append(original_fumen_to_keep)
        else:
            final_structured_fumens.append({
                "difficulty_index": i, "level_info": level_info_for_slot,
                "note_events": [], "timing_events_at_commas": []
            })

    temp_chart_data['fumens_data'] = final_structured_fumens
    self.chart_data = temp_chart_data
    return self


def accelerate(self, factor):
    if not self.chart_data:
        print("错误：加速前请先加载谱面数据。")
        return self
    if math.isclose(factor, 1.0): return self
    if factor <= 0:
        print("错误：加速因子必须为正数。")
        return self

    temp_chart_data = deepcopy(self.chart_data)

    if 'first_offset_sec' in temp_chart_data['metadata']:
        temp_chart_data['metadata']['first_offset_sec'] /= factor
    if 'wholebpm' in temp_chart_data['metadata'] and isinstance(temp_chart_data['metadata']['wholebpm'], (int, float)):
        temp_chart_data['metadata']['wholebpm'] *= factor

    fumens_data = temp_chart_data.get('fumens_data')
    if fumens_data:
        for fumen in fumens_data:
            if not fumen: continue

            for event_type_key in ['note_events', 'timing_events_at_commas']:
                event_list = fumen.get(event_type_key)
                if event_list:
                    for event in event_list:
                        if 'time' in event: event['time'] /= factor
                        if 'current_bpm_at_event' in event and isinstance(event['current_bpm_at_event'], (int, float)):
                            event['current_bpm_at_event'] *= factor

                        if event_type_key == 'note_events' and 'notes' in event and isinstance(event['notes'], list):
                            for note_obj_dict in event['notes']:
                                if 'hold_time' in note_obj_dict and isinstance(note_obj_dict['hold_time'],
                                                                               (int, float)):
                                    note_obj_dict['hold_time'] /= factor
                                if 'slide_time' in note_obj_dict and isinstance(note_obj_dict['slide_time'],
                                                                                (int, float)):
                                    note_obj_dict['slide_time'] /= factor
                                if 'slide_start_time_offset' in note_obj_dict and isinstance(
                                        note_obj_dict['slide_start_time_offset'], (int, float)):
                                    note_obj_dict['slide_start_time_offset'] /= factor

    self.chart_data = temp_chart_data
    return self


def concatenate(self, other_editor, difficulty_index,
                gap_duration_fixed_sec_audio, bpm_at_end_of_chart_A):
    """
    Concatenates another SimaiEditor's chart data to this one for a specific difficulty.
    If gap_duration_fixed_sec_audio > 0, inserts a special timing event (Y){1},
    followed by a comma event, to represent the gap.
    Modifies self.chart_data.
    """
    print(f"\n[DEBUG CHART CONCAT V2] --- Starting Chart Concatenation (difficulty: {difficulty_index}) ---")
    if not self.chart_data:
        print("[DEBUG CHART CONCAT V2] Error: self.chart_data is None.")
        return self
    if not other_editor or not other_editor.chart_data:
        print("[DEBUG CHART CONCAT V2] Error: other_editor or its chart_data is None.")
        return self

    print(f"[DEBUG CHART CONCAT V2] Target difficulty_index: {difficulty_index}")
    print(f"[DEBUG CHART CONCAT V2] Fixed audio gap duration: {gap_duration_fixed_sec_audio:.3f}s")
    print(f"[DEBUG CHART CONCAT V2] BPM at end of Chart A (for context): {bpm_at_end_of_chart_A:.2f}")

    chart_A_full_data_copy = deepcopy(self.chart_data)
    chart_B_full_data_copy = deepcopy(other_editor.chart_data)

    if not isinstance(chart_A_full_data_copy.get('fumens_data'), list):
        chart_A_full_data_copy['fumens_data'] = []
    while len(chart_A_full_data_copy['fumens_data']) <= difficulty_index:
        level_info_default = ""
        current_levels_A_meta = chart_A_full_data_copy['metadata'].get('levels', [])
        if difficulty_index < len(current_levels_A_meta):
            level_info_default = current_levels_A_meta[difficulty_index] or ""

        chart_A_full_data_copy['fumens_data'].append({
            "difficulty_index": difficulty_index,
            "level_info": level_info_default,
            "note_events": [],
            "timing_events_at_commas": []
        })

    fumen_A_active = chart_A_full_data_copy['fumens_data'][difficulty_index]
    fumen_A_active.setdefault('note_events', [])
    fumen_A_active.setdefault('timing_events_at_commas', [])
    fumen_A_active.setdefault('difficulty_index', difficulty_index)
    if "level_info" not in fumen_A_active:
        level_info_A_default = ""
        current_levels_A_meta_check = chart_A_full_data_copy['metadata'].get('levels', [])
        if difficulty_index < len(current_levels_A_meta_check):
            level_info_A_default = current_levels_A_meta_check[difficulty_index] or ""
        fumen_A_active['level_info'] = level_info_A_default

    if hasattr(self, '_remove_trailing_e_from_fumen'):
        self._remove_trailing_e_from_fumen(fumen_A_active)
    else:
        print("[DEBUG CHART CONCAT V2] Warning: _remove_trailing_e_from_fumen method not found on self.")

    max_event_time_A_abs = 0.0
    all_events_A = fumen_A_active.get('note_events', []) + fumen_A_active.get('timing_events_at_commas', [])
    if all_events_A:
        for event_A in all_events_A:
            event_start_time = event_A.get('time', 0.0)
            current_event_end_time = event_start_time
            if 'notes' in event_A and isinstance(event_A['notes'], list) and event_A.get('notes_content_raw',
                                                                                         '').strip() != 'E':
                for note_detail in event_A['notes']:
                    note_specific_end_time = event_start_time
                    if 'hold_time' in note_detail and isinstance(note_detail['hold_time'], (int, float)):
                        note_specific_end_time = event_start_time + note_detail['hold_time']
                    slide_actual_start_time = event_start_time
                    if 'slide_start_time_offset' in note_detail and isinstance(note_detail['slide_start_time_offset'],
                                                                               (int, float)):
                        slide_actual_start_time += note_detail['slide_start_time_offset']
                    if 'slide_time' in note_detail and isinstance(note_detail['slide_time'], (int, float)):
                        slide_end_time = slide_actual_start_time + note_detail['slide_time']
                        note_specific_end_time = max(note_specific_end_time, slide_end_time)
                    current_event_end_time = max(current_event_end_time, note_specific_end_time)
            max_event_time_A_abs = max(max_event_time_A_abs, current_event_end_time)
    print(
        f"[DEBUG CHART CONCAT V2] Max musical event time for Chart A (difficulty {difficulty_index}): {max_event_time_A_abs:.3f}s")

    fumen_B_active = None
    source_fumens_B = chart_B_full_data_copy.get('fumens_data', [])
    if 0 <= difficulty_index < len(source_fumens_B) and source_fumens_B[difficulty_index] is not None:
        if isinstance(source_fumens_B[difficulty_index], dict):
            fumen_B_active = deepcopy(source_fumens_B[difficulty_index])
            fumen_B_active.setdefault('note_events', [])
            fumen_B_active.setdefault('timing_events_at_commas', [])

    if not fumen_B_active or (
            not fumen_B_active.get('note_events') and not fumen_B_active.get('timing_events_at_commas')):
        print(f"[DEBUG CHART CONCAT V2] Chart B (difficulty {difficulty_index}) is effectively empty.")
        if hasattr(self, '_ensure_fumen_ends_with_e') and (
                fumen_A_active['note_events'] or fumen_A_active['timing_events_at_commas']):
            self._ensure_fumen_ends_with_e(fumen_A_active)
        chart_A_full_data_copy['fumens_data'][difficulty_index] = fumen_A_active
        self.chart_data = chart_A_full_data_copy
        return self

    current_time_for_chart_B_start = max_event_time_A_abs

    if gap_duration_fixed_sec_audio > 1e-3:
        # Assuming {1} in Simai means 1 whole note (4 beats).
        # If {1} means 1 beat (quarter note), then multiplier should be 60.0 * 1.0
        Y_bpm = (60.0 * 4.0) / gap_duration_fixed_sec_audio
        Y_bpm_formatted_str = f"{Y_bpm:.5f}"  # Format to 5 decimal places

        print(f"[DEBUG CHART CONCAT V2] Gap detected. Calculated Y_bpm for (Y){{1}} marker: {Y_bpm_formatted_str}")

        last_A_event_props = {'x_pos': 0, 'y_pos': 0, 'hspeed_at_event': 1.0,
                              'current_bpm_at_event': bpm_at_end_of_chart_A}
        sorted_note_events_A = sorted(
            [e for e in fumen_A_active.get('note_events', []) if e.get('notes_content_raw', '').strip() != 'E'],
            key=lambda x: x.get('time', 0)
        )
        if sorted_note_events_A:
            last_actual_note_A = sorted_note_events_A[-1]
            last_A_event_props['x_pos'] = last_actual_note_A.get('x_pos', 0)
            last_A_event_props['y_pos'] = last_actual_note_A.get('y_pos', 0)
            last_A_event_props['hspeed_at_event'] = last_actual_note_A.get('hspeed_at_event', 1.0)
            last_A_event_props['current_bpm_at_event'] = last_actual_note_A.get('current_bpm_at_event',
                                                                                bpm_at_end_of_chart_A)

        gap_marker_event = {
            'time': max_event_time_A_abs,
            'notes_content_raw': f"({Y_bpm_formatted_str}){{1}}",  # Simai notation for BPM and duration
            'current_bpm_at_event': float(Y_bpm_formatted_str),
            'hspeed_at_event': last_A_event_props['hspeed_at_event'],
            'x_pos': last_A_event_props['x_pos'],
            'y_pos': last_A_event_props['y_pos'],
            'notes': []
        }
        fumen_A_active['note_events'].append(gap_marker_event)
        print(
            f"[DEBUG CHART CONCAT V2] Added gap marker event: {gap_marker_event['notes_content_raw']} at {gap_marker_event['time']:.3f}s")

        # Add a comma event to properly terminate the (Y){1} segment
        time_for_gap_closing_comma = max_event_time_A_abs + gap_duration_fixed_sec_audio
        gap_closing_comma_event = {
            'time': time_for_gap_closing_comma,
            'current_bpm_at_event': float(Y_bpm_formatted_str),  # This comma is part of the (Y){1} segment's timing
            'hspeed_at_event': last_A_event_props['hspeed_at_event'],
            # No 'notes_content_raw' for comma events
        }
        fumen_A_active['timing_events_at_commas'].append(gap_closing_comma_event)
        print(
            f"[DEBUG CHART CONCAT V2] Added gap closing comma at {time_for_gap_closing_comma:.3f}s with BPM {Y_bpm_formatted_str}")

        current_time_for_chart_B_start = time_for_gap_closing_comma
    else:
        print(
            "[DEBUG CHART CONCAT V2] No significant audio gap. Chart B will start effectively after Chart A's content.")
        # current_time_for_chart_B_start remains max_event_time_A_abs

    print(f"[DEBUG CHART CONCAT V2] Effective start time for Chart B content: {current_time_for_chart_B_start:.3f}s")

    first_offset_B = chart_B_full_data_copy['metadata'].get('first_offset_sec', 0.0)
    time_shift_for_B_events = current_time_for_chart_B_start - first_offset_B
    print(f"[DEBUG CHART CONCAT V2] Chart B first_offset_sec: {first_offset_B:.3f}")
    print(f"[DEBUG CHART CONCAT V2] Calculated time_shift_for_B_events: {time_shift_for_B_events:.3f}")

    for event_B_item in fumen_B_active.get('note_events', []):
        is_last_event_in_B_notes = (event_B_item == fumen_B_active['note_events'][-1]) if fumen_B_active[
            'note_events'] else False
        is_only_event_type_in_B = not fumen_B_active.get('timing_events_at_commas')

        if event_B_item.get('notes_content_raw',
                            '').strip() == 'E' and is_last_event_in_B_notes and is_only_event_type_in_B:
            print(f"[DEBUG CHART CONCAT V2] Skipping trailing 'E' from Chart B notes: {event_B_item}")
            continue

        new_event = deepcopy(event_B_item)
        new_event['time'] = new_event.get('time', 0.0) + time_shift_for_B_events
        fumen_A_active['note_events'].append(new_event)

    for event_B_item in fumen_B_active.get('timing_events_at_commas', []):
        new_event = deepcopy(event_B_item)
        new_event['time'] = new_event.get('time', 0.0) + time_shift_for_B_events
        fumen_A_active['timing_events_at_commas'].append(new_event)

    if fumen_A_active['note_events']:
        fumen_A_active['note_events'].sort(key=lambda x: x.get('time', 0.0))
    if fumen_A_active['timing_events_at_commas']:
        fumen_A_active['timing_events_at_commas'].sort(key=lambda x: x.get('time', 0.0))

    if hasattr(self, '_ensure_fumen_ends_with_e') and \
            (fumen_A_active['note_events'] or fumen_A_active['timing_events_at_commas']):
        self._ensure_fumen_ends_with_e(fumen_A_active)

    chart_A_full_data_copy['fumens_data'][difficulty_index] = fumen_A_active

    level_A_meta = ""
    current_levels_A_meta = chart_A_full_data_copy['metadata'].get('levels', [])
    if difficulty_index < len(current_levels_A_meta):
        level_A_meta = current_levels_A_meta[difficulty_index] or ""

    level_B_info_from_fumen = fumen_B_active.get("level_info", "") if fumen_B_active else ""
    level_B_info_from_meta = ""
    current_levels_B_meta = chart_B_full_data_copy['metadata'].get('levels', [])
    if difficulty_index < len(current_levels_B_meta):
        level_B_info_from_meta = current_levels_B_meta[difficulty_index] or ""

    final_level_B_info = level_B_info_from_fumen or level_B_info_from_meta

    if final_level_B_info and (not level_A_meta or level_A_meta != final_level_B_info):
        while len(chart_A_full_data_copy['metadata'].get('levels', [])) <= difficulty_index:
            chart_A_full_data_copy['metadata'].setdefault('levels', []).append("")
        chart_A_full_data_copy['metadata']['levels'][difficulty_index] = final_level_B_info
        if chart_A_full_data_copy['fumens_data'][difficulty_index]:
            chart_A_full_data_copy['fumens_data'][difficulty_index]["level_info"] = final_level_B_info

    self.chart_data = chart_A_full_data_copy
    print("[DEBUG CHART CONCAT V2] --- Ending Chart Concatenation ---")
    return self