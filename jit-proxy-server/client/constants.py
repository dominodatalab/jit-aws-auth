import os,json,boto3,botocore,logging,sys

aws_sm_client = boto3.client('secretsmanager')
logger = logging.getLogger('jit_proxy')
certificate_path = os.environ.get('JIT_CERT_FILE','/etc/config/jit-config/ca.crt')

_jit_config_file = os.environ.get('JIT_CONFIG_FILE', '/etc/config/jit-config/jit.json')
jit_config = {}
with open(_jit_config_file, 'r') as f:
   jit_config = json.load(f)

# Module constants. 

access_token_expiry_time = float(jit_config['minimum_token_validity_required_in_seconds'])
minimum_token_validity_required_in_seconds = int(jit_config['minimum_token_validity_required_in_seconds'])
fm_projects_attribute = jit_config['prj_attribute_name']

def to_debug():
   return jit_config

class SecretConfig:

    def __init__(self,jit_config):
        # Retrieve settings        
        self.jit_endpoint = jit_config['jit_endpoint']
        self._ping_secret_arn = jit_config['ping_secret']
        self._nuid_secret_arn = jit_config['nuid_secret']        
        self.secret_metadata = [{'type':'ping','arn': self._ping_secret_arn, 'last_rotated': self._get_secret_lastrotated(self._ping_secret_arn)},
                            {'type':'nuid','arn': self._nuid_secret_arn, 'last_rotated': self._get_secret_lastrotated(self._nuid_secret_arn)}]
        self._ping_dict = self.get_secret(self._ping_secret_arn)
        self._nuid_dict = self.get_secret(self._nuid_secret_arn)
        self.ping_client_id = self._ping_dict['client-id']
        self.ping_client_secret = self._ping_dict['client-secret']
        self.ping_token_endpoint = self._ping_dict['auth-server-url']
        self.nuid_username = self._nuid_dict['username']
        self.nuid_password = self._nuid_dict['password']

    def _get_secret_lastrotated(self,secret_arn):
        secret_last_rotated = None
        try:
            secret_metadata = aws_sm_client.describe_secret(SecretId=secret_arn)
            if 'LastRotatedDate' in secret_metadata:
                secret_last_rotated = secret_metadata['LastRotatedDate']
        except botocore.exceptions.ClientError as e:
            logger.critical(f"Error retrieving secret metadata {secret_arn}: {e.response['Error']['Message']}")
        return secret_last_rotated

    def get_secret(self,secret_arn):
        secret_value = None
        try:
            secret_str = aws_sm_client.get_secret_value(SecretId=secret_arn)['SecretString']
            secret_value = json.loads(secret_str)
        except botocore.exceptions.ClientError as e:
            logger.critical(f"Error retrieving secret {secret_arn}: {e.response['Error']['Message']}")
        return secret_value

    def refresh_secret_data(self,secret_metadata):
        if secret_metadata['type'] == 'ping':
            self._ping_dict = self.get_secret(secret_metadata['arn'])
            self.ping_client_id = self._ping_dict['client-id']
            self.ping_client_secret = self._ping_dict['client-secret']
            self.ping_token_endpoint = self._ping_dict['auth-server-url']
        if secret_metadata['type'] == 'nuid':
            self._nuid_dict = self.get_secret(secret_metadata['arn'])
            self.nuid_username = self._nuid_dict['username']
            self.nuid_password = self._nuid_dict['password']
    
    def check_secret_rotation(self):
        for secret in self.secret_metadata:
            check_rotation_time = self._get_secret_lastrotated(secret['arn'])
            if check_rotation_time and check_rotation_time > secret['last_rotated']:
                logger.info(f"Secret {secret['type']} has been rotated. Refreshing secret data...")
                self.refresh_secret_data(secret)
                self.secret_metadata.remove(secret)
                self.secret_metadata.append({'type':secret['type'], 'arn': secret['arn'], 'last_rotated': check_rotation_time})
                logger.info(f"Secret metadata for {secret['type']} has been updated.")





# secret_metadata = [{'type':'ping','arn': ping_secret_arn, 'last_rotated': get_secret_lastrotated(ping_secret_arn)},
#                    {'type':'nuid','arn': nuid_secret_arn, 'last_rotated': get_secret_lastrotated(nuid_secret_arn)}]

# client_secret = ping_dict['client-secret']
# client_id = ping_dict['client-id']
# token_endpoint = ping_dict['auth-server-url']

# r_username = nuid_dict['username']
# r_password = nuid_dict['password']

# access_token_expiry_time = float(jit_config['minimum_token_validity_required_in_seconds'])
# minimum_token_validity_required_in_seconds = int(jit_config['minimum_token_validity_required_in_seconds'])
# fm_projects_attribute = jit_config['prj_attribute_name']
# certificate_path = os.environ.get('JIT_CERT_FILE','/etc/config/jit-config/ca.crt')

# def to_debug():
#     return jit_config