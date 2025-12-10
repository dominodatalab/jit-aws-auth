"""
Pytest configuration and shared fixtures for jit-aws-auth tests
"""

import pytest
import os
import sys
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Add parent directories to Python path so tests can import the modules
_tests_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_tests_dir)

# Add jit-proxy-server to path
_jit_proxy_server_path = os.path.join(_project_root, 'jit-proxy-server')
if _jit_proxy_server_path not in sys.path:
    sys.path.insert(0, _jit_proxy_server_path)

# Create 'jit' package alias for jit-proxy-server
# The source code uses imports like 'from jit.exceptions import ...'
# which expects the jit-proxy-server directory to be importable as 'jit'
import importlib.util
if 'jit' not in sys.modules:
    # Create a module spec for 'jit' pointing to jit-proxy-server
    _jit_init_path = os.path.join(_jit_proxy_server_path, '__init__.py')
    _jit_spec = importlib.util.spec_from_file_location('jit', _jit_init_path,
        submodule_search_locations=[_jit_proxy_server_path])
    _jit_module = importlib.util.module_from_spec(_jit_spec)
    sys.modules['jit'] = _jit_module
    _jit_spec.loader.exec_module(_jit_module)

# Add jit-client to path
_jit_client_path = os.path.join(_project_root, 'jit-client')
if _jit_client_path not in sys.path:
    sys.path.insert(0, _jit_client_path)


# Sample JWT payload for testing
SAMPLE_JWT_PAYLOAD = {
    "preferred_username": "testuser",
    "email": "testuser@example.com",
    "fm_projects": [
        "sg-jit-prod-app-lifecycle-prj-project1",
        "sg-jit-prod-app-lifecycle-prj-project2",
        "sg-jit-dev-app-lifecycle-prj-POLICY-MANAGER-test"
    ],
    "exp": int((datetime.now() + timedelta(hours=1)).timestamp()),
    "iat": int(datetime.now().timestamp())
}

SAMPLE_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"


# Sample JIT config
SAMPLE_JIT_CONFIG = {
    "jit_endpoint": "https://jit.example.com",
    "minimum_token_validity_required_in_seconds": "30",
    "prj_attribute_name": "fm_projects",
    "ping_secret": "arn:aws:secretsmanager:us-east-1:123456789:secret:ping-secret",
    "nuid_secret": "arn:aws:secretsmanager:us-east-1:123456789:secret:nuid-secret"
}


# Sample secrets
SAMPLE_PING_SECRET = {
    "client-id": "test-client-id",
    "client-secret": "test-client-secret",
    "auth-server-url": "https://auth.example.com/oauth/token"
}

SAMPLE_NUID_SECRET = {
    "username": "test-nuid-user",
    "password": "test-nuid-password"
}


# Sample JIT session response
SAMPLE_JIT_SESSION = {
    "sessionId": "jit-testuser-app-abc123",
    "accessKeyId": "AKIAIOSFODNN7EXAMPLE",
    "secretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "sessionToken": "FwoGZXIvYXdzEBYaDK...",
    "expiration": (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S+0000"),
    "projects": ["project1"]
}


# Sample AWS credentials in different formats
SAMPLE_AWS_CREDS_JIT_FORMAT = [
    {
        "accessKeyId": "AKIAIOSFODNN7EXAMPLE",
        "secretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "sessionToken": "FwoGZXIvYXdzEBYaDK...",
        "expiration": (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S+0000"),
        "session_id": "jit-testuser-app-abc123",
        "projects": ["project1"]
    }
]

SAMPLE_AWS_CREDS_AWS_FORMAT = {
    "project1": {
        "Version": 1,
        "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
        "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "SessionToken": "FwoGZXIvYXdzEBYaDK...",
        "Expiration": (datetime.now() + timedelta(hours=1)).isoformat()
    }
}


@pytest.fixture
def sample_jwt():
    """Return sample JWT token"""
    return SAMPLE_JWT


@pytest.fixture
def sample_jwt_payload():
    """Return sample decoded JWT payload"""
    return SAMPLE_JWT_PAYLOAD.copy()


@pytest.fixture
def sample_jit_config():
    """Return sample JIT configuration"""
    return SAMPLE_JIT_CONFIG.copy()


@pytest.fixture
def sample_ping_secret():
    """Return sample Ping OAuth secret"""
    return SAMPLE_PING_SECRET.copy()


@pytest.fixture
def sample_nuid_secret():
    """Return sample NUID secret"""
    return SAMPLE_NUID_SECRET.copy()


@pytest.fixture
def sample_jit_session():
    """Return sample JIT session response"""
    return SAMPLE_JIT_SESSION.copy()


@pytest.fixture
def sample_aws_creds_jit_format():
    """Return sample AWS credentials in JIT API format"""
    return [cred.copy() for cred in SAMPLE_AWS_CREDS_JIT_FORMAT]


@pytest.fixture
def sample_aws_creds_aws_format():
    """Return sample AWS credentials in AWS credential_process format"""
    return {k: v.copy() for k, v in SAMPLE_AWS_CREDS_AWS_FORMAT.items()}


@pytest.fixture
def mock_boto3_secretsmanager():
    """Mock boto3 Secrets Manager client"""
    with patch('boto3.client') as mock_client:
        mock_sm = MagicMock()
        mock_client.return_value = mock_sm

        mock_sm.get_secret_value.return_value = {
            'SecretString': json.dumps(SAMPLE_PING_SECRET)
        }
        mock_sm.describe_secret.return_value = {
            'LastRotatedDate': datetime.now()
        }

        yield mock_sm


@pytest.fixture
def mock_requests():
    """Mock requests library"""
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post:

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"isAnonymous": False}
        mock_response.text = SAMPLE_JWT

        mock_get.return_value = mock_response
        mock_post.return_value = mock_response

        yield {'get': mock_get, 'post': mock_post, 'response': mock_response}


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file"""
    config_file = tmp_path / "jit.json"
    config_file.write_text(json.dumps(SAMPLE_JIT_CONFIG))
    return str(config_file)


@pytest.fixture
def temp_credentials_file(tmp_path):
    """Create a temporary credentials file"""
    creds_file = tmp_path / "credentials"
    creds_file.write_text(json.dumps(SAMPLE_AWS_CREDS_AWS_FORMAT))
    return str(creds_file)


@pytest.fixture
def temp_profile_file(tmp_path):
    """Create a temporary AWS profile file"""
    profile_file = tmp_path / "profile"
    profile_content = """[profile project1]
credential_process=/etc/.aws/bin/credential-helper -credfile=/etc/.aws/credentials -profile=project1
jitSessionId=jit-testuser-app-abc123
"""
    profile_file.write_text(profile_content)
    return str(profile_file)


@pytest.fixture
def mock_environment(monkeypatch):
    """Set up common environment variables for testing"""
    monkeypatch.setenv("DOMINO_USER_HOST", "http://nucleus-frontend.test:80")
    monkeypatch.setenv("DOMINO_API_PROXY", "http://localhost:8899")
    monkeypatch.setenv("DOMINO_JIT_ENDPOINT", "http://jit-svc.test:5000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("TESTING_MODE", "false")
