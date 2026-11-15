"""工作台导航、机器人选择和总览的页面结构。"""

图标路径 = {
    "dashboard": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 9h18M10 9v11"/>',
    "messages": '<path d="M20 16a2 2 0 0 1-2 2H8l-4 3V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2Z"/><path d="M8 9h8m-8 4h5"/>',
    "bot": '<rect x="4" y="6" width="16" height="14" rx="4"/><path d="M12 3v3M8 12h.01M16 12h.01M9 16h6M2 12v3m20-3v3"/>',
    "novels": '<path d="M12 6v14M3 5c3-1 6-1 9 1 3-2 6-2 9-1v14c-3-1-6-1-9 1-3-2-6-2-9-1Z"/>',
    "pans": '<path d="M7 18H6a4 4 0 0 1-.4-8 6 6 0 0 1 11.5-2 5 5 0 0 1 .9 10h-1m-8-3 3 3 3-3m-3-4v7"/>',
    "runtime": '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
    "settings": '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 4 14 4 14 0V6M5 12c0 4 14 4 14 0"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.4 9a2.7 2.7 0 1 1 4.4 2.2c-1.2.9-1.8 1.4-1.8 2.8m0 3h.01"/>',
    "admin": '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    "exit": '<path d="M10 4H5v16h5m4-12 4 4-4 4m-5-4h11"/>',
    "next": '<path d="m9 6 6 6-6 6"/>',
}

导航分组 = (
    ("工作台", (("dashboard", "工作台总览"), ("messages", "消息记录"))),
    ("业务管理", (("bot", "机器人与账号"), ("novels", "小说服务"), ("pans", "网盘与分享"))),
    ("系统运维", (("runtime", "运行状态"), ("settings", "系统设置"), ("help", "帮助指令"))),
)


def _图标(名称: str) -> str:
    return (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        + 图标路径[名称]
        + "</svg>"
    )


def _导航分组(标题: str, 链接: tuple) -> str:
    项目 = "".join(
        f'<a href="?view={页面}" data-view="{页面}"><span class="studio-nav-icon">{_图标(页面)}</span>'
        f'<span>{文字}</span></a>'
        for 页面, 文字 in 链接
    )
    return f'<div class="studio-nav-group"><p>{标题}</p>{项目}</div>'


工作台侧栏 = """
    <aside class="studio-sidebar" id="console-sidebar" aria-label="工作台侧栏" hidden>
      <div class="studio-robot">
        <div class="studio-bot-avatar" data-bot-avatar><span class="avatar-face">•ᴗ•</span></div>
        <div><strong data-bot-name>馒头助手</strong><small class="bot-profile-status" data-bot-status>状态未知</small></div>
      </div>
      <nav class="studio-nav" aria-label="工作台导航">
""" + "".join(_导航分组(标题, 链接) for 标题, 链接 in 导航分组) + """
      </nav>
      <div class="studio-sidebar-actions">
        <div class="studio-message-tools" aria-label="消息工作台工具">
          <button id="msg-rail-theme" type="button" aria-label="切换主题" title="切换主题"><span class="theme-control-icon" aria-hidden="true">◐</span></button>
          <button id="msg-rail-admin" type="button" aria-label="管理员菜单" title="管理员菜单" aria-expanded="false" aria-controls="admin-popover">""" + _图标("admin") + """</button>
        </div>
        <button class="studio-exit" id="studio-bot-exit" type="button">""" + _图标("exit") + """退出机器人</button>
      </div>
    </aside>
"""

书与馒头插画 = """
<svg class="studio-book-art" viewBox="0 0 260 146" aria-hidden="true" focusable="false">
  <ellipse cx="138" cy="126" rx="95" ry="11" fill="#7869b5" opacity=".12"/>
  <path d="M48 104q42-12 87 9 32-17 77-8l5 16q-47-7-81 9-44-19-92-12z" fill="#8d7ec8"/>
  <path d="M52 99q48-12 83 12 37-23 75-12l4 16q-41-4-79 13-40-19-88-14z" fill="#fff1d9" stroke="#997d9c" stroke-width="1.4"/>
  <path d="M49 99q47-20 85 10 34-28 79-12l-6 13q-37-4-72 14-39-22-90-14z" fill="#fffaf3" stroke="#b59ab3" stroke-width="1.4"/>
  <path d="M135 109v14M60 101q36-8 59 8m35 0q25-11 48-8" fill="none" stroke="#d8c0cd" stroke-linecap="round" stroke-width="1.5"/>
  <path d="M84 77c-1-14 12-22 21-26 10-6 12-17 25-17 14 0 16 10 26 17 13 7 23 15 22 29-1 14-19 19-46 19-29 0-47-7-48-22Z" fill="#fffaf4" stroke="#9c82af" stroke-width="2"/>
  <path d="M126 40q-1 10-10 16m20-15q4 9 10 13" fill="none" stroke="#e5c7ca" stroke-width="2" stroke-linecap="round"/>
  <path d="M112 74h.1m38 0h.1" stroke="#5b456e" stroke-width="4" stroke-linecap="round"/>
  <path d="M126 78q5 7 10 0" fill="none" stroke="#5b456e" stroke-width="1.7" stroke-linecap="round"/>
  <ellipse cx="105" cy="82" rx="7" ry="3" fill="#fac9bc"/><ellipse cx="157" cy="82" rx="7" ry="3" fill="#fac9bc"/>
  <path d="M55 51q11-1 11-12 1 11 11 12-10 1-11 12 0-10-11-12Zm138 10q8-1 9-9 0 8 9 9-9 1-9 9-1-8-9-9Z" fill="#d2b9f2"/>
  <path d="M179 29q7-1 8-9 1 8 8 9-7 1-8 9-1-8-8-9Z" fill="#f0aa85"/>
  <circle cx="45" cy="78" r="3" fill="#efb491"/><circle cx="221" cy="80" r="2.5" fill="#bdace9"/>
</svg>
"""

机器人选择 = """
      <section id="bot-picker" class="bot-picker studio-picker" aria-labelledby="bot-picker-title" tabindex="-1">
        <header class="studio-picker-banner">
          <div>
            <span class="studio-kicker">馒头 Bot · 运营工作台</span>
            <h1 id="bot-picker-title" tabindex="-1">选择机器人</h1>
            <p>每个机器人都有独立的工作台。进入后可管理小说、网盘、账号和聊天记录。</p>
          </div>
""" + 书与馒头插画 + """
        </header>
        <div class="studio-picker-list-head">
          <h2>QQ 官方机器人</h2>
          <button id="bot-picker-refresh" class="outline-button" type="button">刷新列表</button>
        </div>
        <p id="bot-picker-error" class="bot-picker-error" role="status" hidden></p>
        <div id="bot-profile-list" class="bot-profile-list" aria-label="机器人列表" aria-live="polite">
          <div class="bot-selector-empty">正在读取机器人…</div>
        </div>
      </section>
"""


总览业务行 = (
    ("novels", "小说服务", "metric-global-meta", "开关、测试模式与平台状态", "管理小说服务"),
    ("pans", "分享网盘", "metric-pan-meta", "账号、默认项与上传目录", "管理分享网盘"),
    ("settings", "数据库", "metric-db-meta", "连接状态与建表结果", "管理数据库"),
    ("runtime", "运行状态", "metric-version-meta", "版本、资源与依赖", "查看运行状态"),
)


def _总览业务行(序号: int, 页面: str, 名称: str, 摘要: str, 说明: str, 操作: str) -> str:
    return (
        f'<div class="dash-biz-row"><span class="dash-biz-index">{序号:02d}</span>'
        f'<div class="dash-biz-copy"><h3>{名称}</h3><small id="{摘要}">读取中</small></div>'
        f'<span class="dash-biz-note">{说明}</span>'
        f'<button type="button" data-view="{页面}" aria-label="{操作}" title="{操作}">{_图标("next")}</button></div>'
    )


工作台总览 = """
        <section id="page-dashboard" class="page-view studio-dashboard" data-page="dashboard">
          <div class="dash-top">
            <article class="studio-card dash-greet">
              <p class="dash-greet-line"><i class="dash-dot" aria-hidden="true"></i>服务运行概况 · 数据每 30 秒采集一次</p>
              <h2 class="dash-greet-title">你好，<span data-bot-name>馒头助手</span>。</h2>
              <p class="dash-greet-sub">小说、网盘、数据库与聊天状态，都收在这一屏。</p>
              <div class="dash-metrics">
                <div class="dash-metric"><strong id="metric-global">—</strong><span>小说服务</span></div>
                <div class="dash-metric"><strong id="metric-pan">—</strong><span>可用分享网盘</span></div>
                <div class="dash-metric"><strong id="metric-db">—</strong><span>数据库</span></div>
              </div>
              <div class="dash-actions">
                <a class="studio-primary" href="?view=messages" data-view="messages">""" + _图标("messages") + """打开消息记录</a>
                <a class="outline-button" href="?view=novels" data-view="novels">管理小说服务</a>
              </div>
            </article>
            <article class="studio-card dash-snap">
              <header class="dash-snap-head"><span>系统快照</span><a href="?view=runtime" data-view="runtime">详情 """ + _图标("next") + """</a></header>
              <dl class="dash-snap-list">
                <div><dt>CPU 占用</dt><dd id="dashboard-cpu">—</dd></div>
                <div><dt>物理内存</dt><dd id="dashboard-memory">—</dd></div>
                <div><dt>系统运行时间</dt><dd id="dashboard-runtime">—</dd></div>
              </dl>
              <footer class="dash-snap-foot"><span>插件版本</span><strong id="metric-version">—</strong></footer>
            </article>
          </div>
          <article class="studio-card dash-biz">
            <header class="dash-biz-head">
              <div><h2>业务一览</h2><p>点开任一行即可进入对应的管理页</p></div>
              <span class="dash-biz-tag">4 项服务</span>
            </header>
            <div class="dash-biz-list">
""" + "".join(_总览业务行(i + 1, *行) for i, 行 in enumerate(总览业务行)) + """
            </div>
          </article>
          <article class="studio-card dash-guide">
            <span class="dash-guide-icon">""" + _图标("help") + """</span>
            <div><h2>帮助指令</h2><p>找书、下载和管理命令随手查。</p></div>
            <a href="?view=help" data-view="help" aria-label="查看帮助指令">""" + _图标("next") + """</a>
          </article>
        </section>
"""
