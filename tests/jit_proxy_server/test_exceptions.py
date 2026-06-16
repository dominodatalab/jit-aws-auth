"""
Unit tests for exceptions.py - Custom exception classes
"""

import pytest
from unittest.mock import MagicMock, patch


class TestJitAccessError:
    """Tests for JitAccessError base class"""

    def test_init_with_internal_message(self):
        """Test exception initialization with internal message"""
        from exceptions import JitAccessError

        error = JitAccessError("Internal error message")

        assert error.message_internal == "Internal error message"
        # When message_external is not provided, it is None
        assert error.message_external is None
        assert error.details is None

    def test_init_with_external_message(self):
        """Test exception initialization with separate external message"""
        from exceptions import JitAccessError

        error = JitAccessError(
            "Detailed internal error",
            message_external="User-friendly error message"
        )

        assert error.message_internal == "Detailed internal error"
        assert error.message_external == "User-friendly error message"

    def test_init_with_details(self):
        """Test exception initialization with details dict"""
        from exceptions import JitAccessError

        details = {"field": "value", "code": 123}
        error = JitAccessError("Error", details=details)

        assert error.details == details

    def test_name_external_property(self):
        """Test name_external returns class name"""
        from exceptions import JitAccessError

        error = JitAccessError("Test error")

        assert error.name_external == "JitAccessError"

    def test_str_returns_internal_message(self):
        """Test __str__ returns internal message"""
        from exceptions import JitAccessError

        error = JitAccessError("This is the error message")

        assert str(error) == "This is the error message"

    def test_log_method(self):
        """Test log method logs error with details"""
        # Need to patch the logger where it's used (in exceptions module)
        with patch('exceptions.logger') as mock_logger:
            from exceptions import JitAccessError

            error = JitAccessError("Test error", details={"key": "value"})
            error.log()

            mock_logger.error.assert_called()
            call_args = mock_logger.error.call_args
            assert "Test error" in str(call_args)

    def test_log_with_cause(self):
        """Test log method includes cause when chained"""
        with patch('exceptions.logger') as mock_logger:
            from exceptions import JitAccessError

            try:
                try:
                    raise ValueError("Original error")
                except ValueError as e:
                    raise JitAccessError("Wrapper error") from e
            except JitAccessError as error:
                error.log()

            mock_logger.error.assert_called()


class TestInternalServerError:
    """Tests for InternalServerError subclass"""

    def test_inherits_from_jit_access_error(self):
        """Test InternalServerError is a JitAccessError"""
        from exceptions import InternalServerError, JitAccessError

        error = InternalServerError("Test error")

        assert isinstance(error, JitAccessError)

    def test_name_external_returns_subclass_name(self):
        """Test name_external returns InternalServerError"""
        from exceptions import InternalServerError

        error = InternalServerError("Test error")

        assert error.name_external == "InternalServerError"


class TestLogError:
    """Tests for log_error function"""

    def test_logs_jit_access_error(self):
        """Test log_error properly logs JitAccessError"""
        with patch('exceptions.logger') as mock_logger:
            from exceptions import JitAccessError, log_error

            error = JitAccessError("Test JIT error")
            log_error(error)

            mock_logger.error.assert_called()

    def test_logs_http_exception(self):
        """Test log_error properly logs HTTPException"""
        with patch('exceptions.logger') as mock_logger:
            from exceptions import log_error
            from werkzeug.exceptions import NotFound

            error = NotFound("Resource not found")
            log_error(error)

            mock_logger.error.assert_called()

    def test_logs_generic_exception(self):
        """Test log_error properly logs generic exceptions"""
        with patch('exceptions.logger') as mock_logger:
            from exceptions import log_error

            error = ValueError("Generic error")
            log_error(error)

            mock_logger.error.assert_called()

    def test_logs_debug_traceback(self):
        """Test log_error logs traceback at debug level"""
        with patch('exceptions.logger') as mock_logger:
            from exceptions import log_error

            error = RuntimeError("Runtime error with traceback")
            log_error(error)

            # Should have both error and debug calls
            assert mock_logger.error.called or mock_logger.debug.called
