import sys,flask,os,json,random,requests,logging,string
from flask import request
from datetime import datetime,timedelta
app = flask.Flask(__name__)
app.config["DEBUG"] = True

user_sessions = {}
# session_file = os.environ.get("JIT_SESSION_FILE",'/app/jit_sessions.json')
# aws_creds_file = os.environ.get("JIT_CREDS_FILE",'/app/aws_creds.json')
cred_lifetime_seconds = int(os.environ.get("CRED_LIFETIME",3600))
logger = logging.getLogger('jit_mock_server')
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

# def get_user_name(headers):
#     domino_host = os.environ.get(
#         "DOMINO_USER_HOST", "http://nucleus-frontend.domino-platform:80"
#     )
#     endpoint = f"{domino_host}/v4/auth/principal"
#     resp = requests.get(endpoint, headers=headers)
#     if resp.status_code == 200:
#         user = resp.json()["canonicalName"]
#         logger.debug(f"Username: {user}")
#         return user
#     else:
#         return ''


def get_aws_credentials(session_id,project_name):
    # I've hard-coded the expire time as current + 1h.
    expire_time = datetime.now().astimezone() + timedelta(seconds=cred_lifetime_seconds)
    data = {}
    data['accessKeyId'] = ''.join(random.choices(string.ascii_uppercase, k=22))
    data['secretAccessKey'] = ''.join(random.choices(string.ascii_letters + string.digits, k=40))
    data['sessionToken'] = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    data['session_id'] = session_id
    data['expiration'] = expire_time.isoformat()
    data['projects'] = [project_name] or ['default']
    return data

def create_jit_user_session(user_data):
    key_list = ['active','alias','sub','userId','creationTime','expirationTime','session_id']
    session = { key:None for key in key_list}
    session['active'] = 'true'
    session['sub'] = user_data['userId']
    session['userId'] = user_data['userId']
    session['project'] = user_data['projectName']
    session['creationTime'] = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S%z')
    session_expiry = datetime.now().astimezone() + timedelta(hours=1)
    session['expirationTime'] = session_expiry.strftime('%Y-%m-%d %H:%M:%S%z')
    session_uid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    group_short = user_data.get('applicationShortName',''.join(random.choices(string.ascii_uppercase, k=3)))
    session['session_id'] = f'jit-{user_data["userId"]}-{group_short}-{session_uid}'
    session['aws_creds'] = []
    return session

# Add'l route below based on ../jit/client/resources/sessions.py
@app.route('/jit-sessions', methods=['GET'])
@app.route('/infrastructure/management/provisioning/aws-jit-provisioning/jit-sessions',methods=['GET'])
def get_jit_sessions():
    domino_user_name = request.args.get('sub') # Ref: ../jit/client/resources/sessions.py
    user_project = request.args.get('project')
    logger.debug(f'Fetching JIT Sessions for Domino User {domino_user_name}')
    # with open(session_file) as db_file:
    #     data = json.load(db_file)
    user_sessions = [session for session in user_sessions if session['userId'] == domino_user_name and session['project'] == user_project]
    return user_sessions

@app.route('/infrastructure/management/provisioning/aws-jit-provisioning/jit-sessions/<jit_session_id>',methods=['GET'])
def get_jit_sessions_by_id(jit_session_id):
    domino_user_name = request.args.get('sub') # Ref: ../jit/client/resources/sessions.py
    logger.debug(f'Fetching JIT Sessions for Domino User {domino_user_name}')
    # with open(session_file) as db_file:
    #     data = json.load(db_file)
    user_sessions = [session for session in user_sessions if session['session_id'] == jit_session_id]
    return user_sessions

@app.route('/infrastructure/management/provisioning/aws-jit-provisioning/jit-sessions/<jit_session_id>/aws-credentials',methods=['GET'])
def get_jit_aws_creds(jit_session_id,jit_project=None):
    global user_sessions,aws_creds
    logger.debug(f'Fetching AWS Credentials for session {jit_session_id}')
    # with open(aws_creds_file) as cred_db_file:
    #     cred_data = json.load(cred_db_file)
    user_aws_creds = user_sessions[jit_session_id]['aws_creds'][0] # We're expecting only one credential per session, and only want to return one credential per session-id call
    logger.debug(f"User AWS Creds: {user_aws_creds}")
    return user_aws_creds

@app.route('/infrastructure/management/provisioning/aws-jit-provisioning/jit-sessions',methods=['POST'])
def new_jit_session():
    # Expected JSON data: 
    # {
    # "eventType":"createJitProjectSession",
    # "applicationShortName": str,
    # "lifecycle": str,
    # "projectName": str,
    # "userId": str,
    # "userEmail": str
    # }    
    user_data = request.get_json()
    logger.debug(f'Creating JIT Session for Domino User {user_data["userId"]} with Project {user_data["projectName"]}')
    new_user_session = create_jit_user_session(user_data)
    session_id = new_user_session['session_id']
    global user_sessions
    user_sessions.update({session_id:new_user_session})
    user_session_cred = get_aws_credentials(session_id=new_user_session['session_id'],project_name=new_user_session['project'])
    user_sessions[session_id]['aws_creds'].append(user_session_cred)
    # Per FM/PT, a POST to this endpoint doesn't return a JIT session, but rather the AWS credentials for the JIT session.
    session_aws_creds = get_jit_aws_creds(jit_session_id=new_user_session['session_id'],jit_project=new_user_session['project'])
    return session_aws_creds

# Based on https://www.pingidentity.com/content/dam/developer/downloads/Resources/OAuth2%20Developers%20Guide%20(1).pdf
@app.route('/this_isnt_a_pingfed_token',methods=['GET','POST'])
def get_not_really_a_pingfed_oauth_token():
    key_list = ['access_token','token_type','expires_in','refresh_token']
    session = { key:None for key in key_list }
    session['token_type'] = 'Bearer'
    session['expires_in'] = 28800 # 8h pseudo-token expiry
    session['access_token'] = ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))
    session['refresh_token'] = random.randrange(1,10000)
    return session

@app.route('/healthz', methods=['GET'])
def healthz():
    return "healthy"


if __name__ == '__main__':
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(debug=True, host='0.0.0.0',port=os.environ.get('APP_PORT',8080))
