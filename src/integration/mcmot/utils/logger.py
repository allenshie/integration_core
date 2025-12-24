"""
統一的 Logger 管理模組
使用 loguru 提供簡潔的日誌記錄功能
"""
from loguru import logger
import sys
from pathlib import Path
from typing import Optional


class LoggerManager:
    """Logger 管理類別，提供統一的日誌配置和獲取介面"""
    
    _initialized = False
    _loggers = {}
    _file_handlers = {}  # 記錄每個日誌文件的 handler ID
    _base_config = {}  # 儲存基礎配置
    
    @classmethod
    def initialize(
        cls,
        log_dir: str = "logs",
        log_level: str = "DEBUG",
        rotation: str = "00:00",
        retention: str = "30 days",
        format: Optional[str] = None
    ):
        """
        初始化 logger 配置
        
        Args:
            log_dir: 日誌文件目錄
            log_level: 日誌等級 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            rotation: 日誌輪轉時間 (例如: "00:00" 每天午夜, "500 MB" 文件大小)
            retention: 日誌保留時間 (例如: "30 days", "1 week")
            format: 自定義日誌格式
        """
        if cls._initialized:
            return
        
        # 儲存基礎配置
        cls._base_config = {
            "log_dir": log_dir,
            "log_level": log_level,
            "rotation": rotation,
            "retention": retention,
            "format": format
        }

        # 移除預設的 handler
        logger.remove()
        # 設定預設 extra，避免尚未 bind 時缺少欄位
        logger.configure(extra={"module_name": "global", "log_file": "default"})

        # 添加控制台輸出（顯示完整模組路徑）
        logger.add(
            sys.stderr,
            level=log_level,
            format=format or "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[module_name]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True
        )
        
        # 創建日誌目錄
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        cls._initialized = True
        logger.info("Logger 初始化完成")
    
    @classmethod
    def _add_file_handler(cls, log_file: str):
        """
        為指定的日誌文件添加 handler
        
        Args:
            log_file: 日誌文件名稱（不含副檔名和日期）
        """
        if log_file in cls._file_handlers:
            return  # 已經添加過該文件的 handler
        
        config = cls._base_config
        log_path = Path(config["log_dir"])
        
        # 添加文件輸出
        handler_id = logger.add(
            log_path / f"{log_file}_{{time:YYYY-MM-DD}}.log",
            level=config["log_level"],
            rotation=config["rotation"],
            retention=config["retention"],
            format=config["format"] or "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[module_name]}:{function}:{line} - {message}",
            encoding="utf-8",
            filter=lambda record: record["extra"].get("log_file") == log_file
        )
        
        cls._file_handlers[log_file] = handler_id
    
    @classmethod
    def get_logger(cls, name: str, log_file: str = "default"):
        """
        獲取指定名稱的 logger
        
        Args:
            name: logger 名稱，建議使用 __name__ 以獲得完整模組路徑
            log_file: 日誌文件名稱（不含副檔名），相同 log_file 的日誌會輸出到同一個文件
            
        Returns:
            logger 實例
            
        Example:
            >>> # 兩個模組輸出到同一個文件
            >>> logger1 = LoggerManager.get_logger(__name__, log_file="services")
            >>> logger2 = LoggerManager.get_logger(__name__, log_file="services")
            >>> 
            >>> # 輸出到不同文件
            >>> logger3 = LoggerManager.get_logger(__name__, log_file="detection")
        """
        if not cls._initialized:
            cls.initialize()
        
        # 使用 name + log_file 作為唯一鍵
        logger_key = f"{name}:{log_file}"
        
        if logger_key not in cls._loggers:
            # 為該日誌文件添加 handler（如果尚未添加）
            cls._add_file_handler(log_file)
            
            # 創建綁定了模組資訊的 logger
            cls._loggers[logger_key] = logger.bind(
                module_name=name,
                log_file=log_file
            )
        
        return cls._loggers[logger_key]


def get_logger(name: str, log_file: str = "default"):
    """
    便捷函數：獲取 logger 實例
    
    Args:
        name: logger 名稱，建議使用 __name__
        log_file: 日誌文件名稱（不含副檔名），相同 log_file 的日誌會輸出到同一個文件
        
    Returns:
        logger 實例
        
    Example:
        >>> from integration.mcmot.utils.logger import get_logger
        >>> 
        >>> # 在 mcmot_coordinator.py 中
        >>> logger = get_logger(__name__, log_file="services")
        >>> logger.info("開始追蹤流程")
        >>> 
        >>> # 在其他模組中
        >>> logger = get_logger(__name__, log_file="services")
        >>> logger.info("處理任務")
        >>> 
        >>> # 兩者的日誌都會輸出到 services_2025-11-06.log
        >>> # 但可以通過模組名稱區分來源
    """
    return LoggerManager.get_logger(name, log_file)
