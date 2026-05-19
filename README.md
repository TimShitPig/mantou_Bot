# 馒头bot

适用于 AstrBot 的插件项目，当前接入多个 oiapi 文本类接口，并提供基础管理功能。

## 项目信息

| 项目 | 内容 |
| --- | --- |
| 插件名 | 馒头bot |
| 作者 | 馒头 |
| 版本 | v1.6.3 |
| 仓库 | https://github.com/TimShitPig/mantou_Bot |

## 功能导航

| 分类 | 功能 | 触发文本 | 说明 |
| --- | --- | --- | --- |
| oiapi | 随机英文单词 | `随机英文单词` | 获取单词、翻译、例句和译文 |
| oiapi | 随机一言 | `随机一言` | 获取一言内容、出处和时间 |
| oiapi | 疯狂星期四 | `疯狂星期四` | 获取随机 KFC 文案 |
| oiapi | 古诗词名句 | `古诗词名句` | 获取名句、作者和作品 |
| 管理功能 | 数字撤回 | `9-12 位纯数字` | 撤回该用户前 20 条历史消息和当前数字消息 |

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

用户发送整条消息为 9 到 12 位连续数字时，插件会按需拉取当前会话历史消息，撤回该用户在数字消息之前的最近 20 条消息，并撤回当前数字消息。

不会处理数字消息之后的未来消息，也不会主动回复用户。

会触发：`123456789`、`1234567890`、`12345678901`、`123456789012`

不会触发：`12345678`、`1234567890123`、`abc123456789`、`123 456 789`

</details>

## 项目结构

```text
.
├── main.py
├── metadata.yaml
├── requirements.txt
├── README.md
└── 功能文件/
    ├── oiapi/
    │   ├── 古诗词名句.py
    │   ├── 疯狂星期四.py
    │   ├── 随机一言.py
    │   └── 随机英文单词.py
    └── 管理功能/
        └── 数字撤回.py
```

`main.py` 只负责 AstrBot 插件注册、消息监听和功能调用，具体功能代码放在 `功能文件/` 目录中。

## 安装方式

将插件目录放入 AstrBot 的 `data/plugins` 目录，然后在 AstrBot WebUI 的插件管理中重载插件。

## 依赖说明

依赖已写入 `requirements.txt`：

```text
aiohttp
```

## 参考链接

- [AstrBot 官方仓库](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)

