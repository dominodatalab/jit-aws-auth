"""
Unit tests for jit_server.py - Flask application serving JIT credential endpoints
"""

import pytest
import json
import sys
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime


# Sample test data for module initialization
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
    """Create a fresh mock secretsmanager client."""
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
def mock_jit_server_module():
    """
    Create a mock environment for testing jit_server.py.
    This handles all module-level initialization before importing the module.
    """
    mock_sm_client = create_mock_sm_client()

    # Remove cached modules to force reimport with mocks
    modules_to_remove = [k for k in list(sys.modules.keys())
                        if 'jit_server' in k or 'client' in k or 'constants' in k
                        or k.startswith('jit.')]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Patch boto3 and file operations before importing
    with patch('boto3.client', return_value=mock_sm_client):
        with patch('builtins.open', mock_open(read_data=json.dumps(SAMPLE_JIT_CONFIG))):
            # Import after patching
            import jit_server

            # Create the app and client via create_app
            jit_server.create_app()

            yield {
                'module': jit_server,
                'app': jit_server.app,
                'mock_sm_client': mock_sm_client,
            }


class TestVerifyUser:
    """Tests for verify_user function"""

    def test_verify_user_valid_jwt(self, mock_jit_server_module):
        """Test verify_user returns True for valid non-anonymous user"""
        jit_server = mock_jit_server_module['module']

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"isAnonymous": False}

        with patch('requests.get', return_value=mock_response) as mock_get:
            result = jit_server.verify_user("valid_jwt_token")

            assert result is True
            mock_get.assert_called_once()

    def test_verify_user_anonymous_user(self, mock_jit_server_module):
        """Test verify_user returns False for anonymous user"""
        jit_server = mock_jit_server_module['module']

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"isAnonymous": True}

        with patch('requests.get', return_value=mock_response):
            result = jit_server.verify_user("anonymous_jwt_token")

            assert result is False

    def test_verify_user_uses_correct_endpoint(self, mock_jit_server_module, monkeypatch):
        """Test verify_user calls the correct Nucleus endpoint"""
        jit_server = mock_jit_server_module['module']

        monkeypatch.setenv("DOMINO_USER_HOST", "http://test-nucleus:80")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"isAnonymous": False}

        with patch('requests.get', return_value=mock_response) as mock_get:
            jit_server.verify_user("test_token")

            call_args = mock_get.call_args
            assert "v4/auth/principal" in call_args[0][0]
            assert "Authorization" in call_args[1]["headers"]


class TestCreateNewSessions:
    """Tests for create_new_sessions function"""

    def test_create_new_sessions_filters_policy_manager(self, mock_jit_server_module):
        """Test that groups with POLICY-MANAGER are filtered out"""
        jit_server = mock_jit_server_module['module']

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"sessionId": "test-session"}

        # Patch the global client variable
        mock_client = MagicMock()
        mock_client.put_sessions.return_value = mock_response

        with patch.object(jit_server, 'client', mock_client):
            user_groups = [
                "sg-jit-prod-app-lifecycle-prj-project1",
                "sg-jit-prod-app-lifecycle-prj-POLICY-MANAGER-admin"
            ]

            result = jit_server.create_new_sessions("testuser", "test@example.com", user_groups)

            # Should only create session for project1, not POLICY-MANAGER
            assert mock_client.put_sessions.call_count == 1

    def test_create_new_sessions_parses_group_names(self, mock_jit_server_module):
        """Test that group names are correctly parsed into session data"""
        jit_server = mock_jit_server_module['module']

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"sessionId": "test-session"}

        mock_client = MagicMock()
        mock_client.put_sessions.return_value = mock_response

        with patch.object(jit_server, 'client', mock_client):
            # Group format: sg-jit-<lc_part1>-<lc_part2>-<appname>-...-prj-<project>
            # Split index: 0  1   2           3          4
            # So sg-jit-prod-dev-myapp-prj-myproject parses:
            #   applicationShortName = index[4] = myapp
            #   lifecycle = index[2] + index[3] = prod-dev
            #   projectName = last index = myproject
            user_groups = ["sg-jit-prod-dev-myapp-prj-myproject"]

            jit_server.create_new_sessions("testuser", "test@example.com", user_groups)

            call_args = mock_client.put_sessions.call_args[0][0]
            assert call_args['applicationShortName'] == 'myapp'
            assert call_args['projectName'] == 'myproject'
            assert call_args['userId'] == 'testuser'
            assert call_args['userEmail'] == 'test@example.com'
            assert call_args['eventType'] == 'createJitProjectSession'

    def test_create_new_sessions_handles_api_error(self, mock_jit_server_module):
        """Test graceful handling of upstream API errors"""
        jit_server = mock_jit_server_module['module']

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = MagicMock()
        mock_client.put_sessions.return_value = mock_response

        with patch.object(jit_server, 'client', mock_client):
            user_groups = ["sg-jit-prod-app-lifecycle-prj-project1"]

            result = jit_server.create_new_sessions("testuser", "test@example.com", user_groups)

            # Should return empty list on error, not crash
            assert result == []

    def test_create_new_sessions_handles_network_error(self, mock_jit_server_module):
        """Test graceful handling of network errors"""
        import requests.exceptions

        jit_server = mock_jit_server_module['module']

        mock_client = MagicMock()
        mock_client.put_sessions.side_effect = requests.exceptions.RequestException("Network error")

        with patch.object(jit_server, 'client', mock_client):
            user_groups = ["sg-jit-prod-app-lifecycle-prj-project1"]

            result = jit_server.create_new_sessions("testuser", "test@example.com", user_groups)

            # Should return empty list on network error
            assert result == []

    def test_create_new_sessions_handles_json_decode_error(self, mock_jit_server_module):
        """Test graceful handling of invalid JSON response"""
        from json.decoder import JSONDecodeError

        jit_server = mock_jit_server_module['module']

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)

        mock_client = MagicMock()
        mock_client.put_sessions.return_value = mock_response

        with patch.object(jit_server, 'client', mock_client):
            user_groups = ["sg-jit-prod-app-lifecycle-prj-project1"]

            result = jit_server.create_new_sessions("testuser", "test@example.com", user_groups)

            # Should handle JSONDecodeError gracefully
            assert result == []

    def test_create_new_sessions_empty_group_list(self, mock_jit_server_module):
        """Test handling of empty group list"""
        jit_server = mock_jit_server_module['module']

        mock_client = MagicMock()

        with patch.object(jit_server, 'client', mock_client):
            result = jit_server.create_new_sessions("testuser", "test@example.com", [])

            assert result == []
            mock_client.put_sessions.assert_not_called()


class TestFlaskRoutes:
    """Tests for Flask route handlers"""

    @pytest.fixture
    def flask_client(self, mock_jit_server_module):
        """Create Flask test client"""
        app = mock_jit_server_module['app']
        app.config['TESTING'] = True
        return app.test_client()

    def test_healthz_endpoint(self, mock_jit_server_module, flask_client):
        """Test /healthz endpoint returns 200"""
        jit_server = mock_jit_server_module['module']

        mock_client = MagicMock()
        with patch.object(jit_server, 'client', mock_client):
            response = flask_client.get('/healthz')

            assert response.status_code == 200
            mock_client.refresh_secrets_data.assert_called_once()

    def test_jit_sessions_endpoint_valid_user(self, mock_jit_server_module, flask_client):
        """Test /jit-sessions endpoint for valid user"""
        jit_server = mock_jit_server_module['module']

        mock_client = MagicMock()

        with patch.object(jit_server, 'client', mock_client):
            with patch.object(jit_server, 'verify_user', return_value=True):
                with patch.object(jit_server, 'jwt') as mock_jwt:
                    mock_jwt.decode.return_value = {
                        "preferred_username": "testuser",
                        "email": "test@example.com",
                        "fm_projects": ["sg-jit-prod-app-lifecycle-prj-project1"]
                    }
                    with patch.object(jit_server, 'create_new_sessions', return_value=[{"sessionId": "test-session"}]):
                        response = flask_client.get(
                            '/jit-sessions',
                            headers={'Authorization': 'Bearer test_token'}
                        )

                        assert response.status_code == 200

    def test_jit_sessions_endpoint_invalid_user(self, mock_jit_server_module, flask_client):
        """Test /jit-sessions endpoint returns 401 for invalid user"""
        jit_server = mock_jit_server_module['module']

        mock_client = MagicMock()

        with patch.object(jit_server, 'client', mock_client):
            with patch.object(jit_server, 'verify_user', return_value=False):
                response = flask_client.get(
                    '/jit-sessions',
                    headers={'Authorization': 'Bearer invalid_token'}
                )

                assert response.status_code == 401

    def test_user_projects_endpoint(self, mock_jit_server_module, flask_client):
        """Test /user-projects endpoint returns user groups"""
        jit_server = mock_jit_server_module['module']

        mock_client = MagicMock()

        with patch.object(jit_server, 'client', mock_client):
            with patch.object(jit_server, 'verify_user', return_value=True):
                with patch.object(jit_server, 'jwt') as mock_jwt:
                    mock_jwt.decode.return_value = {
                        "fm_projects": ["group1", "group2"]
                    }
                    response = flask_client.get(
                        '/user-projects',
                        headers={'Authorization': 'Bearer test_token'}
                    )

                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert "group1" in data
                    assert "group2" in data

    def test_user_projects_no_groups(self, mock_jit_server_module, flask_client):
        """Test /user-projects endpoint when user has no groups"""
        jit_server = mock_jit_server_module['module']

        mock_client = MagicMock()

        with patch.object(jit_server, 'client', mock_client):
            with patch.object(jit_server, 'verify_user', return_value=True):
                with patch.object(jit_server, 'jwt') as mock_jwt:
                    mock_jwt.decode.return_value = {}  # No fm_projects key
                    response = flask_client.get(
                        '/user-projects',
                        headers={'Authorization': 'Bearer test_token'}
                    )

                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data == []

    def test_dummy_user_projects_testing_mode_disabled(self, mock_jit_server_module, flask_client, monkeypatch):
        """Test /dummy/user-projects returns 404 when TESTING_MODE is false"""
        # The dummy_mode variable is set at module import time
        # We need to directly patch it on the module
        jit_server = mock_jit_server_module['module']

        with patch.object(jit_server, 'dummy_mode', False):
            response = flask_client.get('/dummy/user-projects')

            assert response.status_code == 404

    def test_test_endpoint_debug_mode(self, mock_jit_server_module, flask_client, monkeypatch):
        """Test /test endpoint returns config in DEBUG mode"""
        # This test depends on LOG_LEVEL being DEBUG
        # The endpoint returns empty dict if not in DEBUG mode
        response = flask_client.get('/test')

        assert response.status_code == 200
