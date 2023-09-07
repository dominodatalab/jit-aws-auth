import os
import json

jit_config_file = os.environ.get('JIT_CONFIG_FILE', '/etc/config/jit-config/jit.json')
jit_config = {}

with open(jit_config_file, 'r') as f:
    jit_config = json.load(f)
# Retrieve settings
jit_endpoint = jit_config['jit_endpoint']

ping_cred_file = os.environ.get('PING_CREDENTIAL_FILE','/etc/config/jit-secret/ping-client')
with open(ping_cred_file,'r') as f:
    client_secret = json.load(f)['client_secret']
    client_id = json.load(f)['client_id']
    token_endpoint = json.load(f)['auth-server-url']

nuid_cred_file = os.environ.get('NUID_CREDENTIAL_FILE','/etc/config/jit-secret/nuid')
with open(nuid_cred_file,'r') as f:
    r_username = json.load(f)['username']
    r_password = json.load(f)['password']

access_token_expiry_time = float(jit_config['minimum_token_validity_required_in_seconds'])
minimum_token_validity_required_in_seconds = int(jit_config['minimum_token_validity_required_in_seconds'])
fm_projects_attribute = jit_config['prj_attribute_name']
certificate_path = os.environ.get('JIT_CERT_FILE','/etc/config/jit-config/ca.crt')

def to_debug():
    return jit_config