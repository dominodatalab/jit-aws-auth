"""
Unit tests for client/resources/sessions.py - JIT Sessions API mixin
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
import requests.exceptions
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


@pytest.fixture
def mock_sessions_module():
    """
    Create a mock environment for testing the SessionsClientMixin.
    This handles all module-level initialization.
    """
    from datetime import datetime

    # Create mock boto3 client
    mock_sm_client = MagicMock()
    mock_sm_client.get_secret_value.side_effect = [
        {'SecretString': json.dumps(SAMPLE_PING_SECRET)},
        {'SecretString': json.dumps(SAMPLE_NUID_SECRET)}
    ]
    mock_sm_client.describe_secret.return_value = {
        'LastRotatedDate': datetime.now()
    }

    # Remove cached modules to force reimport with mocks
    modules_to_remove = [k for k in list(sys.modules.keys())
                        if 'client' in k and ('constants' in k or 'sessions' in k or 'resources' in k)]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Patch boto3 and file operations before importing
    with patch('boto3.client', return_value=mock_sm_client):
        with patch('builtins.open', mock_open(read_data=json.dumps(SAMPLE_JIT_CONFIG))):
            # Import after patching
            from client.resources.sessions import SessionsClientMixin

            yield {
                'SessionsClientMixin': SessionsClientMixin,
                'mock_sm_client': mock_sm_client,
            }


class TestSessionsClientMixin:
    """Tests for SessionsClientMixin methods"""

    def test_get_jit_sessions_by_sub(self, mock_sessions_module):
        """Test get_jit_sessions_by_sub makes correct API call"""
        SessionsClientMixin = mock_sessions_module['SessionsClientMixin']

        # Create a mock client with the mixin
        class MockClient(SessionsClientMixin):
            def __init__(self):
                self.get = MagicMock()
                self.post = MagicMock()

        mock_client = MockClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"sessions": []}
        mock_client.get.return_value = mock_response

        result = mock_client.get_jit_sessions_by_sub('user123', 'project1')

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        # Check that params include user and project
        assert call_args[1]['params']['sub'] == 'user123'
        assert call_args[1]['params']['project'] == 'project1'

    def test_get_access_contracts(self, mock_sessions_module):
        """Test get_access_contracts makes correct API call"""
        SessionsClientMixin = mock_sessions_module['SessionsClientMixin']

        class MockClient(SessionsClientMixin):
            def __init__(self):
                self.get = MagicMock()
                self.post = MagicMock()

        mock_client = MockClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {'contracts': []}
        mock_client.get.return_value = mock_response

        result = mock_client.get_access_contracts('myapp', 'prod')

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[1]['params']['applicationShortName'] == 'myapp'
        assert call_args[1]['params']['lifecycle'] == 'prod'

    def test_put_sessions_success(self, mock_sessions_module):
        """Test put_sessions creates session successfully"""
        SessionsClientMixin = mock_sessions_module['SessionsClientMixin']

        class MockClient(SessionsClientMixin):
            def __init__(self):
                self.get = MagicMock()
                self.post = MagicMock()

        mock_client = MockClient()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'sessionId': 'new-session'}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        payload = {
            'eventType': 'createJitProjectSession',
            'applicationShortName': 'myapp',
            'lifecycle': 'prod',
            'projectName': 'myproject',
            'userId': 'testuser',
            'userEmail': 'test@example.com'
        }

        result = mock_client.put_sessions(payload)

        assert result.status_code == 200
        mock_client.post.assert_called_once()

    def test_put_sessions_with_retry_on_exception(self, mock_sessions_module):
        """Test put_sessions behavior on request exceptions"""
        SessionsClientMixin = mock_sessions_module['SessionsClientMixin']

        class MockClient(SessionsClientMixin):
            def __init__(self):
                self.get = MagicMock()
                self.post = MagicMock()

        mock_client = MockClient()

        # Simulate an exception on the first call
        mock_client.post.side_effect = requests.exceptions.RequestException("Server error")

        payload = {'eventType': 'createJitProjectSession'}

        # The backoff decorator will retry, but in unit tests we just verify the exception is raised
        with pytest.raises(requests.exceptions.RequestException):
            mock_client.put_sessions(payload)

    def test_get_aws_credentials(self, mock_sessions_module):
        """Test get_aws_credentials retrieves credentials"""
        SessionsClientMixin = mock_sessions_module['SessionsClientMixin']

        class MockClient(SessionsClientMixin):
            def __init__(self):
                self.get = MagicMock()
                self.post = MagicMock()

        mock_client = MockClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'accessKeyId': 'AKIA...',
            'secretAccessKey': 'secret...',
            'sessionToken': 'token...',
            'expiration': '2024-01-01 00:00:00+0000'
        }
        mock_client.get.return_value = mock_response

        result = mock_client.get_aws_credentials('session-123')

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert 'session-123' in call_args[0][0]
        assert 'accessKeyId' in result

    def test_get_session_by_id(self, mock_sessions_module):
        """Test get_session_by_id retrieves session details"""
        SessionsClientMixin = mock_sessions_module['SessionsClientMixin']

        class MockClient(SessionsClientMixin):
            def __init__(self):
                self.get = MagicMock()
                self.post = MagicMock()

        mock_client = MockClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'sessionId': 'session-123',
            'status': 'active',
            'projectName': 'myproject'
        }
        mock_client.get.return_value = mock_response

        result = mock_client.get_session_by_id('session-123')

        mock_client.get.assert_called_once()
        assert result['sessionId'] == 'session-123'


class TestSessionsClientMixinErrorHandling:
    """Tests for error handling in SessionsClientMixin"""

    def test_get_aws_credentials_handles_network_error(self, mock_sessions_module):
        """Test get_aws_credentials handles network errors"""
        SessionsClientMixin = mock_sessions_module['SessionsClientMixin']

        class MockClient(SessionsClientMixin):
            def __init__(self):
                self.get = MagicMock()
                self.post = MagicMock()

        mock_client = MockClient()
        mock_client.get.side_effect = requests.exceptions.ConnectionError("Network unreachable")

        with pytest.raises(requests.exceptions.ConnectionError):
            mock_client.get_aws_credentials('session-123')

    def test_get_session_by_id_handles_timeout(self, mock_sessions_module):
        """Test get_session_by_id handles timeout errors"""
        SessionsClientMixin = mock_sessions_module['SessionsClientMixin']

        class MockClient(SessionsClientMixin):
            def __init__(self):
                self.get = MagicMock()
                self.post = MagicMock()

        mock_client = MockClient()
        mock_client.get.side_effect = requests.exceptions.Timeout("Request timed out")

        with pytest.raises(requests.exceptions.Timeout):
            mock_client.get_session_by_id('session-123')

    def test_put_sessions_handles_json_error(self, mock_sessions_module):
        """Test put_sessions handles invalid JSON response"""
        SessionsClientMixin = mock_sessions_module['SessionsClientMixin']

        class MockClient(SessionsClientMixin):
            def __init__(self):
                self.get = MagicMock()
                self.post = MagicMock()

        mock_client = MockClient()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        payload = {'eventType': 'createJitProjectSession'}

        result = mock_client.put_sessions(payload)

        # The method returns the response, caller handles JSON parsing
        assert result.status_code == 200
        with pytest.raises(ValueError):
            result.json()
