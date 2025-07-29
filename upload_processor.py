# -*- coding: utf-8 -*-
"""
用戶上傳論文處理器
自動化處理 pending_uploads 表格中的檔案
"""
import logging
import uuid
from typing import List, Dict, Any
from datetime import datetime

from config import settings
from logging_config import setup_logging
from podcast_generater import PaperPodcastGenerator, PaperInfo
from services.supabase_service import SupabaseService
from utils.audio_utils import convert_pcm_to_wav_in_memory


class UploadProcessor:
    """用戶上傳論文處理器"""
    
    def __init__(self):
        """初始化處理器"""
        self.supabase_service = SupabaseService(settings)
        self.podcast_generator = PaperPodcastGenerator(settings.GEMINI_API_KEY)
        logging.info("🚀 用戶上傳論文處理器已初始化")
    
    def process_single_upload(self, upload_record: Dict[str, Any]) -> bool:
        """
        處理單個用戶上傳的檔案
        
        Args:
            upload_record: pending_uploads 表格中的記錄
            
        Returns:
            bool: 處理是否成功
        """
        upload_id = upload_record['id']
        original_filename = upload_record['original_filename']
        file_url = upload_record['file_url']
        user_id = upload_record['user_id']
        
        logging.info(f"📄 開始處理用戶上傳檔案: {original_filename} (ID: {upload_id})")
        
        try:
            # 1. 更新狀態為 processing
            self.supabase_service.update_pending_upload_status(
                upload_id=upload_id,
                status="processing"
            )
            
            # 2. 從 Storage 下載檔案
            logging.info("📥 正在從 Storage 下載檔案...")
            pdf_data = self.supabase_service.download_file_from_storage(file_url)
            
            # 3. 使用 podcast 生成器處理論文
            logging.info("🎧 正在生成播客內容...")
            podcast_result = self.podcast_generator.process_paper(pdf_data=pdf_data)
            
            paper_info: PaperInfo = podcast_result['paper_info']
            script: str = podcast_result['script']
            audio_data: bytes = podcast_result['audio_data']
            duration: float = podcast_result.get('duration_seconds', 0)
            
            # 4. 將 raw PCM 音訊轉換為 WAV 格式
            wav_data = convert_pcm_to_wav_in_memory(audio_data)
            
            # 5. 上傳音檔到 Supabase Storage
            logging.info("☁️ 正在上傳音檔到 Supabase Storage...")
            # 使用上傳記錄的 ID 作為音檔檔名，確保唯一性
            audio_dest_path = f"uploads/{upload_id}.wav"
            audio_url = self.supabase_service.upload_audio(audio_dest_path, wav_data)
            
            # 6. 準備資料並寫入 papers 資料庫
            db_record = {
                "title": paper_info.title,
                "authors": paper_info.authors,
                "journal": "用戶上傳",
                "publish_date": datetime.now().date().isoformat(),
                "summary": paper_info.abstract,
                "full_text": script,
                "category": paper_info.field,
                "tags": paper_info.tags,
                "innovations": paper_info.innovations,
                "method": paper_info.method,
                "results": paper_info.results,
                "audio_url": audio_url,
                "duration_seconds": round(duration),
                "arxiv_url": file_url,
                "pdf_url": file_url,  # 直接使用 Supabase Storage 的 public URL，可直接下載
                "arxiv_id": f"upload_{upload_id[:8]}"  # 生成一個唯一的標識符
            }
            
            # 7. 插入到 papers 表格並更新 pending_uploads 狀態
            paper_record = self.supabase_service.insert_paper_from_upload(db_record, upload_id)
            
            logging.info(f"🎉 成功處理用戶上傳論文: {paper_info.title}")
            return True
            
        except Exception as e:
            logging.error(f"處理用戶上傳檔案 {upload_id} 時發生錯誤: {e}", exc_info=True)
            
            # 更新狀態為 failed
            try:
                self.supabase_service.update_pending_upload_status(
                    upload_id=upload_id,
                    status="failed",
                    error_message=str(e)
                )
            except Exception as update_error:
                logging.error(f"更新失敗狀態時發生錯誤: {update_error}")
            
            return False
    
    def process_pending_uploads(self, max_count: int = 5) -> Dict[str, int]:
        """
        批量處理待處理的上傳檔案
        
        Args:
            max_count: 最大處理數量
            
        Returns:
            Dict[str, int]: 處理結果統計
        """
        logging.info(f"🔍 開始批量處理用戶上傳檔案 (最多 {max_count} 個)...")
        
        # 獲取待處理的上傳檔案
        pending_uploads = self.supabase_service.get_pending_uploads(limit=max_count)
        
        if not pending_uploads:
            logging.info("✅ 沒有待處理的上傳檔案")
            return {"total": 0, "success": 0, "failed": 0}
        
        results = {"total": len(pending_uploads), "success": 0, "failed": 0}
        
        for upload_record in pending_uploads:
            success = self.process_single_upload(upload_record)
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
        
        logging.info(f"📊 批量處理完成: 總共 {results['total']} 個檔案，"
                    f"成功 {results['success']} 個，失敗 {results['failed']} 個")
        
        return results


def main():
    """主程式入口"""
    setup_logging()
    logging.info("🚀 開始執行用戶上傳論文處理工作流程...")
    
    try:
        processor = UploadProcessor()
        results = processor.process_pending_uploads(max_count=10)
        
        if results["total"] > 0:
            logging.info(f"✅ 處理完成！成功率: {results['success']}/{results['total']} "
                        f"({results['success']/results['total']*100:.1f}%)")
        else:
            logging.info("✅ 目前沒有待處理的檔案")
            
    except Exception as e:
        logging.critical(f"😭 工作流程執行失敗: {e}", exc_info=True)
    
    logging.info("🏁 用戶上傳論文處理工作流程執行完畢")


if __name__ == "__main__":
    main() 