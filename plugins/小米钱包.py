# [title: 小米钱包]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@553ad47e5cb49923a02422f1d5678c8166fb43b0/2025/05/11/f1e18712a3d6cd7ad6b7f61b4e7eda25.png]
# [language: python]
# [rule: ^(米包|小米)(登录|查询|兑换|管理|清理|授权|检测|运行|一键运行|一键抢兑)$]
# [disable:false]
# [open_source: false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [priority: 99999]
# [public: true]
# [version: 3.3.3]
# [price: 6666.66]
# [author: yuhualhh]
# [service: ]
# [description: ❶小米钱包内置任务插件，完成浏览组任务、拉新任务、2天拉新任务以及首次访问活动获取会员时长。支持短信登录、账密登录、扫码登录、黑号清理推送、定时抢兑、自定义并发、CK静默续期、查询、管理、授权、检测授权过期以及CK失效推送等功能<br>❷部分功能的实现需自行添加计划任务伪装管理员定时，了解如何添加计划任务请看移动云盘插件介绍，关于指令『米包检测』与『米包清理』定时『30 18 * * *』，关于指令『米包一键运行』定时『0 8,20 * * *』，关于指令『米包一键抢兑』定时『57 23,9 * * *』<img src="https://gcore.jsdelivr.net/gh/lhz03/img@b4ba469f8e936494ea135a11f6103c9375eae783/2025/10/21/1ced24729474ae46348e41768234d0d3.png">]
# [param: {"required":true,"key":"yuhua_xmqb.zsm","bool":false,"placeholder":"","name":"收款码子","desc":"微信Bot收款码直链"}]
# [param: {"required":true,"key":"yuhua_xmqb.price","bool":false,"placeholder":"","name":"收费价格","desc":"不填默认0元，单位: 元/月"}]
# [param: {"required":true,"key":"yuhua_xmqb.bingfa","bool":false,"placeholder":"","name":"任务并发","desc":"不填默认20"}]
# [param: {"required":true,"key":"yuhua_xmqb.qiangdui_bingfa","bool":false,"placeholder":"","name":"抢兑并发","desc":"不填默认20"}]
# [param: {"required":false,"key":"yuhua_xmqb.status","bool":true,"placeholder":"","name":"推送状态","desc":"是否将米包一键运行结果推送给用户"}]
# [param: {"required":false,"key":"yuhua_xmqb.enable_download","bool":true,"placeholder":"","name":"拉新任务","desc":"是否启用视频专区拉新任务(下载试用)，默认关闭以降低风险"}]
# [param: {"required":false,"key":"yuhua_xmqb.enable_2day_task","bool":true,"placeholder":"","name":"2d拉新任务","desc":"是否启用视频专区2天拉新任务(下载试用2天)，默认关闭以降低风险"}]
import re, json, time, random, hashlib, uuid, threading, os, requests, urllib.parse, urllib3, socket, base64
from decimal import Decimal
from datetime import datetime, timedelta, timezone
import middleware
from bs4 import BeautifulSoup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
scripts_name = "米包"
bucket_prefix = "yuhua_xmqb"
CHINA_TZ = timezone(timedelta(hours=8))
_time_offset = None
DEBUG_LOG = False
_DEVICE_PARAMS_SALT = b'\x1a\x2b\x3c\x4d\x5e\x6f\x0a\x1b\x2c\x3d\x4e\x5f\x0a\x1b\x2c\x3d'
_DEVICE_PARAMS_IDENTIFIER = "yuhua_device_params_key"
def _get_encryption_key():
    return hashlib.sha256(_DEVICE_PARAMS_SALT + _DEVICE_PARAMS_IDENTIFIER.encode('utf-8')).digest()
def _encrypt_data(plain_text_str: str) -> str:
    try:
        key = _get_encryption_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plain_text_str.encode('utf-8'), None)
        encrypted_payload = base64.b64encode(nonce + ciphertext).decode('utf-8')
        return encrypted_payload
    except Exception:
        return ""
def _decrypt_data(encrypted_payload_str: str) -> str:
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    decoded_data = base64.b64decode(encrypted_payload_str.encode('utf-8'))
    nonce = decoded_data[:12]
    ciphertext = decoded_data[12:]
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode('utf-8')
def _get_or_create_device_params(acc_unique_id):
    bucket_key = f'{bucket_prefix}_device_params'
    stored_data = middleware.bucketGet(bucket_key, acc_unique_id)
    if stored_data:
        try:
            decrypted_str = _decrypt_data(stored_data)
            return json.loads(decrypted_str)
        except Exception:
            try:
                return json.loads(stored_data)
            except Exception:
                pass
    random_hex = lambda length: ''.join(random.choices('0123456789abcdef', k=length))
    params = {"oaid": random_hex(16), "androidId": random_hex(16), "regId": f"VC84PIuV8vlUt5+tqovAP47+miC3jz02IhFuY/{random_hex(20)}="}
    params_json_str = json.dumps(params)
    encrypted_params = _encrypt_data(params_json_str)
    if encrypted_params:
        middleware.bucketSet(bucket_key, acc_unique_id, encrypted_params)   
    return params
_offset_expiry = 0
def safe_reply(sender, msg):
    parts = split_long_message(msg)
    for i, part in enumerate(parts):
        if i > 0: time.sleep(random.uniform(0.02, 0.05))
        sender.reply(part)
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
    return get_china_time()
STOP_EXCHANGE = False
def within_exchange_window():
    now = local_now()
    start0_pm = now.replace(hour=23, minute=50, second=0, microsecond=0)
    end0_am = now.replace(hour=0, minute=10, second=0, microsecond=0)
    start9 = now.replace(hour=8, minute=50, second=0, microsecond=0)
    end9 = now.replace(hour=9, minute=10, second=0, microsecond=0)
    start10 = now.replace(hour=9, minute=50, second=0, microsecond=0)
    end10 = now.replace(hour=10, minute=10, second=0, microsecond=0)
    return (now >= start0_pm) or (now <= end0_am) or (start9 <= now <= end9) or (start10 <= now <= end10)
def _sanitize(msg: str) -> str:
    sensitive = ["http://selenium.oroe.cn", "selenium.oroe.cn",
                 "http://47.", "://47."]
    for s in sensitive:
        msg = msg.replace(s, "*")
    return msg
def requests_with_retry(session, method, url, **kwargs):
    if DEBUG_LOG:
        print(f"======== Request (Debug) [{method.upper()}] ========")
        print(f"URL: {url}")
        print(f"Cookies: {session.cookies.get_dict()}")
        for key in ['headers', 'params', 'data', 'json']:
            if key in kwargs and kwargs[key] is not None:
                print(f"{key.capitalize()}: {kwargs[key]}")
    kwargs.setdefault('timeout', 15)
    last_exception = None
    for attempt in range(7):
        try:
            response = session.request(method.upper(), url, **kwargs)
            if DEBUG_LOG:
                print(f"======== Response (Debug) [{response.status_code}] ========")
                print(f"Headers: {response.headers}")
                try: print(f"Body: {json.dumps(response.json(), ensure_ascii=False)}")
                except (json.JSONDecodeError, AttributeError): print(f"Body (Raw): {response.text}")
                print("=====================================")
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            last_exception = e
            if attempt < 2:
                wait_time = random.uniform(0.05, 0.1) * (attempt + 1)
                time.sleep(wait_time)
    if DEBUG_LOG and last_exception: print(f"======== Request FAILED (Debug) ========\n{last_exception}\n=====================================")
    if last_exception:
        raise last_exception
def _mask_identifier(identifier: str) -> str:
    if "****" in identifier or len(identifier) <= 8:
        return identifier
    return identifier[:4] + "****" + identifier[-4:]
def _get_display_name(acc_unique_id: str) -> str:
    user_remark = middleware.bucketGet(f'{bucket_prefix}_remark', acc_unique_id)
    if user_remark and user_remark.strip():
        return user_remark.strip()    
    original_phone = middleware.bucketGet(f'{bucket_prefix}_phone_id', acc_unique_id) or "未知号码"
    return _mask_identifier(original_phone)
def modify_account_remark(sender, acc_unique_id):
    """
    处理用户为单个账号修改备注的逻辑。
    """
    prompt_msg = """=====修改备注=====
请输入新备注
-----------------
请在60秒内完成
回复"q"退出"""
    sender.reply(prompt_msg)
    new_remark = sender.input(60000, 0, False)
    if not new_remark:
        sender.reply("❌ 输入超时")
        return        
    if str(new_remark).lower() == 'q':
        sender.reply("✅ 已退出操作")
        return    
    new_remark_str = str(new_remark).strip()
    if not new_remark_str:
        sender.reply("❌ 备注不能为空")
        return
    middleware.bucketSet(f'{bucket_prefix}_remark', acc_unique_id, new_remark_str)    
    sender.reply(f"✅ 已成功修改备注为[{new_remark_str}]")
def qr_login_mibao(sender, userid, user_config):
    sender.reply("正在获取登录码…")
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    })
    try:
        requests_with_retry(session, 'get', "https://account.xiaomi.com/", allow_redirects=True)
        pre_flight_url = "https://account.xiaomi.com/fe/service/lpLogin/lp?_group=DEFAULT&sid=passport&_locale=zh_CN"
        pre_flight_resp = requests_with_retry(session, 'get', pre_flight_url, allow_redirects=True)
        pre_flight_resp.raise_for_status()
        final_qr_page_url = pre_flight_resp.url
        headers_for_qr_request = {
            "Host": "account.xiaomi.com",
            "Connection": "keep-alive",
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua-mobile": "?0",
            "User-Agent": session.headers["User-Agent"],
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": final_qr_page_url,
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        current_dc = str(int(time.time() * 1000))
        initial_qr_request_url = f"https://account.xiaomi.com/longPolling/loginUrl?_group=DEFAULT&sid=passport&_locale=zh_CN&_hasLogo=false&_qrsize=240&_dc={current_dc}"
        resp_init = requests_with_retry(session, 'get', initial_qr_request_url, headers=headers_for_qr_request)
        resp_init.raise_for_status()
        result_text = resp_init.text.replace("&&&START&&&", "")
        qr_data_json = json.loads(result_text)
        qr_image_url_source = qr_data_json.get("qr")
        login_url = qr_data_json.get("loginUrl")
        poll_url = qr_data_json.get("lp")
        if not qr_image_url_source or not login_url or not poll_url:
            sender.reply("❌ 获取登录码失败")
            return
        final_qr_url_to_send = qr_image_url_source
        try:
            encoded_original_url = urllib.parse.quote(qr_image_url_source)
            shortener_service_url = f"http://s.autman.cn/s?url={encoded_original_url}"
            shortener_response = requests_with_retry(session, 'get', shortener_service_url, timeout=5)
            if shortener_response.ok:
                shortened_url = shortener_response.text.strip()
                if shortened_url and shortened_url.startswith("http"):
                    final_qr_url_to_send = shortened_url
        except Exception: pass        
        sender.replyImage(final_qr_url_to_send)        
        sender.reply("""=====扫码登录=====
使用任意扫码工具扫描并
选任一登录方式完成登录
------------------
请在5分钟内完成
回复"q"取消""")
        user_quit_flag = {"quit": False}
        def _listen_user_input():
            while not user_quit_flag["quit"]:
                u_inp = sender.input(500, 0, False)
                if u_inp and str(u_inp).lower() == "q":
                    user_quit_flag["quit"] = True
                    sender.reply("✅ 已退出操作")
                    break
        listener_thread = threading.Thread(target=_listen_user_input, daemon=True)
        listener_thread.start()
        start_time = time.time()
        headers_for_polling = headers_for_qr_request.copy()
        headers_for_polling["Host"] = urllib.parse.urlparse(poll_url).netloc
        headers_for_polling["Origin"] = "https://account.xiaomi.com"
        while time.time() - start_time < 300 and not user_quit_flag["quit"]:
            try:
                poll_resp = requests_with_retry(session, 'get', poll_url, headers=headers_for_polling, timeout=25)
                poll_resp.raise_for_status()                
                poll_data_text = poll_resp.text
                if poll_data_text.startswith("&&&START&&&"):
                    poll_data_text = poll_data_text.replace("&&&START&&&", "", 1)                
                poll_data = json.loads(poll_data_text)
                if poll_data.get("result") == "ok" and "passToken" in poll_data and "cUserId" in poll_data:
                    user_id_resp = str(poll_data["userId"])
                    pass_token_resp = poll_data["passToken"]
                    c_user_id_resp = poll_data["cUserId"]
                    location_url = poll_data.get("location")
                    session.cookies.set('userId', user_id_resp, domain='.account.xiaomi.com', path='/')
                    session.cookies.set('passToken', pass_token_resp, domain='.account.xiaomi.com', path='/')
                    session.cookies.set('cUserId', c_user_id_resp, domain='account.xiaomi.com', path='/')
                    if location_url:
                        requests_with_retry(session, 'get', location_url, allow_redirects=True)
                    final_cookies_dict = session.cookies.get_dict()
                    ck_string = "; ".join([f"{k}={v}" for k, v in final_cookies_dict.items()])
                    _cookie_login_inner(sender, userid, user_config, ck_string, phone_override=user_id_resp)
                    return
                poll_code = str(poll_data.get("code", ""))
                known_good_codes = ["100", "1", "USER_SCAN", "SCANNED_WAIT_CONFIRM", "101", "WAITING_SCAN", "200", "201"]
                if poll_code in known_good_codes:
                    time.sleep(1)
                    continue
                else:
                    sender.reply(f"❌ 登录失败，未知状态码: {poll_code}")
                    return
            except requests.exceptions.Timeout:
                try:
                    verify_resp = requests_with_retry(session, 'get', login_url, timeout=5, allow_redirects=True)
                    final_url = verify_resp.url
                    if "/lpLogin/result" in final_url and "code=70024" in final_url:
                        sender.reply("❌ 登录码已失效")
                        return
                    else:
                        continue
                except Exception: continue            
            except requests.exceptions.HTTPError as http_e:
                if http_e.response is not None and http_e.response.status_code == 403:
                    sender.reply("❌ 已取消登录")
                else:
                    sender.reply(f"❌ 登录请求失败: {http_e}")
                return
            except Exception as e:
                sender.reply(f"❌ 登录时发生未知错误: {e}")
                return
        if not user_quit_flag["quit"]:
            sender.reply("❌ 超时已退出")
    except Exception as e_init:
        sender.reply(f"❌ 获取登录码时发生错误: {e_init}")
    finally:
        user_quit_flag["quit"] = True
        if 'listener_thread' in locals() and listener_thread.is_alive():
            listener_thread.join()
class MiBao:
    def __init__(self, acc_unique_id, user_id_pass_token_phone_str=None, user_id_service_token_str=None, phone_display_override=None):
        self.acc_unique_id = acc_unique_id
        self.session = requests.Session()
        self.user_id = None; self.pass_token = None; self.service_token = None; self.c_user_id = None
        self.jrairstar_ph = None; self.jrairstar_slh = None
        self.phone_for_display = phone_display_override
        self.rnl_instance = None
        if user_id_pass_token_phone_str:
            params_init = {}
            for item in user_id_pass_token_phone_str.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    params_init[key.strip().lower()] = value.strip()
            self.user_id = params_init.get('userid')
            self.pass_token = params_init.get('passtoken')
            self.c_user_id = params_init.get('cuserid')
        if user_id_service_token_str:
            params = {}
            for item in user_id_service_token_str.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    params[key.strip()] = value.strip()
            service_token = params.get('jrairstar_serviceToken') or params.get('serviceToken')
            if not self.user_id: self.user_id = params.get('userid')
            if service_token:
                self.service_token = service_token
                self.c_user_id = params.get('cuserid', self.c_user_id)
                self.jrairstar_ph = params.get('jrairstar_ph')
                self.jrairstar_slh = params.get('jrairstar_slh')
        if self.phone_for_display:
            self.phone_identifier = self.phone_for_display
        elif self.user_id:
            self.phone_identifier = self.user_id[:4] + "****" + self.user_id[-4:] if len(self.user_id) > 7 else self.user_id
        else:
            self.phone_identifier = "未知账户"
        self.base_headers = { 'User-Agent': 'Mozilla/5.0 (Linux; U; Android 13; zh-CN; M2012K11AC Build/TKQ1.221114.001; AppBundle/com.mipay.wallet; AppVersionName/6.98.0.5484.2643; AppVersionCode/20577630; MiuiVersion/stable-V816.0.6.0.TKHCNXM; DeviceId/alioth; NetworkType/WIFI; mix_version; WebViewVersion/116.0.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Mobile Safari/537.36 XiaoMi/MiuiBrowser/4.3', 'Accept': 'application/json, text/plain, */*' }
        if self.service_token and self.c_user_id:
            api_ck = f"cUserId={self.c_user_id};jrairstar_serviceToken={self.service_token};jrairstar_ph={self.jrairstar_ph or ''};jrairstar_slh={self.jrairstar_slh or ''};"
            self.rnl_instance = RNLIntegrated(api_ck, self.acc_unique_id)
    def get_service_token(self):
        if not self.user_id or not self.pass_token or not self.c_user_id:
            return False, "获取serviceToken失败: 缺少userId, passToken或cUserId"
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*'
            }
            initial_url_with_cuserid = (
                "https://m.jr.airstarfinance.net/mp/api/login?"
                "from=mipay_indexicon_TVcard&deepLinkEnable=false&requestUrl="
                "https%3A%2F%2Fm.jr.airstarfinance.net%2Fmp%2Factivity%2FvideoActivity%3F"
                f"from%3Dmipay_indexicon_TVcard%26_noDarkMode%3Dtrue%26_transparentNaviBar%3Dtrue%26cUserId%3D{self.c_user_id}%26_statusBarHeight%3D137"
            )
            session = requests.Session()
            session.cookies.clear()
            session.headers.update(headers)
            response_stage0 = session.get(initial_url_with_cuserid, allow_redirects=False, timeout=15)
            if response_stage0.status_code != 302:
                return False, f"动态获取sign失败，状态码: {response_stage0.status_code}"
            service_login_url = response_stage0.headers.get('Location')
            if not service_login_url:
                return False, "动态获取sign失败，未找到Location"
            session.cookies.set('userId', self.user_id)
            session.cookies.set('passToken', self.pass_token)
            response_final = session.get(service_login_url, allow_redirects=True, timeout=20)
            final_cookies = session.cookies.get_dict()
            new_service_token_val = final_cookies.get('serviceToken') or final_cookies.get('jrairstar_serviceToken')
            if new_service_token_val:
                self.service_token = new_service_token_val
                self.c_user_id = final_cookies.get('cUserId', self.c_user_id)
                self.jrairstar_ph = final_cookies.get('jrairstar_ph')
                self.jrairstar_slh = final_cookies.get('jrairstar_slh')
                new_pass_token = final_cookies.get('passToken')
                if new_pass_token: self.pass_token = new_pass_token
                if self.acc_unique_id:
                    storage_auth_ck = f"userId={self.user_id};passToken={self.pass_token};cUserId={self.c_user_id};"
                    storage_biz_ck = f"cUserId={self.c_user_id or ''};jrairstar_serviceToken={self.service_token};jrairstar_ph={self.jrairstar_ph or ''};jrairstar_slh={self.jrairstar_slh or ''};"
                    self.rnl_instance = RNLIntegrated(storage_biz_ck, self.acc_unique_id)
                    middleware.bucketSet(f'{bucket_prefix}_token', self.acc_unique_id, storage_auth_ck)
                    middleware.bucketSet(f'{bucket_prefix}_token2', self.acc_unique_id, storage_biz_ck)
                return True, "获取serviceToken成功"
            else:
                if 'pass.xiaomi.com/pass/auth/error' in response_final.url:
                    return False, "未能刷新serviceToken，可能是passToken已失效"
                return False, "未能刷新serviceToken"
        except requests.exceptions.RequestException as e:
            return False, f"网络请求异常: {e}"
        except Exception as e:
            return False, f"未知错误: {e}"
    def check_ck_validity(self):
        if not (self.c_user_id and self.jrairstar_ph and self.jrairstar_slh):
            if self.user_id and self.pass_token:
                get_st_ok, _ = self.get_service_token()
                if not get_st_ok: return False, "CK失效"
        if self.user_id and self.service_token and self.rnl_instance:
            device_params = self.rnl_instance.device_params
            params = {"tid": self.rnl_instance.session_tid, "app": "com.mipay.wallet", "oaid": device_params.get("oaid"), "regId": device_params.get("regId"), "deviceType": "2", "system": "1", "visitEnvironment": "2", "userExtra": self.rnl_instance.user_extra_encoded, "activityCode": "2211-videoWelfare"}
            url_activity = f"https://m.jr.airstarfinance.net/mp/api/generalActivity/queryUserGoldRichSum?{urllib.parse.urlencode(params)}"
            response_data = self.rnl_instance.rr.get(url_activity)
            if response_data and response_data.get("code") == 0 and response_data.get("success") is True:
                return True, "CK有效"
        if self.user_id and self.pass_token:
            get_st_ok, _ = self.get_service_token()
            if get_st_ok and self.rnl_instance:
                device_params = self.rnl_instance.device_params
                params = {"tid": self.rnl_instance.session_tid, "app": "com.mipay.wallet", "oaid": device_params.get("oaid"), "regId": device_params.get("regId"), "deviceType": "2", "system": "1", "visitEnvironment": "2", "userExtra": self.rnl_instance.user_extra_encoded, "activityCode": "2211-videoWelfare"}
                url_activity = f"https://m.jr.airstarfinance.net/mp/api/generalActivity/queryUserGoldRichSum?{urllib.parse.urlencode(params)}"
                response_data = self.rnl_instance.rr.get(url_activity)
                if response_data and response_data.get("code") == 0 and response_data.get("success") is True:
                    return True, "CK有效 (静默续期成功)"
            return False, "CK失效"
        return False, "CK失效"
    def get_account_info_for_query(self):
        is_valid, check_msg = self.check_ck_validity()
        if not is_valid:
            return False, 0.0, 0.0, check_msg
        if self.rnl_instance and self.rnl_instance.query_rewards_and_history():
            return (True, self.rnl_instance.current_total_duration_days,
                    self.rnl_instance.today_earned_duration_days, "查询成功")
        else:
            return False, 0.0, 0.0, "查询失败(RNL接口异常)"
    def run_daily_xiaomi_tasks(self, skip_ck_check=False, enable_download_task=False, enable_2day_task=False):
            if not skip_ck_check:
                is_valid, check_msg = self.check_ck_validity()
                if not is_valid:
                    return False, "CK失效", "CK失效"
            if not self.rnl_instance:
                 return False, "CK失效", "CK失效: 无法初始化任务模块"
            task_execution_success, task_message = self.rnl_instance.execute_daily_tasks(enable_download_task=enable_download_task, enable_2day_task=enable_2day_task)
            if task_execution_success:
                return True, task_message, task_message
            else:
                return False, task_message, task_message
import requests, urllib3, json
from typing import Optional, Dict, Any, Union
class RnlRequestOriginal:
    def __init__(self, cookies: Union[str, dict]):
        self.session = requests.Session()
        self._base_headers = {
            'Host': 'm.jr.airstarfinance.net',
            'User-Agent': 'Mozilla/5.0 (Linux; U; Android 13; zh-CN; M2012K11AC Build/TKQ1.221114.001; AppBundle/com.mipay.wallet; AppVersionName/6.98.0.5484.2643; AppVersionCode/20577630; MiuiVersion/stable-V816.0.6.0.TKHCNXM; DeviceId/alioth; NetworkType/WIFI; mix_version; WebViewVersion/116.0.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Mobile Safari/537.36 XiaoMi/MiuiBrowser/4.3',
        }
        self.update_cookies(cookies)
    def request(
            self, method: str, url: str,
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Union[Dict[str, Any], str, bytes]] = None,
            json_payload: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Optional[Dict[str, Any]]:
        headers = {**self._base_headers, **kwargs.pop('headers', {})}
        try:
            resp = requests_with_retry(
                self.session, method, url,
                params=params, data=data, json=json_payload, headers=headers,
                verify=False, **kwargs
            )
            return resp.json()
        except (requests.RequestException, ValueError, json.JSONDecodeError):
            return None
    def update_cookies(self, cookies: Union[str, dict]) -> None:
        if cookies:
            if isinstance(cookies, str):
                str_cookie, dict_cookies = cookies, self._parse_cookies(cookies)
            else:
                dict_cookies, str_cookie = cookies, "; ".join([f"{k}={v}" for k, v in cookies.items()])
            self.session.cookies.update(dict_cookies)
            self._base_headers['Cookie'] = str_cookie
    @staticmethod
    def _parse_cookies(cookies_str: str) -> Dict[str, str]:
        return {k.strip(): v.strip() for k, v in (item.split('=', 1) for item in cookies_str.split(';') if '=' in item)}
    def get(self, url: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Optional[Dict[str, Any]]:
        return self.request('GET', url, params=params, **kwargs)
    def post(self, url: str, data: Optional[Union[Dict[str, Any], str, bytes]] = None, json_payload: Optional[Dict[str, Any]] = None, **kwargs) -> Optional[Dict[str, Any]]:
        return self.request('POST', url, data=data, json_payload=json_payload, **kwargs)
class RNLIntegrated:
    def __init__(self, service_token_ck_str, acc_unique_id):
        self.activity_code = '2211-videoWelfare'
        self.rr = RnlRequestOriginal(service_token_ck_str)
        self.current_total_duration_days = 0.00
        self.today_earned_duration_days = 0.00
        self.acc_unique_id = acc_unique_id
        self.device_params = _get_or_create_device_params(self.acc_unique_id)
        self.user_extra_str = '{"platformType":1,"com.miui.player":"4.38.0.2","com.miui.video":"v2025082090(MiVideo-UN)","com.mipay.wallet":"6.98.0.5484.2643"}'
        self.user_extra_encoded = urllib.parse.quote(self.user_extra_str)
        self._today_rewards_cache = None
        self.session_tid = str(uuid.uuid4())
    def _get_today_rewards(self):
        if self._today_rewards_cache is not None:
            return self._today_rewards_cache
        rewards = []
        try:
            history_url = f'https://m.jr.airstarfinance.net/mp/api/generalActivity/queryUserJoinList?activityCode={self.activity_code}&pageNum=1&pageSize=50&userExtra={self.user_extra_encoded}'
            history_res = self.rr.get(history_url)
            if history_res and history_res.get('code') == 0 and isinstance(history_res.get('value'), dict):
                today_str = local_now().strftime('%Y-%m-%d')
                for item in history_res['value'].get('data', []):
                    if item.get('createTime', '').startswith(today_str) and int(item.get('value', 0)) > 0:
                        rewards.append(int(item.get('value', 0)))
        except Exception:
            pass
        self._today_rewards_cache = rewards
        return self._today_rewards_cache
    def _safe_complete_browse_task(self, task_id, t_id, brows_click_url_id, ad_info_id, trigger_id):
        try:
            device_params = self.device_params
            base_params = {"tid": self.session_tid, "activityCode": self.activity_code, "app": "com.mipay.wallet", "oaid": device_params.get("oaid"), "regId": device_params.get("regId"), "versionCode": "20577630", "versionName": "6.98.0.5484.2643", "isNfcPhone": "true", "channel": "mipay_indexicon_TVcard", "deviceType": "2", "system": "1", "visitEnvironment": "2", "userExtra": self.user_extra_encoded, "taskId": task_id, "browsTaskId": t_id, "browsClickUrlId": brows_click_url_id, "festivalStatus": "0"}
            if ad_info_id and trigger_id:
                base_params.update({"clickEntryType": "", "adInfoId": ad_info_id, "triggerId": trigger_id})
            else:
                base_params.update({"clickEntryType": "undefined"})
            url = f'https://m.jr.airstarfinance.net/mp/api/generalActivity/completeTask?{urllib.parse.urlencode(base_params)}'
            res = self.rr.get(url)
            if res and res.get("code") == 0: return res.get("value")
        except Exception: pass
        return None
    def _safe_receive_award(self, user_task_id):
        try:
            device_params = self.device_params
            app_limit_raw_str = '{"com.qiyi.video":false,"com.youku.phone":false,"com.tencent.qqlive":false,"com.hunantv.imgo.activity":false,"com.cmcc.cmvideo":false,"com.sankuai.meituan":true,"com.anjuke.android.app":false,"com.tal.abctimelibrary":false,"com.lianjia.beike":false,"com.kmxs.reader":false,"com.jd.jrapp":false,"com.smile.gifmaker":false,"com.kuaishou.nebula":false}'
            params = {"tid": self.session_tid, "imei": "", "device": "alioth", "appLimit": app_limit_raw_str, "activityCode": self.activity_code, "userTaskId": user_task_id, "app": "com.mipay.wallet", "oaid": device_params.get("oaid"), "regId": device_params.get("regId"), "versionCode": "20577630", "versionName": "6.98.0.5484.2643", "isNfcPhone": "true", "channel": "mipay_indexicon_TVcard", "deviceType": "2", "system": "1", "visitEnvironment": "2", "userExtra": self.user_extra_str}
            url = f'https://m.jr.airstarfinance.net/mp/api/generalActivity/luckDraw?{urllib.parse.urlencode(params)}'
            res = self.rr.get(url)
            if res:
                if res.get("code") == 0:
                    return True, "奖励领取成功"
                error_msg = res.get('error', '')
                if error_msg:
                    if '您的账号存在安全风险' in error_msg:
                        middleware.bucketSet(f'{bucket_prefix}_risk_accounts', self.acc_unique_id, 'true')
                    return False, error_msg
        except Exception: pass
        return False, "奖励领取失败"        
    def _safe_complete_download_task(self):
        try:
            device_params = self.device_params
            params = {"tid": self.session_tid, "activityCode": "2211-videoWelfare", "app": "com.mipay.wallet", "oaid": device_params.get("oaid"), "regId": device_params.get("regId"), "versionCode": "20577630", "versionName": "6.98.0.5484.2643", "isNfcPhone": "true", "channel": "mipay_indexicon_TVcard", "deviceType": "2", "system": "1", "visitEnvironment": "2", "userExtra": self.user_extra_encoded, "taskCode": "NEW_USER_CAMPAIGN", "browsTaskId": "", "browsClickUrlId": "1306285"}
            url = f'https://m.jr.airstarfinance.net/mp/api/generalActivity/completeTask?{urllib.parse.urlencode(params)}'
            res = self.rr.get(url)
            if res and res.get("code") == 0: return res.get("value")
            if res and ('今日任务已完成' in res.get('message', '') or '已领取' in res.get('message', '')): return "already_completed"
        except Exception: pass
        return None
    def _safe_receive_download_award(self, user_task_id):
        try:
            if user_task_id == "already_completed": return True, "视频专区拉新任务今日已完成或已领取"
            time.sleep(5)
            device_params = self.device_params
            app_limit_raw_str = '{"com.qiyi.video":false,"com.youku.phone":false,"com.tencent.qqlive":false,"com.hunantv.imgo.activity":false,"com.cmcc.cmvideo":false,"com.sankuai.meituan":true,"com.anjuke.android.app":false,"com.tal.abctimelibrary":false,"com.lianjia.beike":false,"com.kmxs.reader":false,"com.jd.jrapp":false,"com.smile.gifmaker":false,"com.kuaishou.nebula":false}'
            params = {"tid": self.session_tid, "imei": "", "device": "alioth", "appLimit": app_limit_raw_str, "activityCode": "2211-videoWelfare", "userTaskId": user_task_id, "app": "com.mipay.wallet", "oaid": device_params.get("oaid"), "regId": device_params.get("regId"), "versionCode": "20577630", "versionName": "6.98.0.5484.2643", "isNfcPhone": "true", "channel": "mipay_indexicon_TVcard", "deviceType": "2", "system": "1", "visitEnvironment": "2", "userExtra": self.user_extra_str}
            url = f'https://m.jr.airstarfinance.net/mp/api/generalActivity/luckDraw?{urllib.parse.urlencode(params)}'
            res = self.rr.get(url)
            if res:
                if res.get("code") == 0:
                    return True, "视频专区拉新任务奖励领取成功"
                error_msg = res.get('error', '')
                if error_msg:
                    if '您的账号存在安全风险' in error_msg:
                        middleware.bucketSet(f'{bucket_prefix}_risk_accounts', self.acc_unique_id, 'true')
                    return False, error_msg
                if ('今日奖励已领取' in res.get('message', '') or '已领取' in res.get('message', '')):
                    return True, "视频专区拉新任务奖励今日已领取"
        except Exception: pass
        return False, "视频专区拉新任务奖励领取失败"  
    def get_task_list(self):
        data = {"tid": self.session_tid, "activityCode": self.activity_code}
        res = self.rr.post("https://m.jr.airstarfinance.net/mp/api/generalActivity/getTaskList", data=data)
        if not res or res.get("code") != 0: return []
        task_list = res.get("value", {}).get("taskInfoList", [])
        return [t for t in task_list if isinstance(t, dict) and '浏览组浏览任务' in t.get('taskName', '')]
    def get_detailed_task_info(self, task_code):
        cookies_dict = self.rr._parse_cookies(self.rr._base_headers.get('Cookie', ''))
        jrairstar_ph_val = cookies_dict.get('jrairstar_ph', '')
        yimi_data_str = json.dumps({"clientInfo": {"deviceInfo": {"androidVersion": "33","device": "alioth","miuiVersion": 816,"miuiVersionName": "V816","model": "M2012K11AC","restrictImei": "true","screenHeight": 873,"screenWidth": 393},"userInfo": {"androidId": self.device_params.get("androidId"),"connectionType": "WIFI","oaid": self.device_params.get("oaid"),"country": "CN","isPersonalizedAdEnabled": True,"language": "zh-rCN","ua": "Mozilla/5.0 (Linux; U; Android 13; zh-CN; M2012K11AC Build/TKQ1.221114.001; AppBundle/com.mipay.wallet; AppVersionName/6.98.0.5484.2643; AppVersionCode/20577630; MiuiVersion/stable-V816.0.6.0.TKHCNXM; DeviceId/alioth; NetworkType/WIFI; mix_version; WebViewVersion/116.0.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Mobile Safari/537.36 XiaoMi/MiuiBrowser/4.3"},"appInfo": {"packageName": "com.mipay.wallet","version": "6.98.0.5484.2643"},"context": {"eid": ""},"impRequests": [{"adsCount": 1,"tagId": "1.140.4.1"}]}})
        data = {"tid": self.session_tid, "isNfcPhone": "true", "deviceType": "2", "device": "alioth", "appLimit": json.dumps({"com.qiyi.video": False,"com.youku.phone": False,"com.tencent.qqlive": False,"com.hunantv.imgo.activity": False,"com.cmcc.cmvideo": False,"com.sankuai.meituan": True,"com.anjuke.android.app": False,"com.tal.abctimelibrary": False,"com.lianjia.beike": False,"com.kmxs.reader": False,"com.jd.jrapp": False,"com.smile.gifmaker": False,"com.kuaishou.nebula": False}), "pagination": "0", "dataType": "0", "activityCode": self.activity_code, "app": "com.mipay.wallet", "oaid": self.device_params.get("oaid"), "regId": self.device_params.get("regId"), "versionCode": "20577630", "versionName": "6.98.0.5484.2643", "channel": "mipay_indexicon_TVcard", "system": "1", "visitEnvironment": "2", "userExtra": self.user_extra_str, "yimiData": yimi_data_str, "taskCode": task_code, "componentStatus": "0", "jrairstar_ph": jrairstar_ph_val}
        res = self.rr.post("https://m.jr.airstarfinance.net/mp/api/generalActivity/getTask", data=data)
        if not res or res.get("code") != 0: return None
        return res.get("value", {}).get("taskInfo", {})
    def query_rewards_and_history(self):
        try:
            device_params = self.device_params
            params_total = {"tid": self.session_tid, "app": "com.mipay.wallet", "oaid": device_params.get("oaid"), "regId": device_params.get("regId"), "deviceType": "2", "system": "1", "visitEnvironment": "2", "userExtra": self.user_extra_encoded, "activityCode": self.activity_code}
            url = f'https://m.jr.airstarfinance.net/mp/api/generalActivity/queryUserGoldRichSum?{urllib.parse.urlencode(params_total)}'
            total_res = self.rr.get(url)
            if not (total_res and total_res.get('code') == 0 and 'value' in total_res): return False
            self.current_total_duration_days = round(int(total_res['value']) / 100, 2)
            params_history = {"tid": self.session_tid, "app": "com.mipay.wallet", "oaid": device_params.get("oaid"), "regId": device_params.get("regId"), "activityCode": self.activity_code, "pageNum": 1, "pageSize": 30, "userExtra": self.user_extra_encoded}
            history_url = f'https://m.jr.airstarfinance.net/mp/api/generalActivity/queryUserJoinList?{urllib.parse.urlencode(params_history)}'
            history_res = self.rr.get(history_url)
            if history_res and history_res.get('code') == 0 and isinstance(history_res.get('value'), dict):
                today_earned_val = 0
                today_str = local_now().strftime('%Y-%m-%d')
                for item in history_res['value'].get('data', []):
                    if item.get('createTime', '').startswith(today_str) and int(item.get('value', 0)) > 0:
                        today_earned_val += int(item.get('value', 0))
                self.today_earned_duration_days = round(today_earned_val / 100, 2)
            return True
        except Exception: return False
    def get_emi_ad_url(self):
        cookies_dict = self.rr._parse_cookies(self.rr._base_headers.get('Cookie', ''))
        jrairstar_ph = cookies_dict.get('jrairstar_ph', '')
        data = {'tid': self.session_tid, 'pagination':'0','dataType':'0','activityCode':self.activity_code,'app':'com.mipay.wallet','taskCode':'NEW_USER_CAMPAIGN','isRetry':'false','isManualRetry':'false','jrairstar_ph':jrairstar_ph}
        result = self.rr.post("https://m.jr.airstarfinance.net/mp/api/video/getEmiAdUrl", data=data)
        if result and result.get("code") == 0: return result.get("value", {})
        return None
    def is_download_task_really_completed(self):
        try:
            ad_info = self.get_emi_ad_url()
            if not ad_info: return False
            return ad_info.get('completeStatus') == 3
        except Exception: return False
    def silently_handle_first_visit_task(self):
        try:
            task_info = self.get_detailed_task_info("FINANCE_FIRSTIN")
            if not task_info:
                return "fail"
            if task_info.get("completeStatus") == 4 and task_info.get("luckDrawStatus") == 2:
                return "already_done"
            if task_info.get("completeStatus") != 4:
                cookies_dict = self.rr._parse_cookies(self.rr._base_headers.get('Cookie', ''))
                jrairstar_ph_val = cookies_dict.get('jrairstar_ph', '')
                visit_data = {
                    "activityCode": self.activity_code,
                    "app": "com.mipay.wallet",
                    "channel": "mipay_indexicon_TVcard",
                    "deviceType": "2",
                    "system": "1",
                    "visitEnvironment": "2",
                    "userExtra": self.user_extra_str,
                    "jrairstar_ph": jrairstar_ph_val
                }
                visit_url = f"https://m.jr.airstarfinance.net/mp/api/generalActivity/visitIndex?tid={self.session_tid}"
                visit_res = self.rr.post(visit_url, data=visit_data)
                if not (visit_res and visit_res.get("code") == 0):
                    return "fail"
                time.sleep(1)
                task_info = self.get_detailed_task_info("FINANCE_FIRSTIN")
                if not task_info:
                    return "fail"
            if task_info.get("completeStatus") == 4 and task_info.get("luckDrawStatus") == 1:
                user_task_id = task_info.get("userTaskId")
                if user_task_id:
                    success, msg = self._safe_receive_award(user_task_id)
                    if not success and '您的账号存在安全风险' in msg:
                        return msg
                    return "success" if success else "fail"
            return "not_needed"
        except Exception:
            return "fail"
    def get_emi_ad_url_v2(self):
        cookies_dict = self.rr._parse_cookies(self.rr._base_headers.get('Cookie', ''))
        jrairstar_ph = cookies_dict.get('jrairstar_ph', '')
        data = {'tid': self.session_tid, 'pagination':'0','dataType':'0','activityCode':self.activity_code,'app':'com.mipay.wallet','taskCode':'NEW_USER_CAMPAIGN','isRetry':'false','isManualRetry':'false','jrairstar_ph':jrairstar_ph}
        result = self.rr.post("https://m.jr.airstarfinance.net/mp/api/video/getEmiAdUrlV2", data=data)
        if result and result.get("code") == 0: return result.get("value", {})
        return None
    def _safe_complete_2day_task(self, task_id, brows_click_url_id):
        try:
            url = f'https://m.jr.airstarfinance.net/mp/api/video/completeTaskV2?tid={self.session_tid}'
            jrairstar_ph_val = self.rr._parse_cookies(self.rr._base_headers.get('Cookie', '')).get('jrairstar_ph', '')
            data = {'activityCode': self.activity_code, 'app': 'com.mipay.wallet', 'oaid': self.device_params.get("oaid"), 'regId': self.device_params.get("regId"), 'versionCode': '20577630', 'versionName': '6.98.0.5484.2643', 'isNfcPhone': 'true', 'channel': 'mipay_indexicon_TVcard', 'deviceType': '2', 'system': '1', 'visitEnvironment': '2', 'userExtra': self.user_extra_str, 'taskCode': 'NEW_USER_CAMPAIGN_2', 'taskId': task_id, 'browsTaskId': '', 'browsClickUrlId': brows_click_url_id, 'jrairstar_ph': jrairstar_ph_val}
            res = self.rr.post(url, data=data)
            if res and res.get("code") == 0: return res.get("value")
        except Exception: pass
        return None
    def silently_handle_2day_trial_task(self):
        try:
            task_info_container = self.get_emi_ad_url_v2()
            if not (task_info_container and 'tasks' in task_info_container and 'NEW_USER_CAMPAIGN_2' in task_info_container.get('tasks', {})):
                return "no_task"           
            task_info = task_info_container['tasks']['NEW_USER_CAMPAIGN_2']
            status = task_info.get("completeStatus")
            if status == 2:
                return "day_action_already_done"
            if status == 1:
                task_id = task_info.get("taskId")
                if not task_id: return "no_task_id"                
                brows_click_url_id = task_info.get("browsClickUrlId") or 4856570
                self._safe_complete_2day_task(task_id, brows_click_url_id)                
                time.sleep(random.uniform(1.5, 2.5))
                task_info_container = self.get_emi_ad_url_v2()
                if not (task_info_container and 'tasks' in task_info_container and 'NEW_USER_CAMPAIGN_2' in task_info_container.get('tasks', {})):
                    return "day_action_recheck_fail"
                task_info = task_info_container['tasks']['NEW_USER_CAMPAIGN_2']
            final_status = task_info.get("completeStatus")
            user_task_id = task_info.get("userTaskId")
            if final_status >= 3 and user_task_id:
                if 300 not in self._get_today_rewards():
                    success, msg = self._safe_receive_award(user_task_id)
                    if '您的账号存在安全风险' in msg: return msg
                    return "reward_claimed" if success else "reward_claim_fail"
                else:
                    return "already_completed_and_claimed"           
            elif final_status >= 3:
                return "already_completed"
        except Exception:
            return "exception"      
        return "unknown_status"
    def execute_daily_tasks(self, skip_ck_check=False, enable_download_task=False, enable_2day_task=False):
        self._today_rewards_cache = None
        tasks_were_actually_run = False
        initial_completed_tasks = 0
        browse_task_info_initial = self.get_detailed_task_info("BROWSE_GROUP_TASK1")
        if browse_task_info_initial:
            initial_completed_tasks = browse_task_info_initial.get("periodCompleteCount", 0)
        first_visit_status = self.silently_handle_first_visit_task()
        if '您的账号存在安全风险' in str(first_visit_status): return False, first_visit_status
        if first_visit_status == "success": tasks_were_actually_run = True
        if enable_2day_task:
            two_day_status = self.silently_handle_2day_trial_task()
            if '您的账号存在安全风险' in str(two_day_status): return False, two_day_status
            if "rewarded" in str(two_day_status): tasks_were_actually_run = True
        if enable_download_task:
            ad_info = self.get_emi_ad_url()
            if ad_info:
                if ad_info.get('completeStatus') == 3 and not ad_info.get('hasDraw') and ad_info.get('userTaskId'):
                    if 200 not in self._get_today_rewards():
                        success, msg = self._safe_receive_download_award(ad_info.get('userTaskId'))
                        if success: tasks_were_actually_run = True
                        elif '您的账号存在安全风险' in msg: return False, msg
                elif ad_info.get('completeStatus') != 3:
                    user_task_id = self._safe_complete_download_task()
                    if user_task_id:
                        success, msg = self._safe_receive_download_award(user_task_id)
                        if success: tasks_were_actually_run = True
                        elif '您的账号存在安全风险' in msg: return False, msg
        while True:
            task_info = self.get_detailed_task_info("BROWSE_GROUP_TASK1")
            if not task_info: break
            total_tasks = task_info.get("periodCount", 3)
            completed_count = task_info.get("periodCompleteCount", 0)
            claimed_browse_rewards_count = len([r for r in self._get_today_rewards() if r <= 100])
            if completed_count > claimed_browse_rewards_count and task_info.get("luckDrawStatus") == 1 and task_info.get("userTaskId"):
                award_success, award_msg = self._safe_receive_award(task_info.get("userTaskId"))
                if not award_success:
                    if '您的账号存在安全风险' in award_msg: return False, award_msg
                    return False, "未能完成所有任务"
                tasks_were_actually_run = True
                self._today_rewards_cache = None
                continue
            if max(completed_count, claimed_browse_rewards_count) >= total_tasks: break
            task_id, task_code = task_info.get("taskId"), task_info.get("taskCode")
            if not all([task_id, task_code]): break
            time.sleep(random.uniform(12, 14))
            gen_info = task_info.get("generalActivityUrlInfo", {}) or {}
            yimi_response = gen_info.get("yimiResponse", {})
            user_task_id = None
            if yimi_response and 'adInfos' in yimi_response and yimi_response.get('triggerId'):
                ad_infos, trigger_id = yimi_response.get("adInfos", []), yimi_response.get("triggerId")
                ad_info_id = ad_infos[0].get("id") if ad_infos else None
                if all([trigger_id, ad_info_id]): user_task_id = self._safe_complete_browse_task(task_id, gen_info.get("id") or task_id, gen_info.get("browsClickUrlId", 0), ad_info_id, trigger_id)
            else:
                user_task_id = self._safe_complete_browse_task(task_id, gen_info.get("id") or task_id, gen_info.get("browsClickUrlId", 0), None, None)
            if user_task_id:
                award_success, award_msg = self._safe_receive_award(user_task_id)
                if not award_success:
                    if '您的账号存在安全风险' in award_msg: return False, award_msg
                    return False, "未能完成所有任务"
                tasks_were_actually_run = True
                self._today_rewards_cache = None
            time.sleep(random.uniform(1, 2))
        self.query_rewards_and_history()
        final_browse_info = self.get_detailed_task_info("BROWSE_GROUP_TASK1")
        is_browse_completed = final_browse_info and final_browse_info.get("periodCompleteCount", 0) >= final_browse_info.get("periodCount", 3)
        is_download_completed = not enable_download_task or self.is_download_task_really_completed()
        all_tasks_are_complete = is_browse_completed and is_download_completed
        if all_tasks_are_complete and self.today_earned_duration_days == 0.00 and (tasks_were_actually_run or initial_completed_tasks > 0):
            return False, "任务已完成，但无法领取奖励，可能为黑号"
        if all_tasks_are_complete:
            daily_msg = f"任务完成，今日获取时长{self.today_earned_duration_days:.2f}天" if tasks_were_actually_run else "任务已做完，请明日再试"
            return True, daily_msg
        else:
            return False, "未能完成所有任务"
def get_exchange_device_info(acc_unique_id):
    return {
        "app": "com.mipay.wallet",
        "versionCode": "20577630",
        "versionName": "6.98.0.5484.2643",
        "deviceType": "2",
        "system": "1",
        "visitEnvironment": "2",
        "isNfcPhone": "true",
        "channel": "exchange_script"
    }
class MiWalletExchanger:
    def __init__(self, service_token_ck, acc_unique_id, session_tid, device_params):
        self.session = requests.Session()
        self.user_id = None
        self.service_token = None
        self.device_info = get_exchange_device_info(acc_unique_id)
        self.activity_code = "2211-videoWelfare"
        self.session_tid = session_tid
        self.device_params = device_params
        self.parse_cookies(service_token_ck)
        self.setup_session()        
        self.rr = RnlRequestOriginal(service_token_ck)
    def parse_cookies(self, cookies_str):
        try:
            self.cookies_dict = {}
            for item in cookies_str.split(';'):
                if '=' in item:
                    key, value = item.split('=', 1)
                    key = key.strip(); value = value.strip()
                    self.cookies_dict[key] = value
                    if key == 'userId': self.user_id = value
                    elif key in ['serviceToken', 'jrairstar_serviceToken']: self.service_token = value
        except Exception as e:
            pass
    def setup_session(self):
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Linux; U; Android 13; zh-CN; M2012K11AC Build/TKQ1.221114.001; AppBundle/com.mipay.wallet; AppVersionName/6.98.0.5484.2643; AppVersionCode/20577630; MiuiVersion/stable-V816.0.6.0.TKHCNXM; DeviceId/alioth; NetworkType/WIFI; mix_version; WebViewVersion/116.0.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Mobile Safari/537.36 XiaoMi/MiuiBrowser/4.3', 'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'zh-CN,zh;q=0.9', 'Host': 'm.jr.airstarfinance.net'})
        if self.user_id and self.service_token:
            cookie_dict = {'userId': self.user_id}
            if 'jrairstar_serviceToken' in self.cookies_dict:
                cookie_dict['jrairstar_serviceToken'] = self.service_token
            else:
                cookie_dict['serviceToken'] = self.service_token
            for key in ['cUserId', 'jrairstar_ph', 'jrairstar_slh']:
                if key in self.cookies_dict: cookie_dict[key] = self.cookies_dict[key]
            self.session.cookies.update(cookie_dict)
    def get_balance(self):
        try:
            user_extra_str = '{"platformType":1,"com.miui.player":"4.27.0.4","com.miui.video":"v2024090290(MiVideo-UN)","com.mipay.wallet":"6.89.1.5275.2323"}'
            params = {"tid": self.session_tid, "app": "com.mipay.wallet", "oaid": self.device_params.get("oaid"), "regId": self.device_params.get("regId"), "deviceType": "2", "system": "1", "visitEnvironment": "2", "userExtra": urllib.parse.quote(user_extra_str), "activityCode": "2211-videoWelfare"}
            url = f'https://m.jr.airstarfinance.net/mp/api/generalActivity/queryUserGoldRichSum?{urllib.parse.urlencode(params)}'
            data = self.rr.get(url)
            if not data: return False, "CK失效或网络异常"
            if data.get('code') == 0 and data.get('success'):
                balance = round(int(data.get('value', 0)) / 100, 2)
                return True, balance
            else:
                return False, f"查询失败: {data.get('error', '未知错误')}"
        except Exception as e:
            return False, f"查询异常: {str(e)}"
    def get_available_products(self):
        try:
            params = {'tid': self.session_tid, 'oaid': self.device_params.get("oaid"), 'regId': self.device_params.get("regId"), 'activityCode': self.activity_code, 'needPrizeBrand': 'youku,mgtv,iqiyi,tencent,bilibili,other'}
            url = f'https://m.jr.airstarfinance.net/mp/api/generalActivity/getPrizeStatusV2?{urllib.parse.urlencode(params)}'
            data = self.rr.get(url)
            if not data: return False, []
            if data.get('code') == 0 and data.get('success'):
                return True, data.get('value', [])
            return False, []
        except Exception as e:
            return False, []
    def get_direct_exchange_products(self):
        success, all_products = self.get_available_products()
        if not success: return False, []
        direct_exchange_items = []
        for item in all_products:
            if isinstance(item, dict):
                item_name = item.get('prizeName', '')
                if not any(k in item_name for k in ['1分购', '特权', '优惠券', '立减', '优惠购']):
                    if any(k in item_name for k in ['会员', 'VIP', 'SVIP', '月卡']):
                        direct_exchange_items.append(item)
        return True, direct_exchange_items
    def exchange_product(self, prize_code, target_phone=None):
        try:
            user_extra_json = json.loads('{"platformType":1,"com.miui.player":"4.27.0.4","com.miui.video":"v2024090290(MiVideo-UN)","com.mipay.wallet":"6.89.1.5275.2323"}')
            params = {'tid': self.session_tid, 'oaid': self.device_params.get("oaid"), 'regId': self.device_params.get("regId"), 'prizeCode': prize_code, 'activityCode': self.activity_code, 'app': self.device_info['app'], 'channel': 'mipay_unloadoff_TVcard', 'deviceType': self.device_info['deviceType'], 'system': self.device_info['system'], 'visitEnvironment': self.device_info['visitEnvironment'], 'userExtra': json.dumps(user_extra_json, separators=(',', ':'))}
            if target_phone: params['phone'] = target_phone
            url = f'https://m.jr.airstarfinance.net/mp/api/generalActivity/convertGoldRich?{urllib.parse.urlencode(params)}'
            data = self.rr.get(url)
            if not data: return False, "CK失效或网络异常", None
            if data.get('code') == 0 and data.get('success'):
                value = data.get('value', {})
                cost = abs(value.get('value', 0))
                coupon_id = value.get('prizeInfo', {}).get('couponId')
                return True, f"成功兑换，消耗{cost/100:.0f}天时长", coupon_id
            else:
                return False, data.get('error', '未知错误'), None
        except Exception as e:
            return False, f"兑换异常: {str(e)}", None
def local_now():
    return datetime.utcnow() + timedelta(hours=8)
def get_config():
    config = {
        'zsm': middleware.bucketGet(bucket_prefix, 'zsm') or '',
        'price_str': middleware.bucketGet(bucket_prefix, 'price') or '0',
        'login_cmd': f'{scripts_name}登录', 'query_cmd': f'{scripts_name}查询',
        'manage_cmd': f'{scripts_name}管理', 'renew_cmd': f'{scripts_name}续期',
        'admin_renew_cmd': f'{scripts_name}一键续期', 'clean_cmd': f'{scripts_name}清理',
        'auth_cmd': f'{scripts_name}授权',
        'admin_detect_cmd': f'{scripts_name}检测',
        'run_cmd': f'{scripts_name}运行',
        'admin_run_cmd': f'{scripts_name}一键运行',
    }
    try: config['price'] = Decimal(config['price_str'])
    except: config['price'] = Decimal('0')
    config['task_bingfa_str'] = middleware.bucketGet(bucket_prefix, 'bingfa') or '20'
    try:
        config['task_bingfa'] = int(config['task_bingfa_str'])
        if config['task_bingfa'] <= 0:
            config['task_bingfa'] = 20
    except ValueError:
        config['task_bingfa'] = 20    
    config['qiangdui_bingfa_str'] = middleware.bucketGet(bucket_prefix, 'qiangdui_bingfa') or '20'
    try:
        config['qiangdui_bingfa'] = int(config['qiangdui_bingfa_str'])
        if config['qiangdui_bingfa'] <= 0:
            config['qiangdui_bingfa'] = 20
    except ValueError:
        config['qiangdui_bingfa'] = 20    
    config['push_status'] = middleware.bucketGet(bucket_prefix, 'status') == 'true'
    config['enable_download_task'] = middleware.bucketGet(bucket_prefix, 'enable_download') == 'true'
    config['enable_2day_task'] = middleware.bucketGet(bucket_prefix, 'enable_2day_task') == 'true'
    return config
def gen_unique_id(prefix=""):
    timestamp = int(time.time() * 1_000_000)
    return f"{prefix}{timestamp}"
def cookie_login_mibao(sender, userid, user_config):
    sender.reply(f"""
====账号登录=====
❶下载Via浏览器访问并选择任意方式登录 account.xiaomi.com 
❷完成登录后点击左上角查看Cookies并复制，建议私发给Bot避免他人利用CK盗刷
❸若需要上车多号，切勿通过退出账号来切号，请直接清空Via浏览器的数据重新操作
------------------
请在120秒内完成
回复"q"退出""")
    ck_line = sender.input(120000, 1, False)
    if not ck_line or str(ck_line).lower() == "q":
        sender.reply("✅ 已退出操作")
        return
    _cookie_login_inner(sender, userid, user_config, ck_line.strip())
def login_mibaob(sender, userid, user_config):
    menu = """=====账号登录=====
[1] 短信登录
[2] 账密登录    
[3] 扫码登录
[4] Cookie登录
------------------
回复数字选择方式
回复"q"退出"""
    sender.reply(menu)
    sel = sender.input(60000, 0, False)
    if not sel or str(sel).lower() == "q":
        sender.reply("✅ 已退出操作")
        return
    if sel == "3":
        qr_login_mibao(sender, userid, user_config)
    elif sel == "4":
        cookie_login_mibao(sender, userid, user_config)
    elif sel == "2":
        pwd_login_mibao(sender, userid, user_config)        
    elif sel == "1":
        sms_login_mibao(sender, userid, user_config)
    else:
        sender.reply("❌ 无效的选择")
def query_mibaob(sender, userid, user_config):
    user_accounts_list = eval(middleware.bucketGet(f'{bucket_prefix}_user_accounts', userid) or '[]')
    if not user_accounts_list:
        sender.reply(f"""
=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 "{user_config['login_cmd']}" 绑定账号
=================="""); return
    sender.reply("正在查询....")
    for acc_unique_id in user_accounts_list:
        time.sleep(random.uniform(0.4, 0.8))
        phone_id_for_display = _get_display_name(acc_unique_id)
        original_phone = middleware.bucketGet(f'{bucket_prefix}_phone_id', acc_unique_id) or "未知号码"
        auth_time_str = middleware.bucketGet(f'{bucket_prefix}_auth', acc_unique_id)
        auth_expiry_display = "未授权"
        is_authorized_and_valid = False
        if auth_time_str:
            try:
                auth_date = datetime.strptime(auth_time_str, "%Y-%m-%d").date()
                if auth_date >= local_now().date():
                    auth_expiry_display = auth_time_str
                    is_authorized_and_valid = True
                else:
                    auth_expiry_display = "已过期"
            except ValueError:
                auth_expiry_display = "日期格式错误"
        if not is_authorized_and_valid:
            sender.reply(f"【{phone_id_for_display}】{auth_expiry_display}")
            continue
        current_duration_val_str = "N/A"
        today_duration_val_str = "N/A"
        service_token_ck = middleware.bucketGet(f'{bucket_prefix}_token2', acc_unique_id)
        pass_token_phone_ck = middleware.bucketGet(f'{bucket_prefix}_token', acc_unique_id)
        if service_token_ck or pass_token_phone_ck:
            mibao_instance = MiBao(acc_unique_id=acc_unique_id,
                                   user_id_pass_token_phone_str=pass_token_phone_ck,
                                   user_id_service_token_str=service_token_ck,
                                   phone_display_override=original_phone)
            query_success, total_d, today_d, error_msg = mibao_instance.get_account_info_for_query()
            if not query_success:
                sender.reply(f"【{phone_id_for_display}】CK失效")
                if "CK失效" not in error_msg:
                    pass
                continue
            current_duration_val_str = f"{total_d:.2f}"
            today_duration_val_str = f"{today_d:.2f}"
        else:
            sender.reply(f"【{phone_id_for_display}】CK失效")
            continue
        account_part = f"""=====账号信息=====
🤪 用户账号: {phone_id_for_display}
💰 当前时长: {current_duration_val_str}
🔥 今日时长: {today_duration_val_str}
☁️ 授权到期: {auth_expiry_display}
=================="""
        sender.reply(account_part)
def _cookie_login_inner(sender, userid, user_config, ck_raw, phone_override: str | None = None):
    cookie_params = {}
    for item in ck_raw.split(';'):
        if '=' in item:
            key, value = item.strip().split('=', 1)
            cookie_params[key.strip().lower()] = value.strip()
    uid = cookie_params.get('userid')
    pt = cookie_params.get('passtoken')
    cuid = cookie_params.get('cuserid')
    if not uid or not pt or not cuid:
        sender.reply("❌ CK格式不正确，未能找到userId, passToken或cUserId参数")
        return
    actual_phone_identifier = phone_override if phone_override else uid
    ck_norm = f"userId={uid};passToken={pt};cUserId={cuid};"
    temp_mibao_instance = MiBao(acc_unique_id=None, user_id_pass_token_phone_str=ck_norm, phone_display_override=actual_phone_identifier)
    get_st_ok, get_st_msg = temp_mibao_instance.get_service_token()
    if not get_st_ok:
        sender.reply(f"❌ 登录失败: {get_st_msg}")
        return
    true_user_id = temp_mibao_instance.user_id
    service_token_val = temp_mibao_instance.service_token
    c_user_id_val = temp_mibao_instance.c_user_id or ''
    jrairstar_ph_val = temp_mibao_instance.jrairstar_ph or ''
    jrairstar_slh_val = temp_mibao_instance.jrairstar_slh or ''
    service_ck_complete = f"cUserId={c_user_id_val};jrairstar_serviceToken={service_token_val};jrairstar_ph={jrairstar_ph_val};jrairstar_slh={jrairstar_slh_val};"
    accounts_list_str = middleware.bucketGet(f"{bucket_prefix}_user_accounts", userid) or "[]"
    try:
        user_accounts = eval(accounts_list_str)
        if not isinstance(user_accounts, list): user_accounts = []
    except:
        user_accounts = []
    target_account_unique_id = None
    for acc_uid_candidate in user_accounts:
        if middleware.bucketGet(f"{bucket_prefix}_user_mapping", acc_uid_candidate) == true_user_id:
            target_account_unique_id = acc_uid_candidate
            break
    is_new_account_mapping = target_account_unique_id is None
    if is_new_account_mapping:
        target_account_unique_id = gen_unique_id()
        user_accounts.append(target_account_unique_id)
        middleware.bucketSet(f"{bucket_prefix}_user_accounts", userid, str(user_accounts))
        middleware.bucketSet(f"{bucket_prefix}_user_mapping", target_account_unique_id, true_user_id)
    middleware.bucketSet(f"{bucket_prefix}_token", target_account_unique_id, ck_norm)
    middleware.bucketSet(f"{bucket_prefix}_token2", target_account_unique_id, service_ck_complete)
    middleware.bucketSet(f"{bucket_prefix}_phone_id", target_account_unique_id, actual_phone_identifier)
    user_remark = middleware.bucketGet(f'{bucket_prefix}_remark', target_account_unique_id)
    if not user_remark or not user_remark.strip():
        sender.reply("""=====设置备注=====
请设置账号备注
-----------------
请在30秒内完成
回复"q"取消""")
        new_remark_input = sender.input(30000, 0, False)
        if not new_remark_input:
            sender.reply("❌ 输入超时")
        elif str(new_remark_input).lower() == 'q':
            sender.reply("✅ 跳过设置备注")
        elif str(new_remark_input).strip():
            middleware.bucketSet(f'{bucket_prefix}_remark', target_account_unique_id, str(new_remark_input).strip())
        else:
            sender.reply("✅ 跳过设置备注")
    phone_mask = _get_display_name(target_account_unique_id)
    login_status_reply = "添加成功" if is_new_account_mapping else "更新成功"
    sender.reply(f"""===== 登录成功 =====
🤪 账号: {phone_mask}
✅ 状态: {login_status_reply}
------------------
发送"{scripts_name}管理"管理账号
发送"{scripts_name}查询"查询账号""")
def _get_auth_status_details(acc_unique_id):
    auth_time_str = middleware.bucketGet(f'{bucket_prefix}_auth', acc_unique_id)
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
def _handle_user_batch_authorization_by_month(sender, user_config, account_ids):
    if not account_ids:
        sender.reply("❌ 未找到可授权的账号")
        return
    price_prompt = f"授权价格: {user_config['price']}元/月\n" if user_config['price'] > 0 else ""
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
    total_amount = user_config['price'] * months * len(account_ids)
    if total_amount > 0:
        if not user_config['zsm']:
            sender.reply("❌ 管理员未配置收款码")
            return
        pay_msg = f"""=====扫码支付====
📅 时长: {months}月
💰 金额: {total_amount:.2f}元
------------------
请在120秒内完成支付
回复"q"取消"""
        sender.reply(pay_msg)
        sender.replyImage(user_config['zsm'])
        payment_result = sender.waitPay("q", 120 * 1000)
        if str(payment_result).lower() == 'q':
            sender.reply("✅ 已退出操作")
            return
        try:
            payment_data = json.loads(payment_result) if isinstance(payment_result, str) else payment_result
            raw_paid_money = payment_data.get('Money', payment_data.get('money', 0))
            paid_money = Decimal(f"{raw_paid_money:.2f}")
            if paid_money < total_amount:
                sender.reply(f"""
=====支付失败=====
❌ 支付金额不足
------------------
💰 应付: {total_amount:.2f}元
💵 实付: {paid_money}元
==================""")
                return
        except Exception as e:
            sender.reply(f"""
=====支付异常=====
❌ 支付验证失败
------------------
⚠️ 错误: {str(e)[:50]}
==================""")
            return
    success_count = 0
    fail_count = 0
    days_to_add = months * 30
    for acc_id in account_ids:
        try:
            current_auth_str = middleware.bucketGet(f'{bucket_prefix}_auth', acc_id)
            start_date = local_now().date()
            if current_auth_str:
                try:
                    current_auth_date = datetime.strptime(current_auth_str, "%Y-%m-%d").date()
                    if current_auth_date > start_date:
                        start_date = current_auth_date
                except ValueError: pass
            new_auth_date = start_date + timedelta(days=days_to_add)
            middleware.bucketSet(f'{bucket_prefix}_auth', acc_id, new_auth_date.strftime("%Y-%m-%d"))
            success_count += 1
        except Exception as e:
            fail_count += 1
    summary_msg = f"""=====授权完成=====
✅ 成功: {success_count}个账号
❌ 失败: {fail_count}个账号
⏰ 时长: 授权{months}月
==================""";
    sender.reply(summary_msg)
def manage_mibaob(sender, userid, user_config):
    user_accounts_list = eval(middleware.bucketGet(f'{bucket_prefix}_user_accounts', userid) or '[]')
    if not user_accounts_list:
        sender.reply(f"""
=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 "{user_config['login_cmd']}" 绑定账号
=================="""); return
    account_display_parts = ["=====账号列表=====", "[0] 授权全部账号", "------------------"]
    for i, acc_unique_id in enumerate(user_accounts_list, 1):
        display_name = _get_display_name(acc_unique_id)
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
            _handle_user_batch_authorization_by_month(sender, user_config, user_accounts_list)
        elif 1 <= choice_idx <= len(user_accounts_list):
            show_account_action_menu(sender, userid, user_config, user_accounts_list[choice_idx - 1])
        else:
            raise ValueError("选择超出范围")
    except ValueError:
        sender.reply("❌ 无效的选择")
def show_account_action_menu(sender, userid, user_config, acc_unique_id):
    menu = f"""
=====账号操作=====
[1] {scripts_name}授权
[2] 修改备注
[3] 运行任务
[4] {scripts_name}兑换
[5] 删除账号
------------------
回复数字选择操作
回复"q"退出"""
    sender.reply(menu)
    action_choice = sender.input(60000, 0, False)
    if not action_choice: sender.reply("❌ 输入超时"); return
    if action_choice.lower() == 'q': sender.reply("✅ 已退出操作"); return
    if action_choice == '1': auth_single_account(sender, userid, user_config, acc_unique_id)
    elif action_choice == '2':
        modify_account_remark(sender, acc_unique_id)
    elif action_choice == '3':
        sender.reply(f"正在运行...")
        run_single_xiaomi_task_from_manage(sender, userid, user_config, acc_unique_id)
    elif action_choice == '4':
        show_exchange_products(sender, userid, user_config, acc_unique_id)
    elif action_choice == '5':
        confirm_delete_single_account(sender, userid, user_config, acc_unique_id)
    else:
        sender.reply("❌ 无效的选择")
def auth_single_account(sender, userid, user_config, acc_unique_id, admin_mode=False, target_user_id_for_admin=None):
    phone_id_display_auth = _get_display_name(acc_unique_id)
    if user_config['price'] > 0 and not admin_mode:
        sender.reply(f"""
=====账号授权=====
授权价格: {user_config['price']}元/月
请输入授权月数
------------------
回复数字设置月数
回复"q"退出""")
    else:
        sender.reply("""
=====账号授权=====
请输入授权月数
------------------
回复数字设置月数
回复"q"退出""")
    months_str = sender.input(60000, 0, False)
    if not months_str: sender.reply("❌ 输入超时"); return
    if months_str.lower() == 'q': sender.reply("✅ 已退出操作"); return
    try:
        months = int(months_str); assert months > 0
    except: sender.reply("❌ 无效的月数"); return
    total_amount = user_config['price'] * months; payment_succeeded = True
    if total_amount > 0 and not admin_mode:
        if not user_config['zsm']: sender.reply("❌ 未配置收款码"); return
        pay_msg = f"""
=====扫码支付====
📅 时长: {months}月
💰 金额: {total_amount}元
------------------
请在120秒内完成支付
回复"q"取消"""
        sender.reply(pay_msg); sender.replyImage(user_config['zsm'])
        payment_result = sender.waitPay("q", 120 * 1000)
        if str(payment_result).lower() == 'q': sender.reply("✅ 已退出操作"); return
        try:
            payment_data = json.loads(payment_result) if isinstance(payment_result, str) else payment_result
            raw_paid_money = payment_data.get('Money', payment_data.get('money', 0))
            paid_money = Decimal(f"{raw_paid_money:.2f}")
            if paid_money < total_amount:
                sender.reply(f"""
=====支付失败=====
❌ 支付金额不足
------------------
💰 应付: {total_amount}元
💵 实付: {paid_money}元
=================="""); payment_succeeded = False
        except Exception as e:
            sender.reply(f"""
=====支付异常=====
❌ 支付验证失败
------------------
⚠️ 错误: {str(e)[:50]}
=================="""); payment_succeeded = False
    if not payment_succeeded: return
    current_auth_str = middleware.bucketGet(f'{bucket_prefix}_auth', acc_unique_id)
    start_date = local_now().date()
    if current_auth_str:
        try:
            current_auth_date = datetime.strptime(current_auth_str, "%Y-%m-%d").date()
            if current_auth_date > start_date: start_date = current_auth_date
        except ValueError: pass
    new_auth_date = start_date + timedelta(days=months * 30)
    new_auth_date_str = new_auth_date.strftime("%Y-%m-%d")
    middleware.bucketSet(f'{bucket_prefix}_auth', acc_unique_id, new_auth_date_str)
    days_authed = months * 30
    sender.reply(f"""
=====授权成功=====
🤪 账号: {phone_id_display_auth}
⏰ 时长: {days_authed}天
📅 到期: {new_auth_date_str}
==================""")
def confirm_delete_single_account(sender, userid, user_config, acc_unique_id):
    phone_id_display_del = _get_display_name(acc_unique_id)
    sender.reply(f"⚠️ 确认要删除账号 {phone_id_display_del} 吗？(y/n)")
    confirm_choice = sender.input(30000, 0, False)
    if not confirm_choice: sender.reply("❌ 输入超时"); return
    if confirm_choice.lower() == 'y': delete_single_account(sender, userid, user_config, acc_unique_id)
    elif confirm_choice.lower() == 'n': sender.reply("✅ 已取消删除操作")
def delete_single_account(sender, userid, user_config, acc_unique_id):
    phone_id_display_del_succ = _get_display_name(acc_unique_id)
    user_accounts_list = eval(middleware.bucketGet(f'{bucket_prefix}_user_accounts', userid) or '[]')
    if acc_unique_id in user_accounts_list:
        user_accounts_list.remove(acc_unique_id)
        if not user_accounts_list:
            try:
                middleware.bucketDel(f'{bucket_prefix}_user_accounts', userid)
            except Exception:
                pass
        else:
            middleware.bucketSet(f'{bucket_prefix}_user_accounts', userid, str(user_accounts_list))
    try:
        middleware.bucketDel(f'{bucket_prefix}_token', acc_unique_id)
    except Exception:
        pass
    try:
        middleware.bucketDel(f'{bucket_prefix}_token2', acc_unique_id)
    except Exception:
        pass
    try:
        middleware.bucketDel(f'{bucket_prefix}_auth', acc_unique_id)
    except Exception:
        pass
    try:
        middleware.bucketDel(f'{bucket_prefix}_phone_id', acc_unique_id)
    except Exception:
        pass
    try:
        middleware.bucketDel(f'{bucket_prefix}_user_mapping', acc_unique_id)
    except Exception:
        pass
    try:
        middleware.bucketDel(f'{bucket_prefix}_remark', acc_unique_id)
    except Exception:
        pass
    try:
        middleware.bucketDel(f'{bucket_prefix}_device_ids', acc_unique_id)
    except Exception:
        pass
    sender.reply(f"✅ 已删除账号 {phone_id_display_del_succ}")
def run_single_xiaomi_task_from_manage(sender, userid, user_config, acc_unique_id):
    display_name = _get_display_name(acc_unique_id)
    original_phone = middleware.bucketGet(f'{bucket_prefix}_phone_id', acc_unique_id) or "未知号码"
    auth_time_str = middleware.bucketGet(f'{bucket_prefix}_auth', acc_unique_id)
    is_authorized = False
    if auth_time_str:
        try:
            if datetime.strptime(auth_time_str, "%Y-%m-%d").date() >= local_now().date():
                is_authorized = True
        except ValueError:
            pass
    if not is_authorized:
        reply = f"""=====米包运行结果=====
🤪 账号: {display_name}
💫 结果: 未授权或授权已过期
=================="""
        sender.reply(reply)
        return
    service_token_ck = middleware.bucketGet(f'{bucket_prefix}_token2', acc_unique_id)
    pass_token_phone_ck = middleware.bucketGet(f'{bucket_prefix}_token', acc_unique_id)
    mibao_instance = MiBao(acc_unique_id=acc_unique_id,
                           user_id_pass_token_phone_str=pass_token_phone_ck,
                           user_id_service_token_str=service_token_ck,
                           phone_display_override=original_phone)
    success, user_message, _ = mibao_instance.run_daily_xiaomi_tasks(enable_download_task=user_config.get('enable_download_task', False), enable_2day_task=user_config.get('enable_2day_task', False))
    if success:
        reply = f"""=====米包运行结果=====
🤪 账号: {display_name}
💫 结果: {user_message}
=================="""
    else:
        final_user_message = "CK失效" if "CK失效" in user_message else user_message
        reply = f"""=====米包运行结果=====
🤪 账号: {display_name}
💫 结果: {final_user_message}
=================="""
    sender.reply(reply)
def run_xiaomi_tasks_for_user(sender, userid, user_config):
    sender.reply(f"正在运行...")
    user_accounts_list = eval(middleware.bucketGet(f'{bucket_prefix}_user_accounts', userid) or '[]')
    if not user_accounts_list:
        sender.reply(f"""
=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 "{user_config['login_cmd']}" 绑定账号
==================""")
        return
    for acc_unique_id in user_accounts_list:
        time.sleep(random.uniform(0.5, 1.0))
        run_single_xiaomi_task_from_manage(sender, userid, user_config, acc_unique_id)    
def _execute_task_for_single_account_admin(acc_details, enable_download_task, enable_2day_task):
    acc_unique_id, owner_sduck_userid, original_phone, pass_token_phone_ck, service_token_ck = acc_details
    display_name = _get_display_name(acc_unique_id)
    auth_time_str = middleware.bucketGet(f'{bucket_prefix}_auth', acc_unique_id)
    if not auth_time_str or datetime.strptime(auth_time_str, "%Y-%m-%d").date() < local_now().date():
        return owner_sduck_userid, display_name, False, "未授权或授权已过期"
    mibao_instance = MiBao(acc_unique_id=acc_unique_id,
                           user_id_pass_token_phone_str=pass_token_phone_ck,
                           user_id_service_token_str=service_token_ck,
                           phone_display_override=original_phone)
    is_valid, check_msg = mibao_instance.check_ck_validity()
    if not is_valid:
        return owner_sduck_userid, display_name, False, check_msg
    task_success, task_user_msg, task_admin_reason = mibao_instance.run_daily_xiaomi_tasks(skip_ck_check=True, enable_download_task=enable_download_task, enable_2day_task=enable_2day_task)
    if task_success:
        return owner_sduck_userid, display_name, True, task_user_msg
    else:
        return owner_sduck_userid, display_name, False, task_admin_reason
def admin_run_all_xiaomi_tasks(sender, user_config):
    if not sender.isAdmin():
        sender.reply("❌ 需要管理员权限")
        return
    sender.reply(f"正在运行...")
    accounts_to_process_details = []
    all_sduck_users = middleware.bucketAllKeys(f'{bucket_prefix}_user_accounts')
    for sduck_userid_map in all_sduck_users:
        sduck_user_acc_list_str = middleware.bucketGet(f'{bucket_prefix}_user_accounts', sduck_userid_map)
        if sduck_user_acc_list_str:
            try:
                sduck_user_acc_list = eval(sduck_user_acc_list_str)
                for acc_id_map in sduck_user_acc_list:
                    original_phone_db = middleware.bucketGet(f'{bucket_prefix}_phone_id', acc_id_map) or f"未知_{acc_id_map}"
                    pass_token_ck_db = middleware.bucketGet(f'{bucket_prefix}_token', acc_id_map)
                    service_token_ck_db = middleware.bucketGet(f'{bucket_prefix}_token2', acc_id_map)
                    if pass_token_ck_db:
                        accounts_to_process_details.append((acc_id_map, sduck_userid_map, original_phone_db, pass_token_ck_db, service_token_ck_db or ""))
            except Exception as e_eval_admin_run:
                pass
    if not accounts_to_process_details:
        sender.reply(f"""=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 "{user_config['login_cmd']}" 绑定账号
==================""")
        return
    max_workers = user_config.get('task_bingfa', 20)
    enable_download_task_flag = user_config.get('enable_download_task', False)
    enable_2day_task_flag = user_config.get('enable_2day_task', False)
    results_from_threads = []
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_details = {executor.submit(_execute_task_for_single_account_admin, details, enable_download_task_flag, enable_2day_task_flag): details for details in accounts_to_process_details}
        for future in as_completed(future_to_details):
            acc_details_key = future_to_details[future]
            try:
                results_from_threads.append(future.result())
            except Exception as exc:
                results_from_threads.append((acc_details_key[1], _mask_identifier(acc_details_key[2]), False, f"执行异常: {str(exc)[:30]}"))
    successful_runs_count = 0
    failed_runs_count = 0
    failure_details_for_admin_reply = []
    for result_tuple in results_from_threads:
        owner_id, masked_ph, success_status, final_message = result_tuple
        if success_status:
            successful_runs_count += 1
            reply_to_user = f"""=====米包运行结果=====
🤪 账号: {masked_ph}
💫 结果: {final_message}
=================="""
        else:
            failed_runs_count += 1
            failure_details_for_admin_reply.append(f"🤪 账号: {masked_ph}\n🪁 原因: {final_message}")
            reply_to_user = f"""=====米包运行结果=====
🤪 账号: {masked_ph}
💫 结果: {final_message}
=================="""
        if user_config.get('push_status') and owner_id:
            try:
                push_message_to_user(owner_id, reply_to_user)
            except Exception as e_push_admin_batch:
                pass
    admin_summary_reply = [
        "=====米包一键统计=====",
        f"✨ 总账号数: {len(accounts_to_process_details)}",
        f"✅ 运行成功: {successful_runs_count}",
        f"❌ 运行失败: {failed_runs_count}",
        "------------------"
    ]
    if failure_details_for_admin_reply:
        admin_summary_reply.append("📝 失败详情:")
        admin_summary_reply.extend(failure_details_for_admin_reply)
    elif failed_runs_count == 0:
        admin_summary_reply.append("所有账号均已成功运行")
    else:
        admin_summary_reply.append("部分账号运行失败，详情请查看日志")
    admin_summary_reply.append("==================")
    safe_reply(sender, "\n".join(admin_summary_reply))
def admin_detect_all_accounts(sender, user_config):
    if not sender.isAdmin():
        sender.reply("❌ 此功能需要管理员权限")
        return
    sender.reply("正在检测....")
    all_sduck_users = middleware.bucketAllKeys(f'{bucket_prefix}_user_accounts')
    if not all_sduck_users:
        sender.reply("✅ 已执行米包检测推送任务")
        return
    for sduck_userid_detect in all_sduck_users:
        user_accounts_list_detect = eval(middleware.bucketGet(f'{bucket_prefix}_user_accounts', sduck_userid_detect) or '[]')
        for acc_unique_id_detect in user_accounts_list_detect:
            time.sleep(random.uniform(0.1, 0.3))
            phone_id_display_detect = _get_display_name(acc_unique_id_detect)
            original_phone_detect = middleware.bucketGet(f'{bucket_prefix}_phone_id', acc_unique_id_detect) or "未知号码"
            service_token_ck = middleware.bucketGet(f'{bucket_prefix}_token2', acc_unique_id_detect)
            pass_token_phone_ck = middleware.bucketGet(f'{bucket_prefix}_token', acc_unique_id_detect)
            push_message_content = None
            auth_time_str = middleware.bucketGet(f'{bucket_prefix}_auth', acc_unique_id_detect)
            auth_problem_msg = None
            auth_is_ok = False
            if not auth_time_str:
                auth_problem_msg = "未授权，请及时授权"
            else:
                try:
                    if datetime.strptime(auth_time_str, "%Y-%m-%d").date() < local_now().date():
                        auth_problem_msg = "授权已过期，请及时续费"
                    else:
                        auth_is_ok = True
                except ValueError:
                    auth_problem_msg = "授权日期异常，请联系管理员"
            if auth_problem_msg:
                push_message_content = auth_problem_msg
            if auth_is_ok and not push_message_content:
                if not service_token_ck and not pass_token_phone_ck:
                    push_message_content = f"缺少必要的CK信息，请重新登录"
                else:
                    mibao_instance = MiBao(acc_unique_id=acc_unique_id_detect,
                                           user_id_pass_token_phone_str=pass_token_phone_ck,
                                           user_id_service_token_str=service_token_ck,
                                           phone_display_override=original_phone_detect)
                    is_valid, check_msg = mibao_instance.check_ck_validity()
                    if not is_valid:
                        push_message_content = "CK失效，请重新登录"
            if push_message_content:
                final_push_msg = f"""
===== {scripts_name}通知 =====
🤪 账号: {phone_id_display_detect}
📢 消息: {push_message_content}
=================="""
                try:
                    push_message_to_user(sduck_userid_detect, final_push_msg)
                except Exception as e_push_main:
                    pass
    sender.reply(f"✅ 已执行{scripts_name}检测推送任务")
def clean_expired_or_invalid_mibaob(sender, user_config):
    if not sender.isAdmin(): 
        sender.reply("❌ 需要管理员权限")
        return
    sender.reply("正在清理..."); 
    cleaned_count = 0    
    accounts_to_delete_final = set()
    managed_accounts_set = set()
    all_sduck_users = middleware.bucketAllKeys(f'{bucket_prefix}_user_accounts') or []
    for sduck_userid in all_sduck_users:
        user_accounts_list_str = middleware.bucketGet(f'{bucket_prefix}_user_accounts', sduck_userid)
        current_user_accounts_orig = []
        try:
            parsed_list = eval(user_accounts_list_str or '[]')
            if isinstance(parsed_list, list):
                current_user_accounts_orig = parsed_list
            else:
                current_user_accounts_orig = []
        except Exception as e_eval:
            current_user_accounts_orig = []
        valid_accounts_for_this_user_new = list(current_user_accounts_orig)        
        for acc_unique_id in current_user_accounts_orig:
            managed_accounts_set.add(acc_unique_id)
            time.sleep(random.uniform(0.01, 0.05))
            if middleware.bucketGet(f'{bucket_prefix}_risk_accounts', acc_unique_id):
                display_name = _get_display_name(acc_unique_id)
                auth_expiry = middleware.bucketGet(f'{bucket_prefix}_auth', acc_unique_id) or "未知"
                push_message = f"""=====米包清理=====
🤪 用户账号: {display_name}
☁️ 授权到期: {auth_expiry}
🪁 清理原因: 您的账号存在安全风险
=================="""
                push_message_to_user(sduck_userid, push_message)
                accounts_to_delete_final.add(acc_unique_id)
                if acc_unique_id in valid_accounts_for_this_user_new:
                    valid_accounts_for_this_user_new.remove(acc_unique_id)
                continue
            auth_expired_or_missing = False
            auth_time_str_clean = middleware.bucketGet(f'{bucket_prefix}_auth', acc_unique_id)
            if not auth_time_str_clean:
                auth_expired_or_missing = True
            else:
                try:
                    if datetime.strptime(auth_time_str_clean, "%Y-%m-%d").date() < local_now().date():
                        auth_expired_or_missing = True
                except ValueError:
                    auth_expired_or_missing = True            
            if auth_expired_or_missing:
                accounts_to_delete_final.add(acc_unique_id)
                if acc_unique_id in valid_accounts_for_this_user_new:
                    valid_accounts_for_this_user_new.remove(acc_unique_id)
        if len(valid_accounts_for_this_user_new) != len(current_user_accounts_orig):
            if not valid_accounts_for_this_user_new:
                try:
                    middleware.bucketDel(f'{bucket_prefix}_user_accounts', sduck_userid)
                except Exception:
                    pass
            else:
                middleware.bucketSet(f'{bucket_prefix}_user_accounts', sduck_userid, str(valid_accounts_for_this_user_new))
    potential_orphan_ids = set()
    data_bucket_names = [
        f'{bucket_prefix}_phone_id', 
        f'{bucket_prefix}_token', 
        f'{bucket_prefix}_token2', 
        f'{bucket_prefix}_user_mapping',
        f'{bucket_prefix}_auth',
        f'{bucket_prefix}_remark',
        f'{bucket_prefix}_risk_accounts'
    ]
    for bucket_name in data_bucket_names:
        keys_from_this_bucket = middleware.bucketAllKeys(bucket_name) or []
        potential_orphan_ids.update(keys_from_this_bucket)        
    for acc_id in potential_orphan_ids:
        if acc_id not in managed_accounts_set:
            accounts_to_delete_final.add(acc_id)
    if accounts_to_delete_final:
        for acc_id_to_delete in accounts_to_delete_final:
            try:
                middleware.bucketDel(f'{bucket_prefix}_token', acc_id_to_delete)
            except Exception:
                pass
            try:
                middleware.bucketDel(f'{bucket_prefix}_token2', acc_id_to_delete)
            except Exception:
                pass
            try:
                middleware.bucketDel(f'{bucket_prefix}_auth', acc_id_to_delete) 
            except Exception:
                pass
            try:
                middleware.bucketDel(f'{bucket_prefix}_phone_id', acc_id_to_delete)
            except Exception:
                pass
            try:
                middleware.bucketDel(f'{bucket_prefix}_user_mapping', acc_id_to_delete)
            except Exception:
                pass
            try:
                middleware.bucketDel(f'{bucket_prefix}_remark', acc_id_to_delete)
            except Exception:
                pass
            try:
                middleware.bucketDel(f'{bucket_prefix}_risk_accounts', acc_id_to_delete)
            except Exception:
                pass
            cleaned_count += 1
    sender.reply(f"✅ 已清理 {cleaned_count} 个未授权、已过期或存在安全风险的账号")
def admin_auth_mibaob(sender, user_config):
    if not sender.isAdmin(): sender.reply("❌ 需要管理员权限"); return
    auth_menu_admin = f"""
=====授权管理=====
[1] 授权所有用户
[2] 授权指定用户
------------------
回复数字选择功能
回复"q"退出"""
    sender.reply(auth_menu_admin)
    choice = sender.input(60000, 0, False)
    if not choice: sender.reply("❌ 输入超时"); return
    if choice.lower() == 'q': sender.reply("✅ 已退出操作"); return
    if choice == '1': admin_batch_auth_all(sender, user_config)
    elif choice == '2': admin_auth_specific_user(sender, user_config)
    else: sender.reply("❌ 无效的选择")
def admin_batch_auth_all(sender, user_config):
    sender.reply("""
=====批量操作=====
请输入授权天数
------------------
回复数字设置天数
回复"q"退出""")
    days_str = sender.input(60000, 0, False)
    if not days_str: sender.reply("❌ 输入超时"); return
    if days_str.lower() == 'q': sender.reply("✅ 已退出操作"); return
    try:
        days_to_modify = int(days_str)
    except:
        sender.reply("❌ 无效的天数"); return
    processed_accounts = 0
    success_auth_count = 0    
    all_users = middleware.bucketAllKeys(f'{bucket_prefix}_user_accounts')
    if not all_users:
        sender.reply(f"""
=====操作完成=====
✅ 成功: 0个账号
❌ 失败: 0个账号
⏰ 授权: {days_to_modify}天
==================""")
        return    
    for current_userid in all_users:
        user_accounts = eval(middleware.bucketGet(f'{bucket_prefix}_user_accounts', current_userid) or '[]')
        for acc_unique_id in user_accounts:
            processed_accounts += 1
            time.sleep(0.05)
            current_auth_str_loop = middleware.bucketGet(f'{bucket_prefix}_auth', acc_unique_id)
            start_date_loop = local_now().date()
            if current_auth_str_loop:
                try:
                    current_auth_date_loop = datetime.strptime(current_auth_str_loop, "%Y-%m-%d").date()
                    if current_auth_date_loop > start_date_loop:
                        start_date_loop = current_auth_date_loop
                except ValueError: pass
            new_auth_date_str_loop = (start_date_loop + timedelta(days=days_to_modify)).strftime("%Y-%m-%d")
            middleware.bucketSet(f'{bucket_prefix}_auth', acc_unique_id, new_auth_date_str_loop)
            success_auth_count +=1    
    sender.reply(f"""
=====授权完成=====
✅ 成功: {success_auth_count}个账号
❌ 失败: {processed_accounts - success_auth_count}个账号
⏰ 授权: {days_to_modify}天
==================""")
def admin_auth_specific_user(sender, user_config):
    sender.reply("""
=====指定授权=====
请输入用户ID
(发送myuid可获取ID)
------------------
回复"q"退出""")
    target_userid = sender.input(60000, 0, False)
    if not target_userid: sender.reply("❌ 输入超时"); return
    if target_userid.lower() == 'q': sender.reply("✅ 已退出操作"); return
    target_user_accounts = eval(middleware.bucketGet(f'{bucket_prefix}_user_accounts', target_userid) or '[]')
    if not target_user_accounts:
        sender.reply(f"❌ 未找到该用户的账号")
        return
    account_display_parts = ["=====账号列表=====", "[0] 授权全部账号", "------------------"]
    for i, acc_id in enumerate(target_user_accounts, 1):
        display_name = _get_display_name(acc_id)
        icon, status_text = _get_auth_status_details(acc_id)        
        account_info = f"""[{i}] 账号信息
🤪 账号: {display_name}
☁ 授权: {icon} {status_text}"""
        account_display_parts.append(account_info)
        account_display_parts.append("------------------")
    account_display_parts.extend(["回复数字选择", "回复'q'退出", "=================="])
    sender.reply("\n".join(account_display_parts))
    choice_acc = sender.input(60000, 0, False)
    if not choice_acc: sender.reply("❌ 输入超时"); return
    if choice_acc.lower() == 'q': sender.reply("✅ 已退出操作"); return
    try:
        idx_choice = int(choice_acc)
        if not (0 <= idx_choice <= len(target_user_accounts)):
            raise ValueError("选择的账号序号无效")
    except ValueError:
        sender.reply("❌ 无效的选择"); return
    sender.reply("""
=====设置授权时间=====
请输入授权天数
------------------
回复数字设置天数
回复"q"退出""")
    days_str_admin = sender.input(60000, 0, False)
    if not days_str_admin: sender.reply("❌ 输入超时"); return
    if days_str_admin.lower() == 'q': sender.reply("✅ 已退出操作"); return
    try:
        days_to_modify = int(days_str_admin)
    except:
        sender.reply("❌ 无效的天数"); return
    accounts_to_process = []
    if idx_choice == 0:
        accounts_to_process = target_user_accounts
    else:
        accounts_to_process.append(target_user_accounts[idx_choice - 1])
    success_count = 0
    fail_count = 0
    for acc_id in accounts_to_process:
        try:
            current_auth_str = middleware.bucketGet(f'{bucket_prefix}_auth', acc_id)
            start_date = local_now().date()
            if current_auth_str:
                try:
                    current_auth_date = datetime.strptime(current_auth_str, "%Y-%m-%d").date()
                    if current_auth_date > start_date:
                        start_date = current_auth_date
                except ValueError: pass
            new_auth_date = start_date + timedelta(days=days_to_modify)
            middleware.bucketSet(f'{bucket_prefix}_auth', acc_id, new_auth_date.strftime("%Y-%m-%d"))
            success_count += 1
        except Exception as e:
            fail_count += 1
    summary_msg = f"""=====授权完成=====
✅ 成功: {success_count}个账号
❌ 失败: {fail_count}个账号
⏰ 授权: {days_to_modify}天
==================""";
    sender.reply(summary_msg)
def _perform_maintenance_check() -> bool:
    url = "https://yuhualhh.250666.xyz/shouquan"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
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
def push_message_to_user(user_id, message):
    if not user_id or not message:
        return
    try:
        platforms = ['qq', 'qb', 'wx', 'gw', 'sb', 'wb', 'tg', 'tb', 'qx', 'xy', 'ip']
        for platform in platforms:
            middleware.push(platform, '', user_id, '', message)
            time.sleep(0.1)
    except Exception as e:
        pass
def check_account_authorization(acc_unique_id):
    auth_time_str = middleware.bucketGet(f'{bucket_prefix}_auth', acc_unique_id)
    if not auth_time_str:
        return False    
    try:
        auth_date = datetime.strptime(auth_time_str, "%Y-%m-%d").date()
        return auth_date >= local_now().date()
    except ValueError:
        return False
def exchange_mibaob(sender, userid, user_config):
    user_accounts_list = eval(middleware.bucketGet(f'{bucket_prefix}_user_accounts', userid) or '[]')
    if not user_accounts_list:
        sender.reply(f"""=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 "{user_config['login_cmd']}" 绑定账号
==================""")
        return
    account_display_parts = ["=====账号列表====="]
    for i, acc_unique_id in enumerate(user_accounts_list, 1):
        display_name = _get_display_name(acc_unique_id)
        icon, status_text = _get_auth_status_details(acc_unique_id)        
        account_info = f"""[{i}] 账号信息
🤪 账号: {display_name}
☁ 授权: {icon} {status_text}"""
        account_display_parts.append(account_info)
        account_display_parts.append("------------------")
    account_display_parts.extend(["回复数字选择", "回复'q'退出", "=================="])
    account_list_msg = "\n".join(account_display_parts)
    sender.reply(account_list_msg)
    choice_str = sender.input(60000, 0, False)
    if not choice_str:
        sender.reply("❌ 输入超时")
        return
    if choice_str.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    try:
        choice_idx = int(choice_str) - 1
        if not (0 <= choice_idx < len(user_accounts_list)):
            raise ValueError("选择超出范围")        
        selected_acc_id = user_accounts_list[choice_idx]
        if not check_account_authorization(selected_acc_id):
            display_name = _get_display_name(selected_acc_id)
            sender.reply(f"""=====兑换失败=====
🤪 账号: {display_name}
❌ 原因: 未授权或授权已过期
==================""")
            return            
        show_exchange_products(sender, userid, user_config, selected_acc_id)
    except ValueError:
        sender.reply("❌ 无效的选择")
def manage_exchange_mibaob(sender, userid, user_config):
    user_accounts_list = eval(middleware.bucketGet(f'{bucket_prefix}_user_accounts', userid) or '[]')
    if not user_accounts_list:
        sender.reply(f"""=====未绑定账号=====
❌ 未找到任何账号信息
💡 发送 "{user_config['login_cmd']}" 绑定账号
==================""")
        return
    first_acc_id = user_accounts_list[0]
    if not check_account_authorization(first_acc_id):
        display_name = _get_display_name(first_acc_id)
        sender.reply(f"""=====兑换失败=====
🤪 账号: {display_name}
❌ 原因: 未授权或授权已过期
==================""")
        return
    show_exchange_products(sender, userid, user_config, first_acc_id)
def show_exchange_products(sender, userid, user_config, acc_unique_id):
    display_name = _get_display_name(acc_unique_id)    
    service_token_ck = middleware.bucketGet(f'{bucket_prefix}_token2', acc_unique_id)
    pass_token_ck = middleware.bucketGet(f'{bucket_prefix}_token', acc_unique_id)    
    if not service_token_ck and not pass_token_ck:
        sender.reply(f"""=====兑换失败=====
🤪 账号: {display_name}
❌ 原因: CK失效，请重新登录
==================""")
        return    
    original_phone = middleware.bucketGet(f'{bucket_prefix}_phone_id', acc_unique_id) or "未知"
    mibao_instance = MiBao(acc_unique_id,
                          user_id_pass_token_phone_str=pass_token_ck,
                          user_id_service_token_str=service_token_ck,
                          phone_display_override=original_phone)    
    ck_valid, ck_msg = mibao_instance.check_ck_validity()
    if not ck_valid:
        sender.reply(f"""=====兑换失败=====
🤪 账号: {display_name}
❌ 原因: {ck_msg}
==================""")
        return
    updated_service_token_ck = middleware.bucketGet(f'{bucket_prefix}_token2', acc_unique_id)    
    exchanger = MiWalletExchanger(updated_service_token_ck or service_token_ck, acc_unique_id, mibao_instance.rnl_instance.session_tid, mibao_instance.rnl_instance.device_params)
    balance_ok, balance_info = exchanger.get_balance()
    if not balance_ok:
        sender.reply(f"""=====兑换失败=====
🤪 账号: {display_name}
❌ 原因: {balance_info}
==================""")
        return    
    products_ok, products_list = exchanger.get_direct_exchange_products()
    if not products_ok or not products_list:
        sender.reply(f"""=====兑换失败=====
🤪 账号: {display_name}
❌ 原因: 获取权益列表失败或暂无可兑换权益
==================""")
        return
    product_display_list = []
    for i, product in enumerate(products_list, 1):
        prize_name = product.get('prizeName', '')
        need_gold_rice = product.get('needGoldRice', 0)
        stock_status = product.get('stockStatus', 0)
        today_stock_status = product.get('todayStockStatus', 0)        
        if stock_status == 1 and today_stock_status == 1:
            stock_icon = "✅"
        else:
            stock_icon = "❌"        
        cost_days = need_gold_rice / 100
        product_display_list.append(f"[{i}] {prize_name}\n    {stock_icon} 消耗{cost_days:.0f}天时长")    
    current_exchange_prize = middleware.bucketGet(f'{bucket_prefix}_exchange', acc_unique_id)
    exchange_status = f"🎫 抢兑权益: {current_exchange_prize}" if current_exchange_prize else "🎫 抢兑权益: 暂未提交"
    
    products_msg = f"""=====小米兑换=====
🤪 账号: {display_name}
💰 当前时长: {balance_info}天
{exchange_status}
------------------
{chr(10).join(product_display_list)}
------------------
+序号=提交抢兑, d=删除抢兑
单序号=立即兑换, q=退出操作
=================="""    
    sender.reply(products_msg)    
    choice_str = sender.input(60000, 0, False)
    if not choice_str:
        sender.reply("❌ 输入超时")
        return
    if choice_str.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return    
    if choice_str.lower() == 'd':
        try:
            middleware.bucketDel(f'{bucket_prefix}_exchange', acc_unique_id)
        except Exception:
            pass
        try:
            middleware.bucketDel(f'{bucket_prefix}_exchange_phone', acc_unique_id)
        except Exception:
            pass
        sender.reply("✅ 已删除抢兑权益")
        return    
    if choice_str.startswith('+'):
        try:
            choice_idx = int(choice_str[1:]) - 1
            if not (0 <= choice_idx < len(products_list)):
                raise ValueError("选择超出范围")            
            selected_product = products_list[choice_idx]
            submit_exchange_request(sender, userid, user_config, acc_unique_id, selected_product, display_name)
            return
        except ValueError:
            sender.reply("❌ 无效的选择")
            return    
    try:
        choice_idx = int(choice_str) - 1
        if not (0 <= choice_idx < len(products_list)):
            raise ValueError("选择超出范围")        
        selected_product = products_list[choice_idx]
        confirm_exchange(sender, userid, user_config, acc_unique_id, exchanger, selected_product, balance_info)
    except ValueError:
        sender.reply("❌ 无效的选择")
def submit_exchange_request(sender, userid, user_config, acc_unique_id, product, display_name):
    prize_name = product.get('prizeName', '')    
    sender.reply(f"""=====确认提交1/2=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
------------------
请输入抢兑到账手机号
回复"q"退出操作
==================""")    
    phone1 = sender.input(60000, 1, False)
    if not phone1:
        sender.reply("❌ 输入超时")
        return
    if phone1.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    if not re.match(r'^1[3-9]\d{9}$', phone1):
        sender.reply(f"""=====提交失败=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
❌ 原因: 手机号格式不正确
==================""")
        return
    sender.reply(f"""=====确认提交2/2=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
------------------
请再次输入抢兑到账手机号
回复"q"退出操作
==================""")    
    phone2 = sender.input(60000, 1, False)
    if not phone2:
        sender.reply("❌ 输入超时")
        return
    if phone2.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    if phone1 != phone2:
        sender.reply(f"""=====提交失败=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
❌ 原因: 两次输入的手机号不一致
==================""")
        return
    existing_exchange = middleware.bucketGet(f'{bucket_prefix}_exchange', acc_unique_id)
    middleware.bucketSet(f'{bucket_prefix}_exchange', acc_unique_id, prize_name)
    middleware.bucketSet(f'{bucket_prefix}_exchange_phone', acc_unique_id, phone1)    
    if existing_exchange:
        sender.reply(f"""=====更新提交=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
==================""")
    else:
        sender.reply(f"""=====提交成功=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
==================""")
def confirm_exchange(sender, userid, user_config, acc_unique_id, exchanger, product, current_balance):
    display_name = _get_display_name(acc_unique_id)
    prize_name = product.get('prizeName', '')
    prize_code = product.get('prizeCode', '')
    need_gold_rice = product.get('needGoldRice', 0)
    cost_days = need_gold_rice / 100    
    stock_status = product.get('stockStatus', 0)
    today_stock_status = product.get('todayStockStatus', 0)
    if stock_status != 1 or today_stock_status != 1:
        sender.reply(f"""=====兑换失败=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
❌ 原因: 权益无库存，无法兑换
==================""")
        return
    if current_balance < cost_days:
        sender.reply(f"""=====兑换失败=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
❌ 原因: 时长不足
💰 需要: {cost_days:.0f}天
💰 当前: {current_balance}天
==================""")
        return
    target_phone = None
    confirm_msg1 = f"""=====确认兑换1/2=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
📛 消耗时长: {cost_days:.0f}天
💰 当前时长: {current_balance}天
------------------
请输入兑换到账手机号
回复"q"退出操作
=================="""        
    sender.reply(confirm_msg1)        
    phone1 = sender.input(60000, 1, False)
    if not phone1:
        sender.reply("❌ 输入超时")
        return
    if phone1.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return        
    phone1 = phone1.strip()
    if not re.match(r'^1[3-9]\d{9}$', phone1):
        sender.reply(f"""=====兑换失败=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
❌ 原因: 手机号格式不正确
==================""")
        return        
    confirm_msg2 = f"""=====确认兑换2/2=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
📛 消耗时长: {cost_days:.0f}天
💰 当前时长: {current_balance}天
------------------
请再次输入兑换到账手机号
回复"q"退出操作
=================="""        
    sender.reply(confirm_msg2)        
    phone2 = sender.input(60000, 1, False)
    if not phone2:
        sender.reply("❌ 输入超时")
        return
    if phone2.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return        
    phone2 = phone2.strip()        
    if phone1 != phone2:
        sender.reply(f"""=====兑换失败=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
❌ 原因: 两次输入的手机号不一致
==================""")
        return        
    target_phone = phone1   
    exchange_ok, exchange_msg, coupon_id = exchanger.exchange_product(prize_code, target_phone)
    if exchange_ok:
        success_msg = f"""=====兑换成功=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
✅ 结果: {exchange_msg}
======================"""
        sender.reply(success_msg)
    else:
        fail_msg = f"""=====兑换失败=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
❌ 原因: {exchange_msg}
=================="""
        sender.reply(fail_msg)
def handle_xiaomi_yijian_qiangdui():
    global STOP_EXCHANGE
    sender = middleware.Sender(middleware.getSenderID())
    if not sender.isAdmin():
        sender.reply("❌ 需要管理员权限")
        return
    STOP_EXCHANGE = False
    if not within_exchange_window():
        sender.reply("❌ 当前时间不在0,10点前后10分钟内，无法执行小米抢兑操作")
        return
    user_config = get_config()
    now = local_now()
    t0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    t9 = now.replace(hour=9, minute=0, second=0, microsecond=0)
    t10 = now.replace(hour=10, minute=0, second=0, microsecond=0)
    if now.hour >= 23:
        target_time = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        diffs = {
            abs((now - t0).total_seconds()): t0,
            abs((now - t9).total_seconds()): t9,
            abs((now - t10).total_seconds()): t10
        }
        target_time = diffs[min(diffs.keys())]
    all_exchange_keys = middleware.bucketAllKeys(f'{bucket_prefix}_exchange')
    if not all_exchange_keys:
        sender.reply("❌ 暂无账号提交抢兑")
        return
    owner_map = {}
    all_users = middleware.bucketAllKeys(f'{bucket_prefix}_user_accounts')
    for u in all_users:
        acc_list = eval(middleware.bucketGet(f'{bucket_prefix}_user_accounts', u) or '[]')
        for ac in acc_list:
            owner_map[ac] = u
    concurrency_data = []
    fail_reasons = []
    cleaned_invalid_accounts = 0
    for acc_id in all_exchange_keys:
        if STOP_EXCHANGE:
            sender.reply("❌ 抢兑已被手动停止")
            return
        prize_name = middleware.bucketGet(f'{bucket_prefix}_exchange', acc_id)
        target_phone = middleware.bucketGet(f'{bucket_prefix}_exchange_phone', acc_id)
        if not prize_name or not target_phone:
            try:
                middleware.bucketDel(f'{bucket_prefix}_exchange', acc_id)
            except Exception:
                pass
            try:
                middleware.bucketDel(f'{bucket_prefix}_exchange_phone', acc_id)
            except Exception:
                pass
            cleaned_invalid_accounts += 1
            continue
        if acc_id not in owner_map:
            try:
                middleware.bucketDel(f'{bucket_prefix}_exchange', acc_id)
            except Exception:
                pass
            try:
                middleware.bucketDel(f'{bucket_prefix}_exchange_phone', acc_id)
            except Exception:
                pass
            cleaned_invalid_accounts += 1
            continue
        display_name = _get_display_name(acc_id)
        if not check_account_authorization(acc_id):
            if display_name == "未知号码":
                try:
                    middleware.bucketDel(f'{bucket_prefix}_exchange', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel(f'{bucket_prefix}_exchange_phone', acc_id)
                except Exception:
                    pass
                cleaned_invalid_accounts += 1
                continue
            else:
                fail_reasons.append(f"【{display_name}】授权已过期")
                continue
        service_token_ck = middleware.bucketGet(f'{bucket_prefix}_token2', acc_id)
        pass_token_ck = middleware.bucketGet(f'{bucket_prefix}_token', acc_id)
        if not service_token_ck and not pass_token_ck:
            fail_reasons.append(f"【{display_name}】无CK或已失效")
            continue
        original_phone = middleware.bucketGet(f'{bucket_prefix}_phone_id', acc_id) or "未知"
        mibao_instance = MiBao(acc_id,
                              user_id_pass_token_phone_str=pass_token_ck,
                              user_id_service_token_str=service_token_ck,
                              phone_display_override=original_phone)
        ck_valid, ck_msg = mibao_instance.check_ck_validity()
        if not ck_valid:
            fail_reasons.append(f"【{display_name}】{ck_msg}")
            continue
        updated_service_token_ck = middleware.bucketGet(f'{bucket_prefix}_token2', acc_id)
        exchanger = MiWalletExchanger(updated_service_token_ck or service_token_ck, acc_id, mibao_instance.rnl_instance.session_tid, mibao_instance.rnl_instance.device_params)
        balance_ok, balance_info = exchanger.get_balance()
        if not balance_ok:
            fail_reasons.append(f"【{display_name}】{balance_info}")
            continue
        products_ok, products_list = exchanger.get_direct_exchange_products()
        if not products_ok or not products_list:
            fail_reasons.append(f"【{display_name}】获取权益列表失败")
            continue
        found_product = None
        for product in products_list:
            if product.get('prizeName') == prize_name:
                found_product = product
                break
        if not found_product:
            fail_reasons.append(f"【{display_name}】未找到权益 {prize_name}")
            continue
        need_gold_rice = found_product.get('needGoldRice', 0)
        cost_days = need_gold_rice / 100
        if balance_info < cost_days:
            fail_reasons.append(f"【{display_name}】时长不足 ({balance_info}/{cost_days})")
            continue
        user_id = owner_map.get(acc_id)
        concurrency_data.append((display_name, prize_name, found_product.get('prizeCode'), target_phone, exchanger, user_id, acc_id))
    if not concurrency_data and not fail_reasons:
        sender.reply("❌ 没有满足条件的抢兑账号")
        return
    now_str = local_now().strftime('%Y-%m-%d %H:%M:%S')
    notice = f"""=====小米抢兑提醒=====
🧭 当前时间: {now_str}
📋 抢兑账号: {len(concurrency_data)}个
🏖️ 抢兑时间: {target_time.strftime('%H:%M:%S')}
=================="""
    sender.reply(notice)
    if fail_reasons:
        safe_reply(sender, "以下账号不满足抢兑条件：\n" + "\n".join(fail_reasons))
    if not concurrency_data:
        sender.reply("✅ 无可执行抢兑的账号")
        return
    diff = (target_time - local_now()).total_seconds()
    if diff > 0:
        time.sleep(diff)
    if STOP_EXCHANGE:
        sender.reply("❌ 抢兑已被手动停止")
        return
    from concurrent.futures import ThreadPoolExecutor, as_completed
    def real_exchange(display_name, prize_name, prize_code, target_phone, exchanger, user_id, acc_id):
        for attempt in range(1, 31):
            if STOP_EXCHANGE:
                return (display_name, prize_name, False, "已被手动停止", user_id, acc_id, None)
            success, msg, coupon_id = exchanger.exchange_product(prize_code, target_phone)
            if success:
                return (display_name, prize_name, True, f"兑换成功(第{attempt}次)", user_id, acc_id, coupon_id)
            else:
                if "您的账号存在安全风险" in msg or "已抢完" in msg:
                    return (display_name, prize_name, False, msg, user_id, acc_id, None)
                if attempt < 30:
                    time.sleep(0.02)
        return (display_name, prize_name, False, msg, user_id, acc_id, None)
    qiangdui_bingfa = user_config['qiangdui_bingfa']
    futures_map = {}
    with ThreadPoolExecutor(max_workers=qiangdui_bingfa) as exe:
        for (dn, pn, pc, tp, ex, uid, acid) in concurrency_data:
            fut = exe.submit(real_exchange, dn, pn, pc, tp, ex, uid, acid)
            futures_map[fut] = dn
        results = []
        for fut in as_completed(futures_map):
            results.append(fut.result())
    succ_count = sum(1 for r in results if r[2] is True)
    fail_count = sum(1 for r in results if r[2] is False)
    total_count = succ_count + fail_count
    fail_msgs = [
        f"🤪 账号: {r[0]}\n🎫 权益: {r[1]}\n🪁 结果: {r[3]}"
        for r in results if not r[2]
    ]
    detail_fail = "\n".join(fail_msgs) if fail_msgs else ""
    final_msg = f"""=====抢兑结果统计=====
✨ 总抢兑数: {total_count}
✅ 抢兑成功: {succ_count}
❌ 抢兑失败: {fail_count}
------------------
📝 失败详情:
{detail_fail if detail_fail else '无'}
=================="""
    safe_reply(sender, final_msg)
    for result in results:
        display_name, prize_name, ok, reason, user_id, acc_id, coupon_id = result
        if ok is True:
            try:
                middleware.bucketDel(f'{bucket_prefix}_exchange', acc_id)
            except Exception:
                pass
            try:
                middleware.bucketDel(f'{bucket_prefix}_exchange_phone', acc_id)
            except Exception:
                pass
        if user_id:
            status_str = "成功" if ok else reason
            push_text = f"""=====抢兑结果=====
🤪 账号: {display_name}
🎫 权益: {prize_name}
🪁 结果：{status_str}
=================="""
            push_message_to_user(user_id, push_text)
            
# [新增辅助函数] 获取动态 S_TOKEN，包含缓存读取、云端获取、重试机制
def _get_dynamic_s_token(sender, force_refresh=False, banned_token=None):
    # ================= 配置区域 =================
    # 请在此处填写你的 PHP 接口地址
    S_TOKEN_PHP_API = "http://yuhualhh.250666.xyz/api/stoken.php"
    
    bucket_key = f'{bucket_prefix}_s_token_cache'
    
    if not force_refresh:
        cached_token = middleware.bucketGet(bucket_prefix, 's_token_cache')
        if cached_token:
            return True, cached_token

    fetched_token = None
    for i in range(3):
        try:
            res = requests.get(S_TOKEN_PHP_API, timeout=10, verify=False)
            if res.status_code == 200:
                data = res.json()
                if data.get('code') == 200 and data.get('token'):
                    fetched_token = data.get('token').strip()
                    break
        except Exception:
            time.sleep(1)
            continue
    
    if not fetched_token:
        return False, "无法连接Token服务器，请稍后重试"

    # 3. 校验逻辑：如果云端Token与当前失效的Token一致
    if banned_token and fetched_token == banned_token:
        return False, "请联系插件开发者更新Token"

    middleware.bucketSet(bucket_prefix, 's_token_cache', fetched_token)
    return True, fetched_token

def sms_login_mibao(sender, userid, user_config):
    # 获取初始 S_TOKEN
    success, s_token_val = _get_dynamic_s_token(sender, force_refresh=False)
    if not success:
        sender.reply(f"❌ {s_token_val}")
        return

    APP_ID = "2021004156646923"
    SID = "micar_alipaylite"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Linux; U; Android 13; zh-CN; M2012K11AC Build/TKQ1.221114.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.6478.122 MYWeb/1.3.126.250916150540 UWS/3.22.2.9999 UCBS/3.22.2.9999_220000000000 Safari/537.36 NebulaSDK/1.8.100112 Nebula AlipayDefined(nt:WIFI,ws:800|0|2.5,ac:sp) AliApp(AP/10.7.86.8000) AlipayClient/10.7.86.8000 Language/zh-Hans isConcaveScreen/false Region/CNAriver/10.7.86.8000 ChannelId(12) DTN/2.0',
        'x-release-type': 'ONLINE',
        'referer': 'https://2021004156646923.hybrid.alipay-eco.com/'
    }
    sender.reply("""=====短信登录=====
请输入您的手机号
------------------
请在60秒内完成
回复"q"退出""")
    phone_number = sender.input(60000, 1, False)
    if not phone_number:
        sender.reply("❌ 输入超时")
        return
    if str(phone_number).lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    phone_number = str(phone_number).strip()
    if not re.match(r'^1[3-9]\d{9}$', phone_number):
        sender.reply("❌ 手机号格式不正确")
        return
    session = requests.Session()
    session.headers.update(HEADERS)
    send_ticket_url = "https://account.xiaomi.com/pass/sns/ali/sendTicket"
        
    def _do_send_ticket(token_to_use):
        send_ticket_data = {
            "_locale": "zh_CN",
            "appid": APP_ID,
            "phone": phone_number,
            "sToken": token_to_use,
            "sid": SID
        }
        return requests_with_retry(session, 'post', send_ticket_url, data=send_ticket_data)

    try:
        response_send = _do_send_ticket(s_token_val)
        result_send_text = response_send.text.replace("&&&START&&&", "")
        result_send = json.loads(result_send_text)
        response_code = result_send.get("code")
        if response_code in [21327, 10031]: 
            success, new_token = _get_dynamic_s_token(sender, force_refresh=True, banned_token=s_token_val)
            if not success:
                sender.reply(f"❌ {new_token}")
                return
            s_token_val = new_token
            response_send = _do_send_ticket(s_token_val)
            result_send_text = response_send.text.replace("&&&START&&&", "")
            result_send = json.loads(result_send_text)
            response_code = result_send.get("code")

        if response_code == 70022:
            sender.reply("❌ 登录失败: 验证码发送过多，请明天再试")
            return

        if response_code != 0:
            error_msg = result_send.get("desc")           
            sender.reply(f"❌ 登录失败: {error_msg}")
            return
    except Exception as e:
        sender.reply(f"❌ 请求验证码时网络异常")
        return
    sender.reply("""=====短信登录=====
请输入短信验证码
------------------
请在120秒内完成
回复"q"退出""")
    ticket = sender.input(120000, 1, False)
    if not ticket:
        sender.reply("❌ 输入超时")
        return
    if str(ticket).lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    ticket = str(ticket).strip()
    if not ticket.isdigit() or len(ticket) != 6:
        sender.reply("❌ 验证码格式不正确，请输入6位数字")
        return
    ticket_login_url = "https://account.xiaomi.com/pass/sns/ali/v3/ticketLogin"
    
    def _do_ticket_login(token_to_use):
        ticket_login_data = {
            "_locale": "zh_CN",
            "appid": APP_ID,
            "authType": 1,
            "force_bind": "false",
            "phone": phone_number,
            "policyName": "miaccount",
            "sToken": token_to_use,
            "serviceTokenValidTime": 2592000,
            "sid": SID,
            "ticket": ticket
        }
        return requests_with_retry(session, 'post', ticket_login_url, data=ticket_login_data)

    try:
        response_login = _do_ticket_login(s_token_val)
        result_login_text = response_login.text.replace("&&&START&&&", "")
        result_login = json.loads(result_login_text)
        response_code_login = result_login.get("code")
        if response_code_login in [21327, 10031]:
            success, new_token = _get_dynamic_s_token(sender, force_refresh=True, banned_token=s_token_val)
            if not success:
                sender.reply(f"❌ {new_token}")
                return
            s_token_val = new_token
            response_login = _do_ticket_login(s_token_val)
            result_login_text = response_login.text.replace("&&&START&&&", "")
            result_login = json.loads(result_login_text)
            response_code_login = result_login.get("code")

        if response_code_login == 0:
            sender.reply("正在处理账号信息...")
            uid = result_login.get('userId')
            pt = result_login.get('passToken')
            cuid = result_login.get('cUserId')
            if not all([uid, pt, cuid]):
                sender.reply("❌ 登录成功，但响应中缺少关键凭证")
                return
            ck_string = f"userId={uid};passToken={pt};cUserId={cuid};"
            _cookie_login_inner(sender, userid, user_config, ck_string, phone_override=str(uid))
        # elif response_code_login in [70007, 70014]:
            # sender.reply("❌ 验证码错误或已失效")
            # return
        else:
            error_msg = result_login.get("desc", "未知错误")
            sender.reply(f"❌ 登录失败: {error_msg}")
            return
    except Exception as e:
        sender.reply(f"❌ 登录时网络异常")
        return
def clean_json_response(text):
    prefix = '&&&START&&&'
    if text.startswith(prefix):
        return text[len(prefix):]
    return text        
def pwd_login_mibao(sender, userid, user_config):
    # 获取初始 S_TOKEN
    success, s_token_val = _get_dynamic_s_token(sender, force_refresh=False)
    if not success:
        sender.reply(f"❌ {s_token_val}")
        return

    APP_ID = "2021004156646923"
    SID = "micar_alipaylite"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Linux; U; Android 13; zh-CN; M2012K11AC Build/TKQ1.221114.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.6478.122 MYWeb/1.3.126.250916150540 UWS/3.22.2.9999 UCBS/3.22.2.9999_220000000000 Safari/537.36 NebulaSDK/1.8.100112 Nebula AlipayDefined(nt:WIFI,ws:800|0|2.5,ac:sp) AliApp(AP/10.7.86.8000) AlipayClient/10.7.86.8000 Language/zh-Hans isConcaveScreen/false Region/CNAriver/10.7.86.8000 ChannelId(12) DTN/2.0',
        'x-release-type': 'ONLINE',
        'referer': 'https://2021004156646923.hybrid.alipay-eco.com/'
    }
    sender.reply("""=====账密登录=====
请输入您的小米账号
------------------
请在60秒内完成
回复"q"退出""")
    username = sender.input(60000, 1, False)
    if not username:
        sender.reply("❌ 输入超时")
        return
    if str(username).lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    username = str(username).strip()
    sender.reply("""=====账密登录=====
请输入您的账号密码
------------------
请在60秒内完成
回复"q"退出""")
    password = sender.input(60000, 1, False)
    if not password:
        sender.reply("❌ 输入超时")
        return
    if str(password).lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    password = str(password).strip()
    session = requests.Session()
    session.headers.update(HEADERS)
    password_hash = hashlib.md5(password.encode('utf-8')).hexdigest().upper()
    login_url = "https://account.xiaomi.com/pass/sns/ali/v3/pwdLogin"
    
    def _do_pwd_login(token_to_use):
        login_data = {
            "_locale": "zh_CN",
            "appid": APP_ID,
            "authType": 1,
            "force_bind": "false",
            "hash": password_hash,
            "policyName": "miaccount",
            "sToken": token_to_use,
            "serviceTokenValidTime": 2592000,
            "sid": SID,
            "user": username
        }
        return session.post(login_url, data=login_data)

    try:
        sender.reply("正在登录...")
        response = _do_pwd_login(s_token_val)
        response.raise_for_status()
        result = json.loads(clean_json_response(response.text))
        
        if result.get("code") in [21327, 10031]:
            success, new_token = _get_dynamic_s_token(sender, force_refresh=True, banned_token=s_token_val)
            if not success:
                sender.reply(f"❌ {new_token}")
                return
            s_token_val = new_token
            # 重试登录
            response = _do_pwd_login(s_token_val)
            response.raise_for_status()
            result = json.loads(clean_json_response(response.text))

        if result.get("code") == 0:
            pass_token = result.get("passToken")
            user_id = result.get("userId")
            c_user_id = result.get("cUserId")
            if not all([pass_token, user_id, c_user_id]):
                 sender.reply("❌ 登录失败: 响应中缺少关键凭证")
                 return
            output_string = f"userId={user_id};passToken={pass_token};cUserId={c_user_id};"
            _cookie_login_inner(sender, userid, user_config, output_string, phone_override=str(user_id))
        else:
            error_code = result.get('code')
            error_desc = result.get('desc', '未知错误')
            # if error_code == 70016:
                # error_desc = "账号或密码错误"
            # elif error_code == 20003:
                # error_desc = "用户不存在"
            # elif error_code == 350008:
                # error_desc = "账号已注销"
            sender.reply(f"❌ 登录失败: {error_desc}")
            return
    except requests.exceptions.RequestException as e:
        sender.reply(f"❌ 登录时网络请求失败")
        return
def main():
    sender = middleware.Sender(middleware.getSenderID())
    userid = sender.getUserID()
    user_config = get_config()
    if not check_maintenance_page():
        sender.reply("❌ 服务端无法连通, 插件停止运行")
        return
    message = sender.getMessage().strip()
    command_core = ""
    if message.startswith("小米") or message.startswith("米包"):
        command_core = message[2:]
    if command_core == "登录":
        #cookie_login_mibao(sender, userid, user_config)
        login_mibaob(sender, userid, user_config)
    elif command_core == "查询":
        query_mibaob(sender, userid, user_config)
    elif command_core == "管理":
        manage_mibaob(sender, userid, user_config)
    elif command_core == "清理":
        clean_expired_or_invalid_mibaob(sender, user_config)
    elif command_core == "授权":
        admin_auth_mibaob(sender, user_config)
    elif command_core == "检测":
        admin_detect_all_accounts(sender, user_config)
    elif command_core == "运行":
        run_xiaomi_tasks_for_user(sender, userid, user_config)
    elif command_core == "一键运行":
        admin_run_all_xiaomi_tasks(sender, user_config)
    elif command_core == "兑换":
        exchange_mibaob(sender, userid, user_config)
    elif command_core == "一键抢兑":
        handle_xiaomi_yijian_qiangdui()
    else:
        sender.setContinue()
if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except Exception as e:
        try:
            temp_sender = middleware.Sender(middleware.getSenderID())
            if temp_sender:
                temp_sender.reply(f"❌ {scripts_name}插件发生内部错误: {str(e)[:100]}")
        except:
            pass
        import traceback
        traceback.print_exc()
    finally:
        pass
