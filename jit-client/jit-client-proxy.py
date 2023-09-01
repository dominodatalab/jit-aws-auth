import sys

import requests
import os
import time,datetime
import logging
import traceback
import configparser

log_file = os.environ.get("JIT_LOG_FOLDER", "/var/log/jit/") + 'app.log'
session_list = []

lvl: str = logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO"))
logging.basicConfig(
    level=lvl,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=log_file, filemode='w'
)
logger = logging.getLogger("werkzeug")
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

# @app.route('/refresh', methods=['GET'])
# def refresh():
#     success = refresh_jit_credentials()
#     return {'is_refreshed': success}

# @app.route('/healthz', methods=['GET'])
# def healthz():
#     return "healthy"

def write_credentials_file(aws_credentials,cred_file_path):
    config = configparser.ConfigParser()
    config.read(cred_file_path)
    for cred in aws_credentials:
        profile_name = cred['projects'][0]
        logger.info('adding aws cli credentials profile', extra={'details': {'profile': profile_name, 'jitSessionId': cred["session_id"]}})
        if not config.has_section(profile_name): 
            config.add_section(profile_name)
        config.set(profile_name,"aws_access_key_id",cred["accessKeyId"])
        config.set(profile_name,"aws_secret_access_key",cred["secretAccessKey"])
        config.set(profile_name,"aws_session_token",cred["sessionToken"])
        config.set(profile_name,"expiration",cred["expiration"])
        config.set(profile_name,"jit_session_id",cred["session_id"])
    with open(cred_file_path, "w") as f:
        config.write(f)
        

def read_credentials_file(cred_file_path):
    config = configparser.ConfigParser()
    config.read(cred_file_path)
    config_dict = [ dict(config.items(section)) for section in config.sections() ]
    return config_dict

def get_domino_user_identity():
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
    return token

def check_credential_expiration(credential_list:[]):
    now = datetime.datetime.now()
    min_expiry_threshold = datetime.timedelta(seconds=os.environ.get['TOKEN_MIN',300])
    min_expiry_time = now + min_expiry_threshold
    expiring_creds = [cred for cred in credential_list if datetime.strptime(cred['expiration'],'%Y-%m-%d %H:%M:%S%z') < min_expiry_time ]
    return expiring_creds

def refresh_jit_credentials(project=None):
    global log_file
    if project:
        service_endpoint = f'{os.environ.get["DOMINO_JIT_ENDPOINT"]}/{project}'
    else:
        service_endpoint = os.environ.get["DOMINO_JIT_ENDPOINT"]
    logger.warning(service_endpoint)
    user_jwt = get_domino_user_identity()
    headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + user_jwt,
    }
    resp = requests.get(service_endpoint, headers=headers, json={})
        # Writing to file
    logger.warning(resp.status_code)
    logger.warning(resp.content)
    # logger.warning(resp.text)
    if resp.status_code == 200:
        return resp.json()
    else:
        result = f'Error calling {service_endpoint}. Check log file {log_file} for details.'
        logger.error(result)

if __name__ == "__main__":
    refresh_jit_credentials()
    port_no = int(os.environ.get('JIT_CLIENT_PROXY_PORT','5003'))
    app.run(debug=True, host='0.0.0.0', port=port_no)
