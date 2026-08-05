# [title: 小蚕霸王餐]
# [icon: https://gcore.jsdelivr.net/gh/lhz03/img@368cbd87cbbdfd3bff1534d4c7a7957ca76f1c54/2025/02/18/4003bcfc1f8d46cd6f9de1b656bbddab.png]
# [language: python]
# [rule: ^(小蚕)(登录|查询|提宝|提微|查单|运行|管理|授权|检测|清理|解限|一键运行|一键监控|一键红包雨)$]
# [open_source: false]
# [platform: qq,qb,wx,gw,sb,wb,tg,tb,qx,xy,ip]
# [public: true]
# [priority: 9999999999999999999]
# [version: 11.2.3]
# [author: yuhualhh]
# [description: ❶小蚕霸王餐内置任务插件，可实现新返现活动推送以及自动抢单、瓜分红包雨、短信验证过火爆、完成每日任务并抽奖、领取累计抽奖奖励、自定义并发、配置代理、微信扫码登录、查询、授权、管理、破上限提现微信、检测授权过期以及CK失效并推送等功能<br>❷部分功能的实现需自行添加计划任务伪装管理员定时，了解如何添加计划任务请看移动云盘插件介绍，关于指令『小蚕检测』与『小蚕清理』定时『30 18 * * *』，关于指令『小蚕一键监控』定时『0 */10 * * * *』，关于指令『小蚕一键红包雨』建议定时『0 59 7,9,11,13,15,18 * * *』，关于指令『小蚕一键运行』定时『0 8,20 * * *』<img src="https://gcore.jsdelivr.net/gh/lhz03/img@f054476821a50f66328fa8271886fab6f8b50964/2025/05/01/9ac4e3c4f46248746e9d0c7a353f38f9.png">]
# [param: {"required":true,"key":"yuhua_xcbwc.share","bool":false,"placeholder":"","name":"推广码子","desc":"小蚕推广码直链"}]
# [param: {"required":true,"key":"yuhua_xcbwc.zsm","bool":false,"placeholder":"","name":"收款方式","desc":"微信Bot收款码直链"}]
# [param: {"required":true,"key":"yuhua_xcbwc.price","bool":false,"placeholder":"","name":"上车价格","desc":"不填默认0元，单位: 元/月"}]
# [param: {"required":true,"key":"yuhua_xcbwc.bingfa","bool":false,"placeholder":"","name":"并发数量","desc":"不填默认5，若频繁提示IP已被风控请配置代理"}]
# [param: {"required":true,"key":"yuhua_xcbwc.status","bool":false,"placeholder":"例:1，不填默认直连","name":"启用代理","desc":"0=直连，1=代理池，2=API代理"}]
# [param: {"required":true,"key":"yuhua_xcbwc.proxy","bool":false,"placeholder":"请输入 http://xxx 或 https://xxx","name":"代理地址","desc":"支持代理池以及API代理"}]
# [param: {"required":true,"key":"yuhua_xcbwc.ip","bool":false,"placeholder":"例:30，不填默认不限制","name":"代理限制","desc":"单IP代理次数限制，仅对API代理有效，填0为不限制"}]
# [param: {"required":false,"key":"yuhua_xcbwc.push","bool":true,"placeholder":"","name":"运行推送","desc":"是否将一键运行结果推送给用户"}]
# [param: {"required":false,"key":"yuhua_xcbwc.hongbaoyu_push","bool":true,"placeholder":"","name":"瓜分推送","desc":"是否将瓜分红包雨结果推送给用户"}]
# [param: {"required":false,"key":"yuhua_xcbwc.img","bool":true,"placeholder":"","name":"店铺头像","desc":"是否在店铺活动信息中显示店铺头像"}]
# [param: {"required":false,"key":"yuhua_xcbwc.jiankong","bool":true,"placeholder":"","name":"监控抢单","desc":"是否启用监控抢单功能"}]
#[param: {"required":false,"key":"yuhua_xcbwc.debug_pwd","bool":false,"placeholder":"","name":"调试模式","desc":"非插件开发者无需理会，填入密钥开启详细日志"}]  
import middleware,re,random,time,json,requests,hashlib,uuid,threading,socket,concurrent.futures,sys
from typing import Dict
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
CHINA_TZ = timezone(timedelta(hours=8))
_time_offset = None
_offset_expiry = 0
_ip_cache_pool = []
_ip_cache_lock = threading.Lock()
REMOTE_PHP_HOST="http://yuhua.oroe.cn/xc/verify.php"
REMOTE_PHP_SECRET = "Yuhua888888"
DDDDOCR_HOST = "http://ddddocr.250666.xyz"
debug_key = middleware.bucketGet('yuhua_xcbwc', 'debug_pwd') or ''
DEBUG_LOG = (debug_key == '123456789abcC@')
if DEBUG_LOG:
    sys.stderr.write("\033[33m[WARN] 🔥🔥🔥 小蚕插件调试模式已开启，密钥验证通过 🔥🔥🔥\033[0m\n")
    sys.stderr.flush()
def printf(msg,level='INFO'):
    if not DEBUG_LOG: return
    c=32 if level in['INFO','DEBUG']else 33 if level in['WARN','WARNING']else 31;sys.stderr.write(f"\033[{c}m[{level}] {str(msg)}\033[0m\n");sys.stderr.flush()
def get_device_data(key):
    k=str(key) if key and str(key)!="0" else str(userid)
    rk=middleware.bucketGet('yuhua_xcbwc_teemo',k) or k
    if d:=middleware.bucketGet('yuhua_xcbwc_dev',rk):
        try:
            old_info = json.loads(d)
            ua = old_info.get('ua', '')
            model = old_info.get('model', '')
            model_code = model.split(' ')[0] if model else "INVALID_MODEL"
            if ("Chrome/14" in ua or "Chrome/13" in ua) and (model_code in ua):
                return old_info
        except: pass
    b=random.choice(["realme","Xiaomi","vivo","OPPO","HUAWEI","HONOR","Samsung"])
    if b=="realme":m=f"RMX{random.randint(3700,3999)}"
    elif b=="Xiaomi":m=f"{random.choice(['24','25','26'])}{random.randint(0,1)}{random.randint(1,9)}{random.randint(10,19)}C"
    elif b=="vivo":m=f"V{random.randint(2300,2500)}A"
    elif b=="OPPO":m=f"P{random.choice(['G','H','J','K'])}{random.choice(['D','M','T'])}{random.randint(110,130)}"
    elif b=="HUAWEI":m=f"{random.choice(['ALN','HBP','BRA'])}-{random.choice(['AL','AN'])}{random.randint(0,9)}0"
    elif b=="HONOR":m=f"{random.choice(['PGT','BVL','MAA'])}-AN{random.randint(0,2)}0"
    else:m=f"SM-S9{random.randint(1,3)}{random.randint(1,8)}0"
    v=str(random.randint(13,15))
    bld=f"{random.choice(['S','T','U','V'])}P1A.{random.randint(230101,251231)}.0{random.randint(10,99)}"
    cv=f"{random.randint(135,145)}.0.{random.randint(5000,7500)}.{random.randint(50,200)}"
    wx_ver=f"8.0.{random.randint(60,66)}"
    ua=f"Mozilla/5.0 (Linux; Android {v}; {m} Build/{bld}; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{cv} Mobile Safari/537.36 XWEB/{random.randint(6000,9999)} MMWEBSDK/2025{random.randint(1,12):02d}02 MMWEBID/{random.randint(1000,9999)} MicroMessenger/{wx_ver}.2600(0x2800{random.randint(30,35)}{random.randint(10,99)}) WeChat/arm64 Weixin NetType/5G Language/zh_CN ABI/arm64 MiniProgramEnv/android"
    info={"ua":ua,"model":f"{m} {b}","dm":b}
    middleware.bucketSet('yuhua_xcbwc_dev',rk,json.dumps(info))
    return info
class TencentCaptchaClient:
    def __init__(self, key=None):
        self.sess=requests.Session();self.host="https://m.captcha.qq.com";self.sid="";self.uid="";self.dev=get_device_data(key)
        self.sess.headers.update({"User-Agent":self.dev['ua'],"Referer":"https://servicewechat.com/wx52ae177248081591/664/page-frame.html","content-type":"application/json"})
    def check_app_id(self):
        for i in range(3):
            try:
                r=self.sess.post(f"{self.host}/",json={"Action":"CheckCaptchaAppId_v1.0.1","CaptchaAppId":2035846791},timeout=5)
                if DEBUG_LOG: printf(f"[TX][{i+1}/3] >>> {r.request.url}\n[Req] {r.request.body}\n<<< {r.status_code}\n[Rsp] {r.text}", "DEBUG")
                js=r.json()
                if js.get("Response",{}).get("CaptchaCode")==0:self.sid=js.get("Response",{}).get("SId","");return True,""
                return False,js.get("Response",{}).get("CaptchaMsg","服务异常")
            except Exception as e: time.sleep(1)
        return False,"连接超时"
    def get_image_data(self):
        for i in range(3):
            try:
                r=self.sess.post(f"{self.host}/",json={"Action":"GetImageData_v1.0.1","ESId":self.sid},timeout=10)
                if DEBUG_LOG: printf(f"[TX][{i+1}/3] >>> {r.request.url}\n[Req] {r.request.body}\n<<< {r.status_code}\n[Rsp] (Base64 Data Ignored for View)", "DEBUG")
                d=r.json().get("Response",{})
                if d.get("CaptchaCode")==0:
                    self.uid=d.get("UniqueSId","")
                    return {"bg":d.get("ImageDataL"),"slide":d.get("ImageDataS"),"y":int(d.get("LeftTopY",0))},""
                return None,d.get("CaptchaMsg","获取失败")
            except Exception as e: time.sleep(1)
        return None,"获取超时"
    def verify_answer(self,x):
        for i in range(3):
            try:
                r=self.sess.post(f"{self.host}/",json={"Action":"VerificationCaptchaImageAnswer_v1.0.1","LeftTopX":str(float(x)),"ranNum":0,"Frequency":1,"UniqueSId":self.uid},timeout=10)
                if DEBUG_LOG: printf(f"[TX][{i+1}/3] >>> {r.request.url}\n[Req] {r.request.body}\n<<< {r.status_code}\n[Rsp] {r.text}", "DEBUG")
                d=r.json().get("Response",{})
                if d.get("CaptchaCode")==0:return True,d.get("Ticket"),d.get("Randstr")
                return False,d.get("CaptchaMsg"),None
            except Exception as e: time.sleep(1)
        return False,"验证超时",None        
class RemoteCaptchaHandler:
    def __init__(self,url):self.url=url;self.token=f"v_{uuid.uuid4().hex[:8]}"
    def init_session(self,bg,slide,y):
        for i in range(3):
            try:
                r=requests.post(f"{self.url}?action=init&token={self.token}",json={"bg":bg,"slide":slide,"y":y},headers={"X-API-Key":REMOTE_PHP_SECRET},timeout=10)
                if DEBUG_LOG: printf(f"[PHP][{i+1}/3] >>> {r.request.url}\n[Req] (Base64 Data)\n<<< {r.status_code}\n[Rsp] {r.text}", "DEBUG")
                if r.status_code==200:return True
            except Exception as e: time.sleep(1)
        return False
    def get_user_url(self):return f"{self.url}?token={self.token}"
    def poll_user_slide(self):
        try:
            r=requests.get(f"{self.url}?action=poll_x&token={self.token}",timeout=5)
            if r.status_code==200 and r.json().get("code")==0:
                 if DEBUG_LOG: printf(f"[PHP-Poll] >>> {r.request.url}\n<<< {r.status_code}\n[Rsp] {r.text}", "DEBUG")
                 return r.json().get("x")
        except:pass
        return None
    def report_result(self,suc,msg=""):
        for i in range(3):
            try:
                r=requests.post(f"{self.url}?action=report_result&token={self.token}",json={"success":suc,"msg":msg},headers={"X-API-Key":REMOTE_PHP_SECRET},timeout=5)
                if DEBUG_LOG: printf(f"[PHP][{i+1}/3] >>> {r.request.url}\n[Req] {r.request.body}\n<<< {r.status_code}\n[Rsp] {r.text}", "DEBUG")
                break
            except:time.sleep(1)
class DdddocrClient:
    def __init__(self,url=None):self.url=url or DDDDOCR_HOST
    def recognize(self,bg_b64,slide_b64):
        for i in range(3):
            try:
                r=requests.post(f"{self.url}/capcode",json={"slidingImage":slide_b64,"backImage":bg_b64,"simpleTarget":True},timeout=15)
                if DEBUG_LOG: printf(f"[DDDDOCR][{i+1}/3] >>> {r.request.url}\n<<< {r.status_code}\n[Rsp] {r.text}", "DEBUG")
                if r.status_code==200:
                    js=r.json();x=js.get("result")
                    if x is not None:return True,float(x)
                    return False,js.get("error","识别失败")
            except Exception as e:
                if DEBUG_LOG: printf(f"[DDDDOCR][{i+1}/3] [Err] {str(e)}", "ERROR")
                time.sleep(0.5)
        return False,"连接超时"
def cmd_fix_risk():
    accs=get_accounts(userid)
    if not accs: sender.reply("=====未绑定账号=====\n❌ 未找到任何账号信息\n💡 发送 小蚕登录 绑定账号\n==================");return
    lines=["=====账号列表====="]
    for i,acid in enumerate(accs,1):
        nm=middleware.bucketGet('yuhua_xcbwc_remark',acid) or acid
        auth_status="⚠️ 未授权"
        if auth_date:=middleware.bucketGet('yuhua_xcbwc_auth',acid):
            try: auth_status=f"✅ {auth_date}" if datetime.strptime(auth_date,"%Y-%m-%d").date()>=today else "❌ 已过期"
            except: pass
        lines.extend([f"[{i}] 账号信息",f"🤪 账号: {nm}",f"☁ 授权: {auth_status}","------------------"])
    lines.extend(["回复数字选择","回复'q'退出","=================="])
    sender.reply("\n".join(lines))
    c=get_user_input(None)
    if not c: return
    try:
        idx=int(c)
        if 1<=idx<=len(accs): sub_fix_risk(accs[idx-1])
        else: sender.reply("❌ 无效选择")
    except: sender.reply("❌ 无效输入")
def sub_fix_risk(acid):
    nm=middleware.bucketGet('yuhua_xcbwc_remark',acid) or acid
    if not check_auth_valid(acid): sender.reply(f"=====小蚕解限=====\n🤪 账号: {nm}\n❌ 状态: 未授权或授权已过期\n==================");return
    ck=middleware.bucketGet('yuhua_xcbwc_token',acid)
    if not ck: sender.reply(f"=====小蚕解限=====\n🤪 账号: {nm}\n❌ 状态: CK不存在\n==================");return
    loc_str=middleware.bucketGet('yuhua_xcbwc_jiankong_weizhi',acid)
    if not loc_str: sender.reply(f"=====小蚕解限=====\n🤪 账号: {nm}\n❌ 状态: 未记录位置\n==================");return
    try: city_code=int(json.loads(loc_str).get("city_code",440304))
    except: sender.reply(f"=====小蚕解限=====\n🤪 账号: {nm}\n❌ 状态: 位置信息解析失败\n==================");return  
    sender.reply(f"正在执行...")
    api=yuhua(ck)
    try: api.get_silk()
    except: pass
    def _execute_unlock_flow(api_obj):
        ph = middleware.bucketGet('yuhua_xcbwc_phone', acid)
        if ph:
            for _ in range(3):
                try:
                    mf=ph[3:7];pc_payload={"silk_id":int(api_obj.teemo),"number":mf,"app_id":20}
                    r1=api_obj._make_rpc_request("Brs","RiskCheckService.PhoneCheck",pc_payload).json()
                    if r1.get("status",{}).get("code")!=0 or not r1.get("pass"): 
                        try:
                            middleware.bucketDel('yuhua_xcbwc_phone',acid)
                        except Exception:
                            pass
                        ph=None;break
                    break
                except Exception as e: time.sleep(1)        
        if not ph:
            sender.reply(f"=====身份验证=====\n请输入绑定的手机号\n------------------\n请在60秒内输入\n回复\"q\"退出");ph=sender.input(60000,1,False)
            if not ph: sender.reply("❌ 超时已退出");return False
            if ph.strip().lower()=='q': sender.reply("✅ 已退出操作");return False
            ph=ph.strip()
            if len(ph)!=11: sender.reply("❌ 手机号格式错误");return False
            pc_ok,pc_msg=False,""
            for _ in range(3):
                try:
                    mf=ph[3:7];pc_payload={"silk_id":int(api_obj.teemo),"number":mf,"app_id":20}
                    r1=api_obj._make_rpc_request("Brs","RiskCheckService.PhoneCheck",pc_payload).json()
                    if r1.get("status",{}).get("code")!=0 or not r1.get("pass"): pc_ok=False;pc_msg=r1.get("status",{}).get("msg");break
                    pc_ok=True;break
                except Exception as e: pc_msg=str(e);time.sleep(1)
            if not pc_ok: sender.reply(f"❌ 预检失败: {pc_msg}");return False
            middleware.bucketSet('yuhua_xcbwc_phone',acid,ph)
        tc=TencentCaptchaClient(acid);ok,msg=tc.check_app_id()
        if not ok: sender.reply(f"❌ 验证码服务异常: {msg}");return False
        cd,msg=tc.get_image_data()
        if not cd: sender.reply(f"❌ 获取滑块失败: {msg}");return False     
        ddocr=DdddocrClient();auto_ok=False;ctx={"tik":None,"rst":None}
        sender.reply("🤖 正在自动识别滑块...")
        for attempt in range(3):
            try:
                rec_ok,rec_x=ddocr.recognize(cd['bg'],cd['slide'])
                if rec_ok:
                    v_ok,tik,rst=tc.verify_answer(rec_x)
                    if v_ok:
                        sender.reply(f"🎉 自动识别成功 (第{attempt+1}次)")
                        ctx={"tik":tik,"rst":rst};auto_ok=True;break
                    else: sender.reply(f"⚠️ 验证失败 ({attempt+1}/3): {tik}")
                else: sender.reply(f"⚠️ 识别失败 ({attempt+1}/3): {rec_x}")
            except Exception as e: sender.reply(f"⚠️ 异常 ({attempt+1}/3): {str(e)}")          
        if not auto_ok:
            sender.reply("🔄 自动识别失败，切换手动验证...")
            rh=RemoteCaptchaHandler(REMOTE_PHP_HOST)
            if not rh.init_session(cd['bg'],cd['slide'],cd['y']): sender.reply("❌ 远程验证初始化失败");return False
            sender.reply(f"=====滑块验证=====\n❶请复制链接到浏览器打开\n❷{rh.get_user_url()}\n------------------\n请在60秒内完成\n回复\"q\"退出")
            ctx_manual={"quit":False,"ok":False}
            def wait_slide():
                st=time.time()
                while time.time()-st<60 and not ctx_manual["quit"]:
                    ux=rh.poll_user_slide()
                    if ux is not None:
                        v_ok,tik,rst=tc.verify_answer(ux);rh.report_result(v_ok)
                        if v_ok: ctx["tik"]=tik;ctx["rst"]=rst;ctx_manual["ok"]=True;break
                    time.sleep(1)
            t=threading.Thread(target=wait_slide,daemon=True);t.start()
            while t.is_alive():
                if sender.input(1000,0,False)=='q': ctx_manual["quit"]=True;sender.reply("✅ 已终止操作");return False
            if not ctx_manual["ok"]: sender.reply("❌ 验证超时或未通过");return False
        sms_ok,sms_msg=False,""
        for _ in range(3):
            try:
                payload={"silk_id":int(api_obj.teemo),"phone":ph,"ticket":ctx["tik"],"rand_str":ctx["rst"] if ctx["rst"] else "","platform":1,"app_id":20}
                r2=api_obj._make_rpc_request("Brs","RiskCheckService.SmsCheck",payload).json()
                if r2.get("status",{}).get("code")!=0: sms_ok=False;sms_msg=r2.get("status",{}).get("msg");break
                sms_ok=True;break
            except Exception as e: sms_msg=str(e);time.sleep(1)
        if not sms_ok: sender.reply(f"❌ 短信发送失败: {sms_msg}");return False
        sender.reply("=====短信验证=====\n请输入短信验证码\n------------------\n请在60秒内输入\n回复\"q\"退出");sc=sender.input(60000,0,False)
        if not sc: sender.reply("❌ 超时已退出");return False
        if sc.strip().lower()=='q': sender.reply("✅ 已退出操作");return False
        sc=sc.strip();vf_ok,vf_msg,vf_pass=False,"",False
        for _ in range(3):
            try:
                cs=hashlib.sha256(f"{ph}{sc}".encode("utf-8")).hexdigest()
                payload_v={"silk_id":int(api_obj.teemo),"service_name":"Brs","sms_code":sc,"check_sum":cs,"app_id":20}
                r3=api_obj._make_rpc_request("Brs","RiskCheckService.Verify",payload_v).json()
                if r3.get("status",{}).get("code")==0 and r3.get("pass"): vf_ok=True;vf_pass=True;break
                vf_ok=True;vf_pass=False;vf_msg=r3.get("status",{}).get("msg");break
            except Exception as e: vf_msg=str(e);time.sleep(1)           
        if vf_ok and vf_pass:
            sender.reply(f"✅ 当前环节解限成功")
            return True
        else:
            sender.reply(f"❌ 解限失败: {vf_msg if vf_msg else '验证未通过'}")
            return False
    rain_risk = False
    rain_msg = ""
    for _ in range(3):
        try:
            ev_payload={"silk_id":int(api.teemo),"city_code":city_code,"date":str(get_china_date()),"app_id":20}
            ev_resp=api._make_rpc_request("SilkwormLottery","SilkwormLotteryMobile.GetRedPackRainEventsByDate",ev_payload,extra_headers={"x-City":str(city_code)})
            ev_js=ev_resp.json();events=ev_js.get("events",[])
            if not events: rain_msg="无场次(跳过)";break
            target_evt=events[0];event_id=target_evt.get("event_id")
            join_payload={"silk_id":int(api.teemo),"city_code":city_code,"event_id":event_id,"app_id":20}
            join_resp=api._make_rpc_request("SilkwormLottery","SilkwormLotteryMobile.JoinRedPackRainEvent",join_payload,extra_headers={"x-City":str(city_code)})
            join_js=join_resp.json()
            code=join_js.get("status",{}).get("code")
            if code == 200001:
                rain_risk = True
                rain_msg = join_js.get("status",{}).get("msg")
            else:
                rain_msg = "正常"
            break
        except Exception as e: rain_msg=str(e);time.sleep(1) 
    if rain_risk:
        sender.reply(f"❶ 红包雨检测: {rain_msg}")
        if not _execute_unlock_flow(api):
            return
    else:
        sender.reply(f"❶ 红包雨检测: {rain_msg}")
    lottery_risk = False
    lottery_msg = ""
    for _ in range(3):
        try:
            lot_payload = {"silk_id": int(api.teemo), "prize_type": 1, "app_id": 20}
            lot_resp = api._make_rpc_request("SilkwormLottery", "SilkwormLotteryMobile.Lottery", lot_payload)
            lot_js = lot_resp.json()
            code = lot_js.get("status", {}).get("code")
            if code == 200001:
                lottery_risk = True
                lottery_msg = lot_js.get("status", {}).get("msg")
            else:
                lottery_msg = "正常"
            break
        except Exception as e: lottery_msg=str(e);time.sleep(1)
    if lottery_risk:
        sender.reply(f"❷ 抽奖检测: {lottery_msg}")
        if not _execute_unlock_flow(api):
            return
    else:
        sender.reply(f"❷ 抽奖检测: {lottery_msg}")
    sender.reply(f"=====解限完成=====\n🤪 账号: {nm}\n✅ 状态: 所有业务节点检测通过\n==================")
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
def get_china_date():
    return get_china_time().date()
def get_china_timestamp():
    return get_china_time().timestamp()
try:
    from concurrent.futures import ThreadPoolExecutor, as_completed
except:
    ThreadPoolExecutor = None
senderID = middleware.getSenderID()
sender = middleware.Sender(senderID)
userid = sender.getUserID()
imtype = sender.getImtype()
today = get_china_date()
bingfa_str = middleware.bucketGet('yuhua_xcbwc', 'bingfa') or ''
try:
    MAX_WORKERS = int(bingfa_str)
    if MAX_WORKERS < 1: MAX_WORKERS = 5
except: MAX_WORKERS = 5
_temp_ip_usage = {}
_temp_used_ips = set()
_proxy_lock = threading.Lock()
status_management_lock = threading.Lock()
def get_ip_limit():
    try: return int(middleware.bucketGet('yuhua_xcbwc', 'ip') or '0')
    except: return 0
def is_monitor_enabled(): return (middleware.bucketGet('yuhua_xcbwc', 'jiankong') or 'false').lower() == 'true'
def extract_ip_from_proxy(proxy_url):
    try:
        if '://' in proxy_url: proxy_url = proxy_url.split('://', 1)[1]
        if '@' in proxy_url: proxy_url = proxy_url.split('@', 1)[1]
        return proxy_url.split(':')[0]
    except: return None
def clear_temp_ip_records():
    global _temp_ip_usage, _temp_used_ips, _proxy_lock
    with _proxy_lock: _temp_ip_usage.clear(); _temp_used_ips.clear()
def clear_session_pool():
    global _session_pool
    try:
        for session in _session_pool.values():
            try: session.close()
            except Exception: pass
        _session_pool.clear()
    except Exception: pass
def cleanup_resources(): clear_temp_ip_records(); clear_session_pool()
def get_user_input(prompt, timeout=60000):
    if prompt:
        sender.reply(prompt)
    user_input = sender.input(timeout, 0, False)
    if not user_input:
        sender.reply("❌ 输入超时")
        return None
    if user_input.strip().lower() == 'q':
        sender.reply("✅ 已退出操作")
        return None
    return user_input.strip()
def get_proxies():
    global _temp_ip_usage, _temp_used_ips, _proxy_lock, _ip_cache_pool, _ip_cache_lock
    proxy_status = middleware.bucketGet('yuhua_xcbwc', 'status') or '0'
    proxy_addr = middleware.bucketGet('yuhua_xcbwc', 'proxy') or ''
    if proxy_status not in ['0', '1', '2'] or proxy_status == '0' or not proxy_addr.strip(): return None
    proxy_addr = proxy_addr.strip()
    if proxy_status == '1':
        if not (proxy_addr.startswith('http://') or proxy_addr.startswith('https://')): return None
        return {"http": proxy_addr, "https": proxy_addr}
    if proxy_status == '2':
        ip_limit = get_ip_limit()
        for _ in range(20):
            candidate_ip = None
            with _ip_cache_lock:
                if _ip_cache_pool: candidate_ip = _ip_cache_pool.pop(0)
            if not candidate_ip:
                with _ip_cache_lock:
                    if _ip_cache_pool: candidate_ip = _ip_cache_pool.pop(0)
                    else:
                        try:
                            r = requests.get(proxy_addr, timeout=5)
                            if r.status_code == 200:
                                ips = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+', r.text)
                                if ips: _ip_cache_pool.extend(ips); candidate_ip = _ip_cache_pool.pop(0)
                        except Exception: pass
            if candidate_ip:
                ip_val = candidate_ip.split(':')[0]
                if ip_limit > 0:
                    should_skip = False
                    with _proxy_lock:
                        if ip_val in _temp_used_ips: should_skip = True
                        elif _temp_ip_usage.get(ip_val, 0) >= ip_limit: _temp_used_ips.add(ip_val); should_skip = True
                        else: _temp_ip_usage[ip_val] = _temp_ip_usage.get(ip_val, 0) + 1
                    if should_skip: continue
                return {"http": f"http://{candidate_ip}", "https": f"http://{candidate_ip}"}
            time.sleep(random.uniform(0.5, 1.0))
    return None
_session_pool: Dict[str, requests.Session] = {}
def _get_session_by_proxy(proxies: dict | None):
    proxy_key = json.dumps(proxies, sort_keys=True) if proxies else "direct"
    if proxy_key not in _session_pool or getattr(_session_pool[proxy_key], "_closed", False):
        sess = requests.Session()
        if proxies: sess.proxies.update(proxies)
        _session_pool[proxy_key] = sess
    return _session_pool[proxy_key]
def parse_error_reason(error_msg: str) -> str:
    if "CK失效" in error_msg: return "CK失效"
    elif "IP已被风控" in error_msg: return "IP已被风控"
    elif "网络异常" in error_msg: return "网络异常"
    elif "连接超时" in error_msg or "timeout" in error_msg.lower(): return "网络超时"
    elif "连接失败" in error_msg or "connection" in error_msg.lower(): return "连接失败"
    else: return f"请求异常: {error_msg}"
def format_result(account_name, title, result, success=True):
    status = "成功" if success else "失败"
    return f"====={title}{status}=====\n🤪 账号: {account_name}\n💫 结果: {result}\n=================="
def check_account_valid(acid):
    if not check_auth_valid(acid): return False, "未授权或授权已过期"
    ck = middleware.bucketGet('yuhua_xcbwc_token', acid)
    if not ck: return False, "CK不存在"
    return True, ck
def safe_request(method, url, max_retries=10, backoff_factor=1, **kwargs):
    global _temp_used_ips, _proxy_lock
    current_proxies = kwargs.get("proxies", get_proxies())
    proxy_status = middleware.bucketGet('yuhua_xcbwc', 'status') or '0'
    consecutive_403_count = 0
    for attempt in range(max_retries):
        if proxy_status!='0' and not current_proxies:
            current_proxies=get_proxies()
            if not current_proxies:
                if attempt<max_retries-1:time.sleep(random.uniform(0.2,0.5));continue
                else:raise Exception("代理获取失败，为防止多号同IP风控，已拦截直连请求")
        try:
            session = _get_session_by_proxy(current_proxies)
            kwargs["proxies"] = current_proxies
            resp = session.request(method, url, **kwargs)
            if DEBUG_LOG: printf(f"[{attempt+1}/{max_retries}] >>> {resp.request.method} {resp.request.url}\n[ReqHead] {resp.request.headers}\n[ReqBody] {resp.request.body}\n<<< {resp.status_code}\n[RspHead] {resp.headers}\n[RspBody] {resp.text}", "DEBUG")
            if resp.status_code == 401: raise Exception("CK失效")
            if resp.status_code == 403:
                consecutive_403_count += 1
                if consecutive_403_count >= 2 and proxy_status == '2' and current_proxies:
                    ip = extract_ip_from_proxy(current_proxies.get("http", ""))
                    if ip:
                        with _proxy_lock: _temp_used_ips.add(ip)
                    raise requests.exceptions.RequestException("IP已被风控")
                elif attempt < max_retries - 1:
                    time.sleep(random.uniform(0.01, 0.05))
                    current_proxies = get_proxies()
                    continue
                else: raise requests.exceptions.RequestException("IP已被风控")
            else: consecutive_403_count = 0
            resp.raise_for_status()
            if "application/json" in resp.headers.get("content-type", ""):
                try:
                    json_data = resp.json()
                    status_code = json_data.get("status", {}).get("code")
                    status_msg = json_data.get("status", {}).get("msg", "")
                    if status_code in [-1, 1001] or "token" in status_msg.lower() or "登录" in status_msg: raise Exception("CK失效")
                except (ValueError, KeyError): pass
            return resp
        except Exception as e:
            if DEBUG_LOG: printf(f"[{attempt+1}/{max_retries}] [Err] {str(e)}", "ERROR")
            if "CK失效" in str(e): raise e
            if "代理获取失败" in str(e) or "已拦截" in str(e): raise e
            if "IP已被风控" in str(e) and proxy_status == '2' and current_proxies:
                ip = extract_ip_from_proxy(current_proxies.get("http", ""))
                if ip:
                    with _proxy_lock: _temp_used_ips.add(ip)
            if attempt == max_retries - 1:
                error_msg = str(e).lower()
                if "ip已被风控" in error_msg or (consecutive_403_count >= 2 and "403" in error_msg): raise Exception("IP已被风控")
                elif "403" in error_msg: raise Exception("IP已被风控")
                raise e
            else:
                time.sleep(random.uniform(0.01, 0.05) * (attempt + 1) * backoff_factor)
                current_proxies = get_proxies()
    return None
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
def push_msg(uid, msg):
    msg = msg.replace("红包", "封紅")
    time.sleep(random.uniform(0.01, 0.05)); parts = split_long_message(msg)
    for i, part in enumerate(parts):
        if i > 0: time.sleep(random.uniform(0.05, 0.1))
        platforms = ["qq", "qb", "wx", "gw", "sb", "wb", "tg", "tb", "qx", "xy", "ip"]
        for p in platforms:
            middleware.push(p, '', uid, '', part)
def safe_reply(msg):
    msg = msg.replace("红包", "封紅")
    parts = split_long_message(msg)
    for i, part in enumerate(parts):
        if i > 0: time.sleep(random.uniform(0.02, 0.05))
        sender.reply(part)
def get_accounts(uid):
    data = middleware.bucketGet('yuhua_xcbwc_user', uid)
    if not data: return []
    try: return json.loads(data)
    except: return []
def set_accounts(uid, arr): middleware.bucketSet('yuhua_xcbwc_user', uid, json.dumps(arr))
def add_account(uid, acc_id):
    arr = get_accounts(uid)
    if acc_id not in arr: arr.append(acc_id); set_accounts(uid, arr)
def remove_account(uid, acc_id):
    arr = get_accounts(uid)
    if acc_id in arr:
        arr.remove(acc_id)
        set_accounts(uid, arr)
        for bucket in['yuhua_xcbwc_token', 'yuhua_xcbwc_teemo', 'yuhua_xcbwc_remark', 'yuhua_xcbwc_auth', 'yuhua_xcbwc_jiankong_weizhi', 'yuhua_xcbwc_jiankong_storeid', 'yuhua_xcbwc_jiankong_todayStoreId', 'yuhua_xcbwc_jiankong_status', 'yuhua_xcbwc_grabbed_store_today', 'yuhua_xcbwc_overlimit_store_today', 'yuhua_xcbwc_repeat_store_today']:
            try:
                middleware.bucketDel(bucket, acc_id)
            except Exception:
                pass
        return True
    return False
def check_auth_valid(acc_id):
    ad = middleware.bucketGet('yuhua_xcbwc_auth', acc_id)
    if not ad: return False
    try: return datetime.strptime(ad, "%Y-%m-%d").date() >= today
    except: return False
def calc_auth_time(old_time, months):
    nowd = get_china_date(); base = nowd
    if old_time:
        try:
            dt = datetime.strptime(old_time, "%Y-%m-%d").date()
            if dt > nowd: base = dt
        except: pass
    return (base + timedelta(days=30*months)).strftime("%Y-%m-%d")
def find_by_teemo(teemo_val):
    all_u = middleware.bucketAllKeys('yuhua_xcbwc_user')
    for u in all_u:
        accs = get_accounts(u)
        for a in accs:
            ck = middleware.bucketGet('yuhua_xcbwc_token', a)
            if ck:
                arr = ck.split('#')
                if len(arr) == 3 and arr[1] == teemo_val: return (u, a)
    return None
_silk_cache = {}
def _md5(s: str) -> str:
    return hashlib.md5(s.encode('utf-8')).hexdigest()
def generate_xc_headers(servername, methodname, teemo="0", vayne="0", sivir="", extra=None, device_key=None, city_code="440304"):
    ru = uuid.uuid4().hex
    teemo_str = str(teemo)
    suffix_len = max(0, 16 - 4 - len(teemo_str))
    x_nami = f"{ru[:4]}{teemo_str}{ru[4:4 + suffix_len]}"
    x_garen = str(int(time.time() * 1000))
    sig = hashlib.md5((hashlib.md5(f"{servername}.{methodname}".lower().encode('utf-8')).hexdigest() + x_garen + x_nami).encode('utf-8')).hexdigest()
    dev = get_device_data(device_key or teemo)
    headers = {
        "Host": "gw.xiaocantech.com", "Connection": "keep-alive", "servername": servername,
        "methodname": methodname, "version": "3.12.5.70", "X-Version": "3.12.5.70",
        "X-Nami": x_nami, "X-Garen": x_garen, "X-Ashe": sig, "x-Annie": "XC",
        "X-Platform": "mini", "x-Teemo": teemo_str, "x-Vayne": vayne, "x-Sivir": sivir,
        "X-Model": dev['model'], "x-City": extra.get("x-City", city_code) if extra else city_code,
        "env": "", "appid": extra.get("appidNum", "20") if extra else "20",
        "content-type": "application/json", "charset": "utf-8",
        "Referer": "https://servicewechat.com/wx52ae177248081591/666/page-frame.html",
        "User-Agent": dev['ua'], "Accept-Encoding": "gzip, deflate, br", "Accept-Language": "zh-CN,zh;q=0.9"
    }
    if vayne != "0": headers["userid"] = vayne
    if extra: headers.update(extra)
    return headers
def _build_headers(servername: str, methodname: str, teemo: str = "0", extra: dict | None = None, device_key: str = None) -> dict:
    return generate_xc_headers(servername, methodname, teemo=teemo, extra=extra, device_key=device_key)
def _anonymous_query(lat, lng, city_code, offset=0, number=20, device_key=None):
    headers = _build_headers("SilkwormRec", "RecService.GetStorePromotionList", "0", {"x-Vayne": "0", "x-City": str(city_code)}, device_key=device_key)
    payload = {"latitude": lat, "longitude": lng, "promotion_sort": 1, "store_type": 0, "offset": offset, "number": number, "silk_id": 0, "promotion_filter": 0, "promotion_category": 0, "city_code": int(city_code), "store_category": 0, "store_platform": 0, "app_id": 20}
    try:
        resp = safe_request("POST", "https://gw.xiaocantech.com/rpc", headers=headers, json=payload, timeout=10)
        js = resp.json()
        if js.get("status", {}).get("code") == 0: return True, js.get("promotion_list", [])
        return False, js.get("status", {}).get("msg", "未知API错误")
    except Exception as e: 
        return False, str(e)
class BaseApiClient:
    def __init__(self, cookie_str):
        parts = cookie_str.split('#')
        if len(parts) < 3: raise ValueError("CK不合法")
        self.vayne = parts[0]; self.teemo = parts[1]; self.sivir = parts[2]
        self.url = "https://gw.xiaocantech.com/rpc"
        self.sess = requests.Session()
        self.proxies = get_proxies()
        self.dev = get_device_data(self.teemo)
        if self.proxies: self.sess.proxies.update(self.proxies)
        self.city_code = "440304"
        self.lat = None
        self.lng = None        
        try:
            loc_json = middleware.bucketGet('yuhua_xcbwc_jiankong_weizhi', self.teemo)
            if loc_json:
                loc_data = json.loads(loc_json)
                self.city_code = str(loc_data.get("city_code", "440304"))
                self.lat = loc_data.get("latitude")
                self.lng = loc_data.get("longitude")
        except Exception:
            pass
    def _md5(self, s: str) -> str: return hashlib.md5(s.encode('utf-8')).hexdigest()
    def _prepare_headers(self, servername: str, methodname: str, extra_headers: dict = None) -> dict:
            return generate_xc_headers(servername, methodname, self.teemo, self.vayne, self.sivir, extra_headers, self.teemo, self.city_code)
    def _make_rpc_request(self, servername: str, methodname: str, payload: dict, extra_headers: dict = None):
        headers = self._prepare_headers(servername, methodname, extra_headers)
        for i in range(20):
            try:
                r = self.sess.post(self.url, headers=headers, json=payload, timeout=12)
                if DEBUG_LOG: printf(f"[{i+1}/20] >>> {r.request.method} {r.request.url}\n[ReqHead] {r.request.headers}\n[ReqBody] {r.request.body}\n<<< {r.status_code}\n[RspHead] {r.headers}\n[RspBody] {r.text}", "DEBUG")
                if r.status_code == 401: raise Exception("CK失效")
                if r.status_code == 403:
                    if i == 19: raise Exception("IP已被风控")
                    self.proxies = get_proxies()
                    if self.proxies: self.sess.proxies.update(self.proxies)
                    time.sleep(0.1); continue
                return r
            except Exception as e:
                if DEBUG_LOG: printf(f"[{i+1}/20] [Err] {str(e)}", "ERROR")
                if i == 19: raise e
                self.proxies = get_proxies()
                if self.proxies: self.sess.proxies.update(self.proxies)
                time.sleep(0.05)
class yuhua(BaseApiClient):
    def get_silk(self, force_refresh=False):
        global _silk_cache
        cache_key = f"{self.vayne}_{self.teemo}_{self.sivir}"
        if not force_refresh and cache_key in _silk_cache: return _silk_cache[cache_key]
        time.sleep(random.uniform(1.0, 2.0))
        payload = {"silk_id": int(self.teemo), "if_need_subscribe": True, "inviter_silk_id": 0, "up": {"rcp": 1, "rc": 0, "dm":self.dev['dm'],"re_ch":""}, "app_id": 20}
        try:
            r = self._make_rpc_request("Silkworm", "SilkwormService.GetClientUserInfo", payload)
            js = r.json()
            if js.get("status", {}).get("code") == 0 and "user_info" in js:
                _silk_cache[cache_key] = js["user_info"]
                return js["user_info"]
            msg = js.get("status", {}).get("msg", "服务器返回错误")
            raise Exception(f"CK失效，服务器响应：{msg}")
        except Exception as e: raise e
    def get_lottery_info(self):
            try:
                self._make_rpc_request("SilkwormLottery", "SilkwormLotteryMobile.LotteryInfo", {"silk_id": int(self.teemo), "app_id": 20})
                time.sleep(random.uniform(0.1, 0.4))
                self._make_rpc_request("SilkwormLottery", "SilkwormLotteryMobile.GetLotteryProgress", {"silk_id": int(self.teemo), "app_id": 20})
            except:
                pass
    def sign_in(self):
        time.sleep(random.uniform(1.0, 3.0))
        payload = {"silk_id": int(self.teemo), "app_id": 20}
        try:
            resp = self._make_rpc_request("ActivityTask", "ActivityTaskMobileService.SignIn", payload).json()
            code = resp.get("status", {}).get("code")
            if code == 0:
                self.get_lottery_info()
                return f"会员签到: 获得{resp.get('point', 0)}"
            elif code == 200001:
                return "会员签到: 触发风控"
            return f"会员签到: {resp.get('status', {}).get('msg')}"
        except Exception as e: return f"会员签到: {str(e)}"
    def task(self, t):
        time.sleep(random.uniform(3.0, 5.0))
        payload = {"silk_id": int(self.teemo), "type": t, "app_id": 20}
        try:
            resp = self._make_rpc_request("SilkwormLottery", "SilkwormLotteryMobile.AddLotteryTimes", payload).json()
            if resp["status"]["code"] == 0:
                self.get_lottery_info()
                return f"任务[{t}]完成, 抽奖次数+1"
            return f"任务[{t}]失败, {resp['status']['msg']}"
        except Exception as e: return f"任务[{t}]异常: {str(e)}"
    def lottery(self):
        time.sleep(random.uniform(3.0, 6.0))
        payload = {"silk_id": int(self.teemo), "prize_type": 1, "app_id": 20}
        try:
            rr = self._make_rpc_request("SilkwormLottery", "SilkwormLotteryMobile.Lottery", payload).json()
            if rr["status"]["code"] == 0:
                self.get_lottery_info()
                return f"抽奖成功, 获得[{rr['prize']['name']}]"
            return f"抽奖状态: {rr['status']['msg']}"
        except Exception as e: return f"抽奖异常: {str(e)}"
    def receive_cumulative_reward(self):
        logs = []
        for stp in [1, 2]:
            time.sleep(random.uniform(2.0, 3.0))
            payload = {"silk_id": int(self.teemo), "step": stp, "app_id": 20}
            try:
                resp = self._make_rpc_request("SilkwormLottery", "SilkwormLotteryMobile.ReceiveExtraLottery", payload).json()
                if resp["status"]["code"] == 0: logs.append(f"奖励状态: 领取奖励[{stp}]成功, 获得[{resp['prize']['name']}]")
                else: logs.append(f"奖励状态: 领取奖励[{stp}]失败, {resp['status']['msg']}")
            except Exception as e: logs.append(f"奖励状态: 领取奖励[{stp}]异常: {str(e)}")
        return "\n".join(logs)
    def get_all_cards(self):
        time.sleep(random.uniform(1.0, 1.5))
        offset, total_dict = 0, {}
        while True:
            payload = {"silk_id": int(self.teemo), "status": 0, "offset": offset, "number": 10, "app_id": 20}
            try:
                r = self._make_rpc_request("SilkwormCard", "SilkwormCardService.GetUserCardList", payload).json()
                if r["status"]["code"] != 0: return f"失败, {r['status']['msg']}"
                lst = r.get("list", [])
                if not lst: break
                for item in lst: total_dict[item["card"]["name"]] = total_dict.get(item["card"]["name"], 0) + 1
                if len(lst) < 10: break
                offset += 10
                time.sleep(random.uniform(1.0, 1.5))
            except Exception as e: return f"异常, {str(e)}"
        if not total_dict: return "暂无"
        return ", ".join([f"{k}x{v}" for k, v in total_dict.items()])
    def get_all_redpacks(self):
        time.sleep(random.uniform(1.0, 1.5))
        page, results = 1, []
        while True:
            payload = {"silk_id": int(self.teemo), "page": page, "page_size": 10, "app_id": 20}
            try:
                resp = self._make_rpc_request("RedPackService", "RedPackService.GetAppRedPackList", payload)
                if not resp or resp.status_code != 200: return "无"
                js = resp.json()
                if js["status"]["code"] != 0: return "暂无"
                items = js.get("unused_items", [])
                if not items: break
                for item in items:
                    if item.get("user_red_pack_status", 0) == 1: results.append(f"{item.get('name', '未知封紅')}{item.get('value_num', 0)/100.0:.2f}")
                if len(items) < 10: break
                page += 1
                time.sleep(random.uniform(1.0, 1.5))
            except Exception: return "暂无"
        return ", ".join(results) or "暂无"
    def run_all(self):
        logs = []
        logs.append(self.sign_in())
        for t in [1, 2, 8, 9, 10, 11]:
            logs.append(self.task(t))
        logs.append(self.ad_task(6, 2))
        logs.append(self.ad_task(7, 4))
        while True:
            ret = self.lottery()
            logs.append(ret)
            if "抽奖成功" in ret:
                time.sleep(random.uniform(2.0, 4.0)) 
            else:
                break
        logs.append(self.receive_cumulative_reward())    
        return "\n".join(logs)
    def ad_task(self, task_type, bus_type):
        import hmac, base64, string
        time.sleep(random.uniform(3.0, 5.0))
        timestamp = int(time.time())
        nonce = ''.join(random.choice(string.digits) for _ in range(6))
        sign_text = f"silk_id={int(self.teemo)}&timestamp={timestamp}&nonce={nonce}&bus_type={int(bus_type)}"
        sign_key = "lcjkbqadfrzsewxy"
        signature = hmac.new(sign_key.encode(), sign_text.encode(), hashlib.sha256).digest()
        sign = base64.b64encode(signature).decode()
        payload = {"silk_id": int(self.teemo), "timestamp": timestamp, "nonce": nonce, "bus_type": int(bus_type), "sign": sign, "task_type": task_type, "app_id": 20}
        try:
            resp = self._make_rpc_request("SilkwormLottery", "SilkwormLotteryMobile.OnAdViewed", payload).json()
            if resp["status"]["code"] == 0:
                self.get_lottery_info()
                return f"任务[{task_type}]完成, 抽奖次数+1"
            return f"任务[{task_type}]失败, {resp['status']['msg']}"
        except Exception as e: return f"任务[{task_type}]异常: {str(e)}"
    def _withdraw_common(self, acid, channel):
        nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
        user_info = self.get_silk()
        if user_info is None: return format_result(nm, "提现", "CK失效", False)
        mon = user_info.get("silk", 0) / 100.0
        if mon < 1: return format_result(nm, "提现", "蚕豆不足, 当前没有足够蚕豆进行提现", False)
        payload = {"silk_id": int(self.teemo), "silk": int(mon * 100), "channel": channel, "app_id": 20}
        try:
            js = self._make_rpc_request("Silkworm", "SilkwormService.ClientWithdraw", payload).json()
            if js["status"]["code"] == 0: return format_result(nm, "提现", f"发起提现{mon:.2f}元, 请及时查验", True)
            return format_result(nm, "提现", js['status']['msg'], False)
        except Exception as e: return format_result(nm, "提现", str(e), False)
    def withdraw_all(self, acid): return self._withdraw_common(acid, 0)
    def withdrawzfb_all(self, acid): return self._withdraw_common(acid, 1)
    def fetch_hb_events(self, city_code):
        payload = {"silk_id": int(self.teemo), "city_code": int(city_code), "date": str(get_china_date()), "app_id": 20}
        try:
            rsp = self._make_rpc_request("SilkwormLottery", "SilkwormLotteryMobile.GetRedPackRainEventsByDate", payload, extra_headers={"x-City": str(city_code)}).json()
            return rsp.get("events") if rsp.get("status", {}).get("code") == 0 else None
        except: return None
    def join_red_pack_rain_event(self, event_id, city_code):
        payload = {"silk_id": int(self.teemo), "city_code": int(city_code), "event_id": event_id, "app_id": 20}
        try:
            r = self._make_rpc_request("SilkwormLottery", "SilkwormLotteryMobile.JoinRedPackRainEvent", payload, extra_headers={"x-City": str(city_code)})
            js = r.json()
            c = js["status"]["code"]
            if c == 0:
                if js.get("success", False): return True, "报名成功", None
                return False, js.get("failed_reason", "报名失败"), None
            elif c == 200001: return False, js["status"].get("msg", "风控验证"), js.get("verify_method", 0)
            return False, js["status"].get("msg", "未知错误"), None
        except Exception as e: return False, str(e), None
    def do_red_pack_rain_grab_num(self, event_id, city_code):
        payload = {"silk_id": int(self.teemo), "event_id": event_id, "click_num": 18, "app_id": 20}
        try:
            resp = self._make_rpc_request("SilkwormLottery", "SilkwormLotteryMobile.RedPackRainGrabNum", payload, extra_headers={"x-City": str(city_code)}).json()
            if resp["status"]["code"] != 0: return False, resp["status"].get("msg", "抽奖失败未知原因")
            items = resp.get("items", [])
            if not items: return False, "无封紅信息"
            it = items[0]
            val_yuan = it.get("prize_value", 0) / 100.0
            return True, f"抽奖成功, 获得[{it.get('name', '未知封紅')}{val_yuan:.2f}]"
        except Exception as e: return False, f"异常:{str(e)}"
class YuhuaClient(BaseApiClient):
    def get_promotion_order_list(self, offset=0, number=10, order_status=0):
        time.sleep(random.uniform(1.0, 2.0))
        payload = {"silk_id": int(self.teemo), "order_status": order_status, "offset": offset, "number": number, "app_id": 20}
        try:
            js = self._make_rpc_request("Silkworm", "SilkwormService.GetPromotionOrderList", payload).json()
            if js.get("status",{}).get("code") != 0:
                return False, js.get("status",{}).get("msg","未知错误"), None
            return True, "ok", js.get("order_list", [])
        except Exception as e: return False, str(e), None
    def grab_promotion(self, pid, pf, city_code, lat, lng):
        time.sleep(random.uniform(0.1, 0.3))
        if not lat or not lng: return False, "坐标无效"
        payload = {"silk_id": int(self.teemo), "promotion_id": pid, "store_platform": pf, "if_advance_order": False, "if_pre_order": False, "latitude": float(lat), "longitude": float(lng), "city_code": int(city_code), "app_id": 20}
        try:
            js = self._make_rpc_request("Silkworm", "SilkwormService.GrabPromotionQuota", payload, extra_headers={"x-City": str(city_code)}).json()
            if js["status"]["code"] == 0: return True, "抢单成功"
            return False, js["status"].get("msg", "未知错误")
        except Exception as e: return False, str(e)
    def cancel_promotion_order(self, promotion_order_id):
        time.sleep(random.uniform(1.0, 2.0))
        payload = {"silk_id": int(self.teemo), "promotion_order_id": promotion_order_id, "app_id": 20}
        try:
            js = self._make_rpc_request("Silkworm", "SilkwormService.CancelPromotionQuota", payload).json()
            if js.get("status",{}).get("code", -1) == 0: return True, "订单取消成功"
            return False, js.get("status",{}).get("msg","取消失败，未知原因")
        except Exception as e: return False, str(e)
def determine_platform(promo):
    if promo.get("tp_promotion", {}).get("tp_status", 0) == 1: return 3
    if promo.get("meituan_status", 0) == 1: return 1
    if promo.get("eleme_status", 0) == 1 or promo.get("meituan_status", 0) == 0: return 2
    return 0
def extract_promo_data(p):
    pf = determine_platform(p)
    if pf == 1: return pf, p.get("meituan_left_number", 0), p.get("meituan_order_money", 0), p.get("meituan_user_rebate", 0)
    elif pf == 2: return pf, p.get("eleme_left_number", 0), p.get("eleme_order_money", 0), p.get("eleme_user_rebate", 0)
    tp = p.get("tp_promotion", {})
    return pf, tp.get("tp_left_number", 0), tp.get("tp_order_money", 0), tp.get("tp_user_rebate", 0)
def format_promotion_list(promotions, reduce_left_num=False):
    if not promotions: return "未发现任何活动"
    show_img = (middleware.bucketGet('yuhua_xcbwc', 'img') or 'false') == 'true'
    grouped = {}
    for item in promotions:
        pf, left, money, rebate = extract_promo_data(item)
        store_id = item["store"]["store_id"]
        key = (store_id, pf)
        if key not in grouped: grouped[key] = {"icon": item["store"].get("icon", ""), "store_id": store_id, "store_name": item["store"].get("name", ""), "platform": "美团" if pf == 1 else ("淘宝闪购" if pf == 2 else "京东"), "distance": item.get("distance", 0), "promotions": []}
        grouped[key]["promotions"].append((item, left, money, rebate))
    lines =[]
    for (_, pf), info in grouped.items():
        dist_km = round(info["distance"] / 1000, 1)
        if show_img and info.get("icon"): lines.append(f"[CQ:image,file={info['icon']}]")
        lines += [f"店铺标识:  {info['store_id']}", f"店铺名称:  {info['store_name']}", f"店铺平台:  {info['platform']}", f"店铺距离:  {dist_km}km"]
        for pm, left, money, rebate in info["promotions"]:
            st_time, ed_time = f"{pm['start_time_hour']:02d}:{pm['start_time_minute']:02d}", f"{pm['end_time_hour']:02d}:{pm['end_time_minute']:02d}"
            condv = pm.get("rebate_condition", 0)
            conds = "无需评价" if condv == 99 else ("用餐反馈" if condv == 2 else "")
            if reduce_left_num and left > 0: left -= 1
            money_str = f"满{money // 100}返{rebate // 100}" if money > 0 else f"每单返{rebate // 100}"
            lines +=[f"活动标识:  {pm.get('promotion_id', '未知ID')}", f"抢单时间:  {st_time}-{ed_time}", f"返现要求:  {money_str} {conds}".strip(), f"剩余名额:  {left}"]
        lines.append("")
    return "\n".join(lines).strip()
def pick_best_promotion_strict(promotions):
    now_val = get_china_time().hour * 60 + get_china_time().minute
    candidates =[]
    for p in promotions:
        pf, left, money, rebate = extract_promo_data(p)
        if left <= 0 or not (p["start_time_hour"] * 60 + p["start_time_minute"] <= now_val <= p["end_time_hour"] * 60 + p["end_time_minute"]): continue
        candidates.append({"promo": p, "left": left, "cond": 1 if p.get("rebate_condition", 0) == 99 else 0, "rebate": rebate, "money": money, "net": rebate - money})
    if not candidates: return None
    candidates.sort(key=lambda x: (-x["net"], -x["cond"], -x["rebate"], x["money"], -x["left"]))
    return candidates[0]["promo"]
def monitor_task():
    if not is_monitor_enabled(): return
    loc_groups = {}
    for u in middleware.bucketAllKeys('yuhua_xcbwc_user'):
        for acid in get_accounts(u):
            if (middleware.bucketGet('yuhua_xcbwc_jiankong_status', acid) or 'off') != 'on': continue
            if not check_auth_valid(acid): continue
            ck = middleware.bucketGet('yuhua_xcbwc_token', acid)
            if not ck: continue
            loc_str = middleware.bucketGet('yuhua_xcbwc_jiankong_weizhi', acid)
            if not loc_str: continue
            try:
                ld = json.loads(loc_str)
                k = f"{ld['city_code']}_{float(ld['latitude']):.2f}_{float(ld['longitude']):.2f}"
                if k not in loc_groups: loc_groups[k] = {"lat": float(ld['latitude']), "lng": float(ld['longitude']), "city": int(ld['city_code']), "accs": []}
                loc_groups[k]["accs"].append((u, acid, ck))
            except: continue
    if not loc_groups: return
    if not ThreadPoolExecutor:
        for g in loc_groups.values(): process_location_group(g)
    else:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
            futs = [exe.submit(process_location_group, g) for g in loc_groups.values()]
            for f in as_completed(futs, timeout=600):
                try: f.result(timeout=120)
                except: pass
def process_location_group(group):
    all_promos = []
    offset = 0
    simulated_acid = group["accs"][0][1] if group["accs"] else None
    while True:
        ok, batch = _anonymous_query(group["lat"], group["lng"], group["city"], offset, 20, device_key=simulated_acid)
        if not ok: break
        if not batch: break        
        all_promos.extend(batch)
        if len(batch) < 20: break         
        offset += 20
        time.sleep(random.uniform(0.5, 1.0))        
    if not all_promos: return
    promos = all_promos
    STORE_BUCKET = {1: 'yuhua_xcbwc_store_mt_info', 2: 'yuhua_xcbwc_store_elm_info', 3: 'yuhua_xcbwc_store_jd_info'}
    MON_BUCKET = {1: 'yuhua_xcbwc_jiankong_store_mt', 2: 'yuhua_xcbwc_jiankong_store_elm', 3: 'yuhua_xcbwc_jiankong_store_jd'}
    current_date = str(get_china_date())
    for p in promos:
        pf = determine_platform(p)
        if pf in STORE_BUCKET: middleware.bucketSet(STORE_BUCKET[pf], str(p["store"]["store_id"]), json.dumps({"store_name": p["store"].get("name", "")}, ensure_ascii=False))
    for u, acid, ck in group["accs"]:
        try:
            mon_stores = {pf: set(json.loads(middleware.bucketGet(b, acid) or "[]")) for pf, b in MON_BUCKET.items()}
            def _get_today_data(bucket_name):
                default_struct = {"date": current_date, "store_ids": []}
                try:
                    raw = middleware.bucketGet(bucket_name, acid)
                    if not raw: return set(), default_struct
                    d = json.loads(raw)
                    if d.get("date") != current_date: return set(), default_struct
                    return set(map(str, d.get("store_ids", []))), d
                except:
                    return set(), default_struct
            grabbed, gj = _get_today_data('yuhua_xcbwc_grabbed_store_today')
            overlimit, ol = _get_today_data('yuhua_xcbwc_overlimit_store_today')
            repeat, rp = _get_today_data('yuhua_xcbwc_repeat_store_today')           
            push_st = middleware.bucketGet('yuhua_xcbwc_jiankong_push', acid) or 'f'
            nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
            notified_set, notified_data = _get_today_data('yuhua_xcbwc_jiankong_todayStoreId')
            valid_promos = [p for p in promos if p.get("distance", 999999) <= 5000]
            new_ids = {str(p["store"]["store_id"]) for p in valid_promos} - notified_set            
            if new_ids:
                notified_set.update(new_ids)
                notified_data["store_ids"] = list(notified_set)
                notified_data["date"] = current_date
                middleware.bucketSet('yuhua_xcbwc_jiankong_todayStoreId', acid, json.dumps(notified_data, ensure_ascii=False))
                if push_st == 't':
                    target_promos = [p for p in valid_promos if str(p['store']['store_id']) in new_ids]
                    if target_promos:
                        try: push_msg(u, f"=====新店铺提醒=====\n🤪 账号: {nm}\n💫 提醒: 监控到新店铺活动\n------------------\n{format_promotion_list(target_promos)}\n==================")
                        except: pass
            store_map = {}
            for p in promos:
                sid, pf = str(p["store"]["store_id"]), determine_platform(p)
                if sid in mon_stores.get(pf, set()) and sid not in grabbed and sid not in overlimit and sid not in repeat: 
                    store_map.setdefault((sid, pf), []).append(p)
            
            now_val = get_china_time().hour * 60 + get_china_time().minute
            
            for (sid, pf), plist in store_map.items():
                if not any(p["start_time_hour"] * 60 + p["start_time_minute"] <= now_val <= p["end_time_hour"] * 60 + p["end_time_minute"] for p in plist): continue
                bestp = pick_best_promotion_strict(plist)
                if not bestp: continue
                cli = YuhuaClient(ck)
                # [优化] 调用 grab_promotion 时传入 group 中存储的真实经纬度
                succ, info = cli.grab_promotion(bestp["promotion_id"], pf, group["city"], group["lat"], group["lng"])
                if succ:
                    grabbed.add(sid); gj["store_ids"] = list(grabbed); gj["date"] = current_date
                    middleware.bucketSet('yuhua_xcbwc_grabbed_store_today', acid, json.dumps(gj, ensure_ascii=False))
                    push_msg(u, f"=====抢单成功=====\n🤪 账号: {nm}\n🎯 店铺: {sid}\n------------------\n{format_promotion_list([bestp], reduce_left_num=True)}\n==================")
                else:
                    if "超过店铺限制" in info: 
                        overlimit.add(sid); ol["store_ids"] = list(overlimit); ol["date"] = current_date
                        middleware.bucketSet('yuhua_xcbwc_overlimit_store_today', acid, json.dumps(ol, ensure_ascii=False))
                    if "无法重复参与" in info: 
                        repeat.add(sid); rp["store_ids"] = list(repeat); rp["date"] = current_date
                        middleware.bucketSet('yuhua_xcbwc_repeat_store_today', acid, json.dumps(rp, ensure_ascii=False))
                    push_msg(u, f"=====抢单失败=====\n🤪 账号: {nm}\n🎯 店铺: {sid}\n🪁 原因: {info}\n------------------\n{format_promotion_list([bestp])}\n==================")
        except: continue
def do_execute_self():
    clear_temp_ip_records()
    accs = get_accounts(userid)
    if not accs: sender.reply("=====未绑定账号=====\n❌ 未找到任何账号信息\n💡 发送 小蚕登录 绑定账号\n=================="); return
    sender.reply("正在运行...")
    for acid in accs:
        resp=do_run_one(acid)
        if resp: safe_reply(resp)
    clear_temp_ip_records()
def do_run_one(acid):
    nm = middleware.bucketGet('yuhua_xcbwc_remark',acid) or acid
    try:
        valid, ck = check_account_valid(acid)
        if not valid: return f"=====小蚕运行失败=====\n🤪 账号: {nm}\n💫 结果: {ck}\n=================="
        obj=yuhua(ck)
        if DEBUG_LOG: printf(f"Account {acid} running in city: {obj.city_code}", "DEBUG")
        
        obj.get_silk()
        handle_ck_result(acid, True)
        logs=obj.run_all()
        return f"=====小蚕运行结果=====\n🤪 账号: {nm}\n💫 结果:\n{format_success_logs(logs)}\n=================="
    except Exception as e:
        error_msg = str(e)
        if "CK失效" in error_msg: pass
        return f"=====小蚕运行失败=====\n🤪 账号: {nm}\n💫 结果: {parse_error_reason(error_msg)}\n=================="
def format_success_logs(logs):
    if not logs: return logs
    replacements = {"失败, 签到限一次": "成功, 签到限一次", "失败, 分享限一次": "成功, 分享限一次", "失败, 领取美团红包限一次": "成功, 领取美团红包限一次", "失败, 领取饿了么红包限一次": "成功, 领取饿了么红包限一次", "失败, 浏览福利页页面限一次": "成功, 浏览福利页页面限一次", "失败, 浏览霸王餐页面限一次": "成功, 浏览霸王餐页面限一次", "失败, 该奖品已经领取过了": "成功, 该奖品已经领取过了", "红包": "封紅"}
    for old, new in replacements.items(): logs = logs.replace(old, new)
    return logs
def analyze_task_result(logs):
    if not logs: return False, "日志为空"
    import re
    if "CK失效" in logs or "401 Client Error: Unauthorized" in logs or "登录状态已过期" in logs: return False, "CK失效"
    success_task_count, total_task_count, ip_blocked_task_count, network_error_count, limit_success_count = 0, 0, 0, 0, 0
    for i in [1, 2, 6, 7, 8, 9, 10, 11]:
        if f"任务[{i}]成功" in logs or f"任务[{i}]完成" in logs: success_task_count += 1; total_task_count += 1
        elif f"任务[{i}]" in logs:
            total_task_count += 1
            task_line = next((line for line in logs.split('\n') if f"任务[{i}]" in line), "")
            if any(p in task_line for p in ["限一次", "限制", "已完成"]): limit_success_count += 1
            elif f"任务[{i}]异常: IP已被风控" in logs: ip_blocked_task_count += 1
            elif f"任务[{i}]异常: 网络异常" in logs: network_error_count += 1
    success_indicators = sum(logs.count(s) for s in ["抽奖成功", "领取奖励[1]成功", "领取奖励[2]成功", "该奖品已经领取过了", "用户已无抽奖次数", "未达到抽奖次数"])
    total_success = success_task_count + limit_success_count
    if total_task_count > 0 and ip_blocked_task_count == total_task_count and success_indicators == 0 and total_success == 0: return False, "IP已被风控"
    if total_task_count > 0 and network_error_count == total_task_count and success_indicators == 0 and total_success == 0: return False, "网络异常"
    if total_success >= 3 or success_indicators >= 2: return True, "运行成功"
    if total_success >= 1 or success_indicators >= 1: return True, "部分成功"
    temp_logs = logs
    success_patterns = ["签到限一次", "分享限一次", "领取美团红包限一次", "领取饿了么红包限一次", "浏览福利页页面限一次", "浏览霸王餐页面限一次", "用户已无抽奖次数", "该奖品已经领取过了", "未达到抽奖次数", "抽奖成功"]
    for p in success_patterns: temp_logs = temp_logs.replace(p, "")
    temp_logs = re.sub(r'奖励状态: 领取奖励\[\d+\][^,\n]*|[^,\n]*IP已被风控[^,\n]*|[^,\n]*网络异常[^,\n]*', '', temp_logs)
    if any(indicator in temp_logs for indicator in ["服务器错误", "连接超时", "参数无效", "系统错误", "请求失败"]): return False, "系统异常"
    if ip_blocked_task_count > 0: return False, "部分IP风控"
    if network_error_count > 0: return False, "网络不稳定"
    return False, "任务执行异常"
def is_task_success(logs):
    success, _ = analyze_task_result(logs)
    return success
def do_execute_all():
    if not sender.isAdmin(): sender.reply("❌ 需要管理员权限"); return
    clear_temp_ip_records()
    try:
        push_enabled = (middleware.bucketGet('yuhua_xcbwc', 'push') or 'false') == 'true'
        sender.reply("正在运行...")
        tasks = [(u, acid) for u in middleware.bucketAllKeys('yuhua_xcbwc_user') for acid in get_accounts(u)]
        total = len(tasks)
        def worker(u, acid):
            nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
            try:
                ck = middleware.bucketGet('yuhua_xcbwc_token', acid)
                if not ck: return "skip", nm, "无CK", u
                if not check_auth_valid(acid): return "skip", nm, "未授权", u
                obj = yuhua(ck)
                if obj.get_silk() is None: return "skip", nm, "CK失效", u
                handle_ck_result(acid, True)
                logs = obj.run_all()
                if push_enabled:
                    ptxt = f"=====小蚕运行结果=====\n🤪 账号: {nm}\n💫 结果:\n{format_success_logs(logs)}\n==================".strip()
                    try: push_msg(u, ptxt)
                    except Exception: pass
                task_success, fail_reason = analyze_task_result(logs)
                return (True if task_success else False), nm, "运行成功" if task_success else fail_reason, u
            except Exception as e:
                if "CK失效" in str(e): pass
                return False, nm, parse_error_reason(str(e)), u
        success, skip, fails = 0, 0, []
        for i, (u, acid) in enumerate(tasks):
            if i > 0: time.sleep(random.uniform(5, 10))
            status, nm, reason, _ = worker(u, acid)
            if status is True: success += 1
            elif status == "skip": skip += 1
            else: fails.append((nm, reason))
        detail = "\n".join([f"🤪 账号: {x[0]}\n🪁 原因: {x[1]}" for x in fails])
        ret = f"=====小蚕一键统计=====\n✨ 总账号数: {total}\n💥 运行跳过: {skip}\n✅ 运行成功: {success}\n❌ 运行失败: {len(fails)}\n------------------\n📝 失败详情:\n{detail or '无'}\n=================="
        time.sleep(2)
        try: safe_reply(ret)
        except Exception: time.sleep(3); sender.reply(ret)
    finally: cleanup_resources()
zsm = middleware.bucketGet('yuhua_xcbwc','zsm') or ''
price_str = middleware.bucketGet('yuhua_xcbwc','price') or '0'
try: price = float(price_str) if float(price_str) >= 0 else 0.0
except: price = 0.0
def process_payment(amount, months, phone_mask):
    if not zsm: sender.reply("❌ 管理员未配置收款码"); return False
    pay_msg=f"=====扫码支付=====\n🤪 账号: {phone_mask}\n⏰ 时长: {months}月\n💰 金额: {amount}元\n------------------\n请在120秒内完成支付\n回复\"q\"取消\n=================="
    sender.reply(pay_msg); sender.replyImage(zsm)
    dd = sender.waitPay("q", 120000)
    if not dd: sender.reply("❌ 输入超时"); return False
    if str(dd).lower() == "q": sender.reply("✅ 已取消支付"); return False
    try:
        dd = json.loads(dd) if isinstance(dd, str) else dd
        mon = float(dd.get("Money") or dd.get("money", 0))
        if mon >= amount: return True
        sender.reply(f"=====支付失败=====\n❌ 支付金额不足\n------------------\n应付: {amount}元\n实付: {mon}元\n==================")
        return False
    except Exception as e: sender.reply(f"=====支付异常=====\n❌ 验证失败\n------------------\n错误: {str(e)}\n=================="); return False
def sub_test_grab(acid):
    nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
    try:
        if not check_auth_valid(acid): sender.reply(f"=====测试抢单=====\n🤪 账号: {nm}\n💫 结果: 未授权或授权已过期\n=================="); return
        ck = middleware.bucketGet('yuhua_xcbwc_token', acid)
        if not ck: sender.reply(f"=====测试抢单=====\n🤪 账号: {nm}\n💫 结果: CK不存在\n=================="); return
        loc_str = middleware.bucketGet('yuhua_xcbwc_jiankong_weizhi', acid)
        if not loc_str: sender.reply(f"=====测试抢单=====\n🤪 账号: {nm}\n💫 结果: 未记录位置\n=================="); return
        try: ld = json.loads(loc_str); lat, lng, city = float(ld["latitude"]), float(ld["longitude"]), int(ld["city_code"])
        except: sender.reply("❌ 位置解析失败"); return
        sender.reply("=====测试抢单=====\n请输入店铺标识\n-----------------\n请在30秒内完成\n回复\"q\"退出"); sid_in = sender.input(30000, 0, False)
        if not sid_in: sender.reply("❌ 输入超时"); return
        if sid_in.lower() == 'q': sender.reply("✅ 已退出操作"); return
        store_id = sid_in.strip()
        if not store_id.isdigit(): sender.reply("❌ 店铺标识应为纯数字"); return
        pf_val = None
        while True:
            sender.reply('请输入所属店铺平台:'); pf_in = sender.input(30000, 0, False)
            if not pf_in: sender.reply("❌ 超时已退出"); return
            pf_in = pf_in.strip().lower()
            if pf_in in ('美团', 'meituan'): pf_val = 1
            elif pf_in in ('淘宝闪购', 'ele', 'elm', 'eleme'): pf_val = 2
            elif pf_in in ('京东', 'jd'): pf_val = 3
            else: sender.reply("❌ 无效输入，请重新输入"); continue
            break
        sender.reply("正在抢单..."); yuhua(ck).get_silk(); cli = YuhuaClient(ck); offset, number = 0, 20; targets = []
        while True:
            ok, msg = _anonymous_query(lat, lng, city, offset, number, device_key=acid)
            if not ok: sender.reply(f"❌ 查询店铺活动失败: {msg}"); return
            pros = msg
            if not pros: break
            for p in pros:
                if str(p["store"]["store_id"]) == store_id and determine_platform(p) == pf_val: targets.append(p)
            if len(pros) < number: break
            offset += number
            time.sleep(random.uniform(1.0, 2.0))
        if not targets: sender.reply(f"❌ 店铺[{store_id}]在指定平台无可抢活动"); return
        bestp = pick_best_promotion_strict(targets)
        if not bestp: sender.reply("❌ 无符合时间段或名额的活动"); return
        pid = bestp["promotion_id"]; succ, info = cli.grab_promotion(pid, pf_val, city, lat, lng)
        if succ: sender.reply(f"=====测抢成功=====\n🤪 账号: {nm}\n------------------\n{format_promotion_list([bestp], reduce_left_num=True)}\n==================")
        else: sender.reply(f"=====测抢失败=====\n🤪 账号: {nm}\n🪁 原因: {info}\n------------------\n{format_promotion_list([bestp])}\n==================")
    except Exception as e: sender.reply(f"=====测试抢单=====\n🤪 账号: {nm}\n💫 结果: {parse_error_reason(str(e))}\n==================")
def show_account_menu(acid):
    is_mon_enabled=is_monitor_enabled()
    menu_items=["[1] 授权账号","[2] 运行任务","[3] 瓜分封紅","[4] 店铺活动","[5] 测试抢单"]
    if is_mon_enabled: menu_items.extend(["[6] 监控抢单","[7] 修改备注","[8] 记录位置","[9] 解除限制","[10] 删除账号"])
    else: menu_items.extend(["[6] 修改备注","[7] 记录位置","[8] 解除限制","[9] 删除账号"])
    menu=f"=====账号操作=====\n"+"\n".join(menu_items)+"\n------------------\n回复数字选择\n回复\"q\"退出\n"
    sender.reply(menu);c=get_user_input(None)
    if not c: return
    action_map_mon={"1":sub_auth,"2":sub_run,"3":cmd_manage_hongbaoyu_for_account,"4":sub_activity_list,"5":sub_test_grab,"6":sub_activity_monitor,"7":sub_rename,"8":sub_submit_location,"10":sub_delete,"9":sub_fix_risk}
    action_map_no_mon={"1":sub_auth,"2":sub_run,"3":cmd_manage_hongbaoyu_for_account,"4":sub_activity_list,"5":sub_test_grab,"6":sub_rename,"7":sub_submit_location,"9":sub_delete,"8":sub_fix_risk}
    action=(action_map_mon if is_mon_enabled else action_map_no_mon).get(c)
    if action: action(acid)
    else: sender.reply("❌ 无效输入")
def sub_auth(acid):
    nm=middleware.bucketGet('yuhua_xcbwc_remark',acid) or acid
    sender.reply("=====账号授权=====\n请输入授权月数\n-----------------\n回复数字设置天数\n回复\"q\"退出")
    c2 = get_user_input(None)
    if not c2: return
    try: months = int(c2); assert months > 0
    except: sender.reply("❌ 无效输入"); return
    amount=price*months
    if amount > 0 and not process_payment(amount, months, nm): return
    old_val = middleware.bucketGet('yuhua_xcbwc_auth', acid)
    new_t = calc_auth_time(old_val, months)
    middleware.bucketSet('yuhua_xcbwc_auth', acid, new_t)
    sender.reply(f"=====授权成功=====\n🤪 账号: {nm}\n⏰ 时长: {30*months}天\n📅 到期: {new_t}\n==================")
def execute_with_account(acid, action_name, action_func, *args):
    nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
    try:
        valid, result = check_account_valid(acid)
        if not valid: sender.reply(format_result(nm, action_name, result, False)); return
        sender.reply(f"正在{action_name}...")
        obj = yuhua(result)
        obj.get_silk(); handle_ck_result(acid, True)
        sender.reply(action_func(obj, acid, *args))
    except Exception as e:
        if "CK失效" in str(e): pass
        sender.reply(format_result(nm, action_name, parse_error_reason(str(e)), False))
def sub_run(acid):
    execute_with_account(acid, "运行", lambda obj, acid: format_result(middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid, "运行", f"\n{format_success_logs(obj.run_all())}", True))
def do_withdraw_all(withdraw_type):
    accs = get_accounts(userid)
    if not accs: sender.reply("=====未绑定账号=====\n❌ 未找到任何账号信息\n💡 发送 小蚕登录 绑定账号\n=================="); return
    sender.reply("正在提现...")
    success_count, skip_count, failure_count = 0, 0, 0
    for acid in accs:
        nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
        try:
            if not check_auth_valid(acid):
                skip_count += 1; sender.reply(f"=====提现失败=====\n🤪 账号: {nm}\n💫 结果: 未授权或授权已过期\n=================="); continue
            ck = middleware.bucketGet('yuhua_xcbwc_token', acid)
            if not ck: skip_count += 1; continue
            obj = yuhua(ck)
            obj.get_silk(); handle_ck_result(acid, True)
            ret = obj.withdrawzfb_all(acid) if withdraw_type == 'zfb' else obj.withdraw_all(acid)
            if "提现成功" in ret: success_count += 1; sender.reply(ret.strip())
            else: failure_count += 1
        except Exception:
            if "CK失效" in str(e): pass
            failure_count += 1
    if success_count == 0 and failure_count + skip_count == len(accs): sender.reply("❌ 暂无可提现账号")
def sub_activity_list(acid):
    nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
    try:
        valid, ck = check_account_valid(acid)
        if not valid: sender.reply(f"=====获取店铺失败=====\n🤪 账号: {nm}\n💫 结果: {ck}\n=================="); return
        sender.reply("正在查询...")
        yuhua(ck).get_silk(); handle_ck_result(acid, True)
        loc_str = middleware.bucketGet('yuhua_xcbwc_jiankong_weizhi', acid)
        if not loc_str: sender.reply(f"=====获取店铺失败=====\n🤪 账号: {nm}\n💫 结果: 未记录位置\n=================="); return
        try: ld = json.loads(loc_str); lat, lng, city = float(ld["latitude"]), float(ld["longitude"]), int(ld["city_code"])
        except: sender.reply("❌ 位置解析失败"); return
        offset = 0
        while True:
            ok, pros = _anonymous_query(lat, lng, city, offset, 20, device_key=acid)
            if not ok: sender.reply(f"❌ 获取店铺活动失败: {pros}"); return
            if not pros: sender.reply("❌ 没有更多店铺活动了" if offset else "❌ 未发现任何店铺活动"); return
            for pm in pros:
                pf = determine_platform(pm)
                if pf in {1, 2, 3}: middleware.bucketSet({1: 'yuhua_xcbwc_store_mt_info', 2: 'yuhua_xcbwc_store_elm_info', 3: 'yuhua_xcbwc_store_jd_info'}[pf], str(pm["store"]["store_id"]), json.dumps({"store_name": pm["store"].get("name","")}, ensure_ascii=False))
            safe_reply(f"=====店铺活动列表=====\n🤪 账号: {nm}\n💫 提醒: 没啥可提醒的\n------------------\n{format_promotion_list(pros)}\n==================")
            sender.reply("是否继续查看下一个页面？(y/n)")
            c = get_user_input(None, 30000)
            if not c or c.lower() != 'y': sender.reply("✅ 已退出操作"); return
            offset += 20
    except Exception as e:
        if "CK失效" in str(e): pass
        sender.reply(f"=====获取店铺失败=====\n🤪 账号: {nm}\n💫 结果: {parse_error_reason(str(e))}\n==================")
def format_order_list(orders, acid):
    nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
    lines = ["=====待上传订单=====", f"🤪 账号: {nm}", "💫 提醒: 请及时提交订单哦", "------------------"]
    now_ts = int(time.time())
    show_img = (middleware.bucketGet('yuhua_xcbwc', 'img') or 'false') == 'true'
    status_dict = {
        0: '已报名，待下单', 
        2: '已完成', 
        4: '已取消', 
        5: '超时取消，订单关闭'
    }
    for od in orders:
        st = od.get("store_promotion", {}).get("store", {})
        pf_val = od.get("store_platform", 1)
        money_val, rebate_val = od.get("store_platform_order_money", 0), od.get("user_rebate", 0)
        money_str = f"满{money_val // 100}返{rebate_val // 100}" if money_val > 0 else f"每单返{rebate_val // 100}"
        if cond_str := od.get("store_promotion", {}).get("rebate_condition_str", ""): money_str += f" {cond_str}"        
        extra = []
        order_status = od.get("order_status", -1)        
        if order_status == 0 and od.get("timeout_time", 0) > now_ts:
            rt = od["timeout_time"] - now_ts
            hh, mm, ss = rt // 3600, (rt % 3600) // 60, rt % 60
            extra.append(f"剩余时间:  {hh:02d}:{mm:02d}:{ss:02d}")        
        if order_status == 2 and od.get("upload_time"): 
            extra.append(f"上传时间:  {datetime.fromtimestamp(od['upload_time']).strftime('%m/%d %H:%M')}")        
        if show_img and (icon := st.get("icon", "")): 
            lines.append(f"[CQ:image,file={icon}]")
        status_text = status_dict.get(order_status, '未知状态')        
        lines.extend([
            f"订单标识:  {od.get('promotion_order_id', 0)}",
            f"店铺名称:  {st.get('name', '')}",
            f"店铺平台:  {'美团' if pf_val == 1 else ('淘宝闪购' if pf_val == 2 else '京东')}",
            f"返现要求:  {money_str}",
            f"活动状态:  {status_text}",
            *extra
        ])
        if od != orders[-1]: 
            lines.append("")            
    lines.append("==================")
    return "\n".join(lines)
def cmd_order_list_all():
    accs = get_accounts(userid)
    if not accs: sender.reply("=====未绑定账号=====\n❌ 未找到任何账号信息\n💡 发送 小蚕登录 绑定账号\n=================="); return
    sender.reply("正在查询...")
    order_map = {}
    for acid in accs:
        nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
        try:
            valid, ck = check_account_valid(acid)
            if not valid: sender.reply(f"=====获取订单失败=====\n🤪 账号: {nm}\n💫 结果: {ck}\n=================="); continue
            yuhua(ck).get_silk(); handle_ck_result(acid, True)
            cli = YuhuaClient(ck)
            ok, msg, orders = cli.get_promotion_order_list(order_status=0)
            if not ok: sender.reply(f"=====获取订单失败=====\n🤪 账号: {nm}\n💫 结果: {msg}\n=================="); continue
            if orders:
                safe_reply(format_order_list(orders, acid))
                for od in orders:
                    if poid := str(od.get("promotion_order_id", "")): order_map[poid] = acid
        except Exception as e:
            if "CK失效" in str(e): pass
            sender.reply(f"=====获取订单失败=====\n🤪 账号: {nm}\n💫 结果: {parse_error_reason(str(e))}\n==================")
    if not order_map: sender.reply("❌ 未发现任何待上传订单"); return
    while True:
        sender.reply("若需取消订单，请输入订单标识，回复 \"q\" 退出")
        inp = get_user_input(None)
        if not inp: return
        poid_str = inp.strip()
        if not poid_str.isdigit(): sender.reply("❌ 订单标识应为纯数字"); continue
        if poid_str not in order_map: sender.reply("❌ 未找到该订单标识"); continue
        acid = order_map[poid_str]
        cli = YuhuaClient(middleware.bucketGet('yuhua_xcbwc_token', acid))
        succ, info = cli.cancel_promotion_order(int(poid_str))
        sender.reply(f"✅ {info}" if succ else f"❌ 取消失败，原因: {info}")
        del order_map[poid_str]
def sub_activity_monitor(acid):
    if not is_monitor_enabled(): sender.reply("❌ 监控抢单功能已关闭"); return
    nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
    valid, ck = check_account_valid(acid)
    if not valid: sender.reply(f"=====监控抢单=====\n🤪 账号: {nm}\n💫 结果: {ck}\n=================="); return
    if not middleware.bucketGet('yuhua_xcbwc_jiankong_weizhi', acid): sender.reply(f"=====监控抢单=====\n🤪 账号: {nm}\n💫 结果: 未记录位置\n=================="); return
    MON_BUCKET = {1: 'yuhua_xcbwc_jiankong_store_mt', 2: 'yuhua_xcbwc_jiankong_store_elm', 3: 'yuhua_xcbwc_jiankong_store_jd'}
    SYM = {1: "ⓜ", 2: "ⓔ", 3: "ⓙ"}
    def _load_list(bname):
        try: return json.loads(middleware.bucketGet(bname, acid) or "[]")
        except: return []
    while True:
        st, push_st = middleware.bucketGet('yuhua_xcbwc_jiankong_status', acid) or 'off', middleware.bucketGet('yuhua_xcbwc_jiankong_push', acid) or 'f'
        store_seq = [(sid, pf) for pf, b in MON_BUCKET.items() for sid in _load_list(b)]
        def _today(name):
            try: d = json.loads(middleware.bucketGet(name, acid) or '{"store_ids":[]}'); return set(d["store_ids"]) if d.get("date") == str(get_china_date()) else set()
            except: return set()
        grabbed, overlimit, repeat = _today('yuhua_xcbwc_grabbed_store_today'), _today('yuhua_xcbwc_overlimit_store_today'), _today('yuhua_xcbwc_repeat_store_today')
        lines = ["=====监控抢单====="]
        if store_seq:
            for idx, (sid, pf) in enumerate(store_seq, 1):
                store_info = middleware.bucketGet({1:'yuhua_xcbwc_store_mt_info', 2:'yuhua_xcbwc_store_elm_info', 3:'yuhua_xcbwc_store_jd_info'}[pf], sid) or "{}"
                try: sname = json.loads(store_info).get("store_name", "")
                except: sname = ""
                disp = f"{SYM.get(pf, 'ⓝ')}{sname}" if sname else sid
                lines.extend([f"[{idx}] {sid}", f"    {disp}" if disp != sid else f"    {SYM.get(pf, 'ⓝ')}", f"    {'✅已抢单' if sid in grabbed else ('❌超过限制' if sid in overlimit else ('❌重复参与' if sid in repeat else '❌未抢单'))}"])
        else: lines.append("当未添加店铺标识, 开启监控后只检测推送5公里内新店铺活动")
        lines.extend([f"⏰ 监控状态: {'已开启' if st=='on' else '已关闭'}", f"⚜️ 上新推送: {'已开启' if push_st=='t' else '已关闭'}", "------------------", "+店铺标识=增加, -序号=删除, q=退出", "on=开启, off=关闭, t=开推送, f=关推送"])
        sender.reply("\n".join(lines)); cmd = get_user_input(None)
        if not cmd: return
        cmd = cmd.lower()
        if cmd in ('on', 'off'): middleware.bucketSet('yuhua_xcbwc_jiankong_status', acid, cmd); sender.reply(f"✅ 已{'开启' if cmd=='on' else '关闭'}监控")
        elif cmd in ('t', 'f'):
            if st != 'on': sender.reply("❌ 请先开启监控抢单")
            else: middleware.bucketSet('yuhua_xcbwc_jiankong_push', acid, cmd); sender.reply("✅ 已修改上新推送状态")
        elif cmd.startswith('+'):
            sid = cmd[1:].strip()
            if not sid.isdigit(): sender.reply("❌ 店铺标识应为数字"); continue
            pf_in = get_user_input('请输入所属店铺平台:', 30000)
            if not pf_in: continue
            pf_map = {'美团': 1, 'meituan': 1, '淘宝闪购': 2, 'ele': 2, 'elm': 2, 'eleme': 2, '京东': 3, 'jd': 3}
            if not (pf_val := pf_map.get(pf_in.lower())): sender.reply("❌ 无效平台"); continue
            lst = _load_list(MON_BUCKET[pf_val])
            if sid in lst: sender.reply("❌ 店铺标识已存在"); continue
            lst.append(sid); middleware.bucketSet(MON_BUCKET[pf_val], acid, json.dumps(lst)); sender.reply(f"✅ 店铺[{sid}]添加成功")
        elif cmd.startswith('-'):
            vs = cmd[1:].strip()
            if not vs.isdigit(): sender.reply("❌ 无效序号"); continue
            idx = int(vs) - 1
            if not (0 <= idx < len(store_seq)): sender.reply("❌ 序号越界"); continue
            sid, pf = store_seq[idx]; lst = _load_list(MON_BUCKET[pf])
            if sid in lst: lst.remove(sid); middleware.bucketSet(MON_BUCKET[pf], acid, json.dumps(lst))
            sender.reply(f"✅ 店铺[{sid}]删除成功")
        else: sender.reply("❌ 无效指令")
def sub_rename(acid):
    sender.reply(f"=====修改备注=====\n请输入新备注\n-----------------\n请在60秒内完成\n回复\"q\"退出")
    c2 = get_user_input(None)
    if not c2: return
    middleware.bucketSet('yuhua_xcbwc_remark', acid, c2.strip())
    sender.reply(f"✅ 已成功修改备注为[{c2.strip()}]")
def sub_submit_location(acid, ignore_auth=False):
    nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
    try:
        ck = middleware.bucketGet('yuhua_xcbwc_token', acid)
        if not ck:
             sender.reply(f"=====记录位置=====\n🤪 账号: {nm}\n💫 结果: CK不存在\n=================="); return False
             
        if not ignore_auth:
            if not check_auth_valid(acid):
                sender.reply(f"=====记录位置=====\n🤪 账号: {nm}\n💫 结果: 未授权或授权已过期\n=================="); return False        
        current_prompt = "=====记录位置=====\n❶为避免误差影响部分功能的使用体验，请打开小蚕软件或微信小蚕小程序刷新获取当前具体定位地址\n❷请一字无误地输入具体的定位地址\n------------------\n请在5分钟内完成\n回复\"q\"取消"        
        max_retries = 5
        for attempt in range(max_retries):
            addr = get_user_input(current_prompt, 300000)
            if not addr: return False 
            try: 
                u="https://apis.map.qq.com/ws/geocoder/v1/"; p={"address": addr, "key": "XKTBZ-YGULJ-6BQFP-DRZFR-YW7X7-U2BMD"}
                r = requests.get(u, params=p, timeout=(5, 12))
                if DEBUG_LOG: printf(f"[Map] >>> {r.request.url}\n[Req] {r.request.body}\n<<< {r.status_code}\n[Rsp] {r.text}", "DEBUG")
                r.raise_for_status(); geo_js = r.json()                
                if geo_js.get("status") != 0:
                    remaining = max_retries - 1 - attempt
                    if remaining > 0:
                        current_prompt = f"⚠️ 请尝试更详细的地址:"
                        continue
                    else:
                        sender.reply(f"❌ 解析失败: {geo_js.get('message', '未知错误')}"); return False
                loc, adinfo = geo_js.get("result", {}).get("location", {}), geo_js.get("result", {}).get("ad_info", {})
                la, ln, cc = loc.get("lat"), loc.get("lng"), adinfo.get("adcode")              
                if not all([la, ln, cc]): 
                    remaining = max_retries - 1 - attempt
                    if remaining > 0:
                        current_prompt = f"⚠️ 请输入完整的地址:"
                        continue
                    else:
                        sender.reply("❌ 地址解析结果不完整"); return False               
                loc_data = {"latitude": la, "longitude": ln, "city_code": cc}
                middleware.bucketSet('yuhua_xcbwc_jiankong_weizhi', acid, json.dumps(loc_data))
                sender.reply(f"=====记录位置=====\n🤪 账号: {nm}\n✅ 状态: 记录成功\n🎨 经度: {la}\n🃏 纬度: {ln}\n🏙️ 城市编码: {cc}\n==================")
                return True              
            except Exception as e:
                remaining = max_retries - 1 - attempt
                if remaining > 0:
                    current_prompt = f"⚠️ 请重新输入:"
                else:
                    sender.reply(f"=====记录位置=====\n🤪 账号: {nm}\n💫 结果: {parse_error_reason(str(e))}\n=================="); return False
        return False
    except Exception as e:
        sender.reply(f"=====记录位置=====\n🤪 账号: {nm}\n💫 结果: {parse_error_reason(str(e))}\n==================")
        return False
def sub_delete(acid):
    nm=middleware.bucketGet('yuhua_xcbwc_remark',acid) or acid
    sender.reply(f"⚠️ 确定删除账号[{nm}]吗? (y/n)")
    c2 = get_user_input(None, 30000)
    if not c2 or c2.lower() != 'y': sender.reply("✅ 已取消删除"); return
    if remove_account(userid, acid): sender.reply(f"✅ 已删除账号[{nm}]")
    else: sender.reply("❌ 删除失败")
def cmd_login():
    sender.reply("=====登录方式=====\n[1] 微信扫码登录\n[2] 抓包提交登录\n------------------\n回复数字选择方式\n回复\"q\"退出")
    choice = get_user_input(None)
    if not choice: return
    if choice == "2":
        sender.reply("=====抓包提交登录=====\n❶微信扫小蚕码登录后抓包 gw.xiaocantech.com/rpc 请求头\n❷发送: 备注#x-vayne#x-teemo#x-sivir\n==================")
        if share := middleware.bucketGet('yuhua_xcbwc', 'share') or '': sender.replyImage(share)
        inp = get_user_input(None)
        if not inp: return
        parts = inp.split("#")
        if len(parts) != 4: sender.reply("❌ 格式错误"); return
        _store_login_info(parts[0], parts[1], parts[2], parts[3], sender.getUserID())
    elif choice == "1": _wx_auth_login_flow()
    else: sender.reply("❌ 无效输入")
def get_qr_code():
    api_url = "https://yuhualhh.250666.xyz/api/wxcode.php"
    data = {
        "project": "xiaocan",
        "action": "create_qr"
    }
    try:
        r = requests.post(api_url, json=data, timeout=15)
        if DEBUG_LOG: printf(f"[QR] >>> {r.request.url}\n[Req] {r.request.body}\n<<< {r.status_code}\n[Rsp] {r.text}", "DEBUG")
        r.raise_for_status()
        result = r.json()
        if result.get('success') and isinstance(result.get('data'), dict):
            qr_url = result['data'].get('qr_img_url')
            uuid_val = result['data'].get('uuid')
            if qr_url and uuid_val:
                return uuid_val, qr_url
    except Exception as e: 
        if DEBUG_LOG: printf(f"[QR-Err] {e}", "ERROR")
    return None, None
def _check_qr_worker(uuid_val, ctx):
    api_url = "https://yuhualhh.250666.xyz/api/wxcode.php"
    data = {
        "project": "xiaocan",
        "action": "poll_scan_status",
        "uuid": uuid_val
    }
    while not ctx['stop'] and not ctx['code']:
        try:
            r = requests.post(api_url, json=data, timeout=15)
            if DEBUG_LOG: 
                printf(f"[QR-Poll] >>> {r.request.url}\n[Req] {r.request.body}\n<<< {r.status_code}\n[Rsp] {r.text}", "DEBUG")
            
            r.raise_for_status()
            result = r.json()
            if result.get('success') and isinstance(result.get('data'), dict):
                code = result['data'].get('code')
                if code:
                    ctx['code'] = code
                    return
        except Exception as e: 
            if DEBUG_LOG: 
                printf(f"[QR-Poll-Err] {e}", "ERROR")
            pass
        for _ in range(10):
            if ctx['stop'] or ctx['code']: return
            time.sleep(0.5)
def generate_login_headers():
    return _build_headers("WechatOpenapi", "WechatOpenapiService.AppLogin", teemo="0", extra={"appid": "16"}, device_key=userid)
def _app_login(wx_code: str, retry: int = 3) -> tuple[str | None, str | None]:
    headers_app = generate_login_headers()
    payload_app = {"code": wx_code, "app_id": 16}
    for _ in range(retry):
        try:
            resp = safe_request("POST", "https://gw.xiaocantech.com/rpc", headers=headers_app, json=payload_app)
            if resp and resp.status_code == 200:
                js = resp.json()
                if js.get("status", {}).get("code") == 0:
                    ui = js["user_info"]; return str(ui["user_id"]), str(ui["token"]["access_token"])
        except Exception: pass
        time.sleep(0.6)
    return None, None
def _get_user_info_scan(vayne: str, sivir: str, retry: int = 3) -> tuple[str | None, str | None]:
    payload = {"user_id": int(vayne), "inviter_silk_id": 0, "up": {"rcp": 1, "rc": 0}, "app_id": 16}
    headers = _build_headers("Silkworm", "SilkwormService.GetClientUserInfo", extra={"userid": vayne, "x-Vayne": vayne, "appidNum": "16", "x-Sivir": sivir})
    try:
        resp = safe_request("POST", "https://gw.xiaocantech.com/rpc", max_retries=retry, headers=headers, json=payload, timeout=12)
        js = resp.json()
        if js.get("status", {}).get("code") == 0:
            ui = js["user_info"]; return str(ui["silk_id"]), ui.get("nickname", "")
    except Exception: pass
    return None, None
def _wx_auth_login_flow():
    sender.reply("正在获取二维码…")
    uuid_val, qr_url = get_qr_code()
    if not uuid_val: sender.reply("❌ 二维码获取失败"); return
    sender.replyImage(qr_url)
    sender.reply("=====微信扫码登录=====\n请使用扫一扫摄像头扫码\n------------------\n请在5分钟内完成\n回复\"q\"取消")
    ctx = {'code': None, 'stop': False}
    t = threading.Thread(target=_check_qr_worker, args=(uuid_val, ctx))
    t.daemon = True
    t.start()
    for _ in range(300):
        if ctx['code']: break
        if inp := sender.input(1000, 0, False):
            if inp.strip().lower() == 'q':
                ctx['stop'] = True; sender.reply("✅ 已退出操作"); return
    ctx['stop'] = True
    if not ctx['code']: sender.reply("❌ 超时已退出"); return
    sender.reply("正在获取账号数据…")
    x_vayne, x_sivir = _app_login(ctx['code'])
    if not x_vayne: sender.reply("❌ 登录失败: 无法获取x_vayne与x_sivir"); return
    x_teemo, nickname = _get_user_info_scan(x_vayne, x_sivir)
    if not x_teemo: sender.reply("❌ 登录失败: 无法获取x_teemo与nickname"); return
    _store_login_info(nickname or x_vayne, x_vayne, x_teemo, x_sivir, sender.getUserID())
def _store_login_info(remark, vayne, teemo, sivir, uid):
    ck_str = f"{vayne}#{teemo}#{sivir}"
    existed_aid = next((aid for aid in get_accounts(uid) if (ck := middleware.bucketGet('yuhua_xcbwc_token', aid)) and ck.split('#')[1] == teemo), None)
    if not existed_aid: existed_aid = next((aid for aid in get_accounts(uid) if middleware.bucketGet('yuhua_xcbwc_teemo', aid) == teemo), None)
    target_acid = existed_aid
    is_new_account = False
    if target_acid:
        middleware.bucketSet('yuhua_xcbwc_token', target_acid, ck_str)
        middleware.bucketSet('yuhua_xcbwc_teemo', target_acid, teemo)
        middleware.bucketSet('yuhua_xcbwc_fail_count', target_acid, '0')
        if not (existing_remark := middleware.bucketGet('yuhua_xcbwc_remark', target_acid)) or existing_remark == target_acid:
            middleware.bucketSet('yuhua_xcbwc_remark', target_acid, remark)
    else:
        is_new_account = True
        target_acid = str(int(time.time()*1000)) + str(random.randint(100, 999))
        add_account(uid, target_acid)
        middleware.bucketSet('yuhua_xcbwc_token', target_acid, ck_str)
        middleware.bucketSet('yuhua_xcbwc_teemo', target_acid, teemo)
        middleware.bucketSet('yuhua_xcbwc_remark', target_acid, remark)
        middleware.bucketSet('yuhua_xcbwc_fail_count', target_acid, '0')
    loc_record = middleware.bucketGet('yuhua_xcbwc_jiankong_weizhi', target_acid)
    final_remark = middleware.bucketGet('yuhua_xcbwc_remark', target_acid) or remark
    
    if not loc_record:
        success = sub_submit_location(target_acid, ignore_auth=True)
        if not success:
            if is_new_account:
                remove_account(uid, target_acid)
            sender.reply(f"=====登录失败=====\n🤪 账号: {final_remark}\n❌ 原因: 未完成位置记录\n==================")
            return
    action_type = "更新成功" if existed_aid else "添加成功"
    sender.reply(f"=====登录成功=====\n🤪 账号: {final_remark}\n✅ 状态: {action_type}\n------------------\n发送\"小蚕管理\"管理账号\n发送\"小蚕查询\"查询账号")
def cmd_query():
    accs=get_accounts(userid)
    if not accs: sender.reply("=====未绑定账号=====\n❌ 未找到任何账号信息\n💡 发送 小蚕登录 绑定账号\n=================="); return
    sender.reply("正在查询...")
    if not ThreadPoolExecutor or len(accs)==1:
        for acid in accs:
            if rr := query_one(acid): safe_reply(rr)
    else:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
            futs = [exe.submit(query_one, a) for a in accs]
            for f in as_completed(futs):
                try:
                    if r := f.result(): safe_reply(r)
                except Exception: pass
def get_user_extra_info(obj):
    try:
        if user_info := obj.get_silk(force_refresh=True):
            return {"withdraw_total": user_info.get("withdraw_total", 0) / 100.0, "register_time": user_info.get("register_time", 0), "completed_number": user_info.get("completed_number", 0), "silk": user_info.get("silk", 0) / 100.0}
    except: pass
    return None
def query_one(acid):
    nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
    valid, ck = check_account_valid(acid)
    if not valid: return f"=====账号信息=====\n🤪 账号: {nm}\n💫 结果: {ck}\n=================="
    obj = yuhua(ck)
    try:
        extra_info = get_user_extra_info(obj)
        if extra_info is None: return f"=====账号信息=====\n🤪 账号: {nm}\n💫 结果: 请求失败，请稍后重试\n=================="
        handle_ck_result(acid, True)
        join_days = (get_china_time().replace(tzinfo=None) - datetime.fromtimestamp(extra_info["register_time"])).days if extra_info["register_time"] > 0 else 0
        auth_date = middleware.bucketGet('yuhua_xcbwc_auth', acid)
        auth_display = "未授权"
        if auth_date:
            try: auth_display = auth_date if datetime.strptime(auth_date, "%Y-%m-%d").date() >= today else "已过期"
            except: pass
        return (f"=====账号信息=====\n"
                f"🤪 用户账号: {nm}\n"
                f"🔥 累计已返: {extra_info['withdraw_total']:.2f}元\n"
                f"🗯️ 加入小蚕: {join_days}天\n"
                f"⚡ 完成订单: {extra_info['completed_number']}笔\n"
                f"💰 当前蚕豆: {extra_info['silk']:.2f}\n"
                f"🎉 全部卡券: {obj.get_all_cards()}\n"
                f"✨ 全部封紅: {obj.get_all_redpacks()}\n"
                f"☁️ 授权到期: {auth_display}\n"
                f"==================")
    except Exception as e:
        error_msg = str(e)
        reason = "CK失效" if "CK失效" in error_msg else parse_error_reason(error_msg)
        return f"=====账号信息=====\n🤪 账号: {nm}\n💫 结果: {reason}\n=================="
def cmd_manage():
    accs = get_accounts(userid)
    if not accs: sender.reply("=====未绑定账号=====\n❌ 未找到任何账号信息\n💡 发送 小蚕登录 绑定账号\n=================="); return
    lines = ["=====账号列表=====", "[0] 授权全部账号", "------------------"]
    for i, acid in enumerate(accs, 1):
        nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or f"账号{i}"
        auth_status = "⚠️ 未授权"
        if auth_date := middleware.bucketGet('yuhua_xcbwc_auth', acid):
            try: auth_status = f"✅ {auth_date}" if datetime.strptime(auth_date, "%Y-%m-%d").date() >= today else "❌ 已过期"
            except: pass
        lines.extend([f"[{i}] 账号信息", f"🤪 账号: {nm}", f"☁ 授权: {auth_status}", "------------------"])
    lines.extend(["回复数字选择", "回复'q'退出", "=================="])
    sender.reply("\n".join(lines))
    c = get_user_input(None)
    if not c: return
    try:
        idx = int(c)
        if idx == 0: handle_bulk_authorization(accs, is_admin_flow=False)
        elif 1 <= idx <= len(accs): show_account_menu(accs[idx - 1])
        else: sender.reply("❌ 无效选择")
    except ValueError: sender.reply("❌ 无效选择")
def cmd_auth():
    if not sender.isAdmin(): sender.reply("❌ 需要管理员权限"); return
    menu="=====授权管理=====\n[1] 授权所有用户\n[2] 授权指定用户\n------------------\n回复数字选择功能\n回复\"q\"退出"
    sender.reply(menu)
    c = get_user_input(None)
    if not c: return
    if c=='1': auth_all()
    elif c=='2': auth_user()
    else: sender.reply("❌ 无效选择")
def auth_all():
    sender.reply("=====一键授权=====\n请输入授权天数\n------------------\n回复数字设置天数\n回复\"q\"退出")
    c2 = get_user_input(None)
    if not c2: return
    try: days = int(c2); assert days != 0
    except: sender.reply("❌ 无效天数"); return
    success, failed = 0, 0
    for u in middleware.bucketAllKeys('yuhua_xcbwc_user'):
        for acid in get_accounts(u):
            try:
                old_val = middleware.bucketGet('yuhua_xcbwc_auth', acid)
                base = today
                if old_val:
                    dt = datetime.strptime(old_val, "%Y-%m-%d").date()
                    if dt > today: base = dt
                middleware.bucketSet('yuhua_xcbwc_auth', acid, (base + timedelta(days=days)).strftime("%Y-%m-%d"))
                success += 1
            except: failed += 1
    sender.reply(f"=====授权完成=====\n✅ 成功: {success}个账号\n❌ 失败: {failed}个账号\n⏰ 时长: {'授权' if days > 0 else '扣除'}{abs(days)}天\n==================")
def auth_user():
    sender.reply("=====指定授权=====\n请输入目标用户ID\n发送myuid可获取ID\n------------------\n回复\"q\"退出")
    uid = get_user_input(None)
    if not uid: return
    accs = get_accounts(uid)
    if not accs: sender.reply("❌ 该用户无账号"); return
    lines = ["=====账号列表=====", "[0] 授权全部账号", "------------------"]
    for i, acid in enumerate(accs, 1):
        nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or f"账号{i}"
        auth_status = "⚠️ 未授权"
        if auth_date := middleware.bucketGet('yuhua_xcbwc_auth', acid):
            try: auth_status = f"✅ {auth_date}" if datetime.strptime(auth_date, "%Y-%m-%d").date() >= today else "❌ 已过期"
            except: pass
        lines.extend([f"[{i}] 账号信息", f"🤪 账号: {nm}", f"☁ 授权: {auth_status}", "------------------"])
    lines.extend(["回复数字选择", "回复'q'退出", "=================="])
    sender.reply("\n".join(lines))
    c2 = get_user_input(None)
    if not c2: return
    try: idx = int(c2); assert 0 <= idx <= len(accs)
    except: sender.reply("❌ 无效选择"); return
    sender.reply("=====设置授权=====\n请输入授权天数\n------------------\n回复数字设置天数\n回复\"q\"退出")
    c3 = get_user_input(None)
    if not c3: return
    try: days = int(c3); assert days != 0
    except: sender.reply("❌ 无效天数"); return
    accounts_to_process = accs if idx == 0 else [accs[idx - 1]]
    success_count, fail_count = 0, 0
    for acid in accounts_to_process:
        try:
            old_val = middleware.bucketGet('yuhua_xcbwc_auth', acid)
            base = today
            if old_val:
                dt = datetime.strptime(old_val, "%Y-%m-%d").date()
                if dt > today: base = dt
            middleware.bucketSet('yuhua_xcbwc_auth', acid, (base + timedelta(days=days)).strftime('%Y-%m-%d'))
            success_count += 1
        except: fail_count += 1
    if idx == 0: sender.reply(f"=====授权完成=====\n✅ 成功: {success_count}个账号\n❌ 失败: {fail_count}个账号\n⏰ 时长: {'授权' if days > 0 else '扣除'}{abs(days)}天\n==================")
    elif success_count == 1:
        acid = accounts_to_process[0]
        rm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
        new_date = middleware.bucketGet('yuhua_xcbwc_auth', acid)
        sender.reply(f"=====授权成功=====\n🤪 账号: {rm}\n⏰ 时长: {'授权' if days > 0 else '扣除'}{abs(days)}天\n📅 到期: {new_date}\n==================")
def handle_bulk_authorization(accounts_to_auth, is_admin_flow=False):
    prompt = f"=====一键授权=====\n" + (f"授权价格: {price}元/月\n" if price > 0 and not is_admin_flow else "") + "请输入授权月数\n------------------\n回复数字设置月数\n回复\"q\"退出"
    sender.reply(prompt)
    c = get_user_input(None)
    if not c: return
    try: months = int(c); assert months > 0
    except: sender.reply("❌ 无效输入"); return
    num_accounts = len(accounts_to_auth)
    amount = price * months * num_accounts
    if amount > 0 and not is_admin_flow and not process_payment(amount, months, f"批量授权{num_accounts}个账号"): return
    success, failed = 0, 0
    for acid in accounts_to_auth:
        try:
            old_val = middleware.bucketGet('yuhua_xcbwc_auth', acid)
            middleware.bucketSet('yuhua_xcbwc_auth', acid, calc_auth_time(old_val, months))
            success += 1
        except: failed += 1
    sender.reply(f"=====授权完成=====\n✅ 成功: {success}个账号\n❌ 失败: {failed}个账号\n⏰ 时长: 授权{months}月\n==================")
def cmd_clean():
    if not sender.isAdmin(): sender.reply("❌ 需要管理员权限"); return
    sender.reply("正在清理...")
    removed = 0
    for u in middleware.bucketAllKeys('yuhua_xcbwc_user'):
        valid_accs = [acid for acid in get_accounts(u) if check_auth_valid(acid)]
        if len(valid_accs) < len(get_accounts(u)):
            removed += len(get_accounts(u)) - len(valid_accs)
            set_accounts(u, valid_accs)
    sender.reply(f"✅ 已清理{removed}个授权过期账号")
def _get_hb_events():
    all_accounts = []
    for u in middleware.bucketAllKeys('yuhua_xcbwc_user'):
        for acid in get_accounts(u):
            if ck := middleware.bucketGet('yuhua_xcbwc_token', acid):
                city_code = 440304
                if loc := middleware.bucketGet('yuhua_xcbwc_jiankong_weizhi', acid):
                    try: city_code = int(json.loads(loc).get("city_code", 440304))
                    except: pass
                all_accounts.append({'ck': ck, 'city_code': city_code})
    if not all_accounts: return None
    for acc_info in all_accounts:
        try:
            if evts := yuhua(acc_info['ck']).fetch_hb_events(acc_info['city_code']): return evts
        except Exception: continue
    return None
def cmd_get_hb_event():
    if evts := _get_hb_events():
        middleware.bucketSet('yuhua_xcbwc_hb_eventid', 'events', json.dumps({"date": str(get_china_date()), "events": evts}, ensure_ascii=False))
def get_current_hb_event():
    today_str = str(get_china_date())
    js = middleware.bucketGet('yuhua_xcbwc_hb_eventid', 'events')
    data = json.loads(js) if js else {}
    if data.get("date") != today_str:
        if not (evts := _get_hb_events()): return None
        data = {"date": today_str, "events": evts}
        middleware.bucketSet('yuhua_xcbwc_hb_eventid', 'events', json.dumps(data, ensure_ascii=False))
    now_ts = int(get_china_timestamp())
    ongoing = next((e for e in data.get("events",[]) if e.get("time", 0) <= now_ts <= e.get("end_time", 0)), None)
    future = [e for e in data.get("events", []) if e.get("time", 0) > now_ts]
    return ongoing or (min(future, key=lambda x: x.get("time")) if future else None)
def select_event_id_for_now():
    evt = get_current_hb_event()
    return evt.get("event_id") if evt else None        
def get_millisecond_time():
    return get_china_time().strftime('%H:%M:%S.%f')[:-3]
def format_analysis_detail(stage_name, first_time, last_time, attempts):
    return f"{stage_name}，请求时间{first_time}" if attempts == 1 else f"{stage_name}，首次请求{first_time}最后请求{last_time}，尝试{attempts}次"
def run_single_account_for_rain(user_id, acid, start_ts):
    nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
    log = {"final_reason": "未知", "last_time": get_millisecond_time()}
    ck = middleware.bucketGet('yuhua_xcbwc_token', acid)
    if not ck: log["final_reason"] = "CK不存在"; return "skip", nm, log
    if not check_auth_valid(acid): log["final_reason"] = "未授权或授权已过期"; return "skip", nm, log
    log.update({"check_attempts": 1, "check_first_time": get_millisecond_time()})
    try:
        obj = yuhua(ck); obj.get_silk()
        log["check_last_time"] = get_millisecond_time(); handle_ck_result(acid, True)
    except Exception as e:
        log["check_last_time"] = get_millisecond_time()
        if "CK失效" in str(e):
            try:
                middleware.bucketDel('yuhua_xcbwc_token', acid)
            except Exception:
                pass
            try:
                middleware.bucketDel('yuhua_xcbwc_fail_count', acid)
            except Exception:
                pass
            log["final_reason"] = "CK失效"
        else: log["final_reason"] = f"检测异常: {str(e)}"
        return False, nm, log
    event_id = select_event_id_for_now()
    if not event_id: log["final_reason"] = "当前无可瓜分封紅雨场次"; return False, nm, log
    city_code = 440304
    if loc_str := middleware.bucketGet('yuhua_xcbwc_jiankong_weizhi', acid):
        try: city_code = int(json.loads(loc_str).get("city_code", 440304))
        except: pass
    current_ts = get_china_timestamp()
    if current_ts > start_ts + 8: log["final_reason"] = "已过最佳时机，停止报名"; return False, nm, log
    if (wait_for_enroll := start_ts - 0.9 - current_ts) > 0: time.sleep(wait_for_enroll)
    log.update({"enroll_attempts": 1, "enroll_first_time": get_millisecond_time()})
    joined_ok, joined_msg, verify_m = obj.join_red_pack_rain_event(event_id, city_code)
    log["enroll_last_time"] = get_millisecond_time()
    if not joined_ok:
        if verify_m is not None or "活动太火爆" in joined_msg:
            log.update({"final_reason": f"请手动瓜分一场封紅雨解除风控，{joined_msg}"})
        else: log["final_reason"] = joined_msg
        return False, nm, log
    if (wait_for_grab := start_ts + 0.1 - get_china_timestamp()) > 0: time.sleep(wait_for_grab)
    log.update({"grab_attempts": 1, "grab_first_time": get_millisecond_time()})
    time.sleep(random.uniform(0.01, 0.05))
    ok, msg = obj.do_red_pack_rain_grab_num(event_id, city_code)
    log.update({"grab_last_time": get_millisecond_time(), "last_time": get_millisecond_time()})
    if ok or "已抽奖" in msg or "已参与" in msg:
        log["final_reason"] = msg if ok else "用户已抽奖"
        return True, nm, log
    log["final_reason"] = msg
    return False, nm, log
def do_redPackRainAll():
    if not sender.isAdmin(): sender.reply("❌ 需要管理员权限"); return
    try:
        global_push_enabled = (middleware.bucketGet('yuhua_xcbwc', 'hongbaoyu_push') or 'false') == 'true'
        sender.reply("正在运行...")
        target_evt = get_current_hb_event()
        if not target_evt: sender.reply("❌ 获取封紅雨场次失败"); return
        now_ts = get_china_timestamp()
        start_ts = target_evt.get("time", 0)
        event_hour = datetime.fromtimestamp(start_ts, CHINA_TZ).hour
        if event_hour not in {7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19} or abs(start_ts - now_ts) > 600:
            sender.reply("❌ 当前时间不在活动前后10分钟内，无法执行瓜分封紅操作")
            return
        all_accounts_tasks =[]
        for u in middleware.bucketAllKeys('yuhua_xcbwc_user'):
            for acid in get_accounts(u):
                if (middleware.bucketGet('yuhua_xcbwc_hongbaoyu_status', acid) or "on") == "on" and check_auth_valid(acid) and middleware.bucketGet('yuhua_xcbwc_token', acid):
                    all_accounts_tasks.append((u, acid))
        total = len(all_accounts_tasks)
        if total == 0: sender.reply("❌ 未找到任何账号"); return
        
        results_with_task_info =[]
        if not ThreadPoolExecutor:
            for task in all_accounts_tasks:
                results_with_task_info.append((task, run_single_account_for_rain(task[0], task[1], start_ts)))
        else:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                future_map = {ex.submit(run_single_account_for_rain, u, a, start_ts): (u, a) for u, a in all_accounts_tasks}
                for future in as_completed(future_map):
                    try: results_with_task_info.append((future_map[future], future.result()))
                    except Exception as exc:
                        _, acid_err = future_map[future]
                        nm_err = middleware.bucketGet('yuhua_xcbwc_remark', acid_err) or acid_err
                        results_with_task_info.append((future_map[future], (False, nm_err, {"enroll_attempts": 0, "grab_attempts": 0, "last_time": get_millisecond_time(), "final_reason": f"执行异常: {exc}"})))
        push_bucket, stats_bucket, today_str = 'yuhua_xcbwc_hongbaoyu_push_status', 'yuhua_xcbwc_hongbaoyu_stats', get_today_date_str()
        stats_updates = {}
        for task_info, result_data in results_with_task_info:
            user_id, acid = task_info
            status, name, details = result_data
            if status != "skip":
                stats_updates.setdefault(acid, {'success': 0, 'fail': 0})
                stats_updates[acid]['success' if status else 'fail'] += 1
            if not status and details.get("need_close_after_push", False):
                try:
                    middleware.bucketSet('yuhua_xcbwc_hongbaoyu_status', acid, 'off')
                    if global_push_enabled and (middleware.bucketGet(push_bucket, acid) or "off") == 'on':
                        push_msg(user_id, f"=====瓜分结果=====\n🤪 账号: {name}\n🪁 原因: {details['final_reason']}\n==================")
                        middleware.bucketSet(push_bucket, acid, 'off')
                except Exception: pass
            elif global_push_enabled and (middleware.bucketGet(push_bucket, acid) or "off") == 'on' and status != "skip":
                push_msg(user_id, f"=====瓜分结果=====\n🤪 账号: {name}\n{'💫 结果' if status else '🪁 原因'}: {details['final_reason']}\n==================")
        
        with stats_update_lock:
            for acid, updates in stats_updates.items():
                stats_data_str = middleware.bucketGet(stats_bucket, acid)
                stats = {'date': today_str, 'total': 0, 'success': 0, 'fail': 0}
                if stats_data_str:
                    try:
                        loaded_stats = json.loads(stats_data_str)
                        if loaded_stats.get('date') == today_str: stats = loaded_stats
                    except: pass
                stats['total'] += updates['success'] + updates['fail']
                stats['success'] += updates['success']
                stats['fail'] += updates['fail']
                middleware.bucketSet(stats_bucket, acid, json.dumps(stats))
        success_count = sum(1 for _, r in results_with_task_info if r[0] is True)
        skip_count = sum(1 for _, r in results_with_task_info if r[0] == "skip")
        failure_count = total - success_count - skip_count
        failure_details =[]
        for _, result_data in results_with_task_info:
            status, name, details = result_data
            if status is False:
                ap =[]
                if details.get('check_attempts', 0) > 0: ap.append(format_analysis_detail("①检测状态", details.get('check_first_time', ''), details.get('check_last_time', ''), details['check_attempts']))
                if details.get('enroll_attempts', 0) > 0: ap.append(format_analysis_detail("②报名操作", details.get('enroll_first_time', ''), details.get('enroll_last_time', ''), details['enroll_attempts']))
                if details.get('grab_attempts', 0) > 0: ap.append(format_analysis_detail("③瓜分操作", details.get('grab_first_time', ''), details.get('grab_last_time', ''), details['grab_attempts']))
                failure_details.append(f"🤪 账号: {name}\n🪁 原因: {details['final_reason']}\n💥 分析: \n" + ("\n".join(ap) if ap else "无详细记录"))
        
        final_reply =[f"=====一键瓜分统计=====\n✨ 总账号数: {total}\n💥 瓜分跳过: {skip_count}\n✅ 瓜分成功: {success_count}\n❌ 瓜分失败: {failure_count}\n------------------"]
        if failure_details: final_reply.extend(["📝 失败详情:"] + failure_details)
        final_reply.append("==================")
        safe_reply("\n".join(final_reply))
    finally: cleanup_resources()
def cron_task():
    sender.reply("正在检测...")
    all_u = middleware.bucketAllKeys('yuhua_xcbwc_user')
    global_stats = {"total": 0, "success": 0, "skip": 0, "fail": 0}
    all_fails = []
    try:
        for i, u in enumerate(all_u):
            if i > 0: time.sleep(random.uniform(3, 6))
            user_stats, user_fails = do_check_for_user(u)
            for key in global_stats:
                global_stats[key] += user_stats.get(key, 0)
            all_fails.extend(user_fails)
        detail = "\n".join([f"🤪 账号: {x[0]}\n🪁 原因: {x[1]}" for x in all_fails])
        admin_summary = f"=====小蚕检测统计=====\n✨ 总账号数: {global_stats['total']}\n💥 检测跳过: {global_stats['skip']}\n✅ 检测有效: {global_stats['success']}\n❌ 检测无效: {global_stats['fail']}\n------------------\n📝 无效详情:\n{detail if detail else '无'}\n=================="
        sender.reply(admin_summary)
    except Exception as e:
        sender.reply(f"❌ 检测失败: {str(e)}")
def do_check_for_user(uid):
    accs=get_accounts(uid)
    check_stats = {"total": 0, "success": 0, "skip": 0, "fail": 0}
    fails = []
    for acid in accs:
        check_stats["total"] += 1
        nm=middleware.bucketGet('yuhua_xcbwc_remark',acid) or acid
        if not check_auth_valid(acid):
            check_stats["skip"] += 1
            push_msg(uid, f"=====小蚕检测通知=====\n🤪 账号: {nm}\n🪁 原因: 授权已过期\n==================")
            continue
        ck=middleware.bucketGet('yuhua_xcbwc_token',acid)
        if not ck:
            check_stats["skip"] += 1
            push_msg(uid, f"=====小蚕检测通知=====\n🤪 账号: {nm}\n🪁 原因: CK为空\n==================")
            continue
        try:
            obj=yuhua(ck)
            obj.get_silk(force_refresh=True)
            handle_ck_result(acid, True)
            check_stats["success"] += 1
        except Exception as e:
            error_msg = str(e)
            if "CK失效" in error_msg:
                try:
                    middleware.bucketDel('yuhua_xcbwc_token', acid)
                except Exception:
                    pass
                try:
                    middleware.bucketDel('yuhua_xcbwc_fail_count', acid)
                except Exception:
                    pass
                check_stats["fail"] += 1
                reason = "CK失效 (已清理)"
                fails.append((nm, reason))
                push_msg(uid, f"=====小蚕检测通知=====\n🤪 账号: {nm}\n🪁 原因: {reason}\n==================")
            continue
    return check_stats, fails
def get_today_date_str():
    return get_china_date().strftime('%Y-%m-%d')
stats_update_lock = threading.Lock()
def handle_ck_result(acid, is_success):
    if is_success:
        middleware.bucketSet('yuhua_xcbwc_fail_count', acid, '0')
def cmd_manage_hongbaoyu_for_account(acid):
    nm = middleware.bucketGet('yuhua_xcbwc_remark', acid) or acid
    if not check_auth_valid(acid):
        sender.reply(f"=====瓜分封紅=====\n🤪 账号: {nm}\n❌ 状态: 未授权或授权已过期\n==================")
        return
    global_push_enabled = (middleware.bucketGet('yuhua_xcbwc', 'hongbaoyu_push') or 'false') == 'true'
    today_str = get_today_date_str()
    status_bucket = 'yuhua_xcbwc_hongbaoyu_status'
    push_bucket = 'yuhua_xcbwc_hongbaoyu_push_status'
    stats_bucket = 'yuhua_xcbwc_hongbaoyu_stats'
    key = acid
    def display_menu_hongbaoyu():
        feature_status = middleware.bucketGet(status_bucket, key) or "on"
        push_status = middleware.bucketGet(push_bucket, key) or "off"
        stats_data_str = middleware.bucketGet(stats_bucket, key)
        display_stats = {'total': 0, 'success': 0, 'fail': 0}
        if stats_data_str:
            try:
                stats_data = json.loads(stats_data_str)
                if stats_data.get('date') == today_str:
                     display_stats['total'] = stats_data.get('total', 0)
                     display_stats['success'] = stats_data.get('success', 0)
                     display_stats['fail'] = stats_data.get('fail', 0)
            except json.JSONDecodeError:
                pass
        base_menu = [
            "=====瓜分封紅=====",
            f"✨ 瓜分场数: {display_stats.get('total', 0)}",
            f"✅ 瓜分成功: {display_stats.get('success', 0)}",
            f"❌ 瓜分失败: {display_stats.get('fail', 0)}",
            f"⏰ 瓜分状态: {'开' if feature_status == 'on' else '关'}"
        ]
        commands = ["on=开, off=关, q=退出"]
        if global_push_enabled and feature_status == 'on':
            base_menu.append(f"⚜️ 瓜分推送: {'开' if push_status == 'on' else '关'}")
            commands.append("t=开启推送, f=关闭推送")
        base_menu.append("------------------")
        base_menu.extend(commands)
        sender.reply("\n".join(base_menu))
    while True:
        display_menu_hongbaoyu()
        feature_status = middleware.bucketGet(status_bucket, key) or "on"
        push_status = middleware.bucketGet(push_bucket, key) or "off"
        user_input = get_user_input(None)
        if not user_input:
            break
        user_input = user_input.lower()
        if user_input in ('on', 'off'):
            if feature_status != user_input:
                middleware.bucketSet(status_bucket, key, user_input)
                sender.reply(f"✅ 瓜分状态已{'开启' if user_input == 'on' else '关闭'}")
                if user_input == 'off' and push_status == 'on':
                    middleware.bucketSet(push_bucket, key, 'off')
                    sender.reply(f"✅ 瓜分推送已自动关闭")
            else:
                sender.reply(f"✅ 瓜分状态已是{'开启' if user_input == 'on' else '关闭'}状态")
        elif global_push_enabled and feature_status == 'on' and user_input in ('t', 'f'):
            new_push_status = 'on' if user_input == 't' else 'off'
            if push_status != new_push_status:
                middleware.bucketSet(push_bucket, key, new_push_status)
                sender.reply(f"✅ 瓜分推送已{'开启' if new_push_status == 'on' else '关闭'}")
            else:
                sender.reply(f"✅ 瓜分推送已是{'开启' if new_push_status == 'on' else '关闭'}状态")
        else:
            sender.reply("❌ 无效输入")
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
    if not check_maintenance_page(): sender.reply("❌ 服务端无法连通, 插件停止运行");return
    msg=sender.getMessage().strip().lower()
    if imtype in ("cron","fake"):
        if is_monitor_enabled(): monitor_task()
        return
    command_map={r'^(小蚕)(登录|登陆)$':cmd_login,r'^(小蚕)(查询)$':cmd_query,r'^(小蚕)(运行)$':do_execute_self,r'^(小蚕)(管理)$':cmd_manage,r'^(小蚕)(授权)$':cmd_auth,'小蚕清理':cmd_clean,'小蚕检测':lambda:cron_task() if sender.isAdmin() else sender.reply("❌ 需要管理员权限"),'小蚕一键运行':do_execute_all,'小蚕一键监控':lambda:(sender.reply("正在运行..."),monitor_task()) if is_monitor_enabled() and sender.isAdmin() else sender.reply("❌ 监控抢单功能已关闭" if not is_monitor_enabled() else "❌ 需要管理员权限"),'小蚕一键红包雨':do_redPackRainAll,'小蚕提宝':lambda:do_withdraw_all('zfb'),'小蚕提微':lambda:do_withdraw_all('wx'),'小蚕查单':cmd_order_list_all,r'^(小蚕)(解限)$':cmd_fix_risk}
    for pattern,handler in command_map.items():
        if re.match(pattern,msg) if pattern.startswith('^') else msg==pattern: handler();return
    sender.setContinue()
if __name__=="__main__":
    try:
        main()
    except Exception as e:
        sender.reply(f"❌ 插件异常: {str(e)}")
