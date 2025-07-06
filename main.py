# -*- coding: utf-8 -*-
import os
import mimetypes
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# 從我們重構的模組中導入函式和類
from arxiv_search import search_latest_ai_paper
from podcast_generater import PaperPodcastGenerator, PaperInfo
from config import ARXIV_SEARCH_CONFIG, SUPABASE_CONFIG

def init_supabase_client() -> Client:
    """初始化並返回 Supabase 客戶端"""
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Supabase URL 和 Key 必須在 .env 文件中設定")
    return create_client(url, key)

def check_paper_exists(client: Client, arxiv_id: str) -> bool:
    """檢查論文是否已存在於資料庫中"""
    try:
        response = client.table("papers").select("id").eq("arxiv_id", arxiv_id).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"檢查論文時發生錯誤: {e}")
        return False

def upload_to_storage(client: Client, bucket_name: str, file_path: str, destination_path: str) -> str:
    """上傳文件到 Supabase Storage 並返回公開 URL"""
    try:
        content_type, _ = mimetypes.guess_type(file_path)
        options = {"contentType": content_type or "application/octet-stream"}

        with open(file_path, 'rb') as f:
            # 首先嘗試更新（如果檔案已存在）
            try:
                client.storage.from_(bucket_name).update(path=destination_path, file=f, file_options=options)
                print(f"🔄 成功更新 Storage 中的檔案: {destination_path}")
            except Exception:
                # 如果更新失敗（通常是因為檔案不存在），則上傳新檔案
                f.seek(0) # 重設檔案指標
                client.storage.from_(bucket_name).upload(path=destination_path, file=f, file_options=options)
                print(f"🔼 成功上傳新檔案到 Storage: {destination_path}")

        # 獲取公開 URL
        response = client.storage.from_(bucket_name).get_public_url(destination_path)
        return response
    except Exception as e:
        raise Exception(f"上傳 {file_path} 到 Storage 時失敗: {e}")


def insert_paper_to_db(client: Client, paper_data: dict):
    """將處理完的論文資訊插入到 Supabase 資料庫中"""
    try:
        response = client.table("papers").insert(paper_data).execute()
        if len(response.data) == 0:
            raise Exception("插入資料失敗，沒有回傳資料。")
        print(f"✅ 成功將論文 '{paper_data['title']}' 插入到資料庫")
        return response.data[0]
    except Exception as e:
        raise Exception(f"插入資料庫時失敗: {e}")

def main_workflow():
    """完整的工作流程"""
    print("🚀 開始執行每日論文播客生成工作流程...")
    
    try:
        # 1. 初始化
        supabase = init_supabase_client()
        podcast_generator = PaperPodcastGenerator()
        
        # 2. 搜尋最新的論文
        print("\n🔍 正在從 arXiv 搜尋最新論文...")
        latest_papers = search_latest_ai_paper(
            query=ARXIV_SEARCH_CONFIG["query"],
            max_results=ARXIV_SEARCH_CONFIG["max_results"]
        )
        if not latest_papers:
            print("沒有找到新的論文。工作流程結束。")
            return

        for paper in latest_papers:
            arxiv_id = paper['arxiv_id']
            pdf_url = paper['pdf_url']
            print(f"\n📄 找到論文: {paper['title']} (ID: {arxiv_id})")

            # 3. 檢查論文是否已存在
            if check_paper_exists(supabase, arxiv_id):
                print(f"✅ 這篇論文 (ID: {arxiv_id}) 已經在資料庫中，跳過處理。")
                continue

            # 4. 處理新論文
            print(f"✨ 找到新論文，開始生成 Podcast...")
            try:
                # 生成 Podcast 內容和檔案
                podcast_result = podcast_generator.process_paper(pdf_url=pdf_url)
                paper_info: PaperInfo = podcast_result['paper_info']

                # 5. 上傳音檔到 Supabase Storage
                print("☁️ 正在上傳音檔到 Supabase Storage...")
                bucket_name = SUPABASE_CONFIG["audio"]

                # 將音檔上傳到 bucket 中的 'audio' 資料夾
                audio_dest_path = f"audio/{arxiv_id}.wav"
                audio_url = upload_to_storage(supabase, bucket_name, podcast_result['audio_path'], audio_dest_path)
                print(f"🔗 音檔 URL: {audio_url}")

                # 6. 準備資料並寫入資料庫
                # 現在，paper_info 的內容和 script 文字稿直接存入資料庫，不再上傳對應的 .json 和 .txt 檔案
                db_record = {
                    "arxiv_id": arxiv_id,
                    "title": paper_info.title,
                    "authors": paper.get('authors', []),
                    "publish_date": paper.get('updated').isoformat(),
                    "summary": paper_info.abstract,
                    "category": paper_info.field,
                    "innovations": paper_info.innovations,
                    "method": paper_info.method,
                    "results": paper_info.results,
                    "arxiv_url": paper.get('arxiv_url'),
                    "pdf_url": pdf_url,
                    "audio_url": audio_url,
                    "podcast_title": podcast_result['podcast_title'],
                    "podcast_script": podcast_result['script'],
                }
                
                insert_paper_to_db(supabase, db_record)
                print(f"🎉 成功處理並儲存論文: {paper_info.title}")

            except Exception as e:
                print(f"處理論文 {arxiv_id} 時發生嚴重錯誤: {e}")
                # 即使單篇論文失敗，也繼續處理下一篇
                continue

    except Exception as e:
        print(f"😭 工作流程執行失敗: {e}")

    print("\n🏁 工作流程執行完畢。")

if __name__ == "__main__":
    main_workflow() 