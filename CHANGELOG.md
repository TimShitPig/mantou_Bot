# 更新日志

## v1.4.0

### 新增

- 新增 `古诗词名句` 功能，接入 `https://oiapi.net/api/Sentences`。
- 新增 `随机英文单词` 功能，接入 `https://oiapi.net/api/RandEnglishDict`。
- 新增 `随机一言` 功能，接入 `https://oiapi.net/api/AWord`。
- 新增 `疯狂星期四` 功能，接入 `https://oiapi.net/api/KFC`。

### 调整

- 将功能代码分类存放到 `功能文件/oiapi/` 目录。
- `main.py` 只保留插件注册、消息监听和功能调用。
- README 改为功能导航和折叠详情结构。

### 依赖

- 添加 `aiohttp` 作为异步 HTTP 请求依赖。
