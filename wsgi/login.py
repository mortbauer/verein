import bcrypt
from functools import wraps
from flask import Blueprint, current_app,request, session, Response,g
from utils import send_response


mod = Blueprint('login', __name__, url_prefix='/login')

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def check_valid_auth():
    if not session.get('user_id'):
        return authenticate()
    else:
        g.user = current_app.db.users.find_one({'user_id':session['user_id']})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        check_valid_auth()
        return f(*args, **kwargs)
    return decorated

@mod.route("/", methods=["GET", "POST"])
def login():
    if session.get('user_id'):
        return send_response({'message':'you are already logged in'})
    auth = request.authorization
    if auth:
        username =  auth.username
        password = auth.password
        user = current_app.db.users.find_one({'username':username})
        if user:
            if current_app.bcrypt.check_password_hash(user['password'], password):
                session['user_id'] = user['user_id']
                return send_response({'message':'login successful'})
            else:
                return send_response({'message':'wrong passphrase'},status=400)
        else:
            if not username:
                return send_response({'message':'provide a username'},status=400)
            else:
                return send_response({'message':'unknown user "{0}"'.format(username)},status=400)
    else:
        return send_response({'message':'username and password required'},status=400)


