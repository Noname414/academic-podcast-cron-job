# -*- coding: utf-8 -*-
import logging
from pathlib import Path
import json

from podcast_generater import PaperInfo

def save_output_locally(
    output_base_folder: str,
    arxiv_id: str,
    paper_info: PaperInfo,
    script: str,
    wav_data: bytes
):
    """
    (可選) 將所有生成的檔案儲存到本地資料夾，主要用於本地測試和除錯。
    """
    try:
        logging.info(f"📁 準備將產出儲存到本地資料夾 (僅供測試)...")
        output_base = Path(output_base_folder)
        paper_folder = output_base / arxiv_id
        paper_folder.mkdir(parents=True, exist_ok=True)
        logging.info(f"   - 本地輸出資料夾: {paper_folder}")

        # 儲存論文資訊
        info_path = paper_folder / f"{arxiv_id}_info.json"
        with open(info_path, 'w', encoding='utf-8') as f:
            # 使用 pydantic 的 model_dump_json 來生成漂亮的 JSON
            f.write(paper_info.model_dump_json(indent=4))
        logging.info(f"   - 論文資訊已儲存到: {info_path}")

        # 儲存逐字稿
        script_path = paper_folder / f"{arxiv_id}_script.txt"
        script_path.write_text(script, encoding='utf-8')
        logging.info(f"   - 逐字稿已儲存到: {script_path}")

        # 儲存音檔
        audio_path = paper_folder / f"{arxiv_id}.wav"
        with open(audio_path, 'wb') as f:
            f.write(wav_data)
        logging.info(f"   - 音檔已儲存到: {audio_path}")
        
    except Exception as e:
        logging.error(f"本地儲存檔案時發生錯誤: {e}", exc_info=True)
        # 本地儲存失敗不應中斷主流程
        pass 