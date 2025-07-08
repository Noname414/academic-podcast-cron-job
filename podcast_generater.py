# -*- coding: utf-8 -*-
"""
論文播客生成器（結構化輸出版）
使用 Gemini API 結構化輸出
"""

import os
import wave
import json
import httpx
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from google import genai
from google.genai.client import Client
from google.genai import types
from google.genai.types import GenerateContentConfig, SpeechConfig, MultiSpeakerVoiceConfig, SpeakerVoiceConfig, VoiceConfig, PrebuiltVoiceConfig

# 匯入設定
from config import GEMINI_MODELS, PODCAST_SPEAKERS, FILE_CONFIG

class PaperInfo(BaseModel):
    """論文資訊的結構化模型"""
    title: str = Field(description="論文標題的中文翻譯")
    abstract: str = Field(description="論文摘要的中文翻譯，約200-300字")
    field: str = Field(description="主要研究領域")
    tags: List[str] = Field(description="論文的關鍵字標籤，3-5個")
    innovations: List[str] = Field(description="核心創新點或貢獻，3-5個要點")
    method: str = Field(description="研究方法簡述")
    results: str = Field(description="主要結果或發現")

class PodcastScript(BaseModel):
    """播客逐字稿的結構化模型"""
    title: str = Field(description="播客節目標題")
    speakers: List[str] = Field(description="主持人列表")
    segments: List[dict] = Field(description="播客段落，包含speaker和content")
    duration_estimate: str = Field(description="預估播放時間")

class PaperPodcastGenerator:
    def __init__(self, api_key: str = None):
        """
        初始化播客生成器
        
        Args:
            api_key (str): Gemini API 金鑰，如果為 None 則從環境變數讀取
        """
        
        # 如果提供了 api_key，則使用它，否則 Client 會自動從環境變數尋找
        self.client = Client(api_key=api_key)
        
        # 從設定檔讀取主持人設定
        self.speaker1 = PODCAST_SPEAKERS["speaker1"]["name"]
        self.speaker2 = PODCAST_SPEAKERS["speaker2"]["name"]
        self.speaker1_voice = PODCAST_SPEAKERS["speaker1"]["voice"]
        self.speaker2_voice = PODCAST_SPEAKERS["speaker2"]["voice"]
        
        # 檔案大小限制
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        
    def read_pdf_from_url(self, pdf_url: str) -> bytes:
        """從URL讀取PDF內容"""
        try:
            print(f"正在下載PDF: {pdf_url}")
            if not pdf_url.startswith(('http://', 'https://')):
                raise ValueError(f"無效的URL格式: {pdf_url}")
            
            with httpx.Client(timeout=60.0) as client:
                response = client.get(pdf_url)
                response.raise_for_status()
                
                if 'pdf' not in response.headers.get('content-type', '').lower() and not pdf_url.lower().endswith('.pdf'):
                    print(f"警告: 內容類型可能不是PDF: {response.headers.get('content-type', '')}")
                
                pdf_data = response.content
                if not pdf_data.startswith(b'%PDF'):
                    raise ValueError("下載的檔案不是有效的PDF格式")
                
                return pdf_data
                
        except Exception as e:
            raise Exception(f"下載PDF失敗: {str(e)}")
    
    def read_pdf_from_file(self, pdf_path):
        """
        從本地文件讀取PDF內容
        
        Args:
            pdf_path (str): PDF文件的本地路徑
            
        Returns:
            bytes: PDF文件的二進位內容
        """
        try:
            pdf_path = Path(pdf_path).resolve()
            
            print(f"正在讀取檔案: {pdf_path}")
            
            if not pdf_path.exists():
                current_dir = Path.cwd()
                raise FileNotFoundError(
                    f"找不到檔案: {pdf_path}\n"
                    f"當前目錄: {current_dir}\n"
                    f"請確認檔案路徑是否正確"
                )
            
            if not pdf_path.is_file():
                raise ValueError(f"路徑不是檔案: {pdf_path}")
            
            file_size = pdf_path.stat().st_size
            if file_size == 0:
                raise ValueError("檔案是空的")
            
            if file_size > self.max_file_size:
                raise ValueError(
                    f"檔案太大: {file_size / 1024 / 1024:.2f}MB "
                    f"(最大 {self.max_file_size / 1024 / 1024}MB)"
                )
            
            print(f"檔案大小: {file_size / 1024 / 1024:.2f}MB")
            
            if not pdf_path.suffix.lower() == '.pdf':
                print(f"警告: 檔案擴展名不是.pdf: {pdf_path.suffix}")
            
            with open(pdf_path, 'rb') as f:
                pdf_data = f.read()
            
            if not pdf_data.startswith(b'%PDF'):
                raise ValueError("檔案不是有效的PDF格式")
            
            print(f"✅ 成功讀取PDF檔案，大小: {len(pdf_data):,} bytes")
            return pdf_data
            
        except FileNotFoundError as e:
            raise Exception(f"檔案不存在: {str(e)}")
        except PermissionError:
            raise Exception(f"沒有權限讀取檔案: {pdf_path}")
        except OSError as e:
            raise Exception(f"系統錯誤: {str(e)}")
        except Exception as e:
            raise Exception(f"讀取PDF文件失敗: {str(e)}")
    
    def extract_paper_info(self, pdf_data: bytes) -> PaperInfo:
        """使用Gemini結構化輸出從PDF中提取論文資訊"""
        try:
            print("正在分析論文內容...")
            prompt = """
            請分析這篇學術論文，並用繁體中文提取以下關鍵資訊：
            1. 將論文標題翻譯成繁體中文
            2. 將論文摘要翻譯成繁體中文，大約200-300字
            3. 識別主要研究領域
            4. 總結3-5個核心創新點或貢獻
            5. 簡述研究方法
            6. 概括主要結果或發現
            7. 提供3-5個最相關的關鍵字標籤 (tags)
            請確保所有內容都使用繁體中文，並且準確反映論文的核心內容。
            """
            
            response = self.client.models.generate_content(
                model=GEMINI_MODELS["info_extraction"],
                contents=[
                    types.Part.from_bytes(
                        data=pdf_data,
                        mime_type='application/pdf'
                    ), 
                    prompt
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": PaperInfo,
                }
            )
            
            paper_info = PaperInfo.model_validate_json(response.text)
            print(f"✅ 成功提取論文資訊: {paper_info.title}")
            return paper_info
            
        except Exception as e:
            raise Exception(f"分析論文失敗: {str(e)}")
    
    def generate_podcast_script(self, paper_info: PaperInfo) -> Dict[str, Any]:
        """生成結構化播客討論逐字稿"""
        try:
            print("正在生成播客逐字稿...")
            innovations_text = '\n'.join([f"- {innovation}" for innovation in paper_info.innovations])
            prompt = f"""
            根據以下論文內容，整理出雙人 Podcast 逐字稿，遵循以下規則：
            - 逐字稿使用繁體中文。
            - 逐字稿總長度約 1000 字。
            - 分別有 主持人 "{self.speaker1}" 與 主持人 "{self.speaker2}"，"{self.speaker1}" 為台灣人年輕男性、"{self.speaker2}" 為台灣人年輕女性。
            - 如果有必要，主持人互相使用 "你" 稱呼。
            - 皆使用台灣用語、台灣連接詞，可以適時使用台灣狀聲詞。
            - 如果有需要描述語氣、情緒，使用 "{{}}"，例如 "{{哈哈大笑}}" 或 "{{難過情緒}}"。
            - 只需要輸出逐字稿，不需要其他說明。
            - <其他要求，例如流程、架構、著重特定聽者>

            逐字稿範例：
            ```
            Speaker 1: {{驚嘆}} 哇塞！各位聽眾朋友，你們知道嗎？
            Speaker 2: {{疑問語氣}} 最近有什麼有趣的新聞嗎？
            Speaker 1: NotebookLM 最近加入一個「Audio Overviews」新功能。
            Speaker 2: {{小小的疑問}} 你是說 Google 推出的 NotebookLM 嗎？
            Speaker 1: 沒錯！它最近有個新功能，可以把 PDF、影片、圖檔這些資料，直接做成精美的簡報，而且還有圖片跟流暢的旁白喔！據說它可能用了那個很威的影片生成模型 Veo2。
            Speaker 2: {{語氣轉折、好奇}} 不過咧，講到這裡，可能有些台灣朋友會想說：「{{疑問語氣}} 那中文版可以用嗎？」
            Speaker 1: {{微微嘆氣}} 欸，很可惜，目前中文版的 NotebookLM 還沒看到這個 Video Overviews 的功能...
            ```
            
            論文資訊：
            ```
            標題：{paper_info.title}
            研究領域：{paper_info.field}
            摘要：{paper_info.abstract}
            創新點：{innovations_text}
            研究方法：{paper_info.method}
            主要結果：{paper_info.results}
            ```
            
            """
            response = self.client.models.generate_content(
                model=GEMINI_MODELS["script_generation"],
                contents=prompt,
            )
            return response.text
            
        except Exception as e:
            raise Exception(f"生成逐字稿失敗: {str(e)}")
    
    def generate_audio(self, script_text: str) -> bytes:
        """將逐字稿轉換為語音並回傳二進位資料"""
        try:
            print("正在生成語音...")
            response = self.client.models.generate_content(
                model=GEMINI_MODELS["tts"],
                contents=script_text,
                config=GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=SpeechConfig(
                        multi_speaker_voice_config=MultiSpeakerVoiceConfig(
                            speaker_voice_configs=[
                                SpeakerVoiceConfig(speaker=self.speaker1, voice_config=VoiceConfig(prebuilt_voice_config=PrebuiltVoiceConfig(voice_name=self.speaker1_voice))),
                                SpeakerVoiceConfig(speaker=self.speaker2, voice_config=VoiceConfig(prebuilt_voice_config=PrebuiltVoiceConfig(voice_name=self.speaker2_voice))),
                            ]
                        )
                    )
                )
            )
            
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            print(f"🎵 語音生成完畢，大小: {len(audio_data):,} bytes")
            return audio_data
            
        except Exception as e:
            raise Exception(f"生成語音失敗: {str(e)}")
    
    def process_paper(self, pdf_url: str) -> Dict[str, Any]:
        """
        完整處理單篇論文，從下載到生成所有內容，並在記憶體中回傳。
        
        Args:
            pdf_url (str): 論文的 PDF URL。
            
        Returns:
            Dict[str, Any]: 包含所有生成資訊和音檔資料的字典。
        """
        try:
            # 1. 下載 PDF
            pdf_data = self.read_pdf_from_url(pdf_url)
            
            # 2. 分析論文
            paper_info = self.extract_paper_info(pdf_data)
            
            # 3. 生成逐字稿 (返回純文字)
            script_text = self.generate_podcast_script(paper_info)
            
            # 4. 生成音檔 (返回二進位資料)
            audio_data = self.generate_audio(script_text)
            
            print("\n✅ 播客生成完成！所有內容已在記憶體中準備好。")
            
            # 建立一個預設的 Podcast 標題
            podcast_title = f"學術新知解密：深入探討《{paper_info.title}》"

            return {
                "paper_info": paper_info,
                "podcast_title": podcast_title,
                "script": script_text,
                "audio_data": audio_data,
            }
            
        except Exception as e:
            # 確保拋出原始錯誤以便上層捕獲
            raise Exception(f"處理論文失敗: {str(e)}")


def main():
    """主程式，用於獨立測試"""
    print("=== 論文播客生成器（模組化版） ===")
    
    try:
        # 從環境變數加載 API Key
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("錯誤：請設定 GEMINI_API_KEY 環境變數。")
            return
            
        generator = PaperPodcastGenerator(api_key=api_key)
        
        # 獲取用戶輸入
        pdf_url = input("請輸入論文PDF的URL：\n").strip()
        if not pdf_url:
            print("未提供URL，程式結束。")
            return
            
        # 處理論文
        results = generator.process_paper(pdf_url)
        
        print("\n=== 處理結果摘要 ===")
        print(f"🎧 Podcast 標題: {results['podcast_title']}")
        print(f"🎵 音檔大小: {len(results['audio_data']) / 1024:.2f} KB")
        print(f"📄 論文標題: {results['paper_info'].title}")
        print(f"📝 逐字稿長度: {len(results['script'])} 字")
        
        # 為了測試，可以選擇性地儲存音檔
        save_choice = input("是否要將音檔儲存為 'test_output.wav'？(y/N): ").lower()
        if save_choice == 'y':
            with wave.open('test_output.wav', 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(results['audio_data'])
            print("音檔已儲存。")
        
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")


if __name__ == "__main__":
    main() 