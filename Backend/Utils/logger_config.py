"""
Centralized logging configuration for AI Oncologist Backend
"""
import logging
import sys

def setup_logger(name, level=logging.INFO):
    """
    Setup a logger with consistent formatting

    Args:
        name: Logger name (usually __name__)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding multiple handlers if logger already exists
    if logger.handlers:
        return logger

    # Create console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        fmt='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    return logger

def log_extraction_start(logger, component_name, pdf_url=None):
    """Log the start of an extraction"""
    logger.info(f"{'='*70}")
    logger.info(f"▶ STARTING: {component_name}")
    if pdf_url:
        logger.info(f"   PDF URL: {pdf_url[:80]}...")
    logger.info(f"{'='*70}")

def log_extraction_complete(logger, component_name, data_keys=None):
    """Log the completion of an extraction"""
    logger.info(f"{'='*70}")
    logger.info(f"✓ COMPLETED: {component_name}")
    if data_keys:
        logger.info(f"   Extracted fields: {', '.join(data_keys)}")
    logger.info(f"{'='*70}\n")

def log_extraction_output(logger, component_name, output_data, max_preview_length=500):
    """Log a preview of extraction output"""
    import json
    logger.info(f"\n{'─'*70}")
    logger.info(f"📊 OUTPUT PREVIEW: {component_name}")
    logger.info(f"{'─'*70}")

    try:
        # Convert to JSON string with nice formatting
        json_str = json.dumps(output_data, indent=2)

        # Truncate if too long
        if len(json_str) > max_preview_length:
            json_str = json_str[:max_preview_length] + "\n... (truncated)"

        logger.info(json_str)
    except Exception as e:
        logger.warning(f"Could not serialize output: {e}")

    logger.info(f"{'─'*70}\n")
