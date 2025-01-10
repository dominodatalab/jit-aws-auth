import sys,requests,os,time,datetime,logging,traceback,configparser,json,shutdown,shutil
from datetime import datetime,timedelta

log_file = os.environ.get("JIT_LOG_FOLDER", "/var/log/jit/") + "app.log"
aws_credentials_profile = os.environ.get("AWS_SHARED_CREDENTIALS_FILE","/etc/.aws/profile")
jit_directory_root = "/etc/.aws"
aws_credentials_file = f"{jit_directory_root}/credentials"
client_bin_dir = f"{jit_directory_root}/bin"
service_endpoint = os.environ.get("DOMINO_JIT_ENDPOINT","http://jit-svc.domino-field")
token_min_expiry_in_seconds = os.environ.get("TOKEN_MIN",300)
poll_jit_interval = os.environ.get("POLL_INTERVAL",10)

session_list = []

# lvl: str = logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO"))
# logging.basicConfig(
#     level=lvl,
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
#     filename=log_file, filemode='w'
# )
# logger = logging.getLogger("werkzeug")
# handler = logging.StreamHandler(sys.stdout)
# logger.addHandler(handler)

logger = logging.getLogger('jit_proxy_client')
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

def write_credentials_profile(aws_credentials:list[dict],cred_file_path):
    config = configparser.ConfigParser()
    config.read(cred_file_path)
    log_creds = [{k,v['AccessKeyId']} for k,v in aws_credentials]
    logger.debug(f"Credential profiles to write: {log_creds}")
    for cred in aws_credentials:
        profile_name = cred['projects'][0]
        if not config.has_section(profile_name): 
            config.add_section(profile_name)
            logger.info(f'Adding AWS cli credentials profile {profile_name}')
        logger.info(f'Adding AWS cli credentials: profile: {profile_name}, jitSessionId: {cred["session_id"]}, AWS Key ID: {cred["accessKeyId"]}')
        config.set(profile_name,"credential_process",f"{client_bin_dir}/credential-helper --cred-file {aws_credentials_file} --profile {profile_name}")
        config.set(profile_name,"jitSessionId",cred["session_id"])
    with open(cred_file_path, "w") as f:
        config.write(f)

def write_credentials_file(aws_credentials:list[dict],cred_file_path):
    log_creds = [{k,v['AccessKeyId']} for k,v in aws_credentials]
    logger.debug(f"Credentials to write: {log_creds}")
    cred_dict = {cred['projects'][0]:cred for cred in aws_credentials}
    with open(cred_file_path, "w") as f:
        json.dumps(cred_dict,f)
        

def read_credentials_file(cred_file_path):
    with open(cred_file_path, "r") as f:
        config_dict = json.load(f)
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
    logger.info("Checking for credential expiry")
    expiring_creds = []
    for cred in credential_list:
        cred_expiration_time = datetime.astimezone(datetime.strptime(cred['expiration'],'%Y-%m-%d %H:%M:%S%z'))
        cred_refresh_time = cred_expiration_time - timedelta(seconds=token_min_expiry_in_seconds)
        now = datetime.now().astimezone()
        if now > cred_refresh_time:
            logger.info(f'Credential for project {cred["jit_project"]} is expiring soon: Cred expiry {cred["expiration"]}, Cred refresh time {cred_refresh_time.strftime("%Y-%m-%d %H:%M:%S%z")}')
            expiring_creds.append(cred)
    return expiring_creds

def refresh_jit_credentials(project=None):
    global log_file
    success = False
    retry_wait = 5
    retry_count = 10
    if project:
        url = f'{service_endpoint}/{project}'
    else:
        url = service_endpoint
    user_jwt = get_domino_user_identity()
    headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + user_jwt,
    }
    logger.info(f'Refreshing credentials from JIT URL: {url}')
    while (not success):
        try:
            resp = requests.get(url, headers=headers, json={})
            logger.warning(f'Status code from JIT URL {url}: {resp.status_code}')
            logger.debug(f'API Response: {resp.json()}')
            if resp.status_code == 200:
                creds = resp.json()
                success = True
        except Exception:
            logger.error(f'Exception: {retry_count}')
            logger.error(f'Error calling {url}. Check log file {log_file} for details.')
            retry_count -= 1
            time.sleep(retry_wait)
            retry_wait = retry_wait * 6
        # Writing to file
    return creds

if __name__ == "__main__":
    shutdown = shutdown.GracefulShutdown(logger)
    shutil.copytree("/app/clientbin",client_bin_dir)
    while not shutdown.shutdown_signal:
        if os.path.isfile(aws_credentials_file) and os.path.getsize(aws_credentials_file) > 0:
            existing_creds = read_credentials_file(aws_credentials_file)
            expiring_creds = check_credential_expiration(existing_creds)
            if len(expiring_creds) > 0:
                new_creds = []
                for cred in expiring_creds:
                    # A note here: in the initial phase, we call the base service endpoint, which returns a list of all credentials
                    # that the user is authorized for (based on their groups).
                    # In the refresh phase, we call the service endpoint by project, based on which credentials are expiring.
                    refreshed_cred = refresh_jit_credentials(cred['jit_project'])
                    new_creds.append(refreshed_cred)
                if len(new_creds) > 0:    
                    write_credentials_file(aws_credentials=new_creds,cred_file_path=aws_credentials_file)
                else:
                    logger.info("Attempted to refresh credentials, but response from JIT Proxy was empty. Will retry on next cycle.")
        else:
            new_creds = refresh_jit_credentials()
            if len(new_creds) > 0:
                write_credentials_profile(aws_credentials=new_creds,cred_file_path=aws_credentials_profile)
                write_credentials_file(aws_credentials=new_creds,cred_file_path=aws_credentials_file)
        if not shutdown.shutdown_signal:
            logger.info(f"Sleeping {poll_jit_interval} seconds until next attempt...")
            time.sleep(poll_jit_interval)
