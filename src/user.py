import flask
from flask import json
import flask_login
from flask_login.utils import login_required, login_user, logout_user
from Util.db import user_db
from bson import ObjectId
from flask import Blueprint, request
from flask_cors import cross_origin

login_manager = flask_login.LoginManager()
user_bp = Blueprint("user", __name__, url_prefix="/api/user")


def register_user_module(app):
    login_manager.init_app(app)
    app.register_blueprint(user_bp)


class User(flask_login.UserMixin):
    def __init__(self, user) -> None:
        super().__init__()
        self.id = user["username"]
        self.username = user["username"]


def query_user(username):
    return user_db.find_one({"username": username})


@login_manager.user_loader
def user_loader(username):
    user = query_user(username)
    if user is None:
        return user
    return User(user)


@user_bp.route("/login", methods=['POST'])
def login():
    recv = request.json
    username = recv["username"]
    password = recv["password"]
    user = query_user(username)
    if user is not None and user["password"] == password:
        user_entity = User(user)
        login_user(User(user))
        return json.dumps({"status": "success"})
    return json.dumps({"status": "error", "type": "user"})


@user_bp.route("/logout", methods=['POST'])
@login_required
def logout():
    logout_user()
    return json.dumps({"status": "success"})


@user_bp.route("/", methods=['GET'])
@login_required
def current_user():
    user = flask_login.current_user
    if user is None:
        return 403
    return json.dumps({"username": user.get_id()})


@user_bp.route("/register", methods=['POST'])
def register():
    recv = request.json
    username = recv["username"]
    password = recv["password"]
    user = query_user(username)
    if user is None:
        user_db.insert_one({"username": username, "password": password})
        return

    return json.dumps({"error": "The username has been registered"}), 400


@user_bp.after_request
def after_request(response):
    header = response.headers
    header['Access-Control-Allow-Credentials'] = 'True'
    return response
