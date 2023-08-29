import sys
import flask
import os
from flask import request
import json
import random
import requests
import logging
import string
from datetime import datetime,timedelta

app = flask.Flask(__name__)
app.config["DEBUG"] = True

log_file = os.environ.get("JIT_LOG_FOLDER", "/var/log/jit/") + 'app.log'
session_file = os.environ.get("JIT_SESSION_FILE",'/app/jit_sessions.json')
aws_creds_file = os.environ.get("JIT_CREDS_FILE",'/app/aws_creds.json')
logger = logging.getLogger("jit-server")
lvl: str = logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO"))
logging.basicConfig(
    level=lvl,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=log_file, filemode='w'
)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
log = logging.getLogger("domino-jit")

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


def get_aws_credentials(session_id):
    # I've hard-coded the expire time as current + 1h.
    expire_time = datetime.now().astimezone() + timedelta(hours=1)
    data = {}
    data['Status'] = 'Success'
    data['accessKeyId'] = str(random.randint(1,10))
    data['secretAccessKey'] = str(random.randint(1,10))
    data['sessionToken'] = str(random.randint(1,10))
    data['session_id'] = session_id
    data['expiration'] = expire_time.strftime('%Y-%m-%d %H:%M:%S%z')
    data['projects'] = ['domino1']
    return data

def create_jit_user_session(username):
    key_list = ['active','alias','sub','userId','creationTime','expirationTime','session_id']
    session = { key:None for key in key_list}
    session['active'] = 'true'
    session['sub'] = username
    session['userId'] = username
    session['creationTime'] = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S%z')
    session_expiry = datetime.now().astimezone() + timedelta(hours=1)
    session['expirationTime'] = session_expiry.strftime('%Y-%m-%d %H:%M:%S%z')
    session_uid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    group_short = ''.join(random.choices(string.ascii_uppercase, k=3))
    session['session_id'] = f'jit-{username}-{group_short}-{session_uid}'
    return session

# Add'l route below based on ../jit/client/resources/sessions.py
@app.route('/jit-sessions', methods=['GET'])
@app.route('/infrastructure/management/provisioning/aws-jit-provisioning/jit-sessions',methods=['GET','POST'])
def get_jit_sessions():
    domino_user_name = request.args.get('sub') # Ref: ../jit/client/resources/sessions.py
    logger.debug(f'Fetching JIT Sessions for Domino User {domino_user_name}')
    with open(session_file) as db_file:
        data = json.load(db_file)
    if request.method == 'POST' or (request.method == 'GET' and domino_user_name not in [session['userId'] for session in data]):
        new_user_session = create_jit_user_session(domino_user_name)
        data.append(new_user_session)
        with open(session_file,'w') as db_file:
            json.dump(data,db_file,indent=4,separators=(',',': '))
        db_file.close
    user_sessions = [session for session in data if session['userId'] == domino_user_name]
    return {'domino_user':domino_user_name, 'jit-sessions':user_sessions}

@app.route('/infrastructure/management/provisioning/aws-jit-provisioning/jit-sessions/<jit_session_id>/aws-credentials',methods=['GET'])
def get_jit_aws_creds(jit_session_id):
    logger.debug(f'Fetching AWS Credentials for session {jit_session_id}')
    with open(aws_creds_file) as cred_db_file:
        cred_data = json.load(cred_db_file)
    if jit_session_id not in [session['session_id'] for session in cred_data]:
        new_aws_cred = get_aws_credentials(jit_session_id)
        cred_data.append(new_aws_cred)
        with open(aws_creds_file,'w') as cred_db_file:
            json.dump(cred_data,cred_db_file,indent=4,separators=(',',': '))
    cred_db_file.close
    aws_creds = [credential for credential in cred_data if credential['session_id'] == jit_session_id]
    return aws_creds

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
