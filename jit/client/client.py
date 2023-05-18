"""
Provides a client for invoking the JIT Access Engine APIs
"""
import datetime
from base64 import b64encode
from json.decoder import JSONDecodeError
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import requests
from werkzeug.exceptions import HTTPException

from jit.exceptions import InternalServerError
from jit.utils.logging import logger
from .resources import SessionsClientMixin
from . import constants


class JitAccessEngineClient(requests.Session, SessionsClientMixin):
    """
    Provides an HTTP client that extends `requests.Session` for easily
    making authorized requests to the JIT Access Engine APIs
    """

    ##Mount from Secrets - TO REMOVE
    JIT_ENDPOINT = constants.jit_endpoint
    JIT_ENDPOINT = constants.jit_endpoint
    TOKEN_ENDPOINT = constants.token_endpoint
    CLIENT_ID = constants.client_id
    CLIENT_SECRET = constants.client_secret

    def __init__(self, *args: List[Any], **kwargs: Dict[str, Any]):
        super().__init__(*args, **kwargs)
        # Retrieve settings
        self._jit_endpoint = constants.jit_endpoint
        logger.info("Engine Endpoint: %s", self._jit_endpoint)
        self._token_endpoint = constants.token_endpoint
        self._client_id = constants.client_id
        self._client_secret = constants.client_secret
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._access_token_expiry_time = constants.access_token_expiry_time
        self._r_username = constants.r_username
        self._r_password = constants.r_password


        encoded_client = b64encode(
            f'{self._client_id}:{self._client_secret}'.encode('utf-8')
        ).decode('utf-8')
        self._auth_header = {'Authorization': f'Basic {encoded_client}'}

    # pylint: disable=arguments-differ
    def request(  # pyright: reportIncompatibleMethodOverride=false
            self, method: str, url: Union[str, bytes], **kwargs: Dict[str, Any]
    ) -> requests.Response:
        """
        Overrides `requests.Session.request`, injecting the Access Engine
        API endpoint base if no base URL was provided and adding the
        necessary auth header

        Args:
            method (str): The HTT
            P method
            url (Union[str, bytes]): The HTTP endpoint to request

        Returns:
            requests.Response: The response from the Access Engine API

        Note:
            This method is not intended to be invoked directly. Instead,
            specific API methods provided by various mixins from which
            this client inherits should be used.
        """
        # Prepend API base endpoint to request URL
        full_url = url
        if not (url.startswith('https://') or url.startswith('http://')):
            full_url = urljoin(self._jit_endpoint, url)

        # Get access token and generate auth header
        access_token = self._get_access_token()
        headers = {
            'X-fnma-jws-token': access_token,
            **(kwargs.get('headers') or {})
        }

        # Make API request
        logger.debug('JIT Access Engine Client Request', extra={'details': {
            'method': method, 'url': url
        }})

        return super().request(method, full_url, headers=headers, **kwargs)

    def _get_access_token(self) -> str:
        """
        Authenticates the client with the configured authorization server
        and returns the resulting access token

        Raises:
            InternalServerError: Failed to retrieve access token

        Returns:
            str: The access token
        """
        now = datetime.datetime.now()
        if self._access_token_expiry_time and self._access_token_expiry_time - now > datetime.timedelta(
                seconds=constants.minimum_token_validity_required_in_seconds) and self._access_token:
            return self._access_token

        if self._refresh_token:
            params = {'grant_type': 'refresh_token', 'refresh_token': self._refresh_token}
            try:
                resp: requests.Response = requests.post(self._token_endpoint, headers=self._auth_header, params=params)
                resp_parsed = resp.json()
                self._access_token = resp_parsed['access_token']
                self._access_token_expiry_time = now + datetime.timedelta(seconds=resp_parsed['expires_in'])
                return self._access_token
            except (HTTPException, JSONDecodeError, KeyError) as error:
                logger.debug('Failed to retrieve access token using refresh token',
                             extra={'details': {'error': error}})

        # Build auth request payload
        data = {
            'grant_type': 'password',
            'username': self._r_username,
            'password': self._r_password
        }
        # Make auth request to token endpoint and parse out access token
        try:
            resp: requests.Response = requests.post(self._token_endpoint,
                                                    headers=self._auth_header, data=data)
            resp_parsed = resp.json()
            self._access_token = resp_parsed['access_token']
            self._access_token_expiry_time = now + datetime.timedelta(seconds=resp_parsed['expires_in'])
            self._refresh_token = resp_parsed['refresh_token']
        except (HTTPException, JSONDecodeError, KeyError) as error:
            raise InternalServerError('Failed to retrieve access token') from error

        if not self._access_token:
            raise InternalServerError('Failed to retrieve access token')

        # Return access token
        return self._access_token


