#!/usr/bin/env python
import flask
import configparser

from flask import request,abort

from jit.utils.logging import logger
import logging,sys,os,jwt,requests,json
from client import JitAccessEngineClient
from jit.client import constants

app = flask.Flask(__name__)
app.config["DEBUG"] = True


# initiate JIT access engine client
client = JitAccessEngineClient()

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

def verify_user(headers:dict):
    domino_host = os.environ.get(
        "DOMINO_USER_HOST", "http://nucleus-frontend.domino-platform:80"
    )
    endpoint = f"{domino_host}/v4/auth/principal"
    resp = requests.get(endpoint, headers=headers)
    user_is_anon = resp.json()['isAnonymous']
    if not user_is_anon:
        return True
    else:
        headers['Authorization'] = "Bearer REDACTED"
        logger.info(f"Nucleus returned non-200 response: url {domino_host}, response_code {resp.status_code}, headers {headers}, response {resp.json()}")
        return False


# def get_jit_sessions(domino_user_name:str,project_name:str):
#     lst_of_jit_sessions = client.get_jit_sessions_by_sub(domino_user_name,project_name)
#     return lst_of_jit_sessions
    # new_list_of_jit_sessions = {}
    # for jit in lst_of_jit_sessions:
    #     key = jit['session_id']
    #     jit_user = jit['userId']
    #     # only access jit sessions that match pod user
    #     if jit_user == domino_user_name:
    #         if not key in current_list_of_jit_sessions:
    #             current_list_of_jit_sessions[key] = jit
    #             new_list_of_jit_sessions[key] = jit
    #     else:
    #         logger.info('skipping JIT session because user=%s', jit_user)
    # logger.info('new list of jit sessions', extra={'details': {'jitSessions': new_list_of_jit_sessions}})
    # return new_list_of_jit_sessions

# def get_session_credential(jit_session_id):
#     session_cred = client.get_aws_credentials(jit_session_id)
#     return session_cred

def create_new_sessions(user_id:str,user_mail:str,user_project_list:[]) -> []:
    key_list = ['eventType','applicationShortName','lifecycle','projectName','userId','userEmail']
    user_project_data = []
    user_session_list = []
    for project in user_project_list:
        session = { key:None for key in key_list }
        session['eventType'] = 'createJitProjectSession'
        session['projectName'] = project
        session['userId'] = user_id
        session['userEmail'] = user_mail
        user_project_data.append(session)
    
    for project in user_project_data:
        session = client.put_sessions(project)
        user_session_list.append(session.json())
    
    return user_session_list


# The configparser logic has been moved to the client. The code is left here for reference.
# def create_new_sessions(jit_session_lst):
#     config = configparser.ConfigParser()
#     jit_session_keys = jit_session_lst.keys()
#     for jit_session_id in jit_session_keys:
#         profile_name = jit_session_lst[jit_session_id]['sessionName']
#         credentials = client.get_aws_credentials(jit_session_id)
#         if profile_name not in config.sections():
#             logger.info('adding aws cli credentials profile',
#                         extra={'details': {'profile': profile_name, 'jitSessionId': jit_session_id}})
#             config.add_section(profile_name)
#             config[profile_name]["aws_access_key_id"] = credentials["accessKeyId"]
#             config[profile_name]["aws_secret_access_key"] = credentials["secretAccessKey"]
#             config[profile_name]["aws_session_token"] = credentials["sessionToken"]
#             config[profile_name]["expiration"] = credentials["expiration"]
#             config[profile_name]["session_id"] = jit_session_id
#     return config



@app.route('/jit-sessions', methods=['GET'])
def jit_aws_credentials(project=None,user_jwt=None):
    user_jwt = user_jwt or request.headers['Authorization'].split()[1]
    if verify_user(dict(request.headers)):
        user = jwt.decode(user_jwt,options={"verify_signature": False})
        if project:
           user[constants.fm_projects_attribute] = [project]
        logger.info(f'Fetching Credentials for user: {user["preferred_username"]}')
        user_id = user['preferred_username']
        user_mail = user['email']
        session_list = create_new_sessions(user_id=user_id,user_mail=user_mail,user_project_list=user[constants.fm_projects_attribute])
        return session_list
    else:
        abort(401,description="Invalid User JWT")

@app.route('/jit-sessions/<project>', methods=['GET'])
def jit_aws_credential_by_project(project):
    user_jwt = request.headers['Authorization'].split()[1]
    new_credential = jit_aws_credentials(project=project,user_jwt=user_jwt)
    return new_credential

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
        port=os.environ.get('APP_PORT',5000),
        debug=debug
    )
