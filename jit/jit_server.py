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

def verify_user(user_jwt):
    headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + user_jwt,
    }    
    domino_host = os.environ.get(
        "DOMINO_USER_HOST", "http://nucleus-frontend.domino-platform:80"
    )
    endpoint = f"{domino_host}/v4/auth/principal"
    resp = requests.get(endpoint, headers=headers)
    headers['Authorization'] = "Bearer REDACTED"
    logger.info(f"Nucleus response: url {domino_host}, response_code {resp.status_code}, headers {json.dumps(headers)}, response {resp.json()}")
    user_is_anon = resp.json()['isAnonymous']
    if not user_is_anon:
        return True
    else:
        headers['Authorization'] = "Bearer REDACTED"
        logger.info(f"Nucleus returned non-200 response: url {domino_host}, response_code {resp.status_code}, headers {headers}, response {resp.json()}")
        return False

def create_new_sessions(user_id:str,user_mail:str,user_group_list:[]) -> []:
    key_list = ['eventType','applicationShortName','lifecycle','projectName','userId','userEmail']
    ug_list = [ ug for ug in user_group_list if 'POLICY-MANAGER' not in ug ] # Any group name with "POLICY-MANAGER" in it can be filtered per PT.
    user_project_data = []
    user_session_list = []
    for group_name in ug_list:
        prj_split = group_name.split("-")
        session = { key:None for key in key_list }
        session['applicationShortName'] = prj_split[4]
        session['lifecycle'] = prj_split[2] + "-" + prj_split[3]
        session['eventType'] = 'createJitProjectSession'
        session['projectName'] = prj_split[-1]
        session['userId'] = user_id
        session['userEmail'] = user_mail
        user_project_data.append(session)
    
    logger.info(f"Body data to send to JIT API: {user_project_data}")
    for project in user_project_data:
        session = client.put_sessions(project)
        user_session_list.append(session.json())
    
    return user_session_list

@app.route('/jit-sessions', methods=['GET'])
def jit_aws_credentials(project=None,user_jwt=None):
    user_jwt = user_jwt or request.headers['Authorization'].split()[1]
    if verify_user(user_jwt):
        user = jwt.decode(user_jwt,options={"verify_signature": False})
        if project:
           user[constants.fm_projects_attribute] = [project]
        logger.info(f'Fetching Credentials for user: {user["preferred_username"]}')
        user_id = user['preferred_username']
        user_mail = user['email']
        session_list = create_new_sessions(user_id=user_id,user_mail=user_mail,user_group_list=user[constants.fm_projects_attribute])
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
