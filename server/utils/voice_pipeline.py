"""
语音管道 — 本地 STT + TTS，替代 Omni 云 API

  STT: faster-whisper (Whisper base 模型, 本地)
  TTS: edge-tts (Microsoft Edge 免费 TTS, 中文语音好)
"""

import asyncio
import base64
import logging
import os
import tempfile
import time
from typing import AsyncIterator

_log = logging.getLogger(__name__)

# ── TTS 文本清洗 ──────────────────────────────────────────
import re

_TTS_CLEANUP = [
    (re.compile(r'\*{1,2}([^*]+?)\*{1,2}'), r'\1'),  # **bold** / *italic*（非贪婪）
    (re.compile(r'_{1,2}([^_]+?)_{1,2}'), r'\1'),    # __bold__ / _italic_
    (re.compile(r'#{1,4}\s*'), ''),                    # ## heading
    (re.compile(r'`{1,3}[^`]*`{1,3}'), ''),           # `code`
    (re.compile(r'\*{1,2}'), ''),                      # 残留的单独 ** 或 *
]

def _clean_tts_text(text: str) -> str:
    """移除 markdown 标记，保留纯文本用于 TTS"""
    for pattern, repl in _TTS_CLEANUP:
        text = pattern.sub(repl, text)
    return text.strip()

# ── STT 配置 ──────────────────────────────────────────────
WHISPER_MODEL = "base"        # tiny/base/small/medium/large-v3
WHISPER_DEVICE = "cuda"       # cpu / cuda
WHISPER_COMPUTE = "float16"   # int8 / float16 / auto（GPU 用 float16）

# ── TTS 配置 ──────────────────────────────────────────────
TTS_VOICE = "zh-CN-YunxiNeural"   # 男声
TTS_RATE = "+25%"          # 语速: -50% ~ +100%

# ── 模块级 Whisper 单例（多协程共享，避免重复加载 140MB 模型）──
_whisper_model = None
_whisper_lock = asyncio.Lock()


async def _get_whisper():
    """获取或初始化全局 Whisper 模型（async-safe 双重检查锁）"""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    async with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model
        from faster_whisper import WhisperModel
        _log.info("加载 Whisper 模型: %s (device=%s compute=%s)",
                  WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE)
        t0 = time.time()
        try:
            _whisper_model = WhisperModel(
                WHISPER_MODEL,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE,
                local_files_only=True,
            )
        except Exception:
            _log.warning("离线加载失败，尝试在线下载...")
            _whisper_model = WhisperModel(
                WHISPER_MODEL,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE,
            )
        _log.info("Whisper 加载完成, 耗时 %.1fs", time.time() - t0)
        return _whisper_model


class VoicePipeline:
    """本地语音管道：STT (Whisper) + TTS (Edge TTS)"""

    def __init__(self, tts_voice: str = TTS_VOICE,
                 tts_rate: str = TTS_RATE):
        self._tts_voice = tts_voice
        self._tts_rate = tts_rate

    async def stt(self, audio_base64: str, fmt: str = "webm") -> str:
        """将 base64 音频转为文字。（单个完整音频的便捷方法）

        Args:
            audio_base64: base64 编码的音频数据
            fmt: 音频格式 (webm / wav / mp3 等)

        Returns:
            转录文本，失败返回空字符串
        """
        if not audio_base64:
            _log.warning("[VP-STT] 音频数据为空")
            return ""

        try:
            raw = base64.b64decode(audio_base64)
        except Exception as e:
            _log.error("[VP-STT] base64 解码失败: %s", e)
            return ""

        return await self.stt_bytes(raw, fmt)

    async def stt_bytes(self, audio_bytes: bytes, fmt: str = "webm") -> str:
        """将原始音频字节转为文字。

        Args:
            audio_bytes: 原始音频数据
            fmt: 音频格式 (webm / wav / mp3 等)

        Returns:
            转录文本，失败返回空字符串
        """
        if not audio_bytes:
            _log.warning("[VP-STT] 音频数据为空")
            return ""

        whisper = await _get_whisper()

        suffix = f".{fmt}" if fmt else ".webm"
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            with open(tmp_path, "wb") as f:
                f.write(audio_bytes)

            _log.debug("[VP-STT] 音频 %s bytes → %s, 开始转录...", len(audio_bytes), tmp_path)

            segments, info = whisper.transcribe(tmp_path, language="zh")

            text = "".join(seg.text for seg in segments).strip()
            _log.debug("[VP-STT] 转录完成: lang=%s prob=%.2f text=%s",
                      info.language, info.language_probability, text[:120])
            return text

        except Exception as e:
            _log.exception("[VP-STT] 转录失败: %s", e)
            return ""
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # ═══════════════════════════════════════════════════════
    # TTS: 文字 → 语音
    # ═══════════════════════════════════════════════════════

    async def tts_stream(self, text: str, voice: str | None = None) -> AsyncIterator[str]:
        """流式 TTS，逐块产出 base64 音频。

        Args:
            text: 要合成语音的文本
            voice: TTS 音色（默认 zh-CN-XiaoxiaoNeural）

        Yields:
            base64 编码的 mp3 音频块
        """
        if not text:
            _log.warning("[VP-TTS] 文本为空，跳过 TTS")
            return

        import edge_tts
        v = voice or self._tts_voice
        text = _clean_tts_text(text)  # 移除 ** 等 markdown

        _log.debug("[VP-TTS] 开始合成 voice=%s rate=%s text_len=%s text=%s",
                  v, self._tts_rate, len(text), text[:60])

        chunk_count = 0
        try:
            communicate = edge_tts.Communicate(text, v, rate=self._tts_rate)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunk_count += 1
                    b64 = base64.b64encode(chunk["data"]).decode("ascii")
                    yield b64
        except Exception as e:
            _log.exception("[VP-TTS] 合成失败: %s", e)

        _log.debug("[VP-TTS] 合成完成, chunks=%s", chunk_count)

    async def tts_full(self, text: str, voice: str | None = None) -> str:
        """非流式 TTS，返回完整 base64 音频。

        Args:
            text: 要合成语音的文本
            voice: TTS 音色

        Returns:
            完整 base64 mp3 音频，失败返回空字符串
        """
        parts = []
        async for chunk in self.tts_stream(text, voice):
            parts.append(chunk)
        return "".join(parts)
