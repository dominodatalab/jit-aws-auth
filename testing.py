import os,requests,json,jwt
aws_credentials_file = 'jit-credfile/credentials'
token_endpoint = os.environ.get('DOMINO_API_PROXY')
access_token_endpoint = token_endpoint + "/access-token"
# val_token_endpoint = 'http://nucleus-frontend.domino-platform:80/v4/auth/principal'
domino_host = os.environ.get("DOMINO_USER_HOST", "http://nucleus-frontend.domino-platform:80")
val_token_endpoint = endpoint = f"{domino_host}/v4/auth/principal"
token_resp = requests.get(access_token_endpoint)
jwt.decode(token_resp.text,options={"verify_signature": False})
headers = { "Content-Type": "application/json", "Authorization": "Bearer " + token_resp.text, }
auth_val_req = requests.get(val_token_endpoint,headers=headers)
auth_val_req.text
jit_ep = 'http://jit-svc.domino-field/jit-sessions'
jit_req = requests.get(jit_ep,headers=headers,verify=False)
mock_ep = 'http://jit-svc-mock.domino-field/infrastructure/management/provisioning/aws-jit-provisioning/jit-sessions'