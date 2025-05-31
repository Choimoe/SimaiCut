[Read this document in English (阅读英文版)](README_en.md)

# SimaiCut - Simai 谱面音频剪辑器

SimaiCut 是一个 Python 工具集，旨在帮助用户处理、剪辑和拼接 Simai 格式的音乐游戏谱面及其对应的音频文件。它可以方便地从现有谱面中提取片段，调整速度，并将多个片段组合成新的谱面和音频。

## 主要功能

* **谱面与音频同步处理**：对谱面 (`maidata.txt`) 和音频 (`track.mp3`) 进行统一的剪辑和变换操作。
* **片段裁剪**：精确裁剪指定时间段的谱面和音频。
* **速度调整**：同步加速或减速谱面事件和音频。
* **多片段拼接**：
    * 将多个（裁剪后的）谱面和音频片段按顺序拼接。
    * 在片段间自动计算并插入可配置时长的静音音频。
    * 在谱面层面，于拼接间隙使用前一首歌的末尾 BPM 填充适当数量的占位音符和逗号事件。
    * 支持在音频拼接处添加淡入/淡出效果。

## 开始使用

### 依赖环境

* **Python 3.7+**
* **FFmpeg**: 必须安装并将其可执行文件路径添加到系统的 `PATH` 环境变量中。FFmpeg 用于所有音频处理操作。
* **[SimaiParser](https://github.com/Choimoe/PySimaiParser)**: 本项目依赖于 `SimaiParser` 库来解析和重建 Simai 谱面数据。请确保该库已正确安装或位于项目的 Python 路径中。你可以使用下面命令来安装：
  ```bash
  pip install PySimaiParser
  ```

### 项目结构

```
SimaiCut/
├── SimaiCut/
│   ├── init.py
│   ├── audio.py              # 音频处理模块
│   ├── chart.py              # 谱面编辑逻辑 (裁剪、加速、拼接)
│   ├── editor.py             # Simai谱面编辑器类 (包装 SimaiParser)
│   ├── processor.py          # 核心处理器类，协调音频和谱面操作
│   └── util.py               # 辅助函数 (BPM计算、时间对齐等)
├── README.md                 # 本文档
└── README_en.md              # 英文版文档
```

## 模块概览

* **`processor.SongProcessor`**:
    核心类，封装了对单个歌曲（音频+谱面）的加载、处理（裁剪、加速）以及与其他 `SongProcessor` 实例拼接的功能。它管理着临时的音频和谱面文件。
* **`editor.SimaiEditor`**:
    包装了 `SimaiParser`，提供了更高级的谱面编辑接口。它将 Simai 文本谱面转换为内部 JSON 结构进行操作，并能将修改后的结构转换回 Simai 文本。
    * `crop()`: 裁剪谱面。
    * `accelerate()`: 加速谱面。
    * `concatenate()`: 将另一个谱面拼接到当前谱面，并处理间隙。
* **`audio.AudioProcessor`**:
    包含一系列静态方法，使用 FFmpeg 执行音频操作，如获取时长、裁剪、加速、应用淡入淡出、创建静音和拼接音频文件列表。
* **`chart.py`**:
    包含 `SimaiEditor` 类实际的谱面操作逻辑（裁剪、加速、拼接的具体实现）。这些方法被动态赋值给 `SimaiEditor` 类。
* **`util.py`**:
    提供一些通用辅助函数，例如在谱面特定时间点获取BPM、将时间点对齐到音乐网格等。

## 贡献

欢迎提交 Pull Request 或提出 Issues 来改进本项目！