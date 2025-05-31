# editor.py
import json
import os
import sys
from copy import deepcopy
from . import chart  # Assuming chart.py contains the methods assigned below

# SimaiParser import block
try:
    from SimaiParser.core import SimaiChart
    from SimaiParser.rebuild import JsonSimaiConverter
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if os.path.isdir(os.path.join(current_dir, "SimaiParser")):
        sys.path.insert(0, current_dir)
    elif os.path.isdir(os.path.join(parent_dir, "SimaiParser")):
        sys.path.insert(0, parent_dir)
    else:
        print("Warning: Could not automatically find SimaiParser module. "
              "Ensure SimaiParser is in your PYTHONPATH or in the correct relative path.")
    try:
        from SimaiParser.core import SimaiChart
        from SimaiParser.rebuild import JsonSimaiConverter
    except ImportError as e:
        print(f"Fatal Error: Failed to import SimaiParser modules: {e}")


        # Dummy classes for basic operation if SimaiParser is missing
        class SimaiChart:
            def __init__(self): self.metadata = {}; self.fumens_raw = []; self.processed_fumens_data = []

            def load_from_text(self, text): print("Error: SimaiChart (dummy) not loaded."); self.chart_data = {
                "metadata": {}, "fumens_data": []}; return

            def to_json(self): print("Error: SimaiChart (dummy) not loaded."); return json.dumps(
                {"metadata": {}, "fumens_data": []})


        class JsonSimaiConverter:
            def __init__(self, data): print("Error: JsonSimaiConverter (dummy) not loaded.")

            def to_simai_text(self): print("Error: JsonSimaiConverter (dummy) not loaded."); return ""

            @classmethod
            def from_json_text(cls, json_text): print("Error: JsonSimaiConverter (dummy) not loaded."); return cls({})


class SimaiEditor:
    def __init__(self, simai_content=None, filepath=None):
        self.chart_data = None
        # Initialize _simai_parser here, even if it's a dummy, to avoid AttributeError
        try:
            self._simai_parser = SimaiChart()
        except NameError:  # SimaiChart might not be defined if import failed badly
            self._simai_parser = None  # Or a more robust dummy
            print("Critical Error: SimaiChart class not available for _simai_parser.")

        if filepath:
            self.load_from_file(filepath)
        elif simai_content:
            self.load_from_text(simai_content)

        if self.chart_data is None:  # Ensure chart_data is initialized if loading failed or no input
            self.chart_data = {"metadata": {}, "fumens_data": [None] * 7}

    def _create_synthetic_e_event(self, reference_event_props):
        """
        Creates a synthetic 'E' note event.
        """
        return {
            "time": reference_event_props.get('time', 0.0),
            "x_pos": reference_event_props.get('x_pos', 0),
            "y_pos": reference_event_props.get('y_pos', 0),
            "notes_content_raw": "E",
            "current_bpm_at_event": reference_event_props.get('current_bpm_at_event', 120.0),
            "hspeed_at_event": reference_event_props.get('hspeed_at_event', 1.0),
            "notes": []
        }

    def _ensure_fumen_ends_with_e(self, fumen_data):
        """
        Ensures a fumen_data dictionary has an 'E' marker as its chronologically last note_event.
        Modifies fumen_data in place.
        """
        if not fumen_data:
            return

        note_events = fumen_data.get('note_events', [])
        if not isinstance(note_events, list):
            note_events = []
            fumen_data['note_events'] = note_events

        timing_events = fumen_data.get('timing_events_at_commas', [])
        if not isinstance(timing_events, list): timing_events = []

        # Determine the latest time of any content (note or timing)
        latest_content_time = -1.0
        reference_event_for_e_props = None

        # Check non-'E' notes first
        non_e_note_events = [n for n in note_events if n.get('notes_content_raw', '').strip() != 'E']
        if non_e_note_events:
            # Consider actual end time of notes (including holds/slides) for reference props
            for note_event in sorted(non_e_note_events, key=lambda x: x.get('time', 0)):  # Iterate sorted
                event_start_time = note_event.get('time', 0.0)
                current_note_actual_end_time = event_start_time
                if 'notes' in note_event and isinstance(note_event['notes'], list):
                    for note_detail in note_event['notes']:
                        nd_end_time = event_start_time
                        if 'hold_time' in note_detail and isinstance(note_detail['hold_time'], (int, float)):
                            nd_end_time = event_start_time + note_detail['hold_time']

                        slide_actual_start = event_start_time
                        if 'slide_start_time_offset' in note_detail and isinstance(
                                note_detail['slide_start_time_offset'], (int, float)):
                            slide_actual_start += note_detail['slide_start_time_offset']
                        if 'slide_time' in note_detail and isinstance(note_detail['slide_time'], (int, float)):
                            nd_end_time = max(nd_end_time, slide_actual_start + note_detail['slide_time'])
                        current_note_actual_end_time = max(current_note_actual_end_time, nd_end_time)

                if current_note_actual_end_time >= latest_content_time:  # Use >= to prefer later notes
                    latest_content_time = current_note_actual_end_time
                    reference_event_for_e_props = note_event  # Base props on this note

        # Check timing events
        if timing_events:
            for timing_event in sorted(timing_events, key=lambda x: x.get('time', 0)):  # Iterate sorted
                timing_event_time = timing_event.get('time', 0.0)
                if timing_event_time >= latest_content_time:  # Use >= to prefer later timing events
                    latest_content_time = timing_event_time
                    # If this timing event is later, it becomes the reference
                    chart_meta_fallback = self.chart_data.get('metadata', {}) if self.chart_data else {}
                    default_bpm = chart_meta_fallback.get('wholebpm', 120.0)
                    reference_event_for_e_props = {
                        "time": timing_event_time,  # This time will be the base for 'E'
                        "current_bpm_at_event": timing_event.get('current_bpm_at_event', default_bpm),
                        "x_pos": 0, "y_pos": 0,
                        "hspeed_at_event": timing_event.get('hspeed_at_event', 1.0)
                    }

        # If no content at all, or only 'E's were present (which are now removed)
        if reference_event_for_e_props is None:
            # This implies the fumen should be empty or was just 'E'.
            # get_simai_text() checks 'has_content'. If it was true (e.g. original was "E"), we add one.
            # If truly empty, 'has_content' would be false, and this isn't called.
            chart_meta = self.chart_data.get('metadata', {}) if self.chart_data else {}
            reference_event_for_e_props = {
                "time": chart_meta.get('first_offset_sec', 0.0),
                "current_bpm_at_event": chart_meta.get('wholebpm', 120.0),
                "x_pos": 0, "y_pos": 0, "hspeed_at_event": 1.0
            }
            latest_content_time = reference_event_for_e_props['time']

        # The 'E' event should be chronologically last.
        # Its time is based on latest_content_time, plus a tiny epsilon if needed.
        e_event_time = latest_content_time + 1e-9  # Ensure it's strictly after all other content

        final_e_props = deepcopy(reference_event_for_e_props)  # Make a mutable copy
        final_e_props['time'] = e_event_time  # Set the slightly later time

        # Rebuild note_events: original non-E notes, plus one 'E' at the very end.
        fumen_data['note_events'] = non_e_note_events

        e_event = self._create_synthetic_e_event(final_e_props)
        fumen_data['note_events'].append(e_event)

        # Sort note_events one last time to ensure 'E' is correctly placed by time.
        fumen_data['note_events'].sort(key=lambda x: x.get('time', 0.0))

    def _remove_trailing_e_from_fumen(self, fumen_data):
        if not fumen_data or not isinstance(fumen_data.get('note_events'), list):
            return
        note_events = fumen_data['note_events']
        # Remove all 'E' events that are effectively at the end.
        # This is to clean up before adding a single, correctly timed 'E'.
        fumen_data['note_events'] = [n for n in note_events if n.get('notes_content_raw', '').strip() != 'E']

    def load_from_text(self, simai_content):
        if not simai_content:
            # Initialize to a default empty structure if content is empty
            self.chart_data = {"metadata": {}, "fumens_data": [None] * 7}  # Ensure 7 slots for difficulties
            print("警告：输入的Simai内容为空，编辑器已初始化为空谱面。")
            return self  # Return self for chaining

        if self._simai_parser is None:  # Guard against missing SimaiParser
            print("错误: SimaiParser 未初始化，无法加载文本。")
            self.chart_data = {"metadata": {}, "fumens_data": [None] * 7}
            return self

        try:
            self._simai_parser.load_from_text(simai_content)
            self.chart_data = json.loads(self._simai_parser.to_json())
        except Exception as e:
            self.chart_data = {"metadata": {}, "fumens_data": [None] * 7}  # Reset on error
            raise ValueError(f"解析Simai内容失败：{e}")
        return self

    def load_from_file(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.load_from_text(content)
        except FileNotFoundError:
            self.chart_data = {"metadata": {}, "fumens_data": [None] * 7}
            raise FileNotFoundError(f"文件未找到：{filepath}")
        except Exception as e:  # Catch other exceptions like ValueError from load_from_text
            self.chart_data = {"metadata": {}, "fumens_data": [None] * 7}
            raise e  # Re-raise the caught exception
        return self

    def get_simai_text(self):
        if not self.chart_data:
            print("错误：没有加载谱面数据。")
            return None

        temp_data_for_rebuild = deepcopy(self.chart_data)
        if temp_data_for_rebuild.get('fumens_data'):
            for fumen_d_idx, fumen_d in enumerate(temp_data_for_rebuild['fumens_data']):
                if not fumen_d:  # If a fumen slot is None, ensure it's an empty dict for processing
                    level_info = ""
                    if 'levels' in temp_data_for_rebuild['metadata'] and fumen_d_idx < len(
                            temp_data_for_rebuild['metadata']['levels']):
                        level_info = temp_data_for_rebuild['metadata']['levels'][fumen_d_idx]
                    fumen_d = {"difficulty_index": fumen_d_idx, "level_info": level_info, "note_events": [],
                               "timing_events_at_commas": []}
                    temp_data_for_rebuild['fumens_data'][fumen_d_idx] = fumen_d

                self._remove_trailing_e_from_fumen(fumen_d)  # Clean before checking content

                has_notes = bool(fumen_d.get('note_events'))  # After removing Es, check if any true notes remain
                has_timing = bool(fumen_d.get('timing_events_at_commas'))

                # Original level string can imply content even if events are empty
                # For example, a chart might be just "&lv_0=1 E" which SimaiParser might treat as having content.
                # We rely on the fact that if SimaiParser parsed it and produced fumens_data,
                # then even an empty note_events/timing_events list for a defined level implies it should end with E.
                # The crucial part is if the original input for this fumen slot was non-empty or if it has a level.

                # A fumen is considered to have content if it has notes, timing events,
                # OR if it has level information defined in the metadata,
                # as this implies the fumen slot is meant to be active.
                has_level_info = False
                if 'levels' in temp_data_for_rebuild['metadata'] and \
                        fumen_d_idx < len(temp_data_for_rebuild['metadata']['levels']) and \
                        temp_data_for_rebuild['metadata']['levels'][fumen_d_idx]:
                    has_level_info = True

                has_content = has_notes or has_timing or has_level_info

                if has_content:
                    self._ensure_fumen_ends_with_e(fumen_d)
                # If no notes, no timing, and no level info, it's truly an inactive/empty fumen.
        try:
            converter = JsonSimaiConverter(temp_data_for_rebuild)
            return converter.to_simai_text()
        except Exception as e:
            print(f"错误：重建Simai文本失败：{e}")
            return None

    def save_to_file(self, filepath):
        simai_text = self.get_simai_text()
        if simai_text is None:
            print(f"未能生成Simai文本，无法保存到 {filepath}")
            return False
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(simai_text)
            print(f"谱面已成功保存到: {filepath}")
            return True
        except Exception as e:
            print(f"错误：保存文件失败 '{filepath}': {e}")
            return False


# Assign methods from chart.py to SimaiEditor class
# These methods operate on self.chart_data
SimaiEditor.accelerate = chart.accelerate
SimaiEditor.crop = chart.crop
SimaiEditor.concatenate = chart.concatenate
