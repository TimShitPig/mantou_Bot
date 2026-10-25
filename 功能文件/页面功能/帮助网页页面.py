"""馒头控制台页面模板。

页面结构、样式和脚本分别维护，后端只负责把模板作为 HTML 响应返回。
"""

from .帮助网页样式 import 控制台样式
from .帮助网页脚本 import 控制台脚本

页面头部前缀 = """<!doctype html>
<html lang="zh-CN" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#081423">
  <title>馒头控制台</title>
  <script>
    (() => {
      try {
        const preference = localStorage.getItem('mantou-theme') === 'light' ? 'light' : 'dark';
        const dark = preference === 'dark';
        document.documentElement.dataset.themePreference = preference;
        document.documentElement.dataset.theme = dark ? 'dark' : 'light';
      } catch (_) {}
    })();
  </script>
  <style>"""
页面头部后缀 = """</style>
</head>
"""
页面主体 = """
<body>
  <div class="shell">
    <header class="topbar">
        <div class="brand"><div class="brand-mark"><svg viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M9 10c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7"/><path d="M5 24a11 11 0 0 1 22 0c0 4-22 4-22 0Z"/><path d="M12 18l-2 5m7-6 1 6m5-4 1 4"/></svg></div><div><strong>馒头Bot</strong><span class="version-badge" id="console-version">加载中</span></div></div>
      <div class="top-actions"><span class="status-dot">服务在线</span><div class="theme-control" role="group" aria-label="主题模式"><span class="theme-control-label">主题</span><button id="theme-toggle" class="theme-toggle-button" type="button" aria-label="切换到深色模式" title="切换到深色模式" aria-pressed="false"><span class="theme-control-icon" aria-hidden="true">◐</span></button><label class="theme-select-wrap" for="theme-select"><select id="theme-select" aria-label="选择主题模式"><option value="light">浅色模式</option><option value="dark">深色模式</option></select></label></div><div class="admin-menu"><button class="admin-chip" id="admin-chip" type="button" aria-expanded="false" aria-controls="admin-popover"><span class="admin-avatar" id="admin-avatar">管</span><span id="admin-name">管理员</span><span class="admin-chevron">⌄</span></button><div class="admin-popover" id="admin-popover" hidden><strong id="admin-popover-name">管理员</strong><small id="admin-popover-role">控制台管理员 · 当前会话</small><small id="admin-popover-scope">插件管理员白名单：读取中</small><button class="popover-logout" id="popover-logout" type="button" hidden>退出登录</button></div></div></div>
    </header>
    <aside class="sidebar">
      <div class="profile"><div class="bot-avatar" data-bot-avatar><span class="avatar-face"><svg viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M9 10c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7"/><path d="M5 24a11 11 0 0 1 22 0c0 4-22 4-22 0Z"/><path d="M12 18l-2 5m7-6 1 6m5-4 1 4"/></svg></span></div><strong data-bot-name>馒头助手</strong><span class="online">在线</span></div>
      <div><div class="nav-label">工作台</div><nav class="nav" aria-label="控制台导航">
        <a href="?view=dashboard" data-view="dashboard"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg></span>控制台</a>
        <a href="?view=bot" data-view="bot"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="6" width="16" height="14" rx="4"/><path d="M12 2v4m-5 6h.01M17 12h.01M9 16h6M1 11v4m22-4v4"/></svg></span>机器人配置</a>
        <a href="?view=novels" data-view="novels"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v16M3 4c4-1 6 0 9 2 3-2 5-3 9-2v15c-4-1-6 0-9 2-3-2-5-3-9-2Z"/></svg></span>小说功能</a>
        <a href="?view=pans" data-view="pans"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 18H6a5 5 0 0 1-1-10 7 7 0 0 1 13-2 6 6 0 0 1 0 12h-1M12 12v10m-3-3 3 3 3-3"/></svg></span>网盘配置</a>
        <a href="?view=messages" data-view="messages"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"/><path d="M7 8h10M7 12h7"/></svg></span>消息记录</a>
        <a href="?view=runtime" data-view="runtime"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12h4l3-8 4 16 3-8h4"/></svg></span>运行状态</a>
        <a href="?view=help" data-view="help"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 1 1 5 2c-1 1-2 1-2 3m0 3h.01"/></svg></span>帮助指令</a>
        <a href="?view=settings" data-view="settings"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="8" cy="18" r="2"/></svg></span>系统设置</a>
      </nav></div>
      <div class="sidebar-foot"><span class="spark" aria-hidden="true">✧</span><strong>馒头工作台</strong><span>消息、小说与网盘，在这里有序运转。</span></div>
    </aside>
    <main class="main">
      <div class="content">
        <div class="page-heading"><div><p id="page-eyebrow" class="page-kicker">馒头Bot / 管理台</p><h1 id="page-title">控制台</h1><p id="page-subtitle">查看机器人和小说服务的实时状态</p></div><div class="heading-actions"><span id="updated" class="updated-label">--</span></div></div>
        <div id="notice" class="notice"></div>
        <section id="page-dashboard" class="page-view" data-page="dashboard">
          <div class="section-head page-view-head"><div><h2>服务总览</h2><p>小说服务、分享网盘与数据库的当前状态。</p></div></div>
          <div class="summary-grid">
            <article class="summary-card"><span>小说总开关</span><strong id="metric-global">--</strong><small id="metric-global-meta">加载中</small><button class="text-button" type="button" data-view="novels">管理小说功能</button></article>
            <article class="summary-card"><span>当前分享网盘</span><strong id="metric-pan">--</strong><small id="metric-pan-meta">加载中</small><button class="text-button" type="button" data-view="pans">管理网盘</button></article>
            <article class="summary-card"><span>数据库状态</span><strong id="metric-db">--</strong><small id="metric-db-meta">加载中</small><button class="text-button" type="button" data-view="settings">查看数据库状态</button></article>
            <article class="summary-card"><span>插件版本</span><strong id="metric-version">--</strong><small id="metric-version-meta">馒头Bot</small><button class="text-button" type="button" data-view="runtime">查看运行状态</button></article>
          </div>
          <div class="page-grid dashboard-grid"><article class="console-card"><h2>快捷入口</h2><p class="card-subtitle">点击入口直接打开对应功能页面。</p><div class="shortcut-grid"><button class="shortcut-card" type="button" data-view="bot"><span class="shortcut-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="6" width="16" height="14" rx="4"/><path d="M12 2v4m-5 6h.01M17 12h.01M9 16h6M1 11v4m22-4v4"/></svg></span><strong>机器人配置</strong><small>查看安全摘要与监听配置</small></button><button class="shortcut-card" type="button" data-view="novels"><span class="shortcut-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v16M3 4c4-1 6 0 9 2 3-2 5-3 9-2v15c-4-1-6 0-9 2-3-2-5-3-9-2Z"/></svg></span><strong>小说功能</strong><small>开关平台和管理员测试模式</small></button><button class="shortcut-card" type="button" data-view="pans"><span class="shortcut-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 18H6a5 5 0 0 1-1-10 7 7 0 0 1 13-2 6 6 0 0 1 0 12h-1M12 12v10m-3-3 3 3 3-3"/></svg></span><strong>网盘配置</strong><small>选择主分享网盘和查看账号摘要</small></button><button class="shortcut-card" type="button" data-view="runtime"><span class="shortcut-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12h4l3-8 4 16 3-8h4"/></svg></span><strong>运行状态</strong><small>查看服务器实时指标</small></button></div></article><article class="console-card"><h2>当前状态</h2><p class="card-subtitle">最近一次读取：<span id="dashboard-updated">--</span></p><div class="status-list compact-status"><div class="status-item"><span>CPU 占用</span><strong id="dashboard-cpu">--</strong></div><div class="status-item"><span>物理内存</span><strong id="dashboard-memory">--</strong></div><div class="status-item"><span>系统运行时间</span><strong id="dashboard-runtime">--</strong></div></div></article></div>
        </section>

        <section id="page-bot" class="page-view" data-page="bot" hidden>
          <div class="workspace-grid"><div class="workspace-left"><article id="overview" class="console-card"><h2>基本信息</h2><p class="card-subtitle">当前插件的安全摘要和运行身份</p><div class="profile-fields"><div class="profile-field"><span>机器人名称</span><div class="readonly-value"><strong data-bot-name>馒头助手</strong><small>来自 QQ 官方资料</small></div></div><div class="profile-field"><span>机器人 QQ 号</span><div class="readonly-value"><strong data-bot-id>由适配器提供</strong><small>页面不读取账号信息</small></div></div><div class="profile-field"><span>机器人头像</span><div class="avatar-inline"><div class="bot-avatar" data-bot-avatar><span class="avatar-face"><svg viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M9 10c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7"/><path d="M5 24a11 11 0 0 1 22 0c0 4-22 4-22 0Z"/><path d="M12 18l-2 5m7-6 1 6m5-4 1 4"/></svg></span></div><small>QQ 官方资料头像</small></div></div><div class="profile-field"><span>机器人简介</span><div class="readonly-value"><strong>小说下载、网盘分享与群聊管理</strong></div></div><div class="profile-field"><span>运行状态</span><div class="state-line"><span class="online">在线运行</span></div></div></div></article><article id="config" class="console-card"><h2>机器人配置</h2><p class="card-subtitle">管理员白名单和帮助网页账号；敏感字段只写入，不在网页回显。</p><div id="basic-config-editor" class="config-editor"><div class="empty">正在读取配置...</div></div></article><article class="console-card"><h2>QQ阅读账号</h2><p class="card-subtitle">点击账号卡片打开配置；支持Cookie、QQ扫码和手机号登录。</p><div id="qq-auth-editor"><div class="empty">正在读取登录态...</div></div></article></div><div class="workspace-right"><article class="console-card"><h2>安全说明</h2><p class="card-subtitle">页面只展示后端允许的摘要。</p><div class="safe-list"><div><span>QQ阅读密钥</span><strong>点击后查看</strong></div><div><span>数据库连接参数</span><strong>登录后可编辑</strong></div><div><span>数据库密码</span><strong>只写入、不回显</strong></div><div><span>网盘 Cookie</span><strong>只写不回显</strong></div><div><span>会话 Cookie</span><strong>仅 HttpOnly 保存</strong></div></div></article></div></div>
        </section>

        <section id="page-novels" class="page-view" data-page="novels" hidden><article id="novels" class="novel-console standalone-card">
          <header class="novel-console-head"><div><span class="novel-overline">小说服务</span><h2>小说功能</h2><p class="card-subtitle">集中管理找书、下载与各平台开关。</p></div><div id="novel-state-pill" class="novel-state-pill"><span class="novel-state-dot"></span><strong>读取中</strong></div></header>
          <div class="novel-control-grid">
            <section class="novel-master-panel"><div class="novel-panel-kicker"><span class="novel-panel-icon">全</span><span>全局开关</span></div><div class="novel-master-copy"><h3>全部小说功能</h3><p>控制下载、找书和翻页的总入口。关闭后所有平台都会暂停响应。</p></div><div class="novel-master-actions"><div class="novel-master-state"><strong id="novel-master-label">读取中</strong><span id="novel-platform-summary">正在读取平台状态</span></div><button id="global-switch" class="switch" type="button" aria-label="切换全局小说功能"><span></span></button></div></section>
            <section class="novel-test-panel"><div class="novel-panel-kicker"><span class="novel-panel-icon">测</span><span>测试模式</span></div><h3>管理员测试模式</h3><p>只影响管理员测试，不会绕过普通用户的平台开关。</p><div class="novel-test-actions"><span id="novel-test-label" class="novel-test-note">状态读取中</span><button id="test-switch" class="switch" type="button" aria-label="切换管理员测试模式"><span></span></button></div></section>
          </div>
          <div class="novel-platform-head"><div><span class="novel-platform-overline">已接入平台</span><h3>平台开关</h3></div><span id="novel-enabled-count" class="novel-platform-count">-- / -- 已开启</span></div>
          <div id="novel-grid" class="novel-grid"><div class="empty">正在读取小说平台...</div></div>
        </article></section>

        <section id="page-pans" class="page-view" data-page="pans" hidden>
          <div id="pans" class="pan-page">
            <nav class="pan-tabs" role="tablist" aria-label="选择网盘">
              <button id="pan-tab-UC" class="pan-tab" type="button" role="tab" data-pan-tab="UC" aria-controls="pan-card-UC" aria-selected="false"><span class="pan-tab-mark pan-tab-uc">U</span><span class="pan-tab-copy"><span>UC网盘</span><small data-pan-tab-meta="UC">读取中</small></span></button>
              <button id="pan-tab-夸克" class="pan-tab" type="button" role="tab" data-pan-tab="夸克" aria-controls="pan-card-夸克" aria-selected="false"><span class="pan-tab-mark pan-tab-quark">夸</span><span class="pan-tab-copy"><span>夸克网盘</span><small data-pan-tab-meta="夸克">读取中</small></span></button>
              <button id="pan-tab-百度" class="pan-tab" type="button" role="tab" data-pan-tab="百度" aria-controls="pan-card-百度" aria-selected="false"><span class="pan-tab-mark pan-tab-baidu">度</span><span class="pan-tab-copy"><span>百度网盘</span><small data-pan-tab-meta="百度">读取中</small></span></button>
            </nav>
            <div id="pan-grid" class="pan-grid"><div class="empty">正在读取网盘状态...</div></div>
          </div>
        </section>

        <section id="page-runtime" class="page-view" data-page="runtime" hidden><article class="console-card standalone-card"><h2>运行状态</h2><p class="card-subtitle">这些数据来自服务器当前运行状态。</p><div class="runtime-grid runtime-page-grid"><div class="runtime-item"><span>CPU占用</span><strong id="runtime-cpu">--</strong></div><div class="runtime-item"><span>物理内存</span><strong id="runtime-memory">--</strong></div><div class="runtime-item"><span>磁盘空间</span><strong id="runtime-disk">--</strong></div><div class="runtime-item"><span>系统运行时间</span><strong id="runtime-runtime">--</strong></div><div class="runtime-item"><span>操作系统</span><strong id="runtime-os">--</strong></div></div><div class="runtime-detail"><div class="status-item"><span>数据库</span><strong id="runtime-db">--</strong></div><div class="status-item"><span>当前网盘</span><strong id="runtime-pan">--</strong></div><div class="status-item"><span>插件版本</span><strong id="runtime-version">--</strong></div></div></article></section>

        <section id="page-help" class="page-view" data-page="help" hidden><div class="section-head page-view-head"><div><h2>帮助指令</h2><p>这里列出机器人当前支持的聊天指令；网页不代替群聊执行指令。</p></div></div><div class="help-grid"><article class="console-card help-card"><h3>管理与状态</h3><p>需要管理员权限的指令。</p><div class="command-list"><span>帮助</span><span>状态</span><span>小说</span><span>开小说 / 关小说</span><span>开测试 / 关测试</span><span>网盘状态</span><span>换UC / 换夸克 / 换百度</span><span>夸克登录</span></div></article><article class="console-card help-card"><h3>小说入口</h3><p>在群聊或私聊发送链接即可识别。</p><div class="command-list"><span>找关键词</span><span>找书 关键词</span><span>找作者 关键词</span><span>上一页 / 下一页</span><span>小说平台分享链接</span><span>小说分享卡片</span></div></article><article class="console-card help-card"><h3>群聊管理</h3><p>由插件管理员和群身份规则共同决定。</p><div class="command-list"><span>禁言 @成员</span><span>禁 @成员 1</span><span>解 @成员</span><span>数字撤回</span><span>卡片撤回</span><span>合并转发撤回</span></div></article></div></section>
        <section id="page-settings" class="page-view" data-page="settings" hidden><article id="settings" class="console-card standalone-card"><h2>系统设置</h2><p class="card-subtitle">UC、夸克和百度账号及上传目录请在“网盘配置”中管理；数据库连接参数可在这里查看和编辑。</p><div class="runtime-detail settings-db-grid"><div class="status-item"><span>数据库连接状态</span><strong id="settings-db-status">读取中</strong></div><div class="status-item"><span>当前数据库名</span><strong id="settings-db-name">读取中</strong></div></div><div id="database-config-editor" class="config-editor"><div class="empty">正在读取数据库配置...</div></div><p class="card-subtitle settings-db-note">地址、端口、用户名和数据库名会显示在登录后的控制台；密码只写入、不回显，留空表示保持现有密码。修改并保存后需要重载插件生效。</p></article></section>

        <section id="page-messages" class="page-view" data-page="messages" hidden>
          <div class="msg-shell" id="msg-shell">
            <div class="msg-panel chat-list-panel" id="msg-chat-list-panel">
              <button class="msg-panel-toggle msg-list-collapse" id="msg-list-collapse" type="button" aria-expanded="true" aria-label="收起会话列表" title="收起会话列表">‹</button>
              <div class="msg-list-head">
                <div class="msg-filter" id="msg-filter" role="tablist" aria-label="消息过滤">
                  <button type="button" data-msg-filter="all" class="active">聊天记录</button>
                  <button type="button" data-msg-filter="group">群聊</button>
                  <button type="button" data-msg-filter="user">私聊</button>
                </div>
                <div class="msg-search">
                  <input id="msg-search-input" type="text" placeholder="搜索群名或 openid" aria-label="搜索会话">
                  <button id="msg-search-btn" type="button">搜索</button>
                </div>
              </div>
              <div class="msg-chats" id="msg-chats"><div class="msg-empty">正在加载会话...</div></div>
              <button class="msg-list-resizer" id="msg-list-resizer" type="button" aria-label="拖动调整会话列表宽度" title="拖动调整会话列表宽度"><span aria-hidden="true"></span></button>
            </div>
            <div class="msg-panel msg-work">
              <div class="msg-head">
                <button class="msg-mobile-back" id="msg-mobile-back" type="button" hidden aria-label="返回会话列表" title="返回会话列表"><span aria-hidden="true">‹</span></button>
                <div style="min-width:0">
                  <div class="msg-head-name" id="msg-head-name">选择一个会话</div>
                  <div class="msg-head-sub" id="msg-head-sub">左侧列表选择群聊或私聊查看消息</div>
                  <span class="msg-admin-tag" id="msg-admin-tag" hidden>· 机器人是管理员</span>
                </div>
                <div class="msg-head-actions">
                  <label class="msg-pan-account-control" id="msg-pan-account-wrap" hidden><span>网盘账号</span><select id="msg-pan-account-select" aria-label="选择当前群的网盘账号" disabled><option value="">读取中</option></select></label>
                  <button class="msg-btn" id="msg-ad-switch" type="button" hidden title="切换当前群的广告拦截">广告拦截</button>
                  <button class="msg-btn" id="msg-refresh-info" type="button" hidden>刷新群信息</button>
                  <button class="msg-btn" id="msg-remark" type="button" hidden>群备注</button>
                  <button class="msg-btn" id="msg-group-settings-open" type="button" hidden aria-label="打开当前群聊设置" aria-expanded="false" aria-controls="msg-group-settings">⚙ 设置</button>
                  <button class="msg-btn" id="msg-reload" type="button">刷新</button>
                </div>
              </div>
              <div class="msg-multi-bar" id="msg-multi-bar" hidden><span id="msg-multi-count">已选 0 条</span><button class="msg-btn primary" id="msg-multi-recall" type="button">撤回选中</button><button class="msg-btn" id="msg-multi-cancel" type="button">取消</button></div>
               <div class="msg-body-wrap" id="msg-body-wrap">
                 <div class="msg-body" id="msg-body"><div class="msg-empty">从左侧选择会话开始查看</div></div>
                 <button class="msg-new-messages" id="msg-new-messages" type="button" hidden title="回到底部查看最新消息"><span class="msg-new-messages-dot" aria-hidden="true"></span><span id="msg-new-messages-label">有新消息</span><span class="msg-new-messages-arrow" aria-hidden="true">↓</span></button>
              </div>
              <div class="msg-composer" id="msg-composer" hidden>
                <button class="msg-composer-resizer" id="msg-composer-resizer" type="button" aria-label="拖动调整编辑区高度" title="拖动调整编辑区高度"><span aria-hidden="true"></span></button>
                <div class="msg-composer-topbar">
                  <button class="msg-panel-toggle msg-composer-toggle" id="msg-composer-toggle" type="button" aria-expanded="true" aria-label="收起编辑区" title="收起编辑区">⌄</button>
                  <label class="msg-tool-btn" title="选择图片" id="msg-img-pick" aria-label="选择图片">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                    <input id="msg-img-file" type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden>
                  </label>
                  <label class="msg-tool-btn" title="选择视频" id="msg-video-pick" aria-label="选择视频">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="13" height="14" rx="2"/><path d="m16 10 5-3v10l-5-3z"/></svg>
                    <input id="msg-video-file" type="file" accept="video/mp4,video/*" hidden>
                  </label>
                  <label class="msg-tool-btn" title="选择文件" id="msg-file-pick" aria-label="选择文件">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><path d="M9 13h6M9 17h6"/></svg>
                    <input id="msg-attachment-file" type="file" accept="*/*" hidden>
                  </label>
                  <span class="msg-composer-top-hint">图片、视频或文件</span>
                </div>
                <div class="msg-composer-mode" hidden>
                  <select id="msg-send-mode" aria-label="发送方式">
                    <option value="default">默认（全量群主动/其他被动）</option>
                    <option value="passive">被动（msg_id）</option>
                    <option value="active">主动</option>
                    <option value="custom_msg_id">自定义 msg_id</option>
                    <option value="custom_event_id">自定义事件 ID</option>
                  </select>
                  <input id="msg-custom-id" type="text" placeholder="自定义 msg_id / 事件 ID" hidden>
                </div>
                <div class="msg-extra" id="msg-extra" hidden></div>
                <div class="msg-composer-tabs" id="msg-composer-tabs" hidden>
                  <button type="button" data-msg-type="text" class="active">文本</button>
                  <button type="button" data-msg-type="markdown">Markdown</button>
                  <button type="button" data-msg-type="media">媒体</button>
                  <button type="button" data-msg-type="ark">ARK模板</button>
                  <button type="button" data-msg-type="card">图文卡片</button>
                </div>
                <div class="msg-input-box" id="msg-input-box">
                  <div class="msg-quote-preview" id="msg-quote-preview" hidden><span class="msg-quote-text" id="msg-quote-text"></span><button class="msg-action" id="msg-quote-clear" type="button" title="取消引用" aria-label="取消引用">×</button></div>
                  <div class="msg-attachment-inline" id="msg-media-inline" hidden>
                    <span class="msg-attachment-icon" id="msg-media-icon" aria-hidden="true">□</span>
                    <span class="msg-attachment-name" id="msg-media-name">待发送附件</span>
                    <button class="msg-img-remove" id="msg-media-clear" type="button" aria-label="移除附件">×</button>
                  </div>
                  <div id="msg-editor" class="msg-editor" contenteditable="true" role="textbox" aria-multiline="true" aria-autocomplete="list" aria-haspopup="listbox" aria-controls="msg-mention-picker" aria-expanded="false" data-placeholder="输入消息内容...（回车发送，Ctrl+Enter 换行）" aria-label="消息内容"></div>
                </div>
                <div class="msg-toolbar">
                  <span style="flex:1"></span>
                  <button class="msg-btn primary" id="msg-send" type="button">发送</button>
                </div>
              </div>
              <div class="msg-group-settings" id="msg-group-settings" hidden>
                <button class="msg-group-mask" id="msg-group-settings-mask" type="button" aria-label="关闭群聊设置"></button>
                <aside class="msg-group-drawer" role="dialog" aria-modal="true" aria-labelledby="msg-group-settings-title" tabindex="-1">
                  <div class="msg-group-drawer-head"><div><strong id="msg-group-settings-title">群聊设置</strong><small id="msg-group-settings-name"></small></div><button class="msg-group-close" id="msg-group-settings-close" type="button" aria-label="关闭群聊设置">×</button></div>
                  <div class="msg-group-tabs" id="msg-group-settings-tabs" role="tablist" aria-label="群聊设置分类"><button type="button" id="msg-group-tab-basic" data-group-tab="basic" class="active" role="tab" aria-selected="true" aria-controls="msg-group-basic">基础设置</button><button type="button" id="msg-group-tab-members" data-group-tab="members" role="tab" aria-selected="false" aria-controls="msg-group-members">群成员</button><button type="button" id="msg-group-tab-mutes" data-group-tab="mutes" role="tab" aria-selected="false" aria-controls="msg-group-mutes">禁言状态</button><button type="button" id="msg-group-tab-blacklist" data-group-tab="blacklist" role="tab" aria-selected="false" aria-controls="msg-group-blacklist">黑名单</button></div>
                  <div class="msg-group-body">
                    <section class="msg-group-pane" id="msg-group-basic" role="tabpanel" aria-labelledby="msg-group-tab-basic">
                      <div class="msg-group-summary" id="msg-group-summary"></div><div class="msg-group-status" id="msg-group-basic-status" role="status"></div>
                      <div class="msg-group-profile" aria-label="群资料">
                        <strong class="msg-group-profile-title">群资料</strong>
                        <dl><dt>群简介</dt><dd class="msg-group-profile-memo" id="msg-group-profile-memo">未设置</dd><dt>群分类</dt><dd id="msg-group-profile-class">未设置</dd><dt>群标签</dt><dd class="msg-group-profile-tags" id="msg-group-profile-tags"><span class="msg-group-profile-empty">暂无标签</span></dd></dl>
                      </div>
                      <label class="msg-group-field">本群备注<input id="msg-group-remark-name" maxlength="128" type="text" placeholder="仅改变本控制台显示的群名" disabled></label>
                      <label class="msg-group-field">群号<input id="msg-group-remark-qq" maxlength="12" inputmode="numeric" type="text" placeholder="用于显示群头像，可留空" disabled></label>
                      <button class="msg-btn primary" id="msg-group-basic-save" type="button" disabled>保存本群设置</button>
                      <label class="msg-group-toggle"><span>广告拦截<small>只对当前群生效，其他群保持原设置</small></span><input id="msg-group-ad-enabled" type="checkbox" aria-label="当前群广告拦截" disabled></label>
                    </section>
                    <section class="msg-group-pane" id="msg-group-mutes" role="tabpanel" aria-labelledby="msg-group-tab-mutes" hidden>
                      <div class="msg-group-tools"><span>当前群聊的禁言状态</span><button class="msg-btn" id="msg-group-mutes-refresh" type="button">刷新</button></div>
                      <div class="msg-group-status" id="msg-group-mutes-status" role="status">尚未查询</div>
                      <div class="msg-group-mute-card"><h4>全员禁言</h4><strong id="msg-group-mutes-mode">未知状态</strong><small id="msg-group-mutes-checked"></small></div>
                      <div class="msg-group-mute-card"><h4>定时禁言</h4><div id="msg-group-mutes-schedules"><span class="msg-group-profile-empty">尚未查询</span></div></div>
                      <div class="msg-group-mute-card"><h4>周期禁言 <small>北京时间</small></h4><div id="msg-group-mutes-recurring"><span class="msg-group-profile-empty">尚未查询</span></div></div>
                      <div class="msg-group-mute-card"><h4>禁言成员 <small id="msg-group-mutes-count"></small></h4><div id="msg-group-mutes-members"><span class="msg-group-profile-empty">尚未查询</span></div></div>
                    </section>
                    <section class="msg-group-pane" id="msg-group-members" role="tabpanel" aria-labelledby="msg-group-tab-members" hidden>
                      <div class="msg-group-status" id="msg-group-members-status" role="status"></div>
                      <div class="msg-group-tools"><label class="msg-group-select-all"><input id="msg-group-members-all" type="checkbox">本页</label><span id="msg-group-members-count">已选 0 / 20</span><button class="msg-btn" id="msg-group-members-refresh" type="button">刷新</button></div>
                      <div class="msg-group-member-detail" id="msg-group-member-detail" hidden></div><div id="msg-group-members-list"></div>
                      <div class="msg-group-pagination"><button class="msg-btn" id="msg-group-members-prev" type="button" disabled>上一页</button><span id="msg-group-members-page">第 1 页 · 每页 30 人</span><button class="msg-btn" id="msg-group-members-next" type="button" disabled>下一页</button></div>
                      <div class="msg-group-batch"><label><input id="msg-group-remove-blacklist" type="checkbox">移除后同时加入本群黑名单</label><button class="msg-btn danger" id="msg-group-members-remove" type="button" disabled>移除选中的成员</button></div>
                    </section>
                    <section class="msg-group-pane" id="msg-group-blacklist" role="tabpanel" aria-labelledby="msg-group-tab-blacklist" hidden>
                      <div class="msg-group-status" id="msg-group-blacklist-status" role="status"></div><p class="msg-group-status">手动添加仅限已离群用户；在群成员可在移除时同时加入黑名单。</p>
                      <div class="msg-group-blacklist-add"><input id="msg-group-blacklist-openid" type="text" maxlength="128" placeholder="输入已离群成员的 OpenID" aria-label="黑名单成员 OpenID" disabled><button class="msg-btn" id="msg-group-blacklist-add" type="button" disabled>添加</button></div>
                      <div class="msg-group-tools"><label class="msg-group-select-all"><input id="msg-group-blacklist-all" type="checkbox">本页</label><span id="msg-group-blacklist-count">已选 0 / 20</span><button class="msg-btn" id="msg-group-blacklist-refresh" type="button">刷新</button></div><div id="msg-group-blacklist-list"></div>
                      <div class="msg-group-pagination"><button class="msg-btn" id="msg-group-blacklist-prev" type="button" disabled>上一页</button><span id="msg-group-blacklist-page">第 1 页 · 每页 20 人</span><button class="msg-btn" id="msg-group-blacklist-next" type="button" disabled>下一页</button></div>
                      <div class="msg-group-batch"><button class="msg-btn" id="msg-group-blacklist-remove" type="button" disabled>解除选中的黑名单</button></div>
                    </section>
                  </div>
                </aside>
              </div>
            </div>
          </div>
          <div class="msg-raw-modal" id="msg-raw-modal" hidden><div class="msg-raw-box" role="dialog" aria-modal="true" aria-labelledby="msg-raw-title" tabindex="-1"><div class="msg-raw-head"><strong id="msg-raw-title">消息原始数据</strong><div class="msg-raw-actions"><button class="msg-raw-copy" id="msg-raw-copy" type="button">复制</button><button id="msg-raw-close" type="button" aria-label="关闭原始数据">×</button></div></div><div class="msg-raw-content" id="msg-raw-content"></div></div></div>
          <div class="msg-remark-modal" id="msg-remark-modal" hidden><div class="msg-remark-box" role="dialog" aria-modal="true" aria-labelledby="msg-remark-title" tabindex="-1"><h3 id="msg-remark-title">群备注</h3><label style="display:block;font-size:11px;color:#999;margin-bottom:4px">备注名（显示在会话列表）</label><input id="msg-remark-name" type="text" placeholder="输入群备注名" style="width:100%;height:34px;padding:0 9px;border:1px solid #e0e1e5;border-radius:8px;font-size:12px;margin-bottom:10px"><label style="display:block;font-size:11px;color:#999;margin-bottom:4px">群号（用于显示群头像，可留空）</label><input id="msg-remark-qq" type="text" placeholder="输入群号" style="width:100%;height:34px;padding:0 9px;border:1px solid #e0e1e5;border-radius:8px;font-size:12px"><div class="msg-mute-actions"><button class="msg-btn" id="msg-remark-delete" type="button" style="color:#e64340;border-color:#f5c2c1;margin-right:auto">删除备注</button><button class="msg-btn" id="msg-remark-cancel" type="button">取消</button><button class="msg-btn primary" id="msg-remark-save" type="button">保存</button></div></div></div>
          <div class="msg-mute-modal" id="msg-mute-modal" hidden><div class="msg-mute-box" role="dialog" aria-modal="true" aria-labelledby="msg-mute-title" tabindex="-1"><h3 id="msg-mute-title">禁言成员</h3><div class="msg-mute-presets" id="msg-mute-presets"><button type="button" data-mute-min="10">10分钟</button><button type="button" data-mute-min="30" class="active">30分钟</button><button type="button" data-mute-min="60">1小时</button><button type="button" data-mute-min="1440">1天</button></div><input id="msg-mute-custom" type="number" min="1" max="30" step="1" placeholder="自定义天数（最多30天）" aria-label="自定义禁言天数，最多30天" style="width:100%;height:32px;padding:0 9px;border:1px solid var(--line);border-radius:8px;font-size:12px"><div class="msg-mute-actions"><button class="msg-btn" id="msg-mute-cancel" type="button">取消</button><button class="msg-btn primary" id="msg-mute-confirm" type="button">确认禁言</button></div></div></div>
        </section>
      </div>
    </main>
    <div class="msg-ctx" id="msg-ctx" hidden></div>
    <div class="msg-mention-picker" id="msg-mention-picker" role="listbox" aria-label="选择提及对象" hidden></div>
    <div class="msg-lightbox" id="msg-lightbox" hidden>
      <div class="msg-lightbox-inner">
        <img id="msg-lightbox-img" alt="图片预览" referrerpolicy="no-referrer">
        <div class="msg-lightbox-hint">点击图片或按 Esc 关闭 · 右键可复制/保存图片</div>
      </div>
      <button class="msg-lightbox-close" id="msg-lightbox-close" type="button" title="关闭">&times;</button>
    </div>
  </div>
  <div id="toast" class="toast" role="status"></div>
"""
脚本标签前缀 = """
  <script>"""
脚本标签后缀 = """</script>
</body>
</html>
"""
_控制台页面缓存: str | None = None


def 渲染控制台页面() -> str:
    global _控制台页面缓存
    if _控制台页面缓存 is None:
        _控制台页面缓存 = (
            页面头部前缀
            + 控制台样式
            + 页面头部后缀
            + 页面主体
            + 脚本标签前缀
            + 控制台脚本
            + 脚本标签后缀
        )
    return _控制台页面缓存
