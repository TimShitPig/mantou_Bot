# -*- coding: utf-8 -*-
"""
点众阅读 API 集成工具（基于 dz_simple.py）
支持：搜索、书籍详情、目录、章节正文（含自动广告解锁）
"""

import json
import sys
import random
import time
import uuid
from pathlib import Path

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# -------------------- 常量（来自 dz_simple.py） --------------------
KEY = b"dz#7gfy)@#ylgz&m"
IV = b"$#iupdo)8^dcr*pt"
ST = "l1t5u51n1wk1yfor1ncrypt"
BASE = "https://asgportal.dianzhong.com/asg-portal/portal/client"  # 使用能工作的域名
CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
UA = (
    "Mozilla/5.0 (Linux; Android 12; SM-G9900 Build/V417IR; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
    "Chrome/110.0.5481.154 Safari/537.36"
)
DEVICE_FILE = Path(__file__).with_name("device.json")

# -------------------- 加密/解密工具 --------------------
def enc(text: str) -> str:
    return AES.new(KEY, AES.MODE_CBC, IV).encrypt(pad(text.encode("utf-8"), 16)).hex()

def dec(hex_str: str) -> str:
    return unpad(AES.new(KEY, AES.MODE_CBC, IV).decrypt(bytes.fromhex(hex_str)), 16).decode("utf-8")

def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

# -------------------- 设备身份管理（完全复用 dz_simple.py） --------------------
def gen_utdid_tmp(ts_ms=None) -> str:
    if ts_ms is None:
        ts_ms = int(time.time() * 1000)
    date = time.strftime("%Y%m%d%H%M%S", time.localtime(ts_ms / 1000.0))
    ms = f"{ts_ms % 1000:03d}"
    rand6 = "".join(random.choice(CHARS) for _ in range(6))
    return "A" + date + ms + rand6

def make_datas():
    now = int(time.time() * 1000)
    sid = str(uuid.uuid4())
    return {
        "version": "7.3.0",
        "pname": "com.dianzhong.reader",
        "channelCode": "TAXSEO1000000",
        "utdidTmp": gen_utdid_tmp(now),
        "token": "",
        "utdid": "",
        "os": "android",
        "osv": 32,
        "brand": "Samsung",
        "model": "SM-G9900",
        "manu": "Samsung",
        "userId": "",
        "launch": "third",
        "mchid": "",
        "nchid": "TAXSEO1000000",
        "session1": sid,
        "session2": sid,
        "installTime": now,
        "p": 20,
        "sex": 1,
        "launchNum": 1,
        "visitor": 1,
        "supportAd": 1,
        "changeChidDate": now,
    }

def call_api(api, body, datas, timeout=20):
    body_plain = dumps(body)
    datas_plain = dumps(datas)
    headers = {
        "User-Agent": "okhttp/4.10.0",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json; charset=utf-8",
        "st": ST,
        "datas": enc(datas_plain),
    }
    r = requests.post(f"{BASE}/{api}", data=enc(body_plain), headers=headers, timeout=timeout)
    raw = r.json()
    data_plain = None
    data_json = None
    data = raw.get("data") if isinstance(raw, dict) else None
    if isinstance(data, str) and data:
        try:
            data_plain = dec(data)
            data_json = json.loads(data_plain)
        except Exception:
            data_plain = data
    return {
        "http": r.status_code,
        "body_plain": body_plain,
        "datas_plain": datas_plain,
        "datas": datas,
        "raw": raw,
        "data_plain": data_plain,
        "data_json": data_json,
    }

def save_device(datas, path=DEVICE_FILE):
    path.write_text(json.dumps(datas, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

def load_device(path=DEVICE_FILE):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def init_and_save():
    datas = make_datas()
    body = {
        "oaid": "",
        "userAgent": UA,
        "upgradeUserId": "",
        "requestType": 1,
        "ocpcSeconds": 0,
        "lastLeftPage": "",
    }
    res = call_api(1001, body, datas)
    raw = res["raw"] if isinstance(res["raw"], dict) else {}
    user_id = raw.get("userId")
    if user_id is None and isinstance(res["data_json"], dict):
        user_id = res["data_json"].get("userId")
        if user_id is None:
            user_id = (res["data_json"].get("userInfoVo") or {}).get("userId")
    if not user_id:
        raise RuntimeError(f"init failed: {json.dumps(raw, ensure_ascii=False)[:400]}")

    datas["userId"] = str(user_id)
    datas["visitor"] = 0
    if raw.get("changeChidDate"):
        datas["changeChidDate"] = raw["changeChidDate"]
    path = save_device(datas)
    res["userId"] = str(user_id)
    res["device_file"] = str(path)
    return datas, res

def get_device(force_init=False):
    if not force_init:
        d = load_device()
        if d and d.get("userId") and d.get("utdidTmp"):
            return d
    datas, _ = init_and_save()
    return datas

# -------------------- 工具函数 --------------------
def print_json(data):
    """格式化打印 JSON"""
    if data is None:
        return
    print(json.dumps(data, ensure_ascii=False, indent=2))

# -------------------- 业务功能 --------------------
def search_books(datas):
    keyword = input("请输入搜索关键词: ").strip()
    if not keyword:
        print("[错误] 关键词不能为空")
        return
    page = input("请输入页码 (默认1): ").strip()
    page = int(page) if page.isdigit() else 1
    typ = input("请输入类型 (默认0): ").strip()
    typ = int(typ) if typ.isdigit() else 0
    body = {"keyWord": keyword, "page": page, "type": typ}
    res = call_api(1203, body, datas)
    print(f"HTTP {res['http']}, code={res['raw'].get('code')}, msg={res['raw'].get('msg')}")
    if res["data_json"]:
        print("\n[搜索结果]")
        print_json(res["data_json"])
    elif res["data_plain"]:
        print("\n[原始响应]")
        print(res["data_plain"][:2000])
    else:
        print("\n[原始响应]")
        print_json(res["raw"])

def get_book_detail(datas):
    book_id = input("请输入 bookId: ").strip()
    if not book_id:
        print("[错误] bookId 不能为空")
        return
    chapter_id = input("请输入 chapterId (可选，直接回车跳过): ").strip()
    body = {"bookId": book_id, "chapterId": chapter_id}
    res = call_api(1111, body, datas)
    print(f"HTTP {res['http']}, code={res['raw'].get('code')}, msg={res['raw'].get('msg')}")
    if res["data_json"]:
        print("\n[书籍详情]")
        print_json(res["data_json"])
    else:
        print("\n[原始响应]")
        print_json(res["raw"])

def get_catalog(datas):
    book_id = input("请输入 bookId: ").strip()
    if not book_id:
        print("[错误] bookId 不能为空")
        return
    chap_idx = input("请输入 chapterIndex (默认0): ").strip()
    chap_idx = int(chap_idx) if chap_idx.isdigit() else 0
    cur_chap_id = input("请输入 currentChapterId (可选，直接回车跳过): ").strip()
    body = {"bookId": book_id, "chapterIndex": chap_idx, "currentChapterId": cur_chap_id}
    res = call_api(1304, body, datas)
    print(f"HTTP {res['http']}, code={res['raw'].get('code')}, msg={res['raw'].get('msg')}")
    if res["data_json"]:
        print("\n[目录]")
        print_json(res["data_json"])
    else:
        print("\n[原始响应]")
        print_json(res["raw"])

def get_chapter_content(datas):
    book_id = input("请输入 bookId: ").strip()
    if not book_id:
        print("[错误] bookId 不能为空")
        return
    chapter_id = input("请输入 chapterId: ").strip()
    if not chapter_id:
        print("[错误] chapterId 不能为空")
        return

    # 构造 source（可自定义，这里保持与 test_content_1303.py 类似）
    source = {
        "origin": "ssym",
        "originName": "搜索页面",
        "channelId": "ssjgy",
        "channelName": "搜索结果页",
        "columnId": "gjc",
        "columnName": "你好",
        "contentType": "book_detail",
        "contentId": book_id,
        "contentName": "未知书籍",
        "triggerTime": int(time.time() * 1000),
        "strategyId": "",
        "expId": "",
        "logId": "",
        "strategyName": "",
        "channelPos": "",
        "columnPos": "0",
        "contentPos": "0",
        "otypeId": "",
        "otypeName": "",
    }
    source_str = json.dumps(source, ensure_ascii=False, separators=(",", ":"))

    body = {
        "bookId": book_id,
        "chapterId": chapter_id,
        "offset": 0,
        "confirmWatch": "1",
        "preload": "0",
        "noDd100": 1,
        "noDd300": 1,
        "source": source_str,
    }

    print("\n[请求章节正文]")
    res = call_api(1303, body, datas)
    print(f"HTTP {res['http']}, code={res['raw'].get('code')}, msg={res['raw'].get('msg')}")

    # 检查是否需要广告解锁
    data_json = res.get("data_json")
    if data_json and data_json.get("status") == 5 and "orderPageVo" in data_json:
        order = data_json["orderPageVo"]
        ad_key = None
        if "unlockOperate" in order and "key" in order["unlockOperate"]:
            ad_key = order["unlockOperate"]["key"]
        elif "exitRetainOperate" in order and "key" in order["exitRetainOperate"]:
            ad_key = order["exitRetainOperate"]["key"]
        if ad_key:
            print(f"[广告] 检测到余额不足，自动上报广告 key: {ad_key}")
            # 上报广告
            advert_body = {"key": ad_key, "advertValue": 0.0}
            ad_res = call_api(1518, advert_body, datas)
            print(f"广告上报 HTTP {ad_res['http']}, code={ad_res['raw'].get('code')}, msg={ad_res['raw'].get('msg')}")
            if ad_res["raw"].get("code") == 0:
                print("[广告] 上报成功，再次请求章节正文...")
                res2 = call_api(1303, body, datas)
                print(f"第二次请求 HTTP {res2['http']}, code={res2['raw'].get('code')}, msg={res2['raw'].get('msg')}")
                if res2["data_json"]:
                    print("\n[最终章节正文]")
                    print_json(res2["data_json"])
                else:
                    print("\n[最终响应（未解密）]")
                    print(res2.get("data_plain", "无数据")[:2000])
            else:
                print("[广告] 上报失败，显示原始响应")
                print_json(data_json)
        else:
            print("[提示] 未找到广告 key，无法自动解锁")
            print_json(data_json)
    else:
        # 正常响应
        if data_json is not None:
            print("\n[章节正文]")
            print_json(data_json)
        else:
            print("\n[原始响应]")
            print_json(res["raw"])

# -------------------- 主菜单 --------------------
def main():
    # 确保设备身份
    datas = get_device()
    print(f"[信息] 当前 userId: {datas.get('userId')}")
    print(f"[信息] device.json 位置: {DEVICE_FILE}")

    while True:
        print("\n" + "="*50)
        print("点众阅读 API 测试工具")
        print("1. 搜索书籍")
        print("2. 获取书籍详情")
        print("3. 获取目录")
        print("4. 获取章节正文（自动广告解锁）")
        print("5. 退出")
        choice = input("请输入序号: ").strip()
        if choice == "1":
            search_books(datas)
        elif choice == "2":
            get_book_detail(datas)
        elif choice == "3":
            get_catalog(datas)
        elif choice == "4":
            get_chapter_content(datas)
        elif choice == "5":
            print("退出程序。")
            break
        else:
            print("无效输入，请重新选择。")

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except:
        pass
    main()
