from Util.db import permission_db
from flask_login import current_user
import random
import string


def init_permission(username):
    permission_db.insert_one(
        {
            "username": username,
            "role": 1,
            "person": [],
            "group": [],
            "key": generate_key(),
        }
    )


def get_permission(username):
    return permission_db.find_one({"username": username}, {"_id": 0})


def update_permission(username, permission):
    permission_db.update_one({"username": username}, {"$set": permission})


def check_person_permission(person):
    perm = get_current_permission()
    return check_per_person_permission(perm, person)


def check_per_person_permission(perm, person):
    if perm["role"] == 0:
        return True
    if not isinstance(person, list):
        person = [person]
    for qq in person:
        if qq not in perm["person"]:
            return False
    return True


def check_group_permission(group):
    perm = get_current_permission()
    return check_per_person_permission(perm, group)


def check_per_group_permission(perm, group):
    if perm["role"] == 0:
        return True
    if not isinstance(group, list):
        group = [group]
    for qq in group:
        if qq not in perm["group"]:
            return False
    return True


def get_current_permission():
    user = current_user
    if not user.is_authenticated:
        return None
    perm = get_permission(user.username)
    return perm


def generate_key():
    return "".join(
        random.SystemRandom().choice(string.ascii_lowercase + string.digits)
        for _ in range(32)
    )
