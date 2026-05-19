# 馒头bot

适用于 AstrBot 的插件项目，当前接入多个 oiapi 文本类接口。

## 项目信息

| 项目 | 内容 |
| --- | --- |
| 插件名 | 馒头bot |
| 作者 | 馒头 |
| 版本 | v1.4.3 |
| 仓库 | https://github.com/TimShitPig/mantou_Bot |

## 触发方式

私聊或群聊直接发送功能触发文本即可，不需要 `/`；QQ 官方机器人私聊也不需要 `@`。

## 功能导航

| 功能 | 触发文本 | 接口 |
| --- | --- | --- |
| 随机英文单词 | `随机英文单词` | `RandEnglishDict` |
| 随机一言 | `随机一言` | `AWord` |
| 疯狂星期四 | `疯狂星期四` | `KFC` |
| 古诗词名句 | `古诗词名句` | `Sentences` |

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

## 项目结构

```text
.
├── main.py
├── metadata.yaml
├── requirements.txt
├── README.md
└── 功能文件/
    └── oiapi/
        ├── 古诗词名句.py
        ├── 疯狂星期四.py
        ├── 随机一言.py
        └── 随机英文单词.py
```

`main.py` 只负责 AstrBot 插件注册、消息监听和功能调用，具体功能代码放在 `功能文件/oiapi/` 目录中。

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




