import os
import shutil
import tempfile
from pathlib import Path
from copy import deepcopy

from .audio import AudioProcessor  # Assuming AudioProcessor is in audio.py
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
        self.audio_processor = AudioProcessor()  # Instance for calling static methods if needed, or if it becomes non-static

        self._temp_dir_obj = tempfile.TemporaryDirectory(prefix=temp_dir_prefix)
        self.temp_dir = Path(self._temp_dir_obj.name)
        print(f"SongProcessor initialized. Audio: {self.current_audio_path}, Chart: {self.current_chart_path}")
        print(f"Temporary directory: {self.temp_dir}")

    def _get_fumen_musical_end_time(self, fumen_data):
        if not fumen_data: return 0.0
        max_fumen_time = 0.0
        if fumen_data.get('note_events'):
            for event in fumen_data['note_events']:
                event_start_time = event.get('time', 0.0)
                current_event_end_time = event_start_time
                if event.get('notes_content_raw', '').strip() == 'E':
                    max_fumen_time = max(max_fumen_time, event_start_time)
                    continue
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
        if fumen_data.get('timing_events_at_commas'):
            for event_timing in fumen_data['timing_events_at_commas']:
                max_fumen_time = max(max_fumen_time, event_timing.get('time', 0.0))
        return max_fumen_time

    def _get_bpm_for_audio_op(self, time_sec=0, default_bpm=120, chart_editor_instance=None):
        editor_to_use = chart_editor_instance if chart_editor_instance else self.simai_editor
        if editor_to_use and editor_to_use.chart_data:
            metadata = editor_to_use.chart_data.get('metadata', {})
            chart_wide_bpm = metadata.get('wholebpm', default_bpm)
            if not isinstance(chart_wide_bpm, (int, float)) or chart_wide_bpm <= 0: chart_wide_bpm = default_bpm
            fumens = editor_to_use.chart_data.get('fumens_data', [])
            if fumens:
                for fumen_data in fumens:
                    if fumen_data and (fumen_data.get('note_events') or fumen_data.get('timing_events_at_commas')):
                        bpm_from_fumen = util.get_bpm_at_time(fumen_data, time_sec, None)
                        if bpm_from_fumen is not None: return bpm_from_fumen
            return chart_wide_bpm
        return default_bpm

    def crop(self, output_audio_path, output_chart_path, start_sec, end_sec, difficulty_indices=None):
        print(f"开始裁剪: 音频从 {self.current_audio_path}, 谱面从 {self.current_chart_path}")
        print(f"裁剪范围: {start_sec}s - {end_sec}s")
        bpm_for_snap = self._get_bpm_for_audio_op(start_sec)
        temp_cropped_audio_name = f"cropped_{Path(self.current_audio_path).name}"
        internal_temp_cropped_audio = self.temp_dir / temp_cropped_audio_name
        AudioProcessor.crop(str(self.current_audio_path), str(internal_temp_cropped_audio), start_sec, end_sec,
                            snap_bpm=bpm_for_snap)
        shutil.copy(str(internal_temp_cropped_audio), output_audio_path)
        print(f"音频裁剪完成并保存到: {output_audio_path}")
        temp_editor_for_crop = SimaiEditor(filepath=str(self.current_chart_path))
        temp_editor_for_crop.crop(start_sec, end_sec, difficulty_indices=difficulty_indices)
        temp_editor_for_crop.save_to_file(output_chart_path)
        print(f"谱面裁剪完成并保存到: {output_chart_path}")
        self.current_audio_path = Path(output_audio_path).resolve()
        self.current_chart_path = Path(output_chart_path).resolve()
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
                               gap_measures=1.0,
                               fade_out_self_sec=0,
                               fade_in_other_sec=0):
        print(
            f"开始拼接: 当前乐曲 ({self.current_audio_path.name}) 与另一个乐曲 ({other_song_processor.current_audio_path.name})")
        bpm_at_end_of_self = 120.0
        last_event_time_self = 0.0
        current_chart_fumens = self.simai_editor.chart_data.get('fumens_data', [])
        if current_chart_fumens and 0 <= difficulty_index_for_chart_concat < len(current_chart_fumens):
            fumen_data_self = current_chart_fumens[difficulty_index_for_chart_concat]
            if fumen_data_self:
                last_event_time_self = self._get_fumen_musical_end_time(fumen_data_self)
                bpm_from_fumen_end = util.get_bpm_at_time(fumen_data_self, last_event_time_self, None)
                if bpm_from_fumen_end is not None:
                    bpm_at_end_of_self = bpm_from_fumen_end
                else:
                    bpm_at_end_of_self = self._get_bpm_for_audio_op(last_event_time_self,
                                                                    chart_editor_instance=self.simai_editor)
            else:
                bpm_at_end_of_self = self._get_bpm_for_audio_op(0, chart_editor_instance=self.simai_editor)
        else:
            bpm_at_end_of_self = self._get_bpm_for_audio_op(0, chart_editor_instance=self.simai_editor)

        if not isinstance(bpm_at_end_of_self, (int, float)) or bpm_at_end_of_self <= 0:
            print(f"警告: 无效的BPM ({bpm_at_end_of_self}) 用于计算间隔，将使用默认值 120 BPM。")
            bpm_at_end_of_self = 120.0

        actual_gap_duration_sec = 0.0
        if gap_measures > 0:
            actual_gap_duration_sec = gap_measures * (60.0 / bpm_at_end_of_self) * 4.0

        print(f"\n[DEBUG SP AUDIO] Target gap_measures: {gap_measures}")
        print(f"[DEBUG SP AUDIO] BPM for gap calculation: {bpm_at_end_of_self:.2f}")
        print(f"[DEBUG SP AUDIO] Calculated actual_gap_duration_sec: {actual_gap_duration_sec:.3f}s")
        print(
            f"计算得到音频/谱面间隔时长: {actual_gap_duration_sec:.3f}s (基于 {gap_measures} 小节 @ {bpm_at_end_of_self:.2f} BPM, 参考时间点: {last_event_time_self:.3f}s)")

        audio_segments_to_concat_paths = []
        processed_self_audio = self.current_audio_path
        if fade_out_self_sec > 0:
            faded_out_self_name = f"faded_out_{self.current_audio_path.name}"
            faded_out_self_path = self.temp_dir / faded_out_self_name
            AudioProcessor.apply_fade(str(processed_self_audio), str(faded_out_self_path), 'out', fade_out_self_sec)
            processed_self_audio = faded_out_self_path
        audio_segments_to_concat_paths.append(str(processed_self_audio.resolve()))
        print(f"[DEBUG SP AUDIO] Added segment 1 (self): {str(processed_self_audio.resolve())}")

        if actual_gap_duration_sec > 0.01:  # Threshold for creating silence
            silence_file_name = "gap_silence.wav"
            silence_path = self.temp_dir / silence_file_name
            print(
                f"[DEBUG SP AUDIO] Attempting to create silence: path={silence_path}, duration={actual_gap_duration_sec:.3f}s")
            try:
                AudioProcessor.create_silence(str(silence_path), actual_gap_duration_sec)
                if silence_path.exists() and silence_path.stat().st_size > 0:  # Check if file exists and is not empty
                    # Verify duration of created silence file
                    try:
                        silence_actual_dur = AudioProcessor.get_duration(str(silence_path))
                        print(
                            f"[DEBUG SP AUDIO] Silence file created: {silence_path}, Reported Duration: {silence_actual_dur:.3f}s, Size: {silence_path.stat().st_size} bytes")
                        if silence_actual_dur > 0.001:  # Use a small threshold for valid duration
                            audio_segments_to_concat_paths.append(str(silence_path.resolve()))
                            print(f"[DEBUG SP AUDIO] Added segment 2 (silence): {str(silence_path.resolve())}")
                        else:
                            print(
                                f"[DEBUG SP AUDIO] ERROR: Silence file created but duration ({silence_actual_dur:.3f}s) is too short. Not adding.")
                    except Exception as e_dur:
                        print(
                            f"[DEBUG SP AUDIO] ERROR: Could not get duration of created silence file {silence_path}: {e_dur}. Not adding.")
                else:
                    print(f"[DEBUG SP AUDIO] ERROR: Silence file {silence_path} was NOT created or is empty.")
            except Exception as e_create:
                print(f"[DEBUG SP AUDIO] ERROR: Failed to create silence file {silence_path}: {e_create}")
        else:
            print(f"[DEBUG SP AUDIO] Gap duration {actual_gap_duration_sec:.3f}s <= 0.01. Skipping silence creation.")

        processed_other_audio = other_song_processor.current_audio_path
        if fade_in_other_sec > 0:
            faded_in_other_name = f"faded_in_{other_song_processor.current_audio_path.name}"
            faded_in_other_path = self.temp_dir / faded_in_other_name
            AudioProcessor.apply_fade(str(processed_other_audio), str(faded_in_other_path), 'in', fade_in_other_sec)
            processed_other_audio = faded_in_other_path
        audio_segments_to_concat_paths.append(str(processed_other_audio.resolve()))
        print(f"[DEBUG SP AUDIO] Added segment 3 (other): {str(processed_other_audio.resolve())}")

        print(f"[DEBUG SP AUDIO] Final list of audio segments for concatenation: {audio_segments_to_concat_paths}")
        AudioProcessor.concatenate_list(audio_segments_to_concat_paths,
                                        str(output_audio_path))  # Ensure output_path is string
        print(f"音频拼接完成并保存到: {output_audio_path}")

        self.simai_editor.concatenate(other_editor=other_song_processor.simai_editor,
                                      difficulty_index=difficulty_index_for_chart_concat,
                                      gap_actual_duration_sec=actual_gap_duration_sec,
                                      bpm_to_use_for_gap_notes=bpm_at_end_of_self)
        self.simai_editor.save_to_file(output_chart_path)
        print(f"谱面拼接完成并保存到: {output_chart_path}")
        self.current_audio_path = Path(output_audio_path).resolve()
        self.current_chart_path = Path(output_chart_path).resolve()
        print("SongProcessor 状态已更新为拼接后的文件 (内存中的谱面数据已拼接)。")
        return self

    def cleanup_temp_dir(self):
        if hasattr(self, '_temp_dir_obj') and isinstance(self._temp_dir_obj, tempfile.TemporaryDirectory):
            print(f"正在清理临时目录: {self.temp_dir}")
            self._temp_dir_obj.cleanup()
        elif self.temp_dir.exists():
            print(f"正在清理临时目录 (fallback): {self.temp_dir}")
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_temp_dir()