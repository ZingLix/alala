import json
from os import abort
from flask import Flask, request
from flask_cors import CORS
from bson import ObjectId
import flask_login
import permission
import requests
from Util.db import rule_db, keywords_db, bili_mtr_db, user_db, permission_db
from rule import keywords, update_keywords_list, update_rules
from qqbot import send, get
from user import current_login_user, register_user_module
from flask_login import login_required
import secrets
from flask_login import current_user

app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(16)
register_user_module(app)
CORS(app)


@app.route("/api/rules/", methods=["POST"], strict_slashes=False)
@login_required
def add_postprocess_file():
    r = request.json
    r["creator"] = current_user.username
    id = str(rule_db.insert_one(r).inserted_id)
    update_rules()
    return json.dumps({"_id": id})


@app.route("/api/rules/<rule_id>", methods=["POST"], strict_slashes=False)
@login_required
def update_postprocess_file(rule_id):
    r = request.json
    r.pop("creator", None)
    rule_db.update_one({"_id": ObjectId(rule_id)}, {"$set": r})
    update_rules()
    return json.dumps({"status": "success"})


@app.route("/api/rules/<rule_id>", methods=["DELETE"], strict_slashes=False)
@login_required
def delete_postprocess_file(rule_id):
    rule_db.delete_one({"_id": ObjectId(rule_id), "creator": current_user.username})
    update_rules()
    return json.dumps({"status": "success"})


@app.route("/api/rules/", methods=["GET"], strict_slashes=False)
@login_required
def get_postprocess_file():
    res = []
    for item in rule_db.find({"creator": current_user.username}):
        item["_id"] = str(item["_id"])
        res.append(item)

    return json.dumps(res)


@app.route("/api/keywords/", methods=["GET"], strict_slashes=False)
@login_required
def get_keywords():
    res = []
    for item in keywords_db.find({"creator": current_user.username}):
        item["_id"] = str(item["_id"])
        res.append(item)

    return json.dumps(res)


@app.route("/api/keywords/", methods=["POST"], strict_slashes=False)
@login_required
def add_keywords():
    r = request.json
    r["creator"] = current_user.username
    id = str(keywords_db.insert_one(r).inserted_id)
    update_keywords_list()
    return json.dumps({"_id": id})


@app.route("/api/keywords/<keyword_id>", methods=["POST"], strict_slashes=False)
@login_required
def update_keywords(keyword_id):
    r = request.json
    r.pop("creator", None)
    keywords_db.update_one({"_id": ObjectId(keyword_id)}, {"$set": r})
    update_keywords_list()
    return json.dumps({"status": "success"})


@app.route("/api/keywords/<keyword_id>", methods=["DELETE"], strict_slashes=False)
@login_required
def delete_keywords(keyword_id):
    keywords_db.delete_one(
        {"_id": ObjectId(keyword_id), "creator": current_user.username}
    )
    update_keywords_list()
    return json.dumps({"status": "success"})


@app.route("/api/send_group/", methods=["POST"], strict_slashes=False)
def remote_send_group_msg():
    recv_req = request.json
    key = request.args.get("key")
    if key is None:
        perm = permission.get_current_permission()
    else:
        perm = permission_db.find_one({"key": str(key)})
    if perm is None or not permission.check_per_group_permission(
        perm, recv_req["target"]
    ):
        return json.dumps({"status": "error", "error": "no permission"}), 403
    send(
        "sendGroupMessage",
        {
            "target": recv_req["target"],
            "messageChain": [{"type": "Plain", "text": recv_req["message"]}],
        },
    )
    return json.dumps({"status": "success"})


@app.route("/api/send/", methods=["POST"], strict_slashes=False)
def remote_send_personal_msg():
    recv_req = request.json
    key = request.args.get("key")
    if key is None or key == "":
        perm = permission.get_current_permission()
    else:
        perm = permission_db.find_one({"key": str(key)})
    if perm is None or not permission.check_per_person_permission(
        perm, recv_req["target"]
    ):
        return json.dumps({"status": "error", "error": "no permission"}), 403
    send(
        "sendFriendMessage",
        {
            "target": recv_req["target"],
            "messageChain": [{"type": "Plain", "text": recv_req["message"]}],
        },
    )
    return json.dumps({"status": "success"})


@app.route("/api/groups", methods=["GET"])
@login_required
def group_list():
    group = get("groupList")
    group = group["data"]
    perm = permission.get_current_permission()
    perm_group = set(perm["group"])
    if perm["role"] != 0:
        group = [g for g in group if g["id"] in perm_group]
    return json.dumps(group)


@app.route("/api/friends", methods=["GET"])
@login_required
def friend_list():
    person = get("friendList")
    person = person["data"]
    perm = permission.get_current_permission()
    perm_person = set(perm["person"])
    if perm["role"] != 0:
        person = [g for g in person if g["id"] in perm_person]
    return json.dumps(person)


@app.route("/api/bili_monitor", methods=["GET"])
@login_required
def get_bili_mtr():
    res = []
    for item in bili_mtr_db.find({"creator": current_user.username}):
        item["_id"] = str(item["_id"])
        res.append(item)
    return json.dumps(res)


@app.route("/api/bili_monitor/<rule_id>", methods=["POST"], strict_slashes=False)
@login_required
def update_bili_mtr(rule_id):
    r = request.json
    r.pop("creator", None)
    bili_mtr_db.update_one({"_id": ObjectId(rule_id)}, {"$set": r})
    return json.dumps({"status": "success"})


@app.route("/api/bili_monitor/<rule_id>", methods=["DELETE"], strict_slashes=False)
@login_required
def delete_bili_mtr(rule_id):
    bili_mtr_db.delete_one({"_id": ObjectId(rule_id), "creator": current_user.username})
    return json.dumps({"status": "success"})


@app.route("/api/bili_monitor/", methods=["POST"], strict_slashes=False)
@login_required
def add_bili_mtr():
    rule = request.json
    rule["creator"] = current_user.username
    bid = rule["uid"]
    user_info = requests.get(
        "https://api.bilibili.com/x/space/acc/info?mid={}&jsonp=jsonp".format(bid)
    ).json()["data"]["name"]
    rule["name"] = user_info
    id = str(bili_mtr_db.insert_one(rule).inserted_id)
    return json.dumps({"_id": id})


@app.route("/api/permission/", methods=["GET"])
@login_required
def get_user_permission():
    user = flask_login.current_user
    perm = permission.get_permission(user.username)
    perm_list = []
    if perm["role"] == 0:
        for user in user_db.find():
            perm_list.append(permission.get_permission(user["username"]))
    else:
        perm_list.append(perm)
    return json.dumps(perm_list)


@app.route("/api/permission/<username>", methods=["POST"])
@login_required
def update_user_permission(username):
    perm = permission.get_current_permission()
    if perm["role"] != 0:
        return json.dumps({"status": "error", "error": "no permission"}), 403
    r = request.json
    permission.update_permission(username, {"person": r["person"], "group": r["group"]})
    return json.dumps({"status": "success"})


@app.route("/api/self_permission/", methods=["GET"])
@login_required
def get_self_permission():
    user = flask_login.current_user
    perm = permission.get_permission(user.username)
    return json.dumps(perm)


@app.route("/api/key/<username>", methods=["POST"])
@login_required
def update_key(username):
    user = flask_login.current_user
    if (
        permission.get_current_permission()["role"] != 0
        and current_user.username != username
    ):
        return json.dumps({"status": "error", "error": "no permission"}), 403
    permission_db.update_one(
        {"username": username}, {"$set": {"key": permission.generate_key()}}
    )
    return json.dumps({"status": "success"})
