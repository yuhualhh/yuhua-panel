# [title: 顺丰速运]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@677fce16677bac49d692cc3d19f0122c7e9793f1/2025/06/06/94baa1a1ccc672f66dfe334b0dcfb162.png]
# [rule: ^(顺丰)(登录|查询|管理|清理|检测|授权|代付)$]
# [disable:false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [cron: 1 1 1 1 1]
# [public: true]
# [priority: 99999999999]
# [open_source: false]
# [class: 工具类]
# [version: 2.3.3]
# [price: 0]
# [admin: false]
# [author: 羽化]
# [description: ❶顺丰速运插件，支持 顺丰代付、验证码登录、微信扫码登录、查询、管理、授权、检测授权过期以及CK失效推送等功能<br>❷已解决登录凭证失效过快问题<br>❸部分功能的实现需自行添加计划任务伪装管理员定时，了解如何添加计划任务请看移动云盘插件介绍，关于指令『顺丰清理』与『顺丰检测』定时『30 18 * * *』<br>❹请把插件触发规则全部替换成^(顺丰)(登录|查询|管理|清理|检测|授权|代付)$<img src="https://gcore.jsdelivr.net/gh/lhz03/img@ce6b6dde1faa7c1f0d2ca461759dcfc4f26f8164/2026/03/31/dd1b294bd43546a59c9b0e932a6a8f59.png">]
import re
from datetime import datetime, timedelta
import middleware
import urllib.parse
from decimal import Decimal
import requests
import time
import json
import hashlib
import urllib.parse
import uuid
import threading
import io
import os
import base64
import socket
from datetime import timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import sys
try:
    import qrcode
except ImportError:
    import os
    os.system("pip install qrcode[pil]")
    import qrcode
try:
    from packaging import version
except ImportError:
    import os
    os.system("pip install packaging")
    from packaging import version
senderID = middleware.getSenderID()
sender = middleware.Sender(senderID)
userid = sender.getUserID()
uservalue = middleware.bucketGet(bucket='yuhua_sf_user', key=userid)
# [param: {"required":true,"key":"yuhua_sf.zsm","bool":false,"placeholder":"","name":"收款码子","desc":"微信Bot收款码直链"}]
# [param: {"required":true,"key":"yuhua_sf.yuhua_sf_qlname","bool":false,"placeholder":"Host丨ClientID丨ClientSecret","name":"对接容器","desc":"各参数之间用中文符丨分割，例如: http://127.0.01:5700/丨abcdef-ghijk丨abcdefghijklmnopqrs_tuvw"}]
# [param: {"required":true,"key":"yuhua_sf.yuhua_sf_osname","bool":false,"placeholder":"必填项，例: sfsyUrl","name":"环境变量","desc":"定义提交至容器的变量名称"}]
# [param: {"required":true,"key":"yuhua_sf.sfVipmoney","bool":false,"placeholder":"","name":"收费价格","desc":"不填默认0元，单位: 元/月"}]
# [param: {"required":false,"key":"yuhua_sf.sfdf","bool":false,"placeholder":"","name":"体验秘钥","desc":"请输入密钥yuhua888，开启顺丰代付功能"}]
### [param: {"required":false,"key":"yuhua_sf.renew_bingfa","bool":false,"placeholder":"","name":"续期并发","desc":"不填默认15"}
# [param: {"required":false,"key":"yuhua_sf.debug_pwd","bool":false,"placeholder":"","name":"调试模式","desc":"非插件开发者无需理会，填入密钥开启详细日志"}]
#[param: {"required":false,"key":"yuhua_sf.hide_medal","bool":true,"placeholder":"","name":"周年勋章","desc":"是否隐藏顺丰查询的33周年勋章详情"}]
debug_key = middleware.bucketGet('yuhua_sf', 'debug_pwd') or ''
DEBUG = (debug_key == '123456789abcC@')
if DEBUG:
    sys.stderr.write("\033[33m[WARN] 🔥🔥🔥 顺丰插件调试模式已开启，密钥验证通过 🔥🔥🔥\033[0m\n")
    sys.stderr.flush()
def printf(msg, level='INFO'):
    if not DEBUG: return
    c = 32 if level in ['INFO', 'DEBUG'] else 33 if level in ['WARN', 'WARNING'] else 31
    sys.stderr.write(f"\033[{c}m[{level}] {str(msg)}\033[0m\n")
    sys.stderr.flush()
def format_sf_amount_fen(amount):
    try:
        amount_str = str(amount).strip()
        if amount_str == '':
            return str(amount)
        return f"{int(float(amount_str)) / 100:.2f}"
    except Exception:
        return str(amount)
def mask_pay_order_id(pay_order_id):
    if not pay_order_id:
        return "-"
    pay_order_id = str(pay_order_id)
    if len(pay_order_id) <= 8:
        return pay_order_id[:2] + "****" if len(pay_order_id) > 2 else pay_order_id
    return pay_order_id[:6] + "****" + pay_order_id[-4:]
def ensure_private_chat_for_sf_pay():
    try:
        chat_id = sender.getChatID()
        if str(chat_id) not in ("0", "", "None"):
            sender.reply("""
=====顺丰代付=====
🔒 顺丰代付仅私聊使用
💡 为避免泄露个人隐私
==================""")
            return False
        return True
    except Exception:
        return True
def send_request_global(method, url, **kwargs):
    session = kwargs.pop('session', None)
    if DEBUG:
        printf(f"\n===== [REQUEST START] =====", "DEBUG")
        printf(f"METHOD: {method} | URL: {url}", "DEBUG")
        printf(f"HEADERS: {json.dumps(kwargs.get('headers', {}), ensure_ascii=False)}", "DEBUG")
        if kwargs.get('json'):
            printf(f"BODY(JSON): {json.dumps(kwargs.get('json'), ensure_ascii=False)}", "DEBUG")
        elif kwargs.get('data'):
            data_str = str(kwargs.get('data'))
            if len(data_str) > 500: data_str = data_str[:200] + "...(truncated)..."
            printf(f"BODY(DATA): {data_str}", "DEBUG")           
    try:
        if session:
            response = session.request(method, url, **kwargs)
        else:
            response = requests.request(method, url, **kwargs)        
        if DEBUG:
            printf(f"----- [RESPONSE] -----", "DEBUG")
            printf(f"STATUS: {response.status_code}", "DEBUG")
            printf(f"RSP HEADERS: {json.dumps(dict(response.headers), ensure_ascii=False)}", "DEBUG")
            try:
                printf(f"RSP BODY: {json.dumps(response.json(), ensure_ascii=False)}", "DEBUG")
            except:
                printf(f"RSP BODY: {response.text[:1000]}", "DEBUG")
            printf(f"===== [REQUEST END] =====\n", "DEBUG")          
        return response
    except Exception as e:
        if DEBUG: printf(f"⚠️ Request Error: {e}", "WARN")
        raise e
def getusercontent():
    yuhua_sf_osname = middleware.bucketGet('yuhua_sf', 'yuhua_sf_osname') or 'yuhua_sf_token'
    yuhua_sf_qlname = middleware.bucketGet('yuhua_sf', 'yuhua_sf_qlname') or 'yuhua_sf_token'
    yuhua_managecommand = middleware.bucketGet('yuhua_sf', 'yuhua_managecommand') or '顺丰管理'
    yuhua_querycommand = middleware.bucketGet('yuhua_sf', 'yuhua_querycommand') or '顺丰查询'
    yuhua_signcommand = middleware.bucketGet('yuhua_sf', 'yuhua_signcommand') or '顺丰登录'
    randommanagecommand = yuhua_managecommand
    randomquerycommand = yuhua_querycommand
    randomsigncommand = yuhua_signcommand
    sfVipmoney = Decimal(middleware.bucketGet('yuhua_sf', 'sfVipmoney') or '0')
    show_point_status = middleware.bucketGet('yuhua_sf', 'show_point_status') or 'false'
    show_point_status = show_point_status.lower() == 'true'
    qiangquan_bingfa_str = middleware.bucketGet('yuhua_sf', 'qiangquan_bingfa') or '15'
    try:
        qiangquan_bingfa = int(qiangquan_bingfa_str)
    except (ValueError, TypeError):
        qiangquan_bingfa = 15
    renew_bingfa_str = middleware.bucketGet('yuhua_sf', 'renew_bingfa') or '15'
    try:
        renew_bingfa = int(renew_bingfa_str)
    except (ValueError, TypeError):
        renew_bingfa = 15
    return (yuhua_sf_osname, yuhua_sf_qlname, yuhua_managecommand, yuhua_querycommand,
            yuhua_signcommand, randommanagecommand, randomquerycommand,
            randomsigncommand, sfVipmoney, show_point_status, qiangquan_bingfa, renew_bingfa)
def seekql():
    try:
        if len(yuhua_sf_qlname) == 0:
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
        qllist = yuhua_sf_qlname.split('丨')
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
    if id is None:
        return
    url = f"{QLurl}/open/envs"
    headers = {
        "Authorization": "Bearer" + ' ' + qltoken,
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    data = [id]
    response = requests.delete(url, headers=headers, json=data).json()
def allenvs(osname, account):
    url = f"{QLurl}/open/envs"
    headers = {
        "Authorization": "Bearer" + ' ' + qltoken,
        "accept": "application/json"
    }
    response = requests.get(url=url, headers=headers).json()
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
    phone = phone[:3] + '*' * 4 + phone[7:]
    url = f"{QLurl}/open/envs"
    headers = {
        "Authorization": "Bearer" + ' ' + qltoken,
        "accept": "application/json"
    }
    response = requests.get(url=url, headers=headers).json()
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
    data = {
        "value": value,
        "name": osname,
        "remarks": f'顺丰:{account}丨用户:{owner_id}丨手机:{phone}丨顺丰管理',
        "id": qlid
    }
    headers = {
        "Authorization": "Bearer" + ' ' + qltoken,
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.put(qlurl, headers=headers, data=json.dumps(data))
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
        data = [{
            "value": value,
            "name": osname,
            "remarks": f'顺丰:{account}丨用户:{owner_id}丨手机:{phone}丨顺丰管理'
        }]        
        headers = {
            "Authorization": f"Bearer {qltoken}",
            "accept": "application/json",
            "Content-Type": "application/json",
        }        
        response = requests.post(qlurl, headers=headers, json=data)        
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
def QLtoken(QLurl, ClientID, ClientSecret):
    try:
        url = f'{QLurl}/open/auth/token?client_id={ClientID}&client_secret={ClientSecret}'
        response = requests.get(url)        
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
def get_ql_cookie_format(account, fallback_url):
    session_id = middleware.bucketGet('yuhua_sf_sessionId', account)
    member_id = middleware.bucketGet('yuhua_sf_memberid', account) or ""
    if not session_id and fallback_url and fallback_url.startswith(('http://', 'https://')):
        s_id, _, ext_m_id = session_ids(fallback_url)
        if s_id:
            session_id = s_id
            middleware.bucketSet('yuhua_sf_sessionId', account, s_id)
            if ext_m_id:
                member_id = ext_m_id
                middleware.bucketSet('yuhua_sf_memberid', account, member_id)                
    if session_id:
        return f"sessionId={session_id}; _login_mobile_={account}; _login_user_id_={member_id}"
    return fallback_url
def session_ids(url):
    if not url or not url.startswith(('http://', 'https://')):
        return None, None, None        
    try:
        response = send_request_global('GET', url, allow_redirects=False, timeout=10)
        headers_str = str(response.headers)        
        session_id_pattern = r'sessionId=([^;]+);'
        login_mobile_pattern = r'_login_mobile_=([^;]+);'
        member_id_pattern = r'_login_user_id_=([^;]+);'        
        session_id_match = re.search(session_id_pattern, headers_str)
        login_mobile_match = re.search(login_mobile_pattern, headers_str)
        member_id_match = re.search(member_id_pattern, headers_str)        
        if session_id_match and login_mobile_match:
            session_id = session_id_match.group(1)
            login_mobile = login_mobile_match.group(1)
            member_id = member_id_match.group(1) if member_id_match else None            
            if '用户手机号校验未通过' in response.text:
                return None, None, None                
            return session_id, login_mobile, member_id
        else:
            return None, None, None            
    except (requests.exceptions.RequestException, Exception):
        return None, None, None
def todaycoin(session_id):
    pageNo = 1
    coin = 0
    while True:
        url = "https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberIntegral~memberPoint~queryMemberPointDetail"
        headers = {
            "Cookie": f"sessionId={session_id}"
        }
        data = {
            "type": "ALL",
            "pageNo": pageNo,
            "pageSize": 10
        }
        try:
            if 'send_request_global' in globals():
                response = send_request_global('POST', url, headers=headers, json=data).json()
            else:
                response = requests.post(url, headers=headers, json=data).json()
            if not response.get('success', False):
                error_msg = response.get('errorMessage', '查询失败')
                return None, error_msg
            obj = response.get('obj')
            if not obj:
                if pageNo == 1:
                    return 0, '0'
                break                
            data_list = obj.get('data', [])
            if not data_list:
                if pageNo == 1:
                    return 0, '0'
                break
            allcoin = obj.get('usablePoint', '0')            
            should_break = False
            for coinjson in data_list:
                createTm = coinjson.get('createTm', '')
                if not createTm: continue
                try:
                    datetime_obj = datetime.strptime(createTm, "%Y-%m-%d %H:%M:%S")
                    date_str = datetime_obj.strftime("%Y-%m-%d")
                    if date_str < str(today_time):
                        should_break = True
                        break
                    else:
                        opCode = coinjson.get('opCode')
                        pointVal = coinjson.get('pointVal', 0)
                        if opCode == 'ADD':
                            coin = coin + int(pointVal)
                        else:
                            continue
                except ValueError:
                    continue            
            if should_break:
                break
            if data_list:
                last_createTm = data_list[-1].get('createTm')
                if last_createTm:
                    try:
                        datetime_obj = datetime.strptime(last_createTm, "%Y-%m-%d %H:%M:%S")
                        date_str = datetime_obj.strftime("%Y-%m-%d")
                        if date_str >= str(today_time):
                            pageNo = pageNo + 1
                        else:
                            break
                    except:
                        break
                else:
                    break
            else:
                break
                
        except Exception as e:
            return None, f"请求异常: {str(e)}"
    return coin, allcoin
def sytTokens(payload, deviceId):
    jsbundle_login = "705088894ad6ef475bdf4875c9d533b8"
    syt_token, time_interval = get_remote_syt_token(payload, deviceId, jsbundle_login)
    return syt_token, time_interval
LOGIN_URL = "https://ccsp-egmas.sf-express.com/cx-app-member/member/app/user/signInAndSignUp"
UNIVERSAL_SIGN_URL = "https://ccsp-egmas.sf-express.com/cx-app-member/member/app/user/universalSign"
SEND_SMS_URL = "https://ccsp-egmas.sf-express.com/cx-app-member/member/app/sms/send"
REGION_CODE = "CN"
SCREEN_SIZE = "2000x2800"
MEDIA_CODE = "AndroidML"
SYSTEM_VERSION = "15"
CLIENT_VERSION = "9.76.0"
MODEL = "OPD2407"
CARRIER = "unknown"
JS_BUNDLE_MD5 = "36b493ed885fd5b9fd7aedd45fe69a34"
SRC_DEVICE_GUID = "DUVdyTROBlUxwEKzRU0r10BQsTMIhtZHSaf0"
LANGUAGE_CODE = "sc"
DEVICE_ID = "0f21782b-b863-3296-b527-0b0346d7f2e4"
def get_remote_syt_token(payload_str, device_id, jsbundle="36b493ed885fd5b9fd7aedd45fe69a34"):
    api_url = "https://yuhualhh.250666.xyz/api/sf_sign.php"    
    data = {
        "payload": payload_str,
        "device_id": device_id,
        "jsbundle": jsbundle
    }    
    for attempt in range(1, 4):
        try:
            response = requests.post(api_url, json=data, timeout=5)
            response.raise_for_status()
            res_json = response.json()            
            is_debug_mode = os.environ.get("sf_debug") == "true" or globals().get("DEBUG", False) or globals().get("debug", False)
            if is_debug_mode:
                print(f"\n🚨🚨🚨{res_json} 🚨🚨🚨\n")            
            if res_json.get("success"):
                return res_json["data"]["sytToken"], res_json["data"]["timeInterval"]
            else:
                raise ValueError(res_json.get("message", "API返回失败"))                
        except Exception as e:
            if attempt == 3:
                raise RuntimeError(f"请求远程云端签名失败(重试3次): {str(e)}")
            time.sleep(1)
def silent_renew_url(account):
    memNo = middleware.bucketGet('yuhua_sf_memNo', account)
    memberId = middleware.bucketGet('yuhua_sf_memberid', account)
    deviceId = middleware.bucketGet('yuhua_sf_deviceId', account)   
    if not all([memNo, memberId, deviceId]):
        return None
    url = "https://ccsp-egmas.sf-express.com/cx-app-member/member/app/user/universalSign"
    payload = {
        "mobile": account,
        "userId": memberId,
        "memNo": memNo,
        "name": "mcs-mimp-web.sf-express.com",
        "extra": "",
        "needReqTime": "1"
    }
    payload_str = json.dumps(payload, separators=(',', ':'))
    for attempt in range(1, 4):
        try:
            if DEBUG:
                printf(f"正在进行第 {attempt} 次静默续期尝试: {account}", "INFO")
            syt_token, time_interval = get_remote_syt_token(payload_str, deviceId, JS_BUNDLE_MD5)
            
            headers = {
                "Host": "ccsp-egmas.sf-express.com",
                "regionCode": "CN",
                "screenSize": "2000x2800",
                "mediaCode": "AndroidML",
                "systemVersion": "15",
                "clientVersion": CLIENT_VERSION,
                "model": "OPD2407",
                "carrier": "unknown",
                "deviceId": deviceId,
                "Content-Type": "application/json",
                "jsbundle": JS_BUNDLE_MD5,
                "srcDeviceGuid": deviceId,
                "languageCode": "sc",
                "memberId": memberId,
                "timeInterval": str(time_interval),
                "sytToken": syt_token,
                "User-Agent": "okhttp/4.9.1"
            }            
            response = requests.post(url, headers=headers, data=payload_str, timeout=10)
            resp_json = response.json()            
            if resp_json.get("success") and resp_json.get("obj", {}).get("sign"):
                sign = resp_json['obj']['sign']
                encoded_sign = urllib.parse.quote(sign)
                new_token_url = f"https://mcs-mimp-web.sf-express.com/mcs-mimp/share/app/shareRedirect?sign={encoded_sign}&source=SFAPP&bizCode=619"
                middleware.bucketSet('yuhua_sf_token', account, new_token_url)                
                try:
                    middleware.bucketDel('yuhua_sf_sessionId', account)
                except Exception:
                    pass
                ql_sync_value = get_ql_cookie_format(account, new_token_url)                
                phone = account[:3] + '*' * 4 + account[7:]
                original_owner_id = middleware.getSenderID() 
                try:
                    all_users = middleware.bucketAllKeys('yuhua_sf_user')
                    for user in all_users:
                        user_accounts_str = middleware.bucketGet('yuhua_sf_user', user)
                        if user_accounts_str and account in user_accounts_str:
                            original_owner_id = user
                            break
                except:
                    pass
                ql_sync_success = False
                for ql_attempt in range(1, 4):
                    try:
                        Addenvs(osname=yuhua_sf_osname, value=ql_sync_value, account=account, phone=phone, owner_id=original_owner_id)
                        ql_sync_success = True
                        if DEBUG:
                            printf(f"青龙同步成功: {account}", "INFO")
                        break
                    except Exception as e:
                        if DEBUG:
                            printf(f"青龙同步失败({ql_attempt}/3): {str(e)}", "WARN")
                        if ql_attempt < 3:
                            time.sleep(2)                
                if not ql_sync_success and DEBUG:
                    printf(f"青龙同步最终失败: {account} (已尝试3次)", "ERROR")
                return new_token_url
            else:
                if DEBUG:
                    printf(f"续期失败API返回: {resp_json.get('errorMessage')}", "WARN")
        except Exception as e:
            if DEBUG:
                printf(f"续期请求异常: {str(e)}", "WARN")
        time.sleep(1)        
    return None
def check_cookie_valid(session_id):
    try:
        url = "https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralTaskStrategyService~queryPointTaskAndSignFromES"
        headers = {"Cookie": f"sessionId={session_id}", "Content-Type": "application/json"}
        payload = {"channelType": "1", "deviceId": str(uuid.uuid4())}
        res = send_request_global('POST', url, headers=headers, json=payload, timeout=5).json()
        if res and res.get('success'):
            return True
    except Exception:
        pass
    return False
def get_valid_session_or_renew(account):
    session_id = middleware.bucketGet('yuhua_sf_sessionId', account)
    if session_id:
        try:
            if check_cookie_valid(session_id):
                if DEBUG:
                    printf(f"使用缓存的有效CK: {account}", "INFO")
                member_id = middleware.bucketGet('yuhua_sf_memberid', account) or None
                return session_id, account, member_id
        except Exception:
            pass
    userurl = middleware.bucketGet(bucket='yuhua_sf_token', key=f'{account}')
    session_id, login_mobile, member_id = None, None, None   
    if userurl:
        session_id, login_mobile, member_id = session_ids(userurl)
        if session_id:
            middleware.bucketSet('yuhua_sf_sessionId', account, session_id)
            if member_id:
                middleware.bucketSet('yuhua_sf_memberid', account, member_id)                
            if check_cookie_valid(session_id):
                try:
                    m_id = member_id if member_id else ""
                    ql_sync_value = f"sessionId={session_id}; _login_mobile_={account}; _login_user_id_={m_id}"
                    phone = account[:3] + '*' * 4 + account[7:]
                    original_owner_id = middleware.getSenderID() 
                    try:
                        for u in middleware.bucketAllKeys('yuhua_sf_user'):
                            if account in str(middleware.bucketGet('yuhua_sf_user', u)):
                                original_owner_id = u
                                break
                    except: pass                    
                    Addenvs(osname=yuhua_sf_osname, value=ql_sync_value, account=account, phone=phone, owner_id=original_owner_id)
                    if DEBUG:
                        printf(f"被动解析提取成功，已同步Cookie格式至青龙: {account}", "INFO")
                except Exception:
                    pass
                return session_id, login_mobile, member_id
            else:
                session_id = None
    if not session_id:
        if DEBUG:
            printf(f"Token失效或不存在，触发静默续期: {account}", "INFO")
        new_url = silent_renew_url(account)
        if new_url:
            session_id = middleware.bucketGet('yuhua_sf_sessionId', account)
            member_id = middleware.bucketGet('yuhua_sf_memberid', account)                
    return session_id, account, member_id
class SFExpressAPI:
    def __init__(self, device_id=DEVICE_ID, src_device_guid=SRC_DEVICE_GUID):
        self.device_id = device_id
        self.src_device_guid = src_device_guid
        self.member_id = ""
        self.user_token = "" 
    def _generate_header_map(self, request_body_str):
        syt_token, time_interval = get_remote_syt_token(request_body_str.strip(), self.device_id, JS_BUNDLE_MD5)        
        headers = {
            "regionCode": REGION_CODE, "screenSize": SCREEN_SIZE, "mediaCode": MEDIA_CODE,
            "systemVersion": SYSTEM_VERSION, "clientVersion": CLIENT_VERSION, "model": MODEL,
            "carrier": CARRIER, "deviceId": self.device_id, "Content-Type": "application/json",
            "jsbundle": JS_BUNDLE_MD5, "srcDeviceGuid": self.src_device_guid,
            "languageCode": LANGUAGE_CODE,
            "sytToken": syt_token,
            "timeInterval": str(time_interval)
        }
        if self.member_id:
            headers["memberId"] = self.member_id
        return headers
    def login(self, mobile_number, captcha_code):
        login_payload = {
            "captcha": captcha_code, "mobile": mobile_number, "registerSource": "",
            "deviceFp": self.src_device_guid
        }
        login_payload_str = json.dumps(login_payload, separators=(',', ':'))
        request_headers = self._generate_header_map(login_payload_str)
        print(f"\n[*] 正在为手机号: {mobile_number} 尝试登录...")
        try:
            response = send_request_global('POST', LOGIN_URL, headers=request_headers, data=login_payload_str, timeout=15)
            response.raise_for_status()
            response_data = response.json()
            if response_data.get("success"):
                user_info = response_data.get("obj", {})
                self.member_id = user_info.get('memberId', '')
                self.user_token = user_info.get('token', '')
                print("\033[92m[+] 登录成功！\033[0m")
                print(f"    - 用户Member ID: {self.member_id}")
                return user_info
            else:
                print(f"\033[91m[-] 登录失败: {response_data.get('errorMessage', '未知错误')}\033[0m")
                return {"error": response_data.get('errorMessage', '登录失败')}
        except requests.exceptions.RequestException as e:
            print(f"\033[91m[-] 请求时发生错误: {e}\033[0m")
            return {"error": f"网络请求错误: {e}"}
    def get_member_center_link(self, mobile, user_id, mem_no):
        if not self.member_id or self.member_id != user_id:
            print("\033[91m[-] 错误: 请先成功登录，并确保传入正确的用户ID。\033[0m")
            return {"error": "用户未登录，无法获取链接"}
        print("\n[*] 正在获取会员中心链接...")
        link_payload = {
            "mobile": mobile, "userId": user_id, "memNo": mem_no,
            "name": "mcs-mimp-web.sf-express.com", "extra": "", "needReqTime": "1"
        }
        link_payload_str = json.dumps(link_payload, separators=(',', ':'))
        request_headers = self._generate_header_map(link_payload_str)
        try:
            response = send_request_global('POST', UNIVERSAL_SIGN_URL, headers=request_headers, data=link_payload_str, timeout=15)
            response.raise_for_status()
            response_data = response.json()
            if response_data.get("success") and response_data.get('obj', {}).get('sign'):
                sign = response_data['obj']['sign']
                encoded_sign = urllib.parse.quote(sign)
                member_center_url = f"https://mcs-mimp-web.sf-express.com/mcs-mimp/share/app/shareRedirect?sign={encoded_sign}&source=SFAPP&bizCode=619"
                print("\033[92m[+] 成功获取到会员中心链接！\033[0m")
                return {"link": member_center_url}
            else:
                print(f"\033[91m[-] 获取链接失败: {response_data.get('errorMessage', '未能获取签名')}\033[0m")
                return {"error": response_data.get('errorMessage', '获取签名失败')}
        except requests.exceptions.RequestException as e:
            print(f"\033[91m[-] 请求链接签名时发生错误: {e}\033[0m")
            return {"error": f"网络请求错误: {e}"}
CHINA_TZ = timezone(timedelta(hours=8))
_time_offset = None
_offset_expiry = 0
def get_ntp_time():
    global _time_offset, _offset_expiry
    now = time.time()
    if _time_offset is None or now > _offset_expiry:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(2)
                s.sendto(b'\x1b' + 47 * b'\0', ('ntp.aliyun.com', 123))
                data, _ = s.recvfrom(1024)
                if data:
                    t = data[40:48]
                    secs = int.from_bytes(t[:4], 'big') - 2208988800
                    frac = int.from_bytes(t[4:], 'big')
                    ntp_time = secs + frac / 2**32
                    _time_offset = ntp_time - time.time()
                    _offset_expiry = time.time() + 600
        except (socket.timeout, OSError):
            if _time_offset is None: _time_offset = 0
            _offset_expiry = time.time() + 60
    return datetime.fromtimestamp(time.time() + _time_offset)
def get_china_time():
    return get_ntp_time().astimezone(CHINA_TZ)
def sms_login_flow():
    try:
        sender.reply(f"""
=====短信登录=====
请输入您的手机号
------------------
请在60秒内完成
回复"q"退出""")
        mobile_input = sender.input(60000, 1, False)
        if not mobile_input or mobile_input.lower() == 'q':
            sender.reply("✅ 已取消登录")
            return None, None, None, None, None, None
        if not re.match(r'^1[3-9]\d{9}$', mobile_input):
            sender.reply("❌ 手机号格式不正确，请重新操作")
            return None, None, None, None, None, None
        mobile = mobile_input.strip()
        sender.reply(f"""
=====短信登录=====
❶打开『顺丰速运App』通过手机号{mobile[:3]}****{mobile[7:]}获取登录验证码
❷回复收到的6位数字验证码
------------------
请在90秒内完成
回复"q"取消""")
        sms_code_input = sender.input(90000, 0, False)
        if not sms_code_input or sms_code_input.lower() == 'q':
            sender.reply("✅ 已取消登录")
            return None, None, None, None, None, None
        sms_code = sms_code_input.strip()
        if not re.match(r'^\d{6}$', sms_code):
            sender.reply("❌ 验证码格式不正确，请重新操作")
            return None, None, None, None, None, None
        sf_api = SFExpressAPI()
        user_credentials = sf_api.login(mobile, sms_code)
        if "error" in user_credentials:
            sender.reply(f"❌ 登录失败: {user_credentials['error']}")
            return None, None, None, None, None, None
        member_id = user_credentials.get('memberId')
        mem_no = user_credentials.get('memNo')
        device_id = sf_api.device_id
        if not member_id or not mem_no:
            sender.reply("❌ 登录成功但无法获取关键信息，请稍后重试")
            return None, None, None, None, None, None
        link_data = sf_api.get_member_center_link(mobile, member_id, mem_no)
        if "error" in link_data:
            sender.reply(f"❌ 生成会话链接失败: {link_data['error']}")
            return None, None, None, None, None, None
        Token = link_data.get('link')
        account = mobile
        mobile_display = mobile[:3] + '*' * 4 + mobile[7:]
        return Token, account, mobile_display, member_id, mem_no, device_id
    except Exception as e:
        sender.reply(f"""
=====短信登录异常=====
❌ 登录过程出错
------------------
错误信息: {str(e)}
------------------
💡 请稍后重试或联系管理员
==================""")
        return None, None, None, None, None, None
def get_friend_pay_api_url():
    api_url = middleware.bucketGet('yuhua_sf', 'friend_pay_api_url')
    return api_url if api_url else "http://sf.250666.xyz"
def call_external_api(endpoint, data=None, method='POST'):
    try:
        api_base_url = get_friend_pay_api_url()
        url = f"{api_base_url}{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'SFPayClient/1.0'
        }
        if data is None:
            data = {}
        auth_key = middleware.bucketGet('yuhua_sf', 'sfdf')
        if auth_key:
            data['auth_key'] = auth_key
        if method == 'GET':
            response = send_request_global('GET', url, headers=headers, timeout=30)
        else:
            response = send_request_global('POST', url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                return True, result.get('data'), None
            else:
                return False, None, result.get('message', '请求失败')
        else:
            return False, None, f"HTTP错误: {response.status_code}"
    except requests.exceptions.Timeout:
        return False, None, "请求超时，请检查网络连接"
    except requests.exceptions.ConnectionError:
        return False, None, "无法连接到API服务器，请确保服务正在运行"
    except Exception as e:
        return False, None, f"请求异常: {str(e)}"
def upload_qr_to_image_host(image_bytes):
    try:
        url = "http://yuhualhh.250666.xyz/img/api.php"
        files = {
            'imgfile': ('qr.png', image_bytes, 'image/png')
        }
        response = requests.post(url, files=files, timeout=15)
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 'success' and result.get('data'):
                final_url = result['data']['url']
                return final_url
        return None
    except Exception as e:
        return None
def send_qr_code_smart(sender, url):
    try:
        qr_bytes = generate_qr_code_base64(url)
        if not qr_bytes:
            return False
        image_url = upload_qr_to_image_host(qr_bytes)
        if image_url:
            cq_code = f"[CQ:image,file={image_url}]"
            sender.reply(cq_code)
            return True
        else:
            qr_base64 = base64.b64encode(qr_bytes).decode('utf-8')
            cq_code = f"[CQ:image,file=base64://{qr_base64}]"
            sender.reply(cq_code)
            return True
    except Exception as e:
        return False
def generate_qr_code_base64(text):
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_bytes = buffer.getvalue()
        return img_bytes
    except Exception as e:
        return None
def get_device_id_for_pay_user(mobile):
    cached_device_id = middleware.bucketGet('yuhua_sf_deviceId', mobile)
    if cached_device_id:
        return cached_device_id
    base_device_id = "12f0d86a-5faa-3b29-a18a-8c41459a3d17"
    hashed = hashlib.md5(f"{base_device_id}_{mobile}".encode('utf-8')).hexdigest()
    return f"{hashed[:8]}-{hashed[8:12]}-{hashed[12:16]}-{hashed[16:20]}-{hashed[20:32]}"
def build_sfpay_headers(payload_str, device_id, member_id=None):
    syt_token, time_interval = get_remote_syt_token(payload_str, device_id, JS_BUNDLE_MD5)
    headers = {
        "jsbundle": JS_BUNDLE_MD5,
        "clientVersion": CLIENT_VERSION,
        "languageCode": LANGUAGE_CODE,
        "systemVersion": SYSTEM_VERSION,
        "deviceId": device_id,
        "regionCode": REGION_CODE,
        "carrier": CARRIER,
        "screenSize": SCREEN_SIZE,
        "model": MODEL,
        "mediaCode": MEDIA_CODE,
        "sytToken": syt_token,
        "timeInterval": str(time_interval),
        "Content-Type": "application/json",
        "User-Agent": "okhttp/4.9.1",
        "srcDeviceGuid": SRC_DEVICE_GUID,
    }
    if member_id:
        headers["memberId"] = member_id
    return headers
def post_sfpay_json(url, payload, device_id, member_id=None):
    payload_str = json.dumps(payload, separators=(',', ':'))
    headers = build_sfpay_headers(payload_str, device_id, member_id=member_id)
    response = send_request_global('POST', url, headers=headers, data=payload_str, timeout=15)
    response.raise_for_status()
    data = response.json()
    success = data.get("success")
    success_flag = success is True or str(success).lower() == "true"
    if not success_flag:
        message = data.get("errorMessage") or data.get("returnMsg") or "请求失败"
        error_code = str(data.get("errorCode") or "").strip()
        if error_code == "001" and "登录信息已失效" in message:
            raise RuntimeError("APP侧登录态已失效，可能用户登录顺丰APP被挤下线")
        raise RuntimeError(message)
    return data
def mask_sf_name(text):
    if not text:
        return "-"
    text = str(text)
    if len(text) == 1:
        return text
    return text[0] + "*" * (len(text) - 1)
def query_unpaid_orders_for_account(account, member_id):
    device_id = get_device_id_for_pay_user(account)
    data = post_sfpay_json(
        "https://ccsp-egmas.sf-express.com/cx-app-query/query/app/sfpay/queryUnPayOrderList",
        {
            "pageSize": "20",
            "page": "1",
            "memberId": member_id
        },
        device_id,
        member_id=member_id
    )
    obj = data.get("obj") or {}
    return obj.get("unpaidOrderDetail") or []
def select_unpaid_order_for_pay(orders, account):
    if not orders:
        sender.reply(f"""
=====待支付订单=====
🤪 账号: {account[:3]}****{account[7:]}
❌ 结果: 当前账号没有待支付订单
==================""")
        return None
    order_list_msg = f"""
=====待支付订单=====
🤪 账号: {account[:3]}****{account[7:]}"""
    count = 1
    for order in orders:
        waybill_no = order.get('waybillNo', '-')
        amt = format_sf_amount_fen(order.get('amt', '-'))
        origin_city = order.get('originCity', '-')
        dest_city = order.get('destCity', '-')
        consignor = mask_sf_name(order.get('consignorContName'))
        addressee = mask_sf_name(order.get('addresseeContName'))
        order_list_msg += f"""
------------------
[{count}] 订单信息
📦 运单: {waybill_no}
💰 金额: {amt}元
🚚 路线: {origin_city} -> {dest_city}
👤 寄件: {consignor}
📮 收件: {addressee}"""
        count += 1
    order_list_msg += """
------------------
回复数字选择
回复"q"退出
=================="""
    sender.reply(order_list_msg)
    inputmessage = sender.input(120000, 0, False)
    try:
        order_index = int(inputmessage)
        if order_index <= 0 or order_index >= count:
            sender.reply('❌ 输入的序号无效')
            return None
        return orders[order_index - 1]
    except (ValueError, TypeError):
        if inputmessage and inputmessage.lower() == 'q':
            sender.reply('✅ 已退出操作')
        elif inputmessage is None:
            sender.reply('⏰ 操作超时，已退出')
        else:
            sender.reply('❌ 输入必须是数字')
        return None
def execute_friend_pay(selected_order, mobile, member_id):
    try:
        device_id = get_device_id_for_pay_user(mobile)
        merge_payload = {
            "serviceVersion": "V2.0.0",
            "amtPre": selected_order["amt"],
            "amt": selected_order["amt"],
            "waybillInfo": [
                {
                    "waybillType": selected_order["waybillType"],
                    "operatorNo": selected_order["operatorNo"],
                    "amt": selected_order["amt"],
                    "orgId": selected_order["orgId"],
                    "deptCode": selected_order["deptCode"],
                    "waybillNo": selected_order["waybillNo"],
                }
            ],
            "serviceName": "HHT-PAY-BILL",
            "memberId": member_id,
        }
        merge_data = post_sfpay_json(
            "https://ccsp-egmas.sf-express.com/cx-app-query/query/app/sfpay/applyMergePay",
            merge_payload,
            device_id,
            member_id=member_id
        )
        merge_obj = merge_data.get("obj") or {}
        order_id = merge_obj.get("id")
        if not order_id:
            raise RuntimeError("applyMergePay 成功但没有返回 id")
        pay_payload = {
            "isDiscount": "N",
            "memberId": member_id,
            "mobile": mobile,
            "id": order_id,
            "additionInfo": [],
            "serviceName": "HHT-PAY-BILL",
            "serviceVersion": "V2.0.0",
            "appVersion": 1097630,
        }
        pay_data = post_sfpay_json(
            "https://ccsp-egmas.sf-express.com/cx-app-query/query/app/sfpay/applyPay",
            pay_payload,
            device_id,
            member_id=member_id
        )
        pay_obj = pay_data.get("obj") or {}
        pay_h5_url = pay_obj.get("payH5Url")
        if not pay_h5_url:
            raise RuntimeError("applyPay 成功但没有返回 payH5Url")
        mobile_display = mobile[:3] + "****" + mobile[7:]
        display_amt = format_sf_amount_fen(selected_order.get('amt', '-'))
        masked_order_id = mask_pay_order_id(order_id)
        response_info = f"""
=====代付页面生成=====
💰 账户: {mobile_display}
✨ 运单: {selected_order.get('waybillNo', '-')}
💵 金额: {display_amt}元
🧾 支付: {masked_order_id}
------------------
🔍 主要响应:
• 状态: True
• 信息: 成功
------------------
✅ 生成代付页面成功
💡 已返回带有登录账户的账单支付页面，请使用顺丰app扫码(无需登录)选择你的优惠券/积分抵扣，完成支付
=================="""
        return response_info, pay_h5_url
    except Exception as e:
        if "APP侧登录态已失效" in str(e):
            exception_msg = f"""
=====操作被拒绝=====
❌ 当前账号APP侧登录状态已失效
💡 可能用户登录顺丰APP被挤下线
🔗 请发送“顺丰登录”重新登录后再试
=================="""
            return exception_msg, None
        exception_msg = f"""
=====代付页面生成异常=====
🤪 账户: {mobile[:3]}****{mobile[7:]}
✨ 运单: {selected_order.get('waybillNo', '-')}
------------------
🔍 异常信息:
• 错误类型: {type(e).__name__}
• 错误详情: {str(e)}
=================="""
        return exception_msg, None
def get_member_id_from_session(session_id):
    try:
        url = "https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~receiveExchangeIndexService~indexData"
        headers = {"Cookie": f"sessionId={session_id}"}
        response = requests.post(url, headers=headers, json={}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('success') and isinstance(data.get('obj'), dict):
            if data['obj'].get('memberId'):
                return str(data['obj']['memberId'])
            if data['obj'].get('userId'):
                return str(data['obj']['userId'])
        return None
    except Exception:
        return None
def get_member_id_for_account(account):
    try:
        member_id = middleware.bucketGet('yuhua_sf_memberid', account)
        if member_id:
            return member_id
        token = middleware.bucketGet('yuhua_sf_token', account)
        if not token:
            return None
        if token.startswith('http'):
            session_id, _, member_id_from_token = get_valid_session_or_renew(account)
            if session_id:
                if member_id_from_token:
                    middleware.bucketSet('yuhua_sf_memberid', account, member_id_from_token)
                    return member_id_from_token
                member_id_from_api = get_member_id_from_session(session_id)
                if member_id_from_api:
                    middleware.bucketSet('yuhua_sf_memberid', account, member_id_from_api)
                    return member_id_from_api
        user_info_url = "https://ccsp-egmas.sf-express.com/cx-app-member/member/app/user/info"
        user_info_payload = json.dumps({
            "mobile": account,
            "serviceName": "APP-USER-INFO",
            "serviceVersion": "V1.0.0"
        })
        device_id = str(uuid.uuid4())
        syt_token, time_interval = sytTokens(user_info_payload, device_id)
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'okhttp/4.9.1',
            'Host': 'ccsp-egmas.sf-express.com',
            'sytToken': syt_token,
            'timeInterval': str(time_interval),
            'deviceId': device_id
        }
        response = requests.post(user_info_url, data=user_info_payload, headers=headers, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('success') and result.get('obj') and result['obj'].get('memInfos'):
                mem_info = result['obj']['memInfos'][0]
                member_id = mem_info.get('userId')
                if member_id:
                    middleware.bucketSet('yuhua_sf_memberid', account, str(member_id))
                    return str(member_id)        
        return None
    except Exception:
        return None
def select_account_for_pay(accounts):
    if len(accounts) == 1:
        accountVip = middleware.bucketGet(bucket='yuhua_sf_auth', key=accounts[0])
        if len(accountVip) == 0:
            sender.reply("""
=====暂无授权=====
❌ 该账号未查到授权
💡 请先进行账号授权
==================""")
            return None
        elif accountVip <= today_time:
            sender.reply(f"""
=====授权过期=====
❌ 该账号授权已过期
💡 请续费授权后使用
==================""")
            return None
        return accounts[0]
    account_list = """
======选择代付账户====="""
    count = 1
    for account_in_loop in accounts:
        accountVip_in_loop = middleware.bucketGet(bucket='yuhua_sf_auth', key=f'{account_in_loop}')
        vip_status_display = ''
        if len(accountVip_in_loop) == 0:
            vip_status_display = '⚠️ 未授权'
        elif accountVip_in_loop < str(datetime.now().date()):
            vip_status_display = '❌ 已过期'
        else:
            vip_status_display = f'✅ {accountVip_in_loop}'
        login_mobile_display = account_in_loop[:3] + "****" + account_in_loop[7:]
        account_list += f"""
[{count}] 账号信息
🤪 账号: {login_mobile_display}
☁ 授权: {vip_status_display}
------------------"""
        count += 1
    account_list += """
回复数字选择
回复"q"退出
=================="""
    sender.reply(account_list)
    inputmessage = sender.input(120000, 0, False)
    try:
        me_as_int = int(inputmessage)
        if me_as_int <= 0 or me_as_int >= count:
            sender.reply('❌ 输入的序号无效')
            return None
        selected_account = accounts[me_as_int - 1]
        accountVip = middleware.bucketGet(bucket='yuhua_sf_auth', key=selected_account)
        if len(accountVip) == 0:
            sender.reply("""
=====暂无授权=====
❌ 该账号未查到授权
💡 请先进行账号授权
==================""")
            return None
        elif accountVip <= today_time:
            sender.reply(f"""
=====授权过期=====
❌ 该账号授权已过期
💡 请续费授权后使用
==================""")
            return None
        return selected_account
    except (ValueError, TypeError):
        if inputmessage and inputmessage.lower() == 'q':
            sender.reply('✅ 已退出操作')
        elif inputmessage is None:
            sender.reply('⏰ 操作超时，已退出')
        else:
            sender.reply('❌ 输入必须是数字')
        return None
def get_qr_code():
    api_url = "https://yuhualhh.250666.xyz/api/wxcode.php"
    data = {
        "project": "sf",
        "action": "create_qr"
    }
    try:
        res = send_request_global('POST', api_url, json=data, timeout=15)
        res.raise_for_status()
        result = res.json()
        if result.get('success') and isinstance(result.get('data'), dict):
            qr_url = result['data'].get('qr_img_url')
            uuid_val = result['data'].get('uuid')
            if qr_url and uuid_val:
                return uuid_val, qr_url
    except Exception as e:
        pass
    return None, None
def poll_scan_status(uuid_val):
    api_url = "https://yuhualhh.250666.xyz/api/wxcode.php"
    for _ in range(24):
        try:
            data = {
                "project": "sf",
                "action": "poll_scan_status",
                "uuid": uuid_val
            }
            r = send_request_global('POST', api_url, json=data, timeout=15)
            r.raise_for_status()
            result = r.json()
            if result.get('success') and isinstance(result.get('data'), dict):
                code = result['data'].get('code')
                if code:
                    return code
        except requests.exceptions.RequestException as e:
            break
        except Exception as e:
            break        
        time.sleep(5)
    return None
def sf_login(sender):
    try:
        scan_msg = """
=====微信扫码登录=====
⌛ 正在加载二维码...
⏳ 请稍候...
=================="""
        sender.reply(scan_msg)
        QRcode, QRcodeImg = get_qr_code()
        if not QRcode or not QRcodeImg:
            sender.reply('❌ 获取二维码失败！')
            exit(0)
        sender.replyImage(QRcodeImg)
        scan_guide = """
=====登录说明=====
🤪 请使用微信扫描二维码登录
------------------
⚠️ 注意事项:
1. 请确保已用微信登录过顺丰APP
2. 如果登录失败，请先下载顺丰APP
3. 使用微信登录APP后再次尝试
4. 请在2分钟内完成，回复“q”取消操作
=================="""
        sender.reply(scan_guide)
        start_time = time.time()
        TOTAL_POLL_TIMEOUT_SECONDS = 120
        code = None
        user_quit = False
        def listen_for_quit():
            nonlocal user_quit
            while not user_quit:
                user_input = sender.input(1000, 0, False)
                if user_input and user_input.strip().lower() == 'q':
                    user_quit = True
                    sender.reply("✅ 已取消登录")
                    break
        listener_thread = threading.Thread(target=listen_for_quit)
        listener_thread.start()
        while time.time() - start_time < TOTAL_POLL_TIMEOUT_SECONDS and not user_quit:
            code = poll_scan_status(QRcode)            
            if code:
                break
            time.sleep(1)
        was_quit_by_user = user_quit
        user_quit = True 
        listener_thread.join()        
        if not code:
            if was_quit_by_user:
                exit(0)
            else:
                sender.reply('⏰ 操作超时，已退出')
                exit(0)
        deviceId = str(uuid.uuid4())
        url = "https://ccsp-egmas.sf-express.com/cx-app-member/member/app/weixin/getAccessTokenByCode"
        payload = json.dumps({"code": code})
        sytToken, t = sytTokens(payload, deviceId)
        headers = {
            'User-Agent': "okhttp/4.9.1",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Content-Type': "application/json",
            'jsbundle': "705088894ad6ef475bdf4875c9d533b8",
            'clientVersion': "9.76.0",
            'languageCode': "sc",
            'systemVersion': "13",
            'deviceId': deviceId,
            'regionCode': "CN",
            'carrier': "unknown",
            'screenSize': "1080x2400",
            'sytToken': sytToken,
            'timeInterval': f"{t}",
            'model': "MEIZU 20",
            'mediaCode': "AndroidML"
        }
        response = requests.post(url, data=payload, headers=headers)
        response_json = response.json() 
        if not response_json.get('success') or not response_json.get('obj') or not response_json['obj'].get('memInfos'):
            error_msg = response_json.get('message', '未知错误')
            sender.reply(f'❌ 获取AccessToken失败: {error_msg}') 
            exit(0)
        mem_info = response_json['obj']['memInfos'][0]
        account_id_from_sf = mem_info.get('userId')
        memNo = mem_info.get('memNo')
        mobile_from_sf = mem_info.get('mobile')
        member_id = account_id_from_sf
        if not all([account_id_from_sf, memNo, mobile_from_sf, member_id]):
            sender.reply('❌ 获取用户信息不完整，请稍后重试！')
            exit(0)
        url = "https://ccsp-egmas.sf-express.com/cx-app-member/member/app/user/universalSign"
        payload = json.dumps({
            "mobile": mobile_from_sf,
            "userId": account_id_from_sf,
            "memNo": memNo,
            "name": "mcs-mimp-web.sf-express.com",
            "extra": "",
            "needReqTime": "1"
        })
        sytToken, t = sytTokens(payload, deviceId)
        headers['sytToken'] = sytToken
        headers['timeInterval'] = str(t)
        response = requests.post(url, data=payload, headers=headers)
        response_json_sign = response.json() 
        if not response_json_sign.get('success') or not response_json_sign.get('obj') or not response_json_sign['obj'].get('sign'):
            error_msg_sign = response_json_sign.get('message', '未知错误')
            sender.reply(f'❌ UniversalSign失败: {error_msg_sign}') 
            exit(0)
        sign = response_json_sign['obj']['sign']
        encoded_string = urllib.parse.quote(sign)
        Token = f'https://mcs-mimp-web.sf-express.com/mcs-mimp/share/app/shareRedirect?sign={encoded_string}&source=SFAPP&bizCode=619'
        account = mobile_from_sf
        mobile_display = mobile_from_sf[:3] + '*' * 4 + mobile_from_sf[7:]
        return Token, str(account), mobile_display, member_id, memNo, deviceId
    except requests.exceptions.RequestException as e: 
        sender.reply(f'❌ 登录过程中网络请求失败: {str(e)}')
        exit(0)
    except json.JSONDecodeError as e: 
        sender.reply(f'❌ 登录过程中解析响应数据失败: {str(e)}')
        exit(0)
    except KeyError as e: 
        sender.reply(f'❌ 登录过程中获取关键信息失败，字段: {str(e)}')
        exit(0)
    except Exception as e:
        sender.reply(f'❌ 登录失败，报错：{str(e)}') 
        exit(0)    
def bindaccount():
    welcome_msg = """
=====顺丰登录=====
[1] 微信扫码登录
[2] 短信验证登录
------------------
回复数字选择方式
回复"q"退出操作
=================="""
    sender.reply(welcome_msg)
    input_choice = sender.input(120000, 0, False)   
    memNo = None
    deviceId = None    
    if input_choice == '1':
        Token, account, mobile, member_id, memNo, deviceId = sf_login(sender)
    elif input_choice == '2':
        Token, account, mobile, member_id, memNo, deviceId = sms_login_flow()
        if not Token:
            return
    elif input_choice == '666':
        ck_guide = """
=====手动链接登录=====
请输入顺丰小程序抓包的完整URL
示例:https://mcs-mimp-web.sf-express.com/mcs-mimp/share/weChat/
✨ 抓包教程:
------------------
1. 打开抓包工具
2. 进入顺丰小程序
3. 找到上述域名开头的URL
4. 复制完整URL地址粘贴发送即可
=================="""
        sender.reply(ck_guide)
        while True:
            ck_input = sender.input(120000, 1, False)
            if not ck_input:
                sender.reply("⏰ 操作超时，已退出")
                exit(0)
            elif ck_input.lower() == 'q':
                sender.reply("✅ 已取消登录")
                exit(0)
            if not ck_input.startswith(('http://', 'https://')):
                sender.reply("""
=====URL格式错误=====
❌ URL必须以http://或https://开头
请重新输入或回复"q"退出
==================""")
                continue
            session_id, login_mobile, member_id = session_ids(ck_input)
            if not session_id or not login_mobile:
                sender.reply("""
=====验证失败提示=====
❌ URL验证失败或已过期
------------------
请检查URL是否正确
重新输入或回复"q"退出
==================""")
                continue
            Token = ck_input
            account = login_mobile
            mobile = login_mobile[:3] + '*' * 4 + login_mobile[7:]
            if member_id:
                pass
            else:
                middleware.bucketSet(bucket='yuhua_sf_token', key=account, value=Token)
            break
    elif input_choice and input_choice.lower() == 'q':
        sender.reply("✅ 已取消登录")
        return
    else:
        sender.reply('❌ 输入错误，请重新选择登录方式')
        return
        
    def accvip(account, Token, mobile, member_id=None, memNo=None, deviceId=None):
        accountVip = middleware.bucketGet(bucket='yuhua_sf_auth', key=account)
        auth_status = '✅ 已授权' if accountVip and accountVip >= today_time else '⚠️ 未授权'
        next_step = f'发送 {randommanagecommand} 可管理账号' if accountVip and accountVip >= today_time else f'发送 {randommanagecommand} 可进行授权'
        success_msg = f"""
=====顺丰账号绑定=====
🤪 绑定账号: {mobile}
☁ 授权状态: {auth_status}
⏰ 下一步操作: 
   {next_step}
=================="""
        accounts = []
        if uservalue:
            try:
                accounts = list(eval(uservalue))
            except:
                accounts = []
        if account not in accounts:
            accounts.append(account)
        accounts = list(dict.fromkeys(accounts))
        if accounts:
            middleware.bucketSet(bucket='yuhua_sf_user', key=userid, value=str(accounts))
        middleware.bucketSet(bucket='yuhua_sf_token', key=account, value=Token)
        if member_id:
            middleware.bucketSet(bucket='yuhua_sf_memberid', key=account, value=member_id)
        if memNo:
            middleware.bucketSet(bucket='yuhua_sf_memNo', key=account, value=memNo)
        if deviceId:
            middleware.bucketSet(bucket='yuhua_sf_deviceId', key=account, value=deviceId)            
        if middleware.bucketGet('yuhua_sf_sessionId', account):
            try:
                middleware.bucketDel('yuhua_sf_sessionId', account)
            except Exception:
                pass
        ql_sync_value = get_ql_cookie_format(account, Token)                
        if accountVip and accountVip >= today_time:
            try:
                Addenvs(osname=yuhua_sf_osname, value=ql_sync_value, account=account, phone=mobile, owner_id=userid)
            except Exception as e:
                sender.reply(f"""
=====青龙更新失败=====
❌ 更新青龙变量失败
⚠️ 错误: {str(e)}
==================""")
        sender.reply(success_msg)    
    accvip(account, Token, mobile, member_id, memNo, deviceId)
def empower(empowertime, me_as_int):
    day = me_as_int * 30
    if len(empowertime) == 0 or empowertime <= str(today_time):
        delayed_date = today_date + timedelta(days=day)
    elif empowertime > today_time:
        empower_date = datetime.strptime(empowertime, "%Y-%m-%d")
        delayed_date = empower_date + timedelta(days=day)
        delayed_date = delayed_date.date()
    else:
        sender.reply('出错！')
        exit(0)
    return str(delayed_date)
def sf_auth():
    if not sender.isAdmin():
        sender.reply("❌ 您没有权限执行此操作！")
        exit(0)
        
    auth_menu = """
=====顺丰授权管理=====
[1] 授权所有用户
[2] 授权指定用户
------------------
回复数字选择功能
回复"q"退出
=================="""
    sender.reply(auth_menu)
    xz = sender.listen(60000) 
    
    if xz is None: 
        sender.reply("⏰ 操作超时，已退出")
        return
    if xz.lower() == 'q':
        sender.reply("✅ 已退出授权管理")
        return
    auth_days_prompt = """
=====设置授权天数=====
请输入要授权的天数
------------------
回复数字设置天数
回复"q"退出操作
=================="""     
    if xz == '1':
        users = middleware.bucketAllKeys('yuhua_sf_user')
        if not users:
            sender.reply("❌ 未找到任何绑定的顺丰账号")
            return            
        sender.reply(auth_days_prompt)        
        sjts_str = sender.listen(60000) 
        if sjts_str is None:
            sender.reply("⏰ 操作超时，已退出")
            return
        if sjts_str.lower() == 'q':
            sender.reply("✅ 已取消授权")
            return        
        try:
            sjts = int(sjts_str) 
        except ValueError:
            sender.reply("❌ 天数必须是数字！")
            return            
        success_count = 0
        fail_count = 0        
        all_unique_sf_accounts_data = {}        
        for user in users:
            accountlist = middleware.bucketGet('yuhua_sf_user', user) 
            if not accountlist or accountlist == '{}': 
                continue            
            try:
                raw_user_accounts = eval(accountlist)
                user_accounts_str_list = []
                if isinstance(raw_user_accounts, list):
                    user_accounts_str_list = [str(acc_id) for acc_id in raw_user_accounts]
                elif isinstance(raw_user_accounts, (str, int, float)):
                    user_accounts_str_list = [str(raw_user_accounts)]
                for account_id in user_accounts_str_list:
                    if account_id not in all_unique_sf_accounts_data:
                        token_val = middleware.bucketGet('yuhua_sf_token', account_id)
                        if token_val:
                            all_unique_sf_accounts_data[account_id] = {'token': token_val, 'owner_id': user}
            except: 
                fail_count += 1
                continue
        if not all_unique_sf_accounts_data:
            sender.reply("❌ 未找到任何有效的顺丰账号进行授权")
            return
        for account, data in all_unique_sf_accounts_data.items():
            try:
                token = data['token']
                owner_id = data['owner_id']                
                dqsj = datetime.now().strftime("%Y-%m-%d") 
                accountVip = middleware.bucketGet('yuhua_sf_auth', account) 
                if accountVip and accountVip > dqsj: 
                    sqsj = datetime.strptime(accountVip, "%Y-%m-%d") 
                    new_sqsj_obj = sqsj + timedelta(days=sjts) 
                else:
                    new_sqsj_obj = datetime.now() + timedelta(days=sjts) 
                new_sqsj = new_sqsj_obj.strftime("%Y-%m-%d")                 
                middleware.bucketSet('yuhua_sf_auth', account, new_sqsj)                
                phone = account[:3] + '*' * 4 + account[7:]
                ql_sync_value = get_ql_cookie_format(account, token)
                Addenvs(osname=yuhua_sf_osname, value=ql_sync_value, account=account, phone=phone, owner_id=owner_id) 
                success_count += 1
            except: 
                fail_count += 1        
        result_msg = f"""
=====授权操作完成=====
✅ 成功: {success_count} 个账号
❌ 失败: {fail_count} 个账号
⏰ 授权: {sjts} 天
==================""" 
        sender.reply(result_msg)            
    elif xz == '2':
        user_guide = """
======账号授权======
请输入需要授权的用户ID
(发送myuid可获取ID)
------------------
回复"q"退出操作
==================""" 
        sender.reply(user_guide)        
        myuid = sender.listen(60000)
        if myuid is None:
            sender.reply("⏰ 操作超时，已退出")
            return
        if myuid.lower() == 'q':
            sender.reply("✅ 已退出授权")
            return            
        accountlist = middleware.bucketGet('yuhua_sf_user', myuid) 
        if not accountlist or accountlist == '{}': 
            sender.reply(f"❌ 未找到用户 {myuid} 的顺丰账号信息！") 
            return            
        try:
            accounts = eval(accountlist)
            if not isinstance(accounts, list):
                accounts = [str(accounts)]
        except:
            sender.reply(f"❌ 解析用户 {myuid} 的账号列表失败！")
            return        
        msg = """
=====账号列表=====
[0] 授权全部账号"""        
        n = 0
        for account_disp in accounts: 
            n += 1
            accountVip_disp = middleware.bucketGet('yuhua_sf_auth', account_disp)
            vip_status = ''
            if not accountVip_disp:
                vip_status = '⚠️ 未授权'
            elif accountVip_disp < today_time:
                vip_status = '❌ 已过期'
            else:
                vip_status = f'✅ {accountVip_disp}'            
            masked_account = account_disp[:3] + '****' + account_disp[7:]
            msg += f"""
------------------
[{n}] 账号信息
🤪 账号: {masked_account}
☁ 授权: {vip_status}"""           
        msg += """
------------------
回复数字选择
回复'q'退出
=================="""
        sender.reply(msg)        
        xz_choice = sender.listen(60000)
        if xz_choice is None: 
            sender.reply("⏰ 操作超时，已退出")
            return
        if xz_choice.lower() == 'q':
            sender.reply("✅ 已退出授权")
            return        
        try:
            xz_int = int(xz_choice)
            if not (0 <= xz_int <= len(accounts)):
                sender.reply("❌ 输入的序号无效！")
                return
        except ValueError:
            sender.reply("❌ 输入的序号无效！")
            return
        sender.reply(auth_days_prompt) 
        sjts_str = sender.listen(60000) 
        if sjts_str is None:
            sender.reply("⏰ 操作超时，已退出")
            return
        if sjts_str.lower() == 'q':
            sender.reply("✅ 已取消授权")
            return            
        try:
            sjts = int(sjts_str)
        except ValueError: 
            sender.reply('❌ 输入的天数无效！') 
            return
        accounts_to_process = []
        if xz_int == 0:
            accounts_to_process = accounts
        else:
            accounts_to_process.append(accounts[xz_int - 1])
        success_count = 0
        fail_count = 0
        for account in accounts_to_process:
            try:
                dqsj = datetime.now().strftime("%Y-%m-%d") 
                accountVip = middleware.bucketGet('yuhua_sf_auth', account) 
                token = middleware.bucketGet('yuhua_sf_token', account) 
                
                if not token:
                    fail_count += 1 
                    continue                    
                if accountVip and accountVip > dqsj: 
                    sqsj = datetime.strptime(accountVip, "%Y-%m-%d") 
                    new_sqsj_obj = sqsj + timedelta(days=sjts) 
                else:
                    new_sqsj_obj = datetime.now() + timedelta(days=sjts) 
                new_sqsj = new_sqsj_obj.strftime("%Y-%m-%d")                 
                middleware.bucketSet('yuhua_sf_auth', account, new_sqsj)                
                phone = account[:3] + '*' * 4 + account[7:] 
                ql_sync_value = get_ql_cookie_format(account, token)
                Addenvs(osname=yuhua_sf_osname, value=ql_sync_value, account=account, phone=phone, owner_id=myuid)
                success_count += 1
            except Exception: 
                fail_count += 1 
        if xz_int == 0:
             result_msg_user_all = f"""
=====授权操作完成=====
👤 用户ID: {myuid}
✅ 成功: {success_count} 个账号
❌ 失败: {fail_count} 个账号
⏰ 授权: {sjts} 天
=================="""
             sender.reply(result_msg_user_all)
        else:
             account_single = accounts[xz_int - 1]
             new_expiry_date = middleware.bucketGet('yuhua_sf_auth', account_single)
             masked_account_single = account_single[:3] + '****' + account_single[7:]
             msg_reply = f"""
=====授权成功=====
🤪 账号: {masked_account_single}
⏰ 授权天数: {sjts}天
📅 到期时间: {new_expiry_date}
==================""" 
             sender.reply(msg_reply)
    else: 
        sender.reply("❌ 无效的选择") 
        return        
def meituanmanage():
    if len(uservalue) != 0:
        count = 0
        account_list = """
======我的顺丰账号=====
[0] 授权全部账号"""
        try:
            accounts = eval(uservalue)
            if isinstance(accounts, (list, tuple, set)):
                accounts = list(dict.fromkeys(accounts))
            else:
                accounts = [str(accounts)]
            middleware.bucketSet(bucket='yuhua_sf_user', key=userid, value=str(accounts))
            for account_in_loop in accounts:
                count += 1
                accountVip_in_loop = middleware.bucketGet(bucket='yuhua_sf_auth', key=f'{account_in_loop}')
                vip_status_display = ''
                if not accountVip_in_loop:
                    vip_status_display = '⚠️ 未授权'
                elif accountVip_in_loop < today_time:
                    vip_status_display = '❌ 已过期'
                else:
                    vip_status_display = f'✅ {accountVip_in_loop}'
                login_mobile_display = account_in_loop[:3] + "****" + account_in_loop[7:]
                account_list += f"""
------------------
[{count}] 账号信息
🤪 账号: {login_mobile_display}
☁ 授权: {vip_status_display}"""
            account_list += """
------------------
回复数字选择
回复'q'退出
=================="""
            sender.reply(account_list)
            inputmessage = sender.input(120000, 0, False)
            try:
                me_as_int = int(inputmessage)
                if me_as_int < 0 or me_as_int > count:
                    sender.reply('❌ 输入的序号无效')
                    return
            except (ValueError, TypeError):
                if inputmessage and inputmessage.lower() == 'q':
                    sender.reply('✅ 已退出管理')
                elif inputmessage is None:
                    sender.reply('⏰ 操作超时，已退出')
                else:
                    sender.reply('❌ 输入必须是数字')
                return
            if me_as_int == 0:
                auth_prompt = ""
                if Decimal(sfVipmoney) == Decimal('0'):
                    auth_prompt = """
=====一键授权=====
请输入授权月数
------------------
回复数字设置月数
回复"q"退出
=================="""
                else:
                    auth_prompt = f"""
=====一键授权=====
授权价格: {sfVipmoney}元/月
请输入授权月数
------------------
回复数字设置月数
回复"q"退出
=================="""
                sender.reply(auth_prompt)
                mes_auth_months_str = sender.input(120000, 0, False)
                if not mes_auth_months_str or mes_auth_months_str.lower() == 'q':
                    sender.reply("✅ 已取消操作")
                    return
                try:
                    mes_auth_months_int = int(mes_auth_months_str)
                    if mes_auth_months_int <= 0:
                         sender.reply('❌ 月数必须是正整数')
                         return
                except (ValueError, TypeError):
                    sender.reply('❌ 月数必须是数字')
                    return
                total_accounts = len(accounts)
                success_count = 0
                fail_count = 0
                if Decimal(sfVipmoney) == Decimal('0'):
                    for acc in accounts:
                        try:
                            acc_vip = middleware.bucketGet(bucket='yuhua_sf_auth', key=f'{acc}')
                            acc_url = middleware.bucketGet(bucket='yuhua_sf_token', key=f'{acc}')
                            if not acc_url:
                                acc_url = "Token已丢失" 
                            
                            new_expiry_date = empower(empowertime=acc_vip, me_as_int=mes_auth_months_int)
                            middleware.bucketSet(bucket='yuhua_sf_auth', key=f'{acc}', value=new_expiry_date)
                            try:
                                ql_sync_value = get_ql_cookie_format(acc, acc_url)
                                Addenvs(osname=yuhua_sf_osname, value=ql_sync_value, account=acc, phone=acc, owner_id=userid)
                            except:
                                pass
                            success_count += 1
                        except:
                            fail_count += 1
                else:
                    total_price_multiplier = mes_auth_months_int * total_accounts
                    zf_success = zf(project=f'顺丰批量授权({total_accounts}个)', me_as_int=total_price_multiplier, accountVip='', token='', phone='', account='', owner_id=userid)
                    if zf_success:
                        for acc in accounts:
                            try:
                                acc_vip = middleware.bucketGet(bucket='yuhua_sf_auth', key=f'{acc}')
                                acc_url = middleware.bucketGet(bucket='yuhua_sf_token', key=f'{acc}')
                                if not acc_url: acc_url = "Token已丢失"
                                new_expiry_date = empower(empowertime=acc_vip, me_as_int=mes_auth_months_int)
                                middleware.bucketSet(bucket='yuhua_sf_auth', key=f'{acc}', value=new_expiry_date)
                                try:
                                    ql_sync_value = get_ql_cookie_format(acc, acc_url)
                                    Addenvs(osname=yuhua_sf_osname, value=ql_sync_value, account=acc, phone=acc, owner_id=userid)
                                except:
                                    pass
                                success_count += 1
                            except Exception:
                                fail_count += 1
                    else:
                        return
                summary_msg = f"""
=====授权完成=====
✅ 成功: {success_count}个账号
❌ 失败: {fail_count}个账号
⏰ 时长: {mes_auth_months_int}月
=================="""
                sender.reply(summary_msg)
                return
            account = accounts[me_as_int - 1]
            accountVip = middleware.bucketGet(bucket='yuhua_sf_auth', key=f'{account}')
            userurl = middleware.bucketGet(bucket='yuhua_sf_token', key=f'{account}')
            login_mobile_for_display = account[:3] + "****" + account[7:]
            vip_status_for_display = ''
            if len(accountVip) == 0:
                vip_status_for_display = '⚠️ 未授权'
            elif accountVip < today_time:
                vip_status_for_display = '❌ 已过期'
            else:
                vip_status_for_display = f'✅ {accountVip}'            
            account_info_display = f"""
=====账号详情=====
🤪 账号: {login_mobile_for_display}
☁ 授权: {vip_status_for_display}
=================="""
            sender.reply(account_info_display)
            menu_for_action = """
=====账号管理=====
[1] 授权账号
[2] 顺丰代付
[3] 删除账号
------------------
回复数字选择功能
回复"q"退出操作
=================="""
            sender.reply(menu_for_action)
            inputmessage_action_choice = sender.input(120000, 0, False)
            try:
                action_choice_validated_int = int(inputmessage_action_choice)
                if action_choice_validated_int not in [1, 2, 3]:
                    sender.reply('❌ 无效的选择')
                    return
            except (ValueError, TypeError):
                if inputmessage_action_choice and inputmessage_action_choice.lower() == 'q':
                    sender.reply('✅ 已取消操作')
                elif inputmessage_action_choice is None:
                    sender.reply('⏰ 操作超时，已退出')
                else:
                    sender.reply('❌ 无效的选择')
                return          
            if action_choice_validated_int == 1: 
                auth_guide_months = ""
                if Decimal(sfVipmoney) == Decimal('0'):
                    auth_guide_months = """
=====设置授权时长=====
请输入授权月数
------------------
回复数字设置月数
回复"q"退出操作
=================="""
                else:
                    auth_guide_months = f"""
=====设置授权时长=====
授权价格: {sfVipmoney}元/月
请输入授权月数
------------------
回复数字设置月数
回复"q"退出操作
=================="""
                sender.reply(auth_guide_months)
                mes_auth_months_str = sender.input(120000, 0, False)
                if not mes_auth_months_str or mes_auth_months_str.lower() == 'q':
                    sender.reply("✅ 已取消操作")
                    return
                try:
                    mes_auth_months_int = int(mes_auth_months_str)
                    if mes_auth_months_int <= 0:
                         sender.reply('❌ 月数必须是正整数')
                         return
                except (ValueError, TypeError):
                    sender.reply('❌ 月数必须是数字')
                    return
                if Decimal(sfVipmoney) == Decimal('0'):
                    new_expiry_date = empower(empowertime=accountVip, me_as_int=mes_auth_months_int)
                    middleware.bucketSet(bucket='yuhua_sf_auth', key=f'{account}', value=new_expiry_date)
                    
                    try:
                        ql_sync_value = get_ql_cookie_format(account, userurl)
                        Addenvs(osname=yuhua_sf_osname, value=ql_sync_value, account=account, phone=account, owner_id=userid) 
                    except:
                        pass
                    sender.reply(f"""
=====授权成功=====
🎫 商品: 顺丰授权
⏰ 授权时长: {mes_auth_months_int}月
==================""")
                else:
                    zf(project='顺丰授权', me_as_int=mes_auth_months_int, accountVip=accountVip, token=userurl,
                       phone=account, account=account, owner_id=userid)
            elif action_choice_validated_int == 2: 
                friend_pay_function_for_account(account)
            elif action_choice_validated_int == 3: 
                confirm_msg_delete = """
=====警告=====
确定要删除该账号吗？
此操作不可恢复！
------------------
[y] 确认删除
[n] 取消操作
==================""" 
                sender.reply(confirm_msg_delete)                
                yesorno_delete_input = sender.input(120000, 0, False)
                if yesorno_delete_input and yesorno_delete_input.lower() in ['y', '是']:
                    accounts.remove(str(account))
                    try:
                        qlid = allenvs(osname=yuhua_sf_osname, account=str(account)) 
                        if qlid:
                            delenvs(id=qlid)
                    except:
                        pass                    
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_token', key=f'{account}')
                    except Exception:
                        pass
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_auth', key=f'{account}')
                    except Exception:
                        pass
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_qiangquan_status', key=account) 
                    except Exception:
                        pass                    
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_memNo', key=account)
                    except Exception:
                        pass
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_deviceId', key=account)
                    except Exception:
                        pass
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_memberid', key=account)
                    except Exception:
                        pass
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_sessionId', key=account)
                    except Exception:
                        pass
                    if len(accounts) == 0:
                        try:
                            middleware.bucketDel(bucket='yuhua_sf_user', key=userid)
                        except Exception:
                            pass
                    else:
                        middleware.bucketSet(bucket='yuhua_sf_user', key=userid, value=f'{accounts}')
                    sender.reply('✅ 账号删除成功！')
                else: 
                    sender.reply('✅ 已取消删除')
                    return
        except Exception as e:
            sender.reply(f"=====账号处理错误=====\n❌ 账号列表处理失败\n⚠️ 错误: {str(e)}")
    else: 
        sender.reply(f"=====未绑定账号=====\n❌ 未找到任何账号信息\n💡 发送 {randomsigncommand} 绑定")
def show_friend_pay_auth_info(user_key):
    if not user_key:
        return """
=====功能未公测=====
❌ 好友代付功能内测中
💡 此功能为内部测试功能
=================="""
    else:
        return f"""
=====验证失败=====
❌ 代付密钥不正确
------------------
💡 当前设置的密钥: {user_key[:3]}****{user_key[-2:] if len(user_key) > 5 else '****'}
🔐 请检查密钥是否正确
------------------
配置路径：插件配置→代付密钥
请联系管理员获取正确密钥
=================="""
def friend_pay_function_for_account(account):
    try:
        if not ensure_private_chat_for_sf_pay():
            return
        auth_key = middleware.bucketGet('yuhua_sf', 'sfdf')
        success, _, error_message = call_external_api('/api/auth/check', {'auth_key': auth_key})
        if not success:
            sender.reply("""
=====功能未公测=====
❌ 好友代付功能内测中
💡 此功能为内部测试功能
==================""")
            return
        accountVip = middleware.bucketGet(bucket='yuhua_sf_auth', key=account)
        if len(accountVip) == 0:
            sender.reply("""
=====暂无授权=====
❌ 该账号未查到授权
💡 请先进行账号授权
==================""")
            return
        elif accountVip <= today_time:
            sender.reply(f"""
=====授权过期=====
❌ 该账号授权已过期
💡 请续费授权后使用
==================""")
            return
        session_id, _, _ = get_valid_session_or_renew(account)
        if not session_id:
            sender.reply(f"""
=====操作被拒绝=====
❌ 账号Token已失效
💡 代付功能需要有效登录状态
🔗 请发送“顺丰登录”重新登录
==================""")
            return
        member_id = get_member_id_for_account(account)
        if not member_id:
            sender.reply("""
=====信息缺失=====
❌ 无法获取账户的memberId信息
💡 请重新登录账号获取完整信息
🔐 可能账号是代付功能之前添加的，所需参数当时没获取完整
================""")
            return
        orders = query_unpaid_orders_for_account(account, member_id)
        selected_order = select_unpaid_order_for_pay(orders, account)
        if not selected_order:
            return
        mobile_display = account[:3] + "****" + account[7:]
        display_amt = format_sf_amount_fen(selected_order.get('amt', '-'))
        sender.reply(f"""
=====代付页面生成确认=====
🤪 账户: {mobile_display}
✨ 运单: {selected_order.get('waybillNo', '-')}
💰 金额: {display_amt}元
💥 会员: {member_id[:8]}****
------------------
确认发起代付页面生成请求？(y/n)
==================""")
        confirm = sender.input(60000, 0, False)
        if confirm and confirm.lower() in ['y', 'yes', '是', '确认']:
            result_text, pay_h5_url = execute_friend_pay(selected_order, account, member_id)
            sender.reply(result_text)
            if pay_h5_url:
                success = send_qr_code_smart(sender, pay_h5_url)
                if not success:
                    sender.reply(f"支付页面链接: {pay_h5_url}")
        else:
            sender.reply("✅ 已取消代付操作")
    except Exception as e:
        if "APP侧登录态已失效" in str(e) or "您的登录信息已失效，请重新登录" in str(e):
            sender.reply(f"""
=====操作被拒绝=====
❌ 当前账号APP侧登录状态已失效
💡 可能用户登录顺丰APP被挤下线
🔗 请发送“顺丰登录”重新登录后再试
==================""")
            return
        sender.reply(f"❌ 代付功能异常: {str(e)}")    
def friend_pay_function():
    if not ensure_private_chat_for_sf_pay():
        return
    auth_key = middleware.bucketGet('yuhua_sf', 'sfdf')
    success, _, error_message = call_external_api('/api/auth/check', {'auth_key': auth_key})
    if not success:
        sender.reply("""
=====功能未公测=====
❌ 好友代付功能内测中
💡 此功能为内部测试功能
==================""")
        return
    if len(uservalue) == 0:
        sender.reply(f"""
=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 {randomsigncommand} 绑定
==================""")
        return
    try:
        accounts = eval(uservalue)
        if not isinstance(accounts, list):
            accounts = [str(accounts)]
        accounts = [str(account) for account in accounts]
    except Exception:
        sender.reply("❌ 账号数据异常，请重新绑定")
        return
    account = select_account_for_pay(accounts)
    if not account:
        return
    friend_pay_function_for_account(account)
def zf(project, me_as_int, accountVip, token, phone, account, owner_id):
    try:
        zsm = middleware.bucketGet('yuhua_sf', 'zsm')
        if not zsm:
            sender.reply('未配置收款方式，请联系管理员！')
            return False
        if sender.atWaitPay():
            sender.reply('⚠️ 当前有人正在支付，请稍后再试！')
            return False
        money = Decimal(me_as_int) * Decimal(sfVipmoney)
        pay_msg = f"""
=====微信扫码支付====
🎫 商品: {project}
💰 金额: {money}元
------------------
请在120秒内完成支付
回复"q"取消支付
=================="""
        if '批量' in project and '个' in project:
            try:
                num_accounts = int(re.search(r'\((\d+)个\)', project).group(1))
                if num_accounts > 0:
                    months = me_as_int // num_accounts
                    pay_msg = f"""
=====微信扫码支付====
🎫 商品: {project}
📅 时长: {months}月
💰 金额: {money}元
------------------
请在120秒内完成支付
回复"q"取消支付
=================="""
            except (AttributeError, ValueError, ZeroDivisionError):
                pass
        sender.reply(pay_msg)
        sender.replyImage(zsm)
        ddzf = sender.waitPay("q", 120 * 1000)
        if str(ddzf) == 'q':
            sender.reply('✅ 已取消支付')
            return False
        if not ddzf:
            return False
        Money = 0.0
        Time = ""
        From = ""
        try:
            if isinstance(ddzf, str):
                ddzf = json.loads(ddzf)            
            if ddzf.get('Type') in ['微信赞赏', '微信收款']:
                Money = float(ddzf.get('Money', 0))
                Time = ddzf.get('Time', '').split('.')[0].replace('T', ' ')
                From = ddzf.get('FromName', '')
            elif ddzf.get('Money'):
                Money = float(ddzf.get('Money', 0))
                Time = ddzf.get('Time', '').replace('T', ' ').split('.')[0]
                From = ddzf.get('FromName', '')
            elif ddzf.get('money'):
                Money = float(ddzf.get('money', 0))
                Time = ddzf.get('time', '').replace('T', ' ').split('.')[0]
                From = ddzf.get('fromName', '')
            else:
                 sender.reply('不支持的支付消息格式')
                 return False
        except Exception:
            sender.reply("❌ 无法解析支付结果")
            return False
        if Money >= float(money):
            if account:
                new_expiry_date = empower(empowertime=accountVip, me_as_int=me_as_int)
                middleware.bucketSet('yuhua_sf_auth', account, new_expiry_date)
                ql_sync_value = get_ql_cookie_format(account, token)
                Addenvs(osname=yuhua_sf_osname, value=ql_sync_value, account=account, phone=phone, owner_id=owner_id)
            result_msg = f"""
=====支付成功=====
🎫 商品: {project}
💰 金额: {Money}元
⏰ 时间: {Time}
{f'👤 付款人: {From}' if From else ''}
=================="""
            sender.reply(result_msg)
            return True
        else:
            sender.reply(f"""
=====支付金额错误=====
💰 应付: {money}元
💳 实付: {Money}元
{f'👤 付款人: {From}' if From else ''}
❗ 请联系管理员处理退款！
==================""")
            return False            
    except Exception as e:
        sender.reply(f"=====系统错误=====\n❌ 支付处理异常\n------------------\n错误信息: {str(e)}")
        return False        
def check_black_account(session_id):
    try:
        url = "https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralTaskStrategyService~queryPointTaskAndSignFromES"
        headers = {"Cookie": f"sessionId={session_id}","Content-Type": "application/json"}
        payload = {"channelType": "1", "deviceId": str(uuid.uuid4())}
        res = requests.post(url, headers=headers, json=payload, timeout=5).json()
        if res.get('success') and res.get('obj'):
            tasks = res['obj'].get('taskTitleLevels', [])
            for t in tasks:
                if t.get('actionType') in ['06', '07']: return False
            return True
    except: pass
    return False
def to_superscript_date(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        year, month, day = str(dt.year), str(dt.month), str(dt.day)
        sup_map = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
        return f"{year.translate(sup_map)}∙{month.translate(sup_map)}∙{day.translate(sup_map)}"
    except:
        return ""
def get_anniversary_medals(session_id):
    CARD_CURRENCIES =['KAI_XIANG', 'FA_CAI', 'DAN_GAO', 'GAO_YA', 'GAN_FAN']
    try:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026CardService~cardStatus'
        headers = {
            "Cookie": f"sessionId={session_id}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf254173b) XWEB/19027"
        }
        res = send_request_global('POST', url, headers=headers, json={}, timeout=5).json()
        if res and res.get('success'):
            card_status = res.get('obj', {})
            balances = {c: 0 for c in CARD_CURRENCIES}
            for acc in card_status.get('currentAccountList',[]):
                currency = acc.get('currency', '')
                if currency in CARD_CURRENCIES:
                    balances[currency] = acc.get('balance', 0)
            part1 = f"拆箱达人×{balances['KAI_XIANG']}, 马上有钱×{balances['FA_CAI']} "
            part2 = f"甜度超标×{balances['DAN_GAO']},  高雅人士×{balances['GAO_YA']}, 全能吃货×{balances['GAN_FAN']}"
            return f"{part1}\n{part2}"
    except Exception:
        pass
    return ""
def get_expiring_points(session_id):
    url = "https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberIntegral~userInfoService~queryUserInfo"
    headers = {
        "Cookie": f"sessionId={session_id}",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Linux; Android 16; RMX5060 Build/BP2A.250605.015; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/142.0.7444.173 Mobile Safari/537.36 XWEB/1420153 MMWEBSDK/20250802 MMWEBID/1393 MicroMessenger/8.0.62.2900(0x28003EA0) WeChat/arm64 Weixin NetType/5G Language/zh_CN ABI/arm64 miniProgram/wxd4185d00bf7e08ac"
    }
    data = {
        "sysCode": "ESG-CEMP-CORE",
        "optionalColumns": ["usablePoint", "cycleSub", "leavePoint", "pointClearCycle"],
        "token": "zeTLTYeG0bLetfRk"
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10).json()
        if response.get('success'):
            obj = response.get('obj', {})
            leave_point = obj.get('leavePoint', 0)
            clear_date = obj.get('pointClearCycle', '')
            
            if int(leave_point) > 0:
                now_date = datetime.now()
                try:
                    if clear_date:
                        exp_date = datetime.strptime(clear_date, "%Y-%m-%d")
                        if exp_date.year == 1970:
                            exp_date = now_date.replace(month=6, day=30)
                        if exp_date < now_date:
                            exp_date = exp_date.replace(year=exp_date.year + 1)                            
                        clear_date = exp_date.strftime("%Y-%m-%d")
                    else:
                        exp_date = now_date.replace(month=6, day=30)
                        if exp_date < now_date:
                            exp_date = exp_date.replace(year=exp_date.year + 1)
                        clear_date = exp_date.strftime("%Y-%m-%d")                        
                except Exception:
                    clear_date = now_date.strftime("%Y") + "-06-30"
            return int(leave_point), clear_date
    except Exception:
        pass
    return 0, ""
def cx(session_id):
    coin, allcoin = todaycoin(session_id)
    if coin is None:
        return None, allcoin, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", 0, "", ""
    large_coupons = query_large_coupons(session_id)
    point_status = "积分正常"
    if int(coin) == 0 and check_black_account(session_id): point_status = "积分黑号"
    expiring_coin, expiring_date = get_expiring_points(session_id)
    anniversary_medals = ""
    hide_medal_str = middleware.bucketGet('yuhua_sf', 'hide_medal')
    if hide_medal_str != 'true':
        anniversary_medals = get_anniversary_medals(session_id)    
    return coin, allcoin, "N/A", "N/A", "N/A", "N/A", large_coupons, point_status, expiring_coin, expiring_date, anniversary_medals
def cxs():
    sender.reply("\n正在查询...")
    if len(uservalue) != 0:
        accounts = list(dict.fromkeys(eval(uservalue)))
        middleware.bucketSet(bucket='yuhua_sf_user', key=userid, value=str(accounts))       
        for account in accounts:
            accountVip = middleware.bucketGet(bucket='yuhua_sf_auth', key=f'{account}')
            login_mobile = account[:3] + "****" + account[7:]            
            if len(accountVip) == 0:
                auth_status = "⚠️ 未授权"
                auth_time = "无"
            elif accountVip <= today_time:
                auth_status = "❌ 已过期"
                auth_time = accountVip
            else:
                auth_status = "✅ 已授权"
                auth_time = accountVip            
            if len(accountVip) == 0 or accountVip <= today_time:
                sender.reply(f"""
=====顺丰授权过期=====
🤪 账号: {login_mobile}
☁ 授权状态: {auth_status}
📅 到期时间: {auth_time}
==================""")
                continue
            session_id, _, _ = get_valid_session_or_renew(account)
            try:
                if not session_id:
                    sender.reply(f"""
=====账号信息=====
🤪 账号: {login_mobile}
💫 结果: 凭证已失效且自动续期失败，请重新登录
==================""")
                    continue
                coin, allcoin, honey, allhoney, capacity, usableHoney, large_coupons, point_status, expiring_coin, expiring_date, anniversary_medals = cx(session_id)                    
                if coin is None:
                    error_msg = allcoin
                    sender.reply(f"""
=====账号信息=====
🤪 账号: {login_mobile}
💫 结果: {error_msg}
==================""")
                    continue              
                formatted_coupons = f"\n{large_coupons}" if '\n' in large_coupons else f" {large_coupons}"  
                expiring_line = ""
                if expiring_coin > 0:
                    sup_date = to_superscript_date(expiring_date)
                    expiring_line = f"\n⛱️ 过期积分: {expiring_coin} {sup_date}"
                medal_line = ""
                if anniversary_medals:
                    medal_line = f"\n🎖️ 周年勋章: {anniversary_medals}"
                account_info = f"""
=====账号详情=====
🤪 用户账号: {login_mobile}
☁ 授权到期: {auth_time}
💎 当前积分: {allcoin}
💥 今日积分: {coin}{expiring_line}
🔆 积分状态: {point_status}{medal_line}
🎫 大额卡券:{formatted_coupons}
=================="""
                sender.reply(account_info)
            except SystemExit:
                sender.reply(f"""
=====顺丰查询异常=====
🤪 账号: {login_mobile}
☁ 授权状态: {auth_status}
📅 到期时间: {auth_time}
❌ 状态: 查询失败
==================""")
                continue
    else:
        sender.reply(f"""
=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 {randomsigncommand} 绑定
==================""")
def _send_push_notification(user, push_msg):
    middleware.push('qq', '', user, '', push_msg)
    middleware.push('qb', '', user, '', push_msg)
    middleware.push('wx', '', user, '', push_msg)
    middleware.push('gw', '', user, '', push_msg)
    middleware.push('sb', '', user, '', push_msg)
    middleware.push('wb', '', user, '', push_msg)
    middleware.push('tg', '', user, '', push_msg)
    middleware.push('tb', '', user, '', push_msg)
    middleware.push('qx', '', user, '', push_msg)
    middleware.push('xy', '', user, '', push_msg)
    middleware.push('ip', '', user, '', push_msg)
def push(user, account, c):
    login_mobile = account[:3] + "****" + account[7:]
    push_msg = f"""
=====顺丰账号通知=====
🤪 账号: {login_mobile}
📢 消息: {c}
=================="""
    _send_push_notification(user, push_msg)
def clean_expired_accounts():
    if not sender.isAdmin():
        sender.reply("""
=====权限不足=====
❌ 您没有权限执行此操作
==================""")
        exit(0)        
    users = middleware.bucketAllKeys(bucket='yuhua_sf_user')    
    if not users:
        sender.reply("""
=====清理结果=====
❌ 未找到任何绑定账号
==================""")
        exit(0)        
    sender.reply(f"""
=====开始清理=====
📊 共找到: {len(users)}个用户
⏳ 清理中请稍候...
==================""")    
    cleaned_count = 0
    for user in users:
        try:
            accountlist = middleware.bucketGet(bucket='yuhua_sf_user', key=f'{user}')
            if not accountlist:
                continue
            accounts = eval(accountlist)
            if isinstance(accounts, (list, tuple, set)):
                accounts = list(dict.fromkeys(accounts))
            else:
                accounts = [str(accounts)]                
            valid_accounts =[]            
            for account in accounts:
                accountVip = middleware.bucketGet(bucket='yuhua_sf_auth', key=account)               
                if len(accountVip) == 0 or accountVip <= today_time:
                    try:
                        qlid = allenvs(osname=yuhua_sf_osname, account=account)
                        if qlid:
                            delenvs(id=qlid)
                    except:
                        pass                        
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_token', key=account)
                    except Exception:
                        pass
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_auth', key=account)
                    except Exception:
                        pass
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_memNo', key=account)
                    except Exception:
                        pass
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_deviceId', key=account)
                    except Exception:
                        pass
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_memberid', key=account)
                    except Exception:
                        pass
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_sessionId', key=account)
                    except Exception:
                        pass
                    try:
                        middleware.bucketDel(bucket='yuhua_sf_qiangquan_status', key=account)
                    except Exception:
                        pass                  
                    cleaned_count += 1
                else:
                    valid_accounts.append(account)
            valid_accounts = list(dict.fromkeys(valid_accounts))            
            if valid_accounts:
                middleware.bucketSet(bucket='yuhua_sf_user', key=user, value=str(valid_accounts))
            else:
                try:
                    middleware.bucketDel(bucket='yuhua_sf_user', key=user)
                except Exception:
                    pass                
        except Exception as e:
            continue
    sender.reply(f"""
=====清理完成=====
✅ 已清理: {cleaned_count}个账号
==================""")
def query_large_coupons(session_id):
    url = "https://mcs-mimp-web.sf-express.com/mcs-mimp/coupon/available/list"    
    headers = {
        "Cookie": f"sessionId={session_id}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    }    
    data = {
        "couponType": "",
        "pageNo": 1,
        "pageSize": 100
    }    
    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()        
        if not result.get('success'):
            return "优惠券查询失败"            
        coupons = result.get('obj', [])
        if not coupons:
            return "暂无优惠券"            
        large_coupons = []
        for coupon in coupons:
            try:
                coupon_name = coupon.get('couponName', '未知优惠券')
                expire_time = coupon.get('invalidTm', '')
                quantity = coupon.get('couponNum', 1)
                coupon_type = str(coupon.get('couponType', ''))
                pledge_amt = float(coupon.get('pledgeAmt', 0))
                if coupon_type == '1' and '元' not in coupon_name:
                    amt_str = f"{int(pledge_amt)}" if pledge_amt.is_integer() else f"{pledge_amt}"
                    coupon_name = f"{amt_str}元{coupon_name}"               
                is_target = False
                if any(kw in coupon_name for kw in ['顺丰免单券', '会员日免单券', '20元免单券', '15元运费券', '10元运费券']):
                    is_target = True
                elif coupon_type == '1' and pledge_amt >= 5:
                    if any(kw in coupon_name for kw in ['运费', '寄件', '立减', '抵扣', '通用']):
                        is_target = True
                if is_target:
                    display_name = coupon_name
                    if quantity > 1:
                        if '（' in coupon_name:
                            parts = coupon_name.split('（', 1)
                            display_name = f"{parts[0]}×{quantity}（{parts[1]}"
                        else:
                            display_name = f"{coupon_name}×{quantity}"                    
                    coupon_info = f"{display_name}, 至{expire_time}失效"
                    large_coupons.append(coupon_info)
            except Exception as e:
                continue
        return '\n'.join(large_coupons) if large_coupons else "暂无大额券"     
    except Exception as e:
        return "优惠券查询失败"
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
yuhua_sf_osname, yuhua_sf_qlname, yuhua_managecommand, yuhua_querycommand, yuhua_signcommand, \
randommanagecommand, randomquerycommand, randomsigncommand, sfVipmoney, show_point_status, qiangquan_bingfa, renew_bingfa = getusercontent()
QLurl, qltoken = seekql()
imtype = sender.getImtype()
today_date = datetime.now().date()
today_time = str(today_date)
usermessage = str(sender.getMessage() or "")
if not check_maintenance_page():
        sender.reply("❌ 服务端无法连通, 插件停止运行")
        exit(0)
# if imtype in["fake", "cron"]:
#     import random  
#     def _safe_renew_task(account):
#         time.sleep(random.uniform(0.1, 0.5))
#         try:
#             accountVip = middleware.bucketGet(bucket='yuhua_sf_auth', key=account)
#             if not accountVip or accountVip <= today_time:
#                 return 
#             if DEBUG:
#                 printf(f"定时任务: 账号 {account} 开始执行强制续期...", "INFO")
#             res = silent_renew_url(account)         
#             if DEBUG and not res:
#                 printf(f"定时任务: 账号 {account} 强制续期失败 (可能缺少关键参数)", "WARN")
#         except Exception as e:
#             if DEBUG:
#                 printf(f"续期任务异常 {account}: {str(e)}", "WARN")
#             pass
#     try:
#         all_accounts = set()
#         users = middleware.bucketAllKeys(bucket='yuhua_sf_user')
#         for user in users:
#             accountlist = middleware.bucketGet(bucket='yuhua_sf_user', key=f'{user}')
#             if not accountlist: continue
#             try:
#                 accs = eval(accountlist)
#                 for acc in accs:
#                     all_accounts.add(str(acc))
#             except: continue 
#         if all_accounts:
#             if DEBUG:
#                 printf(f"开始执行定时强制续期任务，共 {len(all_accounts)} 个账号", "INFO")
#             with ThreadPoolExecutor(max_workers=renew_bingfa) as executor:
#                 list(executor.map(_safe_renew_task, list(all_accounts)))
#     except Exception as e:
#         if DEBUG:
#             printf(f"定时任务全局异常: {str(e)}", "ERROR")
#         pass
#     # exit(0)
if '登录' in usermessage or '登陆' in usermessage:
    bindaccount()
elif '管理' in usermessage:
    if len(uservalue) != 0:
        meituanmanage()
    else:
        sender.reply(f"""
=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 {randomsigncommand} 绑定
==================""")
elif '查询' in usermessage:
    if len(uservalue) != 0:
        cxs()
    else:
        sender.reply(f"""
=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 {randomsigncommand} 绑定
==================""")
elif usermessage == '顺丰清理':
    clean_expired_accounts()
elif usermessage == '顺丰授权':
    sf_auth()
elif '代付' in usermessage:
    friend_pay_function()
elif usermessage == '顺丰检测':
    if not sender.isAdmin():
        sender.reply("❌ 您没有权限执行此操作")
    else:
        sender.reply("⏳ 正在执行账号检测...")
        users = middleware.bucketAllKeys(bucket='yuhua_sf_user')
        for user in users:
            accountlist = middleware.bucketGet(bucket='yuhua_sf_user', key=f'{user}')
            try:
                accounts = eval(accountlist)
            except:
                continue
            for account in accounts:
                accountVip = middleware.bucketGet(bucket='yuhua_sf_auth', key=account)
                session_id, login_mobile, _ = get_valid_session_or_renew(account)
                if not session_id:
                    push(user=user, account=account, c="""
⚠️ 账号状态异常
------------------
❌ Cookie已失效且自动续期失败
💡 请尽快更新账号""")
                    continue
                if len(accountVip) != 0 and accountVip > today_time:
                    continue
                else:
                    qlid = allenvs(osname=yuhua_sf_osname, account=account)
                    delenvs(id=qlid)
                    push(user=user, account=account, c="""
⚠️ 授权已过期
------------------
❌ 授权状态失效
💡 请及时续费授权""")
        sender.reply("✅ 检测完成")
else:
    sender.setContinue()
