# [title: 触电青年]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@785d749e4bb57722a3da925877837ae2232fff55/2026/03/26/221b493dbbf11a17d46d6a476c3f8e30.png]
# [rule: ^(触电)(查询|监控)$]
# [cron: */5 * * * *]
# [admin: false]
# [open_source: false]
# [public: true]
# [disable: false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [priority: 9999999999999999999]
# [version: 1.0.5]
# [price: 0]
# [author: yuhualhh]
# [service: ]
# [description: 这是一个关于服务号触电青年的定时监控并推送新观影活动以及提供活动查询的插件，用户参加观影活动并按要求提交作业可报销金额实现免费观影，启用百夫长模式后可自动监听用户报名待审核并推送]

#[param: {"required":false,"key":"yuhua_cdqn.admin","bool":true,"placeholder":"","name":"百夫长模式","desc":"开启后需配置百夫长后台账密"}]
#[param: {"required":false,"key":"yuhua_cdqn.cdqn_account_pwd","placeholder":"","name":"百夫长账密","desc":"账密使用英文符#分隔，例如: 18888888888#123456789"}]
#[param: {"required":false,"key":"yuhua_cdqn.push_groups","placeholder":"","name":"推送群组","desc":"填写需要接收新活动通知的群号，多个群请用英文逗号,分隔"}]
#[param: {"required":false,"key":"yuhua_cdqn.debug_pwd","placeholder":"","name":"调试模式","desc":"非插件开发者无需理会"}]

import middleware
import requests
import json
import time

# 配置调试模式
debug_key = middleware.bucketGet('yuhua_cdqn', 'debug_pwd') or ''
DEBUG = (debug_key == '123456789abcC@')  # 如果密钥匹配，启用调试模式

def debug_print_request_response(request_type, url, headers, body=None, response=None):
    """用于打印请求和响应的函数"""
    if DEBUG:
        print(f"[DEBUG] {request_type} 请求 URL: {url}")
        print(f"[DEBUG] 请求头: {headers}")
        if body:
            print(f"[DEBUG] 请求体: {body}")
        if response:
            print(f"[DEBUG] 响应头: {response.headers}")
            try:
                print(f"[DEBUG] 响应体: {response.json()}")  # 尝试解析JSON
            except:
                print(f"[DEBUG] 响应体: {response.text}")  # 如果解析失败，打印原始文本

# --- API 和 请求头 配置 ---
API_BASE_URL = "https://www.chudianqingnian.com/chudianqingnian/app/task/"
HEADERS_TEMPLATE = {
    "Connection": "keep-alive",
    "sec-ch-ua-platform": '"Android"',
    "User-Agent": "Mozilla/5.0 (Linux; Android 16; RMX5060 Build/BP2A.250605.015; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/142.0.7444.173 Mobile Safari/537.36 MicroMessenger/8.0.69.3040(0x2800455A) WeChat/arm64 Weixin NetType/5G Language/zh_CN ABI/arm64",
    "Accept": "*/*",
    "Origin": "https://www.chudianqingnian.com",
    "X-Requested-With": "com.tencent.mm",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://www.chudianqingnian.com/front/",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

def check_token_expiry(response):
    """检查 token 是否过期"""
    code = response.get("code")
    message = str(response.get("message", ""))
    if code in [401, 403, 411] or "token已过期" in message or "token失效" in message or "登录失效" in message:
        print("触电青年: token已过期，请重新登录。")
        return True
    return False

def get_cdqn_account_pwd():
    """获取并解析百夫长账密"""
    account_pwd = middleware.bucketGet("yuhua_cdqn", "cdqn_account_pwd") or ""
    if "#" not in account_pwd:
        return None, None

    user_name, password = account_pwd.split("#", 1)
    user_name = user_name.strip()
    password = password.strip()

    if not user_name or not password:
        return None, None

    return user_name, password


def login_and_save_token():
    """智能重登获取 token，并保存复用（3次业务层重试）"""
    login_url = "https://www.chudianqingnian.com/chudianqingnian/admin/administrators/login"
    user_name, password = get_cdqn_account_pwd()

    if not user_name or not password:
        print("触电青年: 百夫长账密配置错误，请使用 账号#密码 格式")
        return None

    headers = HEADERS_TEMPLATE.copy()
    headers["Referer"] = "https://www.chudianqingnian.com/back/"
    headers["X-Requested-With"] = "mark.via"
    headers["Content-Type"] = "application/json;charset=UTF-8"
    headers["Accept"] = "application/json, text/plain, */*"

    body = {
        "userName": user_name,
        "password": password
    }

    for retry_index in range(3):
        try:
            if DEBUG:
                safe_body = {
                    "userName": user_name,
                    "password": "******"
                }
                print(f"[DEBUG] POST 请求 URL: {login_url}")
                print(f"[DEBUG] 请求头: {headers}")
                print(f"[DEBUG] 请求体: {safe_body}")

            login_response = requests.post(login_url, headers=headers, json=body, timeout=15)

            if DEBUG:
                print(f"[DEBUG] 响应头: {login_response.headers}")
                try:
                    print(f"[DEBUG] 响应体: {login_response.json()}")
                except:
                    print(f"[DEBUG] 响应体: {login_response.text}")

            login_response.raise_for_status()
            login_result = login_response.json()

            if login_result.get("code") == 200:
                new_token = login_result.get("data", {}).get("token")
                if new_token:
                    middleware.bucketSet("yuhua_cdqn", "cdqn_token", new_token)
                    print("触电青年: 智能重登成功，已自动更新 token")
                    return new_token

            print(f"触电青年: 智能重登失败 - {login_result.get('message', '未知错误')}")

        except Exception as e:
            print(f"触电青年: 智能重登时发生网络异常 - {e}")

        if retry_index < 2:
            time.sleep(1)

    return None


def get_cached_or_new_token(token):
    """优先使用缓存 token，不存在时自动登录获取"""
    current_token = token or middleware.bucketGet("yuhua_cdqn", "cdqn_token") or ""
    if current_token:
        return current_token
    return login_and_save_token()

def get_wx_code():
    """从远程接口获取微信code"""
    code_url = "http://yuhualhh.250666.xyz/api/get_code.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    try:
        response = requests.get(code_url, headers=headers, timeout=5)
        response.raise_for_status()
        result = response.json()
        code = result.get("code")
        # code为None、空字符串、字符串"null"时均视为无效
        if result.get("err") == 0 and code and code not in ["null", "None", ""]:
            return code
        print(f"触电青年: 获取code失败 - status: {result.get('status', '未知')}, codeType: {result.get('codeType', '未知')}")
        return None
    except Exception as e:
        print(f"触电青年: 获取code时发生网络异常 - {e}")
        return None

def login_by_code_and_save_token():
    """通过code登录获取app token，并保存复用（1次重试）"""
    code = get_wx_code()
    if not code:
        print("触电青年: 获取code失败，无法登录，联系插件开发者处理")
        # code获取失败时清除缓存中的过期token，避免后续仍使用过期token
        middleware.bucketSet("yuhua_cdqn", "cdqn_app_token", "")
        return None

    login_url = f"https://www.chudianqingnian.com/chudianqingnian/app/user/login?wxCode={code}"
    headers = HEADERS_TEMPLATE.copy()
    headers["cdqn-app-token"] = "null"

    try:
        debug_print_request_response('GET', login_url, headers)
        response = requests.get(login_url, headers=headers, timeout=15)
        debug_print_request_response('GET', login_url, headers, response=response)
        response.raise_for_status()
        result = response.json()

        if result.get("code") == 200:
            new_token = result.get("data", {}).get("token")
            if new_token:
                middleware.bucketSet("yuhua_cdqn", "cdqn_app_token", new_token)
                print("触电青年: 通过code登录成功，已自动更新 app token")
                return new_token

        print(f"触电青年: 通过code登录失败 - {result.get('message', '未知错误')}")
    except Exception as e:
        print(f"触电青年: 通过code登录时发生网络异常 - {e}")

    # 登录失败时清除缓存中的过期token
    middleware.bucketSet("yuhua_cdqn", "cdqn_app_token", "")
    return None

def get_cached_or_new_app_token(token=None):
    """优先使用缓存app token，不存在时自动通过code登录获取"""
    current_token = token or middleware.bucketGet("yuhua_cdqn", "cdqn_app_token") or ""
    if current_token:
        return current_token
    return login_by_code_and_save_token()

def _get_fallback_scenes(task_info):
    """从taskScenes提取场次名称（无剩余数据）"""
    task_scenes = task_info.get("taskScenes", {}) or {}
    scene_list = []
    for scene_id, scene_name in task_scenes.items():
        scene_list.append({
            "senceName": scene_name if scene_name not in [None, ""] else "未知场次"
        })
    return scene_list if scene_list else None

def get_tasks_app(token):
    """普通用户模式：通过app token获取任务列表"""
    url = API_BASE_URL + "getTaskList?pageNum=1&pageSize=9999"

    for retry_index in range(2):
        current_token = get_cached_or_new_app_token(token)
        if not current_token:
            print("触电青年: 获取任务列表失败 - 无法自动获取 app token")
            return "__LOGIN_FAILED__"

        headers = HEADERS_TEMPLATE.copy()
        headers["cdqn-app-token"] = current_token

        debug_print_request_response('POST', url, headers)

        try:
            response = requests.post(url, headers=headers, timeout=15)
            debug_print_request_response('POST', url, headers, response=response)
            response.raise_for_status()
            result = response.json()

            if check_token_expiry(result):
                print("触电青年: 获取任务列表失败 - app token已过期，正在尝试重新获取")
                token = login_by_code_and_save_token()
                if not token:
                    if retry_index == 1:
                        return "__LOGIN_FAILED__"
                    time.sleep(1)
                    continue
                continue

            if result.get("code") != 200 or not result.get("data"):
                print(f"触电青年: 获取任务列表失败 - {result.get('message', '未知错误')}")
                return None

            return result.get("data", {}).get("taskList", []) or []

        except Exception as e:
            print(f"触电青年: 请求任务列表时发生网络异常 - {e}")
            token = ""
            if retry_index < 1:
                time.sleep(1)
                continue
            return None

    return "__LOGIN_FAILED__"

def get_task_surplus_app(token, task_id):
    """普通用户模式：通过app token获取任务剩余名额"""
    url = API_BASE_URL + "getTaskSurplusNum"
    body = {"taskId": task_id}

    for retry_index in range(2):
        current_token = get_cached_or_new_app_token(token)
        if not current_token:
            print("触电青年: 获取剩余名额失败 - 无法自动获取 app token")
            return "__LOGIN_FAILED__"

        headers = HEADERS_TEMPLATE.copy()
        headers["cdqn-app-token"] = current_token
        headers["Content-Type"] = "application/json;charset=UTF-8"

        debug_print_request_response('POST', url, headers, body=body)

        try:
            response = requests.post(url, headers=headers, json=body, timeout=15)
            debug_print_request_response('POST', url, headers, body=body, response=response)
            response.raise_for_status()
            result = response.json()

            if check_token_expiry(result):
                print("触电青年: 获取剩余名额失败 - app token已过期，正在尝试重新获取")
                token = login_by_code_and_save_token()
                if not token:
                    if retry_index == 1:
                        return "__LOGIN_FAILED__"
                    time.sleep(1)
                    continue
                continue

            if result.get("code") != 200 or result.get("data") is None:
                print(f"触电青年: 获取剩余名额失败 - {result.get('message', '未知错误')}")
                return None

            scene_list = result.get("data", []) or []
            return scene_list if scene_list else None

        except Exception as e:
            print(f"触电青年: 请求剩余名额时发生网络异常 - {e}")
            token = ""
            if retry_index < 1:
                time.sleep(1)
                continue
            return None

    return "__LOGIN_FAILED__"

def get_intention_list(token):
    """获取后台用户报名审核列表"""
    intention_url = "https://www.chudianqingnian.com/chudianqingnian/admin/examine/getIntentionList?pageNum=1&pageSize=50&queryType=0"

    body = {
        "userId": "",
        "name": "",
        "taskId": "",
        "scenesId": "",
        "status": 99,
        "centurionName": "",
        "schoolName": ""
    }

    for retry_index in range(3):
        current_token = get_cached_or_new_token(token)
        if not current_token:
            print("触电青年: 获取报名审核列表失败 - 无法自动获取 token")
            return "__LOGIN_FAILED__"

        headers = HEADERS_TEMPLATE.copy()
        headers.pop("Origin", None)
        headers["Referer"] = "https://www.chudianqingnian.com/back/"
        headers["X-Requested-With"] = "mark.via"
        headers["Content-Type"] = "application/json;charset=UTF-8"
        headers["cdqn-admin-token"] = current_token

        debug_print_request_response('POST', intention_url, headers, body=body)

        try:
            intention_response = requests.post(intention_url, headers=headers, json=body, timeout=15)
            debug_print_request_response('POST', intention_url, headers, body=body, response=intention_response)
            intention_response.raise_for_status()
            intention_result = intention_response.json()

            if check_token_expiry(intention_result):
                print("触电青年: 获取报名审核列表失败 - token已过期，正在尝试智能重登")
                token = login_and_save_token()
                if not token:
                    if retry_index == 2:
                        return "__LOGIN_FAILED__"
                    time.sleep(1)
                    continue
                continue

            if intention_result.get("code") != 200 or intention_result.get("data") is None:
                print(f"触电青年: 获取报名审核列表失败 - {intention_result.get('message', '未知错误')}")
                return None

            return intention_result.get("data", {}).get("list", []) or []

        except Exception as e:
            print(f"触电青年: 请求报名审核列表时发生网络异常 - {e}")
            token = ""
            if retry_index < 2:
                time.sleep(1)
                continue
            return None

    return "__LOGIN_FAILED__"
        
def format_intention_message(item):
    """格式化报名审核信息为指定模板"""
    intention_status = item.get("intentionStatus")
    if intention_status == 0:
        status_text = "未审核"
    elif intention_status == 1:
        status_text = "已通过"
    elif intention_status == 2:
        status_text = "已驳回"
    else:
        status_text = "未知"

    apply_image = item.get("applyImage")
    apply_image_text = "已传购票图" if apply_image not in [None, ""] else "未传购票图"

    msg = "=====报名审核=====\n"
    msg += f"🤪 姓名: {item.get('userName', '未知')}\n"
    msg += f"🎨 活动: {item.get('taskName', '未知')}\n"
    msg += f"⛱️ 场次: {item.get('sceneName', '未知场次')}\n"
    msg += f"📦 传图: {apply_image_text}\n"
    msg += f"🗯️ 状态: {status_text}\n"
    msg += f"💫 时间: {item.get('createTime', '未知')}\n"
    msg += "=================="
    return msg

def get_tasks(token):
    """获取所有任务列表"""
    index_url = "https://www.chudianqingnian.com/chudianqingnian/admin/index/getIndexData"
    task_name_url = "https://www.chudianqingnian.com/chudianqingnian/admin/common/getTaskNameList?taskNameListType=1"

    for retry_index in range(3):
        current_token = get_cached_or_new_token(token)
        if not current_token:
            print("触电青年: 获取任务列表失败 - 无法自动获取 token")
            return "__LOGIN_FAILED__"

        headers = HEADERS_TEMPLATE.copy()
        headers.pop("Origin", None)
        headers["Referer"] = "https://www.chudianqingnian.com/back/"
        headers["X-Requested-With"] = "mark.via"
        headers["cdqn-admin-token"] = current_token

        debug_print_request_response('GET', index_url, headers)
        debug_print_request_response('GET', task_name_url, headers)

        try:
            index_response = requests.get(index_url, headers=headers, timeout=15)
            debug_print_request_response('GET', index_url, headers, response=index_response)
            index_response.raise_for_status()
            index_result = index_response.json()

            if check_token_expiry(index_result):
                print("触电青年: 获取任务列表失败 - token已过期，正在尝试智能重登")
                token = login_and_save_token()
                if not token:
                    if retry_index == 2:
                        return "__LOGIN_FAILED__"
                    time.sleep(1)
                    continue
                continue

            if index_result.get("code") != 200 or not index_result.get("data"):
                print(f"触电青年: 获取首页活动失败 - {index_result.get('message', '未知错误')}")
                return None

            task_name_response = requests.get(task_name_url, headers=headers, timeout=15)
            debug_print_request_response('GET', task_name_url, headers, response=task_name_response)
            task_name_response.raise_for_status()
            task_name_result = task_name_response.json()

            if check_token_expiry(task_name_result):
                print("触电青年: 获取任务列表失败 - token已过期，正在尝试智能重登")
                token = login_and_save_token()
                if not token:
                    if retry_index == 2:
                        return "__LOGIN_FAILED__"
                    time.sleep(1)
                    continue
                continue

            if task_name_result.get("code") != 200 or task_name_result.get("data") is None:
                print(f"触电青年: 获取活动场次失败 - {task_name_result.get('message', '未知错误')}")
                return None

            admin_task_list = index_result.get("data", {}).get("adminIndexTaskVoList", []) or []
            task_name_list = task_name_result.get("data", []) or []

            scene_map_by_name = {}
            for item in task_name_list:
                item_task_name = item.get("taskName")
                if item_task_name:
                    scene_map_by_name[item_task_name] = item

            merged_tasks = []
            for item in admin_task_list:
                item_task_name = item.get("taskName")
                task_scene_info = scene_map_by_name.get(item_task_name, {})

                merged_task = dict(item)
                merged_task["id"] = task_scene_info.get("id")
                merged_task["taskSence"] = task_scene_info.get("taskSence")
                merged_task["taskScenes"] = task_scene_info.get("taskScenes", {})

                merged_tasks.append(merged_task)

            return merged_tasks

        except Exception as e:
            print(f"触电青年: 请求任务列表时发生网络异常 - {e}")
            token = ""
            if retry_index < 2:
                time.sleep(1)
                continue
            return None

    return "__LOGIN_FAILED__"

def get_task_surplus(token, task_info):
    """获取单个任务的场次剩余名额"""
    task_id = task_info.get("id")

    # 没有taskId时，从taskScenes提取场次名称（无剩余数据）
    if not task_id:
        return _get_fallback_scenes(task_info)

    # 获取app token
    app_token = get_cached_or_new_app_token()
    if not app_token:
        # 无法获取app token，从taskScenes提取场次名称（无剩余数据）
        return _get_fallback_scenes(task_info)

    surplus_url = "https://www.chudianqingnian.com/chudianqingnian/app/task/getTaskSurplusNum"
    body = {"taskId": task_id}

    for retry_index in range(2):
        current_app_token = get_cached_or_new_app_token(app_token)
        if not current_app_token:
            # 无法获取app token，从taskScenes提取场次名称（无剩余数据）
            return _get_fallback_scenes(task_info)

        headers = HEADERS_TEMPLATE.copy()
        headers["cdqn-app-token"] = current_app_token
        headers["Content-Type"] = "application/json;charset=UTF-8"

        debug_print_request_response('POST', surplus_url, headers, body=body)

        try:
            response = requests.post(surplus_url, headers=headers, json=body, timeout=15)
            debug_print_request_response('POST', surplus_url, headers, body=body, response=response)
            response.raise_for_status()
            result = response.json()

            if check_token_expiry(result):
                print("触电青年: 获取剩余名额失败 - app token已过期，正在尝试重新获取")
                app_token = login_by_code_and_save_token()
                if not app_token:
                    # 重登失败，直接降级返回，不再无意义重试
                    return _get_fallback_scenes(task_info)
                continue

            if result.get("code") != 200 or result.get("data") is None:
                print(f"触电青年: 获取剩余名额失败 - {result.get('message', '未知错误')}")
                return None

            scene_list = result.get("data", []) or []
            return scene_list if scene_list else None

        except Exception as e:
            print(f"触电青年: 请求剩余名额时发生网络异常 - {e}")
            app_token = ""
            if retry_index < 1:
                time.sleep(1)
                continue
            return _get_fallback_scenes(task_info)

    return _get_fallback_scenes(task_info)

def format_task_message(task_info, surplus_info, is_admin_mode=True):
    """格式化观影信息为指定模板"""
    msg = "=====观影信息=====\n"
    msg += f"🎉 活动: {task_info.get('taskName', '未知')}\n"
    if is_admin_mode:
        msg += f"✨ 影片: {task_info.get('taskRemarkAdmin', '未知')}\n"

        reimbursement_price_limit = task_info.get('reimbursementPriceLimit', '未知')
        if reimbursement_price_limit not in [None, "", "未知"]:
            try:
                if float(reimbursement_price_limit).is_integer():
                    reimbursement_price_limit = int(float(reimbursement_price_limit))
            except:
                pass
            reimbursement_price_limit = f"{reimbursement_price_limit}元"
        msg += f"💰 报销: {reimbursement_price_limit}\n"
    msg += f"🔥 开始: {task_info.get('taskStartTime', '未知')}\n"
    msg += f"🎨 结束: {task_info.get('taskEndTime', '未知')}"

    if surplus_info:
        for scene in surplus_info:
            msg += f"\n⛱️ 场次: {scene.get('senceName', '未知场次')}"
            if "surplusNum" in scene:
                msg += f"\n🗯️ 剩余: {scene.get('surplusNum')}"

    msg += "\n=================="
    return msg

def _perform_maintenance_check() -> bool:
    from bs4 import BeautifulSoup

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
    except Exception:
        pass
    return live_status    

def main():
    sender = middleware.Sender(middleware.getSenderID())
    imtype = sender.getImtype()
    message = sender.getMessage() # 获取用户消息

    if not check_maintenance_page():
        sender.reply("❌ 服务端无法连通, 插件停止运行")
        return

    # 判断是否为百夫长模式
    is_admin_mode = (middleware.bucketGet("yuhua_cdqn", "admin") or "") in ["true", "True", "1", True]

    if is_admin_mode:
        # ========== 百夫长模式 ==========
        # 1. 读取并校验配置
        account_pwd = middleware.bucketGet("yuhua_cdqn", "cdqn_account_pwd")
        if not account_pwd:
            # 如果是管理员在操作，提示其配置
            if sender.isAdmin() and imtype not in ["fake", "cron"]:
                 sender.reply("=====配置错误=====\n❌ 状态: 未获取到百夫长账密\n💡 提示: 请前往Web后台插件配置中填写\n==================")
            # 定时任务或普通用户则静默失败
            return

        token = middleware.bucketGet("yuhua_cdqn", "cdqn_token") or ""

        # 2. 定时监控 与 手动触发监控 逻辑 (合并处理)
        # 触发条件: 是定时任务 或 管理员发送了 "触电监控" 指令
        if imtype in ["fake", "cron"] or (message == "触电监控" and sender.isAdmin()):

            # 判断是否为手动触发 (只有手动发送指令才有交互提示，定时任务静默执行)
            is_manual = (message == "触电监控")

            if is_manual:
                sender.reply("⏳ 正在执行监控...")

            tasks = get_tasks(token)
            if tasks in ["__TOKEN_EXPIRED__", "__LOGIN_FAILED__"]:
                if is_manual:
                    sender.reply("=====触电监控=====\n❌ 百夫长账密登录失败\n💡 请管理员检查插件配置\n==================")
                return
            if not tasks:
                if is_manual:
                    sender.reply("=====触电监控=====\n🎉 状态: 本次监控未发现任何活动\n==================")
            else:
                push_groups_str = middleware.bucketGet("yuhua_cdqn", "push_groups") or ""
                push_groups =[g.strip() for g in push_groups_str.split(',') if g.strip()]

                new_task_found = False
                for task in tasks:
                    task_id = task.get("id")
                    if not task_id:
                        continue

                    # 检查该任务是否已经被推送过
                    pushed_flag = middleware.bucketGet("yuhua_cdqn_pushed", str(task_id))
                    if pushed_flag:
                        continue # 已推送过，跳过

                    # 发现新任务，获取其剩余名额
                    surplus_data = get_task_surplus(token, task)
                    if surplus_data == "__TOKEN_EXPIRED__":
                        if is_manual:
                            sender.reply("=====触电监控=====\n❌ 百夫长账密登录失败\n💡 请管理员检查插件配置\n==================")
                        return
                    if surplus_data:
                        new_task_found = True
                        message_to_push = format_task_message(task, surplus_data)

                        # 推送给管理员
                        middleware.notifyMasters(message_to_push)

                        # 推送给指定群组
                        for group_id in push_groups:
                            middleware.push("qq", group_id, "", "", message_to_push)

                        # 标记为已推送
                        middleware.bucketSet("yuhua_cdqn_pushed", str(task_id), "true")
                        time.sleep(1) # 避免推送过于频繁

                # 如果是手动触发，且没有发现新任务，给予反馈
                if is_manual and not new_task_found:
                    sender.reply("=====触电监控=====\n🎉 状态: 暂无需要推送的新活动\n==================")

            # 追加：用户报名审核监控（百夫长模式专属，只推送给管理员，不推送群组）
            intention_list = get_intention_list(token)
            if intention_list in ["__TOKEN_EXPIRED__", "__LOGIN_FAILED__"]:
                if is_manual:
                    sender.reply("=====触电监控=====\n❌ 百夫长账密登录失败\n💡 请管理员检查插件配置\n==================")
                return

            if intention_list:
                for item in intention_list:
                    intention_id = item.get("id")
                    if not intention_id:
                        continue

                    # 只推送未审核的报名记录
                    if item.get("intentionStatus") != 0:
                        continue

                    # 检查该报名记录是否已经被推送过
                    pushed_flag = middleware.bucketGet("yuhua_cdqn_intention_pushed", str(intention_id))
                    if pushed_flag:
                        continue

                    message_to_push = format_intention_message(item)

                    # 强制仅推送给管理员，不受配参影响，不推送群组
                    middleware.notifyMasters(message_to_push)

                    # 标记为已推送
                    middleware.bucketSet("yuhua_cdqn_intention_pushed", str(intention_id), "true")
                    time.sleep(1)

        # 3. 用户查询指令逻辑
        elif message == "触电查询":
            sender.reply("⏳ 正在查询...")
            tasks = get_tasks(token)

            if tasks in ["__TOKEN_EXPIRED__", "__LOGIN_FAILED__"]:
                sender.reply("=====观影信息=====\n❌ 百夫长账密登录失败\n💡 请管理员检查插件配置\n==================")
                return
            if not tasks:
                sender.reply("=====观影信息=====\n🎉 状态: 当前暂无观影活动信息\n==================")
                return

            found_and_sent = False
            for task in tasks:
                task_id = task.get("id")
                if not task_id:
                    continue

                surplus_data = get_task_surplus(token, task)
                if surplus_data == "__TOKEN_EXPIRED__":
                    sender.reply("=====观影信息=====\n❌ 百夫长账密登录失败\n💡 请管理员检查插件配置\n==================")
                    return
                if surplus_data:
                    message_to_reply = format_task_message(task, surplus_data)
                    sender.reply(message_to_reply)
                    found_and_sent = True
                    time.sleep(1) # 多个活动时，间隔发送

            if not found_and_sent:
                sender.reply("=====观影信息=====\n❌ 状态: 无法获取活动剩余名额\n💡 提示: 请稍后再试或检查Token是否失效\n==================")

    else:
        # ========== 普通用户模式 ==========
        # 1. 获取app token
        app_token = get_cached_or_new_app_token()
        if not app_token:
            if sender.isAdmin() and imtype not in ["fake", "cron"]:
                sender.reply("=====配置错误=====\n❌ 状态: 无法获取用户Token\n💡 提示: 联系插件开发者处理\n==================")
            # 定时任务或普通用户则静默失败
            return

        # 2. 定时监控 与 手动触发监控 逻辑 (合并处理)
        # 触发条件: 是定时任务 或 管理员发送了 "触电监控" 指令
        if imtype in ["fake", "cron"] or (message == "触电监控" and sender.isAdmin()):

            # 判断是否为手动触发 (只有手动发送指令才有交互提示，定时任务静默执行)
            is_manual = (message == "触电监控")

            if is_manual:
                sender.reply("⏳ 正在执行监控...")

            tasks = get_tasks_app(app_token)
            if tasks in ["__TOKEN_EXPIRED__", "__LOGIN_FAILED__"]:
                if is_manual:
                    sender.reply("=====触电监控=====\n❌ 用户Token登录失败\n💡 联系插件开发者处理\n==================")
                return
            if not tasks:
                if is_manual:
                    sender.reply("=====触电监控=====\n🎉 状态: 本次监控未发现任何活动\n==================")
            else:
                push_groups_str = middleware.bucketGet("yuhua_cdqn", "push_groups") or ""
                push_groups =[g.strip() for g in push_groups_str.split(',') if g.strip()]

                new_task_found = False
                for task in tasks:
                    task_id = task.get("id")
                    if not task_id:
                        continue

                    # 检查该任务是否已经被推送过
                    pushed_flag = middleware.bucketGet("yuhua_cdqn_pushed", str(task_id))
                    if pushed_flag:
                        continue # 已推送过，跳过

                    # 发现新任务，获取其剩余名额
                    surplus_data = get_task_surplus_app(app_token, task_id)
                    if surplus_data in ["__TOKEN_EXPIRED__", "__LOGIN_FAILED__"]:
                        if is_manual:
                            sender.reply("=====触电监控=====\n❌ 用户Token登录失败\n💡 联系插件开发者处理\n==================")
                        return
                    if surplus_data:
                        new_task_found = True
                        message_to_push = format_task_message(task, surplus_data, is_admin_mode=False)

                        # 推送给管理员
                        middleware.notifyMasters(message_to_push)

                        # 推送给指定群组
                        for group_id in push_groups:
                            middleware.push("qq", group_id, "", "", message_to_push)

                        # 标记为已推送
                        middleware.bucketSet("yuhua_cdqn_pushed", str(task_id), "true")
                        time.sleep(1) # 避免推送过于频繁

                # 如果是手动触发，且没有发现新任务，给予反馈
                if is_manual and not new_task_found:
                    sender.reply("=====触电监控=====\n🎉 状态: 暂无需要推送的新活动\n==================")

            # 普通用户模式下不监控报名审核

        # 3. 用户查询指令逻辑
        elif message == "触电查询":
            sender.reply("⏳ 正在查询...")
            tasks = get_tasks_app(app_token)

            if tasks in ["__TOKEN_EXPIRED__", "__LOGIN_FAILED__"]:
                sender.reply("=====观影信息=====\n❌ 用户Token登录失败\n💡 联系插件开发者处理\n==================")
                return
            if not tasks:
                sender.reply("=====观影信息=====\n🎉 状态: 当前暂无观影活动信息\n==================")
                return

            found_and_sent = False
            for task in tasks:
                task_id = task.get("id")
                if not task_id:
                    continue

                surplus_data = get_task_surplus_app(app_token, task_id)
                if surplus_data in ["__TOKEN_EXPIRED__", "__LOGIN_FAILED__"]:
                    sender.reply("=====观影信息=====\n❌ 用户Token登录失败\n💡 联系插件开发者处理\n==================")
                    return
                if surplus_data:
                    message_to_reply = format_task_message(task, surplus_data, is_admin_mode=False)
                    sender.reply(message_to_reply)
                    found_and_sent = True
                    time.sleep(1) # 多个活动时，间隔发送

            if not found_and_sent:
                sender.reply("=====观影信息=====\n❌ 状态: 无法获取活动剩余名额\n💡 提示: 请稍后再试或检查Token是否失效\n==================")

if __name__ == "__main__":
    main()
