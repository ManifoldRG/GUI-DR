"""
Logging setup utility for task-specific log files.
"""

import os
from typing import Optional
from loguru import logger


def setup_task_logging(task_dir: str, task_uid: str) -> str:
    """Set up loguru to write to both console and a task-specific log file.
    
    Args:
        task_dir: The task directory where logs.txt will be saved
        task_uid: Task UID for logging context
    
    Returns:
        Path to the log file
    """
    log_file = os.path.join(task_dir, "logs.txt")
    
    # Remove any existing handlers to avoid duplicates
    logger.remove()
    
    # Add console handler with colors and formatting
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        colorize=True,
        level="INFO"
    )
    
    # Add file handler (no colors in file)
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="INFO",
        rotation=None,  # Don't rotate, keep all logs in one file
        retention=None,  # Keep all logs
        mode="w"  # Overwrite if exists (fresh log per run)
    )
    
    logger.info(f"📝 Logging initialized for task {task_uid}")
    logger.info(f"📁 Log file: {log_file}")
    
    return log_file


def reset_logging():
    """Reset logging to default (console only). Useful when switching between tasks."""
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        colorize=True,
        level="INFO"
    )

