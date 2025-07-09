# -*- coding: utf-8 -*-
import io
import wave
import logging

def convert_pcm_to_wav_in_memory(pcm_data: bytes, channels: int = 1, sample_width: int = 2, frame_rate: int = 24000) -> bytes:
    """
    將 raw PCM 音訊資料在記憶體中轉換為 WAV 格式。
    """
    logging.info("🎙️ 正在將音訊資料轉換為 WAV 格式...")
    try:
        with io.BytesIO() as wav_file:
            with wave.open(wav_file, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(sample_width)
                wf.setframerate(frame_rate)
                wf.writeframes(pcm_data)
            wav_data = wav_file.getvalue()
        logging.info("✅ 音訊已成功轉換為 WAV 格式。")
        return wav_data
    except Exception as e:
        logging.error(f"音訊轉換為 WAV 時發生錯誤: {e}")
        raise 