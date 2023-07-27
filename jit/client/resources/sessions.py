"""
Defines an Access Engine client mixin for accessing the JIT Session APIs
"""
from jit.utils.types import JsonDict
from jit.client import constants

CERT_PATH = constants.certificate_path

class SessionsClientMixin:
    """
    Defines a mixin from which the `JitAccessEngineClient` can inherit
    to access the JIT Access Engine's Sessions APIs
    """

    def get_jit_sessions_by_sub(self, sub: str) -> str:
        """
        Returns an JIT sessions created by user.

        Args:
            template_name (str): The template name (e.g., a persona)

        Returns:
            JsonDict: The IAM role template
        """
        params = {"sub": sub, "active": 'true'}
        return self.get('/infrastructure/management/provisioning/aws-jit-provisioning/jit-sessions', params=params,
                        verify=CERT_PATH).json()

    def get_access_contracts(self, application_short_name: str, lifecycle: str) -> JsonDict:
        """
        Get Access Contracts
        Args:
            application_short_name (str): Application Short Name
            lifecycle (str): Lifecycle

        Returns:
            None
        """
        params = {"applicationShortName": application_short_name, "lifecycle": lifecycle}
        return self.get('/infrastructure/management/provisioning/aws-jit-provisioning/access-contracts', params=params,
                        verify=CERT_PATH).json()

    def put_sessions(self, payload: JsonDict) -> None:
        """
        Creates a JIT session

        Args:
            payload (JsonDict): A dict containing the event payload

        Returns:
            None
        """

        x = self.post(
            f"/infrastructure/management/provisioning/aws-jit-provisioning/jit-sessions",
            json=payload, verify=CERT_PATH)

        return x

    def get_aws_credentials(self, jit_session_id: str) -> JsonDict:
        """
        Returns AWS credentials for a JIT session

        Args:
            jit_session_id

        Returns:
            JsonDict: Get AWS Credentials
        """
        return self.get(
            f"/infrastructure/management/provisioning/aws-jit-provisioning/jit-sessions/{jit_session_id}/aws-credentials",
            verify=CERT_PATH).json()

    def get_session_by_id(self, jit_session_id: str) -> JsonDict:
        """
        Returns Jit session details

        Args:
            jit_session_id

        Returns:
            JsonDict: Returns Jit session details
        """
        return self.get(
            f"/infrastructure/management/provisioning/aws-jit-provisioning/jit-sessions/{jit_session_id}",
            verify=CERT_PATH).json()
