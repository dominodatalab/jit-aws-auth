"""
Unit tests for client/constants.py - Configuration and secrets management
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime
import json
import sys


# Sample test data
SAMPLE_JIT_CONFIG = {
    "jit_endpoint": "https://jit.example.com",
    "minimum_token_validity_required_in_seconds": "30",
    "prj_attribute_name": "fm_projects",
    "ping_secret": "arn:aws:secretsmanager:us-east-1:123456789:secret:ping-secret",
    "nuid_secret": "arn:aws:secretsmanager:us-east-1:123456789:secret:nuid-secret"
}

SAMPLE_PING_SECRET = {
    "client-id": "test-client-id",
    "client-secret": "test-client-secret",
    "auth-server-url": "https://auth.example.com/oauth/token"
}

SAMPLE_NUID_SECRET = {
    "username": "test-nuid-user",
    "password": "test-nuid-password"
}


def create_mock_sm_client():
    """Create a fresh mock secretsmanager client with proper side effects."""
    mock_sm_client = MagicMock()

    def get_secret_side_effect(SecretId=None, **kwargs):
        if 'ping' in SecretId:
            return {'SecretString': json.dumps(SAMPLE_PING_SECRET)}
        elif 'nuid' in SecretId:
            return {'SecretString': json.dumps(SAMPLE_NUID_SECRET)}
        return {'SecretString': json.dumps({})}

    mock_sm_client.get_secret_value.side_effect = get_secret_side_effect
    mock_sm_client.describe_secret.return_value = {
        'LastRotatedDate': datetime.now()
    }
    return mock_sm_client


@pytest.fixture
def mock_constants_module():
    """
    Create a mock constants module that can be imported without file system access.
    This fixture handles the module-level initialization that normally happens at import time.
    """
    mock_sm_client = create_mock_sm_client()

    # Remove cached modules to force reimport with mocks
    modules_to_remove = [k for k in list(sys.modules.keys())
                        if 'client.constants' in k or k == 'client.constants'
                        or 'jit.client.constants' in k]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Patch boto3 and file operations before importing constants
    with patch('boto3.client', return_value=mock_sm_client):
        with patch('builtins.open', mock_open(read_data=json.dumps(SAMPLE_JIT_CONFIG))):
            # Now import the module with mocks in place
            from client import constants

            yield {
                'module': constants,
                'mock_sm_client': mock_sm_client,
                'config': SAMPLE_JIT_CONFIG,
                'ping_secret': SAMPLE_PING_SECRET,
                'nuid_secret': SAMPLE_NUID_SECRET
            }


class TestModuleLevelConstants:
    """Tests for module-level constants loaded at import time"""

    def test_jit_config_loaded(self, mock_constants_module):
        """Test that jit_config is loaded from file"""
        constants = mock_constants_module['module']

        assert constants.jit_config == SAMPLE_JIT_CONFIG

    def test_access_token_expiry_time(self, mock_constants_module):
        """Test access_token_expiry_time is set from config"""
        constants = mock_constants_module['module']

        expected = float(SAMPLE_JIT_CONFIG['minimum_token_validity_required_in_seconds'])
        assert constants.access_token_expiry_time == expected

    def test_minimum_token_validity(self, mock_constants_module):
        """Test minimum_token_validity_required_in_seconds is set from config"""
        constants = mock_constants_module['module']

        expected = int(SAMPLE_JIT_CONFIG['minimum_token_validity_required_in_seconds'])
        assert constants.minimum_token_validity_required_in_seconds == expected

    def test_fm_projects_attribute(self, mock_constants_module):
        """Test fm_projects_attribute is set from config"""
        constants = mock_constants_module['module']

        assert constants.fm_projects_attribute == SAMPLE_JIT_CONFIG['prj_attribute_name']


class TestSecretConfig:
    """Tests for SecretConfig class"""

    def test_init_loads_secrets(self, mock_constants_module):
        """Test SecretConfig initialization loads secrets from Secrets Manager"""
        constants = mock_constants_module['module']

        config = constants.SecretConfig(SAMPLE_JIT_CONFIG)

        assert config.jit_endpoint == 'https://jit.example.com'
        assert config.ping_client_id == 'test-client-id'
        assert config.ping_client_secret == 'test-client-secret'
        assert config.ping_token_endpoint == 'https://auth.example.com/oauth/token'
        assert config.nuid_username == 'test-nuid-user'
        assert config.nuid_password == 'test-nuid-password'

    def test_init_tracks_secret_metadata(self, mock_constants_module):
        """Test SecretConfig tracks secret metadata for rotation checking"""
        constants = mock_constants_module['module']

        config = constants.SecretConfig(SAMPLE_JIT_CONFIG)

        assert len(config.secret_metadata) == 2
        assert any(s['type'] == 'ping' for s in config.secret_metadata)
        assert any(s['type'] == 'nuid' for s in config.secret_metadata)


class TestGetSecretLastRotated:
    """Tests for _get_secret_lastrotated method"""

    def test_returns_rotation_date(self, mock_constants_module):
        """Test returns LastRotatedDate when present"""
        constants = mock_constants_module['module']

        rotation_time = datetime(2024, 6, 15, 12, 0, 0)

        # Patch the module-level aws_sm_client directly
        with patch.object(constants, 'aws_sm_client') as mock_client:
            mock_client.describe_secret.return_value = {'LastRotatedDate': rotation_time}
            mock_client.get_secret_value.side_effect = lambda SecretId=None, **kw: (
                {'SecretString': json.dumps(SAMPLE_PING_SECRET)} if 'ping' in SecretId
                else {'SecretString': json.dumps(SAMPLE_NUID_SECRET)}
            )

            config = constants.SecretConfig(SAMPLE_JIT_CONFIG)
            result = config._get_secret_lastrotated('arn:test')

            assert result == rotation_time

    def test_returns_none_when_never_rotated(self, mock_constants_module):
        """Test returns None when secret has never been rotated"""
        constants = mock_constants_module['module']

        with patch.object(constants, 'aws_sm_client') as mock_client:
            mock_client.describe_secret.return_value = {}  # No LastRotatedDate
            mock_client.get_secret_value.side_effect = lambda SecretId=None, **kw: (
                {'SecretString': json.dumps(SAMPLE_PING_SECRET)} if 'ping' in SecretId
                else {'SecretString': json.dumps(SAMPLE_NUID_SECRET)}
            )

            config = constants.SecretConfig(SAMPLE_JIT_CONFIG)
            result = config._get_secret_lastrotated('arn:test')

            assert result is None

    def test_handles_client_error(self, mock_constants_module):
        """Test handles boto3 ClientError gracefully"""
        import botocore.exceptions

        constants = mock_constants_module['module']

        with patch.object(constants, 'aws_sm_client') as mock_client:
            mock_client.get_secret_value.side_effect = lambda SecretId=None, **kw: (
                {'SecretString': json.dumps(SAMPLE_PING_SECRET)} if 'ping' in SecretId
                else {'SecretString': json.dumps(SAMPLE_NUID_SECRET)}
            )
            mock_client.describe_secret.return_value = {'LastRotatedDate': datetime.now()}

            config = constants.SecretConfig(SAMPLE_JIT_CONFIG)

            # Now make describe_secret fail for subsequent calls
            mock_client.describe_secret.side_effect = botocore.exceptions.ClientError(
                {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Secret not found'}},
                'DescribeSecret'
            )

            result = config._get_secret_lastrotated('arn:nonexistent')

            assert result is None


class TestGetSecret:
    """Tests for get_secret method"""

    def test_returns_parsed_secret(self, mock_constants_module):
        """Test returns parsed JSON secret value"""
        constants = mock_constants_module['module']

        with patch.object(constants, 'aws_sm_client') as mock_client:
            mock_client.describe_secret.return_value = {'LastRotatedDate': datetime.now()}
            mock_client.get_secret_value.side_effect = lambda SecretId=None, **kw: (
                {'SecretString': json.dumps(SAMPLE_PING_SECRET)} if 'ping' in SecretId
                else {'SecretString': json.dumps(SAMPLE_NUID_SECRET)}
            )

            config = constants.SecretConfig(SAMPLE_JIT_CONFIG)

            # Now test get_secret directly with a specific return
            test_secret = {'test': 'data'}
            mock_client.get_secret_value.side_effect = None
            mock_client.get_secret_value.return_value = {
                'SecretString': json.dumps(test_secret)
            }

            result = config.get_secret('arn:test')

            assert result == test_secret

    def test_handles_client_error(self, mock_constants_module):
        """Test handles boto3 ClientError gracefully"""
        import botocore.exceptions

        constants = mock_constants_module['module']

        with patch.object(constants, 'aws_sm_client') as mock_client:
            mock_client.describe_secret.return_value = {'LastRotatedDate': datetime.now()}
            mock_client.get_secret_value.side_effect = lambda SecretId=None, **kw: (
                {'SecretString': json.dumps(SAMPLE_PING_SECRET)} if 'ping' in SecretId
                else {'SecretString': json.dumps(SAMPLE_NUID_SECRET)}
            )

            config = constants.SecretConfig(SAMPLE_JIT_CONFIG)

            # Now make get_secret_value fail
            mock_client.get_secret_value.side_effect = botocore.exceptions.ClientError(
                {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
                'GetSecretValue'
            )

            result = config.get_secret('arn:forbidden')

            assert result is None


class TestRefreshSecretData:
    """Tests for refresh_secret_data method"""

    def test_refreshes_ping_secret(self, mock_constants_module):
        """Test refreshes ping secret credentials"""
        constants = mock_constants_module['module']

        with patch.object(constants, 'aws_sm_client') as mock_client:
            # Set up for init with old secrets
            old_ping = {'client-id': 'old-client', 'client-secret': 'old-secret', 'auth-server-url': 'old-url'}
            mock_client.describe_secret.return_value = {'LastRotatedDate': datetime.now()}
            mock_client.get_secret_value.side_effect = lambda SecretId=None, **kw: (
                {'SecretString': json.dumps(old_ping)} if 'ping' in SecretId
                else {'SecretString': json.dumps(SAMPLE_NUID_SECRET)}
            )

            config = constants.SecretConfig(SAMPLE_JIT_CONFIG)
            assert config.ping_client_id == 'old-client'

            # Now refresh with new secret
            new_ping = {'client-id': 'new-client', 'client-secret': 'new-secret', 'auth-server-url': 'new-url'}
            mock_client.get_secret_value.side_effect = None
            mock_client.get_secret_value.return_value = {'SecretString': json.dumps(new_ping)}

            config.refresh_secret_data({'type': 'ping', 'arn': 'arn:ping'})

            assert config.ping_client_id == 'new-client'
            assert config.ping_client_secret == 'new-secret'
            assert config.ping_token_endpoint == 'new-url'

    def test_refreshes_nuid_secret(self, mock_constants_module):
        """Test refreshes nuid secret credentials"""
        constants = mock_constants_module['module']

        with patch.object(constants, 'aws_sm_client') as mock_client:
            # Set up for init with old secrets
            old_nuid = {'username': 'old-user', 'password': 'old-pass'}
            mock_client.describe_secret.return_value = {'LastRotatedDate': datetime.now()}
            mock_client.get_secret_value.side_effect = lambda SecretId=None, **kw: (
                {'SecretString': json.dumps(SAMPLE_PING_SECRET)} if 'ping' in SecretId
                else {'SecretString': json.dumps(old_nuid)}
            )

            config = constants.SecretConfig(SAMPLE_JIT_CONFIG)
            assert config.nuid_username == 'old-user'

            # Now refresh with new secret
            new_nuid = {'username': 'new-user', 'password': 'new-pass'}
            mock_client.get_secret_value.side_effect = None
            mock_client.get_secret_value.return_value = {'SecretString': json.dumps(new_nuid)}

            config.refresh_secret_data({'type': 'nuid', 'arn': 'arn:nuid'})

            assert config.nuid_username == 'new-user'
            assert config.nuid_password == 'new-pass'


class TestCheckSecretRotation:
    """Tests for check_secret_rotation method"""

    def test_detects_rotation_and_refreshes(self, mock_constants_module):
        """Test detects when secret has been rotated and refreshes"""
        constants = mock_constants_module['module']

        old_rotation_time = datetime(2024, 1, 1, 0, 0, 0)
        new_rotation_time = datetime(2024, 1, 2, 0, 0, 0)

        with patch.object(constants, 'aws_sm_client') as mock_client:
            mock_client.describe_secret.return_value = {'LastRotatedDate': old_rotation_time}
            mock_client.get_secret_value.side_effect = lambda SecretId=None, **kw: (
                {'SecretString': json.dumps(SAMPLE_PING_SECRET)} if 'ping' in SecretId
                else {'SecretString': json.dumps(SAMPLE_NUID_SECRET)}
            )

            config = constants.SecretConfig(SAMPLE_JIT_CONFIG)

            # Now simulate rotation
            mock_client.describe_secret.return_value = {'LastRotatedDate': new_rotation_time}
            new_ping = {'client-id': 'rotated-client', 'client-secret': 'rotated-secret', 'auth-server-url': 'rotated-url'}
            mock_client.get_secret_value.side_effect = None
            mock_client.get_secret_value.return_value = {'SecretString': json.dumps(new_ping)}

            config.check_secret_rotation()

            # Should have refreshed at least ping secret
            assert config.ping_client_id == 'rotated-client'

    def test_no_refresh_when_not_rotated(self, mock_constants_module):
        """Test does not refresh when secrets have not been rotated"""
        constants = mock_constants_module['module']

        rotation_time = datetime(2024, 1, 1, 0, 0, 0)

        with patch.object(constants, 'aws_sm_client') as mock_client:
            mock_client.describe_secret.return_value = {'LastRotatedDate': rotation_time}
            mock_client.get_secret_value.side_effect = lambda SecretId=None, **kw: (
                {'SecretString': json.dumps(SAMPLE_PING_SECRET)} if 'ping' in SecretId
                else {'SecretString': json.dumps(SAMPLE_NUID_SECRET)}
            )

            config = constants.SecretConfig(SAMPLE_JIT_CONFIG)
            original_client_id = config.ping_client_id

            # Same rotation time - should not refresh
            config.check_secret_rotation()

            assert config.ping_client_id == original_client_id


class TestToDebug:
    """Tests for to_debug function"""

    def test_returns_config(self, mock_constants_module):
        """Test to_debug returns the jit_config"""
        constants = mock_constants_module['module']

        result = constants.to_debug()

        assert result == SAMPLE_JIT_CONFIG
