#!/usr/bin/env python
import flask
import configparser

from flask import request

from jit.utils.logging import logger
import logging
from client import JitAccessEngineClient
import sys
import os
import requests
from jit.client import constants

app = flask.Flask(__name__)
app.config["DEBUG"] = True


# initiate JIT access engine client
client = JitAccessEngineClient()
current_list_of_jit_sessions = {}
new_list_of_jit_sessions = {}

log_file = os.environ.get("JIT_LOG_FOLDER", "/var/log/jit/") + 'app.log'
lvl: str = logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO"))
logging.basicConfig(
    level=lvl,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=log_file, filemode='w'
)
logger = logging.getLogger("werkzeug")
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

def get_user_name(headers):
    domino_host = os.environ.get(
        "DOMINO_USER_HOST", "http://nucleus-frontend.domino-platform:80"
    )
    endpoint = f"{domino_host}/v4/auth/principal"
    resp = requests.get(endpoint, headers=headers)
    if resp.status_code == 200:
        return resp.json()["canonicalId"]
    else:
        return ''


def get_jit_sessions(domino_user_name:str):
    lst_of_jit_sessions = client.get_jit_sessions_by_sub(domino_user_name)
    new_list_of_jit_sessions = {}
    for jit in lst_of_jit_sessions:
        key = jit['session_id']
        jit_user = jit['userId']
        # only access jit sessions that match pod user
        if jit_user == domino_user_name:
            if not key in current_list_of_jit_sessions:
                current_list_of_jit_sessions[key] = jit
                new_list_of_jit_sessions[key] = jit
        else:
            logger.info('skipping JIT session because user=%s', jit_user)
    logger.info('new list of jit sessions', extra={'details': {'jitSessions': new_list_of_jit_sessions}})
    return new_list_of_jit_sessions


def create_new_sessions(jit_session_lst):
    config = configparser.ConfigParser()
    jit_session_keys = jit_session_lst.keys()
    for jit_session_id in jit_session_keys:
        profile_name = jit_session_lst[jit_session_id]['sessionName']
        credentials = client.get_aws_credentials(jit_session_id)
        if profile_name not in config.sections():
            logger.info('adding aws cli credentials profile',
                        extra={'details': {'profile': profile_name, 'jitSessionId': jit_session_id}})
            config.add_section(profile_name)
            config[profile_name]["aws_access_key_id"] = credentials["accessKeyId"]
            config[profile_name]["aws_secret_access_key"] = credentials["secretAccessKey"]
            config[profile_name]["aws_session_token"] = credentials["sessionToken"]
            config[profile_name]["expiration"] = credentials["expiration"]
            config[profile_name]["session_id"] = jit_session_id
    return config



@app.route('/jit-sessions', methods=['GET'])
def jit_aws_credentials():    
    user_name = get_user_name(request.headers)
    logger.info(f'Fetching Credentials for user: {user_name}')
    return create_new_sessions(get_jit_sessions(user_name))


@app.route('/healthz', methods=['GET'])
def healthz():
    return {}

@app.route('/test', methods=['GET'])
def test():
    return constants.to_debug()


if __name__ == '__main__':
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=5000,
        debug=debug,
        ssl_context=("/ssl/tls.crt", "/ssl/tls.key"),
    )
