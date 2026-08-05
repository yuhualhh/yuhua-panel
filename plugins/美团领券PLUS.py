# [title: 美团领券PLUS]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@628ca207fcc92493bfdc7b376802df13d290a228/2025/04/18/0227ee80f756be5352c84c94d7f9cdf6.png]
# [rule: ^美团领券$|^美团刷白$|^美团充分$|^美团查分$|^美团加分$|^美团减分$|^释放支付锁$]
# [language: python]
# [disable:false]
# [public: true]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [author: yuhualhh]
# [open_source: false]
# [priority: 999999999999999998]
# [version: 2.1.9]
# [price: 0]
# [service: ]
# [description: ❶提供美团领券的插件，支持对接易支付平台收款、自定义各领券项目价格、管理员可对用户加扣分<br>❷扫码可查看各项目对应领券详情<img src="https://gcore.jsdelivr.net/gh/lhz03/img@21067eaf2abbb6e545cd04507cbcaba81aa51f66/2025/07/05/a55d418210371f7896545baa970b340a.png">]


# [param: {"required":true,"key":"yuhua_meituan.api_key","bool":false,"placeholder":"","name":"API秘钥","desc":"请前往 http://api.oroe.cn 注册获取"}]
# [param: {"required":true,"key":"yuhua_meituan.prices","bool":false,"placeholder":"-1|0.07|-1","name":"项目价格","desc":"自定义领券项目价格，目前有3个项目，各项目之间用英文符|分隔，当设置-1时表示关闭该项目，未配置价格则默认-1|0.07|-1"}]
# [param: {"required":false,"key":"yuhua_meituan.exchange_rate","bool":false,"placeholder":"1","name":"兑换比例","desc":"充值余额换算积分的比例，填1表示1元=1积分，填100表示1元=100积分，默认1"}]
# [param: {"required":false,"key":"yuhua_meituan.payment_lock_timeout","bool":false,"placeholder":"300","name":"支付超时","desc":"支付锁超时时间，防止支付状态被长期占用，默认300秒"}]
# [param: {"required":false,"key":"yuhua_meituan.min_recharge_amount","bool":false,"placeholder":"0.01","name":"充值阈值","desc":"自定义最低充值金额，默认0.01元"}]
# [param: {"required":false,"key":"yuhua_meituan.payment_mode","bool":false,"placeholder":"0","name":"支付模式","desc":"0=Autman内置支付，1=易支付"}]
# [param: {"required":false,"key":"yuhua_meituan.zsm","bool":false,"placeholder":"","name":"收款码子","desc":"微信Bot收款码直链"}]
# [param: {"required":false,"key":"yuhua_meituan.epay_url","bool":false,"placeholder":"","name":"易支付地址","desc":""}]
# [param: {"required":false,"key":"yuhua_meituan.epay_pid","bool":false,"placeholder":"","name":"易支付商户ID","desc":""}]
# [param: {"required":false,"key":"yuhua_meituan.epay_key","bool":false,"placeholder":"","name":"易支付商户密钥","desc":""}]
# [param: {"required":false,"key":"yuhua_meituan.epay_alipay","bool":true,"placeholder":"","name":"支付宝","desc":"是否启用易支付-支付宝通道收款"}]
# [param: {"required":false,"key":"yuhua_meituan.epay_wxpay","bool":true,"placeholder":"","name":"微信","desc":"是否启用易支付-微信通道收款"}]
# [param: {"required":false,"key":"yuhua_meituan.epay_qqpay","bool":true,"placeholder":"","name":"QQ","desc":"是否启用易支付-QQ通道收款"}]

import requests
import middleware
import json
import time
import re
import hashlib
import threading
from urllib.parse import quote
from bs4 import BeautifulSoup

# 全局变量
bucket_prefix = "yuhua_meituan"  # 插件数据桶前缀

# 支付锁管理
payment_lock_key = f"{bucket_prefix}_payment_lock"
payment_sessions_key = f"{bucket_prefix}_payment_sessions"  # 支付会话存储
user_locks = {}  # 用户积分操作锁
lock_manager = threading.Lock()  # 锁管理器

def get_user_lock(user_id):
    """获取用户专用锁"""
    with lock_manager:
        if user_id not in user_locks:
            user_locks[user_id] = threading.Lock()
        return user_locks[user_id]

def set_payment_lock(user_id, timeout_seconds=300):
    """设置支付锁"""
    import uuid
    session_id = str(uuid.uuid4())[:12]  # 生成会话ID
    lock_data = {
        'user_id': user_id,
        'timestamp': time.time(),
        'timeout': timeout_seconds,
        'session_id': session_id
    }
    middleware.bucketSet(bucket_prefix, payment_lock_key, json.dumps(lock_data))

    # 同时保存会话信息
    save_payment_session(user_id, session_id)

    return session_id

def get_payment_lock():
    """获取支付锁信息"""
    try:
        lock_data_str = middleware.bucketGet(bucket_prefix, payment_lock_key)
        if lock_data_str:
            return json.loads(lock_data_str)
        return None
    except:
        return None

def clear_payment_lock():
    """清除支付锁"""
    try:
        middleware.bucketDel(bucket_prefix, payment_lock_key)
    except Exception:
        pass

def save_payment_session(user_id, session_id):
    """保存支付会话"""
    try:
        sessions_data_str = middleware.bucketGet(bucket_prefix, payment_sessions_key)
        if sessions_data_str:
            sessions = json.loads(sessions_data_str)
        else:
            sessions = {}

        sessions[session_id] = {
            'user_id': user_id,
            'timestamp': time.time()
        }

        middleware.bucketSet(bucket_prefix, payment_sessions_key, json.dumps(sessions))
    except:
        pass

def remove_payment_session(session_id):
    """移除支付会话"""
    try:
        sessions_data_str = middleware.bucketGet(bucket_prefix, payment_sessions_key)
        if sessions_data_str:
            sessions = json.loads(sessions_data_str)
            if session_id in sessions:
                del sessions[session_id]
                middleware.bucketSet(bucket_prefix, payment_sessions_key, json.dumps(sessions))
    except:
        pass

def cleanup_expired_sessions():
    """清理过期的支付会话（超过1小时）"""
    try:
        sessions_data_str = middleware.bucketGet(bucket_prefix, payment_sessions_key)
        if not sessions_data_str:
            return

        sessions = json.loads(sessions_data_str)
        current_time = time.time()
        expired_sessions = []

        for session_id, session_data in sessions.items():
            if current_time - session_data.get('timestamp', 0) > 3600:  # 1小时过期
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del sessions[session_id]

        if expired_sessions:
            middleware.bucketSet(bucket_prefix, payment_sessions_key, json.dumps(sessions))
    except:
        pass

def is_payment_lock_expired(lock_data, timeout_seconds):
    """检查支付锁是否过期"""
    if not lock_data:
        return True
    current_time = time.time()
    lock_time = lock_data.get('timestamp', 0)
    return (current_time - lock_time) > timeout_seconds

def check_and_acquire_payment_lock(user_id, config):
    """检查并获取支付锁"""
    timeout_seconds = int(config.get('payment_lock_timeout', 300))

    # 获取当前锁状态
    current_lock = get_payment_lock()

    # 检查是否有锁且未过期
    if current_lock and not is_payment_lock_expired(current_lock, timeout_seconds):
        if current_lock.get('user_id') == user_id:
            # 同一用户，返回现有会话ID
            return current_lock.get('session_id')
        else:
            # 其他用户占用
            return None

    # 没有锁或已过期，设置新锁
    session_id = set_payment_lock(user_id, timeout_seconds)
    return session_id

def validate_payment_session(user_id, session_id):
    """验证支付会话是否有效"""
    try:
        # 先清理过期会话
        cleanup_expired_sessions()

        # 检查会话是否存在
        sessions_data_str = middleware.bucketGet(bucket_prefix, payment_sessions_key)
        if not sessions_data_str:
            return False

        sessions = json.loads(sessions_data_str)
        session_data = sessions.get(session_id)

        if not session_data:
            return False

        # 验证用户ID匹配
        if session_data.get('user_id') != user_id:
            return False

        # 检查当前支付锁状态
        current_lock = get_payment_lock()

        # 情况1：当前锁存在且是同一个会话 - 会话有效
        if current_lock and current_lock.get('session_id') == session_id:
            return True

        # 情况2：当前锁不存在 - 说明被管理员释放了，所有旧会话都失效
        if not current_lock:
            return False

        # 情况3：当前锁存在但是不同的会话 - 说明有新用户获得了锁，旧会话失效
        if current_lock and current_lock.get('session_id') != session_id:
            return False

        return False
    except:
        return False

def get_config():
    """获取插件配置"""
    try:
        # 获取支付模式，默认为0（Autman内置支付）
        payment_mode = middleware.bucketGet(bucket_prefix, 'payment_mode') or '0'
        use_epay = payment_mode == '1'

        # 获取兑换比例，默认为1（1元=1积分）
        exchange_rate = middleware.bucketGet(bucket_prefix, 'exchange_rate') or '1'

        # 验证兑换比例格式
        try:
            exchange_rate_float = float(exchange_rate)
            if exchange_rate_float <= 0:
                exchange_rate_float = 1.0
        except:
            exchange_rate_float = 1.0

        config = {
            'use_epay': use_epay,
            'payment_mode': payment_mode,
            'exchange_rate': exchange_rate_float,
            'epay_url': middleware.bucketGet(bucket_prefix, 'epay_url') or '',
            'epay_pid': middleware.bucketGet(bucket_prefix, 'epay_pid') or '',
            'epay_key': middleware.bucketGet(bucket_prefix, 'epay_key') or '',
            'epay_alipay': middleware.bucketGet(bucket_prefix, 'epay_alipay') == 'true',
            'epay_wxpay': middleware.bucketGet(bucket_prefix, 'epay_wxpay') == 'true',
            'epay_qqpay': middleware.bucketGet(bucket_prefix, 'epay_qqpay') == 'true',
            'zsm': middleware.bucketGet(bucket_prefix, 'zsm') or '',
            'prices': middleware.bucketGet(bucket_prefix, 'prices') or '',
            'api_key': middleware.bucketGet(bucket_prefix, 'api_key') or '',
            'api_url': 'http://api.oroe.cn',  # 内置API地址
            'payment_lock_timeout': middleware.bucketGet(bucket_prefix, 'payment_lock_timeout') or '300',
            'min_recharge_amount': float(middleware.bucketGet(bucket_prefix, 'min_recharge_amount') or '0.01'),
        }
        return config
    except Exception as e:
        # 配置获取失败时返回默认配置
        return {
            'use_epay': False,
            'payment_mode': '0',
            'exchange_rate': 1.0,
            'epay_url': '',
            'epay_pid': '',
            'epay_key': '',
            'epay_alipay': False,
            'epay_wxpay': False,
            'epay_qqpay': False,
            'zsm': '',
            'prices': '',
            'api_key': '',
            'api_url': 'http://api.oroe.cn',
            'payment_lock_timeout': '300',
            'min_recharge_amount': 0.01,
        }

def parse_prices(price_str):
    """解析收费价格配置"""
    TOTAL_PROJECTS = 3
    DEFAULT_PRICE = 88.0
    prices = []
    price_parts = price_str.split('|') if price_str else []
    for i in range(TOTAL_PROJECTS):
        if i < len(price_parts):
            try:
                price = float(price_parts[i])
                prices.append(price)
            except ValueError:
                prices.append(DEFAULT_PRICE)
        else:
            prices.append(DEFAULT_PRICE)
    return prices

def format_price_superscript(price):
    """将价格转换为角标格式"""
    if price == 0:
        return "ᶠʳᵉᵉ"

    # 数字角标映射
    superscript_map = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹'
    }

    # 格式化价格为字符串，保留两位小数
    price_str = f"{price:.2f}"

    # 转换为角标格式
    result = ""
    for char in price_str:
        if char == '.':
            result += "∙"  # 使用子弹运算符替代小数点
        elif char in superscript_map:
            result += superscript_map[char]
        else:
            result += char  # 保留其他字符（虽然在价格中不应该出现）

    return result

def get_user_points(user_id):
    """获取用户积分"""
    try:
        points = middleware.bucketGet(f'{bucket_prefix}_points', str(user_id))
        if points:
            # 严格限制到小数点后两位
            return round(float(points), 2)
        return 0.0
    except:
        return 0.0

def set_user_points(user_id, points):
    """设置用户积分"""
    try:
        # 严格限制到小数点后两位
        rounded_points = round(float(points), 2)
        middleware.bucketSet(f'{bucket_prefix}_points', str(user_id), str(rounded_points))
        return True
    except:
        return False

def add_user_points(user_id, points):
    """线程安全的增加用户积分"""
    user_lock = get_user_lock(user_id)
    with user_lock:
        try:
            current_points = get_user_points(user_id)
            # 严格限制到小数点后两位
            points_to_add = round(float(points), 2)
            new_points = round(current_points + points_to_add, 2)
            return set_user_points(user_id, new_points)
        except:
            return False

def deduct_user_points(user_id, points):
    """线程安全的扣除用户积分"""
    user_lock = get_user_lock(user_id)
    with user_lock:
        try:
            current_points = get_user_points(user_id)
            # 严格限制到小数点后两位
            points_to_deduct = round(float(points), 2)
            if current_points >= points_to_deduct:
                new_points = round(current_points - points_to_deduct, 2)
                return set_user_points(user_id, new_points)
            return False
        except:
            return False

def get_public_ip():
    """获取公网IP地址"""
    try:
        # 尝试从多个源获取，增加成功率
        sources = [
            "https://checkip.amazonaws.com",
            "https://icanhazip.com",
            "https://ifconfig.me/ip"
        ]
        for url in sources:
            try:
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    ip = response.text.strip()
                    # 简单的IP格式验证
                    if 6 < len(ip) < 16 and ip.count('.') == 3:
                        return ip
            except:
                continue
        return "127.0.0.1" # 所有源都失败后返回默认值
    except Exception:
        return "127.0.0.1"

def create_epay_sign(params, merchant_key):
    """创建易支付签名 - 参考Yzyxmm.py的实现"""
    # 过滤空值和sign相关字段
    filtered_params = {k: str(v) for k, v in params.items() if v and k != 'sign' and k != 'sign_type'}
    # 按键名排序
    sorted_params = dict(sorted(filtered_params.items()))
    # 生成签名字符串
    sign_str = '&'.join([f"{k}={v}" for k, v in sorted_params.items()])
    # 添加商户密钥
    sign_str += merchant_key
    # 生成MD5签名
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

def call_meituan_api(cookie, project_type):
    """调用美团领券API - (已优化重试和超时)"""
    config = get_config()
    api_key = config['api_key']
    api_url = config['api_url']

    if not api_key:
        return {"code": -1, "msg": "未配置API秘钥"}
    if not api_url:
        return {"code": -1, "msg": "未配置API系统地址"}

    api_endpoints = {
        1: "meituanvc",
        2: "meituan259",
        3: "meituanza"
    }
    endpoint = api_endpoints.get(project_type, "meituanza")
    url = f"{api_url.rstrip('/')}/API/{endpoint}.php"
    data = {"apikey": api_key, "MeiTuanCookie": cookie}

    # --- 新增：重试逻辑 ---
    for attempt in range(3):
        try:
            # 第一次尝试用JSON，后续也用JSON
            response = requests.post(
                url, 
                json=data, 
                # --- 修改：分离连接和读取超时 ---
                timeout=(5, 30)  # 5秒连接超时, 30秒读取超时
            )

            if response.status_code == 404 or "404 Not Found" in response.text:
                return {"code": -1, "msg": "请求的资源未找到，请检查您的请求地址是否正确"}
            if response.status_code == 402:
                return {"code": -1, "msg": "API秘钥余额不足，请联系管理员处理", "balance_error": True}

            # 如果响应码不是200，但不是上述特定错误，则尝试用表单格式
            if response.status_code != 200:
                 response = requests.post(url, data=data, timeout=(5, 30))
                 # 再次检查
                 if response.status_code == 402:
                    return {"code": -1, "msg": "API秘钥余额不足，请联系管理员处理", "balance_error": True}


            # 只要有一次成功，就返回结果
            return response.json()

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"美团API请求失败，第 {attempt + 1} 次尝试... 错误: {e}")
            if attempt < 2:  # 如果不是最后一次尝试，则等待后重试
                time.sleep(attempt + 1) # 等待1秒, 2秒
            else: # 最后一次尝试失败
                return {"code": -1, "msg": f"网络请求失败: {str(e)}"}
        except Exception as e:
            # 对于其他未知异常，不重试，直接返回错误
            return {"code": -1, "msg": f"请求异常: {str(e)}"}
            
    # 如果循环结束仍未成功
    return {"code": -1, "msg": "服务暂时无法连接，请稍后再试"}

def call_whitelist_api(shop_link):
    """调用美团刷白API - (已优化重试和超时)"""
    config = get_config()
    api_key = config['api_key']
    api_url = config['api_url']

    if not api_key:
        return {"code": -1, "msg": "未配置API秘钥"}
    if not api_url:
        return {"code": -1, "msg": "未配置API系统地址"}
    if "http://dpurl.cn/" not in shop_link:
        return {"code": -1, "msg": "无效的店铺链接"}

    url = f"{api_url.rstrip('/')}/API/whitelist.php"
    data = {"apikey": api_key, "url": shop_link}

    # --- 新增：重试逻辑 ---
    for attempt in range(3):
        try:
            # 直接使用表单格式请求
            response = requests.post(
                url, 
                data=data, 
                # --- 修改：分离连接和读取超时 ---
                timeout=(5, 30) # 刷白可能较慢，给更长的读取时间
            )

            if response.status_code == 404 or "404 Not Found" in response.text:
                return {"code": -1, "msg": "请求的资源未找到，请检查您的请求地址是否正确"}
            if response.status_code == 402:
                return {"code": -1, "msg": "API秘钥余额不足，请联系管理员处理", "balance_error": True}
            
            # 检查响应内容
            if response.status_code == 200 and "No input file specified" not in response.text:
                try:
                    return response.json()
                except:
                    if "成功" in response.text or "SUCCESS" in response.text.upper():
                        return {"code": 0, "msg": "刷白成功"}
                    else:
                        return {"code": -1, "msg": f"API响应格式错误: {response.text[:100]}"}
            
            # 如果不满足成功条件，视为临时失败，进行重试
            print(f"刷白API响应异常，第 {attempt + 1} 次尝试...")
            time.sleep(attempt + 1)


        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"刷白API请求失败，第 {attempt + 1} 次尝试... 错误: {e}")
            if attempt < 2:
                time.sleep(attempt + 1)
            else:
                return {"code": -1, "msg": f"网络请求失败: {str(e)}"}
        except Exception as e:
            return {"code": -1, "msg": f"请求异常: {str(e)}"}
            
    # 如果循环结束仍未成功
    return {"code": -1, "msg": "刷白服务暂时无法连接，请稍后再试"}

def generate_unique_order_id(user_id):
    """生成唯一订单ID"""
    import uuid
    timestamp = int(time.time() * 1000)  # 毫秒级时间戳
    random_part = str(uuid.uuid4())[:8]  # UUID前8位
    user_suffix = user_id[-4:] if len(user_id) >= 4 else user_id
    return f"MT{timestamp}{user_suffix}{random_part}"

def create_epay_order(config, order_id, amount, payment_method):
    """创建易支付订单 - (已优化重试和超时)"""
    params = {
        'pid': config['epay_pid'],
        'type': payment_method,
        'out_trade_no': order_id,
        'notify_url': f"{config['epay_url']}/notify_url.php",
        'return_url': f"{config['epay_url']}/return_url.php",
        'name': '美团积分充值',
        'money': f"{float(amount):.2f}",
        'clientip': get_public_ip(),
        'sign_type': 'MD5'
    }
    params['sign'] = create_epay_sign(params, config['epay_key'])

    # --- 新增：重试逻辑 ---
    for attempt in range(3):
        try:
            response = requests.post(
                f"{config['epay_url']}/mapi.php", 
                data=params, 
                # --- 修改：分离连接和读取超时 ---
                timeout=(5, 30)
            )
            response_json = response.json()

            if response_json.get('code') == 1:
                # 增强兼容性：尝试从多个可能的键中获取支付链接
                payment_url = response_json.get('qrcode') or \
                              response_json.get('payurl') or \
                              response_json.get('qrurl') or \
                              ''
                return {
                    'code': 0,
                    'qr_code': payment_url,
                    'order_id': order_id
                }
            else:
                error_msg = response_json.get('msg', '未知错误')
                return {'code': -1, 'msg': f"创建订单失败: {error_msg}"}

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"创建易支付订单失败，第 {attempt + 1} 次尝试... 错误: {e}")
            if attempt < 2:
                time.sleep(attempt + 1)
            else:
                return {'code': -1, 'msg': f'创建订单网络异常: {str(e)}'}
        except Exception as e:
            return {'code': -1, 'msg': f'创建订单异常: {str(e)}'}
            
    return {'code': -1, 'msg': '易支付服务暂时无法连接'}

def _validate_epay_params(config, order_id):
    """验证易支付参数的安全性"""
    try:
        # 验证必要参数
        if not config.get('epay_url') or not config.get('epay_pid') or not config.get('epay_key'):
            return False

        # 验证订单ID格式（防止注入攻击）
        if not order_id or len(order_id) > 100 or not order_id.replace('_', '').replace('-', '').isalnum():
            return False

        # 验证URL格式
        epay_url = config['epay_url']
        if not epay_url.startswith(('http://', 'https://')):
            return False

        # 验证PID格式（应该是数字）
        epay_pid = config['epay_pid']
        if not epay_pid.isdigit() or len(epay_pid) > 20:
            return False

        # 验证KEY长度（防止过短的密钥）
        epay_key = config['epay_key']
        if len(epay_key) < 16 or len(epay_key) > 100:
            return False

        return True
    except Exception:
        return False

def _validate_v1_payment_success(response_data):
    """V1接口支付成功验证 - 通用兼容版本"""
    try:
        # 基础验证：code必须为1（查询成功）
        if response_data.get('code') != 1:
            return False

        # 核心验证：api_trade_no存在且不为空表示支付成功
        api_trade_no = response_data.get('api_trade_no')
        if not api_trade_no:
            return False

        # 转换为字符串并去除空白
        api_trade_no_str = str(api_trade_no).strip()
        if not api_trade_no_str or api_trade_no_str.lower() in ['null', 'none', '']:
            return False

        # 宽松的长度验证（适应不同平台）
        if len(api_trade_no_str) < 5:  # 太短可能是无效值
            return False

        return True
    except Exception:
        return False

def _validate_v1_payment_pending(response_data):
    """基于实际日志分析的V1接口未支付验证"""
    try:
        # 基础验证：code必须为1（查询成功）
        if response_data.get('code') != 1:
            return False

        # 核心验证：api_trade_no为空或null表示未支付
        api_trade_no = response_data.get('api_trade_no')
        if api_trade_no and str(api_trade_no).strip():
            return False  # 有交易号说明已支付

        # 状态验证：如果有status字段，应该不是1
        status = response_data.get('status')
        if status == 1:
            return False  # status=1通常表示已支付

        return True
    except Exception:
        return False

def _validate_payment_amount(money, min_amount=None):
    """通用金额验证 - 基于两个平台的实际日志"""
    try:
        if not money:
            return False

        # 转换为浮点数
        money_float = float(money)

        # 基础验证：金额必须大于0
        if money_float <= 0:
            return False

        # 充值阈值验证
        if min_amount is not None and money_float < min_amount:
            return False

        # 合理范围验证：防止异常大额
        if money_float > 50000:  # 5万元以上可能有问题
            return False

        return True
    except Exception:
        return False

def _validate_payment_response_integrity(response_data, interface_name):
    """基于实际支付日志的响应完整性验证 - 简化版本"""
    try:
        # V1接口的基础验证
        if 'V1接口' in interface_name:
            # 只检查最基础的字段
            if 'code' not in response_data:
                return False

            # 如果声称支付成功，检查是否有交易号
            if response_data.get('api_trade_no'):
                api_trade_no = str(response_data.get('api_trade_no')).strip()
                # 宽松验证：只要不是空值就认为有效
                if not api_trade_no or api_trade_no.lower() in ['null', 'none', '']:
                    return False

        # V2接口的基础验证
        elif 'V2接口' in interface_name:
            if response_data.get('code') == 1:
                # 检查是否有data字段
                if 'data' not in response_data:
                    return False

        return True
    except Exception:
        return False

def check_epay_order_status(config, order_id):
    """检查易支付订单状态 - 通用兼容所有易支付平台"""

    # 安全验证
    if not _validate_epay_params(config, order_id):
        return {'code': -1, 'msg': '参数验证失败'}

    # 获取充值阈值
    min_recharge_amount = config.get('min_recharge_amount', 0.01)

    epay_url = config['epay_url']

    # 定义通用易支付接口配置
    interface_configs = [
        {
            'name': 'V2接口(新版易支付)',
            'method': 'POST',
            'url': f"{epay_url}/api/pay/chaOrder",
            'data': {
                'out_trade_no': order_id,
                'id': config['epay_pid'],
                'key': config['epay_key']
            },
            'headers': {'server': '1'},
            'success_check': lambda r: r.get('code') == 1 and r.get('data', {}).get('status') == 1,
            'money_field': lambda r: r.get('data', {}).get('truemoney', '0.00'),
            'unpaid_check': lambda r: r.get('code') == 1 and r.get('data', {}).get('status') != 1,
            'error_indicators': ['接口方法不存在', 'method not found', 'api not found']
        },
        {
            'name': 'V1接口(经典易支付)',
            'method': 'GET',
            'url': f"{epay_url}/api.php",
            'params': {
                'act': 'order',
                'pid': config['epay_pid'],
                'key': config['epay_key'],
                'out_trade_no': order_id
            },
            'success_check': _validate_v1_payment_success,
            'money_field': lambda r: r.get('money', '0.00'),
            'unpaid_check': _validate_v1_payment_pending,
            'error_indicators': ['act参数错误', 'action not found', 'invalid act']
        },
        {
            'name': 'V1接口变体(POST方式)',
            'method': 'POST',
            'url': f"{epay_url}/api.php",
            'data': {
                'act': 'order',
                'pid': config['epay_pid'],
                'key': config['epay_key'],
                'out_trade_no': order_id
            },
            'success_check': _validate_v1_payment_success,
            'money_field': lambda r: r.get('money', '0.00'),
            'unpaid_check': _validate_v1_payment_pending,
            'error_indicators': ['act参数错误', 'action not found', 'invalid act']
        }
    ]

    # 依次尝试所有接口格式（限制尝试次数防止滥用）
    max_attempts = 3  # 最多尝试3个接口
    attempt_count = 0

    for interface in interface_configs:
        if attempt_count >= max_attempts:
            break

        try:
            attempt_count += 1
            result = _try_epay_interface(interface, order_id, min_recharge_amount)

            if result['code'] == 0:  # 支付成功
                return result
            elif result['code'] == -1:  # 未支付
                return result
            elif result['code'] == -999:  # 接口不可用，尝试下一个
                continue
            else:  # 其他错误
                continue
        except Exception:
            continue

    return {'code': -1, 'msg': '所有易支付接口都无法使用，请检查平台兼容性和配置'}

def _try_epay_interface(interface_config, order_id, min_recharge_amount=0.01):
    """尝试指定的易支付接口格式"""
    try:
        interface_name = interface_config['name']

        # 发送请求
        if interface_config['method'] == 'POST':
            if 'data' in interface_config:
                response = requests.post(
                    interface_config['url'],
                    data=interface_config['data'],
                    headers=interface_config.get('headers', {}),
                    timeout=10
                )
            else:
                response = requests.post(
                    interface_config['url'],
                    headers=interface_config.get('headers', {}),
                    timeout=10
                )
        else:  # GET
            response = requests.get(
                interface_config['url'],
                params=interface_config.get('params', {}),
                timeout=10
            )

        # 解析响应
        try:
            result = response.json()
        except:
            return {'code': -999, 'msg': '响应格式错误'}

        # 检查是否是接口不存在的错误
        response_text = response.text.lower()
        for error_indicator in interface_config.get('error_indicators', []):
            if error_indicator.lower() in response_text:
                return {'code': -999, 'msg': f'接口不存在: {error_indicator}'}

        # 检查支付成功
        if interface_config['success_check'](result):
            money = interface_config['money_field'](result)

            # 多重验证
            if _validate_payment_amount(money, min_recharge_amount):
                # 双重验证：检查响应数据的完整性
                if _validate_payment_response_integrity(result, interface_name):
                    return {'code': 0, 'msg': '支付成功', 'money': money}
                else:
                    return {'code': -1, 'msg': '响应数据异常'}
            else:
                return {'code': -1, 'msg': f'支付金额低于最低充值阈值{min_recharge_amount}元'}

        # 检查未支付
        if interface_config['unpaid_check'](result):
            return {'code': -1, 'msg': '未支付'}

        # 其他情况
        error_msg = result.get('msg', result.get('message', '未知错误'))
        return {'code': -1, 'msg': f'{interface_name}查询失败: {error_msg}'}

    except Exception:
        return {'code': -999, 'msg': f'接口异常'}

def handle_recharge(sender, user_id):
    """处理美团充分指令"""
    config = get_config()

    sender.reply("""=====美团充分=====
请输入充值金额
------------------
回复数字设置
回复"q"退出""")

    # 获取充值金额
    amount_input = sender.input(60000, 0, False)
    if not amount_input:
        sender.reply("❌ 输入超时")
        return

    if str(amount_input).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return

    try:
        amount = float(str(amount_input).strip())
        # 严格限制到小数点后两位
        amount = round(amount, 2)
        if amount <= 0:
            sender.reply("❌ 充值金额必须大于0")
            return

        # 检查充值阈值
        min_amount = config['min_recharge_amount']
        if amount < min_amount:
            sender.reply(f"❌ 充值金额不能低于{min_amount}元")
            return
    except ValueError:
        sender.reply("❌ 请输入有效的数字")
        return

    # 选择支付方式
    if config['use_epay']:
        handle_epay_recharge(sender, user_id, amount, config)
    else:
        handle_traditional_recharge(sender, user_id, amount, config)

def handle_traditional_recharge(sender, user_id, amount, config):
    """处理传统收款码充值"""
    if not config['zsm']:
        sender.reply("❌ 未配置收款码，请联系管理员")
        return

    # 检查并获取支付锁
    session_id = check_and_acquire_payment_lock(user_id, config)
    if not session_id:
        current_lock = get_payment_lock()
        timeout_seconds = int(config.get('payment_lock_timeout', 300))
        remaining_time = int(timeout_seconds - (time.time() - current_lock.get('timestamp', 0)))

        sender.reply(f"""=====支付繁忙=====
❌ 当前有其他用户正在支付
⏰ 预计 {remaining_time} 秒后可重试
💡 管理员可发送"释放支付锁"强制解除
==================""")
        return

    try:
        # 计算获得的积分
        points_to_get = round(amount * config['exchange_rate'], 2)

        sender.reply(f"""=====扫码支付=====
💰 充值金额: {amount}元
🎯 获得积分: {points_to_get}
------------------
请在120秒内完成
回复"q"退出""")

        sender.replyImage(config['zsm'])

        # 等待支付
        payment_result = sender.waitPay("q", 120 * 1000)

        if str(payment_result).lower() == 'q':
            sender.reply("✅ 已取消操作")
            return

        # 验证支付会话是否仍然有效
        if not validate_payment_session(user_id, session_id):
            current_lock = get_payment_lock()
            current_session = current_lock.get('session_id') if current_lock else 'None'
            current_user = current_lock.get('user_id') if current_lock else 'None'
            sender.reply(f"""=====支付会话失效=====
❌ 支付会话已失效
💡 可能是管理员释放了支付锁
🔄 请重新发起充值
------------------
🔍 调试信息：
🤪 用户ID: {user_id}
🪁 用户会话: {session_id[:8]}
✨ 当前用户: {current_user}
💥 当前会话: {current_session[:8] if current_session != 'None' else 'None'}
==================""")
            return

        # 解析支付结果
        if isinstance(payment_result, str):
            payment_data = json.loads(payment_result)
        else:
            payment_data = payment_result

        paid_money = float(payment_data.get('Money', payment_data.get('money', 0)))

        if paid_money < amount:
            sender.reply(f"""=====支付失败=====
❌ 支付金额不足
------------------
💰 应付: {amount}元
💵 实付: {paid_money}元
==================""")
            return

        # 支付成功，增加积分
        points_to_add = round(amount * config['exchange_rate'], 2)
        if add_user_points(user_id, points_to_add):
            current_points = get_user_points(user_id)
            sender.reply(f"""=====充值成功=====
💰 充值金额: {amount}元
🎯 获得积分: {points_to_add}
💎 当前积分: {current_points}
🔍 会话ID: {session_id[:8]}
==================""")
        else:
            sender.reply("❌ 积分增加失败，请联系管理员")

    except Exception as e:
        sender.reply(f"""=====支付异常=====
❌ 支付验证失败
------------------
⚠️ 错误: {str(e)[:50]}
==================""")
    finally:
        # 支付完成，只清理自己的会话和锁（如果锁还是自己的）
        current_lock = get_payment_lock()
        if current_lock and current_lock.get('session_id') == session_id:
            # 只有当前锁还是自己的时候才清除
            clear_payment_lock()
        # 总是清理自己的会话
        remove_payment_session(session_id)

def handle_epay_recharge(sender, user_id, amount, config):
    """处理易支付充值"""
    # 检查易支付配置
    if not config['epay_url'] or not config['epay_pid'] or not config['epay_key']:
        sender.reply("❌ 易支付未完整配置，请联系管理员")
        return

    # 验证易支付URL格式
    epay_url = config['epay_url'].strip()
    if not epay_url.startswith(('http://', 'https://')):
        sender.reply("❌ 易支付地址格式错误，请联系管理员")
        return

    # 检查并获取支付锁
    session_id = check_and_acquire_payment_lock(user_id, config)
    if not session_id:
        current_lock = get_payment_lock()
        timeout_seconds = int(config.get('payment_lock_timeout', 300))
        remaining_time = int(timeout_seconds - (time.time() - current_lock.get('timestamp', 0)))

        sender.reply(f"""=====支付繁忙=====
❌ 当前有其他用户正在支付
⏰ 预计 {remaining_time} 秒后可重试
💡 管理员可发送"释放支付锁"强制解除
==================""")
        return

    try:
        # 显示支付方式选择
        payment_options = []
        payment_methods = []

        if config['epay_alipay']:
            payment_options.append("[1] 支付宝")
            payment_methods.append(("alipay", "支付宝"))
        if config['epay_wxpay']:
            payment_options.append("[2] 微信")
            payment_methods.append(("wxpay", "微信"))
        if config['epay_qqpay']:
            payment_options.append("[3] QQ")
            payment_methods.append(("qqpay", "QQ"))

        if not payment_options:
            sender.reply("❌ 未启用任何支付方式，请联系管理员")
            return

        # 计算获得的积分
        points_to_get = round(amount * config['exchange_rate'], 2)

        payment_menu = f"""=====支付方式=====
💰 充值金额: {amount}元
🎯 获得积分: {points_to_get}
------------------
{chr(10).join(payment_options)}
------------------
回复数字选择
回复"q"退出"""

        sender.reply(payment_menu)

        # 获取支付方式选择
        choice = sender.input(60000, 0, False)
        if not choice:
            sender.reply("❌ 超时已退出")
            return

        if str(choice).lower() == 'q':
            sender.reply("✅ 已取消操作")
            return

        # 解析支付方式
        try:
            choice_num = int(str(choice))
            if choice_num < 1 or choice_num > len(payment_methods):
                sender.reply("❌ 请选择有效的支付方式")
                return

            payment_method, payment_name = payment_methods[choice_num - 1]

        except ValueError:
            sender.reply("❌ 请输入有效的数字")
            return

        # 创建唯一订单ID
        order_id = generate_unique_order_id(user_id)

#        sender.reply(f"""=====支付订单=====
#💰 充值金额: {amount}元
#💳 支付方式: {payment_name}
#📋 订单编号: {order_id}
#==================""")

        # 调用真实的易支付API创建订单
        epay_result = create_epay_order(config, order_id, amount, payment_method)

        if epay_result.get('code') != 0:
            error_msg = epay_result.get('msg', '未知错误')
            sender.reply(f"""=====创建订单失败=====
❌ {error_msg}
==================""")
            return

        qr_code_url = epay_result.get('qr_code', '')

        points_to_get = round(amount * config['exchange_rate'], 2)

        sender.reply(f"""=====支付信息=====
💰 金额: {amount}元
🎯 积分: {points_to_get}
💳 方式: {payment_name}
📋 订单: {order_id}
------------------
请在240秒内完成
回复"q"退出""")

        # 直接显示二维码（参考Yzyxmm.py的实现）
        if qr_code_url:
            sender.replyImage(f"https://api.pwmqr.com/qrcode/create/?url={quote(qr_code_url)}")
        else:
            sender.reply("❌ 二维码生成失败")
            return

        # 轮询检查支付状态（参考小米钱包插件的取消机制）
        user_quit_flag = {"quit": False}

        def _listen_user_input():
            """监听用户输入的独立线程"""
            while not user_quit_flag["quit"]:
                try:
                    u_inp = sender.input(500, 0, False)  # 短暂检查用户输入
                    if u_inp and str(u_inp).lower() == "q":
                        user_quit_flag["quit"] = True
                        sender.reply("✅ 已取消订单")
                        break
                except:
                    pass  # 忽略输入异常

        # 启动监听线程
        listener_thread = threading.Thread(target=_listen_user_input, daemon=True)
        listener_thread.start()

        start_time = time.time()

        # 主轮询循环
        while time.time() - start_time < 240 and not user_quit_flag["quit"]:
            time.sleep(0.7)  # 参考Yzyxmm.py的间隔时间

            # 调用易支付API检查订单状态
            status_result = check_epay_order_status(config, order_id)

            # 添加调试信息（帮助诊断易支付1的问题）
            if status_result.get('code') != 0 and status_result.get('msg') != '未支付':
                print(f"[DEBUG] 易支付查询结果: {status_result}")
                # 如果是易支付1，尝试直接查询原始响应
                if ':3026' in config.get('epay_url', ''):
                    print(f"[DEBUG] 检测到易支付1，订单ID: {order_id}")

            if status_result.get('code') == 0:
                # 验证支付会话是否仍然有效
                if not validate_payment_session(user_id, session_id):
                    user_quit_flag["quit"] = True
                    current_lock = get_payment_lock()
                    current_session = current_lock.get('session_id') if current_lock else 'None'
                    current_user = current_lock.get('user_id') if current_lock else 'None'
                    sender.reply(f"""=====支付会话失效=====
❌ 支付会话已失效，充值取消
💡 可能是管理员释放了支付锁
🔄 如已支付请联系管理员处理
------------------
🔍 调试信息：
🤪 用户ID: {user_id}
🪁 用户会话: {session_id[:8]}
✨ 当前用户: {current_user}
💥 当前会话: {current_session[:8] if current_session != 'None' else 'None'}
==================""")
                    return

                # 支付成功
                user_quit_flag["quit"] = True  # 停止监听线程
                paid_amount = status_result.get('money', amount)
                points_to_add = round(amount * config['exchange_rate'], 2)
                if add_user_points(user_id, points_to_add):
                    current_points = get_user_points(user_id)
                    sender.reply(f"""=====充值成功=====
💰 充值金额: {amount}元
💵 实付金额: {paid_amount}元
🎯 获得积分: {points_to_add}
💎 当前积分: {current_points}
🔍 会话ID: {session_id[:8]}
==================""")
                else:
                    sender.reply("❌ 积分增加失败，请联系管理员")
                return

        # 确保线程正常结束
        user_quit_flag["quit"] = True
        if listener_thread.is_alive():
            listener_thread.join(timeout=1)

        # 检查退出原因
        if user_quit_flag.get("quit") and time.time() - start_time < 240:
            return  # 用户主动取消，已在监听线程中回复

        # 支付超时
        sender.reply(f"""=====支付超时=====
❌ 订单支付超时
📋 订单编号: {order_id}
------------------
如已支付请联系管理员
==================""")

    except Exception as e:
        sender.reply(f"""=====支付异常=====
❌ 创建订单失败
------------------
⚠️ 错误: {str(e)[:50]}
==================""")
    finally:
        # 支付完成，只清理自己的会话和锁（如果锁还是自己的）
        current_lock = get_payment_lock()
        if current_lock and current_lock.get('session_id') == session_id:
            # 只有当前锁还是自己的时候才清除
            clear_payment_lock()
        # 总是清理自己的会话
        remove_payment_session(session_id)

def handle_release_payment_lock(sender):
    """处理释放支付锁指令（仅管理员）"""
    if not sender.isAdmin():
        sender.reply("""=====权限不足=====
❌ 此功能仅限管理员使用
==================""")
        return

    current_lock = get_payment_lock()
    if not current_lock:
        sender.reply("""=====支付锁状态=====
✅ 当前没有支付锁占用
==================""")
        return

    # 清除支付锁
    clear_payment_lock()

    lock_user = current_lock.get('user_id', '未知')
    lock_time = current_lock.get('timestamp', 0)
    duration = int(time.time() - lock_time)

    sender.reply(f"""=====支付锁已释放=====
✅ 支付锁已强制释放
🤪 原占用用户: {lock_user}
⏰ 占用时长: {duration}秒
💡 支付通道已恢复正常
==================""")

def handle_query_points(sender, user_id):
    """处理美团查分指令"""
    points = get_user_points(user_id)
    sender.reply(f"""=====积分查询=====
🤪 用户ID: {user_id}
💎 当前积分: {points}
==================""")

def handle_admin_add_points(sender):
    """处理美团加分指令（仅管理员）"""
    # 严格检查管理员权限
    if not sender.isAdmin():
        sender.reply("""=====权限不足=====
❌ 此功能仅限管理员使用
💡 请使用"美团充分"指令充值
==================""")
        return

    sender.reply("""=====管理加分=====
请输入被操作用户ID
------------------
回复用户ID
回复"q"退出""")

    # 获取目标用户ID
    target_user_input = sender.input(60000, 0, False)
    if not target_user_input:
        sender.reply("❌ 输入超时")
        return

    if str(target_user_input).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return

    target_user_id = str(target_user_input).strip()

    sender.reply("""=====加分数量=====
请输入要增加的积分数量
------------------
回复数字设置
回复"q"退出""")

    # 获取加分数量
    points_input = sender.input(60000, 0, False)
    if not points_input:
        sender.reply("❌ 输入超时")
        return

    if str(points_input).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return

    try:
        points_to_add = float(str(points_input).strip())
        # 严格限制到小数点后两位
        points_to_add = round(points_to_add, 2)
        if points_to_add <= 0:
            sender.reply("❌ 加分数量必须大于0")
            return
        if points_to_add < 0.01:
            sender.reply("❌ 加分数量最小为0.01分")
            return
    except ValueError:
        sender.reply("❌ 请输入有效的数字")
        return

    # 执行加分操作
    if add_user_points(target_user_id, points_to_add):
        current_points = get_user_points(target_user_id)
        sender.reply(f"""=====加分成功=====
🤪 目标用户: {target_user_id}
➕ 增加积分: {points_to_add}
💎 当前积分: {current_points}
==================""")
    else:
        sender.reply("❌ 加分失败，请稍后重试")

def handle_admin_deduct_points(sender):
    """处理美团减分指令（仅管理员）"""
    # 严格检查管理员权限
    if not sender.isAdmin():
        sender.reply("""=====权限不足=====
❌ 此功能仅限管理员使用
💡 请使用"美团充分"指令充值
==================""")
        return

    sender.reply("""=====管理减分=====
请输入被操作用户ID
------------------
回复用户ID
回复"q"退出""")

    # 获取目标用户ID
    target_user_input = sender.input(60000, 0, False)
    if not target_user_input:
        sender.reply("❌ 输入超时")
        return

    if str(target_user_input).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return

    target_user_id = str(target_user_input).strip()

    sender.reply("""=====减分数量=====
请输入要减少的积分数量
------------------
回复数字设置
回复"q"退出""")

    # 获取减分数量
    points_input = sender.input(60000, 0, False)
    if not points_input:
        sender.reply("❌ 输入超时")
        return

    if str(points_input).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return

    try:
        points_to_deduct = float(str(points_input).strip())
        # 严格限制到小数点后两位
        points_to_deduct = round(points_to_deduct, 2)
        if points_to_deduct <= 0:
            sender.reply("❌ 减分数量必须大于0")
            return
        if points_to_deduct < 0.01:
            sender.reply("❌ 减分数量最小为0.01分")
            return
    except ValueError:
        sender.reply("❌ 请输入有效的数字")
        return

    # 检查目标用户当前积分
    current_points = get_user_points(target_user_id)
    if current_points < points_to_deduct:
        sender.reply(f"""=====积分不足=====
🤪 目标用户: {target_user_id}
💎 当前积分: {current_points}
➖ 减分数量: {points_to_deduct}
❌ 积分不足，无法减分
==================""")
        return

    # 执行减分操作
    if deduct_user_points(target_user_id, points_to_deduct):
        new_points = get_user_points(target_user_id)
        sender.reply(f"""=====减分成功=====
🤪 目标用户: {target_user_id}
➖ 减少积分: {points_to_deduct}
💎 当前积分: {new_points}
==================""")
    else:
        sender.reply("❌ 减分失败，请稍后重试")


def handle_meituan_coupon(sender, user_id):
    """处理美团领券主流程"""
    config = get_config()
    all_prices = parse_prices(config['prices'])
    project_names = ["美团大众无门槛", "美团综合类券包", "美团早中晚神券"]
    available_projects = []
    project_map = []
    for i, price in enumerate(all_prices):
        if price != -1:
            name = project_names[i]
            price_superscript = format_price_superscript(price)
            menu_item = f"[{len(available_projects) + 1}] {name} {price_superscript}"
            available_projects.append(menu_item)
            project_map.append({'original_index': i, 'price': price, 'name': name})
    if not available_projects:
        sender.reply("❌ 当前没有可用的领券项目")
        return
    menu = f"""=====领券项目=====
{chr(10).join(available_projects)}
------------------
回复数字选择
回复"q"退出"""
    sender.reply(menu)
    choice = sender.input(60000, 0, False)
    if not choice:
        sender.reply("❌ 输入超时")
        return
    if str(choice).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return
    try:
        choice_num = int(str(choice))
        if choice_num < 1 or choice_num > len(project_map):
            sender.reply("❌ 请输入项目列表中的数字")
            return
        selected_project = project_map[choice_num - 1]
        project_type = selected_project['original_index'] + 1
        required_points = selected_project['price']
        selected_project_name = selected_project['name']
    except ValueError:
        sender.reply("❌ 请输入有效的数字")
        return               
    sender.reply("""=====美团领券=====
请输入美团账号链接
------------------
请在120秒内完成
回复"q"退出""")
    sender.replyImage('https://gcore.jsdelivr.net/gh/lhz03/img@b339198259ef6dbf4791d87750717911b54c879c/2025/04/18/061201c573e88b6143e39e2ae3f44464.png')
    cookie = sender.input(120000, 1000, False)
    if not cookie:
        sender.reply("❌ 输入超时")
        return
    if str(cookie).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return
    cookie_str = str(cookie).strip()
    if len(cookie_str) < 10:
        sender.reply("""❌ 美团账号链接不正确""")
        return
    if not any(keyword in cookie_str.lower() for keyword in ['token']):
        sender.reply("""❌ 美团账号链接不正确""")
        return
    if required_points > 0:
        current_points = get_user_points(user_id)
        if current_points < required_points:
            sender.reply(f"""=====积分不足=====
💎 当前积分: {current_points}
🎯 需要积分: {required_points}
💡 发送"美团充分"充值积分
==================""")
            return
        confirm_msg = f"""=====确认订单=====
🎉 目标项目: {selected_project_name}
🎯 消耗积分: {required_points}
💎 当前积分: {current_points}
------------------
回复"确认"继续
回复"q"退出"""
        sender.reply(confirm_msg)
        confirm = sender.input(60000, 0, False)
        if not confirm:
            sender.reply("❌ 输入超时")
            return
        if str(confirm).lower() == 'q':
            sender.reply("✅ 已取消操作")
            return
        if str(confirm) != "确认":
            sender.reply("❌ 请回复\"确认\"继续操作")
            return
    if not config['api_key'] or not config['api_url']:
        sender.reply("❌ API秘钥未配置，请联系管理员")
        return
    deducted_points = 0
    if required_points > 0:
        if deduct_user_points(user_id, required_points):
            deducted_points = required_points
        else:
            sender.reply("❌ 积分扣除失败，请稍后重试")
            return
    try:
        sender.reply("正在领取...")
        result = call_meituan_api(str(cookie), project_type)
        if result.get("code") == 0:
            msg = result.get("msg", "")
            failure_keywords = ["领到其他券", "\u8bf7\u52ff\u8bf7\u6c42\u4e0d\u76f8\u5173\u7684\u8def\u5f84\uff01"]
            is_actual_failure = any(keyword in msg for keyword in failure_keywords)
            if is_actual_failure:
                if deducted_points > 0:
                    add_user_points(user_id, deducted_points)
                info_list = result.get("info", [])
                if info_list and "领到其他券" in msg:
                    coupon_text = "\n".join([f"🎁 {info}" for info in info_list])
                    sender.reply(f"""=====领券失败=====
❌ 已退还{deducted_points}积分
{coupon_text}
==================""")
                else:
                    sender.reply(f"""=====领券失败=====
❌ 已退还{deducted_points}积分
💡 {msg}
==================""")
            else:
                info_list = result.get("info", [])
                if info_list:
                    coupon_text = "\n".join([f"🎁 {info}" for info in info_list])
                    success_msg = f"""=====领券成功=====
{coupon_text}
=================="""
                else:
                    success_msg = """=====领券成功=====
✅ 优惠券已成功领取
=================="""
                sender.reply(success_msg)
        else:
            if result.get("balance_error"):
                if deducted_points > 0:
                    add_user_points(user_id, deducted_points)
                sender.reply("❌ API秘钥余额不足，请联系管理员处理")
            else:
                if deducted_points > 0:
                    add_user_points(user_id, deducted_points)
                    sender.reply(f"""=====领券失败=====
❌ 已退还{deducted_points}积分
💡 {result.get('msg', '未知错误')}
==================""")
                else:
                    sender.reply(f"""=====领券失败=====
❌ {result.get('msg', '未知错误')}
==================""")
    except Exception as e:
        if deducted_points > 0:
            add_user_points(user_id, deducted_points)
            sender.reply(f"""=====领券异常=====
❌ 已退还{deducted_points}积分
💡 {str(e)}
==================""")
        else:
            sender.reply(f"""=====领券异常=====
❌ {str(e)}
==================""")

def handle_whitelist(sender):
    """处理美团刷白功能"""
    config = get_config()

    # 检查API配置
    if not config['api_key'] or not config['api_url']:
        sender.reply("❌ API秘钥未配置，请联系管理员")
        return

    sender.replyImage('https://gcore.jsdelivr.net/gh/lhz03/img@e6a4d8f580411217b4483c95c139e25dd16e8024/2025/04/18/c66460199240418a0c73292de85e0ba7.png')
    sender.reply("""=====美团刷白=====
请输入店铺链接
------------------
请在60秒内完成
回复"q"退出""")

    shop_link = sender.input(60000, 1000, False)  # 1秒后自动撤回链接消息
    if not shop_link:
        sender.reply("❌ 输入超时")
        return

    if str(shop_link).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return

    # 提取链接（支持混合文本）
    link_match = re.search(r'http://dpurl\.cn/[a-zA-Z0-9]+', str(shop_link))
    if not link_match:
        sender.reply("❌ 请输入有效的店铺链接")
        return

    extracted_link = link_match.group(0)

    # 调用刷白接口
    sender.reply("正在刷白...")

    try:
        whitelist_result = call_whitelist_api(extracted_link)

        if whitelist_result.get("code") == 0:
            sender.reply("""=====刷白成功=====
✅ 刷白执行完成
💡 打开原链退登后再获新链领券
==================""")
        else:
            error_msg = whitelist_result.get("msg", "未知错误")
            sender.reply(f"""=====刷白失败=====
❌ {error_msg}
==================""")

    except Exception as e:
        sender.reply(f"""=====刷白异常=====
❌ {str(e)}
==================""")


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
    """主函数"""
    sender = middleware.Sender(middleware.getSenderID())
    user_id = sender.getUserID()
    message = sender.getMessage().strip()

    if not check_maintenance_page():
        sender.reply("❌ 服务端无法连通, 插件停止运行")
        return
    if message == "美团领券":
        handle_meituan_coupon(sender, user_id)
    elif message == "美团刷白":
        handle_whitelist(sender)
    elif message == "美团充分":
        handle_recharge(sender, user_id)
    elif message == "美团查分":
        handle_query_points(sender, user_id)
    elif message == "美团加分":
        handle_admin_add_points(sender)
    elif message == "美团减分":
        handle_admin_deduct_points(sender)
    elif message == "释放支付锁":
        handle_release_payment_lock(sender)
    else:
        sender.setContinue()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sender = middleware.Sender(middleware.getSenderID())
        sender.reply(f"❌ 插件发生内部错误: {str(e)[:100]}")
        print(f"美团领券插件错误: {e}")
        import traceback
        traceback.print_exc()
