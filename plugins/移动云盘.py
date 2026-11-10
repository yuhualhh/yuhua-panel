# [title: 移动云盘]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@391e5db5571432ac74c20afa8e958ac83e32e7a3/2025/02/13/437a3d841eaea843d11f97941c33accb.png]
# [language: python]
# [rule: ^(云盘)(登录|查询|管理|清理|授权|检测|兑换|一键抢兑)$]
# [disable:false]
# [open_source: false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [priority: 9999999999999999999]
# [public: true]
# [version: 9.4.5]
# [price: 0]
# [author: 羽化]
# [service: ]
# [description: ❶移动云盘插件，支持自动抢兑、短信登录、自动续期、自定义并发、管理、查询、授权、检测授权过期以及CK失效推送等功能<br>❷部分功能的实现需自行添加计划任务，关于指令『云盘检测』与『云盘清理』定时『30 18 * * *』，关于指令『云盘一键抢兑』定时『57 9,11,15,19,23 * * *』<br>❸添加计划任务教程: ⒈先点'系统管理-对接管理或适配器'设置『管理员』发条消息后在'本地开发-实时日志'查看『类型』再点'系统管理-计划任务'按『新增』⒉'定时'框填『57 9,11,15,23 * * *』⒊'指令或内容'框填『云盘一键抢兑』⒋勾选『自处理』⒌ '伪装媒介'填『类型』⒍'伪装个人'框填『管理员ID』]

# [param: {"required":false,"key":"yuhua_ydyp.zsm","bool":false,"placeholder":"","name":"收款码子","desc":"微信Bot收款码直链"}]
# [param: {"required":true,"key":"yuhua_ydyp.ql_config","bool":false,"placeholder":"Host丨ClientID丨ClientSecret","name":"对接容器","desc":"各参数之间用中文符丨分割，例如: http://127.0.01:5700/丨abcdef-ghijk丨abcdefghijklmnopqrs_tuvw"}]
# [param: {"required":true,"key":"yuhua_ydyp.var_name","bool":false,"placeholder":"必填项,例:ydyp","name":"环境变量","desc":"定义提交至容器的变量名称"}]
# [param: {"required":false,"key":"yuhua_ydyp.price","bool":false,"placeholder":"","name":"收费价格","desc":"不填默认0元，单位: 元/月"}]
# [param: {"required":false,"key":"yuhua_ydyp.bingfa","bool":false,"placeholder":"","name":"抢兑并发","desc":"不填默认20"}]
# [param: {"required":false,"key":"yuhua_ydyp.debug_pwd","bool":false,"placeholder":"","name":"调试模式","desc":"非插件开发者无需理会"}]

import re
import time
from datetime import datetime, timedelta, timezone
import middleware
import urllib.parse
from decimal import Decimal
import requests
import json
import hashlib
import uuid
import random
import socket
import sys
import base64
import os
import gzip
import ast
scripts = "云盘"

def printf(msg, level='INFO'):
    c = 32 if level in ['INFO', 'DEBUG'] else 33 if level in ['WARN', 'WARNING'] else 31
    sys.stderr.write(f"\033[{c}m[{level}] {str(msg)}\033[0m\n")
    sys.stderr.flush()


_LOG_SENSITIVE_KEYS = {
    'authorization', 'jwttoken', 'jwt_token', 'jwt', 'cookie', 'cookies',
    'cookietokenkey', 'token', 'password', 'csrf_token', 'smidv2', 'smid',
}


def _redact_log_value(value, depth=0):
    if depth > 4:
        return '...'
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if str(key).lower() in _LOG_SENSITIVE_KEYS:
                result[key] = '<redacted>'
            else:
                result[key] = _redact_log_value(item, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_redact_log_value(item, depth + 1) for item in value[:20]]
    if isinstance(value, str) and len(value) > 200:
        return value[:200] + f'...<{len(value)} chars>'
    return value


def _redact_log_text(text):
    text = re.sub(
        r'(?i)("?(?:authorization|jwt_?token|cookietokenkey|password|token)"?\s*[:=]\s*"?)(?:Basic\s+)?[A-Za-z0-9+/=_\-\.%]+',
        r'\1<redacted>', str(text))
    text = re.sub(r'(?i)(Basic\s+)[A-Za-z0-9+/=]+', r'\1<redacted>', text)
    return text


def _debug_dump(value, limit=2000):
    try:
        text = json.dumps(_redact_log_value(value), ensure_ascii=False)
    except Exception:
        text = str(value)
    text = _redact_log_text(text)
    if len(text) > limit:
        text = text[:limit] + f'...<truncated total {len(text)} chars>'
    return text

debug_key = middleware.bucketGet('yuhua_ydyp', 'debug_pwd') or ''
DEBUG = (debug_key == '123456789abcC@')
if DEBUG:
    printf("🔥🔥🔥 调试模式已开启，密钥验证通过 🔥🔥🔥", "WARN")
######################### 全局 Session #########################
GLOBAL_SESSION = None

def get_global_session():
    """
    在整个插件生命周期内只使用这一个全局 Session，无连接池限制以最大化并发性能。
    如果尚未创建，则创建并返回；若已存在，则直接返回。
    """
    global GLOBAL_SESSION
    if GLOBAL_SESSION is None:
        GLOBAL_SESSION = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        GLOBAL_SESSION.mount('http://', adapter)
        GLOBAL_SESSION.mount('https://', adapter)
        GLOBAL_SESSION.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Linux; Android 16; RMX5060 Build/BP2A.250605.015; wv) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/149.0.7827.13 '
                'Mobile Safari/537.36 MCloudApp/12.5.4 AppLanguage/zh-CN'
            )
        })
    return GLOBAL_SESSION

def close_global_session():
    """
    彻底关闭全局 Session，并释放资源。
    """
    global GLOBAL_SESSION
    if GLOBAL_SESSION is not None:
        GLOBAL_SESSION.close()
        GLOBAL_SESSION = None


############### 新增：NTP网络时间校准机制 ###############
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
def local_now():
    """返回基于NTP校准的当前北京时间"""
    return get_china_time()
##########################################################

YDYP_GATEWAY_HOST = 'https://gp.mcloud.139.com'
YDYP_MARKET_HOST = 'https://m.mcloud.139.com'
YDYP_SIGN_SECRET = 'sekaMdYYLIZfbCfm'
YDYP_MARKET_NAME = 'sign_in_3'
YDYP_AUTH_PATH = '/ycloud/auth-service/auth/tyrzLogin'
YDYP_TIMESTAMP_PATH = '/ycloud/api/timestamp'
YDYP_APP_VERSION = '13.2.5.0'
YDYP_CLIENT_VERSION = '13.2.5'
YDYP_MARKET_UA = (
    'Mozilla/5.0 (Linux; Android 13; wv) AppleWebKit/537.36 (KHTML, like Gecko) '
    'Version/4.0 Chrome/108.0.5359.128 Mobile Safari/537.36 '
    'MCloudApp/13.2.5 AppLanguage/zh-CN'
)
YDYP_ORG = 'FXlyfmWg2AzwbrxDKSv5'
YDYP_ORG_MD5 = hashlib.md5(YDYP_ORG.encode('utf-8')).hexdigest()
YDYP_EXCHANGE_MARKET_ID = 'sign_in_3_ex'
YDYP_REFRESH_AES_KEY = b'2olBaQGYnEKoStYomsd1n7ax'
YDYP_REFRESH_DEVICE_INFO = (
    '1|127.0.0.1|1|12.5.4|Xiaomi|23049RAD8C|'
    '1E58F2CE422EB2234BB8795E316BD44B|02-00-00-00-00-00|android 13'
)


def fetch_gateway_timestamp(session=None, timeout=8):
    requester = session or requests
    try:
        resp = requester.get(YDYP_GATEWAY_HOST + YDYP_TIMESTAMP_PATH, timeout=timeout)
        data = resp.json()
        result = data.get('result')
        if isinstance(result, int) and result > 0:
            return str(result)
        if isinstance(result, str) and result.isdigit():
            return result
    except Exception:
        pass
    return str(int(time.time() * 1000))


def build_gateway_sign_headers(session=None, extra=None):
    request_id = str(uuid.uuid4())
    timestamp = fetch_gateway_timestamp(session)
    nonce = str(uuid.uuid4())
    raw = YDYP_SIGN_SECRET + request_id + timestamp + nonce + '' + YDYP_SIGN_SECRET
    signature = hashlib.md5(raw.encode('utf-8')).hexdigest()
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'x-request-id': request_id,
        'x-timestamp': timestamp,
        'x-nonce': nonce,
        'x-signature': signature,
        'X-Requested-With': 'XMLHttpRequest',
    }
    if extra:
        headers.update(extra)
    return headers


def is_transient_error(msg):
    text = str(msg or '').lower()
    markers = ('connection refused', 'timeout', 'timed out', 'bad gateway',
               'service unavailable', 'server error', '接口无响应',
               '502', '503', '504', '501', '429', '上游')
    return any(m in text for m in markers)


def _basic_auth_phone(auth_value):
    try:
        raw = str(auth_value or '').strip()
        if raw.lower().startswith('basic '):
            raw = raw[6:].strip()
        decoded = base64.b64decode(raw).decode('utf-8', 'ignore')
        for sep in (':', '|'):
            parts = decoded.split(sep)
            if len(parts) >= 2 and re.match(r'^\d{11}$', parts[1].strip()):
                return parts[1].strip()
    except Exception:
        pass
    return ''


def _auth_expire_ms(auth_value):
    try:
        raw = str(auth_value or '').strip()
        if raw.lower().startswith('basic '):
            raw = raw[6:].strip()
        decoded = base64.b64decode(raw).decode('utf-8', 'ignore')
        parts = decoded.split(':', 2)
        token = parts[2] if len(parts) >= 3 else decoded
        fields = token.split('|')
        if len(fields) > 3:
            value = int(float(fields[3]))
            if value > 0:
                return value if value > 1_000_000_000_000 else value * 1000
    except Exception:
        pass
    return 0


def _set_token_expire_from_auth(account_id, auth_value):
    expires_at = _auth_expire_ms(auth_value)
    if expires_at:
        try:
            middleware.bucketSet('yuhua_ydyp_token_expire', account_id, str(expires_at))
        except Exception:
            pass
    return expires_at


def _jwt_user_domain_id(token):
    try:
        parts = str(token or '').split('.')
        if len(parts) < 2:
            return ''
        payload = parts[1] + '=' * (-len(parts[1]) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        sub = data.get('sub')
        if isinstance(sub, str):
            try:
                sub = json.loads(sub)
            except Exception:
                sub = None
        if isinstance(sub, dict):
            return str(sub.get('userDomainId') or '').strip()
    except Exception:
        pass
    return ''


def _looks_like_success(ret):
    if not isinstance(ret, dict):
        return False
    code = ret.get('code')
    if code not in (None, ''):
        return str(code).strip().lower() in ('0', '0.0', '0000', '000000', '200', 'success', 'ok', 'true')
    if ret.get('success') is True:
        return True
    text = str(ret.get('msg') or ret.get('message') or '').strip().lower()
    return text in ('success', 'ok', '成功')


def _response_message(ret, default='未知错误'):
    if not isinstance(ret, dict):
        return default
    for key in ('msg', 'message', 'resultMsg', 'subMsg', 'sub_msg'):
        value = ret.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    code = ret.get('code')
    if code not in (None, ''):
        return f"{default}(code={code})"
    return default


_QUERY_DEVICE_CACHE = {'device_id': '', 'expires_at': 0}


def _get_query_device_id():
    now = time.time()
    cached = _QUERY_DEVICE_CACHE.get('device_id') or ''
    if cached and now < _QUERY_DEVICE_CACHE.get('expires_at', 0):
        return cached
    try:
        ok, result = fetch_device_id()
    except Exception:
        ok, result = False, ''
    if ok and result:
        device_id = str(result).strip()
        if not device_id.upper().startswith('B'):
            device_id = 'B' + device_id
        _QUERY_DEVICE_CACHE['device_id'] = device_id
        _QUERY_DEVICE_CACHE['expires_at'] = now + 600
        return device_id
    return ''


def _device_id_with_prefix(value):
    value = str(value or '').strip()
    if not value:
        return ''
    return value if value.upper().startswith('B') else 'B' + value


def _is_exchange_terminal(message):
    text = str(message or '')
    patterns = (
        '兑换结果待确认', '兑换资格校验未通过', '非目标用户', '已兑完', '已耗尽',
        '奖品单日已耗尽', '奖品已兑完', '云朵不足', '已兑换', '今日已兑换',
        '本月已兑换', '已下架', '未登录', '账号未登录', '暂无权限', '账号失效', '账号已失效',
        '登录失效', '重新登录', '认证为空', 'JWT token 为空', 'Token 无效',
        '账号被封禁',
    )
    return any(pattern in text for pattern in patterns)


_SHUMEI_PUBLIC_KEY = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC8KHAcHbkCn5rxGgGJE+07tY+pt86D/oZ7sA51FaEBv2jgno2TI9zHJVYKJynmiKpixgwUcv93EfWIrU/p/UCs5Vu+odS3I4UBp3R7IZ1A0W01FkumAHYW2PQpMm8ueQKPLUq/idkpG/9b2JDv/qU+Ks36nbUPwlW4CjdfrV+V9QIDAQAB"
)
_SHUMEI_SDK_CONFIG = {'ConfusionInfo': {'appId': {'is_encrypt': 0, 'obfuscated_name': 'appId'},
                   'data': {'appId': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'a9kbown8', 'obfuscated_name': 'um'},
                            'box': {'is_encrypt': 0, 'obfuscated_name': 'aw'},
                            'canvas': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'ultuhs59', 'obfuscated_name': 'iu'},
                            'clientSize': {'cipher': 'DES', 'is_encrypt': 1, 'key': '7s9eixjh', 'obfuscated_name': 'na'},
                            'organization': {'cipher': 'DES', 'is_encrypt': 1, 'key': '14e30pp1', 'obfuscated_name': 'nl'},
                            'os': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'j862vr1f', 'obfuscated_name': 'lz'},
                            'platform': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'pgutfbo7', 'obfuscated_name': 'lm'},
                            'plugins': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'x98c92bm', 'obfuscated_name': 'hy'},
                            'pmf': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'gwvvsmr4', 'obfuscated_name': 'yu'},
                            'protocol': {'is_encrypt': 0, 'obfuscated_name': 'protocol'},
                            'referer': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'gka1ljjt', 'obfuscated_name': 'mf'},
                            'res': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'ht2n6dwf', 'obfuscated_name': 'ut'},
                            'rtype': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'k2p9ifij', 'obfuscated_name': 'fm'},
                            'sdkver': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'q4ij0mv5', 'obfuscated_name': 'ir'},
                            'status': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'moyspi7i', 'obfuscated_name': 'kp'},
                            'subVersion': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'egsyl21v', 'obfuscated_name': 'dk'},
                            'svm': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'yf780e9w', 'obfuscated_name': 'ee'},
                            'time': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'btb17oag', 'obfuscated_name': 'jt'},
                            'timezone': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'l94h8clc', 'obfuscated_name': 'bl'},
                            'tn': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'crnw0x7e', 'obfuscated_name': 'as'},
                            'trees': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'x6the9nq', 'obfuscated_name': 'ij'},
                            'ua': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'bewicpxu', 'obfuscated_name': 'pu'},
                            'url': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'llj8yd1x', 'obfuscated_name': 'sb'},
                            'version': {'is_encrypt': 0, 'obfuscated_name': 'version'},
                            'vpw': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'f1zlae4b', 'obfuscated_name': 'qb'}},
                   'organization': {'is_encrypt': 0, 'obfuscated_name': 'organization'},
                   'os': {'is_encrypt': 0, 'obfuscated_name': 'os'}},
 'Protocol': 4}
_DEVICE_SMID_CACHE = {}
_DEVICE_ID_CACHE = {'device_id': '', 'smid': '', 'expires_at': 0}


def _sdk_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _sdk_float_string(value):
    if value == 0:
        return '0'
    text = format(float(value), '.15g')
    if 'e' in text or 'E' in text:
        mantissa, exponent = text.lower().split('e')
        return f"{mantissa}e{int(exponent)}"
    return text


def _sdk_string(value):
    if value is None:
        return 'null'
    number = _sdk_number(value)
    if number is not None:
        return _sdk_float_string(number)
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (list, tuple)):
        return ','.join(_sdk_string(item) for item in value if item is not None)
    return '[object Object]'


def _sdk_checksum(profile):
    parts = []
    for key in sorted(profile.keys()):
        value = profile[key]
        number = _sdk_number(value)
        if number is not None:
            parts.append(_sdk_float_string(number * 10000))
        else:
            parts.append(_sdk_string(value))
    return hashlib.md5(''.join(parts).encode('utf-8')).hexdigest()


def _sdk_des(key, text):
    from Crypto.Cipher import DES
    units = []
    for char in str(text):
        code = ord(char)
        if code <= 0xFFFF:
            units.append(code)
        else:
            code -= 0x10000
            units.append(0xD800 + (code >> 10))
            units.append(0xDC00 + (code & 0x3FF))
    data = bytearray((len(units) + 7) // 8 * 8)
    for offset in range(0, len(data), 4):
        word = 0
        for index in range(4):
            if offset + index < len(units):
                word |= units[offset + index] << (24 - 8 * index)
        data[offset:offset + 4] = (word & 0xFFFFFFFF).to_bytes(4, 'big')
    cipher = DES.new(str(key).encode('utf-8'), DES.MODE_ECB)
    return base64.b64encode(cipher.encrypt(bytes(data))).decode('utf-8')


def _sdk_aes(text, key):
    from Crypto.Cipher import AES
    data = str(text).encode('utf-8')
    if len(data) % 16:
        data += b'\x00' * (16 - len(data) % 16)
    cipher = AES.new(str(key).encode('utf-8'), AES.MODE_CBC, b'0102030405060708')
    return cipher.encrypt(data).hex()


def _sdk_obfuscate(profile):
    config = _SHUMEI_SDK_CONFIG['ConfusionInfo']['data']
    result = {}
    for name, value in profile.items():
        field = config.get(name)
        if not field:
            result[name] = value
            continue
        if field.get('is_encrypt') and value is not None and _sdk_string(value) != '':
            if field.get('cipher') != 'DES':
                raise ValueError(f"unsupported SDK cipher {field.get('cipher')}")
            value = _sdk_des(field['key'], _sdk_string(value))
        result[field['obfuscated_name']] = value
    return result


def _sdk_data(profile, uid):
    fields = dict(profile)
    fields['tn'] = _sdk_checksum(profile)
    obfuscated = _sdk_obfuscate(fields)
    payload = json.dumps(obfuscated, ensure_ascii=False, separators=(',', ':'))
    compressed = bytearray(gzip.compress(payload.encode('utf-8'), compresslevel=6))
    # pako gzip header: no timestamp, OS=3
    compressed[4:8] = b'\x00\x00\x00\x00'
    compressed[9] = 3
    encoded = base64.b64encode(bytes(compressed)).decode('utf-8')
    key = hashlib.md5(str(uid).encode('utf-8')).hexdigest()[:16]
    return _sdk_aes(encoded, key)


def _smid(uid):
    base = (datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d%H%M%S')
            + hashlib.md5(str(uid).encode('utf-8')).hexdigest() + '00')
    check = hashlib.md5(('smsk_web_' + base).encode('utf-8')).hexdigest()[:14]
    return base + check + '0'


def _rsa_encrypt(plaintext):
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_v1_5
    key = RSA.import_key(base64.b64decode(_SHUMEI_PUBLIC_KEY))
    cipher = PKCS1_v1_5.new(key)
    return base64.b64encode(cipher.encrypt(str(plaintext).encode('utf-8'))).decode('utf-8')


def _generate_device_profile(ua, page_url):
    uid = str(uuid.uuid4())
    started = time.time()
    ep = _rsa_encrypt(uid)
    smid = _smid(uid)
    profile = {
        'protocol': _SHUMEI_SDK_CONFIG.get('Protocol', 4),
        'organization': YDYP_ORG,
        'appId': 'default',
        'os': 'web',
        'version': '3.0.0',
        'sdkver': '3.0.0',
        'box': '',
        'rtype': 'all',
        'smid': smid,
        'subVersion': '1.0.0',
        'time': int((time.time() - started) * 1000),
        'ua': ua,
        'url': page_url,
    }
    data = _sdk_data(profile, uid)
    payload = json.dumps({
        'appId': 'default',
        'organization': YDYP_ORG,
        'ep': ep,
        'data': data,
        'os': 'web',
        'encode': 5,
        'compress': 2,
    }, ensure_ascii=False, separators=(',', ':'))
    return payload, smid


###################### 移动云盘核心类 (YP) ######################
class YP:
    """
    用于移动云盘登录、刷新 Token、查询云朵数量等操作，
    每个实例都创建自己独立的 session。
    """
    
    def __init__(self, cookie_str, phone='未知'):
        """
        :param cookie_str: 格式 "Authorization值#(可选手机号)"
        :param phone:       用于标识账号
        """
        self.session = requests.Session()  # 为每个账号实例创建独立的 session
        self.token = None
        self.jwtToken = None
        self.total_amount = 0
        self.today_num = 0
        self.timestamp = str(int(round(time.time() * 1000)))
        self.cookies = {'sensors_stay_time': self.timestamp}
        self.ua = YDYP_MARKET_UA
        self.session.headers.update({'User-Agent': self.ua})
        parts = cookie_str.split("#")
        self.Authorization = parts[0].strip()
        phone = str(phone or '').strip()
        if not re.match(r'^\d{11}$', phone):
            phone = _basic_auth_phone(self.Authorization) or '未知'
        self.account = phone or "未知"
        self.market_base_url = YDYP_MARKET_HOST
        self.market_source_id = '1097'
        self.jwtHeaders = {
            'User-Agent': self.ua,
            'Accept': '*/*',
            'Host': 'm.mcloud.139.com',
        }
        self._market_session_ready = False
    
    def close(self):
        """关闭此账号实例的 session"""
        if self.session:
            self.session.close()

    def send_request(self, url, headers=None, data=None, method='GET', cookies=None, retries=3, delay=None):
        """
        使用此实例的 session 发送请求，并在请求前后增加随机延时
        增加了错误重试机制，确保在超时或异常时及时关闭连接并释放资源。
        delay=None 时使用默认随机延时；抢兑/滑块等关键请求传 0 以避免整点延迟。
        """
        if delay is None:
            delay = random.uniform(0.3, 0.7)
        if delay > 0:
            time.sleep(delay)
        for attempt in range(retries):
            started_at = time.time()
            try:
                if DEBUG:
                    printf(f"\n===== [REQUEST START] =====", "DEBUG")
                    printf(f"METHOD: {method} | URL: {url}", "DEBUG")
                    printf(f"HEADERS: {_debug_dump(headers or {})}", "DEBUG")
                    if data is not None:
                        printf(f"BODY(JSON): {_debug_dump(data)}", "DEBUG")
                    if cookies is not None:
                        printf(f"COOKIES: {_debug_dump(cookies)}", "DEBUG")

                # 使用实例自身的 self.session
                with self.session.request(method, url, headers=headers, json=data, cookies=cookies, timeout=15) as response:
                    response.raise_for_status()
                    body = response.json()
                    if DEBUG:
                        printf(f"----- [RESPONSE - Attempt {attempt + 1}] -----", "DEBUG")
                        printf(f"STATUS: {response.status_code} | ELAPSED: {int((time.time() - started_at) * 1000)}ms", "DEBUG")
                        printf(f"RSP HEADERS: {_debug_dump(dict(response.headers))}", "DEBUG")
                        printf(f"RSP BODY: {_debug_dump(body)}", "DEBUG")
                        printf(f"===== [REQUEST END] =====\n", "DEBUG")
                    return body
            except (requests.Timeout, requests.RequestException, Exception) as e:
                if DEBUG:
                    printf(f"⚠️ Attempt {attempt + 1} Failed: {str(e)}", "WARN")
                if attempt < retries - 1:
                    time.sleep(1)
                else:
                    return {"error": f"请求失败: {str(e)}"}

    def build_market_page_url(self, source_id=None, base_url=None):
        current_source_id = source_id or self.market_source_id
        base = (base_url or self.market_base_url).rstrip('/')
        return (f'{base}/portal/mobilecloud/index.html?path=newsignin'
                f'&sourceid={current_source_id}&enableShare=1'
                f'&token={urllib.parse.quote(self.token or "", safe="")}&targetSourceId=001005')

    def _exchange_jwt_via_gateway(self, sso_token):
        payload = {
            'token': sso_token,
            'openAccount': 0,
            'marketName': YDYP_MARKET_NAME,
            'sourceId': self.market_source_id,
        }
        last_err = ''
        for host in ('m.mcloud.139.com', 'gp.mcloud.139.com'):
            base = f'https://{host}'
            extra = {
                'User-Agent': self.ua,
                'Host': host,
                'Origin': 'https://m.mcloud.139.com',
                'Referer': self.build_market_page_url(),
                'activityid': YDYP_MARKET_NAME,
                'appversion': YDYP_APP_VERSION,
                'X-Requested-With': 'com.chinamobile.mcloud',
                'Cache-Control': 'no-cache',
                'showloading': 'true',
            }
            for attempt in range(3):
                headers = build_gateway_sign_headers(self.session, extra)
                data = self.send_request(
                    base + YDYP_AUTH_PATH,
                    headers=headers,
                    data=payload,
                    method='POST',
                    retries=1,
                )
                if data and not data.get('error'):
                    code = data.get('code')
                    if str(code) == '0':
                        result = data.get('result') or {}
                        token = result.get('token') if isinstance(result, dict) else None
                        if token:
                            return token, ''
                        last_err = f'{host}: 响应缺少 token'
                    else:
                        msg = data.get('msg') or data.get('message') or f'code={code}'
                        last_err = f'{host}: {msg}'
                        if str(code) not in ('404', '501', '502', '503', '504', '-1'):
                            return None, last_err
                elif data and data.get('error'):
                    last_err = f'{host}: {data["error"]}'
                else:
                    last_err = f'{host}: 接口无响应'
                if attempt < 2:
                    delay = min(2 ** attempt, 4)
                    printf(f'-网关换取JWT失败({last_err})，{delay}s 后重试', 'WARN')
                    time.sleep(delay)
        return None, last_err

    def _exchange_jwt_legacy(self, sso_token):
        legacy_headers = {
            'User-Agent': self.ua,
            'Accept': '*/*',
            'Host': 'caiyun.feixin.10086.cn:7071',
        }
        jwt_url = f"https://caiyun.feixin.10086.cn:7071/portal/auth/tyrzLogin.action?ssoToken={sso_token}"
        jwt_data = self.send_request(jwt_url, headers=legacy_headers, method='POST', retries=2)
        if not jwt_data or jwt_data.get('error'):
            return None, '接口无响应'
        if jwt_data.get('code') != 0:
            return None, jwt_data.get('msg', '未知错误')
        result = jwt_data.get('result') or {}
        token = result.get('token') if isinstance(result, dict) else None
        if not token:
            return None, '响应缺少 token'
        return token, ''
    
    def sso(self):
        common_headers = {
            'Authorization': self.Authorization,
            'User-Agent': self.ua,
            'Content-Type': 'application/json',
            'Accept': '*/*',
        }
        ret = self.send_request(
            'https://user-njs.yun.139.com/user/querySpecTokenV2',
            headers={**common_headers, 'Host': 'user-njs.yun.139.com'},
            data={"toSourceId": "001005"},
            method='POST',
            retries=4,
        )
        if (not ret) or ret.get("error") or not (
            ret.get('success') and isinstance(ret.get('data'), dict) and ret['data'].get('token')
        ):
            ret = self.send_request(
                'https://orches.yun.139.com/orchestration/auth-rebuild/token/v1.0/querySpecToken',
                headers={**common_headers, 'Host': 'orches.yun.139.com'},
                data={"account": self.account, "toSourceId": "001005"},
                method='POST',
                retries=4,
            )
        if not ret:
            return False, "网络请求失败"
        if ret.get("error"):
            error_msg = ret["error"]
            if "请求失败" in error_msg:
                return False, f"网络请求异常: {error_msg}"
            else:
                return False, error_msg
        if ret.get('success') and isinstance(ret.get('data'), dict) and ret['data'].get('token'):
            self.token = ret['data']['token']
            return True, "ok"
        else:
            message = ret.get('message', '未知错误')
            if any(keyword in message.lower() for keyword in ['unauthorized', 'invalid', 'expired', '无效', '过期', '失效']):
                return False, f"CK已失效: {message}"
            else:
                return False, f"请求异常: {message}"
    
    def _apply_jwt_cookies(self):
        if not self.jwtToken:
            return
        self.cookies['jwtToken'] = self.jwtToken
        self.cookies['sensors_stay_time'] = str(int(time.time() * 1000))
        domain_id = _jwt_user_domain_id(self.jwtToken)
        if domain_id:
            self.cookies['userDomainId'] = domain_id
        auth_b64 = self.Authorization[6:].strip() if self.Authorization.lower().startswith('basic ') else self.Authorization
        if auth_b64:
            self.cookies['cookieTokenKey'] = urllib.parse.quote(auth_b64, safe='')
        self.jwtHeaders['jwtToken'] = self.jwtToken
        self.jwtHeaders['jwttoken'] = self.jwtToken
        if re.match(r'^\d{11}$', self.account):
            try:

                middleware.bucketSet('yuhua_ydyp_jwt_by_phone', self.account, self.jwtToken)
            except Exception:
                pass

    def jwt(self):
        if not self.token:
            return False, "无可用 ssoToken"
        jwt_token, gateway_err = self._exchange_jwt_via_gateway(self.token)
        if jwt_token:
            self.jwtToken = jwt_token
            self._apply_jwt_cookies()
            return True, "ok"

        jwt_token, legacy_err = self._exchange_jwt_legacy(self.token)
        if jwt_token:
            self.jwtToken = jwt_token
            self._apply_jwt_cookies()
            return True, "ok"
        if is_transient_error(gateway_err) or is_transient_error(legacy_err):
            return False, f"JWT获取失败: 上游服务暂不可用（网关={gateway_err} 旧接口={legacy_err}）"
        return False, f"JWT获取失败: 网关={gateway_err} 旧接口={legacy_err}"

    
    def _prepare_market_session(self):
        if getattr(self, '_market_session_ready', False):
            return
        self._market_session_ready = True
        try:
            page_url = self.build_market_page_url()
            headers = {
                'User-Agent': YDYP_MARKET_UA,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': page_url,
            }
            with self.session.get(page_url, headers=headers, cookies=self.cookies, timeout=15) as resp:
                for cookie in self.session.cookies:
                    if cookie.name and cookie.value:
                        self.cookies[cookie.name] = cookie.value
                for cookie in resp.cookies:
                    if cookie.name and cookie.value:
                        self.cookies[cookie.name] = cookie.value
        except Exception:
            pass

    def _info_v3_once(self, base_url, host):
        """单端点查询云朵数量，返回 (ok, msg)。"""
        self._prepare_market_session()
        url = f"{base_url.rstrip('/')}/ycloud/signin/page/infoV3?client=app"
        headers = {
            'Host': host,
            'Connection': 'keep-alive',
            'sec-ch-ua-platform': '"Android"',
            'Cache-Control': 'no-cache',
            'sec-ch-ua': '"Chromium";v="108", "Android WebView";v="108", "Not/A)Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'showLoading': 'true',
            'appVersion': YDYP_APP_VERSION,
            'User-Agent': YDYP_MARKET_UA,
            'jwtToken': self.jwtToken or '',
            'jwttoken': self.jwtToken or '',
            'activityId': 'sign_in_3',
            'Accept': '*/*',
            'X-Requested-With': 'com.chinamobile.mcloud',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': self.build_market_page_url(base_url=f'https://{host}'),
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        device_id = _get_query_device_id()
        if device_id:
            headers['deviceId'] = device_id
        ret = self.send_request(url, headers=headers, cookies=self.cookies)
        if not ret:
            return False, "返回数据为空"
        if ret.get("error"):
            return False, ret["error"]
        if _looks_like_success(ret):
            result = ret.get("result")
            if not isinstance(result, dict):
                return False, "响应缺少 result"
            self.total_amount = result.get("total", 0) or 0
            self.to_receive = result.get("toReceive", 0) or 0
            return True, f"当前云朵数量: {self.total_amount}"
        return False, _response_message(ret, '查询云朵失败')

    def receive(self):
        """查询云朵数量；m 为主，gp 为兜底。"""
        errors = []
        for base_url, host in ((YDYP_MARKET_HOST, 'm.mcloud.139.com'),
                               (YDYP_GATEWAY_HOST, 'gp.mcloud.139.com')):
            ok, msg = self._info_v3_once(base_url, host)
            if ok:
                return True, msg
            errors.append(f'{host}: {msg}')
        return False, "；".join(errors)

    def _prize_log_once(self, base_url, host, api_name):
        """单端点查询待领奖品，返回 (ok, list 或错误文案)。"""
        timestamp = str(int(time.time() * 1000))
        prize_url = (f"{base_url.rstrip('/')}/ycloud/prizeApi/checkPrize/{api_name}"
                     f"?currPage=1&pageSize=15&_={timestamp}")
        headers = {
            'Host': host,
            'User-Agent': YDYP_MARKET_UA,
            'Accept': '*/*',
            'jwtToken': self.jwtToken or '',
            'jwttoken': self.jwtToken or '',
            'activityId': 'sign_in_3',
            'appVersion': YDYP_APP_VERSION,
            'X-Requested-With': 'com.chinamobile.mcloud',
            'Referer': self.build_market_page_url(base_url=f'https://{host}'),
            'showLoading': 'true',
            'Cache-Control': 'no-cache',
        }
        device_id = _get_query_device_id()
        if device_id:
            headers['deviceId'] = device_id
        ret = self.send_request(prize_url, headers=headers, cookies=self.cookies)
        if not ret:
            return False, "返回数据为空"
        if ret.get("error"):
            return False, ret["error"]
        if not _looks_like_success(ret):
            return False, _response_message(ret, '查询待领奖品失败')

        result = ret.get('result')
        if isinstance(result, dict):
            records = result.get('result') or result.get('records') or []
        elif isinstance(result, list):
            records = result
        else:
            records = []

        pending_prizes = []
        for value in records:
            if not isinstance(value, dict):
                continue
            prize_name = value.get('prizeName')
            try:
                flag = int(value.get('flag', 0))
            except Exception:
                flag = 0
            if flag == 1 and prize_name:  # flag=1表示待领取
                expire_time = str(value.get('expireTime') or '')
                if len(expire_time) >= 10:
                    # 截取前10位日期并将 '-' 替换为 '.' 以符合预期展示
                    expire_date = expire_time[:10].replace('-', '.')
                    pending_prizes.append(f"{prize_name},至{expire_date}失效")
                else:
                    pending_prizes.append(prize_name)
        return True, pending_prizes

    def get_pending_prizes(self):
        """获取待领取奖品列表；V2 优先、V1 兜底，m 主 gp 备。"""
        if not self.jwtToken:
            return False, "无 jwtToken, 无法查询待领奖品"
        errors = []
        for api_name in ('getUserPrizeLogPageV2', 'getUserPrizeLogPage'):
            for base_url, host in ((YDYP_MARKET_HOST, 'm.mcloud.139.com'),
                                   (YDYP_GATEWAY_HOST, 'gp.mcloud.139.com')):
                try:
                    ok, result = self._prize_log_once(base_url, host, api_name)
                except Exception as e:
                    ok, result = False, f"查询异常: {str(e)}"
                if ok:
                    return True, result
                errors.append(f'{api_name}@{host}: {result}')
        return False, "；".join(errors)


    def _cloud_record_page(self, base_url, host, page_number, page_size):
        """单端点读取一页云朵记录，返回 (ok, msg, result)。"""
        url = (f"{base_url.rstrip('/')}/signin/public/cloudRecord"
               f"?type=1&pageNumber={page_number}&pageSize={page_size}")
        headers = {
            'Host': host,
            'User-Agent': YDYP_MARKET_UA,
            'Accept': '*/*',
            'jwtToken': self.jwtToken or '',
            'jwttoken': self.jwtToken or '',
            'activityId': 'sign_in_3',
            'appVersion': YDYP_APP_VERSION,
            'X-Requested-With': 'com.chinamobile.mcloud',
            'Referer': self.build_market_page_url(base_url=f'https://{host}'),
        }
        device_id = _get_query_device_id()
        if device_id:
            headers['deviceId'] = device_id
        ret = self.send_request(url, headers=headers, cookies=self.cookies, method='GET')
        if not ret:
            return False, "接口无响应", None
        if ret.get("error"):
            return False, ret["error"], None
        if not _looks_like_success(ret):
            return False, _response_message(ret, '获取云朵记录失败'), None
        result = ret.get("result") if isinstance(ret.get("result"), dict) else {}
        return True, '', result

    def get_today_cloud(self):
        """统计今日新增云朵数量（多端点、多页）。"""
        if not self.jwtToken:
            return False, "无 jwtToken, 无法查询今日云朵"

        today_str = str(local_now().date())  # 北京时间的今日日期 (YYYY-MM-DD)
        # 仓库实现使用 caiyun/market 与 mrp/market；m/ycloud 也仍可用，依次兜底。
        candidates = (
            (f'{YDYP_MARKET_HOST}/ycloud', 'm.mcloud.139.com'),
            ('https://caiyun.feixin.10086.cn/market', 'caiyun.feixin.10086.cn'),
            ('https://mrp.mcloud.139.com/market', 'mrp.mcloud.139.com'),
        )
        last_error = ''
        for base_url, host in candidates:
            total = 0
            page_number = 1
            ok_any = False
            while page_number <= 10:
                ok, msg, result = self._cloud_record_page(base_url, host, page_number, 10)
                if not ok:
                    last_error = f'{host}: {msg}'
                    break
                ok_any = True
                records = result.get("records", []) if isinstance(result, dict) else []
                if not records:
                    break

                page_today_total = 0
                has_today_record = False
                reached_older = False
                for item in records:
                    if not isinstance(item, dict):
                        continue
                    insert_time = str(item.get('inserttime') or '')
                    if not insert_time:
                        continue
                    # inserttime 是 UTC 时间，需要转北京时间再按天统计
                    try:
                        if insert_time.endswith('+00:00'):
                            utc_time = datetime.fromisoformat(insert_time)
                        else:
                            utc_time = datetime.fromisoformat(insert_time.replace('Z', ''))
                            utc_time = utc_time.replace(tzinfo=timezone.utc)
                        day = str(utc_time.astimezone(timezone(timedelta(hours=8))).date())
                    except Exception:
                        day = insert_time[:10]
                    try:
                        num = int(item.get('num', 0) or 0)
                    except Exception:
                        num = 0
                    if day == today_str and num > 0:
                        page_today_total += num
                        has_today_record = True
                    elif day < today_str:
                        # 记录按时间倒序，遇到今天之前的记录即可停止
                        reached_older = True
                        break

                total += page_today_total
                if reached_older or not has_today_record:
                    break
                current_page = result.get("current", page_number)
                total_pages = result.get("pages", 1)
                if current_page >= total_pages:
                    break
                page_number += 1

            if ok_any:
                self.today_num = total
                return True, f"今日云朵: {total}"
        return False, last_error or "获取云朵记录失败"

    def _exchange_cookies(self, device_id, extra=None):
        """构造兑换会话 Cookie：jwtToken/userDomainId/cookieTokenKey/.thumbcache。"""
        cookies = dict(self.cookies)
        if self.jwtToken:
            cookies['jwtToken'] = self.jwtToken
            domain_id = _jwt_user_domain_id(self.jwtToken)
            if domain_id:
                cookies['userDomainId'] = domain_id
        auth_b64 = self.Authorization[6:].strip() if self.Authorization.lower().startswith('basic ') else self.Authorization
        if auth_b64:
            cookies['cookieTokenKey'] = urllib.parse.quote(auth_b64, safe='')
        device_id = _device_id_with_prefix(device_id)
        if device_id:
            thumb_value = device_id[1:] if device_id.startswith('B') else device_id
            cookies[f'.thumbcache_{YDYP_ORG_MD5}'] = urllib.parse.quote(thumb_value, safe='')
            smid = _DEVICE_SMID_CACHE.get(device_id) or _DEVICE_SMID_CACHE.get(device_id[1:])
            if smid:
                cookies['smidV2'] = smid
        if extra:
            cookies.update(extra)
        return cookies

    def _exchange_headers(self, device_id, extra=None, with_device=True):
        headers = {
            'Host': 'm.mcloud.139.com',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json;charset=UTF-8',
            'User-Agent': YDYP_MARKET_UA,
            'Accept': '*/*',
            'Origin': 'https://m.mcloud.139.com',
            'X-Requested-With': 'com.chinamobile.mcloud',
            'appversion': YDYP_APP_VERSION,
            'activityid': 'sign_in_3',
            'jwttoken': self.jwtToken or '',
            'Referer': self.build_market_page_url(),
            'Cache-Control': 'no-cache',
            'showLoading': 'true',
        }
        device_id = _device_id_with_prefix(device_id)
        if device_id:
            headers['deviceId'] = device_id
        if with_device:
            headers['isDeviceId'] = 'true'
        if extra:
            headers.update(extra)
        return headers

    def check_exchange_eligibility(self, prize_id, device_id=''):
        """兑换前资格预检；返回 (ok, msg)。"""
        try:
            pid = int(str(prize_id).strip())
        except Exception:
            return False, '商品 prizeId 格式无效'
        url = (f"{YDYP_MARKET_HOST}/ycloud/signin/page/receivePrizeDetails"
               f"?marketId={YDYP_EXCHANGE_MARKET_ID}&prizeId={pid}")
        headers = self._exchange_headers('', with_device=False)
        ret = self.send_request(url, headers=headers, cookies=self._exchange_cookies(device_id), retries=1, delay=0)
        if not ret:
            printf(f"资格预检无响应: prizeId={pid}", 'WARN')
            return False, '兑换资格校验接口无响应'
        if ret.get('error'):
            printf(f"资格预检请求错误: prizeId={pid} err={ret['error']}", 'WARN')
            return False, ret['error']
        if not _looks_like_success(ret):
            message = _response_message(ret, '兑换资格校验失败')
            printf(f"资格预检失败: prizeId={pid} code={ret.get('code')} msg={message}", 'WARN')
            return False, message
        result = ret.get('result') if isinstance(ret.get('result'), dict) else {}
        if 'exchangeCode' not in result:
            printf(f"资格预检缺少exchangeCode: prizeId={pid}", 'WARN')
            return False, '兑换资格响应缺少 exchangeCode'
        code = str(result.get('exchangeCode') if result.get('exchangeCode') is not None else '').strip()
        printf(f"资格预检: prizeId={pid} exchangeCode={code}", 'INFO')
        if code and code != '0':
            reason = {
                '2302': '当月兑换第三方奖品数量已达上限，下月再来',
                '2303': '需开启自动备份且本月成功备份照片才可兑换',
                '2305': '非目标用户（该奖品有用户范围限制，例如仅限中国移动用户）',
            }.get(code, '上游未给出具体原因')
            return False, f"兑换资格校验未通过: exchangeCode={code}（{reason}）"
        return True, ''

    def exchange_v3(self, prize_id, puzzle_offset, device_id):
        """提交 exchangeV3；返回 (success, message, terminal)。"""
        try:
            pid = int(str(prize_id).strip())
        except Exception:
            return False, '商品 prizeId 格式无效', True
        device_id = _device_id_with_prefix(device_id)
        if not device_id:
            return False, '设备标识为空，未提交兑换', True
        body = {
            'prizeId': pid,
            'client': 'app',
            'clientVersion': YDYP_CLIENT_VERSION,
            'puzzleOffset': int(puzzle_offset),
            'smsCode': '',
            'deviceId': device_id,
        }
        url = f"{YDYP_MARKET_HOST}/ycloud/signin/page/exchangeV3"
        headers = self._exchange_headers(device_id, extra={'isDeviceId': 'true'})
        cookies = self._exchange_cookies(device_id)
        # 兑换不做自动重试，避免超时后重复提交；重试由外层显式控制
        exchange_started = time.time()
        printf(f"提交exchangeV3: prizeId={pid} offset={puzzle_offset} device={device_id[:12]}...", 'INFO')
        ret = self.send_request(url, headers=headers, data=body, method='POST', cookies=cookies, retries=1, delay=0)
        elapsed_ms = int((time.time() - exchange_started) * 1000)
        if not ret:
            printf(f"exchangeV3无响应: prizeId={pid} elapsed={elapsed_ms}ms", 'WARN')
            return False, '兑换接口无响应', False
        if ret.get('error'):
            printf(f"exchangeV3请求错误: prizeId={pid} err={ret['error']} elapsed={elapsed_ms}ms", 'WARN')
            return False, ret['error'], False
        message = _response_message(ret, '兑换失败')
        code = ret.get('code')
        printf(f"exchangeV3回包: prizeId={pid} code={code} msg={str(message)[:160]} elapsed={elapsed_ms}ms", 'INFO')
        if not _looks_like_success(ret):
            if '活动太火爆啦' in message or '锁定失败' in message:
                message += '。'
            return False, message, _is_exchange_terminal(message)
        result = ret.get('result') if isinstance(ret.get('result'), dict) else {}
        oid = result.get('oid') or result.get('oId')
        returned_prize = str(result.get('prizeId') or '').strip()
        if not oid or (returned_prize and returned_prize != str(pid)):
            return False, '兑换结果待确认，请到领奖专区核对（回包缺少奖品记录或商品不一致）', True
        prize_name = result.get('prizeName') or result.get('name') or ''
        return True, (f"兑换成功：{prize_name}" if prize_name else '兑换成功'), True

def gen_unique_id(prefix=""):
    timestamp = int(time.time() * 1_000_000)
    return f"{prefix}{timestamp}"

senderID = middleware.getSenderID()
sender = middleware.Sender(senderID)
userid = sender.getUserID()
uservalue = middleware.bucketGet(bucket='yuhua_ydyp_user', key=userid)


def get_config():
    """获取插件配置"""
    var_name = middleware.bucketGet('yuhua_ydyp', 'var_name') or 'ydyp'
    ql_config = middleware.bucketGet('yuhua_ydyp', 'ql_config') or ''
    manage_cmd = middleware.bucketGet('yuhua_ydyp', 'manage_cmd') or '云盘管理'
    query_cmd = middleware.bucketGet('yuhua_ydyp', 'query_cmd') or '云盘查询'
    login_cmd = middleware.bucketGet('yuhua_ydyp', 'login_cmd') or '云盘登录'
    price = Decimal(middleware.bucketGet('yuhua_ydyp', 'price') or '0')
    coin_price = int(middleware.bucketGet('yuhua_ydyp', 'coin') or '0')
    bf_str = middleware.bucketGet('yuhua_ydyp', 'bingfa') or '20'
    try:
        bf_num = int(bf_str)
    except:
        bf_num = 20
    return (var_name, ql_config, manage_cmd, query_cmd, login_cmd, price, coin_price, bf_num)

def init_qinglong():
    """初始化青龙连接"""
    try:
        if not ql_config:
            sender.reply("❌ 未配置青龙信息")
            exit(0)
        ql_params = ql_config.split('丨')
        if len(ql_params) != 3:
            sender.reply("❌ 青龙配置格式错误")
            exit(0)
        ql_url = ql_params[0].strip().rstrip('/')
        client_id = ql_params[1].strip()
        client_secret = ql_params[2].strip()
        if not all([ql_url, client_id, client_secret]):
            sender.reply("❌ 青龙配置参数不完整")
            exit(0)
        token = get_ql_token(ql_url, client_id, client_secret)
        return ql_url, token
    except Exception as e:
        sender.reply(f"❌ 连接青龙失败")
        exit(0)

def get_ql_token(url, client_id, client_secret):
    """获取青龙token"""
    try:
        token_url = f'{url}/open/auth/token?client_id={client_id}&client_secret={client_secret}'
        session = get_global_session()
        with session.get(token_url, timeout=10) as r:
            if r.status_code != 200:
                raise Exception(f"请求失败: {r.status_code}")
            data = r.json()
        if "token" not in data.get('data', {}):
            raise Exception("获取token失败")
        return data['data']['token']
    except Exception as e:
        raise Exception(f"获取token失败: {str(e)}")

def add_to_qinglong(token_value, account, phone, target_user=None):
    """
    添加变量到青龙，保留原有判断逻辑：只判断 r2.status_code 是否为200
    target_user 为目标用户ID，如为空则使用全局 userid（用户自操作时）；
    管理员授权时请传入对应目标用户ID，确保上传青龙变量时 userid 为目标用户而非管理员。
    """
    try:
        time.sleep(random.uniform(0.3, 0.8))
        url = f"{ql_url}/open/envs"
        headers = {
            "Authorization": f"Bearer {ql_token}",
            "Content-Type": "application/json"
        }
        session = get_global_session()
        session.headers.update(headers)
        with session.get(url, timeout=10) as r1:
            if r1.status_code != 200:
                raise Exception("获取变量失败")
            envs = r1.json().get('data', [])
        exists_id = None
        for env in envs:
            if env.get('name') == var_name and f"UID:{account}" in env.get('remarks', ''):
                exists_id = env.get('id')
                break
        remarks_user = target_user if target_user else userid
        data = {
            "name": var_name,
            "value": token_value,
            "remarks": f"UID:{account}丨用户:{remarks_user}丨手机:{phone}"
        }
        if exists_id:
            data['id'] = exists_id
            with session.put(url, json=data, timeout=10) as r2:
                if r2.status_code != 200:
                    raise Exception("更新变量失败")
        else:
            with session.post(url, json=[data], timeout=10) as r2:
                if r2.status_code != 200:
                    raise Exception("提交变量失败")
        return True
    except Exception as e:
        sender.reply(f"❌ 青龙操作失败: {str(e)}")
        return False

def delete_from_qinglong(account):
    """
    从青龙删除变量 (匹配 "UID:{account}")
    """
    try:
        time.sleep(random.uniform(0.3, 0.8))
        url = f"{ql_url}/open/envs"
        headers = {
            "Authorization": f"Bearer {ql_token}"
        }
        session = get_global_session()
        session.headers.update(headers)
        with session.get(url, timeout=10) as resp:
            if resp.status_code != 200:
                raise Exception("获取变量失败")
            envs = resp.json().get('data', [])
        env_id = None
        for env in envs:
            if env.get('name') == var_name and f"UID:{account}" in env.get('remarks', ''):
                env_id = env.get('id')
                break
        if env_id:
            with session.delete(url, json=[env_id], timeout=10) as rdel:
                if rdel.status_code != 200:
                    raise Exception("删除变量失败")
        return True
    except Exception as e:
        sender.reply(f"❌ 青龙操作失败: {str(e)}")
        return False


def _enable_envs_in_qinglong(id_list):
    """启用指定的青龙环境变量条目（保留函数，后续在登录/更新CK路径中按需调用）。"""
    if not id_list:
        return False
    try:
        url = f"{ql_url}/open/envs/enable"
        headers = {
            "Authorization": f"Bearer {ql_token}",
            "Content-Type": "application/json"
        }
        session = get_global_session()
        session.headers.update(headers)
        with session.put(url, json=id_list, timeout=10) as resp:
            return resp.status_code == 200
    except Exception:
        return False


###################
#   逻辑函数区块   #
###################
def login():
    """账号登录"""
    login_guide = """
=====登录方式=====
[1] 短信登录
[2] Cookie登录
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
        if choice == '1':
            sms_login()
        elif choice == '666':
            password_login()
        elif choice == '2':
            cookie_login()
        else:
            sender.reply("❌ 无效的选择")
            return
            
    except Exception as e:
        sender.reply(f"❌ 登录失败: {str(e)}")
        return

def cookie_login():
    """
    【登录函数】校验 CK，若有效则保存
    """
    guide = """
=====账号登录=====
❶ 下载Via浏览器访问 yun.139.com/m/#/login 完成登录，左上角查看Cookies找到参数authorization的值『Basic xxxxx』
❷请勿点击退出将导致CK失效，多号用户请清软件数据重复操作，不用带『;』号，分隔『#』号是英文符，参数『Basic xxxxx』内的空格不能删
❸按如下格式发送
『参数值#手机号』 例: Basic xxxxx#110
------------------
回复"q"退出"""
    sender.reply(guide)
    user_input = sender.input(60000, 1, False)
    if not user_input:  # 如果超时未输入
        sender.reply("❌ 输入超时")
        return
    elif user_input.lower() == 'q':  # 输入q时退出
        sender.reply("✅ 已退出操作")
        return
    parts = user_input.split('#')
    auth_str = parts[0].strip()
    phone = parts[1].strip() if len(parts) > 1 else "未知"
    yp_check = YP(auth_str, phone=phone)
    ok, msg = yp_check.sso()
    yp_check.close()
    if not ok:
        sender.reply(f"❌ 登录失败: {msg}")
        return
    accounts = eval(uservalue or '[]')
    matched_uid = None
    for uid in accounts:
        old_phone = middleware.bucketGet('yuhua_ydyp_phone', uid) or "未知"
        if old_phone == phone and phone != "未知":
            matched_uid = uid
            break
    if matched_uid:
        middleware.bucketSet('yuhua_ydyp_token', matched_uid, user_input)
        _set_token_expire_from_auth(matched_uid, user_input)
        try:
            middleware.bucketDel('yuhua_ydyp_password', matched_uid)
        except Exception:
            pass
        phone = middleware.bucketGet('yuhua_ydyp_phone', matched_uid) or "未知"
        phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
        auth_time = middleware.bucketGet('yuhua_ydyp_auth', matched_uid)
        if auth_time and auth_time > str(local_now().date()):
            # 仅在登录/更新CK时同步青龙并启用（CK有效期内）
            if add_to_qinglong(user_input, matched_uid, phone):
                try:
                    # 启用该条变量（按 UID 匹配查找 id）
                    ql_envs = get_global_session().get(f"{ql_url}/open/envs", headers={"Authorization": f"Bearer {ql_token}"}, timeout=10)
                    if ql_envs.status_code == 200:
                        items = ql_envs.json().get('data', [])
                        ids = [e.get('id') for e in items if e.get('name') == var_name and f"UID:{matched_uid}" in str(e.get('remarks',''))]
                        if ids:
                            _enable_envs_in_qinglong(ids)
                except Exception:
                    pass
            sender.reply(f"""
=====登录成功=====
🤪 账号: {phone_mask}
✅ 状态: 更新成功
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")
        else:
            sender.reply(f"""
=====登录成功=====
🤪 账号: {phone_mask}
✅ 状态: 更新成功
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")
        return
    unique_id = gen_unique_id()
    if unique_id not in accounts:
        accounts.append(unique_id)
        middleware.bucketSet('yuhua_ydyp_user', userid, str(accounts))
    middleware.bucketSet('yuhua_ydyp_token', unique_id, user_input)
    _set_token_expire_from_auth(unique_id, user_input)
    middleware.bucketSet('yuhua_ydyp_phone', unique_id, phone)
    phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
    sender.reply(f"""
=====登录成功=====
🤪 账号: {phone_mask}
✅ 状态: 添加成功
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")

def _get_auth_status_details(acc_unique_id):
    """获取授权状态详情，返回 (图标, 状态文本)"""
    auth_time_str = middleware.bucketGet('yuhua_ydyp_auth', acc_unique_id)
    if not auth_time_str:
        return "⚠️", "未授权"
    try:
        auth_date = datetime.strptime(auth_time_str, "%Y-%m-%d").date()
        if auth_date >= local_now().date():
            return "✅", auth_time_str
        else:
            return "❌", "已过期"
    except ValueError:
        return "⚠️", "日期异常"

def _query_single_account(unique_id):
    """
    【内部函数】用于并发查询单个账号的云朵信息。
    """
    time.sleep(random.uniform(0.5, 1.0))
    phone = middleware.bucketGet('yuhua_ydyp_phone', unique_id) or "未知"
    if not re.match(r'^\d{11}$', phone):
        phone = _basic_auth_phone(middleware.bucketGet('yuhua_ydyp_token', unique_id) or '') or phone
    phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
    auth_time = middleware.bucketGet('yuhua_ydyp_auth', unique_id)
    now_date = local_now().date()

    if not auth_time:
        return f"【{phone_mask}】未授权"

    try:
        auth_date = datetime.strptime(auth_time, "%Y-%m-%d").date()
    except ValueError:
        return f"【{phone_mask}】授权日期异常: {auth_time}"
    if auth_date < now_date:
        return f"【{phone_mask}】授权已过期"

    # 接入自动刷新与检查校验体系
    ok_ck, ck_str, ck_msg = check_and_refresh_token(unique_id)
    if not ok_ck and not ck_str:
        return f"【{phone_mask}】{ck_msg}"

    yp = YP(ck_str, phone=phone)
    try:
        ok1, msg1 = yp.sso()
        if not ok1:
            msg1_str = str(msg1)
            need_relogin = (
                any(keyword in msg1_str.lower() for keyword in['unauthorized', 'invalid', 'expired', 'authorization'])
                or any(keyword in msg1_str for keyword in ['无效', '过期', '失效', '未登录', '登录失效'])
                or '05050006' in msg1_str
                or '4006' in msg1_str
            )
            if need_relogin:
                # 遇到SSO直接拒绝，强制触发底层刷新刷新
                ok_force, ck_str_force, force_msg = check_and_refresh_token(unique_id, force=True)
                if ok_force and ck_str_force:
                    yp.close()
                    yp = YP(ck_str_force, phone=phone)
                    ok1, msg1 = yp.sso()
                    if not ok1:
                        return f"【{phone_mask}】SSO失败: {msg1}"
                else:
                    return f"【{phone_mask}】强制刷新失败: {force_msg}"
            else:
                return f"【{phone_mask}】SSO失败: {msg1}"

        ok2, msg2 = yp.jwt()
        if not ok2:
            return f"【{phone_mask}】获取jwt失败: {msg2}"

        ok3, msg3 = yp.receive()
        if not ok3:
            return f"【{phone_mask}】查询云朵出错: {msg3}"

        ok4, msg4 = yp.get_today_cloud()
        today_str = str(yp.today_num) if ok4 else f"查询失败({msg4})"

        # 获取待领奖品
        ok5, prizes_result = yp.get_pending_prizes()
        if ok5:
            if prizes_result:
                if len(prizes_result) == 1:
                    prizes_str = prizes_result[0]
                else:
                    prizes_str = "\n" + "\n".join(prizes_result)
            else:
                prizes_str = "暂无"
        else:
            prizes_str = f"查询失败({prizes_result})"

        return f"""
=====账号信息=====
🤪 用户账号: {phone_mask}
💰 当前云朵: {yp.total_amount}
🔥 今日云朵: {today_str}
☁️ 授权到期: {auth_time}
🎉 待领奖品: {prizes_str}
=================="""
    finally:
        yp.close()

def query_account():
    """
    【云盘查询】：查询已授权账号的云朵数量（并发版）
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

    # 读取并发配置，与抢兑功能保持一致
    bf_num_local = bingfa  

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

    account_display_parts = ["=====账号列表=====", "[0] 授权全部账号", "------------------"]
    for i, acc_unique_id in enumerate(accounts, 1):
        phone = middleware.bucketGet('yuhua_ydyp_phone', acc_unique_id) or "未知"
        display_name = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
        icon, status_text = _get_auth_status_details(acc_unique_id)
        
        account_info = f"""[{i}] 账号信息
🤪 账号: {display_name}
☁ 授权: {icon} {status_text}"""
        account_display_parts.append(account_info)
        account_display_parts.append("------------------")

    account_display_parts.extend(["回复数字选择", "回复'q'退出", "=================="])
    manage_guide = "\n".join(account_display_parts)
    sender.reply(manage_guide)

    choice_str = sender.input(60000, 0, False)
    if not choice_str: sender.reply("❌ 输入超时"); return
    if choice_str.lower() == 'q': sender.reply("✅ 已退出操作"); return

    try:
        choice_idx = int(choice_str)
        if choice_idx == 0:
            _handle_user_batch_authorization_by_month(sender, accounts)
        elif 1 <= choice_idx <= len(accounts):
            show_account_menu(accounts[choice_idx - 1])
        else:
            raise ValueError("选择超出范围")
    except ValueError:
        sender.reply("❌ 无效的选择")

def show_account_menu(account):
    """显示账号操作菜单"""
    menu = """
=====账号操作=====
[1] 授权账号
[2] 云盘兑换
[3] 删除账号
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
        show_exchange_menu_ydyp(account)
    elif choice == '3':
        confirm_delete(account)
    else:
        sender.reply("❌ 无效的选择")


def confirm_delete(account):
    """确认是否删除账号"""
    phone = middleware.bucketGet('yuhua_ydyp_phone', account) or "未知"
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
    【删除账号】：删除本地及青龙上的变量记录
    """
    phone = middleware.bucketGet('yuhua_ydyp_phone', account) or "未知"
    phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
    accounts = eval(uservalue or '[]')
    if account not in accounts:
        sender.reply("❌ 未找到账号")
        return
    accounts.remove(account)
    middleware.bucketSet('yuhua_ydyp_user', userid, str(accounts))
    try:
        middleware.bucketDel('yuhua_ydyp_token', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_ydyp_auth', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_ydyp_phone', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_ydyp_password', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_ydyp_prize_regular', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_ydyp_device_id', account)
    except Exception:
        pass
    delete_from_qinglong(account)
    sender.reply(f"✅ 已删除账号 {phone_mask}")

def _handle_user_batch_authorization_by_month(sender, account_ids):
    """处理普通用户批量按月授权的函数。"""
    if not account_ids:
        sender.reply("❌ 未找到可授权的账号")
        return

    price_prompt = f"授权价格: {price}元/月\n" if price > 0 else ""
    prompt = f"""=====一键授权=====
{price_prompt}请输入授权月数
------------------
回复数字设置月数
回复"q"退出"""
    sender.reply(prompt)
    
    months_str = sender.input(60000, 0, False)
    if not months_str or months_str.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    try:
        months = int(months_str)
        if months <= 0: raise ValueError("月份必须为正数")
    except (ValueError, AssertionError):
        sender.reply("❌ 无效的月数")
        return

    total_amount = price * months * len(account_ids)
    if total_amount > 0:
        if not process_payment(total_amount, months, f"批量({len(account_ids)}个)"):
            return

    success_count = 0
    fail_count = 0
    days_to_add = months * 30
    for acc_id in account_ids:
        try:
            new_auth_date_str = calculate_auth_time_by_days(acc_id, days_to_add)
            middleware.bucketSet(f'yuhua_ydyp_auth', acc_id, new_auth_date_str)
            
            # 同步青龙
            ck_str = middleware.bucketGet('yuhua_ydyp_token', acc_id)
            phone = middleware.bucketGet('yuhua_ydyp_phone', acc_id) or "未知"
            if ck_str:
                add_to_qinglong(ck_str, acc_id, phone)
            
            success_count += 1
        except Exception as e:
            fail_count += 1

    summary_msg = f"""=====授权完成=====
✅ 成功: {success_count}个账号
❌ 失败: {fail_count}个账号
⏰ 时长: 授权{months}月
==================""";
    sender.reply(summary_msg)

def auth_account(account):
    """
    【账号授权】：输入授权时长，处理支付（如配置了价格）后计算授权到期时间，
    并同步青龙变量
    """
    phone = middleware.bucketGet('yuhua_ydyp_phone', account) or "未知"
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
    if not months_str:  # 如果超时未输入
        sender.reply("❌ 输入超时")
        return
    elif months_str.lower() == 'q':  # 输入q时退出
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
    
    days_to_add = months * 30
    auth_time = calculate_auth_time_by_days(account, days_to_add)
    middleware.bucketSet('yuhua_ydyp_auth', account, auth_time)
    ck_str = middleware.bucketGet('yuhua_ydyp_token', account)

    if ck_str:
        add_to_qinglong(ck_str, account, phone)

    sender.reply(f"""
=====授权成功=====
🤪 账号: {phone_mask}
⏰ 时长: {days_to_add}天
📅 到期: {auth_time}
==================""")

def process_payment(amount, months, phone_mask):
    """处理支付"""
    zsm = middleware.bucketGet('yuhua_ydyp', 'zsm')
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

def calculate_auth_time_by_days(account, days):
    """
    根据天数计算授权到期时间 (支持负数扣除)
    """
    current = local_now().date()
    auth = middleware.bucketGet('yuhua_ydyp_auth', account)
    start = current
    if auth:
        try:
            auth_date = datetime.strptime(auth, "%Y-%m-%d").date()
            if auth_date > current:
                start = auth_date
        except ValueError:
            pass # 日期格式错误则从今天开始
            
    end_date = start + timedelta(days=days)
    return end_date.strftime("%Y-%m-%d")

def clean_expired():
    """清理过期账号"""
    if not sender.isAdmin():
        sender.reply("❌ 需要管理员权限")
        return
    sender.reply("正在清理...")
    today_str = str(local_now().date())
    valid_acc_ids = set()
    all_existing_acc_ids = set()

    try:
        users = middleware.bucketAllKeys('yuhua_ydyp_user') or []
    except Exception:
        users = []

    for user in users:
        accounts = eval(middleware.bucketGet('yuhua_ydyp_user', user) or '[]')
        still_valid_for_user = []
        for acc_id in accounts:
            auth = middleware.bucketGet('yuhua_ydyp_auth', acc_id)
            if auth and auth > today_str:
                valid_acc_ids.add(acc_id)
                still_valid_for_user.append(acc_id)
        
        if still_valid_for_user:
            middleware.bucketSet('yuhua_ydyp_user', user, str(still_valid_for_user))
        else:
            try:
                middleware.bucketDel('yuhua_ydyp_user', user)
            except Exception:
                pass

    for bucket_name in ['yuhua_ydyp_token', 'yuhua_ydyp_phone', 'yuhua_ydyp_auth', 'yuhua_ydyp_password', 'yuhua_ydyp_prize_regular', 'yuhua_ydyp_token_expire', 'yuhua_ydyp_device_id']:
        try:
            keys = middleware.bucketAllKeys(bucket_name) or []
            for key in keys:
                all_existing_acc_ids.add(key)
        except Exception:
            continue

    accounts_to_delete = all_existing_acc_ids - valid_acc_ids

    if accounts_to_delete:
        for acc_id in accounts_to_delete:
            try:
                middleware.bucketDel('yuhua_ydyp_token', acc_id)
            except Exception:
                pass
            try:
                middleware.bucketDel('yuhua_ydyp_auth', acc_id)
            except Exception:
                pass
            try:
                middleware.bucketDel('yuhua_ydyp_phone', acc_id)
            except Exception:
                pass
            try:
                middleware.bucketDel('yuhua_ydyp_password', acc_id)
            except Exception:
                pass
            try:
                middleware.bucketDel('yuhua_ydyp_prize_regular', acc_id)
            except Exception:
                pass
            try:
                middleware.bucketDel('yuhua_ydyp_token_expire', acc_id)
            except Exception:
                pass
            try:
                middleware.bucketDel('yuhua_ydyp_device_id', acc_id)
            except Exception:
                pass
            delete_from_qinglong(acc_id)
    sender.reply(f"✅ 已清理 {len(accounts_to_delete)} 个授权已过期或无效的账号")

def cron_task():
    """定时任务处理"""
    if imtype == 'fake':
        pass
    today_str = str(local_now().date())
    try:
        users = middleware.bucketAllKeys('yuhua_ydyp_user')
        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_ydyp_user', user) or '[]')
            for acc_id in accounts:
                time.sleep(random.uniform(0.5, 1.0))
                yp = None
                try:
                    phone = middleware.bucketGet('yuhua_ydyp_phone', acc_id) or "未知"
                    
                    # 接入自动刷新与检查校验体系
                    ok_ck, ck_str, ck_msg = check_and_refresh_token(acc_id)
                    if not ok_ck and not ck_str:
                        notify_user(user, acc_id, ck_msg)
                        continue
                        
                    yp = YP(ck_str, phone=phone)
                    ok_sso, msg_sso = yp.sso()
                    if not ok_sso:
                        msg_sso_str = str(msg_sso)
                        need_relogin = any(keyword in msg_sso_str.lower() for keyword in ['unauthorized', 'invalid', 'expired', 'authorization']) or any(keyword in msg_sso_str for keyword in ['无效', '过期', '失效'])
                        if need_relogin:
                            # 遇到SSO直接拒绝，强制触发底层刷新
                            ok_force, ck_str_force, force_msg = check_and_refresh_token(acc_id, force=True)
                            if ok_force and ck_str_force:
                                yp.close()
                                yp = None
                                yp = YP(ck_str_force, phone=phone)
                                ok_sso, msg_sso = yp.sso()
                                if not ok_sso:
                                    notify_user(user, acc_id, f"登录已失效且刷新失败: {msg_sso}")
                                    continue
                            else:
                                notify_user(user, acc_id, f"登录已失效且刷新失败: {force_msg}")
                                continue
                        else:
                            notify_user(user, acc_id, msg_sso)
                            continue
                            
                    auth_time = middleware.bucketGet('yuhua_ydyp_auth', acc_id)
                    if not auth_time or auth_time <= today_str:
                        notify_user(user, acc_id, "授权已过期，请及时续费")
                except Exception as e:
                    print(f"处理账号 {acc_id} 出错: {str(e)}")
                    continue
                finally:
                    if yp:
                        yp.close()
    except Exception as e:
        print(f"定时任务出错: {str(e)}")

notified_accounts = set()
def notify_user(user, account, message):
    """发送用户通知"""
    try:
        if account in notified_accounts:
            return
        phone = middleware.bucketGet('yuhua_ydyp_phone', account) or "未知"
        phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
        notify_msg = f"""
=====云盘通知=====
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

def retry_on_error(func, retries=3, delay=1):
    """错误重试装饰器"""
    def wrapper(*args, **kwargs):
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if i == retries - 1:
                    raise e
                time.sleep(delay)
        return None
    return wrapper

def log_operation(operation, user, account, status, message=''):
    """记录操作日志(仅存储到bucket，不再自动推送给用户)"""
    try:
        log = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'operation': operation,
            'user': user,
            'account': account,
            'status': status,
            'message': message
        }
        logs = eval(middleware.bucketGet('yuhua_ydyp_logs', 'operations') or '[]')
        logs.append(log)
        if len(logs) > 1000:
            logs = logs[-1000:]
        middleware.bucketSet('yuhua_ydyp_logs', 'operations', str(logs))
    except Exception as e:
        print(f"记录日志失败: {str(e)}")

def admin_auth():
    """管理员授权功能"""
    auth_menu = """
=====授权管理=====
[1] 授权所有用户
[2] 授权指定用户
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
=====批量操作=====
请输入授权天数
------------------
回复数字设置天数
回复"q"退出""")
    try:
        days_str = sender.input(60000, 0, False)
        if not days_str:
            sender.reply("❌ 输入超时")
            return
        if days_str.lower() == 'q':
            sender.reply("✅ 已退出操作")
            return
        
        days_to_modify = int(days_str)
        
        users = middleware.bucketAllKeys('yuhua_ydyp_user')
        success = 0
        failed = 0
        total_accounts = 0

        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_ydyp_user', user) or '[]')
            total_accounts += len(accounts)
            for acc_id in accounts:
                try:
                    new_auth_date_str = calculate_auth_time_by_days(acc_id, days_to_modify)
                    middleware.bucketSet('yuhua_ydyp_auth', acc_id, new_auth_date_str)
                    
                    token = middleware.bucketGet('yuhua_ydyp_token', acc_id)
                    phone = middleware.bucketGet('yuhua_ydyp_phone', acc_id) or "未知"
                    if token:
                        add_to_qinglong(token, acc_id, phone, target_user=user)
                    
                    success += 1
                    log_operation('batch_auth', user, acc_id, 'success', f'{days_to_modify} days')
                except Exception as e:
                    failed += 1
                    log_operation('batch_auth', user, acc_id, 'failed', str(e))

        sender.reply(f"""
=====授权完成=====
✅ 成功: {success}个账号
❌ 失败: {failed}个账号
⏰ 授权: {days_to_modify}天
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
        
    accounts = eval(middleware.bucketGet('yuhua_ydyp_user', user_id) or '[]')
    if not accounts:
        sender.reply("❌ 未找到该用户的账号")
        return

    account_display_parts = ["=====账号列表=====", "[0] 授权全部账号", "------------------"]
    for i, acc_id in enumerate(accounts, 1):
        phone = middleware.bucketGet('yuhua_ydyp_phone', acc_id) or "未知"
        display_name = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
        icon, status_text = _get_auth_status_details(acc_id)
        
        account_info = f"""[{i}] 账号信息
🤪 账号: {display_name}
☁ 授权: {icon} {status_text}"""
        account_display_parts.append(account_info)
        account_display_parts.append("------------------")

    account_display_parts.extend(["回复数字选择", "回复'q'退出", "=================="])
    sender.reply("\n".join(account_display_parts))

    choice = sender.input(60000, 0, False)
    if not choice:
        sender.reply("❌ 输入超时")
        return
    if choice.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return

    sender.reply("""
=====设置授权时间=====
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
        days_to_modify = int(days_str)
        choice_idx = int(choice)
        
        accounts_to_process = []
        if choice_idx == 0:
            accounts_to_process = accounts
        elif 1 <= choice_idx <= len(accounts):
            accounts_to_process.append(accounts[choice_idx - 1])
        else:
            raise ValueError("选择无效")

        success_count = 0
        fail_count = 0
        for acc_id in accounts_to_process:
            try:
                new_auth_date_str = calculate_auth_time_by_days(acc_id, days_to_modify)
                middleware.bucketSet('yuhua_ydyp_auth', acc_id, new_auth_date_str)
                
                token = middleware.bucketGet('yuhua_ydyp_token', acc_id)
                phone = middleware.bucketGet('yuhua_ydyp_phone', acc_id) or "未知"
                if token:
                    add_to_qinglong(token, acc_id, phone, target_user=user_id)
                
                success_count += 1
                log_operation('auth', user_id, acc_id, 'success', f'{days_to_modify} days')
            except Exception as e:
                fail_count += 1
                log_operation('auth', user_id, acc_id, 'failed', str(e))
        
        sender.reply(f"""
=====授权完成=====
✅ 成功: {success_count}个账号
❌ 失败: {fail_count}个账号
⏰ 操作: {days_to_modify}天
==================""")

    except ValueError:
        sender.reply("❌ 无效的输入")
    except Exception as e:
        sender.reply(f"❌ 授权失败: {str(e)}")


#################### 仅“一键抢兑”受时间限制 ####################
STOP_EXCHANGE = False

def _fetch_device_id_static():
    url = "https://slw.h5cmpassport.com:9090/deviceprofile/v4"
    headers = {
        "Host": "slw.h5cmpassport.com:9090",
        "Connection": "keep-alive",
        "sec-ch-ua-platform": '"Android"',
        "User-Agent": YDYP_MARKET_UA,
        "sec-ch-ua": '"Chromium";v="108", "Android WebView";v="108", "Not/A)Brand";v="99"',
        "Content-Type": "application/json;charset=UTF-8",
        "sec-ch-ua-mobile": "?1",
        "Accept": "*/*",
        "Origin": "https://m.mcloud.139.com",
        "X-Requested-With": "com.chinamobile.mcloud",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://m.mcloud.139.com/portal/mobilecloud/index.html?path=newsignin",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    data = '{"appId":"default","organization":"FXlyfmWg2AzwbrxDKSv5","ep":"anGhOHfzlh7WPt/KVxj2A4ycutn5Fey6wnwpSLdN0I4Rea71hM7BybZaBZ2KSKZLno56LTsBJR+8eMsoldq95m3wfJmB8ZY+S5kczO2BrK2wiGyRZntpKoaIyyo6LZcFFRF2fan559tmygQCNSC7T9m7xLMGr4y/pN35z1GPOns=","data":"fe99d81711e0806e60a7e54ead0aa4b51c59aabdef53ad876a3b6a1af6f803cc3b3ab7eeed62f0bb6ef3fe6632a305882332f606dc34ece012d4a3cbff8be6dd89012c246e5a98a060b5267fe1869b475460741671827c0e9ecf87798759736005dc5a62f772a6c11a176a837097e06a41f5971a6b65c221cce080854de3986be34ad3dab87b6c6fff1f71b6c9a8c578069aa2bb0e92565d4714cad13ec6990817eec7a3d08aedcaa40c5c13da1a0dd3854d632e9a1cbebf7d5ad86749cba74eee449090b7a0270a3799e190a2a27380c73af34fbd0063cc92a9bbefe1e8f877c36d3f96a9f6bc1ed7c66f253f3d8a50bd7e09e399090f8c83601d0eb0e92646193dc6626d66c8677b9f31988997f3cec2d576ccab233ded79785301c2741b191d62381fa47670229557096a656a523c1b6faaa2e8c919a7a8f7932dfefae408c8bb48afbfb1658a5467c70330155c67567db599b773e5b2a7fdbbfe267f69f409ff1704261f68c598dfb8af3f22ee11eee84e5990c44bd8221d14cbfdde87ad38964db45e1624598d51cfb0a90c035aed84b28dd0cd7e390077e1df9c70b6c924df56a48368e86e0355333edcfbbcb6b8be5c008055a536164028ae4f68b129918948e7acac96e00faecee3e81feeb3d37a575d79b67bee7aeff6dd981a8694fda665b0c3ca5c48a01f4ec47f68a3c65ea0e567fce308395703873fab3d3e0e03346ea2a365395cff54e79d8b24cc8c691a5c0a731857a1414c275203dad64ebfe1e3b3e1fd08c22fbf9ffe95753903f89ee87084c37fe012af911b8ad6e409e49d46a7cd3ef5959f7278dc7a7c44c9c5bc021366913afd2119f17e745e4909670db42b8f53341a38c7f3d077f5cb95b99a6533fd9d74aab2d3d0b11af8cecedb5ca7d4a5ba31fdcf4a86515b98120e14696f573b2a742c2208711ec464a394499986fd28cd6a8c737c2a2ed60439eb95eb4e597948ac4ca52a696ad14604f69067292567a969e6a7a5bfa15abb1614f03c386f7db400db4f5759e5291b01d9b002917361ba0f75c071ef0f185ab5e099eabc7eb5ecd43ddc37f64b7f9765f3ec1a23a240835edd672a0fc0bcfbadc1cabcdb63512bbb3dbf13770627b0fb6f7ef649f16990f1d6be3a769472af40d0f5021cddd073abcfe528d4d5b3710ead8ba9c54c75b858cfb4636ab66b0df9ac52fa5e5d6ebdde5e87f3072535548bfbcbf46e92af5eeb96f33b646fd7375d8caa246f22f659b469e4518733479db088cd6a492e252e6182048de77af3a929d44bb0fb20e2c9d871c3f20f3c139c4cabec0240a027ddd283d105e6ea6e107a0a00357c98f4bb77c1dee85f2ff971b4aa25b6ce7d373f06baa4c51f30c684e06b84210fa6bf65f049ad7ba77370621341090dbe3e28fc1347d5e0211662508a886f1a49a960a395138bbdf69114c3024f1b67974b2f717ad5c34f7825bd74301e9fdd7cc24af7e8646c93789f70495fcdba0722429d07e96c5f0c86cc6264426acc3540343b1920119479eac94da40ca3600198f45b1df7c2020c79d070e715a24e863d21b1eeafbfc18c0c3933e774bf064deb48d697acd438c7a4298235e8bafef31cebdbc49407b1562fd3e5a1c696887e67c069e8e75ed5744969c281bd67264f6c52403fb8d89b5fd06eee39480993d1d1523cae278dd75a0e5941141beb610870eb42b581a79429f9cdf5e95a3b9e3b682b655be76b32e0286327ae0cdd1745b6a70e26d84457269f516a1f5be15453759d9b46fc8ced01ea8d1f5ec9870878ef36d81ef0c73327c5899e9dc3cf95f392e5e003117d9cbaa76958307fe4b20944e54a83ca423fece80fafaf620726d2bc9d6fe9bea04002a9adeffa281de19cbcd25b9b2ab687c5d29a9e46d5ba06723cf21fd2a6e586ac269e341c2aa9","os":"web","encode":5,"compress":2}'
    try:
        session = get_global_session()
        resp = session.post(url, headers=headers, data=data, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        if result.get('code') == 1100 and result.get('detail', {}).get('deviceId'):
            return True, result['detail']['deviceId']
        return False, f"获取deviceId失败: {result}"
    except Exception as e:
        return False, f"获取deviceId异常: {str(e)}"

def _post_device_profile(payload, ua, page_url):
    """提交数美 deviceprofile/v4，返回 (ok, raw deviceId 或错误)。"""
    url = "https://slw.h5cmpassport.com:9090/deviceprofile/v4"
    headers = {
        "Host": "slw.h5cmpassport.com:9090",
        "Connection": "keep-alive",
        "sec-ch-ua-platform": '"Android"',
        "User-Agent": ua,
        "sec-ch-ua": '"Chromium";v="108", "Android WebView";v="108", "Not/A)Brand";v="99"',
        "Content-Type": "application/json;charset=UTF-8",
        "sec-ch-ua-mobile": "?1",
        "Accept": "*/*",
        "Origin": "https://m.mcloud.139.com",
        "X-Requested-With": "com.chinamobile.mcloud",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": page_url,
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        session = get_global_session()
        resp = session.post(url, headers=headers, data=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        if result.get('code') == 1100 and result.get('detail', {}).get('deviceId'):
            return True, result['detail']['deviceId']
        return False, f"获取deviceId失败: {result}"
    except Exception as e:
        return False, f"获取deviceId异常: {str(e)}"


def fetch_device_id():
    """优先动态生成数美设备指纹；失败回退静态报文。"""
    now = time.time()
    cached = _DEVICE_ID_CACHE.get('device_id') or ''
    if cached and now < _DEVICE_ID_CACHE.get('expires_at', 0):
        return True, cached

    page_url = "https://m.mcloud.139.com/portal/mobilecloud/index.html?path=newsignin"
    dynamic_error = ''
    try:
        payload, smid = _generate_device_profile(YDYP_MARKET_UA, page_url)
        ok, device_id = _post_device_profile(payload, YDYP_MARKET_UA, page_url)
        if ok:
            normalized = _device_id_with_prefix(device_id)
            if normalized:
                _DEVICE_SMID_CACHE[normalized] = smid
            _DEVICE_SMID_CACHE[device_id] = smid
            _DEVICE_ID_CACHE.update(device_id=device_id, smid=smid, expires_at=now + 300)
            return True, device_id
        dynamic_error = device_id
    except Exception as e:
        dynamic_error = str(e)

    ok, device_id = _fetch_device_id_static()
    if ok:
        _DEVICE_ID_CACHE.update(device_id=device_id, smid='', expires_at=now + 300)
        return True, device_id
    return False, f"动态设备注册失败: {dynamic_error}；静态设备注册失败: {device_id}"


def get_or_fetch_device_id(account_id):
    ok, result = fetch_device_id()
    if ok:
        return True, result
    return False, result

DDDDOCR_API = "http://ddddocr.250666.xyz/capcode"

def solve_slide_captcha(yp_obj, dev_id):
    """
    获取滑块验证码并识别偏移量，返回 puzzleOffset 值。
    基于抓包: POST /ycloud/auth-service/slide/getSlide → 返回 puzzle(滑块图) + picture(背景图)
    使用 ddddocr 识别偏移距离。
    """
    try:
        device_id = _device_id_with_prefix(dev_id)
        slide_headers = dict(yp_obj.jwtHeaders)
        slide_headers.update({
            'Host': 'm.mcloud.139.com',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'deviceId': device_id,
            'appVersion': YDYP_APP_VERSION,
            'activityId': 'sign_in_3',
            'showLoading': 'true',
            'sec-ch-ua-platform': '"Android"',
            'sec-ch-ua': '"Chromium";v="108", "Android WebView";v="108", "Not/A)Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'Accept': '*/*',
            'Origin': 'https://m.mcloud.139.com',
            'X-Requested-With': 'com.chinamobile.mcloud',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'User-Agent': YDYP_MARKET_UA,
            'Referer': yp_obj.build_market_page_url(),
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7'
        })
        slide_cookies = yp_obj._exchange_cookies(device_id)

        slide_started = time.time()
        resp = yp_obj.send_request(
            "https://m.mcloud.139.com/ycloud/auth-service/slide/getSlide",
            headers=slide_headers,
            cookies=slide_cookies,
            data=None,
            method='POST',
            delay=0
        )

        if not resp or resp.get("code") != 0:
            printf(f"getSlide失败: code={resp.get('code') if isinstance(resp, dict) else resp} "
                   f"msg={_response_message(resp, '')} elapsed={int((time.time()-slide_started)*1000)}ms", 'WARN')
            return None

        result = resp.get("result", {})
        puzzle_b64 = result.get("puzzle", "")
        picture_b64 = result.get("picture", "")
        if DEBUG:
            printf(f"getSlide成功: puzzle={len(puzzle_b64)}B picture={len(picture_b64)}B "
                   f"elapsed={int((time.time()-slide_started)*1000)}ms", 'DEBUG')

        if not puzzle_b64 or not picture_b64:
            printf("getSlide响应中缺少图片数据，未提交兑换", 'WARN')
            return None

        printf(f"开始OCR识别滑块: puzzle={len(puzzle_b64)}B picture={len(picture_b64)}B", 'INFO')
        # 调用 ddddocr 识别滑块偏移；失败返回 None，绝不使用固定偏移兜底
        ocr_status = None
        ocr_text = ''
        try:
            ocr_started = time.time()
            ocr_resp = requests.post(
                DDDDOCR_API,
                json={"slidingImage": puzzle_b64, "backImage": picture_b64, "simpleTarget": True},
                timeout=15
            )
            ocr_status = ocr_resp.status_code
            ocr_text = (ocr_resp.text or '')[:200]
            ocr_elapsed = int((time.time() - ocr_started) * 1000)
            offset = int(float(ocr_resp.json().get("result")))
            try:
                pic_width = int(float(result.get("picWidth") or 0))
                puzzle_width = int(float(result.get("puzzleWidth") or 0))
            except Exception:
                pic_width, puzzle_width = 0, 0
            if offset < 0 or (pic_width > 0 and puzzle_width > 0 and offset > pic_width - puzzle_width):
                printf(f"滑块偏移量超出图片范围: offset={offset} width={pic_width} "
                       f"puzzle={puzzle_width} ocr={ocr_elapsed}ms", 'WARN')
                return None
            if DEBUG:
                printf(f"滑块识别偏移量: {offset} ocr={ocr_elapsed}ms", "DEBUG")
            return offset
        except Exception as e:
            printf(f"ddddocr识别失败: {e} status={ocr_status} body={ocr_text}，未提交兑换", 'WARN')
            return None

    except Exception as e:
        printf(f"滑块验证流程异常: {e}，未提交兑换", "WARN")
        return None

def within_exchange_window():
    """
    判断当前时间是否在 00:00, 10:00, 12:00, 16:00 和 20:00 前后10分钟范围内：
    即 [23:50, 00:10] 或[09:50, 10:10] 或[11:50, 12:10] 或 [15:50, 16:10] 或[19:50, 20:10]
    若在此范围内返回 True，否则 False
    """
    now = local_now()
    start0_pm = now.replace(hour=23, minute=50, second=0, microsecond=0)
    end0_am = now.replace(hour=0, minute=10, second=0, microsecond=0)
    start_8 = now.replace(hour=9, minute=50, second=0, microsecond=0)
    end_8 = now.replace(hour=10, minute=10, second=0, microsecond=0)
    start1 = now.replace(hour=11, minute=50, second=0, microsecond=0)
    end1 = now.replace(hour=12, minute=10, second=0, microsecond=0)
    start2 = now.replace(hour=15, minute=50, second=0, microsecond=0)
    end2 = now.replace(hour=16, minute=10, second=0, microsecond=0)
    start_20 = now.replace(hour=19, minute=50, second=0, microsecond=0)
    end_20 = now.replace(hour=20, minute=10, second=0, microsecond=0)
    return (now >= start0_pm) or (now <= end0_am) or \
           (start_8 <= now <= end_8) or \
           (start1 <= now <= end1) or \
           (start2 <= now <= end2) or \
           (start_20 <= now <= end_20)


def _next_exchange_target(now):
    """返回本次抢兑应等待的整点。

    - 处于某个整点后的 10 分钟窗口内（如 16:06）→ 返回该整点，立即补跑；
    - 23 点后 → 次日 00:00；
    - 其余 → 下一个整点（0/10/12/16/20）。
    """
    for hour in (0, 10, 12, 16, 20):
        slot = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if slot <= now <= slot + timedelta(minutes=10):
            return slot
    if now.hour >= 23:
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    targets = [
        now.replace(hour=hour, minute=0, second=0, microsecond=0)
        for hour in (0, 10, 12, 16, 20)
    ]
    future_targets = [target for target in targets if target > now]
    if not future_targets:
        return min(targets)
    return min(future_targets, key=lambda target: target - now)


def handle_yijian_qiangdui():
    global STOP_EXCHANGE
    if not sender.isAdmin():
        sender.reply("❌ 需要管理员权限")
        return
    if STOP_EXCHANGE:
        sender.reply("❌ 抢兑已被手动停止")
        return
    if not within_exchange_window():
        sender.reply("❌ 当前时间不在0,10,12,16,20点前后，无法执行云盘抢兑操作")
        return
    now = local_now()
    target_time = _next_exchange_target(now)
    prize_bucket_key = 'yuhua_ydyp_prize_regular'
    prize_filter_logic = lambda prize: prize.get('groupId') != 10
    all_keys = middleware.bucketAllKeys(prize_bucket_key)
    if not all_keys:
        sender.reply("❌ 暂无账号提交【福利专区】抢兑")
        return
    owner_map = {}
    all_users = middleware.bucketAllKeys('yuhua_ydyp_user')
    for u in all_users:
        acc_list = eval(middleware.bucketGet('yuhua_ydyp_user', u) or '[]')
        for ac in acc_list:
            owner_map[ac] = u
    concurrency_data = []
    fail_reasons =[]
    cleaned_invalid_accounts = 0
    for acc_id in all_keys:
        if STOP_EXCHANGE:
            sender.reply("❌ 云盘抢兑已被手动停止")
            return
        prize_name = middleware.bucketGet(prize_bucket_key, acc_id)
        if not prize_name:
            try:
                middleware.bucketDel(prize_bucket_key, acc_id)
            except Exception:
                pass
            cleaned_invalid_accounts += 1
            continue
        auth_time = middleware.bucketGet('yuhua_ydyp_auth', acc_id)
        phone = middleware.bucketGet('yuhua_ydyp_phone', acc_id) or "未知"
        phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
        if acc_id not in owner_map:
            try:
                middleware.bucketDel(prize_bucket_key, acc_id)
            except Exception:
                pass
            cleaned_invalid_accounts += 1
            continue
        if not auth_time or auth_time <= str(local_now().date()):
            fail_reasons.append(f"【{phone_mask}】授权已过期")
            try:
                middleware.bucketDel(prize_bucket_key, acc_id)
            except Exception:
                pass
            cleaned_invalid_accounts += 1
            continue
            
        # --- 接入自动刷新与检查校验体系 ---
        ok_ck, ck_str, ck_msg = check_and_refresh_token(acc_id)
        if not ok_ck and not ck_str:
            fail_reasons.append(f"【{phone_mask}】{ck_msg}")
            continue
            
        y = YP(ck_str, phone=phone)
        ok1, msg1 = y.sso()
        if not ok1:
            msg1_str = str(msg1)
            need_relogin = any(keyword in msg1_str.lower() for keyword in['unauthorized', 'invalid', 'expired', 'authorization']) or any(keyword in msg1_str for keyword in['无效', '过期', '失效'])
            if need_relogin:
                # 遇到SSO直接拒绝，强制触发底层刷新
                ok_force, ck_str_force, force_msg = check_and_refresh_token(acc_id, force=True)
                if ok_force and ck_str_force:
                    y.close()
                    y = YP(ck_str_force, phone=phone)
                    ok1, msg1 = y.sso()
                    if not ok1:
                        fail_reasons.append(f"【{phone_mask}】{msg1}")
                        continue
                else:
                    fail_reasons.append(f"【{phone_mask}】强制刷新失败: {force_msg}")
                    continue
            else:
                fail_reasons.append(f"【{phone_mask}】{msg1}")
                continue
        # ---------------------------------
        
        ok2, msg2 = y.jwt()
        if not ok2: fail_reasons.append(f"【{phone_mask}】jwt获取失败: {msg2}"); continue
        try:
            # 预热活动页会话，避免到点后再初始化拖慢首个兑换请求
            y._prepare_market_session()
        except Exception:
            pass
        list_resp = y.send_request("https://m.mcloud.139.com/ycloud/signin/page/exchangeList", headers=y.jwtHeaders, cookies=y.cookies)
        if not list_resp or "result" not in list_resp:
            fail_reasons.append(f"【{phone_mask}】获取奖品列表失败"); continue
        found_pid = None
        cost = 9999999
        for _, arr in list_resp["result"].items():
            for it in arr:
                if prize_filter_logic(it) and it.get("prizeName") == prize_name:
                    found_pid = it.get("prizeId")
                    cost = it.get("pOrder", 9999999)
                    break
                if found_pid: break
        if not found_pid:
            fail_reasons.append(f"【{phone_mask}】未找到奖品 {prize_name}"); continue
        ok3, _ = y.receive()
        if not ok3:
            fail_reasons.append(f"【{phone_mask}】查询云朵失败"); continue
        if y.total_amount < cost:
            fail_reasons.append(f"【{phone_mask}】云朵不足 ({y.total_amount}/{cost})"); continue
        user_id = owner_map.get(acc_id, "")
        ok_dev, dev_id = get_or_fetch_device_id(acc_id)
        if not ok_dev:
            fail_reasons.append(f"【{phone_mask}】{dev_id}")
            continue
        concurrency_data.append((phone_mask, prize_name, found_pid, cost, y, user_id, acc_id, dev_id))
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    notice = f"""🪁 插件【移动云盘】提醒
🧭 当前时间: {now_str}
📋 抢兑账号: {len(concurrency_data)}个
🏖️ 抢兑时间: {target_time.strftime('%H:%M:%S')}
"""
    sender.reply(notice)
    if cleaned_invalid_accounts > 0:
        sender.reply(f"🧹 已自动清理 {cleaned_invalid_accounts} 个无效账号的抢兑数据")
    if fail_reasons:
        sender.reply("以下账号不满足抢兑条件：\n" + "\n".join(fail_reasons))
    diff = (target_time - local_now()).total_seconds()
    if diff > 0:
        time.sleep(diff)
    if STOP_EXCHANGE:
        sender.reply("❌ 云盘抢兑已被手动停止"); return



    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def real_exchange(phone_mask, pname, pid, costnum, yobj, user_id, account_id, dev_id):
        # 确保兑换会话有可用的 SSO/JWT；失败时不提交兑换
        if not yobj.jwtToken:
            ok_sso, msg_sso = yobj.sso()
            if not ok_sso:
                return (phone_mask, pname, False, f"SSO失败: {msg_sso}", user_id, account_id)
            ok_jwt, msg_jwt = yobj.jwt()
            if not ok_jwt:
                return (phone_mask, pname, False, f"JWT失败: {msg_jwt}", user_id, account_id)

        device_id = _device_id_with_prefix(dev_id)
        if not device_id:
            return (phone_mask, pname, False, "设备标识为空", user_id, account_id)

        try:
            yobj._prepare_market_session()
        except Exception:
            pass
        printf(f"开始兑换 {phone_mask} prize={pname} id={pid} device={device_id[:12]}...", 'INFO')
        ok_elig, elig_msg = yobj.check_exchange_eligibility(pid, device_id)
        if not ok_elig:
            printf(f"兑换被资格预检拦截 {phone_mask}: {elig_msg}", 'WARN')
            return (phone_mask, pname, False, elig_msg, user_id, account_id)

        last_msg = '兑换失败'
        for attempt in range(1, 6):
            if STOP_EXCHANGE:
                return (phone_mask, pname, False, "已被手动停止", user_id, account_id)
            # 每次尝试前重新取滑块；失败不提交兑换，也不使用固定偏移兜底
            puzzle_offset = solve_slide_captcha(yobj, device_id)
            if puzzle_offset is None:
                last_msg = '滑块识别失败，未提交兑换'
                printf(f"第{attempt}次兑换未提交 {phone_mask}: 滑块识别失败", 'WARN')
                if attempt < 5:
                    time.sleep(0.5)
                continue
            ok, msg, terminal = yobj.exchange_v3(pid, puzzle_offset, device_id)
            if ok:
                printf(f"兑换成功 {phone_mask} 第{attempt}次: {msg}", 'INFO')
                return (phone_mask, pname, True, f"兑换成功(第{attempt}次) {msg}", user_id, account_id)
            last_msg = msg
            printf(f"兑换失败 {phone_mask} 第{attempt}次: {msg} terminal={terminal}", 'WARN')
            if terminal:
                break
            if attempt < 5:
                time.sleep(0.5)
        printf(f"兑换结束 {phone_mask}: {last_msg}", 'WARN')
        return (phone_mask, pname, False, last_msg, user_id, account_id)
        
    bf_num_local = bingfa
    futures_map = {}
    with ThreadPoolExecutor(max_workers=bf_num_local) as exe:
        for (pm, pn, pd, ct, y, uid, acid, did) in concurrency_data:
            fut = exe.submit(real_exchange, pm, pn, pd, ct, y, uid, acid, did)
            futures_map[fut] = pm
        results =[]
        for fut in as_completed(futures_map): results.append(fut.result())
    succ_count = sum(1 for r in results if r[2] is True)
    fail_count = sum(1 for r in results if r[2] is False)
    fail_msgs =[f"🤪 账号: {r[0]}\n🎁 奖品: {r[1]}\n🪁 结果: {r[3]}" for r in results if not r[2]]
    detail_fail = "\n".join(fail_msgs) if fail_msgs else ""
    final_msg = f"""=====云盘抢兑统计=====
✨ 总抢兑数: {len(results)}
✅ 抢兑成功: {succ_count}
❌ 抢兑失败: {fail_count}
------------------
📝 失败详情:
{detail_fail if detail_fail else '无'}
=================="""
    sender.reply(final_msg)
    for (phone_mask, pname, ok, reason, user_id, account_id) in results:
        if ok is True:
            try:
                middleware.bucketDel(prize_bucket_key, account_id)
            except Exception:
                pass
        if user_id:
            status_str = "成功" if ok else reason
            push_text = f"""=====云盘抢兑=====
🤪 账号: {phone_mask}
🎁 奖品: {pname}
🪁 结果：{status_str}
=================="""
            middleware.push('qq', '', user_id, '', push_text)
            middleware.push('qb', '', user_id, '', push_text)
            middleware.push('wx', '', user_id, '', push_text)
            middleware.push('gw', '', user_id, '', push_text)
            middleware.push('sb', '', user_id, '', push_text)
            middleware.push('wb', '', user_id, '', push_text)
            middleware.push('tg', '', user_id, '', push_text)
            middleware.push('tb', '', user_id, '', push_text)
            middleware.push('qx', '', user_id, '', push_text)
            middleware.push('xy', '', user_id, '', push_text)
            middleware.push('ip', '', user_id, '', push_text)
        if not ok and ("非移动用户不可领奖" in str(reason) or "超过每月兑换限制" in str(reason) or "重复兑奖" in str(reason)):
            try:
                middleware.bucketDel(prize_bucket_key, account_id)
            except Exception:
                pass
def exchange_entry_point():
    """ “云盘兑换”指令的入口函数 """
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
    if len(accounts) == 1:
        show_exchange_menu_ydyp(accounts[0])
        return
    account_display_parts = ["=====请选择账号====="]
    for i, acc_unique_id in enumerate(accounts, 1):
        phone = middleware.bucketGet('yuhua_ydyp_phone', acc_unique_id) or "未知"
        display_name = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
        icon, status_text = _get_auth_status_details(acc_unique_id)
        account_info = f"""[{i}] 账号信息
🤪 账号: {display_name}
☁ 授权: {icon} {status_text}"""
        account_display_parts.append(account_info)
        account_display_parts.append("------------------")
    account_display_parts.extend(["回复数字选择", "回复'q'退出", "=================="])
    sender.reply("\n".join(account_display_parts))
    choice_str = sender.input(60000, 0, False)
    if not choice_str or choice_str.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    try:
        choice_idx = int(choice_str)
        if 1 <= choice_idx <= len(accounts):
            show_exchange_menu_ydyp(accounts[choice_idx - 1])
        else:
            raise ValueError()
    except ValueError:
        sender.reply("❌ 无效的选择")

def show_exchange_menu_ydyp(account):
    """ 显示统一的兑换菜单（核心功能函数） """
    sender.reply("正在执行...")
    phone = middleware.bucketGet('yuhua_ydyp_phone', account) or "未知"
    phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
    auth_time = middleware.bucketGet('yuhua_ydyp_auth', account)
    if not auth_time or auth_time <= str(local_now().date()):
        sender.reply(f"【{phone_mask}】授权已过期，无法进行兑换")
        return
        
    # 接入自动刷新与检查校验体系
    ok_ck, ck_str, ck_msg = check_and_refresh_token(account)
    if not ok_ck and not ck_str:
        sender.reply(f"【{phone_mask}】{ck_msg}")
        return
        
    yp = YP(ck_str, phone=phone)
    try:
        ok1, msg1 = yp.sso()
        if not ok1:
            msg1_str = str(msg1)
            need_relogin = any(keyword in msg1_str.lower() for keyword in['unauthorized', 'invalid', 'expired', 'authorization']) or any(keyword in msg1_str for keyword in ['无效', '过期', '失效'])
            if need_relogin:
                # 遇到SSO直接拒绝，强制触发底层刷新
                ok_force, ck_str_force, force_msg = check_and_refresh_token(account, force=True)
                if ok_force and ck_str_force:
                    yp.close()
                    yp = YP(ck_str_force, phone=phone)
                    ok1, msg1 = yp.sso()
                    if not ok1:
                        sender.reply(f"【{phone_mask}】{msg1}")
                        return
                else:
                    sender.reply(f"【{phone_mask}】强制刷新失败: {force_msg}")
                    return
            else:
                sender.reply(f"【{phone_mask}】{msg1}")
                return
                
        ok2, _ = yp.jwt()
        if not ok2: sender.reply(f"【{phone_mask}】jwt获取失败"); return
        ok3, _ = yp.receive()
        if not ok3: sender.reply(f"【{phone_mask}】查询云朵失败"); return
        list_url = "https://m.mcloud.139.com/ycloud/signin/page/exchangeList"
        r = yp.send_request(list_url, headers=yp.jwtHeaders, cookies=yp.cookies)
        if not r or "result" not in r: sender.reply(f"【{phone_mask}】获取奖品列表失败"); return
        all_prizes_raw =[]
        for _, arr in r["result"].items(): all_prizes_raw.extend(arr)
        all_prizes =[p for p in all_prizes_raw if p.get('groupId') != 10]
        if not all_prizes: sender.reply(f"【{phone_mask}】当前没有可兑换的奖品"); return
        product_display_list =[]
        for i, product in enumerate(all_prizes, 1):
            prize_name = product.get('prizeName', '未知奖品')
            cost = product.get('pOrder', 0)
            stock_status = "✅" if product.get('dailyRemainderCount', 0) > 0 else "❌"
            product_display_list.append(f"[{i}] {prize_name}\n    {stock_status} 消耗{cost}云朵")
        prize_regular = middleware.bucketGet('yuhua_ydyp_prize_regular', account)
        prize_status_regular = f"🎁 福利专区: {prize_regular}" if prize_regular else "🎁 福利专区: 未设置"

        products_msg = f"""=====云盘兑换=====
🤪 用户账号: {phone_mask}
💰 当前云朵: {yp.total_amount}
{prize_status_regular}
------------------
{chr(10).join(product_display_list)}
------------------
+序号=提交抢兑, d=删除抢兑
单序号=立即兑换, q=退出操作"""
        sender.reply(products_msg)
        choice_str = sender.input(60000, 0, False)
        if not choice_str or choice_str.lower() == 'q': sender.reply("✅ 已退出操作"); return
        if choice_str.lower() == 'd':
            try:
                middleware.bucketDel('yuhua_ydyp_prize_regular', account)
            except Exception:
                pass
            sender.reply(f"【{phone_mask}】福利专区抢兑目标已清除")
            return
        if choice_str.startswith('+'):
            try:
                choice_idx = int(choice_str[1:])
                if not (1 <= choice_idx <= len(all_prizes)): raise ValueError()
                selected_product = all_prizes[choice_idx - 1]
                p_input = selected_product.get("prizeName")
                middleware.bucketSet('yuhua_ydyp_prize_regular', account, p_input)
                sender.reply(f"【{phone_mask}】福利专区抢兑目标已设置为: {p_input}")
            except (ValueError, IndexError):
                sender.reply("❌ 无效的选择")
            return
        try:
            choice_idx = int(choice_str)
            if not (1 <= choice_idx <= len(all_prizes)): raise ValueError()
            selected_product = all_prizes[choice_idx - 1]
            if selected_product.get('dailyRemainderCount', 0) <= 0:
                sender.reply(f"【{phone_mask}】兑换失败，该奖品已无库存")
                return
            found_pid = selected_product.get("prizeId")
            cost = selected_product.get("pOrder", 9999999)
            if yp.total_amount < cost:
                sender.reply(f"【{phone_mask}】云朵不足({yp.total_amount}/{cost})")
                return
            
            sender.reply("正在执行...")
            
            ok_dev, dev_raw = get_or_fetch_device_id(account)
            if not ok_dev:
                sender.reply(f"【{phone_mask}】{dev_raw}")
                return
            device_id = _device_id_with_prefix(dev_raw)
            if not device_id:
                sender.reply(f"【{phone_mask}】设备标识为空，未提交兑换")
                return

            try:
                yp._prepare_market_session()
            except Exception:
                pass
            printf(f"手动兑换 {phone_mask} prize={selected_product.get('prizeName')} id={found_pid} device={device_id[:12]}...", 'INFO')
            ok_elig, elig_msg = yp.check_exchange_eligibility(found_pid, device_id)
            if not ok_elig:
                printf(f"手动兑换被资格预检拦截 {phone_mask}: {elig_msg}", 'WARN')
                sender.reply(f"【{phone_mask}】{elig_msg}")
                return

            # 获取滑块偏移量；失败不提交兑换，不使用固定偏移兜底
            sender.reply(f"【{phone_mask}】正在识别滑块...")
            puzzle_offset = solve_slide_captcha(yp, device_id)
            if puzzle_offset is None:
                printf(f"手动兑换未提交 {phone_mask}: 滑块识别失败", 'WARN')
                sender.reply(f"【{phone_mask}】滑块识别失败，未提交兑换")
                return
            ok_ex, msg_ex, _terminal = yp.exchange_v3(found_pid, puzzle_offset, device_id)
            if ok_ex:
                printf(f"手动兑换成功 {phone_mask}: {msg_ex}", 'INFO')
                sender.reply(f"【{phone_mask}】兑换【{selected_product.get('prizeName')}】成功")
            else:
                printf(f"手动兑换失败 {phone_mask}: {msg_ex}", 'WARN')
                sender.reply(f"【{phone_mask}】{msg_ex}")
        except (ValueError, IndexError):
            sender.reply("❌ 无效的选择")
    finally:
        yp.close()
             
def stop_exchange():
    """手动停止一键抢兑"""
    global STOP_EXCHANGE
    if not sender.isAdmin():
        sender.reply("❌ 需要管理员权限")
        return
    STOP_EXCHANGE = True
    sender.reply("✅ 已停止云盘抢兑")


def sms_login():
    def sanitize_message(message):
        """
        用****替换输出中包含敏感URL以防止暴露
        """
        sensitive_urls = ['http://yuhualhh.250666.xyz', 'https://yuhualhh.250666.xyz']
        sanitized = str(message)
        for url in sensitive_urls:
            sanitized = sanitized.replace(url, '****')
        return sanitized

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
        sender.reply("❌ 无效的输入")
        return

    #sender.reply("正在获取验证码...")
    try:
        php_api_url = "https://yuhualhh.250666.xyz/api/ydyp_sms_login.php"
        php_api_key = "yuhua666666"

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'X-API-KEY': php_api_key
        })

        if DEBUG:
            printf("===== [SMS LOGIN START] =====", "DEBUG")
            printf(f"PHONE: {phone}", "DEBUG")
            printf(f"PHP API URL: {php_api_url}", "DEBUG")

        # 获取短信验证码
        sms_payload = {
            "action": "get_sms_code",
            "phone": phone
        }

        if DEBUG:
            printf("===== [PHP GET SMS CODE REQUEST] =====", "DEBUG")
            printf(f"URL: {php_api_url}", "DEBUG")
            printf(f"BODY(JSON): {json.dumps(sms_payload, ensure_ascii=False)}", "DEBUG")

        sms_resp = session.post(php_api_url, json=sms_payload, timeout=20)

        if DEBUG:
            printf("===== [PHP GET SMS CODE RESPONSE] =====", "DEBUG")
            printf(f"STATUS: {sms_resp.status_code}", "DEBUG")
            printf(f"RSP HEADERS: {json.dumps(dict(sms_resp.headers), ensure_ascii=False)}", "DEBUG")
            printf(f"RSP BODY: {_debug_dump(sms_resp.text)}", "DEBUG")

        sms_resp.raise_for_status()
        sms_data = sms_resp.json()

        if sms_data.get('code') != 0:
            sender.reply(sanitize_message(f"❌ 获取验证码失败: {sms_data.get('message', '未知错误')}"))
            return

        # 等待用户输入短信验证码
        sender.reply("请输入验证码:")
        code = sender.input(60000, 0, False)
        if not code:
            sender.reply("❌ 输入超时")
            return
        if code.lower() == 'q':
            sender.reply("✅ 已退出操作")
            return
        code = code.strip()

        if DEBUG:
            printf(f"用户输入验证码: {code}", "DEBUG")

        # 执行登录
        login_payload = {
            "action": "login",
            "phone": phone,
            "code": code
        }

        if DEBUG:
            printf("===== [PHP LOGIN REQUEST] =====", "DEBUG")
            printf(f"URL: {php_api_url}", "DEBUG")
            printf(f"BODY(JSON): {json.dumps(login_payload, ensure_ascii=False)}", "DEBUG")

        login_resp = session.post(php_api_url, json=login_payload, timeout=20)

        if DEBUG:
            printf("===== [PHP LOGIN RESPONSE] =====", "DEBUG")
            printf(f"STATUS: {login_resp.status_code}", "DEBUG")
            printf(f"RSP HEADERS: {json.dumps(dict(login_resp.headers), ensure_ascii=False)}", "DEBUG")
            printf(f"RSP BODY: {_debug_dump(login_resp.text)}", "DEBUG")

        login_resp.raise_for_status()
        login_data = login_resp.json()

        if login_data.get('code') != 0:
            sender.reply(sanitize_message(f"❌ 登录失败: {login_data.get('message', '验证码不正确')}"))
            return

        data = login_data.get('data', {}) or {}
        ck_value = data.get('Authorization', '') or ''

        if DEBUG:
            printf(f"登录响应data: {json.dumps(data, ensure_ascii=False)}", "DEBUG")
            printf(f"直接从PHP响应中获取Authorization: {'成功' if ck_value else '失败'}", "DEBUG")

        time.sleep(random.uniform(0.2, 0.5))

        if not ck_value:
            sender.reply(sanitize_message("❌ 登录失败：无法获取Authorization值"))
            return

        if not ck_value.startswith('Basic '):
            ck_value = f"Basic {ck_value}"

        if DEBUG:
            printf(f"最终Authorization: {ck_value}", "DEBUG")

        user_input = f"{ck_value}#{phone}"

        # 校验并保存
        yp_check = YP(ck_value, phone=phone)
        ok, msg = yp_check.sso()
        yp_check.close()

        if DEBUG:
            printf(f"Authorization校验结果: ok={ok}, msg={msg}", "DEBUG")

        if not ok:
            sender.reply(sanitize_message(f"❌ 登录校验失败: {msg}"))
            return

        accounts = eval(uservalue or '[]')
        matched_uid = None
        for uid in accounts:
            old_phone = middleware.bucketGet('yuhua_ydyp_phone', uid) or "未知"
            if old_phone == phone:
                matched_uid = uid
                break

        if DEBUG:
            printf(f"匹配到已有账号UID: {matched_uid if matched_uid else '无'}", "DEBUG")

        if matched_uid:
            middleware.bucketSet('yuhua_ydyp_token', matched_uid, user_input)
            _set_token_expire_from_auth(matched_uid, user_input)
            try:
                middleware.bucketDel('yuhua_ydyp_password', matched_uid)
            except Exception:
                pass
            auth_time = middleware.bucketGet('yuhua_ydyp_auth', matched_uid)
            if auth_time and auth_time > str(local_now().date()):
                if add_to_qinglong(user_input, matched_uid, phone):
                    try:
                        ql_envs = get_global_session().get(f"{ql_url}/open/envs", headers={"Authorization": f"Bearer {ql_token}"}, timeout=10)
                        if ql_envs.status_code == 200:
                            items = ql_envs.json().get('data', [])
                            ids = [e.get('id') for e in items if e.get('name') == var_name and f"UID:{matched_uid}" in str(e.get('remarks',''))]
                            if ids:
                                _enable_envs_in_qinglong(ids)
                    except Exception:
                        pass
            phone_mask = phone[:3] + "****" + phone[-4:]
            sender.reply(f"=====登录成功=====\n🤪 账号: {phone_mask}\n✅ 状态: 更新成功\n------------------\n发送\"{manage_cmd}\"管理账号\n发送\"{query_cmd}\"查询账号")
        else:
            new_id = gen_unique_id()
            if new_id not in accounts:
                accounts.append(new_id)
                middleware.bucketSet('yuhua_ydyp_user', userid, str(accounts))
            middleware.bucketSet('yuhua_ydyp_token', new_id, user_input)
            _set_token_expire_from_auth(new_id, user_input)
            middleware.bucketSet('yuhua_ydyp_phone', new_id, phone)
            phone_mask = phone[:3] + "****" + phone[-4:]
            sender.reply(f"=====登录成功=====\n🤪 账号: {phone_mask}\n✅ 状态: 添加成功\n------------------\n发送\"{manage_cmd}\"管理账号\n发送\"{query_cmd}\"查询账号")

        if DEBUG:
            printf("===== [SMS LOGIN END] =====", "DEBUG")

    except Exception as e:
        if DEBUG:
            printf(f"短信登录流程异常: {str(e)}", "ERROR")
        sender.reply(sanitize_message(f"❌ 短信登录流程出错: {str(e)}"))


def password_login():
    def sanitize_message(message):
        """
        用****替换输出中包含敏感URL以防止暴露
        """
        sensitive_urls = ['http://yuhualhh.250666.xyz', 'https://yuhualhh.250666.xyz']
        sanitized = str(message)
        for url in sensitive_urls:
            sanitized = sanitized.replace(url, '****')
        return sanitized

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
        sender.reply("❌ 无效的输入")
        return

    sender.reply("请输入密码:")
    password = sender.input(60000, 1, False)
    if not password:
        sender.reply("❌ 输入超时")
        return
    password = password.strip()
    if password.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    if password == '':
        sender.reply("❌ 密码不能为空")
        return

    try:
        php_api_url = "https://yuhualhh.250666.xyz/api/ydyp_sms_login.php"
        php_api_key = "yuhua666666"

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'X-API-KEY': php_api_key
        })

        if DEBUG:
            printf("===== [PASSWORD LOGIN START] =====", "DEBUG")
            printf(f"PHONE: {phone}", "DEBUG")
            printf(f"PHP API URL: {php_api_url}", "DEBUG")

        login_payload = {
            "action": "account_login",
            "phone": phone,
            "password": password
        }

        if DEBUG:
            printf("===== [PHP PASSWORD LOGIN REQUEST] =====", "DEBUG")
            printf(f"URL: {php_api_url}", "DEBUG")
            printf(f"BODY(JSON): {json.dumps({'action': 'account_login', 'phone': phone, 'password': '******'}, ensure_ascii=False)}", "DEBUG")

        login_resp = session.post(php_api_url, json=login_payload, timeout=20)

        if DEBUG:
            printf("===== [PHP PASSWORD LOGIN RESPONSE] =====", "DEBUG")
            printf(f"STATUS: {login_resp.status_code}", "DEBUG")
            printf(f"RSP HEADERS: {json.dumps(dict(login_resp.headers), ensure_ascii=False)}", "DEBUG")
            printf(f"RSP BODY: {_debug_dump(login_resp.text)}", "DEBUG")

        login_resp.raise_for_status()
        login_data = login_resp.json()

        if login_data.get('code') != 0:
            sender.reply(sanitize_message(f"❌ 登录失败: {login_data.get('message', '账号或密码不正确')}"))
            return

        data = login_data.get('data', {}) or {}
        ck_value = data.get('Authorization', '') or ''

        if DEBUG:
            printf(f"登录响应data: {json.dumps(data, ensure_ascii=False)}", "DEBUG")
            printf(f"直接从PHP响应中获取Authorization: {'成功' if ck_value else '失败'}", "DEBUG")

        time.sleep(random.uniform(0.2, 0.5))

        if not ck_value:
            sender.reply(sanitize_message("❌ 登录失败：无法获取Authorization值"))
            return

        if not ck_value.startswith('Basic '):
            ck_value = f"Basic {ck_value}"

        if DEBUG:
            printf(f"最终Authorization: {ck_value}", "DEBUG")

        user_input = f"{ck_value}#{phone}"

        yp_check = YP(ck_value, phone=phone)
        ok, msg = yp_check.sso()
        yp_check.close()

        if DEBUG:
            printf(f"Authorization校验结果: ok={ok}, msg={msg}", "DEBUG")

        if not ok:
            sender.reply(sanitize_message(f"❌ 登录校验失败: {msg}"))
            return

        accounts = eval(uservalue or '[]')
        matched_uid = None
        for uid in accounts:
            old_phone = middleware.bucketGet('yuhua_ydyp_phone', uid) or "未知"
            if old_phone == phone:
                matched_uid = uid
                break

        if DEBUG:
            printf(f"匹配到已有账号UID: {matched_uid if matched_uid else '无'}", "DEBUG")

        if matched_uid:
            middleware.bucketSet('yuhua_ydyp_token', matched_uid, user_input)
            _set_token_expire_from_auth(matched_uid, user_input)
            middleware.bucketSet('yuhua_ydyp_password', matched_uid, password)
            auth_time = middleware.bucketGet('yuhua_ydyp_auth', matched_uid)
            if auth_time and auth_time > str(local_now().date()):
                if add_to_qinglong(user_input, matched_uid, phone):
                    try:
                        ql_envs = get_global_session().get(f"{ql_url}/open/envs", headers={"Authorization": f"Bearer {ql_token}"}, timeout=10)
                        if ql_envs.status_code == 200:
                            items = ql_envs.json().get('data', [])
                            ids = [e.get('id') for e in items if e.get('name') == var_name and f"UID:{matched_uid}" in str(e.get('remarks',''))]
                            if ids:
                                _enable_envs_in_qinglong(ids)
                    except Exception:
                        pass
            phone_mask = phone[:3] + "****" + phone[-4:]
            sender.reply(f"=====登录成功=====\n🤪 账号: {phone_mask}\n✅ 状态: 更新成功\n------------------\n发送\"{manage_cmd}\"管理账号\n发送\"{query_cmd}\"查询账号")
        else:
            new_id = gen_unique_id()
            if new_id not in accounts:
                accounts.append(new_id)
                middleware.bucketSet('yuhua_ydyp_user', userid, str(accounts))
            middleware.bucketSet('yuhua_ydyp_token', new_id, user_input)
            _set_token_expire_from_auth(new_id, user_input)
            middleware.bucketSet('yuhua_ydyp_phone', new_id, phone)
            middleware.bucketSet('yuhua_ydyp_password', new_id, password)
            phone_mask = phone[:3] + "****" + phone[-4:]
            sender.reply(f"=====登录成功=====\n🤪 账号: {phone_mask}\n✅ 状态: 添加成功\n------------------\n发送\"{manage_cmd}\"管理账号\n发送\"{query_cmd}\"查询账号")

        if DEBUG:
            printf("===== [PASSWORD LOGIN END] =====", "DEBUG")

    except Exception as e:
        if DEBUG:
            printf(f"账密登录流程异常: {str(e)}", "ERROR")
        sender.reply(sanitize_message(f"❌ 账密登录流程出错: {str(e)}"))

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

def aes_encrypt(data, key):
    if not HAS_CRYPTO:
        return None
    key_bytes = key.encode('utf-8')
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    cipher = AES.new(key_bytes, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))
    return base64.b64encode(encrypted).decode('utf-8')


def aes_cbc_encrypt_refresh(plaintext):
    if not HAS_CRYPTO:
        return None
    iv = os.urandom(16)
    cipher = AES.new(YDYP_REFRESH_AES_KEY, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(str(plaintext).encode('utf-8'), AES.block_size))
    return base64.b64encode(iv + encrypted).decode('utf-8')


def aes_cbc_decrypt_refresh(cipher_b64):
    if not HAS_CRYPTO:
        return None
    try:
        raw = base64.b64decode(str(cipher_b64).strip())
        if len(raw) < 32 or len(raw) % 16 != 0:
            return None
        iv, ciphertext = raw[:16], raw[16:]
        cipher = AES.new(YDYP_REFRESH_AES_KEY, AES.MODE_CBC, iv)
        plain = cipher.decrypt(ciphertext)
        # PKCS7 去填充
        pad_len = plain[-1] if plain else 0
        if pad_len < 1 or pad_len > 16 or any(byte != pad_len for byte in plain[-pad_len:]):
            return None
        return plain[:-pad_len].decode('utf-8', 'ignore').rstrip('\x00')
    except Exception:
        return None


def _refresh_user_domain_id(phone):
    try:
        jwt_token = middleware.bucketGet('yuhua_ydyp_jwt_by_phone', phone) or ''
    except Exception:
        jwt_token = ''
    return _jwt_user_domain_id(jwt_token)


def _find_account_owner(account_id):
    """从 yuhua_ydyp_user 反查账号所属的机器人用户 ID。"""
    target = str(account_id)
    try:
        users = middleware.bucketAllKeys('yuhua_ydyp_user') or []
    except Exception:
        return ''
    for user in users:
        try:
            raw = middleware.bucketGet('yuhua_ydyp_user', user) or '[]'
            accounts = ast.literal_eval(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        if not isinstance(accounts, (list, tuple)):
            continue
        if any(str(item) == target for item in accounts):
            return str(user)
    return ''


def _store_refreshed_token(account_id, phone, raw_token, expire_seconds=2592000):
    """校验新 CK 后落库并同步青龙；返回 (ok, new_ck 或错误)。"""
    raw_token = str(raw_token or '').strip()
    if not raw_token:
        return False, "刷新响应缺少 token"
    new_auth = 'Basic ' + base64.b64encode(f"mobile:{phone}:{raw_token}".encode('utf-8')).decode('utf-8')
    new_ck_str = f"{new_auth}#{phone}"

    # 先验证新 CK 能否换到 ssoToken，避免把无效 CK 写回覆盖可用凭据
    probe = YP(new_ck_str, phone=phone)
    try:
        probe_ok, probe_msg = probe.sso()
    finally:
        probe.close()
    if not probe_ok:
        return False, f"刷新后校验失败: {probe_msg}"

    middleware.bucketSet('yuhua_ydyp_token', account_id, new_ck_str)
    try:
        expire_seconds = int(float(expire_seconds))
        if expire_seconds > 1_000_000_000_000:
            expire_seconds //= 1000
        if expire_seconds <= 0:
            expire_seconds = 2592000
    except Exception:
        expire_seconds = 2592000
    expires_at = int(time.time() * 1000) + expire_seconds * 1000
    middleware.bucketSet('yuhua_ydyp_token_expire', account_id, str(expires_at))
    # 续期可能由管理员/计划任务触发；备注用户应写账号所属用户，而不是当前操作者
    add_to_qinglong(new_ck_str, account_id, phone, target_user=_find_account_owner(account_id) or None)
    return True, new_ck_str

def _do_native_token_refresh_v2(account_id, phone, current_auth):
    """13.2.5 新版刷新：AES-CBC(clientType=414) + x-yun-* 头。"""
    if not HAS_CRYPTO:
        return False, "未安装pycryptodome依赖，跳过原生刷新"

    user_domain_id = _refresh_user_domain_id(phone)
    headers = {
        'Authorization': current_auth,
        'Content-Type': 'application/json; charset=UTF-8',
        'User-Agent': 'okhttp/4.12.0',
        'x-nettype': '1',
        'x-deviceinfo': YDYP_REFRESH_DEVICE_INFO,
        'x-yun-client-info': YDYP_REFRESH_DEVICE_INFO,
        'x-svctype': '1',
        'hcy-cool-flag': '1',
    }
    if user_domain_id:
        headers['x-yun-uni'] = user_domain_id

    body = aes_cbc_encrypt_refresh('{"clientType":"414"}')
    if not body:
        return False, "加密刷新请求失败"

    try:
        session = get_global_session()
        resp = session.post(
            'https://user-njs.yun.139.com/user/auth/refreshToken',
            headers=headers,
            data=body,
            timeout=15,
        )
        resp.raise_for_status()
        raw = (resp.text or '').strip()
        if not raw:
            return False, "刷新响应为空"
        # 响应可能是 JSON 字符串、{"data":"..."} 或裸 base64
        try:
            unwrapped = json.loads(raw)
            if isinstance(unwrapped, str):
                raw = unwrapped.strip()
            elif isinstance(unwrapped, dict):
                raw = str(unwrapped.get('data') or '').strip()
        except Exception:
            pass

        plain = aes_cbc_decrypt_refresh(raw)
        if plain is None:
            return False, "解密刷新响应失败"
        try:
            payload = json.loads(plain)
        except Exception:
            payload = {'success': True, 'data': {'token': plain.strip()}}

        code = str(payload.get('code') or '')
        if code == '05050006':
            return False, "凭据已失效，请重新登录"
        if not _looks_like_success(payload):
            msg = payload.get('message') or payload.get('msg') or f'code={code}'
            return False, f"刷新失败: {msg}"

        data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
        token = data.get('token') or data.get('authToken')
        expire_seconds = data.get('expireTime') or 2592000
        return _store_refreshed_token(account_id, phone, token, expire_seconds)
    except Exception as e:
        return False, str(e)


def _do_native_token_refresh_legacy(account_id, phone, current_auth):
    """旧版刷新协议（AES-ECB + phoneNumber），保留兜底。"""
    if not HAS_CRYPTO:
        return False, "未安装pycryptodome依赖，跳过原生刷新"

    url = 'https://user-njs.yun.139.com/user/auth/refreshToken'
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.47(0x18002f2c) NetType/WIFI Language/zh_CN miniProgram/wx4e4ed37286c816c2',
        'x-yun-tid': str(uuid.uuid4()),
        'Authorization': current_auth,
        'x-yun-api-version': 'v1',
        'x-yun-module-type': '100',
        'x-yun-op-type': '1',
        'x-yun-app-channel': '10214200',
        'x-yun-client-info': '||8||||||||||||',
        'hcy-cool-flag': '1',
    }

    encrypted_data = aes_encrypt({'phoneNumber': phone}, 'c7lXOigXahPnTViq')
    if not encrypted_data:
        return False, "加密手机号失败"

    try:
        session = get_global_session()
        resp = session.post(url, headers=headers, json={'data': encrypted_data}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        code = str(data.get('code', ''))

        if code in ('0', '00', '000', '0000') or data.get('success'):
            raw_token = (data.get('data') or {}).get('token')
            expire_time = (data.get('data') or {}).get('expireTime')
            return _store_refreshed_token(account_id, phone, raw_token, expire_time)
        return False, data.get('message') or data.get('msg') or "未知错误"
    except Exception as e:
        return False, str(e)


def do_native_token_refresh(account_id, phone, current_auth):
    ok, result = _do_native_token_refresh_v2(account_id, phone, current_auth)
    if ok:
        return True, result
    v2_err = result

    ok_legacy, legacy_result = _do_native_token_refresh_legacy(account_id, phone, current_auth)
    if ok_legacy:
        return True, legacy_result
    return False, f"新版刷新失败: {v2_err}；旧版刷新失败: {legacy_result}"

def check_and_refresh_token(account_id, force=False):
    """
    检查 Token 是否小于 24 小时，如果小于则触发刷新，支持强制刷新。
    返回 (bool是否正常可用, 当前最新ck_str, 提示信息)
    """
    ck_str = middleware.bucketGet('yuhua_ydyp_token', account_id)
    if not ck_str:
        return False, None, "未找到CK"
        
    parts = ck_str.split('#')
    current_auth = parts[0].strip()
    phone = parts[1].strip() if len(parts) > 1 else "未知"
    
    if phone == "未知":
        phone = middleware.bucketGet('yuhua_ydyp_phone', account_id) or "未知"
        
    if not re.match(r'^\d{11}$', phone):
        # 手机号无效则无法执行原生刷新，直接返回现有CK碰碰运气
        return True, ck_str, "手机号无效，跳过刷新"

    phone_mask = phone[:3] + '****' + phone[-4:] if len(phone) >= 7 else phone
    expire_str = middleware.bucketGet('yuhua_ydyp_token_expire', account_id)
    if not expire_str:
        # 旧账号没有 token_expire；尝试从 CK 自带的时间戳补全
        expire_ms = _set_token_expire_from_auth(account_id, current_auth)
        expire_str = str(expire_ms) if expire_ms else ''
        if expire_ms:
            printf(f"[续期] 账号 {phone_mask} 从CK补全到期时间: {expire_ms}", 'INFO')
    now_ms = int(time.time() * 1000)

    need_refresh = force
    if not need_refresh and expire_str:
        try:
            expires_at = int(expire_str)
            # 仅在“已知”剩余有效期小于 24 小时时刷新；缺少过期时间不代表 CK 失效，
            # 继续使用现有 CK，等 SSO/JWT 明确报失效时再由调用方 force 刷新。
            if expires_at - now_ms < 86400000:
                need_refresh = True
        except Exception:
            need_refresh = False

    if need_refresh:
        remaining_hours = 0
        try:
            remaining_hours = int((int(expire_str) - now_ms) / 3600000) if expire_str else 0
        except Exception:
            pass
        printf(f"[续期] 账号 {phone_mask} 触发CK刷新 force={force} 剩余约{remaining_hours}小时", 'INFO')
        ok, result = do_native_token_refresh(account_id, phone, current_auth)
        if ok:
            printf(f"[续期] 账号 {phone_mask} 刷新成功", 'INFO')
            return True, result, "原生刷新成功"
        else:
            printf(f"[续期] 账号 {phone_mask} 刷新失败: {result}", 'WARN')
            # 兜底：如果原生刷新失败（或未安装依赖），尝试使用原有的PHP账密续期
            relogin_ok, relogin_msg = _try_auto_password_relogin(account_id)
            if relogin_ok:
                new_ck = middleware.bucketGet('yuhua_ydyp_token', account_id)
                # 为兜底续期设置一个默认的长期有效时间
                middleware.bucketSet('yuhua_ydyp_token_expire', account_id, str(now_ms + 2592000000))
                printf(f"[续期] 账号 {phone_mask} 账密兜底刷新成功", 'INFO')
                return True, new_ck, "账密兜底刷新成功"
            else:
                printf(f"[续期] 账号 {phone_mask} 账密兜底失败: {relogin_msg}", 'WARN')
                return False, ck_str, f"刷新失败: {result} / {relogin_msg}"

    return True, ck_str, "Token状态良好"

def _try_auto_password_relogin(account_id):
    def sanitize_message(message):
        """
        用****替换输出中包含敏感URL以防止暴露
        """
        sensitive_urls = ['http://yuhualhh.250666.xyz', 'https://yuhualhh.250666.xyz']
        sanitized = str(message)
        for url in sensitive_urls:
            sanitized = sanitized.replace(url, '****')
        return sanitized

    phone = middleware.bucketGet('yuhua_ydyp_phone', account_id) or ""
    password = middleware.bucketGet('yuhua_ydyp_password', account_id) or ""

    if not re.match(r'^\d{11}$', phone):
        return False, "未找到可续期手机号"
    if password == "":
        return False, "未找到账密续期信息"

    try:
        php_api_url = "https://yuhualhh.250666.xyz/api/ydyp_sms_login.php"
        php_api_key = "yuhua666666"

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'X-API-KEY': php_api_key
        })

        relogin_payload = {
            "action": "password_relogin",
            "phone": phone,
            "password": password
        }

        if DEBUG:
            printf("===== [AUTO PASSWORD RELLOGIN REQUEST] =====", "DEBUG")
            printf(f"URL: {php_api_url}", "DEBUG")
            printf(f"BODY(JSON): {json.dumps({'action': 'password_relogin', 'phone': phone, 'password': '******'}, ensure_ascii=False)}", "DEBUG")

        relogin_resp = session.post(php_api_url, json=relogin_payload, timeout=20)

        if DEBUG:
            printf("===== [AUTO PASSWORD RELLOGIN RESPONSE] =====", "DEBUG")
            printf(f"STATUS: {relogin_resp.status_code}", "DEBUG")
            printf(f"RSP HEADERS: {json.dumps(dict(relogin_resp.headers), ensure_ascii=False)}", "DEBUG")
            printf(f"RSP BODY: {_debug_dump(relogin_resp.text)}", "DEBUG")

        relogin_resp.raise_for_status()
        relogin_data = relogin_resp.json()

        if relogin_data.get('code') != 0:
            return False, sanitize_message(relogin_data.get('message', '账密续期失败'))

        data = relogin_data.get('data', {}) or {}
        ck_value = data.get('Authorization', '') or ''
        if not ck_value:
            return False, "账密续期失败：未获取到Authorization"

        if not ck_value.startswith('Basic '):
            ck_value = f"Basic {ck_value}"

        yp_check = YP(ck_value, phone=phone)
        ok, msg = yp_check.sso()
        yp_check.close()
        if not ok:
            return False, sanitize_message(msg)

        user_input = f"{ck_value}#{phone}"
        middleware.bucketSet('yuhua_ydyp_token', account_id, user_input)
        _set_token_expire_from_auth(account_id, user_input)

        auth_time = middleware.bucketGet('yuhua_ydyp_auth', account_id)
        if auth_time and auth_time > str(local_now().date()):
            if add_to_qinglong(user_input, account_id, phone):
                try:
                    ql_envs = get_global_session().get(f"{ql_url}/open/envs", headers={"Authorization": f"Bearer {ql_token}"}, timeout=10)
                    if ql_envs.status_code == 200:
                        items = ql_envs.json().get('data', [])
                        ids = [e.get('id') for e in items if e.get('name') == var_name and f"UID:{account_id}" in str(e.get('remarks',''))]
                        if ids:
                            _enable_envs_in_qinglong(ids)
                except Exception:
                    pass

        return True, "ok"
    except Exception as e:
        return False, sanitize_message(str(e))



from bs4 import BeautifulSoup

# def check_maintenance_page():
    # """
    # 原本用于检查页面标题是否为“服务正常中”，如果不是则停止脚本运行。
    # 现已取消强制限制，仅保留函数定义，不再调用中断逻辑。
    # """
    # url = "http://yuhua.oroe.cn/shouquan"
    # try:
        # session = get_global_session()
        # with session.get(url, timeout=10) as response:
            # response.raise_for_status()
            # response.encoding = 'utf-8'
            # soup = BeautifulSoup(response.text, "html.parser")
            # title = soup.title.string if soup.title else ""
            # if title != "服务正常中":
                # sender.reply("❌ 服务端无法连通，插件停止运行")
                # return False
            # return True
    # except requests.RequestException as e:
        # sender.reply("❌ 服务端无法连通，插件停止运行")
        # return False
    # except Exception as e:
        # sender.reply("❌ 服务端无法连通，插件停止运行")
        # return False

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
    """主函数"""
    try:
        if not check_maintenance_page():
            sender.reply("❌ 服务端无法连通, 插件停止运行")
            return        

        message = sender.getMessage().strip()
   
        if message == '云盘一键抢兑':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            handle_yijian_qiangdui()
        elif message == '云盘停止抢兑':
            stop_exchange()
            return

        if '登录' in message:
            login()
        elif '兑换' in message:
            exchange_entry_point()            
        elif '管理' in message:
            manage_account()
        elif '查询' in message:
            query_account()
        elif message == '云盘清理':
            clean_expired()
        elif message == '云盘授权':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            admin_auth()
        elif message == '云盘检测':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            sender.reply("正在检测....")
            cron_task()
            sender.reply("✅ 已执行云盘检测推送任务")
        else:
            sender.setContinue()
    except Exception as e:
        sender.reply(f"❌ 运行出错: {str(e)}")
    finally:
        close_global_session()

if __name__ == "__main__":
    try:
        var_name, ql_config, manage_cmd, query_cmd, login_cmd, price, coin_price, bingfa = get_config()
        ql_url, ql_token = init_qinglong()
        imtype = sender.getImtype()
        today = str(local_now().date())
        if imtype == 'fake':
            pass
        else:
            main()
    except Exception as e:
        sender.reply(f"❌ 运行出错: {str(e)}")
    finally:
        close_global_session()
