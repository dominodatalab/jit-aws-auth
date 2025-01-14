#!/usr/bin/env python
import logging,sys,os,jwt,requests,json,flask,datetime
from flask import Flask,request,abort
from datetime import datetime

loglevel = os.environ.get("LOG_LEVEL","INFO").upper()
# We want to use the same logger object as the JIT client,
# so we need to set it up before importing the client module.
logger = logging.getLogger('jit_proxy_server')
logging.basicConfig(
    level=loglevel,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
from client import JitAccessEngineClient,constants

# Create a Flask application
app = Flask(__name__)

def create_app():
    global app,client
    client = JitAccessEngineClient()
    # Set up logging
    return app

def check_update_jit_client():
    now = datetime.now()
    global client
    if client._access_token_expiry_time and client._access_token_expiry_time < now:
        logger.info("JIT Client OAuth token expired. Refreshing...")
        client = JitAccessEngineClient()

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
    logger.debug(f"User group list: {ug_list}")
    user_project_data = []
    user_session_list = []
    for group_name in ug_list:
        prj_split = group_name.split("-")
        session = { key:None for key in key_list }
        session['applicationShortName'] = prj_split[4]
        lc_tmp = prj_split[2] + "-" + prj_split[3]
        session['lifecycle'] = lc_tmp.lower() # Per PT
        session['eventType'] = 'createJitProjectSession'
        session['projectName'] = prj_split[-1].lower() # Per PT
        session['userId'] = user_id
        session['userEmail'] = user_mail
        user_project_data.append(session)
    
    logger.info(f"Body data to send to JIT API: {user_project_data}")
    for project in user_project_data:
        session = client.put_sessions(project)
        logger.debug(f"JIT API Response for {project}: {session.json()}")
        if session.status_code == 200:
            user_session_list.append(session.json())
    
    return user_session_list

@app.route('/jit-sessions', methods=['GET'])
def jit_aws_credentials(project=None,user_jwt=None):
    check_update_jit_client()
    user_token = user_jwt or request.headers['Authorization'].split()[1]
    if verify_user(user_token):
        user = jwt.decode(user_token,options={"verify_signature": False})
        if project:
           # Note: we must send the group names as lower-cased to the JIT API (and we write them as lower-cased on the client side),
           # but they are present as upper-cased in the user JWT.
           user[constants.fm_projects_attribute] = [grp_name for grp_name in user[constants.fm_projects_attribute] if project.upper() in grp_name]
        logger.info(f'Fetching Credentials for user: {user["preferred_username"]}')
        user_id = user['preferred_username']
        user_mail = user['email']
        session_list = create_new_sessions(user_id=user['preferred_username'],user_mail=user['email'],user_group_list=user[constants.fm_projects_attribute])
        return session_list
    else:
        abort(401,description="Invalid User JWT")

@app.route('/jit-sessions/<project>', methods=['GET'])
def jit_aws_credential_by_project(project):
    check_update_jit_client()
    user_jwt = request.headers['Authorization'].split()[1]
    new_credential = jit_aws_credentials(project=project,user_jwt=user_jwt)
    # Note: while the /jit-sessions URL returns a list of all of the credentials for a given user, this
    # endpoint will return only a single credential dict based on the project value.
    return new_credential[0]

@app.route('/jit-sessions-dummy', methods=['GET'])
def jit_aws_credentials_dummy(project=None,user_jwt=None):
    check_update_jit_client()
    user_token = user_jwt or request.headers['Authorization'].split()[1]
    if loglevel != "DEBUG":
        abort(401,description="Endpoint not available in non-DEBUG mode")
    if verify_user(user_token):
        user = jwt.decode(user_token,options={"verify_signature": False})
        user[constants.fm_projects_attribute] = ['sg-jit-prod-abcd-efg-prj-domino1','sg-jit-prod-abcd-efg-prj-domino2']
        logger.info(f'Fetching Credentials for user: {user["preferred_username"]}')
        session_list = create_new_sessions(user_id=user['preferred_username'],user_mail=user['email'],user_group_list=user[constants.fm_projects_attribute])
        return session_list
    else:
        abort(401,description="Invalid User JWT")

@app.route('/jit-sessions-dummy/<project>', methods=['GET'])
def jit_aws_credential_by_project_dummy(project):
    check_update_jit_client()
    user_jwt = request.headers['Authorization'].split()[1]
    new_credential = jit_aws_credentials_dummy(project=project,user_jwt=user_jwt)
    # Note: while the /jit-sessions URL returns a list of all of the credentials for a given user, this
    # endpoint will return only a single credential dict based on the project value.
    return new_credential[0]

@app.route('/user-projects', methods=['GET'])
def jit_groups(user_jwt=None):
    check_update_jit_client()
    user_token = user_jwt
    if verify_user(user_token):
        user = jwt.decode(user_token,options={"verify_signature": False})
        try:
            group_list = user[constants.fm_projects_attribute] = [grp_name for grp_name in user[constants.fm_projects_attribute] if project.upper() in grp_name]
        except KeyError:
            group_list = []
        return group_list
    else:
        abort(401,description="Invalid User JWT")


@app.route('/healthz', methods=['GET'])
def healthz():
    return {}

@app.route('/test', methods=['GET'])
def test():
    if loglevel == "DEBUG":
        return constants.to_debug()
    else:
        return {}

if __name__ == "__main__":
    debug: bool = True
    port = 5000
    print(f"Debug mode:{debug}")
    create_app().run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=port,
        debug=debug
    )