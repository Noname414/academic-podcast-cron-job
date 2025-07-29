# -*- coding: utf-8 -*-
import logging
from typing import Optional, List, Dict, Any
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

    def get_pending_uploads(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        獲取狀態為 pending 的上傳檔案列表。
        """
        try:
            response = self.client.table("pending_uploads")\
                .select("*")\
                .eq("status", "pending")\
                .order("created_at", desc=False)\
                .limit(limit)\
                .execute()
            
            logging.info(f"📋 找到 {len(response.data)} 個待處理的上傳檔案")
            return response.data
        except Exception as e:
            logging.error(f"獲取待處理上傳檔案時發生錯誤: {e}")
            return []

    def update_pending_upload_status(self, upload_id: str, status: str, error_message: str = None, 
                                   extracted_info: Dict[str, Any] = None):
        """
        更新 pending_upload 的狀態和相關資訊。
        """
        try:
            update_data = {
                "status": status,
                "updated_at": "now()"
            }
            
            if error_message:
                update_data["error_message"] = error_message
            
            if extracted_info:
                if "title" in extracted_info:
                    update_data["extracted_title"] = extracted_info["title"]
                if "authors" in extracted_info:
                    update_data["extracted_authors"] = extracted_info["authors"]
                if "abstract" in extracted_info:
                    update_data["extracted_abstract"] = extracted_info["abstract"]
            
            response = self.client.table("pending_uploads")\
                .update(update_data)\
                .eq("id", upload_id)\
                .execute()
            
            logging.info(f"✅ 已更新上傳檔案 {upload_id} 的狀態為: {status}")
            return response.data[0] if response.data else None
        except Exception as e:
            logging.error(f"更新上傳檔案狀態時發生錯誤: {e}")
            raise

    def download_file_from_storage(self, file_url: str) -> bytes:
        """
        從 Supabase Storage 下載檔案。
        """
        try:
            # 從完整 URL 中提取檔案路徑
            # URL 格式: https://xxx.supabase.co/storage/v1/object/public/bucket/path
            url_parts = file_url.split('/storage/v1/object/public/')
            if len(url_parts) != 2:
                raise ValueError(f"無效的 Storage URL 格式: {file_url}")
            
            path_with_bucket = url_parts[1]
            # 移除 bucket 名稱，獲取實際檔案路徑
            path_parts = path_with_bucket.split('/', 1)
            if len(path_parts) != 2:
                raise ValueError(f"無法解析檔案路徑: {path_with_bucket}")
            
            bucket_name = path_parts[0]
            file_path = path_parts[1]
            
            logging.info(f"正在從 Storage 下載檔案: {file_path}")
            response = self.client.storage.from_(bucket_name).download(file_path)
            
            logging.info(f"✅ 成功下載檔案，大小: {len(response):,} bytes")
            return response
        except Exception as e:
            logging.error(f"從 Storage 下載檔案失敗: {e}")
            raise

    def insert_paper_from_upload(self, paper_data: dict, upload_id: str):
        """
        將處理完的用戶上傳論文資訊插入到 papers 資料庫中，並更新 pending_uploads 狀態。
        """
        try:
            # 插入論文資料
            response = self.client.table("papers").insert(paper_data).execute()
            if not response.data:
                raise Exception("插入論文資料失敗，沒有回傳資料。")
            
            paper_record = response.data[0]
            logging.info(f"✅ 成功將用戶上傳論文 '{paper_data['title']}' 插入到資料庫")
            
            # 更新 pending_uploads 狀態為 completed
            self.update_pending_upload_status(
                upload_id=upload_id,
                status="completed",
                extracted_info={
                    "title": paper_data['title'],
                    "authors": paper_data.get('authors', []),
                    "abstract": paper_data.get('summary', '')
                }
            )
            
            return paper_record
        except Exception as e:
            # 如果插入失敗，更新狀態為 failed
            try:
                self.update_pending_upload_status(
                    upload_id=upload_id,
                    status="failed",
                    error_message=str(e)
                )
            except:
                pass  # 避免雙重異常
            
            logging.error(f"將用戶上傳論文 '{paper_data.get('title', 'N/A')}' 插入資料庫時失敗: {e}")
            raise 