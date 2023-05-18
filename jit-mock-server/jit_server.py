import sys
import flask
import os
from flask import  request
import json
import random
import requests
import logging

app = flask.Flask(__name__)
app.config["DEBUG"] = True

log_file = os.environ.get("JIT_LOG_FOLDER", "/var/log/jit/") + 'app.log'
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
    data['accessKeyId'] = str(random.randint(1,10))
    data['secretAccessKey'] = str(random.randint(1,10))
    data['sessionToken'] = str(random.randint(1,10))
    data['expiration'] = str('0')
    return data

@app.route('/jit-sessions', methods=['GET'])
def get_jit_sessions():
    domino_user_name = get_user_name(request.headers)
    logger.debug(f'Fetching JIT Sessions for Domino User {domino_user_name}')
    data = json.load(open('/app/jit_sessions.json'))
    result = {}
    for jit in data:
        jit_session_id = jit['jitSessionId']
        result[jit_session_id] = get_aws_credentials(jit['jitSessionId'])
    return {'domino_user':domino_user_name, 'jit-sessions':result}

@app.route('/healthz', methods=['GET'])
def healthz():
    return "healthy"


if __name__ == '__main__':
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(debug=True, host='0.0.0.0',port=os.environ.get('PORT_NO',80))
