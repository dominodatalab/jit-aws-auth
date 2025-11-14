#!/usr/bin/env python
"""
Test S3 Access with JIT Credentials and Auto-Regeneration

This script validates that AWS credentials from the JIT proxy are working correctly
by listing the contents of an S3 bucket using a specified profile. It also tests
the JIT client's auto-regeneration capability by deleting the credentials file
and verifying it gets recreated.

Requirements:
    pip install boto3

Usage:
    python test_s3_access.py --profile my-project --bucket my-bucket-name

Environment Variables:
    AWS_CONFIG_FILE - Path to AWS config file (will be validated if set)
"""

import argparse
import os
import sys
import time
from typing import Optional, Tuple

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
except ImportError:
    print("Error: boto3 package not found. Install with: pip install boto3")
    sys.exit(1)


def get_credentials_file_path() -> Optional[str]:
    """
    Get the credentials file path from AWS_CONFIG_FILE environment variable.
    The credentials file is in the same directory as the config file.

    Returns:
        Path to credentials file if AWS_CONFIG_FILE is set, None otherwise
    """
    config_file = os.environ.get('AWS_CONFIG_FILE')
    if not config_file:
        return None

    # Get directory of config file
    config_dir = os.path.dirname(config_file)
    credentials_file = os.path.join(config_dir, 'credentials')

    return credentials_file


def check_aws_config_file() -> Optional[str]:
    """
    Check if AWS_CONFIG_FILE environment variable is set and valid

    Returns:
        Path to config file if valid, None otherwise
    """
    config_file = os.environ.get('AWS_CONFIG_FILE')

    if not config_file:
        print("WARNING: AWS_CONFIG_FILE environment variable is not set")
        return None

    print(f"AWS_CONFIG_FILE is set to: {config_file}")

    # Check if file exists
    if not os.path.exists(config_file):
        print(f"ERROR: AWS config file does not exist: {config_file}")
        return None

    print(f"AWS config file exists: {config_file}")

    # Check if file has content
    try:
        file_size = os.path.getsize(config_file)
        if file_size == 0:
            print(f"ERROR: AWS config file is empty: {config_file}")
            return None

        print(f"AWS config file has content: {file_size} bytes")

        # Optionally show first few lines
        with open(config_file, 'r') as f:
            lines = f.readlines()[:5]
            print(f"  First few lines of config file:")
            for line in lines:
                print(f"    {line.rstrip()}")

        return config_file

    except Exception as e:
        print(f"ERROR: Error reading AWS config file: {e}")
        return None


def check_credentials_file_exists() -> Tuple[bool, Optional[str]]:
    """
    Check if the credentials file exists and has content

    Returns:
        Tuple of (exists, file_path)
    """
    credentials_file = get_credentials_file_path()

    if not credentials_file:
        print("WARNING: Cannot determine credentials file path (AWS_CONFIG_FILE not set)")
        return (False, None)

    if not os.path.exists(credentials_file):
        print(f"ERROR: Credentials file does not exist: {credentials_file}")
        return (False, credentials_file)

    try:
        file_size = os.path.getsize(credentials_file)
        if file_size == 0:
            print(f"ERROR: Credentials file is empty: {credentials_file}")
            return (False, credentials_file)

        print(f"Credentials file exists with {file_size} bytes: {credentials_file}")
        return (True, credentials_file)

    except Exception as e:
        print(f"ERROR: Error checking credentials file: {e}")
        return (False, credentials_file)


def delete_credentials_file() -> bool:
    """
    Delete the credentials file to test JIT client auto-regeneration

    Returns:
        True if deletion successful, False otherwise
    """
    credentials_file = get_credentials_file_path()

    if not credentials_file:
        print("ERROR: Cannot determine credentials file path (AWS_CONFIG_FILE not set)")
        return False

    if not os.path.exists(credentials_file):
        print(f"WARNING: Credentials file does not exist: {credentials_file}")
        return False

    try:
        print(f"\n{'='*80}")
        print(f"Testing JIT Client Auto-Regeneration")
        print(f"{'='*80}\n")
        print(f"Deleting credentials file: {credentials_file}")

        os.remove(credentials_file)

        # Verify deletion
        if not os.path.exists(credentials_file):
            print(f"Credentials file successfully deleted")
            return True
        else:
            print(f"ERROR: Failed to delete credentials file")
            return False

    except PermissionError:
        print(f"ERROR: Permission denied: Cannot delete {credentials_file}")
        print(f"   You may need to run this script with appropriate permissions")
        return False
    except Exception as e:
        print(f"ERROR: Error deleting credentials file: {e}")
        return False


def list_s3_bucket(profile_name: str, bucket_name: str, max_keys: int = 10, test_name: str = "S3 Access") -> bool:
    """
    List contents of an S3 bucket using the specified profile

    Args:
        profile_name: AWS profile name to use
        bucket_name: S3 bucket name to list
        max_keys: Maximum number of objects to display
        test_name: Name of the test for display purposes

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"Testing {test_name}")
    print(f"Profile: {profile_name}")
    print(f"Bucket: {bucket_name}")
    print(f"{'='*80}\n")

    try:
        # Create a session with the specified profile
        print(f"Creating boto3 session with profile '{profile_name}'...")
        session = boto3.Session(profile_name=profile_name)

        # Create S3 client from the session
        s3_client = session.client('s3')

        # Get caller identity to verify credentials
        print(f"Session created successfully")
        print(f"\nVerifying AWS credentials...")

        sts_client = session.client('sts')
        identity = sts_client.get_caller_identity()

        print(f"Credentials verified:")
        print(f"  Account: {identity['Account']}")
        print(f"  User ARN: {identity['Arn']}")
        print(f"  User ID: {identity['UserId']}")

        # List bucket contents
        print(f"\nListing contents of bucket '{bucket_name}'...")

        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            MaxKeys=max_keys
        )

        if 'Contents' in response:
            objects = response['Contents']
            print(f"Successfully listed bucket contents")
            print(f"\nFound {len(objects)} objects (showing up to {max_keys}):")
            print(f"\n{'Key':<60} {'Size (bytes)':<15} {'Last Modified'}")
            print(f"{'-'*60} {'-'*15} {'-'*20}")

            for obj in objects:
                key = obj['Key']
                size = obj['Size']
                modified = obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')

                # Truncate long keys
                display_key = key if len(key) <= 60 else key[:57] + '...'
                print(f"{display_key:<60} {size:<15} {modified}")

            # Show if there are more objects
            if response.get('IsTruncated', False):
                # Get total count
                total_response = s3_client.list_objects_v2(Bucket=bucket_name)
                total_count = total_response.get('KeyCount', 0)
                print(f"\n... and {total_count - len(objects)} more objects")

            print(f"\n{'='*80}")
            print(f"{test_name} Test SUCCESSFUL")
            print(f"{'='*80}\n")
            return True
        else:
            print(f"Bucket is empty or has no objects")
            print(f"\n{'='*80}")
            print(f"{test_name} Test SUCCESSFUL (bucket is empty)")
            print(f"{'='*80}\n")
            return True

    except ProfileNotFound as e:
        print(f"\nERROR: AWS profile '{profile_name}' not found")
        print(f"   {str(e)}")
        print(f"\n   Available profiles can be found in your AWS config file")
        return False

    except NoCredentialsError as e:
        print(f"\nERROR: No credentials found for profile '{profile_name}'")
        print(f"   {str(e)}")
        print(f"\n   The JIT credentials may not have been generated yet")
        return False

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']

        if error_code == 'NoSuchBucket':
            print(f"\nERROR: Bucket '{bucket_name}' does not exist")
        elif error_code == 'AccessDenied':
            print(f"\nERROR: Access denied to bucket '{bucket_name}'")
            print(f"   Your JIT credentials may not have permission to access this bucket")
        elif error_code == 'InvalidAccessKeyId':
            print(f"\nERROR: Invalid access key (credentials may have expired)")
        elif error_code == 'ExpiredToken':
            print(f"\nERROR: Credentials have expired")
            print(f"   The JIT client should automatically refresh them")
        else:
            print(f"\nERROR: {error_code}")

        print(f"   {error_msg}")
        return False

    except Exception as e:
        print(f"\nERROR: Unexpected error: {type(e).__name__}")
        print(f"   {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Test S3 access and JIT client auto-regeneration with a specified AWS profile',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script performs the following tests:
  1. Validates AWS config file and credentials file
  2. Tests initial S3 access with current credentials
  3. Deletes the credentials file
  4. Waits for JIT client to auto-regenerate credentials (default: 60s)
  5. Tests S3 access with regenerated credentials

Examples:
  # Basic test with default 60 second wait
  python test_s3_access.py --profile my-project --bucket my-bucket

  # Custom wait time for regeneration
  python test_s3_access.py --profile my-project --bucket my-bucket --wait-time 120

  # Show more objects from bucket
  python test_s3_access.py --profile my-project --bucket my-bucket --max-keys 50

  # Use environment variable for profile
  export AWS_PROFILE=my-project
  python test_s3_access.py --bucket my-bucket

Environment Variables:
  AWS_CONFIG_FILE - Path to AWS config file (will be validated)
  AWS_PROFILE     - Default profile to use (can be overridden with --profile)
        """
    )

    parser.add_argument(
        '--profile', '-p',
        type=str,
        help='AWS profile name to use (can also use AWS_PROFILE env var)'
    )

    parser.add_argument(
        '--bucket', '-b',
        type=str,
        required=True,
        help='S3 bucket name to list'
    )

    parser.add_argument(
        '--max-keys',
        type=int,
        default=10,
        help='Maximum number of objects to display (default: 10)'
    )

    parser.add_argument(
        '--wait-time',
        type=int,
        default=60,
        help='Seconds to wait for credentials regeneration after deletion (default: 60)'
    )

    args = parser.parse_args()

    # Get profile name from args or environment
    profile_name = args.profile or os.environ.get('AWS_PROFILE')

    if not profile_name:
        print("Error: AWS profile must be specified via --profile or AWS_PROFILE environment variable")
        sys.exit(1)

    print(f"{'='*80}")
    print(f"JIT Credentials S3 Access Test")
    print(f"{'='*80}\n")

    # Check AWS_CONFIG_FILE
    config_file = check_aws_config_file()

    if not config_file:
        print("\nWARNING: AWS_CONFIG_FILE validation failed")
        print("   Proceeding anyway - boto3 will use default config locations\n")

    # Initial check of credentials file
    print(f"\n{'='*80}")
    print(f"Initial Credentials File Check")
    print(f"{'='*80}\n")
    creds_exists, creds_path = check_credentials_file_exists()

    # Test S3 access (initial test)
    success = list_s3_bucket(profile_name, args.bucket, args.max_keys, "Initial S3 Access")

    if not success:
        print("\nInitial S3 access test failed. Exiting.")
        sys.exit(1)

    # Test auto-regeneration
    if not creds_exists:
        print("\nWARNING: Cannot test regeneration - credentials file doesn't exist")
        sys.exit(1)

    # Delete credentials file
    if not delete_credentials_file():
        print("\nFailed to delete credentials file. Cannot test regeneration.")
        sys.exit(1)

    # Wait for regeneration
    print(f"\nWaiting {args.wait_time} seconds for JIT client to regenerate credentials...")
    for i in range(args.wait_time, 0, -10):
        print(f"  {i} seconds remaining...")
        time.sleep(10 if i >= 10 else i)

    print("\nChecking if credentials file was regenerated...")

    # Check if file was recreated
    regenerated, _ = check_credentials_file_exists()

    if not regenerated:
        print(f"\n{'='*80}")
        print(f"REGENERATION TEST FAILED")
        print(f"{'='*80}")
        print(f"\nCredentials file was NOT regenerated after {args.wait_time} seconds")
        print(f"The JIT client may not be running or may have encountered an error")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"REGENERATION TEST SUCCESSFUL")
    print(f"{'='*80}")
    print(f"\nCredentials file was successfully regenerated")

    # Re-test S3 access with regenerated credentials
    print(f"\nTesting S3 access with regenerated credentials...")
    success_regen = list_s3_bucket(profile_name, args.bucket, args.max_keys, "Post-Regeneration S3 Access")

    if not success_regen:
        print("\nPost-regeneration S3 access test failed")
        print("Credentials were regenerated but are not working")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"ALL TESTS PASSED")
    print(f"{'='*80}")
    print(f"\n1. Initial S3 access: PASSED")
    print(f"2. Credentials regeneration: PASSED")
    print(f"3. Post-regeneration S3 access: PASSED")
    print(f"\nJIT client auto-regeneration is working correctly!")
    sys.exit(0)


if __name__ == '__main__':
    main()
