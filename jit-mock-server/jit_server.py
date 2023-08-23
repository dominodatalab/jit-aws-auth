import sys
import flask
import os
from flask import  request
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


def get_aws_credentials(jit_session_id):
    data = json.load(open('/app/aws_creds.json'))
    # I've hard-coded the expire time as current + 1h.
    expire_time = datetime.now().astimezone() + timedelta(hours=1)
    data['Status'] = 'Success'
    data['accessKeyId'] = str(random.randint(1,10))
    data['secretAccessKey'] = str(random.randint(1,10))
    data['sessionToken'] = str(random.randint(1,10))
    data['expiration'] = expire_time.strftime('%Y-%m-%d %H:%M:%S%z')
    data['projects'] = ['domino1']
    data['session_id'] = jit_session_id
    return data

def create_user_session(username):
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


@app.route('/jit-sessions', methods=['GET'])
def get_jit_sessions():
    domino_user_name = get_user_name(request.headers)
    logger.debug(f'Fetching JIT Sessions for Domino User {domino_user_name}')
    db_file = open(session_file,'r+')
    data = json.load(db_file)
    user_sessions = [session['userId'] for session in data]
    if domino_user_name not in user_sessions:
        new_user_session = create_user_session(domino_user_name)
        data.append(new_user_session)
        db_file.write(json.dumps(data))

    result = {}
    for jit in data:
        jit_session_id = jit['session_id']
        result[jit_session_id] = get_aws_credentials(jit['session_id'])
    return {'domino_user':domino_user_name, 'jit-sessions':result}

@app.route('/healthz', methods=['GET'])
def healthz():
    return "healthy"


if __name__ == '__main__':
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(debug=True, host='0.0.0.0',port=os.environ.get('PORT_NO',8080))
