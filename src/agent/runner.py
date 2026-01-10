"""Runner module for the Content Agent pipeline.

This module wires together all components and executes the workflow.

Requirements: 10.1
"""

import logging
import sys

from src.agent.workflow import run_pipeline
from src.config.settings import ConfigurationError, load_settings


# Exit codes
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_PIPELINE_ERROR = 2


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application.
    
    Args:
        verbose: If True, set log level to DEBUG. Otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def run(mock: bool = False, verbose: bool = False) -> int:
    """Run the content agent pipeline.
    
    Initializes settings, configures logging, and executes the workflow.
    
    Args:
        mock: If True, use mock data instead of live fetching.
              (Currently not implemented - reserved for future use)
        verbose: If True, enable verbose/debug logging.
        
    Returns:
        Exit code:
        - 0: Success
        - 1: Configuration error
        - 2: Pipeline execution error
    """
    _setup_logging(verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("Content Agent starting...")
    
    # Load and validate configuration
    try:
        settings = load_settings(validate=True)
        logger.info("Configuration loaded successfully")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        return EXIT_CONFIG_ERROR
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return EXIT_CONFIG_ERROR
    
    # Handle mock mode (reserved for future implementation)
    if mock:
        logger.info("Mock mode enabled - using mock data")
        # TODO: Implement mock data sources when needed
        # For now, mock mode runs the same pipeline but could be extended
        # to use mock fetchers that return sample data
    
    # Execute the pipeline
    try:
        result = run_pipeline(settings)
        
        if result.success:
            logger.info("Pipeline completed successfully")
            logger.info(f"CSV output: {result.csv_path}")
            logger.info(f"Articles selected: {result.metrics.selected_count}")
            
            if result.upload_result and result.upload_result.success:
                logger.info(f"Uploaded to Google Drive: {result.upload_result.file_id}")
            
            return EXIT_SUCCESS
        else:
            logger.warning("Pipeline completed with issues")
            if result.metrics.errors:
                for error in result.metrics.errors:
                    logger.error(f"  - {error}")
            return EXIT_PIPELINE_ERROR
            
    except Exception as e:
        logger.exception(f"Pipeline failed with unexpected error: {e}")
        return EXIT_PIPELINE_ERROR
