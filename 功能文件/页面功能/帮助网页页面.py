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
  <script src="https://ssl.captcha.qq.com/TCaptcha.js"></script>
  <script>
    (() => {
      try {
        const preference = localStorage.getItem('mantou-theme') === 'dark' ? 'dark' : 'light';
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
        <div class="brand"><div class="brand-mark">馒</div><div><strong>QQ机器人后台</strong><span class="version-badge" id="console-version">v6.1.53</span></div></div>
      <div class="top-actions"><span class="status-dot">服务在线</span><div class="theme-control" role="group" aria-label="主题模式"><span class="theme-control-label">主题</span><button id="theme-toggle" class="theme-toggle-button" type="button" aria-label="切换到深色模式" title="切换到深色模式" aria-pressed="false"><span class="theme-control-icon" aria-hidden="true">◐</span></button><label class="theme-select-wrap" for="theme-select"><select id="theme-select" aria-label="选择主题模式"><option value="light">浅色模式</option><option value="dark">深色模式</option></select></label></div><div class="admin-menu"><button class="admin-chip" id="admin-chip" type="button" aria-expanded="false" aria-controls="admin-popover"><span class="admin-avatar" id="admin-avatar">管</span><span id="admin-name">管理员</span><span class="admin-chevron">⌄</span></button><div class="admin-popover" id="admin-popover" hidden><strong id="admin-popover-name">管理员</strong><small id="admin-popover-role">控制台管理员 · 当前会话</small><small id="admin-popover-scope">插件管理员白名单：读取中</small><button class="popover-logout" id="popover-logout" type="button" hidden>退出登录</button></div></div></div>
    </header>
    <aside class="sidebar">
      <div class="profile"><div class="bot-avatar" data-bot-avatar><span class="avatar-face">•ᴗ•</span></div><strong data-bot-name>馒头助手</strong><span class="online">在线</span></div>
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
          <div class="section-head page-view-head"><div><h2>服务总览</h2><p>快速查看当前功能状态，也可以从快捷入口直接打开页面。</p></div></div>
          <div class="summary-grid">
            <article class="summary-card"><span>小说总开关</span><strong id="metric-global">--</strong><small id="metric-global-meta">加载中</small><button class="text-button" type="button" data-view="novels">管理小说功能</button></article>
            <article class="summary-card"><span>当前分享网盘</span><strong id="metric-pan">--</strong><small id="metric-pan-meta">加载中</small><button class="text-button" type="button" data-view="pans">管理网盘</button></article>
            <article class="summary-card"><span>数据库状态</span><strong id="metric-db">--</strong><small id="metric-db-meta">加载中</small><button class="text-button" type="button" data-view="settings">查看连接配置</button></article>
            <article class="summary-card"><span>插件版本</span><strong id="metric-version">--</strong><small id="metric-version-meta">馒头Bot</small><button class="text-button" type="button" data-view="runtime">查看运行状态</button></article>
          </div>
          <div class="page-grid dashboard-grid"><article class="console-card"><h2>快捷入口</h2><p class="card-subtitle">点击入口直接打开对应功能页面。</p><div class="shortcut-grid"><button class="shortcut-card" type="button" data-view="bot"><span class="shortcut-icon">⚙</span><strong>机器人配置</strong><small>查看安全摘要与监听配置</small></button><button class="shortcut-card" type="button" data-view="novels"><span class="shortcut-icon">☷</span><strong>小说功能</strong><small>开关平台和管理员测试模式</small></button><button class="shortcut-card" type="button" data-view="pans"><span class="shortcut-icon">▣</span><strong>网盘配置</strong><small>选择主分享网盘和查看账号摘要</small></button><button class="shortcut-card" type="button" data-view="runtime"><span class="shortcut-icon">◒</span><strong>运行状态</strong><small>查看服务器实时指标</small></button></div></article><article class="console-card"><h2>当前状态</h2><p class="card-subtitle">最近一次读取：<span id="dashboard-updated">--</span></p><div class="status-list compact-status"><div class="status-item"><span>CPU 占用</span><strong id="dashboard-cpu">--</strong></div><div class="status-item"><span>物理内存</span><strong id="dashboard-memory">--</strong></div><div class="status-item"><span>系统运行时间</span><strong id="dashboard-runtime">--</strong></div></div></article></div>
        </section>

        <section id="page-bot" class="page-view" data-page="bot" hidden>
          <div class="workspace-grid"><div class="workspace-left"><article id="overview" class="console-card"><h2>基本信息</h2><p class="card-subtitle">当前插件的安全摘要和运行身份</p><div class="profile-fields"><div class="profile-field"><span>机器人名称</span><div class="readonly-value"><strong data-bot-name>馒头助手</strong><small>来自 QQ 官方资料</small></div></div><div class="profile-field"><span>机器人 QQ 号</span><div class="readonly-value"><strong data-bot-id>由适配器提供</strong><small>页面不读取账号信息</small></div></div><div class="profile-field"><span>机器人头像</span><div class="avatar-inline"><div class="bot-avatar" data-bot-avatar><span class="avatar-face">•ᴗ•</span></div><small>QQ 官方资料头像</small></div></div><div class="profile-field"><span>机器人简介</span><div class="readonly-value"><strong>小说下载、网盘分享与群聊管理</strong></div></div><div class="profile-field"><span>运行状态</span><div class="state-line"><span class="online">在线运行</span></div></div></div></article><article id="config" class="console-card"><h2>机器人配置</h2><p class="card-subtitle">管理员白名单和帮助网页账号；敏感字段只写入，不在网页回显。</p><div id="basic-config-editor" class="config-editor"><div class="empty">正在读取配置...</div></div></article><article class="console-card"><h2>QQ阅读登录态</h2><p class="card-subtitle">只保存 ywguid 和 ywkey，不显示原值。</p><div id="qq-auth-editor"><div class="empty">正在读取登录态...</div></div></article></div><div class="workspace-right"><article class="console-card"><h2>安全说明</h2><p class="card-subtitle">页面只展示后端允许的摘要。</p><div class="safe-list"><div><span>登录凭据</span><strong>不返回原文</strong></div><div><span>数据库地址</span><strong>只写不读</strong></div><div><span>网盘 Cookie</span><strong>只写不回显</strong></div><div><span>会话 Cookie</span><strong>仅 HttpOnly 保存</strong></div></div></article></div></div>
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

        <section id="page-pans" class="page-view" data-page="pans" hidden>
          <div id="pans" class="pan-page">
            <header class="pan-page-head">
              <div class="pan-heading-copy"><span class="pan-page-overline">网盘管理</span><h2>网盘中心</h2><p>选择一个网盘，管理上传、账号和分享设置。</p></div>
              <div class="pan-live"><span class="pan-live-dot"></span><div><small>默认分享</small><strong id="pan-active-label">--</strong></div></div>
            </header>
            <div class="pan-summary-strip" aria-label="网盘摘要">
              <div class="pan-summary-item"><span>已启用</span><strong id="pan-enabled-count">--</strong><small>参与小说分享</small></div>
              <div class="pan-summary-item"><span>已配置</span><strong id="pan-configured-count">--</strong><small>登录态可用</small></div>
              <div class="pan-summary-item"><span>账号总数</span><strong id="pan-account-count">--</strong><small>按平台独立保存</small></div>
              <div class="pan-summary-item"><span>上传方式</span><strong id="pan-upload-mode">--</strong><small>完成后生成分享链接</small></div>
            </div>
            <nav class="pan-tabs" role="tablist" aria-label="选择网盘">
              <button id="pan-tab-UC" class="pan-tab" type="button" role="tab" data-pan-tab="UC" aria-controls="pan-card-UC" aria-selected="false"><span class="pan-tab-mark pan-tab-uc">U</span><span>UC网盘</span></button>
              <button id="pan-tab-夸克" class="pan-tab" type="button" role="tab" data-pan-tab="夸克" aria-controls="pan-card-夸克" aria-selected="false"><span class="pan-tab-mark pan-tab-quark">夸</span><span>夸克网盘</span></button>
              <button id="pan-tab-百度" class="pan-tab" type="button" role="tab" data-pan-tab="百度" aria-controls="pan-card-百度" aria-selected="false"><span class="pan-tab-mark pan-tab-baidu">度</span><span>百度网盘</span></button>
            </nav>
            <div id="pan-grid" class="pan-grid"><div class="empty">正在读取网盘状态...</div></div>
          </div>
        </section>

        <section id="page-runtime" class="page-view" data-page="runtime" hidden><article class="console-card standalone-card"><h2>运行状态</h2><p class="card-subtitle">这些数据来自服务器当前运行状态。</p><div class="runtime-grid runtime-page-grid"><div class="runtime-item"><span>CPU占用</span><strong id="runtime-cpu">--</strong></div><div class="runtime-item"><span>物理内存</span><strong id="runtime-memory">--</strong></div><div class="runtime-item"><span>磁盘空间</span><strong id="runtime-disk">--</strong></div><div class="runtime-item"><span>系统运行时间</span><strong id="runtime-runtime">--</strong></div><div class="runtime-item"><span>操作系统</span><strong id="runtime-os">--</strong></div></div><div class="runtime-detail"><div class="status-item"><span>数据库</span><strong id="runtime-db">--</strong></div><div class="status-item"><span>当前网盘</span><strong id="runtime-pan">--</strong></div><div class="status-item"><span>插件版本</span><strong id="runtime-version">--</strong></div></div></article></section>

        <section id="page-help" class="page-view" data-page="help" hidden><div class="section-head page-view-head"><div><h2>帮助指令</h2><p>这里列出机器人当前支持的聊天指令；网页不代替群聊执行指令。</p></div></div><div class="help-grid"><article class="console-card help-card"><h3>管理与状态</h3><p>需要管理员权限的指令。</p><div class="command-list"><span>帮助</span><span>状态</span><span>小说</span><span>开小说 / 关小说</span><span>开测试 / 关测试</span><span>网盘状态</span><span>换UC / 换夸克 / 换百度</span><span>夸克登录</span></div></article><article class="console-card help-card"><h3>小说入口</h3><p>在群聊或私聊发送链接即可识别。</p><div class="command-list"><span>找关键词</span><span>找书 关键词</span><span>找作者 关键词</span><span>上一页 / 下一页</span><span>小说平台分享链接</span><span>小说分享卡片</span></div></article><article class="console-card help-card"><h3>群聊管理</h3><p>由插件管理员和群身份规则共同决定。</p><div class="command-list"><span>禁言 @成员</span><span>禁 @成员 1</span><span>解 @成员</span><span>数字撤回</span><span>卡片撤回</span><span>合并转发撤回</span></div></article></div></section>
        <section id="page-settings" class="page-view" data-page="settings" hidden><article id="settings" class="console-card standalone-card"><h2>系统设置</h2><p class="card-subtitle">数据库连接和网页服务设置可直接保存；监听端口等变更需要重载插件。</p><div id="settings-editor" class="config-editor"><div class="empty">正在读取设置...</div></div></article></section>

        <section id="page-messages" class="page-view" data-page="messages" hidden>
          <style>
             .msg-shell { --msg-list-width:340px; display:grid; grid-template-columns:minmax(220px,var(--msg-list-width)) minmax(0,1fr); height:calc(100vh - 126px); min-height:520px; align-items:stretch; background:#fff; border:1px solid #e8e9ec; border-radius:10px; overflow:hidden; transition:grid-template-columns .22s ease; }
             .msg-panel { display:flex; flex-direction:column; min-width:0; min-height:0; background:#fff; }
             .chat-list-panel { position:relative; border-right:1px solid #e8e9ec; background:#fafafa; }
            .msg-list-head { display:flex; flex-direction:column; gap:8px; padding:10px 48px 8px 12px; border-bottom:1px solid #e8e9ec; background:#fff; }
            .msg-filter { display:flex; gap:2px; padding:2px; background:#f2f3f5; border-radius:8px; }
            .msg-filter button { flex:1 1 0; min-width:0; min-height:26px; padding:0 4px; border:0; border-radius:6px; background:transparent; color:#666; font-size:11px; font-weight:600; cursor:pointer; }
            .msg-filter button.active { background:#fff; color:#12b7f5; box-shadow:0 1px 3px rgba(0,0,0,.08); }
            .msg-search { display:flex; gap:6px; }
            .msg-search input { flex:1 1 0; min-width:0; height:30px; padding:0 10px; border:1px solid transparent; border-radius:15px; background:#f2f3f5; color:#333; font-size:12px; outline:none; transition:all .15s ease; }
            .msg-search input:focus { border-color:#12b7f5; background:#fff; }
            .msg-search button { height:30px; padding:0 12px; border:0; border-radius:15px; background:#12b7f5; color:#fff; font-size:11px; font-weight:700; cursor:pointer; }
            .msg-chats { flex:1 1 0; min-height:0; overflow-y:auto; padding:4px 6px; overscroll-behavior:contain; overflow-anchor:none; scrollbar-gutter:stable; }
            .msg-chat-divider { margin:6px 6px 2px; padding:7px 4px 4px; border-top:1px solid #e8e9ec; color:#9a9fa8; font-size:10px; font-weight:650; line-height:1.2; }
            .msg-chat-divider:first-child { margin-top:0; border-top:0; }
            .msg-chat { display:flex; gap:10px; width:100%; min-height:56px; padding:8px 10px; border:0; border-radius:8px; background:transparent; text-align:left; cursor:pointer; transition:background .12s ease; content-visibility:auto; contain-intrinsic-size:56px; }
            .msg-chat:hover { background:#ececee; }
            .msg-chat.active { background:#dbeafd; }
            .msg-chat-badge { flex:0 0 auto; min-width:18px; height:18px; padding:0 5px; border-radius:9px; background:#fa5151; color:#fff; font-size:11px; font-weight:700; line-height:18px; text-align:center; box-sizing:border-box; }
            .msg-chat.pinned { background:#e3ecf7; }
            .msg-chat.pinned:hover { background:#d6e4f4; }
            .msg-chat.pinned.active { background:#cfe0f2; }
            .msg-chat.pinned .msg-chat-top strong { color:#1f5fb0; }
            .msg-chat.pinned .msg-chat-top small { color:#6f8db8; }
            .msg-chat-top strong.admin,
            .msg-chat.pinned .msg-chat-top strong.admin { color:#dc2626 !important; font-weight:700; }
            .msg-chat-avatar { position:relative; width:40px; height:40px; flex:0 0 auto; display:grid; place-items:center; border-radius:50%; background:#cfe3fb; color:#3a7bd5; font-size:14px; font-weight:800; overflow:hidden; }
            .msg-chat-avatar img { width:100%; height:100%; object-fit:cover; position:relative; z-index:1; border-radius:50%; }
            .msg-chat-avatar .avatar-letter { position:absolute; inset:0; display:grid; place-items:center; font-size:14px; font-weight:800; color:#3a7bd5; }
            .msg-chat-avatar.avatar-fallback .avatar-letter { position:static; display:grid; }
            .msg-chat-main { flex:1 1 0; min-width:0; align-self:center; }
            .msg-chat-top { display:flex; align-items:center; gap:6px; }
            .msg-chat-top strong { font-size:13px; font-weight:600; color:#222; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            .msg-chat-top small { margin-left:auto; flex:0 0 auto; color:#999; font-size:10px; }
            .msg-chat-sub-row { display:flex; align-items:center; gap:8px; margin-top:3px; min-width:0; }
            .msg-chat-sub { flex:1 1 0; min-width:0; color:#999; font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            .msg-chat-type { display:none; }
            .msg-chat-meta { display:none; }
            .msg-empty { padding:26px 14px; color:#aaa; font-size:12px; text-align:center; }
            .msg-work { display:flex; flex-direction:column; min-width:0; min-height:0; background:#f5f6f7; }
            .msg-head { display:flex; align-items:center; gap:10px; padding:10px 16px; background:#fff; border-bottom:1px solid #e8e9ec; }
            .msg-head-name { font-size:15px; font-weight:650; color:#222; }
            .msg-head-name.admin { color:#dc2626 !important; font-weight:700; }
            .msg-head-sub { margin-top:2px; color:#999; font-size:11px; }
            .msg-head-actions { margin-left:auto; display:flex; gap:7px; flex-wrap:wrap; justify-content:flex-end; }
            .msg-btn { min-height:28px; padding:0 10px; border:1px solid #dcdfe6; border-radius:6px; background:#fff; color:#666; font-size:11px; font-weight:600; cursor:pointer; transition:all .16s ease; }
            .msg-btn:hover { border-color:#12b7f5; color:#12b7f5; }
            .msg-btn.primary { border-color:#12b7f5; background:#12b7f5; color:#fff; }
            .msg-btn.primary:hover { background:#0ea5e0; }
            .msg-body { flex:1 1 0; min-height:0; overflow-y:auto; padding:18px 16px 10px; background:#f5f6f7; overscroll-behavior:contain; scrollbar-gutter:stable; }
            .msg-body.msg-positioning { visibility:hidden; overflow-anchor:none; }
            .msg-loading { display:grid; gap:12px; padding:18px 8px; }
            .msg-loading span { display:block; width:68%; height:44px; border-radius:10px; background:#e7ebf0; animation:msg-loading-pulse 1.15s ease-in-out infinite alternate; }
            .msg-loading span:nth-child(2) { width:54%; margin-left:18%; animation-delay:.18s; }
            .msg-loading span:nth-child(3) { width:62%; animation-delay:.36s; }
            @keyframes msg-loading-pulse { from { opacity:.48; transform:translateY(1px); } to { opacity:1; transform:translateY(0); } }
            .msg-day { margin:10px 0; color:#aaa; font-size:10px; text-align:center; }
            /* 消息行必须使用真实高度，避免估算布局在显示后把滚动位置推离底部。 */
            .msg-row { display:flex; gap:9px; margin-bottom:14px; }
            .msg-row.self { flex-direction:row-reverse; }
            .msg-avatar { position:relative; width:36px; height:36px; flex:0 0 auto; display:grid; place-items:center; border-radius:50%; background:#cfe3fb; color:#3a7bd5; font-size:12px; font-weight:800; overflow:hidden; }
            .msg-avatar img { width:100%; height:100%; object-fit:cover; position:relative; z-index:1; border-radius:50%; }
            .msg-avatar .avatar-letter { position:absolute; inset:0; display:grid; place-items:center; font-size:12px; font-weight:800; color:#3a7bd5; }
            .msg-avatar.avatar-fallback .avatar-letter { position:static; display:grid; }
            .msg-bubble-wrap { max-width:min(70%,560px); min-width:0; }
            .msg-row.self .msg-bubble-wrap { display:flex; flex-direction:column; align-items:flex-end; }
            .msg-bubble-name { margin-bottom:3px; color:#999; font-size:10px; padding-left:2px; }
            .msg-row.self .msg-bubble-name { padding-left:0; padding-right:2px; }
            .msg-bubble { padding:8px 12px; border-radius:3px 10px 10px 10px; background:#fff; color:#333; font-size:13px; line-height:1.6; word-break:break-word; white-space:pre-wrap; box-shadow:0 1px 2px rgba(0,0,0,.05); }
            .msg-row.self .msg-bubble { border-radius:10px 3px 10px 10px; background:#12b7f5; color:#fff; }
            .msg-row.self .msg-bubble .msg-bubble-quote { color:#dff1fd; }
            .msg-inline-link { color:#1c7ed6; text-decoration:underline; text-underline-offset:2px; }
            .msg-inline-code { padding:1px 4px; border-radius:4px; background:rgba(0,0,0,.08); font:12px/1.4 Consolas,Monaco,monospace; }
            .msg-command-chip { display:inline; margin:0 2px; padding:0 2px; border:0; border-bottom:1px dashed currentColor; background:transparent; color:inherit; font:inherit; line-height:inherit; cursor:pointer; }
            .msg-command-chip:hover { opacity:.72; }
            .msg-bubble.recalled { color:#c45b5b; font-style:italic; background:#fff1f1; border:1px solid #ffd6d6; }
            .msg-bubble-quote { margin:-2px 0 6px; padding:5px 8px; border-left:3px solid #8ec5f2; border-radius:4px; background:#f2f8ff; color:#888; font-size:11px; }
            .msg-row.self .msg-bubble-quote { background:rgba(255,255,255,.22); border-left-color:#fff; }
            .msg-media { margin-top:7px; }
            .msg-media-text { white-space:pre-wrap; word-break:break-word; }
            .msg-media-text-after { margin-top:7px; }
            .msg-inline-media { display:flex; align-items:center; flex-wrap:wrap; gap:4px; min-width:0; max-width:100%; }
            .msg-inline-media > .msg-media { margin-top:0; }
            .msg-inline-media > .msg-media-text { margin-top:0; }
            .msg-image-media { display:flex; flex-direction:column; align-items:flex-start; gap:4px; }
            .msg-image-link { display:block; min-width:24px; min-height:24px; padding:0; border:0; background:transparent; text-align:left; line-height:0; cursor:zoom-in; }
            .msg-image-link:focus-visible { outline:2px solid #12b7f5; outline-offset:3px; }
            .msg-media img { max-width:240px; max-height:240px; border-radius:8px; display:block; cursor:zoom-in; transition:transform .12s ease; background:#f2f3f5; }
            .msg-media img:hover { transform:scale(1.03); }
            .msg-video-media video { display:block; width:min(320px,80vw); max-height:240px; border-radius:8px; background:#111; }
             /* 图片失效时保留占位提示，不能把包含提示的按钮整体隐藏。 */
             .msg-image-link.is-broken { display:inline-flex; align-items:center; min-width:0; min-height:0; padding:0; cursor:default; line-height:1.4; }
             .msg-image-link.is-broken img { display:none; }
             .msg-image-link.is-broken .msg-media-ph { margin:0; }
            .msg-file-card { display:flex; align-items:center; gap:9px; min-width:190px; max-width:290px; padding:8px 10px; border-radius:8px; background:#f5f8fc; color:#3e4a5a; text-decoration:none; }
            .msg-file-card:hover { background:#eaf2fc; }
            .msg-file-card.is-unavailable { color:#8a8f99; }
            .msg-file-icon { width:28px; height:28px; flex:0 0 28px; display:grid; place-items:center; border-radius:6px; background:#dcecff; color:#3a7bd5; font-size:15px; font-weight:700; }
            .msg-file-info { min-width:0; flex:1; display:flex; flex-direction:column; gap:1px; }
            .msg-file-info strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; font-weight:600; }
            .msg-file-info small { color:#8a8f99; font-size:10px; line-height:1.3; }
            .msg-file-action { flex:0 0 auto; color:#3a7bd5; font-size:10px; }
            .msg-media-ph { display:inline-block; padding:8px 14px; background:#f2f3f5; border-radius:8px; font-size:12px; color:#8a8f99; }
            .msg-row.self .msg-file-card { background:rgba(255,255,255,.2); color:#fff; }
            .msg-row.self .msg-file-card:hover { background:rgba(255,255,255,.3); }
            .msg-row.self .msg-file-info small,.msg-row.self .msg-file-action { color:rgba(255,255,255,.78); }
            .msg-lightbox { position:fixed; inset:0; z-index:2000; background:rgba(0,0,0,.86); display:flex; align-items:center; justify-content:center; padding:28px; }
            .msg-lightbox[hidden] { display:none; }
            .msg-lightbox-inner { position:relative; max-width:100%; max-height:100%; display:flex; flex-direction:column; align-items:center; gap:10px; }
            .msg-lightbox img { max-width:92vw; max-height:84vh; border-radius:6px; box-shadow:0 8px 40px rgba(0,0,0,.55); object-fit:contain; }
            .msg-lightbox-close { position:fixed; top:18px; right:22px; width:38px; height:38px; border-radius:50%; border:none; background:rgba(255,255,255,.14); color:#fff; font-size:20px; line-height:38px; text-align:center; cursor:pointer; transition:background .15s ease; }
            .msg-lightbox-close:hover { background:rgba(255,255,255,.28); }
            .msg-lightbox-hint { color:rgba(255,255,255,.62); font-size:11px; }
            .msg-meta { margin-top:3px; color:#b0b0b0; font-size:9px; padding-left:2px; }
            .msg-row.self .msg-meta { text-align:right; padding-left:0; padding-right:2px; }
            .msg-send-error { width:18px; height:18px; margin-left:7px; padding:0; border:0; border-radius:50%; background:#e64340; color:#fff; font-size:12px; font-weight:800; line-height:18px; text-align:center; vertical-align:-5px; cursor:pointer; box-shadow:0 1px 3px rgba(230,67,64,.25); }
            .msg-send-error:hover { background:#c92f2c; transform:scale(1.06); }
            .msg-tags { display:inline-flex; gap:4px; margin-left:6px; vertical-align:middle; }
            .msg-tag { display:inline-block; padding:0 5px; border-radius:4px; font-size:9px; line-height:15px; font-weight:700; }
            .msg-tag.bot { background:#ffeef5; color:#c66791; }
            .msg-tag.role { background:#eef3ff; color:#5b7bd5; }
            .msg-tag.self { background:#e9fbf3; color:#319e6b; }
            .msg-tag.recalled { background:#fff0f0; color:#e64340; }
            .msg-tag.muted { background:#fff0f0; color:#d64545; }
            .msg-row.muted .msg-avatar { background:#d9dde2; color:#89919b; filter:grayscale(.7); }
            .msg-row.muted .msg-avatar img { filter:grayscale(1); opacity:.55; }
            .msg-mute-countdown { display:inline-block; margin-left:7px; color:#d64545; font-size:9px; font-weight:700; }
            .msg-actions { display:flex; gap:5px; margin-top:5px; }
            .msg-row.self .msg-actions { justify-content:flex-end; }
            .msg-action { padding:0 7px; min-height:22px; border:0; border-radius:5px; background:#e4e7ec; color:#888; font-size:10px; cursor:pointer; }
            .msg-action:hover { background:#d2e9fb; color:#12b7f5; }
            .msg-load-older { display:block; margin:0 auto 12px; padding:5px 12px; border:1px solid #dcdfe6; border-radius:6px; background:#fff; color:#999; font-size:11px; cursor:pointer; }
             .msg-composer { position:relative; display:flex; flex-direction:column; gap:8px; min-height:132px; max-height:52vh; padding:10px 14px 12px; overflow:auto; resize:vertical; background:#fff; border-top:1px solid #e8e9ec; transition:height .22s ease,min-height .22s ease,padding .22s ease; }
            .msg-composer-tabs { display:flex; gap:5px; flex-wrap:wrap; }
            .msg-composer-mode[hidden], .msg-composer-tabs[hidden], .msg-composer-toggle[hidden], .msg-composer > .msg-extra[hidden] { display:none !important; }
            .msg-composer-tabs button { min-height:26px; padding:0 10px; border:1px solid #e0e1e5; border-radius:6px; background:#fff; color:#999; font-size:11px; font-weight:600; cursor:pointer; }
            .msg-composer-tabs button.active { border-color:#12b7f5; color:#12b7f5; background:#e8f6fe; }
            .msg-composer-mode { display:flex; gap:5px; flex-wrap:wrap; align-items:center; }
            .msg-composer-mode select { height:28px; padding:0 8px; border:1px solid #e0e1e5; border-radius:6px; background:#fff; color:#333; font-size:11px; }
            .msg-composer-mode input { height:28px; min-width:120px; padding:0 8px; border:1px solid #e0e1e5; border-radius:6px; background:#fbfbff; color:#333; font-size:11px; outline:none; }
            .msg-textarea { min-height:64px; max-height:150px; padding:9px 11px; border:0; border-radius:6px; background:#f2f3f5; color:#333; font-size:12px; line-height:1.55; resize:vertical; outline:none; transition:all .15s ease; }
            .msg-textarea:focus { background:#fff; box-shadow:inset 0 0 0 1px #12b7f5; }
            .msg-extra { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px; }
            .msg-extra input { height:28px; min-width:0; padding:0 8px; border:1px solid #e0e1e5; border-radius:6px; background:#fbfbff; color:#333; font-size:11px; outline:none; }
            .msg-send-row { display:flex; align-items:center; gap:10px; justify-content:flex-end; }
            .msg-send-row .msg-btn.primary { min-height:32px; padding:0 24px; }
         .msg-input-box { position:relative; display:flex; flex:1 1 auto; flex-direction:column; min-height:96px; height:auto; max-height:none; overflow:auto; resize:vertical; border:1px solid #d8d9dd; border-radius:4px; background:#fff; transition:border-color .15s; }
        .msg-input-box:focus-within { border-color:#12b7f5; }
        .msg-input-box.drag-over { border-color:#12b7f5; background:#f0f9ff; box-shadow:0 0 0 2px rgba(18,183,245,.14); }
        .msg-input-box.has-inline-image .msg-editor { min-height:42px; }
        .msg-editor { width:100%; flex:1 1 auto; min-height:88px; height:auto; max-height:none; overflow:auto; padding:12px 14px 6px; border:0; outline:none; color:#333; background:transparent; box-sizing:border-box; font-size:13px; line-height:1.6; white-space:pre-wrap; word-break:break-word; }
        .msg-editor:empty::before { content:attr(data-placeholder); color:#a0a4ad; pointer-events:none; }
        .msg-editor:focus { background:#fff; }
        .composer-inline-image { position:relative; display:inline-flex; align-items:center; vertical-align:middle; margin:2px 3px; padding:0; border:1px solid #dfe3e8; border-radius:6px; background:#f5f6f8; line-height:0; }
        .composer-inline-image img { display:block; width:auto; max-width:180px; max-height:120px; border-radius:5px; object-fit:contain; }
        .composer-inline-image button { position:absolute; top:-7px; right:-7px; width:18px; height:18px; padding:0; border:0; border-radius:50%; background:rgba(0,0,0,.58); color:#fff; cursor:pointer; font-size:12px; line-height:18px; }
        .composer-inline-image button:hover { background:rgba(230,67,64,.92); }
        .msg-img-remove { position:absolute; top:3px; right:3px; width:18px; height:18px; border:0; border-radius:50%; background:rgba(0,0,0,.55); color:#fff; font-size:12px; line-height:1; cursor:pointer; display:grid; place-items:center; }
        .msg-img-remove:hover { background:rgba(230,67,64,.9); }
        .msg-attachment-inline { position:relative; display:flex; align-items:center; gap:8px; min-height:40px; margin:9px 12px 0; padding:7px 34px 7px 9px; border:1px solid #e3e4e8; border-radius:6px; background:#f5f6f8; color:#555; }
        .msg-attachment-inline[hidden] { display:none; }
        .msg-attachment-icon { width:25px; height:25px; display:grid; place-items:center; border-radius:5px; background:#dcecff; color:#3a7bd5; font-size:13px; font-weight:700; }
        .msg-attachment-name { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11px; }
        .msg-quote-preview { display:flex; align-items:center; gap:8px; padding:6px 9px; border:1px solid #e2ddf5; border-radius:4px; background:#f8f7ff; color:#999; font-size:11px; }
        .msg-quote-preview[hidden] { display:none; }
        .msg-quote-preview b { color:#333; }
        .msg-quote-text { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .msg-composer-topbar { display:flex; align-items:center; gap:5px; min-height:30px; }
        .msg-composer-top-hint { margin-left:3px; color:#a0a4ad; font-size:10px; }
        .msg-toolbar { display:flex; align-items:center; gap:10px; min-height:30px; }
        .msg-tool-btn { display:grid; place-items:center; width:28px; height:28px; border-radius:4px; color:#6b6f78; cursor:pointer; }
        .msg-tool-btn:hover { background:#f0f7ff; color:#12b7f5; }
        .msg-tool-btn svg { display:block; }
            .msg-raw-modal { position:fixed; inset:0; z-index:60; display:grid; place-items:center; background:rgba(30,28,50,.45); padding:20px; }
            .msg-raw-modal[hidden] { display:none; }
            .msg-raw-box { width:min(720px,100%); height:min(640px,78vh); min-height:320px; display:flex; flex-direction:column; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 18px 50px rgba(40,36,90,.25); }
            .msg-raw-head { display:flex; align-items:center; justify-content:space-between; padding:12px 15px; border-bottom:1px solid #e8e9ec; }
            .msg-raw-head strong { font-size:13px; color:#222; }
            .msg-raw-head button { border:0; background:transparent; color:#999; font-size:16px; cursor:pointer; }
            .msg-raw-content { flex:1 1 0; min-height:0; overflow:auto; padding:13px 15px; white-space:pre-wrap; word-break:break-all; color:#333; font:12px/1.6 Consolas,Monaco,monospace; }
            .msg-mute-modal { position:fixed; inset:0; z-index:60; display:grid; place-items:center; background:rgba(30,28,50,.45); padding:20px; }
            .msg-mute-modal[hidden] { display:none; }
            .msg-mute-box { width:min(400px,100%); background:#fff; border-radius:12px; padding:16px; box-shadow:0 18px 50px rgba(40,36,90,.25); }
            .msg-mute-box h3 { margin:0 0 12px; font-size:14px; color:#222; }
            .msg-mute-presets { display:flex; gap:7px; flex-wrap:wrap; margin-bottom:12px; }
            .msg-mute-presets button { min-height:30px; padding:0 12px; border:1px solid #e0e1e5; border-radius:8px; background:#fff; color:#666; font-size:11px; cursor:pointer; }
            .msg-mute-presets button.active { border-color:#12b7f5; color:#12b7f5; background:#e8f6fe; }
            .msg-mute-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:12px; }
            .msg-remark-modal { position:fixed; inset:0; z-index:60; display:grid; place-items:center; background:rgba(30,28,50,.45); padding:20px; }
            .msg-remark-modal[hidden] { display:none; }
            .msg-remark-box { width:min(380px,100%); background:#fff; border-radius:12px; padding:16px; box-shadow:0 18px 50px rgba(40,36,90,.25); }
            .msg-remark-box h3 { margin:0 0 12px; font-size:14px; color:#222; }
            /* ===== QQ PC 风格覆盖 ===== */
            .msg-shell { grid-template-columns:minmax(220px,var(--msg-list-width)) minmax(0,1fr); border:1px solid #e1e5ea; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.06); }
            .chat-list-panel { background:#f7f8fa; }
            .msg-list-head { padding:10px 12px; background:#f7f8fa; border-bottom:1px solid #e5e8ec; }
            .msg-filter button.active { color:#12b7f5; }
            .msg-chats { padding:4px 6px; }
            .msg-chat { min-height:52px; padding:6px 8px; border-radius:6px; }
            .msg-chat:hover { background:#eceef1; }
            .msg-chat.removed { background:#fff8f8; }
            .msg-chat.removed:hover { background:#fff0f0; }
            .msg-chat.removed .msg-chat-sub { color:#d15f63; font-weight:600; }
            .msg-chat.removed .msg-chat-avatar { filter:grayscale(.55); opacity:.72; }
            .msg-chat.active { background:#d5ebfb; }
            .msg-chat-avatar { width:38px; height:38px; }
            .msg-chat-top strong { font-size:12.5px; }
            .msg-chat-sub { font-size:11px; margin-top:1px; }
            .msg-work { background:#f5f6f7; }
            .msg-head { padding:8px 14px; background:#fff; }
            .msg-body { padding:14px 20px 8px; background:#f5f6f7; }
            .msg-day { margin:8px 0; color:#b6bcc4; font-size:10px; }
            .msg-row { gap:10px; margin-bottom:12px; align-items:flex-start; }
            .msg-avatar { width:38px; height:38px; }
            .msg-bubble-wrap { max-width:min(62%,560px); }
            .msg-bubble { padding:9px 12px; border-radius:4px 12px 12px 12px; background:#fff; font-size:13px; box-shadow:0 1px 2px rgba(0,0,0,.05); }
            .msg-row.self .msg-bubble { border-radius:12px 4px 12px 12px; background:#95ec69; color:#000; }
            .msg-row.self .msg-bubble .msg-bubble-quote { color:rgba(0,0,0,.55); }
            .msg-meta { color:#b6bcc4; font-size:9px; }
            .msg-bubble-name { font-size:10px; }
            .msg-composer { padding:8px 14px 10px; background:#fff; border-top:1px solid #e5e8ec; }
            .msg-textarea { background:#f7f8fa; border-radius:4px; }
            .msg-textarea:focus { background:#fff; box-shadow:inset 0 0 0 1px #12b7f5; }
            .msg-send-row .msg-btn.primary { background:#12b7f5; border-color:#12b7f5; }

            /* 右键菜单 */
            .msg-ctx { position:fixed; z-index:120; min-width:150px; padding:4px; background:#fff; border:1px solid #e1e5ea; border-radius:8px; box-shadow:0 6px 20px rgba(0,0,0,.14); user-select:none; }
            .msg-ctx[hidden] { display:none; }
            .msg-ctx-item { display:flex; align-items:center; gap:8px; width:100%; padding:7px 10px; border:0; border-radius:5px; background:transparent; color:#333; font-size:12px; text-align:left; cursor:pointer; }
            .msg-ctx-item:hover { background:#f0f7ff; color:#12b7f5; }
            .msg-ctx-item.danger:hover { background:#fff1f0; color:#e64340; }
            .msg-ctx-sep { height:1px; margin:4px 8px; background:#eee; }

            /* 多选模式 */
            .msg-multi-bar { display:flex; align-items:center; gap:10px; padding:6px 14px; background:#e8f6fe; border-bottom:1px solid #cfe8fb; font-size:12px; color:#12b7f5; }
            .msg-multi-bar[hidden] { display:none; }
            .msg-row.multi-mode { cursor:pointer; }
            .msg-row.multi-mode .msg-avatar, .msg-row.multi-mode .msg-bubble { opacity:.85; }
            .msg-row.multi-mode.selected .msg-bubble { outline:2px solid #12b7f5; outline-offset:2px; }
            .msg-pos { position:relative; display:inline-flex; flex:0 0 auto; }
            .msg-multi-check { display:none; }
            .msg-row.multi-mode .msg-multi-check { display:grid; position:absolute; left:-16px; top:50%; transform:translateY(-50%); width:18px; height:18px; border-radius:50%; border:2px solid #c3ccd4; background:#fff; display:grid; place-items:center; font-size:11px; color:#fff; }
            .msg-row.multi-mode.selected .msg-multi-check { border-color:#12b7f5; background:#12b7f5; }
            .msg-row.self.multi-mode .msg-multi-check { left:auto; right:-16px; }
            .msg-row.multi-mode.no-multi { opacity:.55; }
            .msg-row.multi-mode.no-multi .msg-multi-check { display:none; }
             .msg-row.multi-mode .msg-multi-check::after { content:'✓'; }
             .msg-pos { position:relative; }
             .msg-body-wrap { position:relative; display:flex; flex:1 1 0; min-height:0; overflow:hidden; }
             .msg-new-messages { position:absolute; right:18px; bottom:14px; z-index:3; display:inline-flex; align-items:center; gap:7px; min-height:32px; padding:0 12px; border:1px solid #b8dff2; border-radius:17px; background:#fff; color:#0b9bd0; box-shadow:0 5px 16px rgba(30,110,160,.18); font-size:11px; font-weight:700; cursor:pointer; transition:opacity .16s ease, transform .16s ease, box-shadow .16s ease; }
             .msg-new-messages:hover { transform:translateY(-1px); box-shadow:0 7px 18px rgba(30,110,160,.24); }
             .msg-new-messages[hidden] { display:none; }
             .msg-new-messages-dot { width:7px; height:7px; border-radius:50%; background:#12b7f5; box-shadow:0 0 0 4px #e8f6fe; }
             .msg-new-messages-arrow { font-size:15px; line-height:1; }
             /* 面板尺寸控制：脚本写入 --msg-list-width 并切换折叠 class。 */
             .msg-list-resizer { position:absolute; z-index:6; top:0; right:0; bottom:0; width:14px; padding:0; border:0; background:transparent; cursor:col-resize; }
             .msg-list-resizer,.msg-composer-resizer { touch-action:none; }
             .msg-list-resizer::before { content:""; position:absolute; top:50%; left:6px; width:2px; height:42px; border-radius:2px; background:#d5dbe2; transform:translateY(-50%); opacity:0; transition:opacity .16s ease,background .16s ease; }
             .chat-list-panel:hover .msg-list-resizer::before,.msg-list-resizer:focus-visible::before { opacity:1; }
             .msg-list-resizer:hover::before,.msg-list-resizer:focus-visible::before { background:#12b7f5; }
             .msg-panel-toggle { display:grid; place-items:center; flex:0 0 auto; width:27px; height:27px; padding:0; border:1px solid #dfe3e8; border-radius:6px; background:#fff; color:#7a818a; font-size:17px; line-height:1; cursor:pointer; transition:background .16s ease,border-color .16s ease,color .16s ease; }
             .msg-panel-toggle:hover,.msg-panel-toggle:focus-visible { border-color:#12b7f5; background:#f0f7ff; color:#0b9bd0; }
             .msg-list-collapse { position:absolute; z-index:5; top:10px; right:8px; margin:0; }
             .msg-composer-resizer { position:absolute; z-index:2; top:-6px; right:14px; left:14px; width:calc(100% - 28px); height:12px; padding:0; border:0; background:transparent; cursor:row-resize; }
             .msg-composer-resizer::before { content:""; position:absolute; top:5px; left:50%; width:42px; height:3px; border-radius:3px; background:#d5dbe2; transform:translateX(-50%); opacity:.7; transition:background .16s ease,opacity .16s ease; }
             .msg-composer-resizer:hover::before,.msg-composer-resizer:focus-visible::before { background:#12b7f5; opacity:1; }
             .msg-composer-toggle { margin-right:2px; color:#7a818a; }
             .msg-composer { flex:0 0 auto; box-sizing:border-box; resize:none; }
             body.msg-resizing { user-select:none; cursor:col-resize; }
             body.msg-resizing .msg-shell, body.msg-resizing .msg-composer { transition:none !important; }
             body.msg-resizing .msg-composer { cursor:row-resize; }
             .msg-toolbar { min-height:30px; }
             .msg-shell.msg-list-collapsed { --msg-list-width:38px; grid-template-columns:38px minmax(0,1fr); }
             .msg-shell.msg-list-collapsed .chat-list-panel > :not(.msg-list-collapse) { visibility:hidden; pointer-events:none; }
             .msg-shell.msg-list-collapsed .msg-list-collapse { visibility:visible; pointer-events:auto; position:absolute; top:10px; right:5px; margin:0; transform:none; }
             .msg-shell.msg-composer-collapsed .msg-composer { min-height:38px; height:38px; max-height:38px; overflow:hidden; padding:5px 14px; }
             .msg-shell.msg-composer-collapsed .msg-composer > :not(.msg-composer-resizer):not(.msg-composer-topbar) { visibility:hidden; pointer-events:none; }
             .msg-shell.msg-composer-collapsed .msg-composer-topbar { visibility:visible; pointer-events:auto; }
             .msg-shell.msg-composer-collapsed .msg-composer-topbar > :not(.msg-composer-toggle) { visibility:hidden; pointer-events:none; }
             .msg-shell.msg-composer-collapsed .msg-composer .msg-composer-toggle { visibility:visible !important; pointer-events:auto !important; transform:none; }
             .msg-mobile-back { display:none; place-items:center; flex:0 0 auto; width:32px; height:32px; padding:0; border:0; border-radius:7px; background:transparent; color:#5f6873; font-size:27px; line-height:1; cursor:pointer; }
             .msg-mobile-back:hover,.msg-mobile-back:focus-visible { background:#f0f7ff; color:#12b7f5; outline:none; }
             /* 消息页/专用控制页已有自己的标题，隐藏上方重复的全局标题。 */
             .content:has(#page-messages:not([hidden])) > .page-heading,
             .content:has(#page-pans:not([hidden])) > .page-heading,
             .content:has(#page-novels:not([hidden])) > .page-heading { display:none; }
             @media (max-width:900px) {
               .msg-shell { height:auto; min-height:620px; grid-template-columns:1fr; }
               .msg-panel.chat-list-panel { min-height:280px; max-height:38vh; }
               .msg-list-resizer { display:none; }
               .msg-shell.msg-list-collapsed { grid-template-columns:1fr; }
               .msg-shell.msg-list-collapsed .chat-list-panel { min-height:38px; max-height:38px; }
               .msg-shell.msg-list-collapsed .chat-list-panel > :not(.msg-list-collapse) { display:none; }
               .msg-shell.msg-list-collapsed .msg-list-collapse { top:5px; right:8px; }
               .msg-bubble-wrap { max-width:88%; }
               .msg-extra { grid-template-columns:1fr; }
             }
             @media (max-width:600px) {
               .msg-shell { min-height:calc(100vh - 112px); }
               .msg-composer { max-height:58vh; }
               .msg-input-box { max-height:45vh; }
               .msg-head-actions { gap:5px; }
             }
             @media (max-width:760px) {
               .content:has(#page-messages:not([hidden])) { width:100%; padding:0 0 20px; }
               .msg-shell { display:block; height:calc(100dvh - 135px); min-height:420px; margin:0; border-right:0; border-left:0; border-radius:0; }
               body.msg-mobile-chat-view .msg-shell { height:100dvh; min-height:0; }
               .msg-shell .chat-list-panel { display:flex; height:100%; min-height:0; max-height:none; border-right:0; }
               .msg-shell .msg-work { display:none; height:100%; min-height:0; }
               .msg-shell.msg-mobile-chat-open .chat-list-panel { display:none; }
               .msg-shell.msg-mobile-chat-open .msg-work { display:flex; }
               .msg-shell.msg-list-collapsed { grid-template-columns:1fr; }
               .msg-shell.msg-list-collapsed .chat-list-panel { min-height:38px; max-height:38px; }
               .msg-shell.msg-list-collapsed .chat-list-panel > :not(.msg-list-collapse) { display:none; visibility:hidden; pointer-events:none; }
               .msg-list-resizer { display:none; }
               .msg-list-head { padding:9px 44px 8px 12px; }
               .msg-filter { padding:1px; }
               .msg-filter button { min-height:24px; font-size:10px; }
               .msg-search { gap:5px; }
               .msg-search input,.msg-search button { height:28px; font-size:11px; }
               .msg-chat { min-height:60px; padding:8px 10px; border-radius:0; }
               .msg-chat-divider { margin-left:4px; margin-right:4px; }
               .msg-mobile-back { display:grid; }
               .msg-shell:not(.msg-mobile-chat-open) .msg-mobile-back { display:none; }
               .msg-head { min-height:54px; padding:8px 10px; gap:6px; }
               .msg-head-name { font-size:14px; }
               .msg-head-sub { font-size:10px; }
               .msg-head-actions { gap:4px; }
               .msg-head-actions .msg-btn { min-height:27px; padding:0 7px; font-size:10px; }
               .msg-body { padding:14px 10px 8px; }
               .msg-bubble-wrap { max-width:82%; }
               .msg-composer { max-height:52vh; padding:7px 10px 8px; }
               .msg-composer-top-hint { display:none; }
               .msg-input-box { max-height:none; }
               .msg-editor { min-height:42px; }
             }

              /* ===== 深色模式 ===== */
                          :root[data-theme="dark"] .msg-shell { background:#1f2330; border-color:var(--line); }
              :root[data-theme="dark"] .msg-panel { background:#1f2330; }
              :root[data-theme="dark"] .chat-list-panel { border-right-color:var(--line); background:#1a1e2a; }
              :root[data-theme="dark"] .msg-list-head { border-bottom-color:var(--line); background:#1f2330; }
              :root[data-theme="dark"] .msg-filter { background:#161926; }
              :root[data-theme="dark"] .msg-filter button { color:#9aa0b5; }
              :root[data-theme="dark"] .msg-filter button.active { background:#1f2330; color:#12b7f5; box-shadow:0 1px 3px rgba(0,0,0,.35); }
              :root[data-theme="dark"] .msg-search input { background:#161926; color:#e8eaf2; }
              :root[data-theme="dark"] .msg-search input:focus { border-color:#12b7f5; background:#1f2330; }
              :root[data-theme="dark"] .msg-chat:hover { background:#262b3a; }
              :root[data-theme="dark"] .msg-chat.removed { background:#302126; }
              :root[data-theme="dark"] .msg-chat.removed:hover { background:#3a252b; }
              :root[data-theme="dark"] .msg-chat.removed .msg-chat-sub { color:#ef8585; }
              :root[data-theme="dark"] .msg-chat.active { background:#1d3850; }
              :root[data-theme="dark"] .msg-chat.pinned { background:#1e2c44; }
              :root[data-theme="dark"] .msg-chat.pinned:hover { background:#24334e; }
              :root[data-theme="dark"] .msg-chat.pinned.active { background:#27405e; }
              :root[data-theme="dark"] .msg-chat.pinned .msg-chat-top strong { color:#6fa8e8; }
              :root[data-theme="dark"] .msg-chat.pinned .msg-chat-top small { color:#7d96b8; }
              :root[data-theme="dark"] .msg-chat-top strong.admin,
              :root[data-theme="dark"] .msg-chat.pinned .msg-chat-top strong.admin { color:#f87171 !important; }
              :root[data-theme="dark"] .msg-chat-top strong { color:#e8eaf2; }
              :root[data-theme="dark"] .msg-chat-top small,:root[data-theme="dark"] .msg-chat-sub,:root[data-theme="dark"] .msg-bubble-name,:root[data-theme="dark"] .msg-head-sub { color:#8a90a5; }
              :root[data-theme="dark"] .msg-chat-avatar { background:#23405f; color:#8db9f0; }
              :root[data-theme="dark"] .msg-chat-avatar .avatar-letter { color:#8db9f0; }
              :root[data-theme="dark"] .msg-empty { color:#6f7590; }
              :root[data-theme="dark"] .msg-work { background:#161926; }
              :root[data-theme="dark"] .msg-head { background:#1f2330; border-bottom-color:var(--line); }
              :root[data-theme="dark"] .msg-head-name { color:#e8eaf2; }
              :root[data-theme="dark"] .msg-head-name.admin { color:#f87171 !important; }
              :root[data-theme="dark"] .msg-btn { border-color:var(--line); background:#1f2330; color:#9aa0b5; }
               :root[data-theme="dark"] .msg-body { background:#161926; }
               :root[data-theme="dark"] .msg-new-messages { border-color:#235b78; background:#1f2330; color:#42c6ff; box-shadow:0 5px 16px rgba(0,0,0,.35); }
               :root[data-theme="dark"] .msg-new-messages-dot { background:#42c6ff; box-shadow:0 0 0 4px #12344d; }
               :root[data-theme="dark"] .msg-day { color:#6f7590; }
              :root[data-theme="dark"] .msg-avatar { background:#23405f; color:#8db9f0; }
              :root[data-theme="dark"] .msg-avatar .avatar-letter { color:#8db9f0; }
            :root[data-theme="dark"] .msg-bubble { background:#262b3a; color:#e6e8f0; box-shadow:0 1px 2px rgba(0,0,0,.25); }
            :root[data-theme="dark"] .msg-row.self .msg-bubble { background:#12b7f5; color:#fff; }
            :root[data-theme="dark"] .msg-inline-link { color:#77b8f2; }
            :root[data-theme="dark"] .msg-inline-code { background:rgba(255,255,255,.12); }
              :root[data-theme="dark"] .msg-bubble.recalled { color:#f08080; background:#302126; border-color:#5a3038; }
              :root[data-theme="dark"] .msg-bubble-quote { border-left-color:#3f6ea8; background:#16222e; color:#9db4c9; }
              :root[data-theme="dark"] .msg-row.self .msg-bubble .msg-bubble-quote { color:#dff1fd; }
               :root[data-theme="dark"] .msg-media-ph { background:#1a1e2a; color:#9aa0b5; }
               :root[data-theme="dark"] .msg-loading span { background:#2a3040; }
               :root[data-theme="dark"] .msg-image-link.is-broken .msg-media-ph { background:#1a1e2a; color:#9aa0b5; }
              :root[data-theme="dark"] .msg-file-card { background:#202c3d; color:#dce8f6; }
              :root[data-theme="dark"] .msg-file-card:hover { background:#263a52; }
              :root[data-theme="dark"] .msg-file-icon { background:#294b70; color:#9bc9f4; }
              :root[data-theme="dark"] .msg-file-info small { color:#8a9bb2; }
              :root[data-theme="dark"] .msg-meta { color:#6f7590; }
              :root[data-theme="dark"] .msg-send-error { background:#e25555; }
              :root[data-theme="dark"] .msg-send-error:hover { background:#f06b6b; }
              :root[data-theme="dark"] .msg-tag.bot { background:#3a2130; color:#e287ae; }
              :root[data-theme="dark"] .msg-tag.role { background:#1f2a44; color:#8fa8ec; }
              :root[data-theme="dark"] .msg-tag.self { background:#16382c; color:#55d8a2; }
              :root[data-theme="dark"] .msg-tag.recalled { background:#3a2121; color:#f08080; }
              :root[data-theme="dark"] .msg-tag.muted { background:#3a2121; color:#f08080; }
              :root[data-theme="dark"] .msg-row.muted .msg-avatar { background:#3b404a; color:#a6adb8; }
              :root[data-theme="dark"] .msg-mute-countdown { color:#f08080; }
              :root[data-theme="dark"] .msg-action { background:#262b38; color:#9aa0b5; }
              :root[data-theme="dark"] .msg-action:hover { background:#1d3850; color:#12b7f5; }
              :root[data-theme="dark"] .msg-load-older { border-color:var(--line); background:#1f2330; color:#8a90a5; }
              :root[data-theme="dark"] .msg-composer { background:#1f2330; border-top-color:var(--line); }
              :root[data-theme="dark"] .msg-composer-tabs button { border-color:var(--line); background:#1f2330; color:#8a90a5; }
              :root[data-theme="dark"] .msg-composer-tabs button.active { border-color:#12b7f5; color:#12b7f5; background:#12344d; }
              :root[data-theme="dark"] .msg-composer-mode select { border-color:var(--line); background:#1f2330; color:#e8eaf2; }
              :root[data-theme="dark"] .msg-composer-mode input { border-color:var(--line); background:#161926; color:#e8eaf2; }
              :root[data-theme="dark"] .msg-textarea,:root[data-theme="dark"] .msg-editor { background:#161926; color:#e8eaf2; }
              :root[data-theme="dark"] .msg-textarea:focus { background:#1f2330; box-shadow:inset 0 0 0 1px #12b7f5; }
              :root[data-theme="dark"] .msg-extra input { border-color:var(--line); background:#161926; color:#e8eaf2; }
              :root[data-theme="dark"] .msg-input-box { border-color:#2c3044; background:#1f2330; }
              :root[data-theme="dark"] .msg-input-box.drag-over { border-color:#42c6ff; background:#172b39; box-shadow:0 0 0 2px rgba(66,198,255,.16); }
              :root[data-theme="dark"] .msg-attachment-inline { border-color:#2c3044; background:#161926; color:#d3d7e4; }
              :root[data-theme="dark"] .msg-attachment-icon { background:#294b70; color:#9bc9f4; }
              :root[data-theme="dark"] .msg-composer-top-hint { color:#6f7590; }
              :root[data-theme="dark"] .msg-quote-preview { border-color:#3a3f58; background:#1f2133; color:#8a90a5; }
              :root[data-theme="dark"] .msg-quote-preview b { color:#e8eaf2; }
              :root[data-theme="dark"] .msg-tool-btn { color:#9aa0b5; }
              :root[data-theme="dark"] .msg-tool-btn:hover { background:#1d3850; color:#12b7f5; }
              :root[data-theme="dark"] .msg-raw-box,:root[data-theme="dark"] .msg-mute-box,:root[data-theme="dark"] .msg-remark-box { background:#1f2330; box-shadow:0 18px 50px rgba(0,0,0,.5); }
              :root[data-theme="dark"] .msg-raw-head { border-bottom-color:var(--line); }
              :root[data-theme="dark"] .msg-raw-head { border-bottom-color:var(--line); }
              :root[data-theme="dark"] .msg-raw-head strong,:root[data-theme="dark"] .msg-mute-box h3,:root[data-theme="dark"] .msg-remark-box h3 { color:#e8eaf2; }
              :root[data-theme="dark"] .msg-raw-head button { color:#8a90a5; }
              :root[data-theme="dark"] .msg-raw-content { color:#d3d7e4; }
              :root[data-theme="dark"] .msg-mute-presets button { border-color:var(--line); background:#1f2330; color:#9aa0b5; }
              :root[data-theme="dark"] .msg-mute-presets button.active { border-color:#12b7f5; color:#12b7f5; background:#12344d; }
              :root[data-theme="dark"] .msg-ctx { background:#1f2330; border-color:var(--line); box-shadow:0 6px 20px rgba(0,0,0,.5); }
              :root[data-theme="dark"] .msg-ctx-item { color:#e6e8f0; }
              :root[data-theme="dark"] .msg-ctx-item:hover { background:#1d3850; color:#12b7f5; }
              :root[data-theme="dark"] .msg-ctx-item.danger:hover { background:#3a2121; color:#f08080; }
              :root[data-theme="dark"] .msg-ctx-sep { background:#2c3044; }
              :root[data-theme="dark"] .msg-multi-bar { background:#12344d; border-bottom-color:#1e4a68; color:#42c6ff; }
              :root[data-theme="dark"] .msg-row.multi-mode.selected .msg-bubble { outline-color:#12b7f5; }
              :root[data-theme="dark"] .msg-multi-check { border-color:#4a5268; background:#1f2330; }
              /* QQ PC 覆盖在深色下 */
              :root[data-theme="dark"] .msg-shell { border-color:#2c3044; box-shadow:0 1px 4px rgba(0,0,0,.35); }
              :root[data-theme="dark"] .chat-list-panel { background:#1a1e2a; }
              :root[data-theme="dark"] .msg-list-head { background:#1f2330; border-bottom-color:#2c3044; }
              :root[data-theme="dark"] .msg-chat:hover { background:#262b3a; }
              :root[data-theme="dark"] .msg-chat-divider { border-top-color:#2c3044; color:#7f879b; }
              :root[data-theme="dark"] .msg-chat.active { background:#1d3850; }
              :root[data-theme="dark"] .msg-work { background:#161926; }
              :root[data-theme="dark"] .msg-head { background:#1f2330; }
              :root[data-theme="dark"] .msg-body { background:#161926; }
              :root[data-theme="dark"] .msg-day { color:#6f7590; }
              :root[data-theme="dark"] .msg-bubble { background:#262b3a; }
              :root[data-theme="dark"] .msg-row.self .msg-bubble { background:#95ec69; color:#0f1a12; }
              :root[data-theme="dark"] .msg-row.self .msg-bubble .msg-bubble-quote { color:rgba(0,0,0,.55); }
              :root[data-theme="dark"] .msg-meta { color:#6f7590; }
              :root[data-theme="dark"] .msg-composer { background:#1f2330; border-top-color:#2c3044; }
               :root[data-theme="dark"] .msg-textarea,:root[data-theme="dark"] .msg-editor { background:#161926; }
               :root[data-theme="dark"] .msg-textarea:focus,:root[data-theme="dark"] .msg-editor:focus { background:#1f2330; }
               :root[data-theme="dark"] .msg-multi-bar { border-bottom-color:#1e4a68; }
               :root[data-theme="dark"] .msg-list-resizer::before,:root[data-theme="dark"] .msg-composer-resizer::before { background:#4a5268; }
               :root[data-theme="dark"] .msg-list-resizer:hover::before,:root[data-theme="dark"] .msg-list-resizer:focus-visible::before,:root[data-theme="dark"] .msg-composer-resizer:hover::before,:root[data-theme="dark"] .msg-composer-resizer:focus-visible::before { background:#42c6ff; }
              :root[data-theme="dark"] .msg-panel-toggle { border-color:#3a4256; background:#1f2330; color:#9aa0b5; }
              :root[data-theme="dark"] .msg-panel-toggle:hover,:root[data-theme="dark"] .msg-panel-toggle:focus-visible { border-color:#12b7f5; background:#1d3850; color:#42c6ff; }
              :root[data-theme="dark"] .msg-mobile-back { color:#b9c0d0; }
              :root[data-theme="dark"] .msg-mobile-back:hover,:root[data-theme="dark"] .msg-mobile-back:focus-visible { background:#1d3850; color:#42c6ff; }
              @media (prefers-reduced-motion: reduce) {
                *, *::before, *::after { animation-duration:0.01ms !important; animation-iteration-count:1 !important; scroll-behavior:auto !important; transition-duration:0.01ms !important; }
              }
            </style>
          <div class="msg-shell" id="msg-shell">
            <div class="msg-panel chat-list-panel" id="msg-chat-list-panel">
              <button class="msg-panel-toggle msg-list-collapse" id="msg-list-collapse" type="button" aria-expanded="true" aria-label="收起会话列表" title="收起会话列表">‹</button>
              <div class="msg-list-head">
                <div class="msg-filter" id="msg-filter" role="tablist" aria-label="消息过滤">
                  <button type="button" data-msg-filter="all" class="active">全量</button>
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
                <button class="msg-composer-resizer" id="msg-composer-resizer" type="button" aria-label="拖动调整编辑区高度" title="拖动调整编辑区高度"><span aria-hidden="true"></span></button>
                <div class="msg-composer-topbar">
                  <button class="msg-panel-toggle msg-composer-toggle" id="msg-composer-toggle" type="button" aria-expanded="true" aria-label="收起编辑区" title="收起编辑区">⌄</button>
                  <label class="msg-tool-btn" title="选择图片" id="msg-img-pick" aria-label="选择图片">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                    <input id="msg-img-file" type="file" accept="image/*" hidden>
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
                  <div class="msg-quote-preview" id="msg-quote-preview" hidden><b>引用：</b><span class="msg-quote-text" id="msg-quote-text"></span><button class="msg-action" id="msg-quote-clear" type="button">取消引用</button></div>
                  <div class="msg-attachment-inline" id="msg-media-inline" hidden>
                    <span class="msg-attachment-icon" id="msg-media-icon" aria-hidden="true">□</span>
                    <span class="msg-attachment-name" id="msg-media-name">待发送附件</span>
                    <button class="msg-img-remove" id="msg-media-clear" type="button" aria-label="移除附件">×</button>
                  </div>
                  <div id="msg-editor" class="msg-editor" contenteditable="true" role="textbox" aria-multiline="true" data-placeholder="输入消息内容...（回车发送，Ctrl+Enter 换行）" aria-label="消息内容"></div>
                </div>
                <div class="msg-toolbar">
                  <span style="flex:1"></span>
                  <button class="msg-btn primary" id="msg-send" type="button">发送</button>
                </div>
              </div>
            </div>
          </div>
          <div class="msg-raw-modal" id="msg-raw-modal" hidden><div class="msg-raw-box"><div class="msg-raw-head"><strong>消息原始数据</strong><button id="msg-raw-close" type="button">×</button></div><div class="msg-raw-content" id="msg-raw-content"></div></div></div>
          <div class="msg-remark-modal" id="msg-remark-modal" hidden><div class="msg-remark-box"><h3>群备注</h3><label style="display:block;font-size:11px;color:#999;margin-bottom:4px">备注名（显示在会话列表）</label><input id="msg-remark-name" type="text" placeholder="输入群备注名" style="width:100%;height:34px;padding:0 9px;border:1px solid #e0e1e5;border-radius:8px;font-size:12px;margin-bottom:10px"><label style="display:block;font-size:11px;color:#999;margin-bottom:4px">群号（用于显示群头像，可留空）</label><input id="msg-remark-qq" type="text" placeholder="输入群号" style="width:100%;height:34px;padding:0 9px;border:1px solid #e0e1e5;border-radius:8px;font-size:12px"><div class="msg-mute-actions"><button class="msg-btn" id="msg-remark-delete" type="button" style="color:#e64340;border-color:#f5c2c1;margin-right:auto">删除备注</button><button class="msg-btn" id="msg-remark-cancel" type="button">取消</button><button class="msg-btn primary" id="msg-remark-save" type="button">保存</button></div></div></div>
          <div class="msg-mute-modal" id="msg-mute-modal" hidden><div class="msg-mute-box"><h3 id="msg-mute-title">禁言成员</h3><div class="msg-mute-presets" id="msg-mute-presets"><button type="button" data-mute-min="10">10分钟</button><button type="button" data-mute-min="30" class="active">30分钟</button><button type="button" data-mute-min="60">1小时</button><button type="button" data-mute-min="1440">1天</button></div><input id="msg-mute-custom" type="number" min="1" max="30" step="1" placeholder="自定义天数（最多30天）" aria-label="自定义禁言天数，最多30天" style="width:100%;height:32px;padding:0 9px;border:1px solid var(--line);border-radius:8px;font-size:12px"><div class="msg-mute-actions"><button class="msg-btn" id="msg-mute-cancel" type="button">取消</button><button class="msg-btn primary" id="msg-mute-confirm" type="button">确认禁言</button></div></div></div>
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
