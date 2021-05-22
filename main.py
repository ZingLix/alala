from Util.config import config
from api import app
import time
import threading
from qqbot import get_new_msg, deal_msg, verify, bili_monitor
from rule import update_rules, update_keywords_list
import traceback


def run_flask():
    app.run(host='0.0.0.0', port=config["api"]["port"], debug=False)


if __name__ == '__main__':
    update_rules()
    update_keywords_list()
    verify()
    threading.Thread(target=run_flask).start()
    threading.Thread(target=bili_monitor).start()
    while True:
        try:
            msgList = get_new_msg()
            if msgList is None:
                time.sleep(1)
                continue
            if msgList["code"] != 0:
                print(msgList)
                time.sleep(5)
                continue
            msgList = msgList["data"]
            if len(msgList) == 0:
                time.sleep(0.1)
                continue
            for msg in msgList:
                print(msg)
                deal_msg(msg)
        except Exception as e:
            traceback.print_exc()
            continue
