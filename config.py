# -*- coding: utf-8 -*-
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    統一管理專案的所有設定，能自動從 .env 檔案或環境變數讀取。
    """
    # .env 檔案設定
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

    # Supabase 設定
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_BUCKET_NAME: str = "audio"

    # Gemini API 設定
    GEMINI_API_KEY: str

    # Arxiv 搜尋設定
    ARXIV_QUERY: str = "cat:cs.AI"
    ARXIV_MAX_RESULTS: int = 5
    
    # 輸出資料夾 (本地測試用)
    OUTPUT_BASE_FOLDER: str = "Podcast_output"


# 建立一個全域可用的設定實例
settings = Settings() 