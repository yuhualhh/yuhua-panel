# [title: 慧生活798]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@e421156e71bcb44eae66a85b46e7264b39bf6cee/2026/01/19/afaa1db841593a771653e4791962e75c.png]
# [language: python]
# [rule: ^(慧生活)(登录|查询|管理|清理|授权|检测|运行|一键运行|设备|设备添加|设备删除)$]
# [disable:false]
# [open_source: false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [priority: 9999999999999999999]
# [public: true]
# [version: 1.2.3]
# [price: 0]
# [author: 羽化]
# [service: ]
# [description: ❶慧生活798内置任务插件，自动完成每日任务获取315左右积分，支持Token登录、手机号登录、自定义并发、管理、查询、授权、检测授权过期以及Token失效推送等功能<br>❷部分功能的实现需自行添加计划任务伪装管理员定时，了解如何添加计划任务请看移动云盘插件介绍，关于指令『慧生活检测』与『慧生活清理』定时『30 18 * * *』，关于指令『慧生活一键运行』定时『0 7,19 * * *』<br>❸新增设备管理，支持模拟扫码添加设备、查询设备场所|余额|账单详情、切换积分抵扣、立即使用、立即结算等功能<img src="https://gcore.jsdelivr.net/gh/lhz03/img@7b9ff2cf7c406da88575a68400cff2d4604ddaca/2026/04/08/ab67377a6deec9c1303a10353b9d7666.png">]

# [param: {"required":true,"key":"yuhua_hsh.zsm","bool":false,"placeholder":"","name":"收款码子","desc":"微信Bot收款码直链"}]
# [param: {"required":true,"key":"yuhua_hsh.price","bool":false,"placeholder":"","name":"收费价格","desc":"不填默认0元，单位: 元/月"}]
# [param: {"required":true,"key":"yuhua_hsh.bingfa","bool":false,"placeholder":"","name":"并发数量","desc":"不填默认20"}]
# [param: {"required":false,"key":"yuhua_hsh.push_status","bool":true,"placeholder":"","name":"推送状态","desc":"是否将慧生活一键运行结果推送给用户"}]
# [param: {"required":false,"key":"yuhua_hsh.debug_pwd","bool":false,"placeholder":"","name":"调试模式","desc":"非插件开发者无需理会"}]

import re
import time
import os
import io
from datetime import datetime, timedelta
import middleware
import urllib.parse
from decimal import Decimal
import requests
import json
import uuid
import random
import sys
import threading
import base64
import hashlib
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============ 二维码本地解码 (opencv, 懒加载; 单文件插件内联) ============
try:
    import numpy as np
    _QR_HAVE_NUMPY = True
except Exception:
    np = None
    _QR_HAVE_NUMPY = False
try:
    from PIL import Image as _PILImage
    _QR_HAVE_PIL = True
except Exception:
    _PILImage = None
    _QR_HAVE_PIL = False

_CV2_MOD = None
_CV2_TRYED = False
_CV2_ERR = None   # 记录 import cv2 的真实异常，便于排查(默认是"缺依赖"但实际可能是DLL/numpy问题)

def _cv2():
    """懒加载 opencv; 失败返回 None"""
    global _CV2_MOD, _CV2_TRYED, _CV2_ERR
    if _CV2_TRYED:
        return _CV2_MOD
    _CV2_TRYED = True
    try:
        import cv2
        _CV2_MOD = cv2
    except Exception as e:
        _CV2_MOD = None
        _CV2_ERR = repr(e)
        if DEBUG:
            printf(f"cv2 import 失败: {_CV2_ERR}", "WARN")
    return _CV2_MOD

_QR_DID_RE = re.compile(r'(?:did|dev(?:ice)?(?:_?id)?)[=/:]([0-9]{6,25})', re.I)

def _qr_extract_did(text):
    """从二维码文本提取设备号: hnkzy URL / id= 参数 / 纯数字"""
    if not text:
        return None
    text = str(text).strip()
    m = re.search(r'(?:[?&]|^)id=([0-9]{6,25})(?:&|$)', text)
    if m:
        return m.group(1)
    m = _QR_DID_RE.search(text)
    if m:
        return m.group(1)
    m = re.search(r'/(\d{6,25})(?:[/?#]|$)', text)
    if m:
        return m.group(1)
    m = re.fullmatch(r'\d{6,25}', text)
    if m:
        return m.group(0)
    return None

def _qr_to_array(img):
    """PIL/bytes/ndarray -> ndarray(RGB)"""
    if img is None:
        return None
    try:
        if isinstance(img, np.ndarray):
            return img if img.ndim in (2, 3) else None
        if _QR_HAVE_PIL and isinstance(img, _PILImage.Image):
            return np.asarray(img.convert('RGB'))
        if isinstance(img, (bytes, bytearray)):
            if _QR_HAVE_PIL:
                im = _PILImage.open(io.BytesIO(bytes(img)))
                return np.asarray(im.convert('RGB'))
            return None
    except Exception:
        return None
    return None

def _qr_decode_opencv(data):
    """用 OpenCV QRCodeDetector 解码 (多解: 原图+旋转+缩放, 提高拍歪成功率)"""
    cv2 = _cv2()
    if cv2 is None:
        return []
    arr = _qr_to_array(data)
    if arr is None or arr.size == 0:
        return []
    detector = cv2.QRCodeDetector()
    out = []
    candidates = [arr]
    # 附加旋转90/180/270 与灰度, 增强鲁棒性
    try:
        g = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        candidates.append(g)
        for ang in (90, 180, 270):
            M = cv2.getRotationMatrix2D((arr.shape[1] / 2.0, arr.shape[0] / 2.0), ang, 1.0)
            rot = cv2.warpAffine(arr, M, (arr.shape[1], arr.shape[0]), flags=cv2.INTER_NEAREST)
            candidates.append(rot)
    except Exception:
        pass
    seen = set()
    for cand in candidates:
        try:
            val, pts, _ = detector.detectAndDecode(cand)
            if val and val not in seen:
                seen.add(val)
                out.append(val)
        except Exception:
            continue
    return out

def _qr_decode_worker(data, result):
    try:
        result['texts'] = _qr_decode_opencv(data)
    except Exception as e:
        result['error'] = str(e)

def qr_decode(data, timeout=10):
    """解码二维码图片 bytes, 返回文本列表; 超时/失败返回 []"""
    result = {}
    try:
        t = threading.Thread(target=_qr_decode_worker, args=(data, result), daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            return []
        return result.get('texts', [])
    except Exception:
        return []

def _decode_qr_from_msg(msg):
    """从消息提取图片并本地解码, 返回 (解码文本, 设备号did)"""
    src = _extract_image_source(msg)
    if not src:
        return None, None
    data = _fetch_image_bytes(src)
    if not data:
        return None, None
    texts = qr_decode(data)
    if not texts:
        return None, None
    did = _qr_extract_did(texts[0])
    return texts[0], did
 
# 封装函数：支持颜色分级(INFO=绿, WARN=黄, 其他=红)，输出到stderr确保控制台可见
def printf(msg,level='INFO'):
    c=32 if level in['INFO','DEBUG']else 33 if level in['WARN','WARNING']else 31;sys.stderr.write(f"\033[{c}m[{level}] {str(msg)}\033[0m\n");sys.stderr.flush()

# --- 性能与容错 ---
# 全局网络超时（秒）
GLOBAL_TIMEOUT = 45
# ddddocr 服务地址
DDDDOCR_HOST = "http://ddddocr.250666.xyz"

#输出日志
debug_key = middleware.bucketGet('yuhua_hsh', 'debug_pwd') or ''
DEBUG = (debug_key == '123456789abcC@')
if DEBUG:
    printf("🔥🔥🔥 调试模式已开启，密钥验证通过 🔥🔥🔥", "WARN")

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

def token_online_login():
    """
    【Token登录功能】
    通过抓包获取 Authorization
    """
    guide = """
=====Token登录=====
慧生活798请求头中的Authorization值
------------------
请在60秒内完成
回复"q"退出"""
    sender.reply(guide)
    user_input = sender.input(60000, 1, False)
    
    if not user_input:
        sender.reply("❌ 输入超时")
        return
    elif user_input.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    
    token = user_input.strip()

    if not token:
        sender.reply("❌ 输入为空")
        return

    process_login_success(token)

def sms_login_interaction(platform="app"):
    """
    【短信登录功能】
    自动处理算术验证码并发送短信
    """
    sender.reply(f"""
=====短信登录=====
请输入慧生活798手机号
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
        sender.reply("❌ 手机号格式错误")
        return

    sender.reply("正在过数字计算...")

    hsh = HSH(token="", platform=platform, login=True)
    
    # 尝试发送短信（含验证码识别重试逻辑）
    send_ok, send_msg = hsh.send_sms_with_captcha(phone)
    
    if not send_ok:
        sender.reply(f"❌ 验证失败: {send_msg}")
        return

    masked_phone = _mask_identifier(phone)
    sender.reply(f"""
=====短信验证=====
请回复短信验证码
------------------
请在60秒内完成
回复"q"退出""")

    sms_code = sender.input(60000, 0, False)
    if not sms_code:
        sender.reply("❌ 输入超时")
        return
    if sms_code.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    sms_code = sms_code.strip()

    # 执行登录
    login_ok, token_or_msg = hsh.login_by_sms_code(phone, sms_code)
    
    if login_ok:
        process_login_success(token_or_msg)
    else:
        sender.reply(f"❌ 登录失败: {token_or_msg}")

def process_login_success(token, platform="app"):
    """处理登录成功后的逻辑（Token验证与保存）"""
    sender.reply("正在验证凭证有效性...")
    try:
        # 初始化API类进行验证 (按登录平台选择请求头)
        hsh = HSH(token, platform=platform)
        is_valid, msg = hsh.check_token()
        
        if not is_valid:
            sender.reply(f"❌ 登录失败: {msg}")
            return

        # 获取用户信息
        info_ok, info_data = hsh.get_user_info()
        if not info_ok:
            sender.reply(f"❌ 登录失败: 无法获取用户信息")
            return
            
        phone = str(info_data.get('phone', '未知'))
        uid_raw = str(info_data.get('uid', ''))
        
        # 账号处理逻辑
        accounts = eval(uservalue or '[]')
        matched_uid = None
        for uid in accounts:
            old_phone = middleware.bucketGet('yuhua_hsh_phone', str(uid)) or "未知"
            if old_phone == phone:
                matched_uid = str(uid)
                break
        
        final_uid = matched_uid if matched_uid else (uid_raw if uid_raw else gen_unique_id())
        
        if matched_uid:
            middleware.bucketSet('yuhua_hsh_token', str(matched_uid), token)
            try:
                middleware.bucketDel('yuhua_hsh_password', str(matched_uid))
            except Exception:
                pass
            
            phone_mask = _mask_identifier(phone)
            sender.reply(f"""
=====登录成功=====
🤪 账号: {phone_mask}
✅ 状态: 更新成功
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")
        else:
            accounts.append(str(final_uid))
            middleware.bucketSet('yuhua_hsh_user', userid, str(accounts))
            middleware.bucketSet('yuhua_hsh_token', str(final_uid), token)
            middleware.bucketSet('yuhua_hsh_phone', str(final_uid), phone)
            
            phone_mask = _mask_identifier(phone)
            sender.reply(f"""
=====登录成功=====
🤪 账号: {phone_mask}
✅ 状态: 添加成功
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")

    except Exception as e:
        sender.reply(f"❌ 登录失败: {str(e)}")

def get_global_session():
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({
        'User-Agent': 'Android_ilife798_3.1.10',
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip'
    })
    return session

def send_request_global(method, url, **kwargs):
    session = kwargs.pop('session', None) or get_global_session()
    kwargs.setdefault('timeout', 45)
    
    if DEBUG:
        printf(f"\n===== [REQUEST START] =====", "DEBUG")
        printf(f"METHOD: {method} | URL: {url}", "DEBUG")
        printf(f"HEADERS: {json.dumps(kwargs.get('headers', {}), ensure_ascii=False)}", "DEBUG")
        if kwargs.get('json'):
            printf(f"BODY(JSON): {json.dumps(kwargs.get('json'), ensure_ascii=False)}", "DEBUG")
        elif kwargs.get('data'):
            # 如果data太长(如图片base64)截断显示
            data_str = str(kwargs.get('data'))
            if len(data_str) > 500: data_str = data_str[:200] + "...(truncated)..."
            printf(f"BODY(DATA): {data_str}", "DEBUG")
            
    for attempt in range(3):
        try:
            response = session.request(method, url, **kwargs)
            
            if DEBUG:
                printf(f"----- [RESPONSE - Attempt {attempt+1}] -----", "DEBUG")
                printf(f"STATUS: {response.status_code}", "DEBUG")
                printf(f"RSP HEADERS: {json.dumps(dict(response.headers), ensure_ascii=False)}", "DEBUG")
                _ctype = str(response.headers.get('Content-Type') or '')
                try:
                    _blen = len(response.content)
                except Exception:
                    _blen = 0
                if 'image' in _ctype.lower() or 'octet-stream' in _ctype.lower() or _blen > 100000:
                    printf(f"RSP BODY: <{_ctype or 'binary'}, {_blen} bytes>", "DEBUG")
                else:
                    try:
                        printf(f"RSP BODY: {json.dumps(response.json(), ensure_ascii=False)}", "DEBUG")
                    except:
                        printf(f"RSP BODY: {response.text[:1000]}", "DEBUG")
                printf(f"===== [REQUEST END] =====\n", "DEBUG")
                
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if DEBUG: printf(f"⚠️ Attempt {attempt+1} Failed: {e}", "WARN")
            if attempt < 2:
                time.sleep(2 + attempt)
                continue
            else:
                raise e
        except requests.exceptions.RequestException as e:
            if DEBUG: printf(f"⚠️ Request Error: {e}", "WARN")
            if attempt < 2:
                time.sleep(2)
                continue
            else:
                raise e
    return None

###################### ddddocr 识别类 ######################
class DdddocrClient:
    def __init__(self, url=None):
        self.url = url or DDDDOCR_HOST
    
    def classification(self, img_b64):
        """数字计算识别 (针对 /calculate 接口)"""
        # 清理base64前缀
        if "base64," in img_b64:
            img_b64 = img_b64.split("base64,")[1]
            
        # 用户指定的数字计算接口
        target_url = f"{self.url.rstrip('/')}/calculate"

        for i in range(3):
            try:
                if DEBUG: printf(f"正在请求计算接口: {target_url} (第{i+1}次)", "DEBUG")
                
                # 构造 JSON 请求体
                # 常见的 ddddocr 服务 /calculate 接口通常接收 {"image": "base64..."}
                payload = {"image": img_b64}
                
                # 发送请求
                r = requests.post(target_url, json=payload, timeout=15)
                
                if DEBUG: printf(f"计算服务响应: [{r.status_code}] {r.text}", "DEBUG")
                
                if r.status_code == 200:
                    # 获取原始文本
                    res_text = r.text.strip()
                    
                    # 尝试解析 JSON 格式的返回 (例如 {"result": 10} 或 {"data": "10"})
                    try:
                        js = r.json()
                        if isinstance(js, dict):
                            if 'result' in js: res_text = str(js['result'])
                            elif 'data' in js: res_text = str(js['data'])
                            elif 'msg' in js and js.get('code') == 0: res_text = str(js['msg'])
                    except:
                        # 解析失败说明可能是纯文本直接返回
                        pass
                    
                    # 去除可能存在的引号
                    res_text = res_text.replace('"', '').replace("'", "")
                    
                    if DEBUG: printf(f"计算结果: {res_text}", "INFO")
                    return True, res_text
                
                elif r.status_code == 404:
                    if DEBUG: printf(f"接口 {target_url} 不存在 (404)", "WARN")
                else:
                    if DEBUG: printf(f"服务内部错误: {r.text[:100]}", "WARN")
                    
            except Exception as e:
                if DEBUG: printf(f"计算请求异常: {e}", "WARN")
                time.sleep(0.5)
                
        return False, "识别超时"

###################### 慧生活798核心类 (HSH) ######################
_SCORE_SUMMARY_CACHE = {}
_SCORE_SUMMARY_CACHE_TTL = 60


class HSH:

    def _get_remote_sign(self, ad_id, uid, platform="app", no_time=False, token=None, login_payload=None, login_mode="login"):
        SIGN_API_URL = "https://yuhualhh.250666.xyz/api/huishenghuo_sign.php"
        SIGN_API_KEY = "feiwu-cnmb-nmsl"

        if login_payload is not None:
            payload = {
                "apiKey": SIGN_API_KEY,
                "mode": login_mode,
                "payload": login_payload,
                "uid": str(uid),
                "token": str(self.token if token is None else token),
            }
        else:
            payload = {
                "adId": ad_id,
                "uid": str(uid),
                "token": str(self.token if token is None else token),
                "apiKey": SIGN_API_KEY,
                "platform": "mp" if platform in ("zfb", "mp") else "app",
            }
            if no_time:
                payload["noTime"] = True
    
        for i in range(3):
            try:
                if DEBUG:
                    printf(f"\n===== [REMOTE SIGN REQUEST START] =====", "DEBUG")
                    printf(f"METHOD: POST | URL: {SIGN_API_URL}", "DEBUG")
                    printf(f"BODY(JSON): {json.dumps(payload, ensure_ascii=False)}", "DEBUG")
    
                res = requests.post(
                    SIGN_API_URL,
                    json=payload,
                    headers={
                        "Content-Type": "application/json"
                    },
                    timeout=15
                )
    
                if DEBUG:
                    printf(f"----- [REMOTE SIGN RESPONSE - Attempt {i+1}] -----", "DEBUG")
                    printf(f"STATUS: {res.status_code}", "DEBUG")
                    printf(f"RSP HEADERS: {json.dumps(dict(res.headers), ensure_ascii=False)}", "DEBUG")
                    try:
                        printf(f"RSP BODY: {json.dumps(res.json(), ensure_ascii=False)}", "DEBUG")
                    except:
                        printf(f"RSP BODY: {res.text[:1000]}", "DEBUG")
                    printf(f"===== [REMOTE SIGN REQUEST END] =====\n", "DEBUG")
    
                if res.status_code != 200:
                    if i < 2:
                        time.sleep(2)
                        continue
                    return ""
    
                data = res.json()
                if data.get("code") == 0 and data.get("sign"):
                    return str(data.get("sign"))
    
                if i < 2:
                    time.sleep(2)
                    continue
            except Exception as e:
                if DEBUG:
                    printf(f"远程签名请求异常: {e}", "WARN")
                if i < 2:
                    time.sleep(2)
                    continue
    
        return ""

    def _get_login_sign(self, payload_obj, mode="login"):
        return self._get_remote_sign(
            "", "", platform="mp", token="", login_payload=payload_obj, login_mode=mode
        )

    def __init__(self, token, session=None, platform="app", login=False):
        self.session = session or requests.Session()
        self.token = token
        self.platform = platform
        # 配置固定请求头 (按登录平台选择)
        if platform == "zfb":
            self.headers = {
                "Authorization": self.token,
                "ApplicationType": "1,5",
                "VersionCode": "2.0.190" if login else "2.0.175",
                "x-release-type": "ONLINE",
                "alipayMiniMark": "1ZxYH945puiakh7m2yDcX+Dej067vmY/qfe6yORlQlIZWWiuTvpKpHx9t9009Lfz2j/PolGxbV6wcdJEpTRmt6QaUTKpvy5JrWJcv/tw8iE=",
                "Referer": "https://2019061465519660.hybrid.alipay-eco.com/2019061465519660/0.2.2609141412.57/index.html",
                "User-Agent": "Mozilla/5.0 (Linux; Android 15; RMX5060 Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.6478.122 Mobile Safari/537.36 NebulaSDK/1.8.100112 Nebula AlipayDefined(nt:5G,ws:425|0|2.9750001,ac:sp) AliApp(AP/12.12.26.8100) AlipayClient/12.12.26.8100 Language/zh-Hans isConcaveScreen/true Region/CN Ariver/12.12.26.8100",
                "Accept": "*/*",
                "Host": "i.ilife798.com"
            }
        elif platform == "wx":
            self.headers = {
                "Authorization": self.token,
                "ApplicationType": "1,3",
                "VersionCode": "3.0.01",
                "content-type": "application/json",
                "Referer": "https://servicewechat.com/wx323c760258f7b5a4/17/page-frame.html",
                "User-Agent": "Mozilla/5.0 (Linux; Android 15; RMX5060 Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.189 Mobile Safari/537.36 XWEB/1500213 MMWEBSDK/20260604 MMWEBID/1393 MicroMessenger/8.0.77.3160(0x28004D32) WeChat/arm64 Weixin NetType/5G Language/zh_CN ABI/arm64 MiniProgramEnv/android",
                "Host": "i.ilife798.com"
            }
        else:
            self.headers = {
                "Authorization": self.token,
                "ApplicationType": "1,1",
                "VersionCode": "3.1.9",
                "user-agent": "Android_ilife798_3.1.9",
                "Accept-Language": "zh-Hans-CN;q=1",
                "Host": "i.ilife798.com"
            }
        self.stop_reason = None

    def _send_request(self, method, url, **kwargs):
        kwargs['session'] = self.session
        # 合并 Header (大小写不敏感，避免 app 头的 user-agent 残留)
        req_headers = self.headers.copy()
        if 'headers' in kwargs:
            for k, v in kwargs['headers'].items():
                # 先删掉已有的同名 key（忽略大小写）
                for old_k in list(req_headers.keys()):
                    if old_k.lower() == k.lower():
                        del req_headers[old_k]
                req_headers[k] = v
            del kwargs['headers']
        req_headers = {k: v for k, v in req_headers.items()
                       if not (k.lower() == 'authorization' and not v)}
        
        try:
            return send_request_global(method, url, headers=req_headers, **kwargs)
        except Exception:
            return None

    def send_sms_with_captcha(self, phone):
        """
        获取图形验证码 -> 识别计算 -> 发送短信
        包含3次重试机制
        """
        ocr = DdddocrClient()
        
        for attempt in range(1, 4):
            try:
                if DEBUG: printf(f"--- 开始第 {attempt} 次获取验证码 ---", "INFO")
                # 1. 生成随机参数 s 和 r
                s_val = random.random()
                r_val = int(time.time() * 1000)
                
                # 2. 获取验证码图片
                img_url = f"https://i.ilife798.com/api/v1/captcha/?s={s_val}&r={r_val}"
                img_res = self._send_request('GET', img_url)
                if not img_res or img_res.status_code != 200:
                    if DEBUG: printf("获取验证码图片失败", "WARN")
                    continue
                
                img_b64 = base64.b64encode(img_res.content).decode()
                
                # 3. 识别验证码 (ddddocr 会自动处理算术题)
                ocr_ok, ocr_result = ocr.classification(img_b64)
                if not ocr_ok:
                    if DEBUG: printf("OCR识别失败", "WARN")
                    continue
                
                if DEBUG: printf(f"OCR识别结果: {ocr_result}", "INFO")

                # 4. 请求发送短信
                send_url = "https://i.ilife798.com/api/v1/acc/login/code"
                payload = {
                    "authCode": ocr_result, # 识别结果
                    "s": s_val,             # 必须与获取图片时的 s 一致
                    "un": phone
                }
                
                send_res = self._send_request('POST', send_url, json=payload)
                if not send_res:
                    continue
                    
                res_data = send_res.json()
                if res_data.get('code') == 0:
                    if DEBUG: printf("短信发送接口返回成功", "INFO")
                    return True, "发送成功"
                elif res_data.get('code') == -2:
                    # 验证码错误，继续重试
                    if DEBUG: printf(f"第{attempt}次验证码识别错误: {ocr_result}, 服务器返回: {res_data}", "WARN")
                    continue
                else:
                    if DEBUG: printf(f"发送失败，未知错误: {res_data}", "WARN")
                    return False, res_data.get('msg', '发送失败')
                    
            except Exception as e:
                if DEBUG: printf(f"发送短信异常: {e}", "ERROR")
                time.sleep(1)
                
        return False, "验证码识别失败次数过多，请稍后再试"

    def login_by_sms_code(self, phone, sms_code, open_code=None):
        if DEBUG: printf(f"正在尝试短信登录: {phone} code={sms_code}", "INFO")
        is_app = (self.platform == "app")
        payload = {
            "authCode": sms_code,
            "un": phone
        }
        if open_code and not is_app:
            payload["openCode"] = str(open_code)
        sign = self._get_login_sign(payload, mode="login_app" if is_app else "login")
        if not sign:
            return False, "获取登录签名失败"
        url = "https://i.ilife798.com/api/v1/acc/login"
        if sign:
            url += f"?sign={sign}"

        try:
            res = self._send_request('POST', url, json=payload)
            if res:
                data = res.json()
                if data.get('code') == 0:
                    # 提取 Token
                    token = data.get('data', {}).get('al', {}).get('token')
                    if token:
                        if DEBUG: printf("短信登录成功，获取到Token", "INFO")
                        return True, token
                if DEBUG: printf(f"短信登录失败: {data}", "WARN")
                return False, data.get('msg', '登录失败')
        except Exception as e:
            if DEBUG: printf(f"短信登录异常: {e}", "ERROR")
            return False, str(e)
        return False, "网络请求无响应"

    def check_token(self):
        """检测CK有效性"""
        url = "https://i.ilife798.com/api/v1/acc/stat"
        res = self._send_request('GET', url)
        if not res: return False, "网络请求失败"
        
        try:
            data = res.json()
            if data.get('code') == 0:
                return True, "有效"
            else:
                return False, data.get('msg', 'Token无效')
        except:
            return False, "解析响应失败"

    def get_user_info(self):
        """获取手机号和用户ID"""
        url = "https://i.ilife798.com/api/v1/ui/app/master"
        res = self._send_request('GET', url)
        if not res: return False, {}

        try:
            data = res.json()
            if data.get('code') == 0:
                account = data.get('data', {}).get('account', {})
                return True, {
                    "phone": account.get('pn', ''),
                    "uid": account.get('id', '')
                }
        except: pass
        return False, {}

    def get_use_score(self):
        """读取积分自动抵扣开关状态 (master 接口 account.useScore, 1=开 0=关)"""
        url = "https://i.ilife798.com/api/v1/ui/app/master"
        res = self._send_request('GET', url)
        if not res: return False, "网络请求失败"
        try:
            data = res.json()
            if data.get('code') != 0:
                return False, data.get('msg', '查询失败')
            account = data.get('data', {}).get('account', {})
            return True, int(account.get('useScore', 0))
        except Exception:
            return False, "响应解析失败"

    def fetch_all_score_history(self):
        base = "https://i.ilife798.com/api/v1/acc/score/score-lst"
        records = []
        total = 0
        page = 0
        page_size = 5000
        while page < 50:
            url = f"{base}?page={page}&size={page_size}&hasCount=true"
            res = self._send_request('GET', url)
            if not res:
                return None
            try:
                data = res.json()
            except Exception:
                return None
            if not isinstance(data, dict) or data.get('code') != 0:
                return None
            batch = data.get('data') or []
            if page == 0:
                try:
                    total = int(data.get('size') or 0)
                except Exception:
                    total = 0
            records.extend(batch)
            if not batch:
                break
            if total and len(records) >= total:
                break
            if len(batch) < page_size:
                if total and len(records) < total and page_size > 1000:
                    page = len(records) // 1000
                    page_size = 1000
                    continue
                break
            if page_size == 5000:
                page = len(records) // 1000
                page_size = 1000
            else:
                page += 1
        return records

    def get_total_score_from_history(self, force=False):
        cache_key = str(self.token)
        now_ts = time.time()
        if not force:
            cached = _SCORE_SUMMARY_CACHE.get(cache_key)
            if cached and now_ts - cached['ts'] < _SCORE_SUMMARY_CACHE_TTL:
                return True, cached['total']

        records = self.fetch_all_score_history()
        if records is None:
            return False, {"code": None, "msg": "积分流水读取失败"}

        earn = 0.0
        spend = 0.0
        today_earn = 0.0
        today_spend = 0.0
        now = datetime.now()
        today_start_ms = int(datetime(now.year, now.month, now.day).timestamp() * 1000)

        for item in records:
            data_obj = item.get('data') or {}
            try:
                score_val = float(data_obj.get('score') or 0)
            except Exception:
                score_val = 0.0
            is_spend = item.get('type') == 107 or data_obj.get('type') == 107
            if is_spend:
                try:
                    spend_val = float(data_obj.get('spend') or data_obj.get('score') or 0)
                except Exception:
                    spend_val = abs(score_val)
                spend += abs(spend_val)
            else:
                earn += score_val

            try:
                ctime = int(item.get('ctime') or 0)
            except Exception:
                ctime = 0
            if ctime >= today_start_ms:
                if is_spend:
                    try:
                        today_spend += float(data_obj.get('spend', data_obj.get('score', 0)) or 0)
                    except Exception:
                        pass
                else:
                    today_earn += score_val

        total = earn - spend
        total_str = str(int(total)) if float(total).is_integer() else str(total)
        today_str = str(int(today_earn)) if float(today_earn).is_integer() else str(today_earn)
        spend_str = str(int(today_spend)) if float(today_spend).is_integer() else str(today_spend)
        _SCORE_SUMMARY_CACHE[cache_key] = {
            'total': total_str,
            'today': today_str,
            'spend': spend_str,
            'ts': now_ts,
        }
        return True, total_str

    def get_total_score(self, force=False):
        """获取当前总积分; 返回 (True, 分数) 或 (False, 失败响应 dict, 保留 code 供上层判定)"""
        url = "https://i.ilife798.com/api/v1/acc/score/mission-lst"
        res = self._send_request('GET', url)
        if not res: return False, {"code": None, "msg": "网络请求失败"}

        try:
            data = res.json()
        except Exception:
            return False, {"code": None, "msg": "响应解析失败"}
        if not isinstance(data, dict):
            return False, {"code": None, "msg": "响应格式异常"}
        if data.get('code') == 0:
            payload = data.get('data') or {}
            acc = payload.get('accScoreRsp') if isinstance(payload, dict) else None
            score = acc.get('score') if isinstance(acc, dict) else None
            if score is not None:
                return True, str(score)
            if DEBUG:
                printf("mission-lst 无 data，回退到积分流水计算总积分", "WARN")
            return self.get_total_score_from_history(force=force)
        return False, data

    def get_today_score(self):
        """获取今日获取的积分; 返回 (True, 分数) 或 (False, 失败响应 dict)"""
        cached = _SCORE_SUMMARY_CACHE.get(str(self.token))
        if cached and time.time() - cached['ts'] < _SCORE_SUMMARY_CACHE_TTL:
            return True, cached['today']
        url = "https://i.ilife798.com/api/v1/acc/score/score-lst?page=0&size=20&hasCount=true"
        res = self._send_request('GET', url)
        if not res: return False, {"code": None, "msg": "网络请求失败"}

        try:
            data = res.json()
            if data.get('code') == 0:
                score_list = data.get('data', [])
                
                # 获取今日零点的时间戳 (毫秒)
                now = datetime.now()
                today_start = datetime(now.year, now.month, now.day)
                today_start_ms = int(today_start.timestamp() * 1000)
                
                today_sum = 0
                for item in score_list:
                    # ctime是记录时间
                    ctime = item.get('ctime', 0)
                    if ctime >= today_start_ms:
                        # 排除消费类记录(type=107为"用户消费积分", 该类score为支出不应计入今日获取)
                        item_type = item.get('type')
                        data_obj = item.get('data', {}) or {}
                        if item_type == 107 or data_obj.get('type') == 107:
                            continue
                        # 累加分数, item['data']['score']可能是字符串
                        try:
                            score_val = float(data_obj.get('score', 0))
                            today_sum += score_val
                        except: pass
                
                # 如果是整数则转int去掉小数点
                if today_sum.is_integer():
                    return True, str(int(today_sum))
                return True, str(today_sum)
        except Exception:
            return False, {"code": None, "msg": "响应解析失败"}
        return False, data if isinstance(data, dict) else {"code": None, "msg": "响应格式异常"}
      
    def get_today_spend(self):
        """获取今日消耗的积分; 返回 (True, 分数) 或 (False, 失败响应 dict)"""
        cached = _SCORE_SUMMARY_CACHE.get(str(self.token))
        if cached and time.time() - cached['ts'] < _SCORE_SUMMARY_CACHE_TTL:
            return True, cached['spend']
        url = "https://i.ilife798.com/api/v1/acc/score/score-lst?page=0&size=20&hasCount=true"
        res = self._send_request('GET', url)
        if not res: return False, {"code": None, "msg": "网络请求失败"}

        try:
            data = res.json()
            if data.get('code') == 0:
                score_list = data.get('data', [])
                
                # 获取今日零点的时间戳 (毫秒)
                now = datetime.now()
                today_start = datetime(now.year, now.month, now.day)
                today_start_ms = int(today_start.timestamp() * 1000)
                
                today_spend = 0
                for item in score_list:
                    # ctime是记录时间
                    ctime = item.get('ctime', 0)
                    if ctime >= today_start_ms:
                        # 仅统计消费类记录(type=107为"用户消费积分", 该类score/spend为支出)
                        item_type = item.get('type')
                        data_obj = item.get('data', {}) or {}
                        if item_type != 107 and data_obj.get('type') != 107:
                            continue
                        # 累加消费积分, 优先取spend字段, 回退到score
                        try:
                            spend_val = float(data_obj.get('spend', data_obj.get('score', 0)) or 0)
                            today_spend += spend_val
                        except: pass
                
                # 如果是整数则转int去掉小数点
                if today_spend.is_integer():
                    return True, str(int(today_spend))
                return True, str(today_spend)
        except Exception:
            return False, {"code": None, "msg": "响应解析失败"}
        return False, data if isinstance(data, dict) else {"code": None, "msg": "响应格式异常"}
        
    def query_assets(self):
        """聚合查询资产; 返回 (True, dict) 或 (False, 失败响应 dict, 由上层 _fail_reason 判定)"""
        info_ok, info = self.get_user_info()
        total_ok, total = self.get_total_score()
        today_ok, today = self.get_today_score()
        spend_ok, today_spend = self.get_today_spend()

        # 任一取数失败必须把原始响应透传上去, 不能回落成 0 积分
        if not total_ok:
            return False, total
        if not today_ok:
            return False, today
        if not spend_ok:
            return False, today_spend

        return True, {
            "total_score": total,
            "today_score": today,
            "today_spend": today_spend,
            "valid": True
        }

    ###################### 设备管理 API ######################
    def qr_use(self, did):
        """扫码解析设备 (对应抓包 /api/v1/qr/use)"""
        url = f"https://i.ilife798.com/api/v1/qr/use?id={did}"
        res = self._send_request('GET', url)
        if not res: return False, "网络请求失败"
        try:
            data = res.json()
        except Exception:
            return False, "响应解析失败"
        if data.get('code') != 0:
            return False, data.get('msg', f"扫码失败 code={data.get('code')}")
        return True, data.get('data', {})

    def acc_upt(self, use_score=1):
        """设置积分自动抵扣开关 (对应抓包 POST /api/v1/acc/upt, 幂等: useScore=1开 0关)"""
        url = "https://i.ilife798.com/api/v1/acc/upt"
        res = self._send_request('POST', url, json={"useScore": use_score})
        if not res: return False, "网络请求失败"
        try:
            data = res.json()
        except Exception:
            return False, "响应解析失败"
        if data.get('code') != 0:
            return False, data.get('msg', f"设置失败 code={data.get('code')}")
        return True, data.get('data', {})

    def dev_status(self, did):
        """查询设备状态 (对应抓包 /api/v1/ui/app/dev/status)"""
        url = f"https://i.ilife798.com/api/v1/ui/app/dev/status?did={did}&more=false"
        res = self._send_request('GET', url)
        if not res: return False, "网络请求失败"
        try:
            data = res.json()
        except Exception:
            return False, "响应解析失败"
        if data.get('code') != 0:
            return False, data.get('msg', f"查询失败 code={data.get('code')}")
        return True, data.get('data', {})

    def dev_home(self, did):
        """主页设备完整信息 (对应抓包 /api/v1/ui/app/dev/home/1, 含名称/场所/位置/型号)"""
        url = f"https://i.ilife798.com/api/v1/ui/app/dev/home/1?did={did}&apply=6"
        res = self._send_request('GET', url)
        if not res: return False, "网络请求失败"
        try:
            data = res.json()
        except Exception:
            return False, "响应解析失败"
        if data.get('code') != 0:
            return False, data.get('msg', f"查询失败 code={data.get('code')}")
        return True, data.get('data', {})

    def dev_start(self, did):
        url = f"https://i.ilife798.com/api/v1/dev/start?did={did}&upgrade=true&ptype=91&rcp=false"
        res = self._send_request('GET', url)
        if not res: return False, "网络请求失败"
        try:
            data = res.json()
        except Exception:
            return False, "响应解析失败"
        if data.get('code') != 0:
            code = data.get('code')
            msg = data.get('msg') or f"开始失败 code={code}"
            if code == -21:
                msg = "仅通过APP手机号登录方式可用"
            elif code == -99:
                msg = "登录状态已过期，请重新登录"
            return False, msg
        return True, data.get('data', {})

    def dev_end(self, did):
        """立即结算/结束计费 (对应抓包 /api/v1/dev/end)"""
        url = f"https://i.ilife798.com/api/v1/dev/end?did={did}&rcp=false"
        res = self._send_request('GET', url)
        if not res: return False, "网络请求失败"
        try:
            data = res.json()
        except Exception:
            return False, "响应解析失败"
        if data.get('code') != 0:
            return False, data.get('msg', f"结束结算失败 code={data.get('code')}")
        return True, data.get('data', {})

    def bill_list(self, did, status=1):
        """账单列表 (对应抓包 /api/v1/bill/lst-owner)"""
        url = f"https://i.ilife798.com/api/v1/bill/lst-owner?page=0&size=20&hasCount=true&status={status}"
        res = self._send_request('GET', url)
        if not res: return False, "网络请求失败"
        try:
            data = res.json()
        except Exception:
            return False, "响应解析失败"
        if data.get('code') != 0:
            return False, data.get('msg', f"账单查询失败 code={data.get('code')}")
        return True, data.get('data', [])

    def close(self):
        if self.session:
            self.session.close()
            self.session = None

    def _is_rate_limited(self, data):
        if not data:
            return False
        if data.get("code") == -98:
            return True
        msg = str(data.get("msg") or "")
        return "频繁" in msg

    def _is_fatal_biz_error(self, data):
        if not data:
            return False
        if self._is_rate_limited(data):
            return False
        code = data.get("code")
        msg = str(data.get("msg") or "")
        if code == -99:
            return True
        fatal_keywords = ("登录状态已过期", "登录过期", "token", "未登录", "签名", "验签", "参数")
        return any(k in msg for k in fatal_keywords)

    def _fail_reason(self, resp):
        """按响应判定"该给用户看什么原因"(供查询/展示类接口复用, 不要用它决定是否熔断)

        判定顺序: code(-98 限频 / -99 登录过期) 优先, msg 关键词兜底, 最后原样回显服务端 msg。
        与 _is_fatal_biz_error 的区别: 那个是"要不要停止后续任务"(宁滥勿缺),
        这个是"跟用户怎么解释"(宁准勿滥), 所以不能直接复用同一套关键词。
        """
        resp = resp if isinstance(resp, dict) else {"code": None, "msg": resp}
        code = resp.get('code')
        msg = str(resp.get('msg') or '').strip()
        if self._is_rate_limited(resp):
            return f"{msg or '请求过于频繁'}，请稍后再试"
        low = msg.lower()
        if code == -99 or any(k in msg for k in ("过期", "失效", "未登录")) or "token" in low:
            return "登录凭证已失效，请重新登录"
        if msg:
            return msg
        return f"读取失败(code={code})" if code is not None else "网络请求失败"

    def _mark_stop(self, reason):
        if reason and not self.stop_reason:
            self.stop_reason = str(reason)
            if DEBUG:
                printf(f"账号中止: {self.stop_reason}", "WARN")

    def _request_safe(self, method, url, platform="app", data=None, retry=2):
        # 与 HSH.__init__ 里 ZFB 分支保持一致（已在登录接口验证有效）
        ALIPAY_MARK = "1ZxYH945puiakh7m2yDcX+Dej067vmY/qfe6yORlQlIZWWiuTvpKpHx9t9009Lfz2j/PolGxbV6wcdJEpTRmt6QaUTKpvy5JrWJcv/tw8iE="
        ALIPAY_UA   = "Mozilla/5.0 (Linux; Android 15; RMX5060 Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.6478.122 Mobile Safari/537.36 NebulaSDK/1.8.100112 Nebula AlipayDefined(nt:5G,ws:425|0|2.9750001,ac:sp) AliApp(AP/12.12.26.8100) AlipayClient/12.12.26.8100 Language/zh-Hans isConcaveScreen/true Region/CN Ariver/12.12.26.8100"
        req_headers = {}
        if platform == "zfb":
            req_headers = {
                "ApplicationType": "1,5",
                "VersionCode": "2.0.175",                      # ← 与登录一致
                "x-release-type": "ONLINE",
                "alipayMiniMark": ALIPAY_MARK,                  # ← 与登录一致
                "Referer": "https://2019061465519660.hybrid.alipay-eco.com/2019061465519660/0.2.2609141412.57/index.html",
                "User-Agent": ALIPAY_UA,                        # ← 与登录一致
                "Accept": "*/*",
            }
        for i in range(retry):
            try:
                res = self._send_request(method, url, json=data, headers=req_headers)
                if not res:
                    if i < retry - 1:
                        time.sleep(1)
                        continue
                    return None
                if "频繁" in res.text:
                    try:
                        data_obj = res.json()
                    except Exception:
                        data_obj = {"code": -98, "msg": "请求过于频繁"}
                    if DEBUG:
                        printf("触发请求过于频繁，交由上层等待重试", "WARN")
                    return data_obj
                try:
                    data_obj = res.json()
                except Exception:
                    if i < retry - 1:
                        time.sleep(1)
                        continue
                    return None
                if self._is_fatal_biz_error(data_obj):
                    self._mark_stop(data_obj.get("msg") or f"业务错误 code={data_obj.get('code')}")
                return data_obj
            except Exception as e:
                if i == retry - 1 and DEBUG:
                    printf(f"请求失败: {e}", "ERROR")
                if i < retry - 1:
                    time.sleep(1)
        return None

    def get_score_history(self, page=0, size=50):
        url = f"https://i.ilife798.com/api/v1/acc/score/score-lst?page={page}&size={size}&hasCount=true"
        res = self._send_request('GET', url)
        if not res:
            return []
        try:
            data = res.json()
            return data.get("data", []) if data.get("code") == 0 else []
        except Exception:
            return []

    def get_week_signed_set(self, history):
        now = datetime.now()
        today = now.date()
        monday = today - timedelta(days=today.weekday())
        today_iso = today.isoweekday()

        signed_days = set()
        for item in history or []:
            data = item.get("data", {}) or {}
            ad_id = data.get("adId")
            if ad_id != "DAILY_CHECK_IN":
                continue

            wd = data.get("weekDay", data.get("weekday", 0))
            try:
                wd = int(wd or 0)
            except Exception:
                wd = 0

            ctime = item.get("ctime", 0) or 0
            r_date = None
            if ctime:
                try:
                    r_date = datetime.fromtimestamp(ctime / 1000).date()
                except Exception:
                    r_date = None

            if 1 <= wd <= 7:
                if r_date is None or r_date >= monday:
                    if wd <= today_iso:
                        signed_days.add(wd)
                continue

            if r_date and monday <= r_date <= today:
                signed_days.add(r_date.isoweekday())
        return signed_days

    def fetch_week_signed_set(self, max_pages=6, size=50):
        now = datetime.now()
        today = now.date()
        monday = today - timedelta(days=today.weekday())
        monday_ms = int(datetime(monday.year, monday.month, monday.day).timestamp() * 1000)
        today_iso = today.isoweekday()
        need = set(range(1, today_iso + 1))
        signed_days = set()

        for page in range(max(1, int(max_pages))):
            history = self.get_score_history(page=page, size=size)
            if not history:
                if DEBUG:
                    printf(f"签到历史翻页结束: page={page} 空页", "DEBUG")
                break

            page_signed = self.get_week_signed_set(history)
            if page_signed:
                signed_days.update(page_signed)

            oldest_ctime = None
            for item in history:
                ctime = item.get("ctime", 0) or 0
                try:
                    ctime = int(ctime)
                except Exception:
                    ctime = 0
                if ctime > 0 and (oldest_ctime is None or ctime < oldest_ctime):
                    oldest_ctime = ctime

            if DEBUG:
                printf(
                    f"签到历史 page={page}: 本页签到天={sorted(page_signed)} 累计={sorted(signed_days)} 最旧ctime={oldest_ctime}",
                    "DEBUG",
                )

            if need.issubset(signed_days):
                if DEBUG:
                    printf(f"签到历史早停: 本周已齐 {sorted(signed_days)}", "DEBUG")
                break

            if oldest_ctime is not None and oldest_ctime < monday_ms:
                if DEBUG:
                    printf("签到历史早停: 已越过本周一", "DEBUG")
                break

            if len(history) < size:
                if DEBUG:
                    printf(f"签到历史翻页结束: 最后一页 page={page} size={len(history)}", "DEBUG")
                break

        return signed_days

    def calculate_score_for_day(self, target_day, signed_set):
        """计算目标日期应得分数"""
        if target_day == 3:
            return 10 if {1, 2}.issubset(signed_set) else 5
        if target_day == 7:
            return 15 if {1, 2, 3, 4, 5, 6}.issubset(signed_set) else 5
        return 5

    def send_sign_in_request(self, weekday_iso, score, uid, is_retro=False):
        if self.stop_reason:
            return False, self.stop_reason
        rate_retry = 0
        while True:
            if self.stop_reason:
                return False, self.stop_reason
            sign = self._get_remote_sign("DAILY_CHECK_IN", uid, "zfb")
            if not sign:
                self._mark_stop("获取签名失败")
                return False, "获取签名失败"
            url = f"https://i.ilife798.com/api/v1/acc/score/score-send?sign={sign}&s=true"
            payload = {
                "adId": "DAILY_CHECK_IN",
                "addScore": score,
                "addScoreType": 3 if is_retro else 1,
                "weekday": weekday_iso
            }
            data = self._request_safe("POST", url, "zfb", payload)
            if data and data.get("code") == 0:
                tag = "补签" if is_retro else "签到"
                return True, f"{tag}成功({score}分)"
            msg = data.get("msg") if data else "未知"
            if self._is_rate_limited(data):
                if rate_retry >= 2:
                    self._mark_stop("请求过于频繁")
                    return False, "请求过于频繁"
                rate_retry += 1
                if DEBUG:
                    printf(f"签到触发频繁，等待30秒后重试({rate_retry}/2)...", "WARN")
                time.sleep(30)
                continue
            if self.stop_reason or self._is_fatal_biz_error(data):
                self._mark_stop(msg)
                return False, msg
            if score > 5:
                if DEBUG:
                    printf(f"高分签到失败({msg})，降级尝试 5 分...", "WARN")
                time.sleep(2)
                return self.send_sign_in_request(weekday_iso, 5, uid, is_retro)
            return False, msg

    def handle_sign_in_process(self, uid, task_logs, allow_retro=True):
        if self.stop_reason:
            return False

        signed_days = self.fetch_week_signed_set(max_pages=6, size=50)
        today_iso = datetime.now().isoweekday()
        has_action = False
        if DEBUG:
            printf(f"本周已签: {sorted(signed_days)} allow_retro={allow_retro}", "INFO")

        missed_days = [d for d in range(1, today_iso) if d not in signed_days] if allow_retro else []
        if missed_days:
            for d in missed_days:
                if self.stop_reason:
                    break
                target_score = self.calculate_score_for_day(d, signed_days)
                ok, msg = self.send_sign_in_request(d, target_score, uid, is_retro=True)
                if ok:
                    task_logs.append(f"🔧 补签周{d}: {msg}")
                    signed_days.add(d)
                    time.sleep(15) # 补签冷却
                    has_action = True
                else:
                    task_logs.append(f"❌ 补签周{d}失败: {msg}")
                    if self.stop_reason:
                        break
                    time.sleep(2)

        # 2. 今日签到
        if not self.stop_reason and today_iso not in signed_days:
            target_score = self.calculate_score_for_day(today_iso, signed_days)
            ok, msg = self.send_sign_in_request(today_iso, target_score, uid, is_retro=False)
            if ok:
                task_logs.append(f"🎨 今日签到: {msg}")
                has_action = True
                return True # 刚签到成功
            else:
                task_logs.append(f"❌ 签到失败: {msg}")
        else:
             # 如果日志列表为空且已签到，可以不记录，或者记录已完成
             pass
             
        return has_action

    def do_task_logic(self, task_key, current_count, task_config, uid, task_logs):
        if self.stop_reason:
            return
        cfg = task_config[task_key]
        remain = cfg["limit"] - current_count
        if remain <= 0:
            return
        if DEBUG:
            printf(f"执行 [{cfg['name']}] (剩余 {remain} 次)", "INFO")
        success_in_batch = 0
        fail_streak = 0
        for i in range(remain):
            if self.stop_reason:
                break
            rate_retry = 0
            while True:
                if self.stop_reason:
                    break
                sign = self._get_remote_sign(cfg["adId"], uid, cfg.get("platform", "app"))
                if not sign:
                    fail_streak += 1
                    self._mark_stop("获取签名失败")
                    task_logs.append(f"❌ {cfg['name']}: 获取签名失败")
                    break
                s_param = "true" if cfg.get("platform") == "zfb" else "1"
                url = f"https://i.ilife798.com/api/v1/acc/score/score-send?sign={sign}&s={s_param}"
                payload = {"adId": cfg["adId"]}
                if task_key == "APP_VIDEO":
                    payload.update({"addScore": 30, "addScoreType": 4, "type": 101})
                elif task_key == "APP_AD":
                    payload.update({"addScore": 10, "addScoreType": 4, "type": 101})
                else:
                    payload.update({"type": 101})
                data = self._request_safe("POST", url, cfg["platform"], payload)
                if data and data.get("code") == 0:
                    success_in_batch += 1
                    fail_streak = 0
                    if i < remain - 1:
                        time.sleep(15) # 任务内冷却
                    break
                msg = data.get("msg") if data else "网络异常"
                if self._is_rate_limited(data):
                    if rate_retry >= 2:
                        self._mark_stop("请求过于频繁")
                        task_logs.append(f"❌ {cfg['name']}: 请求过于频繁(已重试2次)")
                        break
                    rate_retry += 1
                    if DEBUG:
                        printf(f"[{cfg['name']}] 触发频繁，等待30秒后重试({rate_retry}/2)...", "WARN")
                    time.sleep(30)
                    continue
                fail_streak += 1
                if self.stop_reason or self._is_fatal_biz_error(data):
                    self._mark_stop(msg)
                    task_logs.append(f"❌ {cfg['name']}: {msg}")
                    break
                if fail_streak >= 2:
                    task_logs.append(f"❌ {cfg['name']}: 连续失败停止({msg})")
                    break
                time.sleep(2)
                break
        if success_in_batch > 0:
            task_logs.append(f"▶️ {cfg['name']}: 执行{success_in_batch}次")

    def run_daily_tasks(self, phone_mask):
        """执行日常任务 (全流程3轮重试 + 严格顺序 + 状态回溯)"""
        info_ok, info_data = self.get_user_info()
        uid = info_data.get('uid', '')
        if not uid: 
            return f"=====慧生活运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 获取用户信息失败\n======================="
    
        task_logs = []
        
        # 任务配置 (与脚本保持一致)
        TASKS_CONFIG = {
            "CHECKIN":    {"name": "每日签到",  "adId": "DAILY_CHECK_IN", "limit": 1, "platform": "zfb", "score": 5},
            "APP_VIDEO":  {"name": "APP看视频", "adId": "1705776998",     "limit": 5, "platform": "zfb", "score": 30},
            "APP_AD":     {"name": "APP看广告", "adId": "popsreen",       "limit": 5, "platform": "zfb", "score": 10},
            "ZFB_VIDEO":  {"name": "ZFB看视频", "adId": "ad_tiny_2019061465519660_202402222200083035", "limit": 5, "platform": "zfb", "score": 20},
            "ZFB_WAIMAI": {"name": "ZFB点外卖", "adId": "1435961748560572416", "limit": 1, "platform": "zfb", "score": 10}
        }
        TASK_ORDER = ["APP_VIDEO", "APP_AD", "ZFB_VIDEO", "ZFB_WAIMAI"]
    
        last_progress_snapshot = None
        for round_idx in range(1, 3):
            if self.stop_reason:
                if DEBUG: printf(f"--- 第 {round_idx} 轮跳过: {self.stop_reason} ---", "WARN")
                break

            if DEBUG: printf(f"--- 第 {round_idx} 轮检测 ---", "INFO")
            
            did_sign = self.handle_sign_in_process(uid, task_logs, allow_retro=(round_idx == 1))
            if self.stop_reason:
                break
            
            # 2. 获取任务进度 (反推状态)
            history = self.get_score_history()
            today_date = datetime.now().date()
            progress = {k: 0 for k in TASKS_CONFIG.keys()}
            
            for item in history:
                ctime = item.get("ctime", 0)
                if not ctime: continue
                if datetime.fromtimestamp(ctime / 1000).date() != today_date: continue
                ad_id = item.get("data", {}).get("adId")
                for k, cfg in TASKS_CONFIG.items():
                    if ad_id == cfg["adId"]:
                        progress[k] += 1
            
            # 修正签到进度 (防止刚签完没更新到列表)
            if did_sign: progress["CHECKIN"] = 1
    
            # 3. 检查是否全部完成
            if all(progress.get(k, 0) >= v['limit'] for k, v in TASKS_CONFIG.items()):
                break # 全部完成，提前结束

            progress_snapshot = tuple(progress.get(k, 0) for k in TASKS_CONFIG.keys())
            if last_progress_snapshot == progress_snapshot and not did_sign:
                if DEBUG: printf("进度无变化，停止补漏轮次", "WARN")
                break
            last_progress_snapshot = progress_snapshot
    
            # 4. 如果刚签到过，休息一下再做任务 (防频繁)
            if did_sign:
                time.sleep(15)
    
            # 5. 执行通用任务
            for i, key in enumerate(TASK_ORDER):
                if self.stop_reason:
                    break

                current_done = progress.get(key, 0)
                limit = TASKS_CONFIG[key]['limit']
                
                if current_done < limit:
                    # 如果不是第一个任务且前面有任务执行，或者刚签到完，增加间隔
                    if i > 0 and progress.get(TASK_ORDER[i-1], 0) < TASKS_CONFIG[TASK_ORDER[i-1]]['limit']:
                        time.sleep(15) # 任务切换冷却
                    
                    self.do_task_logic(key, current_done, TASKS_CONFIG, uid, task_logs)

        # === 最终统计生成报告 ===
        # 再次查询确保数据最新
        history = self.get_score_history()
        final_progress = {k: 0 for k in TASKS_CONFIG.keys()}
        today_date = datetime.now().date()
        for item in history:
            ctime = item.get("ctime", 0)
            if not ctime: continue
            if datetime.fromtimestamp(ctime / 1000).date() != today_date: continue
            ad_id = item.get("data", {}).get("adId")
            for k, cfg in TASKS_CONFIG.items():
                if ad_id == cfg["adId"]: final_progress[k] += 1
        
        total_tasks_count = len(TASKS_CONFIG)
        finished_tasks_count = 0
        report_lines = []
        
        # 签到状态
        checkin_done = final_progress.get("CHECKIN", 0)
        if checkin_done >= 1:
            finished_tasks_count += 1
            report_lines.append("🎨 每日签到")
        else:
            report_lines.append("❌ 每日签到")
    
        # 其他任务状态
        icon_map = {"APP_VIDEO": "📝", "APP_AD": "🔆", "ZFB_VIDEO": "⛱️", "ZFB_WAIMAI": "🎯"}
        for key in TASK_ORDER:
            cfg = TASKS_CONFIG[key]
            done = final_progress.get(key, 0)
            if done >= cfg['limit']:
                finished_tasks_count += 1
                report_lines.append(f"{icon_map.get(key, '🔹')} {cfg['name']}")
            else:
                report_lines.append(f"❌ {cfg['name']} ({done}/{cfg['limit']})")
    
        final_msg = f"=====慧生活运行结果=====\n🤪 账号: {phone_mask}\n💫 结果: 完成{finished_tasks_count}/{total_tasks_count}\n------------------\n"
        final_msg += "\n".join(report_lines)
        if self.stop_reason:
            final_msg += f"\n⚠️ 中止原因: {self.stop_reason}"
        final_msg += "\n======================="
        return final_msg
        

def gen_unique_id(prefix=""):
    timestamp = int(time.time() * 1_000_000)
    return f"{prefix}{timestamp}"

###################### 设备管理模块（模拟扫码设备） ######################
# 设备固定保存在个人数据桶 yuhua_hsh_dev / 按 userid 存放
DEV_BUCKET = 'yuhua_hsh_dev'
DEV_BUCKET_LIST = 'yuhua_hsh_dev_list'

def _dev_list_raw():
    return eval(middleware.bucketGet(DEV_BUCKET_LIST, userid) or '[]')

def _dev_list():
    """返回 (devices, devs_by_id)"""
    devs = _dev_list_raw()
    return devs, {d.get('id'): d for d in devs}

def _dev_save(devs):
    middleware.bucketSet(DEV_BUCKET_LIST, userid, str(devs))

def _dev_get(did):
    devs = _dev_list_raw()
    for d in devs:
        if d.get('id') == did:
            return d
    return None

def _dev_patch(did, **fields):
    devs = _dev_list_raw()
    for d in devs:
        if d.get('id') == did:
            d.update(fields)
            _dev_save(devs)
            return d
    return None

def _dev_login_accounts():
    """返回所有已登录的账号 uid 列表"""
    accounts = eval(uservalue or '[]')
    return [str(a) for a in accounts if middleware.bucketGet('yuhua_hsh_token', str(a))]

def _dev_token_for(d, uid=None):
    """取指定账号(或默认第一个已登录账号)的 token"""
    if uid:
        return middleware.bucketGet('yuhua_hsh_token', str(uid))
    uids = _dev_login_accounts()
    return middleware.bucketGet('yuhua_hsh_token', str(uids[0])) if uids else None

def _dev_token_uid(d, uid=None):
    """取实际使用的账号 uid (指定或默认第一个已登录账号)"""
    if uid:
        return str(uid)
    uids = _dev_login_accounts()
    return uids[0] if uids else None

def _dev_add_uid(d, uid):
    """把账号并入设备归属列表"""
    uids = d.get('uids') or []
    if uid not in uids:
        uids.append(uid)
    _dev_patch(d.get('id'), uids=uids)

def _dev_mark_session(did, on_off, uid=None):
    if on_off:
        _dev_patch(did, use_ts=int(time.time() * 1000), use_uid=str(uid or ''))
    else:
        _dev_patch(did, use_ts=0, use_uid='')

def _dev_is_using(d):
    ts = int(d.get('use_ts') or 0)
    return ts > 0 and (time.time() * 1000 - ts) < 30 * 60 * 1000

def _mask_did(did):
    s = str(did or '')
    if len(s) > 12:
        return s[:6] + '****' + s[-4:]
    return s

def _fetch_dev_view(hsh, did):
    """拉取设备实时信息, 返回 (ok, msg, view dict)
    dev/status 提供实时余额(subs), home/1 提供名称/场所/位置/型号, 合并两者"""
    ok, data = hsh.dev_status(did)
    if not ok:
        return False, data, None
    st_dev = data.get('device', {}) or {}
    dev = dict(st_dev)  # status 精简字段 + 实时 subs
    # 补调 home/1 获取完整设备信息 (名称/场所/位置/型号)
    try:
        h_ok, h_data = hsh.dev_home(did)
        if h_ok:
            h_dev = (h_data or {}).get('device', {}) or {}
            if h_dev:
                # status 优先保留实时 subs/gene, home 补充其余完整字段; bm 合并补齐
                subs = dev.get('subs') or h_dev.get('subs') or []
                cur_bm = dev.get('bm') or {}
                h_bm = h_dev.get('bm') or {}
                if isinstance(cur_bm, dict) and isinstance(h_bm, dict):
                    merged_bm = dict(cur_bm)
                    for k, v in h_bm.items():
                        if k not in merged_bm or not merged_bm.get(k):
                            merged_bm[k] = v
                    dev['bm'] = merged_bm
                for k, v in h_dev.items():
                    if k not in dev or not dev.get(k):
                        dev[k] = v
                dev['subs'] = subs
    except Exception:
        pass
    ep = dev.get('ep', {}) or {}
    bm = dev.get('bm', {}) or {}
    subs = dev.get('subs') or []
    out = 0.0
    for s in subs:
        try:
            out += float(s.get('out') or 0)
        except Exception:
            pass
    view = {
        'id': did,
        'name': dev.get('name') or '',
        'gtype': dev.get('gtype'),
        'ntype': dev.get('ntype'),
        'status': dev.get('status'),
        'gene': dev.get('gene') or {},
        'out': out,
        'epName': ep.get('name') or '',
        'epContact': (ep.get('contact') or {}).get('name') or '',
        'epPhone': (ep.get('contact') or {}).get('pn') or '',
        'model': bm.get('model') or '',
        'brand': bm.get('brand') or '',
        'fetti': dev.get('fmv') or '',
        'loc': (dev.get('addr') or {}).get('detail') or '',
        'dev': dev,
    }
    return True, '', view

def _batch_refresh_status(devs, uid=None):
    """批量实时拉取设备服务端状态, 返回 {did: {'status': code, 'out': float}}
    同时同步本地 use_ts 缓存, 供 _dev_is_using 等旧逻辑保持一致"""
    status_map = {}
    if not devs:
        return status_map
    use_uid = uid or _dev_token_uid(None)
    if not use_uid:
        return status_map
    token = _dev_token_for(None, use_uid)
    if not token:
        return status_map
    hsh = HSH(token)
    try:
        for d in devs:
            did = d.get('id')
            if not did:
                continue
            try:
                s_ok, s_data = hsh.dev_status(did)
                if s_ok:
                    dev = (s_data or {}).get('device', {}) or {}
                    gene = dev.get('gene') or {}
                    subs = dev.get('subs') or []
                    code = str(gene.get('status') or '')
                    # 实时累加出水量
                    out = 0.0
                    for s in subs:
                        try:
                            out += float(s.get('out') or 0)
                        except Exception:
                            pass
                    status_map[did] = {'status': code, 'out': out}
                    # 同步本地 use_ts 缓存, 保持后续 _dev_is_using 判断一致
                    if code == '1':
                        _dev_mark_session(did, True, use_uid)
                    elif code == '99':
                        _dev_mark_session(did, False)
            except Exception:
                pass
    finally:
        hsh.close()
    return status_map


def _fmt_dev_brief(view, status_info=None):
    """列表项: 名称 | 场所 | 状态 | 余额"""
    name = view.get('name') or _mask_did(view.get('id', ''))
    ep = view.get('epName') or ''
    # 优先用服务端实时数据, 没有时用本地缓存兜底
    if status_info:
        code = status_info.get('status')
        out_val = status_info.get('out')
    else:
        code = None
        out_val = view.get('out')
    if code == '99':
        status = '⏸ 空闲'
    elif code == '1':
        status = '🔄 使用中'
    elif code:
        status = f'❓ {code}'
    else:
        status = '🔄 使用中' if _dev_is_using(view) else '⏸ 空闲'
    out = ''
    try:
        if out_val is not None:
            out = f" | 💰{out_val}"
    except Exception:
        pass
    line = f"{name}{' | ' + ep if ep else ''} | {status}{out}"
    return line


def _fmt_dev_detail(view):
    id_ = view.get('id')
    dev = view.get('dev') or {}
    ep = dev.get('ep', {}) or {}
    bm = dev.get('bm', {}) or {}
    addr = dev.get('addr', {}) or {}
    geo = None
    try:
        geo = (addr.get('geo') or {}).get('coordinates')
    except Exception:
        geo = None
    gene = dev.get('gene') or {}
    subs = dev.get('subs') or []
    out = 0.0
    for s in subs:
        try:
            out += float(s.get('out') or 0)
        except Exception:
            pass
    # 短响应可能没有 name/loc, 用缓存字段兜底
    name = dev.get('name') or view.get('name') or '未知'
    ep_name = ep.get('name') or view.get('epName') or '未知'
    # 当前所选账号
    cur_uid = view.get('curUid')
    detail = f"=====设备详情=====\n"
    detail += f"📇 编号: {id_}\n"
    detail += f"🏷 名称: {name}\n"
    detail += f"🏢 场所: {ep_name}\n"
    if cur_uid:
        p = middleware.bucketGet('yuhua_hsh_phone', str(cur_uid)) or str(cur_uid)
        detail += f"👤 账号: {_mask_identifier(p)}\n"
    detail += f"🔧 型号: {bm.get('brand') or '未知'} {bm.get('model') or ''}\n"
    detail += f"📍 位置: {addr.get('prov') or ''}{addr.get('city') or ''}{addr.get('dist') or ''} {addr.get('detail') or ''}\n"
    if geo and len(geo) >= 2:
        detail += f"🗺 经纬: {geo[1]}, {geo[0]}\n"
    detail += f"💰 余额/用量: {out}\n"
    detail += f"⚙️ 状态: {gene.get('status')}  mode={gene.get('mode')}\n"
    if cur_uid:
        sc_state = '❓ 未知' if view.get('scoreOn') is None else ('✅ 开启' if view.get('scoreOn') == 1 else '❌ 关闭')
        detail += f"🎫 积分抵扣: {sc_state}\n"
    detail += f"\n📊 最近账单:\n"
    bills = view.get('bills') or []
    if not bills:
        detail += "目录为空\n"
    else:
        for b in bills[:5]:
            detail += _fmt_bill_line(b)
    detail += "=================="
    return detail

def _fmt_bill_line(b):
    try:
        from datetime import datetime as _dt
        ts = int(b.get('ctime') or b.get('t') or 0) / 1000
        t = _dt.fromtimestamp(ts).strftime('%m-%d %H:%M')
    except Exception:
        t = '-'
    try:
        amount = float(b.get('money') or b.get('amount') or 0)
    except Exception:
        amount = 0
    try:
        out = float(b.get('out') or 0)
    except Exception:
        out = 0
    try:
        status = int(b.get('status') or 0)
    except Exception:
        status = 0
    st = {0: '待付', 1: '已付', 2: '结算中', 99: '进行中'}.get(status, str(status))
    return f"{t} {st} 金额:{amount} 用量:{out} id:{b.get('id') or ''}\n"

CQ_IMG_RE = re.compile(r'\[CQ:image[^\]]*?((?:file|url)=[^,\]^\s]+)\]')

def _extract_image_source(msg):
    """从消息文本提取可下载的图片源(file= / url= / base64:// / http(s)://)"""
    if not msg:
        return None
    m = CQ_IMG_RE.search(msg)
    if m:
        return m.group(1).split('=', 1)[1].strip()
    msg = msg.strip()
    if msg.startswith('base64://') or msg.startswith('http://') or msg.startswith('https://') or msg.startswith('file://'):
        return msg
    return None

def _fetch_image_bytes(src):
    """图片源 -> bytes (base64:// / http(s):// / file:// / 本地路径)"""
    try:
        if not src:
            return None
        if src.startswith('base64://'):
            return base64.b64decode(src[len('base64://'):])
        if src.startswith('http://') or src.startswith('https://'):
            # 部分平台(如QQ频道)图片直链有防盗链, 需伪装浏览器 UA
            resp = requests.get(src, timeout=20, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Referer': src,
            })
            resp.raise_for_status()
            return resp.content
        if src.startswith('file://'):
            import urllib.parse as _up
            p = _up.unquote(src[len('file://'):])
            if p.startswith('/') and len(p) >= 3 and p[2] == ':':
                p = p[1:]
            with open(p, 'rb') as f:
                return f.read()
        if os.path.exists(src):
            with open(src, 'rb') as f:
                return f.read()
    except Exception as e:
        if DEBUG:
            printf(f"图片下载失败: {e}", "WARN")
    return None

def dev_add():
    """【扫码添加设备】 等待二维码图片 -> 本地解码 -> 核实绑定"""
    if not uservalue:
        sender.reply(f"=====未绑定账号=====\n❌ 未找到任何账号信息\n💡 发送 {login_cmd} 绑定账号\n==================")
        return
    if not _QR_HAVE_NUMPY or _cv2() is None:
        _dep_np = "有" if _QR_HAVE_NUMPY else "缺"
        _dep_cv = "有" if _cv2() is not None else "缺"
        _detail = _CV2_ERR or "未安装/未调用import cv2"
        sender.reply(
            "❌ 二维码解析依赖不可用\n"
            f"numpy: {_dep_np} | cv2: {_dep_cv}\n"
            f"真实原因: {_detail}\n"
            "可尝试在共享依赖重装/降级:\n"
            "  pip install --force-reinstall opencv-python-headless==4.10.0.84"
        )
        return
    sender.reply("""
=====添加设备=====
请发送设备二维码图片
(对着设备二维码拍照/截图发我)
------------------
请在60秒内完成
回复"q"退出""")
    raw = sender.input(60000, 0, False)
    if not raw:
        sender.reply("❌ 输入超时")
        return
    if raw.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    raw = raw.strip()
    # 1) 尝试本地解码图片
    text, did = _decode_qr_from_msg(raw)
    if not did:
        # 诊断信息: 帮助定位卡在哪一步
        diag = []
        # 依赖状态 (最优先展示, 线上多数是缺依赖; 有真实异常则显示真实原因)
        _dep_cv_txt = "有" if _cv2() is not None else (f"缺({_CV2_ERR})" if _CV2_ERR else "缺(未安装)")
        diag.append(f"依赖: numpy={'有' if _QR_HAVE_NUMPY else '缺'} PIL={'有' if _QR_HAVE_PIL else '缺'} opencv={_dep_cv_txt}")
        src = _extract_image_source(raw)
        diag.append(f"图片源: {'找到' if src else '未找到'}")
        if src:
            data = _fetch_image_bytes(src)
            diag.append(f"下载: {'成功(' + str(len(data)) + 'B)' if data else '失败'}")
            if data:
                try:
                    if _PILImage is None:
                        diag.append("图片: PIL未安装，无法查看")
                    else:
                        im = _PILImage.open(io.BytesIO(data))
                        diag.append(f"图片: {im.format} {im.size[0]}x{im.size[1]}")
                except Exception:
                    diag.append("图片: 无法解析(非图片数据?)")
                texts = qr_decode(data)
                if _cv2() is None:
                    diag.append(f"解码: 跳过({_CV2_ERR or 'opencv未安装'})")
                else:
                    diag.append(f"解码: {'成功' if texts else '无结果(可能不是二维码/图片模糊)'}")
                    if texts:
                        diag.append(f"内容: {texts[0][:100]}")
        diag.append(f"原文: {raw[:80]}")
        sender.reply("❌ 未识别到二维码图片\n" + "\n".join(diag))
        return
    sender.reply(f"✅ 已解析二维码: {text[:120]}\n📇 设备号: {did}\n正在核实...")
    # 2) 设备固定: 已存在则提示 (设备只有一台, 不重复建)
    exist = _dev_get(did)
    if exist:
        sender.reply(f"✅ 设备 {_mask_did(did)} 已在列表中\n💡 发送\"慧生活设备\"选择账号使用吧")
        return
    # 3) 需要至少一个已登录账号来核实设备
    login_uids = _dev_login_accounts()
    if not login_uids:
        sender.reply("❌ 名下没有已登录的账号，请先登录")
        return
    token = middleware.bucketGet('yuhua_hsh_token', login_uids[0])
    hsh = HSH(token)
    try:
        ok, qr_data = hsh.qr_use(did)
        if not ok:
            sender.reply(f"❌ 设备核实失败: {qr_data}")
            return
        qr = qr_data.get('qr') or {}
        qr_type = qr.get('type')
        # 拉一次完整状态
        ok2, err2, view = _fetch_dev_view(hsh, did)
        if not ok2:
            sender.reply(f"⚠️ 设备已识别但状态拉取失败: {err2}")
            view = {'id': did, 'name': ''}
        # 设备固定: 只存设备信息, 不绑定账号 (操作时可选任意已登录账号)
        view['qrType'] = qr_type
        view['add_ts'] = int(time.time() * 1000)
        view['use_ts'] = 0
        view['use_uid'] = ''
        dev_by_id = _dev_list()[1]
        dev_by_id[did] = view
        _dev_save(list(dev_by_id.values()))
        sender.reply(f"""
=====设备添加成功=====
📇 编号: {did}
🏷 名称: {view.get('name') or '未知'}
🏢 场所: {view.get('epName') or '未知'}
------------------
发送"慧生活设备"选择账号使用吧
==================""")
    finally:
        hsh.close()

def dev_list(uid=None):
    """【设备列表】"""
    devs, _ = _dev_list()
    # 实时拉取每台设备状态, 避免显示本地缓存的陈旧状态
    status_map = _batch_refresh_status(devs, uid)
    msg = "=====设备列表=====\n"
    msg += "[0] 全部立即结算\n"
    msg += "[1] 添加新设备\n"
    msg += "[2] 删除设备\n"
    if not devs:
        msg += "------------------\n❌ 暂无已添加设备\n"
    else:
        for i, d in enumerate(devs, 1):
            did = d.get('id')
            msg += f"------------------\n[{i + 2}] {_fmt_dev_brief(d, status_map.get(did))}\n"
    msg += "------------------\n回复数字选择\n回复'q'退出\n=================="
    sender.reply(msg)
    choice = sender.input(60000, 0, False)
    if not choice or choice.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    try:
        idx = int(choice)
        if idx == 0:
            dev_settle_all()
        elif idx == 1:
            dev_add()
        elif idx == 2:
            dev_remove()
        elif 3 <= idx <= len(devs) + 2:
            dev_detail(devs[idx - 3].get('id'), uid)
        else:
            raise ValueError()
    except (ValueError, IndexError):
        sender.reply("❌ 无效的选择")

def dev_pick_account(title="账号"):
    """列出所有已登录账号供选择, 返回所选 uid 或 None"""
    uids = _dev_login_accounts()
    if not uids:
        sender.reply("❌ 名下没有已登录的账号，请先登录")
        return None
    menu = f"=====选择{title}=====\n"
    for i, acc in enumerate(uids, 1):
        p = middleware.bucketGet('yuhua_hsh_phone', str(acc)) or '未知'
        auth_str = middleware.bucketGet('yuhua_hsh_auth', str(acc))
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
        menu += f"------------------\n[{i}] 账号信息\n🤪 账号: {_mask_identifier(p)}\n☁ 授权: {status_line}\n"
    menu += "------------------\n回复数字选择账号\n回复'q'退出\n=================="
    sender.reply(menu)
    choice = sender.input(60000, 0, False)
    if not choice or choice.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return None
    try:
        idx = int(choice)
        if not 1 <= idx <= len(uids):
            raise ValueError()
        return str(uids[idx - 1])
    except (ValueError, IndexError):
        sender.reply("❌ 无效的选择")
        return None


def dev_detail(did=None, uid=None):
    """【设备详情+操作菜单】选设备后选账号, 用所选账号查详情"""
    if not did:
        did = _pick_device()
        if not did:
            return
    # 若已传入账号上下文 (如从慧生活管理进入), 直接使用当前账号, 跳过选账号流程
    if not uid:
        uid = dev_pick_account("账号")
        if not uid:
            return
    dev_detail_for(did, uid)

def _pick_device():
    devs, _ = _dev_list()
    if not devs:
        sender.reply("❌ 暂无设备")
        return None
    # 实时拉取每台设备状态
    status_map = _batch_refresh_status(devs)
    msg = "=====选择设备=====\n"
    msg += "[0] 全部立即结算\n"
    msg += "[1] 添加新设备\n"
    msg += "[2] 删除设备\n"
    for i, d in enumerate(devs, 1):
        did = d.get('id')
        msg += f"------------------\n[{i + 2}] {_fmt_dev_brief(d, status_map.get(did))}\n"
    msg += "------------------\n回复数字选择\n回复'q'退出\n=================="
    sender.reply(msg)
    choice = sender.input(60000, 0, False)
    if not choice or choice.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return None
    try:
        idx = int(choice)
        if idx == 0:
            dev_settle_all()
            return None
        if idx == 1:
            dev_add()
            return None
        if idx == 2:
            dev_remove()
            return None
        if not 3 <= idx <= len(devs) + 2:
            raise ValueError()
        return devs[idx - 3].get('id')
    except (ValueError, IndexError):
        sender.reply("❌ 无效的选择")
        return None

def dev_op_menu(did, view, uid=None):
    """设备操作: 立即使用/立即结算/切换账号 (用指定账号)"""
    if not uid:
        uid = view.get('curUid') or _dev_token_uid(None)
    while True:
        # 每次进入菜单前都实时拉取最新状态 (解决"操作后状态不更新"和"设备被外部关闭"的问题)
        token = _dev_token_for(None, uid)
        if not token:
            sender.reply("❌ 该账号未登录")
            return
        hsh = HSH(token)
        try:
            ok, msg, new_view = _fetch_dev_view(hsh, did)
            if not ok:
                sender.reply(f"❌ 状态查询失败: {msg}")
                return
            d = _dev_get(did) or {}
            new_view = dict(d, **new_view)
            new_view['dev'] = new_view.get('dev') or {}
            new_view['curUid'] = uid
            # 实时查询积分抵扣状态
            sc_ok, sc_val = _dev_query_score(hsh)
            new_view['scoreOn'] = sc_val if sc_ok else None
            # 实时查询账号总积分
            try:
                ts_ok, ts_val = hsh.get_total_score()
                new_view['totalScore'] = ts_val if ts_ok else '0'
            except Exception:
                new_view['totalScore'] = '0'
            # 缓存 name/out, 供列表页使用
            live_name = new_view.get('name') or ''
            if live_name and live_name != d.get('name'):
                _dev_patch(did, name=live_name)
            try:
                live_out = float(new_view.get('out') or 0)
                if live_out != d.get('out'):
                    _dev_patch(did, out=live_out)
            except Exception:
                pass
            view = new_view
        finally:
            hsh.close()

        # 组装菜单 (状态以服务端 gene.status 为准: 99=空闲, 1=使用中)
        name = view.get('name') or _mask_did(did)
        gene = (view.get('dev') or {}).get('gene') or {}
        status_code = str(gene.get('status') or '')
        if status_code == '99':
            status_line = '⏸ 空闲'
        elif status_code == '1':
            status_line = '🔄 使用中'
        elif status_code:
            status_line = f'❓ {status_code}'
        else:
            # 服务端没返回 status 时, 用本地缓存的 use_ts 兜底
            status_line = '🔄 使用中' if _dev_is_using(view) else '⏸ 空闲'

        cur_phone = ''
        if uid:
            p = middleware.bucketGet('yuhua_hsh_phone', str(uid)) or ''
            cur_phone = _mask_identifier(p) if p else str(uid)
        total_score = view.get('totalScore', '0')
        sc_val = view.get('scoreOn')
        sc_state = '❓ 未知' if sc_val is None else ('✅ 开启' if sc_val == 1 else '❌ 关闭')

        menu = "=====设备操作=====\n"
        menu += f"⚜️ 设备: {name}\n"
        menu += f"📝 状态: {status_line}\n"
        if cur_phone:
            menu += f"🤪 账号: {cur_phone}\n"
        menu += f"🎫 当前积分: {total_score}\n"
        menu += f"🔆 积分抵扣: {sc_state}\n"
        menu += "------------------\n"
        menu += "[1] 立即使用\n[2] 立即结算\n[3] 刷新状态\n[4] 切换账号\n[5] 切换积分抵扣\n"
        menu += "------------------\n回复数字选择操作\n回复'q'退出\n=================="
        sender.reply(menu)

        choice = sender.input(60000, 0, False)
        if not choice or choice.lower() == 'q':
            sender.reply("✅ 已退出操作")
            return
        if choice == '1':
            dev_start(did, view, uid)
        elif choice == '2':
            dev_end(did, view, uid)
        elif choice == '3':
            # 每次循环已自动刷新, 这里提示一下即可
            sender.reply("🔄 已刷新")
            continue
        elif choice == '4':
            # 切换账号: 交给 dev_switch_account 打开新账号菜单, 本菜单退出
            dev_switch_account(did)
            return
        elif choice == '5':
            dev_toggle_score(did, uid)
            continue
        else:
            sender.reply("❌ 无效的选择")

def dev_switch_account(did):
    """重新选择设备操作账号, 选好后直接用该账号进详情"""
    uid = dev_pick_account("账号")
    if not uid:
        return
    dev_detail_for(did, uid)

def dev_toggle_score(did, uid):
    """切换积分自动抵扣开关 (当前账号): 先实时查当前状态再取反"""
    if not uid:
        uid = _dev_token_uid(None)
    token = _dev_token_for(None, uid)
    if not token:
        sender.reply("❌ 该账号未登录")
        return
    hsh = HSH(token)
    try:
        q_ok, cur_on = _dev_query_score(hsh)
        if not q_ok or cur_on is None:
            sender.reply("❌ 查询当前积分抵扣状态失败")
            return
        new_on = 0 if cur_on == 1 else 1
        ok, msg = hsh.acc_upt(new_on)
        if not ok:
            sender.reply(f"❌ 设置积分抵扣失败: {msg}")
            return
        p = middleware.bucketGet('yuhua_hsh_phone', str(uid)) or str(uid)
        state = '✅ 已开启' if new_on == 1 else '❌ 已关闭'
        sender.reply(f"🎫 积分抵扣 {state}\n👤 账号: {_mask_identifier(p)}")
    finally:
        hsh.close()

def dev_set_score_cmd(uid, on):
    """指令设置积分抵扣 (开/关)"""
    if not uid:
        uid = _dev_token_uid(None)
    token = _dev_token_for(None, uid)
    if not token:
        sender.reply("❌ 该账号未登录")
        return
    hsh = HSH(token)
    try:
        ok, msg = hsh.acc_upt(1 if on else 0)
        if not ok:
            sender.reply(f"❌ 设置积分抵扣失败: {msg}")
            return
        p = middleware.bucketGet('yuhua_hsh_phone', str(uid)) or str(uid)
        state = '✅ 已开启' if on else '❌ 已关闭'
        sender.reply(f"🎫 积分抵扣 {state}\n👤 账号: {_mask_identifier(p)}")
    finally:
        hsh.close()

def _dev_query_score(hsh):
    """实时查询积分自动抵扣开关状态, 返回 (ok, 1开/0关/None未知)"""
    try:
        ok, val = hsh.get_use_score()
        if ok:
            return True, int(val) if val in (0, 1) else None
    except Exception:
        pass
    return False, None

def _parse_status_from_device(dev):
    """从 device 对象解析状态. 返回 dict:
    {
      'billing': '99'/'1'/''  (计费状态),
      'physical': bool,       (物理出水/使用中),
      'raw_status': int,      (原始 gene.status),
      'raw_mode': int,        (原始 gene.mode),
      'subs': [...]
    }"""
    gene = dev.get('gene') or {}
    subs = dev.get('subs') or []
    billing = str(gene.get('status') or '')
    physical = any(str(s.get('status') or '0') != '0' for s in subs)
    return {
        'billing': billing,
        'physical': physical,
        'raw_status': gene.get('status'),
        'raw_mode': gene.get('mode'),
        'subs': subs,
    }

def _wait_status(hsh, did, expect, max_retries=5, interval=2):
    """轮询等待服务端设备状态变为 expect ('1'=使用中 / '99'=空闲)
    最多等 max_retries * interval 秒, 返回 True/False"""
    for i in range(max_retries):
        try:
            s_ok, s_data = hsh.dev_status(did)
            if s_ok:
                gene = (s_data or {}).get('device', {}).get('gene') or {}
                if str(gene.get('status')) == expect:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False

def dev_detail_for(did, uid):
    """用指定账号查设备详情"""
    token = _dev_token_for(None, uid)
    if not token:
        sender.reply("❌ 该账号未登录")
        return
    hsh = HSH(token)
    try:
        ok, msg, view = _fetch_dev_view(hsh, did)
        if not ok:
            sender.reply(f"❌ 状态查询失败: {msg}")
            return
        b_ok, bills = hsh.bill_list(did)
        d = _dev_get(did) or {}
        view = dict(d, **view)
        view['dev'] = view.get('dev') or {}
        view['bills'] = bills if b_ok else []
        view['curUid'] = uid
        # 实时查询积分抵扣状态
        sc_ok, sc_val = _dev_query_score(hsh)
        view['scoreOn'] = sc_val if sc_ok else None
        live_name = view.get('name') or ''
        if live_name and live_name != d.get('name'):
            _dev_patch(did, name=live_name)
        try:
            live_out = float(view.get('out') or 0)
            if live_out != d.get('out'):
                _dev_patch(did, out=live_out)
        except Exception:
            pass
        sender.reply(_fmt_dev_detail(view))
        dev_op_menu(did, view, uid)
    finally:
        hsh.close()


def dev_start(did, view, uid=None):
    """立即使用 (开始计费), 用指定账号"""
    if not uid:
        uid = view.get('curUid') or _dev_token_uid(None)
    d = _dev_get(did)
    if not d:
        sender.reply("❌ 未找到设备")
        return
    token = _dev_token_for(None, uid)
    if not token:
        sender.reply("❌ 该账号未登录")
        return
    sender.reply("⏳ 正在处理...")   # ← 新增提示
    hsh = HSH(token)
    try:
        # 先读真实状态, 已在使用中(status=1)则跳过
        s_ok, s_data = hsh.dev_status(did)
        if s_ok:
            gene = (s_data or {}).get('device', {}).get('gene') or {}
            if str(gene.get('status')) == '1':
                _dev_mark_session(did, True, uid)
                sender.reply(f"⚠️ 设备 {_mask_did(did)} 已在使用中，无需重复开启\n")
                return
        # 积分自动抵扣: 实时检测, 未开启就启动, 已开启保持不变
        try:
            q_ok, sc_val = _dev_query_score(hsh)
            if q_ok and sc_val == 0:
                s_ok2, s_msg = hsh.acc_upt(1)
                if not s_ok2 and DEBUG:
                    printf(f"积分自动抵扣开启失败: {s_msg}", "WARN")
        except Exception as e:
            if DEBUG:
                printf(f"积分自动抵扣检测异常: {e}", "WARN")
        ok, msg = hsh.dev_start(did)
        if not ok:
            sender.reply(f"❌ 开始使用失败: {msg}")
            return
        # 服务端状态异步更新, 回读不可靠; code=0 视为成功, 立即同步本地缓存
        _dev_mark_session(did, True, uid)
        # 等服务端状态追上, 保证返回菜单时状态显示正确 (最长约 10s)
        if not _wait_status(hsh, did, '1', max_retries=5, interval=2):
            if DEBUG:
                printf("dev_start 后服务端状态未在 10s 内变为 1", "WARN")
        sender.reply(f"✅ 设备 {_mask_did(did)} 已开始使用，费用已计\n")
    finally:
        hsh.close()

def dev_end(did, view, uid=None):
    """立即结算 (结束计费)"""
    if not uid:
        uid = view.get('curUid') or _dev_token_uid(None)
    d = _dev_get(did)
    if not d:
        sender.reply("❌ 未找到设备")
        return
    token = _dev_token_for(None, uid)
    if not token:
        sender.reply("❌ 该账号未登录")
        return
    sender.reply("⏳ 正在处理...")   # ← 新增提示
    hsh = HSH(token)
    try:
        # 先读真实状态
        s_ok, s_data = hsh.dev_status(did)
        if s_ok:
            dev = (s_data or {}).get('device', {}) or {}
            st = _parse_status_from_device(dev)
            # 物理设备正在运行中: 无法通过 API 结算
            if st['physical']:
                sender.reply(f"⚠️ 设备 {_mask_did(did)} 正在运行中（出水/使用中），无法通过接口结算\n💡 请在设备上点击结算，或等设备自动结束\n")
                return
            # 已经是空闲且没有物理运行: 无需结算
            if st['billing'] == '99':
                _dev_mark_session(did, False, uid)
                sender.reply(f"⚠️ 设备 {_mask_did(did)} 已是空闲状态，无需结算\n")
                return
        # 记录结算前积分
        score_before = None
        try:
            sb_ok, sb_val = hsh.get_total_score(force=True)
            score_before = int(sb_val) if sb_ok else None
        except Exception:
            score_before = None
        ok, msg = hsh.dev_end(did)
        if not ok:
            if "设备运行中" in str(msg) or "设备正在" in str(msg):
                sender.reply(f"⚠️ 设备 {_mask_did(did)} 正在运行中，无法通过接口结算\n💡 请在设备上点击结算，或等设备自动结束\n")
                return
            sender.reply(f"❌ 立即结算失败: {msg} (可再次尝试)")
            return
        _dev_mark_session(did, False, uid)
        # 等服务端计费状态变为 99
        if not _wait_status(hsh, did, '99', max_retries=5, interval=2):
            if DEBUG:
                printf("dev_end 后服务端状态未在 10s 内变为 99", "WARN")
        # 结算后积分, 计算本次消耗
        score_after = None
        try:
            sa_ok, sa_val = hsh.get_total_score(force=True)
            score_after = int(sa_val) if sa_ok else None
        except Exception:
            score_after = None
        consume_str = ""
        if score_before is not None and score_after is not None:
            consumed = score_before - score_after
            if consumed > 0:
                consume_str = f"，本次消耗 {consumed} 积分"
            elif consumed < 0:
                consume_str = f"，本次获得 {-consumed} 积分"
            else:
                consume_str = "，本次消耗 0 积分"
        sender.reply(f"✅ 设备 {_mask_did(did)} 已结算{consume_str}\n")
    finally:
        hsh.close()

def dev_settle_all():
    """全部立即结算: 只结算正在使用中的设备, 每台用其启动账号(use_uid)结算,
    失败只记单台原因并原样保留使用状态, 不连累其他设备"""
    devs, _ = _dev_list()
    if not devs:
        sender.reply("❌ 暂无设备")
        return
    using = [d for d in devs if _dev_is_using(d)]
    idle = [d for d in devs if not _dev_is_using(d)]
    if not using:
        sender.reply(f"=====结算完成=====\n✅ 无使用中的设备 (空闲 {len(idle)} 台)\n==================")
        return
    sender.reply(f"正在结算 {len(using)} 台使用中的设备...")
    ok_n = 0
    fail_n = 0
    fail_msgs = []
    idle_msgs = []
    last_uid = None
    for d in using:
        did = d.get('id')
        # 结算账号: 优先设备启动账号, 其次设备归属/已登录账号
        uid = str(d.get('use_uid') or '')
        token = _dev_token_for(None, uid) if uid else None
        if not token:
            owner = [str(u) for u in (d.get('uids') or [])
                     if middleware.bucketGet('yuhua_hsh_token', str(u))]
            uid = owner[0] if owner else None
            token = _dev_token_for(None, uid) if uid else None
        if not token:
            fail_n += 1
            fail_msgs.append(f"{_mask_did(did)}: 无可用的已登录账号")
            continue
        # 同账号连续结算间隔, 防止触发请求过于频繁
        if last_uid and uid == last_uid:
            time.sleep(0.3)
        last_uid = uid
        hsh = HSH(token)
        try:
            ok, msg = hsh.dev_end(did)
            if ok:
                _dev_mark_session(did, False)
                ok_n += 1
            else:
                # 已结算过会返回失败, 回读一次状态确认是否真的还在计费
                retried = False
                try:
                    s_ok, s_data = hsh.dev_status(did)
                    if s_ok:
                        gene = (s_data or {}).get('device', {}).get('gene') or {}
                        if str(gene.get('status')) == '99':
                            retried = True
                            time.sleep(0.3)
                            ok2, msg2 = hsh.dev_end(did)
                            if ok2:
                                _dev_mark_session(did, False)
                                ok_n += 1
                            else:
                                msg = msg2
                except Exception:
                    pass
                if not retried:
                    fail_n += 1
                    fail_msgs.append(f"{_mask_did(did)}: {msg}")
        except Exception as e:
            fail_n += 1
            fail_msgs.append(f"{_mask_did(did)}: {str(e)}")
        finally:
            hsh.close()
    msg = f"=====结算完成=====\n✅ 成功: {ok_n}\n❌ 失败: {fail_n}\n"
    if idle_msgs:
        msg += "------------------\n" + "\n".join(idle_msgs[:10]) + "\n"
    if fail_msgs:
        msg += "------------------\n" + "\n".join(fail_msgs[:10])
    msg += "\n=================="
    sender.reply(msg)

def dev_remove(did=None):
    """删除设备 (只删设备记录, 不动账号/授权)"""
    if not did:
        # 独立选择要删除的设备
        devs = _dev_list_raw()
        if not devs:
            sender.reply("❌ 暂无设备")
            return
        menu = "=====删除设备=====\n"
        menu += "回复'q'退出\n"
        for i, d in enumerate(devs, 1):
            menu += f"------------------\n[{i}] {_fmt_dev_brief(d)}\n"
        menu += "------------------\n回复数字选择要删除的设备"
        sender.reply(menu)
        choice = sender.input(60000, 0, False)
        if not choice or choice.lower() == 'q':
            sender.reply("✅ 已退出操作")
            return
        try:
            idx = int(choice)
            if not 1 <= idx <= len(devs):
                raise ValueError()
            did = devs[idx - 1].get('id')
        except (ValueError, IndexError):
            sender.reply("❌ 无效的选择")
            return
    d = _dev_get(did)
    if not d:
        sender.reply("❌ 未找到设备")
        return
    name = d.get('name') or _mask_did(did)
    sender.reply(f"⚠️ 确认删除设备「{name}」吗？(y/n)")
    confirm = sender.input(30000, 0, False)
    if not confirm:
        sender.reply("❌ 输入超时")
        return
    if confirm.lower() in ('n', 'q'):
        sender.reply("✅ 已退出操作")
        return
    if confirm.lower() != 'y':
        sender.reply("❌ 无效的选择")
        return
    devs = _dev_list_raw()
    devs = [d for d in devs if d.get('id') != did]
    _dev_save(devs)
    sender.reply(f"""
=====删除成功=====
📇 设备: {name}
✅ 状态: 已删除本地记录
==================""")

def main_dev_command(message):
    """设备指令入口: 设备 添加 / 管理 / 详情 / 使用 / 结算 / 删除 / 积分"""
    if '积分开' in message:
        uid = _dev_token_uid(None)
        dev_set_score_cmd(uid, True)
        return
    if '积分关' in message:
        uid = _dev_token_uid(None)
        dev_set_score_cmd(uid, False)
        return
    if '积分切换' in message or ('积分' in message and '开关' in message):
        uid = _dev_token_uid(None)
        dev_toggle_score(None, uid)
        return
    if '管理' in message or message in ('慧生活设备', '慧生活设备管理'):
        dev_list()
        return
    if '添加' in message:
        dev_add()
        return
    if '删除' in message:
        dev_remove()
        return
    # 其他: 设备详情菜单
    dev_list()

senderID = middleware.getSenderID()
sender = middleware.Sender(senderID)
userid = sender.getUserID()
imtype = sender.getImtype()
uservalue = middleware.bucketGet(bucket='yuhua_hsh_user', key=userid)

def get_config():
    """获取插件配置"""
    manage_cmd = middleware.bucketGet('yuhua_hsh', 'manage_cmd') or '慧生活管理'
    query_cmd = middleware.bucketGet('yuhua_hsh', 'query_cmd') or '慧生活查询'
    login_cmd = middleware.bucketGet('yuhua_hsh', 'login_cmd') or '慧生活登录'
    price = Decimal(middleware.bucketGet('yuhua_hsh', 'price') or '0')
    bf_str = middleware.bucketGet('yuhua_hsh', 'bingfa') or '20'
    
    try:
        bf_num = int(bf_str)
    except:
        bf_num = 20
    return (manage_cmd, query_cmd, login_cmd, price, bf_num)

# 获取配置
manage_cmd, query_cmd, login_cmd, price, bingfa = get_config()

today_time = str(datetime.now().date())

###################
#   逻辑函数区块   #
###################

def login():
    """账号登录"""
    login_guide = """=====登录方式=====
[1] Token登录
[2] 手机号登录 (APP)
[3] 手机号登录 (WX)
------------------
回复数字选择方式
回复"q"退出"""

    sender.reply(login_guide)
    choice = sender.input(60000, 0, False)

    if not choice:
        sender.reply("❌ 输入超时")
        return
    elif choice.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return

    try:
        if choice == '1':
            token_online_login()
        elif choice == '2':
            sms_login_interaction("app")
        elif choice == '3':
            sms_login_interaction("wx")
        else:
            sender.reply("❌ 无效的选择")
            return
    except Exception as e:
        sender.reply(f"❌ 登录失败: {str(e)}")
        return

def _query_single_account(unique_id):
    """【内部函数】并发查询单个账号"""
    time.sleep(random.uniform(0.5, 1.0))
    phone = middleware.bucketGet('yuhua_hsh_phone', unique_id) or "未知"
    phone_mask = _mask_identifier(phone)
    auth_time = middleware.bucketGet('yuhua_hsh_auth', unique_id)
    now_date = datetime.now().date()
    
    if not auth_time: return f"【{phone_mask}】未授权"
    auth_date = datetime.strptime(auth_time, "%Y-%m-%d").date()
    if auth_date < now_date: return f"【{phone_mask}】授权已过期"  
    
    token = middleware.bucketGet('yuhua_hsh_token', unique_id)
    if not token: return f"【{phone_mask}】本地未找到Token"

    hsh = HSH(token)
    
    try:
        # 验证Token
        valid, msg = hsh.check_token()
        if not valid:
            return f"【{phone_mask}】{hsh._fail_reason(msg)}"

        # 取数接口同样可能回 -99 登录状态已过期(而 acc/stat 仍放行), 按响应判定原因
        assets_ok, assets = hsh.query_assets()
        if not assets_ok:
            return f"【{phone_mask}】{hsh._fail_reason(assets)}"

        return f"""
=====账号信息=====
🤪 账号: {phone_mask}
🎫 当前积分: {assets.get('total_score', '0')}
🎨 今日积分: {assets.get('today_score', '0')}
📝 今日消耗: {assets.get('today_spend', '0')}
☁️ 授权到期: {auth_date.strftime('%Y-%m-%d')}
=================="""

    finally:
        hsh.close()

def query_account():
    """
    【慧生活查询】
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

    bf_num_local = bingfa  

    with ThreadPoolExecutor(max_workers=bf_num_local) as executor:
        futures = {executor.submit(_query_single_account, acc_id): acc_id for acc_id in accounts}
        for future in as_completed(futures):
            try:
                result_msg = future.result()
                if result_msg:
                    sender.reply(result_msg)
            except Exception as e:
                sender.reply(f"❌ 查询某个账号时出错: {e}")

def _wrap_task_run(unique_id):
    """【内部函数】任务运行包装器"""
    time.sleep(random.uniform(0.5, 2.0))
    phone = middleware.bucketGet('yuhua_hsh_phone', unique_id) or "未知"
    phone_mask = _mask_identifier(phone)
    
    # 鉴权
    auth_time = middleware.bucketGet('yuhua_hsh_auth', unique_id)
    now_date = datetime.now().date()
    if not auth_time: 
        return f"=====慧生活运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 未授权\n======================="
    if datetime.strptime(auth_time, "%Y-%m-%d").date() < now_date: 
        return f"=====慧生活运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 授权已过期\n======================="
    
    token = middleware.bucketGet('yuhua_hsh_token', unique_id)
    if not token: 
        return f"=====慧生活运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 未登录\n======================="

    hsh = HSH(token)
    try:
        valid, msg = hsh.check_token()
        if not valid:
            return f"=====慧生活运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 凭证失效({msg})\n======================="
        return hsh.run_daily_tasks(phone_mask)
    except Exception as e:
        return f"=====慧生活运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 运行异常({str(e)})\n======================="
    finally:
        hsh.close()

def execute_batch_run():
    """【慧生活运行】用户侧指令"""
    if not uservalue:
        sender.reply(f"=====未绑定账号=====\n❌ 未找到任何账号信息\n💡 发送 {login_cmd} 绑定账号\n==================")
        return
    accounts = eval(uservalue)
    if not accounts:
        sender.reply(f"=====未绑定账号=====\n❌ 未找到任何账号信息\n💡 发送 {login_cmd} 绑定账号\n==================")
        return
        
    sender.reply(f"正在执行...")
    
    bf_num_local = bingfa
    with ThreadPoolExecutor(max_workers=bf_num_local) as executor:
        futures = {executor.submit(_wrap_task_run, acc_id): acc_id for acc_id in accounts}
        for future in as_completed(futures):
            try:
                result_msg = future.result()
                if result_msg:
                    safe_reply(sender, result_msg)
            except Exception as e:
                sender.reply(f"❌ 执行出错: {e}")

def admin_run_all_tasks():
    """【慧生活一键运行】管理员侧指令 (已优化：全量日志分段发送)"""
    sender.reply("正在执行...")
    
    # 收集任务
    tasks = []
    users = middleware.bucketAllKeys('yuhua_hsh_user')
    for u in users:
        acc_list = eval(middleware.bucketGet('yuhua_hsh_user', u) or '[]')
        for a in acc_list:
            # 仅运行已授权且不过期的
            auth = middleware.bucketGet('yuhua_hsh_auth', a)
            if auth and auth >= str(datetime.now().date()):
                tasks.append((u, a))
    
    if not tasks:
        sender.reply("❌ 暂无已授权的账号")
        return

    success = 0
    failed = 0
    details = []
    
    # 获取推送状态配置 (默认关闭)
    push_cfg = middleware.bucketGet('yuhua_hsh', 'push_status')
    is_push = str(push_cfg).lower() == 'true'

    def _run_single(u, a):
        try:
            res = _wrap_task_run(a)
            p = middleware.bucketGet('yuhua_hsh_phone', a) or '未知'
            p_mask = _mask_identifier(p)
            
            # 推送给用户 (根据配置决定)
            if is_push:
                for ch in ['qq','qb','wx','gw','sb','wb','tg','tb','qx','xy','ip']: 
                    try: middleware.push(ch, '', u, '', res)
                    except: pass
            
            # 统计逻辑：判断是否全完成
            match = re.search(r"完成(\d+)/(\d+)", res)
            if match and match.group(1) == match.group(2):
                return True, u, p_mask, ""
            else:
                # 提取失败原因
                reason = "部分任务失败"
                if "授权" in res: reason = "授权问题"
                elif "凭证" in res: reason = "凭证失效"
                elif "未登录" in res: reason = "未登录"
                else:
                    # 尝试提取❌后面的内容
                    errs = []
                    for line in res.split('\n'):
                        if "❌" in line:
                            clean = line.replace("❌", "").strip()
                            clean = re.sub(r'（.*?）', '', clean)
                            if clean and clean not in errs: errs.append(clean)
                    if errs:
                        reason = ",".join(errs[:2]) 
                
                return False, u, p_mask, reason
        except Exception as e:
            return False, u, '未知', str(e)

    # 并发执行
    with ThreadPoolExecutor(max_workers=bingfa) as ex:
        futures = [ex.submit(_run_single, u, a) for u, a in tasks]
        for f in as_completed(futures):
            s, u, p, r = f.result()
            if s:
                success += 1
            else:
                failed += 1
                details.append(f"🤪 账号: {p}\n🪁 原因: {r}")

    # 生成管理员汇总报告
    report = [
        f"=====慧生活一键=====",
        f"✨ 总账号数: {len(tasks)}",
        f"✅ 运行成功: {success}",
        f"❌ 运行失败: {failed}",
        "------------------"
    ]

    if details:
        report.append("📝 失败详情:")
        report.extend(details)
    else:
        report.append("📝 失败详情: 暂无")
        
    report.append("==================")
    
    safe_reply(sender, "\n".join(report))

def _mask_identifier(identifier: str) -> str:
    if "****" in identifier or len(identifier) <= 8:
        return identifier
    return identifier[:3] + "****" + identifier[-4:]

def auth_all_accounts_for_user(accounts):
    """一键授权"""
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
            middleware.bucketSet('yuhua_hsh_auth', acc_id, auth_time)
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
    """管理账号"""
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
        phone = middleware.bucketGet('yuhua_hsh_phone', acc_id) or "未知"
        phone_mask = _mask_identifier(phone)
        auth_str = middleware.bucketGet('yuhua_hsh_auth', acc_id)
        
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
[3] 运行任务
[4] 设备管理
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
        sender.reply("正在执行...")
        safe_reply(sender, _wrap_task_run(account))
    elif choice == '4':
        dev_list(account)
    else:
        sender.reply("❌ 无效的选择")

def confirm_delete(account):
    """确认是否删除账号"""
    phone = middleware.bucketGet('yuhua_hsh_phone', account) or "未知"
    phone_mask = _mask_identifier(phone)
    sender.reply(f"⚠️ 确认要删除账号 {phone_mask} 吗？(y/n)")
    confirm = sender.input(30000, 0, False)
    if not confirm:
        sender.reply("❌ 输入超时")
        return
    elif confirm.lower() == 'n':
        sender.reply("✅ 已退出操作")
        return
    elif confirm.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    elif confirm.lower() != 'y':
        sender.reply("❌ 无效的选择")
        return
    delete_account(account)

def delete_account(account):
    """删除本地记录"""
    phone = middleware.bucketGet('yuhua_hsh_phone', account) or "未知"
    phone_mask = _mask_identifier(phone)
    accounts = eval(uservalue or '[]')
    if account not in accounts:
        sender.reply("❌ 未找到账号")
        return
        
    accounts.remove(account)
    middleware.bucketSet('yuhua_hsh_user', userid, str(accounts))
    try:
        middleware.bucketDel('yuhua_hsh_token', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_hsh_auth', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_hsh_phone', account)
    except Exception:
        pass

    sender.reply(f"""
=====删除成功=====
🤪 账号: {phone_mask}
✅ 状态: 已删除数据
==================""")

def auth_account(account):
    """用户侧手动授权"""
    phone = middleware.bucketGet('yuhua_hsh_phone', account) or "未知"
    phone_mask = _mask_identifier(phone)
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
    middleware.bucketSet('yuhua_hsh_auth', account, auth_time)
    
    days = 30*months
    sender.reply(f"""
=====授权成功=====
🤪 账号: {phone_mask}
⏰ 时长: {days}天
📅 到期: {auth_time}
=======================""")

def calculate_auth_time(account, days):
    current_date = datetime.now().date()
    auth_str = middleware.bucketGet('yuhua_hsh_auth', account)
    
    start_date = current_date
    if auth_str:
        try:
            auth_date = datetime.strptime(auth_str, "%Y-%m-%d").date()
            if auth_date > current_date:
                start_date = auth_date
        except ValueError:
            pass 

    end_date = start_date + timedelta(days=days)
    if days < 0 and end_date < current_date:
        return str(current_date - timedelta(days=1))
        
    return str(end_date)

def process_payment(amount, months, phone_mask):
    """处理支付"""
    zsm = middleware.bucketGet('yuhua_hsh', 'zsm')
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
    users = middleware.bucketAllKeys('yuhua_hsh_user')
    cleaned = 0
    for user in users:
        accounts = eval(middleware.bucketGet('yuhua_hsh_user', user) or '[]')
        valid = []
        for acc_id in accounts:
            auth = middleware.bucketGet('yuhua_hsh_auth', acc_id)
            if (not auth) or (auth <= str(datetime.now().date())):
                try:
                    middleware.bucketDel('yuhua_hsh_token', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_hsh_auth', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_hsh_phone', acc_id)
                except Exception:
                    pass
                cleaned += 1
            else:
                valid.append(acc_id)
        if valid:
            middleware.bucketSet('yuhua_hsh_user', user, str(valid))
        else:
            try:
                middleware.bucketDel('yuhua_hsh_user', user)
            except Exception:
                pass
    sender.reply(f"✅ 已清理 {cleaned} 个慧生活授权已过期账号")

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
    if not choice:
        sender.reply("❌ 输入超时")
        return
    elif choice.lower() == 'q':
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
    """一键授权所有用户"""
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
        users = middleware.bucketAllKeys('yuhua_hsh_user')
        success = 0
        failed = 0
        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_hsh_user', user) or '[]')
            for acc_id in accounts:
                try:
                    auth_time = calculate_auth_time(acc_id, days)
                    middleware.bucketSet('yuhua_hsh_auth', acc_id, auth_time)
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

    accounts = eval(middleware.bucketGet('yuhua_hsh_user', user_id) or '[]')
    if not accounts:
        sender.reply("❌ 该用户没有绑定账号")
        return

    account_list_msg = "=====账号列表=====\n[0] 授权全部账号\n"
    for i, acc_id in enumerate(accounts, 1):
        phone = middleware.bucketGet('yuhua_hsh_phone', acc_id) or "未知"
        phone_mask = _mask_identifier(phone)
        auth_str = middleware.bucketGet('yuhua_hsh_auth', acc_id)
        
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
        latest_accounts = eval(middleware.bucketGet('yuhua_hsh_user', user_id) or '[]')
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
                middleware.bucketSet('yuhua_hsh_auth', acc_id, auth_time)
                success += 1
            except Exception as e:
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
        users = middleware.bucketAllKeys('yuhua_hsh_user')
        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_hsh_user', user) or '[]')
            for acc_id in accounts:
                time.sleep(random.uniform(0.5, 1.0))
                try:
                    token = middleware.bucketGet('yuhua_hsh_token', acc_id)
                    phone = middleware.bucketGet('yuhua_hsh_phone', acc_id) or "未知"
                    if not token:
                        notify_user(user, acc_id, "未找到登录凭证")
                        continue
                        
                    hsh = HSH(token)
                    ok, msg = hsh.check_token()
                    hsh.close()
                    
                    if not ok:
                        notify_user(user, acc_id, f"登录凭证已失效: {msg}")
                        continue
                        
                    auth_time = middleware.bucketGet('yuhua_hsh_auth', acc_id)
                    if not auth_time or auth_time <= today_str:
                        notify_user(user, acc_id, "授权已过期，请及时续费")
                except Exception as e:
                    print(f"处理账号 {acc_id} 出错: {str(e)}")
                    continue
    except Exception as e:
        print(f"定时任务出错: {str(e)}")

notified_accounts = set()
def notify_user(user, account, message):
    """发送用户通知"""
    try:
        if account in notified_accounts:
            return
        phone = middleware.bucketGet('yuhua_hsh_phone', account) or "未知"
        phone_mask = _mask_identifier(phone)
        notify_msg = f"""
=====慧生活通知=====
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
        elif message == '慧生活运行':
            execute_batch_run()
        elif message == '慧生活清理':
            clean_expired()
        elif message == '慧生活授权':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            admin_auth()
        elif message == '慧生活检测':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            sender.reply("正在检测....")
            cron_task()
            sender.reply("✅ 已执行检测推送任务")
        elif message == '慧生活一键运行':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            admin_run_all_tasks()
        elif '设备' in message:
            main_dev_command(message)
        else:
            sender.setContinue()
    except Exception as e:
        sender.reply(f"❌ 运行出错: {str(e)}")
                
if __name__ == "__main__":
    try:
        manage_cmd, query_cmd, login_cmd, price, bingfa = get_config()
        today = str(datetime.now().date())
        if imtype == 'fake':
            pass
        else:
            main()
    except Exception as e:
        sender.reply(f"❌ 运行出错: {str(e)}")
