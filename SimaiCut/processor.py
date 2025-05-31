import os
import shutil
import tempfile
from pathlib import Path
from copy import deepcopy

from .audio import AudioProcessor
from .editor import SimaiEditor
from . import util


class SongProcessor:
    def __init__(self, audio_path, chart_path, temp_dir_prefix="song_proc_"):
        self.original_audio_path = Path(audio_path).resolve()
        self.original_chart_path = Path(chart_path).resolve()

        if not self.original_audio_path.exists():
            raise FileNotFoundError(f"音频文件未找到: {self.original_audio_path}")
        if not self.original_chart_path.exists():
            raise FileNotFoundError(f"谱面文件未找到: {self.original_chart_path}")

        self.current_audio_path = self.original_audio_path
        self.current_chart_path = self.original_chart_path

        self.simai_editor = SimaiEditor(filepath=str(self.current_chart_path))
        self.audio_processor = AudioProcessor()

        self._temp_dir_obj = tempfile.TemporaryDirectory(prefix=temp_dir_prefix)
        self.temp_dir = Path(self._temp_dir_obj.name)
        print(f"SongProcessor initialized. Audio: {self.current_audio_path}, Chart: {self.current_chart_path}")
        print(f"Temporary directory: {self.temp_dir}")

    def _get_fumen_musical_end_time(self, fumen_data):
        """
        Calculates the effective musical end time of a fumen based on its events.
        Considers note start times, hold times, and slide times.
        Excludes 'E' events from determining the end of active musical content for this purpose.
        """
        if not fumen_data: return 0.0
        max_fumen_time = 0.0
        if fumen_data.get('note_events'):
            for event in fumen_data['note_events']:
                event_start_time = event.get('time', 0.0)
                # Skip 'E' events when determining the end of active musical notes
                if event.get('notes_content_raw', '').strip() == 'E':
                    # We might still consider its time if it's later than any musical note,
                    # but it doesn't define a musical duration itself.
                    # For now, let's focus on notes that have musical content.
                    # max_fumen_time = max(max_fumen_time, event_start_time) # Option: include E time
                    continue

                current_event_end_time = event_start_time
                if 'notes' in event and isinstance(event['notes'], list):
                    for note_detail in event['notes']:
                        note_specific_end_time = event_start_time
                        if 'hold_time' in note_detail and isinstance(note_detail['hold_time'], (int, float)):
                            note_specific_end_time = event_start_time + note_detail['hold_time']

                        slide_actual_start_time = event_start_time
                        if 'slide_start_time_offset' in note_detail and isinstance(
                                note_detail['slide_start_time_offset'], (int, float)):
                            slide_actual_start_time += note_detail['slide_start_time_offset']
                        if 'slide_time' in note_detail and isinstance(note_detail['slide_time'], (int, float)):
                            slide_end_time = slide_actual_start_time + note_detail['slide_time']
                            note_specific_end_time = max(note_specific_end_time, slide_end_time)
                        current_event_end_time = max(current_event_end_time, note_specific_end_time)
                max_fumen_time = max(max_fumen_time, current_event_end_time)

        # Consider timing events (commas) as they can also define the end of a chart segment
        if fumen_data.get('timing_events_at_commas'):
            for event_timing in fumen_data['timing_events_at_commas']:
                max_fumen_time = max(max_fumen_time, event_timing.get('time', 0.0))

        return max_fumen_time

    def _get_bpm_for_audio_op(self, time_sec=0, default_bpm=120, chart_editor_instance=None):
        """
        Gets the BPM at a specific time, primarily for audio operations like snapping.
        Uses the provided chart_editor_instance or self.simai_editor.
        """
        editor_to_use = chart_editor_instance if chart_editor_instance else self.simai_editor
        if editor_to_use and editor_to_use.chart_data:
            metadata = editor_to_use.chart_data.get('metadata', {})
            # Use 'wholebpm' from metadata as a primary fallback if available and valid
            chart_wide_bpm_from_meta = metadata.get('wholebpm')
            if isinstance(chart_wide_bpm_from_meta, (int, float)) and chart_wide_bpm_from_meta > 0:
                default_bpm_to_pass_util = chart_wide_bpm_from_meta
            else:
                default_bpm_to_pass_util = default_bpm

            fumens = editor_to_use.chart_data.get('fumens_data', [])
            if fumens:
                # Try to get BPM from any fumen that has events
                for fumen_data in fumens:
                    if fumen_data and (fumen_data.get('note_events') or fumen_data.get('timing_events_at_commas')):
                        # util.get_bpm_at_time should handle finding the relevant BPM
                        bpm_from_fumen = util.get_bpm_at_time(fumen_data, time_sec,
                                                              None)  # Pass None to see if fumen has it
                        if bpm_from_fumen is not None and bpm_from_fumen > 0:
                            return bpm_from_fumen
            # If no fumen provided a specific BPM at time_sec, return the chart-wide (or overall default)
            return default_bpm_to_pass_util
        return default_bpm  # Absolute fallback

    def crop(self, output_audio_path, output_chart_path, start_sec, end_sec, difficulty_indices=None):
        print(f"开始裁剪: 音频从 {self.current_audio_path}, 谱面从 {self.current_chart_path}")
        print(f"裁剪范围: {start_sec}s - {end_sec}s")

        bpm_for_snap = self._get_bpm_for_audio_op(start_sec)  # Get BPM at the start for snapping

        temp_cropped_audio_name = f"cropped_{Path(self.current_audio_path).name}"
        internal_temp_cropped_audio = self.temp_dir / temp_cropped_audio_name

        AudioProcessor.crop(str(self.current_audio_path), str(internal_temp_cropped_audio), start_sec, end_sec,
                            snap_bpm=bpm_for_snap)
        shutil.copy(str(internal_temp_cropped_audio), output_audio_path)
        print(f"音频裁剪完成并保存到: {output_audio_path}")

        # Create a new editor instance for the current chart path to ensure fresh data for cropping
        temp_editor_for_crop = SimaiEditor(filepath=str(self.current_chart_path))
        temp_editor_for_crop.crop(start_sec, end_sec, difficulty_indices=difficulty_indices)
        temp_editor_for_crop.save_to_file(output_chart_path)
        print(f"谱面裁剪完成并保存到: {output_chart_path}")

        self.current_audio_path = Path(output_audio_path).resolve()
        self.current_chart_path = Path(output_chart_path).resolve()
        # Update the main simai_editor's chart_data with the cropped data
        self.simai_editor.chart_data = deepcopy(temp_editor_for_crop.chart_data)
        print("SongProcessor 状态已更新为裁剪后的文件 (使用内存中的谱面数据)。")
        return self

    def accelerate(self, output_audio_path, output_chart_path, factor):
        print(f"开始加速: 音频从 {self.current_audio_path}, 谱面从 {self.current_chart_path}")
        print(f"加速因子: {factor}")
        if factor <= 0: raise ValueError("加速因子必须大于0。")

        temp_accel_audio_name = f"accel_{Path(self.current_audio_path).name}"
        internal_temp_accel_audio = self.temp_dir / temp_accel_audio_name
        AudioProcessor.accelerate(str(self.current_audio_path), str(internal_temp_accel_audio), factor)
        shutil.copy(str(internal_temp_accel_audio), output_audio_path)
        print(f"音频加速完成并保存到: {output_audio_path}")

        temp_editor_for_accel = SimaiEditor(filepath=str(self.current_chart_path))
        temp_editor_for_accel.accelerate(factor)
        temp_editor_for_accel.save_to_file(output_chart_path)
        print(f"谱面加速完成并保存到: {output_chart_path}")

        self.current_audio_path = Path(output_audio_path).resolve()
        self.current_chart_path = Path(output_chart_path).resolve()
        self.simai_editor.chart_data = deepcopy(temp_editor_for_accel.chart_data)
        print("SongProcessor 状态已更新为加速后的文件 (使用内存中的谱面数据)。")
        return self

    def concatenate_with_other(self, other_song_processor,
                               output_audio_path, output_chart_path,
                               difficulty_index_for_chart_concat,
                               gap_duration_fixed_sec=0.0,  # Changed from gap_measures
                               fade_out_self_sec=0,
                               fade_in_other_sec=0):
        print(
            f"开始拼接: 当前乐曲 ({self.current_audio_path.name}) 与另一个乐曲 ({other_song_processor.current_audio_path.name})")
        print(f"固定音频间隔时长: {gap_duration_fixed_sec:.3f}s")

        # Determine BPM at the end of the current song (self) for chart concatenation context
        bpm_at_end_of_self = 120.0  # Default
        last_event_time_self = 0.0
        if self.simai_editor.chart_data:
            current_chart_fumens = self.simai_editor.chart_data.get('fumens_data', [])
            if current_chart_fumens and 0 <= difficulty_index_for_chart_concat < len(current_chart_fumens):
                fumen_data_self = current_chart_fumens[difficulty_index_for_chart_concat]
                if fumen_data_self:
                    last_event_time_self = self._get_fumen_musical_end_time(fumen_data_self)
                    # Get BPM at this musical end time
                    bpm_from_fumen_end = util.get_bpm_at_time(fumen_data_self, last_event_time_self, None)
                    if bpm_from_fumen_end is not None and bpm_from_fumen_end > 0:
                        bpm_at_end_of_self = bpm_from_fumen_end
                    else:  # Fallback to metadata or overall default if not found at exact time
                        bpm_at_end_of_self = self._get_bpm_for_audio_op(last_event_time_self,
                                                                        chart_editor_instance=self.simai_editor)
            else:  # If specific fumen is empty, use chart-wide BPM for self
                bpm_at_end_of_self = self._get_bpm_for_audio_op(0, chart_editor_instance=self.simai_editor)

        if not isinstance(bpm_at_end_of_self, (int, float)) or bpm_at_end_of_self <= 0:
            print(f"警告: 为 'self' 谱面末尾确定的BPM无效 ({bpm_at_end_of_self})，将使用默认值 120 BPM。")
            bpm_at_end_of_self = 120.0

        print(f"  谱面A (self) 末端参考BPM: {bpm_at_end_of_self:.2f} (在约 {last_event_time_self:.3f}s)")

        # --- Audio Processing ---
        audio_segments_to_concat_paths = []
        processed_self_audio = self.current_audio_path
        if fade_out_self_sec > 0:
            faded_out_self_name = f"faded_out_{self.current_audio_path.name}"
            faded_out_self_path = self.temp_dir / faded_out_self_name
            AudioProcessor.apply_fade(str(processed_self_audio), str(faded_out_self_path), 'out', fade_out_self_sec)
            processed_self_audio = faded_out_self_path
        audio_segments_to_concat_paths.append(str(processed_self_audio.resolve()))

        # Use the fixed duration for silence
        actual_audio_gap_duration_sec = gap_duration_fixed_sec
        if actual_audio_gap_duration_sec > 0.001:  # Threshold for creating silence
            silence_file_name = "gap_silence.wav"  # Using .wav for broad compatibility
            silence_path = self.temp_dir / silence_file_name
            try:
                AudioProcessor.create_silence(str(silence_path), actual_audio_gap_duration_sec)
                if silence_path.exists() and silence_path.stat().st_size > 0:
                    audio_segments_to_concat_paths.append(str(silence_path.resolve()))
                    print(f"  已添加静音片段: {actual_audio_gap_duration_sec:.3f}s")
                else:
                    print(f"警告: 静音文件 {silence_path} 未创建或为空。音频间隔可能不准确。")
            except Exception as e_create_silence:
                print(f"警告: 创建静音文件失败: {e_create_silence}。音频间隔可能不准确。")
        else:
            print("  音频间隔时长过短，跳过创建静音片段。")

        processed_other_audio = other_song_processor.current_audio_path
        if fade_in_other_sec > 0:
            faded_in_other_name = f"faded_in_{other_song_processor.current_audio_path.name}"
            faded_in_other_path = self.temp_dir / faded_in_other_name
            AudioProcessor.apply_fade(str(processed_other_audio), str(faded_in_other_path), 'in', fade_in_other_sec)
            processed_other_audio = faded_in_other_path
        audio_segments_to_concat_paths.append(str(processed_other_audio.resolve()))

        AudioProcessor.concatenate_list(audio_segments_to_concat_paths, str(output_audio_path))
        print(f"音频拼接完成并保存到: {output_audio_path}")

        # --- Chart Processing ---
        # The simai_editor of 'self' will be modified
        self.simai_editor.concatenate(
            other_editor=other_song_processor.simai_editor,
            difficulty_index=difficulty_index_for_chart_concat,
            gap_duration_fixed_sec_audio=actual_audio_gap_duration_sec,  # Pass the fixed audio gap duration
            bpm_at_end_of_chart_A=bpm_at_end_of_self  # Pass BPM at end of self for context
        )
        self.simai_editor.save_to_file(output_chart_path)
        print(f"谱面拼接完成并保存到: {output_chart_path}")

        self.current_audio_path = Path(output_audio_path).resolve()
        self.current_chart_path = Path(output_chart_path).resolve()
        # The self.simai_editor instance already holds the concatenated chart data in memory.
        print("SongProcessor 状态已更新为拼接后的文件。")
        return self

    def cleanup_temp_dir(self):
        if hasattr(self, '_temp_dir_obj') and isinstance(self._temp_dir_obj, tempfile.TemporaryDirectory):
            print(f"正在清理临时目录: {self.temp_dir}")
            self._temp_dir_obj.cleanup()
        elif self.temp_dir.exists():  # Fallback if _temp_dir_obj is already gone or was not set
            print(f"正在清理临时目录 (fallback): {self.temp_dir}")
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_temp_dir()
