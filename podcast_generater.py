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
        
    def create_output_folder(self, paper_title: str) -> Path:
        """為每次執行創建專用的輸出資料夾"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in paper_title if c.isalnum() or c in (' ', '-', '_', '，', '。'))
        safe_title = safe_title[:30].strip() or "論文播客"
        folder_name = f"{timestamp}_{safe_title}"
        
        output_base = Path(FILE_CONFIG["output_base_folder"])
        output_base.mkdir(exist_ok=True)
        output_folder = output_base / folder_name
        output_folder.mkdir(exist_ok=True)
        
        print(f"📁 創建輸出資料夾: {output_folder}")
        return output_folder
    
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
            基於以下論文資訊，為播客節目「學術新知解密」生成一段專業且引人入勝的逐字稿，確保對話內容自然流暢。
            
            論文資訊：
            標題：{paper_info.title}
            研究領域：{paper_info.field}
            摘要：{paper_info.abstract}
            創新點：{innovations_text}
            研究方法：{paper_info.method}
            主要結果：{paper_info.results}
            
            播客要求：
            - 主持人：{self.speaker1}（偏向理論分析）和 {self.speaker2}（偏向實際應用）
            - 節目名稱：「學術新知解密」
            - 時長：約5-7分鐘
            - 語氣：專業但親和
            - 結構：開場、背景介紹、核心創新點討論、應用價值探討、總結。
            
            請直接輸出逐字稿，不要輸出任何其他內容。
            """
            
                        
            # 請在逐字稿中明確標示兩位主持人的發言，例如：
            # {self.speaker1}: 【興奮地說】大家好...
            # {self.speaker2}: 【笑著說】沒錯...
            
            response = self.client.models.generate_content(
                model=GEMINI_MODELS["script_generation"],
                contents=prompt,
            )
            return response.text
            
        except Exception as e:
            raise Exception(f"生成逐字稿失敗: {str(e)}")
    
    def generate_audio(self, script_text: str, output_folder: Path, filename: str = "播客音檔.wav") -> Path:
        """將逐字稿轉換為語音"""
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
            output_path = output_folder / filename
            self.save_wave_file(str(output_path), audio_data)
            
            print(f"🎵 音頻文件已保存: {output_path}")
            return output_path
            
        except Exception as e:
            raise Exception(f"生成語音失敗: {str(e)}")
    
    def save_wave_file(self, filename: str, pcm_data: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2):
        """保存Wave格式音頻文件"""
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm_data)
    
    def save_json(self, data: Dict, path: Path):
        """將字典儲存為 JSON 檔案"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"📄 JSON 文件已保存: {path}")
    
    def process_paper(self, pdf_url: str) -> Dict[str, Any]:
        """
        完整處理單篇論文，從下載到生成所有檔案，並返回所有資訊。
        
        Args:
            pdf_url (str): 論文的 PDF URL。
            
        Returns:
            Dict[str, Any]: 包含所有生成資訊和檔案路徑的字典。
        """
        try:
            # 1. 下載 PDF
            pdf_data = self.read_pdf_from_url(pdf_url)
            
            # 2. 分析論文
            paper_info = self.extract_paper_info(pdf_data)
            
            # 3. 創建輸出資料夾
            output_folder = self.create_output_folder(paper_info.title)
            
            # 4. 生成逐字稿 (現在返回純文字)
            script_text = self.generate_podcast_script(paper_info)
            
            # 5. 生成音檔
            audio_path = self.generate_audio(script_text, output_folder)
            
            # 6. 保存論文資訊和逐字稿
            paper_info_path = output_folder / "論文資訊.json"
            self.save_json(paper_info.model_dump(), paper_info_path)
            
            script_path = output_folder / "播客逐字稿.txt"
            script_path.write_text(script_text, encoding='utf-8')
            print(f"📝 播客逐字稿已保存: {script_path}")
            
            print(f"\n✅ 播客生成完成！所有文件已保存到: {output_folder}")
            
            # 建立一個預設的 Podcast 標題
            podcast_title = f"學術新知解密：深入探討《{paper_info.title}》"

            return {
                "paper_info": paper_info,
                "podcast_title": podcast_title,
                "script": script_text,
                "output_folder": str(output_folder),
                "audio_path": str(audio_path),
                "paper_info_path": str(paper_info_path),
                "script_path": str(script_path),
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
        print(f"📁 輸出資料夾: {results['output_folder']}")
        print(f"🎵 音檔路徑: {results['audio_path']}")
        print(f"📄 論文資訊路徑: {results['paper_info_path']}")
        print(f"📝 逐字稿路徑: {results['script_path']}")
        
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")


if __name__ == "__main__":
    main() 