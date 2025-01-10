"""
Provides a preconfigured logger that writes log messages in JSON format.
Additional info can be logged by passing JSON-serializable details in a
`dict` to the `extra` keyward arg of any logging method, under the
`details` key.

Example:
    extra_details = {'foo': 'bar'}
    logger.info('Hello!', extra={'details': extra_details})
"""
import json
import logging
import os
from traceback import format_tb


class JsonFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """
    Defines a logging filter that converts log messages into JSON format,
    adding context info and additional details if specified

    NOTE: Only the message is JSON-serialized. While it's possible to
    serialize the entire log record (level + time + request ID + message),
    it may affect integration with other systems which expect the standard
    Lambda log format.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Convert message to a dict
        message_dict = {'message': record.msg}

        # Add additional details to message
        try:
            message_dict['details'] = record.details  # type: ignore
        except AttributeError:
            pass

        # Add module name and line number to message
        message_dict['module'] = f'{record.module}:{record.lineno}'

        # If we're using SAM local invoke pretty print JSON logs
        json_kwargs = {}
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') == 'test':
            json_kwargs = {'indent': 4}

        # Serialize message as JSON
        try:
            record.msg = json.dumps(message_dict, **json_kwargs)
        except TypeError as error:
            record.levelname = 'WARN'
            record.msg = json.dumps({
                'message': 'Failed to serialize log message',
                'details': {
                    'origMsg': str(record.msg),
                    'cause': {
                        'exception': error.__class__.__name__,
                        'message': str(error),
                        'traceback': format_tb(error.__traceback__)
                    }
                }
            }, **json_kwargs)

        return True


# Set log level based on LOG_LEVEL environment variable
log_level = getattr(logging, os.environ.get('LOG_LEVEL', 'INFO'))

# Configger root logger's level and create JSON filter
logging.basicConfig(level=log_level,filename='/var/log/jit/app.log',filemode='a',format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',)
logger = logging.getLogger("werkzeug")
logger.setLevel(log_level)
logger.addFilter(JsonFilter())
