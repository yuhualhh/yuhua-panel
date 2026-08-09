# [title: 王者战力查询]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@8b8c57f2b4173a6ec2b5c7e58db07be1158e0e16/2025/02/20/f63f99f95da0cf1fb83949c22061cbfb.png]
# [rule: ^战力查询$]
# [language: python]
# [disable:false]
# [public: true]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb]
# [author: 羽化]
# [open_source: false]
# [priority: 9999999999999999999]
# [version: 1.1.1]
# [price: 0]
# [service: ]
# [description: 王者战力查询精美图片版，触发指令战力查询 ]


import requests
import middleware
import json

def check_hero_exists(hero_input: str) -> bool:
    """
    通过 http://api.xxoo.team/hero/getHeroList.php 获取所有英雄
    并检查是否 cname(小写) 包含 hero_input(小写).
    """
    try:
        url = "http://api.xxoo.team/hero/getHeroList.php"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        js = r.json()     # => {"code":200,"data":[{ename:...,cname:...}, ...]}
        
        hero_list = js.get("data", [])
        if not hero_list:
            print("【DEBUG】data字段为空，无法匹配任何英雄")
            return False
        
        hero_input_lower = hero_input.lower().strip()  # 去掉前后空格再小写
        
        found_any = False

        print("【DEBUG】用户输入(小写)：", hero_input_lower)
        print("【DEBUG】接口返回总英雄数：", len(hero_list))

        for item in hero_list:
            cname_raw = str(item.get("cname",""))
            cname = cname_raw.lower().strip()  # 同样转小写去空格

            # 可加调试打印
            # print("【DEBUG】当前cname:", cname_raw, "(转小写后:", cname, ")")

            if hero_input_lower == cname:
                found_any = True
                break
        
        return found_any
    
    except Exception as e:
        print("【DEBUG】接口或解析异常 =>", e)
        return False

# def check_maintenance_page():
    # sender_id = middleware.getSenderID()
    # sender = middleware.Sender(sender_id)
    # url = "http://yuhua.oroe.cn/shouquan"
    # try:
        # r=requests.get(url,timeout=10)
        # r.raise_for_status()
        # r.encoding='utf-8'
        # soup=BeautifulSoup(r.text,"html.parser")
        # title=soup.title.string if soup.title else ""
        # if title!="服务正常中":
            # sender.reply("❌ 服务端无法连通，插件停止运行")
            # return False
        # return True
    # except:
        # sender.reply("❌ 服务端无法连通，插件停止运行")
        # return False

import time
from bs4 import BeautifulSoup

def _perform_maintenance_check() -> bool:
    url = "https://yuhualhh.250666.xyz/shouquan"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cache-Control": "no-cache"
    }
    for attempt in range(3):
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=(5, 10),
                verify=True,
                allow_redirects=True
            )
            response.raise_for_status()
            response.encoding = 'UTF-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            content_div = soup.find('div', class_='note-content')
            if content_div:
                return "服务正常中" in content_div.get_text(strip=True)
            return any("服务正常中" in tag.get_text() for tag in soup.find_all(['div', 'p']))
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < 2:
                time.sleep(2)
                continue
            return False
        except requests.exceptions.HTTPError:
            return False
        except Exception:
            return False
    return False
def check_maintenance_page() -> bool:
    import os, base64, hashlib, json
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    cache_bucket = "time"
    cache_key = "status_cache"
    ttl_seconds = 1 * 3600
    try:
        salt = b'\x8a\x9b\x1f\xe3\x7d\x4c\x5b\x6a\x01\x23\x45\x67\x89\xab\xcd\xef'
        identifier = "yuhua888"
        key = hashlib.sha256(salt + identifier.encode('utf-8')).digest()
        aesgcm = AESGCM(key)
        cached_data_str = middleware.bucketGet(cache_bucket, cache_key)
        if cached_data_str:
            decoded_data = base64.b64decode(cached_data_str.encode('utf-8'))
            nonce = decoded_data[:12]
            ciphertext = decoded_data[12:]
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            cached_data = json.loads(decrypted_bytes.decode('utf-8'))
            if (time.time() - cached_data.get("timestamp", 0)) < ttl_seconds and cached_data.get("status") is True:
                return True
    except Exception:
        pass
    live_status = _perform_maintenance_check()
    new_cache_payload = {
        "status": live_status,
        "timestamp": time.time()
    }
    try:
        salt = b'\x8a\x9b\x1f\xe3\x7d\x4c\x5b\x6a\x01\x23\x45\x67\x89\xab\xcd\xef'
        identifier = "yuhua888"
        key = hashlib.sha256(salt + identifier.encode('utf-8')).digest()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        plaintext = json.dumps(new_cache_payload).encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        encrypted_payload = base64.b64encode(nonce + ciphertext).decode('utf-8')
        middleware.bucketSet(cache_bucket, cache_key, encrypted_payload)
    except Exception as e:
        pass
    return live_status

def main():
    sender_id = middleware.getSenderID()
    sender = middleware.Sender(sender_id)
    if not check_maintenance_page():
        sender.reply("❌ 服务端无法连通, 插件停止运行")
        return
    msg = sender.getMessage().strip()

    if msg == "战力查询":
        sender.reply("请输入查询英雄：")
        hero_name = sender.input(15000, 0, False)
        if not hero_name:
            sender.reply("超时已退出")
            return
        if hero_name.lower() == 'q':
            sender.reply("已取消操作")
            return
        
        # 校验英雄
        if not check_hero_exists(hero_name):
            sender.reply("该英雄不存在")
            return
        
        menu = """请输入数字选择平台：
❶ 安卓-扣扣区
❷ 苹果-扣扣区
❸ 安卓-微信区
❹ 苹果-微信区
"""
        sender.reply(menu)
        choice = sender.input(15000, 0, False)
        if not choice:
            sender.reply("超时已退出")
            return
        if choice.lower() == 'q':
            sender.reply("已取消操作")
            return
        
        mapping = {
            "1": "aqq",
            "2": "iqq",
            "3": "awx",
            "4": "iwx"
        }
        if choice not in mapping:
            sender.reply("输入无效")
            return
        ptype = mapping[choice]
        sender.reply("正在查询....")
        # 拼接图片链接
        pic_url = f"https://www.sapi.run/pic/getHero.php?hero={hero_name.strip()}&type={ptype}&format=png"
        sender.replyImage(pic_url)

    else:
        sender.setContinue()

if __name__ == "__main__":
    main()
