# 馒头bot

适用于 AstrBot 的插件项目，当前接入多个 API 文本类接口，并提供基础管理功能。

## 项目信息

| 项目 | 内容 |
| --- | --- |
| 插件名 | 馒头bot |
| 作者 | 馒头 |
| 版本 | v1.8.0 |
| 仓库 | https://github.com/TimShitPig/mantou_Bot |

## 功能导航

| 分类 | 功能 | 触发文本 | 说明 |
| --- | --- | --- | --- |
| API功能 / OIAPI | 随机英文单词 | `随机英文单词` | 获取单词、翻译、例句和译文 |
| API功能 / OIAPI | 随机一言 | `随机一言` | 获取一言内容、出处和时间 |
| API功能 / OIAPI | 疯狂星期四 | `疯狂星期四` | 获取随机 KFC 文案 |
| API功能 / OIAPI | 古诗词名句 | `古诗词名句` | 获取名句、作者和作品 |
| 管理功能 | 数字撤回 | `连续 9-12 位数字` | 自动撤回符合规则的数字消息 |
| 管理功能 | 卡片撤回 | 群名片/群分享/JSON 卡片/合并转发/QQ 闪传 | 自动撤回群名片、JSON 卡片、合并转发和 QQ 闪传消息 |
| 管理功能 | 群文件清理 | `清理群文件` / `群文件清理` | 仅插件配置白名单 QQ 可用，循环扫描并发清理当前群群文件 |
| 管理功能 | 授权链接 | `授权` / `授权 数字群号` / `授权 数字群号 机器人QQ` | 生成 QQ 群服务授权链接，供群主在安卓/鸿蒙 QQ 打开授权 |
| 管理功能 | 七猫小说 | 七猫链接/七猫分享卡片 | 识别七猫链接，先回复书籍信息再下载并发送到 QQ |
| API功能 / OIAPI | 番茄小说 | 番茄链接/番茄 JSON 分享卡片 | 识别番茄小说链接，按指令手动选择 OIAPI 或析API 下载 |
| API功能 | 番茄小说API切换 | `查看API` 后发送 `1` / `2` | 查看并切换番茄小说下载 API，1 为 OIAPI，2 为析API |

<details>
<summary>查看随机英文单词</summary>

发送 `随机英文单词`，返回单词、中文翻译、英文例句和例句译文。

接口：`https://oiapi.net/api/RandEnglishDict`

</details>

<details>
<summary>查看随机一言</summary>

发送 `随机一言`，返回一言内容、出处和时间。

接口：`https://oiapi.net/api/AWord`

</details>

<details>
<summary>查看疯狂星期四</summary>

发送 `疯狂星期四`，返回一段随机 KFC 疯狂星期四文案。

接口：`https://oiapi.net/api/KFC`

</details>

<details>
<summary>查看古诗词名句</summary>

发送 `古诗词名句`，返回名句、作者和作品。

接口：`https://oiapi.net/api/Sentences`

</details>

<details>
<summary>查看数字撤回</summary>

用户发送的消息中包含连续 9 到 12 位数字时，插件会尝试撤回该消息。

会触发：`123456789`、`你好1078887813`、`你好A1078887813 你好`

不会触发：`12345678`、`1234567890123`、`107888A7813`、`123 456 789`、包含 `http://` 或 `https://` 的链接消息

</details>

## 项目结构

```text
.
├── main.py
├── metadata.yaml
├── requirements.txt
├── README.md
└── 功能文件/
    ├── API功能/
    │   ├── OIAPI/
    │   │   ├── 古诗词名句.py
    │   │   ├── 番茄小说.py
    │   │   ├── 疯狂星期四.py
    │   │   ├── 随机一言.py
    │   │   └── 随机英文单词.py
    │   └── 析API/
    │       └── 番茄小说.py
    ├── 下载缓存/
    └── 管理功能/
        ├── 消息工具.py
        ├── 授权链接.py
        ├── 七猫小说.py
        ├── 群文件清理.py
        └── 数字撤回.py
```

`main.py` 只负责 AstrBot 插件注册、消息监听和功能调用，具体功能代码放在 `功能文件/` 目录中。

## 安装方式

将插件目录放入 AstrBot 的 `data/plugins` 目录，然后在 AstrBot WebUI 的插件管理中重载插件。

## 依赖说明

依赖已写入 `requirements.txt`：

```text
aiohttp
pycryptodome
```

## 插件配置

| 配置项 | 说明 |
| --- | --- |
| `group_file_cleanup_admin_qq` | 群文件清理功能管理员 QQ 白名单 |
| `番茄小说key` | 调用 `https://oiapi.net/api/FqRead` 的 OIAPI key |

群文件清理只调用当前 AstrBot 适配器暴露的 OneBot 扩展接口 `get_group_root_files`、`get_group_files_by_folder` 和 `delete_group_file`，不会连接 NapCat 或 NapCat WebUI。删除阶段使用有限并发逐个调用 `delete_group_file`，默认同时删除 200 个文件；`qq_official` 事件只返回 `group_openid`，不能直接当作数字 QQ 群号；当前适配器没有 `api.call_action` 或返回非数字群号时，插件会输出 `群文件清理事件诊断` 日志用于查看真实事件参数。

七猫小说下载完成后会临时写入 `功能文件/下载缓存/`，优先通过 AstrBot `File` 组件上传到 QQ，无法使用时再回退 OneBot 本地路径上传。通过 `File` 组件发送时会延迟清理缓存，避免适配器读取前文件被删除；OneBot 回退上传尝试结束后立即删除 txt 文件。发送文件名格式为 `[完结]书名：xxx 作者：xxx.txt` 或 `[连载]书名：xxx 作者：xxx.txt`。txt 文件顶部会写入免责声明，文件发送成功后不再额外发送完成提示，只有发送失败时回复错误原因。

番茄小说识别 `fanqienovel.com`、`changdunovel.com`、`fqnovel.com` 和 `novelfm.com` 链接，支持 `changdunovel.com/t/短码` 分享短链和 JSON 卡片中的链接。下载前会先回复书名、作者、状态、章节、字数和 `正在下载中请稍等.....`，外部提示不显示简介，txt 文件头部会保留简介。发送 `查看API` 会列出番茄小说下载 API，随后发送 `1` 切换到 OIAPI，发送 `2` 切换到析API；当前选择会写入 `功能文件/下载缓存/番茄小说API.json`，重载后继续生效。两个接口不会自动互相切换，当前接口失败时会直接返回当前接口的错误。文件写入 `功能文件/下载缓存/`，优先使用 AstrBot `File` 组件发送；无法使用时再尝试裸本地路径和 `file://` URI 的 OneBot 上传接口。通过 `File` 组件发送时会延迟清理缓存，OneBot 回退上传尝试结束后删除缓存 txt，成功时不额外发送完成提示。

QQ 官方机器人 `qq_official` 发送文件应优先走 AstrBot `File` 组件，它会封装官方富媒体接口并发送 `media` 消息；如果 QQ 官方群聊返回 `call inner proxy error`，这是平台富媒体上传限制或临时错误。OneBot 的 `upload_group_file`/`upload_private_file` 只适用于 OneBot 适配器回退。

发送 `授权` 会生成 `https://club.vip.qq.com/transfer?open_kuikly_info=...` 授权链接；如果当前适配器取不到数字群号，可以发送 `授权 数字群号` 手动指定 `groupCode`；如果也取不到机器人 QQ，可以发送 `授权 数字群号 机器人QQ` 手动指定 `botUin`。插件会动态获取当前群号和机器人 QQ 号，机器人 QQ 会优先读取 AstrBot `context.robot_id`，并会递归读取事件 JSON、消息段 JSON 和 URL 编码 JSON 中的 `groupCode`、`botUin`、`botUid` 等字段；如果适配器不支持 UID 转换，会明确回复缺少机器人 UID。触发授权命令时会输出一条受控诊断日志 `授权链接事件诊断`，UID 转换接口有返回但无法识别时会输出 `授权链接UID转换响应未识别`。链接必须由群主在安卓/鸿蒙 QQ 9.2.90 及以上打开，iOS 暂不支持。

## 参考链接

- [AstrBot 官方仓库](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
