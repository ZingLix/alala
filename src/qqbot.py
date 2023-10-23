from threading import Lock
import threading
import requests
import random
import re
import time
from Util.config import config, req_headers, mixinKeyEncTab
from rule import keywords, rules, bili_mtr_list, filter_sentence
import json
from concurrent.futures import ThreadPoolExecutor
import traceback
from Util.db import api_db, error_db, history_db
from bson import ObjectId
from string import Template
import datetime
import logging
import websocket
from functools import reduce
from hashlib import md5
import urllib.parse

chat_history = {}
MAX_LEN = config["bot"]["max_msg_len"]

executor = ThreadPoolExecutor(max_workers=8)
lock = Lock()
session = None
mirai_ws_path = "{}://{}:{}".format(
    "wss" if config["mirai"]["https"] else "ws",
    config["mirai"]["path"],
    config["mirai"]["ws_port"],
)

mirai_http_path = "{}://{}:{}".format(
    "https" if config["mirai"]["https"] else "http",
    config["mirai"]["path"],
    config["mirai"]["http_port"],
)


ws_server = None


def on_message(ws, message):
    data = json.loads(message)
    if "retcode" in data:
        if data["retcode"] != 0:
            logging.error("recv bad response: {}".format(json.dumps(data)))
        return
    logging.info("Mirai pushed: " + json.dumps(message, ensure_ascii=False))
    deal_msg(data)


def on_error(ws, error):
    logging.error("Mirai connection error: " + str(error))


def on_open(ws):
    logging.info("Mirai connect to {} success.".format(mirai_ws_path))


def on_close(ws, close_status_code, close_msg):
    global ws_server
    ws_server = None
    logging.info(
        'Mirai connection closed with code "{}" and message "{}"'.format(
            str(close_status_code), str(close_msg)
        )
    )
    time.sleep(3)
    logging.info("Reconnecting Mirai...")
    start_qqbot_loop()


def start_qqbot_loop():
    global ws_server
    ws_server = websocket.WebSocketApp(
        "{}/".format(mirai_ws_path),
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )
    wst = threading.Thread(target=ws_server.run_forever)
    wst.daemon = True
    wst.start()


def send(path, msg):
    send_msg = {"action": path, "params": msg}
    if ws_server is not None:
        ws_server.send(json.dumps(send_msg))


def get(path, param={}):
    r = requests.get("{}/{}".format(mirai_http_path, path), params=param)
    if len(r.text) == 0:
        return None
    return r.json()


def send_group_msg(msgChain, group_id, quote=None):
    if quote is not None:
        msgChain = [{"type": "reply", "data": {"id": quote}}] + msgChain
    send_msg = {"group_id": group_id, "message": msgChain}
    send("send_group_msg", send_msg)


def send_group_text(text, group_id, quote=None):
    if text.startswith("image: "):
        image = text[len("image: "):]
        data = [{"type": "image", "data": {"file": image}}]
    else:
        data = [{"type": "text", "data": {"text": text}}]
    send_group_msg(data, group_id, quote)


def send_personal_msg(msg_chain, target):
    send("send_private_msg", {"user_id": target, "message": msg_chain})


def send_personal_text(text, target):
    if text.startswith("image: "):
        image = text[len("image: "):]
        data = [{"type": "image", "data": {"file": image}}]
    else:
        data = [{"type": "text", "data": {"text": text}}]
    send_personal_msg(data, target)


def mute(user_id, group_id, time_len):
    send(
        "set_group_ban",
        {"user_id": user_id, "group_id": group_id, "duration": time_len},
    )


def unmute(user_id, group_id):
    mute(user_id, group_id, 0)


def check_if_plain_msg(msg):
    return len(msg["message"]) == 1 and msg["message"][0]["type"] == "text"


def cmp_obj(o1, o2):
    d1, d2 = o1["data"], o2["data"]
    if o1["type"] != o2["type"]:
        return False
    if o1["type"] == "at":
        return d1["qq"] == d1["qq"]
    if o1["type"] == "face":
        return d1["id"] == d2["id"]
    if o1["type"] == "text":
        return d1["text"] == d2["text"]
    if o1["type"] == "image":
        return d1["file"] == d2["file"]
    return False


def deal_msg(msg):
    executor.submit(deal_msg_, msg)


def deal_msg_(msg):
    try:
        if msg["post_type"] == "message":
            if msg["message_type"] == "private":
                deal_friend_msg(msg)
            elif msg["message_type"] == "group":
                deal_group_msg(msg)
        if msg["post_type"] == "request" and msg["request_type"] == "friend":
            auto_add_friend(msg)
    except:
        error_db.insert_one(
            {
                "time": str(datetime.datetime.now()),
                "type": "msg",
                "detail": {"msg": msg},
                "error": traceback.format_exc(),
            }
        )
        logging.error(traceback.format_exc())


def auto_add_friend(msg):
    req = {"flag": msg["flag"], "approve": True, "remark": ""}
    send("set_friend_add_request", req)


def deal_friend_msg(msg):
    deal_command(msg)


def deal_group_msg(msg):
    global chat_history
    global MAX_LEN

    message = {"id": msg["user_id"], "msg": msg["message"]}
    group_id = msg["group_id"]

    lock.acquire()
    if group_id not in chat_history:
        chat_history[group_id] = [message] + [
            {
                "id": 0,
                "msg": [{"type": "text", "data": {"text": ""}}],
            }
        ] * (MAX_LEN - 1)
    else:
        chat_history[group_id].insert(0, message)
    if len(chat_history[group_id]) > MAX_LEN:
        chat_history[group_id] = chat_history[group_id][:MAX_LEN]
    lock.release()

    if ban_user(msg):
        return
    if alalalala(msg):
        return
    if deal_command(msg):
        return
    if repeat(msg):
        return
    if deal_plain_text(msg):
        return

    return


def filter_msg(msg):
    chain = msg["message"]
    if len(chain) != 1 or chain[0]["type"] != "text":
        return False
    recv_message = chain[0]["data"]["text"]
    for item in filter_sentence():
        if item in recv_message:
            return True
    return False


def ban_user(msg):
    chain = msg["message"]
    if len(chain) != 1 or chain[0]["type"] != "text":
        return False
    group_id = msg["group_id"]
    user_id = msg["user_id"]
    recv_message = chain[0]["data"]["text"]
    for rule in keywords():
        if group_id not in rule["suitable_group"]:
            continue
        for keyword in rule["keywords"]:
            if keyword in recv_message:
                if rule["mute_time"] != 0:
                    mute(user_id, group_id, rule["mute_time"])
                for id in rule["unmute_list"]:
                    unmute(id, group_id)
                if rule["recall"]:
                    send("delete_msg", {"message_id": msg["message_id"]})
                return True
    return False


def alalalala(msg):
    chain = msg["message"]
    if chain[0]["type"] == "at":
        if chain[0]["data"]["qq"] != config["mirai"]["qq"]:
            return False
        m = chain[1]["data"]["text"]
        logging.info("alala recv: " + m)
        r = requests.post(config["bot"]["chatbot"]["url"], json={"text": m})
        logging.info("alala response: " + r.json()["text"])
        send_group_msg(
            [{"type": "text", "data": {"text": r.json()["text"]}}], msg["group_id"]
        )
        return True
    return False


def repeat(msg):
    lock.acquire()
    msg_history = chat_history[msg["group_id"]]
    lock.release()
    if len(msg_history) < 3:
        return False
    msgChainList = []
    for m in msg_history:
        msgChainList.append(m["msg"])

    if len(msgChainList[0]) == 1 and msgChainList[0][0]["type"] == "text":
        return False

    def compare_list(a, b):
        if len(a) != len(b):
            return False
        for i in range(len(a)):
            if not cmp_obj(a[i], b[i]):
                return False
        return True

    if compare_list(msgChainList[0], msgChainList[1]) and not compare_list(
        msgChainList[1], msgChainList[2]
    ):
        send_group_msg(msgChainList[1], msg["group_id"])
        return True
    return False


def deal_plain_text(msg):
    if not check_if_plain_msg(msg):
        return False
    group_id = msg["group_id"]
    sender_id = msg["user_id"]
    recv_message = "".join([x["data"]["text"] for x in msg["message"]])
    time = msg["time"]
    msg_id = msg["message_id"]
    history_db.insert_one(
        {
            "group_id": group_id,
            "sender_id": sender_id,
            "msg": recv_message,
            "time": time,
        }
    )
    for rule in rules():
        if group_id in rule["suitable_group"]:
            if random.randint(0, 99) >= rule["probability"]:
                continue
            return_msg = get_return_msg(recv_message, group_id, rule, str(sender_id))
            if return_msg is not None:
                quote = None
                if rule.get("quote", False):
                    quote = msg_id
                send_group_text(return_msg, group_id, quote=quote)
                return True
    return False


def rec(cur_idx, field_list, replace_dict):
    field = field_list[cur_idx]
    if cur_idx == len(field_list) - 1:
        return [{field: i} for i in replace_dict[field]]
    last = rec(cur_idx + 1, field_list, replace_dict)
    res = []
    for item in last:
        for new_val in replace_dict[field]:
            item[field] = new_val
            res.append(item)
    return res


def get_all_replace_result(s, replace_dict):
    field_list = re.findall(r"\{(.*?)\}", s, re.MULTILINE | re.DOTALL)
    field_list = list(set(field_list))
    if len(field_list) == 0:
        return [s]
    new_dict = rec(0, field_list, replace_dict)
    res = []
    for d in new_dict:
        res.append(s.format(**d))
    return res


def get_return_msg(input_msg, group_id, rule, user_id):
    chat_history_map = {}
    lock.acquire()
    for idx, item in enumerate(chat_history[group_id]):
        if len(item["msg"]) == 1 and item["msg"][0]["type"] == "text":
            chat_history_map["m" + str(idx)] = item["msg"][0]["data"]["text"]
        else:
            chat_history_map["m" + str(idx)] = ""
    lock.release()
    chat_history_map["user_id"] = user_id
    replace_dict = {k: [chat_history_map[k]] for k in chat_history_map}
    for var in rule["vars"]:
        var_possible_str = []
        for v in var["varlist"]:
            all_replace_res = get_all_replace_result(v, replace_dict)
            var_possible_str += all_replace_res
        replace_dict[var["varname"]] = var_possible_str
    try:
        all_res = None
        for expr in rule["exprs"]:
            expr1 = expr["expr1"].format(**chat_history_map)
            expr2 = [get_all_replace_result(s, replace_dict) for s in expr["expr2"]]
            tmp = []
            for t in expr2:
                tmp += t
            expr2 = tmp
            if expr["regex"] == False:
                if expr["operator"] == "equal":
                    cur_res = expr1 in expr2
                else:
                    # elif expr["operator"] == "in":
                    cur_res = False
                    for string in expr2:
                        if string in expr1:
                            cur_res = True
                            break
            else:
                if expr["operator"] == "equal":
                    cur_res = False
                    for string in expr2:
                        if re.fullmatch(string, expr1, re.MULTILINE | re.DOTALL):
                            cur_res = True
                            break
                else:
                    # elif expr["operator"] == "in":
                    cur_res = False
                    for string in expr2:
                        if re.match(string, expr1, re.MULTILINE | re.DOTALL):
                            cur_res = True
                            break
            if expr["negative"] == True:
                cur_res = not cur_res
            if all_res is None:
                all_res = cur_res
            else:
                if expr["relation"] == "and":
                    all_res = cur_res and all_res
                else:
                    all_res = cur_res or all_res
    except KeyError as e:
        error_db.insert_one(
            {
                "time": str(datetime.datetime.now()),
                "type": "rule",
                "detail": {
                    "chat_history": chat_history_map,
                    "replace_dict": replace_dict,
                    "rule_name": rule["name"],
                },
                "error": traceback.format_exc(),
            }
        )
        return None
    if all_res:
        context = {
            "text": json.dumps(input_msg)[1:-1],
            "groupid": group_id,
            "userid": user_id,
        }
        for i, part in enumerate(input_msg.split(" ")):
            context["p" + str(i)] = part

        if "api" in rule:
            for api in rule["api"]:
                result = get_api_result(api["api_id"], context)
                if result is None:
                    return None
                replace_dict[api["varname"]] = [result]
        return random.choice(get_all_replace_result(rule["reply"], replace_dict))
    else:
        return None


def deal_command(msg):
    text_list = []
    for item in msg["message"]:
        if item["type"] != "text":
            return False
        text_list.append(item["data"]["text"])
    if text_list[0][0] not in [".", "。"] or len(text_list[0]) < 2:
        return False
    text_list = " ".join(text_list).split(" ")
    command = text_list[0][1:]
    if msg["message_type"] == "private":
        if command == "send":
            return command_personal_send(text_list, msg)
        if command == "sendgroup":
            return command_personal_send_group(text_list, msg)
    if msg["message_type"] == "group":
        if command == "roll":
            return command_group_roll(text_list, msg)
        if command[0] == "r":
            return command_new_roll(text_list, msg)
    return False


def command_personal_send(text_list, msg):
    if not text_list[1].isdigit():
        send_personal_text("用户QQ号错误", msg["user_id"])
        return True
    target = int(text_list[1])
    text = " ".join(text_list[2:])
    send_personal_text(text, target)
    send_personal_text("已发送", msg["user_id"])
    return True


def command_new_roll(text_list, msg):
    text = text_list[0]
    frequency = 1
    dimension = 100

    matchObj = re.match(r"\.r(.*)d(.*)", text, re.M | re.I)
    frequency = matchObj.group(1)
    dimension = matchObj.group(2)

    if frequency == "" or frequency is None:
        frequency = 1
    if dimension == "" or dimension is None:
        dimension = 100

    frequency = int(frequency)
    dimension = int(dimension)

    if frequency < 1 or frequency > 10000:
        send_group_text("爬", msg["group_id"])
        return True

    random_num = 0
    for i in range(frequency):
        random_num += random.randint(1, dimension)
    if len(text_list) > 1:
        action = text_list[1]
        if len(action) == 1:
            return_msg = "{}直接进行一个{}:\n{}".format(
                msg["sender"]["nickname"], action, random_num
            )
        else:
            return_msg = "{}直接进行一个{}的{}:\n{}".format(
                msg["sender"]["nickname"], action[1:], action[0], random_num
            )
    else:
        return_msg = "{}投掷了{}次{}面骰子：\n{}".format(
            msg["sender"]["nickname"], str(frequency), str(dimension), random_num
        )

    if frequency == 1 and dimension == 100:
        if random_num > 95:
            return_msg += "\n大失败，心中已无悲喜"
        elif random_num < 6:
            return_msg += "\n好耶大成功"
    send_group_text(return_msg, msg["group_id"])
    return True


def command_group_roll(text_list, msg):
    for item in text_list[1:]:
        if not item.isdigit():
            send_group_text("参数错误", msg["group_id"])
            return True
    low = 0
    high = 100
    count = 1
    num_list = [int(i) for i in text_list[1:]]
    if len(num_list) == 1:
        high = num_list[0]
    elif len(num_list) == 2:
        low = num_list[0]
        high = num_list[1]
    elif len(num_list) > 2:
        low = num_list[0]
        high = num_list[1]
        count = num_list[2]

    random_list = []
    for i in range(count):
        random_num = random.randint(low, high)
        random_list.append(random_num)
    return_msg = "{}投出了[{}, {})：\n".format(
        msg["sender"]["nickname"], str(low), str(high)
    )
    append_msg = ""
    if count == 1:
        append_msg = str(random_list[0])
    else:
        s = 0
        for num in random_list:
            append_msg += "{}+".format(str(num))
            s += num
        append_msg = append_msg[:-1]
        append_msg += " = {}".format(s)
    return_msg += append_msg
    send_group_text(return_msg, msg["group_id"])
    return True


def command_personal_send_group(text_list, msg):
    if not text_list[1].isdigit():
        send_personal_text("群号错误", msg["user_id"])
        return True
    target = int(text_list[1])
    text = " ".join(text_list[2:])
    send_group_text(text, target)
    send_personal_text("已发送", msg["user_id"])
    return True


def getMixinKey(orig: str):
    "对 imgKey 和 subKey 进行字符顺序打乱编码"
    return reduce(lambda s, i: s + orig[i], mixinKeyEncTab, "")[:32]


def encWbi(params: dict, img_key: str, sub_key: str):
    "为请求参数进行 wbi 签名"
    mixin_key = getMixinKey(img_key + sub_key)
    curr_time = round(time.time())
    params["wts"] = curr_time  # 添加 wts 字段
    params = dict(sorted(params.items()))  # 按照 key 重排参数
    # 过滤 value 中的 "!'()*" 字符
    params = {
        k: "".join(filter(lambda chr: chr not in "!'()*", str(v)))
        for k, v in params.items()
    }
    query = urllib.parse.urlencode(params)  # 序列化参数
    wbi_sign = md5((query + mixin_key).encode()).hexdigest()  # 计算 w_rid
    params["w_rid"] = wbi_sign
    return params


def getWbiKeys() -> tuple[str, str]:
    "获取最新的 img_key 和 sub_key"
    resp = requests.get("https://api.bilibili.com/x/web-interface/nav")
    resp.raise_for_status()
    json_content = resp.json()
    img_url: str = json_content["data"]["wbi_img"]["img_url"]
    sub_url: str = json_content["data"]["wbi_img"]["sub_url"]
    img_key = img_url.rsplit("/", 1)[1].split(".")[0]
    sub_key = sub_url.rsplit("/", 1)[1].split(".")[0]
    return img_key, sub_key


def bili_monitor():
    cfg = config["bot"]["bili_monitor"]
    sleep_time = cfg["interval"]
    headers = req_headers["bili"]
    last_check_time = int(time.time())
    while True:
        img_key, sub_key = getWbiKeys()
        for item in bili_mtr_list():
            try:
                params = {
                    "mid": item["uid"],
                    "pn": 1,
                    "ps": 25,
                    "order": "pubdate",
                    "index": 1,
                    "jsonp": "jsonp",
                }
                signed_params = encWbi(params, img_key, sub_key)
                r = requests.get(
                    "https://api.bilibili.com/x/space/wbi/arc/search",
                    params=signed_params,
                    headers=headers,
                )
                r = r.json()
                if r["code"] != 0:
                    print(r)
                    continue
                video = r["data"]["list"]["vlist"][0]
                rel_time = video["created"]
                vid_info = {
                    "bvid": video["bvid"],
                    "url": "https://www.bilibili.com/video/{}".format(video["bvid"]),
                    "title": video["title"],
                    "author": video["author"],
                    "comment": video["comment"],
                    "play": video["play"],
                    "description": video["description"],
                    "length": video["length"],
                    "newline": "\n",
                }
                if last_check_time < rel_time:
                    logging.info(
                        'Bilibili new video found: "{}" from "{}"'.format(
                            vid_info["title"], vid_info["author"]
                        )
                    )
                    send_msg = []
                    for m in item["send_msg"]:
                        send_msg.append(
                            [{"type": "text", "data": {"text": m.format(**vid_info)}}]
                        )
                    for msg in send_msg:
                        for user in item["subs_user"]:
                            send_personal_msg(msg, user)
                        for group in item["subs_group"]:
                            send_group_msg(msg, group)
                time.sleep(0.1)
            except Exception as e:
                logging.error(traceback.format_exc())
                continue
        last_check_time = int(time.time())
        time.sleep(sleep_time)


def format_template(template, data):
    t = Template(template)
    return t.substitute(data)


def get_api_result(api_id, context):
    try:
        api = api_db.find_one({"_id": ObjectId(api_id)})
        if api is None:
            return None
        headers = {}
        for item in api["headers"]:
            headers[item["header"]] = format_template(item["content"], context)
        send_data = format_template(api["body"], context).encode("utf-8")
        url = format_template(api["url"], context)
        if api["method"] == "GET":
            r = requests.get(url, headers=headers)
        elif api["method"] == "POST":
            r = requests.post(url, data=send_data, headers=headers)
        elif api["method"] == "PUT":
            r = requests.put(url, data=send_data, headers=headers)
        elif api["method"] == "DELETE":
            r = requests.delete(url, data=send_data, headers=headers)
        else:
            return None
        if r.status_code != 200:
            return None
        if "eval" not in api or api["eval"] in [None, ""]:
            return None
        post = eval(api["eval"])
        if post in [None, ""]:
            return None
        return post
    except:
        error_db.insert_one(
            {
                "time": str(datetime.datetime.now()),
                "type": "api",
                "detail": {"api_id": api_id, "context": context},
                "error": traceback.format_exc(),
            }
        )
        logging.error(traceback.format_exc())
        return None
