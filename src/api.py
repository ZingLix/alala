import json
from flask import Flask, request
from flask_cors import CORS
from bson import ObjectId
import requests
from Util.db import rule_db, keywords_db, bili_mtr_db
from rule import keywords, update_keywords_list, update_rules
from qqbot import send, get
from user import register_user_module
from flask_login import login_required
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(16)
register_user_module(app)
CORS(app)


@app.route("/api/rules/", methods=["POST"], strict_slashes=False)
@login_required
def add_postprocess_file():
    id = str(rule_db.insert_one(request.json).inserted_id)
    update_rules()
    return json.dumps({"_id": id})


@app.route("/api/rules/<rule_id>", methods=["POST"], strict_slashes=False)
@login_required
def update_postprocess_file(rule_id):
    rule_db.update_one({"_id": ObjectId(rule_id)}, {"$set": request.json})
    update_rules()
    return json.dumps({"status": "success"})


@app.route("/api/rules/<rule_id>", methods=["DELETE"], strict_slashes=False)
@login_required
def delete_postprocess_file(rule_id):
    rule_db.delete_one({"_id": ObjectId(rule_id)})
    update_rules()
    return json.dumps({"status": "success"})


@app.route("/api/rules/", methods=["GET"], strict_slashes=False)
@login_required
def get_postprocess_file():
    res = []
    for item in rule_db.find():
        item["_id"] = str(item["_id"])
        res.append(item)

    return json.dumps(res)


@app.route("/api/keywords/", methods=["GET"], strict_slashes=False)
@login_required
def get_keywords():
    res = []
    for item in keywords_db.find():
        item["_id"] = str(item["_id"])
        res.append(item)

    return json.dumps(res)


@app.route("/api/keywords/", methods=["POST"], strict_slashes=False)
@login_required
def add_keywords():
    id = str(keywords_db.insert_one(request.json).inserted_id)
    update_keywords_list()
    return json.dumps({"_id": id})


@app.route("/api/keywords/<keyword_id>", methods=["POST"], strict_slashes=False)
@login_required
def update_keywords(keyword_id):
    keywords_db.update_one({"_id": ObjectId(keyword_id)}, {
                           "$set": request.json})
    update_keywords_list()
    return json.dumps({"status": "success"})


@app.route("/api/keywords/<keyword_id>", methods=["DELETE"], strict_slashes=False)
@login_required
def delete_keywords(keyword_id):
    keywords_db.delete_one({"_id": ObjectId(keyword_id)})
    update_keywords_list()
    return json.dumps({"status": "success"})


@app.route("/api/send_group/", methods=["POST"], strict_slashes=False)
@login_required
def remote_send_group_msg():
    recv_req = request.json
    send("sendGroupMessage", {"target": recv_req["target"], "messageChain": [
         {"type": "Plain", "text": recv_req["message"]}]})
    return json.dumps({"status": "success"})


@app.route("/api/send/", methods=["POST"], strict_slashes=False)
@login_required
def remote_send_personal_msg():
    recv_req = request.json
    send("sendFriendMessage", {"target": recv_req["target"], "messageChain": [
         {"type": "Plain", "text": recv_req["message"]}]})
    return json.dumps({"status": "success"})


@app.route("/api/groups", methods=["GET"])
@login_required
def group_list():
    group = get("groupList")
    return json.dumps(group['data'])


@app.route("/api/friends", methods=["GET"])
@login_required
def friend_list():
    group = get("friendList")
    return json.dumps(group['data'])


@app.route("/api/bili_monitor", methods=["GET"])
@login_required
def get_bili_mtr():
    res = []
    for item in bili_mtr_db.find():
        item["_id"] = str(item["_id"])
        res.append(item)
    return json.dumps(res)


@app.route("/api/bili_monitor/<rule_id>", methods=["POST"], strict_slashes=False)
@login_required
def update_bili_mtr(rule_id):
    bili_mtr_db.update_one({"_id": ObjectId(rule_id)}, {"$set": request.json})
    return json.dumps({"status": "success"})


@app.route("/api/bili_monitor/<rule_id>", methods=["DELETE"], strict_slashes=False)
@login_required
def delete_bili_mtr(rule_id):
    bili_mtr_db.delete_one({"_id": ObjectId(rule_id)})
    return json.dumps({"status": "success"})


@app.route("/api/bili_monitor/", methods=["POST"], strict_slashes=False)
@login_required
def add_bili_mtr():
    rule = request.json
    bid = rule['uid']
    user_info = requests.get(
        "https://api.bilibili.com/x/space/acc/info?mid={}&jsonp=jsonp".format(bid)).json()['data']['name']
    rule['name'] = user_info
    id = str(bili_mtr_db.insert_one(rule).inserted_id)
    return json.dumps({"_id": id})
