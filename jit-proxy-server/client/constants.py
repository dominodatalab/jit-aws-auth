import os,json,boto3,botocore,logging,sys,datetime

aws_sm_client = boto3.client('secretsmanager')
logger = logging.getLogger('jit_proxy')
certificate_path = os.environ.get('JIT_CERT_FILE','/etc/config/jit-config/ca.crt')
# Per-call timeout for requests to the upstream JIT Access Engine. The Access Engine's
# own API owner has stated a single call may legitimately take up to 60 seconds.
access_engine_timeout = int(os.environ.get('JIT_ACCESS_ENGINE_TIMEOUT_SECONDS', 60))

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
        ping_last_rotated, ping_next_rotation = self._get_secret_rotation_dates(self._ping_secret_arn)
        nuid_last_rotated, nuid_next_rotation = self._get_secret_rotation_dates(self._nuid_secret_arn)
        self.secret_metadata = [{'type':'ping','arn': self._ping_secret_arn, 'last_rotated': ping_last_rotated, 'next_rotation': ping_next_rotation},
                            {'type':'nuid','arn': self._nuid_secret_arn, 'last_rotated': nuid_last_rotated, 'next_rotation': nuid_next_rotation}]
        self._ping_dict = self.get_secret(self._ping_secret_arn)
        self._nuid_dict = self.get_secret(self._nuid_secret_arn)
        self.ping_client_id = self._ping_dict['client-id']
        self.ping_client_secret = self._ping_dict['client-secret']
        self.ping_token_endpoint = self._ping_dict['auth-server-url']
        self.nuid_username = self._nuid_dict['username']
        self.nuid_password = self._nuid_dict['password']

    def _get_secret_rotation_dates(self,secret_arn):
        """
        Returns a (last_rotated, next_rotation) tuple from Secrets Manager's
        describe_secret response, either of which may be None if absent
        (e.g. rotation is not enabled for this secret).
        """
        last_rotated = None
        next_rotation = None
        try:
            secret_metadata = aws_sm_client.describe_secret(SecretId=secret_arn)
            last_rotated = secret_metadata.get('LastRotatedDate')
            next_rotation = secret_metadata.get('NextRotationDate')
        except botocore.exceptions.ClientError as e:
            logger.critical(f"Error retrieving secret metadata {secret_arn}: {e.response['Error']['Message']}")
        return last_rotated, next_rotation

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
        now = datetime.datetime.now(datetime.timezone.utc)
        for secret in self.secret_metadata:
            next_rotation = secret.get('next_rotation')
            if next_rotation is not None and now < next_rotation:
                logger.debug(f"Secret {secret['type']} is still cached (next rotation: {next_rotation}).")
            else:
                logger.info(f"Secret {secret['type']} is due for rotation check. Refreshing secret data...")
                last_rotated, next_rotation = self._get_secret_rotation_dates(secret['arn'])
                secret['last_rotated'] = last_rotated
                secret['next_rotation'] = next_rotation
                self.refresh_secret_data(secret)
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