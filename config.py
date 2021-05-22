from flask import Blueprint, request, copy_current_request_context, abort
import json
import os
from Util.db import db
from bson import ObjectId
from qqbot import update_rules
from flask_login import login_required

rulesApp = Blueprint("rules", __name__)
rule_db = db["rules"]


@login_required
@rulesApp.route("/", methods=["POST"], strict_slashes=False)
def add_postprocess_file():
    id = str(rule_db.insert_one(request.json).inserted_id)
    update_rules()
    return json.dumps({"_id": id})


@login_required
@rulesApp.route("/<rule_id>", methods=["POST"], strict_slashes=False)
def update_postprocess_file(rule_id):
    rule_db.update_one({"_id": ObjectId(rule_id)}, {"$set": request.json})
    update_rules()
    return json.dumps({"status": "success"})


@login_required
@rulesApp.route("/", methods=["GET"], strict_slashes=False)
def get_postprocess_file():
    res = []
    for item in rule_db.find():
        item["_id"] = str(item["_id"])
        res.append(item)

    return json.dumps(res)
