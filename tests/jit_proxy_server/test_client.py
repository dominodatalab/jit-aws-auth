"""
Unit tests for client/client.py - JIT Access Engine HTTP client
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime, timedelta
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
def mock_client_module():
    """
    Create a mock environment for testing the JitAccessEngineClient.
    This handles all module-level initialization.
    """
    mock_sm_client = create_mock_sm_client()

    # Remove cached modules to force reimport with mocks
    modules_to_remove = [k for k in list(sys.modules.keys())
                        if 'client.client' in k or 'client.constants' in k
                        or 'jit.client' in k]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Patch boto3 and file operations before importing
    with patch('boto3.client', return_value=mock_sm_client):
        with patch('builtins.open', mock_open(read_data=json.dumps(SAMPLE_JIT_CONFIG))):
            # Import after patching
            from client.client import JitAccessEngineClient

            yield {
                'JitAccessEngineClient': JitAccessEngineClient,
                'mock_sm_client': mock_sm_client,
                'config': SAMPLE_JIT_CONFIG,
                'ping_secret': SAMPLE_PING_SECRET,
                'nuid_secret': SAMPLE_NUID_SECRET
            }


class TestJitAccessEngineClientInit:
    """Tests for JitAccessEngineClient initialization"""

    def test_init_loads_config(self, mock_client_module):
        """Test client initialization loads configuration"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()

        assert client._jit_endpoint == "https://jit.example.com"
        assert client._token_endpoint == "https://auth.example.com/oauth/token"
        assert client._client_id == "test-client-id"

    def test_init_creates_auth_header(self, mock_client_module):
        """Test client creates proper Basic auth header"""
        from base64 import b64encode

        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()

        expected_encoded = b64encode(b'test-client-id:test-client-secret').decode('utf-8')
        assert client._auth_header['Authorization'] == f'Basic {expected_encoded}'


class TestGetAccessToken:
    """Tests for get_access_token method"""

    def test_returns_cached_token_if_valid(self, mock_client_module):
        """Test returns cached token if not expired"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()
        client._access_token = "cached_token"
        client.access_token_expiry_time = datetime.now() + timedelta(hours=1)

        result = client.get_access_token()

        assert result == "cached_token"

    def test_refreshes_with_refresh_token(self, mock_client_module):
        """Test uses refresh token when access token expired"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()
        client._access_token = "expired_token"
        client.access_token_expiry_time = datetime.now() - timedelta(hours=1)
        client._refresh_token = "valid_refresh_token"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 3600
        }

        with patch('requests.post', return_value=mock_response) as mock_post:
            result = client.get_access_token()

            assert result == "new_token"
            # Verify refresh token grant was used
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs['params']['grant_type'] == 'refresh_token'

    def test_falls_back_to_password_grant(self, mock_client_module):
        """Test falls back to password grant when refresh token fails"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()
        client._access_token = None
        client.access_token_expiry_time = None
        client._refresh_token = "expired_refresh"

        # First call (refresh) fails, second call (password) succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.json.side_effect = KeyError("access_token")

        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {
            "access_token": "password_grant_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600
        }

        with patch('requests.post', side_effect=[mock_response_fail, mock_response_success]):
            result = client.get_access_token()

            assert result == "password_grant_token"
            assert client._refresh_token == "new_refresh_token"

    def test_raises_on_all_auth_failures(self, mock_client_module):
        """Test raises InternalServerError when all auth methods fail"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        # Import exception - need to use jit.exceptions since that's what the code raises
        from jit.exceptions import InternalServerError

        client = JitAccessEngineClient()
        client._access_token = None
        client.access_token_expiry_time = None
        client._refresh_token = None

        mock_response = MagicMock()
        mock_response.json.side_effect = KeyError("access_token")

        with patch('requests.post', return_value=mock_response):
            with pytest.raises(InternalServerError):
                client.get_access_token()


class TestRequest:
    """Tests for request method override"""

    def test_prepends_base_url_to_relative_path(self, mock_client_module):
        """Test relative URLs get base endpoint prepended"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()
        client._access_token = "test_token"
        client.access_token_expiry_time = datetime.now() + timedelta(hours=1)

        with patch.object(client, 'get_access_token', return_value='test_token'):
            with patch('requests.Session.request') as mock_request:
                mock_request.return_value = MagicMock()

                client.request('GET', '/api/sessions')

                call_args = mock_request.call_args
                assert 'https://jit.example.com' in call_args[0][1]

    def test_preserves_absolute_urls(self, mock_client_module):
        """Test absolute URLs are not modified"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()
        client._access_token = "test_token"
        client.access_token_expiry_time = datetime.now() + timedelta(hours=1)

        with patch.object(client, 'get_access_token', return_value='test_token'):
            with patch('requests.Session.request') as mock_request:
                mock_request.return_value = MagicMock()

                client.request('GET', 'https://other.example.com/api')

                call_args = mock_request.call_args
                assert call_args[0][1] == 'https://other.example.com/api'

    def test_adds_auth_header(self, mock_client_module):
        """Test adds X-fnma-jws-token header"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()

        with patch.object(client, 'get_access_token', return_value='my_access_token'):
            with patch('requests.Session.request') as mock_request:
                mock_request.return_value = MagicMock()

                client.request('GET', '/api/test')

                call_kwargs = mock_request.call_args[1]
                assert call_kwargs['headers']['X-fnma-jws-token'] == 'my_access_token'


class TestRefreshSecretsData:
    """Tests for refresh_secrets_data method"""

    def test_calls_check_secret_rotation(self, mock_client_module):
        """Test refresh_secrets_data triggers rotation check"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()

        # Mock the config's check_secret_rotation method
        client.cfg.check_secret_rotation = MagicMock()

        client.refresh_secrets_data()

        client.cfg.check_secret_rotation.assert_called_once()

    def test_updates_credentials_after_rotation(self, mock_client_module):
        """Test credentials are updated after secret rotation"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()

        # Simulate rotation updating the config
        client.cfg.ping_client_id = "new_client"
        client.cfg.nuid_username = "new_user"
        client.cfg.check_secret_rotation = MagicMock()

        client.refresh_secrets_data()

        assert client._client_id == "new_client"
        assert client._r_username == "new_user"


class TestRefreshJitAccessToken:
    """Tests for refresh_jit_access_token method"""

    def test_refreshes_expired_token(self, mock_client_module):
        """Test token is refreshed when expired"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()
        client.access_token_expiry_time = datetime.now() - timedelta(hours=1)

        with patch.object(client, 'get_access_token') as mock_get_token:
            client.refresh_jit_access_token()

            mock_get_token.assert_called_once()

    def test_does_not_refresh_valid_token(self, mock_client_module):
        """Test token is not refreshed when still valid"""
        JitAccessEngineClient = mock_client_module['JitAccessEngineClient']

        client = JitAccessEngineClient()
        client.access_token_expiry_time = datetime.now() + timedelta(hours=1)

        with patch.object(client, 'get_access_token') as mock_get_token:
            client.refresh_jit_access_token()

            mock_get_token.assert_not_called()
