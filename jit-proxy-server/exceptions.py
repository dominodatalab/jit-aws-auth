"""
Provides reusable exception classes and utilities
"""
from http import HTTPStatus
from traceback import format_tb
from typing import Optional, Union

from werkzeug.exceptions import HTTPException

from utils.logging import logger
from utils.types import JsonDict


class JitAccessError(Exception):
    """
    Defines the base exception class from which other exceptions should
    extend. Provides standard messaging attributes and HTTP statuses so
    that exceptions can be handled appropriately.

    Should not be thrown directly - instead a subclass instance should
    be thrown.

    Attributes:
        http_status (HTTPStatus): The HTTP status to return if the
            exception occurs while responding to an HTTP request

    Args:
        message_internal (str): A message to log internally
        message_external (str, optional): A message to return to the
            requesting client
        details (dict, optional): Additional details to log internally
            along with the message. IMPORTANT: Must be JSON-serializable
    """
    http_status = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, message_internal: str,
                 message_external: Union[str, None] = None,
                 details: Optional[JsonDict] = None):
        super().__init__(self)
        self.message_internal = message_internal
        self.message_external = message_external
        self.details = details

    def __str__(self):
        return self.message_internal

    @property
    def name_external(self) -> str:
        """
        Returns:
            str: The name of the error to be returned to the requesting
                client. This is equal to the exception class's name unless
                overridden.
        """
        return self.__class__.__name__

    def log(self) -> None:
        """
        Logs the error along with its cause (if available)
        """
        # Gather basic error details
        error_name = self.__class__.__name__
        err_log_details: JsonDict = {
            'exception': error_name,
            'message': self.message_internal
        }

        # Add external message and details if available
        if (self.message_external
                and self.message_external != self.message_internal):
            err_log_details['messageExternal'] = self.message_external
        if self.details:
            err_log_details['details'] = self.details

        # Add error cause if available
        if self.__cause__:  # pylint: disable=using-constant-test
            cause = self.__cause__

            if 'details' not in err_log_details:
                err_log_details['details'] = {}
            err_log_details['details']['cause'] = {
                'message': str(cause),
                'details': {
                    'exception': cause.__class__.__name__,
                    # pylint: disable=no-member
                    'traceback': format_tb(cause.__traceback__)
                }
            }

        # Log error
        log_args = {
            'error_name': error_name,
            'message_internal': self.message_internal
        }
        logger.error('%(error_name)s: %(message_internal)s' % log_args,
                     extra={'details': err_log_details})


class InternalServerError(JitAccessError):
    """
    An unhandled, internal error occurred
    """

class ResourcesExceededError(JitAccessError):
    """
    limit reached
    """
    http_status = HTTPStatus.FORBIDDEN

class BadRequestError(JitAccessError):
    """
    An invalid request/event was received
    """
    http_status = HTTPStatus.BAD_REQUEST


class InvalidParameterError(BadRequestError):
    """
    A parameter in the request was invalid/malformed
    """


class NotFoundError(JitAccessError):
    """
    The requested resource was not found (HTTP) or no event handler
    exists for the received event type (non-HTTP)
    """
    http_status = HTTPStatus.NOT_FOUND


class ResourceExistsError(JitAccessError):
    """
    An attempt was made to create a resource that already exists
    """
    http_status = HTTPStatus.CONFLICT


class EventNotImplementedError(JitAccessError):
    """
    The event source could not be determined
    """
    http_status = HTTPStatus.NOT_IMPLEMENTED


class UnauthorizedError(JitAccessError):
    """
    The requester is not authorized the make the request. It should be
    retried after authorization.
    """
    http_status = HTTPStatus.UNAUTHORIZED


class ForbiddenError(JitAccessError):
    """
    The requester does not have permission to make the request.
    """
    http_status = HTTPStatus.FORBIDDEN


class ExpiredError(JitAccessError):
    """
    The JIT session has expired.
    """
    http_status = HTTPStatus.FORBIDDEN


def log_error(error: Exception):
    """
    Logs standard error details for any exception. If the `Exception`
    is an instance of `JitAccessError`, the class's native `log()`
    method is used.

    Args:
        error (Exception): The exception to log
    """
    if isinstance(error, JitAccessError):
        error.log()
    elif isinstance(error, HTTPException):
        logger.error('An HTTP error occurred', extra={
            'details': {
                'exception': error.__class__.__name__
            }
        })
        logger.debug('HTTP error traceback', extra={'details': {
            'traceback': format_tb(error.__traceback__)
        }})
    else:
        logger.error('An unrecognized error occurred', extra={
            'details': {
                'exception': error.__class__.__name__,
                'message': str(error),
                'traceback': format_tb(error.__traceback__)
            }
        })
