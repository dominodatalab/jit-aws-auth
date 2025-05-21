import sys,requests,os,time,datetime,logging,traceback,configparser,json,shutdown,shutil,backoff
from datetime import datetime,timedelta

log_file = os.environ.get("JIT_LOG_FOLDER", "/var/log/jit/") + "app.log"
aws_credentials_profile = os.environ.get("AWS_CONFIG_FILE","/etc/.aws/profile")
jit_directory_root = "/etc/.aws"
aws_credentials_file = f"{jit_directory_root}/credentials"
client_bin_dir = f"{jit_directory_root}/bin"
service_endpoint = os.environ.get("DOMINO_JIT_ENDPOINT","http://jit-svc.domino-field")
token_min_expiry_in_seconds = os.environ.get("TOKEN_MIN",300)
poll_jit_interval = os.environ.get("POLL_INTERVAL",10)

session_list = []

logger = logging.getLogger('jit_proxy_client')
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

def check_update_clientbin():
    commit = None
    image_commit = os.getenv('COMMIT',None)
    logger.debug(f"Env var COMMIT: {image_commit}")
    if os.path.isfile(f'{client_bin_dir}/commithash'):
        logger.debug(f"Reading commit hash from {client_bin_dir}/commithash")
        with open(f'{client_bin_dir}/commithash','r') as f:
            commit = f.read().strip()
            logger.debug(f"Commit hash in {client_bin_dir}: {commit}")
    if (commit != image_commit):
        logger.info(f"Copying credential process binaries to {client_bin_dir}...")
        shutil.copytree("/app/clientbin",client_bin_dir,dirs_exist_ok=True)

def write_credentials_profile(aws_credentials:list[dict],cred_file_path):
    config = configparser.ConfigParser()
    config.read(cred_file_path)
    log_creds = [{cred['accessKeyId']} for cred in aws_credentials]
    logger.debug(f"Credential profiles to write: {log_creds}")
    for cred in aws_credentials:
        profile_name = cred['projects'][0]
        profile_str = f'profile {profile_name}'
        if not config.has_section(profile_str):
            config.add_section(profile_str)
            logger.info(f'Adding AWS cli credentials profile {profile_name}')
        logger.info(f'Adding AWS cli credentials: profile: {profile_name}, jitSessionId: {cred["session_id"]}, AWS Key ID: {cred["accessKeyId"]}')
        config.set(profile_str,"credential_process",f"{client_bin_dir}/credential-helper -credfile={aws_credentials_file} -profile={profile_name}")
        config.set(profile_str,"jitSessionId",cred["session_id"])
    with open(cred_file_path, "w") as f:
        config.write(f)

def convert_jit_api_to_aws_creds(jit_creds:list[dict]) -> dict[dict]:
    # Based on https://docs.aws.amazon.com/cli/v1/userguide/cli-configure-sourcing-external.html:
    # {
    # "Version": 1,
    # "AccessKeyId": "an AWS access key",
    # "SecretAccessKey": "your AWS secret access key",
    # "SessionToken": "the AWS session token for temporary credentials", 
    # "Expiration": "ISO8601 timestamp when the credentials expire"
    # }
    cred_dict = {}
    for cred in jit_creds:
        profile_name = cred['projects'][0]
        if 'Version' not in cred:            
            expiration_time = datetime.strptime(cred['expiration'],'%Y-%m-%d %H:%M:%S%z').isoformat()
            cred_dict[profile_name] = {
                "Version": 1,
                "AccessKeyId": cred["accessKeyId"],
                "SecretAccessKey": cred["secretAccessKey"],
                "SessionToken": cred["sessionToken"],
                "Expiration": expiration_time
            }
        else:
            cred_dict[profile_name] = cred
    logger.debug(f"Credentials to write: {cred_dict}")
    return cred_dict

def convert_aws_creds_to_jit_api(aws_creds:dict[dict]) -> list[dict]:
    cred_list = []
    for key,cred in aws_creds.items():
            cred['projects'] = [key]
            cred_list.append(cred)
    return cred_list

def write_credentials_file(aws_credentials:list[dict],cred_file_path):
    cred_dict = convert_jit_api_to_aws_creds(aws_credentials)
    with open(cred_file_path, "w") as f:
        json.dump(cred_dict,f,indent=4)
        

def read_credentials_file(cred_file_path) -> list[dict]:
    with open(cred_file_path, "r") as f:
        config_dict = convert_aws_creds_to_jit_api(json.load(f))
    return config_dict

@backoff.on_exception(backoff.expo,requests.exceptions.RequestException,max_time=poll_jit_interval,raise_on_giveup=False)
def get_domino_user_identity():
    token = None
    token_endpoint = os.environ.get('DOMINO_API_PROXY','http://localhost:8899')
    access_token_endpoint = token_endpoint + "/access-token"
    logger.warning(f'Invoking  {access_token_endpoint}/')
    resp = requests.get(access_token_endpoint)
    resp.raise_for_status()
    if (resp.status_code==200):
        logger.warning(f'Success invoking  {access_token_endpoint}')
        token = resp.text
    else:
        logger.warning(f'Failed invoking  {access_token_endpoint} status code {resp.status_code}')
        logger.warning(f'Error invoking api proxy endpoint {resp.text}')
    return token

def check_credential_expiration(credential_list:list[dict]) -> list[dict]:
    logger.info("Checking for credential expiry")
    expiring_creds = []
    for cred in credential_list:
        cred_expiration_time = datetime.astimezone(datetime.fromisoformat(cred['Expiration']))
        projectname = cred['projects'][0]
        cred_refresh_time = cred_expiration_time - timedelta(seconds=token_min_expiry_in_seconds)
        now = datetime.now().astimezone()
        if now > cred_refresh_time:
            logger.info(f'Credential for project {projectname} is expiring soon: Cred expiry {cred["Expiration"]}, Cred refresh time {cred_refresh_time.strftime("%Y-%m-%d %H:%M:%S%z")}')
            expiring_creds.append(cred)
    return expiring_creds

@backoff.on_exception(backoff.expo,requests.exceptions.RequestException,max_time=poll_jit_interval,raise_on_giveup=False)
def refresh_jit_credentials(project=None):
    # The structure we're expecting from the JIT Proxy:
    # [ 
    #     {
    #         'expiration': <date str '%Y-%m-%d %H:%M:%S%z'>, 
    #         'projects': <list[str]>,
    #         'secretAccessKey':'<str>', 
    #         'sessionToken': '<str>', 
    #         'session_id': '<str>'
    #     }
    # ]
    creds = []
    if project:
        url = f'{service_endpoint}/{project}'
    else:
        url = service_endpoint
    user_jwt = get_domino_user_identity()
    if user_jwt != None:
        headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + user_jwt,
        }
        logger.info(f'Refreshing credentials from JIT URL: {url}')
        resp = requests.get(url, headers=headers, json={})
        logger.warning(f'Status code from JIT URL {url}: {resp.status_code}')
        resp.raise_for_status()
        if resp.status_code == 200:
            logger.debug(f'API Response: {resp.json()}')
            creds = resp.json()
    return creds

if __name__ == "__main__":
    shutdown = shutdown.GracefulShutdown(logger)
    logger.info("Starting JIT Client Proxy...")
    check_update_clientbin()
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
                    projectname = cred['projects'][0]
                    refreshed_cred = refresh_jit_credentials(projectname)
                    new_creds.append(refreshed_cred)
                    existing_creds.remove(cred)
                mux_creds = [*existing_creds,*new_creds]      
                if len(new_creds) > 0:
                    logger.debug(f"Refreshed credentials for projects: {new_creds}")
                    write_credentials_file(aws_credentials=mux_creds,cred_file_path=aws_credentials_file)
                else:
                    logger.info("Attempted to refresh credentials, but response from JIT Proxy was empty. Will retry on next cycle.")
        else:
            new_creds = refresh_jit_credentials()
            if new_creds != None and len(new_creds) > 0:
                write_credentials_profile(aws_credentials=new_creds,cred_file_path=aws_credentials_profile)
                write_credentials_file(aws_credentials=new_creds,cred_file_path=aws_credentials_file)
        if not shutdown.shutdown_signal:
            logger.debug(f"Sleeping {poll_jit_interval} seconds until next attempt...")
            time.sleep(poll_jit_interval)