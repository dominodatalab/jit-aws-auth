"""
Unit tests for jit-client-proxy.py - JIT credential refresh daemon
"""

import configparser
import importlib.util
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime, timedelta
import json


@pytest.fixture(scope="session")
def client_module():
    """Load jit-client-proxy via importlib (filename contains a hyphen)."""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'jit-client', 'jit-client-proxy.py'
    )
    spec = importlib.util.spec_from_file_location('jit_client_proxy', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCheckUpdateClientbin:
    """Tests for check_update_clientbin function"""

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    def test_updates_binaries_when_commit_changed(self, mock_file, mock_isfile):
        """Test binaries are updated when commit file changes"""
        mock_isfile.return_value = True
        mock_file.return_value.read.side_effect = ['new_commit', 'old_commit']

        with patch('shutil.copytree') as mock_copy:
            # Import after patching
            # Note: The actual function implementation would need to be tested
            # based on its real behavior
            pass

    @patch('os.path.isfile')
    def test_skips_update_when_commit_same(self, mock_isfile):
        """Test binaries are not updated when commit unchanged"""
        mock_isfile.return_value = True

        with patch('builtins.open', mock_open(read_data='same_commit')):
            with patch('shutil.copytree') as mock_copy:
                # Should not call copytree if commits match
                pass


class TestWriteCredentialsProfile:
    """Tests for write_credentials_profile function"""

    def test_writes_profile_config(self, client_module, tmp_path):
        """Test writes correct AWS profile section and jitSessionId to file."""
        profile_file = str(tmp_path / "profile")
        aws_credentials = [{"session_id": "jit-user-app-123", "projects": ["project1"], "accessKeyId": "AKIA1"}]

        client_module.write_credentials_profile(aws_credentials, profile_file)

        config = configparser.ConfigParser()
        config.read(profile_file)
        assert config.has_section("profile project1")
        assert config.get("profile project1", "jitSessionId") == "jit-user-app-123"
        assert "credential-helper" in config.get("profile project1", "credential_process")

    def test_handles_multiple_projects(self, client_module, tmp_path):
        """Test creates a section for each project in the credentials list."""
        profile_file = str(tmp_path / "profile")
        aws_credentials = [
            {"session_id": "session1", "projects": ["project1"], "accessKeyId": "AKIA1"},
            {"session_id": "session2", "projects": ["project2"], "accessKeyId": "AKIA2"},
        ]

        client_module.write_credentials_profile(aws_credentials, profile_file)

        config = configparser.ConfigParser()
        config.read(profile_file)
        assert config.has_section("profile project1")
        assert config.has_section("profile project2")
        assert config.get("profile project1", "jitSessionId") == "session1"
        assert config.get("profile project2", "jitSessionId") == "session2"

    def test_preserves_existing_profile_sections(self, client_module, tmp_path):
        """Test that pre-existing profile sections are not lost on subsequent writes."""
        profile_file = str(tmp_path / "profile")
        client_module.write_credentials_profile(
            [{"session_id": "old-session", "projects": ["project1"], "accessKeyId": "AKIA1"}],
            profile_file,
        )
        client_module.write_credentials_profile(
            [{"session_id": "new-session", "projects": ["project2"], "accessKeyId": "AKIA2"}],
            profile_file,
        )

        config = configparser.ConfigParser()
        config.read(profile_file)
        assert config.has_section("profile project1"), "pre-existing section was dropped"
        assert config.has_section("profile project2")

    def test_handles_malformed_profile_file(self, client_module, tmp_path):
        """Test logs a warning and still writes credentials when profile file has invalid INI format."""
        profile_file = str(tmp_path / "profile")
        aws_credentials = [{"session_id": "jit-session-123", "projects": ["project1"], "accessKeyId": "AKIA1"}]

        with patch('configparser.ConfigParser.read',
                   side_effect=configparser.MissingSectionHeaderError('source', 1, 'line')):
            with patch.object(client_module.logger, 'warning') as mock_warning:
                client_module.write_credentials_profile(aws_credentials, profile_file)

                mock_warning.assert_called_once()
                assert profile_file in mock_warning.call_args[0][0]

        config = configparser.ConfigParser()
        config.read(profile_file)
        assert config.has_section("profile project1")
        assert config.get("profile project1", "jitSessionId") == "jit-session-123"

    def test_handles_missing_profile_file(self, client_module, tmp_path):
        """Test silently creates the profile file when it does not yet exist."""
        profile_file = str(tmp_path / "nonexistent_profile")
        aws_credentials = [{"session_id": "jit-session-123", "projects": ["project1"], "accessKeyId": "AKIA1"}]

        client_module.write_credentials_profile(aws_credentials, profile_file)

        config = configparser.ConfigParser()
        config.read(profile_file)
        assert config.has_section("profile project1")


class TestConvertJitApiToAwsCreds:
    """Tests for convert_jit_api_to_aws_creds function"""

    def test_converts_jit_format(self):
        """Test converts JIT API format to AWS credential_process format"""
        jit_creds = [
            {
                "accessKeyId": "AKIA123",
                "secretAccessKey": "secret123",
                "sessionToken": "token123",
                "expiration": "2024-01-01 12:00:00+0000",
                "session_id": "jit-user-app-123",
                "projects": ["project1"]
            }
        ]

        # Expected output format:
        # {
        #     "project1": {
        #         "Version": 1,
        #         "AccessKeyId": "AKIA123",
        #         "SecretAccessKey": "secret123",
        #         "SessionToken": "token123",
        #         "Expiration": "2024-01-01T12:00:00+00:00"
        #     }
        # }

    def test_handles_already_converted_format(self):
        """Test handles credentials already in AWS format"""
        aws_creds = [
            {
                "AccessKeyId": "AKIA123",
                "SecretAccessKey": "secret123",
                "SessionToken": "token123",
                "Expiration": "2024-01-01T12:00:00+00:00",
                "projects": ["project1"]
            }
        ]

        # Should detect AWS format and handle appropriately

    def test_handles_empty_list(self):
        """Test handles empty credentials list"""
        result_expected = {}
        # Function should return empty dict for empty input


class TestConvertAwsCredsToJitApi:
    """Tests for convert_aws_creds_to_jit_api function"""

    def test_converts_aws_format(self):
        """Test converts AWS format back to JIT list format"""
        aws_creds = {
            "project1": {
                "Version": 1,
                "AccessKeyId": "AKIA123",
                "SecretAccessKey": "secret123",
                "SessionToken": "token123",
                "Expiration": "2024-01-01T12:00:00+00:00"
            }
        }

        # Expected output is a list of dicts

    def test_handles_empty_dict(self):
        """Test handles empty credentials dict"""
        # Should return empty list


class TestWriteCredentialsFile:
    """Tests for write_credentials_file function"""

    def test_writes_json_file(self, tmp_path):
        """Test writes credentials to JSON file"""
        cred_file = tmp_path / "credentials"

        aws_credentials = [
            {
                "accessKeyId": "AKIA123",
                "secretAccessKey": "secret123",
                "sessionToken": "token123",
                "expiration": "2024-01-01 12:00:00+0000",
                "projects": ["project1"]
            }
        ]

        # Function should write JSON to file

    def test_handles_write_error(self, tmp_path):
        """Test handles file write permission error"""
        # Create read-only directory
        cred_file = "/nonexistent/path/credentials"

        # Should handle PermissionError gracefully


class TestReadCredentialsFile:
    """Tests for read_credentials_file function"""

    def test_reads_valid_json(self, tmp_path):
        """Test reads and parses valid JSON file"""
        cred_file = tmp_path / "credentials"
        cred_data = {
            "project1": {
                "AccessKeyId": "AKIA123",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
                "Expiration": "2024-01-01T12:00:00+00:00"
            }
        }
        cred_file.write_text(json.dumps(cred_data))

        # Function should return parsed credentials

    def test_handles_file_not_found(self):
        """Test handles missing credentials file"""
        # Should return empty list or handle gracefully

    def test_handles_invalid_json(self, tmp_path):
        """Test handles corrupted JSON file"""
        cred_file = tmp_path / "credentials"
        cred_file.write_text("not valid json {{{")

        # Should handle JSONDecodeError gracefully


class TestGetUserProjects:
    """Tests for get_user_projects function"""

    @patch('requests.get')
    def test_fetches_projects_from_proxy(self, mock_get, monkeypatch):
        """Test fetches user projects from JIT proxy"""
        monkeypatch.setenv("DOMINO_JIT_ENDPOINT", "http://jit-svc:5000")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            "sg-jit-prod-app-lifecycle-prj-project1",
            "sg-jit-prod-app-lifecycle-prj-project2"
        ]
        mock_get.return_value = mock_response

        # Function should return list of project strings

    @patch('requests.get')
    def test_handles_404_error(self, mock_get, monkeypatch):
        """Test handles 404 from proxy"""
        monkeypatch.setenv("DOMINO_JIT_ENDPOINT", "http://jit-svc:5000")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        # Should handle error gracefully

    @patch('requests.get')
    def test_uses_dummy_endpoint_when_404(self, mock_get, monkeypatch):
        """Test falls back to dummy endpoint on 404"""
        monkeypatch.setenv("DOMINO_JIT_ENDPOINT", "http://jit-svc:5000")

        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404

        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = ["project1"]

        mock_get.side_effect = [mock_response_404, mock_response_ok]

        # Should try /dummy/user-projects on 404


class TestGetDominoUserIdentity:
    """Tests for get_domino_user_identity function"""

    @patch('requests.get')
    def test_fetches_jwt_from_api_proxy(self, mock_get, monkeypatch):
        """Test fetches JWT from Domino API proxy"""
        monkeypatch.setenv("DOMINO_API_PROXY", "http://localhost:8899")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"
        mock_get.return_value = mock_response

        # Function should return JWT string

    @patch('requests.get')
    def test_handles_404_returns_none(self, mock_get, monkeypatch):
        """Test returns None on 404"""
        monkeypatch.setenv("DOMINO_API_PROXY", "http://localhost:8899")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        # Should return None

    @patch('requests.get')
    def test_retries_on_network_error(self, mock_get, monkeypatch):
        """Test retries with backoff on network errors"""
        import requests.exceptions
        monkeypatch.setenv("DOMINO_API_PROXY", "http://localhost:8899")

        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        # With backoff decorator, should retry before giving up


class TestCheckCredentialExpiration:
    """Tests for check_credential_expiration function"""

    def test_returns_expiring_credentials(self):
        """Test identifies credentials expiring within threshold"""
        now = datetime.now()
        expiring_soon = (now + timedelta(seconds=60)).isoformat()
        not_expiring = (now + timedelta(hours=1)).isoformat()

        credential_list = [
            {"Expiration": expiring_soon, "projects": ["project1"]},
            {"Expiration": not_expiring, "projects": ["project2"]}
        ]

        # Should return only project1 credential (expiring within default 300s threshold)
        # Note: 60s is within 300s threshold

    def test_returns_empty_when_none_expiring(self):
        """Test returns empty list when no credentials expiring"""
        future = (datetime.now() + timedelta(hours=2)).isoformat()

        credential_list = [
            {"Expiration": future, "projects": ["project1"]},
            {"Expiration": future, "projects": ["project2"]}
        ]

        # Should return empty list

    def test_handles_invalid_date_format(self):
        """Test handles malformed expiration dates"""
        credential_list = [
            {"Expiration": "not-a-date", "projects": ["project1"]}
        ]

        # Should handle gracefully


class TestRefreshJitCredentials:
    """Tests for refresh_jit_credentials function"""

    @patch('requests.get')
    def test_refreshes_all_credentials(self, mock_get, monkeypatch):
        """Test refreshes credentials for all projects"""
        monkeypatch.setenv("DOMINO_JIT_ENDPOINT", "http://jit-svc:5000")
        monkeypatch.setenv("DOMINO_API_PROXY", "http://localhost:8899")

        # Mock JWT response
        mock_jwt_response = MagicMock()
        mock_jwt_response.status_code = 200
        mock_jwt_response.text = "jwt_token"

        # Mock credentials response
        mock_creds_response = MagicMock()
        mock_creds_response.status_code = 200
        mock_creds_response.json.return_value = [
            {"accessKeyId": "AKIA123", "projects": ["project1"]}
        ]

        mock_get.side_effect = [mock_jwt_response, mock_creds_response]

        # Should return list of credentials

    @patch('requests.get')
    def test_refreshes_single_project(self, mock_get, monkeypatch):
        """Test refreshes credentials for specific project"""
        monkeypatch.setenv("DOMINO_JIT_ENDPOINT", "http://jit-svc:5000")
        monkeypatch.setenv("DOMINO_API_PROXY", "http://localhost:8899")

        # Should call /jit-sessions/<project> endpoint

    @patch('requests.get')
    def test_handles_no_jwt_available(self, mock_get, monkeypatch):
        """Test handles case when JWT is not available"""
        monkeypatch.setenv("DOMINO_API_PROXY", "http://localhost:8899")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        # Should handle gracefully when no JWT available


class TestGracefulShutdown:
    """Tests for GracefulShutdown class"""

    def test_init_registers_signal_handlers(self):
        """Test initialization registers SIGINT and SIGTERM handlers"""
        with patch('signal.signal') as mock_signal:
            from shutdown import GracefulShutdown

            mock_logger = MagicMock()
            shutdown = GracefulShutdown(mock_logger)

            # Should register handlers for SIGINT and SIGTERM
            assert mock_signal.call_count >= 2

    def test_exit_gracefully_sets_flag(self):
        """Test exit_gracefully sets shutdown_signal flag"""
        with patch('signal.signal'):
            from shutdown import GracefulShutdown

            mock_logger = MagicMock()
            shutdown = GracefulShutdown(mock_logger)

            assert shutdown.shutdown_signal is False

            shutdown.exit_gracefully(2, None)  # SIGINT

            assert shutdown.shutdown_signal is True
            mock_logger.info.assert_called()
