# -*- coding: utf-8 -*-
"""
專案設定檔
集中管理所有可調整的參數，方便維護與修改。
"""

# Gemini API 相關設定
GEMINI_MODELS = {
    # 用於從 PDF 提取結構化論文資訊的模型
    "info_extraction": "gemini-2.5-pro",
    
    # 用於生成 Podcast 逐字稿的模型
    "script_generation": "gemini-2.5-pro",
    
    # 用於文字轉語音 (TTS) 的模型
    "tts": "gemini-2.5-pro-preview-tts",
}

# Podcast 主持人設定
PODCAST_SPEAKERS = {
    "speaker1": {
        "name": "林冠傑",
        "voice": "Charon"  # 可選: Charon, Zephyr, Echo, Onyx, Nova, Aurora
    },
    "speaker2": {
        "name": "林欣潔",
        "voice": "Zephyr"
    }
}

# ArXiv 搜尋設定
ARXIV_SEARCH_CONFIG = {
    # 每次執行時，從 arXiv 獲取的最新論文數量
    "max_results": 5,
    
    # 搜尋的論文領域，例如 'cat:cs.AI', 'cat:cs.CV', 'cat:cs.CL'
    "query": "cat:cs.AI"
}

# 檔案與路徑設定
FILE_CONFIG = {
    # 生成的 Podcast 檔案存放的基礎資料夾名稱
    "output_base_folder": "Podcast_output"
}

# Supabase 設定
SUPABASE_CONFIG = {
    # 用於儲存音檔的 Storage Bucket 名稱
    "bucket_name": "audios"
} 