# [title: 中国联通]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@7c2616699a9cf7a628d4a087eb458bb013913a85/2025/12/26/e1b072befcce7bbe3a55685176de670f.png]
# [language: python]
# [rule: ^(联通)(登录|查询|管理|清理|授权|检测)$]
# [disable:false]
# [open_source: false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [priority: 9999999999999999999]
# [public:true]
# [version: 1.1.0]
# [price: 0]
# [author: 羽化]
# [service: ]
# [description: ❶中国联通资产查询以及对接青龙面板代挂插件，适配妖火论坛联通整合本，支持 Token登录、联通账密登录、联通短信登录、管理、查询、授权、检测授权过期以及CK失效推送等功能<br>❷部分功能的实现需自行添加计划任务伪装管理员定时，了解如何添加计划任务请看移动云盘插件介绍，关于指令『联通检测』与『联通清理』定时『30 18 * * *』<img src="https://gcore.jsdelivr.net/gh/lhz03/img@1dab556e9d04a77d6b15802655355fd7be26fa9a/2026/01/21/2157c0cf735b321263a710cf978f43b0.png">]

# [param: {"required":true,"key":"yuhua_zglt.zsm","bool":false,"placeholder":"","name":"收款码子","desc":"微信Bot收款码直链"}]
# [param: {"required":true,"key":"yuhua_zglt.yuhua_zglt_qlname","bool":false,"placeholder":"Host丨ClientID丨ClientSecret","name":"对接容器","desc":"各参数之间用中文符丨分割，例如: http://127.0.01:5700/丨abcdef-ghijk丨abcdefghijklmnopqrs_tuvw"}]
# [param: {"required":true,"key":"yuhua_zglt.yuhua_zglt_osname","bool":false,"placeholder":"必填项，例: chinaUnicomCookie","name":"环境变量","desc":"定义提交至容器的变量名称"}]
### [param: {"required":true,"key":"yuhua_zglt.aiting_var","bool":false,"placeholder":"例: PHONE_V","name":"爱听变量","desc":"定义提交至容器的联通爱听变量名称，默认留空不提交"}
# [param: {"required":true,"key":"yuhua_zglt.price","bool":false,"placeholder":"","name":"收费价格","desc":"不填默认0元，单位: 元/月"}]
# [param: {"required":true,"key":"yuhua_zglt.bingfa","bool":false,"placeholder":"","name":"查询并发","desc":"不填默认5"}]
### [param: {"required":true,"key":"yuhua_zglt.status","bool":false,"placeholder":"例:1，不填默认直连","name":"启用代理","desc":"0=直连，1=代理池，2=API代理"}
### [param: {"required":true,"key":"yuhua_zglt.proxy","bool":false,"placeholder":"请输入 http://xxx 或 https://xxx","name":"代理地址","desc":"支持代理池以及API代理"}
### [param: {"required":true,"key":"yuhua_zglt.ip","bool":false,"placeholder":"例:30，不填默认不限制","name":"代理限制","desc":"单IP代理次数限制，仅对API代理有效，填0为不限制"}
# [param: {"required":false,"key":"yuhua_zglt.debug_pwd","bool":false,"placeholder":"","name":"调试模式","desc":"非插件开发者无需理会"}]
# [param: {"required":false,"key":"yuhua_zglt.yuedu","bool":true,"placeholder":"","name":"阅读红包","desc":"是否在联通查询中显示阅读红包详情，默认关闭"}]
#[param: {"required":false,"key":"yuhua_zglt.lianchao","bool":true,"placeholder":"","name":"权超记录","desc":"是否在联通查询中显示权益超市中奖记录，默认关闭"}]

import re
import time
from datetime import datetime, timedelta
import middleware
import urllib.parse
from decimal import Decimal
import requests
import time
import json
import hashlib
import uuid
import random
import socket
from datetime import timezone
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from bs4 import BeautifulSoup
import threading
import concurrent.futures
import os
import string
from concurrent.futures import ThreadPoolExecutor, as_completed
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

import sys
# 封装函数：支持颜色分级(INFO=绿, WARN=黄, 其他=红)，输出到stderr确保控制台可见
def printf(msg,level='INFO'):
    c=32 if level in['INFO','DEBUG']else 33 if level in['WARN','WARNING']else 31;sys.stderr.write(f"\033[{c}m[{level}] {str(msg)}\033[0m\n");sys.stderr.flush()


# --- 核心参数 ---
BASE_URL = "https://panservice.mail.wo.cn"
CHANNEL = "wohome"
ROOT_DIR_ID = "0"
IV = b'wNSOYIB1k1DjY5lA'
PRODUCT_ID = "91015539"

# --- 性能与容错 ---
# 宏观重试（整个任务流程）
MACRO_MAX_RETRIES = 3
# 微观重试（单个子任务）
MICRO_MAX_RETRIES = 3
# 全局网络超时（秒）
GLOBAL_TIMEOUT = 45

#输出日志
debug_key = middleware.bucketGet('yuhua_zglt', 'debug_pwd') or ''
DEBUG = (debug_key == '123456789abcC@')
if DEBUG:
    printf("🔥🔥🔥 调试模式已开启，密钥验证通过 🔥🔥🔥", "WARN")

# --- 代理机制全局变量 ---
_ip_cache_pool =[]
_ip_cache_lock = threading.Lock()
_temp_ip_usage = {}
_temp_used_ips = set()
_proxy_lock = threading.Lock()
_session_pool = {}

def get_ip_limit():
    try: return int(middleware.bucketGet('yuhua_zglt', 'ip') or '0')
    except: return 0

def extract_ip_from_proxy(proxy_url):
    try:
        if '://' in proxy_url: proxy_url = proxy_url.split('://', 1)[1]
        if '@' in proxy_url: proxy_url = proxy_url.split('@', 1)[1]
        return proxy_url.split(':')[0]
    except: return None

def clear_temp_ip_records():
    global _temp_ip_usage, _temp_used_ips, _proxy_lock
    with _proxy_lock: _temp_ip_usage.clear(); _temp_used_ips.clear()

def clear_session_pool():
    global _session_pool
    try:
        for session in _session_pool.values():
            try: session.close()
            except Exception: pass
        _session_pool.clear()
    except Exception: pass

def cleanup_resources(): clear_temp_ip_records(); clear_session_pool()

def get_proxies():
    # 【修改】: 强制直连，忽略所有代理配置。
    return None

    # --- 以下是保留的原始代码 ---
    global _temp_ip_usage, _temp_used_ips, _proxy_lock, _ip_cache_pool, _ip_cache_lock
    proxy_status = middleware.bucketGet('yuhua_zglt', 'status') or '0'
    proxy_addr = middleware.bucketGet('yuhua_zglt', 'proxy') or ''
    if proxy_status not in ['0', '1', '2'] or proxy_status == '0' or not proxy_addr.strip(): return None
    proxy_addr = proxy_addr.strip()
    if proxy_status == '1':
        if not (proxy_addr.startswith('http://') or proxy_addr.startswith('https://')): return None
        return {"http": proxy_addr, "https": proxy_addr}
    if proxy_status == '2':
        ip_limit = get_ip_limit()
        for _ in range(20):
            candidate_ip = None
            with _ip_cache_lock:
                if _ip_cache_pool: candidate_ip = _ip_cache_pool.pop(0)
            if not candidate_ip:
                with _ip_cache_lock:
                    if _ip_cache_pool: candidate_ip = _ip_cache_pool.pop(0)
                    else:
                        try:
                            # 强制无代理请求获取 API，防止本地全局代理导致死循环
                            r = requests.get(proxy_addr, timeout=5, proxies={"http": None, "https": None})
                            if r.status_code == 200:
                                ips = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+', r.text)
                                if ips: _ip_cache_pool.extend(ips); candidate_ip = _ip_cache_pool.pop(0)
                        except Exception: pass
            if candidate_ip:
                ip_val = candidate_ip.split(':')[0]
                should_skip = False
                with _proxy_lock:
                    # 核心修复：无论 ip_limit 是否为 0，都必须优先拦截黑名单中已被 403 风控的废弃 IP
                    if ip_val in _temp_used_ips:
                        should_skip = True
                    else:
                        if ip_limit > 0:
                            if _temp_ip_usage.get(ip_val, 0) >= ip_limit:
                                _temp_used_ips.add(ip_val); should_skip = True
                            else:
                                _temp_ip_usage[ip_val] = _temp_ip_usage.get(ip_val, 0) + 1
                if should_skip: continue
                return {"http": f"http://{candidate_ip}", "https": f"http://{candidate_ip}"}
            time.sleep(random.uniform(0.5, 1.0))
    return None

def _get_session_by_proxy(proxies):
    proxy_key = json.dumps(proxies, sort_keys=True) if proxies else "direct"
    if proxy_key not in _session_pool or getattr(_session_pool[proxy_key], "_closed", False):
        sess = requests.Session()
        # 移除了会导致雪崩的 HTTPAdapter(max_retries=3) 挂载，将重试权彻底移交给上层
        sess.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Linux; Android 15; OPD2407 Build/UKQ1.231108.001; wv) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/142.0.7444.32 '
                'Safari/537.36/woapp LianTongYunPan/5.0.7 (Android 15)'
            )
        })
        if proxies: sess.proxies.update(proxies)
        _session_pool[proxy_key] = sess
    return _session_pool[proxy_key]

# --- 验证码登录相关常量 (radomLogin.htm) ---
VERIFICATION_LOGIN_URL = "https://m.client.10010.com/mobileService/radomLogin.htm"
VERIFICATION_APP_ID = "06eccb0b7c2fd02bc1bb5e8a9ca2874175f50d8af589ecbd499a7c937a2fda7754dc135192b3745bd20073a687faee1755c67fab695164a090edd8e0da8771b83913890a44ec38e628cf2445bc476dfd"
VERIFICATION_KEY_VERSION = "1"
VERIFICATION_DEVICE_PARAMS = {
    "deviceOS": "android15",
    "netWay": "Wifi",
    "deviceCode": "12b46022d1f94f67973f6923d619ca1f",
    "version": "android@12.0500",
    "deviceId": "12b46022d1f94f67973f6923d619ca1f",
    "pip": "192.168.7.234",
    "simOperator": "1%2C--%2C--%2C--%2C--%401%2C--%2C--%2C--%2C--",
    "deviceModel": "OPD2407",
    "androidId": "108dea287b0317f4",
    "deviceBrand": "OnePlus",
    "uniqueIdentifier": "anda62d4d2b15888868200f59f61c27b1b29"
}

# --- 账号密码登录相关常量 ---
# 联通登录接口
LOGIN_URL = "https://m.client.10010.com/mobileService/login.htm"
TICKET_URL = "https://m.client.10010.com/edop_ng/getTicketByNative"
ACCESS_TOKEN_URL = "https://panservice.mail.wo.cn/wohome/dispatcher"
CLOUD_DISK_APP_ID = "edop_unicom_d67b3e30"

# 登录固定参数
LOGIN_APP_ID = "06eccb0b7c2fd02bc1bb5e8a9ca2874175f50d8af589ecbd499a7c937a2fda7754dc135192b3745bd20073a687faee1755c67fab695164a090edd8e0da8771b83913890a44ec38e628cf2445bc476dfd"
LOGIN_KEY_VERSION = "2"
LOGIN_VOIP_TOKEN = "citc-default-token-do-not-push"
LOGIN_IS_FIRST_INSTALL = "1"
LOGIN_IS_REMEMBER_PWD = "false"
LOGIN_SIM_COUNT = "1"
LOGIN_NET_WAY = "wifi"

# RSA加密相关
PUBLIC_KEY_BASE64 = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDc+CZK9bBA9IU+gZUOc6FUGu7yO9WpTNB0PzmgFBh96Mg1WrovD1oqZ+eIF4LjvxKXGOdI79JRdve9NPhQo07+uqGQgE4imwNnRx7PFtCRryiIEcUoavuNtuRVoBAm6qdB0SrctgaqGfLgKvZHOnwTjyNqjBUxzMeQlEC2czEMSwIDAQAB"
DEFAULT_SPLIT = "#PART#"
MAX_BLOCK_SIZE = 117

# --- 阅读专区加密常量 ---
WOREAD_KEY = b"woreadst^&*12345"
WOREAD_IV = b"16-Bytes--String"
WOREAD_PRODUCT_ID = "10000002"
WOREAD_SECRET = "7k1HcDL8RKvc"

def split_long_message(msg, max_length=4000):
    if len(msg) <= max_length: return [msg]
    parts = []; current_pos = 0
    while current_pos < len(msg):
        end_pos = current_pos + max_length
        if end_pos >= len(msg): parts.append(msg[current_pos:]); break
        split_pos = msg.rfind('\n', current_pos, end_pos)
        if split_pos == -1 or split_pos <= current_pos: split_pos = end_pos
        parts.append(msg[current_pos:split_pos]); current_pos = split_pos + (1 if split_pos < end_pos else 0)
    return parts

def safe_reply(sender, msg):
    parts = split_long_message(msg)
    for i, part in enumerate(parts):
        if i > 0: time.sleep(random.uniform(0.02, 0.05))
        sender.reply(part)

# --- 账号密码登录相关函数 ---
def load_rsa_public_key():
    """加载RSA公钥"""
    try:
        public_key_der = base64.b64decode(PUBLIC_KEY_BASE64)
        public_key = serialization.load_der_public_key(public_key_der)
        return public_key
    except Exception as e:
        if DEBUG:
            print(f"❌ RSA公钥加载失败: {e}")
        return None

def rsa_encrypt(plaintext, key):
    """RSA加密函数"""
    plaintext_bytes = plaintext.encode('utf-8')
    if len(plaintext_bytes) <= MAX_BLOCK_SIZE:
        return key.encrypt(plaintext_bytes, padding.PKCS1v15())
    encrypted_blocks = []
    for i in range(0, len(plaintext_bytes), MAX_BLOCK_SIZE):
        block = plaintext_bytes[i:i + MAX_BLOCK_SIZE]
        encrypted_block = key.encrypt(block, padding.PKCS1v15())
        if i > 0: encrypted_blocks.append(DEFAULT_SPLIT.encode('utf-8'))
        encrypted_blocks.append(encrypted_block)
    return b''.join(encrypted_blocks)

def mobile_encrypt(data, public_key):
    """手机号加密"""
    encrypted_bytes = rsa_encrypt(data, public_key)
    return base64.b64encode(encrypted_bytes).decode('utf-8').replace('\n', '')

def password_encrypt(password, public_key, random_str="000000"):
    """密码加密"""
    return mobile_encrypt(password + random_str, public_key)

def encrypt_for_api(data, public_key):
    """执行加密并进行Base64编码，用于API请求（验证码登录专用）"""
    plaintext_bytes = data.encode('utf-8')
    max_block_size = 117
    encrypted_blocks = []
    for i in range(0, len(plaintext_bytes), max_block_size):
        block = plaintext_bytes[i:i + max_block_size]
        encrypted_blocks.append(public_key.encrypt(block, padding.PKCS1v15()))
    encrypted_bytes = b''.join(encrypted_blocks)
    return base64.b64encode(encrypted_bytes).decode('utf-8')

# --- 阅读专区 AES 加密 ---
def woread_encrypt(text):
    """AES-CBC-PKCS7 加密 (1:1 复刻 JS: JSON无空格 -> AES -> HexStr -> Base64)"""
    try:
        if isinstance(text, dict):
            text = json.dumps(text, separators=(',', ':'))
        
        cipher = AES.new(WOREAD_KEY, AES.MODE_CBC, WOREAD_IV)
        pad_text = pad(text.encode('utf-8'), AES.block_size)
        encrypted_bytes = cipher.encrypt(pad_text)
        
        hex_str = encrypted_bytes.hex()
        
        return base64.b64encode(hex_str.encode('utf-8')).decode('utf-8')
    except Exception as e:
        return ""

def _perform_login_and_get_token(phone, password):
    public_key = load_rsa_public_key()
    if not public_key: return None, None, None, "加密公钥加载失败"
    try:
        mobile_encrypted = mobile_encrypt(phone, public_key)
        password_encrypted = password_encrypt(password, public_key)
    except Exception: return None, None, None, "加密过程出错"
    device_id = hashlib.md5(phone.encode()).hexdigest()
    payload = {"voipToken": LOGIN_VOIP_TOKEN, "deviceBrand": "iPhone", "simOperator": "--,%E4%B8%AD%E5%9B%BD%E7%A7%BB%E5%8A%A8,--,--,--", "deviceId": device_id, "netWay": LOGIN_NET_WAY, "deviceCode": device_id, "deviceOS": "15.8.3", "uniqueIdentifier": device_id, "version": "iphone_c@12.0200", "pip": "192.168.5.14", "isFirstInstall": LOGIN_IS_FIRST_INSTALL, "keyVersion": LOGIN_KEY_VERSION, "simCount": LOGIN_SIM_COUNT, "mobile": mobile_encrypted, "isRemberPwd": LOGIN_IS_REMEMBER_PWD, "appId": LOGIN_APP_ID, "reqtime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "deviceModel": "iPhone8,2", "password": password_encrypted}
    headers = {"Host": "m.client.10010.com", "Content-Type": "application/x-www-form-urlencoded", "Connection": "keep-alive", "Accept": "*/*", "User-Agent": "ChinaUnicom4.x/12.2 (com.chinaunicom.mobilebusiness; build:44; iOS 15.8.3) Alamofire/4.7.3 unicom{version:iphone_c@12.0200}", "Accept-Language": "zh-CN,zh-Hans;q=0.9"}
    
    with requests.Session() as sess:
        response = send_request_global('POST', LOGIN_URL, data=payload, headers=headers, session=sess)
        if not response: return None, None, None, "登录请求失败"
        try: data = response.json()
        except json.JSONDecodeError: return None, None, None, "登录响应解析失败"
        if data.get("code") not in ["0", "0000"]: return None, None, None, data.get('desc', '未知错误')
        token_online = data.get("token_online", "")
        cookie_string = "; ".join([f"{c.name}={c.value}" for c in response.cookies])
        
    # 核心优化：彻底删除云盘鉴权，使用 dummy_token 兼容解包结构
    return "dummy_token", cookie_string, token_online, None

def _perform_verification_code_login_and_get_token(phone, verification_code):
    public_key = load_rsa_public_key() 
    if not public_key: return None, None, None, "加密公钥加载失败" 
    try: 
        mobile_encrypted = encrypt_for_api(phone, public_key) 
        password_encrypted = encrypt_for_api(verification_code, public_key) 
    except Exception as e: return None, None, None, f"加密过程出错: {e}" 
    payload = {"isFirstInstall": "1", "yw_code": "", "loginStyle": "0", "isRemberPwd": "true", "provinceChanel": "general", "voice_code": "", "voiceoff_flag": "1", "timestamp": datetime.now().strftime('%Y%m%d%H%M%S'), "mobile": mobile_encrypted, "password": password_encrypted, "appId": VERIFICATION_APP_ID, "keyVersion": VERIFICATION_KEY_VERSION, **VERIFICATION_DEVICE_PARAMS} 
    ua = (f"Dalvik/2.1.0 (Linux; U; Android {VERIFICATION_DEVICE_PARAMS.get('deviceOS', '15')}; " f"{VERIFICATION_DEVICE_PARAMS.get('deviceModel', 'OPD2407')} Build/UKQ1.231108.001);" f"unicom{{version:{VERIFICATION_DEVICE_PARAMS.get('version', 'android@12.0500')}}};ltst;") 
    headers = {"User-Agent": ua, "Content-Type": "application/x-www-form-urlencoded", "Connection": "keep-alive", "Accept": "*/*"} 
    
    with requests.Session() as sess:
        response = send_request_global('POST', VERIFICATION_LOGIN_URL, data=payload, headers=headers, session=sess) 
        if not response: return None, None, None, "登录请求失败，网络或服务器无响应" 
        try: data = response.json() 
        except json.JSONDecodeError: return None, None, None, f"登录响应解析失败: {response.text[:200]}" 
        if data.get("code") != "0": return None, None, None, data.get('desc', '登录失败，未知错误') 
        token_online = data.get("token_online", "")
        cookie_string = "; ".join([f"{c.name}={c.value}" for c in response.cookies]) 
    
    # 核心优化：彻底删除云盘鉴权，直接返回核心 ecs_token
    return "dummy_token", cookie_string, token_online, None

def token_online_login():
    """
    【token_online登录功能】
    参考联通云盘插件的风格，通过 token_online 换取凭证
    """
    guide = """
=====账号登录=====
❶ 通过抓包工具获取中国联通的token_online
❷ 按如下格式发送
『token_online#手机号』例: 66666666-1f66-4bde-66666-aaaaaaaaaaaa#18888888888
------------------
回复"q"退出"""
    sender.reply(guide)
    user_input = sender.input(60000, 1, False)
    
    if not user_input:
        sender.reply("❌ 输入超时")
        return
    elif user_input.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    
    parts = user_input.split('#')
    token_online = parts[0].strip()
    phone = parts[1].strip() if len(parts) > 1 else ""

    if not token_online or not re.match(r'^\d{11}$', phone):
        sender.reply("❌ 格式错误，请确保格式为: token_online#11位手机号")
        return

    sender.reply("正在验证凭证有效性...")

    try:
        pl = {
            "token_online": token_online, 
            "reqtime": int(time.time()*1000), 
            "isFirstInstall": "1", 
            "provinceChanel": "general", 
            **VERIFICATION_DEVICE_PARAMS
        }
        
        ua = f"Dalvik/2.1.0 (Linux; U; Android {VERIFICATION_DEVICE_PARAMS.get('deviceOS')}; {VERIFICATION_DEVICE_PARAMS.get('deviceModel')} Build/UKQ1.231108.001);unicom{{version:{VERIFICATION_DEVICE_PARAMS.get('version')}}};ltst;"
        hd = {
            "User-Agent": ua, 
            "Content-Type": "application/x-www-form-urlencoded", 
            "Host": "m.client.10010.com"
        }
        
        with requests.Session() as sess:
            resp = send_request_global('POST', "https://m.client.10010.com/mobileService/onLine.htm", data=pl, headers=hd, session=sess)
        
        if not resp:
            sender.reply("❌ 登录失败: 网络请求无响应")
            return
            
        try:
            rj = resp.json()
        except json.JSONDecodeError:
            sender.reply("❌ 登录失败: 响应解析错误")
            return

        if rj.get('code') not in ['0', '0000']:
            # 优先获取 dsc，其次 desc
            fail_reason = rj.get('dsc') or rj.get('desc') or '凭证已失效'
            sender.reply(f"❌ 登录失败: {fail_reason}")
            return
            
        cookie_string = "; ".join([f"{c.name}={c.value}" for c in resp.cookies])
        if not cookie_string:
            sender.reply("❌ 登录失败: 未获取到Cookie")
            return
            
        # 核心优化：彻底废除云盘Ticket获取，直接使用轻量级商城探活
        ltp_check = LTP(ecs_token=cookie_string)
        ok, msg = ltp_check.check_validity()
        ltp_check.close()
        
        if not ok:
            sender.reply(f"❌ 登录失败: Cookie验证失败，{msg}")
            return
            
        access_token = "dummy_token"

        accounts = eval(uservalue or '[]')
        matched_uid = None
        for uid in accounts:
            old_phone = middleware.bucketGet('yuhua_zglt_phone', uid) or "未知"
            if old_phone == phone:
                matched_uid = uid
                break
        
        final_uid = matched_uid if matched_uid else gen_unique_id()
        
        # --- 新增配置AppId流程 ---
        existing_appid = middleware.bucketGet('yuhua_zglt_appid', final_uid)
        if not existing_appid:
            sender.reply("""=====添加AppId=====
❶ 该步骤非强制性，可选择取消
❷ 打开该路径中的文件『/storage/emulated/0/Documents/Unicom/appid』复制文本内容并回复
-----------------
请在300秒内完成
回复"q"取消""")
            app_input = sender.input(300000, 1, False)
            if not app_input:
                sender.reply("❌ 输入超时")
            elif app_input.lower() == 'q':
                sender.reply("✅ 已取消操作")
            else:
                new_appid = app_input.strip()
                # 鉴权测试
                pl["appId"] = new_appid
                with requests.Session() as sess:
                    test_resp = send_request_global('POST', "https://m.client.10010.com/mobileService/onLine.htm", data=pl, headers=hd, session=sess)
                if test_resp:
                    rj_test = test_resp.json()
                    if rj_test.get('code') in ['0', '0000']:
                        middleware.bucketSet('yuhua_zglt_appid', final_uid, new_appid)
                        sender.reply("✅ 已成功添加")
                    else:
                        # 优先获取 dsc，其次 desc
                        fail_reason = rj_test.get('dsc') or rj_test.get('desc') or '未知原因'
                        sender.reply(f"❌ 鉴权失败: {fail_reason}")
                else:
                    sender.reply("❌ 鉴权失败: 网络请求无响应")

        if matched_uid:
            middleware.bucketSet('yuhua_zglt_token', matched_uid, access_token)
            middleware.bucketSet('yuhua_zglt_ecs_token', matched_uid, cookie_string)
            middleware.bucketSet('yuhua_zglt_token_online', matched_uid, token_online)
            try:
                middleware.bucketDel('yuhua_zglt_password', matched_uid)
            except Exception:
                pass
            
            phone_mask = phone[:3] + "****" + phone[-4:]
            sender.reply(f"""
=====登录成功=====
🤪 账号: {phone_mask}
✅ 状态: 更新成功
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")
        else:
            accounts.append(final_uid)
            middleware.bucketSet('yuhua_zglt_user', userid, str(accounts))
            middleware.bucketSet('yuhua_zglt_token', final_uid, access_token)
            middleware.bucketSet('yuhua_zglt_phone', final_uid, phone)
            middleware.bucketSet('yuhua_zglt_ecs_token', final_uid, cookie_string)
            middleware.bucketSet('yuhua_zglt_token_online', final_uid, token_online)
            
            phone_mask = phone[:3] + "****" + phone[-4:]
            sender.reply(f"""
=====登录成功=====
🤪 账号: {phone_mask}
✅ 状态: 添加成功
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")

        accountVip = middleware.bucketGet(bucket='yuhua_zglt_auth', key=final_uid)
        if accountVip and accountVip >= today_time:
            try:
                sync_appid = middleware.bucketGet('yuhua_zglt_appid', final_uid)
                sync_val = f"{token_online}#{sync_appid}" if sync_appid else token_online
                Addenvs(osname=yuhua_zglt_osname, value=sync_val, account=final_uid, phone=phone, owner_id=userid)
                
                # --- 新增：爱听变量提交 ---
                if aiting_var and aiting_var != '0':
                    Addenvs(osname=aiting_var, value=phone, account=final_uid, phone=phone, owner_id=userid)
            except Exception as e:
                if DEBUG: print(f"青龙同步失败: {e}")

    except Exception as e:
        sender.reply(f"❌ 登录失败: {str(e)}")


def verification_code_login(): 
    """ 
    【API短信登录功能】： 
    引导用户输入手机号和验证码，通过API直接登录。 
    """ 
    sender.reply(f"""
=====短信登录=====
请输入中国联通手机号
------------------
请在60秒内完成
回复"q"退出""")    
    phone = sender.input(60000, 1, False) 
    if not phone: 
        sender.reply("❌ 输入超时") 
        return 
    phone = phone.strip() 
    if phone.lower() == 'q': 
        sender.reply("✅ 已退出操作") 
        return 
    if not re.match(r'^\d{11}$', phone): 
        sender.reply("❌ 请输入正确的11位手机号") 
        return 
        
    # 手机号脱敏显示
    masked_phone = phone[:3] + "****" + phone[-4:]
    sender.reply(f"""=====短信登录=====
❶打开『中国联通App』使用手机号{masked_phone}获取登录验证码
❷ 回复收到的6位数字验证码
------------------
请在120秒内完成
回复"q"取消""") 
    code = sender.input(120000, 1, False) 
    if not code: 
        sender.reply("❌ 输入超时") 
        return 
    code = code.strip() 
    if code.lower() == 'q': 
        sender.reply("✅ 已退出操作") 
        return       
    sender.reply("正在通过API登录，请稍候...")
    access_token, cookie_string, token_online, error_message = _perform_verification_code_login_and_get_token(phone, code)
    if not cookie_string:
        sender.reply(f"❌ 登录失败: {error_message}")
        return
    # 核心优化：使用商城接口进行轻量级探活，替代云盘 Ticket 校验
    ltp_check = LTP(ecs_token=cookie_string, phone=phone)
    ok, msg = ltp_check.check_validity()
    ltp_check.close()
    
    if not ok:
        sender.reply(f"❌ 凭证校验失败: {msg}")
        return

    # 登录成功后的账号处理逻辑 (与账密登录一致) 
    accounts = eval(uservalue or '[]') 
    matched_uid = None 
    for uid in accounts: 
        if (middleware.bucketGet('yuhua_zglt_phone', uid) or "未知") == phone: 
            matched_uid = uid 
            break 
            
    final_uid = matched_uid if matched_uid else gen_unique_id()
    
    # --- 新增配置AppId流程 ---
    existing_appid = middleware.bucketGet('yuhua_zglt_appid', final_uid)
    if not existing_appid:
        sender.reply("""=====添加AppId=====
❶ 该步骤非强制性，可选择取消
❷ 打开该路径中的文件『/storage/emulated/0/Documents/Unicom/appid』复制文本内容并回复
-----------------
请在300秒内完成
回复"q"取消""")
        app_input = sender.input(300000, 1, False)
        if not app_input:
            sender.reply("❌ 输入超时")
        elif app_input.lower() == 'q':
            sender.reply("✅ 已取消操作")
        else:
            new_appid = app_input.strip()
            # 鉴权测试
            pl_test = {"token_online": token_online, "appId": new_appid, "reqtime": int(time.time()*1000), **VERIFICATION_DEVICE_PARAMS}
            ua_test = f"Dalvik/2.1.0 (Linux; U; Android {VERIFICATION_DEVICE_PARAMS.get('deviceOS')}; {VERIFICATION_DEVICE_PARAMS.get('deviceModel')} Build/UKQ1.231108.001);unicom{{version:{VERIFICATION_DEVICE_PARAMS.get('version')}}};ltst;"
            hd_test = {"User-Agent": ua_test, "Content-Type": "application/x-www-form-urlencoded", "Host": "m.client.10010.com"}
            with requests.Session() as sess:
                test_resp = send_request_global('POST', "https://m.client.10010.com/mobileService/onLine.htm", data=pl_test, headers=hd_test, session=sess)
            if test_resp:
                rj_test = test_resp.json()
                if rj_test.get('code') in ['0', '0000']:
                    middleware.bucketSet('yuhua_zglt_appid', final_uid, new_appid)
                    sender.reply("✅ 已成功添加")
                else:
                    # 优先获取 dsc
                    fail_reason = rj_test.get('dsc') or rj_test.get('desc') or '未知原因'
                    sender.reply(f"❌ 鉴权失败: {fail_reason}")
            else:
                sender.reply("❌ 鉴权失败: 网络请求无响应")

    if matched_uid: 
        middleware.bucketSet('yuhua_zglt_token', matched_uid, access_token) 
        middleware.bucketSet('yuhua_zglt_ecs_token', matched_uid, cookie_string) 
        # 短信登录成功后，清除可能已失效的静态密码
        if token_online: middleware.bucketSet('yuhua_zglt_token_online', matched_uid, token_online)
        try:
            middleware.bucketDel('yuhua_zglt_password', matched_uid) 
        except Exception:
            pass
        sender.reply(f"=====登录成功=====\n🤪 账号: {_mask_identifier(phone)}\n✅ 状态: 更新成功\n------------------\n发送\"{manage_cmd}\"管理账号\n发送\"{query_cmd}\"查询账号") 
    else: 
        accounts.append(final_uid) 
        middleware.bucketSet('yuhua_zglt_user', userid, str(accounts)) 
        middleware.bucketSet('yuhua_zglt_token', final_uid, access_token) 
        middleware.bucketSet('yuhua_zglt_phone', final_uid, phone) 
        middleware.bucketSet('yuhua_zglt_ecs_token', final_uid, cookie_string) 
        if token_online: middleware.bucketSet('yuhua_zglt_token_online', final_uid, token_online)
        sender.reply(f"=====登录成功=====\n🤪 账号: {_mask_identifier(phone)}\n✅ 状态: 添加成功\n------------------\n发送\"{manage_cmd}\"管理账号\n发送\"{query_cmd}\"查询账号") 

    # 同步青龙
    accountVip = middleware.bucketGet(bucket='yuhua_zglt_auth', key=final_uid)
    if accountVip and accountVip >= today_time:
        try:
            sync_online = token_online if token_online else middleware.bucketGet('yuhua_zglt_token_online', final_uid)
            sync_appid = middleware.bucketGet('yuhua_zglt_appid', final_uid)
            if sync_online:
                sync_val = f"{sync_online}#{sync_appid}" if sync_appid else sync_online
                Addenvs(osname=yuhua_zglt_osname, value=sync_val, account=final_uid, phone=phone, owner_id=userid)
                
                # --- 新增：爱听变量提交 ---
                if aiting_var and aiting_var != '0':
                    Addenvs(osname=aiting_var, value=phone, account=final_uid, phone=phone, owner_id=userid)
        except Exception as e:
            sender.reply(f"""
=====青龙更新失败=====
❌ 更新青龙变量失败
⚠️ 错误: {str(e)}
==================""")

def _try_auto_relogin(account_id):
    """精简版智能续期：仅刷新 ecs_token 或走账密兜底，彻底废除云盘流程"""
    token_online = middleware.bucketGet('yuhua_zglt_token_online', account_id)
    appid = middleware.bucketGet('yuhua_zglt_appid', account_id)
    if token_online:
        try:
            pl = {"token_online": token_online, "reqtime": int(time.time()*1000), "isFirstInstall": "1", "provinceChanel": "general", **VERIFICATION_DEVICE_PARAMS}
            if appid: pl["appId"] = appid
            ua = f"Dalvik/2.1.0 (Linux; U; Android {VERIFICATION_DEVICE_PARAMS.get('deviceOS')}; {VERIFICATION_DEVICE_PARAMS.get('deviceModel')} Build/UKQ1.231108.001);unicom{{version:{VERIFICATION_DEVICE_PARAMS.get('version')}}};ltst;"
            hd = {"User-Agent": ua, "Content-Type": "application/x-www-form-urlencoded", "Host": "m.client.10010.com"}
            resp = send_request_global('POST', "https://m.client.10010.com/mobileService/onLine.htm", data=pl, headers=hd)
            if resp:
                rj = resp.json()
                if rj.get('code') in ['0', '0000']:
                    cks = "; ".join([f"{c.name}={c.value}" for c in resp.cookies])
                    if cks:
                        middleware.bucketSet('yuhua_zglt_ecs_token', account_id, cks)
                        middleware.bucketSet('yuhua_zglt_token', account_id, "dummy_token") # 兼容旧本地结构占位
                        return True
        except: pass
        
    ph = middleware.bucketGet('yuhua_zglt_phone', account_id)
    pw = middleware.bucketGet('yuhua_zglt_password', account_id)
    if ph and pw:
        at, ck, to, err = _perform_login_and_get_token(ph, pw)
        if ck:
            middleware.bucketSet('yuhua_zglt_token', account_id, "dummy_token")
            middleware.bucketSet('yuhua_zglt_ecs_token', account_id, ck)
            if to: 
                middleware.bucketSet('yuhua_zglt_token_online', account_id, to)
                try:
                    auth_time = middleware.bucketGet('yuhua_zglt_auth', account_id)
                    if auth_time and auth_time >= str(datetime.now().date()):
                        real_owner = userid
                        try:
                            all_users = middleware.bucketAllKeys('yuhua_zglt_user')
                            for u in all_users:
                                user_accs = eval(middleware.bucketGet('yuhua_zglt_user', u) or '[]')
                                if account_id in user_accs:
                                    real_owner = u
                                    break
                        except: pass
                        sync_appid = middleware.bucketGet('yuhua_zglt_appid', account_id)
                        sync_val = f"{to}#{sync_appid}" if sync_appid else to
                        Addenvs(osname=yuhua_zglt_osname, value=sync_val, account=account_id, phone=ph, owner_id=real_owner)
                except Exception as e:
                    if DEBUG: print(f"自动刷新同步青龙失败: {e}")
            return True
    return False

def account_password_login():
    """
    【账号密码登录功能】：
    使用账号密码直接登录联通云盘
    """
    sender.reply("请输入手机号:")
    phone = sender.input(30000, 1, False)
    if not phone:
        sender.reply("❌ 输入超时")
        return
    phone = phone.strip()
    if phone.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    if not re.match(r'^\d{11}$', phone):
        sender.reply("❌ 请输入正确的11位手机号")
        return
    sender.reply("请输入密码:")
    password = sender.input(30000, 1, False)
    if not password:
        sender.reply("❌ 输入超时")
        return
    password = password.strip()
    if password.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    sender.reply("正在登录中，请稍候...")
    access_token, cookie_string, token_online, error_message = _perform_login_and_get_token(phone, password)
    if not access_token:
        sender.reply(f"❌ 登录失败: {error_message}")
        return
    ltp_check = LTP(access_token, phone=phone)
    ok, msg = ltp_check.get_ticket()
    ltp_check.close()
    if not ok:
        sender.reply(f"❌ 凭证校验失败: {msg}")
        return
    accounts = eval(uservalue or '[]')
    matched_uid = None
    for uid in accounts:
        old_phone = middleware.bucketGet('yuhua_zglt_phone', uid) or "未知"
        if old_phone == phone:
            matched_uid = uid
            break
            
    final_uid = matched_uid if matched_uid else gen_unique_id()

    # --- 新增配置AppId流程 ---
    existing_appid = middleware.bucketGet('yuhua_zglt_appid', final_uid)
    if not existing_appid:
        sender.reply("""=====添加AppId=====
❶ 该步骤非强制性，可选择取消
❷ 打开该路径中的文件『/storage/emulated/0/Documents/Unicom/appid』复制文本内容并回复
-----------------
请在300秒内完成
回复"q"取消""")
        app_input = sender.input(300000, 1, False)
        if not app_input:
            sender.reply("❌ 输入超时")
        elif app_input.lower() == 'q':
            sender.reply("✅ 已取消操作")
        else:
            new_appid = app_input.strip()
            # 鉴权测试
            if token_online:
                pl_test = {"token_online": token_online, "appId": new_appid, "reqtime": int(time.time()*1000), **VERIFICATION_DEVICE_PARAMS}
                ua_test = f"Dalvik/2.1.0 (Linux; U; Android {VERIFICATION_DEVICE_PARAMS.get('deviceOS')}; {VERIFICATION_DEVICE_PARAMS.get('deviceModel')} Build/UKQ1.231108.001);unicom{{version:{VERIFICATION_DEVICE_PARAMS.get('version')}}};ltst;"
                hd_test = {"User-Agent": ua_test, "Content-Type": "application/x-www-form-urlencoded", "Host": "m.client.10010.com"}
                with requests.Session() as sess:
                    test_resp = send_request_global('POST', "https://m.client.10010.com/mobileService/onLine.htm", data=pl_test, headers=hd_test, session=sess)
                if test_resp:
                    rj_test = test_resp.json()
                    if rj_test.get('code') in['0', '0000']:
                        middleware.bucketSet('yuhua_zglt_appid', final_uid, new_appid)
                        sender.reply("✅ 已成功添加")
                    else:
                        # 优先获取 dsc
                        fail_reason = rj_test.get('dsc') or rj_test.get('desc') or '未知原因'
                        sender.reply(f"❌ 鉴权失败: {fail_reason}")
                else:
                    sender.reply("❌ 鉴权失败: 网络请求无响应")

    if matched_uid:
        middleware.bucketSet('yuhua_zglt_token', matched_uid, access_token)
        middleware.bucketSet('yuhua_zglt_password', matched_uid, password)
        middleware.bucketSet('yuhua_zglt_ecs_token', matched_uid, cookie_string)
        if token_online: middleware.bucketSet('yuhua_zglt_token_online', matched_uid, token_online)
        phone_mask = phone[:3] + "****" + phone[-4:]
        sender.reply(f"""
=====登录成功=====
🤪 账号: {phone_mask}
✅ 状态: 更新成功
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")
    else:
        accounts.append(final_uid)
        middleware.bucketSet('yuhua_zglt_user', userid, str(accounts))
        middleware.bucketSet('yuhua_zglt_token', final_uid, access_token)
        middleware.bucketSet('yuhua_zglt_phone', final_uid, phone)
        middleware.bucketSet('yuhua_zglt_password', final_uid, password)
        middleware.bucketSet('yuhua_zglt_ecs_token', final_uid, cookie_string)
        if token_online: middleware.bucketSet('yuhua_zglt_token_online', final_uid, token_online)
        phone_mask = phone[:3] + "****" + phone[-4:]
        sender.reply(f"""
=====登录成功=====
🤪 账号: {phone_mask}
✅ 状态: 添加成功
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")

    # 同步青龙
    accountVip = middleware.bucketGet(bucket='yuhua_zglt_auth', key=final_uid)
    if accountVip and accountVip >= today_time:
        try:
            sync_online = token_online if token_online else middleware.bucketGet('yuhua_zglt_token_online', final_uid)
            sync_appid = middleware.bucketGet('yuhua_zglt_appid', final_uid)
            if sync_online:
                sync_val = f"{sync_online}#{sync_appid}" if sync_appid else sync_online
                Addenvs(osname=yuhua_zglt_osname, value=sync_val, account=final_uid, phone=phone, owner_id=userid)
                
                # --- 新增：爱听变量提交 ---
                if aiting_var and aiting_var != '0':
                    Addenvs(osname=aiting_var, value=phone, account=final_uid, phone=phone, owner_id=userid)
        except Exception as e:
            sender.reply(f"""
=====青龙更新失败=====
❌ 更新青龙变量失败
⚠️ 错误: {str(e)}
==================""")


def get_global_session():
    return _get_session_by_proxy(None)

def send_request_global(method, url, **kwargs):
    global _temp_used_ips, _proxy_lock
    passed_session = kwargs.pop('session', None)
    
    # 【修改】: 强制直连，直接将代理设置为 None，并注释掉原始代码。
    current_proxies = None
    # proxy_status = middleware.bucketGet('yuhua_zglt', 'status') or '0'
    
    consecutive_403_count = 0
    
    # 针对 autman 框架特性，缩短网络超时，避免假死阻塞挂起
    # (5, 15) 代表：建立 TCP 连接最长 5 秒，等待接口返回数据最长 15 秒
    kwargs.setdefault('timeout', (10, 15))
    
    if DEBUG:
        printf(f"\n===== [REQUEST START] =====", "DEBUG")
        printf(f"METHOD: {method} | URL: {url}", "DEBUG")
        printf(f"HEADERS: {json.dumps(kwargs.get('headers', {}), ensure_ascii=False)}", "DEBUG")
        if kwargs.get('json'):
            printf(f"BODY(JSON): {json.dumps(kwargs.get('json'), indent=2, ensure_ascii=False)}", "DEBUG")
        elif kwargs.get('data'):
            data_str = str(kwargs.get('data'))
            if len(data_str) > 500: data_str = data_str[:200] + "...(truncated)..."
            printf(f"BODY(DATA): {data_str}", "DEBUG")

    for attempt in range(3):
        # 【修改】: 由于已强制直连，故注释掉代理切换逻辑以保留代码。
        # if proxy_status != '0' and not current_proxies:
        #     current_proxies = get_proxies()
        #     if not current_proxies:
        #         if attempt < 2: time.sleep(random.uniform(0.2, 0.5)); continue
        #         else: raise Exception("代理获取失败，为防止多号同IP风控，已拦截直连请求")
        try:
            session = passed_session if passed_session else _get_session_by_proxy(current_proxies)
            kwargs["proxies"] = current_proxies
            response = session.request(method, url, **kwargs)
            
            if DEBUG:
                printf(f"-----[RESPONSE - Attempt {attempt+1}] -----", "DEBUG")
                printf(f"STATUS: {response.status_code}", "DEBUG")
                try:
                    printf(f"RSP HEADERS: {json.dumps(dict(response.headers), ensure_ascii=False)}", "DEBUG")
                    rsp_text = response.text
                    if len(rsp_text) < 1000: printf(f"RSP BODY: {rsp_text}", "DEBUG")
                    else: printf(f"RSP BODY: {rsp_text[:500]}...(truncated)", "DEBUG")
                except: pass
                printf(f"=====[REQUEST END] =====\n", "DEBUG")

            if response.status_code == 403:
                # 修复BUG：发现403立即精准定位并拉黑当前导致403的IP，防止下一个IP背锅
                # 【修改】: 此处逻辑依赖代理，直连模式下无需操作，保留代码。
                # if proxy_status == '2' and current_proxies:
                #     ip = extract_ip_from_proxy(current_proxies.get("http", ""))
                #     if ip:
                #         with _proxy_lock: _temp_used_ips.add(ip)
                        
                consecutive_403_count += 1
                if attempt < 2:
                    time.sleep(random.uniform(0.01, 0.05))
                    # 【修改】: 强制直连，无需再获取代理。
                    # current_proxies = get_proxies()
                    continue
                else: raise requests.exceptions.RequestException("IP已被风控")
            else: consecutive_403_count = 0
            
            response.raise_for_status()
            return response
            
        except Exception as e:
            if DEBUG:
                printf(f"⚠️ Attempt {attempt + 1} FAILED (Error): {e}", "WARN")
            # 【隐患二修复】：精准判断异常类型，仅网络层连接失败(代理失效)才拉黑废弃代理，防止错杀
            # 【修改】: 此处逻辑依赖代理，直连模式下无需操作，保留代码。
            # if proxy_status == '2' and current_proxies:
            #     if isinstance(e, (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError)):
            #         ip = extract_ip_from_proxy(current_proxies.get("http", ""))
            #         if ip:
            #             with _proxy_lock: _temp_used_ips.add(ip)
                    
            if "代理获取失败" in str(e) or "已拦截" in str(e): raise e
            
            if attempt == 2:
                error_msg = str(e).lower()
                if "ip已被风控" in error_msg or (consecutive_403_count >= 2 and "403" in error_msg): raise requests.exceptions.RequestException("IP已被风控")
                elif "403" in error_msg: raise requests.exceptions.RequestException("IP已被风控")
                raise e
            else:
                time.sleep(random.uniform(0.01, 0.05) * (attempt + 1))
                # 【修改】: 强制直连，无需再获取代理。
                # current_proxies = get_proxies()
                
    return None


###################### 联通云盘核心类 (LTP) ######################
class LTP:
    def __init__(self, cookie_str=None, phone='未知', session=None, ecs_token=None, token_online=None):
        self.session = session or requests.Session()
        self.ecs_token = ecs_token
        self.token_online = token_online
        self.phone = phone
        self.ua = (
            'Mozilla/5.0 (Linux; Android 15; OPD2407 Build/UKQ1.231108.001; wv) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/142.0.7444.32 '
            'Safari/537.36/woapp LianTongYunPan/5.0.7 (Android 15)'
        )
        self.session.headers.update({'User-Agent': self.ua})
        # 核心防御：绑定账号生命周期的专属代理
        self.proxies = get_proxies()

    def check_validity(self):
        """修复版：严格区分代理网络异常与真实CK失效"""
        if not self.ecs_token: return False, "缺少基础Cookie(ecs_token)"
        try:
            url = "https://act.10010.com/SigninApp/convert/getTelephone"
            headers = {
                "Cookie": self.ecs_token,
                "User-Agent": self.ua,
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json"
            }
            res = self._send_request('POST', url, headers=headers, json={})
            
            # 【核心修复1】如果 res 是 None，说明底层网络请求重试后依然失败，这是IP/网络问题
            if res is None:
                return False, "代理IP不可用或网络请求超时"
                
            data = res.json()
            # 状态码 0000 代表成功，如果没登录会返回其他错误码
            if data.get('status') == '0000':
                return True, "凭证有效"
            else:
                return False, "CK已失效"
        except:
            pass
        return False, "接口响应异常"
        

    def _send_request(self, method, url, **kwargs):
        # 默认注入当前账号绑定的独立隔离 session
        if 'session' not in kwargs:
            kwargs['session'] = self.session
            
        # 校验当前绑定的代理是否在其他并发线程中报废（403拉黑或宕机），如被拉黑则主动刷新
        if self.proxies and middleware.bucketGet('yuhua_zglt', 'status') == '2':
            ip_val = extract_ip_from_proxy(self.proxies.get("http", ""))
            if ip_val:
                is_banned = False
                with _proxy_lock:
                    is_banned = ip_val in _temp_used_ips
                if is_banned:
                    self.proxies = get_proxies()
                    # 【隐患三修复】：代理被拉黑更换时，强制销毁旧的 Session 连接池，防止底层的脏 Socket 导致连接重置
                    if self.session:
                        try:
                            self.session.close()
                        except Exception:
                            pass
                    self.session = requests.Session()
                    self.session.headers.update({'User-Agent': self.ua})
                    kwargs['session'] = self.session
                
        # 强制使用账号专属代理
        if 'proxies' not in kwargs:
            kwargs['proxies'] = self.proxies

        try:
            return send_request_global(method, url, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException):
            return None

    def _get_signin_redpacket(self):
        """查询签到话费红包 (返回: 总额, 即将过期金额, 过期月份)"""
        for _ in range(1):
            try:
                url = "https://act.10010.com/SigninApp/convert/getTelephone"
                headers = {"Cookie": self.ecs_token} if self.ecs_token else {}
                res = self._send_request('POST', url, headers=headers, json={})
                if res:
                    data = res.json()
                    if data.get('status') == '0000':
                        d = data.get('data', {})
                        # needexpNumber: 金额, month: 过期月份(如 "1", "12")
                        return d.get('telephone', '0.00'), d.get('needexpNumber', '0'), str(d.get('month', ''))
            except: 
                pass
            #time.sleep(0.2) # 失败短暂等待
        return "0.00", "0", ""

    def _get_woread_redpacket(self):
        """查询阅读红包 (返回: 总额, 7天内过期金额)"""
        total = "0.00"
        expire_7d = "0"
        if not self.token_online: return total, expire_7d
        
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_1_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 unicom{version:iphone_c@11.0503}"
        ts = int(time.time() * 1000)
        sign_str = f"{WOREAD_PRODUCT_ID}{WOREAD_SECRET}{ts}"
        md5_hash = hashlib.md5(sign_str.encode()).hexdigest()
        date_str = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # 1. 认证 (局部重试)
        access_token = None
        for _ in range(1):
            try:
                auth_sign = woread_encrypt({"timestamp": date_str})
                auth_url = f"https://10010.woread.com.cn/ng_woread_service/rest/app/auth/{WOREAD_PRODUCT_ID}/{ts}/{md5_hash}"
                auth_res = self._send_request('POST', auth_url, json={"sign": auth_sign}, headers={"User-Agent": ua})
                if auth_res and auth_res.json().get('code') == '0000':
                    access_token = auth_res.json().get('data', {}).get('accesstoken')
                    break
            except: pass
            #time.sleep(0.2)
        if not access_token: return total, expire_7d # 认证失败直接退出
        
        # 2. 登录 (局部重试)
        phone_str = self.phone if self.phone and self.phone != "未知" else "13800000000"
        login_inner = {"tokenOnline": woread_encrypt(self.token_online), "phone": woread_encrypt(phone_str), "timestamp": date_str}
        login_sign = woread_encrypt(login_inner)
        headers_login = {"accesstoken": access_token, "User-Agent": ua}
        
        d = None
        for _ in range(1):
            try:
                login_res = self._send_request('POST', "https://10010.woread.com.cn/ng_woread_service/rest/account/login", headers=headers_login, json={"sign": login_sign})
                if login_res and login_res.json().get('code') == '0000':
                    d = login_res.json().get('data', {})
                    break
            except: pass
            #time.sleep(0.2)
        if not d: return total, expire_7d # 登录失败直接退出
        
        # 构造通用参数
        base_param = {
            "timestamp": date_str, "token": d.get('token'), "userid": d.get('userid'),
            "userId": d.get('userid'), "userIndex": d.get('userindex'),
            "userAccount": phone_str, "verifyCode": d.get('verifycode')
        }

        # 3. 查总额 (局部重试)
        q_sign = woread_encrypt(base_param)
        q_url = "https://10010.woread.com.cn/ng_woread_service/rest/phone/vouchers/queryTicketAccount"
        for _ in range(1):
            try:
                q_res = self._send_request('POST', q_url, headers=headers_login, json={"sign": q_sign})
                if q_res and q_res.json().get('code') == '0000':
                    total = f"{(q_res.json().get('data', {}).get('usableNum', 0) / 100):.2f}"
                    break
            except: pass
            #time.sleep(0.2)

        # 4. 查7天过期 (局部重试，不依赖查总额是否成功)
        e_sign = woread_encrypt(base_param) 
        e_url = "https://10010.woread.com.cn/ng_woread_service/rest/phone/vouchers/query7DayExpireTicketValue"
        for _ in range(1):
            try:
                e_res = self._send_request('POST', e_url, headers=headers_login, json={"sign": e_sign})
                if e_res and e_res.json().get('code') == '0000':
                    expire_val = int(e_res.json().get('data', '0'))
                    if expire_val > 0:
                        expire_7d = f"{(expire_val / 100):.2f}"
                    break
            except: pass
            #time.sleep(0.2)
        
        return total, expire_7d

    def _get_epay_balance(self):
        """查询沃立减金 (返回: 总额, 7天内过期总额, 标记字符) - 最终修复版"""
        total = "0.00"
        expire_soon = "0.00"
        tag = "" 
        
        if not self.ecs_token: return total, expire_soon, tag

        # 1. 固定设备指纹，防止会话在鉴权和查询之间失效
        fixed_tongdun = f"chinaunicom-{uuid.uuid4().hex.upper()}"
        fixed_xindun = uuid.uuid4().hex

        def get_biz_str(rptid=""):
            biz_info = {
                "bizChannelCode": "225", "disriBiz": "party", "unionSessionId": "", 
                "stType": "", "stDesmobile": "", "source": "", "rptId": rptid, 
                "ticket": "", "tongdunTokenId": fixed_tongdun, "xindunTokenId": fixed_xindun
            }
            return json.dumps(biz_info, separators=(',', ':'))

        # 2. 获取 Authorization Code (局部重试)
        ticket = ""
        st_type = "02"
        loc = ""
        for _ in range(1):
            try:
                getUrl = f"https://m.client.10010.com/mobileService/openPlatform/openPlatLineNew.htm?to_url=https://epay.10010.com/ci-mps-st-web/?webViewNavIsHidden=webViewNavIsHidden"
                getRes = self._send_request('GET', getUrl, headers={"Cookie": self.ecs_token}, allow_redirects=False)
                if getRes and 'location' in getRes.headers:
                    loc = getRes.headers['location']
                    parsed = urllib.parse.urlparse(loc)
                    qs = urllib.parse.parse_qs(parsed.query)
                    ticket = qs.get('ticket', [''])[0]
                    st_type = qs.get('type', ['02'])[0]
                    if ticket:
                        break
            except: pass
            #time.sleep(0.2)
        if not ticket: return total, expire_soon, tag

        # 3. OAuth 授权 (局部重试)
        auth_success = False
        for _ in range(1):
            try:
                token_id_auth = f"chinaunicom-pro-{int(time.time())}-{random.randint(1000000000000, 9999999999999)}"
                auth_payload = {
                    "response_type": "rptid", "client_id": "73b138fd-250c-4126-94e2-48cbcc8b9cbe",
                    "redirect_uri": "https://epay.10010.com/ci-mps-st-web/",
                    "login_hint": {"credential_type": "st_ticket", "credential": ticket, "st_type": st_type, "force_logout": True, "source": "app_sjyyt"},
                    "device_info": {"token_id": token_id_auth, "trace_id": uuid.uuid4().hex}
                }
                auth_res = self._send_request('POST', "https://epay.10010.com/woauth2/v2/authorize", json=auth_payload, headers={"Origin": "https://epay.10010.com", "Referer": loc})
                if auth_res and auth_res.json().get('status') == 200:
                    auth_success = True
                    break
            except: pass
            #time.sleep(0.2)
        if not auth_success: return total, expire_soon, tag

        # 4. 检查鉴权状态 (局部重试)
        session_id = ""
        token_id = ""
        user_id = "" 
        rptid = ""
        for _ in range(1):
            try:
                check_url = "https://epay.10010.com/ps-pafs-auth-front/v1/auth/check"
                check_res = self._send_request('POST', check_url, headers={"bizchannelinfo": get_biz_str(rptid)})
                if check_res:
                    check_data = check_res.json()
                    
                    # 处理登录跳转
                    if check_data.get('code') == "2101000100": 
                        login_url = check_data.get('data', {}).get('woauth_login_url')
                        if login_url:
                            full_jump_url = f"{login_url}https://epay.10010.com/ci-mcss-party-web/clockIn/?bizFrom=225&bizChannelCode=225"
                            jump_res = self._send_request('GET', full_jump_url, allow_redirects=False)
                            if jump_res and 'location' in jump_res.headers:
                                rptid = urllib.parse.parse_qs(urllib.parse.urlparse(jump_res.headers['location']).query).get('rptid', [''])[0]
                                if rptid:
                                    check_res = self._send_request('POST', check_url, headers={"bizchannelinfo": get_biz_str(rptid)})
                                    check_data = check_res.json()

                    if check_data.get('code') == '0000':
                        auth_info_data = check_data.get('data', {}).get('authInfo', {})
                        session_id = auth_info_data.get('sessionId')
                        token_id = auth_info_data.get('tokenId')
                        user_id = auth_info_data.get('userId')
                        if session_id and token_id and user_id:
                            break
            except: pass
            #time.sleep(0.2)
        if not session_id or not token_id or not user_id: return total, expire_soon, tag

        # 5. 查询资产 (局部重试)
        for _ in range(1):
            try:
                auth_str = json.dumps({"mobile": "", "sessionId": session_id, "tokenId": token_id, "userId": user_id}, separators=(',', ':'))
                query_url = "https://epay.10010.com/ci-mcss-party-front/v1/ttlxj/queryAvailable"
                avail_res = self._send_request('POST', query_url, headers={"bizchannelinfo": get_biz_str(rptid), "authinfo": auth_str})
                
                if avail_res:
                    rj = avail_res.json()
                    if rj.get('code') == '0000' and str(rj.get('data', {}).get('returnCode')) == "0":
                        data = rj.get('data', {})
                        amt = float(data.get('availableAmount', 0))
                        total = f"{(amt/100):.2f}"
                        
                        prize_list = data.get('prizeList',[])
                        expiring_sum = 0
                        now_date = datetime.now().date()
                        
                        for prize in prize_list:
                            if prize.get('status') == 'A': 
                                raw_time = str(prize.get('endTime', ''))
                                clean_time = re.sub(r'\D', '', raw_time)[:8]
                                
                                if len(clean_time) == 8:
                                    try:
                                        end_date = datetime.strptime(clean_time, "%Y%m%d").date()
                                        delta = (end_date - now_date).days
                                        
                                        if delta <= 3:
                                            amount_val = float(prize.get('amount', 0))
                                            expiring_sum += amount_val
                                    except Exception: 
                                        pass
                        
                        if expiring_sum > 0:
                            expire_soon = f"{(expiring_sum):.2f}"
                            tag = '3d'
                        
                        return total, expire_soon, tag
            except: pass
            #time.sleep(0.2)
            
        return total, expire_soon, tag
        

    def _get_market_watering(self):
        """查询权益超市浇花进度 (已重构：细粒度局部重试)"""
        if not self.ecs_token: return "0/0"
        
        # 1. 获取 Ticket (局部重试，2次即可，底层有3次兜底 = 最多6次请求)
        ticket = ""
        for _ in range(1):
            try:
                t_url = "https://m.client.10010.com/mobileService/openPlatform/openPlatLineNew.htm?to_url=https://contact.bol.wo.cn/market"
                t_res = self._send_request('GET', t_url, headers={"Cookie": self.ecs_token}, allow_redirects=False)
                if t_res and 'location' in t_res.headers:
                    ticket = urllib.parse.parse_qs(urllib.parse.urlparse(t_res.headers['location']).query).get('ticket', [''])[0]
                    if ticket: break
            except: pass
            #time.sleep(0.2)
        if not ticket: return "0/0"
        
        # 2. 换取 Token (局部重试)
        u_token = ""
        for _ in range(1):
            try:
                u_url = f"https://backward.bol.wo.cn/prod-api/auth/marketUnicomLogin?ticket={ticket}"
                u_res = self._send_request('POST', u_url)
                if u_res and u_res.json().get('code') == 200:
                    u_token = u_res.json().get('data', {}).get('token')
                    if u_token: break
            except: pass
            #time.sleep(0.2)
        if not u_token: return "0/0"

        # 3. 查询浇花进度 (局部重试)
        for _ in range(1):
            try:
                s_url = "https://backward.bol.wo.cn/prod-api/promotion/activityTask/getMultiCycleProcess?activityId=13"
                s_res = self._send_request('GET', s_url, headers={"Authorization": f"Bearer {u_token}"})
                if s_res and s_res.json().get('code') == 200:
                    data = s_res.json().get('data', {})
                    return f"{data.get('triggeredTime', 0)}/{data.get('triggerTime', 0)}"
            except: pass
            #time.sleep(0.2)
            
        return "0/0"

    def _get_points_info(self):
        """查询通用总积分与本月到期积分"""
        # 1. 优先使用旧接口（主接口）获取总积分与本月到期积分，增加3次重试保障机制
        for _ in range(1):
            try:
                url = "https://m.client.10010.com/welfare-mall-front/mobile/show/bj2205/v2/1"
                headers = {
                    "Cookie": self.ecs_token,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://img.client.10010.com",
                    "Referer": "https://img.client.10010.com/"
                }
                data = "position=123&isTermShow=1"
                res = self._send_request('POST', url, headers=headers, data=data)
                if res:
                    rj = res.json()
                    if rj.get('code') == '0':
                        items = rj.get('resdata', {}).get('data',[])
                        total_score = "0"
                        exp_score = "0"
                        for item in items:
                            # type 1 对应 通用总积分
                            if str(item.get('type')) == '1':
                                total_score = str(item.get('number', '0'))
                            # type 5 对应 本月到期积分
                            elif str(item.get('type')) == '5':
                                exp_score = str(item.get('number', '0'))
                        # 成功获取数据后直接返回，不再执行备用接口
                        return total_score, exp_score
            except:
                pass
            # 失败短暂等待后重试
            #time.sleep(0.2)

        # 2. 如果主接口连续失败，则启用备用接口查询通用总积分
        for _ in range(1):
            try:
                url_fallback = "https://activity.10010.com/sixPalaceGridTurntableLottery/signin/getIntegral"
                headers_fallback = {
                    "Cookie": self.ecs_token,
                    "Accept": "application/json, text/plain, */*",
                    "Origin": "https://img.client.10010.com",
                    "Referer": "https://img.client.10010.com/"
                }
                res_fallback = self._send_request('GET', url_fallback, headers=headers_fallback)
                if res_fallback:
                    rj_fallback = res_fallback.json()
                    if rj_fallback.get('code') == '0000':
                        total_score_fallback = str(rj_fallback.get('data', {}).get('integralTotal', '0'))
                        # 备用接口无法获取到期积分，故返回 "0" 以兼容原代码
                        return total_score_fallback, "0"
            except:
                pass
            # 失败短暂等待后重试
            #time.sleep(0.2)
        
        # 3. 如果所有接口都失败，返回默认值
        return "0", "0"

    def _get_today_score_from_summary(self):
        """新增：从积分明细查询今日获取积分 (已优化：降低重试放大效应)"""
        for _ in range(1):
            try:
                now = datetime.now()
                year_month = now.strftime('%Y%m')
                today_str = now.strftime('%Y-%m-%d')
                
                url = "https://m.client.10010.com/welfare-mall-front/new/integral/querySummaryList/v1"
                headers = {
                    "Cookie": self.ecs_token,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://img.client.10010.com",
                    "Referer": "https://img.client.10010.com/"
                }
                data = f"scoreType=2&typeChar=0&yearMonth={year_month}&from=97000001317%2C003"
                
                res = self._send_request('POST', url, headers=headers, data=data)
                if res:
                    rj = res.json()
                    if rj.get('code') == '0000':
                        items = rj.get('resdata',[])
                        today_sum = 0
                        if items:
                            for item in items:
                                create_time = str(item.get('createTime', ''))
                                score_val = str(item.get('scoreValue', '0'))
                                if create_time.startswith(today_str):
                                    try:
                                        score = int(float(score_val.replace('+', '')))
                                        if score > 0:
                                            today_sum += score
                                    except: pass
                        return str(today_sum)
            except: pass
            #time.sleep(0.2)
        return "0"

    def _get_unused_coupons(self):
        """新增：查询待领卡券 (已优化：降低重试放大效应)"""
        for _ in range(1):
            try:
                url = "https://m.client.10010.com/myPrizeForActivity/openServices/listWinningRecordsForDouble11"
                headers = {
                    "Cookie": self.ecs_token,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://img.client.10010.com",
                    "Referer": "https://img.client.10010.com/"
                }
                data = "sysActiveStr=SHAKECLIENT_AC20220811152323%2CSHAKECLIENT_AC20231127165002%2CSIGNIN_AC20141230175502%2CSHAKECLIENT_AC20230322151845%2CSHAKECLIENT_AC20240806140724%2CSHAKECLIENT_AC20241119161231%2CSHAKECLIENT_AC20250226023238&enMobile=&otherFlag=1"
                
                res = self._send_request('POST', url, headers=headers, data=data)
                if res:
                    rj = res.json()
                    if rj.get('code') == '200':
                        records = rj.get('data', {}).get('winningRecords',[])
                        valid_coupons =[]
                        for item in records:
                            if item.get('prizeState') == '00':
                                name = item.get('prizeName', '未知卡券')
                                deadline = str(item.get('deadLineTime', ''))[:10]
                                valid_coupons.append(f"{name},至{deadline}失效")
                        return valid_coupons
            except: pass
            #time.sleep(0.2)
        return

    def _get_lianchao_records(self):
        """新增：查询联超记录 (返回格式化的字符串或空字符串)"""
        if not self.ecs_token: return ""
        
        # 1. 获取 Ticket (局部重试)
        ticket = ""
        for _ in range(1):
            try:
                t_url = "https://m.client.10010.com/mobileService/openPlatform/openPlatLineNew.htm?to_url=https://contact.bol.wo.cn/"
                t_res = self._send_request('GET', t_url, headers={"Cookie": self.ecs_token}, allow_redirects=False)
                if t_res and 'location' in t_res.headers:
                    ticket = urllib.parse.parse_qs(urllib.parse.urlparse(t_res.headers['location']).query).get('ticket', [''])[0]
                    if ticket: break
            except: pass
        if not ticket: return ""
        
        # 2. 换取 Token (局部重试)
        market_token = ""
        for _ in range(1):
            try:
                login_y_param = ''.join(random.choices(string.ascii_letters + string.digits + "._-", k=800))
                u_url = f"https://backward.bol.wo.cn/prod-api/auth/marketUnicomLogin?yGdtco4r={login_y_param}"
                headers = {"Content-Type": "application/x-www-form-urlencoded", "Referer": "https://contact.bol.wo.cn/"}
                u_res = self._send_request('POST', u_url, headers=headers, data={"ticket": ticket})
                if u_res:
                    rj = u_res.json()
                    if rj.get('code') == 200:
                        market_token = rj.get('data', {}).get('token')
                        if market_token: break
            except: pass
        if not market_token: return ""

        # 3. 查询记录
        for _ in range(1):
            try:
                prize_y = "0w7_01AEqWtGwhhIWWIF.rWkMvnBB9Mh9xz3FEIloLlnYoZJbLc0eDwQZnsxojfIE27JZ.59713kGB6h5GOPecA2a4wyzfycIr9ENlR2t255omrrxyPAEEhsZqziXJ95Ysc6jE8a2_rJYdsdALymdBZvd9jLeNpw8M9DHnoScRN_bd.tlRZAyGT.NjmA2zeWt_rT9EWM0mVTaTEfvFVkg8baol5OBBmnTmLzs1R57IjOSB3AouoNc6CSBDlED3PQt09epkhhK4FjuVZ1Sfq._6eMMHKHrRAtpPPcCrwE6thPEFFPEANzTnVAjJLFZ3AIkNFrywUSOmoR1k0yxLC_sEHfbRdqGCX26nNJYXKn3dFuzRZAK.4sQrOV"
                q_url = f"https://backward.bol.wo.cn/prod-api/market/contactReceive/queryReceiveRecord?yGdtco4r={prize_y}"
                headers = {
                    "Authorization": f"Bearer {market_token}",
                    "Content-Type": "application/json",
                    "Referer": "https://contact.bol.wo.cn/"
                }
                phone_str = self.phone if self.phone and self.phone != "未知" else ""
                payload = {
                    "limit": 10, 
                    "page": 1, 
                    "mobile": phone_str, 
                    "businessSources":["3", "4", "5", "6", "99"], 
                    "isPromotion": 1, 
                    "returnFormatType": 1
                }
                q_res = self._send_request('POST', q_url, headers=headers, json=payload)
                if q_res:
                    rj = q_res.json()
                    if rj.get('code') == 200:
                        records = rj.get("data", {}).get("recordObjs",[])
                        if records:
                            prize_lines =[]
                            for item in records:
                                status_icon = '✔' if str(item.get('isReceive')) == '1' else '✘'
                                prize_name = item.get('recordName', '未知奖品')
                                prize_time = str(item.get('prizeTime') or item.get('receiveTime') or '未知').split(' ')[0]
                                prize_lines.append(f"{status_icon}{prize_name}, 于{prize_time}中")
                            return "\n🎉 权超记录: \n" + "\n".join(prize_lines)
            except: pass

        return ""

    def query_all_assets(self):
        """聚合查询所有资产 (已新增阅读红包与联超记录开关逻辑)"""
        results = {
            "score": "0", "today_score": "0",
            "tel_red": "0.00", "tel_exp": "0", "tel_month": "",
            "read_red": "0.00", "read_exp": "0",
            "epay": "0.00", "epay_exp": "0.00", "epay_sub": "",
            "watering": "0/0",
            "score_exp": "0",
            "coupons":[],  # 新增卡券字段
            "lianchao": "" # 新增联超记录字段
        }
        
        # 判断是否为联通手机号 (包含常见联通号段及部分虚拟号段)
        is_unicom = False
        if self.phone and re.match(r'^1(3[0-2]|4[56]|5[56]|6[67]|7[0156]|8[56]|9[6])\d{8}$', str(self.phone)):
            is_unicom = True
            
        results["is_unicom"] = is_unicom
        
        # 解包返回值 (利用合并后的原生接口，一次性获取总积分与本月到期积分，彻底去除云盘冗余鉴权)
        results["score"], results["score_exp"] = self._get_points_info()
        
        # 维持其余资产的查询不变，仅联通号段去查询话费红包与待领卡券，减少无用请求
        if is_unicom:
            results["tel_red"], results["tel_exp"], results["tel_month"] = self._get_signin_redpacket()
            results["coupons"] = self._get_unused_coupons()
            
        # 【新增】读取阅读红包开关配置 (默认关闭，关闭时直接跳过网络请求节省时间)
        yuedu_enable = str(middleware.bucketGet('yuhua_zglt', 'yuedu')).lower() in ['true', '1', 'yes']
        if yuedu_enable:
            results["read_red"], results["read_exp"] = self._get_woread_redpacket()
            
        # 【修复】联超记录不限制运营商，移出 is_unicom 的判断范围
        lianchao_enable = str(middleware.bucketGet('yuhua_zglt', 'lianchao')).lower() in ['true', '1', 'yes']
        if lianchao_enable:
            results["lianchao"] = self._get_lianchao_records()
            
        results["epay"], results["epay_exp"], results["epay_sub"] = self._get_epay_balance()
        results["watering"] = self._get_market_watering()
        results["today_score"] = self._get_today_score_from_summary()
            
        return results
            
    def close(self):
        if self.session:
            self.session.close()
            self.session = None

def gen_unique_id(prefix=""):
    timestamp = int(time.time() * 1_000_000)
    return f"{prefix}{timestamp}"

senderID = middleware.getSenderID()
sender = middleware.Sender(senderID)
userid = sender.getUserID()
imtype = sender.getImtype()
uservalue = middleware.bucketGet(bucket='yuhua_zglt_user', key=userid)

def get_config():
    """获取插件配置"""
    manage_cmd = middleware.bucketGet('yuhua_zglt', 'manage_cmd') or '联通管理'
    query_cmd = middleware.bucketGet('yuhua_zglt', 'query_cmd') or '联通查询'
    login_cmd = middleware.bucketGet('yuhua_zglt', 'login_cmd') or '联通登录'
    price = Decimal(middleware.bucketGet('yuhua_zglt', 'price') or '0')
    bf_str = middleware.bucketGet('yuhua_zglt', 'bingfa') or '5'
    yuhua_zglt_qlname = middleware.bucketGet('yuhua_zglt', 'yuhua_zglt_qlname') or ''
    yuhua_zglt_osname = middleware.bucketGet('yuhua_zglt', 'yuhua_zglt_osname') or 'chinaUnicomCookie'
    aiting_var = middleware.bucketGet('yuhua_zglt', 'aiting_var') # 新增
    
    try:
        bf_num = int(bf_str)
    except:
        bf_num = 5
    return (manage_cmd, query_cmd, login_cmd, price, bf_num, yuhua_zglt_qlname, yuhua_zglt_osname, aiting_var)

# 获取配置 (更新解包变量)
manage_cmd, query_cmd, login_cmd, price, bingfa, yuhua_zglt_qlname, yuhua_zglt_osname, aiting_var = get_config()

# 对接青龙
def seekql():
    try:
        if len(yuhua_zglt_qlname) == 0:
            sender.reply("""
=====配置错误=====
❌ 未配置青龙信息
------------------
请在插件配置中填写:
Host丨ClientID丨ClientSecret
• 使用中文丨分隔
• 示例:
http://ql.example.com/丨abcd丨1234
==================""")
            exit(0)
            
        qllist = yuhua_zglt_qlname.split('丨')
        if len(qllist) != 3:
            sender.reply("""
=====格式错误=====
❌ 青龙配置格式错误
------------------
正确格式:
Host丨ClientID丨ClientSecret
==================""")
            exit(0)
            
        QLurl = qllist[0].strip().rstrip('/')
        ClientID = qllist[1].strip()
        ClientSecret = qllist[2].strip()
        
        # 验证每个参数是否为空
        if not all([QLurl, ClientID, ClientSecret]):
            sender.reply("""
=====参数错误=====
❌ 青龙配置参数不完整
------------------
请确保以下参数都已填写:
• 青龙面板地址(Host)
• 应用ID(ClientID)
• 应用密钥(ClientSecret)
==================""")
            exit(0)
            
        # 验证URL格式
        if not QLurl.startswith(('http://', 'https://')):
            sender.reply(f"""
=====地址错误=====
❌ 青龙地址格式错误
------------------
正确格式:
• http://qinglong.example.com/
• https://ql.example.com:5700/
==================""")
            exit(0)
            
        try:
            qltoken = QLtoken(QLurl=QLurl, ClientID=ClientID, ClientSecret=ClientSecret)
            return QLurl, qltoken
        except Exception as e:
            raise Exception(f"获取Token失败: {str(e)}")
            
    except Exception as e:
        sender.reply(f"""
=====连接失败=====
❌ 无法连接青龙面板
------------------
请检查:
1. 青龙面板是否运行
2. 网络是否正常
3. 配置是否正确
------------------
当前配置:
• 地址: {QLurl if 'QLurl' in locals() else '未设置'}
• 应用ID: {ClientID[:4] + '****' if 'ClientID' in locals() else '未设置'}
==================""")
        exit(0)

def delenvs(id):
    if id is None or not QLurl or not qltoken:
        return
    url = f"{QLurl}/open/envs"
    headers = {
        "Authorization": "Bearer" + ' ' + qltoken,
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    data = [id]
    response = requests.delete(url, headers=headers, json=data, proxies={"http": None, "https": None}).json()

def allenvs(osname, account):
    if not QLurl or not qltoken:
        return None
    url = f"{QLurl}/open/envs"
    headers = {
        "Authorization": "Bearer" + ' ' + qltoken,
        "accept": "application/json"
    }
    response = requests.get(url=url, headers=headers, proxies={"http": None, "https": None}).json()
    qlid = None
    if response['code'] == 200:
        envslist = response['data']
        for envs in envslist:
            envname = envs['name']
            remarks = envs['remarks']
            if remarks is None:
                continue
            if osname == envname and str(account) in remarks:
                qlid = envs['id']
                break
        return qlid
    else:
        sender.reply('连接青龙获取变量失败')
        exit(0)

def Addenvs(osname, value, account, phone, owner_id): 
    if not QLurl or not qltoken:
        return
    phone = phone[:3] + '*' * 4 + phone[7:]
    url = f"{QLurl}/open/envs"
    headers = {
        "Authorization": "Bearer" + ' ' + qltoken,
        "accept": "application/json"
    }
    response = requests.get(url=url, headers=headers, proxies={"http": None, "https": None}).json()
    qlid = None
    if response['code'] == 200:
        envslist = response['data']
        for envs in envslist:
            remarks = envs['remarks']
            envname = envs['name']
            if remarks is None:
                continue
            if osname == envname and str(account) in remarks:
                qlid = envs['id']
                break
    else:
        sender.reply('连接青龙获取变量失败')
        exit(0)
        
    if qlid is None:
        QLzt(osname, value, account, phone, owner_id)
    else:
        QLupdate(osname, value, account, qlid, phone, owner_id)

def QLupdate(osname, value, account, qlid, phone, owner_id): 
    qlurl = f"{QLurl}/open/envs"
    # --- 已删除 value = urllib.parse.quote(value) ---
    data = {
        "value": value, # 直接使用原始字符串
        "name": osname,
        "remarks": f'联通:{account}丨用户:{owner_id}丨手机:{phone}丨联通管理',
        "id": qlid
    }
    headers = {
        "Authorization": "Bearer" + ' ' + qltoken,
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.put(qlurl, headers=headers, data=json.dumps(data), proxies={"http": None, "https": None})
    if response.status_code == 200:
        response_json = response.json()
        data = response_json['data']
        if data is None:
            exit(0)
        id = data['id']
        createdAt = data['createdAt']
        return id, createdAt
    else:
        sender.reply('更新变量失败，请联系管理员处理')
        exit(0)

def QLzt(osname, value, account, phone, owner_id):  
    try:
        qlurl = f"{QLurl}/open/envs"
        
        data =[{
            "value": value,
            "name": osname,
            "remarks": f'联通:{account}丨用户:{owner_id}丨手机:{phone}丨联通管理'
        }]
        
        headers = {
            "Authorization": f"Bearer {qltoken}",
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        
        response = requests.post(qlurl, headers=headers, json=data, proxies={"http": None, "https": None})
        
        if response.status_code != 200:
            sender.reply(f"""
=====添加变量失败=====
❌ 请求失败
状态码: {response.status_code}
==================""")
            exit(0)
            
        result = response.json()
        if result.get('code') != 200:
            sender.reply(f"""
=====添加变量失败=====
❌ 青龙返回错误
错误信息: {result.get('message')}
==================""")
            exit(0)
            
        if "value must be unique" in response.text:
            # 变量已存在,不需要处理
            return
            
        data = result.get('data')
        if not data or not isinstance(data, list) or len(data) == 0:
            sender.reply("""
=====添加变量失败=====
❌ 青龙返回数据异常
==================""")
            exit(0)
            
        return data[0].get('id')
        
    except Exception as e:
        sender.reply(f"""
=====系统错误=====
❌ 添加青龙变量失败
------------------
错误信息: {str(e)}
==================""")
        exit(0)

def QLtoken(QLurl, ClientID, ClientSecret):  # 获取青龙token
    try:
        url = f'{QLurl}/open/auth/token?client_id={ClientID}&client_secret={ClientSecret}'
        response = requests.get(url, proxies={"http": None, "https": None})
        
        if response.status_code != 200:
            sender.reply(f"""
=====请求失败=====
❌ 青龙API请求失败
------------------
状态码: {response.status_code}
请检查:
• API地址是否正确
• 面板是否正常运行
==================""")
            exit(0)
            
        result = response.json()
        if "token" in result.get('data', {}):
            return result['data']['token']
        else:
            sender.reply("""
=====认证失败=====
❌ 获取Token失败
------------------
请检查:
• ClientID是否正确
• ClientSecret是否正确
• 应用是否有权限
==================""")
            exit(0)
            
    except requests.exceptions.RequestException as e:
        sender.reply(f"""
=====网络错误=====
❌ 连接青龙面板失败
------------------
请检查:
• 青龙地址是否正确
• 网络是否正常
==================""")
        exit(0)
    except Exception as e:
        sender.reply(f"""
=====系统错误=====
❌ 处理请求时出错
------------------
请检查:
• 配置格式是否正确
• 错误信息: {str(e)}
==================""")
        exit(0)

# 初始化青龙连接
QLurl, qltoken = seekql()
today_time = str(datetime.now().date())

###################
#   逻辑函数区块   #
###################

def login():
    """账号登录"""
    login_guide = """
=====登录方式=====
[1] Token登录
[2] 中国联通账密 (维护)
[3] 中国联通短信 (推荐)
------------------
回复数字选择方式
回复"q"退出"""

    sender.reply(login_guide)
    choice = sender.input(60000, 0, False)

    if not choice:  # 如果超时未输入
        sender.reply("❌ 输入超时")
        return
    elif choice.lower() == 'q':  # 输入q时退出
        sender.reply("✅ 已退出操作")
        return
        
    try:
        if choice == '2':
            account_password_login()
        elif choice == '3':
            verification_code_login()
        elif choice == '1':
            token_online_login()
        else:
            sender.reply("❌ 无效的选择")
            return
            
    except Exception as e:
        sender.reply(f"❌ 登录失败: {str(e)}")
        return
        
        
def _query_single_account(unique_id):
    """【内部函数】用于并发查询单个账号的积分信息。"""
    time.sleep(random.uniform(0.2, 0.5))
    phone = middleware.bucketGet('yuhua_zglt_phone', unique_id) or "未知"
    phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
    auth_time = middleware.bucketGet('yuhua_zglt_auth', unique_id)
    now_date = datetime.now().date()
    if not auth_time: return f"【{phone_mask}】未授权"
    auth_date = datetime.strptime(auth_time, "%Y-%m-%d").date()
    if auth_date < now_date: return f"【{phone_mask}】授权已过期"  

    ecs_token = middleware.bucketGet('yuhua_zglt_ecs_token', unique_id)
    token_online = middleware.bucketGet('yuhua_zglt_token_online', unique_id)

    # 不再传入无用的 access_token
    ltp = LTP(phone=phone, ecs_token=ecs_token, token_online=token_online)
    
    try:
        # 使用全新的探活方法替代 get_ticket
        ok, msg = ltp.check_validity()
        if not ok:
            is_relogin = _try_auto_relogin(unique_id)
            if is_relogin:
                ltp.close()
                ecs_token = middleware.bucketGet('yuhua_zglt_ecs_token', unique_id)
                token_online = middleware.bucketGet('yuhua_zglt_token_online', unique_id)
                ltp = LTP(phone=phone, ecs_token=ecs_token, token_online=token_online)
                ok, msg = ltp.check_validity()
            if not ok:
                # 【核心修复2】精准匹配真实验证失败，绝不错怪IP网络问题
                if "CK已失效" in msg or "缺少基础" in msg: 
                    return f"【{phone_mask}】登录凭证已失效，请重新登录"
                # 如果是网络代理问题，直接把真实原因(msg)告诉用户
                return f"【{phone_mask}】查询失败: {msg}"
        
        assets = ltp.query_all_assets()
        
        # --- 格式化显示逻辑 (上标字符) ---
        
        # [核心安全函数]：无论传入什么乱七八糟的数据，只返回 float 或 0.0
        def safe_float(value):
            try:
                if value is None: return 0.0
                return float(value)
            except (ValueError, TypeError):
                return 0.0

        # [金额美化]：基于 safe_float，强制保留两位小数 (处理 --, null 等)
        def format_money(value):
            return f"{safe_float(value):.2f}"

        # 上标映射表
        sup_map = {
            '0':'⁰', '1':'¹', '2':'²', '3':'³', '4':'⁴', '5':'⁵', '6':'⁶', '7':'⁷', '8':'⁸', '9':'⁹',
            'm':'ᵐ', 'd':'ᵈ'
        }
        def to_sup(s):
            return "".join(sup_map.get(c, c) for c in str(s))
        
        # 1. 话费红包 (强制 0.00 格式) -> 动态判断仅联通号显示
        tel_display = ""
        if assets.get("is_unicom", False):
            tel_str = f"{format_money(assets.get('tel_red'))}元"
            
            if safe_float(assets.get('tel_exp')) > 0:
                month_val = str(assets.get('tel_month', '')).lstrip('0')
                current_month = str(now_date.month)
                
                if month_val == current_month:
                    tag_str = 'm'  # 本月过期
                else:
                    tag_str = f"{month_val}m" if month_val else 'm'
                
                # 增加空格
                tel_str += f" | {assets['tel_exp']} {to_sup(tag_str)}"
            
            tel_display = f"\n📦 话费红包: {tel_str}"
            
        # 2. 阅读红包 (【新增】通过后台开关动态控制展示与否)
        read_display = ""
        yuedu_enable = str(middleware.bucketGet('yuhua_zglt', 'yuedu')).lower() in ['true', '1', 'yes']
        if yuedu_enable:
            read_str = f"{format_money(assets.get('read_red'))}元"
            if safe_float(assets.get('read_exp')) > 0:
                read_str += f" | {assets['read_exp']} {to_sup('7d')}"
            read_display = f"\n📝 阅读红包: {read_str}"
            
        # 3. 沃立减金 (强制 0.00 格式)
        epay_str = f"{format_money(assets.get('epay'))}元"
        if safe_float(assets.get('epay_exp')) > 0:
            # 增加空格
            epay_str += f" | {assets['epay_exp']} {to_sup('3d')}"

        # 4. 通用积分 (强制转为整数，避免 '500.0' 或 '--')
        try:
            # 先转 float 处理 '500.0' 这种情况，再转 int 取整
            score_val_int = int(safe_float(assets.get('score')))
            score_str = str(score_val_int)
        except:
            score_str = "0"
        
        score_exp_val = str(assets.get('score_exp', '0'))
        if score_exp_val != "0" and safe_float(score_exp_val) > 0:
            # 增加空格
            score_str += f" | {score_exp_val} {to_sup('m')}"
            
        # 今日积分
        today_score_str = str(assets.get('today_score', '0'))

        # 卡券显示逻辑 -> 动态判断仅联通号显示
        coupons = assets.get('coupons',[])
        coupon_str = ""
        if assets.get("is_unicom", False) and coupons:
            if len(coupons) == 1:
                # 只有一张时，同行显示
                coupon_str = f"\n🎫 待领卡券: {coupons[0]}"
            else:
                # 多张时，换行显示
                coupon_str = f"\n🎫 待领卡券: \n" + "\n".join(coupons)

        # 联超记录显示逻辑 (如果接口异常或为空，它会是空字符串，隐匿显示完美符合要求)
        lianchao_str = assets.get('lianchao', '')

        return f"""
=====账号信息=====
🤪 账号: {phone_mask}
🔥 当前积分: {score_str}
🎨 今日积分: {today_score_str}{tel_display}
💳 沃立减金: {epay_str}{read_display}
⛱️ 浇花进度: {assets.get('watering', '0/0')}
☁️ 授权到期: {auth_date.strftime('%Y-%m-%d')}{coupon_str}{lianchao_str}
=================="""

    finally:
        ltp.close()

def query_account():
    """
    【联通查询】：查询已授权账号的积分信息（并发版）
    """
    # 引入并发处理库
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not uservalue:
        sender.reply(f"""
=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 {login_cmd} 绑定账号
==================""")
        return
    accounts = eval(uservalue)
    if not accounts:
        sender.reply(f"""
=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 {login_cmd} 绑定账号
==================""")
        return
        
    sender.reply(f"正在查询....")

    # 读取并发配置
    bf_num_local = bingfa  

    try:
        with ThreadPoolExecutor(max_workers=bf_num_local) as executor:
            # 提交所有查询任务到线程池
            futures = {executor.submit(_query_single_account, acc_id): acc_id for acc_id in accounts}
    
            # 按照任务完成的顺序，直接逐个发送结果
            for future in as_completed(futures):
                try:
                    result_msg = future.result()
                    if result_msg:
                        # 不再存入列表，而是直接发送
                        sender.reply(result_msg)
                except Exception as e:
                    # 如果线程中出现异常，也直接发送错误信息
                    sender.reply(f"❌ 查询某个账号时出错: {e}")
    finally:
        # 【核心修复】防止多线程查询积累的大量僵尸 Session 导致内存泄露
        cleanup_resources()

def _mask_identifier(identifier: str) -> str:
    """
    将账号/手机号/UID 等中间 4 位替换为 **** 用于展示
    - 已经含 **** 时原样返回
    - 长度 <= 8 时返回原值
    """
    if "****" in identifier or len(identifier) <= 8:
        return identifier
    return identifier[:4] + "****" + identifier[-4:]

def auth_all_accounts_for_user(accounts):
    """为指定用户的所有账号一键授权"""
    prompt = "=====一键授权=====\n"
    if price > 0:
        prompt += f"授权价格: {price}元/月\n"
    prompt += "请输入授权月数\n------------------\n回复数字设置月数\n回复\"q\"退出"
    sender.reply(prompt)

    months_str = sender.input(60000, 0, False)
    if not months_str or months_str.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return

    try:
        months = int(months_str)
        if months <= 0: raise ValueError()
    except ValueError:
        sender.reply("❌ 无效的月数")
        return

    # 对于“一键授权”，目标就是所有账号
    accounts_to_auth = accounts
    
    total_amount = len(accounts_to_auth) * months * price
    if total_amount > 0:
        pay_ok = process_payment(total_amount, months, f"名下所有 {len(accounts_to_auth)} 个账号")
        if not pay_ok:
            return

    success_count = 0
    failed_count = 0
    for acc_id in accounts_to_auth:
        try:
            auth_time = calculate_auth_time(acc_id, months * 30)
            middleware.bucketSet('yuhua_zglt_auth', acc_id, auth_time)
            
            token = middleware.bucketGet('yuhua_zglt_token_online', acc_id)
            phone = middleware.bucketGet('yuhua_zglt_phone', acc_id) or acc_id
            if token:
                sync_appid = middleware.bucketGet('yuhua_zglt_appid', acc_id)
                sync_val = f"{token}#{sync_appid}" if sync_appid else token
                Addenvs(osname=yuhua_zglt_osname, value=sync_val, account=acc_id, phone=phone, owner_id=userid)
                
                # --- 新增：爱听变量提交 ---
                if aiting_var and aiting_var != '0':
                    Addenvs(osname=aiting_var, value=phone, account=acc_id, phone=phone, owner_id=userid)
            
            success_count += 1
        except Exception:
            failed_count += 1
            
    sender.reply(f"""
=====授权完成=====
✅ 成功: {success_count}个账号
❌ 失败: {failed_count}个账号
⏰ 时长: 授权{months}月
==================""")


def manage_account():
    """
    【账号管理函数】展示账号列表并允许用户选择操作
    """
    if not uservalue:
        sender.reply(f"""
=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 {login_cmd} 绑定账号
==================""")
        return
        
    accounts = eval(uservalue)
    if not accounts:
        sender.reply(f"""
=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 {login_cmd} 绑定账号
==================""")
        return

    account_list = "=====账号列表=====\n[0] 授权全部账号\n"
    
    for i, acc_id in enumerate(accounts, 1):
        phone = middleware.bucketGet('yuhua_zglt_phone', acc_id) or "未知"
        phone_mask = _mask_identifier(phone)
        auth_str = middleware.bucketGet('yuhua_zglt_auth', acc_id)
        
        status_line = ""
        if auth_str:
            try:
                auth_date = datetime.strptime(auth_str, "%Y-%m-%d").date()
                if auth_date > datetime.now().date():
                    status_line = f"✅ {auth_date.strftime('%Y-%m-%d')}"
                else:
                    status_line = "❌ 已过期"
            except ValueError:
                status_line = "⚠️ 未授权"
        else:
            status_line = "⚠️ 未授权"
            
        account_list += f"------------------\n[{i}] 账号信息\n🤪 账号: {phone_mask}\n☁ 授权: {status_line}\n"
        
    account_list += "------------------\n回复数字选择\n回复'q'退出\n=================="
    sender.reply(account_list)
    
    choice = sender.input(60000, 0, False)
    if not choice or choice.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
        
    try:
        choice_idx = int(choice)
        if choice_idx == 0:
            auth_all_accounts_for_user(accounts)
        elif 1 <= choice_idx <= len(accounts):
            account = accounts[choice_idx - 1]
            show_account_menu(account)
        else:
            raise ValueError()
    except (ValueError, IndexError):
        sender.reply("❌ 无效的选择")

def show_account_menu(account):
    """显示账号操作菜单"""
    menu = """
=====账号操作=====
[1] 授权账号
[2] 删除账号
[3] 配置AppId
------------------
回复数字选择操作
回复"q"退出"""
    sender.reply(menu)
    choice = sender.input(60000, 0, False)
    if not choice:
        sender.reply("❌ 输入超时")
        return
    if choice.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    if choice == '1':
        auth_account(account)
    elif choice == '2':
        confirm_delete(account)
    elif choice == '3':
        configure_appid_manual(account)
    else:
        sender.reply("❌ 无效的选择")

def configure_appid_manual(account):
    """管理菜单手动配置AppId流程"""
    auth_time = middleware.bucketGet('yuhua_zglt_auth', account)
    if not auth_time or auth_time < today_time:
        sender.reply("❌ 该账号授权无效或已过期")
        return
        
    sender.reply("""=====配置AppId=====
❶ 回复『d』清除数据或按②新增或更新
② 打开该路径中的文件『/storage/emulated/0/Documents/Unicom/appid』复制文本内容并回复
-----------------
请在300秒内完成
回复"q"取消""")
    
    app_input = sender.input(300000, 1, False)
    if not app_input:
        sender.reply("❌ 输入超时")
        return
    if app_input.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    if app_input.lower() == 'd':
        try:
            middleware.bucketDel('yuhua_zglt_appid', account)
        except Exception:
            pass
        sender.reply("✅ 已完成删除")
        # 同步更新青龙
        token_online = middleware.bucketGet('yuhua_zglt_token_online', account)
        phone = middleware.bucketGet('yuhua_zglt_phone', account)
        if token_online: Addenvs(osname=yuhua_zglt_osname, value=token_online, account=account, phone=phone, owner_id=userid)
        return

    new_appid = app_input.strip()
    token_online = middleware.bucketGet('yuhua_zglt_token_online', account)
    
    # 鉴权测试
    if token_online:
        pl = {"token_online": token_online, "appId": new_appid, "reqtime": int(time.time()*1000), **VERIFICATION_DEVICE_PARAMS}
        ua = f"Dalvik/2.1.0 (Linux; U; Android {VERIFICATION_DEVICE_PARAMS.get('deviceOS')}; {VERIFICATION_DEVICE_PARAMS.get('deviceModel')} Build/UKQ1.231108.001);unicom{{version:{VERIFICATION_DEVICE_PARAMS.get('version')}}};ltst;"
        hd = {"User-Agent": ua, "Content-Type": "application/x-www-form-urlencoded", "Host": "m.client.10010.com"}
        
        with requests.Session() as sess:
            resp = send_request_global('POST', "https://m.client.10010.com/mobileService/onLine.htm", data=pl, headers=hd, session=sess)
            
        if resp:
            rj = resp.json()
            if rj.get('code') in ['0', '0000']:
                middleware.bucketSet('yuhua_zglt_appid', account, new_appid)
                sender.reply("✅ 已成功配置")
                # 同步更新青龙
                phone = middleware.bucketGet('yuhua_zglt_phone', account)
                Addenvs(osname=yuhua_zglt_osname, value=f"{token_online}#{new_appid}", account=account, phone=phone, owner_id=userid)
            else:
                # 优先获取 dsc
                fail_reason = rj.get('dsc') or rj.get('desc') or '未知原因'
                sender.reply(f"❌ 鉴权失败: {fail_reason}")
        else:
            sender.reply("❌ 鉴权失败: 网络请求无响应")
    else:
        sender.reply("❌ 未找到Token Online，无法验证AppId，请重新登录")

def confirm_delete(account):
    """确认是否删除账号"""
    phone = middleware.bucketGet('yuhua_zglt_phone', account) or "未知"
    phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
    sender.reply(f"⚠️ 确认要删除账号 {phone_mask} 吗？(y/n)")
    confirm = sender.input(30000, 0, False)
    if not confirm:  # 如果超时未输入
        sender.reply("❌ 输入超时")
        return
    elif confirm.lower() == 'n':
        sender.reply("✅ 已退出操作")
        return
    elif confirm.lower() == 'q':  # 输入q时退出
        sender.reply("✅ 已退出操作")
        return
    elif confirm.lower() != 'y':
        sender.reply("❌ 无效的选择")
        return
    delete_account(account)

def delete_account(account):
    """
    【删除账号】：删除本地记录
    """
    phone = middleware.bucketGet('yuhua_zglt_phone', account) or "未知"
    phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
    accounts = eval(uservalue or '[]')
    if account not in accounts:
        sender.reply("❌ 未找到账号")
        return
        
    # 删除青龙变量
    try:
        qlid = allenvs(osname=yuhua_zglt_osname, account=account)
        if qlid:
            delenvs(id=qlid)
            
        # --- 新增：删除爱听变量 ---
        if aiting_var and aiting_var != '0':
            qlid_aiting = allenvs(osname=aiting_var, account=account)
            if qlid_aiting:
                delenvs(id=qlid_aiting)
    except:
        pass
        
    accounts.remove(account)
    middleware.bucketSet('yuhua_zglt_user', userid, str(accounts))
    try:
        middleware.bucketDel('yuhua_zglt_token', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_zglt_auth', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_zglt_phone', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_zglt_password', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_zglt_ecs_token', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_zglt_token_online', account)
    except Exception:
        pass
    sender.reply(f"✅ 已删除账号 {phone_mask}")

def auth_account(account):
    """【账号授权】：用户侧手动授权/续费"""
    phone = middleware.bucketGet('yuhua_zglt_phone', account) or "未知"
    phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
    if not price:
        sender.reply("""
=====账号授权=====
请输入授权月数
------------------
回复数字设置月数
回复"q"退出""")
    else:
        sender.reply(f"""
=====账号授权=====
授权价格: {price}元/月
请输入授权月数
------------------
回复数字设置月数
回复"q"退出""")
    months_str = sender.input(60000, 0, False)
    if not months_str:
        sender.reply("❌ 输入超时")
        return
    elif months_str.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    try:
        months = int(months_str)
        if months <= 0:
            raise ValueError()
    except:
        sender.reply("❌ 无效的月数")
        return
    amount = months * price
    if amount > 0:
        if not process_payment(amount, months, phone_mask):
            return
    auth_time = calculate_auth_time(account, months * 30)
    middleware.bucketSet('yuhua_zglt_auth', account, auth_time)
    
    # --- 修复：增加 AppId 拼接逻辑 ---
    token = middleware.bucketGet('yuhua_zglt_token_online', account)
    appid = middleware.bucketGet('yuhua_zglt_appid', account)
    if token:
        sync_val = f"{token}#{appid}" if appid else token
        Addenvs(osname=yuhua_zglt_osname, value=sync_val, account=account, phone=phone, owner_id=userid)
        
        # --- 新增：爱听变量提交 ---
        if aiting_var and aiting_var != '0':
            Addenvs(osname=aiting_var, value=phone, account=account, phone=phone, owner_id=userid)
    
    days = 30*months
    sender.reply(f"""
=====授权成功=====
🤪 账号: {phone_mask}
⏰ 时长: {days}天
📅 到期: {auth_time}
=======================""")

def calculate_auth_time(account, days):
    """计算授权到期时间，days 为授权天数 (支持负数)"""
    current_date = datetime.now().date()
    auth_str = middleware.bucketGet('yuhua_zglt_auth', account)
    
    start_date = current_date
    if auth_str:
        try:
            auth_date = datetime.strptime(auth_str, "%Y-%m-%d").date()
            if auth_date > current_date:
                start_date = auth_date
        except ValueError:
            pass # 如果日期格式错误，则从今天开始计算

    end_date = start_date + timedelta(days=days)

    # 如果是扣除天数，且结果早于今天，则让授权直接过期
    if days < 0 and end_date < current_date:
        # 设置为昨天，确保授权状态为“已过期”
        return str(current_date - timedelta(days=1))
        
    return str(end_date)

def process_payment(amount, months, phone_mask):
    """处理支付"""
    zsm = middleware.bucketGet('yuhua_zglt', 'zsm')
    if not zsm:
        sender.reply("❌ 未配置收款码")
        return False
        
    pay_msg = f"""
=====扫码支付====
📅 时长: {months}月
💰 金额: {amount}元
------------------
请在120秒内完成支付
回复"q"取消"""
    sender.reply(pay_msg)
    sender.replyImage(zsm)
    
    ddzf = sender.waitPay("q", 120 * 1000)
    if str(ddzf) == 'q':
        sender.reply("✅ 已退出操作")
        return False
        
    try:
        if isinstance(ddzf, str):
            ddzf = json.loads(ddzf)
        if 'Money' in ddzf:
            Money = float(ddzf.get('Money', 0))
            Time = ddzf.get('Time', '')
            From = ''
        else:
            Money = float(ddzf.get('money', 0))
            Time = ddzf.get('Time', '')
            From = ddzf.get('FromName', '')
        if float(Money) >= float(amount):
            return True
        else:
            sender.reply(f"""
=====支付失败=====
❌ 支付金额不足
------------------
💰 应付: {amount}元
💵 实付: {Money}元
==================""")
            return False
    except Exception as e:
        sender.reply(f"""
=====支付异常=====
❌ 支付验证失败
------------------
⚠️ 错误: {str(e)}
==================""")
        return False

def clean_expired():
    """清理过期账号"""
    if not sender.isAdmin():
        sender.reply("❌ 需要管理员权限")
        return
    users = middleware.bucketAllKeys('yuhua_zglt_user')
    cleaned = 0
    for user in users:
        accounts = eval(middleware.bucketGet('yuhua_zglt_user', user) or '[]')
        valid = []
        for acc_id in accounts:
            auth = middleware.bucketGet('yuhua_zglt_auth', acc_id)
            if (not auth) or (auth <= str(datetime.now().date())):
                # 删除青龙变量
                try:
                    qlid = allenvs(osname=yuhua_zglt_osname, account=acc_id)
                    if qlid:
                        delenvs(id=qlid)
                    
                    # --- 新增：删除爱听变量 ---
                    if aiting_var and aiting_var != '0':
                        qlid_aiting = allenvs(osname=aiting_var, account=acc_id)
                        if qlid_aiting:
                            delenvs(id=qlid_aiting)
                except:
                    pass
                
                try:
                    middleware.bucketDel('yuhua_zglt_token', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_zglt_auth', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_zglt_phone', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_zglt_password', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_zglt_ecs_token', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_zglt_token_online', acc_id)
                except Exception:
                    pass
                cleaned += 1
            else:
                valid.append(acc_id)
        if valid:
            middleware.bucketSet('yuhua_zglt_user', user, str(valid))
        else:
            try:
                middleware.bucketDel('yuhua_zglt_user', user)
            except Exception:
                pass
    sender.reply(f"✅ 已清理 {cleaned} 个授权已过期账号")

def admin_auth():
    """管理员授权功能"""
    if not sender.isAdmin():
        sender.reply("❌ 需要管理员权限")
        return
    
    auth_menu = """
=====授权管理=====
[1] 一键授权所有用户
[2] 指定用户授权
------------------
回复数字选择功能
回复"q"退出"""
    sender.reply(auth_menu)
    choice = sender.input(60000, 0, False)
    if not choice:  # 如果超时未输入
        sender.reply("❌ 输入超时")
        return
    elif choice.lower() == 'q':  # 输入q时退出
        sender.reply("✅ 已退出操作")
        return
    elif choice == '1':
        auth_all_users()
        return
    elif choice == '2':
        auth_specific_user()
        return
    else:
        sender.reply("❌ 无效的选择")
        return

def auth_all_users():
    """一键授权所有用户（批量授权）"""
    sender.reply("""
=====批量授权=====
请输入授权天数
------------------
回复数字设置天数
回复"q"退出""")
    try:
        days_str = sender.input(60000, 0, False)
        if not days_str:
            sender.reply("❌ 输入超时")
            return
        elif days_str.lower() == 'q':
            sender.reply("✅ 已退出操作")
            return
        days = int(days_str)
        users = middleware.bucketAllKeys('yuhua_zglt_user')
        success = 0
        failed = 0
        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_zglt_user', user) or '[]')
            for acc_id in accounts:
                try:
                    auth_time = calculate_auth_time(acc_id, days)
                    middleware.bucketSet('yuhua_zglt_auth', acc_id, auth_time)
                    
                    # --- 修复：增加 AppId 拼接逻辑 ---
                    token = middleware.bucketGet('yuhua_zglt_token_online', acc_id)
                    appid = middleware.bucketGet('yuhua_zglt_appid', acc_id)
                    phone = middleware.bucketGet('yuhua_zglt_phone', acc_id) or acc_id
                    if token:
                        sync_val = f"{token}#{appid}" if appid else token
                        Addenvs(osname=yuhua_zglt_osname, value=sync_val, account=acc_id, phone=phone, owner_id=user)
                        
                        # --- 新增：爱听变量提交 ---
                        if aiting_var and aiting_var != '0':
                            Addenvs(osname=aiting_var, value=phone, account=acc_id, phone=phone, owner_id=user)
                    
                    success += 1
                    log_operation('batch_auth', user, acc_id, 'success')
                except Exception as e:
                    failed += 1
                    log_operation('batch_auth', user, acc_id, 'failed', str(e))
        
        action_text = "授权" if days > 0 else "扣除"
        day_abs = abs(days)
        sender.reply(f"""
=====操作完成=====
✅ 成功: {success}个账号
❌ 失败: {failed}个账号
⏰ 时长: {action_text}{day_abs}天
==================""")
    except ValueError:
        sender.reply("❌ 无效的天数")
    except Exception as e:
        sender.reply(f"❌ 授权失败: {str(e)}")

def auth_specific_user():
    """指定用户授权"""
    sender.reply("""
=====指定授权=====
请输入用户ID
(发送myuid可获取ID)
------------------
回复"q"退出""")
    user_id = sender.input(60000, 0, False)
    if not user_id:
        sender.reply("❌ 输入超时")
        return
    if user_id.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return

    accounts = eval(middleware.bucketGet('yuhua_zglt_user', user_id) or '[]')
    if not accounts:
        sender.reply("❌ 该用户没有绑定账号")
        return

    account_list_msg = "=====账号列表=====\n[0] 授权全部账号\n"
    for i, acc_id in enumerate(accounts, 1):
        phone = middleware.bucketGet('yuhua_zglt_phone', acc_id) or "未知"
        phone_mask = _mask_identifier(phone)
        auth_str = middleware.bucketGet('yuhua_zglt_auth', acc_id)
        
        status_line = ""
        if auth_str:
            try:
                auth_date = datetime.strptime(auth_str, "%Y-%m-%d").date()
                if auth_date > datetime.now().date():
                    status_line = f"✅ {auth_date.strftime('%Y-%m-%d')}"
                else:
                    status_line = "❌ 已过期"
            except ValueError:
                status_line = "⚠️ 未授权"
        else:
            status_line = "⚠️ 未授权"
            
        account_list_msg += f"------------------\n[{i}] 账号信息\n🤪 账号: {phone_mask}\n☁ 授权: {status_line}\n"
        
    account_list_msg += "------------------\n回复数字选择\n回复'q'退出\n=================="
    sender.reply(account_list_msg)

    choice_str = sender.input(60000, 0, False)
    if not choice_str:
        sender.reply("❌ 输入超时")
        return
    if choice_str.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return

    try:
        choice_idx = int(choice_str)
        if not 0 <= choice_idx <= len(accounts):
            raise ValueError("无效的选择")
    except ValueError:
        sender.reply("❌ 无效的选择")
        return

    target_accounts = []
    if choice_idx == 0:
        target_accounts = accounts
    else:
        target_accounts.append(accounts[choice_idx - 1])

    sender.reply("""
=====指定授权=====
请输入授权天数
------------------
回复数字设置天数
回复"q"退出""")
    days_str = sender.input(60000, 0, False)
    if not days_str:
        sender.reply("❌ 输入超时")
        return
    if days_str.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return

    try:
        days = int(days_str)
        latest_accounts = eval(middleware.bucketGet('yuhua_zglt_user', user_id) or '[]')
        if not latest_accounts:
            sender.reply("❌ 操作失败：该用户已无任何账号")
            return

        success = 0
        failed = 0
        for acc_id in target_accounts:
            if acc_id not in latest_accounts:
                failed += 1
                continue

            try:
                auth_time = calculate_auth_time(acc_id, days)
                middleware.bucketSet('yuhua_zglt_auth', acc_id, auth_time)
                
                # --- 修复：增加 AppId 拼接逻辑 ---
                token = middleware.bucketGet('yuhua_zglt_token_online', acc_id)
                appid = middleware.bucketGet('yuhua_zglt_appid', acc_id)
                phone = middleware.bucketGet('yuhua_zglt_phone', acc_id) or acc_id
                if token:
                    sync_val = f"{token}#{appid}" if appid else token
                    Addenvs(osname=yuhua_zglt_osname, value=sync_val, account=acc_id, phone=phone, owner_id=user_id)
                    
                    # --- 新增：爱听变量提交 ---
                    if aiting_var and aiting_var != '0':
                         Addenvs(osname=aiting_var, value=phone, account=acc_id, phone=phone, owner_id=user_id)

                success += 1
                log_operation('specific_auth', user_id, acc_id, 'success')
            except Exception as e:
                failed += 1
                log_operation('specific_auth', user_id, acc_id, 'failed', str(e))
        
        action_text = "授权" if days > 0 else "扣除"
        day_abs = abs(days)
        reply_msg = f"""
=====操作完成=====
👤 用户: {user_id}
✅ 成功: {success}个账号
❌ 失败: {failed}个账号
⏰ 时长: {action_text}{day_abs}天"""
        
        if failed > 0:
            reply_msg += "\n⚠️ 部分账号授权失败，原因可能是它们在操作期间被后台任务自动清理"
        
        reply_msg += "\n=================="
        sender.reply(reply_msg)

    except ValueError:
        sender.reply("❌ 无效的天数")
    except Exception as e:
        sender.reply(f"❌ 授权时发生未知错误: {str(e)}")


def log_operation(operation, user, account, status, message=''):
    """记录操作日志(仅存储到bucket，不再自动推送给用户)"""
    try:
        log = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'user': user,
            'account': account,
            'status': status,
            'message': message
        }
        log_key = f"{operation}_{user}_{account}_{int(time.time())}"
        middleware.bucketSet('yuhua_zglt_logs', log_key, json.dumps(log))
    except Exception:
        pass

def cron_task():
    """定时任务处理"""
    if imtype != 'fake':
        pass
    today_str = str(datetime.now().date())
    try:
        users = middleware.bucketAllKeys('yuhua_zglt_user')
        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_zglt_user', user) or '[]')
            for acc_id in accounts:
                time.sleep(random.uniform(0.5, 1.0))
                try:
                    # 核心优化：不再获取无用的云盘 token，直接获取 ecs_token
                    ecs_token = middleware.bucketGet('yuhua_zglt_ecs_token', acc_id)
                    phone = middleware.bucketGet('yuhua_zglt_phone', acc_id) or "未知"
                    if not ecs_token:
                        notify_user(user, acc_id, "未找到登录凭证")
                        continue
                    
                    # 核心优化：使用轻量级的商城接口探活
                    ltp = LTP(ecs_token=ecs_token, phone=phone)
                    ok, msg = ltp.check_validity()
                    ltp.close()
                    
                    if not ok:
                        # 尝试续期失败后，进行精准判断
                        if not _try_auto_relogin(acc_id):
                            # 【核心修复3】：只有真实CK失效才推送，代理IP问题则静默处理，避免骚扰用户
                            if "CK已失效" in msg:
                                notify_user(user, acc_id, "登录凭证已过期且自动刷新失败，请重新登录")
                            else:
                                # 如果是代理IP/网络问题，仅在后台打印日志，不打扰用户
                                print(f"定时检测账号 {acc_id} 失败(不推送): {msg}")
                        continue
                        
                    auth_time = middleware.bucketGet('yuhua_zglt_auth', acc_id)
                    if not auth_time or auth_time <= today_str:
                        notify_user(user, acc_id, "授权已过期，请及时续费")
                except Exception as e:
                    print(f"处理账号 {acc_id} 出错: {str(e)}")
                    continue

    except Exception as e:
            print(f"定时任务出错: {str(e)}")
    finally:
            # 【核心修复】定时任务结束后强制回收全局 Session 和黑名单，防止长期挂机导致的内存与文件描述符泄漏
        cleanup_resources()

notified_accounts = set()
def notify_user(user, account, message):
    """发送用户通知"""
    try:
        if account in notified_accounts:
            return
        phone = middleware.bucketGet('yuhua_zglt_phone', account) or "未知"
        phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
        notify_msg = f"""
=====联通通知=====
🤪 账号: {phone_mask}
📢 消息: {message}
=================="""
        middleware.push('qq', '', user, '', notify_msg)
        middleware.push('qb', '', user, '', notify_msg)
        middleware.push('wx', '', user, '', notify_msg)
        middleware.push('gw', '', user, '', notify_msg)
        middleware.push('sb', '', user, '', notify_msg)
        middleware.push('wb', '', user, '', notify_msg)
        middleware.push('tg', '', user, '', notify_msg)
        middleware.push('tb', '', user, '', notify_msg)
        middleware.push('qx', '', user, '', notify_msg)
        middleware.push('xy', '', user, '', notify_msg)
        middleware.push('ip', '', user, '', notify_msg)
        notified_accounts.add(account)
    except Exception as e:
        print(f"发送通知失败: {str(e)}")


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
            # 直接使用 requests.get 替代 session.get，并强制要求不走代理
            response = requests.get(
                url,
                headers=headers,
                timeout=(5, 10),
                verify=True,
                allow_redirects=True,
                proxies={"http": None, "https": None}
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
        except Exception:
            if attempt < 2:
                time.sleep(2)
                continue
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
    """主函数"""
    try:
        if not check_maintenance_page():
            sender.reply("❌ 服务端无法连通, 插件停止运行")
            return
        message = sender.getMessage().strip()
        if '登录' in message:
            login()
        elif '管理' in message:
            manage_account()
        elif '查询' in message:
            query_account()
        elif message == '联通清理':
            clean_expired()
        elif message == '联通授权':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            admin_auth()
        elif message == '联通检测':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            sender.reply("正在检测....")
            cron_task()
            sender.reply("✅ 已执行联通检测推送任务")
        else:
            sender.setContinue()
    except Exception as e:
        sender.reply(f"❌ 运行出错: {str(e)}")
                
if __name__ == "__main__":
    try:
        manage_cmd, query_cmd, login_cmd, price, bingfa, yuhua_zglt_qlname, yuhua_zglt_osname, aiting_var = get_config()
        today = str(datetime.now().date())
        if imtype == 'fake':
            pass
        else:
            main()
    except Exception as e:
        sender.reply(f"❌ 运行出错: {str(e)}")
