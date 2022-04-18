from Util.db import rule_db, keywords_db, bili_mtr_db, unrelated_db
import logging

rule_list = []
keywords_list = []
filter_sentence_set = set()


def init():
    update_rules()
    update_keywords_list()
    update_filter_sentence_set()


def update_rules():
    global rule_list
    rule_list = []
    for item in rule_db.find():
        if not item["disabled"]:
            rule_list.append(item)
    rule_list.sort(key=lambda x: x["priority"], reverse=True)
    logging.info("Rule list updated")


def update_keywords_list():
    global keywords_list
    keywords_list = []
    for item in keywords_db.find():
        if not item["disabled"]:
            keywords_list.append(item)
    logging.info("Keywords list updated")


def update_filter_sentence_set():
    global filter_sentence_set
    filter_sentence_set = set()
    for item in unrelated_db.find():
        filter_sentence_set.add(item["text"])
    logging.info("Filter sentence set updated")


def bili_mtr_list():
    mtr_list = []
    for item in bili_mtr_db.find():
        if not item["disabled"]:
            mtr_list.append(item)
    return mtr_list


def rules():
    return rule_list


def keywords():
    return keywords_list


def filter_sentence():
    return filter_sentence_set
