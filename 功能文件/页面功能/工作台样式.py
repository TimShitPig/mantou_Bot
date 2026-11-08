"""运营工作台的设计变量与响应式页面样式。"""

工作台样式 = """
    body:not(.messages-workspace) {
      --studio-canvas:#f4f1fc; --studio-card:#fffdfd; --studio-ink:#27213d; --studio-muted:#625c75;
      --studio-border:#e5dfef; --studio-accent:#6659c1; --studio-accent-soft:#eee9ff;
      --studio-soft:#f7f4fc; --studio-peach:#ffe9d8; --studio-peach-ink:#87462e;
      --studio-mint:#e6f5ed; --studio-mint-ink:#2d6950; --studio-hover:#f1ecfa;
      --studio-wash:linear-gradient(112deg,#f4eeff 1%,#f8f2ff 53%,#fff0e4 100%);
      --studio-shadow:0 8px 24px #40316b0d,0 2px 4px #40316b06;
      --ink:var(--studio-ink); --muted:var(--studio-muted); --soft:var(--studio-muted); --line:var(--studio-border);
      --bg:var(--studio-canvas); --panel:var(--studio-card); --raised:var(--studio-soft);
      --input:var(--studio-soft); --hover:var(--studio-hover); --shadow:var(--studio-shadow);
      --primary:var(--studio-accent); --primary-dark:#5243ac; --primary-soft:var(--studio-accent-soft);
      --accent-fill:#6659c1; --accent-hover:#5243ac; --mint:var(--studio-mint); --mint-ink:var(--studio-mint-ink);
      --peach:var(--studio-peach); --peach-ink:var(--studio-peach-ink);
      background:radial-gradient(ellipse at 0 0,#fff0ddad,transparent 33rem),
                 radial-gradient(ellipse at 94% 0,#e5e7ffb3,transparent 44rem),var(--studio-canvas);
      color:var(--studio-ink);
      /* 工作台随文档滚动。消息记录仍由原来的视口内面板滚动。 */
      height:auto;
      overflow-x:clip;
      overflow-y:visible;
    }
    :root[data-theme="dark"] body:not(.messages-workspace) {
      --studio-canvas:#211c2e; --studio-card:#2d263d; --studio-ink:#fbf4ff; --studio-muted:#c3b8d4;
      --studio-border:#493d5d; --studio-accent:#c6b6ff; --studio-accent-soft:#3e325a;
      --studio-soft:#332b45; --studio-peach:#48332e; --studio-peach-ink:#ffd0b4;
      --studio-mint:#263c35; --studio-mint-ink:#a2dcc0; --studio-hover:#3c3153;
      --studio-wash:linear-gradient(112deg,#382a50 1%,#332744 58%,#422d36 100%);
      --studio-shadow:0 8px 24px #160e2354;
      --primary-dark:#e2d7ff; --accent-fill:#9e88ef; --accent-hover:#b9a7ff;
      background:radial-gradient(ellipse at 0 0,#49334799,transparent 33rem),
                 radial-gradient(ellipse at 94% 0,#403259aa,transparent 44rem),var(--studio-canvas);
    }
    .studio-sidebar { display:none; }
    body:not(.messages-workspace) .shell {
      --studio-space:clamp(12px,2vw,24px);
      display:grid; width:min(1740px,100%); height:auto; min-height:100vh; min-height:100dvh;
      margin:0 auto; padding:12px var(--studio-space) var(--studio-space);
      grid-template-columns:218px minmax(0,1fr);
      grid-template-rows:auto minmax(0,1fr); grid-template-areas:"top top" "side main";
      gap:var(--studio-space); align-content:start; overflow:visible;
    }
    body:not(.messages-workspace) .shell.bot-picker-open {
      grid-template-columns:minmax(0,1fr); grid-template-areas:"top" "main";
    }
    body:not(.messages-workspace) .shell > #console-sidebar { display:none; }
    body:not(.messages-workspace) .shell:not(.bot-picker-open) > .studio-sidebar {
      grid-area:side; display:flex; flex-direction:column; align-self:start; position:sticky; top:16px;
      min-width:0; padding:13px; gap:15px;
      border:1px solid var(--studio-border); border-radius:22px;
      background:var(--studio-card); box-shadow:var(--studio-shadow);
    }
    body:not(.messages-workspace) .shell > .topbar {
      position:relative; display:flex; gap:16px; min-width:0; min-height:61px;
      padding:3px 5px; background:transparent; border:0;
    }
    body:not(.messages-workspace) .topbar .brand { gap:11px; flex:1 1 auto; }
    body:not(.messages-workspace) .topbar .brand-mark {
      width:43px; height:43px; flex:0 0 43px; border:0; border-radius:15px;
      background:var(--studio-peach); color:var(--studio-peach-ink); box-shadow:none;
    }
    body:not(.messages-workspace) .topbar .brand-mark svg { width:26px; height:26px; }
    body:not(.messages-workspace) .topbar .studio-brand-copy { max-width:none; display:flex; flex-wrap:wrap; align-items:center; gap:4px 8px; min-width:0; }
    body:not(.messages-workspace) .topbar .studio-brand-title {
      margin:0; color:var(--studio-ink); font:800 clamp(17px,2.1vw,29px)/1.18 system-ui,sans-serif;
      letter-spacing:.01em; overflow:visible; text-overflow:clip; white-space:normal;
    }
    body:not(.messages-workspace) .topbar .version-badge {
      margin:0; border:1px solid var(--studio-border); border-radius:999px; padding:2px 8px;
      color:var(--studio-muted); background:var(--studio-card);
    }
    body:not(.messages-workspace) .topbar .version-badge[hidden] { display:none; }
    body:not(.messages-workspace) .topbar .top-actions { gap:8px; flex:0 0 auto; }
    body:not(.messages-workspace) .topbar .theme-control { padding:0; border:0; background:none; }
    body:not(.messages-workspace) .topbar .theme-toggle-button,
    body:not(.messages-workspace) .topbar .admin-chip {
      min-height:41px; border:1px solid var(--studio-border); border-radius:13px;
      background:var(--studio-card); color:var(--studio-ink);
    }
    body:not(.messages-workspace) .topbar .theme-toggle-button { width:41px; color:var(--studio-accent); }
    body:not(.messages-workspace) .topbar .theme-toggle-button:hover,
    body:not(.messages-workspace) .topbar .admin-chip:hover,
    body:not(.messages-workspace) .topbar .admin-chip[aria-expanded="true"] { background:var(--studio-accent-soft); }
    body:not(.messages-workspace) .topbar .admin-popover { z-index:30; border-radius:15px; }
    .studio-robot {
      display:grid; grid-template-columns:39px minmax(0,1fr); gap:10px; align-items:center;
      padding:12px 10px; border-radius:14px; background:var(--studio-wash);
    }
    .studio-robot strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:14px; }
    .studio-robot small { display:inline-flex; font-size:11px; }
    .studio-bot-avatar {
      width:39px; height:39px; position:relative; overflow:hidden; border-radius:13px;
      border:1px solid var(--studio-border); background:var(--studio-card); color:var(--studio-accent);
    }
    .studio-bot-avatar .avatar-face { inset:0; display:grid; place-items:center; font-size:14px; letter-spacing:0; color:inherit; }
    .studio-bot-avatar.has-image .avatar-face { display:none; }
    .studio-nav { display:grid; gap:12px; }
    .studio-nav-group { display:grid; gap:4px; }
    .studio-nav-group > p {
      margin:0 0 3px; padding:0 10px; color:var(--studio-muted);
      font-size:11px; font-weight:720; letter-spacing:.075em;
    }
    .studio-nav-group a {
      display:flex; align-items:center; gap:9px; min-height:40px; padding:7px 10px;
      border-radius:11px; text-decoration:none; color:var(--studio-ink); font-weight:620;
    }
    .studio-nav-group a:hover { background:var(--studio-hover); }
    .studio-nav-group a[aria-current="page"] { background:var(--studio-accent-soft); color:var(--studio-accent); }
    .studio-nav-icon {
      width:26px; height:26px; display:grid; place-items:center; flex:0 0 auto;
      border-radius:8px; background:var(--studio-accent-soft); color:var(--studio-accent);
    }
    .studio-nav-group:nth-child(2) .studio-nav-icon { background:var(--studio-peach); color:var(--studio-peach-ink); }
    .studio-nav-group:nth-child(3) .studio-nav-icon { background:var(--studio-mint); color:var(--studio-mint-ink); }
    .studio-nav-icon svg,.studio-exit svg { width:17px; height:17px; }
    .studio-exit {
      display:flex; align-items:center; justify-content:center; gap:7px; min-height:38px;
      padding:7px; background:var(--studio-soft); border:1px solid var(--studio-border);
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
      border:1px solid var(--studio-border); border-radius:18px;
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
      border-radius:19px; background:var(--studio-card); color:var(--studio-ink); box-shadow:var(--studio-shadow);
    }
    .studio-kicker {
      display:block; color:var(--studio-accent); font-size:10px; font-weight:800; letter-spacing:.11em;
    }
    .studio-card-head { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:10px; }
    .studio-card-head h2 { margin:3px 0 0; font-size:18px; font-weight:750; }
    #page-dashboard.studio-dashboard:not([hidden]) { display:grid; gap:16px; margin:0; }
    .studio-hero {
      display:grid; grid-template-columns:minmax(0,1fr) clamp(142px,27%,245px);
      align-items:center; gap:12px; background:var(--studio-wash);
    }
    .studio-hero h2 { margin:5px 0 6px; font-size:clamp(20px,3vw,32px); line-height:1.3; overflow-wrap:anywhere; }
    .studio-hero p,.studio-picker-banner p { max-width:58ch; margin:0; color:var(--studio-muted); }
    .studio-book-art { display:block; width:100%; }
    .studio-primary {
      display:inline-flex; align-items:center; gap:7px; min-height:38px; margin-top:15px;
      padding:7px 13px; border-radius:11px; background:var(--accent-fill); color:#fff;
      text-decoration:none; font-size:13px; font-weight:710;
    }
    :root[data-theme="dark"] .studio-primary { color:#201631; }
    .studio-primary:hover { background:var(--accent-hover); }
    .studio-primary svg { width:17px; height:17px; }
    .studio-dashboard-grid { display:grid; grid-template-columns:minmax(0,1.6fr) minmax(0,1fr); gap:16px; align-items:start; }
    .studio-dashboard-side { display:grid; gap:16px; }
    .studio-service-list { display:grid; margin-top:12px; }
    .studio-service-row {
      display:grid; grid-template-columns:38px minmax(0,1fr) minmax(0,max-content) 33px;
      align-items:center; gap:9px; min-height:60px; padding:9px 0; border-top:1px solid var(--studio-border);
    }
    .studio-service-icon {
      display:grid; place-items:center; width:36px; height:36px;
      border-radius:11px; color:var(--studio-accent); background:var(--studio-accent-soft);
    }
    .studio-service-row:nth-child(2) .studio-service-icon,.studio-guide .studio-service-icon {
      color:var(--studio-peach-ink); background:var(--studio-peach);
    }
    .studio-service-row:nth-child(3) .studio-service-icon { color:var(--studio-mint-ink); background:var(--studio-mint); }
    .studio-service-icon svg { width:20px; height:20px; }
    .studio-service-row h3 { margin:0; font-size:14px; font-weight:720; }
    .studio-service-row small { display:block; color:var(--studio-muted); font-size:11px; overflow-wrap:anywhere; }
    .studio-service-value {
      padding:4px 8px; border-radius:999px; background:var(--studio-soft); color:var(--studio-ink);
      font-size:12px; font-weight:700; text-align:right; overflow-wrap:anywhere;
    }
    .studio-service-row > button,.studio-guide > a {
      display:grid; place-items:center; width:33px; height:33px; padding:0;
      border:1px solid var(--studio-border); border-radius:10px; background:var(--studio-card); color:var(--studio-accent);
    }
    .studio-service-row > button:hover,.studio-guide > a:hover { background:var(--studio-accent-soft); }
    .studio-service-row > button svg,.studio-guide > a svg,.studio-health > a svg { width:17px; height:17px; }
    .studio-health dl { margin:10px 0; }
    .studio-health dl div { display:flex; flex-wrap:wrap; justify-content:space-between; gap:2px 9px; padding:8px 0; border-bottom:1px solid var(--studio-border); }
    .studio-health dt { color:var(--studio-muted); font-size:12px; }
    .studio-health dd { margin:0; font-weight:680; font-size:12px; overflow-wrap:anywhere; }
    .studio-health > a { display:inline-flex; align-items:center; gap:4px; color:var(--studio-accent); text-decoration:none; font-weight:700; font-size:12px; }
    .studio-health > a:hover { text-decoration:underline; }
    .studio-guide { display:grid; grid-template-columns:36px minmax(0,1fr) 33px; align-items:center; gap:10px; }
    .studio-guide h2 { margin:0; font-size:15px; }
    .studio-guide p { margin:3px 0 0; color:var(--studio-muted); font-size:12px; }

    body:not(.messages-workspace) .studio-picker {
      width:min(1100px,100%); margin:0 auto; padding:clamp(6px,2vw,24px) 0 32px;
    }
    .studio-picker-banner {
      display:grid; grid-template-columns:minmax(0,1fr) minmax(115px,26%); align-items:center; gap:14px;
      padding:clamp(17px,4vw,42px); border:1px solid var(--studio-border); border-radius:23px;
      background:var(--studio-wash); box-shadow:var(--studio-shadow);
    }
    .studio-picker-banner h1 { margin:4px 0 7px; font-size:clamp(26px,4.5vw,42px); line-height:1.2; }
    .studio-picker-list-head { display:flex; align-items:center; justify-content:space-between; gap:10px; margin:20px 0 11px; }
    .studio-picker-list-head h2 { margin:0; font-size:18px; }
    body:not(.messages-workspace) .studio-picker .bot-profile-list { grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr)); gap:14px; }
    body:not(.messages-workspace) .studio-picker .bot-selector-item {
      grid-template-columns:48px minmax(0,1fr) 20px; column-gap:10px; row-gap:14px;
      min-height:0; padding:17px; border:1px solid var(--studio-border); border-radius:18px;
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

    @media (max-width:1100px) {
      body:not(.messages-workspace) .shell { grid-template-columns:184px minmax(0,1fr); }
      .studio-nav-group a { padding-inline:7px; }
    }
    @media (max-width:900px) {
      .studio-dashboard-grid { grid-template-columns:minmax(0,1fr); }
      .studio-dashboard-side { grid-template-columns:repeat(2,minmax(0,1fr)); align-items:start; }
    }
    @media (max-width:740px) {
      body:not(.messages-workspace) .shell {
        grid-template-columns:minmax(0,1fr); grid-template-rows:auto auto minmax(0,1fr);
        grid-template-areas:"top" "side" "main"; gap:10px;
      }
      body:not(.messages-workspace) .shell.bot-picker-open { grid-template-rows:auto minmax(0,1fr); }
      body:not(.messages-workspace) .shell:not(.bot-picker-open) > .studio-sidebar {
        position:static; display:grid; grid-template-columns:minmax(0,1fr) auto; gap:9px;
        padding:9px; border-radius:17px;
      }
      .studio-robot { grid-template-columns:29px minmax(0,1fr); padding:5px 8px; gap:7px; }
      .studio-bot-avatar { width:29px; height:29px; border-radius:9px; }
      .studio-robot strong { font-size:12px; }
      .studio-robot small { font-size:10px; }
      .studio-exit { grid-area:1 / 2; align-self:center; padding-inline:8px; min-height:34px; font-size:11px; }
      .studio-nav { grid-column:1 / -1; display:flex; flex-wrap:wrap; gap:5px 8px; }
      .studio-nav-group { display:flex; flex-wrap:wrap; gap:4px; }
      .studio-nav-group > p { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
      .studio-nav-group a { min-height:34px; padding:4px 6px; gap:4px; font-size:12px; }
      .studio-nav-icon { width:22px; height:22px; border-radius:6px; }
      .studio-nav-icon svg { width:14px; height:14px; }
      body:not(.messages-workspace) .topbar .brand-mark { width:35px; height:35px; flex-basis:35px; border-radius:12px; }
      body:not(.messages-workspace) .topbar .brand-mark svg { width:22px; height:22px; }
      body:not(.messages-workspace) .shell > .topbar { gap:5px; min-height:47px; padding-inline:1px; }
      body:not(.messages-workspace) .topbar .theme-toggle-button,
      body:not(.messages-workspace) .topbar .admin-chip { min-height:36px; }
      body:not(.messages-workspace) .topbar .theme-toggle-button { width:36px; }
      body:not(.messages-workspace) .topbar #admin-name { max-width:65px; }
    }
    @media (max-width:470px) {
      .studio-dashboard-side { grid-template-columns:minmax(0,1fr); }
      .studio-hero,.studio-picker-banner { grid-template-columns:minmax(0,1fr) 85px; gap:5px; }
      .studio-hero p,.studio-picker-banner p { font-size:12px; }
      .studio-service-row { grid-template-columns:32px minmax(0,1fr) minmax(0,max-content) 30px; gap:6px; }
      .studio-service-row .studio-service-icon { width:30px; height:30px; }
      .studio-service-row > button { width:30px; height:30px; }
      .studio-service-value { max-width:84px; font-size:11px; }
      body:not(.messages-workspace) .topbar #admin-name { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
    }
"""
