# -*- coding: utf-8 -*-
import json
import arxiv
import datetime
from typing import List, Dict, Any

# 匯入設定
from config import ARXIV_SEARCH_CONFIG

def json_default(o: Any) -> Any:
    """自訂 JSON 序列化程式，用於處理預設無法序列化的物件。"""
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    if hasattr(o, '__dict__'):
        return o.__dict__
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

def search_latest_ai_paper(query: str, max_results: int) -> List[Dict[str, Any]]:
    """
    從 arXiv 搜尋最新的論文。

    Args:
        query (str): arXiv 搜尋查詢字串。
        max_results (int): 要獲取的最大結果數量。

    Returns:
        List[Dict[str, Any]]: 包含論文資訊的字典列表。
    """
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    results_list = []
    for result in client.results(search):
        paper_info = {
            "arxiv_id": result.get_short_id(),
            "updated": result.updated,
            "title": result.title,
            "authors": [author.name for author in result.authors],
            "primary_category": result.primary_category,
            "arxiv_url": result.entry_id,
            "pdf_url": result.pdf_url,
            "summary": result.summary
        }
        results_list.append(paper_info)
    
    return results_list

def save_results_to_json(results: List[Dict[str, Any]], filename: str = "arxiv_search.json"):
    """
    將搜尋結果儲存到 JSON 檔案中。

    Args:
        results (List[Dict[str, Any]]): 要儲存的搜尋結果。
        filename (str): 儲存結果的檔名。
    """
    with open(filename, "w", encoding='utf-8') as f:
        json.dump(results, f, default=json_default, indent=4, ensure_ascii=False)
    print(f"成功將 {len(results)} 筆結果儲存到 {filename}")

if __name__ == "__main__":
    print("正在搜尋最新的 AI 論文...")
    latest_papers = search_latest_ai_paper(
        query=ARXIV_SEARCH_CONFIG["query"],
        max_results=ARXIV_SEARCH_CONFIG["max_results"]
    )
    
    if latest_papers:
        save_results_to_json(latest_papers)
    else:
        print("找不到新的論文。")

    # print("📄 Title:", result.title)
    # print("👨‍🔬 Authors:", [author.name for author in result.authors])
    # print("📅 Published:", result.published)
    # print("🔗 URL:", result.entry_id)
    # print("📝 Summary:", result.summary[:200], "...\n")
