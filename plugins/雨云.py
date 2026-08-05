# [title: 雨云]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@0d28f1a9cc71d7269440d5f1eb40f40df08689da/2026/01/31/2a7606203ed51989a1bc2887c5a9489d.png]
# [language: python]
# [rule: ^(雨云)(登录|查询|管理|清理|授权|检测|运行|一键运行)$]
# [disable:false]
# [open_source: false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [priority: 9999999999999999999]
# [public: true]
# [version: 1.0.4]
# [price: 0]
# [author: yuhualhh]
# [service: ]
# [description: ❶雨云内置任务插件，自动完成每日签到任务，支持账密登录、管理、查询、授权、检测授权过期以及账密错误推送等功能<br>❷部分功能的实现需自行添加计划任务伪装管理员定时，了解如何添加计划任务请看移动云盘插件介绍，关于指令『雨云检测』与『雨云清理』定时『30 18 * * *』，关于指令『雨云一键运行』定时『0 7,19 * * *』]

# [param: {"required":false,"key":"yuhua_yuyun.captcha_api","bool":false,"placeholder":"","name":"打码接口","desc":"自定义腾讯图形点选验证打码接口，不填则默认使用内置接口"}
# [param: {"required":false,"key":"yuhua_yuyun.invite_url","bool":false,"placeholder":"https://www.rainyun.com/MzU4OTE=_","name":"推广链接","desc":"雨云推广链接"}]
# [param: {"required":true,"key":"yuhua_yuyun.zsm","bool":false,"placeholder":"","name":"收款码子","desc":"微信Bot收款码直链"}]
# [param: {"required":true,"key":"yuhua_yuyun.price","bool":false,"placeholder":"","name":"收费价格","desc":"不填默认0元，单位: 元/月"}]
# [param: {"required":true,"key":"yuhua_yuyun.bingfa","bool":false,"placeholder":"","name":"并发数量","desc":"不填默认5"}]
# [param: {"required":false,"key":"yuhua_yuyun.push_status","bool":true,"placeholder":"","name":"推送状态","desc":"是否将雨云一键运行结果推送给用户"}]
# [param: {"required":false,"key":"yuhua_yuyun.debug_pwd","bool":false,"placeholder":"","name":"调试模式","desc":"非插件开发者无需理会"}]

import re
import time
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

# 封装函数：支持颜色分级(INFO=绿, WARN=黄, 其他=红)，输出到stderr确保控制台可见
def printf(msg,level='INFO'):
    c=32 if level in['INFO','DEBUG']else 33 if level in['WARN','WARNING']else 31;sys.stderr.write(f"\033[{c}m[{level}] {str(msg)}\033[0m\n");sys.stderr.flush()

# --- 性能与容错 ---
# 全局网络超时（秒）
GLOBAL_TIMEOUT = 45
# ddddocr 服务地址
DDDDOCR_HOST = "http://ddddocr.250666.xyz"

#输出日志
debug_key = middleware.bucketGet('yuhua_yuyun', 'debug_pwd') or ''
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

def account_login_interaction():
    """
    【雨云登录功能】
    账号密码登录
    """
    
    sender.reply(f"""
=====雨云登录=====
❶请扫码访问官网注册账号
❷请输入用户名/手机/邮箱
------------------
请在10分钟内完成
回复"q"退出""")
 
    # === 新增：推广链接逻辑 (本地模块版) ===
    invite_url = middleware.bucketGet('yuhua_yuyun', 'invite_url') or 'https://www.rainyun.com/MzU4OTE=_'
    
    try:
        # 尝试导入 qrcode 库，需要在环境安装: pip install qrcode[pil]
        import qrcode
        from io import BytesIO
        
        # 创建二维码对象
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(invite_url)
        qr.make(fit=True)
        
        # 生成图片并存入内存
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf)
        
        # 转为 Base64 字符串
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        
        # 发送 Base64 图片 (大多数框架支持 base64:// 前缀)
        sender.replyImage("base64://" + img_b64)
        
    except ImportError:
        sender.reply("❌ 错误: 未安装qrcode库")
        # 这里可以选择回退发送纯文本链接
        sender.reply(f"🔗 雨云官网: {invite_url}")
    except Exception as e:
        sender.reply(f"❌ 生成二维码失败: {str(e)}")
    # ========================           
    
    account_input = sender.input(600000, 1, False)
    if not account_input or account_input.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return
    
    sender.reply(f"""
=====雨云登录=====
请输入登录密码
------------------
请在60秒内完成
回复"q"退出""")
    
    pwd_input = sender.input(60000, 1, False)
    if not pwd_input or pwd_input.lower() == 'q':
        sender.reply("✅ 已退出操作")
        return

    # 简单的本地校验 (可选)
    if len(pwd_input.strip()) < 6:
        sender.reply("❌ 登录失败: 密码必须至少有6个字符")
        # 这里不强制退出，依然尝试请求，万一有短密码
    
    sender.reply("正在登录...")
    
    # 初始化空HSH进行登录尝试
    hsh = HSH(token="", uid=None)
    # 使用修复后的 perform_login
    login_ok, data = hsh.perform_login(account_input.strip(), pwd_input.strip())
    
    if login_ok:
        process_login_success(data, account_input.strip(), pwd_input.strip())
    else:
        # 这里现在会显示 "用户名或密码错误..." 而不是 "HTTP 400"
        sender.reply(f"❌ 登录失败: {data}")

def process_login_success(token_data, username, password):
    """处理登录成功后的逻辑（保存凭证与密码）"""
    try:
        # token_data 是一个包含 cookie 和 csrf 的字典
        token_str = json.dumps(token_data)
        
        # 初始化API类
        hsh = HSH(token_str)
        info_ok, info_data = hsh.get_user_info()
        
        if not info_ok:
            sender.reply(f"❌ 登录失败: 无法获取用户信息")
            return
            
        # 雨云返回的 Name 或 Email
        user_display = info_data.get('name', '未知用户')
        uid_raw = str(info_data.get('uid', ''))
        
        # 账号处理逻辑
        accounts = eval(uservalue or '[]')
        
        # 判断是否已存在（通过UID）
        matched_uid = None
        if uid_raw in accounts:
            matched_uid = uid_raw
        
        final_uid = matched_uid if matched_uid else (uid_raw if uid_raw else gen_unique_id())
        
        # 保存核心数据：Token(Cookie+CSRF), 密码(用于重登), 账号名(用于重登), 显示名
        middleware.bucketSet('yuhua_yuyun_token', final_uid, token_str)
        middleware.bucketSet('yuhua_yuyun_pwd', final_uid, password) # 新增：保存密码
        middleware.bucketSet('yuhua_yuyun_acct', final_uid, username) # 新增：保存登录账号
        middleware.bucketSet('yuhua_yuyun_phone', final_uid, user_display) # 这里复用phone字段存显示名
        
        if matched_uid:
            mask_name = _mask_identifier(user_display)
            sender.reply(f"""
=====登录成功=====
🤪 账号: {mask_name}
✅ 状态: 更新成功
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")
        else:
            accounts.append(final_uid)
            middleware.bucketSet('yuhua_yuyun_user', userid, str(accounts))
            
            mask_name = _mask_identifier(user_display)
            sender.reply(f"""
=====登录成功=====
🤪 账号: {mask_name}
✅ 状态: 添加成功
------------------
发送"{manage_cmd}"管理账号
发送"{query_cmd}"查询账号""")

    except Exception as e:
        sender.reply(f"❌ 处理数据失败: {str(e)}")

def login():
    """账号登录菜单"""
    account_login_interaction()


def get_global_session():
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({
        'User-Agent': 'Android_ilife798_2.0.12',
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
                # 尝试解析JSON以便漂亮打印，否则打印文本
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

###################### 雨云核心类 (HSH) ######################
class HSH:
    def __init__(self, token, session=None, uid=None):
        self.session = session or requests.Session()
        self.uid = uid # 用于重登获取密码
        self.csrf_token = ""
        self.cookie = ""
        
        # 尝试解析Token (现在存储的是JSON字符串)
        try:
            if token and "{" in token:
                data = json.loads(token)
                self.csrf_token = data.get("csrf", "")
                self.cookie = data.get("cookie", "")
            else:
                self.cookie = token # 兼容旧格式或直接传入
        except:
            self.cookie = token

        # 配置固定请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Content-Type": "application/json",
            "Host": "api.v2.rainyun.com",
            "Origin": "https://app.rainyun.com",
            "Referer": "https://app.rainyun.com/",
            "X-CSRF-Token": self.csrf_token,
            "Cookie": self.cookie
        }
        self.base_url = "https://api.v2.rainyun.com"

    def _update_headers(self):
        self.headers["X-CSRF-Token"] = self.csrf_token
        self.headers["Cookie"] = self.cookie

    def _silent_relogin(self):
        """静默重登：包含3次重试保障机制"""
        if not self.uid: return False
        
        pwd = middleware.bucketGet('yuhua_yuyun_pwd', self.uid)
        acct = middleware.bucketGet('yuhua_yuyun_acct', self.uid)
        
        if not pwd or not acct:
            if DEBUG: printf(f"❌ [重登失败] 数据库缺账号/密码 (UID:{self.uid})", "WARN")
            return False
        
        # 增加业务层重试：最多尝试3次
        for attempt in range(3):
            if DEBUG: printf(f"🔄 正在执行静默重登: {acct} (第 {attempt+1}/3 次尝试)", "INFO")
            
            # 调用独立登录方法
            success, data = self.perform_login(acct, pwd)
            
            if success:
                self.csrf_token = data["csrf"]
                self.cookie = data["cookie"]
                self._update_headers()
                
                token_str = json.dumps(data)
                middleware.bucketSet('yuhua_yuyun_token', self.uid, token_str)
                if DEBUG: printf("✅ 静默重登成功，凭证已刷新", "INFO")
                return True
            else:
                if DEBUG: printf(f"⚠️ 第 {attempt+1} 次重登失败: {data}", "WARN")
                if attempt < 2: time.sleep(2) # 失败等待
        
        if DEBUG: printf("❌ 静默重登彻底失败", "WARN")
        return False
        

    def _send_request(self, method, url, **kwargs):
        """发送请求并托管异常重试"""
        kwargs['session'] = self.session
        
        # 构造当前请求头
        req_headers = self.headers.copy()
        if 'headers' in kwargs:
            req_headers.update(kwargs['headers'])
            del kwargs['headers']
        
        # --- 第1次请求 ---
        res = None
        try:
            res = send_request_global(method, url, headers=req_headers, **kwargs)
        except Exception as e:
            if DEBUG: printf(f"⚠️ 请求网络异常: {e}", "WARN")

        # --- 判定是否需要重登 ---
        need_relogin = False
        
        if res is not None:
            # 1. 状态码判定 (403 是雨云最常见的Token过期码)
            if res.status_code in [401, 403]:
                need_relogin = True
                if DEBUG: printf(f"⚠️ [Auth] 捕获状态码 {res.status_code}，准备重登", "WARN")
            
            # 2. 业务码判定 (30002 = 需要登录)
            if not need_relogin:
                try:
                    d = res.json()
                    code = d.get("code")
                    msg = str(d.get("message", "")).lower()
                    if code == 30002 or "login" in msg or "session" in msg or "登录" in msg:
                        need_relogin = True
                        if DEBUG: printf(f"⚠️ [Auth] 捕获业务错 {code}/{msg}，准备重登", "WARN")
                except: pass

        # --- 执行重登与重试 ---
        if need_relogin:
            if self.uid:
                # 尝试重登
                if self._silent_relogin():
                    # 重登成功，使用新凭证构造Header
                    req_headers["X-CSRF-Token"] = self.csrf_token
                    req_headers["Cookie"] = self.cookie
                    
                    if DEBUG: printf("🚀 [Retry] 使用新凭证重发请求...", "INFO")
                    try:
                        # 第2次请求 (重试)
                        return send_request_global(method, url, headers=req_headers, **kwargs)
                    except: return None
            else:
                if DEBUG: printf("❌ 凭证失效但未绑定UID，无法重登", "WARN")
        
        return res
       

    def perform_login(self, username, password):
        """
        【完全独立的登录逻辑】
        创建一个全新的临时会话进行登录，支持自动处理滑块验证码
        """
        url = f"{self.base_url}/user/login"
        # 初始请求载荷
        payload = {"field": username, "password": password}
        
        # 1. 建立全新会话 (模拟首次登录)
        temp_session = requests.Session()
        temp_headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Content-Type": "application/json"
        }
        
        try:
            # 发起首次登录请求
            res = temp_session.post(url, json=payload, headers=temp_headers, timeout=20)
            
            # 解析响应
            res_data = {}
            try: res_data = res.json()
            except: pass

            # --- 新增：智能滑块验证处理逻辑 ---
            # 根据抓包分析，未传验证码时会返回 400 错误，code 为 10004
            if res.status_code == 400 and (res_data.get("code") == 10004 or "验证码" in str(res_data.get("message", ""))):
                if DEBUG: printf(f"⚠️ 登录触发滑块验证({username})，尝试获取票据...", "WARN")
                
                # 调用类中已有的验证码获取方法
                ticket, randstr = self.get_slide_verify()
                
                if ticket and randstr:
                    if DEBUG: printf("✅ 获取滑块票据成功，正在重试登录...", "INFO")
                    # 追加验证参数
                    payload["vticket"] = ticket
                    payload["vrandstr"] = randstr
                    # 发起第二次带票据的登录请求
                    res = temp_session.post(url, json=payload, headers=temp_headers, timeout=20)
                    try: res_data = res.json()
                    except: pass
                else:
                    return False, "触发滑块验证但获取票据失败"
            # -------------------------------

            if res.status_code == 200:
                raw_cookies = res.headers.get("Set-Cookie", "")
                
                # 2. 提取 CSRF
                csrf_val = ""
                csrf_match = re.search(r'X-CSRF-Token=([^;]+)', raw_cookies)
                if csrf_match:
                    csrf_val = csrf_match.group(1)
                
                # 3. 【关键修复】强制清洗 Cookie
                clean_cookie = raw_cookies # 兜底
                session_match = re.search(r'(rain-session=[^;]+)', raw_cookies)
                if session_match:
                    clean_cookie = session_match.group(1)
                
                if "rain-session" in clean_cookie:
                    return True, {"csrf": csrf_val, "cookie": clean_cookie}
                
                return False, res_data.get("message", "未获取到有效Session")
            else:
                return False, res_data.get("message", f"HTTP {res.status_code}")

        except Exception as e:
            return False, f"请求异常: {str(e)}"
        finally:
            # 销毁临时会话
            temp_session.close()

    def check_token(self):
        """检测Token有效性（通过获取用户信息）"""
        url = f"{self.base_url}/user/"
        res = self._send_request('GET', url)
        if not res: return False, "网络请求失败"
        
        try:
            data = res.json()
            if data.get('code') == 200 and data.get('data'):
                return True, "有效"
            else:
                # 这里的逻辑其实已经被 _send_request 中的重登覆盖了
                # 如果代码走到这，说明重登也没救回来，或者单纯的业务错误
                return False, data.get('message', '凭证失效且重登失败')
        except:
            return False, "解析响应失败"

    def get_user_info(self):
        """获取用户信息"""
        url = f"{self.base_url}/user/"
        res = self._send_request('GET', url)
        if not res: return False, {}
        
        try:
            data = res.json()
            if data.get('code') == 200:
                d = data.get('data', {})
                # 雨云 ID 是 int，统一转 str
                uid = str(d.get('ID', ''))
                # 修改优先级：手机 > 昵称 > 邮箱
                name_show = d.get('Phone') or d.get('Name') or d.get('Email')
                return True, {
                    "name": name_show,
                    "uid": uid,
                    "points": str(d.get('Points', 0))
                }
        except: pass
        return False, {}

    def get_today_score(self):
        """获取今日获取的积分"""
        # 计算今日零点时间戳
        today_start = int(time.mktime(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timetuple()))
        
        # 构造复杂的过滤器参数
        options = {
            "columnFilters": {"ID": ""},
            "sort": [],
            "page": 1,
            "perPage": 20,
            "timeFilters": {"Time": {"start": today_start}}
        }
        params_str = json.dumps(options)
        # 雨云 API 需要 encode
        url = f"{self.base_url}/user/logs?log_type=user%2F&options={urllib.parse.quote(params_str)}"
        
        res = self._send_request('GET', url)
        if not res: return "0"
        
        try:
            data = res.json()
            total_points = 0
            if data.get('code') == 200:
                records = data.get('data', {}).get('Records', [])
                for record in records:
                    if record.get('Type') and "获得" in record.get('Type') and record.get('Data'):
                        try:
                            d_obj = json.loads(record.get('Data'))
                            if 'Points' in d_obj:
                                total_points += int(d_obj['Points'])
                        except: pass
            return str(total_points)
        except: pass
        return "0"
        
    def query_assets(self):
        """聚合查询资产"""
        ok, info = self.get_user_info() # 这一步会触发自动重登
        today = self.get_today_score()
        
        return {
            "total_score": info.get('points', '0') if ok else "查询失败",
            "today_score": today,
            "valid": ok
        }

    def close(self):
        if self.session:
            self.session.close()
            self.session = None

    def get_slide_verify(self):
        try:
            captcha_api = (middleware.bucketGet('yuhua_yuyun', 'captcha_api') or '').strip()
            default_api = "https://txdx.wxtool.de5.net"
            base = captcha_api or default_api
            if "solve_captcha" in base:
                url = base
                sep = "&" if "?" in url else "?"
                if "aid=" not in url:
                    url = f"{url}{sep}aid=2039519451&type=1"
                elif "type=" not in url:
                    url = f"{url}{sep}type=1"
            else:
                base = base.rstrip("/")
                if "?" in base:
                    root, qs = base.split("?", 1)
                    url = f"{root}/solve_captcha?{qs}&aid=2039519451&type=1"
                else:
                    url = f"{base}/solve_captcha?aid=2039519451&type=1"
            headers = {}
            try:
                parsed = urllib.parse.urlparse(url)
                q = urllib.parse.parse_qs(parsed.query)
                token = (q.get("token") or [""])[0]
                if token:
                    headers["X-Token"] = token
            except Exception:
                pass
            log_url = re.sub(r'(?i)([?&]token=)[^&]*', r'\1***', url)
            if DEBUG:
                printf("\n===== [CAPTCHA REQUEST START] =====", "DEBUG")
                printf(f"METHOD: GET | URL: {log_url}", "DEBUG")
                printf(f"HEADERS: {json.dumps(headers or {}, ensure_ascii=False)}", "DEBUG")
                printf("TIMEOUT: 90", "DEBUG")
            t0 = time.time()
            res = requests.get(url, headers=headers or None, timeout=90)
            elapsed_ms = int((time.time() - t0) * 1000)
            if DEBUG:
                printf("----- [CAPTCHA RESPONSE] -----", "DEBUG")
                printf(f"STATUS: {res.status_code} | ELAPSED: {elapsed_ms}ms", "DEBUG")
                try:
                    body_preview = json.dumps(res.json(), ensure_ascii=False)
                except Exception:
                    body_preview = res.text or ""
                if len(body_preview) > 1000:
                    body_preview = body_preview[:1000] + "...(truncated)..."
                printf(f"RSP BODY: {body_preview}", "DEBUG")
            if res.status_code == 200:
                d = res.json()
                if d.get("code") == 200 and d.get("data"):
                    ticket = d["data"].get("ticket")
                    randstr = d["data"].get("randstr")
                    if DEBUG:
                        t_preview = (str(ticket)[:24] + "...") if ticket and len(str(ticket)) > 24 else ticket
                        printf(f"✅ 打码成功 ticket={t_preview} randstr={randstr}", "DEBUG")
                        printf("===== [CAPTCHA REQUEST END] =====\n", "DEBUG")
                    return ticket, randstr
                if DEBUG:
                    printf(f"⚠️ 打码业务失败 code={d.get('code')} msg={d.get('message') or d.get('msg')}", "WARN")
                    printf("===== [CAPTCHA REQUEST END] =====\n", "DEBUG")
            else:
                if DEBUG:
                    printf(f"⚠️ 打码HTTP失败 status={res.status_code}", "WARN")
                    printf("===== [CAPTCHA REQUEST END] =====\n", "DEBUG")
        except Exception as e:
            if DEBUG:
                printf(f"⚠️ 打码请求异常: {e}", "WARN")
                printf("===== [CAPTCHA REQUEST END] =====\n", "DEBUG")
        return "", ""

    def run_daily_tasks(self, phone_mask):
        """执行日常任务（仅每日签到）"""
        
        # 1. 检查任务状态
        sign_status = "❌ 未知"
        is_signed = False
        
        try:
            task_url = f"{self.base_url}/user/reward/tasks"
            res = self._send_request('GET', task_url)
            if res and res.json().get('code') == 200:
                tasks = res.json().get('data', [])
                for t in tasks:
                    if t.get('Name') == "每日签到":
                        if t.get('Status') == 2:
                            sign_status = "今日已签"
                            is_signed = True
                        break
        except: pass
        
        # 2. 如果未签到，执行签到
        if not is_signed:
            ticket, randstr = self.get_slide_verify()
            if not ticket:
                # 修改：主动抛出异常，利用外层的重试机制处理超时或失败
                raise Exception("尝试点选验证失败")
            else:
                try:
                    sign_url = f"{self.base_url}/user/reward/tasks"
                    payload = {
                        "task_name": "每日签到",
                        "verifyCode": "",
                        "vticket": ticket,
                        "vrandstr": randstr
                    }
                    # 允许 400 错误以便捕获业务信息
                    post_res = self._send_request('POST', sign_url, json=payload)
                    
                    if post_res:
                        d = post_res.json()
                        if d.get('code') == 200:
                            sign_status = "🎨 每日签到"
                            is_signed = True
                        else:
                            sign_status = f"❌ {d.get('message', '签到失败')}"
                    else:
                        sign_status = "❌ 请求失败"
                except Exception as e:
                    sign_status = f"❌ 异常: {str(e)}"
        else:
            sign_status = "🎨 每日签到 (无需重复)"

        # 构造结果
        count_str = "1/1" if is_signed else "0/1"
        
        final_msg = f"=====雨云运行结果=====\n🤪 账号: {phone_mask}\n💫 结果: 完成{count_str}\n------------------\n"
        final_msg += f"{sign_status}"
        final_msg += "\n======================="
        return final_msg
        

def gen_unique_id(prefix=""):
    timestamp = int(time.time() * 1_000_000)
    return f"{prefix}{timestamp}"

senderID = middleware.getSenderID()
sender = middleware.Sender(senderID)
userid = sender.getUserID()
imtype = sender.getImtype()
uservalue = middleware.bucketGet(bucket='yuhua_yuyun_user', key=userid)

def get_config():
    """获取插件配置"""
    manage_cmd = middleware.bucketGet('yuhua_yuyun', 'manage_cmd') or '雨云管理'
    query_cmd = middleware.bucketGet('yuhua_yuyun', 'query_cmd') or '雨云查询'
    login_cmd = middleware.bucketGet('yuhua_yuyun', 'login_cmd') or '雨云登录'
    price = Decimal(middleware.bucketGet('yuhua_yuyun', 'price') or '0')
    bf_str = middleware.bucketGet('yuhua_yuyun', 'bingfa') or '5'
    
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


def _query_single_account(unique_id):
    """【内部函数】并发查询单个账号 (含3次重试机制)"""
    time.sleep(random.uniform(0.5, 1.0))
    phone = middleware.bucketGet('yuhua_yuyun_phone', unique_id) or "未知"
    phone_mask = _mask_identifier(phone)
    
    auth_time = middleware.bucketGet('yuhua_yuyun_auth', unique_id)
    now_date = datetime.now().date()
    
    if not auth_time: return f"【{phone_mask}】未授权"
    auth_date = datetime.strptime(auth_time, "%Y-%m-%d").date()
    if auth_date < now_date: return f"【{phone_mask}】授权已过期"  
    
    token = middleware.bucketGet('yuhua_yuyun_token', unique_id)
    if not token: return f"【{phone_mask}】本地未找到凭证"

    last_error = "未知错误"
    
    # 增加3次业务重试
    for attempt in range(3):
        hsh = None
        try:
            hsh = HSH(token, uid=unique_id)
            # 获取资产 (内部会自动处理 check_token 和重登)
            assets = hsh.query_assets()
            
            if assets['valid']:
                hsh.close()
                return f"""
=====账号信息=====
🤪 账号: {phone_mask}
🎫 当前积分: {assets.get('total_score', '0')}
🎨 今日积分: {assets.get('today_score', '0')}
☁️ 授权到期: {auth_date.strftime('%Y-%m-%d')}
=================="""
            else:
                last_error = "凭证失效且重登失败"
        except Exception as e:
            last_error = str(e)
        finally:
            if hsh: hsh.close()
            
        # 如果不是最后一次尝试，稍微等待后重试
        if attempt < 2:
            time.sleep(1.5)
            
    return f"【{phone_mask}】查询失败: {last_error}"
    

def query_account():
    """
    【雨云查询】
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
    """【内部函数】任务运行包装器 (含3次重试机制)"""
    time.sleep(random.uniform(0.5, 2.0))
    phone = middleware.bucketGet('yuhua_yuyun_phone', unique_id) or "未知"
    phone_mask = _mask_identifier(phone)
    
    # 1. 基础鉴权 (无需重试)
    auth_time = middleware.bucketGet('yuhua_yuyun_auth', unique_id)
    now_date = datetime.now().date()
    if not auth_time: 
        return f"=====雨云运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 未授权\n======================="
    if datetime.strptime(auth_time, "%Y-%m-%d").date() < now_date: 
        return f"=====雨云运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 授权已过期\n======================="
    
    token = middleware.bucketGet('yuhua_yuyun_token', unique_id)
    if not token: 
        return f"=====雨云运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 未登录\n======================="

    last_result_msg = ""
    
    # 2. 运行逻辑 (增加3次重试)
    for attempt in range(3):
        hsh = None
        try:
            hsh = HSH(token, uid=unique_id)
            
            # 先检查有效性/重登
            valid, msg = hsh.check_token()
            if not valid:
                last_result_msg = f"=====雨云运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 凭证失效({msg})\n======================="
            else:
                # 执行任务
                res = hsh.run_daily_tasks(phone_mask)
                hsh.close()
                return res # 成功执行则直接返回
                
        except Exception as e:
            last_result_msg = f"=====雨云运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 运行异常({str(e)})\n======================="
        finally:
            if hsh: hsh.close()
            
        # 失败等待
        if attempt < 2:
            time.sleep(2)

    return last_result_msg


def execute_batch_run():
    """【雨云运行】用户侧指令"""
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
    """【雨云一键运行】管理员侧指令 (已优化：动态判断完成率)"""
    sender.reply("正在执行...")
    
    # 收集任务
    tasks = []
    users = middleware.bucketAllKeys('yuhua_yuyun_user')
    for u in users:
        acc_list = eval(middleware.bucketGet('yuhua_yuyun_user', u) or '[]')
        for a in acc_list:
            # 仅运行已授权且不过期的
            auth = middleware.bucketGet('yuhua_yuyun_auth', a)
            if auth and auth >= str(datetime.now().date()):
                tasks.append((u, a))
    
    if not tasks:
        sender.reply("❌ 暂无已授权的账号")
        return

    success = 0
    failed = 0
    details = []
    
    # 获取推送状态配置 (默认关闭)
    push_cfg = middleware.bucketGet('yuhua_yuyun', 'push_status')
    is_push = str(push_cfg).lower() == 'true'

    def _run_single(u, a):
        try:
            res = _wrap_task_run(a)
            p = middleware.bucketGet('yuhua_yuyun_phone', a) or '未知'
            p_mask = _mask_identifier(p)
            
            # 推送给用户 (根据配置决定)
            if is_push:
                for ch in ['qq','qb','wx','gw','sb','wb','tg','tb','qx','xy','ip']: 
                    try: middleware.push(ch, '', u, '', res)
                    except: pass
            
            # 统计逻辑：动态正则匹配 "完成X/Y"
            match = re.search(r"完成(\d+)/(\d+)", res)
            is_success = False
            if match:
                done_cnt = int(match.group(1))
                total_cnt = int(match.group(2))
                if done_cnt == total_cnt and total_cnt > 0:
                    is_success = True
            
            if is_success:
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
        f"=====雨云一键=====",
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
    """
    账号显示处理逻辑 (优化版)：
    1. 手机号 (11位数字): 显示前3后4 -> 138****8888
    2. 邮箱: 
       - 长度>=6: 保留前3后3 -> 255****191@qq.com
       - 长度<6:  保留首尾 -> t****t@qq.com
    3. 其他长账号 (>8位): 
       - 长度>=11: 保留前3后4 (修复：防止手机号因正则匹配失败只显示3位)
       - 长度<11: 保留前3后3
    4. 短账号: 原样显示
    """
    val = str(identifier).strip()
    
    # 1. 手机号处理 (标准11位数字)
    if re.match(r'^\d{11}$', val):
        return val[:3] + "****" + val[-4:]
        
    # 2. 邮箱处理
    if '@' in val:
        parts = val.split('@')
        local_part = parts[0]
        # 防止邮箱域名部分也包含@（虽然罕见），稳健拼接
        domain_part = "@".join(parts[1:]) 
        
        if len(local_part) >= 6:

            return local_part[:3] + "****" + local_part[-3:] + "@" + domain_part
        elif len(local_part) > 2:
            # 短邮箱：test -> t****t
            return local_part[:1] + "****" + local_part[-1:] + "@" + domain_part
        else:
            # 极短邮箱：ab -> ab****
            return local_part + "****@" + domain_part

    # 3. 其他不规则长账号 (大于8位视为长账号)
    if len(val) > 8:
        # 修复：如果是11位或更长的字符串，强制保留后4位，解决手机号显示问题
        if len(val) >= 11:
            return val[:3] + "****" + val[-4:]
        return val[:3] + "****" + val[-3:]
        
    # 4. 短账号直接显示
    return val

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
            middleware.bucketSet('yuhua_yuyun_auth', acc_id, auth_time)
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
        phone = middleware.bucketGet('yuhua_yuyun_phone', acc_id) or "未知"
        phone_mask = _mask_identifier(phone)
        auth_str = middleware.bucketGet('yuhua_yuyun_auth', acc_id)
        
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
    else:
        sender.reply("❌ 无效的选择")

def confirm_delete(account):
    """确认是否删除账号"""
    phone = middleware.bucketGet('yuhua_yuyun_phone', account) or "未知"
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
    phone = middleware.bucketGet('yuhua_yuyun_phone', account) or "未知"
    phone_mask = _mask_identifier(phone)
    accounts = eval(uservalue or '[]')
    if account not in accounts:
        sender.reply("❌ 未找到账号")
        return
        
    accounts.remove(account)
    middleware.bucketSet('yuhua_yuyun_user', userid, str(accounts))
    try:
        middleware.bucketDel('yuhua_yuyun_token', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_yuyun_pwd', account) # 新增：同步删除密码数据
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_yuyun_acct', account) # 新增：同步删除登录账号数据
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_yuyun_auth', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_yuyun_phone', account)
    except Exception:
        pass
    sender.reply(f"""
=====删除成功=====
🤪 账号: {phone_mask}
✅ 状态: 已删除数据
==================""")

def auth_account(account):
    """用户侧手动授权"""
    phone = middleware.bucketGet('yuhua_yuyun_phone', account) or "未知"
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
    middleware.bucketSet('yuhua_yuyun_auth', account, auth_time)
    
    days = 30*months
    sender.reply(f"""
=====授权成功=====
🤪 账号: {phone_mask}
⏰ 时长: {days}天
📅 到期: {auth_time}
=======================""")

def calculate_auth_time(account, days):
    current_date = datetime.now().date()
    auth_str = middleware.bucketGet('yuhua_yuyun_auth', account)
    
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
    zsm = middleware.bucketGet('yuhua_yuyun', 'zsm')
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
    users = middleware.bucketAllKeys('yuhua_yuyun_user')
    cleaned = 0
    for user in users:
        accounts = eval(middleware.bucketGet('yuhua_yuyun_user', user) or '[]')
        valid = []
        for acc_id in accounts:
            auth = middleware.bucketGet('yuhua_yuyun_auth', acc_id)
            if (not auth) or (auth <= str(datetime.now().date())):
                try:
                    middleware.bucketDel('yuhua_yuyun_token', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_yuyun_auth', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_yuyun_phone', acc_id)
                except Exception:
                    pass
                # 新增：同步清理密码和登录账号数据
                try:
                    middleware.bucketDel('yuhua_yuyun_pwd', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_yuyun_acct', acc_id)
                except Exception:
                    pass
                cleaned += 1
            else:
                valid.append(acc_id)
        if valid:
            middleware.bucketSet('yuhua_yuyun_user', user, str(valid))
        else:
            try:
                middleware.bucketDel('yuhua_yuyun_user', user)
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
        users = middleware.bucketAllKeys('yuhua_yuyun_user')
        success = 0
        failed = 0
        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_yuyun_user', user) or '[]')
            for acc_id in accounts:
                try:
                    auth_time = calculate_auth_time(acc_id, days)
                    middleware.bucketSet('yuhua_yuyun_auth', acc_id, auth_time)
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

    accounts = eval(middleware.bucketGet('yuhua_yuyun_user', user_id) or '[]')
    if not accounts:
        sender.reply("❌ 该用户没有绑定账号")
        return

    account_list_msg = "=====账号列表=====\n[0] 授权全部账号\n"
    for i, acc_id in enumerate(accounts, 1):
        phone = middleware.bucketGet('yuhua_yuyun_phone', acc_id) or "未知"
        phone_mask = _mask_identifier(phone)
        auth_str = middleware.bucketGet('yuhua_yuyun_auth', acc_id)
        
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
        latest_accounts = eval(middleware.bucketGet('yuhua_yuyun_user', user_id) or '[]')
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
                middleware.bucketSet('yuhua_yuyun_auth', acc_id, auth_time)
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
    """定时任务处理 (雨云智能检测版)"""
    if imtype != 'fake':
        pass
    today_str = str(datetime.now().date())
    try:
        users = middleware.bucketAllKeys('yuhua_yuyun_user')
        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_yuyun_user', user) or '[]')
            for acc_id in accounts:
                time.sleep(random.uniform(0.5, 1.0))
                try:
                    token = middleware.bucketGet('yuhua_yuyun_token', acc_id)
                    
                    if not token:
                        # 尝试静默登录补救 (如果密码还在)
                        hsh = HSH("", uid=acc_id)
                        if not hsh._silent_relogin():
                            notify_user(user, acc_id, "未找到登录凭证，请重新登录")
                        hsh.close()
                        continue
                        
                    # 传入 uid 进行检测
                    hsh = HSH(token, uid=acc_id)
                    ok, msg = hsh.check_token()
                    hsh.close()
                    
                    if not ok:
                        # check_token 内部已经尝试过重登了，如果还是False，说明密码错误或被封禁
                        notify_user(user, acc_id, f"登录凭证失效且自动重连失败，请检查密码: {msg}")
                        continue
                        
                    auth_time = middleware.bucketGet('yuhua_yuyun_auth', acc_id)
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
        phone = middleware.bucketGet('yuhua_yuyun_phone', account) or "未知"
        phone_mask = _mask_identifier(phone)
        notify_msg = f"""
=====雨云通知=====
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
        elif message == '雨云运行':
            execute_batch_run()
        elif message == '雨云清理':
            clean_expired()
        elif message == '雨云授权':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            admin_auth()
        elif message == '雨云检测':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            sender.reply("正在检测....")
            cron_task()
            sender.reply("✅ 已执行检测推送任务")
        elif message == '雨云一键运行':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            admin_run_all_tasks()
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
