# [title: 乐仔生活]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@e9cd9a11a480cadebc2fd54b8302d737d580595d/2026/01/30/81fd4cd42a523da597582e5727913a23.png]
# [language: python]
# [rule: ^(乐仔)(登录|查询|管理|清理|授权|检测|运行|一键运行)$]
# [disable:false]
# [open_source: false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [priority: 9999999999999999999]
# [public: true]
# [version: 1.1.3]
# [price: 0]
# [author: yuhualhh]
# [service: ]
# [description: ❶乐仔生活内置任务插件，自动完成每日任务获取346左右积分，支持Token登录、手机号登录、自定义并发、管理、查询、授权、检测授权过期以及Token失效推送等功能<br>❷部分功能的实现需自行添加计划任务伪装管理员定时，了解如何添加计划任务请看移动云盘插件介绍，关于指令『乐仔检测』与『乐仔清理』定时『30 18 * * *』，关于指令『乐仔一键运行』定时『0 4,16 * * *』<img src="https://gcore.jsdelivr.net/gh/lhz03/img@bd8210bc5df21199ccd7228aa6246390ff0ebe5a/2026/01/30/72f1808271bcf657c196256a7e2c3fb1.png">]

# [param: {"required":true,"key":"yuhua_lzsh.zsm","bool":false,"placeholder":"","name":"收款码子","desc":"微信Bot收款码直链"}]
# [param: {"required":true,"key":"yuhua_lzsh.price","bool":false,"placeholder":"","name":"收费价格","desc":"不填默认0元，单位: 元/月"}]
# [param: {"required":true,"key":"yuhua_lzsh.bingfa","bool":false,"placeholder":"","name":"并发数量","desc":"不填默认20"}]
# [param: {"required":false,"key":"yuhua_lzsh.push_status","bool":true,"placeholder":"","name":"推送状态","desc":"是否将乐仔一键运行结果推送给用户"}]
# [param: {"required":false,"key":"yuhua_lzsh.debug_pwd","bool":false,"placeholder":"","name":"调试模式","desc":"非插件开发者无需理会"}]

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
debug_key = middleware.bucketGet('yuhua_lzsh', 'debug_pwd') or ''
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
    通过抓包获取 xiaoletoken
    """
    guide = """
=====Token登录=====
乐仔生活请求头中的xiaoletoken值
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

def sms_login_interaction():
    """
    【短信登录功能】
    自动发送短信
    """
    sender.reply(f"""
=====短信登录=====
请输入乐仔生活手机号
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

    sender.reply("正在请求验证码...")
    
    # 初始化临时 HSH 实例用于发送请求
    hsh = HSH(token="") 
    
    # 尝试发送短信
    send_ok, send_msg = hsh.send_sms_with_captcha(phone)
    
    if not send_ok:
        sender.reply(f"❌ 发送失败: {send_msg}")
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

def process_login_success(token):
    """处理登录成功后的逻辑（Token验证与保存）"""
    sender.reply("正在验证凭证有效性...")
    try:
        # 初始化API类进行验证
        hsh = HSH(token)
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
            old_phone = middleware.bucketGet('yuhua_lzsh_phone', str(uid)) or "未知"
            if old_phone == phone:
                matched_uid = str(uid)
                break
        
        final_uid = matched_uid if matched_uid else (uid_raw if uid_raw else gen_unique_id())
        
        if matched_uid:
            middleware.bucketSet('yuhua_lzsh_token', str(matched_uid), token)
            
            try:
                middleware.bucketDel('yuhua_lzsh_password', str(matched_uid))
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
            middleware.bucketSet('yuhua_lzsh_user', userid, str(accounts))
            middleware.bucketSet('yuhua_lzsh_token', str(final_uid), token)
            middleware.bucketSet('yuhua_lzsh_phone', str(final_uid), phone)
            
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

###################### 乐仔生活核心类 (HSH) ######################
class HSH:
    def __init__(self, token, session=None):
        self.session = session or requests.Session()
        self.token = token
        # 配置固定请求头
        self.headers = {
            "xiaoletoken": self.token,
            "User-Agent": "okhttp/4.9.2",
            "Content-Type": "application/json",
            "Host": "infor.leyaoyao.com",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip"
        }
        self.base_url = "https://infor.leyaoyao.com/infor/xiaolelife"

    def _send_request(self, method, url, **kwargs):
        kwargs['session'] = self.session
        # 合并Header
        req_headers = self.headers.copy()
        if 'headers' in kwargs:
            req_headers.update(kwargs['headers'])
            del kwargs['headers']
        
        try:
            return send_request_global(method, url, headers=req_headers, **kwargs)
        except Exception:
            return None

    def _build_task_finish_payload(self, task_id):
            api_url = f"https://yuhualhh.250666.xyz/api/lezai_sign.php?taskId={task_id}"
            
            for attempt in range(3):
                try:
                    res = requests.get(api_url, timeout=10)
                    if res.status_code == 200:
                        data = res.json()
                        if "signedText" in data:
                            return {
                                "taskId": task_id,
                                "random": data.get("random"),
                                "timestamp": data.get("timestamp"),
                                "signedText": data.get("signedText")
                            }
                except Exception as e:
                    if attempt == 2:
                        raise Exception(f"远程签名获取失败: {e}")
                
                import time
                time.sleep(2)
                
            raise Exception("远程获取签名多次尝试失败")

    def send_sms_with_captcha(self, phone):
        """发送短信验证码"""
        try:
            url = f"{self.base_url}/verification-code?phoneNumber={phone}"
            res = self._send_request('GET', url)
            if res:
                data = res.json()
                if data.get('code') == "0000000":
                    return True, "发送成功"
                return False, data.get('message', '发送失败')
        except Exception as e:
            return False, str(e)
        return False, "请求失败"

    def login_by_sms_code(self, phone, sms_code):
        """使用短信验证码登录"""
        if DEBUG: printf(f"正在尝试短信登录: {phone} code={sms_code}", "INFO")
        url = f"{self.base_url}/register-or-login"
        # 固定deviceId避免风控
        payload = {
            "phoneNumber": phone,
            "verificationCode": sms_code,
            "deviceId": "fb965a27c91647849b642751dfbd6e59", 
            "endpoint": "ANDROID",
            "modelName": "default",
            "version": "v_1.2.4"
        }
        
        try:
            res = self._send_request('POST', url, json=payload)
            if res:
                data = res.json()
                if data.get('code') == "0000000":
                    token = data.get('body', {}).get('token')
                    if token:
                        if DEBUG: printf("短信登录成功，获取到Token", "INFO")
                        return True, token
                if DEBUG: printf(f"短信登录失败: {data}", "WARN")
                return False, data.get('message', '登录失败')
        except Exception as e:
            return False, str(e)
        return False, "网络请求无响应"

    def check_token(self):
        """检测Token有效性 (已修复Token泄露问题)"""
        url = f"{self.base_url}/user-info"
        res = self._send_request('GET', url)
        if res is None: return False, "网络请求失败"

        # 定义内部脱敏函数
        def clean_msg(text):
            if not isinstance(text, str): return str(text)
            # 1. 优先替换当前上下文中的Token
            if self.token and self.token in text:
                text = text.replace(self.token, "******")
            # 2. 使用正则通用匹配JWT格式 (eyJ开头, 中间有点号, 长度较长) 防止泄露其他Token
            text = re.sub(r'eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+', '******', text)
            return text
        
        if getattr(res, "status_code", None) == 401:
            try:
                data = res.json()
                msg = data.get('message') or data.get('msg')
                if msg: return False, clean_msg(msg)
                return False, clean_msg(json.dumps(data, ensure_ascii=False))
            except:
                text = (res.text or "").strip()
                if text: return False, clean_msg(text[:200])
                return False, f"HTTP {res.status_code}"
        
        try:
            data = res.json()
            if data.get('code') == "0000000":
                return True, "有效"
            else:
                return False, clean_msg(data.get('message', 'Token无效'))
        except:
            return False, "解析响应失败"

    def get_user_info(self):
        """获取手机号和用户ID"""
        url = f"{self.base_url}/user-info"
        res = self._send_request('GET', url)
        if not res: return False, {}
        
        try:
            data = res.json()
            if data.get('code') == "0000000":
                body = data.get('body', {})
                return True, {
                    "phone": body.get('telephone', ''),
                    "uid": str(body.get('userId', ''))
                }
        except: pass
        return False, {}

    def get_total_score(self):
        """获取当前总积分"""
        url = f"{self.base_url}/points/wall/v4"
        res = self._send_request('GET', url)
        if not res: return "0"
        
        try:
            data = res.json()
            if data.get('code') == "0000000":
                return str(data.get('body', {}).get('totalPoints', '0'))
        except: pass
        return "0"

    def get_today_score(self):
        """获取今日获取的积分"""
        url = f"{self.base_url}/points/desc"
        res = self._send_request('GET', url)
        if not res: return "0"
        
        try:
            data = res.json()
            if data.get('code') == "0000000":
                records = data.get('body', [])
                if not records: return "0"
                
                today_str = datetime.now().strftime("%Y-%m-%d")
                today_sum = 0
                
                for item in records:
                    create_time = item.get("createTime", "")
                    if today_str in create_time:
                        p = item.get("points", 0)
                        if p > 0:
                            today_sum += p
                    else:
                        # 列表通常是倒序的，非今日数据可跳过，但为保险遍历完
                        pass 
                
                return str(int(today_sum))
        except: pass
        return "0"
        
    def query_assets(self):
        """聚合查询资产"""
        self.get_user_info() # 刷新状态
        total = self.get_total_score()
        today = self.get_today_score()
        
        return {
            "total_score": total,
            "today_score": today,
            "valid": True
        }

    def close(self):
        if self.session:
            self.session.close()
            self.session = None

    def sign_in(self):
        """每日签到"""
        try:
            url = f"{self.base_url}/sign-in"
            res = self._send_request('GET', url)
            if res:
                data = res.json()
                if data.get("code") == "0000000":
                    body = data.get("body", {})
                    points = body.get("points", 0)
                    if points > 0:
                        return True, f"成功(获得{points}分)"
                    else:
                        return True, "今日已签"
                return False, data.get("message", "失败")
        except:
            pass
        return False, "异常"

    def do_task_with_retry(self, task_id, task_name, is_video=False):
        """执行单个任务(含重试)"""
        url = f"{self.base_url}/points/mark-finished"
        payload = {"taskId": task_id}
        
        # 最大重试3次
        for i in range(3):
            try:
                try:
                    payload = self._build_task_finish_payload(task_id)
                except Exception as e:
                    if DEBUG: printf(f"任务签名生成失败: {e}", "WARN")
                res = self._send_request('POST', url, json=payload)
                if not res: continue
                data = res.json()
                
                if data.get("code") == "0000000":
                    body = data.get('body')
                    if body and body.get('flag') is True:
                        return True
                    else:
                        # 失败(flag=false)，通常是CD不够
                        time.sleep(61)
                else:
                    time.sleep(3)
            except:
                time.sleep(3)
        return False

    def get_qrcode_task_count(self):
        """获取今日扫码任务完成次数"""
        url = f"{self.base_url}/points/desc"
        res = self._send_request('GET', url)
        count = 0
        if not res: return 0
        
        try:
            data = res.json()
            if data.get('code') == "0000000":
                records = data.get('body', [])
                today_str = datetime.now().strftime("%Y-%m-%d")
                for item in records:
                    create_time = item.get("createTime", "")
                    desc = item.get("desc", "")
                    # 根据描述统计今日已完成次数
                    if today_str in create_time and "扫码积分派发任务" in desc:
                        count += 1
        except: pass
        return count

    def do_qrcode_task(self):
        """执行扫码积分派发任务"""
        # 随机生成设备ID 541000-549999 模拟扫码
        equipment_value = str(540000 + random.randint(1000, 9999))
        url = "https://infor.leyaoyao.com/infor/xiaolelife/third/auth/qr-code/wxmini/url/v3"
        payload = {
            "authDomain": "c.cooleasy.net",
            "equipmentValue": equipment_value
        }
        try:
            res = self._send_request('POST', url, json=payload)
            if res and res.json().get("code") == "0000000":
                return True
        except:
            pass
        return False

    def run_daily_tasks(self, phone_mask):
        """执行日常任务"""
        # 1. 签到
        sign_ok, sign_msg = self.sign_in()
        
        # 2. 获取任务列表
        url = f"{self.base_url}/points/wall/v4"
        task_report_lines = []
        total_tasks_count = 0
        finished_tasks_count = 0
        
        # 黑名单任务ID (需要第三方回调的)
        BLACKLIST_TASK_IDS = [150, 151]
        
        # 图标映射逻辑
        def get_icon(name, route_type):
            if "短剧" in name: return "🎬"
            if "文章" in name: return "📜"
            if "抖音" in name: return "🎶"
            if "吃喝玩乐" in name: return "🎮"            
            if "饿了么学生特权" in name: return "🛁" 
            if "资讯" in name: return "🗨️"
            if "小程序" in name: return "🏖️"
            if "美团学生特权" in name: return "🃏"                         
            if "看视频广告得积分" in name: return "🫧"
            if "看广告得积分" in name: return "🪅"
            return "📝"

        try:
            # --- 新增：扫码积分派发任务逻辑 (隐形任务) ---
            qrcode_limit = 3
            qrcode_done = self.get_qrcode_task_count()
            total_tasks_count += 1
            
            # 闲时判断 (仅用于显示，服务器会自动判定积分)
            now_hour = datetime.now().hour
            is_idle = (0 <= now_hour < 7) or (14 <= now_hour < 17)
            points_display = 20 if is_idle else 10
            
            if qrcode_done >= qrcode_limit:
                finished_tasks_count += 1
                task_report_lines.append(f"💳 扫码积分派发任务")
            else:
                needed = qrcode_limit - qrcode_done
                success_cnt = 0
                for _ in range(needed):
                    if self.do_qrcode_task():
                        success_cnt += 1
                        time.sleep(random.uniform(2, 4)) # 随机延迟防止风控
                    else:
                        time.sleep(1)
                
                final_done = qrcode_done + success_cnt
                if final_done >= qrcode_limit:
                    finished_tasks_count += 1
                    task_report_lines.append(f"💳 扫码积分派发任务")
                else:
                    task_report_lines.append(f"❌ 扫码积分派发任务 ({final_done}/{qrcode_limit})")
            # --------------------------------------------

            res = self._send_request('GET', url)
            if res and res.json().get("code") == "0000000":
                groups = res.json().get("body", {}).get("types", [])
                
                # 签到状态记录
                total_tasks_count += 1
                if sign_ok:
                    finished_tasks_count += 1 
                    task_report_lines.append(f"🎨 每日签到")
                else:
                    task_report_lines.append(f"❌ 每日签到")

                for group in groups:
                    for task in group.get("tasks", []):
                        t_id = task.get("taskId")
                        t_name = task.get("name")
                        
                        if t_id in BLACKLIST_TASK_IDS: continue
                        
                        limit = task.get("limit", 1)
                        done = task.get("doneCount", 0)
                        is_finished = task.get("finished", False)
                        route_type = task.get("routeType", "")
                        
                        total_tasks_count += 1
                        
                        # 获取动态图标
                        icon = get_icon(t_name, route_type)
                        
                        if is_finished or done >= limit:
                            finished_tasks_count += 1
                            task_report_lines.append(f"{icon} {t_name}")
                            continue
                            
                        # 执行任务
                        needed = limit - done
                        success_cnt = 0
                        is_video = "VIDEO" in route_type
                        
                        for _ in range(needed):
                            if self.do_task_with_retry(t_id, t_name, is_video):
                                success_cnt += 1
                                # 成功后固定延迟 0.2 秒
                                time.sleep(0.2)
                            else:
                                time.sleep(61)
                        
                        final_done = done + success_cnt
                        if final_done >= limit:
                            finished_tasks_count += 1
                            task_report_lines.append(f"{icon} {t_name}")
                        else:
                            task_report_lines.append(f"❌ {t_name} ({final_done}/{limit})")
            else:
                task_report_lines.append("❌ 获取任务列表失败")
                
        except Exception as e:
            task_report_lines.append(f"❌ 任务执行异常: {str(e)}")

        final_msg = f"=====乐仔运行结果=====\n🤪 账号: {phone_mask}\n💫 结果: 完成{finished_tasks_count}/{total_tasks_count}\n------------------\n"
        final_msg += "\n".join(task_report_lines)
        final_msg += "\n======================="
        return final_msg
        

def gen_unique_id(prefix=""):
    timestamp = int(time.time() * 1_000_000)
    return f"{prefix}{timestamp}"

senderID = middleware.getSenderID()
sender = middleware.Sender(senderID)
userid = sender.getUserID()
imtype = sender.getImtype()
uservalue = middleware.bucketGet(bucket='yuhua_lzsh_user', key=userid)

def get_config():
    """获取插件配置"""
    manage_cmd = middleware.bucketGet('yuhua_lzsh', 'manage_cmd') or '乐仔管理'
    query_cmd = middleware.bucketGet('yuhua_lzsh', 'query_cmd') or '乐仔查询'
    login_cmd = middleware.bucketGet('yuhua_lzsh', 'login_cmd') or '乐仔登录'
    price = Decimal(middleware.bucketGet('yuhua_lzsh', 'price') or '0')
    bf_str = middleware.bucketGet('yuhua_lzsh', 'bingfa') or '20'
    
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
    login_guide = """
=====登录方式=====
[1] Token登录
[2] 手机号登录 (推荐)
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
            sms_login_interaction()
        else:
            sender.reply("❌ 无效的选择")
            return
    except Exception as e:
        sender.reply(f"❌ 登录失败: {str(e)}")
        return

def _query_single_account(unique_id):
    """【内部函数】并发查询单个账号"""
    time.sleep(random.uniform(0.5, 1.0))
    phone = middleware.bucketGet('yuhua_lzsh_phone', unique_id) or "未知"
    phone_mask = _mask_identifier(phone)
    auth_time = middleware.bucketGet('yuhua_lzsh_auth', unique_id)
    now_date = datetime.now().date()
    
    if not auth_time: return f"【{phone_mask}】未授权"
    auth_date = datetime.strptime(auth_time, "%Y-%m-%d").date()
    if auth_date < now_date: return f"【{phone_mask}】授权已过期"  
    
    token = middleware.bucketGet('yuhua_lzsh_token', unique_id)
    if not token: return f"【{phone_mask}】本地未找到Token"

    hsh = HSH(token)
    
    try:
        # 验证Token
        valid, msg = hsh.check_token()
        if not valid:
            if "过期" in msg or "失效" in msg:
                return f"【{phone_mask}】登录凭证已失效，请重新登录"
            return f"【{phone_mask}】{msg}"
            
        assets = hsh.query_assets()
        
        return f"""
=====账号信息=====
🤪 账号: {phone_mask}
🎫 当前积分: {assets.get('total_score', '0')}
🎨 今日积分: {assets.get('today_score', '0')}
☁️ 授权到期: {auth_date.strftime('%Y-%m-%d')}
=================="""

    finally:
        hsh.close()

def query_account():
    """
    【乐仔查询】
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
    phone = middleware.bucketGet('yuhua_lzsh_phone', unique_id) or "未知"
    phone_mask = _mask_identifier(phone)
    
    # 鉴权
    auth_time = middleware.bucketGet('yuhua_lzsh_auth', unique_id)
    now_date = datetime.now().date()
    if not auth_time: 
        return f"=====乐仔运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 未授权\n======================="
    if datetime.strptime(auth_time, "%Y-%m-%d").date() < now_date: 
        return f"=====乐仔运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 授权已过期\n======================="
    
    token = middleware.bucketGet('yuhua_lzsh_token', unique_id)
    if not token: 
        return f"=====乐仔运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 未登录\n======================="

    hsh = HSH(token)
    try:
        valid, msg = hsh.check_token()
        if not valid:
            return f"=====乐仔运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 凭证失效({msg})\n======================="
        return hsh.run_daily_tasks(phone_mask)
    except Exception as e:
        return f"=====乐仔运行结果=====\n🤪 账号: {phone_mask}\n❌ 结果: 运行异常({str(e)})\n======================="
    finally:
        hsh.close()

def execute_batch_run():
    """【乐仔运行】用户侧指令"""
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
    """【乐仔一键运行】管理员侧指令 (已优化：动态判断完成率)"""
    sender.reply("正在执行...")
    
    # 收集任务
    tasks = []
    users = middleware.bucketAllKeys('yuhua_lzsh_user')
    for u in users:
        acc_list = eval(middleware.bucketGet('yuhua_lzsh_user', u) or '[]')
        for a in acc_list:
            # 仅运行已授权且不过期的
            auth = middleware.bucketGet('yuhua_lzsh_auth', a)
            if auth and auth >= str(datetime.now().date()):
                tasks.append((u, a))
    
    if not tasks:
        sender.reply("❌ 暂无已授权的账号")
        return

    success = 0
    failed = 0
    details = []
    
    # 获取推送状态配置 (默认关闭)
    push_cfg = middleware.bucketGet('yuhua_lzsh', 'push_status')
    is_push = str(push_cfg).lower() == 'true'

    def _run_single(u, a):
        try:
            res = _wrap_task_run(a)
            p = middleware.bucketGet('yuhua_lzsh_phone', a) or '未知'
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
        f"=====乐仔一键=====",
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
            middleware.bucketSet('yuhua_lzsh_auth', acc_id, auth_time)
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
        phone = middleware.bucketGet('yuhua_lzsh_phone', acc_id) or "未知"
        phone_mask = _mask_identifier(phone)
        auth_str = middleware.bucketGet('yuhua_lzsh_auth', acc_id)
        
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
    phone = middleware.bucketGet('yuhua_lzsh_phone', account) or "未知"
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
    phone = middleware.bucketGet('yuhua_lzsh_phone', account) or "未知"
    phone_mask = _mask_identifier(phone)
    accounts = eval(uservalue or '[]')
    if account not in accounts:
        sender.reply("❌ 未找到账号")
        return
        
    accounts.remove(account)
    middleware.bucketSet('yuhua_lzsh_user', userid, str(accounts))
    try:
        middleware.bucketDel('yuhua_lzsh_token', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_lzsh_auth', account)
    except Exception:
        pass
    try:
        middleware.bucketDel('yuhua_lzsh_phone', account)
    except Exception:
        pass
    sender.reply(f"""
=====删除成功=====
🤪 账号: {phone_mask}
✅ 状态: 已删除数据
==================""")

def auth_account(account):
    """用户侧手动授权"""
    phone = middleware.bucketGet('yuhua_lzsh_phone', account) or "未知"
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
    middleware.bucketSet('yuhua_lzsh_auth', account, auth_time)
    
    days = 30*months
    sender.reply(f"""
=====授权成功=====
🤪 账号: {phone_mask}
⏰ 时长: {days}天
📅 到期: {auth_time}
=======================""")

def calculate_auth_time(account, days):
    current_date = datetime.now().date()
    auth_str = middleware.bucketGet('yuhua_lzsh_auth', account)
    
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
    zsm = middleware.bucketGet('yuhua_lzsh', 'zsm')
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
    users = middleware.bucketAllKeys('yuhua_lzsh_user')
    cleaned = 0
    for user in users:
        accounts = eval(middleware.bucketGet('yuhua_lzsh_user', user) or '[]')
        valid = []
        for acc_id in accounts:
            auth = middleware.bucketGet('yuhua_lzsh_auth', acc_id)
            if (not auth) or (auth <= str(datetime.now().date())):
                try:
                    middleware.bucketDel('yuhua_lzsh_token', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_lzsh_auth', acc_id)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_lzsh_phone', acc_id)
                except Exception:
                    pass
                cleaned += 1
            else:
                valid.append(acc_id)
        if valid:
            middleware.bucketSet('yuhua_lzsh_user', user, str(valid))
        else:
            try:
                middleware.bucketDel('yuhua_lzsh_user', user)
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
        users = middleware.bucketAllKeys('yuhua_lzsh_user')
        success = 0
        failed = 0
        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_lzsh_user', user) or '[]')
            for acc_id in accounts:
                try:
                    auth_time = calculate_auth_time(acc_id, days)
                    middleware.bucketSet('yuhua_lzsh_auth', acc_id, auth_time)
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

    accounts = eval(middleware.bucketGet('yuhua_lzsh_user', user_id) or '[]')
    if not accounts:
        sender.reply("❌ 该用户没有绑定账号")
        return

    account_list_msg = "=====账号列表=====\n[0] 授权全部账号\n"
    for i, acc_id in enumerate(accounts, 1):
        phone = middleware.bucketGet('yuhua_lzsh_phone', acc_id) or "未知"
        phone_mask = _mask_identifier(phone)
        auth_str = middleware.bucketGet('yuhua_lzsh_auth', acc_id)
        
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
        latest_accounts = eval(middleware.bucketGet('yuhua_lzsh_user', user_id) or '[]')
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
                middleware.bucketSet('yuhua_lzsh_auth', acc_id, auth_time)
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
        users = middleware.bucketAllKeys('yuhua_lzsh_user')
        for user in users:
            accounts = eval(middleware.bucketGet('yuhua_lzsh_user', user) or '[]')
            for acc_id in accounts:
                time.sleep(random.uniform(0.5, 1.0))
                try:
                    token = middleware.bucketGet('yuhua_lzsh_token', acc_id)
                    phone = middleware.bucketGet('yuhua_lzsh_phone', acc_id) or "未知"
                    if not token:
                        notify_user(user, acc_id, "未找到登录凭证")
                        continue
                        
                    hsh = HSH(token)
                    ok, msg = hsh.check_token()
                    hsh.close()
                    
                    if not ok:
                        notify_user(user, acc_id, f"登录凭证已失效: {msg}")
                        continue
                        
                    auth_time = middleware.bucketGet('yuhua_lzsh_auth', acc_id)
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
        phone = middleware.bucketGet('yuhua_lzsh_phone', account) or "未知"
        phone_mask = _mask_identifier(phone)
        notify_msg = f"""
=====乐仔通知=====
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
        elif message == '乐仔运行':
            execute_batch_run()
        elif message == '乐仔清理':
            clean_expired()
        elif message == '乐仔授权':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            admin_auth()
        elif message == '乐仔检测':
            if not sender.isAdmin():
                sender.reply("❌ 需要管理员权限")
                return
            sender.reply("正在检测....")
            cron_task()
            sender.reply("✅ 已执行检测推送任务")
        elif message == '乐仔一键运行':
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
