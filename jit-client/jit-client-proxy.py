import sys

import requests
import os
import time,datetime
import logging
import traceback
import configparser
from datetime import datetime,timedelta

log_file = os.environ.get("JIT_LOG_FOLDER", '/var/log/jit/') + 'app.log'
aws_credentials_file = os.environ.get("AWS_SHARED_CREDENTIALS_FILE",'/etc/.aws/credentials')
service_endpoint = os.environ.get("DOMINO_JIT_ENDPOINT",'https://jit-svc.domino-field')
token_min_expiry_in_seconds = os.environ.get('TOKEN_MIN',300)
poll_jit_interval = os.environ.get('POLL_INTERVAL',60)
cacert_path = os.environ.get('REQUESTS_CACERT')
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

def write_credentials_file(aws_credentials:[],cred_file_path):
    config = configparser.ConfigParser()
    config.read(cred_file_path)
    for cred in aws_credentials:
        profile_name = cred['projects'][0]
        if not config.has_section(profile_name): 
            config.add_section(profile_name)
            logger.info('Adding AWS cli credentials profile', extra={'details': {'profile': profile_name, 'jitSessionId': cred["session_id"], 'project': cred["projects"]}})
        logger.info('Adding AWS cli credentials', extra={'details': {'profile': profile_name, 'jitSessionId': cred["session_id"], 'AWS Key ID':cred["accessKeyId"]}})
        config.set(profile_name,"aws_access_key_id",cred["accessKeyId"])
        config.set(profile_name,"aws_secret_access_key",cred["secretAccessKey"])
        config.set(profile_name,"aws_session_token",cred["sessionToken"])
        config.set(profile_name,"expiration",cred["expiration"])
        config.set(profile_name,"jit_session_id",cred["session_id"])
        config.set(profile_name,"jit_project",profile_name)
    with open(cred_file_path, "w") as f:
        config.write(f)
        

def read_credentials_file(cred_file_path):
    config = configparser.ConfigParser()
    config.read(cred_file_path)
    config_dict = [ dict(config.items(section)) for section in config.sections() ]
    return config_dict

def get_domino_user_identity():
    success = False
    retries = 5
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
    min_expiry_time = datetime.now().astimezone() + timedelta(seconds=token_min_expiry_in_seconds)
    min_expiry_time_str = min_expiry_time.strftime('%Y-%m-%d %H:%M:%S%z')
    expiring_creds = [cred for cred in credential_list if datetime.astimezone(datetime.strptime(cred['expiration'],'%Y-%m-%d %H:%M:%S%z')) < min_expiry_time ]
    for cred in expiring_creds:
        logger.info(f'Credential for {cred["jit_project"]} is expiring soon: Cred expiry {cred["expiration"]}, Min expiry time {min_expiry_time_str}')
    return expiring_creds

def refresh_jit_credentials(project=None):
    global log_file
    if project:
        url = f'{service_endpoint}/{project}'
    else:
        url = service_endpoint
    logger.warning(url)
    user_jwt = get_domino_user_identity()
    headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + user_jwt,
    }
    resp = requests.get(url, headers=headers, json={},verify=cacert_path)
        # Writing to file
    logger.warning(resp.status_code)
    logger.warning(resp.content)
    # logger.warning(resp.text)
    if resp.status_code == 200:
        return resp.json()
    else:
        result = f'Error calling {url}. Check log file {log_file} for details.'
        logger.error(result)

if __name__ == "__main__":
    while True:
        if os.path.isfile(aws_credentials_file) and os.path.getsize(aws_credentials_file) > 0:
            existing_creds = read_credentials_file(aws_credentials_file)
            expiring_creds = check_credential_expiration(existing_creds)
            if len(expiring_creds) > 0:
                new_creds = []
                for project in expiring_creds['jit_project']:                
                    new_creds.append(refresh_jit_credentials(project))
                write_credentials_file(aws_credentials=new_creds,cred_file_path=aws_credentials_file)
        else:
            new_creds = refresh_jit_credentials()
            write_credentials_file(new_creds,aws_credentials_file)
        time.sleep(poll_jit_interval)
                
    refresh_jit_credentials()
    port_no = int(os.environ.get('JIT_CLIENT_PROXY_PORT','5003'))
    app.run(debug=True, host='0.0.0.0', port=port_no)
