# -*- coding: utf-8 -*-
import logging
import sys

def setup_logging():
    """
    設定全域日誌記錄器。
    - 輸出格式包含時間、日誌級別、模組名稱和訊息。
    - 確保在不同環境（如 GitHub Actions）中能正確顯示。
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(module)s] - %(message)s",
        stream=sys.stdout,  # 確保日誌輸出到標準輸出
        force=True # 在某些環境中，需要強制覆蓋現有設定
    )

    # 取得根記錄器並確保其處理器設定正確
    logger = logging.getLogger()
    
    # 清除現有的任何處理器，以避免日誌重複輸出
    if logger.hasHandlers():
        logger.handlers.clear()

    # 重新加入我們設定的處理器
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logging.info("日誌系統已成功設定。") 