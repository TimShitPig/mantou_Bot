"""馒头控制台的样式资源。"""

控制台样式 = """
    :root { color-scheme:light; --ink:#17324a; --muted:#5f778b; --soft:#6f8296; --line:#d9e5ef; --bg:#edf3f8; --panel:#fff; --raised:#f4f8fc; --input:#f6f9fc; --hover:#e9f2fa; --primary:#067ca7; --primary-dark:#05688d; --primary-soft:#e1f3fb; --accent-fill:#087eaa; --accent-hover:#066b91; --mint:#e1f5ec; --mint-ink:#217c58; --peach:#fff0df; --peach-ink:#a46722; --yellow:#fff5de; --yellow-ink:#94651f; --pink:#fff0f5; --pink-ink:#ac4c72; --danger:#bb4259; --danger-bg:#fff0f3; --danger-line:#f0c8d1; --shadow:0 8px 24px rgba(25,63,93,.045); --nav-bg:#0c1d30; --nav-ink:#acbfd2; --nav-line:#22384e; --nav-active:#183c55; --nav-accent:#66dcff; }
    * { box-sizing:border-box; }
    .msg-group-profile { margin:0 0 18px; padding:14px; border:1px solid var(--line); border-radius:10px; }
    .msg-group-profile-title { display:block; margin-bottom:12px; font-size:12px; }
    .msg-group-profile dl { display:grid; gap:6px; min-width:0; margin:0; }
    .msg-group-profile dt { color:var(--muted); font-size:11px; }
    .msg-group-profile dt:not(:first-child) { margin-top:7px; }
    .msg-group-profile dd { min-width:0; margin:0; font-size:12px; line-height:1.7; white-space:pre-wrap; overflow-wrap:anywhere; }
    .msg-group-profile-tags { display:flex; flex-wrap:wrap; align-items:flex-start; gap:6px; }
    .msg-group-profile-tag { display:inline-block; min-width:0; max-width:100%; padding:2px 9px; border-radius:999px; background:var(--primary-soft); color:var(--primary); font-size:11px; white-space:pre-wrap; overflow-wrap:anywhere; }
    .msg-group-profile-empty { color:var(--muted); }
    html { scroll-behavior:smooth; }
    body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.55 Inter,"PingFang SC","Microsoft YaHei",ui-sans-serif,system-ui,sans-serif; overflow-x:hidden; }
    button,input { font:inherit; }
    button { cursor:pointer; }
    .shell { min-height:100vh; display:grid; grid-template-columns:252px minmax(0,1fr); grid-template-rows:64px minmax(0,1fr); grid-template-areas:"top top" "side main"; }
    .topbar { grid-area:top; display:flex; align-items:center; justify-content:space-between; gap:20px; padding:0 30px; background:var(--panel); border-bottom:1px solid var(--line); }
    .brand { display:flex; align-items:center; gap:10px; min-width:0; }
    .brand-mark { width:34px; height:34px; flex:0 0 34px; display:grid; place-items:center; border-radius:11px; background:var(--primary-soft); color:var(--primary); font-size:16px; font-weight:800; }
    .brand strong { font-size:16px; letter-spacing:.1px; }
    .version-badge { display:inline-flex; margin-left:7px; padding:3px 8px; border-radius:999px; background:#f3f3f8; color:var(--muted); font-size:11px; font-weight:650; }
    .top-actions { display:flex; align-items:center; gap:16px; }
    .theme-control { display:inline-flex; align-items:center; gap:5px; min-height:32px; padding:3px 6px 3px 9px; border:1px solid transparent; border-radius:8px; color:var(--muted); font-size:11px; font-weight:650; transition:background .18s ease,border-color .18s ease; }
    .theme-control:hover,.theme-control:focus-within { border-color:var(--line); background:var(--raised); }
    .theme-toggle-button { display:grid; place-items:center; width:28px; height:28px; padding:0; border:0; border-radius:7px; background:transparent; color:var(--primary); cursor:pointer; transition:background .18s ease,color .18s ease,transform .18s ease; }
    .theme-toggle-button:hover,.theme-toggle-button:focus-visible { background:var(--primary-soft); color:var(--primary-dark); outline:none; }
    .theme-toggle-button:active { transform:scale(.92); }
    .theme-control-icon { display:inline-block; color:currentColor; font-size:16px; line-height:1; transform-origin:center; }
    .theme-select-wrap { display:inline-flex; align-items:center; }
    .theme-control select { min-height:26px; padding:2px 20px 2px 3px; border:0; border-radius:5px; background:transparent; color:var(--ink); font-size:11px; font-weight:650; cursor:pointer; outline:none; }
    .theme-control select option { background:var(--panel); color:var(--ink); }
    html.theme-switching *,html.theme-switching *::before,html.theme-switching *::after { transition-property:background-color,border-color,color,box-shadow,fill,stroke !important; transition-duration:.28s !important; transition-timing-function:ease !important; }
    .theme-switching .theme-control-icon { animation:theme-icon .32s ease both; }
    .status-dot { display:inline-flex; align-items:center; gap:7px; color:var(--mint-ink); font-size:12px; font-weight:650; }
    .status-dot::before { content:""; width:7px; height:7px; border-radius:50%; background:#4dbb82; box-shadow:0 0 0 4px var(--mint); }
    .admin-menu { position:relative; }
    .admin-chip { display:inline-flex; align-items:center; gap:8px; min-height:36px; padding:4px 8px 4px 5px; border:1px solid transparent; border-radius:9px; background:transparent; color:var(--ink); font-size:13px; font-weight:650; transition:background .18s ease,border-color .18s ease; }
    .admin-chip:hover,.admin-chip[aria-expanded="true"] { border-color:var(--line); background:var(--raised); }
    .admin-avatar { width:28px; height:28px; display:grid; place-items:center; border-radius:50%; background:var(--primary-soft); color:var(--primary); font-size:12px; font-weight:800; }
    #admin-name { max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .admin-chevron { color:var(--soft); font-size:13px; }
    .admin-popover { position:absolute; z-index:5; top:calc(100% + 8px); right:0; width:220px; padding:13px 14px; border:1px solid var(--line); border-radius:10px; background:var(--panel); box-shadow:0 12px 30px rgba(60,57,112,.12); }
    .admin-popover[hidden] { display:none; }
    .admin-popover strong { display:block; font-size:13px; }
    .admin-popover small { display:block; margin-top:5px; color:var(--muted); font-size:11px; line-height:1.45; }
    .popover-logout { display:block; width:100%; margin-top:10px; padding:7px 10px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--danger); font-size:12px; cursor:pointer; text-align:center; }
    .popover-logout:hover { background:#fdf2f2; border-color:#e8b8b8; }
    .sidebar { grid-area:side; min-width:0; background:var(--panel); border-right:1px solid var(--line); padding:24px 14px 18px; display:flex; flex-direction:column; gap:24px; }
    .profile { display:grid; justify-items:center; gap:7px; padding:4px 0 8px; }
    .bot-avatar { position:relative; width:72px; height:72px; overflow:hidden; border:5px solid var(--primary-soft); border-radius:50%; background:var(--primary-soft); box-shadow:0 5px 14px rgba(92,87,210,.12); }
    .bot-avatar::before { content:""; position:absolute; width:62px; height:58px; left:0; top:5px; border-radius:50% 50% 42% 42%; background:#a2a5f7; }
    .bot-avatar::after { content:"✦"; position:absolute; right:7px; top:4px; color:#fff; font-size:13px; }
    .avatar-face { position:absolute; left:16px; top:27px; z-index:1; color:var(--primary-dark); font-size:23px; letter-spacing:5px; }
    .bot-avatar.has-image::before,.bot-avatar.has-image::after,.bot-avatar.has-image .avatar-face { display:none; }
    .bot-avatar-image { position:absolute; inset:0; z-index:1; width:100%; height:100%; border-radius:50%; object-fit:cover; display:block; }
    .profile strong { font-size:14px; }
    .online { display:inline-flex; align-items:center; gap:5px; color:var(--mint-ink); font-size:12px; }
    .online::before { content:""; width:6px; height:6px; border-radius:50%; background:#4dbb82; }
    .nav-label { margin:0 10px 8px; color:var(--soft); font-size:10px; font-weight:800; letter-spacing:1px; text-transform:uppercase; }
    .nav { display:grid; gap:5px; }
    .nav a { display:flex; align-items:center; gap:11px; padding:11px 12px; border-radius:9px; color:var(--muted); text-decoration:none; transition:background .18s ease,color .18s ease,transform .18s ease,box-shadow .18s ease; }
    .nav a:hover { transform:translateX(3px); }
    .nav a:hover,.nav a.active,.nav a[aria-current="true"] { background:var(--primary-soft); color:var(--primary-dark); }
    .nav-icon { width:18px; color:var(--soft); text-align:center; font-size:16px; }
    .nav a.active .nav-icon,.nav a[aria-current="true"] .nav-icon { color:var(--primary); }
    .nav a:focus-visible,.refresh:focus-visible,.switch:focus-visible,.pan-select:focus-visible { outline:3px solid var(--primary); outline-offset:2px; }
    .sidebar-foot { margin-top:auto; padding:14px 13px; border:1px solid var(--line); border-radius:11px; background:var(--raised); color:var(--muted); font-size:11px; }
    .sidebar-foot strong { display:block; margin-bottom:5px; color:var(--ink); font-size:13px; }
    .sidebar-foot .spark { color:var(--primary); font-size:16px; }
    .main { grid-area:main; min-width:0; background:var(--bg); }
    .content { width:min(1500px,calc(100% - 50px)); margin:0 auto; padding:34px 0 60px; }
    .page-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:20px; }
    .page-kicker { margin:0 0 4px; color:var(--primary); font-size:12px; font-weight:750; }
    .page-heading h1 { margin:0; font-size:25px; letter-spacing:-.2px; }
    .page-heading p { margin:5px 0 0; color:var(--muted); font-size:13px; }
    .notice { display:none; margin:18px 0; padding:13px 15px; border:1px solid #f1df9b; border-radius:10px; background:var(--yellow); color:#8b681c; }
    .notice.show { display:block; }
    .primary-button { display:inline-flex; align-items:center; gap:7px; min-height:38px; border:0; border-radius:9px; padding:0 15px; background:var(--primary); color:#fff; font-size:12px; font-weight:700; box-shadow:0 6px 16px rgba(107,99,245,.18); }
    .primary-button:hover { background:var(--primary-dark); }
    .button-icon { font-size:15px; line-height:1; }
    .metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:13px; margin:27px 0 30px; }
    .metric { min-height:104px; padding:17px 18px; background:var(--panel); border:1px solid var(--line); border-radius:11px; box-shadow:var(--shadow); }
    .metric:nth-child(1) { background:var(--raised); }
    .metric:nth-child(2) { background:#fbfffd; }
    .metric:nth-child(3) { background:#fffdfa; }
    .metric:nth-child(4) { background:#fffafd; }
    .metric-label { color:var(--muted); font-size:12px; }
    .metric-value { margin-top:11px; color:var(--ink); font-size:22px; font-weight:750; }
    .metric-meta { margin-top:4px; color:var(--muted); font-size:11px; }
    .section { margin-top:28px; scroll-margin-top:82px; }
    .section-head { display:flex; align-items:flex-end; justify-content:space-between; gap:15px; margin-bottom:11px; }
    .section-head h2 { margin:0; font-size:17px; }
    .section-head p { margin:3px 0 0; color:var(--muted); font-size:12px; }
    .section-link { color:var(--primary); font-size:12px; font-weight:650; text-decoration:none; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:11px; box-shadow:var(--shadow); overflow:hidden; }
    .global-bar { display:flex; align-items:center; justify-content:space-between; gap:18px; padding:16px 19px; border-bottom:1px solid var(--line); background:var(--raised); }
    .global-actions { display:flex; align-items:center; gap:18px; flex:0 0 auto; }
    .test-mode { display:flex; align-items:center; gap:8px; color:var(--muted); font-size:12px; white-space:nowrap; }
    .global-copy strong { display:block; font-size:14px; }
    .global-copy span { display:block; margin-top:2px; color:var(--muted); font-size:12px; }
    .switch { position:relative; width:42px; height:24px; flex:0 0 auto; border:0; border-radius:999px; background:#d7d8e4; transition:background .18s ease; }
    .switch span { position:absolute; top:3px; left:3px; width:18px; height:18px; border-radius:50%; background:var(--panel); box-shadow:0 1px 3px #0002; transition:transform .18s ease; }
    .switch.on { background:var(--primary); }
    .switch.on span { transform:translateX(18px); }
    .switch:disabled { cursor:not-allowed; opacity:.45; }
    .novel-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); }
    .novel-item { display:flex; align-items:center; justify-content:space-between; gap:12px; min-height:73px; padding:15px 18px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); }
    .novel-item:nth-child(3n) { border-right:0; }
    .novel-item:nth-last-child(-n+3) { border-bottom:0; }
    .novel-name { display:flex; align-items:center; gap:10px; min-width:0; }
    .novel-badge { width:29px; height:29px; display:grid; place-items:center; border-radius:9px; background:var(--primary-soft); color:var(--primary); font-size:12px; font-weight:800; }
    .novel-item:nth-child(3n+2) .novel-badge { background:var(--mint); color:var(--mint-ink); }
    .novel-item:nth-child(3n) .novel-badge { background:var(--peach); color:var(--peach-ink); }
    .novel-name strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
    .novel-name small { display:block; margin-top:2px; color:var(--muted); font-size:11px; }
    .pan-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:13px; }
    .pan-card { padding:18px; border:1px solid var(--line); border-radius:11px; background:var(--panel); box-shadow:var(--shadow); }
    .pan-enable-switch { transform:scale(.82); transform-origin:right top; }
    .tag { display:inline-flex; padding:3px 7px; border-radius:999px; font-size:10px; font-weight:700; }
    .tag.active { background:var(--primary-soft); color:var(--primary-dark); }
    .tag.ok { background:var(--mint); color:var(--mint-ink); }
    .tag.off { background:#f2f4f7; color:#667085; }
    .account-list { display:grid; gap:6px; margin:0 0 14px; }
    .account-row { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 9px; border:1px solid var(--line); border-radius:6px; background:var(--raised); color:var(--muted); font-size:11px; }
    .account-row strong { color:var(--ink); font-size:12px; font-weight:650; }
    .account-row span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pan-select { width:100%; min-height:40px; border:1px solid var(--line); border-radius:8px; background:var(--panel); color:var(--ink); padding:8px 10px; }
    .pan-select:disabled { color:var(--soft); cursor:not-allowed; }
    .runtime-grid { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; }
    .runtime-item { padding:14px 15px; border:1px solid var(--line); border-radius:10px; background:var(--panel); box-shadow:var(--shadow); }
    .runtime-item span { display:block; color:var(--muted); font-size:11px; }
    .runtime-item strong { display:block; margin-top:7px; font-size:14px; }
    .config-list { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); }
    .config-item { padding:15px 18px; border-right:1px solid var(--line); }
    .config-item:last-child { border-right:0; }
    .config-item span { display:block; color:var(--muted); font-size:11px; }
    .config-item strong { display:block; margin-top:5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
    .toast { position:fixed; right:22px; bottom:22px; z-index:10; transform:translateY(12px); opacity:0; pointer-events:none; padding:11px 14px; border-radius:9px; background:#353250; color:#fff; box-shadow:0 8px 25px rgba(48,45,90,.22); transition:opacity .2s,transform .2s; }
    .toast.show { transform:translateY(0); opacity:1; }
    .empty { padding:30px; color:var(--muted); text-align:center; }
    @keyframes theme-switch { 0% { opacity:.72; } 100% { opacity:1; } }
    @keyframes theme-icon { 0% { transform:rotate(0deg) scale(.86); } 55% { transform:rotate(180deg) scale(1.08); } 100% { transform:rotate(360deg) scale(1); } }
    @media (max-width:1050px) { .metrics { grid-template-columns:repeat(2,1fr); } .runtime-grid { grid-template-columns:repeat(3,1fr); } .config-list { grid-template-columns:repeat(2,1fr); } .config-item { border-right:1px solid var(--line); border-bottom:1px solid var(--line); } .config-item:nth-child(2n) { border-right:0; } .config-item:nth-last-child(-n+2) { border-bottom:0; } }
     @media (max-width:760px) { .shell { display:block; } .topbar { min-height:62px; padding:12px 15px; } .brand strong { font-size:14px; } .top-actions { gap:8px; } .admin-chip { font-size:12px; } .status-dot { display:none; } .sidebar { padding:10px 12px 8px; border-right:0; border-bottom:1px solid var(--line); gap:10px; } .profile { display:flex; align-items:center; justify-content:flex-start; gap:9px; padding:0 2px; } .bot-avatar { width:38px; height:38px; border-width:3px; } .bot-avatar::before { width:34px; height:32px; top:2px; } .avatar-face { left:8px; top:12px; font-size:12px; letter-spacing:2px; } .bot-avatar::after { right:2px; top:1px; font-size:8px; } .profile strong { font-size:13px; } .online { margin-left:-3px; } .nav-label,.sidebar-foot { display:none; } .nav { display:flex; gap:4px; overflow-x:auto; scrollbar-width:none; } .nav::-webkit-scrollbar { display:none; } .nav a { flex:0 0 auto; padding:8px 10px; } .content { width:calc(100% - 28px); padding:23px 0 40px; } .page-heading h1 { font-size:21px; } .page-heading p { font-size:12px; } .primary-button { min-height:34px; padding:0 11px; } .metrics,.pan-grid { grid-template-columns:1fr; } .novel-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .novel-item:nth-child(3n) { border-right:1px solid var(--line); } .novel-item:nth-child(2n) { border-right:0; } .novel-item:nth-last-child(-n+3),.novel-item:last-child,.novel-item:nth-last-child(2) { border-bottom:1px solid var(--line); } .global-bar { align-items:flex-start; } .global-actions { gap:10px; } .test-mode span { max-width:68px; white-space:normal; line-height:1.2; } .runtime-grid { grid-template-columns:repeat(2,1fr); } .config-list { grid-template-columns:1fr; } .config-item,.config-item:nth-child(2n) { padding:13px; border-right:0; border-bottom:1px solid var(--line); } .config-item:last-child { border-bottom:0; } }
     /* Screenshot-inspired configuration workspace. The data/API contract stays unchanged. */
     .shell { grid-template-columns:248px minmax(0,1fr); grid-template-rows:62px minmax(0,1fr); }
     .topbar { padding:0 30px; }
     .brand-mark { width:36px; height:36px; border-radius:50%; background:var(--primary-soft); color:var(--primary); border:3px solid var(--primary-soft); font-size:13px; }
     .brand strong { font-size:17px; }
     .sidebar { padding:28px 18px 18px; gap:25px; }
     .profile { gap:8px; padding-bottom:13px; }
     .bot-avatar { width:76px; height:76px; }
     .nav-label { margin:0 12px 8px; font-size:11px; letter-spacing:0; text-transform:none; color:var(--soft); }
     .nav { gap:4px; }
     .nav a { min-height:40px; padding:10px 12px; border-radius:8px; font-size:13px; }
     .nav-icon { width:19px; font-size:15px; }
     .sidebar-foot { border-radius:8px; background:var(--hover); padding:15px 13px; line-height:1.65; }
     .main { background:#f7f8fc; }
     .content { width:min(1300px,calc(100% - 44px)); padding:38px 0 65px; }
     .page-kicker { display:none; }
     .page-heading h1 { font-size:24px; letter-spacing:0; }
     .page-heading p { margin-top:6px; font-size:13px; }
     .primary-button { min-height:40px; border-radius:7px; padding:0 17px; }
     .notice { margin:14px 0 0; border-radius:7px; }
     .metrics { display:none; }
     .workspace-grid { display:grid; grid-template-columns:minmax(0,1.62fr) minmax(310px,.96fr); align-items:start; gap:16px; margin-top:17px; }
     .workspace-left,.workspace-right { display:grid; gap:16px; align-content:start; min-width:0; }
     .console-card { margin:0; padding:21px 21px 20px; background:var(--panel); border:1px solid var(--line); border-radius:8px; box-shadow:0 5px 18px rgba(55,59,103,.045); scroll-margin-top:80px; }
     .console-card h2 { margin:0; font-size:15px; }
     .card-subtitle { margin:4px 0 18px; color:var(--muted); font-size:12px; }
     .profile-fields { display:grid; gap:0; }
     .profile-field { display:grid; grid-template-columns:112px minmax(0,1fr); align-items:center; gap:16px; min-height:58px; border-bottom:1px solid var(--line); }
     .profile-field:last-child { border-bottom:0; }
     .profile-field > span { color:var(--muted); font-size:13px; }
     .readonly-value { min-height:38px; display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 11px; border:1px solid var(--line); border-radius:7px; color:var(--ink); background:var(--panel); }
     .readonly-value small { color:var(--soft); font-size:11px; }
     .avatar-inline { display:flex; align-items:center; gap:10px; }
     .avatar-inline .bot-avatar { width:43px; height:43px; border-width:3px; }
     .avatar-inline .bot-avatar::before { width:37px; height:35px; top:3px; }
     .avatar-inline .avatar-face { left:9px; top:14px; font-size:13px; letter-spacing:2px; }
     .avatar-inline .bot-avatar::after { right:3px; top:1px; font-size:9px; }
     .avatar-inline small { color:var(--muted); font-size:11px; }
     .state-line { display:flex; align-items:center; gap:10px; }
     .state-line .online { font-size:12px; }
     .connection-fields { display:grid; gap:12px; }
     .connection-row { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:12px 0; border-bottom:1px solid var(--line); }
     .connection-row:last-child { border-bottom:0; padding-bottom:0; }
     .connection-row:first-child { padding-top:0; }
     .connection-row > span { color:var(--muted); font-size:12px; }
     .connection-row strong { max-width:66%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--ink); font-size:12px; font-weight:600; text-align:right; }
     .module-card { padding:21px 0 0; overflow:hidden; }
     .module-card h2,.module-card .card-subtitle { margin-left:21px; margin-right:21px; }
     .module-card .global-bar { padding:14px 21px; border-top:1px solid var(--line); background:var(--raised); }
     .module-card .novel-grid { grid-template-columns:1fr; }
     .module-card .novel-item { min-height:51px; padding:10px 21px; border-right:0; }
     .module-card .novel-item:nth-last-child(-n+3) { border-bottom:1px solid var(--line); }
     .module-card .novel-item:last-child { border-bottom:0; }
     .module-card .novel-badge { width:26px; height:26px; border-radius:7px; }
     .module-card .novel-name strong { font-size:12px; }
     .module-card .novel-name small { font-size:10px; }
     .module-card .switch { transform:scale(.88); transform-origin:right center; }
     .status-card { padding-bottom:13px; }
     .status-card .status-list { display:grid; gap:0; margin-top:10px; }
     .status-item { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:9px 0; border-bottom:1px solid var(--line); font-size:12px; }
     .status-item:last-child { border-bottom:0; }
     .status-item span { color:var(--muted); }
     .status-item strong { color:var(--ink); font-weight:600; text-align:right; }
     .status-item strong.good { color:var(--mint-ink); }
     .test-card { padding-bottom:17px; }
     .test-bubble { display:flex; align-items:flex-start; gap:9px; margin-top:14px; }
     .test-mini-avatar { width:28px; height:28px; flex:0 0 auto; display:grid; place-items:center; border-radius:50%; background:var(--primary-soft); color:var(--primary); font-size:11px; font-weight:800; }
     .test-bubble p { margin:0; padding:9px 11px; border-radius:5px 10px 10px 10px; background:var(--primary-soft); color:var(--muted); font-size:11px; line-height:1.55; }
     .test-hint { margin:13px 0 0; color:var(--soft); font-size:11px; }
     .pan-section { margin-top:16px; }
     .pan-section .section-head { margin:0 0 10px; }
     .pan-grid { grid-template-columns:1fr; }
     .pan-card[hidden] { display:none !important; }
     .pan-console { padding:22px 0 24px; overflow:visible; }
     .pan-console > h2,.pan-console > .card-subtitle { margin-left:24px; margin-right:24px; }
     .pan-console .pan-note { margin-left:24px; margin-right:24px; }
     .pan-console .pan-grid { padding:0 24px; }
     .pan-console .pan-card { min-width:0; padding:20px; transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease; }
     .pan-console .pan-card:hover { transform:translateY(-2px); }
     .runtime-grid { display:none; }
     .config-list { grid-template-columns:repeat(2,minmax(0,1fr)); border-radius:7px; box-shadow:none; }
     .config-item { min-height:64px; padding:13px 15px; border-bottom:1px solid var(--line); }
     .config-item:nth-child(2n) { border-right:0; }
     .config-item:nth-last-child(-n+2) { border-bottom:0; }
     .config-section { margin-top:16px; }
     .sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
     @media (max-width:1050px) { .workspace-grid { grid-template-columns:minmax(0,1.35fr) minmax(280px,.9fr); } .pan-grid { grid-template-columns:1fr; } }
     @media (max-width:760px) { .pan-console { padding-top:18px; } .pan-console > h2,.pan-console > .card-subtitle,.pan-console .pan-note { margin-left:17px; margin-right:17px; } .pan-console .pan-grid { padding:0 17px; } }
     @media (max-width:760px) { .content { width:calc(100% - 28px); padding:23px 0 40px; } .workspace-grid { grid-template-columns:1fr; } .workspace-right { order:-1; } .module-card .novel-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .module-card .novel-item { border-right:1px solid var(--line); } .module-card .novel-item:nth-child(2n) { border-right:0; } .module-card .novel-item:nth-last-child(-n+2) { border-bottom:0; } .profile-field { grid-template-columns:92px minmax(0,1fr); gap:10px; } .connection-row strong { max-width:58%; } .config-list { grid-template-columns:1fr; } .config-item,.config-item:nth-child(2n) { border-right:0; border-bottom:1px solid var(--line); } .config-item:last-child { border-bottom:0; } }
     .page-view[hidden] { display:none !important; }
     .page-view { min-width:0; scroll-margin-top:82px; }
     .heading-actions { display:flex; align-items:center; gap:12px; }
     .updated-label { color:var(--muted); font-size:11px; white-space:nowrap; }
     .summary-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:13px; margin-top:18px; }
     .summary-card { min-height:168px; display:flex; flex-direction:column; align-items:flex-start; padding:17px 18px; background:var(--panel); border:1px solid var(--line); border-radius:8px; box-shadow:0 5px 18px rgba(55,59,103,.045); }
     .summary-card > span { color:var(--muted); font-size:12px; }
     .summary-card > strong { margin-top:12px; color:var(--ink); font-size:21px; }
     .summary-card > small { min-height:18px; margin-top:4px; color:var(--muted); font-size:11px; }
     .text-button { display:block; margin-top:auto; padding:0; border:0; background:transparent; color:var(--primary); cursor:pointer; font:inherit; font-size:12px; font-weight:700; text-align:left; }
     .text-button:hover { color:var(--primary-dark); }
     .page-grid { display:grid; grid-template-columns:minmax(0,1.55fr) minmax(280px,.9fr); gap:16px; margin-top:16px; }
     .page-grid .console-card { min-width:0; }
     .page-view-head { margin-top:18px; margin-bottom:0; }
     .shortcut-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
     .shortcut-card { width:100%; min-height:94px; display:grid; grid-template-columns:30px minmax(0,1fr); grid-template-rows:auto auto; column-gap:10px; align-items:center; padding:13px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); cursor:pointer; font:inherit; text-align:left; }
     .shortcut-card:hover { border-color:var(--primary); background:var(--raised); }
     .shortcut-icon { grid-row:1 / span 2; width:30px; height:30px; display:grid; place-items:center; border-radius:8px; background:var(--primary-soft); color:var(--primary); font-size:14px; }
     .shortcut-card strong { font-size:12px; }
     .shortcut-card small { color:var(--muted); font-size:10px; line-height:1.45; }
     .compact-status { margin-top:8px; }
     .outline-button { min-height:36px; padding:0 16px; border:1px solid var(--primary); border-radius:7px; background:var(--panel); color:var(--primary-dark); font-size:12px; font-weight:700; }
     .outline-button:hover { background:var(--primary-soft); }
     .standalone-card { margin-top:18px; }
     .standalone-card > h2 { font-size:18px; }
     .module-heading { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:18px 0 10px; }
     .module-heading h3 { margin:0; font-size:13px; }
     .module-heading span { color:var(--muted); font-size:11px; }
     .pan-note { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:16px 0; padding:13px 15px; border:1px solid #e9e8f7; border-radius:7px; background:var(--raised); }
     .pan-note span { color:var(--muted); font-size:12px; }
     .pan-note strong { color:var(--primary-dark); font-size:13px; }
     .runtime-page-grid { display:grid !important; grid-template-columns:repeat(5,minmax(0,1fr)); margin-top:18px; }
     .runtime-detail { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:16px; }
     .settings-db-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
     .settings-db-grid .status-item strong { overflow-wrap:anywhere; }
     .settings-db-note { margin-top:14px; }
     .runtime-detail .status-item { padding:13px; border:1px solid var(--line); border-radius:7px; background:var(--raised); }
     .safe-list,.settings-list { display:grid; gap:0; }
     .safe-list > div,.settings-row { display:flex; align-items:center; justify-content:space-between; gap:16px; min-height:50px; border-bottom:1px solid var(--line); font-size:12px; }
     .safe-list > div:last-child,.settings-row:last-child { border-bottom:0; }
     .safe-list span,.settings-row span { color:var(--muted); }
     .safe-list strong,.settings-row strong { color:var(--ink); font-weight:600; text-align:right; }
     .settings-row strong { max-width:65%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
     .config-editor { display:grid; gap:18px; }
     .config-group { padding:16px; border:1px solid var(--line); border-radius:8px; background:var(--raised); }
     .config-group h3 { margin:0 0 13px; font-size:13px; }
     .config-fields { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:13px 15px; }
     .config-field { display:grid; gap:6px; min-width:0; }
     .config-field.full { grid-column:1 / -1; }
     .config-field label { color:var(--muted); font-size:11px; font-weight:700; }
     .config-input-wrap { position:relative; min-width:0; }
     .config-field input,.config-field textarea,.config-field select,.account-add input,.group-account input { width:100%; min-height:39px; padding:8px 10px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); outline:none; }
     .config-input-wrap input { padding-right:62px; }
     .config-secret-toggle { position:absolute; top:50%; right:8px; transform:translateY(-50%); padding:3px 5px; border:0; background:transparent; color:var(--primary); cursor:pointer; font-size:11px; font-weight:700; }
     .config-secret-toggle:disabled { cursor:not-allowed; opacity:.45; }
     .config-field textarea { min-height:74px; resize:vertical; }
     .config-field input:focus,.config-field textarea:focus,.config-field select:focus,.account-add input:focus,.group-account input:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--primary-soft); }
     .config-field small,.secret-hint,.config-message,.qq-auth-message { color:var(--muted); font-size:10px; line-height:1.55; }
     .config-actions { display:flex; align-items:center; gap:12px; }
     .config-actions .primary-button { min-height:38px; }
     .config-message.ok,.qq-auth-message.ok { color:var(--mint-ink); }
     .config-message.error,.qq-auth-message.error { color:var(--danger); }
     .account-actions { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:12px; }
     .account-add { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:7px; margin-top:13px; }
     .account-add .outline-button,.group-account .outline-button { min-height:39px; padding:0 11px; }
     .account-row { min-width:0; }
     .account-row button { flex:0 0 auto; border:0; background:transparent; color:var(--danger); font-size:11px; }
     .account-row button:hover { color:var(--danger); }
     .pan-directory { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:7px; margin:0 0 12px; }
     .pan-directory input { min-width:0; min-height:36px; padding:7px 9px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); outline:none; }
     .pan-directory input:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--primary-soft); }
     .pan-directory .outline-button { min-height:36px; padding:0 10px; }
     .pan-security-note { margin:0 0 12px; padding:8px 9px; border-radius:6px; background:var(--raised); color:var(--muted); font-size:10px; line-height:1.5; }
     .group-account { display:grid; grid-template-columns:minmax(0,1fr) 74px auto; gap:7px; margin-top:9px; }
     .group-account input { min-width:0; }
     .group-account select { min-height:39px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); }
     .qq-reader-toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:4px 0 12px; color:var(--muted); font-size:12px; }
     .qq-reader-accounts { display:grid; grid-template-columns:repeat(auto-fill,minmax(min(100%,210px),1fr)); gap:10px; }
     .qq-reader-account { min-width:0; padding:12px; border:1px solid var(--line); border-radius:9px; background:var(--panel); animation:pan-account-card-enter .25s ease-out both; transition:border-color .18s ease,box-shadow .18s ease,transform .18s ease; }
     .qq-reader-account:hover { transform:translateY(-2px); border-color:var(--primary); box-shadow:var(--shadow); }
     .qq-reader-account.is-current { border-color:var(--primary); background:var(--primary-soft); }
     .qq-reader-account.is-disabled { opacity:.68; }
     .qq-reader-account-top { display:flex; align-items:center; justify-content:space-between; gap:8px; }
     .qq-reader-account-switch { width:34px; height:20px; }
     .qq-reader-account-switch span { top:3px; left:3px; width:14px; height:14px; }
     .qq-reader-account-switch.on span { transform:translateX(14px); }
     .qq-reader-account-open { display:grid; grid-template-columns:40px minmax(0,1fr) 10px; align-items:center; gap:9px; width:100%; margin:12px 0 10px; padding:0; border:0; background:transparent; color:var(--ink); text-align:left; }
     .qq-reader-account-open > span:nth-child(2) { display:grid; min-width:0; gap:3px; }
     .qq-reader-account-open strong { overflow:hidden; font-size:13px; text-overflow:ellipsis; white-space:nowrap; }
     .qq-reader-account-open small { overflow:hidden; color:var(--muted); font-size:10px; text-overflow:ellipsis; white-space:nowrap; }
     .qq-reader-arrow { color:var(--soft); font-size:19px; }
     .qq-reader-avatar { position:relative; display:grid; place-items:center; flex:0 0 40px; width:40px; height:40px; overflow:hidden; border-radius:50%; background:var(--primary-soft); color:var(--primary); font-size:16px; font-weight:700; }
     .qq-reader-avatar img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }
     .qq-reader-account-vip { display:grid; gap:3px; padding-top:8px; border-top:1px solid var(--line); color:var(--muted); font-size:11px; }
     .qq-reader-account-vip .is-vip { color:var(--yellow-ink); font-weight:700; }
     .qq-reader-account-vip small { overflow-wrap:anywhere; font-size:10px; }
     .qq-reader-empty { grid-column:1 / -1; border:1px dashed var(--line); border-radius:9px; }
     .qq-reader-modal { position:fixed; inset:0; width:min(640px,calc(100vw - 32px)); height:fit-content; max-width:none; max-height:calc(100vh - 48px); max-height:calc(100dvh - 48px); margin:auto; padding:0; border:1px solid var(--line); border-radius:16px; background:var(--panel); color:var(--ink); box-shadow:0 24px 80px #14152433; overflow:hidden; }
     .qq-reader-modal:not([open]) { display:none; }
     .qq-reader-modal[open] { display:flex; flex-direction:column; }
     .qq-reader-modal::backdrop { background:rgba(29,31,39,.38); backdrop-filter:blur(4px); -webkit-backdrop-filter:blur(4px); }
     .qq-reader-modal-head { display:flex; align-items:center; justify-content:space-between; gap:16px; flex:0 0 auto; padding:20px 24px; border-bottom:1px solid var(--line); }
     .qq-reader-modal-head h3 { margin:0; color:var(--ink); font-size:16px; font-weight:700; }
     .qq-reader-modal-close { display:grid; place-items:center; width:30px; height:30px; flex:0 0 30px; padding:0; border:0; border-radius:7px; background:transparent; color:var(--muted); font-size:24px; line-height:1; cursor:pointer; }
     .qq-reader-modal-close:hover { background:var(--primary-soft); color:var(--primary); }
     .qq-reader-modal-close:focus-visible { outline:2px solid var(--primary); outline-offset:2px; }
     .qq-reader-modal-body { min-height:0; padding:22px 24px 24px; overflow:auto; overscroll-behavior:contain; }
     .qq-reader-detail,.qq-reader-add-panel { display:grid; gap:16px; min-width:0; }
     .qq-reader-captcha-frame { max-width:100%; overflow:auto; overscroll-behavior:contain; }
     .qq-reader-captcha { width:300px; min-height:230px; margin-inline:auto; }
     .qq-reader-captcha-frame[hidden] { display:none; }
     @media(max-width:520px) { .qq-reader-modal { width:calc(100vw - 20px); max-height:calc(100vh - 24px); max-height:calc(100dvh - 24px); border-radius:13px; } .qq-reader-modal-head { padding:15px 16px; } .qq-reader-modal-body { padding:17px 16px 20px; } }
     #qq-reader-list[hidden],.qq-reader-detail[hidden],.qq-reader-add-panel[hidden],#qq-reader-phone-panel[hidden],#qq-reader-manual-panel[hidden],.qq-reader-scan-panel[hidden],.qq-reader-qr-image[hidden] { display:none !important; }
     .qq-reader-detail-head { display:flex; align-items:center; gap:11px; min-width:0; }
     .qq-reader-detail-head .qq-reader-avatar { width:46px; height:46px; flex-basis:46px; }
     .qq-reader-detail-copy { display:grid; gap:3px; min-width:0; flex:1; }
     .qq-reader-detail-copy strong { overflow-wrap:anywhere; font-size:14px; }
     .qq-reader-detail-copy small { color:var(--muted); font-size:11px; overflow-wrap:anywhere; }
     .qq-reader-detail-head .outline-button { min-height:30px; padding:0 9px; font-size:11px; }
     .qq-reader-profile { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px 16px; margin:0; padding:13px 0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }
     .qq-reader-profile > div { min-width:0; }
     .qq-reader-profile dt { margin-bottom:4px; color:var(--muted); font-size:10px; }
     .qq-reader-profile dd { margin:0; color:var(--ink); font-size:12px; overflow-wrap:anywhere; }
     .qq-reader-key-row { display:grid; gap:6px; min-width:0; }
     .qq-reader-key-row > label,.qq-reader-field-label { display:block; color:var(--muted); font-size:11px; }
     .qq-reader-key-row > div { display:flex; align-items:stretch; gap:8px; min-width:0; }
     .qq-reader-key-row input { min-width:0; width:100%; flex:1; }
     .qq-reader-key-row .outline-button { flex:0 0 auto; min-height:36px; padding:0 11px; }
     .qq-reader-key-row input,.qq-auth-row input,.qq-reader-cookie { min-height:38px; padding:8px 10px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); font-size:12px; outline:none; }
     .qq-reader-key-row input:focus,.qq-auth-row input:focus,.qq-reader-cookie:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--primary-soft); }
     .qq-reader-delete { min-height:32px; margin-left:auto; padding:0 9px; border:0; border-radius:6px; background:transparent; color:var(--danger); font-size:11px; }
     .qq-reader-delete:hover { background:var(--pink); }
     .qq-reader-phone-panel { display:grid; gap:9px; }
     .qq-reader-phone-row { display:flex; align-items:stretch; gap:8px; min-width:0; }
     .qq-reader-phone-row input { flex:1; width:100%; min-width:0; min-height:38px; padding:8px 10px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); font-size:12px; outline:none; }
     .qq-reader-phone-row button { flex:0 0 auto; min-height:38px; }
     .qq-reader-phone-row input:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--primary-soft); }
     .qq-auth-tabs { display:flex; flex-wrap:wrap; gap:7px; padding-bottom:10px; border-bottom:1px solid var(--line); }
     .qq-auth-tab { padding:7px 12px; border:0; border-radius:7px; background:transparent; color:var(--muted); font-size:12px; font-weight:650; }
     .qq-auth-tab.active { background:var(--primary-soft); color:var(--primary-dark); }
     #qq-reader-manual-panel { display:grid; gap:9px; }
     .qq-reader-cookie { width:100%; min-height:76px; resize:vertical; font-family:inherit; }
     .qq-reader-field-hint { margin:0; color:var(--muted); font-size:11px; line-height:1.6; }
     .qq-auth-row { display:grid; grid-template-columns:1fr 1fr; gap:10px; min-width:0; }
     .qq-auth-row > input { min-width:0; width:100%; }
     .qq-reader-new-key { display:flex; align-items:center; gap:5px; min-width:0; }
     .qq-reader-new-key input { width:100%; min-width:0; flex:1; }
     .qq-reader-new-key .text-button { flex:0 0 auto; margin:0; }
     .qq-auth-actions { display:flex; align-items:center; gap:9px; flex-wrap:wrap; }
     .qq-reader-scan-panel { display:grid; justify-items:start; gap:12px; }
     .qq-reader-qr-image { width:min(100%,220px); height:auto; padding:8px; border:1px solid var(--line); border-radius:10px; background:var(--panel); image-rendering:pixelated; }
     .qq-reader-account-open:focus-visible,.qq-auth-tab:focus-visible { outline:3px solid var(--primary); outline-offset:3px; border-radius:6px; }
     @media (max-width:540px) { .qq-reader-accounts { grid-template-columns:1fr; } .qq-reader-detail,.qq-reader-add-panel { padding:13px; } .qq-auth-row { grid-template-columns:1fr; } .qq-reader-detail-head { display:grid; grid-template-columns:46px minmax(0,1fr); } .qq-reader-detail-head .outline-button { grid-column:2; justify-self:start; margin:0; } }
     @media (prefers-reduced-motion:reduce) { .qq-reader-account { animation:none; transition:none; } .qq-reader-account:hover { transform:none; } }

     .settings-hint { margin-top:15px; padding:12px 13px; border-radius:7px; background:var(--hover); color:var(--muted); font-size:11px; line-height:1.6; }
     .help-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; margin-top:16px; }
     .help-card h3 { margin:0; font-size:14px; }
     .help-card > p { margin:4px 0 15px; color:var(--muted); font-size:11px; }
     .command-list { display:flex; flex-wrap:wrap; gap:7px; }
     .command-list span { display:inline-flex; min-height:28px; align-items:center; padding:0 9px; border:1px solid var(--line); border-radius:6px; background:var(--raised); color:var(--muted); font-size:11px; }
     @media (max-width:1050px) { .summary-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .runtime-page-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
      @keyframes switch-feedback { 0% { transform:scale(1); } 45% { transform:scale(1.08); } 100% { transform:scale(1); } }
      .summary-card,.shortcut-card,.pan-card,.runtime-item { transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease; }
      .summary-card:hover,.shortcut-card:hover,.pan-card:hover,.runtime-item:hover { transform:translateY(-2px); }
      .switch:active { animation:switch-feedback .22s ease both; }
     /* Novel controls use an unframed workspace with compact, real controls. */
     .novel-console { margin-top:18px; padding:4px 0 0; }
     .novel-console-head { display:flex; align-items:flex-start; justify-content:space-between; gap:22px; margin-bottom:20px; }
     .novel-console-head h2 { margin:4px 0 0; font-size:23px; letter-spacing:0; }
     .novel-console-head .card-subtitle { margin:7px 0 0; max-width:520px; }
     .novel-overline,.novel-panel-kicker,.novel-platform-overline { color:var(--soft); font-size:10px; font-weight:800; letter-spacing:1.3px; }
     .novel-state-pill { display:inline-flex; align-items:center; gap:8px; min-height:34px; padding:0 12px; border:1px solid #dbe8df; border-radius:999px; background:#f4fbf7; color:#318260; white-space:nowrap; }
     .novel-state-pill.is-off { border-color:#e3e4eb; background:#fafafd; color:#838697; }
     .novel-state-dot { width:7px; height:7px; border-radius:50%; background:#4eb781; box-shadow:0 0 0 4px #e3f6eb; }
     .novel-state-pill.is-off .novel-state-dot { background:#a7a9b6; box-shadow:0 0 0 4px #eff0f4; }
     .novel-state-pill strong { font-size:11px; font-weight:750; }
     .novel-control-grid { display:grid; grid-template-columns:minmax(0,1.42fr) minmax(280px,.92fr); gap:12px; }
     .novel-master-panel,.novel-test-panel { min-height:178px; padding:20px; border:1px solid var(--line); border-radius:10px; background:var(--panel); box-shadow:0 5px 18px rgba(55,59,103,.045); }
     .novel-master-panel { border-color:#dedcff; background:var(--raised); }
     .novel-test-panel { border-color:#f0ded4; background:#fffaf7; }
     .novel-panel-kicker { display:flex; align-items:center; gap:8px; color:var(--primary); letter-spacing:.7px; }
     .novel-test-panel .novel-panel-kicker { color:#bf7961; }
     .novel-panel-icon { width:25px; height:25px; display:grid; place-items:center; border-radius:7px; background:var(--primary-soft); color:var(--primary); font-size:12px; letter-spacing:0; }
     .novel-test-panel .novel-panel-icon { background:#ffebe2; color:#c5755b; }
     .novel-master-copy h3,.novel-test-panel h3 { margin:19px 0 4px; font-size:17px; }
     .novel-master-copy p,.novel-test-panel p { max-width:410px; margin:0; color:var(--muted); font-size:12px; line-height:1.65; }
     .novel-master-actions,.novel-test-actions { display:flex; align-items:flex-end; justify-content:space-between; gap:15px; margin-top:18px; }
     .novel-master-state { display:grid; gap:2px; }
     .novel-master-state strong { color:var(--ink); font-size:12px; }
     .novel-master-state span,.novel-test-note { color:var(--soft); font-size:11px; }
     .novel-console .novel-master-panel .switch { width:50px; height:28px; }
     .novel-console .novel-master-panel .switch span { width:22px; height:22px; }
     .novel-console .novel-master-panel .switch.on span { transform:translateX(22px); }
     .novel-test-actions { align-items:center; margin-top:20px; }
     .novel-test-actions .switch { transform:scale(.95); transform-origin:right center; }
     .novel-platform-head { display:flex; align-items:flex-end; justify-content:space-between; gap:18px; margin:29px 0 12px; }
     .novel-platform-head h3 { margin:4px 0 0; font-size:15px; }
     .novel-platform-count { color:var(--muted); font-size:11px; }
     .novel-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
     .novel-item { display:flex; align-items:center; justify-content:space-between; gap:14px; min-height:78px; padding:14px 16px; border:1px solid var(--line); border-radius:9px; background:var(--panel); box-shadow:none; transition:border-color .2s ease,background .2s ease,transform .2s ease,box-shadow .2s ease; }
     .novel-item:hover { border-color:var(--primary); background:var(--raised); transform:translateY(-2px); box-shadow:0 7px 18px rgba(55,59,103,.06); }
     .novel-item.is-enabled { border-color:#d8e9df; }
     .novel-item.is-disabled { background:var(--raised); }
     .novel-item-main { display:flex; align-items:center; gap:11px; min-width:0; }
     .novel-badge { width:34px; height:34px; flex:0 0 auto; display:grid; place-items:center; border-radius:10px; background:var(--primary-soft); color:var(--primary); font-size:12px; font-weight:800; }
     .novel-item:nth-child(3n+2) .novel-badge { background:#e8f8ef; color:#35936a; }
     .novel-item:nth-child(3n) .novel-badge { background:#fff0e9; color:#ca7b5f; }
     .novel-item-copy { min-width:0; }
     .novel-item-title { display:flex; align-items:center; gap:8px; min-width:0; }
     .novel-item-title strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
     .novel-item-copy small { display:block; margin-top:4px; color:var(--soft); font-size:10px; }
     .novel-item-status { flex:0 0 auto; color:var(--soft); font-size:10px; }
     .novel-item.is-enabled .novel-item-status { color:#35936a; }
     .novel-item .switch { transform:scale(.9); transform-origin:right center; }
     .novel-item .switch:focus-visible,.novel-master-panel .switch:focus-visible,.novel-test-panel .switch:focus-visible { outline:3px solid var(--primary); outline-offset:3px; }
     @media (max-width:900px) { .novel-control-grid { grid-template-columns:1fr; } }
     @media (max-width:760px) { .novel-console { margin-top:15px; padding-top:0; } .novel-console-head { display:block; } .novel-state-pill { margin-top:14px; } .novel-master-panel,.novel-test-panel { min-height:0; padding:17px; } .novel-master-copy h3,.novel-test-panel h3 { margin-top:15px; } .novel-platform-head { align-items:flex-start; margin-top:24px; } .novel-platform-head { display:block; } .novel-platform-count { display:block; margin-top:6px; } .novel-grid { grid-template-columns:1fr; } .novel-item { min-height:72px; padding:13px 14px; } }
      .msg-group-tabs { overflow-x:auto; }
      .msg-group-tabs > button { white-space:nowrap; }
      .msg-group-mute-card { margin-bottom:12px; padding:13px; border:1px solid var(--line); border-radius:9px; background:var(--raised); }
      .msg-group-mute-card h4 { margin:0 0 10px; font-size:12px; font-weight:600; }
      .msg-group-mute-card h4 small { margin-left:5px; color:var(--muted); font-size:10px; font-weight:400; }
      .msg-group-mute-card > strong { display:block; font-size:13px; }
      .msg-group-mute-card > small { display:block; margin-top:6px; color:var(--muted); font-size:10px; }
      .msg-group-mute-rule,.msg-group-muted-member { padding:9px 0; border-top:1px solid var(--line); font-size:11px; line-height:1.65; overflow-wrap:anywhere; }
      .msg-group-mute-rule:first-child,.msg-group-muted-member:first-child { border-top:0; padding-top:0; }
      .msg-group-mute-rule small,.msg-group-muted-member small { display:block; color:var(--muted); font-size:10px; }
      .msg-group-mute-rule.is-disabled { color:var(--muted); }
      :root[data-theme="dark"] .msg-group-mute-card { background:var(--raised); border-color:var(--line); }
      :root[data-theme="dark"] .msg-group-mute-rule,:root[data-theme="dark"] .msg-group-muted-member { border-color:var(--line); }
      @media (max-width:760px) { #admin-name { max-width:88px; } .admin-popover { right:-2px; width:205px; } }
      @media (prefers-reduced-motion: reduce) {
        *,*::before,*::after { animation-duration:.01ms !important; animation-iteration-count:1 !important; scroll-behavior:auto !important; transition-duration:.01ms !important; }
      }
      @media (max-width:760px) { .heading-actions { gap:7px; } .updated-label { display:none; } .summary-grid,.page-grid,.runtime-detail,.help-grid { grid-template-columns:1fr; } .shortcut-grid { grid-template-columns:1fr; } .runtime-page-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .standalone-card { margin-top:15px; } .safe-list > div,.settings-row { min-height:56px; } .config-fields,.qq-auth-row { grid-template-columns:1fr; } .group-account { grid-template-columns:minmax(0,1fr) 70px; } .group-account .outline-button { grid-column:1 / -1; } }
      @media (max-width:760px) { .theme-control { flex:0 0 auto; gap:1px; padding:2px 3px 2px 5px; } .theme-control-label { display:none; } .theme-toggle-button { width:26px; height:26px; } .theme-control-icon { display:inline-block; font-size:15px; } .theme-control select { width:76px; max-width:76px; padding-right:13px; } }
      @media (max-width:340px) { .topbar { gap:8px; padding-left:12px; padding-right:12px; } .brand { flex:0 0 auto; gap:7px; } .brand > div { max-width:64px; min-width:0; } .brand strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; } .version-badge { display:none; } .top-actions { min-width:0; gap:5px; } .status-dot { font-size:0; gap:0; } .status-dot::before { width:6px; height:6px; } .theme-control select { width:68px; max-width:68px; } .theme-toggle-button { width:24px; height:24px; } .admin-chip { gap:3px; padding-right:4px; } #admin-name { display:none; } }

      /* 桌面端让右侧内容独立滚动，侧栏保持视口高度，不随页面内容拉伸。 */
      @media (min-width:761px) {
        html,body { height:100%; }
        body { overflow:hidden; }
        .shell { height:100vh; min-height:100vh; overflow:hidden; }
        .sidebar { position:sticky; top:0; align-self:start; height:calc(100vh - 62px); min-height:0; overflow-x:hidden; overflow-y:auto; overscroll-behavior:contain; scrollbar-gutter:stable; }
        .main { min-height:0; overflow-x:hidden; overflow-y:auto; overscroll-behavior:contain; }
      }
      @media (max-width:760px) {
        html,body { height:auto; min-height:100%; }
        body { overflow-x:hidden; overflow-y:auto; }
        .shell { height:auto; min-height:100vh; overflow:visible; }
        .sidebar { position:static; height:auto; max-height:none; overflow:visible; }
        .main { min-height:0; overflow:visible; }
      }

      /* 网盘页：平台页签下只显示账号卡，单账号详情集中承载账号与平台配置。 */
      .pan-page { margin-top:18px; }
      .pan-tabs { display:flex; align-items:stretch; gap:4px; overflow-x:auto; border-bottom:1px solid var(--line); scrollbar-width:thin; }
      .pan-tab { display:flex; align-items:center; gap:10px; min-width:170px; min-height:58px; padding:8px 13px; border:1px solid transparent; border-bottom:0; border-radius:7px 7px 0 0; background:transparent; color:var(--muted); font-family:inherit; text-align:left; cursor:pointer; }
      .pan-tab:hover { background:var(--panel); color:var(--ink); }
      .pan-tab.active { border-color:var(--line); background:var(--panel); color:var(--ink); box-shadow:0 1px 0 var(--panel); }
      .pan-tab:focus-visible,.pan-object-card:focus-visible,.pan-object-open:focus-visible { outline:3px solid var(--primary); outline-offset:2px; }
      .pan-tab-mark { display:grid; place-items:center; width:32px; height:32px; flex:0 0 32px; border-radius:7px; background:var(--primary-soft); color:var(--primary); font-size:13px; font-weight:800; }
      .pan-tab-quark { background:#e6f5eb; color:#398b5a; }
      .pan-tab-baidu { background:#fff0e7; color:#b96438; }
      .pan-tab-copy { display:grid; gap:3px; min-width:0; }
      .pan-tab-copy > span { color:inherit; font-size:12px; font-weight:750; white-space:nowrap; }
      .pan-tab-copy small { color:var(--muted); font-size:10px; white-space:nowrap; }
      .pan-page .pan-grid { display:block; grid-template-columns:1fr; gap:0; min-width:0; padding-top:0; }
      .pan-back-button { display:inline-flex; align-items:center; gap:7px; min-height:36px; padding:0 11px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--primary-dark); font-family:inherit; font-size:11px; font-weight:700; cursor:pointer; }
      .pan-back-button:hover { border-color:#98a8d9; background:var(--hover); }
      .pan-back-button:focus-visible { outline:3px solid var(--primary); outline-offset:2px; }
      .pan-back-button > span { font-size:17px; line-height:1; }
      .pan-page .pan-card { min-width:0; padding:0; overflow:visible; border:0; border-radius:0; background:transparent; box-shadow:none; }
      .pan-page .pan-card:hover { transform:none; box-shadow:none; }
      .pan-page .pan-card[hidden] { display:none !important; }
      .pan-card-content { min-width:0; }
      .pan-account-toolbar { display:flex; align-items:center; justify-content:flex-end; flex-wrap:wrap; gap:10px 16px; padding:12px 0; }
      .pan-account-toolbar-actions { display:flex; align-items:center; justify-content:flex-end; gap:15px; }
      .pan-platform-switch { display:flex; align-items:center; gap:8px; color:var(--muted); font-size:11px; white-space:nowrap; }
      .pan-page .pan-enable-switch { transform:none; transform-origin:center; }
      .pan-page .pan-add-account { min-height:35px; padding:0 12px; }
      .pan-section-kicker { display:block; margin-bottom:3px; color:var(--muted); font-size:9px; font-weight:800; }
      .pan-security-note { margin:11px 0 0; padding:8px 10px; border:0; border-left:3px solid #90a4cf; border-radius:3px; background:var(--hover); color:var(--muted); font-size:10px; line-height:1.55; }
      .pan-object-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(min(100%,210px),1fr)); justify-content:start; gap:10px; padding:14px 0 3px; }
      .pan-object-card { min-width:0; min-height:110px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--ink); }
      .pan-object-card:hover { border-color:#a9b6d4; background:var(--raised); }
      .pan-account-object.is-disabled { background:#f6f7fa; }
      .pan-account-object { display:flex; flex-direction:column; align-items:stretch; justify-self:start; width:100%; max-width:240px; aspect-ratio:auto; min-height:0; padding:12px; animation:pan-account-card-enter .28s ease-out both; transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease,background-color .18s ease; }
      .pan-account-object:nth-child(2) { animation-delay:35ms; }
      .pan-account-object:nth-child(3) { animation-delay:70ms; }
      .pan-account-object:nth-child(4) { animation-delay:105ms; }
      .pan-account-object:nth-child(5) { animation-delay:140ms; }
      .pan-account-object:hover { transform:translateY(-3px); box-shadow:0 8px 20px rgba(30,48,85,.11); }
      @keyframes pan-account-card-enter { from { opacity:0; } to { opacity:1; } }
      .pan-object-open { position:relative; display:grid; grid-template-columns:52px minmax(0,1fr) 12px; align-content:start; align-items:start; gap:0 10px; flex:0 0 auto; min-width:0; min-height:0; padding:1px 0 9px; border:0; background:transparent; color:inherit; font-family:inherit; text-align:left; cursor:pointer; }
      .pan-object-open:hover { color:var(--ink); }
      .pan-account-avatar { position:relative; display:grid; place-items:center; width:52px; height:52px; flex:0 0 52px; overflow:hidden; border-radius:50%; background:#e4f2e9; color:#318154; font-size:16px; font-weight:800; }
      .pan-account-avatar img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; background:var(--panel); }
      .pan-object-copy { display:grid; align-content:start; gap:5px; min-width:0; flex:1; }
      .pan-object-copy strong { overflow:hidden; color:var(--ink); font-size:13px; text-overflow:ellipsis; white-space:nowrap; }
      .pan-object-copy small { overflow-wrap:anywhere; color:var(--muted); font-size:10px; white-space:normal; }
      .pan-object-copy .pan-account-meta { display:grid; grid-template-columns:minmax(0,1fr); gap:3px; overflow:visible; color:var(--soft); font-size:10px; font-weight:600; line-height:1.35; white-space:normal; }
      .pan-account-meta > span { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .pan-object-arrow { justify-self:end; color:var(--soft); font-size:18px; line-height:1; transition:transform .18s ease; }
      .pan-account-object:hover .pan-object-arrow { transform:translateX(2px); }
      .pan-account-card-actions { display:flex; align-items:center; justify-content:space-between; gap:6px; padding:8px 1px 0; border-top:1px solid var(--line); }
      .pan-account-card-actions .tag { white-space:nowrap; }
      .pan-account-default { min-height:26px; padding:0 7px; border:1px solid #cce4d5; border-radius:5px; background:#f3faf5; color:#318154; font-family:inherit; font-size:10px; font-weight:650; white-space:nowrap; cursor:pointer; }
      .pan-account-default:hover:not(:disabled) { border-color:#8fc4a1; background:#e8f6ed; }
      .pan-account-default:disabled { cursor:not-allowed; opacity:.55; }
      .pan-account-default-tag { font-size:9px; }
      .pan-page .pan-account-switch { width:36px; height:21px; flex:0 0 36px; border:0; border-radius:999px; background:#d7d8e4; transition:background-color .2s ease; }
      .pan-page .pan-account-switch.on { background:#3fa979; }
      .pan-page .pan-account-switch span { top:3px; left:3px; width:15px; height:15px; border-radius:50%; background:var(--panel); box-shadow:0 1px 3px #0002; transition:transform .2s cubic-bezier(.2,.8,.2,1); }
      .pan-page .pan-account-switch.on span { transform:translateX(15px); }
      .pan-page .pan-account-switch:hover:not(:disabled) { background:#c3c5d3; }
      .pan-page .pan-account-switch.on:hover:not(:disabled) { background:#358f67; }
      .pan-account-delete { min-height:32px; padding:0 10px; border:1px solid var(--danger-line); border-radius:6px; background:var(--danger-bg); color:#a94d65; font-family:inherit; font-size:11px; cursor:pointer; }
      .pan-account-delete:hover:not(:disabled) { border-color:var(--danger-line); background:var(--danger-bg); }
      .pan-account-delete:disabled { cursor:not-allowed; opacity:.55; }
      .pan-object-empty { grid-column:1 / -1; min-height:0; padding:17px; border:1px dashed var(--line); border-radius:6px; background:transparent; }
      .pan-object-detail[hidden],.pan-object-browser[hidden] { display:none !important; }
      .pan-object-detail { padding-top:2px; }
      .pan-object-detail-head { display:flex; align-items:center; gap:14px; width:min(100%,1000px); margin:0 auto; padding:12px 0 15px; border-bottom:1px solid var(--line); }
      .pan-detail-heading { display:grid; gap:2px; min-width:0; flex:1; }
      .pan-detail-heading small { color:var(--muted); font-size:10px; }
      .pan-detail-heading strong { color:var(--ink); font-size:17px; line-height:1.3; }
      .pan-object-pane { width:min(100%,1000px); max-width:1000px; margin:18px auto 26px; padding:23px 26px 25px; border:1px solid var(--line); border-radius:10px; background:var(--panel); box-shadow:0 4px 18px rgba(36,36,58,.045); }
      .pan-object-account-detail { display:flex; align-items:center; gap:18px; padding:2px 0 20px; border-bottom:1px solid var(--line); }
      .pan-object-account-detail > .pan-account-avatar { width:62px; height:62px; flex-basis:62px; font-size:18px; }
      .pan-object-account-copy { min-width:0; flex:1; max-width:700px; }
      .pan-object-account-copy > .pan-section-kicker { display:none; }
      .pan-object-account-copy h3 { margin:3px 0 4px; color:var(--ink); font-size:19px; line-height:1.35; }
      .pan-object-account-detail > .tag { align-self:flex-start; margin-top:4px; padding:5px 10px; font-size:11px; }
      .pan-object-pane .pan-security-note { margin:12px 0 0; padding:0; border:0; background:transparent; color:var(--muted); font-size:10px; }
      .pan-account-stats { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0; max-width:540px; margin-top:13px; padding-top:12px; border-top:1px solid var(--line); }
      .pan-account-stats > div { min-width:0; padding:1px 16px; border-left:1px solid var(--line); }
      .pan-account-stats > div:first-child { padding-left:0; border-left:0; }
      .pan-account-stats small { display:block; color:var(--muted); font-size:10px; }
      .pan-account-stats strong { display:block; margin-top:4px; overflow-wrap:anywhere; color:var(--ink); font-size:14px; font-weight:700; }
      @media (max-width:420px) { .pan-account-stats { grid-template-columns:1fr; gap:6px; } }
      .pan-object-detail-actions { display:flex; align-items:center; gap:11px; flex-wrap:wrap; padding:15px 0 13px; border-bottom:1px solid var(--line); color:var(--muted); font-size:12px; }
      .pan-object-detail-actions > span:first-child { color:var(--muted); font-weight:650; }
      .pan-object-detail-actions .pan-account-switch { margin-right:5px; }
      .pan-object-detail-actions .pan-account-delete { min-height:34px; margin-left:auto; padding:0 12px; }
      .pan-detail-section { display:grid; gap:11px; margin-top:18px; padding-top:18px; border-top:1px solid var(--line); }
      .pan-detail-section-head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
      .pan-detail-section-head h3 { margin:0; color:var(--ink); font-size:16px; line-height:1.35; }
      .pan-detail-section-head p { margin:0; color:var(--muted); font-size:10px; }
      .pan-object-form { display:grid; gap:10px; padding:6px 0; }
      .pan-add-method { display:inline-grid; grid-template-columns:96px 96px; gap:3px; width:max-content; max-width:100%; padding:3px; border:1px solid var(--line); border-radius:7px; background:var(--bg); }
      .pan-add-method button { min-height:32px; padding:0 12px; border:0; border-radius:5px; background:transparent; color:var(--muted); font:inherit; font-size:11px; font-weight:700; cursor:pointer; }
      .pan-add-method button[aria-pressed="true"] { background:var(--panel); color:var(--primary-dark); box-shadow:0 1px 3px rgba(26,35,58,.12); }
      .pan-quark-scan { display:grid; justify-items:start; gap:10px; }
      .pan-quark-scan[hidden],.pan-quark-scan-image[hidden] { display:none !important; }
      .pan-quark-scan .pan-security-note { margin:0; }
      .pan-quark-scan-image { display:block; width:min(100%,240px); aspect-ratio:1; padding:8px; border:1px solid var(--line); border-radius:6px; background:var(--panel); object-fit:contain; }
      .pan-quark-scan-status { min-height:16px; margin:0; color:var(--muted); font-size:11px; }
      .pan-directory { display:grid; grid-template-columns:minmax(0,1fr) 132px; gap:10px; margin:0; }
      .pan-directory input { min-width:0; min-height:44px; padding:9px 12px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); outline:none; }
      .pan-directory input:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--primary-soft); }
      .pan-directory .outline-button { min-height:44px; padding:0 14px; }
      .pan-page .account-add { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px; margin:0; }
      .pan-page .account-add input { min-width:0; min-height:39px; padding:8px 10px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); outline:none; }
      .pan-page .account-add input:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--primary-soft); }
      .pan-page .account-add .outline-button { min-height:39px; padding:0 13px; }
      .pan-page .account-actions { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1.35fr); gap:8px; margin:0; }
      .pan-page .account-actions .outline-button { min-height:39px; }
      .pan-action-row { align-items:stretch; }
      .pan-field-label { display:block; margin:0 0 6px; color:var(--muted); font-size:10px; font-weight:700; }
      .pan-page .pan-select { width:100%; min-height:39px; padding:8px 10px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); }
      .pan-page .pan-select:focus-visible { outline:3px solid var(--primary); outline-offset:2px; }
      .pan-page .group-account { display:grid; grid-template-columns:minmax(0,1fr) 84px auto; gap:8px; }
      .pan-page .group-account input,.pan-page .group-account select { min-width:0; min-height:39px; padding:8px 10px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--ink); }
      .pan-page .group-account .outline-button { min-height:39px; padding:0 12px; }
      .pan-page .outline-button:disabled,.pan-page .pan-select:disabled,.pan-page input:disabled { cursor:not-allowed; opacity:.55; }
      .pan-page .outline-button { border-color:var(--primary); background:var(--panel); color:var(--primary-dark); }
      .pan-page .outline-button:hover:not(:disabled) { background:var(--primary-soft); }
      @media (max-width:760px) {
        .pan-page { margin-top:15px; }
        .pan-tabs { margin-right:-2px; }
        .pan-tab { min-width:150px; min-height:54px; padding:7px 10px; }
        .pan-account-toolbar { align-items:flex-start; }
        .pan-account-toolbar-actions { gap:9px; }
        .pan-object-grid { grid-template-columns:repeat(auto-fill,minmax(min(100%,200px),1fr)); gap:8px; padding-top:12px; }
        .pan-account-object { max-width:230px; padding:11px; }
        .pan-object-open { grid-template-columns:48px minmax(0,1fr) 10px; column-gap:8px; }
        .pan-account-avatar { width:48px; height:48px; flex-basis:48px; }
        .pan-account-card-actions { gap:5px; }
        .pan-object-detail-head { display:grid; grid-template-columns:auto minmax(0,1fr); gap:7px 11px; width:100%; }
        .pan-detail-heading { grid-column:2; }
        .pan-object-detail-head > .pan-platform-switch { grid-column:2; justify-self:start; margin:0; }
        .pan-object-pane { width:100%; max-width:none; margin:13px 0 20px; padding:17px; }
        .pan-object-account-detail { display:grid; grid-template-columns:62px minmax(0,1fr); align-items:start; gap:12px; }
        .pan-account-stats { max-width:100%; }
        .pan-object-account-detail > .tag { grid-column:2; grid-row:2; justify-self:start; }
        .pan-directory,.pan-page .account-add { grid-template-columns:1fr; }
        .pan-directory .outline-button,.pan-page .account-add .outline-button { width:100%; }
        .pan-page .account-actions { grid-template-columns:1fr; }
        .pan-page .group-account { grid-template-columns:minmax(0,1fr) 78px; }
        .pan-page .group-account .outline-button { grid-column:1 / -1; }
        .pan-object-detail-actions { flex-wrap:wrap; }
      }
      @media (max-width:390px) {
        .pan-account-toolbar-actions { width:100%; justify-content:flex-end; }
        .pan-object-detail-head { align-items:start; }
        .pan-detail-heading { min-width:0; }
        .pan-object-pane { padding:14px; }
        .pan-object-copy small { max-width:none; }
      }

      /* ===== 可选深色模式 ===== */
      :root[data-theme="dark"] { color-scheme:dark; --ink:#e6f3ff; --muted:#9bb3ca; --soft:#829bb4; --line:#27425b; --bg:#081423; --panel:#102338; --raised:#152c43; --input:#0c1c2e; --hover:#1b354e; --primary:#57d6ff; --primary-dark:#8ce3ff; --primary-soft:#163a51; --accent-fill:#126e96; --accent-hover:#1681ac; --mint:#123b36; --mint-ink:#73d7b2; --peach:#3a2d20; --peach-ink:#f6b76a; --yellow:#3c3221; --yellow-ink:#f6c57c; --pink:#3a2536; --pink-ink:#e9a2c7; --danger:#ff9bab; --danger-bg:#3c2533; --danger-line:#70404e; --shadow:0 10px 30px rgba(0,6,15,.18); --nav-bg:#091a2c; --nav-ink:#9bb3ca; --nav-line:#22384e; --nav-active:#163a51; --nav-accent:#57d6ff; }
      :root[data-theme="dark"] body { background:var(--bg); color:var(--ink); scrollbar-color:#506075 var(--bg); }
      :root[data-theme="dark"] .topbar,:root[data-theme="dark"] .sidebar,:root[data-theme="dark"] .admin-popover { background:var(--panel); }
      :root[data-theme="dark"] .theme-control:hover,:root[data-theme="dark"] .theme-control:focus-within,:root[data-theme="dark"] .admin-chip:hover,:root[data-theme="dark"] .admin-chip[aria-expanded="true"] { border-color:var(--line); background:var(--hover); }
      :root[data-theme="dark"] .version-badge { background:var(--raised); color:var(--muted); }
      :root[data-theme="dark"] .brand-mark,:root[data-theme="dark"] .admin-avatar { background:var(--primary-soft); border-color:var(--line); color:var(--primary); }
      :root[data-theme="dark"] .popover-logout { background:var(--raised); color:var(--danger); }
      :root[data-theme="dark"] .popover-logout:hover { background:var(--danger-bg); border-color:var(--danger-line); }
      :root[data-theme="dark"] .bot-avatar { background:var(--primary-soft); border-color:var(--line); box-shadow:var(--shadow); }
      :root[data-theme="dark"] .bot-avatar::before { background:#667b98; }
      :root[data-theme="dark"] .avatar-face { color:#e5eaf1; }
      :root[data-theme="dark"] .nav-label,:root[data-theme="dark"] .nav-icon { color:var(--soft); }
      :root[data-theme="dark"] .nav a { color:var(--muted); }
      :root[data-theme="dark"] .nav a:hover,:root[data-theme="dark"] .nav a.active,:root[data-theme="dark"] .nav a[aria-current="true"] { background:var(--primary-soft); color:var(--primary-dark); }
      :root[data-theme="dark"] .sidebar-foot { border-color:var(--line); background:var(--raised); }
      :root[data-theme="dark"] .notice { border-color:#665a3d; color:var(--yellow-ink); }
      :root[data-theme="dark"] .metric:nth-child(1) { background:var(--panel); }
      :root[data-theme="dark"] .metric:nth-child(2) { background:#1d2b28; }
      :root[data-theme="dark"] .metric:nth-child(3) { background:#2b2821; }
      :root[data-theme="dark"] .metric:nth-child(4) { background:#2c222b; }
      :root[data-theme="dark"] .global-bar { background:var(--raised); }
      :root[data-theme="dark"] .primary-button { background:var(--accent-fill); color:#fff; box-shadow:0 4px 12px rgba(0,0,0,.18); }
      :root[data-theme="dark"] .primary-button:hover { background:var(--accent-hover); }
      :root[data-theme="dark"] .switch { background:#4b586b; }
      :root[data-theme="dark"] .switch.on { background:var(--accent-fill); }
      :root[data-theme="dark"] .switch span,:root[data-theme="dark"] .pan-page .pan-account-switch span { background:#edf1f7; }
      :root[data-theme="dark"] .tag.off { background:var(--raised); color:var(--muted); }
      :root[data-theme="dark"] .account-row { border-color:var(--line); background:var(--raised); }
      :root[data-theme="dark"] .pan-select,:root[data-theme="dark"] .console-card,:root[data-theme="dark"] .summary-card { background:var(--panel); }
      :root[data-theme="dark"] .console-card,:root[data-theme="dark"] .summary-card,:root[data-theme="dark"] .novel-master-panel,:root[data-theme="dark"] .novel-test-panel,:root[data-theme="dark"] .pan-object-pane { box-shadow:var(--shadow); }
      :root[data-theme="dark"] .profile-field,:root[data-theme="dark"] .connection-row,:root[data-theme="dark"] .status-item,:root[data-theme="dark"] .safe-list > div,:root[data-theme="dark"] .settings-row { border-bottom-color:var(--line); }
      :root[data-theme="dark"] .readonly-value { border-color:var(--line); background:var(--raised); }
      :root[data-theme="dark"] .main { background:var(--bg); }
      :root[data-theme="dark"] .profile-field > span,:root[data-theme="dark"] .connection-row > span,:root[data-theme="dark"] .status-item span,:root[data-theme="dark"] .safe-list span,:root[data-theme="dark"] .settings-row span { color:var(--muted); }
      :root[data-theme="dark"] .readonly-value small,:root[data-theme="dark"] .test-hint { color:var(--soft); }
      :root[data-theme="dark"] .test-bubble p { background:var(--raised); color:var(--muted); }
      :root[data-theme="dark"] .test-mini-avatar { background:var(--primary-soft); color:var(--primary); }
      :root[data-theme="dark"] .pan-tab:hover,:root[data-theme="dark"] .pan-tab.active { border-color:var(--line); background:var(--panel); }
      :root[data-theme="dark"] .pan-tab.active { box-shadow:0 1px 0 var(--panel); }
      :root[data-theme="dark"] .pan-tab-mark { background:var(--primary-soft); color:var(--primary); }
      :root[data-theme="dark"] .pan-tab-quark { background:var(--mint); color:var(--mint-ink); }
      :root[data-theme="dark"] .pan-tab-baidu { background:var(--peach); color:var(--peach-ink); }
      :root[data-theme="dark"] .pan-object-card { border-color:var(--line); background:var(--panel); }
      :root[data-theme="dark"] .pan-account-object.is-disabled { background:var(--input); }
      :root[data-theme="dark"] .pan-account-avatar { background:var(--mint); color:var(--mint-ink); }
      :root[data-theme="dark"] .pan-security-note { border-color:#526782; background:var(--raised); }
      :root[data-theme="dark"] .pan-object-card:hover { border-color:var(--primary); background:var(--raised); }
      :root[data-theme="dark"] .pan-object-empty { border-color:var(--line); background:transparent; }
      :root[data-theme="dark"] .pan-object-account-detail,:root[data-theme="dark"] .pan-object-detail { border-color:var(--line); }
      :root[data-theme="dark"] .pan-back-button { border-color:var(--line); }
      :root[data-theme="dark"] .pan-back-button:hover { border-color:var(--primary); background:var(--hover); }
      :root[data-theme="dark"] .shortcut-card { border-color:var(--line); background:var(--panel); }
      :root[data-theme="dark"] .shortcut-card:hover { border-color:var(--primary); background:var(--raised); }
      :root[data-theme="dark"] .outline-button,:root[data-theme="dark"] .pan-page .outline-button { border-color:#637198; background:var(--panel); }
      :root[data-theme="dark"] .outline-button:hover { background:var(--primary-soft); }
      :root[data-theme="dark"] .pan-note { border-color:var(--line); background:var(--raised); }
      :root[data-theme="dark"] .runtime-detail .status-item { background:var(--raised); }
      :root[data-theme="dark"] .config-group { border-color:var(--line); background:var(--raised); }
      :root[data-theme="dark"] .config-field label { color:var(--muted); }
      :root[data-theme="dark"] .config-field input,:root[data-theme="dark"] .config-field textarea,:root[data-theme="dark"] .config-field select,:root[data-theme="dark"] .account-add input,:root[data-theme="dark"] .group-account input,:root[data-theme="dark"] .group-account select,:root[data-theme="dark"] .pan-directory input,:root[data-theme="dark"] .qq-auth-row input,:root[data-theme="dark"] .qq-reader-key-row input,:root[data-theme="dark"] .qq-reader-phone-row input,:root[data-theme="dark"] .qq-reader-cookie { border-color:var(--line); background:var(--input); color:var(--ink); }
      :root[data-theme="dark"] .config-field input:focus,:root[data-theme="dark"] .config-field textarea:focus,:root[data-theme="dark"] .config-field select:focus,:root[data-theme="dark"] .account-add input:focus,:root[data-theme="dark"] .group-account input:focus,:root[data-theme="dark"] .pan-directory input:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--primary-soft); }
      :root[data-theme="dark"] input::placeholder,:root[data-theme="dark"] textarea::placeholder { color:var(--soft); opacity:1; }
      :root[data-theme="dark"] .settings-hint { background:var(--raised); }
      :root[data-theme="dark"] .command-list span { border-color:var(--line); background:var(--raised); color:var(--muted); }
      :root[data-theme="dark"] .novel-overline,:root[data-theme="dark"] .novel-panel-kicker,:root[data-theme="dark"] .novel-platform-overline { color:var(--muted); }
      :root[data-theme="dark"] .novel-test-panel .novel-panel-kicker { color:var(--peach-ink); }
      :root[data-theme="dark"] .novel-state-pill { border-color:#466457; background:var(--mint); color:var(--mint-ink); }
      :root[data-theme="dark"] .novel-state-dot { background:var(--mint-ink); box-shadow:0 0 0 4px var(--mint); }
      :root[data-theme="dark"] .novel-state-pill.is-off { border-color:var(--line); background:var(--raised); color:var(--muted); }
      :root[data-theme="dark"] .novel-state-pill.is-off .novel-state-dot { background:var(--soft); box-shadow:0 0 0 4px var(--hover); }
      :root[data-theme="dark"] .novel-master-panel { border-color:#4a5477; background:#202838; }
      :root[data-theme="dark"] .novel-test-panel { border-color:#5b4a3d; background:#2b2723; }
      :root[data-theme="dark"] .novel-panel-icon,:root[data-theme="dark"] .novel-badge { background:var(--primary-soft); color:var(--primary); }
      :root[data-theme="dark"] .novel-test-panel .novel-panel-icon { background:var(--peach); color:var(--peach-ink); }
      :root[data-theme="dark"] .novel-master-copy p,:root[data-theme="dark"] .novel-test-panel p { color:var(--muted); }
      :root[data-theme="dark"] .novel-master-state span,:root[data-theme="dark"] .novel-test-note,:root[data-theme="dark"] .novel-platform-count,:root[data-theme="dark"] .novel-item-copy small,:root[data-theme="dark"] .novel-item-status { color:var(--soft); }
      :root[data-theme="dark"] .novel-item { border-color:var(--line); background:var(--panel); }
      :root[data-theme="dark"] .novel-item:hover { border-color:var(--primary); background:var(--raised); box-shadow:var(--shadow); }
      :root[data-theme="dark"] .novel-item.is-enabled { border-color:#466457; }
      :root[data-theme="dark"] .novel-item.is-enabled .novel-item-status { color:var(--mint-ink); }
      :root[data-theme="dark"] .novel-item.is-disabled { background:var(--input); }
      :root[data-theme="dark"] .novel-item:nth-child(3n+2) .novel-badge { background:var(--mint); color:var(--mint-ink); }
      :root[data-theme="dark"] .novel-item:nth-child(3n) .novel-badge { background:var(--peach); color:var(--peach-ink); }
      :root[data-theme="dark"] .toast { background:#344054; color:var(--ink); }
      :root[data-theme="dark"] .nav a:focus-visible,:root[data-theme="dark"] .refresh:focus-visible,:root[data-theme="dark"] .switch:focus-visible,:root[data-theme="dark"] .pan-select:focus-visible,:root[data-theme="dark"] .pan-object-card:focus-visible,:root[data-theme="dark"] .pan-back-button:focus-visible,:root[data-theme="dark"] .config-field input:focus-visible,:root[data-theme="dark"] .pan-directory input:focus-visible { outline-color:var(--primary); }
      :root[data-theme="dark"] .account-row button,:root[data-theme="dark"] .qq-reader-delete,:root[data-theme="dark"] .config-message.error,:root[data-theme="dark"] .qq-auth-message.error { color:var(--danger); }
      :root[data-theme="dark"] .account-row button:hover { color:#f2b6bb; }
      :root[data-theme="dark"] .qq-reader-account:hover { border-color:var(--primary); }
      :root[data-theme="dark"] .qq-reader-account.is-current { border-color:#7989c3; }
      :root[data-theme="dark"] .qq-reader-modal::backdrop { background:rgba(5,10,17,.65); }
      :root[data-theme="dark"] .pan-live { border-color:#466457; background:var(--mint); }
      :root[data-theme="dark"] .pan-live-dot { background:var(--mint-ink); box-shadow:0 0 0 4px #2e4c41; }
      :root[data-theme="dark"] .pan-live small { color:var(--muted); }
      :root[data-theme="dark"] .pan-live strong { color:var(--mint-ink); }
      :root[data-theme="dark"] .pan-page .pan-account-switch { background:#4b586b; }
      :root[data-theme="dark"] .pan-page .pan-account-switch:hover:not(:disabled) { background:#5c6a7e; }
      :root[data-theme="dark"] .pan-page .pan-account-switch.on { background:#497b64; }
      :root[data-theme="dark"] .pan-page .pan-account-switch.on:hover:not(:disabled) { background:#548e73; }
      :root[data-theme="dark"] .pan-page .pan-account-card-actions .tag.off { background:var(--raised); color:var(--muted); }
      :root[data-theme="dark"] .pan-page .pan-account-default { border-color:#466457; background:var(--mint); color:var(--mint-ink); }
      :root[data-theme="dark"] .pan-page .pan-account-default:hover:not(:disabled) { border-color:#608976; background:#2d493e; }
      :root[data-theme="dark"] .pan-page .pan-account-delete { border-color:var(--danger-line); background:var(--danger-bg); color:var(--danger); }
      :root[data-theme="dark"] .pan-page .pan-account-delete:hover:not(:disabled) { border-color:#986573; background:#4a333d; color:#f2b6bb; }
      :root[data-theme="dark"] .pan-object-pane .pan-security-note { border:0; background:transparent; }
      :root[data-theme="dark"] .pan-section-kicker { color:var(--soft); }
      @media (max-width:760px) {
        .topbar { min-height:50px; height:50px; padding:0 10px; gap:8px; }
        .brand { gap:7px; }
        .brand-mark { width:30px; height:30px; border-width:2px; font-size:11px; }
        .brand strong { font-size:14px; }
        .version-badge { display:none; }
        .top-actions { min-width:0; gap:4px; }
        .theme-control { min-height:28px; gap:1px; padding:2px 3px 2px 5px; }
        .theme-control-label { display:none; }
        .theme-toggle-button { width:26px; height:26px; }
        .theme-control-icon { display:inline-block; font-size:15px; }
        .theme-control select { width:68px; max-width:68px; padding-right:12px; font-size:10px; }
        .admin-chip { min-height:30px; gap:4px; padding:2px 5px 2px 3px; font-size:11px; }
        .admin-avatar { width:24px; height:24px; font-size:10px; }
        .admin-chevron { font-size:11px; }
        #admin-name { max-width:64px; }
        .sidebar { display:flex; flex-direction:row; align-items:center; gap:8px; min-height:48px; max-height:54px; padding:6px 10px; }
        .sidebar > div:nth-child(2) { flex:1 1 auto; min-width:0; }
        .profile { display:flex; align-items:center; justify-content:flex-start; gap:6px; min-width:0; padding:0; }
        .bot-avatar { width:32px; height:32px; flex:0 0 32px; border-width:2px; box-shadow:none; }
        .bot-avatar::before { width:28px; height:27px; top:2px; }
        .avatar-face { left:7px; top:10px; font-size:11px; letter-spacing:1px; }
        .bot-avatar::after { right:1px; top:0; font-size:7px; }
        .profile strong { max-width:62px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11px; }
        .online { margin-left:0; font-size:10px; white-space:nowrap; }
        .nav { gap:2px; overflow-x:auto; scrollbar-width:none; }
        .nav::-webkit-scrollbar { display:none; }
        .nav a { min-height:32px; gap:5px; padding:6px 7px; border-radius:6px; font-size:11px; white-space:nowrap; }
        .nav-icon { width:14px; font-size:13px; }
        .content:has(#page-messages:not([hidden])) { width:100%; padding-top:0; }
      }
      @media (max-width:390px) {
        .profile strong { display:none; }
        .online { display:none; }
        .sidebar { gap:5px; padding-left:7px; padding-right:7px; }
        .nav a { padding-left:6px; padding-right:6px; }
      }
      @media (max-width:760px) {
        body.msg-mobile-chat-view .topbar,
        body.msg-mobile-chat-view .sidebar { display:none; }
        body.msg-mobile-chat-view .main { min-height:100dvh; }
        body.msg-mobile-chat-view .content { width:100%; padding:0; }
      }

    /* 聊天工作区，与控制台共用主题变量。 */
.msg-shell { --msg-list-width:340px; display:grid; grid-template-columns:minmax(220px,var(--msg-list-width)) minmax(0,1fr); height:calc(100vh - 126px); min-height:520px; align-items:stretch; background:var(--panel); border:1px solid var(--line); border-radius:10px; overflow:hidden; transition:grid-template-columns .22s ease; }
             .msg-panel { display:flex; flex-direction:column; min-width:0; min-height:0; background:var(--panel); }
             .chat-list-panel { position:relative; border-right:1px solid var(--line); background:#fafafa; }
            .msg-list-head { display:flex; flex-direction:column; gap:8px; padding:10px 48px 8px 12px; border-bottom:1px solid var(--line); background:var(--panel); }
            .msg-filter { display:flex; gap:2px; padding:2px; background:var(--hover); border-radius:8px; }
            .msg-filter button { flex:1 1 0; min-width:0; min-height:26px; padding:0 4px; border:0; border-radius:6px; background:transparent; color:var(--muted); font-size:11px; font-weight:600; cursor:pointer; }
            .msg-filter button.active { background:var(--panel); color:var(--primary); box-shadow:0 1px 3px rgba(0,0,0,.08); }
            .msg-search { display:flex; gap:6px; }
            .msg-search input { flex:1 1 0; min-width:0; height:30px; padding:0 10px; border:1px solid transparent; border-radius:15px; background:var(--hover); color:var(--ink); font-size:12px; outline:none; transition:all .15s ease; }
            .msg-search input:focus { border-color:var(--primary); background:var(--panel); }
            .msg-search button { height:30px; padding:0 12px; border:0; border-radius:15px; background:var(--primary); color:#fff; font-size:11px; font-weight:700; cursor:pointer; }
            .msg-chats { --msg-chat-row-height:52px; flex:1 1 0; min-height:0; overflow-y:auto; padding:4px 6px; overscroll-behavior:contain; overflow-anchor:none; scrollbar-gutter:stable; }
            .msg-chat-list-track { position:relative; width:100%; min-height:100%; overflow:visible; }
            .msg-chat-folder { display:flex; box-sizing:border-box; align-items:center; gap:9px; width:100%; height:38px; min-height:38px; max-height:38px; margin:0; padding:0 8px; border:0; border-radius:6px; background:transparent; color:var(--muted); text-align:left; cursor:pointer; }
            .msg-chat-folder:hover { background:var(--hover); }
            .msg-chat-folder strong { font-size:12px; font-weight:700; }
            .msg-chat-folder small { margin-left:auto; color:var(--soft); font-size:10px; }
            .msg-chat-folder-caret { width:7px; height:7px; border-right:1.5px solid currentColor; border-bottom:1.5px solid currentColor; transform:rotate(45deg) translateY(-2px); transition:transform .14s ease; }
            .msg-chat-folder[aria-expanded="false"] .msg-chat-folder-caret { transform:rotate(-45deg); }
            .msg-chat-divider { display:flex; box-sizing:border-box; align-items:center; height:28px; margin:0 6px; padding:0 4px; border-top:1px solid var(--line); color:var(--soft); font-size:10px; font-weight:650; line-height:1.2; }
            .msg-chat-divider:first-child { margin-top:0; border-top:0; }
            .msg-chat { display:flex; box-sizing:border-box; gap:10px; width:100%; height:52px; min-height:52px; max-height:52px; padding:6px 8px; border:0; border-radius:8px; background:transparent; text-align:left; cursor:pointer; transition:background .12s ease; }
            .msg-chat:hover { background:var(--hover); }
            .msg-chat.active { background:var(--primary-soft); }
            .msg-chat-badge { flex:0 0 auto; min-width:18px; height:18px; padding:0 5px; border-radius:9px; background:#fa5151; color:#fff; font-size:11px; font-weight:700; line-height:18px; text-align:center; box-sizing:border-box; }
            .msg-chat.pinned { background:var(--primary-soft); }
            .msg-chat.pinned:hover { background:var(--primary-soft); }
            .msg-chat.pinned.active { background:var(--primary-soft); }
            .msg-chat.pinned .msg-chat-top strong { color:var(--primary-dark); }
            .msg-chat.pinned .msg-chat-top small { color:var(--primary-dark); }
            .msg-chat-top strong.admin,
            .msg-chat.pinned .msg-chat-top strong.admin { color:#dc2626 !important; font-weight:700; }
            .msg-chat-avatar { position:relative; width:40px; height:40px; flex:0 0 auto; display:grid; place-items:center; border-radius:50%; background:var(--primary-soft); color:var(--primary); font-size:14px; font-weight:800; overflow:hidden; }
            .msg-chat-avatar img { width:100%; height:100%; object-fit:cover; position:relative; z-index:1; border-radius:50%; }
            .msg-chat-avatar .avatar-letter { position:absolute; inset:0; display:grid; place-items:center; font-size:14px; font-weight:800; color:var(--primary); }
            .msg-chat-avatar.avatar-fallback .avatar-letter { position:static; display:grid; }
            .msg-chat-main { flex:1 1 0; min-width:0; align-self:center; }
            .msg-chat-top { display:flex; align-items:center; gap:6px; }
            .msg-chat-top strong { font-size:13px; font-weight:600; color:var(--ink); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            .msg-chat-top small { margin-left:auto; flex:0 0 auto; color:var(--muted); font-size:10px; }
            .msg-chat-sub-row { display:flex; align-items:center; gap:8px; margin-top:3px; min-width:0; }
            .msg-chat-sub { flex:1 1 0; min-width:0; color:var(--muted); font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            .msg-chat-type { display:none; }
            .msg-chat-meta { display:none; }
            .msg-empty { padding:26px 14px; color:var(--muted); font-size:12px; text-align:center; }
            .msg-work { position:relative; display:flex; flex-direction:column; min-width:0; min-height:0; background:var(--raised); }
            .msg-head { display:flex; align-items:center; gap:10px; padding:10px 16px; background:var(--panel); border-bottom:1px solid var(--line); }
            .msg-head-name { font-size:15px; font-weight:650; color:var(--ink); }
            .msg-head-name.admin { color:#dc2626 !important; font-weight:700; }
            .msg-head-sub { margin-top:2px; color:var(--muted); font-size:11px; }
            .msg-head-actions { margin-left:auto; display:flex; gap:7px; flex-wrap:wrap; justify-content:flex-end; }
            .msg-pan-account-control { display:flex; align-items:center; gap:6px; min-width:0; min-height:28px; padding:0 8px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--muted); font-size:10px; white-space:nowrap; }
            .msg-pan-account-control[hidden] { display:none; }
            .msg-pan-account-control select { min-width:0; max-width:155px; border:0; outline:0; background:transparent; color:var(--muted); font-family:inherit; font-size:11px; font-weight:600; cursor:pointer; }
            .msg-pan-account-control select:disabled { cursor:not-allowed; opacity:.65; }
            .msg-btn { min-height:28px; padding:0 10px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--muted); font-size:11px; font-weight:600; cursor:pointer; transition:all .16s ease; }
            .msg-btn:hover { border-color:var(--primary); color:var(--primary); }
            .msg-btn.primary { border-color:var(--primary); background:var(--primary); color:#fff; }
            .msg-btn.primary:hover { background:#0ea5e0; }
            .msg-body { flex:1 1 0; min-height:0; overflow-y:auto; padding:18px 16px 10px; background:var(--raised); overscroll-behavior:contain; scrollbar-gutter:stable; }
            .msg-body.msg-positioning { visibility:hidden; overflow-anchor:none; }
            .msg-loading { display:grid; gap:12px; padding:18px 8px; }
            .msg-loading span { display:block; width:68%; height:44px; border-radius:10px; background:#e7ebf0; animation:msg-loading-pulse 1.15s ease-in-out infinite alternate; }
            .msg-loading span:nth-child(2) { width:54%; margin-left:18%; animation-delay:.18s; }
            .msg-loading span:nth-child(3) { width:62%; animation-delay:.36s; }
            @keyframes msg-loading-pulse { from { opacity:.48; transform:translateY(1px); } to { opacity:1; transform:translateY(0); } }
            .msg-day { margin:10px 0; color:var(--muted); font-size:10px; text-align:center; }
            .msg-system-row { display:flex; flex-direction:column; align-items:center; gap:5px; margin:12px 0 16px; text-align:center; }
            .msg-system-time { padding:2px 8px; border-radius:12px; background:#e2e4e8; color:var(--muted); font-size:10px; line-height:1.35; }
            .msg-system-notice { max-width:min(90%,520px); padding:4px 12px; border-radius:16px; background:#e5e6e9; color:var(--muted); font-size:12px; line-height:1.5; overflow-wrap:anywhere; }
            .msg-system-name { color:var(--primary); }
            /* 消息行必须使用真实高度，避免估算布局在显示后把滚动位置推离底部。 */
            .msg-row { display:flex; gap:9px; margin-bottom:14px; }
            .msg-row.self { flex-direction:row-reverse; }
            .msg-avatar { position:relative; width:36px; height:36px; flex:0 0 auto; display:grid; place-items:center; border-radius:50%; background:var(--primary-soft); color:var(--primary); font-size:12px; font-weight:800; overflow:hidden; }
            .msg-avatar img { width:100%; height:100%; object-fit:cover; position:relative; z-index:1; border-radius:50%; }
            .msg-avatar .avatar-letter { position:absolute; inset:0; display:grid; place-items:center; font-size:12px; font-weight:800; color:var(--primary); }
            .msg-avatar.avatar-fallback .avatar-letter { position:static; display:grid; }
            .msg-bubble-wrap { max-width:min(70%,560px); min-width:0; }
            .msg-row.self .msg-bubble-wrap { display:flex; flex-direction:column; align-items:flex-end; }
            .msg-bubble-name { margin-bottom:3px; color:var(--muted); font-size:10px; padding-left:2px; }
            .msg-row.self .msg-bubble-name { padding-left:0; padding-right:2px; }
            .msg-bubble { padding:8px 12px; border-radius:3px 10px 10px 10px; background:var(--panel); color:var(--ink); font-size:13px; line-height:1.6; word-break:break-word; white-space:pre-wrap; box-shadow:0 1px 2px rgba(0,0,0,.05); }
            .msg-row.self .msg-bubble { border-radius:10px 3px 10px 10px; background:var(--primary); color:#fff; }
            .msg-row.self .msg-bubble .msg-bubble-quote { color:#dff1fd; }
            .msg-inline-link { color:var(--primary); text-decoration:underline; text-underline-offset:2px; }
            .msg-inline-code { padding:1px 4px; border-radius:4px; background:rgba(0,0,0,.08); font:12px/1.4 Consolas,Monaco,monospace; }
            .msg-command-chip { display:inline; margin:0 2px; padding:0 2px; border:0; border-bottom:1px dashed currentColor; background:transparent; color:inherit; font:inherit; line-height:inherit; cursor:pointer; }
            .msg-command-chip:hover { opacity:.72; }
            .msg-bubble.recalled { color:#c45b5b; font-style:italic; background:var(--danger-bg); border:1px solid var(--danger-line); }
            .msg-bubble-quote { display:flex; flex-direction:column; gap:3px; max-width:100%; margin:0 0 8px; padding:6px 9px; border-left:2px solid var(--primary); border-radius:3px; background:var(--primary-soft); color:var(--muted); font-size:12px; white-space:normal; }
            .msg-quote-jump { position:relative; width:100%; border:0; border-left:2px solid var(--primary); text-align:left; font-family:inherit; line-height:inherit; cursor:pointer; padding-right:26px; }
            .msg-quote-jump:hover { background:var(--primary-soft); }
            .msg-quote-jump:focus-visible { outline:2px solid var(--primary); outline-offset:2px; }
            .msg-quote-jump-icon { position:absolute; top:5px; right:8px; opacity:.65; font-size:14px; }
            .msg-row.msg-jump-target .msg-bubble { animation:msg-reference-highlight 2.2s ease-out; outline:2px solid #5caaff; outline-offset:3px; }
            @keyframes msg-reference-highlight { 0%,25% { box-shadow:0 0 0 6px rgba(71,156,255,.26); } 100% { box-shadow:0 0 0 2px rgba(71,156,255,0); } }
            @media (prefers-reduced-motion:reduce) { .msg-row.msg-jump-target .msg-bubble { animation:none; } }
            .msg-quote-name { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:500; }
            .msg-quote-content { display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:2; overflow:hidden; white-space:pre-wrap; overflow-wrap:anywhere; }
            .composer-mention { color:var(--primary); white-space:pre-wrap; user-select:all; }
            .msg-mention-picker { position:fixed; z-index:1800; width:260px; max-height:min(300px,60vh); padding:5px; box-sizing:border-box; overflow:hidden; border:1px solid #e2e7ef; border-radius:10px; background:var(--panel); color:var(--ink); box-shadow:0 10px 36px #15263d24; }
            .msg-mention-picker[hidden] { display:none; }
            .msg-mention-heading { padding:4px 7px 6px; color:var(--soft); font-size:11px; }
            .msg-mention-options { max-height:min(258px,calc(60vh - 42px)); overflow:auto; overscroll-behavior:contain; }
            .msg-mention-item { display:flex; width:100%; align-items:center; gap:8px; min-height:44px; padding:5px 7px; border:0; border-radius:7px; background:transparent; color:inherit; text-align:left; cursor:pointer; }
            .msg-mention-item.active,.msg-mention-item:not(:disabled):hover { background:var(--primary-soft); }
            .msg-mention-item:disabled { cursor:default; opacity:.5; }
            .msg-mention-avatar { position:relative; display:grid; place-items:center; flex:none; width:28px; height:28px; overflow:hidden; border-radius:50%; background:var(--primary-soft); color:var(--primary-dark); font-size:13px; }
            .msg-mention-avatar img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }
            .msg-mention-avatar .avatar-letter { position:absolute; inset:0; display:grid; place-items:center; }
            .msg-mention-avatar.everyone { background:var(--primary-soft); color:var(--primary); font-size:18px; }
            .msg-mention-copy { display:flex; min-width:0; flex-direction:column; gap:2px; }
            .msg-mention-copy strong { overflow:hidden; font-size:13px; font-weight:500; text-overflow:ellipsis; white-space:nowrap; }
            .msg-mention-copy small,.msg-mention-empty { color:#8993a1; font-size:11px; }
            .msg-mention-empty { padding:16px 9px; }
            .msg-row.self .msg-bubble-quote { background:rgba(255,255,255,.22); border-left-color:#fff; }
            .msg-media { margin-top:7px; }
            .msg-media-text { white-space:pre-wrap; word-break:break-word; }
            .msg-media-text-after { margin-top:7px; }
            .msg-inline-media { display:flex; align-items:center; flex-wrap:wrap; gap:4px; min-width:0; max-width:100%; }
            .msg-inline-media > .msg-media { margin-top:0; }
            .msg-inline-media > .msg-media-text { margin-top:0; }
            .msg-image-media { display:flex; flex-direction:column; align-items:flex-start; gap:4px; }
            .msg-image-link { display:block; min-width:24px; min-height:24px; padding:0; border:0; background:transparent; text-align:left; line-height:0; cursor:zoom-in; }
            .msg-image-link:focus-visible { outline:2px solid var(--primary); outline-offset:3px; }
            .msg-media img { max-width:240px; max-height:240px; border-radius:8px; display:block; cursor:zoom-in; transition:transform .12s ease; background:var(--hover); }
            .msg-media img:hover { transform:scale(1.03); }
            .msg-video-media video { display:block; width:min(320px,80vw); max-height:240px; border-radius:8px; background:#111; }
             /* 图片失效时保留占位提示，不能把包含提示的按钮整体隐藏。 */
             .msg-image-link.is-broken { display:inline-flex; align-items:center; min-width:0; min-height:0; padding:0; cursor:default; line-height:1.4; }
             .msg-image-link.is-broken img { display:none; }
             .msg-image-link.is-broken .msg-media-ph { margin:0; }
            .msg-file-card { display:flex; align-items:center; gap:9px; min-width:190px; max-width:290px; padding:8px 10px; border-radius:8px; background:#f5f8fc; color:#3e4a5a; text-decoration:none; }
            .msg-file-card:hover { background:#eaf2fc; }
            .msg-file-card.is-unavailable { color:var(--muted); }
            .msg-file-icon { width:28px; height:28px; flex:0 0 28px; display:grid; place-items:center; border-radius:6px; background:var(--primary-soft); color:var(--primary); font-size:15px; font-weight:700; }
            .msg-file-info { min-width:0; flex:1; display:flex; flex-direction:column; gap:1px; }
            .msg-file-info strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; font-weight:600; }
            .msg-file-info small { color:var(--muted); font-size:10px; line-height:1.3; }
            .msg-file-action { flex:0 0 auto; color:var(--primary); font-size:10px; }
            .msg-media-ph { display:inline-block; padding:8px 14px; background:var(--hover); border-radius:8px; font-size:12px; color:var(--muted); }
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
            .msg-send-error { width:18px; height:18px; margin-left:7px; padding:0; border:0; border-radius:50%; background:var(--danger); color:#fff; font-size:12px; font-weight:800; line-height:18px; text-align:center; vertical-align:-5px; cursor:pointer; box-shadow:0 1px 3px rgba(230,67,64,.25); }
            .msg-send-error:hover { background:#c92f2c; transform:scale(1.06); }
            .msg-tags { display:inline-flex; gap:4px; margin-left:6px; vertical-align:middle; }
            .msg-tag { display:inline-block; padding:0 5px; border-radius:4px; font-size:9px; line-height:15px; font-weight:700; }
            .msg-tag.bot { background:#e5edfb; color:#3b7bf7; }
            .msg-tag.role { background:#f0f1f3; color:#858b96; }
            .msg-tag.role.owner { background:#fef1dd; color:#f59e0b; }
            .msg-tag.role.admin { background:#e9fbf3; color:#319e6b; }
            .msg-tag.self { background:#e9fbf3; color:#319e6b; }
            .msg-tag.recalled { background:var(--danger-bg); color:var(--danger); }
            .msg-tag.muted { background:var(--danger-bg); color:var(--danger); }
            .msg-row.muted .msg-avatar { background:#d9dde2; color:#89919b; filter:grayscale(.7); }
            .msg-row.muted .msg-avatar img { filter:grayscale(1); opacity:.55; }
            .msg-mute-countdown { display:inline-block; margin-left:7px; color:var(--danger); font-size:9px; font-weight:700; }
            .msg-actions { display:flex; gap:5px; margin-top:5px; }
            .msg-row.self .msg-actions { justify-content:flex-end; }
            .msg-action { padding:0 7px; min-height:22px; border:0; border-radius:5px; background:#e4e7ec; color:var(--muted); font-size:10px; cursor:pointer; }
            .msg-action:hover { background:#d2e9fb; color:var(--primary); }
            .msg-load-older { display:block; margin:0 auto 12px; padding:5px 12px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--muted); font-size:11px; cursor:pointer; }
             .msg-composer { position:relative; display:flex; flex-direction:column; gap:8px; min-height:132px; max-height:52vh; padding:10px 14px 12px; overflow:auto; resize:vertical; background:var(--panel); border-top:1px solid var(--line); transition:height .22s ease,min-height .22s ease,padding .22s ease; }
            .msg-composer-tabs { display:flex; gap:5px; flex-wrap:wrap; }
            .msg-composer-mode[hidden], .msg-composer-tabs[hidden], .msg-composer-toggle[hidden], .msg-composer > .msg-extra[hidden] { display:none !important; }
            .msg-composer-tabs button { min-height:26px; padding:0 10px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--muted); font-size:11px; font-weight:600; cursor:pointer; }
            .msg-composer-tabs button.active { border-color:var(--primary); color:var(--primary); background:var(--primary-soft); }
            .msg-composer-mode { display:flex; gap:5px; flex-wrap:wrap; align-items:center; }
            .msg-composer-mode select { height:28px; padding:0 8px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--ink); font-size:11px; }
            .msg-composer-mode input { height:28px; min-width:120px; padding:0 8px; border:1px solid var(--line); border-radius:6px; background:var(--raised); color:var(--ink); font-size:11px; outline:none; }
            .msg-textarea { min-height:64px; max-height:150px; padding:9px 11px; border:0; border-radius:6px; background:var(--hover); color:var(--ink); font-size:12px; line-height:1.55; resize:vertical; outline:none; transition:all .15s ease; }
            .msg-textarea:focus { background:var(--panel); box-shadow:inset 0 0 0 1px var(--primary); }
            .msg-extra { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px; }
            .msg-extra input { height:28px; min-width:0; padding:0 8px; border:1px solid var(--line); border-radius:6px; background:var(--raised); color:var(--ink); font-size:11px; outline:none; }
            .msg-send-row { display:flex; align-items:center; gap:10px; justify-content:flex-end; }
            .msg-send-row .msg-btn.primary { min-height:32px; padding:0 24px; }
         .msg-input-box { position:relative; display:flex; flex:1 1 auto; flex-direction:column; min-height:96px; height:auto; max-height:none; overflow:auto; resize:vertical; border:1px solid #d8d9dd; border-radius:4px; background:var(--panel); transition:border-color .15s; }
        .msg-input-box:focus-within { border-color:var(--primary); }
        .msg-input-box.drag-over { border-color:var(--primary); background:#f0f9ff; box-shadow:0 0 0 2px rgba(18,183,245,.14); }
        .msg-input-box.has-inline-image .msg-editor { min-height:42px; }
        .msg-editor { width:100%; flex:1 1 auto; min-height:88px; height:auto; max-height:none; overflow:auto; padding:12px 14px 6px; border:0; outline:none; color:var(--ink); background:transparent; box-sizing:border-box; font-size:13px; line-height:1.6; white-space:pre-wrap; word-break:break-word; }
        .msg-editor:empty::before { content:attr(data-placeholder); color:var(--soft); pointer-events:none; }
        .msg-editor:focus { background:var(--panel); }
        .composer-inline-image { position:relative; display:inline-flex; align-items:center; vertical-align:middle; margin:2px 3px; padding:0; border:1px solid var(--line); border-radius:6px; background:var(--raised); line-height:0; }
        .composer-inline-image img { display:block; width:auto; max-width:180px; max-height:120px; border-radius:5px; object-fit:contain; }
        .composer-inline-image button { position:absolute; top:-7px; right:-7px; width:18px; height:18px; padding:0; border:0; border-radius:50%; background:rgba(0,0,0,.58); color:#fff; cursor:pointer; font-size:12px; line-height:18px; }
        .composer-inline-image button:hover { background:rgba(230,67,64,.92); }
        .msg-img-remove { position:absolute; top:3px; right:3px; width:18px; height:18px; border:0; border-radius:50%; background:rgba(0,0,0,.55); color:#fff; font-size:12px; line-height:1; cursor:pointer; display:grid; place-items:center; }
        .msg-img-remove:hover { background:rgba(230,67,64,.9); }
        .msg-attachment-inline { position:relative; display:flex; align-items:center; gap:8px; min-height:40px; margin:9px 12px 0; padding:7px 34px 7px 9px; border:1px solid #e3e4e8; border-radius:6px; background:var(--raised); color:#555; }
        .msg-attachment-inline[hidden] { display:none; }
        .msg-attachment-icon { width:25px; height:25px; display:grid; place-items:center; border-radius:5px; background:var(--primary-soft); color:var(--primary); font-size:13px; font-weight:700; }
        .msg-attachment-name { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11px; }
        .msg-quote-preview { display:flex; align-items:flex-start; gap:10px; width:fit-content; max-width:min(100%,420px); margin:7px 9px 0; padding:7px 9px; border:0; border-left:2px solid #b6bdc8; border-radius:5px; background:#f1f2f5; color:#7d8490; font-size:12px; }
        .msg-quote-preview[hidden] { display:none; }
        .msg-quote-preview b { color:var(--ink); }
        .msg-quote-text { display:grid; gap:3px; flex:1; min-width:0; overflow:hidden; }
        .msg-quote-preview .msg-action { flex:none; padding:0 3px; background:transparent; font-size:16px; line-height:20px; }
        .msg-quote-preview .msg-quote-content { -webkit-line-clamp:1; }
        .msg-composer-topbar { display:flex; align-items:center; gap:5px; min-height:30px; }
        .msg-composer-top-hint { margin-left:3px; color:var(--soft); font-size:10px; }
        .msg-toolbar { display:flex; align-items:center; gap:10px; min-height:30px; }
        .msg-tool-btn { display:grid; place-items:center; width:28px; height:28px; border-radius:4px; color:#6b6f78; cursor:pointer; }
        .msg-tool-btn:hover { background:var(--primary-soft); color:var(--primary); }
        .msg-tool-btn svg { display:block; }
            .msg-raw-modal { position:fixed; inset:0; z-index:60; display:grid; place-items:center; background:rgba(30,28,50,.45); padding:20px; }
            .msg-raw-modal[hidden] { display:none; }
            .msg-raw-box { width:min(720px,100%); height:min(640px,78vh); min-height:320px; display:flex; flex-direction:column; background:var(--panel); border-radius:12px; overflow:hidden; box-shadow:0 18px 50px rgba(40,36,90,.25); }
            .msg-raw-head { display:flex; align-items:center; justify-content:space-between; padding:12px 15px; border-bottom:1px solid var(--line); }
            .msg-raw-head strong { font-size:13px; color:var(--ink); }
            .msg-raw-head button { border:0; background:transparent; color:var(--muted); font-size:16px; cursor:pointer; }
            .msg-raw-actions { display:flex; align-items:center; gap:14px; }
            .msg-raw-head .msg-raw-copy { padding:4px 8px; font-size:12px; color:var(--primary); }
            .msg-raw-copy:disabled { cursor:wait; opacity:.65; }
            .msg-raw-content { flex:1 1 0; min-height:0; overflow:auto; padding:13px 15px; white-space:pre-wrap; word-break:break-all; color:var(--ink); font:12px/1.6 Consolas,Monaco,monospace; }
            .msg-mute-modal { position:fixed; inset:0; z-index:60; display:grid; place-items:center; background:rgba(30,28,50,.45); padding:20px; }
            .msg-mute-modal[hidden] { display:none; }
            .msg-mute-box { width:min(400px,100%); background:var(--panel); border-radius:12px; padding:16px; box-shadow:0 18px 50px rgba(40,36,90,.25); }
            .msg-mute-box h3 { margin:0 0 12px; font-size:14px; color:var(--ink); }
            .msg-mute-presets { display:flex; gap:7px; flex-wrap:wrap; margin-bottom:12px; }
            .msg-mute-presets button { min-height:30px; padding:0 12px; border:1px solid var(--line); border-radius:8px; background:var(--panel); color:var(--muted); font-size:11px; cursor:pointer; }
            .msg-mute-presets button.active { border-color:var(--primary); color:var(--primary); background:var(--primary-soft); }
            .msg-mute-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:12px; }
            .msg-remark-modal { position:fixed; inset:0; z-index:60; display:grid; place-items:center; background:rgba(30,28,50,.45); padding:20px; }
            .msg-remark-modal[hidden] { display:none; }
            .msg-remark-box { width:min(380px,100%); background:var(--panel); border-radius:12px; padding:16px; box-shadow:0 18px 50px rgba(40,36,90,.25); }
            .msg-remark-box h3 { margin:0 0 12px; font-size:14px; color:var(--ink); }
            /* ===== QQ PC 风格覆盖 ===== */
            .msg-shell { grid-template-columns:minmax(220px,var(--msg-list-width)) minmax(0,1fr); border:1px solid var(--line); border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.06); }
            .chat-list-panel { background:var(--raised); }
            .msg-list-head { padding:10px 12px; background:var(--raised); border-bottom:1px solid var(--line); }
            .msg-filter button.active { color:var(--primary); }
            .msg-chats { padding:4px 6px; }
            .msg-chat { height:52px; min-height:52px; max-height:52px; padding:6px 8px; border-radius:6px; }
            .msg-chat:hover { background:#eceef1; }
            .msg-chat.removed { background:#fff8f8; }
            .msg-chat.removed:hover { background:var(--danger-bg); }
            .msg-chat.removed .msg-chat-sub { color:#d15f63; font-weight:600; }
            .msg-chat.removed .msg-chat-avatar { filter:grayscale(.55); opacity:.72; }
            .msg-chat.active { background:#d5ebfb; }
            .msg-chat-avatar { width:38px; height:38px; }
            .msg-chat-top strong { font-size:12.5px; }
            .msg-chat-sub { font-size:11px; margin-top:1px; }
            .msg-work { background:var(--raised); }
            .msg-head { padding:8px 14px; background:var(--panel); }
            .msg-body { padding:14px 20px 8px; background:var(--raised); }
            .msg-day { margin:8px 0; color:#b6bcc4; font-size:10px; }
            .msg-row { gap:10px; margin-bottom:12px; align-items:flex-start; }
            .msg-avatar { width:38px; height:38px; }
            .msg-bubble-wrap { max-width:min(62%,560px); }
            .msg-bubble { padding:9px 12px; border-radius:4px 12px 12px 12px; background:var(--panel); font-size:13px; box-shadow:0 1px 2px rgba(0,0,0,.05); }
            .msg-row.self .msg-bubble { border-radius:12px 4px 12px 12px; background:#95ec69; color:#000; }
            .msg-row.self .msg-bubble .msg-bubble-quote { color:rgba(0,0,0,.55); }
            .msg-meta { color:#b6bcc4; font-size:9px; }
            .msg-bubble-name { font-size:10px; }
            .msg-composer { padding:8px 14px 10px; background:var(--panel); border-top:1px solid var(--line); }
            .msg-textarea { background:var(--raised); border-radius:4px; }
            .msg-textarea:focus { background:var(--panel); box-shadow:inset 0 0 0 1px var(--primary); }
            .msg-send-row .msg-btn.primary { background:var(--primary); border-color:var(--primary); }

            /* 右键菜单 */
            .msg-ctx { position:fixed; z-index:120; min-width:150px; padding:4px; background:var(--panel); border:1px solid var(--line); border-radius:8px; box-shadow:0 6px 20px rgba(0,0,0,.14); user-select:none; }
            .msg-ctx[hidden] { display:none; }
            .msg-ctx-item { display:flex; align-items:center; gap:8px; width:100%; padding:7px 10px; border:0; border-radius:5px; background:transparent; color:var(--ink); font-size:12px; text-align:left; cursor:pointer; }
            .msg-ctx-item:hover { background:var(--primary-soft); color:var(--primary); }
            .msg-ctx-item.danger:hover { background:#fff1f0; color:var(--danger); }
            .msg-ctx-sep { height:1px; margin:4px 8px; background:#eee; }

            /* 多选模式 */
            .msg-multi-bar { display:flex; align-items:center; gap:10px; padding:6px 14px; background:var(--primary-soft); border-bottom:1px solid #cfe8fb; font-size:12px; color:var(--primary); }
            .msg-multi-bar[hidden] { display:none; }
            .msg-row.multi-mode { cursor:pointer; }
            .msg-row.multi-mode .msg-avatar, .msg-row.multi-mode .msg-bubble { opacity:.85; }
            .msg-row.multi-mode.selected .msg-bubble { outline:2px solid var(--primary); outline-offset:2px; }
            .msg-pos { position:relative; display:inline-flex; flex:0 0 auto; }
            .msg-multi-check { display:none; }
            .msg-row.multi-mode .msg-multi-check { display:grid; position:absolute; left:-16px; top:50%; transform:translateY(-50%); width:18px; height:18px; border-radius:50%; border:2px solid #c3ccd4; background:var(--panel); display:grid; place-items:center; font-size:11px; color:#fff; }
            .msg-row.multi-mode.selected .msg-multi-check { border-color:var(--primary); background:var(--primary); }
            .msg-row.self.multi-mode .msg-multi-check { left:auto; right:-16px; }
            .msg-row.multi-mode.no-multi { opacity:.55; }
            .msg-row.multi-mode.no-multi .msg-multi-check { display:none; }
             .msg-row.multi-mode .msg-multi-check::after { content:'✓'; }
             .msg-pos { position:relative; }
             .msg-body-wrap { position:relative; display:flex; flex:1 1 0; min-height:0; overflow:hidden; }
             .msg-new-messages { position:absolute; right:18px; bottom:14px; z-index:3; display:inline-flex; align-items:center; gap:7px; min-height:32px; padding:0 12px; border:1px solid #b8dff2; border-radius:17px; background:var(--panel); color:var(--primary); box-shadow:0 5px 16px rgba(30,110,160,.18); font-size:11px; font-weight:700; cursor:pointer; transition:opacity .16s ease, transform .16s ease, box-shadow .16s ease; }
             .msg-new-messages:hover { transform:translateY(-1px); box-shadow:0 7px 18px rgba(30,110,160,.24); }
             .msg-new-messages[hidden] { display:none; }
             .msg-new-messages-dot { width:7px; height:7px; border-radius:50%; background:var(--primary); box-shadow:0 0 0 4px var(--primary-soft); }
             .msg-new-messages-arrow { font-size:15px; line-height:1; }
             /* 面板尺寸控制：脚本写入 --msg-list-width 并切换折叠 class。 */
             /* 缩放拖柄移到滚动条外侧，避免与会话列表滚轮滑块叠在同一条轨道。 */
             .msg-list-resizer { position:absolute; z-index:6; top:0; right:-12px; bottom:0; width:12px; padding:0; border:0; background:transparent; cursor:col-resize; }
             .msg-list-resizer,.msg-composer-resizer { touch-action:none; }
             .msg-list-resizer::before { content:""; position:absolute; top:50%; left:5px; width:2px; height:42px; border-radius:2px; background:#d5dbe2; transform:translateY(-50%); opacity:0; transition:opacity .16s ease,background .16s ease; }
             .chat-list-panel:hover .msg-list-resizer::before,.msg-list-resizer:focus-visible::before { opacity:1; }
             .msg-list-resizer:hover::before,.msg-list-resizer:focus-visible::before { background:var(--primary); }
             .msg-panel-toggle { display:grid; place-items:center; flex:0 0 auto; width:27px; height:27px; padding:0; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--muted); font-size:17px; line-height:1; cursor:pointer; transition:background .16s ease,border-color .16s ease,color .16s ease; }
             .msg-panel-toggle:hover,.msg-panel-toggle:focus-visible { border-color:var(--primary); background:var(--primary-soft); color:var(--primary); }
             .msg-list-collapse { position:absolute; z-index:5; top:10px; right:8px; margin:0; }
             .msg-composer-resizer { position:absolute; z-index:2; top:-6px; right:14px; left:14px; width:calc(100% - 28px); height:12px; padding:0; border:0; background:transparent; cursor:row-resize; }
             .msg-composer-resizer::before { content:""; position:absolute; top:5px; left:50%; width:42px; height:3px; border-radius:3px; background:#d5dbe2; transform:translateX(-50%); opacity:.7; transition:background .16s ease,opacity .16s ease; }
             .msg-composer-resizer:hover::before,.msg-composer-resizer:focus-visible::before { background:var(--primary); opacity:1; }
             .msg-composer-toggle { margin-right:2px; color:var(--muted); }
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
             .msg-mobile-back:hover,.msg-mobile-back:focus-visible { background:var(--primary-soft); color:var(--primary); outline:none; }
             /* 消息页/专用控制页已有自己的标题，隐藏上方重复的全局标题。 */
             .content:has(#page-messages:not([hidden])) > .page-heading,
             .content:has(#page-pans:not([hidden])) > .page-heading,
             .content:has(#page-novels:not([hidden])) > .page-heading { display:none; }
             /* 消息工作区优先使用可用宽度，减少桌面端两侧空白。 */
             .content:has(#page-messages:not([hidden])) { width:calc(100% - 20px); max-width:none; padding-top:0; }
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
               .msg-chats { --msg-chat-row-height:60px; }
               .msg-chat { height:60px; min-height:60px; max-height:60px; padding:8px 10px; border-radius:0; }
               .msg-chat-divider { margin-left:4px; margin-right:4px; }
               .msg-mobile-back { display:grid; }
               .msg-shell:not(.msg-mobile-chat-open) .msg-mobile-back { display:none; }
               .msg-head { min-height:54px; padding:8px 10px; gap:6px; }
               .msg-head-name { font-size:14px; }
               .msg-head-sub { font-size:10px; }
               .msg-head-actions { gap:4px; }
               .msg-head-actions .msg-btn { min-height:27px; padding:0 7px; font-size:10px; }
               .msg-pan-account-control { min-height:27px; padding:0 6px; }
               .msg-pan-account-control select { max-width:105px; font-size:10px; }
               .msg-body { padding:14px 10px 8px; }
               .msg-bubble-wrap { max-width:82%; }
               .msg-composer { max-height:52vh; padding:7px 10px 8px; }
               .msg-composer-top-hint { display:none; }
               .msg-input-box { max-height:none; }
               .msg-editor { min-height:42px; }
             }

              /* ===== 深色模式：统一炭灰层次与柔和强调色 ===== */
              :root[data-theme="dark"] .msg-shell { background:var(--panel); border-color:var(--line); box-shadow:0 1px 4px rgba(0,0,0,.2); }
              :root[data-theme="dark"] .msg-panel,:root[data-theme="dark"] .msg-list-head,:root[data-theme="dark"] .msg-head { background:var(--panel); border-color:var(--line); }
              :root[data-theme="dark"] .chat-list-panel { border-right-color:var(--line); background:#181e27; }
              :root[data-theme="dark"] .msg-filter { background:var(--input); }
              :root[data-theme="dark"] .msg-filter button { color:var(--muted); }
              :root[data-theme="dark"] .msg-filter button.active { background:var(--primary-soft); color:var(--primary); box-shadow:none; }
              :root[data-theme="dark"] .msg-search input { border-color:var(--line); background:var(--input); color:var(--ink); }
              :root[data-theme="dark"] .msg-search input:focus { border-color:var(--primary); background:var(--input); }
              :root[data-theme="dark"] .msg-search button { border-color:var(--line); background:var(--raised); color:var(--muted); }
              :root[data-theme="dark"] .msg-search button:hover { border-color:var(--primary); color:var(--primary); }
              :root[data-theme="dark"] .msg-chat:hover,:root[data-theme="dark"] .msg-chat-folder:hover { background:var(--raised); }
              :root[data-theme="dark"] .msg-chat.removed { background:#292127; }
              :root[data-theme="dark"] .msg-chat.removed:hover { background:var(--danger-bg); }
              :root[data-theme="dark"] .msg-chat.removed .msg-chat-sub { color:var(--danger); }
              :root[data-theme="dark"] .msg-chat.active { background:var(--primary-soft); }
              :root[data-theme="dark"] .msg-chat.pinned { background:#202a39; }
              :root[data-theme="dark"] .msg-chat.pinned:hover { background:var(--hover); }
              :root[data-theme="dark"] .msg-chat.pinned.active { background:var(--primary-soft); }
              :root[data-theme="dark"] .msg-chat.pinned .msg-chat-top strong { color:var(--primary); }
              :root[data-theme="dark"] .msg-chat.pinned .msg-chat-top small { color:var(--muted); }
              :root[data-theme="dark"] .msg-chat-top strong.admin,:root[data-theme="dark"] .msg-chat.pinned .msg-chat-top strong.admin,:root[data-theme="dark"] .msg-head-name.admin { color:var(--danger) !important; }
              :root[data-theme="dark"] .msg-chat-top strong,:root[data-theme="dark"] .msg-head-name { color:var(--ink); }
              :root[data-theme="dark"] .msg-chat-top small,:root[data-theme="dark"] .msg-chat-sub,:root[data-theme="dark"] .msg-bubble-name,:root[data-theme="dark"] .msg-head-sub { color:var(--muted); }
              :root[data-theme="dark"] .msg-chat-avatar,:root[data-theme="dark"] .msg-avatar { background:#2c3b50; color:#b0c6e4; }
              :root[data-theme="dark"] .msg-chat-avatar .avatar-letter,:root[data-theme="dark"] .msg-avatar .avatar-letter { color:#b0c6e4; }
              :root[data-theme="dark"] .msg-chat-folder { color:var(--muted); }
              :root[data-theme="dark"] .msg-chat-folder small,:root[data-theme="dark"] .msg-chat-divider { color:var(--soft); border-color:var(--line); }
              :root[data-theme="dark"] .msg-empty,:root[data-theme="dark"] .msg-day,:root[data-theme="dark"] .msg-meta { color:var(--soft); }
              :root[data-theme="dark"] .msg-work,:root[data-theme="dark"] .msg-body { background:var(--bg); }
              :root[data-theme="dark"] .msg-btn,:root[data-theme="dark"] .msg-pan-account-control { border-color:var(--line); background:var(--raised); color:var(--muted); }
              :root[data-theme="dark"] .msg-btn:hover { border-color:var(--primary); color:var(--primary); }
              :root[data-theme="dark"] .msg-btn.primary,:root[data-theme="dark"] .msg-send-row .msg-btn.primary { border-color:var(--accent-fill); background:var(--accent-fill); color:#fff; }
              :root[data-theme="dark"] .msg-btn.primary:hover,:root[data-theme="dark"] .msg-send-row .msg-btn.primary:hover { border-color:var(--accent-hover); background:var(--accent-hover); }
              :root[data-theme="dark"] .msg-pan-account-control select { color:var(--ink); }
              :root[data-theme="dark"] .msg-pan-account-control select option { background:var(--panel); color:var(--ink); }
              :root[data-theme="dark"] .msg-new-messages { border-color:#596783; background:var(--raised); color:var(--primary); box-shadow:var(--shadow); }
              :root[data-theme="dark"] .msg-new-messages-dot { background:var(--primary); box-shadow:0 0 0 4px var(--primary-soft); }
              :root[data-theme="dark"] .msg-system-time,:root[data-theme="dark"] .msg-system-notice { background:var(--raised); color:var(--muted); }
              :root[data-theme="dark"] .msg-system-name { color:var(--primary); }
              :root[data-theme="dark"] .msg-bubble { background:var(--raised); color:var(--ink); box-shadow:0 1px 2px rgba(0,0,0,.2); }
              :root[data-theme="dark"] .msg-row.self .msg-bubble { background:#304c40; color:#e1efe7; }
              :root[data-theme="dark"] .msg-inline-link,:root[data-theme="dark"] .composer-mention { color:#b5c6f5; }
              :root[data-theme="dark"] .msg-mention-picker { border-color:var(--line); background:var(--panel); color:var(--ink); box-shadow:0 12px 36px #0006; }
              :root[data-theme="dark"] .msg-mention-item.active,:root[data-theme="dark"] .msg-mention-item:not(:disabled):hover { background:var(--raised); }
              :root[data-theme="dark"] .msg-mention-avatar { background:var(--raised); color:var(--primary); }
              :root[data-theme="dark"] .msg-mention-avatar.everyone { background:var(--primary-soft); color:var(--primary); }
              :root[data-theme="dark"] .msg-mention-heading,:root[data-theme="dark"] .msg-mention-copy small,:root[data-theme="dark"] .msg-mention-empty { color:var(--muted); }
              :root[data-theme="dark"] .msg-inline-code { background:rgba(255,255,255,.08); }
              :root[data-theme="dark"] .msg-bubble.recalled { color:var(--danger); background:var(--danger-bg); border-color:var(--danger-line); }
              :root[data-theme="dark"] .msg-bubble-quote { border-left-color:#7b8cae; background:#1a222e; color:#b8c5d8; }
              :root[data-theme="dark"] .msg-quote-jump:hover { background:#293647; }
              :root[data-theme="dark"] .msg-row.self .msg-bubble .msg-bubble-quote { background:#263e33; border-left-color:#8bb69e; color:#c3d8ca; }
              :root[data-theme="dark"] .msg-row.self .msg-bubble .msg-quote-jump:hover { background:#2a4438; }
              :root[data-theme="dark"] .msg-quote-jump:focus-visible,:root[data-theme="dark"] .msg-image-link:focus-visible,:root[data-theme="dark"] .msg-row.msg-jump-target .msg-bubble { outline-color:var(--primary); }
              :root[data-theme="dark"] .msg-media-ph,:root[data-theme="dark"] .msg-image-link.is-broken .msg-media-ph { background:var(--input); color:var(--muted); }
              :root[data-theme="dark"] .msg-media img { background:var(--input); }
              :root[data-theme="dark"] .msg-loading span { background:var(--raised); }
              :root[data-theme="dark"] .msg-file-card,:root[data-theme="dark"] .msg-row.self .msg-file-card { background:#253343; color:var(--ink); }
              :root[data-theme="dark"] .msg-file-card:hover,:root[data-theme="dark"] .msg-row.self .msg-file-card:hover { background:#2d4054; }
              :root[data-theme="dark"] .msg-file-card.is-unavailable { color:var(--muted); }
              :root[data-theme="dark"] .msg-file-icon,:root[data-theme="dark"] .msg-attachment-icon { background:#344960; color:#c0d3ed; }
              :root[data-theme="dark"] .msg-file-info small,:root[data-theme="dark"] .msg-row.self .msg-file-info small { color:#b3c1d2; }
              :root[data-theme="dark"] .msg-file-action,:root[data-theme="dark"] .msg-row.self .msg-file-action { color:#b5c6f5; }
              :root[data-theme="dark"] .msg-send-error { background:#a74751; color:#fff; box-shadow:none; }
              :root[data-theme="dark"] .msg-send-error:hover { background:#913e48; }
              :root[data-theme="dark"] .msg-tag.bot { background:#233857; color:#83b3ff; }
              :root[data-theme="dark"] .msg-tag.role { background:var(--raised); color:var(--muted); }
              :root[data-theme="dark"] .msg-tag.role.owner { background:#483721; color:#f4ba60; }
              :root[data-theme="dark"] .msg-tag.role.admin { background:var(--mint); color:var(--mint-ink); }
              :root[data-theme="dark"] .msg-tag.self { background:var(--mint); color:var(--mint-ink); }
              :root[data-theme="dark"] .msg-tag.recalled,:root[data-theme="dark"] .msg-tag.muted { background:var(--danger-bg); color:var(--danger); }
              :root[data-theme="dark"] .msg-row.muted .msg-avatar { background:var(--hover); color:var(--muted); }
              :root[data-theme="dark"] .msg-mute-countdown { color:var(--danger); }
              :root[data-theme="dark"] .msg-action { background:var(--raised); color:var(--muted); }
              :root[data-theme="dark"] .msg-action:hover,:root[data-theme="dark"] .msg-tool-btn:hover { background:var(--primary-soft); color:var(--primary); }
              :root[data-theme="dark"] .msg-load-older { border-color:var(--line); background:var(--panel); color:var(--muted); }
              :root[data-theme="dark"] .msg-composer { background:var(--panel); border-top-color:var(--line); }
              :root[data-theme="dark"] .msg-composer-tabs button,:root[data-theme="dark"] .msg-composer-mode select { border-color:var(--line); background:var(--raised); color:var(--muted); }
              :root[data-theme="dark"] .msg-composer-tabs button.active,:root[data-theme="dark"] .msg-mute-presets button.active { border-color:#7b8cc1; color:var(--primary); background:var(--primary-soft); }
              :root[data-theme="dark"] .msg-composer-mode input,:root[data-theme="dark"] .msg-extra input { border-color:var(--line); background:var(--input); color:var(--ink); }
              :root[data-theme="dark"] .msg-textarea,:root[data-theme="dark"] .msg-editor { background:var(--input); color:var(--ink); }
              :root[data-theme="dark"] .msg-textarea:focus { background:var(--input); box-shadow:inset 0 0 0 1px var(--primary); }
              :root[data-theme="dark"] .msg-editor:focus { background:var(--input); }
              :root[data-theme="dark"] .msg-input-box { border-color:var(--line); background:var(--input); }
              :root[data-theme="dark"] .msg-input-box:focus-within { border-color:var(--primary); }
              :root[data-theme="dark"] .msg-input-box.drag-over { border-color:var(--primary); background:var(--primary-soft); box-shadow:0 0 0 2px rgba(170,184,245,.16); }
              :root[data-theme="dark"] .msg-attachment-inline,:root[data-theme="dark"] .composer-inline-image { border-color:var(--line); background:var(--raised); color:var(--ink); }
              :root[data-theme="dark"] .msg-composer-top-hint,:root[data-theme="dark"] .msg-editor:empty::before { color:var(--soft); }
              :root[data-theme="dark"] .msg-quote-preview { border-color:#7b8cae; background:var(--raised); color:var(--muted); }
              :root[data-theme="dark"] .msg-quote-preview b { color:var(--ink); }
              :root[data-theme="dark"] .msg-tool-btn { color:var(--muted); }
              :root[data-theme="dark"] .msg-raw-modal,:root[data-theme="dark"] .msg-mute-modal,:root[data-theme="dark"] .msg-remark-modal { background:rgba(5,10,17,.65); }
              :root[data-theme="dark"] .msg-raw-box,:root[data-theme="dark"] .msg-mute-box,:root[data-theme="dark"] .msg-remark-box { background:var(--panel); box-shadow:0 18px 50px rgba(0,0,0,.4); }
              :root[data-theme="dark"] .msg-raw-head { border-bottom-color:var(--line); }
              :root[data-theme="dark"] .msg-raw-head strong,:root[data-theme="dark"] .msg-mute-box h3,:root[data-theme="dark"] .msg-remark-box h3,:root[data-theme="dark"] .msg-raw-content { color:var(--ink); }
              :root[data-theme="dark"] .msg-raw-head button { color:var(--muted); }
              :root[data-theme="dark"] .msg-raw-head .msg-raw-copy { color:var(--primary); }
              :root[data-theme="dark"] .msg-remark-box label { color:var(--muted) !important; }
              :root[data-theme="dark"] .msg-mute-box input,:root[data-theme="dark"] .msg-remark-box input { background:var(--input); border-color:var(--line) !important; color:var(--ink); }
              :root[data-theme="dark"] .msg-mute-box input:focus,:root[data-theme="dark"] .msg-remark-box input:focus { outline:2px solid var(--primary); outline-offset:1px; }
              :root[data-theme="dark"] #msg-remark-delete { color:var(--danger) !important; border-color:var(--danger-line) !important; }
              :root[data-theme="dark"] .msg-mute-presets button { border-color:var(--line); background:var(--raised); color:var(--muted); }
              :root[data-theme="dark"] .msg-ctx { background:var(--raised); border-color:var(--line); box-shadow:0 6px 20px rgba(0,0,0,.35); }
              :root[data-theme="dark"] .msg-ctx-item { color:var(--ink); }
              :root[data-theme="dark"] .msg-ctx-item:hover { background:var(--primary-soft); color:var(--primary); }
              :root[data-theme="dark"] .msg-ctx-item.danger { color:var(--danger); }
              :root[data-theme="dark"] .msg-ctx-item.danger:hover { background:var(--danger-bg); color:var(--danger); }
              :root[data-theme="dark"] .msg-ctx-sep { background:var(--line); }
              :root[data-theme="dark"] .msg-multi-bar { background:var(--primary-soft); border-bottom-color:#596783; color:var(--primary); }
              :root[data-theme="dark"] .msg-row.multi-mode.selected .msg-bubble { outline-color:var(--primary); }
              :root[data-theme="dark"] .msg-multi-check { border-color:var(--primary); background:var(--raised); color:transparent; }
              :root[data-theme="dark"] .msg-row.multi-mode.selected .msg-multi-check { border-color:var(--accent-fill); background:var(--accent-fill); color:#fff; }
              :root[data-theme="dark"] .msg-list-resizer::before,:root[data-theme="dark"] .msg-composer-resizer::before { background:var(--primary); }
              :root[data-theme="dark"] .msg-list-resizer:hover::before,:root[data-theme="dark"] .msg-list-resizer:focus-visible::before,:root[data-theme="dark"] .msg-composer-resizer:hover::before,:root[data-theme="dark"] .msg-composer-resizer:focus-visible::before { background:var(--primary); }
              :root[data-theme="dark"] .msg-panel-toggle { border-color:var(--line); background:var(--raised); color:var(--muted); }
              :root[data-theme="dark"] .msg-panel-toggle:hover,:root[data-theme="dark"] .msg-panel-toggle:focus-visible,:root[data-theme="dark"] .msg-mobile-back:hover,:root[data-theme="dark"] .msg-mobile-back:focus-visible { border-color:var(--primary); background:var(--primary-soft); color:var(--primary); }
              :root[data-theme="dark"] .msg-mobile-back { color:var(--muted); }
              .msg-group-settings { position:absolute; inset:0; z-index:35; display:flex; justify-content:flex-end; overflow:hidden; border-radius:inherit; }
              .msg-group-settings[hidden] { display:none; }
              .msg-group-mask { position:absolute; inset:0; border:0; background:rgba(21,37,56,.18); cursor:default; }
              .msg-group-drawer { position:relative; display:flex; flex-direction:column; width:min(420px,100%); min-width:0; background:var(--panel); color:var(--ink); box-shadow:-10px 0 28px rgba(23,39,66,.1); animation:msg-group-slide .18s ease-out; }
              @keyframes msg-group-slide { from { transform:translateX(24px); opacity:.6; } to { transform:translateX(0); opacity:1; } }
              .msg-group-drawer-head { display:flex; align-items:center; gap:10px; padding:17px 18px 13px; border-bottom:1px solid var(--line); }
              .msg-group-drawer-head > div { flex:1; min-width:0; }
              .msg-group-drawer-head strong { display:block; font-size:15px; }
              .msg-group-drawer-head small { display:block; margin-top:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--muted); font-size:11px; }
              .msg-group-close { width:28px; height:28px; border:0; border-radius:6px; background:var(--raised); color:var(--muted); font-size:20px; cursor:pointer; }
              .msg-group-tabs { display:flex; gap:4px; padding:9px 14px 0; border-bottom:1px solid var(--line); }
              .msg-group-tabs button { flex:1; padding:10px 4px; border:0; border-bottom:2px solid transparent; background:none; color:var(--muted); font-size:12px; cursor:pointer; }
              .msg-group-tabs button.active { border-bottom-color:var(--primary); color:var(--primary); font-weight:650; }
              .msg-group-body { flex:1 1 0; min-height:0; overflow:auto; overscroll-behavior:contain; padding:16px; }
              .msg-group-pane[hidden],.msg-group-member-detail[hidden] { display:none; }
              .msg-group-summary { display:flex; align-items:center; gap:12px; padding:3px 0 16px; }
              .msg-group-summary .msg-chat-avatar { width:48px; height:48px; }
              .msg-group-summary strong { display:block; font-size:14px; overflow-wrap:anywhere; }
              .msg-group-summary small { display:block; margin-top:5px; color:var(--muted); font-size:11px; }
              .msg-group-field { display:block; margin-bottom:14px; font-size:12px; color:var(--muted); }
              .msg-group-field > input { display:block; width:100%; margin-top:7px; padding:9px 10px; box-sizing:border-box; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); font-family:inherit; font-size:12px; }
              .msg-group-field > input:focus { outline:2px solid var(--primary-soft); border-color:var(--primary); }
              .msg-group-toggle { display:flex; align-items:center; justify-content:space-between; gap:14px; margin-top:21px; padding-top:16px; border-top:1px solid var(--line); font-size:12px; }
              .msg-group-toggle small { display:block; margin-top:5px; color:var(--muted); line-height:1.5; }
              .msg-group-toggle input { width:34px; height:18px; accent-color:var(--primary); cursor:pointer; }
              .msg-group-status { margin:0 0 12px; padding:10px 11px; border-radius:7px; background:var(--primary-soft); color:var(--muted); font-size:11px; line-height:1.55; overflow-wrap:anywhere; }
              .msg-group-status:empty { display:none; }
              .msg-group-status.error { color:var(--danger); background:var(--danger-bg); }
              .msg-group-tools { display:flex; align-items:center; gap:8px; margin-bottom:12px; font-size:11px; color:var(--muted); }
              .msg-group-tools > span { flex:1; }
              .msg-group-select-all { display:inline-flex; align-items:center; gap:5px; color:var(--muted); cursor:pointer; }
              .msg-group-member { display:flex; align-items:center; gap:9px; padding:9px 0; border-bottom:1px solid var(--line); }
              .msg-group-member > input { width:15px; height:15px; flex:0 0 auto; accent-color:var(--primary); }
              .msg-group-member-open { flex:1; display:flex; align-items:center; gap:10px; min-width:0; padding:0; border:0; background:none; text-align:left; color:inherit; cursor:pointer; }
              .msg-group-member-open > div { flex:1; min-width:0; }
              .msg-group-member-open strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; font-weight:550; }
              .msg-group-member-open small { display:block; margin-top:4px; color:var(--muted); font-size:10px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
              .msg-group-role { padding:3px 5px; border-radius:4px; font-size:9px; background:#eef7ff; color:var(--primary); white-space:nowrap; }
              .msg-group-pagination { display:flex; align-items:center; justify-content:space-between; gap:8px; padding:15px 0; color:var(--muted); font-size:11px; }
              .msg-group-batch { position:sticky; bottom:-16px; padding:12px 0 16px; background:var(--panel); border-top:1px solid var(--line); }
              .msg-group-batch label { display:flex; align-items:center; gap:6px; margin-bottom:10px; color:var(--muted); font-size:11px; }
              .msg-group-batch > .msg-btn { width:100%; min-height:34px; }
              .msg-btn.danger { color:var(--danger); border-color:var(--danger-line); background:var(--panel); }
              .msg-btn:disabled,.msg-group-drawer button:disabled { cursor:not-allowed; opacity:.48; }
              .msg-group-member-detail { margin:0 0 15px; padding:12px; border:1px solid #d9e9f6; border-radius:9px; background:var(--raised); }
              .msg-group-detail-head { display:flex; align-items:center; gap:10px; margin-bottom:12px; }
              .msg-group-detail-head strong { flex:1; min-width:0; overflow-wrap:anywhere; font-size:13px; }
              .msg-group-detail-field { display:grid; grid-template-columns:58px minmax(0,1fr); gap:8px; margin:8px 0; font-size:11px; line-height:1.5; }
              .msg-group-detail-field span { color:var(--muted); }
              .msg-group-detail-field b { color:var(--muted); font-weight:450; overflow-wrap:anywhere; }
              .msg-group-blacklist-add { display:flex; gap:7px; margin-bottom:14px; }
              .msg-group-blacklist-add input { min-width:0; flex:1; padding:9px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:inherit; font-size:11px; }
              :root[data-theme="dark"] .msg-group-drawer,:root[data-theme="dark"] .msg-group-batch { background:var(--panel); color:var(--ink); }
              :root[data-theme="dark"] .msg-group-mask { background:rgba(5,10,17,.5); }
              :root[data-theme="dark"] .msg-group-drawer-head,:root[data-theme="dark"] .msg-group-tabs,:root[data-theme="dark"] .msg-group-toggle,:root[data-theme="dark"] .msg-group-batch,:root[data-theme="dark"] .msg-group-member { border-color:var(--line); }
              :root[data-theme="dark"] .msg-group-field > input,:root[data-theme="dark"] .msg-group-blacklist-add input { background:var(--input); border-color:var(--line); color:var(--ink); }
              :root[data-theme="dark"] .msg-group-field > input:focus,:root[data-theme="dark"] .msg-group-blacklist-add input:focus { border-color:var(--primary); outline-color:var(--primary-soft); }
              :root[data-theme="dark"] .msg-group-close { background:var(--raised); color:var(--muted); }
              :root[data-theme="dark"] .msg-group-status,:root[data-theme="dark"] .msg-group-member-detail { background:var(--raised); border-color:var(--line); color:var(--muted); }
              :root[data-theme="dark"] .msg-group-status.error { background:var(--danger-bg); color:var(--danger); }
              :root[data-theme="dark"] .msg-group-detail-field b,:root[data-theme="dark"] .msg-group-field,:root[data-theme="dark"] .msg-group-select-all { color:var(--muted); }
              :root[data-theme="dark"] .msg-group-drawer-head small,:root[data-theme="dark"] .msg-group-summary small,:root[data-theme="dark"] .msg-group-toggle small,:root[data-theme="dark"] .msg-group-tools,:root[data-theme="dark"] .msg-group-member-open small,:root[data-theme="dark"] .msg-group-pagination,:root[data-theme="dark"] .msg-group-detail-field span,:root[data-theme="dark"] .msg-group-batch label,:root[data-theme="dark"] .msg-group-mute-card small,:root[data-theme="dark"] .msg-group-mute-rule small,:root[data-theme="dark"] .msg-group-muted-member small,:root[data-theme="dark"] .msg-group-mute-rule.is-disabled { color:var(--soft); }
              :root[data-theme="dark"] .msg-group-tabs button { color:var(--muted); }
              :root[data-theme="dark"] .msg-group-tabs button.active { border-bottom-color:var(--primary); color:var(--primary); }
              :root[data-theme="dark"] .msg-group-role { background:var(--primary-soft); color:var(--primary); }
              :root[data-theme="dark"] .msg-group-toggle input,:root[data-theme="dark"] .msg-group-member > input { accent-color:var(--accent-fill); }
              :root[data-theme="dark"] .msg-btn.danger { color:var(--danger); border-color:var(--danger-line); background:var(--panel); }
              @media (max-width:640px) { .msg-group-drawer { width:100%; } .msg-group-body { padding:13px; } }
              @media (prefers-reduced-motion: reduce) {
                *, *::before, *::after { animation-duration:0.01ms !important; animation-iteration-count:1 !important; scroll-behavior:auto !important; transition-duration:0.01ms !important; }
              }


    /* 夜航工作台：轨道侧栏、分段仪表带与安静的消息工作区。 */
    body { font-family:"Microsoft YaHei UI","PingFang SC",system-ui,sans-serif; -webkit-font-smoothing:antialiased; }
    button,input,select,textarea { font:inherit; }
    button,a,input,select,textarea,[contenteditable] { -webkit-tap-highlight-color:transparent; }
    :focus-visible { outline:2px solid var(--primary); outline-offset:3px; }
    ::selection { background:var(--primary-soft); color:var(--ink); }
    * { scrollbar-width:thin; scrollbar-color:var(--line) transparent; }
    .shell { grid-template-columns:232px minmax(0,1fr); }
    .topbar { border-bottom:1px solid var(--line); padding-inline:25px; }
    .brand { gap:12px; }
    .brand-mark { width:34px; height:34px; border:0; border-radius:10px; background:var(--primary-soft); color:var(--primary); }
    .brand-mark svg { width:25px; height:25px; }
    .brand strong { font:600 19px/1.2 Bahnschrift,"Microsoft YaHei UI",sans-serif; letter-spacing:.2px; }
    .version-badge { padding:3px 7px; border:1px solid var(--line); border-radius:5px; background:var(--raised); font-variant-numeric:tabular-nums; font-size:10px; }
    .sidebar { padding:25px 15px 18px; background:var(--nav-bg); border-right:1px solid var(--nav-line); color:var(--nav-ink); gap:28px; }
    .profile { position:relative; padding:15px 8px 22px; gap:8px; border-bottom:1px solid var(--nav-line); }
    .profile::before { content:""; position:absolute; top:3px; left:50%; width:102px; height:102px; transform:translateX(-50%); border:1px solid var(--nav-line); border-radius:50%; pointer-events:none; }
    .profile strong { margin-top:8px; color:#e6f3ff; font-size:15px; }
    .bot-avatar { width:80px; height:80px; border:5px solid #15344c; background:#19465d; box-shadow:0 0 28px #57d6ff17; }
    .bot-avatar::before,.bot-avatar::after { display:none; }
    .avatar-face { position:absolute; inset:0; display:grid; place-items:center; color:#88e5ff; letter-spacing:0; }
    .avatar-face svg { width:65%; height:65%; }
    .avatar-inline .avatar-face { inset:0; }
    .nav-label { margin:0 13px 12px; color:#6e91ab; font-size:10px; font-weight:600; letter-spacing:.1em; }
    .nav { gap:5px; }
    .nav a { position:relative; min-height:44px; padding:11px 13px; border:1px solid transparent; border-radius:8px; color:var(--nav-ink); font-size:12px; transition:background .16s,color .16s,border-color .16s; }
    .nav a:hover { transform:none; background:#112d43; color:#e6f3ff; }
    .nav a.active,.nav a[aria-current="page"] { border-color:#2b556d; background:var(--nav-active); color:var(--nav-accent); }
    .nav a.active::before { content:""; position:absolute; left:-16px; width:3px; height:20px; border-radius:0 3px 3px 0; background:var(--nav-accent); box-shadow:0 0 15px #57d6ff66; }
    .nav-icon { display:grid; place-items:center; width:19px; color:inherit; }
    .nav-icon svg,.shortcut-icon svg { width:19px; height:19px; }
    .sidebar-foot { padding:15px 13px; border:1px solid var(--nav-line); border-radius:10px; background:#10283b; color:#7e9bb1; font-size:10px; line-height:1.9; }
    .sidebar-foot strong { color:#c1d6e8; font-size:12px; }
    .sidebar-foot .spark { float:right; color:var(--nav-accent); font-size:25px; }
    .content { width:min(1420px,calc(100% - 64px)); padding:35px 0 52px; }
    .page-heading { align-items:center; margin-bottom:25px; }
    .page-heading h1 { font-size:29px; font-weight:650; letter-spacing:-.5px; line-height:1.35; }
    .page-heading p { max-width:70ch; margin-top:8px; color:var(--muted); font-size:12px; }
    .updated-label { display:inline-flex; align-items:center; gap:7px; padding:7px 10px; border:1px solid var(--line); border-radius:6px; background:var(--panel); font-size:10px; font-variant-numeric:tabular-nums; }
    .updated-label::before { content:""; width:5px; height:5px; background:var(--mint-ink); border-radius:50%; }
    .summary-grid { gap:0; margin-top:16px; border:1px solid var(--line); border-radius:13px; background:var(--panel); overflow:hidden; box-shadow:var(--shadow); }
    .summary-card { min-height:173px; padding:23px 24px 20px; border:0; border-right:1px solid var(--line); border-radius:0; background:transparent; box-shadow:none; }
    .summary-card:last-child { border-right:0; }
    .summary-card > span { display:flex; align-items:center; gap:8px; font-size:11px; }
    .summary-card > span::before { content:""; width:5px; height:5px; border-radius:1px; background:var(--primary); }
    .summary-card:last-child > span::before { background:var(--peach-ink); }
    .summary-card > strong { margin-top:14px; font:600 26px/1.35 Bahnschrift,"Microsoft YaHei UI",sans-serif; }
    .summary-card > small { margin-top:3px; font-size:10px; }
    .summary-card .text-button { margin-top:17px; font-size:11px; }
    .summary-card:hover,.shortcut-card:hover,.runtime-item:hover { transform:none; }
    .console-card { padding:24px; border-radius:12px; box-shadow:var(--shadow); }
    .console-card h2 { font-size:15px; font-weight:650; }
    .card-subtitle { margin-top:6px; font-size:11px; line-height:1.8; }
    .page-grid { gap:18px; margin-top:22px; }
    .shortcut-grid { gap:0; }
    .shortcut-card { min-height:101px; padding:17px 12px; border:0; border-bottom:1px solid var(--line); border-radius:0; background:transparent; grid-template-columns:38px minmax(0,1fr); column-gap:12px; transition:background .16s; }
    .shortcut-card:nth-last-child(-n+2) { border-bottom:0; }
    .shortcut-card:nth-child(odd) { border-right:1px solid var(--line); }
    .shortcut-card:hover { background:var(--raised); border-color:var(--line); }
    .shortcut-icon { width:36px; height:36px; border:1px solid var(--line); border-radius:10px; background:var(--raised); }
    .shortcut-card strong { font-size:12px; }
    .shortcut-card small { font-size:10px; line-height:1.7; }
    .status-item { padding-block:14px; }
    .status-item strong { font-variant-numeric:tabular-nums; }
    .config-group { padding:20px; border-radius:10px; }
    .primary-button,.outline-button { min-height:40px; border-radius:7px; }
    .primary-button { background:var(--accent-fill); box-shadow:0 4px 12px #067ca718; color:#fff; }
    .primary-button:hover { background:var(--accent-hover); }
    .outline-button { border-color:var(--line); background:var(--raised); color:var(--primary); }
    .config-field input,.config-field select,.config-field textarea,.pan-directory input { background:var(--input); }
    .switch.on { background:var(--accent-fill); }
    .novel-master-panel,.novel-test-panel { border-radius:12px; }
    .novel-master-panel { border-color:var(--line); background:var(--panel); }
    .novel-test-panel { border-color:var(--line); background:var(--raised); }
    .novel-overline,.novel-panel-kicker,.novel-platform-overline { letter-spacing:0; font-size:11px; font-weight:600; }
    .novel-item { background:var(--panel); border-color:var(--line); border-radius:9px; }
    .novel-item:hover { transform:none; box-shadow:none; border-color:var(--primary); }
    .pan-tabs { gap:8px; border-bottom:0; padding-bottom:12px; }
    .pan-tab { min-width:162px; border:1px solid var(--line); border-radius:9px; background:var(--panel); }
    .pan-tab.active { border-color:var(--primary); background:var(--primary-soft); box-shadow:none; }
    .pan-object-card { border-radius:11px; }
    .pan-account-object { max-width:none; padding:17px; }
    .pan-account-object:hover,.qq-reader-account:hover { transform:none; border-color:var(--primary); }
    .pan-object-pane { border-radius:12px; }
    .qq-reader-modal,.msg-raw-box,.msg-remark-box,.msg-mute-box { border:1px solid var(--line); box-shadow:0 24px 85px #0005; }
    .toast { z-index:2000; max-width:min(440px,calc(100vw - 32px)); border:1px solid var(--line); background:var(--panel); color:var(--ink); }
    .msg-shell { border-color:var(--line); border-radius:12px; box-shadow:var(--shadow); }
    .msg-list-head { padding-top:13px; padding-bottom:11px; }
    .msg-search input { border-radius:7px; }
    .msg-search button { border-radius:7px; background:var(--accent-fill); }
    .msg-chat.active { box-shadow:inset 3px 0 var(--primary); }
    .msg-head { min-height:62px; padding-inline:20px; }
    .msg-body { padding:24px 24px 12px; }
    .msg-row { margin-bottom:19px; }
    .msg-bubble { border:1px solid var(--line); border-radius:3px 11px 11px 11px; padding:9px 13px; box-shadow:none; }
    .msg-row.self .msg-bubble { border-color:var(--accent-fill); background:var(--accent-fill); color:#fff; }
    .msg-composer { min-height:164px; border-top-color:var(--line); gap:6px; overflow:hidden; }
    .msg-composer[hidden] { display:none !important; }
    .msg-composer-topbar,.msg-toolbar,.msg-head { flex-shrink:0; }
    .msg-input-box { min-height:42px; resize:none; }
    .msg-editor { min-height:40px; }
    .msg-btn.primary { border-color:var(--accent-fill); background:var(--accent-fill); color:#fff; }
    .msg-btn.primary:hover { border-color:var(--accent-hover); background:var(--accent-hover); }
    :root[data-theme="dark"] .topbar { background:var(--panel); }
    :root[data-theme="dark"] .sidebar { background:var(--nav-bg); border-color:var(--nav-line); }
    :root[data-theme="dark"] .nav a { color:var(--nav-ink); }
    :root[data-theme="dark"] .nav a.active,:root[data-theme="dark"] .nav a[aria-current="page"] { color:var(--nav-accent); background:var(--nav-active); }
    :root[data-theme="dark"] .summary-card { background:transparent; box-shadow:none; }
    :root[data-theme="dark"] .summary-card:last-child > strong { color:var(--peach-ink); }
    :root[data-theme="dark"] .sidebar-foot { background:#10283b; border-color:var(--nav-line); }
    :root[data-theme="dark"] .bot-avatar { border-color:#15344c; background:#19465d; }
    :root[data-theme="dark"] .avatar-face { color:#88e5ff; }
    :root[data-theme="dark"] .novel-master-panel { background:var(--panel); border-color:var(--line); }
    :root[data-theme="dark"] .novel-test-panel { background:var(--raised); border-color:var(--line); }
    :root[data-theme="dark"] .chat-list-panel { background:var(--input); }
    :root[data-theme="dark"] .msg-chat-avatar,:root[data-theme="dark"] .msg-avatar { background:var(--primary-soft); color:var(--primary); }
    :root[data-theme="dark"] .msg-chat-avatar .avatar-letter,:root[data-theme="dark"] .msg-avatar .avatar-letter { color:var(--primary); }
    :root[data-theme="dark"] .msg-bubble { background:var(--panel); }
    @media (max-width:1050px) and (min-width:761px) {
      .shell { grid-template-columns:204px minmax(0,1fr); }
      .content { width:calc(100% - 40px); }
      .summary-card { border-bottom:1px solid var(--line); }
      .summary-card:nth-child(2) { border-right:0; }
      .summary-card:nth-last-child(-n+2) { border-bottom:0; }
      .page-grid { grid-template-columns:1fr; }
    }
    @media (max-width:760px) {
      .content { width:calc(100% - 28px); padding-top:23px; }
      .page-heading { margin-bottom:17px; }
      .page-heading h1 { font-size:24px; }
      .topbar { padding-inline:12px; }
      .brand strong { font-size:17px; }
      .sidebar { padding:7px 10px; gap:8px; }
      .profile { padding:0; border:0; }
      .profile::before { display:none; }
      .profile strong { margin:0; font-size:11px; }
      .bot-avatar { width:32px; height:32px; border-width:2px; }
      .nav a { min-height:33px; padding:6px 9px; font-size:11px; border-radius:6px; }
      .nav a.active::before { display:none; }
      .nav-icon,.nav-icon svg { width:15px; height:15px; }
      .summary-grid { grid-template-columns:repeat(2,minmax(0,1fr)); border-radius:10px; }
      .summary-card { min-height:153px; padding:17px; border-bottom:1px solid var(--line); }
      .summary-card:nth-child(2) { border-right:0; }
      .summary-card:nth-last-child(-n+2) { border-bottom:0; }
      .summary-card > strong { font-size:22px; }
      .console-card { padding:19px; }
      .shortcut-grid { grid-template-columns:1fr; }
      .shortcut-card { min-height:84px; padding:13px 4px; }
      .shortcut-card:nth-child(odd) { border-right:0; }
      .shortcut-card:nth-last-child(2) { border-bottom:1px solid var(--line); }
      .content:has(#page-messages:not([hidden])) { padding:0; }
      .msg-shell { height:calc(100dvh - 98px); min-height:0; border-radius:0; }
      body.msg-mobile-chat-view { height:100dvh; overflow:hidden; }
      body.msg-mobile-chat-view .main,body.msg-mobile-chat-view .content { height:100dvh; min-height:0; padding:0; overflow:hidden; }
      body.msg-mobile-chat-view .shell { height:100dvh; min-height:0; overflow:hidden; }
      .msg-composer { min-height:164px; max-height:52dvh; padding:7px 10px 9px; }
      .msg-input-box { min-height:38px; }
      .msg-composer-topbar,.msg-toolbar { min-height:27px; }
      .msg-editor { min-height:36px; }
      .msg-head { display:grid; grid-template-columns:30px minmax(0,1fr); min-height:54px; padding:9px 10px; gap:7px; }
      .msg-head > div:not(.msg-head-actions) { grid-column:2; min-width:0; }
      .msg-head-name,.msg-head-sub { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .msg-head-actions { grid-column:1 / -1; width:100%; min-width:0; margin-left:0; padding-bottom:3px; flex-wrap:nowrap; justify-content:flex-start; overflow-x:auto; overscroll-behavior-x:contain; scrollbar-width:thin; }
      .msg-head-actions > * { flex-shrink:0; }
      .msg-body { padding:16px 10px 8px; }
      .msg-row { margin-bottom:15px; }
      .pan-tab { min-width:146px; }
      .pan-account-object { padding:14px; }
      .toast { right:16px; bottom:16px; }
    }
    @media (max-width:360px) {
      .summary-card { padding:14px 12px; }
      .summary-card > strong { font-size:19px; }
      .brand strong { font-size:15px; }
      .profile .online { display:none; }
    }
    @media (prefers-reduced-motion:reduce) {
      *,*::before,*::after { animation:none !important; transition:none !important; scroll-behavior:auto !important; }
    }
    """
