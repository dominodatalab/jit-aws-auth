import sys

import flask
import requests
import os
import time
import logging
import traceback

app = flask.Flask(__name__)
app.config["DEBUG"] = True

log_file = os.environ.get("JIT_LOG_FOLDER", "/var/log/jit/") + 'app.log'

lvl: str = logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO"))
logging.basicConfig(
    level=lvl,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=log_file, filemode='w'
)
logger = logging.getLogger("werkzeug")
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

@app.route('/refresh', methods=['GET'])
def refresh():
    result = refresh_jit_credentials()
    return {'result':result}

@app.route('/healthz', methods=['GET'])
def healthz():
    return "healthy"

def refresh_jit_credentials():
    global log_file
    aws_credentials_file = os.environ["AWS_SHARED_CREDENTIALS_FILE"]
    service_endpoint = os.environ["DOMINO_JIT_ENDPOINT"]
    logger.warning(aws_credentials_file)
    logger.warning(service_endpoint)
    success = False
    retries=5
    logger.warning('Now trying')
    while (not success) and retries > 0 :
        try:
            token_endpoint = os.environ.get('DOMINO_API_PROXY')
            access_token_endpoint = token_endpoint + "/access-token"
            logger.warning(f'Invoking  {access_token_endpoint}/')
            resp = requests.get(access_token_endpoint)
            if (resp.status_code==200):
                logger.warning(f'Success invoking  {access_token_endpoint}')
                token = resp.text
                success = True
            else:
                logger.warning(f'Failed invoking  {access_token_endpoint} status code {resp.status_code}')
                logger.warning(f'Error invoking api proxy endpoint {resp.text}')
                retries = retries - 1
                time.sleep(2)
        except Exception:
            # printing stack trace
            print(f'Exception {retries}')
            retries = retries - 1
            traceback.print_exc()
            time.sleep(2)
    logger.warning(f'Should I invoke jit endpoint {success}')
    if success:
        headers = {
             "Content-Type": "application/json",
             "Authorization": "Bearer " + token,
        }
        logger.warning(f'token {token}')
        resp = requests.get(service_endpoint, headers=headers, json={})
        # Writing to file
        logger.warning(resp.status_code)
        logger.warning(resp.content)
        logger.warning(resp.text)
        if resp.status_code == 200:
            with open(aws_credentials_file, "w") as f:
                # Writing data to a file
                f.write(resp.content.decode())
                result = f'Successfully updated {aws_credentials_file} with current set of JIT sessions'
                logger.warning(result)
        else:
            result = f'Error calling {service_endpoint}. Check log file {log_file} for details.'
            logger.error(result)
    else:
        result = 'Trouble getting the access token from api_proxy. Check log file {log_file} for details.'
        logger.error(result)

if __name__ == "__main__":
    refresh_jit_credentials()
    port_no = int(os.environ.get('JIT_CLIENT_PROXY_PORT','5003'))
    app.run(debug=True, host='0.0.0.0', port=port_no)
