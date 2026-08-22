# 馒头bot

适用于 AstrBot 的小说下载与群聊管理插件。

![version](https://img.shields.io/badge/version-v5.32.1-2ea44f)
![AstrBot](https://img.shields.io/badge/AstrBot-plugin-4a90d9)
![license](https://img.shields.io/badge/license-AGPL--3.0-blue)

| 项目 | 内容 |
| --- | --- |
| 插件名 | 馒头bot |
| 作者 | 馒头 |
| 版本 | v5.32.1 |
| 仓库 | https://github.com/TimShitPig/mantou_Bot |

## 快速开始

### 公开仓库安装

AstrBot WebUI 插件管理中可添加仓库地址：

```text
https://github.com/TimShitPig/mantou_Bot
```

也可以手动安装到插件目录：

```bash
git clone https://github.com/TimShitPig/mantou_Bot.git /AstrBot/data/plugins/馒头bot
```

安装后到 AstrBot WebUI 的插件管理里重载插件。

### 私有仓库安装

GitHub 没有“公开但不可被搜索”的模式。若仓库为 Private，AstrBot 无法匿名拉取，需要在服务器上使用带权限的方式同步：

```bash
git clone https://<用户名>:<token>@github.com/TimShitPig/mantou_Bot.git /AstrBot/data/plugins/馒头bot
```

之后更新插件：

```bash
git -C /AstrBot/data/plugins/馒头bot pull
```

更安全的方式是在仓库 `Settings -> Deploy keys` 添加服务器 SSH 公钥，然后使用 `git@github.com:TimShitPig/mantou_Bot.git` 拉取。

### 依赖

依赖写在 `requirements.txt`：

```text
aiohttp
pycryptodome
pymysql
qrcode[pil]
```

## 功能总览

### 群聊管理

| 功能 | 触发文本 | 说明 |
| --- | --- | --- |
| 数字撤回 | 连续 9-12 位数字 | 普通成员触发后撤回当前消息，并从最近 100 条群历史中最多撤回该用户最近 8 条；QQ 群主和管理员不撤回 |
| 跨群累计禁言 | 广告类消息撤回 | 同一用户在不同群触发时按跨群累计次数递增禁言时长，群2不会重新从 0 计算 |
| 卡片撤回 | 群名片 / 群分享 / JSON 卡片 / 空间相册分享 / 合并转发 / QQ 闪传 | 自动撤回对应消息 |
| 单成员禁言 | `禁言 @成员` / `禁 @成员 1` / `解除禁言 @成员` / `解 @成员` | 默认禁言 7 天，支持秒、分、时、天；OneBot 与 QQ 官方群均支持 |

### 小说下载

| 平台 | 支持内容 | 说明 |
| --- | --- | --- |
| 番茄小说 | 番茄链接 / JSON 分享卡片 | 使用番茄畅听详情、目录和批量正文接口，最多 5 路动态并发 |
| 七猫小说 | 长篇/短篇链接 / 分享卡片 | 正文优先使用 App 批量接口 |
| 书旗小说 | 书旗链接 / 分享卡片 | SQB/SQC 整本下载与解密 |
| QQ阅读 | 详情/目录/分享链接、Cookie | 动态网关签名、动态密钥池、libfock 解密，普通正文每批 200 章 |
| QQ浏览器小说 | 链接 / `qb://ext/novelreader` | 公开搜索、详情、目录和正文接口 |
| 得间小说 | 链接 / 分享卡片 | 自定义 CTR 协议，最高 500 路并发 |
| 点众小说 | 链接 / 分享卡片 | 独立 App 会话，最高 60 路并发 |
| 知乎 | `story.zhihu.com` 付费专栏分享链接 | 只处理当前分享章节 |
| 塔读小说 | `reader.tadu.com` 书籍链接 | TDZ/AES/DES 解密，最高 400 路并发 |
| 百度小说 | 百度链接 / 分享卡片 | 出版源和 AES 普通源 |
| 小米小说 | 小米链接 / 分享卡片 | 兼容 `reader.browser.miui.com` 旧链接 |
| 宜搜小说 | 链接 / 分享卡片 | DES-CBC 解密 |
| 米读小说 | 链接 / 分享卡片 | 异步并发下载 |
| 猫眼小说 | 猫眼/掌阅链接 | XML 目录与 HTML 正文清理 |
| 酷我小说 | 链接 / 分享卡片 | 明文正文异步下载 |
| 酷匠小说 | 链接 / 分享卡片 | AES-CBC + gzip 解压 |
| 连城小说 | 链接 / 分享卡片 | HTML 正文清理 |
| 菠萝包小说 | 链接 / 分享卡片 | 支持 `m.sfacg.com/Novel/{书籍ID}` 与 `m.sfacg.com/b/{书籍ID}` 短链 |
| 晋江小说 | 链接 / 分享卡片 | 只请求公开章节，跳过付费或明确锁定章节 |

所有小说缺章时不生成部分 TXT；下载完成后上传当前主分享网盘，并发送“点击打开”按钮。

### 管理与工具

| 功能 | 触发文本 | 说明 |
| --- | --- | --- |
| 找书 | `找关键词` / `找书 关键词` / `找书名 关键词` / `找作者 关键词` | 聚合搜索多个平台，每页 5 条 |
| 小说开关 | `开小说` / `关小说` / `开平台名` / `关平台名` | 管理员可独立控制各平台下载开关 |
| 小说网盘 | `网盘` / `网盘状态` / `当前网盘` / `换UC` / `换夸克` / `换百度` / `夸克登录` | 查看或切换主分享网盘，保存网盘 Cookie |
| 帮助 | `帮助` / `帮助 数字` / `0` | 管理员查看主动触发和被动触发菜单 |
| 状态 | `状态` | 查看系统、进程、数据库和运行状态 |

## 详细说明

<details>
<summary>群管功能</summary>

用户消息包含连续 9 到 12 位数字时，插件会尝试撤回。群名片、JSON 卡片、空间相册分享、合并转发和 QQ 闪传也会进入同一撤回模块。

QQ 群主和管理员不会被自动撤回；插件优先通过 OneBot `get_group_member_info` 查询真实角色，查询不到时才使用事件 `role` 兜底。

普通成员当前消息撤回成功后，会从最近 100 条群历史中筛选该用户消息并逐条撤回，默认最多 8 条。广告类消息撤回并成功禁言后，只会发送一条“@发送者 / 请勿发送此类消息 / 如果是小说请联系群主”提醒。

数字撤回禁言次数按同一用户跨群累计：群1触发后，再到群2触发会继续递增禁言时长，不会重新从 0 开始计算。

本模块不提供踢人和全体禁言功能。单成员禁言默认 7 天，`禁 @成员 1` 表示 1 天，带 `秒`、`分`、`时`、`天` 时按对应单位计算；OneBot 使用 `set_group_ban`，QQ 官方群使用官方成员禁言接口。

</details>

<details>
<summary>小说下载与文件出口</summary>

所有小说模块都复用统一的 TXT 合成和网盘出口。正文写入 `功能文件/下载缓存/`，仅用于当前主分享网盘和百度后台备份，不直接通过 QQ 发送 txt 文件。

主网盘上传成功后，QQ 官方机器人会发送“点击打开”链接按钮；当前主网盘未配置或上传失败时只回复 `文件发送失败，请稍后再试`。

支持平台及特点：

- 番茄：批量正文接口，每批最多 1500 章，最多 5 路动态并发。
- 七猫：长篇正文优先 App 批量接口，短篇走短篇详情/目录与 `reader_agent=1` 正文接口。
- 书旗：固定 UID、盐值、M9 请求/响应加密，SQB/SQC 解密后按目录顺序合成。
- QQ阅读：动态网关签名、动态密钥池和 libfock 解密；普通正文每批 200 章、最多 100 路并发；支持 Cookie 登录态写入数据库。
- 得间：按参考源码执行单章授权、下载和解密，动态调度最高 500 路并发。
- 点众：每路正文任务使用独立 App 身份和 HTTP Session，最高 60 路并发。
- 知乎：只下载一条分享链接对应的当前章节。
- 塔读：TDZ/AES/DES 与 UTF-16LE 正文解析合并到单文件，最高 400 路动态并发。
- 百度：出版源使用 `doc_id` 接口，普通源使用 AES 正文接口。
- 小米：使用 `dushu.xiaomi.com` 接口，兼容旧 `reader.browser.miui.com` 链接。
- 菠萝包：支持 `m.sfacg.com/Novel/{书籍ID}` 和 `m.sfacg.com/b/{书籍ID}` 短链。
- 晋江：只请求公开章节，付费或明确锁定章节不请求。

</details>

<details>
<summary>网盘与运行状态</summary>

网盘登录态和当前主网盘保存在 MySQL `mantou_runtime_state` 表：

- `novel_pan_auth`：UC、夸克、百度 Cookie
- `qq_reader_auth`：QQ阅读 `ywguid` / `ywkey`
- `novel_share_pan`：当前主分享网盘

未配置数据库时不会尝试连接 MySQL，小说功能默认全部开启，主网盘默认 UC，相关运行状态无法持久化。

管理员可直接粘贴 UC、夸克、百度或 QQ阅读 Cookie，无需命令前缀；数据库登录态优先于插件配置。

</details>

## 项目结构

```text
.
├── AGENTS.md
├── CHANGELOG.md
├── LICENSE
├── README.md
├── _conf_schema.json
├── main.py
├── metadata.yaml
├── requirements.txt
└── 功能文件/
    ├── 下载缓存/
    └── 管理功能/
        ├── 基础功能/
        │   ├── QQ官方交互桥.py
        │   ├── 帮助功能.py
        │   ├── 权限工具.py
        │   ├── 消息工具.py
        │   ├── 状态功能.py
        │   └── 运行状态数据库.py
        ├── 小说功能/
        │   ├── 小说/
        │   │   ├── QQ浏览器小说.py
        │   │   ├── QQ阅读.py
        │   │   ├── 七猫小说.py
        │   │   ├── 书旗小说.py
        │   │   ├── 塔读小说.py
        │   │   ├── 宜搜小说.py
        │   │   ├── 小米小说.py
        │   │   ├── 得间小说.py
        │   │   ├── 晋江小说.py
        │   │   ├── 点众小说.py
        │   │   ├── 猫眼小说.py
        │   │   ├── 番茄小说.py
        │   │   ├── 百度小说.py
        │   │   ├── 知乎分享恢复客户端.py
        │   │   ├── 知乎小说.py
        │   │   ├── 米读小说.py
        │   │   ├── 菠萝包小说.py
        │   │   ├── 连城小说.py
        │   │   ├── 酷匠小说.py
        │   │   └── 酷我小说.py
        │   └── 功能/
        │       ├── 下载缓存清理.py
        │       ├── 小说下载任务.py
        │       ├── 小说功能开关.py
        │       ├── 找书.py
        │       └── 文本处理.py
        ├── 网盘功能/
        │   ├── UC网盘.py
        │   ├── 夸克网盘.py
        │   ├── 小说网盘.py
        │   ├── 百度网盘.py
        │   └── 网盘Cookie.py
        └── 群聊功能/
            ├── 群列表工具.py
            ├── 群成员事件.py
            └── 群管功能.py
```

`main.py` 只负责 AstrBot 插件注册、消息监听和功能调用，具体功能代码放在 `功能文件/` 中。

## 配置

| 配置项 | 说明 |
| --- | --- |
| `group_file_cleanup_admin_qq` | 管理员 QQ 白名单 |
| `uc_pan_settings` | UC 网盘 Cookie 和上传目录 |
| `quark_pan_settings` | 夸克网盘 Cookie 和上传目录 |
| `baidu_pan_settings` | 百度网盘 Cookie、上传目录和后台备份状态 |
| `database_settings` | MySQL 连接配置 |

`group_file_cleanup_admin_qq` 白名单内的 QQ 可使用帮助、状态、小说网盘切换、保存网盘与 QQ阅读 Cookie、小说开关和群管指令。

小说下载功能全部免费可用，不保留用户激活、卡密、收费、付费或每日免费额度。

## 更新日志

完整版本记录见 [CHANGELOG.md](./CHANGELOG.md)。

## 开源协议

本项目使用 [GNU AGPL-3.0](./LICENSE) 开源协议。

## 参考链接

- [AstrBot 官方仓库](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
