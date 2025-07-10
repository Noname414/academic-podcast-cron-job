# -*- coding: utf-8 -*-
import logging
import os

# 匯入重構後的模組
from config import settings
from logging_config import setup_logging
from arxiv_search import search_latest_ai_paper
from podcast_generater import PaperPodcastGenerator, PaperInfo
from services.supabase_service import SupabaseService
from utils.audio_utils import convert_pcm_to_wav_in_memory
from utils.file_utils import save_output_locally

def process_single_paper(
    paper: dict,
    supabase_service: SupabaseService,
    podcast_generator: PaperPodcastGenerator
):
    """
    處理單篇新論文的完整流程。
    """
    arxiv_id = paper['arxiv_id']
    pdf_url = paper['pdf_url']
    logging.info(f"📄 開始處理新論文: {paper['title']} (ID: {arxiv_id})")

    try:
        # 1. 生成 Podcast 內容和音訊
        podcast_result = podcast_generator.process_paper(pdf_url=pdf_url)
        paper_info: PaperInfo = podcast_result['paper_info']
        script: str = podcast_result['script']
        audio_data: bytes = podcast_result['audio_data']
        duration: float = podcast_result.get('duration_seconds', 0)

        # 2. 將 raw PCM 音訊轉換為 WAV 格式
        wav_data = convert_pcm_to_wav_in_memory(audio_data)

        # 3. (可選) 儲存所有產出到本地，方便除錯
        # 透過環境變數 SAVE_FILES_LOCALLY=true 來啟用
        if os.getenv("SAVE_FILES_LOCALLY", "false").lower() == "true":
            save_output_locally(
                output_base_folder=settings.OUTPUT_BASE_FOLDER,
                arxiv_id=arxiv_id,
                paper_info=paper_info,
                script=script,
                wav_data=wav_data
            )
            
        # 4. 上傳音檔到 Supabase Storage
        logging.info("☁️ 正在上傳音檔到 Supabase Storage...")
        audio_dest_path = f"{arxiv_id}.wav"
        audio_url = supabase_service.upload_audio(audio_dest_path, wav_data)

        # 5. 準備資料並寫入資料庫
        db_record = {
            "arxiv_id": arxiv_id,
            "title": paper_info.title,
            "authors": paper.get('authors', []),
            "publish_date": paper.get('updated').isoformat(),
            "summary": paper_info.abstract,
            "full_text": script,
            "category": paper.get('category'),
            "tags": paper_info.tags,
            "innovations": paper_info.innovations,
            "method": paper_info.method,
            "results": paper_info.results,
            "arxiv_url": paper.get('arxiv_url'),
            "pdf_url": pdf_url,
            "audio_url": audio_url,
            "duration_seconds": round(duration),
        }
        
        supabase_service.insert_paper(db_record)
        logging.info(f"🎉 成功處理並儲存論文: {paper_info.title}")

    except Exception as e:
        logging.error(f"處理論文 {arxiv_id} 時發生嚴重錯誤: {e}", exc_info=True)
        # 即使單篇論文失敗，也繼續處理下一篇
        pass

def main_workflow():
    """
    重構後的主工作流程。
    """
    # 1. 初始化
    setup_logging()
    logging.info("🚀 開始執行每日論文播客生成工作流程...")
    
    try:
        # 初始化服務
        supabase_service = SupabaseService(settings)
        podcast_generator = PaperPodcastGenerator(settings.GEMINI_API_KEY)
        
        # 2. 搜尋最新的論文
        logging.info("\n🔍 正在從 arXiv 搜尋最新論文...")
        latest_papers = search_latest_ai_paper(
            query=settings.ARXIV_QUERY,
            max_results=settings.ARXIV_MAX_RESULTS
        )
        if not latest_papers:
            logging.info("沒有找到新的論文。工作流程結束。")
            return

        new_papers_found = 0
        for paper in latest_papers:
            arxiv_id = paper['arxiv_id']
            
            # 3. 檢查論文是否已存在
            existing_title = supabase_service.check_paper_exists(arxiv_id)
            if existing_title:
                logging.info(f"✅ 論文 (ID: {arxiv_id}, 標題: {existing_title}) 已存在，跳過處理。")
                continue
            
            new_papers_found += 1
            process_single_paper(paper, supabase_service, podcast_generator)
            
            # 預設只處理一篇新論文，以避免超時
            # 若要處理所有找到的新論文，可註解掉此行
            break
        
        if new_papers_found == 0:
            logging.info("✅ 所有找到的論文都已處理過，本次無新論文。")

    except Exception as e:
        logging.critical(f"😭 工作流程執行失敗: {e}", exc_info=True)

    logging.info("\n🏁 工作流程執行完畢。")

if __name__ == "__main__":
    main_workflow() 