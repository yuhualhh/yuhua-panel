# [pin: true]
# [title: 支付接管]
# [language: python]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@9ae7129b6ed8df625254f8d5124497313838f109/2026/04/10/ed70df4c4bd110811434662c2ec69a51.png]
#[rule: ^(支付接管|.*中间件|.*支付接管|核心(积分|卡密).*)$]
# [disable:false]
# [router: /epay_hijack]
# [method: post]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [public: true]
# [open_source: false]
# [class: 工具类]
# [version: 1.0.4]
# [price: 0]
# [admin: false]
# [author: yuhualhh]
# [service: 2550306191]
# [description: ❶该插件可为任意订阅源的Python、NodeJS插件提供支付接管与积分卡密系统服务。使内置微信支付被支付宝商家账单免挂或易支付或积分抵扣所接管，同时兼容V1接口(MD5签名方式)各大码支付平台<br>❷先发指令『替换中间件』待提示替换成功，继续发送指令『开启支付接管』待提示已开启，然后重启奥特曼使插件生效，再发指令『管理支付接管』添加需启用支付接管的插件。如需暂时关闭则发指令『关闭支付接管』<br>❸使用本插件需授予一定权限，前往"系统管理-插件权限"全部启用<br>❹更新日志: 2026.07.07 00:35 自动识别待付金额无需手动输入核对，需发指令『替换中间件』更新一下<img src="https://gcore.jsdelivr.net/gh/lhz03/img@29949cd67168912e9b439d29d52a1a509fc70be2/2026/03/28/72bbaadb24ca85e3afb59b270e448cdd.png">]
import middleware,requests,re,os,importlib,json,threading,shutil,time,random,sys
from datetime import datetime
from requests.exceptions import ConnectionError, Timeout
from bs4 import BeautifulSoup
from urllib.parse import quote
PROTECTED_PLUGIN_TITLES =["羽化核心", "文本转图", "支付接管"]
#[param: {"required":true,"key":"yuhua_epay.plugins","placeholder":"例: 插件A,插件B","name":"支付接管列表","desc":"各插件之间用英文符,分割"}]
#[param: {"required":false,"key":"yuhua_epay.amount_regex","placeholder":"例: 应付(\\d+\\.?\\d*)元","name":"正则匹配金额","desc":"多个正则使用中文符｜分隔，命中则跳过手动核对金额流程"}]
# [param: {"spliter":true}]
#[param: {"required":false,"key":"yuhua_epay.alipay_bill","bool":true,"placeholder":"","name":"某宝商家账单","desc":"启用支付宝商家账单免挂通道收款，配置教程: https://my.feishu.cn/docx/R280dtOaWothSix6KBRcGFxQncb"}]
#[param: {"required":false,"key":"yuhua_epay.alipay_qrcode","placeholder":"","name":"支付宝收款码","desc":"支付宝商家账单免挂通道的收款码直链"}]
#[param: {"required":false,"key":"yuhua_epay.alipay_app_id","placeholder":"","name":"平台的APPID","desc":"支付宝开放平台应用APPID"}]
#[param: {"required":false,"key":"yuhua_epay.alipay_private_key","placeholder":"","name":"平台应用私钥","desc":"支付宝开放平台应用私钥"}]
# [param: {"spliter":true}]
#[param: {"required":false,"key":"yuhua_epay.epay_alipay","bool":true,"placeholder":"","name":"易支付支付宝","desc":"启用易支付支付宝通道收款"}]
#[param: {"required":false,"key":"yuhua_epay.epay_wxpay","bool":true,"placeholder":"","name":"易支付的微信","desc":"启用易支付微信通道收款"}]
#[param: {"required":false,"key":"yuhua_epay.epay_qqpay","bool":true,"placeholder":"","name":"易支付的扣扣","desc":"启用易支付扣扣通道收款"}]
#[param: {"required":false,"key":"yuhua_epay.epay_url","bool":false,"placeholder":"","name":"易支付的地址","desc":"兼容V1接口(MD5签名方式)各大码支付平台"}]
#[param: {"required":false,"key":"yuhua_epay.epay_pid","bool":false,"placeholder":"","name":"平台的商户ID","desc":""}]
#[param: {"required":false,"key":"yuhua_epay.epay_key","bool":false,"placeholder":"","name":"平台商户密钥","desc":""}]
# [param: {"spliter":true}]
#[param: {"required":false,"key":"yuhua_epay.points_pay","bool":true,"placeholder":"","name":"核心积分抵扣","desc":"启用核心积分抵扣收款"}]
#[param: {"required":false,"key":"yuhua_epay.exchange_rate","bool":false,"placeholder":"100","name":"积分兑换比例","desc":"充值余额换算核心积分的比例，填100表示1元=100积分，默认100"}]
#[param: {"required":false,"key":"yuhua_epay.compat_points","bool":true,"placeholder":"","name":"兼容其他积分","desc":"弃用默认积分桶，改用下方自定义积分桶，可发指令『核心积分迁移』转移数据"}]
#[param: {"required":false,"key":"yuhua_epay.custom_points_bucket","placeholder":"如: dd_sign_points","name":"自定义数据桶","desc":"实现与其他插件积分互通，可填dd_sign_points兼容呆呆积分桶"}]
#[param: {"required":false,"key":"yuhua_epay.sign_in","bool":true,"placeholder":"","name":"核心积分签到","desc":"允许用户每天签到获取随机核心积分"}]
#[param: {"required":false,"key":"yuhua_epay.sign_range","bool":false,"placeholder":"1-5","name":"积分签到区间","desc":"签到随机获得的积分区间，默认1-5"}]
#[param: {"required":false,"key":"yuhua_epay.lottery","bool":true,"placeholder":"","name":"核心积分抽奖","desc":"允许用户使用核心积分进行随机抽奖"}]
#[param: {"required":false,"key":"yuhua_epay.lottery_config","placeholder":"5|50%|5-10","name":"积分抽奖配置","desc":"消耗积分|中奖概率|奖励范围，默认: 5|50%|5-10"}]
# [param: {"spliter":true}]
#[param: {"required":false,"key":"yuhua_epay.native_wxpay","bool":true,"placeholder":"","name":"内置微信支付","desc":"在核心积分充值中增加该支付方式"}]
#[param: {"required":false,"key":"yuhua_epay.wx_qrcode","placeholder":"","name":"微信收款码子","desc":"内置微信支付的收款码直链"}]
core_user_locks = {}
core_lock_manager = threading.Lock()
core_card_locks = {}
core_card_lock_manager = threading.Lock()
def _update_core_points(user_id, points, is_deduct=False):
    user_lock = get_core_user_lock(user_id)
    with user_lock:
        try:
            current_points = get_core_points(user_id)
            points_value = int(round(float(points)))
            if is_deduct:
                if current_points >= points_value:
                    new_points = current_points - points_value
                    return set_core_points(user_id, new_points)
                return False
            new_points = current_points + points_value
            return set_core_points(user_id, new_points)
        except:
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
def debug_print(message):
    if DEBUG:
        print(message)
def get_core_card_lock(card_key):
    with core_card_lock_manager:
        if card_key not in core_card_locks:
            core_card_locks[card_key] = threading.Lock()
        return core_card_locks[card_key]
def create_alipay_bill_pending_settle_task(session_id, user_id, amount, paid_money, points_to_get, bill):
    task_data = {
        "session_id": str(session_id),
        "user_id": str(user_id),
        "amount": float(amount),
        "paid_money": float(paid_money),
        "points_to_get": int(round(float(points_to_get))),
        "bill": bill or {},
        "status": "pending",
        "created_ts": time.time()
    }
    middleware.bucketSet("yuhua_alipay_bill_pending_settle", str(session_id), json.dumps(task_data, ensure_ascii=False))
    return task_data    
def clear_alipay_bill_pending_settle_task(session_id):
    try:
        middleware.bucketDel("yuhua_alipay_bill_pending_settle", str(session_id))
        return True
    except Exception:
        return False      
def build_alipay_bill_unique_key(bill):
    account_log_id = str(bill.get("account_log_id", "")).strip()
    if account_log_id:
        return f"account_log_id:{account_log_id}"
    alipay_order_no = str(bill.get("alipay_order_no", "")).strip()
    if alipay_order_no:
        return f"alipay_order_no:{alipay_order_no}"
    biz_orig_no = str(bill.get("biz_orig_no", "")).strip()
    if biz_orig_no:
        return f"biz_orig_no:{biz_orig_no}"
    merchant_order_no = str(bill.get("merchant_order_no", "")).strip()
    if merchant_order_no:
        return f"merchant_order_no:{merchant_order_no}"
    biz_nos = str(bill.get("biz_nos", "")).strip()
    if biz_nos:
        return f"biz_nos:{biz_nos}"
    trans_dt = str(bill.get("trans_dt", "")).strip()
    trans_amount = str(bill.get("trans_amount", "")).strip()
    other_account = str(bill.get("other_account", "")).strip()
    direction = str(bill.get("direction", "")).strip()
    return f"fallback:{trans_dt}|{trans_amount}|{other_account}|{direction}"
def allocate_alipay_bill_amount(user_id, base_amount, timeout_seconds=240):
    from decimal import Decimal, ROUND_HALF_UP
    now_ts = time.time()
    base_decimal = Decimal(str(base_amount)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    base_amount_key = format(base_decimal, ".2f")
    lock = get_core_card_lock("alipay_bill_global_registry")
    session_id = "ALIPAYBILL-" + generate_unique_order_id(user_id)
    with lock:
        used_amounts = set()
        pending_keys_raw = middleware.bucketAllKeys("yuhua_alipay_bill_pending")
        if not pending_keys_raw:
            pending_keys = []
        elif isinstance(pending_keys_raw, str):
            pending_keys = [k.strip() for k in pending_keys_raw.split(',') if k.strip()]
        elif isinstance(pending_keys_raw, list):
            pending_keys = [str(k).strip() for k in pending_keys_raw if str(k).strip()]
        else:
            pending_keys = []
        for pending_key in pending_keys:
            pending_str = middleware.bucketGet("yuhua_alipay_bill_pending", pending_key) or "[]"
            try:
                pending_list = json.loads(pending_str)
                if not isinstance(pending_list, list):
                    pending_list = []
            except:
                pending_list = []
            valid_pending_list = []
            changed = False
            for item in pending_list:
                try:
                    item_status = str(item.get("status", "pending"))
                    deadline_ts = float(item.get("deadline_ts", 0) or 0)
                    if item_status == "pending" and deadline_ts > now_ts:
                        adjusted_amount = str(item.get("adjusted_amount", "")).strip()
                        if adjusted_amount:
                            used_amounts.add(adjusted_amount)
                        valid_pending_list.append(item)
                    else:
                        changed = True
                except:
                    changed = True
            if changed:
                if valid_pending_list:
                    middleware.bucketSet("yuhua_alipay_bill_pending", pending_key, json.dumps(valid_pending_list, ensure_ascii=False))
                else:
                    try:
                        middleware.bucketDel("yuhua_alipay_bill_pending", pending_key)
                    except Exception:
                        middleware.bucketSet("yuhua_alipay_bill_pending", pending_key, "[]")
        offset_index = 0
        while True:
            adjusted_decimal = (base_decimal + (Decimal("0.01") * Decimal(offset_index))).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            adjusted_amount = format(adjusted_decimal, ".2f")
            if adjusted_amount not in used_amounts:
                break
            offset_index += 1
        session_data = {
            "session_id": session_id,
            "user_id": str(user_id),
            "base_amount": base_amount_key,
            "base_amount_key": base_amount_key,
            "adjusted_amount": adjusted_amount,
            "offset_index": offset_index,
            "created_ts": now_ts,
            "deadline_ts": now_ts + timeout_seconds,
            "status": "pending",
            "matched_bill": {}
        }
        current_pending_str = middleware.bucketGet("yuhua_alipay_bill_pending", base_amount_key) or "[]"
        try:
            current_pending_list = json.loads(current_pending_str)
            if not isinstance(current_pending_list, list):
                current_pending_list = []
        except:
            current_pending_list = []
        valid_current_pending_list = []
        for item in current_pending_list:
            try:
                item_status = str(item.get("status", "pending"))
                deadline_ts = float(item.get("deadline_ts", 0) or 0)
                if item_status == "pending" and deadline_ts > now_ts:
                    valid_current_pending_list.append(item)
            except:
                pass
        valid_current_pending_list.append(session_data)
        middleware.bucketSet("yuhua_alipay_bill_pending", base_amount_key, json.dumps(valid_current_pending_list, ensure_ascii=False))
        middleware.bucketSet("yuhua_alipay_bill_session", session_id, json.dumps(session_data, ensure_ascii=False))
        return session_data
def release_alipay_bill_amount(session_id, status="closed", matched_bill=None):
    now_ts = time.time()
    session_str = middleware.bucketGet("yuhua_alipay_bill_session", session_id)
    if not session_str:
        return None
    try:
        session_data = json.loads(session_str)
        if not isinstance(session_data, dict):
            return None
    except:
        return None
    base_amount_key = str(session_data.get("base_amount_key", "")).strip()
    if not base_amount_key:
        try:
            base_amount_key = format(float(session_data.get("base_amount", 0)), ".2f")
        except:
            base_amount_key = ""
    if base_amount_key:
        lock = get_core_card_lock("alipay_bill_global_registry")
        with lock:
            pending_str = middleware.bucketGet("yuhua_alipay_bill_pending", base_amount_key) or "[]"
            try:
                pending_list = json.loads(pending_str)
                if not isinstance(pending_list, list):
                    pending_list = []
            except:
                pending_list = []
            new_pending_list = []
            for item in pending_list:
                try:
                    if str(item.get("session_id", "")) == str(session_id):
                        continue
                    item_status = str(item.get("status", "pending"))
                    deadline_ts = float(item.get("deadline_ts", 0) or 0)
                    if item_status == "pending" and deadline_ts > now_ts:
                        new_pending_list.append(item)
                except:
                    pass
            if new_pending_list:
                middleware.bucketSet("yuhua_alipay_bill_pending", base_amount_key, json.dumps(new_pending_list, ensure_ascii=False))
            else:
                try:
                    middleware.bucketDel("yuhua_alipay_bill_pending", base_amount_key)
                except Exception:
                    middleware.bucketSet("yuhua_alipay_bill_pending", base_amount_key, "[]")
    session_data["status"] = status
    session_data["updated_ts"] = now_ts
    if matched_bill is not None:
        session_data["matched_bill"] = matched_bill
    middleware.bucketSet("yuhua_alipay_bill_session", session_id, json.dumps(session_data, ensure_ascii=False))
    return session_data    
def sign_alipay_openapi_params(params, private_key):
    import base64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    filtered_params = {}
    for k, v in params.items():
        if k == "sign":
            continue
        if v is None or v == "":
            continue
        filtered_params[k] = str(v)
    unsigned_string = "&".join([f"{k}={filtered_params[k]}" for k in sorted(filtered_params.keys())])
    private_key = str(private_key or "").replace("\\n", "\n").strip()
    if not private_key:
        raise Exception("应用私钥未配置")
    if "-----BEGIN" not in private_key:
        import textwrap
        formatted_key = "\n".join(textwrap.wrap(private_key, 64))
        private_key = f"-----BEGIN PRIVATE KEY-----\n{formatted_key}\n-----END PRIVATE KEY-----"
    try:
        key_obj = serialization.load_pem_private_key(private_key.encode("utf-8"), password=None)
        sign_bytes = key_obj.sign(
            unsigned_string.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(sign_bytes).decode("utf-8")
    except Exception as e:
        print(f"[签名生成异常] 私钥解析或签名失败，请检查密钥内容格式。详情: {e}")
        raise Exception(f"签名失败: {e}")
def query_alipay_bill_accountlog(config, start_time, end_time, page_no=1, page_size=2000):
    api_url = "https://openapi.alipay.com/gateway.do"
    biz_content = {
        "start_time": start_time,
        "end_time": end_time,
        "page_no": str(page_no),
        "page_size": str(page_size)
    }
    params = {
        "app_id": config["alipay_app_id"],
        "method": "alipay.data.bill.accountlog.query",
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "biz_content": json.dumps(biz_content, ensure_ascii=False, separators=(",", ":"))
    }
    try:
        params["sign"] = sign_alipay_openapi_params(params, config["alipay_private_key"])
    except Exception as e:
        print(f"[支付宝请求拦截] 签名生成失败: {e}")
        return {"code": -1, "msg": f"签名失败: {e}"}
    if DEBUG:
        safe_params = params.copy()
        if "sign" in safe_params:
            safe_params["sign"] = "***(Hidden)***"
        printf(f"\n=====[ALIPAY BILL QUERY REQUEST START] =====", "DEBUG")
        printf(f"METHOD: POST | URL: {api_url}", "DEBUG")
        printf(f"PAYLOAD: {json.dumps(safe_params, ensure_ascii=False)}", "DEBUG")
    try:
        response = requests.post(api_url, data=params, timeout=(10, 20))
        if DEBUG:
            printf(f"-----[ALIPAY BILL QUERY RESPONSE] -----", "DEBUG")
            printf(f"STATUS: {response.status_code}", "DEBUG")
            printf(f"RSP BODY: {response.text[:1000]}", "DEBUG")
            printf(f"=====[ALIPAY BILL QUERY REQUEST END] =====\n", "DEBUG")
        response.raise_for_status()
        response_json = response.json()
        body = response_json.get("alipay_data_bill_accountlog_query_response", {})
        if str(body.get("code")) != "10000":
            error_msg = body.get("sub_msg") or body.get("msg") or "支付宝账单查询失败"
            print(f"[支付宝接口报错] {error_msg}")
            return {
                "code": -1,
                "msg": error_msg
            }
        return {
            "code": 0,
            "msg": "查询成功",
            "page_no": int(body.get("page_no", page_no) or page_no),
            "page_size": int(body.get("page_size", page_size) or page_size),
            "total_size": int(body.get("total_size", 0) or 0),
            "detail_list": body.get("detail_list",[]) or []
        }
    except Exception as e:
        print(f"[支付宝请求异常] 网络请求或数据解析失败: {e}")
        return {"code": -1, "msg": f"请求失败: {e}"}
def check_alipay_bill_payment(config, session_id):
    from decimal import Decimal, ROUND_HALF_UP
    from datetime import datetime, timedelta
    session_str = middleware.bucketGet("yuhua_alipay_bill_session", session_id)
    if not session_str:
        return {"code": -1, "msg": "支付会话不存在"}
    try:
        session_data = json.loads(session_str)
        if not isinstance(session_data, dict):
            return {"code": -1, "msg": "支付会话数据异常"}
    except:
        return {"code": -1, "msg": "支付会话数据异常"}
    if str(session_data.get("status", "pending")) != "pending":
        return {"code": -1, "msg": "支付会话已结束"}
    expected_paid_amount = Decimal(str(session_data.get("adjusted_amount", "0.00"))).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    original_amount = Decimal(str(session_data.get("base_amount", "0.00"))).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    created_ts = float(session_data.get("created_ts", 0) or 0)
    if created_ts <= 0:
        return {"code": -1, "msg": "支付会话时间异常"}
    start_dt = datetime.fromtimestamp(max(0, created_ts - 120))
    end_dt = datetime.now() + timedelta(seconds=5)
    start_time = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    end_time = end_dt.strftime("%Y-%m-%d %H:%M:%S")
    page_no = 1
    total_size = 0
    all_detail_list = []
    while True:
        query_result = query_alipay_bill_accountlog(config, start_time, end_time, page_no=page_no, page_size=2000)
        if query_result.get("code") != 0:
            return query_result
        detail_list = query_result.get("detail_list", []) or []
        total_size = int(query_result.get("total_size", 0) or 0)
        page_size = int(query_result.get("page_size", 2000) or 2000)
        all_detail_list.extend(detail_list)
        if not detail_list:
            break
        if len(all_detail_list) >= total_size:
            break
        if len(detail_list) < page_size:
            break
        page_no += 1
    created_dt = datetime.fromtimestamp(max(0, created_ts - 2))
    matched_bill = None
    matched_dt = None
    for item in all_detail_list:
        try:
            direction = str(item.get("direction", "")).strip()
            if direction != "收入":
                continue
            trans_amount = Decimal(str(item.get("trans_amount", "0"))).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            if trans_amount != expected_paid_amount:
                continue
            trans_dt_str = str(item.get("trans_dt", "")).strip()
            if not trans_dt_str:
                continue
            trans_dt = datetime.strptime(trans_dt_str, "%Y-%m-%d %H:%M:%S")
            if trans_dt < created_dt:
                continue
            bill_key = build_alipay_bill_unique_key(item)
            bill_lock = get_core_card_lock(f"alipay_bill_used_{bill_key}")
            with bill_lock:
                used_str = middleware.bucketGet("yuhua_alipay_bill_used", bill_key)
                if used_str:
                    try:
                        used_data = json.loads(used_str)
                        if not isinstance(used_data, dict):
                            used_data = {}
                    except:
                        used_data = {}
                    used_session_id = str(used_data.get("session_id", "")).strip()
                    if used_session_id and used_session_id != str(session_id):
                        continue
                else:
                    used_data = {
                        "session_id": str(session_id),
                        "claimed_ts": time.time(),
                        "base_amount": format(original_amount, ".2f"),
                        "paid_amount": format(expected_paid_amount, ".2f"),
                        "bill": item
                    }
                    middleware.bucketSet("yuhua_alipay_bill_used", bill_key, json.dumps(used_data, ensure_ascii=False))
            if matched_dt is None or trans_dt < matched_dt:
                matched_dt = trans_dt
                matched_bill = dict(item)
                matched_bill["bill_key"] = bill_key
        except Exception:
            continue
    if matched_bill:
        return {
            "code": 0,
            "msg": "支付成功",
            "money": float(original_amount),
            "paid_money": float(expected_paid_amount),
            "bill": matched_bill
        }
    return {"code": -1, "msg": "未支付"}     
def settle_core_points_after_alipay_bill(sender: middleware.Sender, user_id: str, session_id: str, amount: float, points_to_get, status_result: dict):
    paid_money = float(status_result.get("paid_money", amount))
    bill = status_result.get("bill", {}) or {}
    last_error = ""
    for attempt in range(3):
        try:
            if add_core_points(user_id, points_to_get):
                clear_alipay_bill_pending_settle_task(session_id)
                release_alipay_bill_amount(session_id, status="paid", matched_bill=bill)
                return {
                    "code": 0,
                    "msg": "结算成功",
                    "paid_money": paid_money
                }
            last_error = "积分增加失败"
        except Exception as e:
            last_error = str(e)
        if attempt < 2:
            time.sleep(0.8 * (attempt + 1))
    create_alipay_bill_pending_settle_task(
        session_id=session_id,
        user_id=user_id,
        amount=amount,
        paid_money=paid_money,
        points_to_get=points_to_get,
        bill=bill
    )
    release_alipay_bill_amount(session_id, status="paid_wait_settle", matched_bill=bill)
    try:
        middleware.notifyMasters(
            f"""【羽化核心】支付宝账单充值已付款但积分补发失败
用户ID: {user_id}
原金额: {amount:.2f}
实付金额: {paid_money:.2f}
应补积分: {int(round(float(points_to_get)))}
会话ID: {session_id}"""
        )
    except Exception:
        pass
    return {
        "code": -1,
        "msg": "支付成功，但积分补发任务已记录，请联系管理员处理",
        "paid_money": paid_money
    }                           
def get_core_user_lock(user_id):
    with core_lock_manager:
        if user_id not in core_user_locks:
            core_user_locks[user_id] = threading.Lock()
        return core_user_locks[user_id]
def get_active_points_bucket():
    try:
        is_compat = middleware.bucketGet("yuhua_epay", "compat_points") == "true"
        custom_bucket = middleware.bucketGet("yuhua_epay", "custom_points_bucket")
        if is_compat and custom_bucket and custom_bucket.strip():
            return custom_bucket.strip()
    except Exception:
        pass
    return 'yuhua_core_points'
def get_core_points(user_id):
    try:
        bucket_name = get_active_points_bucket()
        points = middleware.bucketGet(bucket_name, str(user_id))
        if points:
            return int(round(float(points)))
        return 0
    except:
        return 0
def set_core_points(user_id, points):
    try:
        bucket_name = get_active_points_bucket()
        int_points = int(round(float(points)))
        middleware.bucketSet(bucket_name, str(user_id), str(int_points))
        return True
    except:
        return False
def add_core_points(user_id, points):
    return _update_core_points(user_id, points, is_deduct=False)        
def deduct_core_points(user_id, points):
    return _update_core_points(user_id, points, is_deduct=True)
def printf(msg, level='INFO'):
    c = 32 if level in ['INFO', 'DEBUG'] else 33 if level in['WARN', 'WARNING'] else 31
    sys.stderr.write(f"\033[{c}m[{level}] {str(msg)}\033[0m\n")
    sys.stderr.flush()
try:
    debug_val = middleware.bucketGet('yuhua_wbzt', 'debug_mode') or ''
    DEBUG = (debug_val == '123456789abcC@')
except Exception:
    DEBUG = False
if DEBUG:
    printf("🔥🔥🔥 文本转图调试模式已开启，密钥验证通过，将输出详细网络日志 🔥🔥🔥", "WARN")
def get_base_url_by_version():
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
    try:
        if os.path.exists(file_path):
            backup_path = file_path + ".bak"
            if not os.path.exists(backup_path):
                shutil.copy2(file_path, backup_path)
                debug_print(f"首次备份原版中间件: {file_path} -> {backup_path}")
                return True
            else:
                debug_print(f"中间件备份已存在，跳过备份: {backup_path}")
                return True
        return False
    except Exception as e:
        debug_print(f"备份中间件失败 {file_path}: {e}")
        return False
def restore_from_backup(file_path: str) -> bool:
    try:
        backup_path = file_path + ".bak"
        if os.path.exists(backup_path):
            if os.path.exists(file_path):
                os.remove(file_path)
            shutil.copy2(backup_path, file_path)
            debug_print(f"从备份恢复中间件: {backup_path} -> {file_path}")
            return True
        return False
    except Exception as e:
        debug_print(f"从备份恢复失败 {file_path}: {e}")
        return False
def reset_text_to_image(sender: middleware.Sender):
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
    RETRYABLE_EXCEPTIONS = (
        ConnectionError,
        Timeout,
        requests.exceptions.HTTPError,
    )    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                debug_print(f"🔄 正在重试下载中间件 (第{attempt}次重试): {url}")
            else:
                debug_print(f"📥 正在下载中间件: {url}")
            timeout = 15 + (attempt * 5)            
            response = requests.get(url, timeout=timeout)            
            if response.status_code == 404:
                debug_print(f"❌ 中间件不存在 (404): {url}")
                return False
            elif response.status_code == 403:
                debug_print(f"❌ 访问被拒绝 (403): {url}")
                return False
            elif response.status_code == 401:
                debug_print(f"❌ 未授权访问 (401): {url}")
                return False
            if response.status_code >= 500:
                raise requests.exceptions.HTTPError(f"服务器错误 ({response.status_code})")
            elif response.status_code >= 400:
                debug_print(f"❌ 客户端错误 ({response.status_code}): {url}")
                return False            
            response.raise_for_status()
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(response.text)            
            debug_print(f"✅ 中间件下载成功: {target_path}")
            return True            
        except RETRYABLE_EXCEPTIONS as e:
            if attempt < max_retries - 1:
                base_delay = 2 ** attempt
                jitter = random.uniform(0, 1)
                delay = base_delay + jitter                
                error_type = type(e).__name__
                debug_print(f"⚠️  下载失败 ({error_type}): {str(e)[:100]}")
                debug_print(f"⏱️  将在 {delay:.1f} 秒后重试...")
                time.sleep(delay)
            else:
                debug_print(f"❌ 下载最终失败，已重试 {max_retries} 次: {str(e)[:100]}")
                return False                
        except Exception as e:
            debug_print(f"❌ 下载失败（不可重试的错误）: {str(e)[:100]}")
            return False    
    return False
def clear_python_cache(py_file_path: str):
    try:
        try:
            pyc_file = importlib.util.cache_from_source(py_file_path)
            if os.path.exists(pyc_file):
                os.remove(pyc_file)
        except Exception:
            pass            
        cache_dir = os.path.join(os.path.dirname(py_file_path), "__pycache__")
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
            except Exception:
                pass
    except Exception as e:
        debug_print(f"清理缓存失败: {e}")
def check_network_connectivity() -> bool:
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
def get_epay_config():
    try:
        exchange_rate = float(middleware.bucketGet("yuhua_epay", "exchange_rate") or 100.0)
        if exchange_rate <= 0:
            exchange_rate = 100.0
    except:
        exchange_rate = 100.0
    return {
        'epay_url': middleware.bucketGet("yuhua_epay", 'epay_url') or '',
        'epay_pid': middleware.bucketGet("yuhua_epay", 'epay_pid') or '',
        'epay_key': middleware.bucketGet("yuhua_epay", 'epay_key') or '',
        'epay_alipay': middleware.bucketGet("yuhua_epay", 'epay_alipay') != 'false',
        'epay_wxpay': middleware.bucketGet("yuhua_epay", 'epay_wxpay') != 'false',
        'epay_qqpay': middleware.bucketGet("yuhua_epay", 'epay_qqpay') != 'false',
        'points_pay': middleware.bucketGet("yuhua_epay", 'points_pay') == 'true',
        'exchange_rate': exchange_rate,
        'native_wxpay': middleware.bucketGet("yuhua_epay", 'native_wxpay') == 'true',
        'wx_qrcode': middleware.bucketGet("yuhua_epay", 'wx_qrcode') or '',
        'alipay_bill': middleware.bucketGet("yuhua_epay", 'alipay_bill') == 'true',
        'alipay_qrcode': middleware.bucketGet("yuhua_epay", 'alipay_qrcode') or '',
        'alipay_app_id': middleware.bucketGet("yuhua_epay", 'alipay_app_id') or '',
        'alipay_private_key': middleware.bucketGet("yuhua_epay", 'alipay_private_key') or ''
    }
def create_epay_sign(params, merchant_key):
    import hashlib
    filtered_params = {k: str(v) for k, v in params.items() if v and k != 'sign' and k != 'sign_type'}
    sorted_params = dict(sorted(filtered_params.items()))
    sign_str = '&'.join([f"{k}={v}" for k, v in sorted_params.items()])
    sign_str += merchant_key
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

def generate_unique_order_id(user_id):
    import uuid, time
    timestamp = int(time.time() * 1000)
    random_part = str(uuid.uuid4())[:8]
    user_suffix = str(user_id)[-4:] if len(str(user_id)) >= 4 else str(user_id)
    return f"EPAY{timestamp}{user_suffix}{random_part}"

def create_epay_order(config, order_id, amount, payment_method):
    params = {
        'pid': config['epay_pid'],
        'type': payment_method,
        'out_trade_no': order_id,
        'notify_url': f"{config['epay_url'].rstrip('/')}/notify_url.php",
        'return_url': f"{config['epay_url'].rstrip('/')}/return_url.php",
        'name': '羽化核心',
        'money': f"{float(amount):.2f}",
        'clientip': '127.0.0.1',
        'sign_type': 'MD5'
    }
    params['sign'] = create_epay_sign(params, config['epay_key'])    
    api_url = f"{config['epay_url'].rstrip('/')}/mapi.php"    
    if DEBUG:
        printf(f"\n=====[EPAY CREATE ORDER REQUEST START] =====", "DEBUG")
        printf(f"METHOD: POST | URL: {api_url}", "DEBUG")
        safe_params = params.copy()
        if 'sign' in safe_params: safe_params['sign'] = '***(Hidden)***'
        printf(f"PAYLOAD: {json.dumps(safe_params, ensure_ascii=False)}", "DEBUG")        
    try:
        response = requests.post(api_url, data=params, timeout=(5, 15))        
        if DEBUG:
            printf(f"-----[EPAY CREATE ORDER RESPONSE] -----", "DEBUG")
            printf(f"STATUS: {response.status_code}", "DEBUG")
            printf(f"RSP BODY: {response.text}", "DEBUG")
            printf(f"=====[EPAY CREATE ORDER REQUEST END] =====\n", "DEBUG") 
        response_json = response.json()
        if response_json.get('code') == 1:
            payment_url = response_json.get('qrcode') or response_json.get('payurl') or response_json.get('qrurl') or ''
            return {'code': 0, 'qr_code': payment_url, 'order_id': order_id}
        else:
            return {'code': -1, 'msg': response_json.get('msg', '未知错误')}
    except Exception as e:
        if DEBUG:
            printf(f"⚠️ Epay Create Order FAILED (Error): {e}", "WARN")
        return {'code': -1, 'msg': f'创建订单异常: {str(e)}'}
def check_epay_order_status(config, order_id):
    epay_url = config['epay_url'].rstrip('/')
    pid = config['epay_pid']
    key = config['epay_key']    
    try:
        v1_url = f"{epay_url}/api.php"
        v1_params = {'act': 'order', 'pid': pid, 'key': key, 'out_trade_no': order_id}        
        if DEBUG:
            printf(f"\n=====[EPAY CHECK V1 REQUEST START] =====", "DEBUG")
            printf(f"METHOD: GET | URL: {v1_url}", "DEBUG")            
        res_v1 = requests.get(v1_url, params=v1_params, timeout=10)        
        if DEBUG:
            printf(f"-----[EPAY CHECK V1 RESPONSE] -----", "DEBUG")
            printf(f"STATUS: {res_v1.status_code}", "DEBUG")
            printf(f"RSP BODY: {res_v1.text}", "DEBUG")
            printf(f"=====[EPAY CHECK V1 REQUEST END] =====\n", "DEBUG")            
        data_v1 = res_v1.json()
        if str(data_v1.get('code')) == '1' and str(data_v1.get('status')) == '1':
            raw_money = data_v1.get('money')
            if raw_money in[None, '', 'null']:
                raw_money = 0                
            return {'code': 0, 'msg': '支付成功', 'money': float(raw_money)}            
    except Exception as e:
        if DEBUG:
            printf(f"⚠️ Epay Check V1 FAILED (Error): {e}", "WARN")
    return {'code': -1, 'msg': '未支付或查询异常'}
def handle_epay_hijack_api(sender: middleware.Sender):
    try:
        request_body = sender.getRouterBody()
        if not request_body:
            sender.reply(json.dumps({"success": False, "reason": "empty_body"}))
            return
        request_data = json.loads(request_body)
        action = request_data.get("action", "start")
        session_bucket = "yuhua_epay_session"
        active_bucket = "yuhua_epay_user_active"
        current_time = time.time()
        heartbeat_expire_seconds = 90
        cleanup_keep_seconds = 300
        def _safe_float(value, default=0):
            try:
                return float(value)
            except Exception:
                return default
        def _safe_int(value, default=0):
            try:
                return int(value)
            except Exception:
                return default
        def _build_active_key(senderid, plugin_name):
            return f"{senderid}:{plugin_name}"
        def _mark_session_closed(session_id, session_data, status, close_ts=None):
            if close_ts is None:
                close_ts = time.time()
            if session_data.get("payment_method") == "alipay_bill":
                alipay_bill_session_id = session_data.get("alipay_bill_session_id", "")
                if alipay_bill_session_id:
                    try:
                        alipay_bill_status = "closed"
                        if status == "cancelled":
                            alipay_bill_status = "cancelled"
                        elif status == "timeout":
                            alipay_bill_status = "timeout"
                        elif status == "failed":
                            alipay_bill_status = "failed"
                        release_alipay_bill_amount(alipay_bill_session_id, status=alipay_bill_status)
                    except Exception:
                        pass
            session_data["status"] = status
            session_data["finished"] = True
            session_data["closed_ts"] = close_ts
            session_data["last_active_ts"] = close_ts
            session_data["cleanup_after_ts"] = close_ts + cleanup_keep_seconds
            middleware.bucketSet(session_bucket, session_id, json.dumps(session_data, ensure_ascii=False))
            target_senderid = session_data.get("senderid")
            target_plugin_name = session_data.get("plugin_name", "")
            if target_senderid and target_plugin_name:
                active_key = _build_active_key(str(target_senderid), str(target_plugin_name))
                active_sid = middleware.bucketGet(active_bucket, active_key)
                if active_sid == session_id:
                    try:
                        middleware.bucketDel(active_bucket, active_key)
                    except Exception:
                        pass
        def _delete_expired_session_if_needed(session_id, session_data, now_ts):
            cleanup_after_ts = _safe_float(session_data.get("cleanup_after_ts", 0), 0)
            if cleanup_after_ts > 0 and now_ts >= cleanup_after_ts:
                try:
                    middleware.bucketDel(session_bucket, session_id)
                except Exception:
                    pass
                target_senderid = session_data.get("senderid")
                target_plugin_name = session_data.get("plugin_name", "")
                if target_senderid and target_plugin_name:
                    try:
                        active_key = _build_active_key(str(target_senderid), str(target_plugin_name))
                        active_sid = middleware.bucketGet(active_bucket, active_key)
                        if active_sid == session_id:
                            middleware.bucketDel(active_bucket, active_key)
                    except Exception:
                        pass
                return True
            return False
        def _is_session_stale(session_data, now_ts):
            status = session_data.get("status", "pending")
            deadline_ts = _safe_float(session_data.get("deadline_ts", 0), 0)
            last_active_ts = _safe_float(session_data.get("last_active_ts", 0), 0)
            if status in ["paid", "cancelled", "timeout", "closed", "failed"]:
                return True
            if deadline_ts > 0 and now_ts >= deadline_ts:
                return True
            if last_active_ts > 0 and now_ts - last_active_ts > heartbeat_expire_seconds:
                return True
            return False
        def _load_session(session_id):
            if not session_id:
                return None, None
            session_str = middleware.bucketGet(session_bucket, session_id)
            if not session_str:
                return None, None
            try:
                session_data = json.loads(session_str)
                return session_str, session_data
            except Exception:
                return session_str, None
        if action == "cancel":
            session_id = request_data.get("session_id", "")
            if not session_id:
                sender.reply(json.dumps({"success": False, "reason": "empty_session_id"}))
                return
            session_str, session_data = _load_session(session_id)
            if not session_str or not session_data:
                try:
                    middleware.bucketDel(session_bucket, session_id)
                except Exception:
                    pass
                sender.reply(json.dumps({"success": True, "status": "closed"}))
                return
            _mark_session_closed(session_id, session_data, "cancelled", time.time())
            sender.reply(json.dumps({"success": True, "status": "cancelled"}))
            return
        if action == "status":
            session_id = request_data.get("session_id", "")
            if not session_id:
                sender.reply(json.dumps({"success": False, "reason": "empty_session_id"}))
                return
            session_str, session_data = _load_session(session_id)
            if not session_str:
                sender.reply(json.dumps({"success": False, "reason": "session_not_found", "status": "closed"}))
                return
            if not session_data:
                try:
                    middleware.bucketDel(session_bucket, session_id)
                except Exception:
                    pass
                sender.reply(json.dumps({"success": False, "reason": "session_data_invalid", "status": "failed"}))
                return
            current_time = time.time()
            if _delete_expired_session_if_needed(session_id, session_data, current_time):
                sender.reply(json.dumps({"success": False, "reason": "session_cleaned", "status": "closed"}))
                return
            status = session_data.get("status", "pending")
            deadline_ts = _safe_float(session_data.get("deadline_ts", 0), 0)
            if status == "paid":
                sender.reply(json.dumps({
                    "success": True,
                    "status": "paid",
                    "money": session_data.get("money", 0),
                    "paid_money": session_data.get("paid_money", session_data.get("money", 0)),
                    "session_id": session_id
                }, ensure_ascii=False))
                return
            if status in ["cancelled", "closed", "failed", "timeout"]:
                sender.reply(json.dumps({
                    "success": True,
                    "status": status,
                    "session_id": session_id
                }, ensure_ascii=False))
                return
            if deadline_ts > 0 and current_time >= deadline_ts:
                _mark_session_closed(session_id, session_data, "timeout", current_time)
                sender.reply(json.dumps({
                    "success": True,
                    "status": "timeout",
                    "session_id": session_id
                }, ensure_ascii=False))
                return
            target_senderid = session_data.get("senderid")
            target_sender = middleware.Sender(target_senderid)
            session_data["last_active_ts"] = current_time
            middleware.bucketSet(session_bucket, session_id, json.dumps(session_data, ensure_ascii=False))
            config = get_epay_config()
            order_id = session_data.get("order_id", "")
            amount = session_data.get("amount", 0)
            if session_data.get("payment_method") == "alipay_bill":
                alipay_bill_session_id = session_data.get("alipay_bill_session_id", "")
                if alipay_bill_session_id:
                    try:
                        status_result = check_alipay_bill_payment(config, alipay_bill_session_id)
                        if status_result.get("code") == 0:
                            paid_amount = status_result.get("money", amount)
                            paid_money = status_result.get("paid_money", paid_amount)
                            session_data["status"] = "paid"
                            session_data["finished"] = True
                            session_data["money"] = paid_amount
                            session_data["paid_money"] = paid_money
                            session_data["paid_ts"] = current_time
                            session_data["last_active_ts"] = current_time
                            session_data["cleanup_after_ts"] = current_time + cleanup_keep_seconds
                            middleware.bucketSet(session_bucket, session_id, json.dumps(session_data, ensure_ascii=False))
                            try:
                                release_alipay_bill_amount(
                                    alipay_bill_session_id,
                                    status="paid",
                                    matched_bill=status_result.get("bill", {})
                                )
                            except Exception:
                                pass
                            target_plugin_name = session_data.get("plugin_name", "")
                            if target_senderid and target_plugin_name:
                                active_key = _build_active_key(str(target_senderid), str(target_plugin_name))
                                active_sid = middleware.bucketGet(active_bucket, active_key)
                                if active_sid == session_id:
                                    try:
                                        middleware.bucketDel(active_bucket, active_key)
                                    except Exception:
                                        pass
                            sender.reply(json.dumps({
                                "success": True,
                                "status": "paid",
                                "money": paid_amount,
                                "paid_money": paid_money,
                                "session_id": session_id
                            }, ensure_ascii=False))
                            return
                    except Exception:
                        pass
            if order_id and session_data.get("payment_method") != "points":
                try:
                    status_result = check_epay_order_status(config, order_id)
                    if status_result.get('code') == 0:
                        paid_amount = status_result.get('money', amount)
                        session_data["status"] = "paid"
                        session_data["finished"] = True
                        session_data["money"] = paid_amount
                        session_data["paid_ts"] = current_time
                        session_data["last_active_ts"] = current_time
                        session_data["cleanup_after_ts"] = current_time + cleanup_keep_seconds
                        middleware.bucketSet(session_bucket, session_id, json.dumps(session_data, ensure_ascii=False))
                        target_plugin_name = session_data.get("plugin_name", "")
                        if target_senderid and target_plugin_name:
                            active_key = _build_active_key(str(target_senderid), str(target_plugin_name))
                            active_sid = middleware.bucketGet(active_bucket, active_key)
                            if active_sid == session_id:
                                try:
                                    middleware.bucketDel(active_bucket, active_key)
                                except Exception:
                                    pass
                        sender.reply(json.dumps({
                            "success": True,
                            "status": "paid",
                            "money": paid_amount,
                            "session_id": session_id
                        }, ensure_ascii=False))
                        return
                except Exception:
                    pass
            sender.reply(json.dumps({
                "success": True,
                "status": "pending",
                "session_id": session_id,
                "remaining_seconds": max(0, int(deadline_ts - current_time)) if deadline_ts > 0 else 0
            }, ensure_ascii=False))
            return
        target_senderid = request_data.get("senderid")
        if not target_senderid:
            sender.reply(json.dumps({"success": False, "reason": "empty_senderid"}))
            return
        target_sender = middleware.Sender(target_senderid)
        plugin_name = request_data.get("plugin_name", "未知插件")
        active_key = _build_active_key(str(target_senderid), str(plugin_name))
        timeout_ms = request_data.get("timeout", 120000)
        try:
            timeout_ms = int(timeout_ms)
        except Exception:
            timeout_ms = 120000
        if timeout_ms <= 0:
            timeout_ms = 120000
        if timeout_ms > 1800000:
            timeout_ms = 1800000
        total_budget_seconds = timeout_ms / 1000.0
        total_start_time = time.time()
        deadline_ts = total_start_time + total_budget_seconds
        active_session_id = middleware.bucketGet(active_bucket, active_key)
        if active_session_id:
            active_session_str, active_session_data = _load_session(active_session_id)
            if not active_session_str:
                try:
                    middleware.bucketDel(active_bucket, active_key)
                except Exception:
                    pass
            elif not active_session_data:
                try:
                    middleware.bucketDel(active_bucket, active_key)
                except Exception:
                    pass
                try:
                    middleware.bucketDel(session_bucket, active_session_id)
                except Exception:
                    pass
            else:
                if _delete_expired_session_if_needed(active_session_id, active_session_data, total_start_time):
                    try:
                        middleware.bucketDel(active_bucket, active_key)
                    except Exception:
                        pass
                elif _is_session_stale(active_session_data, total_start_time):
                    stale_deadline_ts = _safe_float(active_session_data.get("deadline_ts", 0), 0)
                    stale_last_active_ts = _safe_float(active_session_data.get("last_active_ts", 0), 0)
                    stale_now = total_start_time
                    if stale_deadline_ts > 0 and stale_now >= stale_deadline_ts:
                        stale_status = "timeout"
                    elif stale_last_active_ts > 0 and stale_now - stale_last_active_ts > heartbeat_expire_seconds:
                        stale_status = "closed"
                    else:
                        stale_status = "closed"
                    _mark_session_closed(active_session_id, active_session_data, stale_status, stale_now)
                else:
                    active_session_data["last_active_ts"] = total_start_time
                    middleware.bucketSet(session_bucket, active_session_id, json.dumps(active_session_data, ensure_ascii=False))
                    sender.reply(json.dumps({
                        "success": True,
                        "session_id": active_session_id,
                        "status": active_session_data.get("status", "pending")
                    }, ensure_ascii=False))
                    return
        config = get_epay_config()
        has_alipay_bill = bool(config['alipay_bill'] and config['alipay_qrcode'] and config['alipay_app_id'] and config['alipay_private_key'])
        auto_amount = None
        recent_texts = request_data.get("recent_texts", [])
        if recent_texts:
            custom_regex_str = middleware.bucketGet("yuhua_epay", "amount_regex") or ""
            builtin_patterns = [
                r'(?:合计|总额|总价|应付|需付|需付款|付款金额|支付金额|金额)[：:\s]*(\d+(?:\.\d{1,2})?)\s*元?',
                r'(\d+(?:\.\d{1,2})?)\s*元'
            ]
            custom_patterns = [p.strip() for p in custom_regex_str.split('｜') if p.strip()] if custom_regex_str else []
            all_patterns = custom_patterns + builtin_patterns
            for text_info in reversed(recent_texts):
                text = text_info.get("text", "")
                if not text:
                    continue
                for pattern in all_patterns:
                    try:
                        match = re.search(pattern, text)
                        if match:
                            matched_amount = float(match.group(1))
                            if matched_amount > 0:
                                auto_amount = matched_amount
                                break
                    except:
                        pass
                if auto_amount is not None:
                    break
        
        if auto_amount is not None:
            amount = round(auto_amount, 2)
        else:
            target_sender.reply(f"""=====羽化核心=====
❶请核对输入需付款金额
②羽化核心正在接管支付
------------------
请在20秒内完成
回复"q"取消""")
            amount_input = target_sender.input(20000, 0, False)
            if not amount_input or str(amount_input).lower() == 'q':
                target_sender.reply("✅ 已取消支付")
                sender.reply(json.dumps({"success": False, "reason": "cancel_or_timeout"}))
                return
            try:
                amount = round(float(str(amount_input).strip()), 2)
                if amount <= 0:
                    raise ValueError
            except:
                target_sender.reply("❌ 金额输入无效，已取消")
                sender.reply(json.dumps({"success": False, "reason": "invalid_amount"}))
                return
        payment_options = []
        payment_methods = []
        if config['epay_alipay']:
            payment_options.append(f"[{len(payment_options) + 1}] 支付宝")
            payment_methods.append(("alipay", "支付宝"))
        if config['epay_wxpay']:
            payment_options.append(f"[{len(payment_options) + 1}] 微信")
            payment_methods.append(("wxpay", "微信"))
        if config['epay_qqpay']:
            payment_options.append(f"[{len(payment_options) + 1}] QQ")
            payment_methods.append(("qqpay", "QQ"))
        if has_alipay_bill:
            payment_options.append(f"[{len(payment_options) + 1}] 支付宝账单")
            payment_methods.append(("alipay_bill", "支付宝账单"))
        header_info = f"💰 充值金额: {amount}元"
        if config['points_pay']:
            current_points = get_core_points(target_sender.getUserID())
            points_needed = round(amount * config['exchange_rate'], 2)
            points_needed = int(points_needed) if points_needed.is_integer() else points_needed
            payment_options.append(f"[{len(payment_options) + 1}] 核心积分")
            payment_methods.append(("points", "核心积分"))
            header_info = f"💳 充值金额: {amount}元\n🎯 消耗积分: {points_needed}\n💎 当前积分: {current_points}"
        if not payment_options:
            target_sender.reply("❌ 未启用任何支付方式，请联系管理员")
            sender.reply(json.dumps({"success": False, "reason": "no_payment_method"}))
            return
        payment_menu = f"""=====支付方式=====
{header_info}
------------------
{chr(10).join(payment_options)}
------------------
请在20秒内选择
回复"q"退出"""
        target_sender.reply(payment_menu)
        choice = target_sender.input(20000, 0, False)
        if not choice or str(choice).lower() == 'q':
            target_sender.reply("✅ 已取消操作")
            sender.reply(json.dumps({"success": False, "reason": "cancel_or_timeout"}))
            return
        try:
            choice_num = int(str(choice))
            if choice_num < 1 or choice_num > len(payment_methods):
                raise ValueError
            payment_method, payment_name = payment_methods[choice_num - 1]
        except ValueError:
            target_sender.reply("❌ 请选择有效的支付方式")
            sender.reply(json.dumps({"success": False, "reason": "invalid_choice"}))
            return
        import uuid
        session_id = "EPAYSESSION-" + uuid.uuid4().hex
        if payment_method == "points":
            current_points = get_core_points(target_sender.getUserID())
            points_needed = round(amount * config['exchange_rate'], 2)
            points_needed = int(points_needed) if points_needed.is_integer() else points_needed
            if current_points >= points_needed:
                if deduct_core_points(target_sender.getUserID(), points_needed):
                    paid_now = time.time()
                    session_data = {
                        "session_id": session_id,
                        "senderid": target_senderid,
                        "plugin_name": plugin_name,
                        "status": "paid",
                        "finished": True,
                        "money": amount,
                        "amount": amount,
                        "payment_method": payment_method,
                        "payment_name": payment_name,
                        "order_id": "",
                        "deadline_ts": deadline_ts,
                        "created_ts": total_start_time,
                        "last_active_ts": paid_now,
                        "paid_ts": paid_now,
                        "closed_ts": 0,
                        "cleanup_after_ts": paid_now + cleanup_keep_seconds
                    }
                    middleware.bucketSet(session_bucket, session_id, json.dumps(session_data, ensure_ascii=False))
                    sender.reply(json.dumps({
                        "success": True,
                        "session_id": session_id,
                        "status": "paid"
                    }, ensure_ascii=False))
                    return
                else:
                    target_sender.reply("❌ 积分扣除失败，系统并发异常")
                    sender.reply(json.dumps({"success": False, "reason": "deduct_fail"}))
                    return
            else:
                target_sender.reply("❌ 核心积分不足，请发送\"核心积分充值\"获取积分")
                sender.reply(json.dumps({"success": False, "reason": "insufficient_points"}))
                return
        if payment_method == "alipay_bill":
            remaining_seconds = max(30, int(deadline_ts - time.time()))
            alipay_bill_session_data = allocate_alipay_bill_amount(target_sender.getUserID(), amount, timeout_seconds=remaining_seconds)
            if not alipay_bill_session_data:
                target_sender.reply("❌ 支付会话创建失败，请稍后重试")
                sender.reply(json.dumps({"success": False, "reason": "create_alipay_bill_session_fail"}))
                return
            adjusted_amount = float(alipay_bill_session_data.get("adjusted_amount", amount))
            alipay_bill_session_id = alipay_bill_session_data.get("session_id", "")
            target_sender.reply(f"""=====等待支付=====
💰 金额: {amount}元
💳 方式: {payment_name}
♨️ 实付: {adjusted_amount:.2f}元
------------------
请在{max(0, int(deadline_ts - time.time()))}秒内实付{adjusted_amount:.2f}元
回复"q"取消支付""")
            try:
                target_sender.replyImage(config['alipay_qrcode'])
            except Exception:
                target_sender.reply("❌ 收款码发送失败，请联系管理员")
                try:
                    release_alipay_bill_amount(alipay_bill_session_id, status="failed")
                except Exception:
                    pass
                sender.reply(json.dumps({"success": False, "reason": "send_alipay_qrcode_fail"}))
                return
            session_data = {
                "session_id": session_id,
                "senderid": target_senderid,
                "plugin_name": plugin_name,
                "status": "pending",
                "finished": False,
                "cancelled": False,
                "money": 0,
                "paid_money": 0,
                "amount": amount,
                "payment_method": payment_method,
                "payment_name": payment_name,
                "order_id": "",
                "alipay_bill_session_id": alipay_bill_session_id,
                "adjusted_amount": adjusted_amount,
                "deadline_ts": deadline_ts,
                "created_ts": total_start_time,
                "last_active_ts": total_start_time,
                "paid_ts": 0,
                "closed_ts": 0,
                "timeout_ms": timeout_ms,
                "cleanup_after_ts": deadline_ts + cleanup_keep_seconds
            }
            middleware.bucketSet(session_bucket, session_id, json.dumps(session_data, ensure_ascii=False))
            middleware.bucketSet(active_bucket, active_key, session_id)
            sender.reply(json.dumps({
                "success": True,
                "session_id": session_id,
                "status": "pending"
            }, ensure_ascii=False))
            return
        if not config['epay_url'] or not config['epay_pid'] or not config['epay_key']:
            target_sender.reply("❌ 易支付未完整配置，请联系管理员")
            sender.reply(json.dumps({"success": False, "reason": "unconfigured"}))
            return
        order_id = generate_unique_order_id(target_sender.getUserID())
        epay_result = create_epay_order(config, order_id, amount, payment_method)
        if epay_result.get('code') != 0:
            error_msg = epay_result.get('msg', '未知错误')
            target_sender.reply(f"❌ 创建订单失败: {error_msg}")
            sender.reply(json.dumps({"success": False, "reason": "create_order_fail"}))
            return
        qr_code_url = epay_result.get('qr_code', '')
        remaining_seconds = max(0, int(deadline_ts - time.time()))
        target_sender.reply(f"""=====等待支付=====
💰 金额: {amount}元
💳 方式: {payment_name}
📋 订单: {order_id}
------------------
请在 {remaining_seconds} 秒内完成扫码支付
回复"q"取消支付""")
        if qr_code_url:
            qr_image_url = f"https://api.pwmqr.com/qrcode/create/?url={quote(qr_code_url)}"
            try:
                middleware.get_service_response("/sendImage", {
                    "senderid": target_sender.senderID,
                    "imageurl": qr_image_url
                })
            except Exception as e:
                if DEBUG:
                    printf(f"⚠️ 发送二维码图片失败: {e}", "WARN")
                target_sender.reply("二维码链接(长按复制到浏览器打开):" + chr(10) + str(qr_code_url))
        else:
            target_sender.reply("❌ 二维码生成失败")
            sender.reply(json.dumps({"success": False, "reason": "qr_fail"}))
            return
        session_data = {
            "session_id": session_id,
            "senderid": target_senderid,
            "plugin_name": plugin_name,
            "status": "pending",
            "finished": False,
            "cancelled": False,
            "money": 0,
            "amount": amount,
            "payment_method": payment_method,
            "payment_name": payment_name,
            "order_id": order_id,
            "qr_code_url": qr_code_url,
            "deadline_ts": deadline_ts,
            "created_ts": total_start_time,
            "last_active_ts": total_start_time,
            "paid_ts": 0,
            "closed_ts": 0,
            "timeout_ms": timeout_ms,
            "cleanup_after_ts": deadline_ts + cleanup_keep_seconds
        }
        middleware.bucketSet(session_bucket, session_id, json.dumps(session_data, ensure_ascii=False))
        middleware.bucketSet(active_bucket, active_key, session_id)
        sender.reply(json.dumps({
            "success": True,
            "session_id": session_id,
            "status": "pending"
        }, ensure_ascii=False))
    except Exception as e:
        sender.reply(json.dumps({"success": False, "reason": str(e)}))
def toggle_epay_status(sender: middleware.Sender, enable: bool):
    if not sender.isAdmin():
        sender.reply("❌ 权限不足：若非管理员请勿操作")
        return
    status_str = "true" if enable else "false"
    action_str = "开启" if enable else "关闭"
    try:
        middleware.bucketSet("yuhua_epay", "enabled", status_str)
        sender.reply(f"✅ 支付接管功能已{action_str}")
    except Exception as e:
        sender.reply(f"❌ {action_str}支付接管功能时发生错误: {e}")
def manage_epay_plugin_list(sender: middleware.Sender):
    if not sender.isAdmin():
        sender.reply("❌ 您没有权限执行此操作")
        return
    message = sender.getMessage()
    bucket_name = "yuhua_epay"
    key_name = "plugins"
    try:
        current_plugins_str = middleware.bucketGet(bucket_name, key_name) or ""
        plugin_list = current_plugins_str.split(',') if current_plugins_str else[]
        plugin_list =[p.strip() for p in plugin_list if p.strip()]
        if message == "支付接管列表":
            if not plugin_list:
                sender.reply("❌ 暂未添加支付接管插件")
            else:
                reply_msg = "✨ 支付接管列表：\n" + "\n".join(f"{p}" for p in plugin_list)
                sender.reply(reply_msg)        
        elif message.startswith("添加支付接管"):
            parts = message.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                reply_msg = "✨ 支付接管列表：\n"
                if plugin_list:
                    reply_msg += "\n".join(f"{p}" for p in plugin_list)
                else:
                    reply_msg += "（暂无）"
                reply_msg += "\n\n🎉 触发指令：\n添加支付接管 插件名称"
                sender.reply(reply_msg)
                return            
            plugin_to_add = parts[1].strip()
            if plugin_to_add in PROTECTED_PLUGIN_TITLES:
                sender.reply("❌ 安全拦截：为防止逻辑错乱，系统基建插件已列入内置黑名单，禁止开启接管！")
                return            
            if plugin_to_add in plugin_list:
                sender.reply(f"✅ 插件 '{plugin_to_add}' 已在支付接管列表中")
            else:
                plugin_list.append(plugin_to_add)
                new_plugins_str = ",".join(plugin_list)
                middleware.bucketSet(bucket_name, key_name, new_plugins_str)
                sender.reply(f"✅ 成功添加支付接管插件：{plugin_to_add}")
        elif message.startswith("删除支付接管"):
            parts = message.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                reply_msg = "✨ 支付接管列表：\n"
                if plugin_list:
                    reply_msg += "\n".join(f"{p}" for p in plugin_list)
                else:
                    reply_msg += "（暂无）"
                reply_msg += "\n\n🎉 触发指令：\n删除支付接管 插件名称"
                sender.reply(reply_msg)
                return
            plugin_to_remove = parts[1].strip()
            if plugin_to_remove in plugin_list:
                plugin_list.remove(plugin_to_remove)
                new_plugins_str = ",".join(plugin_list)
                middleware.bucketSet(bucket_name, key_name, new_plugins_str)
                sender.reply(f"✅ 成功删除支付接管插件：{plugin_to_remove}")
            else:
                sender.reply(f"❌ 列表中不存在该插件：{plugin_to_remove}")
    except Exception as e:
        sender.reply(f"❌ 支付接管列表操作失败：{e}")
def handle_plugin_management(sender: middleware.Sender, title: str, bucket_name: str, key_name: str):
    if not sender.isAdmin():
        sender.reply("❌ 您没有权限执行此操作")
        return
    while True:
        try:
            plugin_names = set()
            for b in ["plugins_script"]:
                keys_data = middleware.bucketAllKeys(b)
                if not keys_data:
                    continue
                keys_list = keys_data.split(',') if isinstance(keys_data, str) else keys_data
                for k in keys_list:
                    k = str(k).strip()
                    if not k:
                        continue
                    if ':' in k:
                        k = k.split(':', 1)[1]
                    if not (k.endswith('.js') or k.endswith('.py')):
                        continue
                    name = os.path.splitext(k)[0]
                    if name:
                        plugin_names.add(name)
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
            plugin_names.update(enabled_set)
            for _protected_plugin_title in PROTECTED_PLUGIN_TITLES:
                plugin_names.discard(_protected_plugin_title)
            sorted_plugins = sorted(list(plugin_names))
            total_count = len(sorted_plugins)
            enabled_count = len(enabled_set)
            disabled_count = total_count - enabled_count
            reply_lines = [
                f"====={title}=====",
                f"🎉 插件数量: {total_count}",
                f"✨ 开启数量: {enabled_count}",
                f"💢 关闭数量: {disabled_count}",
                "------------------"
            ]
            for idx, p_name in enumerate(sorted_plugins, 1):
                status = "✅ 开启" if p_name in enabled_set else "❌ 关闭"
                reply_lines.append(f"[{idx}] {p_name}\n    {status}")
            reply_lines.append("------------------")
            reply_lines.append("t=全部开启, f=全部关闭, q=退出操作")
            reply_lines.append("+序号或名称=开启, -序号或名称=关闭")
            sender.reply("\n".join(reply_lines))
            user_input = sender.input(60000, 0, False)
            if not user_input:
                sender.reply("❌ 输入超时，已自动退出操作")
                return
            cmd = str(user_input).strip()
            if cmd.lower() == 'q':
                sender.reply("✅ 已退出操作")
                return
            if cmd.lower() == 't':
                middleware.bucketSet(bucket_name, key_name, ",".join(sorted_plugins))
                sender.reply("✅ 已全部开启")
                continue
            if cmd.lower() == 'f':
                middleware.bucketSet(bucket_name, key_name, "")
                sender.reply("✅ 已全部关闭")
                continue
            if cmd.startswith('+') or cmd.startswith('-'):
                action = cmd[0]
                target = cmd[1:].strip()
                target_plugin = None
                if target.isdigit():
                    idx = int(target) - 1
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
def handle_core_points_query(sender: middleware.Sender, user_id: str):
    points = get_core_points(user_id)
    sender.reply(f"""=====核心积分=====
🤪 用户ID: {user_id}
💎 当前积分: {points}
==================""")
def handle_core_points_recharge(sender: middleware.Sender, user_id: str):
    config = get_epay_config()
    has_epay = bool(config['epay_url'] and config['epay_pid'] and config['epay_key'])
    has_native = bool(config['native_wxpay'] and config['wx_qrcode'])
    has_alipay_bill = bool(config['alipay_bill'] and config['alipay_qrcode'] and config['alipay_app_id'] and config['alipay_private_key'])
    if not has_epay and not has_native and not has_alipay_bill:
        sender.reply("❌ 支付未完整配置，请联系管理员")
        return
    sender.reply("""=====核心积分充值=====
请输入充值金额(元)
------------------
回复数字设置
回复"q"退出""")
    amount_input = sender.input(60000, 0, False)
    if not amount_input or str(amount_input).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return
    try:
        amount = round(float(str(amount_input).strip()), 2)
        if amount <= 0:
            raise ValueError
    except:
        sender.reply("❌ 充值金额输入无效")
        return
    payment_options = []
    payment_methods = []
    if config['epay_alipay'] and has_epay:
        payment_options.append(f"[{len(payment_options) + 1}] 支付宝")
        payment_methods.append(("alipay", "支付宝"))
    if config['epay_wxpay'] and has_epay:
        payment_options.append(f"[{len(payment_options) + 1}] 微信")
        payment_methods.append(("wxpay", "微信"))
    if config['epay_qqpay'] and has_epay:
        payment_options.append(f"[{len(payment_options) + 1}] QQ")
        payment_methods.append(("qqpay", "QQ"))
    if config['native_wxpay'] and config['wx_qrcode']:
        payment_options.append(f"[{len(payment_options) + 1}] 内置微信支付")
        payment_methods.append(("native_wxpay", "内置微信支付"))
    if has_alipay_bill:
        payment_options.append(f"[{len(payment_options) + 1}] 支付宝账单")
        payment_methods.append(("alipay_bill", "支付宝账单"))
    if not payment_options:
        sender.reply("❌ 未启用任何充值支付方式，请联系管理员")
        return
    points_to_get = round(amount * config['exchange_rate'], 2)
    points_to_get = int(points_to_get) if points_to_get.is_integer() else points_to_get
    payment_menu = f"""=====支付方式=====
💰 充值金额: {amount}元
🎯 获得积分: {points_to_get}
------------------
{chr(10).join(payment_options)}
------------------
回复数字选择
回复"q"退出"""
    sender.reply(payment_menu)
    choice = sender.input(60000, 0, False)
    if not choice or str(choice).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return
    try:
        choice_num = int(str(choice))
        if choice_num < 1 or choice_num > len(payment_methods):
            raise ValueError
        payment_method, payment_name = payment_methods[choice_num - 1]
    except ValueError:
        sender.reply("❌ 请选择有效的支付方式")
        return
    if payment_method == "native_wxpay":
        sender.reply(f"""=====扫码充值=====
💰 金额: {amount}元
🎯 积分: {points_to_get}
💳 方式: {payment_name}
------------------
请在240秒内完成扫码支付
回复"q"取消充值""")
        sender.replyImage(config['wx_qrcode'])
        ddzf = sender.waitPay("q", 240 * 1000)
        if str(ddzf) == 'q':
            sender.reply("✅ 已主动取消充值")
            return
        try:
            if isinstance(ddzf, str):
                ddzf = json.loads(ddzf)
            if 'Money' in ddzf:
                Money = float(ddzf.get('Money', 0))
            else:
                Money = float(ddzf.get('money', 0))
            if float(Money) >= float(amount):
                if add_core_points(user_id, points_to_get):
                    sender.reply(f"""=====充值成功=====
💰 充值金额: {amount}元
🎯 获得积分: {points_to_get}
💎 当前积分: {get_core_points(user_id)}
==================""")
                else:
                    sender.reply("❌ 支付成功，但积分增加失败，请联系管理员")
                return
            else:
                sender.reply(f"""=====充值失败=====
❌ 支付金额不足
------------------
💰 应付: {amount}元
💵 实付: {Money}元
==================""")
                return
        except Exception as e:
            sender.reply(f"""=====支付异常=====
❌ 支付验证失败
------------------
⚠️ 错误: {str(e)}
==================""")
            return
    elif payment_method == "alipay_bill":
        session_data = allocate_alipay_bill_amount(user_id, amount, timeout_seconds=240)
        if not session_data:
            sender.reply("❌ 支付会话创建失败，请稍后重试")
            return
        adjusted_amount = float(session_data.get("adjusted_amount", amount))
        session_id = session_data.get("session_id", "")
        sender.reply(f"""=====扫码充值=====
💰 金额: {amount}元
🎯 积分: {points_to_get}
💳 方式: {payment_name}
♨️ 实付: {adjusted_amount:.2f}元
------------------
请在240秒内实付{adjusted_amount:.2f}元
回复"q"取消充值""")
        sender.replyImage(config['alipay_qrcode'])
        poll_start_time = time.time()
        user_quit_flag = {"quit": False}
        def _listen_user_input():
            while not user_quit_flag["quit"]:
                try:
                    u_inp = sender.input(1000, 0, False)
                    if u_inp and str(u_inp).lower() == "q":
                        user_quit_flag["quit"] = True
                        release_alipay_bill_amount(session_id, status="cancelled")
                        sender.reply("✅ 已主动取消充值")
                        break
                except:
                    pass
        listener_thread = threading.Thread(target=_listen_user_input, daemon=True)
        listener_thread.start()
        while time.time() - poll_start_time < 240 and not user_quit_flag["quit"]:
            time.sleep(1.5)
            try:
                status_result = check_alipay_bill_payment(config, session_id)
                if status_result.get('code') == 0:
                    user_quit_flag["quit"] = True
                    settle_result = settle_core_points_after_alipay_bill(
                        sender=sender,
                        user_id=user_id,
                        session_id=session_id,
                        amount=amount,
                        points_to_get=points_to_get,
                        status_result=status_result
                    )
                    if settle_result.get("code") == 0:
                        sender.reply(f"""=====充值成功=====
💰 充值金额: {amount}元
♨️ 实付金额: {float(settle_result.get("paid_money", adjusted_amount)):.2f}元
🎯 获得积分: {points_to_get}
💎 当前积分: {get_core_points(user_id)}
==================""")
                    else:
                        sender.reply(f"❌ 支付成功，但积分增加失败，请联系管理员")
                    return
            except Exception:
                pass
        user_quit_flag["quit"] = True
        if listener_thread.is_alive():
            listener_thread.join(timeout=1)
        release_alipay_bill_amount(session_id, status="timeout")
        if time.time() - poll_start_time >= 240:
            sender.reply("❌ 充值订单已超时")
        return
    else:
        order_id = generate_unique_order_id(user_id)
        epay_result = create_epay_order(config, order_id, amount, payment_method)
        if epay_result.get('code') != 0:
            sender.reply(f"❌ 创建订单失败: {epay_result.get('msg', '未知错误')}")
            return
        qr_code_url = epay_result.get('qr_code', '')
        sender.reply(f"""=====扫码充值=====
💰 金额: {amount}元
🎯 积分: {points_to_get}
💳 方式: {payment_name}
📋 订单: {order_id}
------------------
请在240秒内完成扫码支付
回复"q"取消充值""")
        if qr_code_url:
            from urllib.parse import quote
            qr_image_url = f"https://api.pwmqr.com/qrcode/create/?url={quote(qr_code_url)}"
            try:
                middleware.get_service_response("/sendImage", {
                    "senderid": sender.senderID,
                    "imageurl": qr_image_url
                })
            except:
                sender.reply("二维码链接(长按复制到浏览器打开):" + chr(10) + str(qr_code_url))
        else:
            sender.reply("❌ 二维码生成失败")
            return
        poll_start_time = time.time()
        user_quit_flag = {"quit": False}
        def _listen_user_input():
            while not user_quit_flag["quit"]:
                try:
                    u_inp = sender.input(1000, 0, False)
                    if u_inp and str(u_inp).lower() == "q":
                        user_quit_flag["quit"] = True
                        sender.reply("✅ 已主动取消充值")
                        break
                except:
                    pass
        listener_thread = threading.Thread(target=_listen_user_input, daemon=True)
        listener_thread.start()
        while time.time() - poll_start_time < 240 and not user_quit_flag["quit"]:
            time.sleep(1.5)
            status_result = check_epay_order_status(config, order_id)
            if status_result.get('code') == 0:
                user_quit_flag["quit"] = True
                if add_core_points(user_id, points_to_get):
                    sender.reply(f"""=====充值成功=====
💰 充值金额: {amount}元
🎯 获得积分: {points_to_get}
💎 当前积分: {get_core_points(user_id)}
==================""")
                else:
                    sender.reply("❌ 支付成功，但积分增加失败，请联系管理员")
                return
        user_quit_flag["quit"] = True
        if listener_thread.is_alive():
            listener_thread.join(timeout=1)
        if time.time() - poll_start_time >= 240:
            sender.reply("❌ 充值订单已超时")
def handle_admin_auth_points(sender: middleware.Sender):
    if not sender.isAdmin():
        sender.reply("❌ 权限不足：若非管理员请勿操作")
        return
    sender.reply("""=====积分授权=====
请输入目标用户ID
------------------
请在60秒内完成
回复"q"退出""")
    target_user_input = sender.input(60000, 0, False)
    if not target_user_input or str(target_user_input).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return
    target_user_id = str(target_user_input).strip()
    sender.reply(f"""=====积分数量=====
🤪 目标用户: {target_user_id}
💎 当前积分: {get_core_points(target_user_id)}
------------------
输入授权积分数
回复"q"退出""")
    
    points_input = sender.input(60000, 0, False)
    if not points_input or str(points_input).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return
    try:
        points_val = int(round(float(str(points_input).strip())))
        if points_val == 0:
            sender.reply("❌ 变动积分不能为0")
            return
    except:
        sender.reply("❌ 输入无效，必须为数字")
        return
    if points_val > 0:
        if add_core_points(target_user_id, points_val):
            sender.reply(f"""=====加分成功=====
🤪 目标用户: {target_user_id}
➕ 增加积分: {points_val}
💎 当前积分: {get_core_points(target_user_id)}
==================""")
        else:
            sender.reply("❌ 积分增加失败")
    else:
        deduct_val = abs(points_val)
        if deduct_core_points(target_user_id, deduct_val):
            sender.reply(f"""=====减分成功=====
🤪 目标用户: {target_user_id}
➖ 减少积分: {deduct_val}
💎 当前积分: {get_core_points(target_user_id)}
==================""")
        else:
            sender.reply(f"❌ 积分扣除失败，可能该用户余额不足 {deduct_val} 积分")      
def handle_core_points_sign_in(sender: middleware.Sender, user_id: str):
    is_sign_in_enabled = middleware.bucketGet("yuhua_epay", "sign_in") == "true"
    if not is_sign_in_enabled:
        sender.reply("❌ 核心积分签到功能未开启")
        return
    today_str = datetime.now().strftime("%Y-%m-%d")
    last_sign_in = middleware.bucketGet("yuhua_core_sign_in", str(user_id))
    
    if last_sign_in == today_str:
        sender.reply(f"""=====签到失败=====
🤪 用户ID: {user_id}
💎 当前积分: {get_core_points(user_id)}
✨ 签到结果: 今日已签请明日再来
==================""")
        return
    sign_range = middleware.bucketGet("yuhua_epay", "sign_range") or "1-5"
    try:
        min_val, max_val = map(float, sign_range.split('-'))
        if min_val > max_val:
            min_val, max_val = max_val, min_val
    except:
        min_val, max_val = 1.0, 5.0
    points_to_add = random.randint(int(round(min_val)), int(round(max_val)))
    if add_core_points(user_id, points_to_add):
        middleware.bucketSet("yuhua_core_sign_in", str(user_id), today_str)
        sender.reply(f"""=====签到成功=====
🤪 用户ID: {user_id}
➕ 获得积分: {points_to_add}
💎 当前积分: {get_core_points(user_id)}
==================""")
    else:
        sender.reply("❌ 签到失败，积分增加异常，请稍后重试")
def handle_core_points_lottery(sender: middleware.Sender, user_id: str):
    is_lottery_enabled = middleware.bucketGet("yuhua_epay", "lottery") == "true"
    if not is_lottery_enabled:
        sender.reply("❌ 核心积分抽奖功能未开启")
        return
    config_str = middleware.bucketGet("yuhua_epay", "lottery_config") or "5|50%|5-10"
    try:
        parts = config_str.split('|')
        cost = int(round(float(parts[0])))    
        prob = float(parts[1].replace('%', '')) / 100.0       
        min_val, max_val = map(float, parts[2].split('-'))
        if min_val > max_val:
            min_val, max_val = max_val, min_val
    except:
        cost, prob, min_val, max_val = 5, 0.5, 5.0, 10.0
    current_points = get_core_points(user_id)
    sender.reply(f"""=====积分抽奖=====
🎯 消耗积分: {cost}
💎 当前积分: {current_points}
------------------
回复"1"确定抽奖
回复"q"取消操作""")
    user_input = sender.input(60000, 0, False)
    if not user_input or str(user_input).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return        
    if str(user_input).strip() != '1':
        sender.reply("❌ 输入有误，已退出")
        return
    if current_points < cost:
        sender.reply("❌ 抽奖失败：您的核心积分不足")
        return
    if deduct_core_points(user_id, cost):
        if random.random() < prob:
            reward = random.randint(int(round(min_val)), int(round(max_val)))           
            if add_core_points(user_id, reward):
                sender.reply(f"""=====抽奖结果=====
🎉 运气不错，还来么~
➕ 获得积分: {reward}
➖ 消耗积分: {cost}
💎 当前积分: {get_core_points(user_id)}
==================""")
            else:
                sender.reply("❌ 中奖结算失败，积分增加异常")
        else:
            sender.reply(f"""=====抽奖结果=====
😭 谢谢惠顾，未中奖~
➖ 消耗积分: {cost}
💎 当前积分: {get_core_points(user_id)}
==================""")
    else:
        sender.reply("❌ 抽奖失败，积分扣除异常，请稍后重试")
def handle_core_points_migration(sender: middleware.Sender):
    if not sender.isAdmin():
        sender.reply("❌ 权限不足：若非管理员请勿操作")
        return
    try:
        custom_bucket = middleware.bucketGet("yuhua_epay", "custom_points_bucket")
        custom_bucket = custom_bucket.strip() if custom_bucket else ""
    except Exception:
        custom_bucket = ""
    if not custom_bucket:
        sender.reply("❌ 迁移失败：未在后台配置『自定义桶』参数")
        return
    try:
        is_compat = middleware.bucketGet("yuhua_epay", "compat_points") == "true"
    except Exception:
        is_compat = False
    if is_compat:
        source_bucket = "yuhua_core_points"
        target_bucket = custom_bucket
        direction_text = f"【羽化原生桶(yuhua_core_points)】 转移至 【自定义桶({custom_bucket})】"
    else:
        source_bucket = custom_bucket
        target_bucket = "yuhua_core_points"
        direction_text = f"【自定义桶({custom_bucket})】 转移至 【羽化原生桶(yuhua_core_points)】"
    sender.reply(f"""=====核心积分迁移=====
❶即将从 {direction_text}
❷请提前发送指令导出数据防止迁移过程出错丢失数据
------------------
回复"确定"开始迁移
回复"q"取消""")  
    user_input = sender.input(60000, 0, False)
    if not user_input or str(user_input).strip() != '确定':
        sender.reply("✅ 已取消迁移操作")
        return
    sender.reply("⏳ 正在处理积分迁移，请稍候...")  
    success_count = 0
    fail_count = 0
    try:
        source_keys_raw = middleware.bucketAllKeys(source_bucket)
        if not source_keys_raw:
            source_keys = []
        elif isinstance(source_keys_raw, str):
            source_keys = [k.strip() for k in source_keys_raw.split(',') if k.strip()]
        elif isinstance(source_keys_raw, list):
            source_keys = [str(k).strip() for k in source_keys_raw if str(k).strip()]
        else:
            source_keys = []
        if not source_keys:
            sender.reply("❌ 迁移结束：源积分桶为空，未发现任何数据")
            return
        for uid in source_keys:
            user_lock = get_core_user_lock(uid)
            with user_lock:
                try:
                    src_val_str = middleware.bucketGet(source_bucket, uid)
                    if not src_val_str:
                        continue
                    src_val_float = float(src_val_str)
                    src_val_rounded = int(src_val_float + 0.5)
                    tgt_val_str = middleware.bucketGet(target_bucket, uid)
                    tgt_val_int = int(round(float(tgt_val_str))) if tgt_val_str else 0                 
                    new_val = src_val_rounded + tgt_val_int                
                    middleware.bucketSet(target_bucket, uid, str(new_val))
                    try:
                        middleware.bucketDel(source_bucket, uid)
                    except Exception:
                        pass                
                    success_count += 1
                except ValueError:
                    fail_count += 1
                except Exception:
                    fail_count += 1
        sender.reply(f"""=====迁移结果=====
✅ 迁移成功: {success_count} 条
❌ 迁移失败: {fail_count} 条
==================""")
    except Exception as e:
        sender.reply(f"❌ 迁移过程中发生系统异常：{str(e)}")
def handle_generate_core_cards(sender: middleware.Sender):
    if not sender.isAdmin():
        sender.reply("❌ 权限不足：若非管理员请勿操作")
        return
    chat_id = sender.getChatID()
    user_id = sender.getUserID()
    if chat_id and str(chat_id) not in["0", "", str(user_id)]:
        sender.reply("❌ 为保护卡密数据安全，此指令强制要求在私聊中使用")
        return
    sender.reply("""=====生成卡密=====
请输入生成的卡密面额(核心积分)
------------------
回复数字设置
回复"q"退出""")
    points_input = sender.input(60000, 0, False)
    if not points_input or str(points_input).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return
    try:
        points = int(round(float(str(points_input).strip())))
        if points <= 0:
            raise ValueError
    except:
        sender.reply("❌ 面额输入无效")
        return
    sender.reply(f"""=====生成卡密=====
💰 卡密面额: {points} 积分
------------------
请输入生成数量
回复"q"退出""")
    count_input = sender.input(60000, 0, False)
    if not count_input or str(count_input).lower() == 'q':
        sender.reply("✅ 已取消操作")
        return
    try:
        count = int(str(count_input).strip())
        if count <= 0 or count > 200:
            sender.reply("❌ 数量输入无效或过大(最多200个)")
            return
    except:
        sender.reply("❌ 数量输入无效")
        return
    generated_keys =[]
    current_list_str = middleware.bucketGet("yuhua_core_cards_list", "keys") or ""
    current_list =[k.strip() for k in current_list_str.split(',') if k.strip()]
    for _ in range(count):
        import uuid
        new_key = "YH-" + str(uuid.uuid4()).split('-')[0].upper() + str(uuid.uuid4()).split('-')[1].upper()
        card_data = {
            "points": points,
            "status": 0,
            "user": "",
            "used_time": ""
        }
        middleware.bucketSet("yuhua_core_cards", new_key, json.dumps(card_data, ensure_ascii=False))
        generated_keys.append(new_key)
        current_list.append(new_key)
    middleware.bucketSet("yuhua_core_cards_list", "keys", ",".join(current_list))
    reply_msg = f"=====生成成功=====\n"
    reply_msg += f"💰 面额: {points} 积分\n"
    reply_msg += f"📦 数量: {count} 个\n"
    reply_msg += "------------------\n"
    reply_msg += "\n".join(generated_keys)
    reply_msg += "\n=================="
    sender.reply(reply_msg)
def handle_view_core_cards(sender: middleware.Sender):
    if not sender.isAdmin():
        sender.reply("❌ 权限不足：若非管理员请勿操作")
        return
    chat_id = sender.getChatID()
    user_id = sender.getUserID()
    if chat_id and str(chat_id) not in ["0", "", str(user_id)]:
        sender.reply("❌ 为保护卡密数据安全，此指令强制要求在私聊中使用")
        return
    current_list_str = middleware.bucketGet("yuhua_core_cards_list", "keys") or ""
    current_list =[k.strip() for k in current_list_str.split(',') if k.strip()]
    if not current_list:
        sender.reply("❌ 暂无任何核心卡密记录")
        return
    reply_msg = "=====核心卡密列表=====\n"
    for idx, card_key in enumerate(current_list):
        card_data_str = middleware.bucketGet("yuhua_core_cards", card_key)
        if card_data_str:
            try:
                card_data = json.loads(card_data_str)
                status_str = "已使用" if card_data.get("status") == 1 else "未使用"
                points = card_data.get("points", 0)
                points = int(points) if float(points).is_integer() else points
                user = card_data.get("user") or "暂无"
                used_time = card_data.get("used_time") or "暂无"
                reply_msg += f"🔑 卡密: {card_key}\n💰 面额: {points} 积分\n"
                reply_msg += f"📌 状态: {status_str}\n🤪 用户: {user}\n⏰ 时间: {used_time}\n"
                reply_msg += "------------------\n"
            except:
                pass
        if (idx + 1) % 15 == 0:
            if reply_msg.endswith("------------------\n"):
                reply_msg = reply_msg[:-19]
            sender.reply(reply_msg)
            reply_msg = ""
            time.sleep(0.5)
    if reply_msg:
        if reply_msg.endswith("------------------\n"):
            reply_msg = reply_msg[:-19]
        reply_msg += "=================="
        sender.reply(reply_msg)
    else:
        sender.reply("==================")
def handle_query_core_card(sender: middleware.Sender):
    message = sender.getMessage()
    parts = message.split(" ", 1)
    if len(parts) > 1 and parts[1].strip():
        card_key = parts[1].strip()
    else:
        sender.reply("""=====查询卡密=====
请输入您要查询的卡密
------------------
请在60秒内输入
回复"q"退出""")
        card_key_input = sender.input(60000, 0, False)
        if not card_key_input or str(card_key_input).lower() == 'q':
            sender.reply("✅ 已取消操作")
            return
        card_key = str(card_key_input).strip()
    card_data_str = middleware.bucketGet("yuhua_core_cards", card_key)
    if not card_data_str:
        sender.reply("❌ 查询失败：该卡密不存在或拼写错误")
        return
    try:
        card_data = json.loads(card_data_str)
        status_str = "已使用" if card_data.get("status") == 1 else "未使用"
        points = card_data.get("points", 0)
        points = int(points) if float(points).is_integer() else points     
        user = card_data.get("user") or "暂无"
        used_time = card_data.get("used_time") or "暂无"
        sender.reply(f"""=====卡密详情=====
🔑 卡密: {card_key}
💰 面额: {points} 积分
📌 状态: {status_str}
🤪 用户: {user}
⏰ 时间: {used_time}
==================""")
    except:
        sender.reply("❌ 卡密数据解析异常，请联系管理员")
def handle_activate_core_card(sender: middleware.Sender, user_id: str):
    message = sender.getMessage()
    parts = message.split(" ", 1)    
    if len(parts) > 1 and parts[1].strip():
        card_key = parts[1].strip()
    else:
        sender.reply("""=====激活卡密=====
请输入您要激活的卡密
------------------
请在60秒内输入
回复"q"退出""")
        card_key_input = sender.input(60000, 0, False)
        if not card_key_input or str(card_key_input).lower() == 'q':
            sender.reply("✅ 已取消操作")
            return
        card_key = str(card_key_input).strip()
    card_lock = get_core_card_lock(card_key)
    with card_lock:
        card_data_str = middleware.bucketGet("yuhua_core_cards", card_key)
        if not card_data_str:
            sender.reply("❌ 激活失败：该卡密不存在或已被物理删除")
            return
        try:
            card_data = json.loads(card_data_str)
        except:
            sender.reply("❌ 激活失败：卡密数据损坏")
            return
        if card_data.get("status") == 1:
            sender.reply(f"❌ 激活失败：该卡密已被用户 {card_data.get('user')} 在 {card_data.get('used_time')} 激活使用")
            return
        points_to_add = card_data.get("points", 0)
        points_to_add = int(points_to_add) if float(points_to_add).is_integer() else points_to_add
        if add_core_points(user_id, points_to_add):
            card_data["status"] = 1
            card_data["user"] = user_id
            card_data["used_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            middleware.bucketSet("yuhua_core_cards", card_key, json.dumps(card_data, ensure_ascii=False))
            sender.reply(f"""=====激活成功=====
🤪 用户ID: {user_id}
➕ 获得积分: {points_to_add}
💎 当前积分: {get_core_points(user_id)}
==================""")
        else:
            sender.reply("❌ 激活失败，积分并发系统异常，请稍后重试")            
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
def main():
    sender = middleware.Sender(middleware.getSenderID())
    if not check_maintenance_page():
        sender.reply("❌ 服务端无法连通, 插件停止运行")
        return
    if sender.getImtype() == 'rt':
        router_path = sender.getRouterPath()
        if router_path == "/epay_hijack":
            handle_epay_hijack_api(sender)
        return
    message = sender.getMessage()
    if message == "支付接管":
        sender.reply("""
        
请回复以下指令：
核心积分签到
核心积分查询
核心积分抽奖
核心积分充值
核心积分授权
核心卡密激活
核心卡密生成
核心卡密查询
核心卡密查看
开启支付接管
关闭支付接管
管理支付接管""")
    elif message == "开启支付接管":
        toggle_epay_status(sender, enable=True)
    elif message == "关闭支付接管":
        toggle_epay_status(sender, enable=False)
    elif message == "替换中间件":
        enable_text_to_image(sender)
    elif message == "还原中间件":
        reset_text_to_image(sender)
    elif message.startswith("支付接管列表") or message.startswith("添加支付接管") or message.startswith("删除支付接管"):
        manage_epay_plugin_list(sender)
    elif message == "管理支付接管":
        handle_plugin_management(sender, "管理支付接管", "yuhua_epay", "plugins")
    elif message == "核心积分查询":
        handle_core_points_query(sender, sender.getUserID())
    elif message == "核心积分充值":
        handle_core_points_recharge(sender, sender.getUserID())
    elif message == "核心积分授权":
        handle_admin_auth_points(sender)
    elif message == "核心积分签到":
        handle_core_points_sign_in(sender, sender.getUserID())
    elif message == "核心积分抽奖":
        handle_core_points_lottery(sender, sender.getUserID())
    elif message == "核心积分迁移":
        handle_core_points_migration(sender)
    elif message == "核心卡密生成":
        handle_generate_core_cards(sender)
    elif message == "核心卡密查看":
        handle_view_core_cards(sender)
    elif message.startswith("核心卡密激活"):
        handle_activate_core_card(sender, sender.getUserID())
    elif message.startswith("核心卡密查询"):
        handle_query_core_card(sender)
    else:
        pass
if __name__ == '__main__':
    main()
