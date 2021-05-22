from Util.db import rule_db, keywords_db, bili_mtr_db

rule_list = []
keywords_list = []


def update_rules():
    global rule_list
    rule_list = []
    for item in rule_db.find():
        if not item["disabled"]:
            rule_list.append(item)
    rule_list.sort(key=lambda x: x["priority"], reverse=True)


def update_keywords_list():
    global keywords_list
    keywords_list = []
    for item in keywords_db.find():
        if not item["disabled"]:
            keywords_list.append(item)


def bili_mtr_list():
    mtr_list = []
    for item in bili_mtr_db.find():
        if not item['disabled']:
            mtr_list.append(item)
    return mtr_list


def rules():
    return rule_list


def keywords():
    return keywords_list
