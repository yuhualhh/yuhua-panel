# [pin: true]
# [title: 文本转图]
# [language: python]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@c444ef7846496b486d2e5b1bf9c7ca6905619949/2026/04/10/67e3d3aeb941bce23849692787716acf.png]
#[rule: ^(文本转图|.*文本转图|切换转图主题.*|设置转图接口.*)$]
# [disable:false]
# [router: /text2image]
# [method: post]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [public: true]
# [open_source: false]
# [class: 工具类]
# [version: 1.0.5]
# [price: 0]
# [admin: false]
# [author: 羽化]
# [service: 2550306191]
# [description: ❶该插件可为消息规则的问答回复以及任意插件源的Python、NodeJS插件提供文本转图服务。使其文本内容替换成图片输出，可有效降低各大社交平台文本检测封禁风险。<br>❷先送指令『开启文本转图』待提示已开启，再发指令『管理文本转图』添加需启用文本转图的插件。如需暂时关闭则发指令『关闭文本转图』<img src="https://gcore.jsdelivr.net/gh/lhz03/img@29949cd67168912e9b439d29d52a1a509fc70be2/2026/03/28/72bbaadb24ca85e3afb59b270e448cdd.png">]

import middleware
import base64
import requests
import re
import os
import importlib
import types
import json
import queue
import threading
import shutil
import time
import random
from datetime import datetime
from requests.exceptions import ConnectionError, Timeout, RequestException
from bs4 import BeautifulSoup
from urllib.parse import quote

import sys

PROTECTED_PLUGIN_TITLES =["羽化核心", "文本转图", "支付接管"]

# [param: {"required":true,"key":"yuhua_wbzt.img","placeholder":"例: 插件A,插件B","name":"文本转图列表","desc":"各插件之间用英文符,分割"}]
# [param: {"required":false,"key":"yuhua_wbzt.push","bool":true,"placeholder":"","name":"强制URL发图","desc":"当对接框架不支持base64发图时开启"}]
# [param: {"required":false,"key":"yuhua_wbzt.api_domain","placeholder":"例: 127.0.0.1:3000","name":"文本转图接口","desc":"不再提供公共转图接口，请访问pan.oroe.cn在其他应用分类下获取转图后端程序自建接口"}]
# [param: {"required":false,"key":"yuhua_wbzt.theme","placeholder":"例: 白蓝","name":"文本转图主题","desc":"目前有 灰、白彩、白蓝(默认)"}]
#[param: {"required":false,"key":"yuhua_wbzt.debug_mode","bool":false,"placeholder":"","name":"开发调试模式","desc":"非开发者无需理会"}]

def debug_print(message):
    """仅在调试模式下输出普通日志"""
    if DEBUG:
        print(message)

def printf(msg, level='INFO'):
    """控制台染色日志输出"""
    c = 32 if level in ['INFO', 'DEBUG'] else 33 if level in['WARN', 'WARNING'] else 31
    sys.stderr.write(f"\033[{c}m[{level}] {str(msg)}\033[0m\n")
    sys.stderr.flush()

# 初始化全局调试模式
try:
    debug_val = middleware.bucketGet('yuhua_wbzt', 'debug_mode') or ''
    DEBUG = (debug_val == '123456789abcC@')
except Exception:
    DEBUG = False

if DEBUG:
    printf("🔥🔥🔥 文本转图调试模式已开启，密钥验证通过，将输出详细网络日志 🔥🔥🔥", "WARN")

# --- 配置读取功能 ---
def get_config_theme():
    """
    获取配置的主题值。如果未配置，则默认返回 "白蓝"。
    
    返回:
        str: 主题值
    """
    try:
        theme = middleware.bucketGet("yuhua_wbzt", "theme")
        # 如果用户有配置则使用配置，否则默认为 "白蓝"
        return theme if theme else "白蓝"
    except Exception:
        # 如果读取配置失败，也安全地返回 "白蓝"
        return "白蓝"


def get_config_api_domain():
    """
    获取配置的API域名。如果未配置，则默认返回 "text2image-eo.250666.xyz"。
    
    返回:
        str: API域名
    """
    try:
        domain = middleware.bucketGet("yuhua_wbzt", "api_domain")
        # 如果用户有配置则使用配置，否则使用默认值
        if domain:
            return domain
        return "127.0.0.1:3000"
    except Exception:
        # 如果读取配置失败，也安全地返回默认值
        return "127.0.0.1:3000"

def set_config_api_domain(domain: str):
    """
    设置配置的API域名
    
    参数:
        domain (str): 要设置的API域名
    
    返回:
        bool: 设置是否成功
    """
    try:
        middleware.bucketSet("yuhua_wbzt", "api_domain", domain)
        return True
    except Exception as e:
        print(f"设置转图接口配置失败: {e}")
        return False




# --- 配置设置功能 ---
def set_config_theme(theme: str):
    """
    设置配置的主题值
    
    参数:
        theme (str): 要设置的主题值，支持任意主题值
    """
    try:
        middleware.bucketSet("yuhua_wbzt", "theme", theme)
        return True
    except Exception as e:
        print(f"设置主题配置失败: {e}")
        return False

def get_available_themes():
    """
    从API获取可用的主题列表。如果失败，返回一个硬编码的备用列表。
    
    返回:
        list: 主题名称列表
    """
    fallback_themes =["白蓝", "灰"]
    try:
        api_domain = get_config_api_domain()
        api_url = f"http://{api_domain}/api/v1/templates"
        
        if DEBUG:
            printf(f"\n===== [THEME API REQUEST START] =====", "DEBUG")
            printf(f"METHOD: GET | URL: {api_url}", "DEBUG")
        else:
            print(f"正在从API获取主题列表: {api_url}")
        
        response = _requests_get_with_retry(api_url, timeout=15)
        
        if DEBUG:
            printf(f"-----[THEME API RESPONSE] -----", "DEBUG")
            printf(f"STATUS: {response.status_code}", "DEBUG")
            printf(f"RSP BODY: {response.text}", "DEBUG")
            printf(f"=====[THEME API REQUEST END] =====\n", "DEBUG")
            
        response.raise_for_status()
        data = response.json()
        
        print(f"从API收到的原始数据: {data}")

        themes =[]
        # 增强对不同JSON格式的兼容性
        if isinstance(data, dict):
            # 兼容 {"templates": ["主题1", ...]}
            if "templates" in data and isinstance(data.get("templates"), list):
                themes = data["templates"]
            # 兼容 {"data":["主题1", ...]}
            elif "data" in data and isinstance(data.get("data"), list):
                themes = data["data"]
            # 兼容 {"themes": ["主题1", ...]}
            elif "themes" in data and isinstance(data.get("themes"), list):
                themes = data["themes"]
        elif isinstance(data, list):
            # 直接就是列表 ["主题1", ...]
            themes = data
        
        # 过滤掉非字符串和空字符串
        themes =[str(theme) for theme in themes if isinstance(theme, str) and theme]

        if themes:
            print(f"成功解析主题列表: {themes}")
            return themes
        else:
            print(f"API返回数据为空或格式不正确，使用备用列表")
            return fallback_themes
            
    except Exception as e:
        if DEBUG:
            printf(f"⚠️ Theme API FAILED (Error): {e}", "WARN")
        print(f"通过API获取可用主题列表失败: {e}, 使用备用列表")
        return fallback_themes



# --- 核心功能：文本转图片 ---


def _requests_get_with_retry(url, retries=3, delay=2, **kwargs):
    """带重试机制的requests.get请求"""
    for i in range(retries):
        try:
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response
        except (ConnectionError, Timeout, RequestException) as e:
            print(f"请求失败 (尝试 {i + 1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(delay)
            else:
                raise

def _requests_post_with_retry(url, retries=3, delay=2, **kwargs):
    """带重试机制的requests.post请求"""
    for i in range(retries):
        try:
            response = requests.post(url, **kwargs)
            response.raise_for_status()
            return response
        except (ConnectionError, Timeout, RequestException) as e:
            print(f"请求失败 (尝试 {i + 1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(delay)
            else:
                raise

def _call_render_api(content: str, custom_params: dict = None, timeout: int = 115, retries: int = 1, delay: int = 2):
    """
    统一调用文本转图片渲染API的核心函数，包含业务逻辑重试。
    
    参数:
        content (str): 要渲染的内容，可包含CQ码
        custom_params (dict): 自定义参数，可覆盖配置文件中的设置
        timeout (int): 请求超时时间
        retries (int): 业务逻辑重试次数
        delay (int): 重试延迟时间
    
    返回:
        str: base64编码的图片数据，失败则返回 None
    """
    actual_retries = max(1, retries)
    total_delay = (actual_retries - 1) * delay
    per_attempt_timeout = max(1.0, (timeout - total_delay) / actual_retries)

    for i in range(actual_retries):
        try:
            # 获取配置参数
            theme = get_config_theme()
            # 如果有自定义参数，覆盖配置参数
            if custom_params:
                theme = custom_params.get("theme", theme)
            
            # 修复：去除主题名称前后可能存在的空格
            if isinstance(theme, str):
                theme = theme.strip()
                
            # 将用户友好的主题名映射到API模板名
            template_name = theme
            
            # API接口
            api_domain = get_config_api_domain()
            api_url = f"http://{api_domain}/api/v1/render"
            
            payload = {
                "mode": "image-text",
                "content": content,
                "template": template_name,
                "output": {
                    "return_type": "url"
                }
            }
            headers = {"Content-Type": "application/json"}
            
            if DEBUG:
                printf(f"\n===== [RENDER API REQUEST START] =====", "DEBUG")
                printf(f"METHOD: POST | URL: {api_url}", "DEBUG")
                printf(f"HEADERS: {json.dumps(headers, ensure_ascii=False)}", "DEBUG")
                payload_str = json.dumps(payload, ensure_ascii=False)
                if len(payload_str) > 500: payload_str = payload_str[:300] + "...(truncated)..."
                printf(f"BODY: {payload_str}", "DEBUG")

            api_response = requests.post(api_url, json=payload, headers=headers, timeout=per_attempt_timeout)
            
            if DEBUG:
                printf(f"-----[RENDER API RESPONSE - Attempt {i+1}] -----", "DEBUG")
                printf(f"STATUS: {api_response.status_code}", "DEBUG")
                rsp_text = api_response.text
                if len(rsp_text) < 1000:
                    printf(f"RSP BODY: {rsp_text}", "DEBUG")
                else:
                    printf(f"RSP BODY: {rsp_text[:500]}...(truncated)", "DEBUG")
                printf(f"=====[RENDER API REQUEST END] =====\n", "DEBUG")
            
            result = api_response.json()
            
            # 优先使用返回的URL，如果没有URL则使用base64数据
            image_url = result.get("image_url")
            if image_url:
                # 返回完整的URL
                return f"http://{get_config_api_domain()}{image_url}"
            
            # 如果没有URL，降级使用base64数据
            image_data = result.get("image_data")
            if image_data:
                return image_data
            
            print(f"图片转换失败 (尝试 {i + 1}/{actual_retries}): API未返回图片数据")
            if i < actual_retries - 1:
                time.sleep(delay)

        except Exception as e:
            if DEBUG:
                printf(f"⚠️ Render API Attempt {i + 1} FAILED (Error): {e}", "WARN")
            print(f"文本转图片API调用失败 (尝试 {i + 1}/{actual_retries}): {e}")
            if i < actual_retries - 1:
                time.sleep(delay)

    return None


def convert_text_to_image_url(text: str, custom_params: dict = None, timeout: int = 115):
    """
    接收文本，调用API将其转换为图片，并返回图片URL或base64编码的图片数据。
    优先返回URL，如果API不支持URL则返回base64数据。
    如果失败，则返回 None。
    """
    return _call_render_api(content=text, custom_params=custom_params, timeout=timeout)

def convert_multi_element_to_image_url(elements, custom_params: dict = None, timeout: int = 115):
    """
    接收多个文本和图片元素，调用API将其转换为组合图片，并返回图片URL或base64数据。
    优先返回URL，如果API不支持URL则返回base64数据。
    """
    content_parts = []
    for element in elements:
        if isinstance(element, str):
            if element.startswith("http://") or element.startswith("https://"):
                content_parts.append(f"[CQ:image,file={element}]")
            else:
                content_parts.append(element)
        else:
            content_parts.append(str(element))
    
    content = "\n".join(content_parts)
    return _call_render_api(content=content, custom_params=custom_params, timeout=timeout)


def parse_multi_element_content(content: str):
    """
    解析用户输入的内容，提取文本和图片元素
    
    参数:
        content (str): 用户输入的内容
    
    返回:
        list: 元素列表，按从左到右的顺序排列
    """
    elements = []
    try:
        # 改进后的正则表达式，能正确处理URL和Base64
        # 它会通过CQ码分割字符串，并保留分隔符
        # 例如: "text1[CQ:...]text2" -> ["text1", "[CQ:...]", "text2"]
        image_pattern = r'(\[CQ:image,file=[^\]]+\])'
        
        parts = re.split(image_pattern, content)
        
        for part in parts:
            # 忽略 re.split 产生的空字符串
            if not part:
                continue
            # 检查部分是否是CQ码
            if part.startswith('[CQ:image,file=') and part.endswith(']'):
                # 提取 file=... 的内容
                # [CQ:image,file=http://...] -> http://...
                file_content = part[15:-1]
                elements.append(file_content)
            else:
                # 否则就是普通文本
                stripped_part = part.strip()
                if stripped_part:
                    elements.append(stripped_part)
        
        return elements
        
    except Exception as e:
        print(f"解析多元素内容失败: {e}")
        return []


def get_base_url_by_version():
    """
    根据当前奥特曼版本号，智能选择中间件下载的基础URL。
    """
    url_v371="http://yuhualhh.250666.xyz/img/middleware3.7.1/"
    url_v451="http://yuhualhh.250666.xyz/img/middleware4.5.1/"
    url_latest="http://yuhualhh.250666.xyz/img/latest/"
    try:
        current_version_raw = middleware.version()

        if DEBUG:
            printf(f"版本原始返回值: {repr(current_version_raw)} | 类型: {type(current_version_raw).__name__}", "DEBUG")

        if not current_version_raw:
            debug_print("⚠️ 未能获取到奥特曼版本，默认使用新版URL")
            return url_latest

        current_version_str = ""

        if isinstance(current_version_raw, str):
            current_version_str = current_version_raw.strip()
        elif isinstance(current_version_raw, dict):
            for key in ["sn", "version", "data", "ver", "appVersion", "autmanVersion", "value"]:
                value = current_version_raw.get(key)
                if isinstance(value, str) and value.strip():
                    current_version_str = value.strip()
                    break

            if not current_version_str:
                for value in current_version_raw.values():
                    if isinstance(value, str) and value.strip():
                        current_version_str = value.strip()
                        break

            if not current_version_str:
                current_version_str = json.dumps(current_version_raw, ensure_ascii=False)
        elif isinstance(current_version_raw, (list, tuple)):
            for value in current_version_raw:
                if isinstance(value, str) and value.strip():
                    current_version_str = value.strip()
                    break

            if not current_version_str:
                current_version_str = json.dumps(current_version_raw, ensure_ascii=False)
        else:
            current_version_str = str(current_version_raw).strip()

        if not current_version_str:
            debug_print("⚠️ 版本信息为空，默认使用新版URL")
            return url_latest

        if DEBUG:
            printf(f"版本解析字符串: {current_version_str}", "DEBUG")

        import re
        match=re.search(r'(\d+)\.(\d+)\.(\d+)', current_version_str)
        if not match:
            debug_print(f"⚠️ 无法解析版本号 '{current_version_str}'，默认使用新版URL")
            return url_latest

        current_version_tuple=tuple(map(int, match.groups()))

        if DEBUG:
            printf(f"版本解析结果: {current_version_tuple}", "DEBUG")

        if current_version_tuple<(3,8,6):
            debug_print(f"✅ 检测到旧版奥特曼 (版本: {current_version_str})，使用3.7.1中间件URL")
            return url_v371
        elif current_version_tuple<(4,5,2):
            debug_print(f"✅ 检测到过渡版奥特曼 (版本: {current_version_str})，使用4.5.1中间件URL")
            return url_v451
        else:
            debug_print(f"✅ 检测到新版奥特曼 (版本: {current_version_str})，使用新版中间件URL")
            return url_latest
    except Exception as e:
        debug_print(f"⚠️ 版本检测过程中发生异常: {e}，默认使用新版中间件URL")
        return url_latest


def backup_middleware_file(file_path: str) -> bool:
    """备份中间件，添加.bak后缀（仅首次备份，避免覆盖原版）"""
    try:
        if os.path.exists(file_path):
            backup_path = file_path + ".bak"
            # 关键改进：只在备份中间件不存在时才进行备份
            # 这确保备份中间件始终是原版中间件，不会被修改版覆盖
            if not os.path.exists(backup_path):
                # 首次备份：保存原版中间件
                shutil.copy2(file_path, backup_path)
                debug_print(f"首次备份原版中间件: {file_path} -> {backup_path}")
                return True
            else:
                # 备份中间件已存在，说明已经备份过原版，不再重复备份
                debug_print(f"中间件备份已存在，跳过备份: {backup_path}")
                return True  # 返回True表示备份状态正常
        return False
    except Exception as e:
        debug_print(f"备份中间件失败 {file_path}: {e}")
        return False


def restore_from_backup(file_path: str) -> bool:
    """从中间件备份恢复"""
    try:
        backup_path = file_path + ".bak"
        if os.path.exists(backup_path):
            # 如果目标中间件存在，先删除
            if os.path.exists(file_path):
                os.remove(file_path)
            # 恢复备份中间件（复制而不是移动，保留中间件备份）
            shutil.copy2(backup_path, file_path)
            debug_print(f"从备份恢复中间件: {backup_path} -> {file_path}")
            return True
        return False
    except Exception as e:
        debug_print(f"从备份恢复失败 {file_path}: {e}")
        return False

def resolve_middleware_paths():
    current_workdir = os.getcwd()
    current_plugin_file_raw = globals().get("__file__", "")
    current_plugin_file = os.path.abspath(current_plugin_file_raw) if current_plugin_file_raw else ""
    middleware_module_file = os.path.abspath(getattr(middleware, "__file__", "")) if getattr(middleware, "__file__", "") else ""

    py_middleware_path = ""
    js_middleware_path = ""

    normalized_workdir = os.path.abspath(current_workdir)
    workdir_name = os.path.basename(normalized_workdir)
    workdir_parent_name = os.path.basename(os.path.dirname(normalized_workdir))

    if workdir_name == "scripts" and workdir_parent_name == "plugin":
        py_middleware_path = os.path.join(normalized_workdir, "middleware.py")
        js_middleware_path = os.path.join(normalized_workdir, "middleware.js")
    else:
        current_scripts_dir = os.path.dirname(current_plugin_file) if current_plugin_file else normalized_workdir
        if os.path.basename(current_scripts_dir) == ".tmpfs":
            current_scripts_dir = normalized_workdir
        py_middleware_path = os.path.join(normalized_workdir, "middleware.py")
        js_middleware_path = os.path.join(normalized_workdir, "middleware.js")

    py_middleware_path = os.path.abspath(py_middleware_path)
    js_middleware_path = os.path.abspath(js_middleware_path)

    return current_workdir, current_plugin_file, middleware_module_file, py_middleware_path, js_middleware_path

def reset_text_to_image(sender: middleware.Sender):
    """还原中间件"""
    if not sender.isAdmin():
        sender.reply("❌ 权限不足：若非管理员请勿操作")
        return

    try:
        sender.reply("🔄 正在智能识别版本并还原中间件...")

        base_url = get_base_url_by_version()
        py_original_url = f"{base_url}middleware.py"
        js_original_url = f"{base_url}middleware.js"

        try:
            current_workdir, current_plugin_file, middleware_module_file, py_middleware_path, js_middleware_path = resolve_middleware_paths()
        except Exception as e:
            sender.reply(f"❌ 定位中间件路径失败: {e}")
            return

        if DEBUG:
            printf(f"\n===== [RESTORE MIDDLEWARE DEBUG START] =====", "DEBUG")
            printf(f"CWD: {current_workdir}", "DEBUG")
            printf(f"PLUGIN FILE: {current_plugin_file}", "DEBUG")
            printf(f"MIDDLEWARE MODULE FILE: {middleware_module_file}", "DEBUG")
            printf(f"RESOLVED PY PATH: {py_middleware_path}", "DEBUG")
            printf(f"RESOLVED JS PATH: {js_middleware_path}", "DEBUG")
            printf(f"PY EXISTS BEFORE: {os.path.exists(py_middleware_path)}", "DEBUG")
            printf(f"JS EXISTS BEFORE: {os.path.exists(js_middleware_path)}", "DEBUG")
            printf(f"PY ORIGINAL URL: {py_original_url}", "DEBUG")
            printf(f"JS ORIGINAL URL: {js_original_url}", "DEBUG")

        restore_count = 0
        
        for name, path, url in [
            ("Python中间件", py_middleware_path, py_original_url),
            ("JavaScript中间件", js_middleware_path, js_original_url)
        ]:
            backup_path = path + ".bak"
            restored = False

            if DEBUG:
                printf(f"[{name}] TARGET PATH: {path}", "DEBUG")
                printf(f"[{name}] BACKUP PATH: {backup_path}", "DEBUG")
                printf(f"[{name}] DOWNLOAD URL: {url}", "DEBUG")
                printf(f"[{name}] EXISTS BEFORE: {os.path.exists(path)}", "DEBUG")
                printf(f"[{name}] BACKUP EXISTS BEFORE: {os.path.exists(backup_path)}", "DEBUG")

            debug_print(f"ℹ️ 正在尝试从远程服务器下载匹配当前版本的 {name}...")
            if download_middleware_file(url, path, max_retries=2):
                debug_print(f"✅ 已成功从远程下载并恢复 {name}")
                restore_count += 1
                restored = True
                if DEBUG:
                    printf(f"[{name}] REMOTE RESTORE SUCCESS", "DEBUG")
                    try:
                        printf(f"[{name}] FILE SIZE AFTER REMOTE RESTORE: {os.path.getsize(path)}", "DEBUG")
                    except Exception:
                        pass
            else:
                debug_print(f"⚠️ 从远程下载 {name} 失败")
                if DEBUG:
                    printf(f"[{name}] REMOTE RESTORE FAILED", "WARN")

            if not restored:
                debug_print(f"ℹ️ 正在尝试使用本地备份文件恢复 {name}...")
                if os.path.exists(backup_path):
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                        shutil.copy2(backup_path, path)
                        debug_print(f"✅ 已从本地备份恢复 {name}，请注意如果您升级过奥特曼，此备份可能已过期")
                        restore_count += 1
                        if DEBUG:
                            printf(f"[{name}] LOCAL BACKUP RESTORE SUCCESS", "DEBUG")
                            try:
                                printf(f"[{name}] FILE SIZE AFTER LOCAL RESTORE: {os.path.getsize(path)}", "DEBUG")
                            except Exception:
                                pass
                    except Exception as e:
                        debug_print(f"❌ 从本地备份恢复 {name} 失败: {e}")
                        if DEBUG:
                            printf(f"[{name}] LOCAL BACKUP RESTORE FAILED: {e}", "WARN")
                else:
                    debug_print(f"❌ 未找到 {name} 的本地备份文件")
                    if DEBUG:
                        printf(f"[{name}] BACKUP FILE NOT FOUND", "WARN")

        if restore_count > 0:
            try:
                if DEBUG:
                    printf(f"[Python中间件] CLEAR CACHE PATH: {py_middleware_path}", "DEBUG")
                clear_python_cache(py_middleware_path)
                with open(py_middleware_path, 'r', encoding='utf-8') as f:
                    original_code = f.read()
                if DEBUG:
                    printf(f"[Python中间件] CODE LENGTH: {len(original_code)}", "DEBUG")
                exec(original_code, middleware.__dict__)
                if DEBUG:
                    printf(f"[Python中间件] HOT RELOAD SUCCESS", "DEBUG")
            except Exception as e:
                debug_print(f"Python中间件热重载失败: {e}")
                if DEBUG:
                    printf(f"[Python中间件] HOT RELOAD FAILED: {e}", "WARN")

        reset_count = 0
        for path in [py_middleware_path, js_middleware_path]:
            backup_path = path + ".bak"
            try:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                    debug_print(f"删除中间件备份: {backup_path}")
                    reset_count += 1
                    if DEBUG:
                        printf(f"BACKUP REMOVED: {backup_path}", "DEBUG")
            except Exception as e:
                debug_print(f"删除中间件备份失败 {backup_path}: {e}")
                if DEBUG:
                    printf(f"BACKUP REMOVE FAILED {backup_path}: {e}", "WARN")
        
        try:
            plugin_file_for_touch = globals().get("__file__", "")
            if plugin_file_for_touch:
                os.utime(plugin_file_for_touch, None)
                if DEBUG:
                    printf("PLUGIN FILE MTIME TOUCHED", "DEBUG")
        except Exception:
            pass

        if DEBUG:
            printf(f"RESTORE COUNT: {restore_count}", "DEBUG")
            printf(f"RESET COUNT: {reset_count}", "DEBUG")
            printf(f"PY EXISTS FINAL: {os.path.exists(py_middleware_path)}", "DEBUG")
            printf(f"JS EXISTS FINAL: {os.path.exists(js_middleware_path)}", "DEBUG")
            printf(f"=====[RESTORE MIDDLEWARE DEBUG END] =====\n", "DEBUG")
        
        if restore_count > 0:
            sender.reply("✅ 还原中间件成功" + ("并清理了备份" if reset_count > 0 else ""))
        else:
            sender.reply("❌ 还原中间件失败，未能从远程或本地备份恢复")
            
    except Exception as e:
        sender.reply(f"❌ 还原中间件时发生异常: {e}")

def download_middleware_file(url: str, target_path: str, max_retries: int = 3) -> bool:
    """
    从URL下载中间件（带重试机制）
    
    参数:
        url: 下载地址
        target_path: 目标中间件路径
        max_retries: 最大重试次数，默认3次
    
    返回:
        bool: 下载是否成功
    """
    
    # 可重试的异常类型
    RETRYABLE_EXCEPTIONS = (
        ConnectionError,    # 连接错误
        Timeout,           # 超时
        requests.exceptions.HTTPError,  # HTTP错误（会在下面进一步判断）
    )
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                debug_print(f"🔄 正在重试下载中间件 (第{attempt}次重试): {url}")
            else:
                debug_print(f"📥 正在下载中间件: {url}")
            
            # 渐进式超时：每次重试增加超时时间
            timeout = 15 + (attempt * 5)
            
            response = requests.get(url, timeout=timeout)
            
            # 区分不同的HTTP错误
            if response.status_code == 404:
                debug_print(f"❌ 中间件不存在 (404): {url}")
                return False  # 404错误不重试
            elif response.status_code == 403:
                debug_print(f"❌ 访问被拒绝 (403): {url}")
                return False  # 403错误不重试
            elif response.status_code == 401:
                debug_print(f"❌ 未授权访问 (401): {url}")
                return False  # 401错误不重试
            
            # 检查其他HTTP错误（5xx服务器错误可以重试）
            if response.status_code >= 500:
                raise requests.exceptions.HTTPError(f"服务器错误 ({response.status_code})")
            elif response.status_code >= 400:
                debug_print(f"❌ 客户端错误 ({response.status_code}): {url}")
                return False  # 4xx错误（除了已处理的）不重试
            
            response.raise_for_status()  # 确保请求成功
            
            # 确保目录存在
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # 写入中间件
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            debug_print(f"✅ 中间件下载成功: {target_path}")
            return True
            
        except RETRYABLE_EXCEPTIONS as e:
            if attempt < max_retries - 1:
                # 指数退避 + 随机抖动，避免多用户同时重试
                base_delay = 2 ** attempt  # 1, 2, 4
                jitter = random.uniform(0, 1)  # 0-1秒随机抖动
                delay = base_delay + jitter
                
                error_type = type(e).__name__
                debug_print(f"⚠️  下载失败 ({error_type}): {str(e)[:100]}")
                debug_print(f"⏱️  将在 {delay:.1f} 秒后重试...")
                time.sleep(delay)
            else:
                debug_print(f"❌ 下载最终失败，已重试 {max_retries} 次: {str(e)[:100]}")
                return False
                
        except Exception as e:
            # 不可重试的异常（如磁盘空间不足、权限错误等）
            debug_print(f"❌ 下载失败（不可重试的错误）: {str(e)[:100]}")
            return False
    
    return False


def clear_python_cache(py_file_path: str):
    """清理Python中间件的缓存"""
    try:
        # 清理pyc文件
        try:
            pyc_file = importlib.util.cache_from_source(py_file_path)
            if os.path.exists(pyc_file):
                os.remove(pyc_file)
        except Exception:
            pass
            
        # 清理__pycache__目录
        cache_dir = os.path.join(os.path.dirname(py_file_path), "__pycache__")
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
            except Exception:
                pass
    except Exception as e:
        debug_print(f"清理缓存失败: {e}")


def check_network_connectivity() -> bool:
    """
    检测网络连通性
    
    
    参数:
        test_url: 测试中间件下载服务端连通性
    
    返回:
        bool: 网络是否可用
    """
    try:
        test_url = "http://yuhualhh.250666.xyz"
        debug_print(f"🌐 检测网络连通性: {test_url}")
        response = requests.head(test_url, timeout=15)
        is_connected = response.status_code < 400
        if is_connected:
            debug_print("✅ 网络连接正常")
        else:
            debug_print(f"⚠️  网络连接异常，状态码: {response.status_code}")
        return is_connected
    except Exception as e:
        debug_print(f"❌ 网络连接检测失败: {str(e)[:100]}")
        return False


def enable_text_to_image(sender: middleware.Sender):
    """替换中间件"""
    if not sender.isAdmin():
        sender.reply("❌ 权限不足：若非管理员请勿操作")
        return

    try:
        sender.reply("🔄 正在智能识别版本并替换中间件...")
        
        base_url = get_base_url_by_version()
        
        if not check_network_connectivity():
            sender.reply("❌ 网络连接异常，请检查网络后重试")
            return

        try:
            current_workdir, current_plugin_file, middleware_module_file, py_middleware_path, js_middleware_path = resolve_middleware_paths()
        except Exception as e:
            sender.reply(f"❌ 定位中间件路径失败: {e}")
            return

        if DEBUG:
            printf(f"\n===== [REPLACE MIDDLEWARE DEBUG START] =====", "DEBUG")
            printf(f"CWD: {current_workdir}", "DEBUG")
            printf(f"PLUGIN FILE: {current_plugin_file}", "DEBUG")
            printf(f"MIDDLEWARE MODULE FILE: {middleware_module_file}", "DEBUG")
            printf(f"RESOLVED PY PATH: {py_middleware_path}", "DEBUG")
            printf(f"RESOLVED JS PATH: {js_middleware_path}", "DEBUG")
            printf(f"PY EXISTS BEFORE: {os.path.exists(py_middleware_path)}", "DEBUG")
            printf(f"JS EXISTS BEFORE: {os.path.exists(js_middleware_path)}", "DEBUG")
            printf(f"BASE URL: {base_url}", "DEBUG")

        files_config = [
            {
                "name": "Python中间件",
                "path": py_middleware_path,
                "url": f"{base_url}middleware-img.py",
                "needs_reload": True
            },
            {
                "name": "JavaScript中间件",
                "path": js_middleware_path,
                "url": f"{base_url}middleware-img.js",
                "needs_reload": False
            }
        ]
        
        success_count = 0
        total_count = len(files_config)
        failed_files = []
        
        for file_config in files_config:
            name = file_config["name"]
            path = file_config["path"]
            url = file_config["url"]
            needs_reload = file_config["needs_reload"]
            
            try:
                debug_print(f"\n📁 开始处理{name}...")
                if DEBUG:
                    printf(f"[{name}] TARGET PATH: {path}", "DEBUG")
                    printf(f"[{name}] DOWNLOAD URL: {url}", "DEBUG")
                    printf(f"[{name}] EXISTS BEFORE: {os.path.exists(path)}", "DEBUG")
                    printf(f"[{name}] BACKUP PATH: {path + '.bak'}", "DEBUG")
                
                backup_success = backup_middleware_file(path)
                if backup_success:
                    debug_print(f"✅ {name}备份成功")
                    if DEBUG:
                        printf(f"[{name}] BACKUP EXISTS AFTER: {os.path.exists(path + '.bak')}", "DEBUG")
                else:
                    if DEBUG:
                        printf(f"[{name}] BACKUP SKIPPED OR FAILED", "DEBUG")
                
                download_success = download_middleware_file(url, path, max_retries=3)
                
                if download_success:
                    if DEBUG:
                        printf(f"[{name}] EXISTS AFTER DOWNLOAD: {os.path.exists(path)}", "DEBUG")
                        try:
                            printf(f"[{name}] FILE SIZE AFTER DOWNLOAD: {os.path.getsize(path)}", "DEBUG")
                        except Exception:
                            pass

                    if needs_reload:
                        debug_print(f"🧹 清理{name}缓存...")
                        if DEBUG:
                            printf(f"[{name}] CLEAR CACHE PATH: {path}", "DEBUG")
                        clear_python_cache(path)
                        
                        try:
                            debug_print(f"🔄 热重载{name}...")
                            with open(path, 'r', encoding='utf-8') as f:
                                new_code = f.read()
                            if DEBUG:
                                printf(f"[{name}] CODE LENGTH: {len(new_code)}", "DEBUG")
                            exec(new_code, middleware.__dict__)
                            debug_print(f"✅ {name}热重载成功")
                            if DEBUG:
                                printf(f"[{name}] HOT RELOAD SUCCESS", "DEBUG")
                        except Exception as e:
                            debug_print(f"⚠️  {name}热重载失败: {e}")
                            if DEBUG:
                                printf(f"[{name}] HOT RELOAD FAILED: {e}", "WARN")
                    
                    success_count += 1
                    debug_print(f"✅ {name}更新成功")
                else:
                    failed_files.append(name)
                    if DEBUG:
                        printf(f"[{name}] DOWNLOAD FAILED", "WARN")
                    if backup_success:
                        restore_from_backup(path)
                        debug_print(f"🔄 {name}下载失败，已恢复备份")
                        if DEBUG:
                            printf(f"[{name}] RESTORE FROM BACKUP EXECUTED", "DEBUG")
                    
            except Exception as e:
                failed_files.append(name)
                debug_print(f"❌ 处理{name}时发生异常: {e}")
                if DEBUG:
                    printf(f"[{name}] EXCEPTION: {e}", "WARN")
        
        try:
            plugin_file_for_touch = globals().get("__file__", "")
            if plugin_file_for_touch:
                os.utime(plugin_file_for_touch, None)
                debug_print("🔄 触发框架重载...")
                if DEBUG:
                    printf("PLUGIN FILE MTIME TOUCHED", "DEBUG")
        except Exception as e:
            debug_print(f"⚠️  框架重载触发失败: {e}")
            if DEBUG:
                printf(f"PLUGIN FILE MTIME TOUCH FAILED: {e}", "WARN")
        
        if DEBUG:
            printf(f"SUCCESS COUNT: {success_count}/{total_count}", "DEBUG")
            printf(f"FAILED FILES: {failed_files}", "DEBUG")
            printf(f"PY EXISTS FINAL: {os.path.exists(py_middleware_path)}", "DEBUG")
            printf(f"JS EXISTS FINAL: {os.path.exists(js_middleware_path)}", "DEBUG")
            printf(f"=====[REPLACE MIDDLEWARE DEBUG END] =====\n", "DEBUG")

        if success_count == total_count:
            sender.reply("✅ 替换中间件成功")
        elif success_count > 0:
            failed_list = "、".join(failed_files) if failed_files else "部分文件"
            sender.reply(f"⚠️  部分中间件未能完成替换，请重新执行命令")
        else:
            sender.reply("❌ 替换中间件失败")
            
    except Exception as e:
        sender.reply(f"❌ 替换中间件时发生异常: {e}")



# --- 管理功能：插件列表管理 ---
def manage_plugin_list(sender: middleware.Sender):
    """处理插件列表的增删查操作"""
    if not sender.isAdmin():
        sender.reply("❌ 您没有权限执行此操作")
        return

    message = sender.getMessage()
    bucket_name = "yuhua_wbzt"
    key_name = "img"

    try:
        # 获取当前列表
        current_plugins_str = middleware.bucketGet(bucket_name, key_name) or ""
        plugin_list = current_plugins_str.split(',') if current_plugins_str else []
        # 移除可能存在的空字符串
        plugin_list = [p.strip() for p in plugin_list if p.strip()]

        if message == "文本转图列表":
            if not plugin_list:
                sender.reply("❌ 暂未添加文本转图插件")
            else:
                reply_msg = "✨ 文本转图列表：\n" + "\n".join(f"{p}" for p in plugin_list)
                sender.reply(reply_msg)
        
        elif message.startswith("添加文本转图"):
            parts = message.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                # 如果没有提供插件名，显示帮助菜单
                reply_msg = "✨ 文本转图列表：\n"
                if plugin_list:
                    reply_msg += "\n".join(f"{p}" for p in plugin_list)
                else:
                    reply_msg += "（暂无）"
                reply_msg += "\n\n🎉 触发指令：\n添加文本转图 插件名称"
                sender.reply(reply_msg)
                return
            
            plugin_to_add = parts[1].strip()
            if plugin_to_add in PROTECTED_PLUGIN_TITLES:
                sender.reply("❌ 安全拦截：为防止死循环瘫痪，系统基建插件已列入内置黑名单，禁止开启转图！")
                return            
            if plugin_to_add in plugin_list:
                sender.reply(f"✅ 插件 '{plugin_to_add}' 已在列表中")
            else:
                plugin_list.append(plugin_to_add)
                new_plugins_str = ",".join(plugin_list)
                middleware.bucketSet(bucket_name, key_name, new_plugins_str)
                sender.reply(f"✅ 成功添加文本转图插件：{plugin_to_add}")

        elif message.startswith("删除文本转图"):
            parts = message.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                # 如果没有提供插件名，显示帮助菜单
                reply_msg = "✨ 文本转图列表：\n"
                if plugin_list:
                    reply_msg += "\n".join(f"{p}" for p in plugin_list)
                else:
                    reply_msg += "（暂无）"
                reply_msg += "\n\n🎉 触发指令：\n删除文本转图 插件名称"
                sender.reply(reply_msg)
                return

            plugin_to_remove = parts[1].strip()
            if plugin_to_remove in plugin_list:
                plugin_list.remove(plugin_to_remove)
                new_plugins_str = ",".join(plugin_list)
                middleware.bucketSet(bucket_name, key_name, new_plugins_str)
                sender.reply(f"✅ 成功删除文本转图插件：{plugin_to_remove}")
            else:
                sender.reply(f"❌ 列表中不存在该插件：{plugin_to_remove}")

    except Exception as e:
        sender.reply(f"❌ 插件列表操作失败：{e}")


# --- 管理功能：主题切换 ---
def handle_theme_change(sender: middleware.Sender):
    """处理主题切换的管理员指令"""
    if not sender.isAdmin():
        sender.reply("❌ 您没有权限执行此操作")
        return

    message = sender.getMessage()
    
    try:
        # 匹配格式：切换转图主题 主题名称
        match = re.match(r"^切换转图主题\s+(.+)$", message)
        if not match:
            current_theme = get_config_theme()
            available_themes = get_available_themes()
            
            reply_msg = f"✨ 当前主题：\n"
            reply_msg += f"{current_theme}\n\n"
            
            if available_themes:
                themes_str = "、".join(available_themes)
                reply_msg += f"🎨 可用主题：\n{themes_str}\n\n"
            
            reply_msg += f"🎉 触发指令：\n"
            reply_msg += f"切换转图主题 主题名称"
            sender.reply(reply_msg)
            return

        new_theme = match.group(1).strip()
        if not new_theme:
            sender.reply("❌ 主题名称不能为空")
            return

        # 设置新主题
        if set_config_theme(new_theme):
            sender.reply(f"✅ 主题已成功切换为：{new_theme}")
        else:
            sender.reply(f"❌ 主题切换失败，请稍后重试")

    except Exception as e:
        sender.reply(f"❌ 主题切换操作失败：{e}")

def handle_api_domain_change(sender: middleware.Sender):
    """处理API域名切换的管理员指令"""
    if not sender.isAdmin():
        sender.reply("❌ 您没有权限执行此操作")
        return

    message = sender.getMessage()
    
    try:
        # 匹配格式：设置转图接口 域名
        match = re.match(r"^设置转图接口\s+(.+)$", message)
        if not match:
            current_domain = get_config_api_domain()
            
            reply_msg = f"✨ 当前接口：\n"
            reply_msg += f"{current_domain}\n\n"
            
            reply_msg += f"🎉 触发指令：\n"
            reply_msg += f"设置转图接口 域名"
            sender.reply(reply_msg)
            return

        new_domain = match.group(1).strip()
        if not new_domain:
            sender.reply("❌ 域名不能为空")
            return

        # 验证域名格式（基本验证）
        if not re.match(r'^[a-zA-Z0-9.-]+$', new_domain):
            sender.reply("❌ 域名格式不正确，请输入有效的域名（如：text2image-eo.250666.xyz）")
            return

        # 设置新域名
        if set_config_api_domain(new_domain):
            sender.reply(f"✅ 转图接口已成功设置为：{new_domain}")
        else:
            sender.reply(f"❌ 转图接口设置失败，请稍后重试")

    except Exception as e:
        sender.reply(f"❌ 转图接口设置操作失败：{e}")


# --- 管理功能：输出格式切换 ---
def upload_image_to_host(base64_data: str, retries: int = 1, delay: int = 2, timeout: int = 60):
    """将base64图片上传到图床获取直链（包含网络层和业务层重试）"""
    api_url = "http://yuhualhh.250666.xyz/img/api.php"
    data_uri = f"data:image/png;base64,{base64_data}"
    payload = {'imgbase64': data_uri}
    
    actual_retries = max(1, retries)
    total_delay = (actual_retries - 1) * delay
    per_attempt_timeout = max(1.0, (timeout - total_delay) / actual_retries)

    for i in range(actual_retries):
        try:
            if DEBUG:
                printf(f"\n===== [UPLOAD IMAGE REQUEST START] =====", "DEBUG")
                printf(f"METHOD: POST | URL: {api_url}", "DEBUG")
                printf(f"PAYLOAD: data:image/png;base64,...(Length: {len(base64_data)})", "DEBUG")

            response = requests.post(api_url, data=payload, timeout=per_attempt_timeout)
            
            if DEBUG:
                printf(f"-----[UPLOAD IMAGE RESPONSE - Attempt {i+1}] -----", "DEBUG")
                printf(f"STATUS: {response.status_code}", "DEBUG")
                printf(f"RSP BODY: {response.text}", "DEBUG")
                printf(f"=====[UPLOAD IMAGE REQUEST END] =====\n", "DEBUG")

            response.raise_for_status()
            result = response.json()
            if result.get("code") == "success" and result.get("data", {}).get("url"):
                return result["data"]["url"]
            else:
                print(f"获取图片直链失败 (尝试 {i + 1}/{actual_retries}): {result.get('msg', 'API未返回成功状态')}")
        except Exception as e:
            if DEBUG:
                printf(f"⚠️ Upload API Attempt {i + 1} FAILED (Error): {e}", "WARN")
            print(f"获取图片直链请求异常 (尝试 {i + 1}/{actual_retries}): {e}")
        if i < actual_retries - 1:
            time.sleep(delay)
    return None
    

# --- 微服务API处理 ---
def handle_text2image_api(sender: middleware.Sender):
    try:
        request_body = sender.getRouterBody()
        if not request_body:
            response = {"success": False, "error": "请求体为空", "code": 400}
            sender.reply(json.dumps(response, ensure_ascii=False))
            return
        try:
            request_data = json.loads(request_body)
        except json.JSONDecodeError as e:
            response = {"success": False, "error": f"JSON解析失败: {str(e)}", "code": 400}
            sender.reply(json.dumps(response, ensure_ascii=False))
            return
        text_to_convert = request_data.get("text", "")
        if not text_to_convert:
            response = {"success": False, "error": "text参数不能为空", "code": 400}
            sender.reply(json.dumps(response, ensure_ascii=False))
            return
        if "[CQ:file," in text_to_convert or "[CQ:video," in text_to_convert:
            response = {"success": False, "error": "内容包含文件或视频CQ码，跳过转图", "code": 422}
            sender.reply(json.dumps(response, ensure_ascii=False))
            return
        
        timeout_budget = request_data.get("timeout_budget", 115)
        start_time = time.time()

        user_context = request_data.get("userContext", {})
        user_id = user_context.get("userId", "")
        chat_id = user_context.get("chatId", "")
        im_type = user_context.get("imType", "")
        custom_params = {key: value for key, value in request_data.items() if key in ["theme"]}
        result_data = None
        image_pattern = r'\[CQ:image,file=(https?://[^\]]+)\]|\[CQ:image,file=(base64://[^\]]+)\]'
        image_matches = re.findall(image_pattern, text_to_convert)
        if len(image_matches) >= 1:
            elements = parse_multi_element_content(text_to_convert)
            if elements and len(elements) > 0:
                result_data = convert_multi_element_to_image_url(elements, custom_params=custom_params, timeout=timeout_budget)
        else:
            result_data = convert_text_to_image_url(text_to_convert, custom_params=custom_params, timeout=timeout_budget)
        
        if result_data:
            cq_code = ""
            image_url = ""
            if result_data.startswith("http://") or result_data.startswith("https://"):
                image_url = result_data
                cq_code = f"[CQ:image,file={image_url}]"
            else:
                try:
                    push_enabled = middleware.bucketGet("yuhua_wbzt", "push")
                    use_http = push_enabled == True or push_enabled == "true"
                except Exception:
                    use_http = False
                
                if use_http:
                    elapsed_time = time.time() - start_time
                    remaining_budget = timeout_budget - elapsed_time
                    
                    if remaining_budget > 0:
                        uploaded_url = upload_image_to_host(result_data, timeout=remaining_budget)
                        if uploaded_url:
                            image_url = uploaded_url
                            cq_code = f"[CQ:image,file={uploaded_url}]"
                        else:
                            response = {"success": False, "error": "图片生成成功，但上传图床获取直链失败", "originalText": text_to_convert, "code": 500}
                            sender.reply(json.dumps(response, ensure_ascii=False))
                            return
                    else:
                        response = {"success": False, "error": "图片生成成功，但上传图床时间不足", "originalText": text_to_convert, "code": 500}
                        sender.reply(json.dumps(response, ensure_ascii=False))
                        return
                else:
                    cq_code = f"[CQ:image,file=base64://{result_data}]"

            response = {
                "success": True,
                "imageUrl": image_url,
                "cqCode": cq_code,
                "code": 200
            }
        else:
            response = {"success": False, "error": "图片转换失败", "originalText": text_to_convert, "code": 500}
        sender.reply(json.dumps(response, ensure_ascii=False))
    except Exception as e:
        response = {"success": False, "error": f"服务器内部错误: {str(e)}", "code": 500}
        sender.reply(json.dumps(response, ensure_ascii=False))
        
        
def toggle_text_to_image_status(sender: middleware.Sender, enable: bool):
    if not sender.isAdmin():
        sender.reply("❌ 权限不足：若非管理员请勿操作")
        return
    status_str = "true" if enable else "false"
    action_str = "开启" if enable else "关闭"
    try:
        middleware.bucketSet("yuhua_wbzt", "enabled", status_str)
        sender.reply(f"✅ 文本转图功能已{action_str}")
    except Exception as e:
        sender.reply(f"❌ {action_str}文本转图功能时发生错误: {e}")

def handle_plugin_management(sender: middleware.Sender, title: str, bucket_name: str, key_name: str):
    """处理文本转图与支付接管的沉浸式交互管理"""
    if not sender.isAdmin():
        sender.reply("❌ 您没有权限执行此操作")
        return

    while True:
        try:
            plugin_names = set()

            # 1. 从本地插件桶中提取所有已安装的插件（原有逻辑保留）
            for b in ["plugins_script"]:
                keys_data = middleware.bucketAllKeys(b)
                if not keys_data:
                    continue
                # 兼容返回格式(字符串或列表)
                keys_list = keys_data.split(',') if isinstance(keys_data, str) else keys_data
                for k in keys_list:
                    k = str(k).strip()
                    if not k:
                        continue
                    # 提取冒号后面的文件名 (e.g. hunyan:Y_查询.js -> Y_查询.js)
                    if ':' in k:
                        k = k.split(':', 1)[1]

                    # --- 【新增完美过滤逻辑】读取 plugins_script 时，仅放行 .js 和 .py 结尾的插件 ---
                    if not (k.endswith('.js') or k.endswith('.py')):
                        continue

                    # 剥离后缀名 (e.g. Y_查询.js -> Y_查询)
                    name = os.path.splitext(k)[0]
                    if '@' in name:
                        name = name.split('@', 1)[1].strip()
                    if name:
                        plugin_names.add(name)

            # 1.1 若能获取到账密，则额外读取本地的所有 py、js 插件（参考云市场助手实现）
            try:
                username = sender.bucketGet("autMan", "adminUsername")
                password = sender.bucketGet("autMan", "adminPassword")
                autman_port = middleware.port()

                if username and password and autman_port:
                    cookie = None
                    login_url = f"http://127.0.0.1:{autman_port}/login"
                    login_data = {"username": username, "password": password}
                    login_headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}

                    for _ in range(3):
                        try:
                            login_response = requests.post(login_url, data=login_data, headers=login_headers, timeout=5)
                            if login_response.status_code == 200:
                                login_json = login_response.json()
                                if login_json.get("code") == 200:
                                    set_cookie = login_response.headers.get("Set-Cookie", "")
                                    if set_cookie:
                                        cookie = set_cookie.split(';')[0]
                                        break
                        except Exception:
                            time.sleep(1)

                    if cookie:
                        shelf_url = f"http://127.0.0.1:{autman_port}/shelf"
                        shelf_headers = {"Cookie": cookie}
                        for _ in range(3):
                            try:
                                shelf_response = requests.get(shelf_url, headers=shelf_headers, timeout=10)
                                if shelf_response.status_code == 200:
                                    shelf_json = shelf_response.json()
                                    if shelf_json.get("code") == 200:
                                        all_plugins = shelf_json.get("data", [])
                                        for plugin in all_plugins:
                                            plugin_title = str(plugin.get("title", "")).strip()
                                            plugin_language = str(plugin.get("language", "")).strip().lower()
                                            plugin_path = str(plugin.get("plugin_path", "")).strip()

                                            is_py_js_plugin = False

                                            if plugin_language in ["python", "py", "javascript", "js"]:
                                                is_py_js_plugin = True
                                            elif plugin_path.endswith(".py") or plugin_path.endswith(".js"):
                                                is_py_js_plugin = True

                                            if plugin_title and is_py_js_plugin:
                                                plugin_names.add(plugin_title)
                                        break
                            except Exception:
                                time.sleep(1)
            except Exception:
                pass

            # 2. 获取当前配置中已开启的插件列表
            current_str = middleware.bucketGet(bucket_name, key_name) or ""
            enabled_list = [p.strip() for p in current_str.split(',') if p.strip()]

            filtered_enabled_list = []
            filtered_removed = False
            for _plugin_name in enabled_list:
                if _plugin_name in PROTECTED_PLUGIN_TITLES:
                    filtered_removed = True
                    continue
                filtered_enabled_list.append(_plugin_name)
            if filtered_removed:
                enabled_list = filtered_enabled_list
                middleware.bucketSet(bucket_name, key_name, ",".join(enabled_list))

            enabled_set = set(enabled_list)

            # 3. 补充合并：将手动添加但在本地不存在的插件纳入展示范围
            # （若该手动添加的插件被关闭，下一轮则不会在 enabled_set 中，自然在列表中隐去）
            plugin_names.update(enabled_set)

            for _protected_plugin_title in PROTECTED_PLUGIN_TITLES:
                plugin_names.discard(_protected_plugin_title)

            # 转换为有序列表以固定显示顺序
            # 「消息规则-回复」为固定条目，永远置顶为 [0]（序号即其在列表中的位置）：
            # 管理员可开启/关闭文本转图对消息规则（自动回复）的接管，不可移除
            if "消息规则-回复" in plugin_names:
                plugin_names.discard("消息规则-回复")
            sorted_plugins = ["消息规则-回复"] + sorted(list(plugin_names))

            total_count = len(sorted_plugins)
            enabled_count = len(enabled_set)
            disabled_count = total_count - enabled_count

            # 4. 构建UI排版
            reply_lines = [
                f"====={title}=====",
                f"🎉 插件数量: {total_count}",
                f"✨ 开启数量: {enabled_count}",
                f"💢 关闭数量: {disabled_count}",
                "------------------"
            ]

            # 序号从 0 开始：[0] 固定为「消息规则-回复」，其余插件从 [1] 起
            for idx, p_name in enumerate(sorted_plugins, 0):
                status = "✅ 开启" if p_name in enabled_set else "❌ 关闭"
                reply_lines.append(f"[{idx}] {p_name}\n    {status}")

            reply_lines.append("------------------")
            reply_lines.append("t=全部开启, f=全部关闭, q=退出操作")
            reply_lines.append("+序号或名称=开启, -序号或名称=关闭")

            # 发送菜单并等待用户指令
            sender.reply("\n".join(reply_lines))

            user_input = sender.input(60000, 0, False)
            if not user_input:
                sender.reply("❌ 输入超时，已自动退出操作")
                return

            cmd = str(user_input).strip()

            if cmd.lower() == 'q':
                sender.reply("✅ 已退出操作")
                return

            # 处理全部开启 / 全部关闭
            if cmd.lower() == 't':
                middleware.bucketSet(bucket_name, key_name, ",".join(sorted_plugins))
                sender.reply("✅ 已全部开启")
                continue

            if cmd.lower() == 'f':
                middleware.bucketSet(bucket_name, key_name, "")
                sender.reply("✅ 已全部关闭")
                continue

            # 处理单独开启 / 关闭
            if cmd.startswith('+') or cmd.startswith('-'):
                action = cmd[0]
                target = cmd[1:].strip()

                target_plugin = None
                if target.isdigit():
                    idx = int(target)
                    if 0 <= idx < len(sorted_plugins):
                        target_plugin = sorted_plugins[idx]
                else:
                    if target:
                        target_plugin = target

                if not target_plugin:
                    sender.reply("❌ 无效的序号或名称，请重试")
                    continue

                if ',' in target_plugin or '，' in target_plugin:
                    sender.reply("❌ 插件名称中不能包含逗号，请重试")
                    continue

                if target_plugin in PROTECTED_PLUGIN_TITLES and action == '+':
                    sender.reply("❌ 安全拦截：为防止系统基建插件发生自接管或互相接管，内置黑名单插件禁止添加！")
                    continue

                if action == '+':
                    if target_plugin not in enabled_list:
                        enabled_list.append(target_plugin)
                        middleware.bucketSet(bucket_name, key_name, ",".join(enabled_list))
                        sender.reply(f"✅ 已开启: {target_plugin}")
                    else:
                        sender.reply(f"⚠️ {target_plugin} 已经是开启状态")
                elif action == '-':
                    if target_plugin in enabled_list:
                        enabled_list.remove(target_plugin)
                        middleware.bucketSet(bucket_name, key_name, ",".join(enabled_list))
                        sender.reply(f"✅ 已关闭: {target_plugin}")
                    else:
                        sender.reply(f"⚠️ {target_plugin} 已经是关闭状态")
            else:
                sender.reply("❌ 无效的指令格式，请重试")

        except Exception as e:
            sender.reply(f"❌ 管理列表操作发生异常: {e}")
            return
            

# --- 核心积分业务功能 ---

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
                timeout=30,
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

# --- 主函数：指令分发 ---

# --- 主函数：指令分发 ---
def main():
    sender = middleware.Sender(middleware.getSenderID())
    if not check_maintenance_page():
        sender.reply("❌ 服务端无法连通, 插件停止运行")
        return
        
    # 处理被中间件路由过来的微服务请求
    if sender.getImtype() == 'rt':
        router_path = sender.getRouterPath()
        if router_path == "/text2image":
            handle_text2image_api(sender)
        return
        
    # 处理聊天群/私聊发出的交互指令
    message = sender.getMessage()
    if message == "文本转图":
        sender.reply("""
        
请回复以下指令：
切换转图主题
设置转图接口
开启文本转图
关闭文本转图
管理文本转图""")
    elif message == "开启文本转图":
        toggle_text_to_image_status(sender, enable=True)
    elif message == "关闭文本转图":
        toggle_text_to_image_status(sender, enable=False)
    elif message == "替换中间件":
        enable_text_to_image(sender)
    elif message == "还原中间件":
        reset_text_to_image(sender)
    elif message.startswith("文本转图列表") or message.startswith("添加文本转图") or message.startswith("删除文本转图"):
        manage_plugin_list(sender)
    elif message.startswith("切换转图主题"):
        handle_theme_change(sender)
    elif message.startswith("设置转图接口"):
        handle_api_domain_change(sender)
    elif message == "管理文本转图":
        handle_plugin_management(sender, "管理文本转图", "yuhua_wbzt", "img")
    else:
        pass


if __name__ == '__main__':
    main()
