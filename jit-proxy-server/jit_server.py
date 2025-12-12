#!/usr/bin/env python
import logging,sys,os,jwt,requests,json,flask,datetime
from flask import Flask,request,abort
from datetime import datetime
from json.decoder import JSONDecodeError
from concurrent.futures import ThreadPoolExecutor, as_completed

loglevel = os.environ.get("LOG_LEVEL","INFO").upper()
dummy_mode = bool(os.environ.get("TESTING_MODE","false").lower())
dummy_groups = ['sg-jit-prod-abcd-efg-prj-domino1','sg-jit-prod-abcd-efg-prj-domino2','sg-jit-prod-abcd-efg-prj-other','sg-jit-prod-abcd-efg-prj-domino3'] if dummy_mode else None
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

# Maximum number of parallel requests to the upstream JIT API
MAX_PARALLEL_REQUESTS = int(os.environ.get("JIT_MAX_PARALLEL_REQUESTS", 30))

def create_app():
    global app,client
    client = JitAccessEngineClient()
    # Set up logging
    return app

def check_update_jit_client():
    global client
    client.refresh_jit_access_token()

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

def fetch_session(project: dict) -> dict:
    """
    Fetch a single JIT session from the upstream API.

    Args:
        project: Dict containing project session request payload

    Returns:
        Dict containing session credentials if successful, None otherwise
    """
    try:
        session = client.put_sessions(project)
        logger.debug(f"JIT API Response for {project}: {session.json()}")
        if session.status_code == 200:
            return session.json()
        else:
            logger.warning(f"Upstream API returned {session.status_code} for project {project['projectName']}: {session.text}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error calling upstream API for project {project['projectName']}: {e}")
        return None
    except (KeyError, JSONDecodeError) as e:
        logger.error(f"Invalid response from upstream API for project {project['projectName']}: {e}")
        return None

def create_new_sessions(user_id:str,user_mail:str,user_group_list:[]) -> []:
    key_list = ['eventType','applicationShortName','lifecycle','projectName','userId','userEmail']
    ug_list = [ ug for ug in user_group_list if 'POLICY-MANAGER' not in ug ] # Any group name with "POLICY-MANAGER" in it can be filtered per PT.
    logger.debug(f"User group list: {ug_list}")
    user_project_data = []
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

    # Execute all upstream calls in parallel
    user_session_list = []
    num_workers = min(len(user_project_data), MAX_PARALLEL_REQUESTS)
    if num_workers > 0:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(fetch_session, project): project for project in user_project_data}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    user_session_list.append(result)

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
           user[constants.fm_projects_attribute] = [grp_name for grp_name in user[constants.fm_projects_attribute] if project.upper() == grp_name.split("-")[-1]]
        logger.info(f'Fetching Credentials for user: {user["preferred_username"]}')
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
    if len(new_credential) == 0:
        abort(503, description=f"Failed to retrieve credentials for project {project} from upstream API")
    return new_credential[0]

@app.route('/jit-sessions-parallel', methods=['GET'])
def jit_aws_credentials_parallel(user_jwt=None):
    check_update_jit_client()
    user_token = user_jwt or request.headers['Authorization'].split()[1]
    if verify_user(user_token) and request.is_json and isinstance(request.json.get('projects'), list):
        user = jwt.decode(user_token,options={"verify_signature": False})
        project_list = []
        for proj in request.json['projects']:
            for grp_name in user[constants.fm_projects_attribute]:
                if proj.upper() == grp_name.split("-")[-1]:
                    project_list.append(grp_name)
        # if project:
        #    # Note: we must send the group names as lower-cased to the JIT API (and we write them as lower-cased on the client side),
        #    # but they are present as upper-cased in the user JWT.
        #    user[constants.fm_projects_attribute] = [grp_name for grp_name in user[constants.fm_projects_attribute] if project.upper() == grp_name.split("-")[-1]]
        logger.info(f'Fetching Credentials for user: {user["preferred_username"]} on projects {project_list}')
        session_list = create_new_sessions(user_id=user['preferred_username'],user_mail=user['email'],user_group_list=project_list)
        return session_list
    else:
        abort(401,description="Invalid User JWT")

@app.route('/user-projects', methods=['GET'])
def jit_groups():
    check_update_jit_client()
    user_token = request.headers['Authorization'].split()[1]
    if verify_user(user_token):
        user = jwt.decode(user_token,options={"verify_signature": False})
        try:
            group_list = user[constants.fm_projects_attribute]
        except KeyError:
            group_list = []
        return group_list
    else:
        abort(401,description="Invalid User JWT")

@app.route('/dummy/user-projects', methods=['GET'])
def jit_groups_dummy():
    global dummy_groups
    if dummy_mode:
        return dummy_groups
    else:
        abort(404,description="Endpoint not available outside of TESTING_MODE")


@app.route('/dummy/jit-sessions', methods=['GET'])
def jit_aws_credentials_dummy(project=None,user_jwt=None):
    check_update_jit_client()
    user_token = user_jwt or request.headers['Authorization'].split()[1]
    user_groups = dummy_groups
    if not dummy_mode:
        abort(404,description="Endpoint not available outside of TESTING_MODE")
    if verify_user(user_token):
        user = jwt.decode(user_token,options={"verify_signature": False})
        if project:
           # Note: we must send the group names as lower-cased to the JIT API (and we write them as lower-cased on the client side),
           # but they are present as upper-cased in the user JWT.
            user_groups = [grp_name for grp_name in user_groups if project in grp_name]
        logger.info(f'Fetching Credentials for user: {user["preferred_username"]}')
        session_list = create_new_sessions(user_id=user['preferred_username'],user_mail=user['email'],user_group_list=user_groups)
        logger.debug(f"Dummy Session List: {session_list}")
        return session_list
    else:
        abort(401,description="Invalid User JWT")

@app.route('/dummy/jit-sessions/<project>', methods=['GET'])
def jit_aws_credential_by_project_dummy(project):
    if dummy_mode:
        user_jwt = request.headers['Authorization'].split()[1]
        new_credential = jit_aws_credentials_dummy(project=project,user_jwt=user_jwt)
        # Note: while the /jit-sessions URL returns a list of all of the credentials for a given user, this
        # endpoint will return only a single credential dict based on the project value.
        if len(new_credential) == 0:
            abort(503, description=f"Failed to retrieve credentials for project {project} from upstream API")
        return new_credential[0]
    else:
        abort(404,description="Endpoint not available outside of TESTING_MODE")

@app.route('/healthz', methods=['GET'])
def healthz():
    global client
    client.refresh_secrets_data()
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