# -*- coding: utf-8 -*-
import logging
from typing import Optional
from supabase import Client, create_client
from config import Settings

class SupabaseService:
    """
    封裝所有與 Supabase 互動的操作。
    """
    def __init__(self, settings: Settings):
        """
        初始化 Supabase 客戶端。
        """
        self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        self.bucket_name: str = settings.SUPABASE_BUCKET_NAME
        logging.info("Supabase 服務已成功初始化。")

    def check_paper_exists(self, arxiv_id: str) -> Optional[str]:
        """
        檢查論文是否已存在於資料庫中。
        """
        try:
            response = self.client.table("papers").select("title").eq("arxiv_id", arxiv_id).execute()
            if response.data:
                return response.data[0]['title']
            return None
        except Exception as e:
            logging.error(f"檢查論文 '{arxiv_id}' 時發生錯誤: {e}")
            # 在發生錯誤時，我們假設論文不存在，以允許重試
            return None

    def upload_audio(self, destination_path: str, audio_data: bytes) -> str:
        """
        上傳音訊檔案到 Supabase Storage 並返回公開 URL。
        使用 upsert=True，如果檔案已存在則會覆蓋，不存在則會建立。
        """
        try:
            self.client.storage.from_(self.bucket_name).upload(
                path=destination_path,
                file=audio_data,
                file_options={"contentType": "audio/wav", "upsert": "true"}
            )
            logging.info(f"🔼 成功上傳/更新 Storage 中的音檔: {destination_path}")

            # 獲取公開 URL
            public_url = self.client.storage.from_(self.bucket_name).get_public_url(destination_path)
            logging.info(f"🔗 成功獲取音檔的公開 URL: {public_url}")
            return public_url
        except Exception as e:
            logging.error(f"上傳音檔到 Storage 時失敗: {e}", exc_info=True)
            raise

    def insert_paper(self, paper_data: dict):
        """
        將處理完的論文資訊插入到 Supabase 資料庫中。
        """
        try:
            response = self.client.table("papers").insert(paper_data).execute()
            if not response.data:
                raise Exception("插入資料失敗，沒有回傳資料。")
            
            logging.info(f"✅ 成功將論文 '{paper_data['title']}' 插入到資料庫")
            return response.data[0]
        except Exception as e:
            logging.error(f"將論文 '{paper_data.get('title', 'N/A')}' 插入資料庫時失敗: {e}")
            raise 