# 项目固定规则

以后修改这个仓库前先读本文件。

## 版本同步清单

每次更新插件版本时，必须同步修改这些位置：

- `main.py` 里的 `@register(..., "版本号")`
- `metadata.yaml` 里的 `version`
- `README.md` 项目信息表里的版本
- `CHANGELOG.md` 顶部新增对应版本更新记录

版本检查命令：

- `rg -n "1\.[0-9]+\.[0-9]+|v1\.[0-9]+\.[0-9]+" main.py metadata.yaml README.md CHANGELOG.md`

## 收尾流程

每次运行代码检查或修改代码后，必须执行：

- 删除仓库内生成的 `.pyc` 文件和空的 `__pycache__` 目录。
- 运行 `git status --short` 确认变更。
- 提交 Git，提交信息使用中文，格式为：`更新版本号至 vX.Y.Z，变更说明`。
- 如果没有版本升级，提交信息使用：`更新功能，变更说明`。
- 删除明显无用的旧代码，避免保留历史撤回、重复文本清理等不再需要的逻辑。
- `main.py` 只用来调用：只保留插件注册、模块加载和功能分发，不写具体功能实现、消息解析或业务判断。
- 消息解析与管理功能判断放到 `功能文件/管理功能/` 内，oiapi 请求逻辑放到 `功能文件/oiapi/` 内。
- 数字撤回判断只能使用可见文本或 text 消息段，禁止把事件对象、非文本消息段或 ID 字段 `str()` 后参与数字匹配。
- 插件配置必须使用 AstrBot `_conf_schema.json`；新增配置时同步说明 README、CHANGELOG 和 AGENTS。

## 排错原则

- 不要只按猜测下结论。遇到 OneBot、AstrBot、适配器消息段等外部协议细节不确定时，必须先联网查官方文档或上游资料，再改代码。
- 如果不知道如何做，或者用户给的消息样本不足以确定消息段结构，必须先联网搜索官方文档、上游源码或适配器资料。
- 日志行号和版本号必须作为判断依据。如果用户日志里的行号与当前源码不一致，优先怀疑 AstrBot 实际运行的插件目录没有同步或仍在加载旧代码。
- 排查加载问题时，应临时让运行日志输出当前插件版本和源码路径，避免误以为 GitHub 最新代码已经被 AstrBot 加载。
- 排查未知消息类型时，应先加受限诊断日志查看真实参数，包括 `message_str`、`raw_message`、消息段 type/data、对象字符串和 message_id，再按日志改规则；卡片类撤回应保留可定位真实消息段的诊断日志。
- OneBot 11 普通 `@人` 是 `at` 消息段或 `[CQ:at,qq=...]`，不是群名片；普通 `@人` 必须优先放行，不能进入数字撤回或群名片撤回。

## AstrBot 重载排查

- AstrBot 官方文档说明：代码修改后，在 WebUI 插件管理里点击 `管理` -> `重载插件`。
- 重载插件只重新加载 AstrBot 运行目录里的当前磁盘文件，不等于自动 `git pull` GitHub 最新代码。
- 本插件使用 `功能文件...` 这类顶层导入；AstrBot 重载主插件时，Python 可能仍缓存这些子模块。`main.py` 必须显式 `importlib.invalidate_caches()` 并 `reload()` 子模块。
- 如果 GitHub 已更新但日志仍显示旧版本或旧行号，必须先进入 AstrBot 实际插件目录执行 `git pull`，再删除 `.pyc` 和空 `__pycache__`，最后重载插件。
- 正确加载最新版时，日志必须出现 `Plugin 馒头bot (vX.Y.Z)`；如果仍有缓存疑问，再临时加入启动日志确认版本号和源码路径。
- 如果 WebUI 重载后仍是旧行号，直接重启 AstrBot 进程或容器；重启前后都要确认 `/AstrBot/data/plugins/馒头bot` 下的文件内容就是最新版本。

## AstrBot 限流排查

- 日志出现 `rate_limit_check.stage`、`会话 xxx 被限流`、`根据限流策略，此会话处理将被暂停 xxx 秒` 时，优先判断为 AstrBot 核心限流，不是本插件代码限流。
- AstrBot 官方配置在 `data/cmd_config.json` 的 `platform_settings.rate_limit`，默认示例为 `time: 60`、`count: 30`、`strategy: "stall"`；`stall` 会暂停会话等待，`discard` 会丢弃超限消息。
- 官方文档说明 `data/cmd_config.json` 是默认配置 `default`，WebUI 新建的其他配置文件在 `data/config/abconf_*.json`；排查时必须确认当前平台实际使用哪个配置文件。
- 想取消或降低触发概率，应在 AstrBot 配置里调大 `count`、调小 `time`，或把 `strategy` 改成 `discard`；插件内无法清除已经由 AstrBot 核心挂起的会话。
- 如果已经触发 `stall`，通常只能等待暂停时间结束；想立即恢复应先尝试在 WebUI 禁用/启用对应会话或重载配置，仍无效再重启 AstrBot。

## 功能边界

- 保留 oiapi 功能：`随机英文单词`、`随机一言`、`疯狂星期四`、`古诗词名句`。
- 数字撤回只撤回当前触发消息，不拉取历史消息，不撤回之前的消息。
- 群名片/群分享/JSON 卡片消息需要撤回当前消息，包括 `[ComponentType.Json]` 和组件对象字符串中的 `ComponentType.Json`。
- 白名单域名 `changdunovel.com` 不撤回；白名单判断必须优先于 JSON 卡片、合并转发、闪传和数字撤回判断。
- 合并转发/聊天记录消息需要撤回当前消息，包括 OneBot `forward`/`node` 和 AstrBot `ComponentType.Forward`、`ComponentType.Node`、`ComponentType.Nodes`。
- QQ 闪传消息需要撤回当前消息，只识别展示文本 `QQ闪传` 和 aiocqhttp 显示文本 `该消息类型暂不支持查看`；普通文件、OneBot `file`、`[CQ:file,...]`、AstrBot `ComponentType.File` 不应撤回。
- OneBot 11 标准撤回接口是单条 `delete_msg`，没有标准批量撤回接口；除非确认适配器支持扩展接口，否则只循环单条撤回，不写臆造的批量接口。
- 群文件清理只能由插件配置 `group_file_cleanup_admin_qq` 里的 QQ 使用；这是插件管理员白名单，不等同于群管理员。
- 群文件批量清理使用适配器扩展接口 `get_group_root_files`、`get_group_files_by_folder` 枚举文件，再逐个调用 `delete_group_file` 删除；不要把消息撤回接口当成群文件删除接口。
- 群文件清理不设置数量上限；必须递归扫描所有文件夹并去重后逐个删除。适配器单次枚举可能只返回前 50 个文件，删除一轮后必须重新扫描并继续删除，直到接口不再返回可删除文件。
- 目前未确认 go-cqhttp/NapCat 有单接口批量删除多个群文件的 API；如果以后要改成真正批量接口，必须先联网查到明确接口名和参数。
- 七猫小说功能只允许放在 `功能文件/管理功能/七猫小说.py` 一个文件内，不拆分多个 py 文件；`main.py` 只负责加载模块并调用 `获取七猫小说回复流`。
- 七猫小说只识别直接发送的七猫链接和七猫 JSON 分享卡片，不保留 `七猫搜索`、`七猫小说`、`七猫下载`、`七猫小说下载` 等文本命令。支持 `https://www.qimao.com/shuku/数字/`、`app-share.wtzw.com/.../article-detail/数字`、`app-share.wtzw.com/.../short-story-detail/数字` 或七猫 JSON 分享卡片，识别后下载 txt 发送到 QQ。下载前必须先回复书名、作者、状态、章节、字数和 `正在下载中请稍等.....`。优先尝试 base64 直传；适配器不支持时使用临时 txt 调用 `upload_group_file` 或 `upload_private_file`，上传结束必须删除临时文件，不要保存到仓库 `downloads`。
- 数字/卡片撤回白名单必须包含七猫域名 `qimao.com` 和 `app-share.wtzw.com`，七猫分享卡片不能被 JSON 卡片撤回逻辑撤回。
- 七猫小说下载必须记录受控日志：开始下载、章节进度、章节完成汇总、发送方式、临时文件删除结果；章节进度日志不能逐章刷屏，应按约 10% 分段输出。
- 七猫小说发送文件必须兼容不同适配器：优先尝试 `base64://` 和 `data:text/plain;base64,`，再用临时文件的 `file://` URI，最后才尝试裸路径；每个候选失败要写日志，临时文件必须删除。
- `shing-yu/7mao-novel-downloader` 已归档且 README 说明 4.0+ 开源部分为 AGPL-3.0、核心模块部分代码私有；本仓库不要直接复制其私有下载逻辑，七猫功能应以本地自测接口结果维护。
- 数字撤回规则：消息中出现独立连续 9 到 12 位数字就触发。
- `你好1078887813` 和 `你好A1078887813 你好` 应触发。
- `107888A7813`、`1234567890123`、`123 456 789` 不应触发。
- 包含明文链接、URL 编码链接或常见域名路径的链接消息不应触发数字撤回。
- 普通 `@人` 消息不应触发数字撤回或群名片撤回。
- 修改数字撤回后必须至少运行语法检查：`python -m py_compile main.py '功能文件\管理功能\数字撤回.py'`。
