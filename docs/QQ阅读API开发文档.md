# QQ 阅读 API 开发文档

适用于馒头bot v6.1.343 及以上。调用方只需一个 API Key，无需 AppID、QQ 机器人凭据或控制台登录 Cookie。

## 1. 开启与管理 Key

接口复用帮助网页的域名和端口。下面示例的 `https://你的域名` 请替换为实际帮助网页地址，HTTPS 可由现有反向代理提供。

控制台「机器人与账号 → 基础设置 → QQ 阅读开放接口」：

1. 点击「随机生成并添加」，立即复制新 Key；可重复添加多个。
2. 开启接口并保存配置。生成按钮本身会保存新 Key，无需再保存才能生效。
3. 列表只显示 Key 指纹，点击对应「撤销」可单独停用。新 Key 仅生成成功时显示一次；刷新、隐藏或离开页面后不再显示，遗失时撤销对应指纹并重新生成。

也可直接使用 AstrBot 插件配置（更改后重载插件）：

```json
{
  "qq_reader_api_settings": {
    "qq_reader_api_enabled": true,
    "qq_reader_api_keys": [
      "替换为第一个32至128位Key",
      "替换为第二个32至128位Key"
    ]
  }
}
```

示例值是占位文字，需替换。Key 允许 ASCII 字母、数字、`_`、`-`，长度32～128；自动去重。可用 Python 生成：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

配置列表 `[]` 表示撤销全部。控制台可选替换框按每行一个 Key 输入，保存后替换全部；留空保持原列表。旧版 `qq_reader_api_key` 继续有效，首次生成、撤销或替换列表时迁移并清空旧字段；旧 `qq_reader_api_appid` 不再参与鉴权或账号选择。

Key 属于同一服务的公共设置。不同 Key 的任务与文件独立隔离，撤销一个不影响其他 Key；被撤销 Key 的任务不可再读取，后台回收其结果。

下载无需调用方提交机器人身份。自动检查已配置机器人的当前 QQ 阅读账号：只有一个机器人选中了账号时复用该账号，即使共配置多个机器人；没有账号或多个机器人均选中账号时使用匿名阅读，不猜选首个账号或借用控制台当前作用域。一批任务固定提交时的阅读账号，切换后不修改已提交任务；新请求按账号快照隔离缓存，登录后不会继续复用旧匿名结果。账号是否仍有效及可读范围由现有 QQ 阅读流程校验。

## 浏览器直达下载（v6.1.344 起）

把以下链接中的服务地址、Key 和书籍 ID 换成自己的值，然后直接粘贴到浏览器地址栏：

```text
http://你的服务器:8090/openapi/qq-reader/v1/download?key=你的API_KEY&book_id=123456&chapter_range=1-n
```

这是 GET 下载接口，等待完成后直接返回 UTF-8 TXT 附件，不需要网页、请求头、AppID 或章节 ID。`book_id` 必填，`chapter_range` 默认 `1-n`；也可用 `1-100`、`101-n`。仅允许 `key`、`book_id`、`chapter_range`，不接受重复参数。支持以 Bearer 头调用；明确提供请求头时优先校验请求头，不回退 URL Key。

与任务接口共用两路队列、账号快照、任务复用、正文时限、文件上限与过期清理。相同 Key、书籍和范围复用未失败且未过期的任务。浏览器关闭不取消下载，重新打开同链接继续等待或获取已完成文件；反向代理或浏览器自身超时后也可重新打开。下载失败返回502 `download_failed`，Key 撤销返回401；其他参数和开关错误沿用下表。未完成任务的队列等待可能较长，自动化调用仍可使用异步任务接口。

URL Key 只用于 `/download`、`/chapter`、`/chapters` 三个浏览器 GET 入口，其他任务与文件接口仍要求 Bearer。插件关闭访问日志，并返回 `Cache-Control: private, no-store`、`Referrer-Policy: no-referrer`；URL 仍会出现在浏览器历史及由管理员配置的代理日志中，不应公开分享个人 Key。没有配置或启用 API 时不会启动下载。

## 单章与多章 JSON（v6.1.345 起）

整本继续用 `/download?key=KEY&book_id=ID`，直接返回 TXT 附件。单章、多章使用以下两个浏览器 GET 入口，等待正文完成后直接显示 `application/json`，不设置附件下载头；只需 Key，无需 AppID 或章节 ID。

```text
/openapi/qq-reader/v1/chapter?key=KEY&book_id=ID&chapter=1
/openapi/qq-reader/v1/chapters?key=KEY&book_id=ID&chapter_range=1-1000
```

`chapter` 为必填正整数目录序号；多章 `chapter_range` 默认 `1-n`，支持 `1-1000`、`101-200`、`101-n`。只处理实际存在且可获取的目录项：例如总共80章，请求 `1-1000` 只处理这80章，不提交不存在的第81～1000章，不以1000作为等待完成条件。起点超出目录或该范围没有可获取正文时返回受控错误。

两个入口共用 JSON 结构，单章的 `chapters` 最多一项。`total_chapters` 是实际原目录总数，`chapter_count` 是本次实际返回的章数；`index` 保留原目录序号，即使免费章节筛选或跳过图片章也不重排。仅输出以下公开字段，不输出资源地址或账号凭据。

```json
{
  "ok": true,
  "book_id": "123456",
  "title": "示例书名",
  "author": "作者",
  "chapter_range": "1-1000",
  "total_chapters": 2,
  "chapter_count": 2,
  "chapters": [
    {"index": 1, "title": "第一章", "content": "第一章正文"},
    {"index": 2, "title": "第二章", "content": "第二章正文"}
  ]
}
```

复用原有两路队列、账号冻结、超时、64 MiB 单结果上限及1小时清理；JSON 与 TXT 分别缓存，互不混用。浏览器断开不取消共享正文，Key 撤销后不可读取。旧 `/download` 的 `chapter_range` 参数仍可用于范围 TXT；浏览器要 JSON 时使用 `/chapter` 或 `/chapters`。

## 2. 鉴权与地址

统一前缀：`/openapi/qq-reader/v1`。所有请求，包括状态和 TXT，携带：

```http
Authorization: Bearer API_KEY
```

除上面三个浏览器 GET 入口外，不支持通过 URL 查询参数或控制台 Cookie 代替 Key。提交任务使用 `Content-Type: application/json`，不要提交 `appid` 或章节 ID。返回地址 `status_url` / `download_url` 是相对于服务域名的路径，调用时仍需同一 Key。

## 3. 提交任务

### 单本：POST /tasks

```json
{"book_id":"123456","chapter_range":"1-n"}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `book_id` | 是 | QQ 阅读书籍数字 ID，1～20位正整数；推荐字符串，也接受 JSON 整数 |
| `chapter_range` | 否 | 完整目录中从1开始的章节序号范围，默认 `1-n` |

范围示例：`1-n` 全部、`1-100` 前100章、`101-n` 第101章至目录末尾、`20-30` 第20～30章。终点超出目录时截到末章，起点超出目录时任务失败；不是章节 ID，不需要先获取目录或填写章节 ID。可读范围受原下载流程约束，实际章数看成功结果 `chapter_count`。

新任务返回 HTTP 202，`Location` 为查询路径；相同 Key、书籍 ID、规范章节范围、结果格式及账号快照复用排队中或下载中任务，复用尚未过期的成功结果返回200。失败后重新提交会创建新任务。除表内字段外的参数会被拒绝。

```bash
BASE='https://你的域名/openapi/qq-reader/v1'
API_KEY='替换为你保存的Key'
curl -X POST "$BASE/tasks" \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"book_id":"123456","chapter_range":"1-n"}'
```

响应示例：

```json
{
  "ok": true,
  "task": {
    "task_id": "a8b6c4d2e0f143579abcdef0123456789",
    "book_id": "123456",
    "chapter_range": "1-n",
    "status": "queued",
    "stage": "queued",
    "created_at": 1794225600,
    "expires_at": null,
    "status_url": "/openapi/qq-reader/v1/tasks/a8b6c4d2e0f143579abcdef0123456789"
  }
}
```

### 批量：POST /tasks/batch

多本批量（1～N本，没有插件级数量或排队上限）：

```json
{"book_ids":["123456","234567","345678"],"chapter_range":"1-n"}
```

单书章节范围也可以使用同一个批量入口：

```json
{"book_id":"123456","chapter_range":"1-100"}
```

`book_id` 与 `book_ids` 必须且只能选择一个。`book_ids` 为非空数组，按首次出现顺序去重；同批共用一个 `chapter_range`，默认 `1-n`。所有参数先完整校验，任何一项无效则整批400，不新增任务。插件不限制批量请求体字节数，反向代理的大小与读取超时设置仍然适用。

```bash
curl -X POST "$BASE/tasks/batch" \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"book_ids":["123456","234567"],"chapter_range":"1-n"}'
```

返回 `{"ok":true,"count":2,"tasks":[任务对象,任务对象]}`。每个对象结构与单本的 `task` 相同，各自查询、下载。全部复用成功结果时200，其余202；不存在单独的“批次状态”接口。

## 4. 状态与 TXT

`GET /tasks/{task_id}` 返回 HTTP 200 和 `{"ok":true,"task":{...}}`，建议每3～5秒轮询。

| status | 含义 |
| --- | --- |
| `queued` | 排队等待执行 |
| `running` | 下载中，`stage` 是当前处理阶段 |
| `succeeded` | 已完成，可下载 TXT |
| `failed` | 下载失败，`task.error` 为固定 `code/message` |

`created_at` / `expires_at` 为 Unix 秒时间戳；未结束任务 `expires_at` 是 null。成功时增加 `title`、`author`、`chapter_count`、`size_bytes`、`filename`、`download_url`。

```bash
TASK_ID='替换为返回的task_id'
curl "$BASE/tasks/$TASK_ID" -H "Authorization: Bearer $API_KEY"
# 仅在 status=succeeded 后下载：
curl -f "$BASE/tasks/$TASK_ID/file" -H "Authorization: Bearer $API_KEY" -o novel.txt
```

文件响应为 UTF-8 `text/plain`，`Content-Disposition` 含原始文件名；下载地址本身不带授权，转给其他人仍需提供创建任务的 Key。不触发 QQ 发消息或网盘上传。

固定2个后台工作协程，其余任务排队。每项正文开始后最多30分钟、单文件最多64 MiB；排队时间不计入正文超时。成功或失败后保留1小时，超时查询返回404，后台每分钟清理。同进程热重载保留任务ID、账号和已完成文件；未完成正文重新执行。进程重启不恢复这些内存任务，需重新提交。

## 5. 错误

接口级错误格式：

```json
{"ok":false,"error":{"code":"unauthorized","message":"API Key 无效"}}
```

| HTTP | code | 处理方式 |
| --- | --- | --- |
| 400 | `invalid_book_id` / `invalid_book_ids` / `invalid_chapter_range` / `invalid_request` | 修正 JSON、数字 ID、范围或额外参数 |
| 401 | `unauthorized` | 检查 Bearer Key 是否缺失、错误或已撤销 |
| 404 | `task_not_found` | 不存在、属于其他 Key、已过期或进程已重启 |
| 404 | `route_not_found` | 检查路径与 HTTP 方法 |
| 408 | `request_timeout` | 请求体需在10秒内读取完成 |
| 409 | `file_not_ready` | 先查询任务，成功后再下载 |
| 410 | `file_expired` | 文件丢失，重新提交 |
| 413 | `request_too_large` | 单本请求体超过8 KiB，批量不设此上限 |
| 415 | `json_required` | 使用 application/json |
| 503 | `api_disabled` / `api_not_configured` | 管理员开启接口并添加有效 Key |
| 500 | `internal_error` | 服务端处理失败，稍后重试 |

查询到 `status=failed` 仍为HTTP 200，应读取 `task.error`。例如正文超时 `download_timeout`、其他下载异常 `download_failed`，目录范围无结果 `chapter_range_out_of_bounds`；下载模块也可能返回其他受控错误码。响应不会包含账号凭据、异常原文或服务器文件路径。

## 6. Python 批量客户端

只使用 Python 3 标准库。保存为 `qq_reader_client.py`，设置 `QQ_READER_BASE`（含接口前缀）和 `QQ_READER_API_KEY` 后执行 `python qq_reader_client.py 123456 234567`；可设置 `QQ_READER_CHAPTER_RANGE=1-100`，默认 `1-n`。示例按任务ID保存到当前目录，避免把上游文件名当本地路径。

```python
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = os.environ["QQ_READER_BASE"].rstrip("/")
KEY = os.environ["QQ_READER_API_KEY"]


def request(path, payload=None, file=False):
    headers = {"Authorization": "Bearer " + KEY}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(BASE + path, data=body, headers=headers)
    try:
        with urlopen(req, timeout=60) as response:
            raw = response.read()
    except HTTPError as exc:
        try:
            code = json.loads(exc.read()).get("error", {}).get("code", "http_error")
        except (ValueError, AttributeError):
            code = "http_error"
        raise RuntimeError(f"HTTP {exc.code}: {code}") from None
    return raw if file else json.loads(raw)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("用法：python qq_reader_client.py 书籍ID [书籍ID ...]")
    result = request("/tasks/batch", {
        "book_ids": sys.argv[1:],
        "chapter_range": os.getenv("QQ_READER_CHAPTER_RANGE", "1-n"),
    })
    pending = {task["task_id"]: task for task in result["tasks"]}
    while pending:
        for task_id in list(pending):
            task = request("/tasks/" + task_id)["task"]
            if task["status"] == "succeeded":
                path = Path("qq-reader-" + task_id + ".txt")
                path.write_bytes(request("/tasks/" + task_id + "/file", file=True))
                print(task["book_id"], "已保存", path.name, task["chapter_count"], "章")
                del pending[task_id]
            elif task["status"] == "failed":
                print(task["book_id"], "失败", task.get("error", {}).get("code", "download_failed"))
                del pending[task_id]
        if pending:
            time.sleep(3)


if __name__ == "__main__":
    main()
```
