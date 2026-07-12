from pathlib import Path

# 下载临时ffmpeg
ffmpeg_bin = Path("ffmpeg.exe")
if not ffmpeg_bin.exists():
    # windows简易版ffmpeg
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    print("请手动下载ffmpeg放到当前文件夹，或者改用在线工具：https://convertio.co/cn/mp3-pcm/")

# 备选：在线网站一键转换（最省事）
"""
打开网站：https://convertio.co/zh/mp3-pcm/
1.上传demo.mp3
2.输出格式选 PCM → 参数：16000Hz、16bit、单声道
3.下载后文件名改成demo.pcm丢进文件夹
"""
