# 羽化面板 (yuhua-panel)

基于 [sillyGirl](https://github.com/smallfawn/sillyGirl) 的聊天机器人面板，基本兼容 AutMan 插件生态，无需改动插件直接放入即用，支持 QQ / QQ官方机器人 / 微信ClawBot / 千寻微信Pro / 企业微信AiBot / Telegram / agerMaid-Pyro / 钉钉 / Web Bot 多平台接入

推荐安装官方`支付接管`插件，可为任意插件源的Python、NodeJS插件提供支付接管与积分卡密系统服务。将插件原本调用的微信收款，统一接管为支付宝商家账单免挂、易支付或积分抵扣支付，同时兼容V1接口(MD5签名方式)各大码支付平台

推荐安装官方`文本转图`插件，可为消息规则的问答回复以及任意插件源的Python、NodeJS插件提供文本转图服务。使其文本内容替换成图片输出，可有效降低各大社交平台文本检测封禁风险

## 界面预览

<img src="https://gcore.jsdelivr.net/gh/lhz03/img@de716e632f4dbe8b756c97bb0b773dfc09a2b214/2026/08/11/55fb7d07dff2de9fecad7e3bea76c04d.png" width="50%" alt="羽化面板界面预览1">

<img src="https://gcore.jsdelivr.net/gh/lhz03/img@5bcb0526c07328887e09a67868ba35990368f220/2026/08/11/fad4c89281d1e4809f68c971639e2b0a.png" width="50%" alt="羽化面板界面预览2">

## 快速开始

| 方式 | 平台 | 说明 |
|---|---|---|
| [Docker](#docker部署推荐) | Linux | 一条命令部署，自动下载最新版 |
| [二进制](#linux二进制部署) | Linux | 自配环境 Node 24 + Python 3.12 |
| [Windows](#windows部署) | Windows | 自配环境 Node 24 + Python 3.12 |

管理员后台`http://服务器IP:6060/admin`，用户前台`http://服务器IP:6060`

## Docker部署（推荐）

镜像内置 Node 24 + Python 3.12 插件运行环境，首次启动自动下载最新版主程序到宿主机 `/root/yuhua-panel/`

### 国内服务器拉取镜像加速

Docker Hub 直连易断，先配置镜像加速器：

```bash
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1panel.live",
    "https://dockerproxy.link"
  ]
}
EOF
systemctl restart docker
```

### 方式一：docker compose

创建 `docker-compose.yml`：

```yaml
services:
  yuhua-panel:
    image: yuhualhh/yuhua-panel:latest
    container_name: yuhua-panel
    restart: unless-stopped
    ports:
      - "6060:6060"
    environment:
      SILLYGIRL_DATA_PATH: /data
    volumes:
      - ${YUHUA_PANEL_DIR:-/root/yuhua-panel}:/app/main
      - ${YUHUA_PANEL_DIR:-/root/yuhua-panel}/data:/data
```

```bash
mkdir -p /root/yuhua-panel && cd /root/yuhua-panel
docker compose up -d
```

### 方式二：docker run

```bash
mkdir -p /root/yuhua-panel/data
docker run -d \
  --name yuhua-panel \
  --restart unless-stopped \
  -p 6060:6060 \
  -e SILLYGIRL_DATA_PATH=/data \
  -v /root/yuhua-panel:/app/main \
  -v /root/yuhua-panel/data:/data \
  yuhualhh/yuhua-panel:latest
```

## Linux二进制部署

下载 [Releases](https://github.com/yuhualhh/yuhua-panel/releases) 中 `yuhua-panel-linux-<arch>-<版本>.tar.gz`：

```bash
mkdir -p /opt/yuhua-panel && cd /opt/yuhua-panel
tar -xzf yuhua-panel-linux-amd64-*.tar.gz
chmod +x yuhua-panel
./yuhua-panel
```

## Windows部署

下载 [Releases](https://github.com/yuhualhh/yuhua-panel/releases) 中 `yuhua-panel-windows-amd64-<版本>.zip`，解压双击 `yuhua-panel.exe` 即可


## 更新面板

- 面板后台有「更新」按钮，系统设置处有「自动更新」开关
- 管理员可发「更新」进行升级，也可发「回退」切换任意版本


## 社媒对接

- **QQ**：OneBot 反向 WebSocket，接入地址 `ws://<你的地址>:6060/qq/receive`（ [NapCat](https://napneko.github.io/) / [LLBot](https://luckylillia.com/) 兼容）
- **QQ官方机器人**：[查看配置教程](https://docs.astrbot.app/platform/qqofficial/websockets.html)，支持 WebSocket / Webhook 双模式，建议用户发指令`关联QQ`设置后开启映射功能，可同步使用该QQ对应的插件授权数据
- **微信ClawBot**：用户发「微信龙虾登录」扫码接入聊天，管理员可发「微信龙虾管理」进行管理
- **千寻微信Pro**：[访问官网下载安装启动](https://daenmax.github.io/qxpro-doc/)，在「框架设置-HTTP API服务端」页勾选「启用HTTPAPI、框架启动后自动开启HTTPAPI 」以及默认千寻监听接口7777，HTTP事件回调地址填 `http://<你的地址>:6060/qx/webhook`（可选 `webhook_key` 鉴权）；支持文本/图片/视频收发、好友自动同意、收款事件（10007/10015）
- **企业微信AiBot**：[查看配置教程](https://gcore.jsdelivr.net/gh/lhz03/img@b439d7ee31969c2102c08eba5f671e8fcb6f853f/2026/08/07/52d772bf84a495061e1ecf74c2347ba3.png)，企业微信群聊需@私聊不用
- **Telegram**：[查看创建TGBot教程](https://docs.astrbot.app/platform/telegram.html)，国内网络环境需要反代TG，[查看反代TG教程](https://mp.weixin.qq.com/s?__biz=Mzk5MDg4MzkwMw==&mid=2247483787&idx=1&sn=8ed139615fb93e4070fea30d5f5a1c34&chksm=c4e0b44e71a893e03228722a0d81d7ff2ef8470a8932fc7fb09c36ed3e810f223458affe6a84&mpshare=1&scene=1&srcid=0721Bck5S9Z3vl0IGZpu9Xtd&sharer_shareinfo=1731fe9070c841b4ecad2c2a159ccc40&sharer_shareinfo_first=1731fe9070c841b4ecad2c2a159ccc40&poc_token=HP7miGqjO8kWimCdpGq4KKc_UoSq_W4bs0CHjLmM)
- **钉钉**：[查看手动配置教程](https://docs.astrbot.app/platform/dingtalk.html)，群聊需@私聊不用
- **Web**：面板配置
- **agerMaid-Pyro**：[查看官网](https://xtaolabs.com/#/)
- **邮件服务**：当用户使用`Web`或`微信ClawBot`等任意平台进行对话聊天时，可发指令`推送管理`配置收信邮箱，用于接收某些内置任务插件的自动运行结果推送。建议用户设置QQ邮箱，然后在QQ或微信搜索启用`QQ邮箱提醒`功能。管理员需提前在后台系统设置配置邮件服务，[查看配置QQ邮箱发信教程](https://zhuanlan.zhihu.com/p/648304984)，默认打开QQ邮箱新版界面，请点击右上角头像昵称处切换旧版界面操作

## 备份数据

全部数据默认在 `/root/yuhua-panel/data/` 目录，可直接备份/迁移拷贝整个 `data/`目录。若无需打包依赖，可发备份指令 `导出数据`

## 项目致谢

基于并延续 [cdle/sillyGirl](https://github.com/cdle/sillyGirl) 与 [smallfawn/sillyGirl](https://github.com/smallfawn/sillyGirl) 的项目思想与代码积累

## 项目许可

MIT
