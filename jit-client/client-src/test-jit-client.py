#!/usr/bin/env python3

import os,requests,json,jwt

aws_credentials_file = 'jit-credfile/credentials'
token_endpoint = os.environ.get('DOMINO_API_PROXY')
jit_proxy_endpoint = os.environ.get('DOMINO_JIT_ENDPOINT')
access_token_endpoint = token_endpoint + "/access-token"
domino_host = os.environ.get("DOMINO_USER_HOST", "http://nucleus-frontend.domino-platform:80")
val_token_endpoint = endpoint = f"{domino_host}/v4/auth/principal"

print (f"Pulling User JWT from {token_endpoint}")
token_resp = requests.get(access_token_endpoint)

print("Testing User JWT validity...")
headers = { "Content-Type": "application/json", "Authorization": "Bearer " + token_resp.text, }
auth_val_req = requests.get(val_token_endpoint,headers=headers)
if (auth_val_req.status_code == 200):
    print("User JWT is valid!") 
else:
    print("User JWT rejected by Nucleus!")

print(f"Nucleus response for User JWT:\n {auth_val_req.text}")

user_jwt = jwt.decode(token_resp.text,options={"verify_signature": False})

print(f"User JWT contents:\n {user_jwt}")

print("Gathering User project list from JIT Proxy...")

jit_proxy_groups_endpoint = jit_proxy_endpoint.rpartition('/')[0] + '/user-projects'

user_group_list = requests.get(jit_proxy_groups_endpoint,headers=headers)

print(f"User project list: {user_group_list.json()}")