import os,json,botocore,botocore.session,aws_secretsmanager_caching,logging,sys
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

aws_sm_client = botocore.session.get_session().create_client('secretsmanager')
sm_cache_cfg = SecretCacheConfig(secret_refresh_interval=30)
sm_cache = SecretCache(config=sm_cache_cfg, client=aws_sm_client)
logger = logging.getLogger('jit_proxy')

jit_config_file = os.environ.get('JIT_CONFIG_FILE', '/etc/config/jit-config/jit.json')
jit_config = {}

with open(jit_config_file, 'r') as f:
    jit_config = json.load(f)
# Retrieve settings
jit_endpoint = jit_config['jit_endpoint']
ping_secret_arn = jit_config['ping_secret']
nuid_secret_arn = jit_config['nuid_secret']

def get_secret(secret_arn):
    secret_value = None
    try:
        secret_str = sm_cache.get_secret_string(secret_arn)
        secret_value = json.loads(secret_str)
    except Exception as e:
        logger.critical(f"Error retrieving secret {secret_arn}: {e}")
    return secret_value

ping_dict = get_secret(ping_secret_arn)
nuid_dict = get_secret(nuid_secret_arn)

client_secret = ping_dict['client-secret']
client_id = ping_dict['client-id']
token_endpoint = ping_dict['auth-server-url']

r_username = nuid_dict['username']
r_password = nuid_dict['password']

access_token_expiry_time = float(jit_config['minimum_token_validity_required_in_seconds'])
minimum_token_validity_required_in_seconds = int(jit_config['minimum_token_validity_required_in_seconds'])
fm_projects_attribute = jit_config['prj_attribute_name']
certificate_path = os.environ.get('JIT_CERT_FILE','/etc/config/jit-config/ca.crt')

def to_debug():
    return jit_config