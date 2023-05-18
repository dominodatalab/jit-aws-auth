import os
import json

jit_config_file = os.environ.get('JIT_CONFIG_FILE', '/etc/config/jit/jit.json')
jit_config = {}

with open(jit_config_file, 'r') as f:
    jit_config = json.load(f)
# Retrieve settings
jit_endpoint = jit_config['jit_endpoint']

token_endpoint = jit_config['token_endpoint']
client_id = jit_config['client_id']
client_secret = jit_config['client_secret']
r_username = jit_config['r_username']
r_password = jit_config['r_password']
access_token_expiry_time = float(jit_config['minimum_token_validity_required_in_seconds'])
certificate_path = os.environ.get('JIT_CERT_FILE','/etc/config/jit/certificate.cer')

def to_debug():
    return jit_config