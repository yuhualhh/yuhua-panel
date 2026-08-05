# [title: 朴朴超市]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@9636ea5e5ff455c65827dd7e411c82146dedf07a/2026/01/10/041c4df955cddcaadb56c25a94433010.png]
# [language: python]
# [rule: ^(朴朴)(登录|查询|管理|清理|授权|检测|刷新|一键刷新)$]
# [disable: false]
# [open_source: false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [public: true]
# [admin: true
# [priority: 9999999999999999999]
# [version: 1.1.3]
# [price: 0]
# [author: yuhualhh]
# [service: ]
# [description: ❶朴朴超市资产查询以及对接青龙面板代挂插件，支持微信扫码登录、批量刷新Token、管理、查询、授权、检测授权过期以及Token失效并推送等功能<br>❷部分功能的实现需自行添加计划任务伪装管理员定时，了解如何添加计划任务请看移动云盘插件介绍，关于指令『朴朴检测』与『朴朴清理』定时『30 18 * * *』，关于指令『朴朴一键刷新』定时『0 9,21 * * *』]

# [param: {"required":true,"key":"yuhua_pp.zsm","bool":false,"placeholder":"","name":"收款码子","desc":"微信Bot收款码直链"}]
# [param: {"required":true,"key":"yuhua_pp.Qinglong","bool":false,"placeholder":"Host丨ClientID丨ClientSecret","name":"对接容器","desc":"各参数之间用中文符丨分割，例如: http://127.0.01:5700/丨abcdef-ghijk丨abcdefghijklmnopqrs_tuvw"}]
# [param: {"required":true,"key":"yuhua_pp.files","bool":false,"placeholder":"","name":"文件路径","desc":"定义提交变量至容器中某个文件，不填默认pupuCookie.txt"}]
# [param: {"required":true,"key":"yuhua_pp.price","bool":false,"placeholder":"","name":"收费价格","desc":"不填默认0元，单位: 元/月"}]

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

# 调用示例
# printf("请求成功，正在解析数据...", "INFO")   # 显示绿色

#输出日志
DEBUG = False

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

######################### 全局 Session #########################
def get_global_session():
    """
    在整个插件生命周期内只使用这一个全局 Session，无连接池限制以最大化并发性能。
    如果尚未创建，则创建并返回；若已存在，则直接返回。
    """
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_1_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.46(0x18002e2c) NetType/WIFI Language/zh_CN miniProgram/wx122ef876a7132eb4'
    })
    return session

def send_request_global(method, url, **kwargs):
    session = kwargs.pop('session', None) or get_global_session()
    kwargs.setdefault('timeout', 45)
    if DEBUG:
        print(f"\n===== [send_request_global LOG START] =====")
        print(f"--> METHOD: {method}")
        print(f"--> URL: {url}")
        print(f"--> HEADERS: {kwargs.get('headers')}")
    for attempt in range(3):
        try:
            response = session.request(method, url, **kwargs)
            if DEBUG:
                print(f"<-- STATUS: {response.status_code}")
            response.raise_for_status()
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < 2:
                time.sleep(2 + attempt)
                continue
            else:
                raise e
        except requests.exceptions.RequestException as e:
            if attempt < 2:
                time.sleep(2)
                continue
            else:
                raise e
    return None


def ScanCodeLogin():
    """微信扫码登录逻辑"""
    import time
    import json
    
    try:
        scan_msg = """
=====微信扫码登录=====
⌛ 正在加载二维码...
⏳ 请稍候...
=================="""
        sender.reply(scan_msg)

        api_url = "https://yuhualhh.250666.xyz/api/wxcode.php"
        data_create = {
            "project": "pupu",
            "action": "create_qr"
        }

        response = send_request_global('POST', api_url, json=data_create)
        response_data = response.json()

        if response_data.get('success') and isinstance(response_data.get('data'), dict):
            QRcodeImg = response_data['data'].get('qr_img_url')
            uuid = response_data['data'].get('uuid')
            if not QRcodeImg or not uuid:
                sender.reply('❌ 获取二维码失败')
                return None
        else:
            sender.reply('❌ 获取二维码失败')
            return None

        sender.replyImage(QRcodeImg)

        scan_guide = """
=====登录说明=====
📱 请使用微信扫描二维码登录
------------------
⚠️ 注意事项:
1. 确保该微信已登录朴朴超市小程序
=================="""
        sender.reply(scan_guide)

        retry = 100
        code = None

        while retry > 0:
            time.sleep(2)

            try:
                data_poll = {
                    "project": "pupu",
                    "action": "poll_scan_status",
                    "uuid": uuid
                }

                resp_check = send_request_global('POST', api_url, json=data_poll)
                resp_data = resp_check.json()

                if resp_data.get('success') and isinstance(resp_data.get('data'), dict):
                    code = resp_data['data'].get('code')
                    if code:
                        break
            except Exception as e:
                pass

            retry -= 1

        if not code:
            sender.reply('❌ 扫码超时, 请重新尝试!')
            return None

        url_login = "https://cauth.pupuapi.com/clientauth/user/society/wechat/login"
        params = {'user_society_type': "11"}
        
        payload_dict = {
            "code": code,
            "user_device": {
                "app_version": 400804,
                "device_model": "MEIZU 20",
                "device_os": 10,
                "device_token": "",
                "mac_address": ""
            }
        }
        payload = json.dumps(payload_dict)

        headers_pp = {
            'User-Agent': "Pupumall/4.8.4;Android/13;",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'pp-version': "2023022500",
            'pp-os': "10",
            'pp_store_city_zip': "440100",
            'pp-elder-mode': "false",
            'Content-Type': "application/json; charset=UTF-8"
        }
        
        response = send_request_global('POST', url_login, params=params, data=payload, headers=headers_pp)
        response_data = response.json()
        
        return_code = response_data.get('errcode') if 'errcode' in response_data else response_data.get('code')
        
        if return_code == 0 and 'data' in response_data:
            refresh_token = response_data['data']['refresh_token']
            return refresh_token
        else:
            sender.reply(f"❌ 登录失败: {response_data.get('message', '未知错误')}")
            return None
            
    except Exception as e:
        sender.reply(f"""
=====登录失败=====
❌ 登录出错
------------------
⚠️ 错误信息: 
{str(e)}
==================""")
        return None

def _refresh_token_logic(refresh_token):
    """朴朴Token刷新逻辑"""
    try:
        url = 'https://cauth.pupuapi.com/clientauth/user/refresh_token'
        h = {
            "User-Agent": 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_1_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.46(0x18002e2c) NetType/WIFI Language/zh_CN miniProgram/wx122ef876a7132eb4'
        }
        data = {'refresh_token': refresh_token}

        response = send_request_global('PUT', url, json=data, headers=h).json()
        if response.get('errcode') == 0:
            access_token = response['data']['access_token']
            new_refresh_token = response['data']['refresh_token']
            user_id = response['data']['user_id']
            
            url_info = "https://cauth.pupuapi.com/clientauth/user/info"
            h['Authorization'] = f"Bearer {access_token}"
            r = send_request_global('GET', url_info, headers=h).json()
            
            mobile = r['data']['phone']
            nick_name = r['data']['nick_name']
            return mobile, nick_name, new_refresh_token, access_token, user_id, True
        else:
            return None, None, None, None, None, False
    except Exception as e:
        return None, None, None, None, None, False

def coin(access_token):
    """查询朴分"""
    try:
        url = "https://j1.pupuapi.com/client/coin"
        headers = {
            'User-Agent': "Mozilla/5.0 (Linux; Android 13; MEIZU 20 Build/TKQ1.221114.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/108.0.5359.128 Mobile Safari/537.36 D/d53f198d94ef00ec424d9aac9b0db734",
            'Authorization': f"Bearer {access_token}"
        }
        response = send_request_global('GET', url, headers=headers)
        data_json = response.json()['data']
        balance = data_json['balance']
        # 新增获取过期积分和时间，默认为0
        expiring_coin = data_json.get('expiring_coin', 0)
        expire_time = data_json.get('expire_time', 0)
        
        url_rec = "https://j1.pupuapi.com/client/coin/record?page=1&size=20"
        response_rec = send_request_global('GET', url_rec, headers=headers)
        data = response_rec.json()['data']
        todaycoin = 0
        if len(data) != 0:
            for coinjson in data:
                time_create = coinjson['time_create']
                timestamp = time_create / 1000
                cointime = str(datetime.fromtimestamp(timestamp))
                if str(datetime.now().date()) in cointime:
                    types = coinjson['type']
                    if types == 0:
                        coins = coinjson['value']
                        todaycoin += coins
                else:
                    continue
        return balance, todaycoin, expiring_coin, expire_time
    except Exception:
        return '查询失败', '0', 0, 0

def gen_unique_id(prefix=""):
    timestamp = int(time.time() * 1_000_000)
    return f"{prefix}{timestamp}"

senderID = middleware.getSenderID()
sender = middleware.Sender(senderID)
userid = sender.getUserID()
imtype = sender.getImtype()
uservalue = middleware.bucketGet(bucket='yuhua_pp_user', key=userid)

def get_config():
    """获取插件配置"""
    manage_cmd = '朴朴管理'
    query_cmd = '朴朴查询'
    login_cmd = '朴朴登录'
    price = Decimal(middleware.bucketGet('yuhua_pp', 'price') or '0')
    bf_num = 1
    yuhua_pp_qlname = middleware.bucketGet('yuhua_pp', 'Qinglong')
    filespath = middleware.bucketGet('yuhua_pp', 'files')
    
    if not filespath:
        filespath = "pupuCookie.txt"
    
    return (manage_cmd, query_cmd, login_cmd, price, bf_num, yuhua_pp_qlname, filespath)

# 获取配置
manage_cmd, query_cmd, login_cmd, price, bingfa, yuhua_pp_qlname, filespath = get_config()

# 对接青龙
def seekql():
    try:
        if len(yuhua_pp_qlname) == 0:
            if sender.getImtype() != 'fake':
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
            
        qllist = yuhua_pp_qlname.split('丨')
        if len(qllist) != 3:
            if sender.getImtype() != 'fake':
                sender.reply("""
=====格式错误=====
❌ 青龙配置格式错误
------------------
正确格式:
Host丨ClientID丨ClientSecret
==================""")
            exit(0)
            
        QLurl = qllist[0].strip()
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
    response = send_request_global('DELETE', url, headers=headers, json=data)
    if response:
        response.json()

def allenvs(osname, account):
    if not QLurl or not qltoken:
        return None
    url = f"{QLurl}/open/envs"
    headers = {
        "Authorization": "Bearer" + ' ' + qltoken,
        "accept": "application/json"
    }
    response = send_request_global('GET', url=url, headers=headers)
    if not response:
        sender.reply('连接青龙获取变量失败(无响应)')
        exit(0)
        
    response = response.json()
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
    response = send_request_global('GET', url=url, headers=headers)
    if not response:
        sender.reply('连接青龙获取变量失败(无响应)')
        exit(0)
        
    response = response.json()
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
        "remarks": f'朴朴:{account}丨用户:{owner_id}丨手机:{phone}丨朴朴管理',
        "id": qlid
    }
    headers = {
        "Authorization": "Bearer" + ' ' + qltoken,
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    response = send_request_global('PUT', qlurl, headers=headers, data=json.dumps(data))
    if response and response.status_code == 200:
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
        
        data = [{
            "value": value,
            "name": osname,
            "remarks": f'朴朴:{account}丨用户:{owner_id}丨手机:{phone}丨朴朴管理'
        }]
        
        headers = {
            "Authorization": f"Bearer {qltoken}",
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        
        response = send_request_global('POST', qlurl, headers=headers, json=data)
        
        if not response or response.status_code != 200:
            sender.reply(f"""
=====添加变量失败=====
❌ 请求失败
状态码: {response.status_code if response else '无响应'}
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
        response = send_request_global('GET', url)
        
        if not response or response.status_code != 200:
            sender.reply(f"""
=====请求失败=====
❌ 青龙API请求失败
------------------
状态码: {response.status_code if response else '无响应'}
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

# --- 青龙文件操作函数 (替换原本的Addenvs) ---
def lookfiles(filespath):
    """读取青龙文件（兼容新旧API）"""
    try:
        if not QLurl or not qltoken: 
            return ""
            
        if '/' in filespath:
            filespaths = filespath.split("/")
            path = filespaths[0]
            file = filespaths[1]
        else:
            path = ''
            file = filespath
            
        headers = {
            'accept': 'application/json',
            'Authorization': f"Bearer {qltoken}",
        }
        
        # 方式1：尝试新版API（/detail）
        url_new = f"{QLurl}/open/scripts/detail"
        params_new = {"path": path, "file": file}
        
        response = send_request_global('GET', url_new, headers=headers, params=params_new)
        if response and response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                return result.get('data', '')
        
        # 方式2：尝试旧版API（/{file}）
        url_old = f"{QLurl}/open/scripts/{file}"
        params_old = {"path": path}
        
        response = send_request_global('GET', url_old, headers=headers, params=params_old)
        if response and response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                return result.get('data', '')
        
        return ""
        
    except Exception:
        return ""

def Addfiles(filespath, content):
    try:
        if not QLurl or not qltoken: return
        if '/' in filespath:
            filespaths = filespath.split("/")
            path = filespaths[0]
            filename = filespaths[1]
        else:
            path = ''
            filename = filespath
            
        url = f'{QLurl}/open/scripts'
        headers = {
            'accept': 'application/json',
            'Authorization': f"Bearer {qltoken}",
        }
        json_data = {
            'filename': filename,
            'path': path,
            'content': content,
        }
        send_request_global('POST', url, headers=headers, json=json_data)
    except Exception:
        pass

def SyncToQinglong(account_id, mobile, refresh_token):
    """同步Token到青龙文件"""
    if not filespath: return
    try:
        current_content = lookfiles(filespath)
        new_line = f'{refresh_token}#By 朴朴管理丨朴朴:{mobile}丨用户:{userid}丨身份id:{account_id}'
        
        final_content = ""
        if current_content:
            lines = current_content.split("\n")
            new_lines = []
            found = False
            for line in lines:
                if account_id in line:
                    new_lines.append(new_line)
                    found = True
                elif line.strip():
                    new_lines.append(line)
            if not found:
                new_lines.append(new_line)
            final_content = "\n".join(new_lines)
        else:
            final_content = new_line
            
        Addfiles(filespath, final_content)
    except Exception:
        pass

###################
#   逻辑函数区块   #
###################

def login():
    """账号登录"""
    login_guide = """
=====朴朴登录=====
[1] Cookie登录
[2] 微信扫码登录
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
        
    refresh_token = None
    if choice == '2':
        refresh_token = ScanCodeLogin()
    elif choice == '1':
        sender.reply("=====Cookie登录=====\n请输入refresh_token:\n------------------\n回复'q'退出")
        ck_input = sender.input(60000, 1, False)
        if ck_input and ck_input.lower() != 'q':
            refresh_token = ck_input
        else:
            sender.reply("✅ 已退出操作")
            return
    else:
        sender.reply("❌ 无效的选择")
        return

    if not refresh_token: return

    sender.reply("正在验证Token有效性...")
    mobile, nick_name, new_refresh, access_token, user_id, valid = _refresh_token_logic(refresh_token)
    
    if not valid:
        sender.reply("❌ 登录失败: Token无效或已过期")
        return

    # 账号绑定逻辑
    accounts = eval(middleware.bucketGet('yuhua_pp_user', userid) or '[]')
    
    is_new = True
    if user_id in accounts:
        is_new = False
    elif not accounts:
        pass
        
    if user_id not in accounts:
        accounts.append(user_id)
        middleware.bucketSet('yuhua_pp_user', userid, str(accounts))
        
    middleware.bucketSet('yuhua_pp_token', user_id, new_refresh)
    middleware.bucketSet('yuhua_pp_mobile', user_id, mobile)
    
    mobile_mask = mobile[:3] + "****" + mobile[-4:] if len(mobile) > 7 else mobile
    status_msg = "添加成功" if is_new else "更新成功"
    
    sender.reply(f"""
=====登录成功=====
🤪 账号: {mobile_mask}
✅ 状态: {status_msg}
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")

    # 检查授权并同步
    auth_time = middleware.bucketGet('yuhua_pp_auth', user_id)
    if auth_time and auth_time >= str(datetime.now().date()):
        SyncToQinglong(user_id, mobile, new_refresh)

def _try_auto_refresh(account_id):
    """智能刷新保活逻辑"""
    _sync_token_from_ql(account_id)
    
    old_refresh = middleware.bucketGet('yuhua_pp_token', account_id)
    if not old_refresh: return None, None
    
    mobile, nick_name, new_refresh, access_token, user_id, valid = _refresh_token_logic(old_refresh)
    
    if valid:
        middleware.bucketSet('yuhua_pp_token', account_id, new_refresh)
        middleware.bucketSet('yuhua_pp_mobile', account_id, mobile)
        
        auth_time = middleware.bucketGet('yuhua_pp_auth', account_id)
        if auth_time and auth_time >= str(datetime.now().date()):
            SyncToQinglong(account_id, mobile, new_refresh)
            
        return access_token, mobile
    return None, None

def _sync_token_from_ql(account_id):
    """
    【新增】前置同步函数
    作用：在操作前检查青龙文件，如果青龙端已有新Token，强制同步到本地。
    解决：Node.js脚本刷新Token后，插件因持有旧Token导致操作失败的问题。
    """
    try:

        if not filespath or not qltoken: return

        content = lookfiles(filespath)
        if not content: return

        lines = content.split("\n")
        for line in lines:

            if str(account_id) in line and "#" in line:
                
                ql_token = line.split("#")[0].strip()
                
                local_token = middleware.bucketGet('yuhua_pp_token', account_id)
                
                if ql_token and ql_token != local_token:
                    if DEBUG:
                        printf(f"发现Token差异，正在从青龙同步账号 {account_id}", "INFO")
                    middleware.bucketSet('yuhua_pp_token', account_id, ql_token)
                
                break
    except Exception as e:
        if DEBUG:
            printf(f"前置同步出错: {str(e)}", "WARN")
        pass

def _query_single_account(unique_id):
    """【内部函数】用于并发查询单个账号的朴分信息。"""
    time.sleep(random.uniform(0.5, 1.0))
    mobile = middleware.bucketGet('yuhua_pp_mobile', unique_id) or "未知"
    phone_mask = mobile[:3] + "****" + mobile[-4:] if len(mobile) >= 7 else mobile
    
    auth_time = middleware.bucketGet('yuhua_pp_auth', unique_id)
    now_date = datetime.now().date()
    if not auth_time: return f"【{phone_mask}】未授权"
    auth_date = datetime.strptime(auth_time, "%Y-%m-%d").date()
    if auth_date < now_date: return f"【{phone_mask}】授权已过期"  
    
    refresh_token = middleware.bucketGet('yuhua_pp_token', unique_id)
    if not refresh_token: return f"【{phone_mask}】Token丢失"

    # 智能刷新确保Token有效
    access_token, new_mobile = _try_auto_refresh(unique_id)
    if not access_token:
        return f"【{phone_mask}】登录失效，请重新登录"
        
    balance, todaycoin, expiring_coin, expire_time = coin(access_token)
    if balance == '查询失败':
        return f"【{phone_mask}】查询接口异常"

    # 处理过期朴分显示逻辑
    exp_line = ""
    if expiring_coin and int(expiring_coin) > 0:
        date_badge = ""
        if expire_time:
            try:
                # 将时间戳转换为日期对象
                dt = datetime.fromtimestamp(int(expire_time) / 1000)
                # 格式化为 YYYY.M.D (例如 2026.3.31)
                date_str = f"{dt.year}.{dt.month}.{dt.day}"
                # 映射表：数字和点号转为上标
                trans_table = str.maketrans("0123456789.", "⁰¹²³⁴⁵⁶⁷⁸⁹∙")
                date_badge = " " + date_str.translate(trans_table)
            except:
                pass
        exp_line = f"⛱️ 过期朴分: {expiring_coin}{date_badge}\n"

    return f"""
=====账号信息=====
🤪 账号: {phone_mask}
🎫 当前朴分: {balance}
🎨 今日朴分: {todaycoin}
{exp_line}☁️ 授权到期: {auth_time}
=================="""

def query_account():
    """
    【朴朴查询】：查询已授权账号的朴分信息（并发版）
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
        
    sender.reply(f"正在查询....")

    for acc_id in accounts:
        try:
            result_msg = _query_single_account(acc_id)
            if result_msg:
                sender.reply(result_msg)
        except Exception as e:
            sender.reply(f"❌ 查询出错: {e}")

def _mask_identifier(identifier: str) -> str:
    """
    将账号/手机号/UID 等中间脱敏，保留前3位和后4位
    例如: 13812345678 -> 138****5678
    """
    if not identifier: return "未知"
    if "****" in identifier: return identifier
    # 长度不足的直接返回或简单处理
    if len(identifier) <= 7: return identifier
    
    # 修改核心: [:4] 改为 [:3]
    return identifier[:3] + "****" + identifier[-4:]

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

    total_amount = len(accounts) * months * price
    if total_amount > 0:
        pay_ok = process_payment(total_amount, months, f"名下所有 {len(accounts)} 个账号")
        if not pay_ok:
            return

    success_count = 0
    failed_count = 0
    for acc_id in accounts:
        try:
            auth_time = calculate_auth_time(acc_id, months * 30)
            middleware.bucketSet('yuhua_pp_auth', acc_id, auth_time)
            
            # 立即同步
            refresh = middleware.bucketGet('yuhua_pp_token', acc_id)
            mobile = middleware.bucketGet('yuhua_pp_mobile', acc_id)
            if refresh:
                SyncToQinglong(acc_id, mobile, refresh)
            
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
    uservalue = middleware.bucketGet('yuhua_pp_user', userid)
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
        mobile = middleware.bucketGet('yuhua_pp_mobile', acc_id) or "未知"
        mobile_mask = _mask_identifier(mobile)
        auth_str = middleware.bucketGet('yuhua_pp_auth', acc_id)
        
        status_line = "⚠️ 未授权"
        if auth_str:
            try:
                auth_date = datetime.strptime(auth_str, "%Y-%m-%d").date()
                if auth_date > datetime.now().date():
                    status_line = f"✅ {auth_str}"
                else:
                    status_line = "❌ 已过期"
            except: pass
            
        account_list += f"------------------\n[{i}] 账号信息\n🤪 账号: {mobile_mask}\n☁ 授权: {status_line}\n"
        
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
[3] 刷新凭证
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
        manual_refresh_single(account)
    else:
        sender.reply("❌ 无效的选择")

def manual_refresh_single(account_id):
    """【新增】手动刷新单个账号凭证（用户/菜单通用）"""

    mobile = middleware.bucketGet('yuhua_pp_mobile', account_id) or "未知"
    mobile_mask = _mask_identifier(mobile)
    
    # 检查授权
    auth_time = middleware.bucketGet('yuhua_pp_auth', account_id)
    today_str = str(datetime.now().date())
    
    if not auth_time or auth_time < today_str:
        sender.reply(f"""
=====刷新失败=====
🤪 账号: {mobile_mask}
💫 结果: 未授权或授权已过期
==================""")
        return

    # 调用原有的智能刷新逻辑，该函数内部成功后会自动同步到青龙
    access_token, _ = _try_auto_refresh(account_id)
    
    if access_token:
        sender.reply(f"""
=====刷新成功=====
🤪 账号: {mobile_mask}
💫 结果: 登录凭证已刷新
==================""")
    else:
        sender.reply(f"""
=====刷新失败=====
🤪 账号: {mobile_mask}
💫 结果: 登录凭证已失效
==================""")

def admin_batch_refresh():
    """【新增】管理员一键刷新所有账号"""
    if not sender.isAdmin():
        sender.reply("❌ 需要管理员权限")
        return

    sender.reply("正在执行...")
    
    users = middleware.bucketAllKeys('yuhua_pp_user')
    today_str = str(datetime.now().date())
    
    total_count = 0
    success_count = 0
    failed_count = 0
    fail_details = ""
    
    for user in users:
        accounts = eval(middleware.bucketGet('yuhua_pp_user', user) or '[]')
        for acc_id in accounts:
            total_count += 1
            mobile = middleware.bucketGet('yuhua_pp_mobile', acc_id) or "未知"
            mobile_mask = _mask_identifier(mobile)
            
            # 检查授权
            auth_time = middleware.bucketGet('yuhua_pp_auth', acc_id)
            if not auth_time or auth_time < today_str:
                failed_count += 1
                fail_details += f"🤪 账号: {mobile_mask}\n🪁 原因: 未授权或授权已过期\n"
                continue
            
            # 执行刷新
            try:
                # _try_auto_refresh 成功后会自动 SyncToQinglong
                access_token, _ = _try_auto_refresh(acc_id)
                if access_token:
                    success_count += 1
                else:
                    failed_count += 1
                    fail_details += f"🤪 账号: {mobile_mask}\n🪁 原因: 登录凭证已失效，请重新登录\n"
            except Exception as e:
                failed_count += 1
                fail_details += f"🤪 账号: {mobile_mask}\n🪁 原因: 刷新过程发生异常\n"
                
    if not fail_details:
        fail_details = "无"
    else:
        fail_details = fail_details.rstrip()
        
    reply_msg = f"""
=====朴朴一键刷新=====
✨ 总账号数: {total_count}
✅ 刷新成功: {success_count}
❌ 刷新失败: {failed_count}
------------------
📝 失败详情:
{fail_details}
=================="""
    sender.reply(reply_msg)
    

def confirm_delete(account):
    """确认是否删除账号"""
    mobile = middleware.bucketGet('yuhua_pp_mobile', account) or "未知"
    sender.reply(f"⚠️ 确认要删除账号 {mobile} 吗？(y/n)")
    confirm = sender.input(60000, 0, False)
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
    uservalue = middleware.bucketGet('yuhua_pp_user', userid)
    accounts = eval(uservalue or '[]')
    if account not in accounts:
        sender.reply("❌ 未找到账号")
        return
        
    # 删除青龙文件记录
    if filespath:
        try:
            content = lookfiles(filespath)
            new_lines = [line for line in content.split("\n") if account not in line]
            Addfiles(filespath, "\n".join(new_lines))
        except: pass
        
    accounts.remove(account)
    if accounts:
        middleware.bucketSet('yuhua_pp_user', userid, str(accounts))
    else:
        try:
            middleware.bucketDel('yuhua_pp_user', userid)
        except Exception:
            pass

    try:
        middleware.bucketDel('yuhua_pp_token', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_pp_mobile', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_pp_auth', account)
    except Exception:
        pass
    
    sender.reply(f"✅ 已删除账号")

def auth_account(account):
    """【账号授权】：用户侧手动授权/续费"""
    mobile = middleware.bucketGet('yuhua_pp_mobile', account) or "未知"
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
        if not process_payment(amount, months, mobile):
            return
    auth_time = calculate_auth_time(account, months * 30)
    middleware.bucketSet('yuhua_pp_auth', account, auth_time)
    
    refresh = middleware.bucketGet('yuhua_pp_token', account)
    if refresh:
        SyncToQinglong(account, mobile, refresh)
    
    days = 30*months
    sender.reply(f"""
=====授权成功=====
🤪 账号: {mobile}
⏰ 时长: {days}天
📅 到期: {auth_time}
=======================""")

def calculate_auth_time(account, days):
    """计算授权到期时间，days 为授权天数 (支持负数)"""
    current_date = datetime.now().date()
    auth_str = middleware.bucketGet('yuhua_pp_auth', account)
    
    start_date = current_date
    if auth_str:
        try:
            auth_date = datetime.strptime(auth_str, "%Y-%m-%d").date()
            if auth_date > current_date:
                start_date = auth_date
        except ValueError:
            pass # 如果日期格式错误，则从今天开始计算

    end_date = start_date + timedelta(days=days)

    if days < 0 and end_date < current_date:
        return str(current_date - timedelta(days=1))
        
    return str(end_date)

def process_payment(amount, months, phone_mask):
    """处理支付"""
    zsm = middleware.bucketGet('yuhua_pp', 'zsm')
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
    users = middleware.bucketAllKeys('yuhua_pp_user')
    cleaned = 0
    
    file_content = lookfiles(filespath) if filespath else ""
    valid_file_lines = file_content.split("\n") if file_content else []

    for user in users:
        accounts = eval(middleware.bucketGet('yuhua_pp_user', user) or '[]')
        valid = []
        for acc_id in accounts:
            auth = middleware.bucketGet('yuhua_pp_auth', acc_id)
            if (not auth) or (auth <= str(datetime.now().date())):
                try:
                    middleware.bucketDel('yuhua_pp_token', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_pp_mobile', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_pp_auth', acc_id)
                except Exception:
                    pass
                valid_file_lines =[l for l in valid_file_lines if acc_id not in l]
                cleaned += 1
            else:
                valid.append(acc_id)
        if valid:
            middleware.bucketSet('yuhua_pp_user', user, str(valid))
        else:
            try:
                middleware.bucketDel('yuhua_pp_user', user)
            except Exception:
                pass
            
    if filespath and cleaned > 0:
        Addfiles(filespath, "\n".join(valid_file_lines))
        
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
        users = middleware.bucketAllKeys('yuhua_pp_user')
        success = 0
        failed = 0
        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_pp_user', user) or '[]')
            for acc_id in accounts:
                try:
                    auth_time = calculate_auth_time(acc_id, days)
                    middleware.bucketSet('yuhua_pp_auth', acc_id, auth_time)
                    
                    refresh = middleware.bucketGet('yuhua_pp_token', acc_id)
                    mobile = middleware.bucketGet('yuhua_pp_mobile', acc_id)
                    if refresh:
                        SyncToQinglong(acc_id, mobile, refresh)
                    
                    success += 1
                except Exception as e:
                    failed += 1
        
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
    """指定用户授权 (修复版: 增加账号选择菜单)"""
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

    accounts = eval(middleware.bucketGet('yuhua_pp_user', user_id) or '[]')
    if not accounts:
        sender.reply("❌ 该用户没有绑定账号")
        return

    # 生成账号选择菜单
    account_list_msg = "=====账号列表=====\n[0] 授权全部账号\n"
    for i, acc_id in enumerate(accounts, 1):
        mobile = middleware.bucketGet('yuhua_pp_mobile', acc_id) or "未知"
        mobile_mask = _mask_identifier(mobile)
        auth_str = middleware.bucketGet('yuhua_pp_auth', acc_id)
        
        status_line = "⚠️ 未授权"
        if auth_str:
            try:
                auth_date = datetime.strptime(auth_str, "%Y-%m-%d").date()
                if auth_date > datetime.now().date():
                    status_line = f"✅ {auth_date.strftime('%Y-%m-%d')}"
                else:
                    status_line = "❌ 已过期"
            except ValueError:
                status_line = "⚠️ 未授权"
        
        account_list_msg += f"------------------\n[{i}] 账号信息\n🤪 账号: {mobile_mask}\n☁ 授权: {status_line}\n"
        
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

    # 确定目标账号
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
        # 重新获取最新的账号列表以防止并发操作导致的差异
        latest_accounts = eval(middleware.bucketGet('yuhua_pp_user', user_id) or '[]')
        
        success = 0
        failed = 0
        for acc_id in target_accounts:
            if acc_id not in latest_accounts:
                failed += 1
                continue

            try:
                auth_time = calculate_auth_time(acc_id, days)
                middleware.bucketSet('yuhua_pp_auth', acc_id, auth_time)
                
                # 同步到青龙
                refresh = middleware.bucketGet('yuhua_pp_token', acc_id)
                mobile = middleware.bucketGet('yuhua_pp_mobile', acc_id)
                if refresh:
                    SyncToQinglong(acc_id, mobile, refresh)

                success += 1
            except Exception:
                failed += 1
        
        action_text = "授权" if days > 0 else "扣除"
        day_abs = abs(days)
        reply_msg = f"""
=====操作完成=====
👤 用户: {user_id}
✅ 成功: {success}个账号
❌ 失败: {failed}个账号
⏰ 时长: {action_text}{day_abs}天
=================="""
        sender.reply(reply_msg)

    except ValueError:
        sender.reply("❌ 无效的天数")
    except Exception as e:
        sender.reply(f"❌ 授权时发生未知错误: {str(e)}")


def cron_task():
    """定时任务处理"""
    if imtype != 'fake':
        pass
    today_str = str(datetime.now().date())
    try:
        users = middleware.bucketAllKeys('yuhua_pp_user')
        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_pp_user', user) or '[]')
            for acc_id in accounts:
                time.sleep(random.uniform(0.5, 1.0))
                try:
                    auth_time = middleware.bucketGet('yuhua_pp_auth', acc_id)
                    if not auth_time or auth_time <= today_str:
                        notify_user(user, acc_id, "授权已过期，请及时续费")
                        continue
                        
                    token, mobile = _try_auto_refresh(acc_id)
                    if not token:
                        notify_user(user, acc_id, "登录凭证已失效，请重新登录")
                except Exception as e:
                    printf(f"处理账号 {acc_id} 出错: {str(e)}", "WARN")
                    continue
    except Exception as e:
        printf(f"定时任务出错: {str(e)}", "ERROR")

notified_accounts = set()
def notify_user(user, account, message):
    """发送用户通知"""
    try:
        if account in notified_accounts:
            return
        mobile = middleware.bucketGet('yuhua_pp_mobile', account) or "未知"
        notify_msg = f"""
=====朴朴通知=====
🤪 账号: {mobile}
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
        printf(f"发送通知失败: {str(e)}", "WARN")

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
            session = get_global_session()
            response = session.get(
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
        elif message == '朴朴清理':
            clean_expired()
        elif message == '朴朴授权':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            admin_auth()
        elif message == '朴朴检测':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            sender.reply("正在检测....")
            cron_task()
            sender.reply("✅ 已执行朴朴检测推送任务")
        elif message == '朴朴一键刷新':
            admin_batch_refresh()
        elif message == '朴朴刷新':
            uservalue = middleware.bucketGet('yuhua_pp_user', userid)
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
            
            sender.reply("正在执行...")
            
            for acc in accounts:
                manual_refresh_single(acc)
        else:
            sender.setContinue()
    except Exception as e:
        sender.reply(f"❌ 运行出错: {str(e)}")
                
if __name__ == "__main__":
    try:
        manage_cmd, query_cmd, login_cmd, price, bingfa, yuhua_pp_qlname, filespath = get_config()
        today = str(datetime.now().date())
        if imtype == 'fake':
            cron_task()
        else:
            main()
    except Exception as e:
        sender.reply(f"❌ 运行出错: {str(e)}")
