# [title: 插件数据迁移]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@0962a854c10ff46e6cea733453fb39ad4535b243/2026/08/05/968cf1f5878f4c34e963afe81346960c.png]
# [language: python]
# [rule: ^插件数据(导出|导入|测试重启)$]
# [disable:false]
# [open_source: false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [priority: 999999999]
# [public: true]
# [admin: true]
# [version: 1.0.0]
# [author: yuhualhh]
# [price: 0]
# [service: ]
# [description: ❶这是一个用于迁移奥特曼插件数据的插件，默认导出羽化系列插件数据，可通过自定义正则导出任意数据桶进行迁移<br>❷使用本插件需授予一定权限，前往"系统管理-插件权限"全部启用<img src="https://gcore.jsdelivr.net/gh/lhz03/img@6f32560e6260ca49eb0250c004027d73dcbb8383/2026/08/05/b687467c06e968c9e537230018b3c5de.png">]
# [param: {"required":false,"key":"yuhua_migrate.bucket_pattern","bool":false,"placeholder":"yuhua_.*","name":"导出正则","desc":"留空默认yuhua_.*导出羽化系列插件数据"}]

import hashlib
import json
import os
import re
import sys
import time
import uuid

import requests

try:
    import middleware
except Exception:
    middleware = None

DEFAULT_PATTERN = r"yuhua_.*"
MIGRATE_BUCKET = "yuhua_migrate"

MIGRATE_SERVER = "http://yuhualhh.250666.xyz/api/plugin_migrate.php"
MIGRATE_API_SECRET = "7WiYGRDUnUszw3VNXLRBMlOD1GS3K2I5n5FftAcouOQ"
MIGRATE_ENC_SECRET = "Qnq6EcoMnX3MS0PiBIOPn-FMzJdavNWeFRBMXxCar0Y"

def _config_get(key):
    if middleware is not None:
        try:
            return (middleware.bucketGet(MIGRATE_BUCKET, key) or "").strip()
        except Exception:
            pass
    return ""

def _get_config():
    pattern = _config_get("bucket_pattern") or DEFAULT_PATTERN
    return {
        "server": MIGRATE_SERVER,
        "secret": MIGRATE_API_SECRET,
        "enc_key": MIGRATE_ENC_SECRET,
        "pattern": pattern,
    }

def _make_request(method, url, **kwargs):
    for _ in range(3):
        try:
            resp = requests.request(method, url, timeout=kwargs.pop("timeout", 15), **kwargs)
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception:
                    return resp.text
        except Exception as e:
            pass
        time.sleep(1)
    return None

def _is_autman_platform():
    if middleware is None:
        return False
    if getattr(middleware, "sillygirl", None) is not None:
        return False
    try:
        port = middleware.port()
        return bool(port)
    except Exception:
        return False

def _all_bucket_names(cfg):
    names = set()
    if _is_autman_platform():
        try:
            names.update(_autman_http_bucket_names())
            return sorted(names)
        except Exception as e:
            return sorted(names)
    if middleware is not None:
        try:
            import sillygirl as sg
            resp = sg.get_stub().BucketBuckets(sg.srpc_pb2.Empty(), metadata=sg.metadata)
            names.update(str(n) for n in resp.buckets if n)
        except Exception as e:
            _printf(f"[插件数据迁移] 枚举桶名失败: {e}")
    return sorted(names)

_autman_cookie = ""

def _safe_bucket_get(bucket, key):
    try:
        if middleware is not None:
            return (middleware.bucketGet(bucket, key) or "").strip()
    except Exception as e:
        pass
    try:
        sid = middleware.getSenderID() if middleware is not None else ""
        s = middleware.Sender(sid)
        return (s.bucketGet(bucket, key) or "").strip()
    except Exception:
        pass
    return ""

def _clear_autman_cookie():
    global _autman_cookie
    _autman_cookie = ""
    try:
        if middleware is not None:
            middleware.bucketDel(MIGRATE_BUCKET, "autMan")
    except Exception:
        pass

def _safe_bucket_set(bucket, key, value):
    try:
        if middleware is not None:
            middleware.bucketSet(bucket, key, value)
            return True
    except Exception as e:
        pass
    try:
        sid = middleware.getSenderID() if middleware is not None else ""
        s = middleware.Sender(sid)
        s.bucketSet(bucket, key, value)
        return True
    except Exception:
        pass
    return False

def _autman_login_cookie():
    global _autman_cookie
    if _autman_cookie:
        return _autman_cookie
    cookie = _safe_bucket_get(MIGRATE_BUCKET, "autMan")
    if cookie:
        _autman_cookie = cookie
        return cookie
    username = _safe_bucket_get("autMan", "adminUsername")
    password = _safe_bucket_get("autMan", "adminPassword")
    port = middleware.port() if middleware is not None else 8080
    if not (username and password and port):
        return ""
    for _ in range(3):
        try:
            resp = requests.post(f"http://127.0.0.1:{port}/login",
                                 data={"username": username, "password": password},
                                 headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                                 timeout=5)
            if resp.status_code == 200 and resp.json().get("code") == 200:
                cookie_value = resp.headers.get("Set-Cookie", "").split(";")[0]
                try:
                    if middleware is not None:
                        middleware.bucketSet(MIGRATE_BUCKET, "autMan", cookie_value)
                except Exception:
                    pass
                _autman_cookie = cookie_value
                return cookie_value
        except Exception as e:
            pass
        time.sleep(1)
    return ""

def _autman_http_bucket_names():
    names = set()
    for attempt in range(2):
        cookie = _autman_login_cookie()
        if not cookie:
            return names
        port = middleware.port() if middleware is not None else 8080
        resp = requests.get(f"http://127.0.0.1:{port}/buckets",
                            headers={"Cookie": cookie, "X-Requested-With": "XMLHttpRequest",
                                     "User-Agent": "Mozilla/5.0"}, timeout=10)
        result = resp.json()
        if result.get("code") == 200:
            for item in result.get("data", []):
                if item.get("name"):
                    names.add(str(item["name"]))
            return names
        if result.get("code") == 401:
            _clear_autman_cookie()
            continue
        break
    return names

def _bucket_all(bucket):
    if _is_autman_platform():
        return _autman_http_bucket_data(bucket)
    if middleware is not None:
        try:
            data = middleware.bucketAll(bucket)
            if isinstance(data, dict):
                return data
        except Exception as e:
            pass
    return {}

def _autman_http_bucket_data(bucket):
    for attempt in range(2):
        try:
            cookie = _autman_login_cookie()
            if not cookie:
                return {}
            port = middleware.port() if middleware is not None else 8080
            resp = requests.get(f"http://127.0.0.1:{port}/buckets",
                                params={"bucket": bucket},
                                headers={"Cookie": cookie, "X-Requested-With": "XMLHttpRequest",
                                         "User-Agent": "Mozilla/5.0"}, timeout=10)
            result = resp.json()
            if result.get("code") == 200:
                data = {}
                for item in result.get("data", []):
                    if item.get("name") == bucket and isinstance(item.get("kvs"), list):
                        for kv in item["kvs"]:
                            if kv.get("key") is not None:
                                data[str(kv["key"])] = kv.get("value")
                return data
            if result.get("code") == 401:
                _clear_autman_cookie()
                continue
            return {}
        except Exception as e:
            pass
            return {}
    return {}

def _collect_buckets(cfg):
    compiled = re.compile(cfg["pattern"])
    result = {}
    for bucket in _all_bucket_names(cfg):
        if not compiled.match(bucket):
            continue
        data = _bucket_all(bucket)
        if data:
            result[bucket] = data
    return result

def _encrypt_aes_cbc(plaintext, enc_key):
    try:
        import base64
        import hmac
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        key = hashlib.sha256(enc_key.encode("utf-8")).digest()
        iv = os.urandom(16)
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        ct = cipher.update(padded) + cipher.finalize()
        mac = hmac.new(key, iv + ct, hashlib.sha256).digest()
        return base64.b64encode(iv + mac + ct).decode("utf-8")
    except Exception as e:
        _printf(f"[插件数据迁移] 加密失败: {e}")
        return ""

def _decrypt_aes_cbc(payload, enc_key):
    try:
        import base64
        import hmac
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        raw = base64.b64decode(payload)
        key = hashlib.sha256(enc_key.encode("utf-8")).digest()
        iv = raw[:16]
        mac = raw[16:48]
        ct = raw[48:]
        calc = hmac.new(key, iv + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(calc, mac):
            return None
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        padded = cipher.update(ct) + cipher.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        plain = unpadder.update(padded) + unpadder.finalize()
        return plain.decode("utf-8")
    except Exception as e:
        _printf(f"[插件数据迁移] 解密失败: {e}")
        return None

def _printf(msg):
    try:
        if middleware is not None and hasattr(middleware, "printf"):
            middleware.printf(msg)
        else:
            print(msg)
    except Exception:
        print(msg)

class MigrateRemote:
    def __init__(self, url, secret, token=None):
        self.url = url.rstrip('/')
        self.secret = secret
        self.token = token or "m_" + uuid.uuid4().hex + os.urandom(8).hex()

    def _headers(self):
        return {"X-API-Key": self.secret}

    def init_session(self, voucher, bucket_pattern, encrypted_data):
        payload = {
            "voucher": voucher,
            "bucket_pattern": bucket_pattern,
            "encrypted_data": encrypted_data,
            "req_secret": self.secret,
            "ts": int(time.time()),
        }
        resp = _make_request("post", f"{self.url}?action=init_session&token={self.token}",
                             json=payload, headers=self._headers(), timeout=15)
        return resp and resp.get("code") == 0

    def get_user_url(self):
        return f"{self.url}?token={self.token}"

    def get_meta(self):
        resp = _make_request("get", f"{self.url}?action=get_meta&token={self.token}",
                             headers=self._headers(), timeout=10)
        if resp and resp.get("code") == 0:
            return resp
        if resp and resp.get("code") == -1:
            return "expired"
        return None

    def poll_result(self):
        resp = _make_request("get", f"{self.url}?action=poll_result&token={self.token}",
                             headers=self._headers(), timeout=10)
        if resp and resp.get("code") == 0 and resp.get("plugin_text"):
            return True, resp
        if resp and resp.get("code") == 1 and resp.get("status") in ("success", "fail"):
            return False, resp.get("status")
        return None, None

    def report_result(self, success, msg=""):
        try:
            _make_request("post", f"{self.url}?action=report_result&token={self.token}",
                          json={"success": success, "msg": msg},
                          headers=self._headers(), timeout=10)
        except Exception:
            pass

def _prompt_box(sender, title, lines):
    text = f"====={title}=====\n"
    text += "\n".join(lines)
    text += "\n==================="
    sender.reply(text)

def _private_admin_guard(sender):
    if not sender.isAdmin():
        sender.reply("🚫 您没有权限执行此操作")
        return False
    try:
        chat_id = sender.getChatID()
        if str(chat_id) not in ("0", "", "None"):
            sender.reply("🚫 当前功能仅允许私聊使用，请切换至私聊环境后重试")
            return False
    except Exception:
        pass
    return True

def _restart_yuhua(sender):
    try:
        import sillygirl as sg
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sg.Bucket("sillyGirl").started_at = now
        return True
    except Exception as e:
        return False

def _restart_autman(sender):
    if not _is_autman_platform():
        return _restart_yuhua(sender)
    cookie = ""
    try:
        username = _safe_bucket_get("autMan", "adminUsername")
        password = _safe_bucket_get("autMan", "adminPassword")
        port = middleware.port() if middleware is not None else 8080
        if username and password:
            resp = requests.post(f"http://127.0.0.1:{port}/login",
                                 data={"username": username, "password": password},
                                 headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                                 timeout=5)
            if resp.status_code == 200 and resp.json().get("code") == 200:
                cookie = resp.headers.get("Set-Cookie", "").split(";")[0]
    except Exception:
        pass
    for endpoint in ["/restart", "/reboot", "/system/restart", "/admin/restart"]:
        try:
            port = middleware.port() if middleware is not None else 8080
            url = f"http://127.0.0.1:{port}{endpoint}"
            headers = {}
            if cookie:
                headers["Cookie"] = cookie
            resp = _make_request("post", url, headers=headers, timeout=5)
            if resp and isinstance(resp, dict) and resp.get("code") == 200:
                return True
        except Exception:
            pass
    return False

def handle_test_restart(sender):
    if not _private_admin_guard(sender):
        return
    platform = "奥特曼(AutMan)" if _is_autman_platform() else "羽化面板(yuhua)"
    sender.reply(f"🔍 检测到当前平台: {platform}，正在测试重启...")
    if _restart_autman(sender):
        sender.reply(f"✨ 已在{platform}发起重启，请等待系统恢复")
    else:
        sender.reply("⚠️ 重启指令未生效，请查看 DEBUG 日志排查")

def handle_export(sender):
    if not _private_admin_guard(sender):
        return
    cfg = _get_config()

    sender.reply(f"正在处理...")

    try:
        data = _collect_buckets(cfg)
    except Exception as e:
        sender.reply(f"🚫 获取数据桶失败: {str(e)[:100]}")
        return
    if not data:
        all_names = _all_bucket_names(cfg)
        if not all_names:
            sender.reply("🚫 未获取到任何数据桶，请检查奥特曼/羽化面板数据存储是否正常")
        else:
            sender.reply(f"🚫 正则 {cfg['pattern']} 未匹配到数据桶（共枚举到 {len(all_names)} 个桶）")
        return

    plaintext = json.dumps(data, ensure_ascii=False)
    encrypted = _encrypt_aes_cbc(plaintext, cfg["enc_key"])
    if not encrypted:
        sender.reply("🚫 数据加密失败，请检查加密依赖（cryptography）")
        return

    voucher_salt = hashlib.sha256((cfg["enc_key"] + ":" + cfg["pattern"]).encode()).hexdigest()[:16]
    voucher = f"{voucher_salt}-{cfg['pattern']}"
    remote = MigrateRemote(cfg["server"], cfg["secret"])
    if not remote.init_session(voucher, cfg["pattern"], encrypted):
        sender.reply("🚫 上传到后端失败，请检查服务器配置/网络")
        return

    sender.reply(f"迁移凭证: {voucher}")
    sender.reply(f"迁移链接: {remote.get_user_url()}")
    _prompt_box(sender, "自动导入教程", [
        "①请在10分钟内复制迁移凭证与迁移链接",
        "②在目标机器安装『插件数据迁移』插件",
        "③发指令『插件数据导入』，先粘贴迁移凭证，再粘贴迁移链接",
        "④导入完成自动重启，插件数据即生效",
    ])

def handle_import(sender):
    if not _private_admin_guard(sender):
        return
    cfg = _get_config()

    _prompt_box(sender, "插件数据导入", [
        "请输入迁移凭证",
        "------------------",
        "请在60秒内完成",
        '输入"q"退出',
    ])
    voucher_input = sender.input(60000, 0, False)
    if not voucher_input:
        sender.reply("❌ 输入超时")
        return
    if str(voucher_input).strip().lower() == 'q':
        sender.reply("✅ 已退出操作")
        return

    voucher_data = _parse_voucher(str(voucher_input).strip())
    if not voucher_data:
        sender.reply("🚫 迁移凭证格式错误，请检查后重新输入")
        return

    _prompt_box(sender, "插件数据导入", [
        "请输入迁移链接",
        "------------------",
        "请在60秒内完成",
        '输入"q"退出',
    ])
    link_input = sender.input(60000, 0, False)
    if not link_input:
        sender.reply("❌ 输入超时")
        return
    if str(link_input).strip().lower() == 'q':
        sender.reply("✅ 已退出操作")
        return

    token = _extract_token(str(link_input))
    if not token:
        sender.reply("🚫 迁移链接格式错误")
        return

    sender.reply("正在处理...")

    remote = MigrateRemote(cfg["server"], cfg["secret"], token)
    meta = remote.get_meta()
    if meta == "expired":
        sender.reply("🚫 迁移链接已超时销毁")
        return
    if not meta:
        sender.reply("🚫 获取迁移信息失败，请稍后再试")
        return
    if str(meta.get("voucher", "")) != str(voucher_data["voucher"]):
        sender.reply("🚫 迁移凭证与迁移链接不匹配")
        return
    if meta.get("status") in ("success", "fail"):
        sender.reply("🚫 该迁移链接已被处理完成")
        return

    status, result = None, None
    start = time.time()
    while time.time() - start < 60:
        status, result = remote.poll_result()
        if status is True and result:
            break
        if status is False:
            if result == "expired":
                sender.reply("🚫 迁移链接已超时销毁")
                return
            sender.reply("🚫 该迁移链接状态异常")
            return
        time.sleep(1)

    if not (status is True and result):
        sender.reply("🚫 获取迁移数据超时")
        return

    encrypted = result.get("plugin_text", "")
    if not encrypted:
        remote.report_result(False, "迁移数据为空")
        sender.reply("🚫 迁移数据为空")
        return

    plaintext = _decrypt_aes_cbc(encrypted, cfg["enc_key"])
    if plaintext is None:
        remote.report_result(False, "解密失败")
        sender.reply("🚫 解密失败（加密密钥不匹配？）")
        return

    try:
        data = json.loads(plaintext)
        if not isinstance(data, dict):
            raise ValueError("数据格式错误")
    except Exception as e:
        remote.report_result(False, f"数据解析失败: {str(e)[:80]}")
        sender.reply(f"🚫 数据解析失败: {str(e)[:80]}")
        return

    written = 0
    skipped = 0
    failed = 0
    total = sum(len(v) for v in data.values() if isinstance(v, dict))
    for bucket, kv in data.items():
        if not isinstance(kv, dict):
            continue
        if not _safe_name(bucket):
            skipped += 1
            continue
        for key, value in kv.items():
            if not _safe_name(str(key)):
                skipped += 1
                continue
            if _safe_bucket_set(bucket, key, value):
                written += 1
            else:
                failed += 1

    if skipped or failed:
        sender.reply(f"⚠️ 部分数据未写入: 跳过{skipped} 失败{failed}（通常是键名含特殊字符）")

    remote.report_result(True, f"写入成功: {written}/{total}")
    _prompt_box(sender, "插件数据导入", [
        f"🗯️ 写入桶数: {len(data)}",
        f"🔑 写入键数: {written}/{total}",
        "------------------",
        "❶即将进行自动重启",
        "❷可以选择暂停重启",
        "------------------",
        "请在10秒内输入",
        '输入"q"暂停',
    ])
    restart_input = sender.input(10000, 0, False)
    if restart_input and str(restart_input).strip().lower() in ("q", "取消"):
        sender.reply("✨ 已取消重启操作，请自行重启生效")
        return
    if _restart_autman(sender):
        sender.reply("✨ 已发起重启指令，请等待系统恢复")
    else:
        sender.reply("⚠️ 自动重启未成功，请手动重启")

def _safe_name(name):
    if not name or len(name) > 200:
        return False
    if ".." in name or "/" in name or "\\" in name:
        return False
    if "\x00" in name:
        return False
    return True

_VOUCHER_TOKEN_RE = re.compile(r'([0-9a-fA-F]{8,32}-[\w.*$^|()+\[\]-]{1,200})')

def _parse_voucher(text):
    text = str(text).strip()
    if not text:
        return None
    match = _VOUCHER_TOKEN_RE.search(text)
    if not match:
        return None
    voucher = match.group(1)
    salt, pattern = voucher.split("-", 1)
    return {
        "voucher": voucher,
        "enc_salt": salt,
        "bucket_pattern": pattern,
    }

def _extract_token(text):
    text = str(text).strip()
    if not text:
        return ""
    m = re.search(r'token=([a-zA-Z0-9_]+)', text)
    if m:
        return m.group(1)
    m = re.search(r'(?:迁移链接|链接|url)[:：\s]*(\S+)', text)
    if m:
        url = m.group(1)
        m2 = re.search(r'token=([a-zA-Z0-9_]+)', url)
        return m2.group(1) if m2 else ""
    if re.fullmatch(r'[a-zA-Z0-9_]{8,64}', text):
        return text
    return ""

def main():
    try:
        sender_id = middleware.getSenderID()
    except Exception:
        sender_id = ""
    sender = middleware.Sender(sender_id)
    msg = sender.getMessage().strip()

    if msg == "插件数据导出":
        handle_export(sender)
    elif msg == "插件数据导入":
        handle_import(sender)
    elif msg == "插件数据测试重启":
        handle_test_restart(sender)

if __name__ == "__main__":
    main()
