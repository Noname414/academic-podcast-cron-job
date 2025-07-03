# 學術論文 Podcast 自動生成器

本專案是一個自動化的內容生成系統，旨在每日從 arXiv 拉取最新的學術論文，並利用 AI 技術將其轉換為易於收聽的 Podcast 格式。系統會自動處理論文摘要、生成中文翻譯、撰寫 Podcast 腳本，並最終生成語音檔案，上傳至雲端儲存。

## ✨ 主要功能

- **自動化論文拉取**: 每日定時從 arXiv 的特定領域（預設為 `cs.AI`）獲取最新發表的論文。
- **AI 驅動的內容處理**:
  - 使用 Gemini Pro 2.5 進行論文標題和摘要的**中文翻譯**。
  - 提取論文的**核心創新點**、**研究方法**與**主要成果**。
  - 自動生成生動有趣的**雙人對話式 Podcast 腳本**。
- **語音生成**:
  - 調用 Gemini TTS 服務，將腳本轉換為自然的語音。
  - 支援多位預設的 Podcast 主持人角色。
- **雲端整合**:
  - 將處理後的論文資訊儲存於 **Supabase** 資料庫。
  - 將生成的音檔、腳本等檔案上傳至 **Supabase Storage**，方便管理與取用。
- **持續部署**:
  - 透過 **GitHub Actions** 實現每日自動執行，無需人工干預。

## 🛠️ 技術棧

- **後端**: Python 3.11
- **套件管理**: uv
- **AI 模型**:
  - Google Gemini 2.5 Pro (內容生成)
  - Google Gemini TTS (語音合成)
- **資料庫與儲存**: Supabase (PostgreSQL + Storage)
- **CI/CD**: GitHub Actions

## 🚀 快速開始

### 1. 複製專案

```bash
git clone https://github.com/your-username/academic-podcast-cron-job.git
cd academic-podcast-cron-job
```

### 2. 環境設定

本專案使用 `uv` 進行 Python 環境與套件管理。

首先，安裝 `uv`:

```bash
pip install uv
```

接著，同步依賴套件來建立虛擬環境：

```bash
uv sync
```

### 3. 設定環境變數

複製 `.env.example` (如果有的話) 或手動建立一個名為 `.env` 的檔案，並填入以下必要的金鑰：

```env
# Supabase 專案 URL
SUPABASE_URL="YOUR_SUPABASE_URL"

# Supabase 專案的 service_role 金鑰
SUPABASE_KEY="YOUR_SUPABASE_SERVICE_KEY"

# Google AI Studio 的 API 金鑰
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
```

### 4. 執行資料庫遷移

將 `migration.sql` 檔案中的 SQL 指令碼在您的 Supabase 專案的 **SQL Editor** 中執行，以建立所需的資料表和結構。

> **注意**: 請確保為 `service_role` 授予對 `papers` 資料表的 `INSERT`, `SELECT` 等權限，否則腳本將無法寫入資料。

## 📖 使用方法

### 手動執行

您可以透過以下指令手動觸發一次完整的工作流程：

```bash
python main.py
```

腳本會執行以下步驟：

1. 從 arXiv 搜尋最新的論文。
2. 檢查論文是否已存在於資料庫。
3. 若為新論文，則進行處理並生成 Podcast。
4. 將結果存入 Supabase。

### 自動化流程 (GitHub Actions)

本專案已設定好 GitHub Actions，會於每日 UTC 時間午夜 00:00 自動執行 `main.py` 腳本。

您也可以在專案的 **Actions** 頁面手動觸發 `每日論文播客生成` 工作流程。

> **重要**: 請務必在專案的 `Settings > Secrets and variables > Actions` 中設定 `SUPABASE_URL`, `SUPABASE_KEY`, 和 `GEMINI_API_KEY` 三個 Repository secrets，自動化流程才能順利執行。

## ⚙️ 專案設定

所有可調整的參數都集中在 `config.py` 檔案中，方便您進行客製化：

- **`GEMINI_MODELS`**: 可替換用於不同任務的 Gemini 模型版本。
- **`PODCAST_SPEAKERS`**: 可新增或修改 Podcast 主持人的名稱與語音。
- **`ARXIV_SEARCH_CONFIG`**: 可調整 `max_results` (每次拉取的論文數) 和 `query` (搜尋的領域)。
- **`FILE_CONFIG`**: 設定輸出檔案的本地資料夾。
- **`SUPABASE_CONFIG`**: 設定 Supabase Storage 的 Bucket 名稱。
