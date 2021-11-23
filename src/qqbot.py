import requests
import random
import re
import time
from Util.config import config, req_headers
from rule import keywords, rules, bili_mtr_list
import json

import traceback


chat_history = {}
MAX_LEN = config["bot"]["max_msg_len"]

session = None
mirai_path = "{}:{}".format(config["mirai"]["path"], config["mirai"]["port"])


def send(path, msg):
    if session is not None:
        msg["sessionKey"] = session
    r = requests.post("{}/{}".format(mirai_path, path), json=msg)
    if r.status_code != 200:
        print("bad request:")
        print("send: {} - {}".format(path, json.dumps(msg)))
        print("return: {}", r.content)
        return {}
    return r.json()


def get(path, param={}):
    param["sessionKey"] = session
    r = requests.get("{}/{}".format(mirai_path, path), params=param)
    if len(r.text) == 0:
        return None
    return r.json()


def verify():
    global session
    auth = send("verify", {"verifyKey": str(config["mirai"]["authKey"])})
    print(auth)
    session = auth["session"]
    send("bind", {"qq": config["mirai"]["qq"]})


def get_new_msg():
    return get("fetchMessage", {"count": 100})


def send_group_msg(msgChain, group_id):
    send("sendGroupMessage", {"target": group_id, "messageChain": msgChain})


def send_personal_msg(msg_chain, target):
    send("sendFriendMessage", {"target": target, "messageChain": msg_chain})


def mute(user_id, group_id, time_len):
    send("mute", {"memberId": user_id, "target": group_id, "time": time_len})


def unmute(user_id, group_id):
    send("unmute", {"memberId": user_id, "target": group_id})


def check_if_plain_msg(msg):
    return len(msg["messageChain"]) == 2 and msg["messageChain"][1]["type"] == "Plain"


def cmp_obj(o1, o2):
    if o1["type"] != o2["type"]:
        return False
    if o1["type"] == "At":
        return o1["target"] == o2["target"]
    if o1["type"] == "AtAll":
        return True
    if o1["type"] == "Face":
        return o1["faceId"] == o2["faceId"]
    if o1["type"] == "Plain":
        return o1["text"] == o2["text"]
    if o1["type"] == "Image" or o1["type"] == "FlashImage":
        return o1["imageId"] == o2["imageId"]
    return False


def deal_msg(msg):
    if msg["type"] == "GroupMessage":
        deal_group_msg(msg)
    if msg["type"] == "FriendMessage":
        deal_friend_msg(msg)
    if msg["type"] == "NewFriendRequestEvent":
        auto_add_friend(msg)


def auto_add_friend(msg):
    req = {
        "eventId": msg["eventId"],
        "fromId": msg["fromId"],
        "groupId": msg["groupId"],
        "operate": 0,
        "message": "",
    }
    send("resp/newFriendRequestEvent", req)


def deal_friend_msg(msg):
    deal_command(msg)


def deal_group_msg(msg):
    global chat_history
    global MAX_LEN

    message = {"id": msg["sender"]["id"], "msg": msg["messageChain"]}
    group_id = msg["sender"]["group"]["id"]
    if group_id not in chat_history:
        chat_history[group_id] = [message] + [{"id": 0, "msg": ""}] * (MAX_LEN - 1)
    else:
        chat_history[group_id].insert(0, message)
    if len(chat_history[group_id]) > MAX_LEN:
        chat_history[group_id] = chat_history[group_id][:MAX_LEN]

    if ban_user(msg):
        return
    if alalalala(msg):
        return
    if deal_command(msg):
        return
    if alalasb(msg):
        return
    if zuitian(msg):
        return
    if repeat(msg):
        return
    if deal_plain_text(msg):
        return

    return


def ban_user(msg):
    chain = msg["messageChain"]
    if len(chain) != 2 or chain[1]["type"] != "Plain":
        return False
    group_id = msg["sender"]["group"]["id"]
    user_id = msg["sender"]["id"]
    recv_message = msg["messageChain"][1]["text"]
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
                    send("recall", {"target": chain[0]["id"]})
                return True
    return False


def alalalala(msg):
    chain = msg["messageChain"]
    if chain[1]["type"] == "At":
        if chain[1]["target"] != config["mirai"]["qq"]:
            return False
        m = chain[2]["text"]
        print(m)
        r = requests.post(config["bot"]["chatbot"]["url"], json={"text": m})
        print(r.json()["text"])
        send(
            "sendGroupMessage",
            {
                "target": msg["sender"]["group"]["id"],
                "messageChain": [{"type": "Plain", "text": r.json()["text"]}],
            },
        )
        return True
    return False


def alalasb(msg):
    chain = msg["messageChain"]
    if (
        len(chain) == 2
        and chain[1]["type"] == "Plain"
        and chain[1]["text"] == "alalasb"
    ):
        send("recall", {"target": chain[0]["id"]})
        send(
            "memberInfo",
            {
                "target": msg["sender"]["group"]["id"],
                "memberId": msg["sender"]["id"],
                "info": {"name": "alala的儿子"},
            },
        )
        return True
    return False


def repeat(msg):
    msg_history = chat_history[msg["sender"]["group"]["id"]]
    if len(msg_history) < 3:
        return False
    msgChainList = []
    # print(msgChainList[0])
    for m in msg_history:
        msgChainList.append(m["msg"][1:])

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
        send_group_msg(msgChainList[1], msg["sender"]["group"]["id"])
        return True
    return False


def deal_plain_text(msg):
    if not check_if_plain_msg(msg):
        return False
    group_id = msg["sender"]["group"]["id"]
    sender_id = msg["sender"]["id"]
    recv_message = msg["messageChain"][1]["text"]
    for rule in rules():
        if group_id in rule["suitable_group"]:
            try:
                return_msg = get_return_msg(
                    recv_message, group_id, rule, str(sender_id)
                )
            except KeyError:
                continue
            if return_msg is not None:
                print(return_msg)
                send_group_msg([{"type": "Plain", "text": return_msg}], group_id)
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
    field_list = re.findall(r"\{(.*?)\}", s)
    if len(field_list) == 0:
        return [s]
    new_dict = rec(0, field_list, replace_dict)
    res = []
    for d in new_dict:
        res.append(s.format(**d))
    return res


def get_return_msg(input_msg, group_id, rule, user_id):
    chat_history_map = {}
    for idx, item in enumerate(chat_history[group_id]):
        if len(item["msg"]) == 2 and item["msg"][1]["type"] == "Plain":
            chat_history_map["m" + str(idx)] = item["msg"][1]["text"]
    chat_history_map["user_id"] = user_id
    replace_dict = {k: [chat_history_map[k]] for k in chat_history_map}
    for var in rule["vars"]:
        var_possible_str = []
        for v in var["varlist"]:
            all_replace_res = get_all_replace_result(v, replace_dict)
            var_possible_str += all_replace_res
        replace_dict[var["varname"]] = var_possible_str

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
                    if re.fullmatch(string, expr1):
                        cur_res = True
                        break
            else:
                # elif expr["operator"] == "in":
                cur_res = False
                for string in expr2:
                    if re.match(string, expr1):
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
    if all_res:
        if random.randrange(100) > rule["probability"]:
            return None
        return random.choice(get_all_replace_result(rule["reply"], replace_dict))
    else:
        return None


def deal_command(msg):
    text_list = []
    for item in msg["messageChain"][1:]:
        if item["type"] != "Plain":
            return False
        text_list.append(item["text"])
    if text_list[0][0] not in [".", "。"] or len(text_list[0]) < 2:
        return False
    text_list = " ".join(text_list).split(" ")
    command = text_list[0][1:]
    if msg["type"] == "FriendMessage":
        if command == "send":
            return command_personal_send(text_list, msg)
        if command == "sendgroup":
            return command_personal_send_group(text_list, msg)
    if msg["type"] == "GroupMessage":
        print(command)
        if command == "roll":
            return command_group_roll(text_list, msg)
        if command[0] == "r":
            return command_new_roll(text_list, msg)
        if "股票" in command:
            return stock_report(text_list, msg)
        if command == "意义":
            return command_meaning(text_list, msg)
    return False


def command_meaning(text_list, msg):
    group_id = msg["sender"]["group"]["id"]
    if len(text_list) < 2:
        send_group_msg([{"type": "Plain", "text": "缺少参数"}], group_id)
        return True
    name = text_list[1]
    r = requests.get(
        "https://wtf.hiigara.net/api/run/mRIFuS/{}?event=ManualRun".format(name)
    )
    r = r.json()
    send_group_msg([{"type": "Plain", "text": r["text"]}], group_id)
    return True


def command_personal_send(text_list, msg):
    if not text_list[1].isdigit():
        send(
            "sendFriendMessage",
            {
                "target": msg["sender"]["id"],
                "messageChain": [{"type": "Plain", "text": "用户QQ号错误"}],
            },
        )
        return True
    target = int(text_list[1])
    text = " ".join(text_list[2:])
    send_personal_msg([{"type": "Plain", "text": text}], target)
    send_personal_msg([{"type": "Plain", "text": "已发送"}], msg["sender"]["id"])
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

    random_num = 0
    for i in range(frequency):
        random_num += random.randint(1, dimension)
    if len(text_list) > 1:
        action = text_list[1]
        if len(action) == 1:
            return_msg = "{}直接进行一个{}:\n{}".format(
                msg["sender"]["memberName"], action, random_num
            )
        else:
            return_msg = "{}直接进行一个{}的{}:\n{}".format(
                msg["sender"]["memberName"], action[1:], action[0], random_num
            )
    else:
        return_msg = "{}投掷了{}次{}面骰子：\n{}".format(
            msg["sender"]["memberName"], str(frequency), str(dimension), random_num
        )

    if frequency == 1 and dimension == 100:
        if random_num > 95:
            return_msg += "\n大失败，心中已无悲喜"
        elif random_num < 6:
            return_msg += "\n好耶大成功"
    send(
        "sendGroupMessage",
        {
            "target": msg["sender"]["group"]["id"],
            "messageChain": [{"type": "Plain", "text": return_msg}],
        },
    )
    return True


def command_group_roll(text_list, msg):
    for item in text_list[1:]:
        if not item.isdigit():
            send(
                "sendGroupMessage",
                {
                    "target": msg["sender"]["group"]["id"],
                    "messageChain": [{"type": "Plain", "text": "参数错误"}],
                },
            )
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
        msg["sender"]["memberName"], str(low), str(high)
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
    send(
        "sendGroupMessage",
        {
            "target": msg["sender"]["group"]["id"],
            "messageChain": [{"type": "Plain", "text": return_msg}],
        },
    )
    return True


def command_personal_send_group(text_list, msg):
    if not text_list[1].isdigit():
        send(
            "sendFriendMessage",
            {
                "target": msg["sender"]["id"],
                "messageChain": [{"type": "Plain", "text": "群号错误"}],
            },
        )
        return True
    target = int(text_list[1])
    text = " ".join(text_list[2:])
    send(
        "sendGroupMessage",
        {"target": target, "messageChain": [{"type": "Plain", "text": text}]},
    )
    send(
        "sendFriendMessage",
        {
            "target": msg["sender"]["id"],
            "messageChain": [{"type": "Plain", "text": "已发送"}],
        },
    )
    return True


def bili_monitor():
    cfg = config["bot"]["bili_monitor"]
    sleep_time = cfg["interval"]
    headers = req_headers["bili"]
    while True:
        for item in bili_mtr_list():
            try:
                r = requests.get(
                    "https://api.bilibili.com/x/space/arc/search?mid={}&pn=1&ps=25&order=pubdate&index=1&jsonp=jsonp".format(
                        item["uid"]
                    ),
                    headers=headers,
                )
                r = r.json()
                video = r["data"]["list"]["vlist"][0]
                cur_time = int(time.time())
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
                if cur_time - rel_time < sleep_time:
                    send_msg = []
                    for m in item["send_msg"]:
                        send_msg.append(
                            [{"type": "Plain", "text": m.format(**vid_info)}]
                        )
                    for msg in send_msg:
                        for user in item["subs_user"]:
                            send_personal_msg(msg, user)
                        for group in item["subs_group"]:
                            send_group_msg(msg, group)
            except Exception as e:
                traceback.print_exc()
                continue
        time.sleep(sleep_time)


def stock_report(text_list, msg):
    requests.get(
        config["bot"]["stock"]["url"], params={"groupid": msg["sender"]["group"]["id"]}
    )
    return True


def zuitian(msg):
    headers = req_headers["zuitian"]
    chain = msg["messageChain"]
    if not (len(chain) == 2 and chain[1]["type"] == "Plain"):
        return False
    text = chain[1]["text"]
    group_id = msg["sender"]["group"]["id"]
    if text == "来点嘴甜":
        r = requests.get("https://nmsl.fans/getloveword?type=1", headers=headers)
        send_group_msg([{"type": "Plain", "text": r.json()["content"]}], group_id)
        return True
    if text == "来点彩虹屁":
        r = requests.get("https://chp.shadiao.app/api.php", headers=headers)
        send_group_msg([{"type": "Plain", "text": r.text}], group_id)
        return True
    headers["referer"] = "https://zuanbot.com/"
    if text == "来点莲花":
        r = requests.get(
            "https://zuanbot.com/api.php?level=min&lang=zh_cn", headers=headers
        )
        send_group_msg([{"type": "Plain", "text": r.text}], group_id)
        return True
    if text == "来点嘴臭":
        r = requests.get("https://zuanbot.com/api.php?lang=zh_cn", headers=headers)
        send_group_msg([{"type": "Plain", "text": r.text}], group_id)
        return True
    tmp = set(text)
    if len(tmp) == 1 and "咕" in tmp:
        r = requests.get("http://www.koboldgame.com/gezi/api.php")
        t = re.findall('"([^"]*)"', r.text)[0]
        send_group_msg([{"type": "Plain", "text": t}], group_id)
        return True
    return False
