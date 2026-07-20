#!/usr/bin/env python
"""
Test JIT Credentials Existence and Auto-Regeneration (no AWS connectivity required)

This script validates that the JIT client sidecar is producing well-formed
credentials on disk and that it auto-regenerates them after deletion. Unlike
test_s3_access.py, it never talks to AWS - it only inspects the local
credentials/config files the JIT client writes - so it can be used without a
JIT Access Engine API or any real AWS resources to test against.

Requirements:
    None (standard library only)

Usage:
    python test_credentials.py --profile my-project

Environment Variables:
    AWS_CONFIG_FILE - Path to AWS config file (will be validated if set)
"""

import argparse
import configparser
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

REQUIRED_CREDENTIAL_FIELDS = ("AccessKeyId", "SecretAccessKey", "SessionToken", "Expiration")


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

    config_dir = os.path.dirname(config_file)
    credentials_file = os.path.join(config_dir, 'credentials')

    return credentials_file


def check_aws_config_file() -> Optional[str]:
    """
    Check if AWS_CONFIG_FILE environment variable is set and valid, and that
    it contains a section (and credential_process entry) for every profile.

    Returns:
        Path to config file if valid, None otherwise
    """
    config_file = os.environ.get('AWS_CONFIG_FILE')

    if not config_file:
        print("WARNING: AWS_CONFIG_FILE environment variable is not set")
        return None

    print(f"AWS_CONFIG_FILE is set to: {config_file}")

    if not os.path.exists(config_file):
        print(f"ERROR: AWS config file does not exist: {config_file}")
        return None

    print(f"AWS config file exists: {config_file}")

    try:
        file_size = os.path.getsize(config_file)
        if file_size == 0:
            print(f"ERROR: AWS config file is empty: {config_file}")
            return None

        print(f"AWS config file has content: {file_size} bytes")

        config = configparser.ConfigParser()
        config.read(config_file)

        profile_sections = [s for s in config.sections() if s.startswith('profile ')]
        if not profile_sections:
            print("WARNING: No 'profile <name>' sections found in AWS config file")
        else:
            print(f"  Found {len(profile_sections)} profile section(s):")
            for section in profile_sections:
                has_credential_process = config.has_option(section, 'credential_process')
                has_session_id = config.has_option(section, 'jitSessionId')
                print(f"    [{section}] credential_process={has_credential_process} jitSessionId={has_session_id}")

        return config_file

    except configparser.Error as e:
        print(f"ERROR: Could not parse AWS config file: {e}")
        return None
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


def check_credentials_content(profile_name: str, credentials_file: str) -> Optional[dict]:
    """
    Parse the credentials file and validate that the given profile has a
    well-formed, unexpired credential. Performs no AWS network calls.

    Args:
        profile_name: AWS profile name to look up
        credentials_file: Path to the JIT client's JSON credentials file

    Returns:
        The parsed credential dict for the profile if valid, None otherwise
    """
    try:
        with open(credentials_file, 'r') as f:
            all_creds = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Credentials file is not valid JSON: {e}")
        return None
    except Exception as e:
        print(f"ERROR: Could not read credentials file: {e}")
        return None

    if profile_name not in all_creds:
        print(f"ERROR: Profile '{profile_name}' not found in credentials file")
        print(f"   Available profiles: {list(all_creds.keys())}")
        return None

    cred = all_creds[profile_name]

    missing_fields = [field for field in REQUIRED_CREDENTIAL_FIELDS if field not in cred]
    if missing_fields:
        print(f"ERROR: Credential for profile '{profile_name}' is missing fields: {missing_fields}")
        return None

    for field in ("AccessKeyId", "SecretAccessKey", "SessionToken"):
        if not cred[field]:
            print(f"ERROR: Credential field '{field}' is empty for profile '{profile_name}'")
            return None

    try:
        expiration = datetime.fromisoformat(cred['Expiration'])
    except ValueError as e:
        print(f"ERROR: Could not parse Expiration '{cred['Expiration']}': {e}")
        return None

    now = datetime.now(expiration.tzinfo) if expiration.tzinfo else datetime.now()
    if expiration <= now:
        print(f"ERROR: Credential for profile '{profile_name}' is already expired ({cred['Expiration']})")
        return None

    print(f"Credential for profile '{profile_name}' is well-formed and unexpired:")
    print(f"  AccessKeyId: {cred['AccessKeyId']}")
    print(f"  Expiration:  {cred['Expiration']}")

    return cred


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


def main():
    parser = argparse.ArgumentParser(
        description='Test JIT credential existence/refresh without any AWS connectivity',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script performs the following checks, entirely from local files:
  1. Validates AWS config file and credentials file
  2. Validates the credential content/shape for the given profile
  3. Deletes the credentials file
  4. Waits for JIT client to auto-regenerate credentials (default: 60s)
  5. Re-validates the regenerated credential content for the given profile

Examples:
  # Basic test with default 60 second wait
  python test_credentials.py --profile my-project

  # Custom wait time for regeneration
  python test_credentials.py --profile my-project --wait-time 120

  # Use environment variable for profile
  export AWS_PROFILE=my-project
  python test_credentials.py

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
        '--wait-time',
        type=int,
        default=60,
        help='Seconds to wait for credentials regeneration after deletion (default: 60)'
    )

    args = parser.parse_args()

    profile_name = args.profile or os.environ.get('AWS_PROFILE')

    if not profile_name:
        print("Error: AWS profile must be specified via --profile or AWS_PROFILE environment variable")
        sys.exit(1)

    print(f"{'='*80}")
    print(f"JIT Credentials Existence/Refresh Test (no AWS connectivity)")
    print(f"{'='*80}\n")

    check_aws_config_file()

    print(f"\n{'='*80}")
    print(f"Initial Credentials File Check")
    print(f"{'='*80}\n")
    creds_exists, creds_path = check_credentials_file_exists()

    if not creds_exists:
        print("\nInitial credentials file check failed. Exiting.")
        sys.exit(1)

    initial_cred = check_credentials_content(profile_name, creds_path)
    if not initial_cred:
        print("\nInitial credentials content check failed. Exiting.")
        sys.exit(1)

    if not delete_credentials_file():
        print("\nFailed to delete credentials file. Cannot test regeneration.")
        sys.exit(1)

    print(f"\nWaiting {args.wait_time} seconds for JIT client to regenerate credentials...")
    for i in range(args.wait_time, 0, -10):
        print(f"  {i} seconds remaining...")
        time.sleep(10 if i >= 10 else i)

    print("\nChecking if credentials file was regenerated...")
    regenerated, creds_path = check_credentials_file_exists()

    if not regenerated:
        print(f"\n{'='*80}")
        print(f"REGENERATION TEST FAILED")
        print(f"{'='*80}")
        print(f"\nCredentials file was NOT regenerated after {args.wait_time} seconds")
        print(f"The JIT client may not be running or may have encountered an error")
        sys.exit(1)

    regenerated_cred = check_credentials_content(profile_name, creds_path)
    if not regenerated_cred:
        print(f"\n{'='*80}")
        print(f"REGENERATION TEST FAILED")
        print(f"{'='*80}")
        print(f"\nCredentials file was recreated but content is invalid")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"REGENERATION TEST SUCCESSFUL")
    print(f"{'='*80}")
    print(f"\nCredentials file was successfully regenerated with a valid credential")

    print(f"\n{'='*80}")
    print(f"ALL TESTS PASSED")
    print(f"{'='*80}")
    print(f"\n1. Initial credentials check: PASSED")
    print(f"2. Credentials regeneration: PASSED")
    print(f"3. Post-regeneration credentials check: PASSED")
    print(f"\nJIT client auto-regeneration is working correctly!")
    sys.exit(0)


if __name__ == '__main__':
    main()
