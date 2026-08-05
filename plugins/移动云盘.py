# [title: 移动云盘]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@391e5db5571432ac74c20afa8e958ac83e32e7a3/2025/02/13/437a3d841eaea843d11f97941c33accb.png]
# [language: python]
# [rule: ^(云盘)(登录|查询|管理|清理|授权|检测|兑换|一键抢兑)$]
# [disable:false]
# [open_source: false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [priority: 9999999999999999999]
# [public: true]
# [version: 9.4.4]
# [price: 0]
# [author: yuhualhh]
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
scripts = "云盘"

def printf(msg, level='INFO'):
    c = 32 if level in ['INFO', 'DEBUG'] else 33 if level in ['WARN', 'WARNING'] else 31
    sys.stderr.write(f"\033[{c}m[{level}] {str(msg)}\033[0m\n")
    sys.stderr.flush()

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
        self.ua = (
            'Mozilla/5.0 (Linux; Android 16; RMX5060 Build/BP2A.250605.015; wv) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/149.0.7827.13 '
            'Mobile Safari/537.36 MCloudApp/12.5.4 AppLanguage/zh-CN'
        )
        self.session.headers.update({'User-Agent': self.ua})  # 将UA设置到独立的 session 中
        parts = cookie_str.split("#")
        self.Authorization = parts[0].strip()
        self.account = phone or "未知"
        self.jwtHeaders = {
            'User-Agent': self.ua,
            'Accept': '*/*',
            'Host': 'caiyun.feixin.10086.cn:7071',
        }
    
    def close(self):
        """关闭此账号实例的 session"""
        if self.session:
            self.session.close()

    def send_request(self, url, headers=None, data=None, method='GET', cookies=None, retries=3):
        """
        使用此实例的 session 发送请求，并在请求前后增加随机延时
        增加了错误重试机制，确保在超时或异常时及时关闭连接并释放资源。
        """
        time.sleep(random.uniform(0.3, 0.7))
        for attempt in range(retries):
            try:
                if DEBUG:
                    printf(f"\n===== [REQUEST START] =====", "DEBUG")
                    printf(f"METHOD: {method} | URL: {url}", "DEBUG")
                    printf(f"HEADERS: {json.dumps(headers or {}, ensure_ascii=False)}", "DEBUG")
                    if data is not None:
                        printf(f"BODY(JSON): {json.dumps(data, ensure_ascii=False)}", "DEBUG")
                    if cookies is not None:
                        try:
                            printf(f"COOKIES: {json.dumps(cookies, ensure_ascii=False)}", "DEBUG")
                        except Exception:
                            printf(f"COOKIES: {str(cookies)}", "DEBUG")
    
                # 使用实例自身的 self.session
                with self.session.request(method, url, headers=headers, json=data, cookies=cookies, timeout=15) as response:
                    if DEBUG:
                        printf(f"----- [RESPONSE - Attempt {attempt + 1}] -----", "DEBUG")
                        printf(f"STATUS: {response.status_code}", "DEBUG")
                        printf(f"RSP HEADERS: {json.dumps(dict(response.headers), ensure_ascii=False)}", "DEBUG")
                        try:
                            printf(f"RSP BODY: {json.dumps(response.json(), ensure_ascii=False)}", "DEBUG")
                        except Exception:
                            printf(f"RSP BODY: {response.text}", "DEBUG")
                        printf(f"===== [REQUEST END] =====\n", "DEBUG")
    
                    response.raise_for_status()
                    return response.json()
            except (requests.Timeout, requests.RequestException, Exception) as e:
                if DEBUG:
                    printf(f"⚠️ Attempt {attempt + 1} Failed: {str(e)}", "WARN")
                if attempt < retries - 1:
                    time.sleep(1)
                else:
                    return {"error": f"请求失败: {str(e)}"}
    
    def sso(self):
        """刷新令牌，获取新的 ssoToken，区分CK失效与请求失败"""
        url = 'https://orches.yun.139.com/orchestration/auth-rebuild/token/v1.0/querySpecToken'
        headers = {
            'Authorization': self.Authorization,
            'Content-Type': 'application/json',
            'Accept': '*/*',
            'Host': 'orches.yun.139.com'
        }
        data = {"account": self.account, "toSourceId": "001005"}
        ret = self.send_request(url, headers=headers, data=data, method='POST')
        if not ret:
            return False, "网络请求失败"
        if ret.get("error"):
            error_msg = ret["error"]
            if "请求失败" in error_msg:
                return False, f"网络请求异常: {error_msg}"
            else:
                return False, error_msg
        if ret.get('success'):
            self.token = ret['data']['token']
            return True, "ok"
        else:
            message = ret.get('message', '未知错误')
            if any(keyword in message.lower() for keyword in ['unauthorized', 'invalid', 'expired', '无效', '过期', '失效']):
                return False, f"CK已失效: {message}"
            else:
                return False, f"请求异常: {message}"
    
    def jwt(self):
        """通过 ssoToken 获取 jwtToken"""
        if not self.token:
            return False, "无可用 ssoToken"
        url = f"https://caiyun.feixin.10086.cn:7071/portal/auth/tyrzLogin.action?ssoToken={self.token}"
        ret = self.send_request(url=url, headers=self.jwtHeaders, method='POST')
        if not ret:
            return False, "返回数据为空"
        if ret.get("error"):
            return False, ret["error"]
        if ret.get('code') != 0:
            return False, ret.get('msg', '获取jwtToken失败')
        self.jwtToken = ret['result']['token']
        self.jwtHeaders['jwtToken'] = self.jwtToken
        self.cookies['jwtToken'] = self.jwtToken
        return True, "ok"
    
    def receive(self):
        """查询云朵数量"""
        url = "https://m.mcloud.139.com/ycloud/signin/page/infoV3?client=app"
        headers = {
            'Host': 'm.mcloud.139.com',
            'Connection': 'keep-alive',
            'sec-ch-ua-platform': '"Android"',
            'Cache-Control': 'no-cache',
            'sec-ch-ua': '"Android WebView";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'showLoading': 'true',
            'appVersion': '12.5.4.0',
            'User-Agent': self.ua,
            'jwtToken': self.jwtToken,
            'activityId': 'sign_in_3',
            'Accept': '*/*',
            'X-Requested-With': 'com.chinamobile.mcloud',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://m.mcloud.139.com/portal/mobilecloud/index.html?path=newsignin&sourceid=1097&enableShare=1&token=YZsidssolgfdde1e1e1ba1a278ef83975b675337a6&targetSourceId=001005',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        ret = self.send_request(url, headers=headers, cookies=self.cookies)
        if not ret:
            return False, "返回数据为空"
        if ret.get("error"):
            return False, ret["error"]
        if ret.get('code') == 0 and ret.get('msg') == 'success':
            self.total_amount = ret.get("result", {}).get("total", 0)
            self.to_receive = ret.get("result", {}).get("toReceive", 0)
            return True, f"当前云朵数量: {self.total_amount}"
        else:
            return False, ret.get('msg', '未知错误')
    
    def get_pending_prizes(self):
        """获取待领取奖品列表"""
        if not self.jwtToken:
            return False, "无 jwtToken, 无法查询待领奖品"
        
        try:
            timestamp = str(int(time.time() * 1000))
            prize_url = f"https://caiyun.feixin.10086.cn/market/prizeApi/checkPrize/getUserPrizeLogPage?currPage=1&pageSize=15&_={timestamp}"
            
            ret = self.send_request(prize_url, headers=self.jwtHeaders, cookies=self.cookies)
            if not ret:
                return False, "返回数据为空"
            if ret.get("error"):
                return False, ret["error"]
            
            result = ret.get('result', {}).get('result', [])
            pending_prizes =[]
            
            for value in result:
                prize_name = value.get('prizeName')
                flag = value.get('flag')
                if flag == 1 and prize_name:  # flag=1表示待领取
                    expire_time = value.get('expireTime', '')
                    if expire_time and len(expire_time) >= 10:
                        # 截取前10位日期并将 '-' 替换为 '.' 以符合预期展示
                        expire_date = expire_time[:10].replace('-', '.')
                        prize_str = f"{prize_name},至{expire_date}失效"
                    else:
                        prize_str = prize_name
                    pending_prizes.append(prize_str)
            
            return True, pending_prizes
            
        except Exception as e:
            return False, f"查询待领奖品异常: {str(e)}"

    def get_today_cloud(self):
        """统计今日新增云朵数量（支持多页获取）"""
        if not self.jwtToken:
            return False, "无 jwtToken, 无法查询今日云朵"
        
        today_str = str(local_now().date())  # 北京时间的今日日期 (YYYY-MM-DD)
        total = 0
        page_number = 1
        page_size = 10  # 增大页面大小，减少请求次数
        
        while True:
            url = f"https://m.mcloud.139.com/ycloud/signin/public/cloudRecord?type=1&pageNumber={page_number}&pageSize={page_size}"
            headers = {
                'jwttoken': self.jwtToken,
                'Accept': '*/*'
            }
            ret = self.send_request(url, headers=headers, method='GET')
            if not ret:
                return False, "接口无响应"
            if ret.get("error"):
                return False, ret["error"]
            if ret.get('code') != 0:
                return False, ret.get('msg', '获取失败')
            
            result = ret.get("result", {})
            records = result.get("records", [])
            
            # 如果当前页没有记录，说明已经到最后一页了
            if not records:
                break
            
            # 统计当前页的今日云朵
            page_today_total = 0
            has_today_record = False
            
            for item in records:
                insert_time = item.get('inserttime', '')
                if insert_time:
                    # 处理 UTC 时间格式 "2025-08-09T20:14:26.000+00:00"
                    # 这个时间是UTC时间，需要转换为北京时间（UTC+8）才是图片中显示的实际领取时间
                    try:
                        from datetime import datetime, timezone, timedelta
                        # 解析UTC时间（格式如："2025-08-09T20:14:26.000+00:00"）
                        if insert_time.endswith('+00:00'):
                            utc_time = datetime.fromisoformat(insert_time)
                        else:
                            # 如果没有时区信息，假设是UTC时间
                            utc_time = datetime.fromisoformat(insert_time.replace('Z', ''))
                            utc_time = utc_time.replace(tzinfo=timezone.utc)
                        
                        # 转换为北京时间（UTC+8）
                        beijing_tz = timezone(timedelta(hours=8))
                        beijing_time = utc_time.astimezone(beijing_tz)
                        day = str(beijing_time.date())
                    except Exception as e:
                        # 兜底：直接取前10位（可能不准确但不会崩溃）
                        day = insert_time[:10]
                        print(f"时间解析失败: {insert_time}, 错误: {e}")  # 调试用
                else:
                    continue
                
                num = item.get('num', 0)
                if day == today_str and num > 0:
                    page_today_total += num
                    has_today_record = True
                elif day < today_str:
                    # 如果遇到了今天之前的记录，说明后续页面也不会有今天的记录了
                    # 因为记录是按时间倒序排列的
                    break
            
            total += page_today_total
            
            # 如果当前页没有今天的记录，或者遇到了今天之前的记录，就不需要继续查询了
            if not has_today_record:
                break
            
            # 检查是否还有下一页
            current_page = result.get("current", page_number)
            total_pages = result.get("pages", 1)
            if current_page >= total_pages:
                break
            
            page_number += 1
            
            # 防止无限循环，最多查询10页
            if page_number > 10:
                break
        
        self.today_num = total
        return True, f"今日云朵: {total}"

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
        try:
            middleware.bucketDel('yuhua_ydyp_password', matched_uid)
        except Exception:
            pass
        phone = middleware.bucketGet('yuhua_ydyp_phone', matched_uid) or "未知"
        phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
        auth_time = middleware.bucketGet('yuhua_ydyp_auth', matched_uid)
        if auth_time and auth_time > str(datetime.now().date()):
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
    phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone
    auth_time = middleware.bucketGet('yuhua_ydyp_auth', unique_id)
    now_date = datetime.now().date()
    
    if not auth_time:
        return f"【{phone_mask}】未授权"
        
    auth_date = datetime.strptime(auth_time, "%Y-%m-%d").date()
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
            need_relogin = any(keyword in msg1_str.lower() for keyword in['unauthorized', 'invalid', 'expired', 'authorization']) or any(keyword in msg1_str for keyword in ['无效', '过期', '失效'])
            if need_relogin:
                # 遇到SSO直接拒绝，强制触发底层刷新刷新
                ok_force, ck_str_force, force_msg = check_and_refresh_token(unique_id, force=True)
                if ok_force and ck_str_force:
                    yp.close()
                    yp = YP(ck_str_force, phone=phone)
                    ok1, msg1 = yp.sso()
                    if not ok1:
                        return f"【{phone_mask}】{msg1}"
                else:
                    return f"【{phone_mask}】强制刷新失败: {force_msg}"
            else:
                return f"【{phone_mask}】{msg1}"
            
        ok2, _ = yp.jwt()
        if not ok2:
            return f"【{phone_mask}】获取jwt失败"
            
        ok3, _ = yp.receive()
        if not ok3:
            return f"【{phone_mask}】查询云朵出错"
            
        ok4, _ = yp.get_today_cloud()
        today_str = str(yp.today_num) if ok4 else "查询失败"
        
        # 获取待领奖品
        ok5, prizes_result = yp.get_pending_prizes()
        if ok5 and prizes_result:
            if len(prizes_result) == 1:
                prizes_str = prizes_result[0]
            else:
                prizes_str = "\n" + "\n".join(prizes_result)
        else:
            prizes_str = "暂无"
        
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
    today_str = str(datetime.now().date())
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
    today_str = str(datetime.now().date())
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

def fetch_device_id():
    url = "https://slw.h5cmpassport.com:9090/deviceprofile/v4"
    headers = {
        "Host": "slw.h5cmpassport.com:9090",
        "Connection": "keep-alive",
        "sec-ch-ua-platform": '"Android"',
        "User-Agent": "Mozilla/5.0 (Linux; Android 16; RMX5060 Build/BP2A.250605.015; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/148.0.7778.49 Mobile Safari/537.36 MCloudApp/12.6.0 AppLanguage/zh-CN",
        "sec-ch-ua": '"Chromium";v="148", "Android WebView";v="148", "Not/A)Brand";v="99"',
        "Content-Type": "application/json;charset=UTF-8",
        "sec-ch-ua-mobile": "?1",
        "Accept": "*/*",
        "Origin": "https://m.mcloud.139.com",
        "X-Requested-With": "com.chinamobile.mcloud",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://m.mcloud.139.com/portal/yunClound/index.html?path=National_v12giftPop&sourceid=1003&enableShare=1&token=YZsidssolg06dc47929877172f1cdb7e5d2474d1b7",
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
        slide_headers = dict(yp_obj.jwtHeaders)
        slide_headers.update({
            'Host': 'm.mcloud.139.com',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'deviceId': 'B' + dev_id if not dev_id.startswith('B') else dev_id,
            'appVersion': '12.5.4.0',
            'activityId': 'sign_in_3',
            'showLoading': 'true',
            'sec-ch-ua-platform': '"Android"',
            'sec-ch-ua': '"Android WebView";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'Accept': '*/*',
            'Origin': 'https://m.mcloud.139.com',
            'X-Requested-With': 'com.chinamobile.mcloud',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://m.mcloud.139.com/portal/mobilecloud/index.html?path=newsignin&sourceid=1097&enableShare=1&token=YZsidssolgfdde1e1e1ba1a278ef83975b675337a6&targetSourceId=001005',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7'
        })
        slide_cookies = dict(yp_obj.cookies)

        resp = yp_obj.send_request(
            "https://m.mcloud.139.com/ycloud/auth-service/slide/getSlide",
            headers=slide_headers,
            cookies=slide_cookies,
            data={},
            method='POST'
        )

        if not resp or resp.get("code") != 0:
            if DEBUG:
                printf(f"getSlide失败: {resp}", "WARN")
            return None

        result = resp.get("result", {})
        puzzle_b64 = result.get("puzzle", "")
        picture_b64 = result.get("picture", "")

        if not puzzle_b64 or not picture_b64:
            if DEBUG:
                printf("getSlide响应中缺少图片数据", "WARN")
            return None

        # 调用 ddddocr 识别滑块偏移
        try:
            ocr_resp = get_global_session().post(
                DDDDOCR_API,
                json={"slidingImage": puzzle_b64, "backImage": picture_b64, "simpleTarget": True},
                timeout=15
            )
            offset = int(float(ocr_resp.json().get("result", 257)))
            if DEBUG:
                printf(f"滑块识别偏移量: {offset}", "DEBUG")
            return offset
        except Exception as e:
            if DEBUG:
                printf(f"ddddocr识别失败: {e}, 使用默认偏移257", "WARN")
            return 257

    except Exception as e:
        if DEBUG:
            printf(f"滑块验证流程异常: {e}", "WARN")
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
    possible_targets =[
        now.replace(hour=0, minute=0, second=0, microsecond=0),
        now.replace(hour=8, minute=0, second=0, microsecond=0),
        now.replace(hour=12, minute=0, second=0, microsecond=0),
        now.replace(hour=16, minute=0, second=0, microsecond=0),
        now.replace(hour=20, minute=0, second=0, microsecond=0)
    ]
    if now.hour >= 23:
        target_time = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        future_targets =[t for t in possible_targets if t > now]
        if not future_targets:
            target_time = min(possible_targets)
        else:
            target_time = min(future_targets, key=lambda t: t - now)
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
        if not auth_time or auth_time <= str(datetime.now().date()):
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
        
        ok2, _ = y.jwt()
        if not ok2: fail_reasons.append(f"【{phone_mask}】jwt获取失败"); continue
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
        import hashlib
        import urllib.parse
        import random
        
        target_deviceId = dev_id
        if not target_deviceId.startswith('B'):
            target_deviceId = 'B' + target_deviceId
        thumb_val = target_deviceId[1:]
        
        exchange_headers = dict(yobj.jwtHeaders)
        exchange_headers.update({
            'Host': 'm.mcloud.139.com',
            'Connection': 'keep-alive',
            'sec-ch-ua-platform': '"Android"',
            'Cache-Control': 'no-cache',
            'sec-ch-ua': '"Android WebView";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'deviceId': target_deviceId,
            'showLoading': 'true',
            'appVersion': '12.5.4.0',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 16; RMX5060 Build/BP2A.250605.015; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/149.0.7827.13 Safari/537.36 MCloudApp/12.5.4 AppLanguage/zh-CN',
            'activityId': 'sign_in_3',
            'Accept': '*/*',
            'X-Requested-With': 'com.chinamobile.mcloud',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://m.mcloud.139.com/portal/mobilecloud/index.html?path=newsignin&sourceid=1097&enableShare=1&token=YZsidssolgfdde1e1e1ba1a278ef83975b675337a6&targetSourceId=001005',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7'
        })
        
        exchange_cookies = dict(yobj.cookies)
        # 核心修复点：将手机号转换为小写MD5作为键名，与官方逻辑保持一致
        account_md5 = hashlib.md5(yobj.account.encode('utf-8')).hexdigest()
        exchange_cookies[f".thumbcache_{account_md5}"] = urllib.parse.quote(thumb_val)

        for attempt in range(1, 6):
            if STOP_EXCHANGE:
                return (phone_mask, pname, False, "已被手动停止", user_id, account_id)
            # 每次尝试前获取滑块偏移量
            puzzle_offset = solve_slide_captcha(yobj, dev_id)
            if puzzle_offset is None:
                puzzle_offset = 257
            exc_url = f"https://m.mcloud.139.com/ycloud/signin/page/exchangeV2?prizeId={pid}&client=app&clientVersion=12.5.4&puzzleOffset={puzzle_offset}&smsCode="
            resp = yobj.send_request(exc_url, headers=exchange_headers, cookies=exchange_cookies, method='GET')
            if resp and resp.get("code") == 0:
                return (phone_mask, pname, True, f"兑换成功(第{attempt}次)", user_id, account_id)
            else:
                if attempt < 5: time.sleep(0.5)
        msg = resp.get("msg", "兑换失败") if resp else "未知错误"
        if "活动太火爆啦" in msg or "锁定失败" in msg:
            msg += "。"
        return (phone_mask, pname, False, msg, user_id, account_id)
        
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
    if not auth_time or auth_time <= str(datetime.now().date()):
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
            
            import hashlib
            import urllib.parse
            import random
            
            ok_dev, dev_id = get_or_fetch_device_id(account)
            if not ok_dev:
                sender.reply(f"【{phone_mask}】{dev_id}")
                return
                
            target_deviceId = dev_id
            if not target_deviceId.startswith('B'):
                target_deviceId = 'B' + target_deviceId
            thumb_val = target_deviceId[1:]
            
            exchange_headers = dict(yp.jwtHeaders)
            exchange_headers.update({
                'Host': 'm.mcloud.139.com',
                'Connection': 'keep-alive',
                'sec-ch-ua-platform': '"Android"',
                'Cache-Control': 'no-cache',
                'sec-ch-ua': '"Android WebView";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'deviceId': target_deviceId,
                'showLoading': 'true',
                'appVersion': '12.5.4.0',
                'User-Agent': 'Mozilla/5.0 (Linux; Android 16; RMX5060 Build/BP2A.250605.015; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/149.0.7827.13 Safari/537.36 MCloudApp/12.5.4 AppLanguage/zh-CN',
                'activityId': 'sign_in_3',
                'Accept': '*/*',
                'X-Requested-With': 'com.chinamobile.mcloud',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Dest': 'empty',
                'Referer': 'https://m.mcloud.139.com/portal/mobilecloud/index.html?path=newsignin&sourceid=1097&enableShare=1&token=YZsidssolgfdde1e1e1ba1a278ef83975b675337a6&targetSourceId=001005',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7'
            })
            
            exchange_cookies = dict(yp.cookies)
            account_md5 = hashlib.md5(yp.account.encode('utf-8')).hexdigest()
            exchange_cookies[f".thumbcache_{account_md5}"] = urllib.parse.quote(thumb_val)

            # 获取滑块偏移量
            puzzle_offset = solve_slide_captcha(yp, dev_id)
            if puzzle_offset is None:
                puzzle_offset = 257
            exc_url = f"https://m.mcloud.139.com/ycloud/signin/page/exchangeV2?prizeId={found_pid}&client=app&clientVersion=12.5.4&puzzleOffset={puzzle_offset}&smsCode="
            resp = yp.send_request(exc_url, headers=exchange_headers, cookies=exchange_cookies, method='GET')
            if resp and resp.get("code") == 0:
                sender.reply(f"【{phone_mask}】兑换【{selected_product.get('prizeName')}】成功")
            else:
                msg = resp.get("msg", "兑换失败") if resp else "未知错误"
                if "活动太火爆啦" in msg or "锁定失败" in msg:
                    msg += "。"
                sender.reply(f"【{phone_mask}】{msg}")
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
            printf(f"RSP BODY: {sms_resp.text}", "DEBUG")

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
            printf(f"RSP BODY: {login_resp.text}", "DEBUG")

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
            try:
                middleware.bucketDel('yuhua_ydyp_password', matched_uid)
            except Exception:
                pass
            auth_time = middleware.bucketGet('yuhua_ydyp_auth', matched_uid)
            if auth_time and auth_time > str(datetime.now().date()):
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
            printf(f"RSP BODY: {login_resp.text}", "DEBUG")

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
            middleware.bucketSet('yuhua_ydyp_password', matched_uid, password)
            auth_time = middleware.bucketGet('yuhua_ydyp_auth', matched_uid)
            if auth_time and auth_time > str(datetime.now().date()):
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

def do_native_token_refresh(account_id, phone, current_auth):
    """底层原生刷新机制"""
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
            raw_token = data.get('data', {}).get('token')
            expire_time = data.get('data', {}).get('expireTime')
            
            if raw_token:
                # 重新组装完整的 Authorization
                new_auth_str = f"mobile:{phone}:{raw_token}"
                new_auth = f"Basic {base64.b64encode(new_auth_str.encode('utf-8')).decode('utf-8')}"
                
                # 更新本地数据库 (Token)
                new_ck_str = f"{new_auth}#{phone}"
                middleware.bucketSet('yuhua_ydyp_token', account_id, new_ck_str)
                
                # 更新本地数据库 (过期时间戳)
                try:
                    expire_seconds = int(float(expire_time))
                except Exception:
                    expire_seconds = 2592000
                expires_at = int(time.time() * 1000) + expire_seconds * 1000
                middleware.bucketSet('yuhua_ydyp_token_expire', account_id, str(expires_at))
                
                # 同步青龙环境变量
                add_to_qinglong(new_ck_str, account_id, phone)
                
                return True, new_ck_str
                
        return False, data.get('message') or data.get('msg') or "未知错误"
    except Exception as e:
        return False, str(e)

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
    
    expire_str = middleware.bucketGet('yuhua_ydyp_token_expire', account_id)
    now_ms = int(time.time() * 1000)
    
    need_refresh = force
    if not need_refresh:
        if not expire_str:
            need_refresh = True
        else:
            try:
                expires_at = int(expire_str)
                # 如果剩余有效期小于 24 小时 (86400000 毫秒)
                if expires_at - now_ms < 86400000:
                    need_refresh = True
            except Exception:
                need_refresh = True
                
    if need_refresh:
        ok, result = do_native_token_refresh(account_id, phone, current_auth)
        if ok:
            return True, result, "原生刷新成功"
        else:
            # 兜底：如果原生刷新失败（或未安装依赖），尝试使用原有的PHP账密续期
            relogin_ok, relogin_msg = _try_auto_password_relogin(account_id)
            if relogin_ok:
                new_ck = middleware.bucketGet('yuhua_ydyp_token', account_id)
                # 为兜底续期设置一个默认的长期有效时间
                middleware.bucketSet('yuhua_ydyp_token_expire', account_id, str(now_ms + 2592000000))
                return True, new_ck, "账密兜底刷新成功"
            else:
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
            printf(f"RSP BODY: {relogin_resp.text}", "DEBUG")

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

        auth_time = middleware.bucketGet('yuhua_ydyp_auth', account_id)
        if auth_time and auth_time > str(datetime.now().date()):
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
        today = str(datetime.now().date())
        if imtype == 'fake':
            pass
        else:
            main()
    except Exception as e:
        sender.reply(f"❌ 运行出错: {str(e)}")
    finally:
        close_global_session()