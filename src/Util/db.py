import pymongo
import urllib.parse
import yaml
from Util.config import config


db_config = config["database"]

username = urllib.parse.quote_plus(db_config["username"])
password = urllib.parse.quote_plus(db_config["password"])
client = pymongo.MongoClient(
    "mongodb://%s:%s@%s:%s/"
    % (username, password, db_config["path"], db_config["port"])
)

db = client["alala"]
rule_db = db["rules"]
user_db = db["user"]
keywords_db = db["keywords"]
bili_mtr_db = db["bili_monitor"]
permission_db = db["permission"]
api_db = db["api"]
error_db = db["error"]
history_db = db["history"]
