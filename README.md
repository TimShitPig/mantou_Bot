# 馒头bot

## 项目简介

馒头bot 是一个适用于 AstrBot 的插件项目。

当前已接入 oiapi 的随机英文单词、随机一言和疯狂星期四接口，可用于获取英语学习内容、一句随机文字和 KFC 文案。

## 项目信息

- 插件名：馒头bot
- 作者：馒头
- 仓库：https://github.com/TimShitPig/mantou_Bot
- 版本：v1.3.0

## 功能列表

### 随机英文单词

发送以下普通文本即可触发：

```text
随机英文单词
```

回复内容包含：

- 单词
- 中文翻译
- 英文例句
- 例句译文

接口来源：

```text
https://oiapi.net/api/RandEnglishDict
```

### 随机一言

发送以下普通文本即可触发：

```text
随机一言
```

回复内容包含：

- 一言内容
- 出处
- 时间

接口来源：

```text
https://oiapi.net/api/AWord
```

### 疯狂星期四

发送以下普通文本即可触发：

```text
疯狂星期四
```

回复内容为一段随机 KFC 疯狂星期四文案。

接口来源：

```text
https://oiapi.net/api/KFC
```

## 项目结构

```text
.
├── main.py
├── metadata.yaml
├── requirements.txt
├── README.md
└── 功能文件/
    └── oiapi/
        ├── 疯狂星期四.py
        ├── 随机一言.py
        └── 随机英文单词.py
```

`main.py` 只负责 AstrBot 插件注册、消息监听和功能调用。

具体功能代码放在 `功能文件/oiapi/` 目录中。

## 安装方式

将插件目录放入 AstrBot 的 `data/plugins` 目录。

然后在 AstrBot WebUI 的插件管理中重载插件。

## 依赖说明

本插件使用异步 HTTP 请求库：

```text
aiohttp
```

依赖已写入 `requirements.txt`，AstrBot 加载插件时可按插件依赖机制安装。

## 参考链接

- [AstrBot 官方仓库](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
