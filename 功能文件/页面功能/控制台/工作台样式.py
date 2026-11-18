"""运营工作台的设计变量与响应式页面样式。"""

工作台样式 = """
    body {
      --studio-canvas:#f6f5f8; --studio-card:#ffffff; --studio-ink:#282632; --studio-muted:#696574;
      --studio-border:#e6e3eb; --studio-accent:#6554b2; --studio-accent-soft:#eeeaf8;
      --studio-soft:#f5f3f8; --studio-peach:#f8eee5; --studio-peach-ink:#865d40;
      --studio-mint:#eaf3ee; --studio-mint-ink:#356850; --studio-hover:#eeebf4;
      --studio-wash:#f1edf8;
      --studio-shadow:none; --studio-float-shadow:0 8px 28px #28203214;
      --studio-space:clamp(12px,2vw,24px); --studio-sidebar-width:232px;
    }
    body:not(.messages-workspace) {
      --ink:var(--studio-ink); --muted:var(--studio-muted); --soft:var(--studio-muted); --line:var(--studio-border);
      --bg:var(--studio-canvas); --panel:var(--studio-card); --raised:var(--studio-soft);
      --input:var(--studio-soft); --hover:var(--studio-hover); --shadow:var(--studio-shadow);
      --primary:var(--studio-accent); --primary-dark:#54439b; --primary-soft:var(--studio-accent-soft);
      --accent-fill:#6554b2; --accent-hover:#54439b; --mint:var(--studio-mint); --mint-ink:var(--studio-mint-ink);
      --peach:var(--studio-peach); --peach-ink:var(--studio-peach-ink);
      background:var(--studio-canvas);
      color:var(--studio-ink);
      /* 工作台随文档滚动。消息记录仍由原来的视口内面板滚动。 */
      height:auto;
      overflow-x:clip;
      overflow-y:visible;
    }
    :root[data-theme="dark"] body {
      --studio-canvas:#19171f; --studio-card:#24212c; --studio-ink:#eeeaf3; --studio-muted:#b1aabc;
      --studio-border:#3d3747; --studio-accent:#c1b0ef; --studio-accent-soft:#342c47;
      --studio-soft:#2b2735; --studio-peach:#3a2e2b; --studio-peach-ink:#dfb99c;
      --studio-mint:#26382f; --studio-mint-ink:#a2cdb3; --studio-hover:#332d40;
      --studio-wash:#2c2638;
      --studio-shadow:none; --studio-float-shadow:0 10px 32px #00000040;
    }
    :root[data-theme="dark"] body:not(.messages-workspace) {
      --primary-dark:#d6c9f4; --accent-fill:#7963c0; --accent-hover:#745cba;
      background:var(--studio-canvas);
    }
    body:not(.messages-workspace) .shell {
      display:grid; width:min(1740px,100%); height:auto; min-height:100vh; min-height:100dvh;
      margin:0 auto; padding:12px var(--studio-space) var(--studio-space);
      grid-template-columns:var(--studio-sidebar-width) minmax(0,1fr);
      grid-template-rows:auto minmax(0,1fr); grid-template-areas:"top top" "side main";
      gap:var(--studio-space); align-content:start; overflow:visible;
    }
    body:not(.messages-workspace) .shell.bot-picker-open {
      grid-template-columns:minmax(0,1fr); grid-template-areas:"top" "main";
    }
    .shell > .studio-sidebar:not([hidden]) {
      grid-area:side; display:flex; flex-direction:column; align-self:start; position:sticky; top:16px;
      min-width:0; max-height:calc(100dvh - 32px); padding:16px; gap:18px;
      border:1px solid var(--studio-border); border-radius:16px;
      background:var(--studio-card); box-shadow:var(--studio-shadow);
    }
    .studio-sidebar :focus-visible { outline:2px solid var(--studio-accent); outline-offset:2px; }
    .shell > .topbar {
      position:relative; display:flex; gap:16px; min-width:0; min-height:61px;
      padding:3px 5px; background:transparent; border:0;
    }
    .topbar .brand { gap:11px; flex:1 1 auto; }
    .topbar .brand-mark {
      width:43px; height:43px; flex:0 0 43px; border:0; border-radius:15px;
      background:var(--studio-peach); color:var(--studio-peach-ink); box-shadow:none;
    }
    .topbar .brand-mark svg { width:26px; height:26px; }
    .topbar .studio-brand-copy { max-width:none; display:flex; flex-wrap:wrap; align-items:center; gap:4px 8px; min-width:0; }
    .topbar .studio-brand-title {
      margin:0; color:var(--studio-ink); font:800 clamp(17px,2.1vw,29px)/1.18 system-ui,sans-serif;
      letter-spacing:.01em; overflow:visible; text-overflow:clip; white-space:normal;
    }
    .topbar .version-badge {
      margin:0; border:1px solid var(--studio-border); border-radius:999px; padding:2px 8px;
      color:var(--studio-muted); background:var(--studio-card);
    }
    .topbar .version-badge[hidden] { display:none; }
    .topbar .top-actions { gap:8px; flex:0 0 auto; }
    .topbar .theme-control { padding:0; border:0; background:none; }
    .topbar .theme-toggle-button,
    .topbar .admin-chip {
      min-height:41px; border:1px solid var(--studio-border); border-radius:13px;
      background:var(--studio-card); color:var(--studio-ink);
    }
    .topbar .theme-toggle-button { width:41px; color:var(--studio-accent); }
    .topbar .theme-toggle-button:hover,
    .topbar .admin-chip:hover,
    .topbar .admin-chip[aria-expanded="true"] { background:var(--studio-accent-soft); }
    .topbar .admin-popover { z-index:30; border-radius:12px; box-shadow:var(--studio-float-shadow); }
    .studio-robot {
      display:grid; grid-template-columns:39px minmax(0,1fr); gap:10px; align-items:center;
      flex:none; padding:12px; border-radius:14px; background:var(--studio-wash);
    }
    .studio-robot strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:14px; }
    .studio-robot small { display:inline-flex; font-size:11px; }
    .studio-bot-avatar {
      width:39px; height:39px; position:relative; overflow:hidden; border-radius:13px;
      border:1px solid var(--studio-border); background:var(--studio-card); color:var(--studio-accent);
    }
    .studio-bot-avatar .avatar-face { inset:0; display:grid; place-items:center; font-size:14px; letter-spacing:0; color:inherit; }
    .studio-bot-avatar.has-image .avatar-face { display:none; }
    .studio-nav { display:grid; align-content:start; gap:15px; min-height:0; overflow-y:auto; scrollbar-width:thin; padding:2px; }
    .studio-nav-group { display:grid; gap:7px; }
    .studio-nav-group > p {
      margin:0 0 3px; padding:0 9px; color:var(--studio-muted);
      font-size:11px; font-weight:720; letter-spacing:.075em;
    }
    .studio-nav-group a {
      display:flex; align-items:center; gap:10px; min-height:43px; padding:8px 9px;
      border-radius:11px; text-decoration:none; color:var(--studio-ink); font-weight:620;
    }
    .studio-nav-group a:focus-visible { outline-offset:-2px; }
    .studio-nav-group a:hover { background:var(--studio-hover); }
    .studio-nav-group a[aria-current="page"] { background:var(--studio-accent-soft); color:var(--studio-accent); }
    .studio-nav-icon {
      width:26px; height:26px; display:grid; place-items:center; flex:0 0 auto;
      border-radius:8px; background:var(--studio-accent-soft); color:var(--studio-accent);
    }
    .studio-nav-group:nth-child(2) .studio-nav-icon { background:var(--studio-peach); color:var(--studio-peach-ink); }
    .studio-nav-group:nth-child(3) .studio-nav-icon { background:var(--studio-mint); color:var(--studio-mint-ink); }
    .studio-nav-icon svg,.studio-exit svg { width:17px; height:17px; }
    .studio-sidebar-actions { display:flex; flex:none; align-items:stretch; gap:5px; }
    .studio-message-tools { display:none; }
    .studio-message-tools button {
      display:grid; place-items:center; width:31px; padding:0;
      border:1px solid var(--studio-border); border-radius:9px;
      background:var(--studio-soft); color:var(--studio-muted);
    }
    .studio-message-tools button:hover,.studio-message-tools button[aria-expanded="true"] {
      background:var(--studio-accent-soft); color:var(--studio-accent);
    }
    .studio-message-tools svg { width:17px; height:17px; }
    .studio-exit {
      display:flex; align-items:center; justify-content:center; gap:5px; min-height:40px; flex:1;
      padding:6px; background:var(--studio-soft); border:1px solid var(--studio-border);
      border-radius:11px; color:var(--studio-muted); font-weight:650; white-space:nowrap;
    }
    .studio-exit:hover { color:var(--studio-accent); background:var(--studio-accent-soft); }

    body:not(.messages-workspace) .shell > .main {
      min-width:0; height:auto; min-height:0; overflow:visible; background:transparent;
    }
    body:not(.messages-workspace) #console-workspace {
      width:100%; max-width:none; padding:0; margin:0;
    }
    body:not(.messages-workspace) #console-workspace > .page-heading {
      display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap;
      gap:10px 18px; margin:0 0 16px; padding:15px clamp(15px,2vw,23px);
      border:1px solid var(--studio-border); border-radius:14px;
      background:var(--studio-card); box-shadow:var(--studio-shadow);
    }
    body:not(.messages-workspace) #console-workspace > .page-heading h1 {
      margin:0; color:var(--studio-ink); font:770 clamp(21px,2.3vw,28px)/1.25 system-ui,sans-serif;
    }
    body:not(.messages-workspace) #console-workspace > .page-heading .page-kicker {
      margin:0 0 5px; color:var(--studio-accent); font-size:11px; font-weight:720;
    }
    body:not(.messages-workspace) #console-workspace > .page-heading #page-subtitle {
      margin:5px 0 0; color:var(--studio-muted); font-size:13px;
    }
    body:not(.messages-workspace) .updated-label {
      color:var(--studio-muted); background:var(--studio-soft);
      border-color:var(--studio-border); border-radius:999px;
    }
    body:not(.messages-workspace) :is(.studio-sidebar,.studio-dashboard,.studio-picker,.topbar) :focus-visible {
      outline:2px solid var(--studio-accent); outline-offset:3px;
    }
    .studio-card {
      min-width:0; padding:clamp(16px,2.3vw,25px); border:1px solid var(--studio-border);
      border-radius:14px; background:var(--studio-card); color:var(--studio-ink); box-shadow:var(--studio-shadow);
    }
    .studio-kicker {
      display:block; color:var(--studio-accent); font-size:10px; font-weight:800; letter-spacing:.11em;
    }
    #page-dashboard.studio-dashboard:not([hidden]) { display:grid; gap:16px; margin:0; }
    .studio-picker-banner p { max-width:58ch; margin:0; color:var(--studio-muted); }
    .studio-book-art { display:block; width:100%; }
    .studio-primary {
      display:inline-flex; align-items:center; gap:7px; min-height:38px; margin-top:15px;
      padding:7px 13px; border-radius:11px; background:var(--accent-fill); color:#fff;
      text-decoration:none; font-size:13px; font-weight:710;
    }
    :root[data-theme="dark"] .studio-primary { color:#fff; }
    .studio-primary:hover { background:var(--accent-hover); }
    .studio-primary svg { width:17px; height:17px; }
    .studio-service-icon {
      display:grid; place-items:center; width:36px; height:36px;
      border-radius:11px; color:var(--studio-accent); background:var(--studio-accent-soft);
    }
    .studio-service-icon svg { width:20px; height:20px; }

    body:not(.messages-workspace) .studio-picker {
      width:min(1100px,100%); margin:0 auto; padding:clamp(6px,2vw,24px) 0 32px;
    }
    .studio-picker-banner {
      display:grid; grid-template-columns:minmax(0,1fr) minmax(115px,26%); align-items:center; gap:14px;
      padding:clamp(17px,4vw,42px); border:1px solid var(--studio-border); border-radius:16px;
      background:var(--studio-wash); box-shadow:var(--studio-shadow);
    }
    .studio-picker-banner h1 { margin:4px 0 7px; font-size:clamp(26px,4.5vw,42px); line-height:1.2; }
    .studio-picker-list-head { display:flex; align-items:center; justify-content:space-between; gap:10px; margin:20px 0 11px; }
    .studio-picker-list-head h2 { margin:0; font-size:18px; }
    body:not(.messages-workspace) .studio-picker .bot-profile-list { grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr)); gap:14px; }
    body:not(.messages-workspace) .studio-picker .bot-selector-item {
      grid-template-columns:48px minmax(0,1fr) 20px; column-gap:10px; row-gap:14px;
      min-height:0; padding:17px; border:1px solid var(--studio-border); border-radius:14px;
      background:var(--studio-card); box-shadow:var(--studio-shadow); align-content:start;
    }
    body:not(.messages-workspace) .studio-picker .bot-selector-item:hover { border-color:var(--studio-accent); }
    body:not(.messages-workspace) .studio-picker .bot-selector-avatar {
      width:48px; height:48px; border-radius:15px; background:var(--studio-accent-soft); box-shadow:none;
    }
    .studio-picker .bot-selector-copy strong { font-size:16px; font-weight:750; }
    .studio-picker .bot-selector-stats { padding:0; border:0; }
    .studio-picker .bot-selector-stat {
      display:grid; grid-template-columns:15px minmax(0,1fr); align-items:center; gap:3px 5px;
      padding:8px; border-radius:10px; background:var(--studio-soft); color:var(--studio-muted); font-size:11px;
    }
    .studio-picker .bot-selector-stat strong { grid-column:2; font-size:16px; line-height:1.25; }
    body:not(.messages-workspace) .studio-picker .bot-selector-empty {
      padding:19px; border:1px dashed var(--studio-border); border-radius:14px; background:var(--studio-card);
    }
    body:not(.messages-workspace) .studio-picker .bot-picker-error { border-radius:12px; }


    body:not(.messages-workspace) ::selection { color:var(--studio-ink); background:var(--studio-accent-soft); }
    body:not(.messages-workspace) :is(input,textarea,[contenteditable="true"]) { caret-color:var(--studio-accent); }
    :root body:not(.messages-workspace) .primary-button { background:var(--accent-fill); color:#fff; box-shadow:none; }
    :root body:not(.messages-workspace) .primary-button:hover:not(:disabled) { background:var(--accent-hover); }
    body:not(.messages-workspace) .switch { background:#d9d4e1; }
    body:not(.messages-workspace) .switch.on { background:var(--accent-fill); }
    :root[data-theme="dark"] body:not(.messages-workspace) .switch { background:#4a4357; }
    :root[data-theme="dark"] body:not(.messages-workspace) .switch.on { background:var(--accent-fill); }
    body:not(.messages-workspace) :is(.outline-button,.text-button,.primary-button):focus-visible {
      outline:2px solid var(--studio-accent); outline-offset:3px;
    }

    @media (max-width:1100px) {
      body { --studio-sidebar-width:204px; }
      .studio-nav-group a { padding-inline:7px; }
    }
    @media (max-width:760px) {
      body:not(.messages-workspace) .shell {
        grid-template-columns:minmax(0,1fr); grid-template-rows:auto auto minmax(0,1fr);
        grid-template-areas:"top" "side" "main"; gap:10px;
      }
      body:not(.messages-workspace) .shell.bot-picker-open { grid-template-rows:auto minmax(0,1fr); }
      .shell > .studio-sidebar:not([hidden]) {
        position:static; display:grid; grid-template-columns:minmax(0,1fr) auto; gap:9px;
        padding:9px; border-radius:14px; max-height:none;
      }
      :root body.messages-workspace.msg-mobile-chat-view .shell > .studio-sidebar { display:none; }
      .studio-robot { grid-template-columns:29px minmax(0,1fr); padding:5px 8px; gap:7px; }
      .studio-bot-avatar { width:29px; height:29px; border-radius:9px; }
      .studio-robot strong { font-size:12px; }
      .studio-robot small { font-size:10px; }
      .studio-sidebar-actions { grid-area:1 / 2; align-self:center; }
      .messages-workspace .studio-sidebar-actions { margin-top:0; }
      .studio-exit { padding-inline:7px; min-height:34px; font-size:11px; }
      .studio-nav { grid-column:1 / -1; display:flex; flex-wrap:wrap; gap:5px 8px; overflow:visible; padding:0; }
      .studio-nav-group { display:flex; flex-wrap:wrap; gap:4px; }
      .studio-nav-group > p { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
      .studio-nav-group a { min-height:34px; padding:4px 6px; gap:4px; font-size:12px; }
      .studio-nav-icon { width:22px; height:22px; border-radius:6px; }
      .studio-nav-icon svg { width:14px; height:14px; }
      .messages-workspace .studio-message-tools { display:flex; flex:none; gap:5px; }
      body:not(.messages-workspace) .topbar .brand-mark { width:35px; height:35px; flex-basis:35px; border-radius:12px; }
      body:not(.messages-workspace) .topbar .brand-mark svg { width:22px; height:22px; }
      body:not(.messages-workspace) .shell > .topbar { gap:5px; min-height:47px; padding-inline:1px; }
      body:not(.messages-workspace) .topbar .theme-toggle-button,
      body:not(.messages-workspace) .topbar .admin-chip { min-height:36px; }
      body:not(.messages-workspace) .topbar .theme-toggle-button { width:36px; }
      body:not(.messages-workspace) .topbar #admin-name { max-width:65px; }
    }
    @media (max-width:470px) {
      .studio-picker-banner { grid-template-columns:minmax(0,1fr) 85px; gap:5px; }
      .studio-picker-banner p { font-size:12px; }
      body:not(.messages-workspace) .topbar #admin-name { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
    }
"""
