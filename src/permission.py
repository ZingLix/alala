from Util.db import permission_db
from flask_login import current_user


def init_permission(username):
    permission_db.insert_one(
        {"username": username, "role": 1, "person": [], "group": []}
    )


def get_permission(username):
    return permission_db.find_one({"username": username}, {"_id": 0})


def update_permission(username, permission):
    permission_db.update_one({"username": username}, {"$set": permission})


def get_current_permission():
    user = current_user
    perm = get_permission(user.username)
    return perm
