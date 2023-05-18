"""
Provides utilities for configuring or interacting with the `boto3` SDK
"""
import logging
import os


def configure_boto_logging() -> None:
    """
    Configures the logging level for `boto3` (and internal packages)
    based on the value assigned to the `BOTO_LOG_LEVEL` environment
    variable
    """
    boto_level = getattr(logging, os.environ.get('BOTO_LOG_LEVEL',
                                                 'INFO'))
    logging.getLogger('boto3').setLevel(boto_level)
    logging.getLogger('botocore').setLevel(boto_level)
    logging.getLogger('s3transfer').setLevel(boto_level)
    logging.getLogger('urllib3').setLevel(boto_level)
