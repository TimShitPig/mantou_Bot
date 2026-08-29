"""馒头控制台页面模板。

页面结构、样式和脚本分别维护，后端只负责把模板作为 HTML 响应返回。
"""

from .帮助网页样式 import 控制台样式
from .帮助网页脚本 import 控制台脚本

页面头部前缀 = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f8f8ff">
  <title>馒头控制台</title>
  <script>
    (() => {
      try {
        const preference = ['light', 'dark', 'system'].includes(localStorage.getItem('mantou-theme')) ? localStorage.getItem('mantou-theme') : 'system';
        const dark = preference === 'dark' || (preference === 'system' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
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
        <div class="brand"><div class="brand-mark">馒</div><div><strong>QQ机器人后台</strong><span class="version-badge" id="console-version">v5.54.2</span></div></div>
      <div class="top-actions"><span class="status-dot">服务在线</span><label class="theme-control" for="theme-select"><span class="theme-control-label">主题</span><span class="theme-control-icon" aria-hidden="true">◐</span><select id="theme-select" aria-label="主题模式"><option value="system">跟随系统</option><option value="light">浅色模式</option><option value="dark">深色模式</option></select></label><div class="admin-menu"><button class="admin-chip" id="admin-chip" type="button" aria-expanded="false" aria-controls="admin-popover"><span class="admin-avatar" id="admin-avatar">管</span><span id="admin-name">管理员</span><span class="admin-chevron">⌄</span></button><div class="admin-popover" id="admin-popover" hidden><strong id="admin-popover-name">管理员</strong><small id="admin-popover-role">控制台管理员 · 当前会话</small><small id="admin-popover-scope">插件管理员白名单：读取中</small><button class="popover-logout" id="popover-logout" type="button" hidden>退出登录</button></div></div></div>
    </header>
    <aside class="sidebar">
      <div class="profile"><div class="bot-avatar"><span class="avatar-face">•ᴗ•</span></div><strong>馒头助手</strong><span class="online">在线</span></div>
      <div><div class="nav-label">工作台</div><nav class="nav" aria-label="控制台导航">
        <a href="?view=dashboard" data-view="dashboard"><span class="nav-icon">⌂</span>控制台</a>
        <a href="?view=bot" data-view="bot"><span class="nav-icon">⚙</span>机器人配置</a>
        <a href="?view=novels" data-view="novels"><span class="nav-icon">☷</span>小说功能</a>
        <a href="?view=pans" data-view="pans"><span class="nav-icon">▣</span>网盘配置</a>
        <a href="?view=messages" data-view="messages"><span class="nav-icon">✉</span>消息记录</a>
        <a href="?view=runtime" data-view="runtime"><span class="nav-icon">◒</span>运行状态</a>
        <a href="?view=help" data-view="help"><span class="nav-icon">?</span>帮助指令</a>
        <a href="?view=settings" data-view="settings"><span class="nav-icon">⚙</span>系统设置</a>
      </nav></div>
      <div class="sidebar-foot"><span class="spark">✦</span><strong>只显示真实功能</strong><span>未接入后端的数据入口不会伪装成可用按钮。</span></div>
    </aside>
    <main class="main">
      <div class="content">
        <div class="page-heading"><div><p id="page-eyebrow" class="page-kicker">馒头Bot / 管理台</p><h1 id="page-title">控制台</h1><p id="page-subtitle">查看机器人和小说服务的实时状态</p></div><div class="heading-actions"><span id="updated" class="updated-label">--</span></div></div>
        <div id="notice" class="notice"></div>
        <section id="page-dashboard" class="page-view" data-page="dashboard">
          <div class="section-head page-view-head"><div><h2>服务总览</h2><p>快速查看当前功能状态；页面切换请使用左侧导航。</p></div></div>
          <div class="summary-grid">
            <article class="summary-card"><span>小说总开关</span><strong id="metric-global">--</strong><small id="metric-global-meta">加载中</small><span class="text-button">管理小说功能</span></article>
            <article class="summary-card"><span>当前分享网盘</span><strong id="metric-pan">--</strong><small id="metric-pan-meta">加载中</small><span class="text-button">管理网盘</span></article>
            <article class="summary-card"><span>数据库状态</span><strong id="metric-db">--</strong><small id="metric-db-meta">加载中</small><span class="text-button">查看连接配置</span></article>
            <article class="summary-card"><span>插件版本</span><strong id="metric-version">--</strong><small id="metric-version-meta">馒头Bot</small><span class="text-button">查看运行状态</span></article>
          </div>
          <div class="page-grid dashboard-grid"><article class="console-card"><h2>快捷入口</h2><p class="card-subtitle">各项功能均有独立页面，请从左侧导航打开。</p><div class="shortcut-grid"><article class="shortcut-card"><span class="shortcut-icon">⚙</span><strong>机器人配置</strong><small>查看安全摘要与监听配置</small></article><article class="shortcut-card"><span class="shortcut-icon">☷</span><strong>小说功能</strong><small>开关平台和管理员测试模式</small></article><article class="shortcut-card"><span class="shortcut-icon">▣</span><strong>网盘配置</strong><small>选择主分享网盘和查看账号摘要</small></article><article class="shortcut-card"><span class="shortcut-icon">◒</span><strong>运行状态</strong><small>查看服务器实时指标</small></article></div></article><article class="console-card"><h2>当前状态</h2><p class="card-subtitle">最近一次读取：<span id="dashboard-updated">--</span></p><div class="status-list compact-status"><div class="status-item"><span>CPU 占用</span><strong id="dashboard-cpu">--</strong></div><div class="status-item"><span>物理内存</span><strong id="dashboard-memory">--</strong></div><div class="status-item"><span>系统运行时间</span><strong id="dashboard-runtime">--</strong></div></div></article></div>
        </section>

        <section id="page-bot" class="page-view" data-page="bot" hidden>
          <div class="workspace-grid"><div class="workspace-left"><article id="overview" class="console-card"><h2>基本信息</h2><p class="card-subtitle">当前插件的安全摘要和运行身份</p><div class="profile-fields"><div class="profile-field"><span>机器人名称</span><div class="readonly-value"><strong>馒头助手</strong><small>管理台</small></div></div><div class="profile-field"><span>机器人 QQ 号</span><div class="readonly-value"><strong>由适配器提供</strong><small>页面不读取账号信息</small></div></div><div class="profile-field"><span>机器人头像</span><div class="avatar-inline"><div class="bot-avatar"><span class="avatar-face">•ᴗ•</span></div><small>馒头Bot 二次元助手</small></div></div><div class="profile-field"><span>机器人简介</span><div class="readonly-value"><strong>小说下载、网盘分享与群聊管理</strong></div></div><div class="profile-field"><span>运行状态</span><div class="state-line"><span class="online">在线运行</span></div></div></div></article><article id="config" class="console-card"><h2>机器人配置</h2><p class="card-subtitle">管理员白名单和帮助网页账号；敏感字段只写入，不在网页回显。</p><div id="basic-config-editor" class="config-editor"><div class="empty">正在读取配置...</div></div></article><article class="console-card"><h2>QQ阅读登录态</h2><p class="card-subtitle">只保存 ywguid 和 ywkey，不显示原值。</p><div id="qq-auth-editor"><div class="empty">正在读取登录态...</div></div></article></div><div class="workspace-right"><article class="console-card"><h2>安全说明</h2><p class="card-subtitle">页面只展示后端允许的摘要。</p><div class="safe-list"><div><span>登录凭据</span><strong>不返回原文</strong></div><div><span>数据库地址</span><strong>只写不读</strong></div><div><span>网盘 Cookie</span><strong>只写不回显</strong></div><div><span>会话 Cookie</span><strong>仅 HttpOnly 保存</strong></div></div></article></div></div>
        </section>

        <section id="page-novels" class="page-view" data-page="novels" hidden><article id="novels" class="novel-console standalone-card">
          <header class="novel-console-head"><div><span class="novel-overline">NOVEL CONTROL</span><h2>小说功能</h2><p class="card-subtitle">集中管理小说入口和平台状态，下载逻辑保持不变。</p></div><div id="novel-state-pill" class="novel-state-pill"><span class="novel-state-dot"></span><strong>读取中</strong></div></header>
          <div class="novel-control-grid">
            <section class="novel-master-panel"><div class="novel-panel-kicker"><span class="novel-panel-icon">全</span><span>GLOBAL ACCESS</span></div><div class="novel-master-copy"><h3>全部小说功能</h3><p>控制下载、找书和翻页的总入口。关闭后所有平台都会暂停响应。</p></div><div class="novel-master-actions"><div class="novel-master-state"><strong id="novel-master-label">读取中</strong><span id="novel-platform-summary">正在读取平台状态</span></div><button id="global-switch" class="switch" type="button" aria-label="切换全局小说功能"><span></span></button></div></section>
            <section class="novel-test-panel"><div class="novel-panel-kicker"><span class="novel-panel-icon">测</span><span>ADMIN MODE</span></div><h3>管理员测试模式</h3><p>只影响管理员测试，不会绕过普通用户的平台开关。</p><div class="novel-test-actions"><span id="novel-test-label" class="novel-test-note">状态读取中</span><button id="test-switch" class="switch" type="button" aria-label="切换管理员测试模式"><span></span></button></div></section>
          </div>
          <div class="novel-platform-head"><div><span class="novel-platform-overline">PLATFORMS</span><h3>平台开关</h3></div><span id="novel-enabled-count" class="novel-platform-count">-- / -- 已开启</span></div>
          <div id="novel-grid" class="novel-grid"><div class="empty">正在读取小说平台...</div></div>
        </article></section>

        <section id="page-pans" class="page-view" data-page="pans" hidden><article id="pans" class="pan-console console-card standalone-card"><h2>网盘配置</h2><p class="card-subtitle">选择一个网盘页面进行管理，左侧导航负责页面切换；Cookie 只写入，不在网页回显。</p><div class="pan-note"><span>当前主分享网盘</span><strong id="pan-active-label">--</strong></div><div class="pan-tabs" role="tablist" aria-label="网盘配置页面"><button id="pan-tab-UC" class="pan-tab" type="button" role="tab" data-pan-tab="UC" aria-controls="pan-card-UC" aria-selected="false">UC网盘</button><button id="pan-tab-夸克" class="pan-tab" type="button" role="tab" data-pan-tab="夸克" aria-controls="pan-card-夸克" aria-selected="false">夸克网盘</button><button id="pan-tab-百度" class="pan-tab" type="button" role="tab" data-pan-tab="百度" aria-controls="pan-card-百度" aria-selected="false">百度网盘</button></div><div id="pan-grid" class="pan-grid"><div class="empty">正在读取网盘状态...</div></div></article></section>

        <section id="page-runtime" class="page-view" data-page="runtime" hidden><article class="console-card standalone-card"><h2>运行状态</h2><p class="card-subtitle">这些数据来自服务器当前运行状态。</p><div class="runtime-grid runtime-page-grid"><div class="runtime-item"><span>CPU占用</span><strong id="runtime-cpu">--</strong></div><div class="runtime-item"><span>物理内存</span><strong id="runtime-memory">--</strong></div><div class="runtime-item"><span>磁盘空间</span><strong id="runtime-disk">--</strong></div><div class="runtime-item"><span>系统运行时间</span><strong id="runtime-runtime">--</strong></div><div class="runtime-item"><span>操作系统</span><strong id="runtime-os">--</strong></div></div><div class="runtime-detail"><div class="status-item"><span>数据库</span><strong id="runtime-db">--</strong></div><div class="status-item"><span>当前网盘</span><strong id="runtime-pan">--</strong></div><div class="status-item"><span>插件版本</span><strong id="runtime-version">--</strong></div></div></article></section>

        <section id="page-help" class="page-view" data-page="help" hidden><div class="section-head page-view-head"><div><h2>帮助指令</h2><p>这里列出机器人当前支持的聊天指令；网页不代替群聊执行指令。</p></div></div><div class="help-grid"><article class="console-card help-card"><h3>管理与状态</h3><p>需要管理员权限的指令。</p><div class="command-list"><span>帮助</span><span>状态</span><span>小说</span><span>开小说 / 关小说</span><span>开测试 / 关测试</span><span>网盘状态</span><span>换UC / 换夸克 / 换百度</span><span>夸克登录</span></div></article><article class="console-card help-card"><h3>小说入口</h3><p>在群聊或私聊发送链接即可识别。</p><div class="command-list"><span>找关键词</span><span>找书 关键词</span><span>找作者 关键词</span><span>上一页 / 下一页</span><span>小说平台分享链接</span><span>小说分享卡片</span></div></article><article class="console-card help-card"><h3>群聊管理</h3><p>由插件管理员和群身份规则共同决定。</p><div class="command-list"><span>禁言 @成员</span><span>禁 @成员 1</span><span>解 @成员</span><span>数字撤回</span><span>卡片撤回</span><span>合并转发撤回</span></div></article></div></section>
        <section id="page-settings" class="page-view" data-page="settings" hidden><article id="settings" class="console-card standalone-card"><h2>系统设置</h2><p class="card-subtitle">数据库连接和网页服务设置可直接保存；监听端口等变更需要重载插件。</p><div id="settings-editor" class="config-editor"><div class="empty">正在读取设置...</div></div></article></section>

        <section id="page-messages" class="page-view" data-page="messages" hidden>
          <style>
            .msg-shell { display:grid; grid-template-columns:330px minmax(0,1fr); min-height:calc(100vh - 130px); align-items:stretch; background:var(--panel); border:1px solid var(--line); border-radius:14px; box-shadow:var(--shadow); overflow:hidden; }
            .msg-panel { display:flex; flex-direction:column; min-width:0; min-height:0; background:var(--panel); }
            .chat-list-panel { border-right:1px solid var(--line); background:var(--bg); }
            .msg-list-head { display:flex; flex-direction:column; gap:9px; padding:12px 14px 10px; border-bottom:1px solid var(--line); background:var(--panel); }
            .msg-filter { display:flex; gap:3px; padding:3px; background:var(--bg); border:1px solid var(--line); border-radius:10px; }
            .msg-filter button { flex:1 1 0; min-width:0; min-height:28px; padding:0 6px; border:0; border-radius:7px; background:transparent; color:var(--muted); font-size:11.5px; font-weight:700; cursor:pointer; transition:all .15s ease; }
            .msg-filter button.active { background:var(--panel); color:var(--primary); box-shadow:var(--shadow-xs); }
            .msg-search { display:flex; gap:8px; }
            .msg-search input { flex:1 1 0; min-width:0; height:32px; padding:0 12px; border:1px solid var(--line); border-radius:16px; background:var(--bg); color:var(--ink); font-size:12px; outline:none; transition:all .15s ease; }
            .msg-search input:focus { border-color:var(--primary); background:var(--panel); box-shadow:0 0 0 3px var(--primary-glow); }
            .msg-search button { height:32px; padding:0 14px; border:0; border-radius:16px; background:linear-gradient(135deg, var(--primary), var(--primary-dark)); color:#fff; font-size:11.5px; font-weight:750; cursor:pointer; transition:filter .15s ease; }
            .msg-search button:hover { filter:brightness(1.08); }
            .msg-chats { flex:1 1 0; min-height:0; overflow-y:auto; padding:6px; display:flex; flex-direction:column; gap:2px; }
            .msg-chat { display:flex; gap:10px; width:100%; min-height:56px; padding:8px 10px; border:0; border-radius:10px; background:transparent; text-align:left; cursor:pointer; position:relative; transition:background .15s ease, transform .12s ease; }
            .msg-chat:hover { background:var(--primary-soft); }
            .msg-chat.active { background:var(--primary-soft); }
            .msg-chat.active::before { content:""; position:absolute; left:0; top:8px; bottom:8px; width:3.5px; border-radius:0 4px 4px 0; background:var(--primary); }
            .msg-chat-badge { flex:0 0 auto; min-width:18px; height:18px; padding:0 5px; border-radius:9px; background:var(--danger); color:#fff; font-size:11px; font-weight:750; line-height:18px; text-align:center; box-sizing:border-box; box-shadow:0 2px 6px rgba(239,68,68,.35); }
            .msg-chat.pinned { background:rgba(92,84,229,.05); }
            .msg-chat.pinned:hover { background:var(--primary-soft); }
            .msg-chat.pinned.active { background:var(--primary-soft); }
            .msg-chat-top strong.admin,
            .msg-chat.pinned .msg-chat-top strong.admin { color:#dc2626 !important; font-weight:750; }
            .msg-chat-avatar { position:relative; width:40px; height:40px; flex:0 0 auto; display:grid; place-items:center; border-radius:50%; background:var(--primary-soft); color:var(--primary); font-size:13px; font-weight:800; overflow:hidden; border:1.5px solid var(--line); }
            .msg-chat-avatar img { width:100%; height:100%; object-fit:cover; position:relative; z-index:1; border-radius:50%; }
            .msg-chat-avatar .avatar-letter { position:absolute; inset:0; display:grid; place-items:center; font-size:13px; font-weight:800; color:var(--primary); }
            .msg-chat-avatar.avatar-fallback .avatar-letter { position:static; display:grid; }
            .msg-chat-main { flex:1 1 0; min-width:0; align-self:center; }
            .msg-chat-top { display:flex; align-items:center; gap:6px; }
            .msg-chat-top strong { font-size:13px; font-weight:650; color:var(--ink); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            .msg-chat-top small { margin-left:auto; flex:0 0 auto; color:var(--muted); font-size:10px; }
            .msg-chat-sub-row { display:flex; align-items:center; gap:8px; margin-top:3px; min-width:0; }
            .msg-chat-sub { flex:1 1 0; min-width:0; color:var(--muted); font-size:11.5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            .msg-chat-type { display:none; }
            .msg-chat-meta { display:none; }
            .msg-empty { padding:30px 14px; color:var(--muted); font-size:12px; text-align:center; }
            .msg-work { display:flex; flex-direction:column; min-width:0; min-height:0; background:var(--bg); }
            .msg-head { display:flex; align-items:center; gap:12px; padding:12px 18px; background:var(--panel); border-bottom:1px solid var(--line); backdrop-filter:blur(8px); }
            .msg-head-name { font-size:15px; font-weight:750; color:var(--ink); }
            .msg-head-name.admin { color:#dc2626 !important; font-weight:750; }
            .msg-head-sub { margin-top:2px; color:var(--muted); font-size:11px; }
            .msg-admin-tag { color:#dc2626; font-size:11px; font-weight:700; }
            .msg-head-actions { margin-left:auto; display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
            .msg-btn { min-height:30px; padding:0 12px; border:1px solid var(--line); border-radius:8px; background:var(--panel); color:var(--ink-secondary); font-size:11.5px; font-weight:650; cursor:pointer; transition:all .15s ease; box-shadow:var(--shadow-xs); }
            .msg-btn:hover { border-color:var(--primary); color:var(--primary); background:var(--primary-soft); }
            .msg-btn.primary { border:0; background:linear-gradient(135deg, var(--primary), var(--primary-dark)); color:#fff; font-weight:750; box-shadow:0 2px 8px var(--primary-glow); }
            .msg-btn.primary:hover { filter:brightness(1.08); }
            .msg-body { flex:1 1 0; min-height:0; overflow-y:auto; padding:18px 20px 12px; background:var(--bg); }
            .msg-day { margin:12px 0; color:var(--soft); font-size:10.5px; font-weight:600; text-align:center; }
            .msg-row { display:flex; gap:10px; margin-bottom:14px; align-items:flex-start; }
            .msg-row.self { flex-direction:row-reverse; }
            .msg-avatar { position:relative; width:38px; height:38px; flex:0 0 auto; display:grid; place-items:center; border-radius:50%; background:var(--primary-soft); color:var(--primary); font-size:12px; font-weight:800; overflow:hidden; border:1px solid var(--line); }
            .msg-avatar img { width:100%; height:100%; object-fit:cover; position:relative; z-index:1; border-radius:50%; }
            .msg-avatar .avatar-letter { position:absolute; inset:0; display:grid; place-items:center; font-size:12px; font-weight:800; color:var(--primary); }
            .msg-avatar.avatar-fallback .avatar-letter { position:static; display:grid; }
            .msg-bubble-wrap { max-width:min(68%, 580px); min-width:0; }
            .msg-row.self .msg-bubble-wrap { display:flex; flex-direction:column; align-items:flex-end; }
            .msg-bubble-name { margin-bottom:4px; color:var(--muted); font-size:10.5px; padding-left:2px; font-weight:600; }
            .msg-row.self .msg-bubble-name { padding-left:0; padding-right:2px; }
            .msg-bubble { padding:9px 13px; border-radius:4px 13px 13px 13px; background:var(--panel); color:var(--ink); font-size:13px; line-height:1.6; word-break:break-word; white-space:pre-wrap; border:1px solid var(--line); box-shadow:var(--shadow-xs); }
            .msg-row.self .msg-bubble { border-radius:13px 4px 13px 13px; background:linear-gradient(135deg, var(--primary), var(--primary-dark)); color:#fff; border:0; box-shadow:0 3px 10px var(--primary-glow); }
            .msg-row.self .msg-bubble .msg-bubble-quote { color:rgba(255,255,255,.85); background:rgba(255,255,255,.18); border-left-color:#fff; }
            .msg-inline-link { color:var(--primary); text-decoration:underline; text-underline-offset:2px; }
            .msg-row.self .msg-inline-link { color:#e0e7ff; }
            .msg-inline-code { padding:1px 5px; border-radius:5px; background:rgba(0,0,0,.06); font:12px/1.4 Consolas,Monaco,monospace; }
            .msg-row.self .msg-inline-code { background:rgba(255,255,255,.2); color:#fff; }
            .msg-command-chip { display:inline; margin:0 2px; padding:0 2px; border:0; border-bottom:1px dashed currentColor; background:transparent; color:inherit; font:inherit; line-height:inherit; cursor:pointer; }
            .msg-command-chip:hover { opacity:.75; }
            .msg-bubble.recalled { color:var(--soft); font-style:italic; background:var(--bg); border-style:dashed; }
            .msg-bubble-quote { margin:-2px 0 6px; padding:6px 9px; border-left:3px solid var(--primary); border-radius:5px; background:var(--primary-soft); color:var(--muted); font-size:11px; }
            .msg-media { margin-top:7px; }
            .msg-image-media { display:flex; flex-direction:column; align-items:flex-start; gap:4px; }
            .msg-image-link { display:block; min-width:24px; min-height:24px; padding:0; border:0; background:transparent; text-align:left; line-height:0; cursor:zoom-in; }
            .msg-media img { max-width:240px; max-height:240px; border-radius:10px; display:block; cursor:zoom-in; transition:transform .14s ease, box-shadow .14s ease; background:var(--bg); border:1px solid var(--line); }
            .msg-media img:hover { transform:scale(1.02); box-shadow:var(--shadow-sm); }
            .msg-file-card { display:flex; align-items:center; gap:10px; min-width:200px; max-width:300px; padding:9px 12px; border-radius:10px; background:var(--bg); border:1px solid var(--line); color:var(--ink); text-decoration:none; transition:background .15s ease; }
            .msg-file-card:hover { background:var(--primary-soft); border-color:var(--primary); }
            .msg-file-icon { width:30px; height:30px; flex:0 0 30px; display:grid; place-items:center; border-radius:8px; background:var(--primary-soft); color:var(--primary); font-size:15px; font-weight:700; }
            .msg-file-info { min-width:0; flex:1; display:flex; flex-direction:column; gap:1px; }
            .msg-file-info strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; font-weight:650; }
            .msg-file-info small { color:var(--muted); font-size:10px; line-height:1.3; }
            .msg-file-action { flex:0 0 auto; color:var(--primary); font-size:10.5px; font-weight:700; }
            .msg-row.self .msg-file-card { background:rgba(255,255,255,.18); border-color:rgba(255,255,255,.3); color:#fff; }
            .msg-row.self .msg-file-card:hover { background:rgba(255,255,255,.28); }
            .msg-row.self .msg-file-info small, .msg-row.self .msg-file-action { color:rgba(255,255,255,.85); }
            .msg-meta { margin-top:4px; color:var(--soft); font-size:9.5px; padding-left:2px; }
            .msg-row.self .msg-meta { text-align:right; padding-left:0; padding-right:2px; }
            .msg-tags { display:inline-flex; gap:4px; margin-left:6px; vertical-align:middle; }
            .msg-tag { display:inline-block; padding:1px 6px; border-radius:4px; font-size:9px; line-height:14px; font-weight:750; }
            .msg-tag.bot { background:var(--pink); color:var(--pink-ink); }
            .msg-tag.role { background:var(--primary-soft); color:var(--primary-dark); }
            .msg-tag.self { background:var(--mint); color:var(--mint-ink); }
            .msg-tag.recalled { background:var(--bg); color:var(--muted); }
            .msg-actions { display:flex; gap:5px; margin-top:5px; }
            .msg-row.self .msg-actions { justify-content:flex-end; }
            .msg-action { padding:2px 8px; min-height:22px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--muted); font-size:10px; font-weight:600; cursor:pointer; }
            .msg-action:hover { background:var(--primary-soft); color:var(--primary-dark); border-color:var(--primary); }
            .msg-composer { display:flex; flex-direction:column; gap:9px; padding:12px 16px 14px; background:var(--panel); border-top:1px solid var(--line); }
            .msg-composer-tabs { display:flex; gap:6px; flex-wrap:wrap; }
            .msg-composer-tabs button { min-height:28px; padding:0 11px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--muted); font-size:11.5px; font-weight:650; cursor:pointer; transition:all .15s ease; }
            .msg-composer-tabs button.active { border-color:var(--primary); color:var(--primary); background:var(--primary-soft); }
            .msg-composer-mode { display:flex; gap:6px; flex-wrap:wrap; align-items:center; }
            .msg-composer-mode select, .msg-composer-mode input { height:30px; padding:0 10px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); font-size:11.5px; outline:none; }
            .msg-composer-mode select:focus, .msg-composer-mode input:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--primary-glow); }
            .msg-input-box { position:relative; border:1px solid var(--line); border-radius:10px; background:var(--panel); transition:border-color .15s, box-shadow .15s; }
            .msg-input-box:focus-within { border-color:var(--primary); box-shadow:0 0 0 3px var(--primary-glow); }
            .msg-textarea { width:100%; min-height:86px; max-height:180px; border:0; outline:none; resize:none; padding:10px 12px; font-size:13px; line-height:1.6; color:var(--ink); background:transparent; box-sizing:border-box; }
            .msg-toolbar { display:flex; align-items:center; gap:8px; padding:0 10px 8px; }
            .msg-tool-btn { display:grid; place-items:center; width:30px; height:30px; border-radius:6px; color:var(--muted); cursor:pointer; transition:all .15s ease; }
            .msg-tool-btn:hover { background:var(--primary-soft); color:var(--primary); }
            .msg-send-row { display:flex; align-items:center; gap:10px; justify-content:flex-end; }
            .msg-send-row .msg-btn.primary { min-height:34px; padding:0 24px; border-radius:9px; }
            .msg-raw-modal, .msg-mute-modal, .msg-remark-modal { position:fixed; inset:0; z-index:100; display:grid; place-items:center; background:rgba(12,16,28,.55); backdrop-filter:blur(6px); padding:20px; }
            .msg-raw-modal[hidden], .msg-mute-modal[hidden], .msg-remark-modal[hidden] { display:none; }
            .msg-raw-box, .msg-mute-box, .msg-remark-box { width:min(500px,100%); background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:20px; box-shadow:var(--shadow-lg); }
            .msg-raw-box { width:min(720px,100%); height:min(640px,78vh); display:flex; flex-direction:column; padding:0; overflow:hidden; }
            .msg-raw-head { display:flex; align-items:center; justify-content:space-between; padding:14px 18px; border-bottom:1px solid var(--line); }
            .msg-raw-head strong { font-size:14px; font-weight:750; color:var(--ink); }
            .msg-raw-head button { border:0; background:transparent; color:var(--muted); font-size:18px; cursor:pointer; }
            .msg-raw-content { flex:1 1 0; min-height:0; overflow:auto; padding:14px 18px; white-space:pre-wrap; word-break:break-all; color:var(--ink); font:12px/1.65 Consolas,Monaco,monospace; }
            .msg-ctx { position:fixed; z-index:120; min-width:150px; padding:5px; background:var(--panel); border:1px solid var(--line); border-radius:10px; box-shadow:var(--shadow-lg); user-select:none; backdrop-filter:blur(8px); }
            .msg-ctx[hidden] { display:none; }
            .msg-ctx-item { display:flex; align-items:center; gap:8px; width:100%; padding:8px 11px; border:0; border-radius:6px; background:transparent; color:var(--ink); font-size:12px; font-weight:600; text-align:left; cursor:pointer; }
            .msg-ctx-item:hover { background:var(--primary-soft); color:var(--primary); }
            .msg-ctx-item.danger:hover { background:var(--danger-soft); color:var(--danger); }
            .msg-ctx-sep { height:1px; margin:4px 6px; background:var(--line); }
            .msg-body-wrap { position:relative; display:flex; flex:1 1 0; min-height:0; overflow:hidden; }
            .msg-new-messages { position:absolute; right:18px; bottom:14px; z-index:3; display:inline-flex; align-items:center; gap:7px; min-height:32px; padding:0 13px; border:1px solid var(--line); border-radius:17px; background:var(--panel); color:var(--primary); box-shadow:var(--shadow-md); font-size:11.5px; font-weight:700; cursor:pointer; }
            .msg-new-messages:hover { transform:translateY(-1px); box-shadow:var(--shadow-lg); }
            .msg-new-messages[hidden] { display:none; }
            .msg-new-messages-dot { width:7px; height:7px; border-radius:50%; background:var(--primary); box-shadow:0 0 0 3px var(--primary-glow); }
            .msg-lightbox { position:fixed; inset:0; z-index:2000; background:rgba(0,0,0,.85); backdrop-filter:blur(10px); display:flex; align-items:center; justify-content:center; padding:28px; }
            .msg-lightbox[hidden] { display:none; }
            .msg-lightbox img { max-width:92vw; max-height:84vh; border-radius:10px; box-shadow:0 8px 40px rgba(0,0,0,.6); object-fit:contain; }

            /* ===== 暗色模式 (Dark Mode) ===== */
            :root[data-theme="dark"] .msg-shell { background:var(--panel); border-color:var(--line); }
            :root[data-theme="dark"] .chat-list-panel { background:#111520; border-right-color:var(--line); }
            :root[data-theme="dark"] .msg-list-head { background:var(--panel); border-bottom-color:var(--line); }
            :root[data-theme="dark"] .msg-filter { background:#111520; border-color:var(--line); }
            :root[data-theme="dark"] .msg-filter button.active { background:var(--panel); color:var(--primary); }
            :root[data-theme="dark"] .msg-search input { background:#111520; border-color:var(--line); color:var(--ink); }
            :root[data-theme="dark"] .msg-search input:focus { border-color:var(--primary); background:var(--panel); }
            :root[data-theme="dark"] .msg-chat:hover { background:var(--panel-hover); }
            :root[data-theme="dark"] .msg-chat.active { background:var(--primary-soft); }
            :root[data-theme="dark"] .msg-chat.pinned { background:#191e2e; }
            :root[data-theme="dark"] .msg-chat-top strong.admin,
            :root[data-theme="dark"] .msg-chat.pinned .msg-chat-top strong.admin { color:#f87171 !important; }
            :root[data-theme="dark"] .msg-work { background:#0e111a; }
            :root[data-theme="dark"] .msg-head { background:var(--panel); border-bottom-color:var(--line); }
            :root[data-theme="dark"] .msg-head-name.admin { color:#f87171 !important; }
            :root[data-theme="dark"] .msg-admin-tag { color:#f87171; }
            :root[data-theme="dark"] .msg-btn { border-color:var(--line); background:var(--panel); color:var(--ink-secondary); }
            :root[data-theme="dark"] .msg-btn:hover { border-color:var(--primary); color:var(--primary); background:var(--primary-soft); }
            :root[data-theme="dark"] .msg-body { background:#0e111a; }
            :root[data-theme="dark"] .msg-bubble { background:var(--panel); border-color:var(--line); color:var(--ink); }
            :root[data-theme="dark"] .msg-bubble.recalled { background:#121622; color:var(--soft); }
            :root[data-theme="dark"] .msg-bubble-quote { border-left-color:var(--primary); background:var(--primary-soft); color:var(--muted); }
            :root[data-theme="dark"] .msg-file-card { background:#161a26; border-color:var(--line); color:var(--ink); }
            :root[data-theme="dark"] .msg-file-card:hover { background:var(--primary-soft); border-color:var(--primary); }
            :root[data-theme="dark"] .msg-composer { background:var(--panel); border-top-color:var(--line); }
            :root[data-theme="dark"] .msg-composer-tabs button { border-color:var(--line); background:var(--panel); color:var(--muted); }
            :root[data-theme="dark"] .msg-composer-tabs button.active { border-color:var(--primary); color:var(--primary); background:var(--primary-soft); }
            :root[data-theme="dark"] .msg-composer-mode select, :root[data-theme="dark"] .msg-composer-mode input { border-color:var(--line); background:var(--panel); color:var(--ink); }
            :root[data-theme="dark"] .msg-input-box { border-color:var(--line); background:var(--panel); }
            :root[data-theme="dark"] .msg-textarea { color:var(--ink); }
            :root[data-theme="dark"] .msg-raw-box, :root[data-theme="dark"] .msg-mute-box, :root[data-theme="dark"] .msg-remark-box { background:var(--panel); border-color:var(--line); }
            :root[data-theme="dark"] .msg-ctx { background:var(--panel); border-color:var(--line); }
            :root[data-theme="dark"] .msg-ctx-sep { background:var(--line); }
            :root[data-theme="dark"] .msg-new-messages { border-color:var(--line); background:var(--panel); color:var(--primary); }
          </style>
          <div class="msg-shell">
            <div class="msg-panel chat-list-panel">
              <div class="msg-list-head">
                <div class="msg-filter" id="msg-filter" role="tablist" aria-label="消息过滤">
                  <button type="button" data-msg-filter="all" class="active">全量</button>
                  <button type="button" data-msg-filter="remark">备注</button>
                  <button type="button" data-msg-filter="group">群聊</button>
                  <button type="button" data-msg-filter="user">私聊</button>
                </div>
                <div class="msg-search">
                  <input id="msg-search-input" type="text" placeholder="搜索群名或 openid" aria-label="搜索会话">
                  <button id="msg-search-btn" type="button">搜索</button>
                </div>
              </div>
              <div class="msg-chats" id="msg-chats"><div class="msg-empty">正在加载会话...</div></div>
            </div>
            <div class="msg-panel msg-work">
              <div class="msg-head">
                <div style="min-width:0">
                  <div class="msg-head-name" id="msg-head-name">选择一个会话</div>
                  <div class="msg-head-sub" id="msg-head-sub">左侧列表选择群聊或私聊查看消息</div>
                  <span class="msg-admin-tag" id="msg-admin-tag" hidden>· 机器人是管理员</span>
                </div>
                <div class="msg-head-actions">
                  <button class="msg-btn" id="msg-ad-switch" type="button" hidden title="切换当前群的广告拦截">广告拦截</button>
                  <button class="msg-btn" id="msg-refresh-info" type="button" hidden>刷新群信息</button>
                  <button class="msg-btn" id="msg-remark" type="button" hidden>群备注</button>
                  <button class="msg-btn" id="msg-reload" type="button">刷新</button>
                </div>
              </div>
              <div class="msg-multi-bar" id="msg-multi-bar" hidden><span id="msg-multi-count">已选 0 条</span><button class="msg-btn primary" id="msg-multi-recall" type="button">撤回选中</button><button class="msg-btn" id="msg-multi-cancel" type="button">取消</button></div>
               <div class="msg-body-wrap" id="msg-body-wrap">
                 <div class="msg-body" id="msg-body"><div class="msg-empty">从左侧选择会话开始查看</div></div>
                 <button class="msg-new-messages" id="msg-new-messages" type="button" hidden title="回到底部查看最新消息"><span class="msg-new-messages-dot" aria-hidden="true"></span><span id="msg-new-messages-label">有新消息</span><span class="msg-new-messages-arrow" aria-hidden="true">↓</span></button>
               </div>
              <div class="msg-composer" id="msg-composer" hidden>
                <div class="msg-composer-mode">
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
                <div class="msg-composer-tabs" id="msg-composer-tabs">
                  <button type="button" data-msg-type="text" class="active">文本</button>
                  <button type="button" data-msg-type="markdown">Markdown</button>
                  <button type="button" data-msg-type="media">媒体</button>
                  <button type="button" data-msg-type="ark">ARK模板</button>
                  <button type="button" data-msg-type="card">图文卡片</button>
                </div>
                <div class="msg-input-box" id="msg-input-box">
                  <div class="msg-quote-preview" id="msg-quote-preview" hidden><b>引用：</b><span class="msg-quote-text" id="msg-quote-text"></span><button class="msg-action" id="msg-quote-clear" type="button">取消引用</button></div>
                  <div class="msg-img-inline" id="msg-img-inline" hidden>
                    <div class="msg-img-chip"><img id="msg-img-thumb" alt="待发送图片"><button class="msg-img-remove" id="msg-img-clear" type="button" aria-label="移除图片">×</button></div>
                  </div>
                  <textarea id="msg-textarea" class="msg-textarea" placeholder="输入消息内容...（回车发送，Ctrl+Enter 换行）" aria-label="消息内容"></textarea>
                </div>
                <div class="msg-toolbar">
                  <label class="msg-tool-btn" title="选择图片" id="msg-img-pick">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                    <input id="msg-img-file" type="file" accept="image/*" hidden>
                  </label>
                  <span id="msg-send-status" style="color:var(--muted);font-size:11px"></span>
                  <span style="flex:1"></span>
                  <button class="msg-btn primary" id="msg-send" type="button">发送</button>
                </div>
              </div>
            </div>
          </div>
          <div class="msg-raw-modal" id="msg-raw-modal" hidden><div class="msg-raw-box"><div class="msg-raw-head"><strong>消息原始数据</strong><button id="msg-raw-close" type="button">×</button></div><div class="msg-raw-content" id="msg-raw-content"></div></div></div>
          <div class="msg-remark-modal" id="msg-remark-modal" hidden><div class="msg-remark-box"><h3>群备注</h3><label style="display:block;font-size:11px;color:#999;margin-bottom:4px">备注名（显示在会话列表）</label><input id="msg-remark-name" type="text" placeholder="输入群备注名" style="width:100%;height:34px;padding:0 9px;border:1px solid #e0e1e5;border-radius:8px;font-size:12px;margin-bottom:10px"><label style="display:block;font-size:11px;color:#999;margin-bottom:4px">群号（用于显示群头像，可留空）</label><input id="msg-remark-qq" type="text" placeholder="输入群号" style="width:100%;height:34px;padding:0 9px;border:1px solid #e0e1e5;border-radius:8px;font-size:12px"><div class="msg-mute-actions"><button class="msg-btn" id="msg-remark-delete" type="button" style="color:#e64340;border-color:#f5c2c1;margin-right:auto">删除备注</button><button class="msg-btn" id="msg-remark-cancel" type="button">取消</button><button class="msg-btn primary" id="msg-remark-save" type="button">保存</button></div></div></div>
          <div class="msg-mute-modal" id="msg-mute-modal" hidden><div class="msg-mute-box"><h3 id="msg-mute-title">禁言成员</h3><div class="msg-mute-presets" id="msg-mute-presets"><button type="button" data-mute-min="10">10分钟</button><button type="button" data-mute-min="30" class="active">30分钟</button><button type="button" data-mute-min="60">1小时</button><button type="button" data-mute-min="1440">1天</button></div><input id="msg-mute-custom" type="number" min="1" max="43200" placeholder="自定义分钟" style="width:100%;height:32px;padding:0 9px;border:1px solid var(--line);border-radius:8px;font-size:12px"><div class="msg-mute-actions"><button class="msg-btn" id="msg-mute-cancel" type="button">取消</button><button class="msg-btn primary" id="msg-mute-confirm" type="button">确认禁言</button></div></div></div>
        </section>
      </div>
    </main>
    <div class="msg-ctx" id="msg-ctx" hidden></div>
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


def 渲染控制台页面() -> str:
    return (
        页面头部前缀
        + 控制台样式
        + 页面头部后缀
        + 页面主体
        + 脚本标签前缀
        + 控制台脚本
        + 脚本标签后缀
    )
