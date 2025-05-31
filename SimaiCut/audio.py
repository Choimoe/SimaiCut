# audio.py
import subprocess
import os
import math
from tempfile import NamedTemporaryFile
import shutil
from pathlib import Path  # 确保导入 Path

from . import util


class AudioProcessor:
    @staticmethod
    def get_duration(input_path):
        input_path_str = str(input_path)  # 确保是字符串
        if not os.path.exists(input_path_str):
            raise FileNotFoundError(f"输入文件不存在: {input_path_str}")

        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'default=noprint_wrappers=1:nokey=1', input_path_str]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True,
                                    encoding='utf-8')
            duration = float(result.stdout.strip())
            return duration
        except subprocess.CalledProcessError as e:
            print(f"[DEBUG AUDIO GET_DURATION] Error getting duration for {input_path_str}: {e.stderr}")
            raise RuntimeError(f"获取音频时长失败 {input_path_str}: {e.stderr}")
        except FileNotFoundError:
            print("[DEBUG AUDIO GET_DURATION] ffprobe not found.")
            raise FileNotFoundError("ffprobe 未找到。请确保 ffmpeg (包含 ffprobe) 已安装并在系统路径中。")
        except ValueError as e:
            print(
                f"[DEBUG AUDIO GET_DURATION] ValueError converting ffprobe output for {input_path_str}: {result.stdout.strip()} - {e}")
            raise RuntimeError(f"ffprobe输出转换失败 {input_path_str}: {result.stdout.strip()}")

    @staticmethod
    def crop(input_path, output_path, start_sec, end_sec, snap_bpm=120):
        # (代码与 audio_processing_debug_v3 中的版本相同，此处省略以减少重复)
        # ...
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"输入文件不存在: {input_path}")

        snapped_start = util.snap_to_grid(start_sec, snap_bpm)
        snapped_end = util.snap_to_grid(end_sec, snap_bpm)

        cmd = [
            'ffmpeg', '-y',
            '-ss', str(snapped_start),
            '-to', str(snapped_end),
            '-i', str(input_path),
            '-c', 'copy',  # For cropping, -c copy is usually fine and fast
            str(output_path)
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音频裁剪失败: {e.stderr.decode(errors='ignore')}")

    @staticmethod
    def accelerate(input_path, output_path, factor):
        # (代码与 audio_processing_debug_v3 中的版本相同，此处省略以减少重复)
        # ...
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        if factor <= 0:
            raise ValueError("加速因子必须大于0")

        atempo_chain = []
        if not math.isclose(factor, 1.0):
            temp_factor = factor
            if temp_factor > 100.0:
                while temp_factor > 100.0:
                    atempo_chain.append('atempo=100.0')
                    temp_factor /= 100.0
                if temp_factor > 0.5:
                    atempo_chain.append(f'atempo={temp_factor}')
            elif temp_factor < 0.5:
                while temp_factor < 0.5:
                    atempo_chain.append('atempo=0.5')
                    temp_factor /= 0.5
                if temp_factor < 100.0 and not math.isclose(temp_factor, 1.0):
                    atempo_chain.append(f'atempo={temp_factor}')
            else:
                atempo_chain.append(f'atempo={factor}')

        filter_str = ','.join(atempo_chain) if atempo_chain else 'anull'
        cmd = [
            'ffmpeg', '-y',
            '-i', str(input_path),
            '-filter:a', filter_str,
            '-vn',
            str(output_path)
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音频加速失败: {e.stderr.decode(errors='ignore')}")

    @staticmethod
    def apply_fade(input_path, output_path, fade_type, duration_sec):
        # (代码与 audio_processing_debug_v3 中的版本相同，此处省略以减少重复)
        # ...
        if fade_type not in ['in', 'out']:
            raise ValueError("fade_type 必须是 'in' 或 'out'")
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"用于淡化的输入文件未找到: {input_path}")
        if duration_sec <= 0:
            shutil.copy(str(input_path), str(output_path))
            return

        fade_filter_params = ""
        if fade_type == 'in':
            fade_filter_params = f"afade=t=in:st=0:d={duration_sec}"
        else:  # 'out'
            audio_total_duration = AudioProcessor.get_duration(input_path)
            fade_start_time = audio_total_duration - duration_sec
            actual_fade_duration = duration_sec
            if fade_start_time < 0:
                fade_start_time = 0
                actual_fade_duration = audio_total_duration
            if actual_fade_duration <= 0:
                shutil.copy(str(input_path), str(output_path))
                return
            fade_filter_params = f"afade=t=out:st={max(0, fade_start_time)}:d={actual_fade_duration}"

        cmd = ['ffmpeg', '-y', '-i', str(input_path), '-af', fade_filter_params, str(output_path)]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音频淡化失败: {e.stderr.decode(errors='ignore')}")

    @staticmethod
    def create_silence(output_path, duration_sec):
        output_path_str = str(output_path)
        print(
            f"[DEBUG AUDIO CREATE_SILENCE] Attempting to create silence: {output_path_str}, Duration: {duration_sec:.3f}s")

        # Ensure duration is positive for ffmpeg
        safe_duration = max(0.001, duration_sec)

        cmd = [
            'ffmpeg', '-y', '-f', 'lavfi',
            '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100:d={safe_duration}',
            output_path_str
        ]
        try:
            print(f"[DEBUG AUDIO CREATE_SILENCE] Running: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.path.exists(output_path_str):
                print(
                    f"[DEBUG AUDIO CREATE_SILENCE] Silence file created successfully: {output_path_str}, Size: {os.path.getsize(output_path_str)}")
            else:
                print(f"[DEBUG AUDIO CREATE_SILENCE] ERROR: ffmpeg ran but silence file NOT found: {output_path_str}")
        except subprocess.CalledProcessError as e:
            print(
                f"[DEBUG AUDIO CREATE_SILENCE] Error creating silence for {output_path_str}: {e.stderr.decode(errors='ignore')}")
            raise RuntimeError(f"创建静音失败: {e.stderr.decode(errors='ignore')}")
        except Exception as ex:
            print(f"[DEBUG AUDIO CREATE_SILENCE] Unknown error creating silence: {ex}")
            raise RuntimeError(f"创建静音时发生未知错误: {ex}")

    @staticmethod
    def concatenate_list(input_paths, output_path):
        output_path_str = str(output_path)
        if not input_paths:
            raise ValueError("用于拼接的输入路径列表不能为空。")
        print(f"\n[DEBUG AUDIO CONCAT_LIST V2] Initial input paths: {input_paths}")

        valid_input_paths = []
        for path_str_orig in input_paths:
            p = Path(path_str_orig)
            if p.exists():
                try:
                    duration = AudioProcessor.get_duration(p)
                    if duration > 0.001:
                        valid_input_paths.append(str(p.resolve()))
                        print(
                            f"[DEBUG AUDIO CONCAT_LIST V2] Path {p} is valid. Duration: {duration:.3f}s. Added: {str(p.resolve())}")
                    else:
                        print(
                            f"[DEBUG AUDIO CONCAT_LIST V2] Path {p} exists but duration {duration:.3f}s is too short. Filtering out.")
                except Exception as e:
                    print(f"[DEBUG AUDIO CONCAT_LIST V2] Error getting duration for {p}: {e}. Filtering out.")
            else:
                print(f"[DEBUG AUDIO CONCAT_LIST V2] Path {p} does not exist. Filtering out.")

        print(f"[DEBUG AUDIO CONCAT_LIST V2] Filtered valid_input_paths for ffmpeg: {valid_input_paths}")

        if not valid_input_paths:
            print(
                "[DEBUG AUDIO CONCAT_LIST V2] No valid input paths after filtering. Creating a short silent file as output.")
            AudioProcessor.create_silence(output_path_str, 0.1)
            return

        if len(valid_input_paths) == 1:
            print(
                f"[DEBUG AUDIO CONCAT_LIST V2] Only one valid file: {valid_input_paths[0]}. Copying to output (trying -c copy first).")
            cmd_copy_single = ['ffmpeg', '-y', '-i', valid_input_paths[0], '-c', 'copy', output_path_str]
            try:
                print(f"[DEBUG AUDIO CONCAT_LIST V2] Running single file copy: {' '.join(cmd_copy_single)}")
                subprocess.run(cmd_copy_single, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print(f"[DEBUG AUDIO CONCAT_LIST V2] Single file copied successfully to {output_path_str}")
                return
            except subprocess.CalledProcessError as e_copy:
                print(
                    f"[DEBUG AUDIO CONCAT_LIST V2] Single file copy with -c copy failed: {e_copy.stderr.decode(errors='ignore')}. Trying re-encode.")
                cmd_reencode_single = ['ffmpeg', '-y', '-i', valid_input_paths[0],
                                       output_path_str]  # Let ffmpeg handle codecs
                try:
                    subprocess.run(cmd_reencode_single, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print(f"[DEBUG AUDIO CONCAT_LIST V2] Single file re-encoded successfully to {output_path_str}")
                    return
                except subprocess.CalledProcessError as e_reencode:
                    raise RuntimeError(
                        f"复制/重编码单个音频文件失败: Copy: {e_copy.stderr.decode(errors='ignore')}, Re-encode: {e_reencode.stderr.decode(errors='ignore')}")

        # For multiple files, ALWAYS RE-ENCODE for robustness
        temp_list_file_name = ""
        try:
            with NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as list_file:
                for path_str_resolved in valid_input_paths:
                    list_file.write(f"file '{path_str_resolved}'\n")
                temp_list_file_name = list_file.name
            print(f"[DEBUG AUDIO CONCAT_LIST V2] Temp list file for ffmpeg: {temp_list_file_name}")
            with open(temp_list_file_name, 'r', encoding='utf-8') as f_check:
                print(f"[DEBUG AUDIO CONCAT_LIST V2] Content of temp list file:\n{f_check.read()}")

            # Filter complex string for ffmpeg: [0:a][1:a][2:a]...concat=n=N:v=0:a=1[outa]
            # N is the number of input files
            filter_complex_inputs = "".join([f"[{i}:a]" for i in range(len(valid_input_paths))])
            filter_complex_params = f"concat=n={len(valid_input_paths)}:v=0:a=1[outa]"

            cmd_reencode_concat = ['ffmpeg', '-y']
            for p in valid_input_paths:  # Add all inputs
                cmd_reencode_concat.extend(['-i', p])

            cmd_reencode_concat.extend([
                '-filter_complex', f"{filter_complex_inputs}{filter_complex_params}",
                '-map', '[outa]',  # Map the output of the filter_complex
                output_path_str
            ])

            print(
                f"[DEBUG AUDIO CONCAT_LIST V2] Running ffmpeg concat (ALWAYS RE-ENCODE for multiple files): {' '.join(cmd_reencode_concat)}")
            subprocess.run(cmd_reencode_concat, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"[DEBUG AUDIO CONCAT_LIST V2] Concat (re-encode) successful: {output_path_str}")

        except subprocess.CalledProcessError as e:
            print(f"[DEBUG AUDIO CONCAT_LIST V2] Concat (re-encode) FAILED: {e.stderr.decode(errors='ignore')}")
            # Fallback to simpler concat if filter_complex fails (older ffmpeg might not like it as much)
            # This is the previous re-encode attempt without filter_complex, using the file list
            print(f"[DEBUG AUDIO CONCAT_LIST V2] Trying simpler re-encode via file list due to previous failure.")
            cmd_reencode_simple = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', temp_list_file_name,
                output_path_str
            ]
            try:
                print(
                    f"[DEBUG AUDIO CONCAT_LIST V2] Running ffmpeg concat (simpler re-encode): {' '.join(cmd_reencode_simple)}")
                subprocess.run(cmd_reencode_simple, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print(f"[DEBUG AUDIO CONCAT_LIST V2] Concat (simpler re-encode) successful: {output_path_str}")
            except subprocess.CalledProcessError as e_reencode_simple:
                print(
                    f"[DEBUG AUDIO CONCAT_LIST V2] Concat (simpler re-encode) also failed: {e_reencode_simple.stderr.decode(errors='ignore')}")
                raise RuntimeError(
                    f"音频拼接失败 (多种重新编码尝试均失败): FilterComplex: {e.stderr.decode(errors='ignore')}, SimplerReEncode: {e_reencode_simple.stderr.decode(errors='ignore')}")

        except Exception as ex:
            print(f"[DEBUG AUDIO CONCAT_LIST V2] Unknown error during concatenation: {ex}")
            raise RuntimeError(f"音频拼接时发生未知错误: {ex}")
        finally:
            if temp_list_file_name and os.path.exists(temp_list_file_name):
                try:
                    os.unlink(temp_list_file_name)
                    print(f"[DEBUG AUDIO CONCAT_LIST V2] Deleted temp list file: {temp_list_file_name}")
                except Exception as e_unlink:
                    print(
                        f"[DEBUG AUDIO CONCAT_LIST V2] Error deleting temp list file {temp_list_file_name}: {e_unlink}")
