"""馒头控制台的样式资源。"""

控制台样式 = """
    :root { color-scheme: light; --ink:#24243a; --muted:#7d8096; --soft:#a8abc0; --line:#e8e9f2; --bg:#f7f8fd; --panel:#fff; --primary:#6b63f5; --primary-dark:#574eea; --primary-soft:#f0efff; --mint:#e9fbf3; --mint-ink:#319e6b; --peach:#fff3ed; --peach-ink:#d77755; --yellow:#fff9e5; --yellow-ink:#bd8a23; --pink:#fff0f7; --pink-ink:#c66791; --shadow:0 10px 30px rgba(60,57,112,.06); }
    * { box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.55 Inter,"PingFang SC","Microsoft YaHei",ui-sans-serif,system-ui,sans-serif; overflow-x:hidden; }
    button,input { font:inherit; }
    button { cursor:pointer; }
    .shell { min-height:100vh; display:grid; grid-template-columns:252px minmax(0,1fr); grid-template-rows:64px minmax(0,1fr); grid-template-areas:"top top" "side main"; }
    .topbar { grid-area:top; display:flex; align-items:center; justify-content:space-between; gap:20px; padding:0 30px; background:#fff; border-bottom:1px solid var(--line); }
    .brand { display:flex; align-items:center; gap:10px; min-width:0; }
    .brand-mark { width:34px; height:34px; flex:0 0 34px; display:grid; place-items:center; border-radius:11px; background:var(--primary-soft); color:var(--primary); font-size:16px; font-weight:800; }
    .brand strong { font-size:16px; letter-spacing:.1px; }
    .version-badge { display:inline-flex; margin-left:7px; padding:3px 8px; border-radius:999px; background:#f3f3f8; color:var(--muted); font-size:11px; font-weight:650; }
    .top-actions { display:flex; align-items:center; gap:16px; }
    .theme-control { display:inline-flex; align-items:center; gap:6px; min-height:32px; padding:3px 7px 3px 9px; border:1px solid transparent; border-radius:8px; color:var(--muted); font-size:11px; font-weight:650; transition:background .18s ease,border-color .18s ease; }
    .theme-control:hover,.theme-control:focus-within { border-color:#e5e3f7; background:#fbfaff; }
    .theme-control-icon { color:var(--primary); font-size:15px; line-height:1; }
    .theme-control select { min-height:26px; padding:2px 20px 2px 3px; border:0; border-radius:5px; background:transparent; color:var(--ink); font-size:11px; font-weight:650; cursor:pointer; outline:none; }
    .theme-control select option { background:var(--panel); color:var(--ink); }
    .status-dot { display:inline-flex; align-items:center; gap:7px; color:var(--mint-ink); font-size:12px; font-weight:650; }
    .status-dot::before { content:""; width:7px; height:7px; border-radius:50%; background:#4dbb82; box-shadow:0 0 0 4px var(--mint); }
    .admin-menu { position:relative; }
    .admin-chip { display:inline-flex; align-items:center; gap:8px; min-height:36px; padding:4px 8px 4px 5px; border:1px solid transparent; border-radius:9px; background:transparent; color:var(--ink); font-size:13px; font-weight:650; transition:background .18s ease,border-color .18s ease; }
    .admin-chip:hover,.admin-chip[aria-expanded="true"] { border-color:#e5e3f7; background:#fbfaff; }
    .admin-avatar { width:28px; height:28px; display:grid; place-items:center; border-radius:50%; background:#f0efff; color:var(--primary); font-size:12px; font-weight:800; }
    #admin-name { max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .admin-chevron { color:var(--soft); font-size:13px; }
    .admin-popover { position:absolute; z-index:5; top:calc(100% + 8px); right:0; width:220px; padding:13px 14px; border:1px solid var(--line); border-radius:10px; background:#fff; box-shadow:0 12px 30px rgba(60,57,112,.12); }
    .admin-popover[hidden] { display:none; }
    .admin-popover strong { display:block; font-size:13px; }
    .admin-popover small { display:block; margin-top:5px; color:var(--muted); font-size:11px; line-height:1.45; }
    .popover-logout { display:block; width:100%; margin-top:10px; padding:7px 10px; border:1px solid var(--line); border-radius:7px; background:#fff; color:var(--danger,#d64545); font-size:12px; cursor:pointer; text-align:center; }
    .popover-logout:hover { background:#fdf2f2; border-color:#e8b8b8; }
    .sidebar { grid-area:side; min-width:0; background:#fff; border-right:1px solid var(--line); padding:24px 14px 18px; display:flex; flex-direction:column; gap:24px; }
    .profile { display:grid; justify-items:center; gap:7px; padding:4px 0 8px; }
    .bot-avatar { position:relative; width:72px; height:72px; overflow:hidden; border:5px solid #f3f2ff; border-radius:50%; background:#e9eaff; box-shadow:0 5px 14px rgba(92,87,210,.12); }
    .bot-avatar::before { content:""; position:absolute; width:62px; height:58px; left:0; top:5px; border-radius:50% 50% 42% 42%; background:#a2a5f7; }
    .bot-avatar::after { content:"✦"; position:absolute; right:7px; top:4px; color:#fff; font-size:13px; }
    .avatar-face { position:absolute; left:16px; top:27px; z-index:1; color:#4f50a8; font-size:23px; letter-spacing:5px; }
    .bot-avatar.has-image::before,.bot-avatar.has-image::after,.bot-avatar.has-image .avatar-face { display:none; }
    .bot-avatar-image { position:absolute; inset:0; z-index:1; width:100%; height:100%; border-radius:50%; object-fit:cover; display:block; }
    .profile strong { font-size:14px; }
    .online { display:inline-flex; align-items:center; gap:5px; color:var(--mint-ink); font-size:12px; }
    .online::before { content:""; width:6px; height:6px; border-radius:50%; background:#4dbb82; }
    .nav-label { margin:0 10px 8px; color:#afb1c1; font-size:10px; font-weight:800; letter-spacing:1px; text-transform:uppercase; }
    .nav { display:grid; gap:5px; }
    .nav a { display:flex; align-items:center; gap:11px; padding:11px 12px; border-radius:9px; color:#55586d; text-decoration:none; transition:background .18s ease,color .18s ease,transform .18s ease,box-shadow .18s ease; }
    .nav a:hover { transform:translateX(3px); }
    .nav a:hover,.nav a.active,.nav a[aria-current="true"] { background:var(--primary-soft); color:var(--primary-dark); }
    .nav-icon { width:18px; color:#777a90; text-align:center; font-size:16px; }
    .nav a.active .nav-icon,.nav a[aria-current="true"] .nav-icon { color:var(--primary); }
    .nav a:focus-visible,.refresh:focus-visible,.switch:focus-visible,.pan-select:focus-visible { outline:3px solid #c9c6ff; outline-offset:2px; }
    .sidebar-foot { margin-top:auto; padding:14px 13px; border:1px solid #ebeaf4; border-radius:11px; background:#fbfbff; color:var(--muted); font-size:11px; }
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
    .metric:nth-child(1) { background:#fbfaff; }
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
    .global-bar { display:flex; align-items:center; justify-content:space-between; gap:18px; padding:16px 19px; border-bottom:1px solid var(--line); background:#fcfbff; }
    .global-actions { display:flex; align-items:center; gap:18px; flex:0 0 auto; }
    .test-mode { display:flex; align-items:center; gap:8px; color:var(--muted); font-size:12px; white-space:nowrap; }
    .global-copy strong { display:block; font-size:14px; }
    .global-copy span { display:block; margin-top:2px; color:var(--muted); font-size:12px; }
    .switch { position:relative; width:42px; height:24px; flex:0 0 auto; border:0; border-radius:999px; background:#d7d8e4; transition:background .18s ease; }
    .switch span { position:absolute; top:3px; left:3px; width:18px; height:18px; border-radius:50%; background:#fff; box-shadow:0 1px 3px #0002; transition:transform .18s ease; }
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
    .pan-card.active { border-color:#c4c0ff; box-shadow:0 0 0 2px #eeecff inset, var(--shadow); }
      .pan-top { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; }
      .pan-top-actions { display:flex; align-items:flex-start; justify-content:flex-end; gap:8px; }
      .pan-enable { display:flex; align-items:center; gap:6px; color:var(--muted); font-size:10px; white-space:nowrap; }
      .pan-enable-switch { transform:scale(.82); transform-origin:right top; }
      .pan-card.is-disabled { opacity:.78; }
    .pan-title { display:flex; align-items:center; gap:9px; }
    .pan-logo { width:31px; height:31px; display:grid; place-items:center; border-radius:9px; background:var(--primary-soft); color:var(--primary); font-weight:800; }
    .pan-title strong { font-size:14px; }
    .tag { display:inline-flex; padding:3px 7px; border-radius:999px; font-size:10px; font-weight:700; }
    .tag.active { background:var(--primary-soft); color:var(--primary-dark); }
    .tag.ok { background:var(--mint); color:var(--mint-ink); }
    .tag.off { background:#f2f4f7; color:#667085; }
    .pan-meta { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:20px 0 14px; }
    .pan-meta span { display:block; color:var(--muted); font-size:11px; }
    .pan-meta strong { display:block; margin-top:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
    .account-list { display:grid; gap:6px; margin:0 0 14px; }
    .account-row { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 9px; border:1px solid #eef0f3; border-radius:6px; background:#fbfcfe; color:var(--muted); font-size:11px; }
    .account-row strong { color:var(--ink); font-size:12px; font-weight:650; }
    .account-row span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pan-select { width:100%; min-height:40px; border:1px solid var(--line); border-radius:8px; background:#fff; color:var(--ink); padding:8px 10px; }
    .pan-select:disabled { color:#98a2b3; cursor:not-allowed; }
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
    @media (max-width:1050px) { .metrics { grid-template-columns:repeat(2,1fr); } .runtime-grid { grid-template-columns:repeat(3,1fr); } .config-list { grid-template-columns:repeat(2,1fr); } .config-item { border-right:1px solid var(--line); border-bottom:1px solid var(--line); } .config-item:nth-child(2n) { border-right:0; } .config-item:nth-last-child(-n+2) { border-bottom:0; } }
     @media (max-width:760px) { .shell { display:block; } .topbar { min-height:62px; padding:12px 15px; } .brand strong { font-size:14px; } .top-actions { gap:8px; } .admin-chip { font-size:12px; } .status-dot { display:none; } .sidebar { padding:10px 12px 8px; border-right:0; border-bottom:1px solid var(--line); gap:10px; } .profile { display:flex; align-items:center; justify-content:flex-start; gap:9px; padding:0 2px; } .bot-avatar { width:38px; height:38px; border-width:3px; } .bot-avatar::before { width:34px; height:32px; top:2px; } .avatar-face { left:8px; top:12px; font-size:12px; letter-spacing:2px; } .bot-avatar::after { right:2px; top:1px; font-size:8px; } .profile strong { font-size:13px; } .online { margin-left:-3px; } .nav-label,.sidebar-foot { display:none; } .nav { display:flex; gap:4px; overflow-x:auto; scrollbar-width:none; } .nav::-webkit-scrollbar { display:none; } .nav a { flex:0 0 auto; padding:8px 10px; } .content { width:calc(100% - 28px); padding:23px 0 40px; } .page-heading h1 { font-size:21px; } .page-heading p { font-size:12px; } .primary-button { min-height:34px; padding:0 11px; } .metrics,.pan-grid { grid-template-columns:1fr; } .novel-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .novel-item:nth-child(3n) { border-right:1px solid var(--line); } .novel-item:nth-child(2n) { border-right:0; } .novel-item:nth-last-child(-n+3),.novel-item:last-child,.novel-item:nth-last-child(2) { border-bottom:1px solid var(--line); } .global-bar { align-items:flex-start; } .global-actions { gap:10px; } .test-mode span { max-width:68px; white-space:normal; line-height:1.2; } .runtime-grid { grid-template-columns:repeat(2,1fr); } .config-list { grid-template-columns:1fr; } .config-item,.config-item:nth-child(2n) { padding:13px; border-right:0; border-bottom:1px solid var(--line); } .config-item:last-child { border-bottom:0; } }
     /* Screenshot-inspired configuration workspace. The data/API contract stays unchanged. */
     .shell { grid-template-columns:248px minmax(0,1fr); grid-template-rows:62px minmax(0,1fr); }
     .topbar { padding:0 30px; }
     .brand-mark { width:36px; height:36px; border-radius:50%; background:#e9e9ff; color:#5d58d8; border:3px solid #f5f4ff; font-size:13px; }
     .brand strong { font-size:17px; }
     .sidebar { padding:28px 18px 18px; gap:25px; }
     .profile { gap:8px; padding-bottom:13px; }
     .bot-avatar { width:76px; height:76px; }
     .nav-label { margin:0 12px 8px; font-size:11px; letter-spacing:0; text-transform:none; color:#a0a2b5; }
     .nav { gap:4px; }
     .nav a { min-height:40px; padding:10px 12px; border-radius:8px; font-size:13px; }
     .nav-icon { width:19px; font-size:15px; }
     .sidebar-foot { border-radius:8px; background:#f5f6fb; padding:15px 13px; line-height:1.65; }
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
     .console-card { margin:0; padding:21px 21px 20px; background:#fff; border:1px solid var(--line); border-radius:8px; box-shadow:0 5px 18px rgba(55,59,103,.045); scroll-margin-top:80px; }
     .console-card h2 { margin:0; font-size:15px; }
     .card-subtitle { margin:4px 0 18px; color:var(--muted); font-size:12px; }
     .profile-fields { display:grid; gap:0; }
     .profile-field { display:grid; grid-template-columns:112px minmax(0,1fr); align-items:center; gap:16px; min-height:58px; border-bottom:1px solid #f0f1f5; }
     .profile-field:last-child { border-bottom:0; }
     .profile-field > span { color:#55586d; font-size:13px; }
     .readonly-value { min-height:38px; display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 11px; border:1px solid #e4e6ee; border-radius:7px; color:var(--ink); background:#fff; }
     .readonly-value small { color:#a1a4b4; font-size:11px; }
     .avatar-inline { display:flex; align-items:center; gap:10px; }
     .avatar-inline .bot-avatar { width:43px; height:43px; border-width:3px; }
     .avatar-inline .bot-avatar::before { width:37px; height:35px; top:3px; }
     .avatar-inline .avatar-face { left:9px; top:14px; font-size:13px; letter-spacing:2px; }
     .avatar-inline .bot-avatar::after { right:3px; top:1px; font-size:9px; }
     .avatar-inline small { color:var(--muted); font-size:11px; }
     .state-line { display:flex; align-items:center; gap:10px; }
     .state-line .online { font-size:12px; }
     .connection-fields { display:grid; gap:12px; }
     .connection-row { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:12px 0; border-bottom:1px solid #f0f1f5; }
     .connection-row:last-child { border-bottom:0; padding-bottom:0; }
     .connection-row:first-child { padding-top:0; }
     .connection-row > span { color:#55586d; font-size:12px; }
     .connection-row strong { max-width:66%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--ink); font-size:12px; font-weight:600; text-align:right; }
     .module-card { padding:21px 0 0; overflow:hidden; }
     .module-card h2,.module-card .card-subtitle { margin-left:21px; margin-right:21px; }
     .module-card .global-bar { padding:14px 21px; border-top:1px solid #f0f1f5; background:#fcfbff; }
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
     .status-item { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:9px 0; border-bottom:1px solid #f0f1f5; font-size:12px; }
     .status-item:last-child { border-bottom:0; }
     .status-item span { color:#65687b; }
     .status-item strong { color:var(--ink); font-weight:600; text-align:right; }
     .status-item strong.good { color:var(--mint-ink); }
     .test-card { padding-bottom:17px; }
     .test-bubble { display:flex; align-items:flex-start; gap:9px; margin-top:14px; }
     .test-mini-avatar { width:28px; height:28px; flex:0 0 auto; display:grid; place-items:center; border-radius:50%; background:#e9e9ff; color:#5c58d8; font-size:11px; font-weight:800; }
     .test-bubble p { margin:0; padding:9px 11px; border-radius:5px 10px 10px 10px; background:#f0f1f7; color:#65687b; font-size:11px; line-height:1.55; }
     .test-hint { margin:13px 0 0; color:#a0a2b5; font-size:11px; }
     .pan-section { margin-top:16px; }
     .pan-section .section-head { margin:0 0 10px; }
     .pan-tabs { display:flex; gap:8px; margin:0 24px 16px; padding:4px; border:1px solid #e8e8f4; border-radius:9px; background:#fafaff; }
     .pan-tab { flex:1 1 0; min-width:0; min-height:38px; padding:0 14px; border:0; border-radius:7px; background:transparent; color:#777992; font-size:12px; font-weight:700; white-space:nowrap; transition:color .18s ease,background .18s ease,box-shadow .18s ease; }
     .pan-tab:hover { color:var(--primary-dark); background:#f2f1ff; }
     .pan-tab.active { color:var(--primary-dark); background:#fff; box-shadow:0 2px 8px rgba(72,68,146,.1); }
     .pan-tab:focus-visible { outline:2px solid #aaa0e7; outline-offset:2px; }
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
     @media (max-width:760px) { .pan-console { padding-top:18px; } .pan-console > h2,.pan-console > .card-subtitle,.pan-console .pan-note { margin-left:17px; margin-right:17px; } .pan-console .pan-tabs { margin-left:17px; margin-right:17px; gap:6px; overflow-x:auto; scrollbar-width:none; } .pan-console .pan-tabs::-webkit-scrollbar { display:none; } .pan-console .pan-tab { flex:0 0 auto; min-width:92px; padding:0 12px; } .pan-console .pan-grid { padding:0 17px; } }
     @media (max-width:760px) { .content { width:calc(100% - 28px); padding:23px 0 40px; } .workspace-grid { grid-template-columns:1fr; } .workspace-right { order:-1; } .module-card .novel-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .module-card .novel-item { border-right:1px solid var(--line); } .module-card .novel-item:nth-child(2n) { border-right:0; } .module-card .novel-item:nth-last-child(-n+2) { border-bottom:0; } .profile-field { grid-template-columns:92px minmax(0,1fr); gap:10px; } .connection-row strong { max-width:58%; } .config-list { grid-template-columns:1fr; } .config-item,.config-item:nth-child(2n) { border-right:0; border-bottom:1px solid var(--line); } .config-item:last-child { border-bottom:0; } }
     .page-view[hidden] { display:none !important; }
     .page-view { min-width:0; scroll-margin-top:82px; }
     .heading-actions { display:flex; align-items:center; gap:12px; }
     .updated-label { color:var(--muted); font-size:11px; white-space:nowrap; }
     .summary-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:13px; margin-top:18px; }
     .summary-card { min-height:168px; display:flex; flex-direction:column; align-items:flex-start; padding:17px 18px; background:#fff; border:1px solid var(--line); border-radius:8px; box-shadow:0 5px 18px rgba(55,59,103,.045); }
     .summary-card > span { color:var(--muted); font-size:12px; }
     .summary-card > strong { margin-top:12px; color:var(--ink); font-size:21px; }
     .summary-card > small { min-height:18px; margin-top:4px; color:var(--muted); font-size:11px; }
     .text-button { display:block; margin-top:auto; padding:0; color:var(--primary); font-size:12px; font-weight:700; text-align:left; }
     .text-button:hover { color:var(--primary-dark); }
     .page-grid { display:grid; grid-template-columns:minmax(0,1.55fr) minmax(280px,.9fr); gap:16px; margin-top:16px; }
     .page-grid .console-card { min-width:0; }
     .page-view-head { margin-top:18px; margin-bottom:0; }
     .shortcut-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
     .shortcut-card { min-height:94px; display:grid; grid-template-columns:30px minmax(0,1fr); grid-template-rows:auto auto; column-gap:10px; align-items:center; padding:13px; border:1px solid #e8e9f2; border-radius:7px; background:#fff; color:var(--ink); text-align:left; }
     .shortcut-card:hover { border-color:#c9c6ff; background:#fbfaff; }
     .shortcut-icon { grid-row:1 / span 2; width:30px; height:30px; display:grid; place-items:center; border-radius:8px; background:var(--primary-soft); color:var(--primary); font-size:14px; }
     .shortcut-card strong { font-size:12px; }
     .shortcut-card small { color:var(--muted); font-size:10px; line-height:1.45; }
     .compact-status { margin-top:8px; }
     .outline-button { min-height:36px; padding:0 16px; border:1px solid #c9c6ff; border-radius:7px; background:#fff; color:var(--primary-dark); font-size:12px; font-weight:700; }
     .outline-button:hover { background:var(--primary-soft); }
     .standalone-card { margin-top:18px; }
     .standalone-card > h2 { font-size:18px; }
     .module-heading { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:18px 0 10px; }
     .module-heading h3 { margin:0; font-size:13px; }
     .module-heading span { color:var(--muted); font-size:11px; }
     .pan-note { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:16px 0; padding:13px 15px; border:1px solid #e9e8f7; border-radius:7px; background:#fbfaff; }
     .pan-note span { color:var(--muted); font-size:12px; }
     .pan-note strong { color:var(--primary-dark); font-size:13px; }
     .runtime-page-grid { display:grid !important; grid-template-columns:repeat(5,minmax(0,1fr)); margin-top:18px; }
     .runtime-detail { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:16px; }
     .runtime-detail .status-item { padding:13px; border:1px solid var(--line); border-radius:7px; background:#fbfcff; }
     .safe-list,.settings-list { display:grid; gap:0; }
     .safe-list > div,.settings-row { display:flex; align-items:center; justify-content:space-between; gap:16px; min-height:50px; border-bottom:1px solid #f0f1f5; font-size:12px; }
     .safe-list > div:last-child,.settings-row:last-child { border-bottom:0; }
     .safe-list span,.settings-row span { color:#65687b; }
     .safe-list strong,.settings-row strong { color:var(--ink); font-weight:600; text-align:right; }
     .settings-row strong { max-width:65%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
     .config-editor { display:grid; gap:18px; }
     .config-group { padding:16px; border:1px solid #eef0f5; border-radius:8px; background:#fcfcff; }
     .config-group h3 { margin:0 0 13px; font-size:13px; }
     .config-fields { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:13px 15px; }
     .config-field { display:grid; gap:6px; min-width:0; }
     .config-field.full { grid-column:1 / -1; }
     .config-field label { color:#65687b; font-size:11px; font-weight:700; }
     .config-field input,.config-field textarea,.config-field select,.account-add input,.group-account input { width:100%; min-height:39px; padding:8px 10px; border:1px solid #e1e3ec; border-radius:7px; background:#fff; color:var(--ink); outline:none; }
     .config-field textarea { min-height:74px; resize:vertical; }
     .config-field input:focus,.config-field textarea:focus,.config-field select:focus,.account-add input:focus,.group-account input:focus { border-color:#aaa0e7; box-shadow:0 0 0 3px #efedff; }
     .config-field small,.secret-hint,.config-message,.qq-auth-message { color:var(--muted); font-size:10px; line-height:1.55; }
     .config-actions { display:flex; align-items:center; gap:12px; }
     .config-actions .primary-button { min-height:38px; }
     .config-message.ok,.qq-auth-message.ok { color:var(--mint-ink); }
     .config-message.error,.qq-auth-message.error { color:#c06478; }
     .account-actions { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:12px; }
     .account-add { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:7px; margin-top:13px; }
     .account-add .outline-button,.group-account .outline-button { min-height:39px; padding:0 11px; }
     .account-row { min-width:0; }
     .account-row button { flex:0 0 auto; border:0; background:transparent; color:#c06478; font-size:11px; }
     .account-row button:hover { color:#a94761; }
     .pan-directory { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:7px; margin:0 0 12px; }
     .pan-directory input { min-width:0; min-height:36px; padding:7px 9px; border:1px solid #e1e3ec; border-radius:7px; background:#fff; color:var(--ink); outline:none; }
     .pan-directory input:focus { border-color:#aaa0e7; box-shadow:0 0 0 3px #efedff; }
     .pan-directory .outline-button { min-height:36px; padding:0 10px; }
     .pan-security-note { margin:0 0 12px; padding:8px 9px; border-radius:6px; background:#fafaff; color:var(--muted); font-size:10px; line-height:1.5; }
     .group-account { display:grid; grid-template-columns:minmax(0,1fr) 74px auto; gap:7px; margin-top:9px; }
     .group-account input { min-width:0; }
     .group-account select { min-height:39px; border:1px solid #e1e3ec; border-radius:7px; background:#fff; color:var(--ink); }
     .qq-auth-form { display:grid; gap:11px; max-width:500px; }
     .qq-auth-row { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
     .qq-auth-row input { min-height:39px; padding:8px 10px; border:1px solid #e1e3ec; border-radius:7px; background:#fff; color:var(--ink); }
     .qq-auth-actions { display:flex; align-items:center; gap:9px; }
     .settings-hint { margin-top:15px; padding:12px 13px; border-radius:7px; background:#f7f7fd; color:var(--muted); font-size:11px; line-height:1.6; }
     .help-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; margin-top:16px; }
     .help-card h3 { margin:0; font-size:14px; }
     .help-card > p { margin:4px 0 15px; color:var(--muted); font-size:11px; }
     .command-list { display:flex; flex-wrap:wrap; gap:7px; }
     .command-list span { display:inline-flex; min-height:28px; align-items:center; padding:0 9px; border:1px solid #e8e8f1; border-radius:6px; background:#fbfbfe; color:#55586d; font-size:11px; }
     @media (max-width:1050px) { .summary-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .runtime-page-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
      @keyframes page-enter { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
      @keyframes card-enter { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
      @keyframes switch-feedback { 0% { transform:scale(1); } 45% { transform:scale(1.08); } 100% { transform:scale(1); } }
      .page-view:not([hidden]) { animation:page-enter .32s cubic-bezier(.22,.8,.35,1) both; }
      .page-view:not([hidden]) .console-card,.page-view:not([hidden]) .summary-card,.page-view:not([hidden]) .shortcut-card,.page-view:not([hidden]) .pan-card,.page-view:not([hidden]) .runtime-item { animation:card-enter .34s cubic-bezier(.22,.8,.35,1) both; }
      .page-view:not([hidden]) .console-card:nth-child(2),.page-view:not([hidden]) .summary-card:nth-child(2),.page-view:not([hidden]) .shortcut-card:nth-child(2),.page-view:not([hidden]) .pan-card:nth-child(2),.page-view:not([hidden]) .runtime-item:nth-child(2) { animation-delay:.045s; }
      .page-view:not([hidden]) .console-card:nth-child(3),.page-view:not([hidden]) .summary-card:nth-child(3),.page-view:not([hidden]) .shortcut-card:nth-child(3),.page-view:not([hidden]) .pan-card:nth-child(3),.page-view:not([hidden]) .runtime-item:nth-child(3) { animation-delay:.09s; }
      .page-view:not([hidden]) .console-card:nth-child(4),.page-view:not([hidden]) .summary-card:nth-child(4),.page-view:not([hidden]) .shortcut-card:nth-child(4),.page-view:not([hidden]) .pan-card:nth-child(4),.page-view:not([hidden]) .runtime-item:nth-child(4) { animation-delay:.135s; }
      .summary-card,.shortcut-card,.pan-card,.runtime-item { transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease; }
      .summary-card:hover,.shortcut-card:hover,.pan-card:hover,.runtime-item:hover { transform:translateY(-2px); }
      .shortcut-card { cursor:default; }
      .switch:active { animation:switch-feedback .22s ease both; }
     /* Novel controls use an unframed workspace with compact, real controls. */
     .novel-console { margin-top:18px; padding:4px 0 0; }
     .novel-console-head { display:flex; align-items:flex-start; justify-content:space-between; gap:22px; margin-bottom:20px; }
     .novel-console-head h2 { margin:4px 0 0; font-size:23px; letter-spacing:0; }
     .novel-console-head .card-subtitle { margin:7px 0 0; max-width:520px; }
     .novel-overline,.novel-panel-kicker,.novel-platform-overline { color:#9295aa; font-size:10px; font-weight:800; letter-spacing:1.3px; }
     .novel-state-pill { display:inline-flex; align-items:center; gap:8px; min-height:34px; padding:0 12px; border:1px solid #dbe8df; border-radius:999px; background:#f4fbf7; color:#318260; white-space:nowrap; }
     .novel-state-pill.is-off { border-color:#e3e4eb; background:#fafafd; color:#838697; }
     .novel-state-dot { width:7px; height:7px; border-radius:50%; background:#4eb781; box-shadow:0 0 0 4px #e3f6eb; }
     .novel-state-pill.is-off .novel-state-dot { background:#a7a9b6; box-shadow:0 0 0 4px #eff0f4; }
     .novel-state-pill strong { font-size:11px; font-weight:750; }
     .novel-control-grid { display:grid; grid-template-columns:minmax(0,1.42fr) minmax(280px,.92fr); gap:12px; }
     .novel-master-panel,.novel-test-panel { min-height:178px; padding:20px; border:1px solid var(--line); border-radius:10px; background:#fff; box-shadow:0 5px 18px rgba(55,59,103,.045); }
     .novel-master-panel { border-color:#dedcff; background:#fbfaff; }
     .novel-test-panel { border-color:#f0ded4; background:#fffaf7; }
     .novel-panel-kicker { display:flex; align-items:center; gap:8px; color:#716cbf; letter-spacing:.7px; }
     .novel-test-panel .novel-panel-kicker { color:#bf7961; }
     .novel-panel-icon { width:25px; height:25px; display:grid; place-items:center; border-radius:7px; background:#ecebff; color:#605bd2; font-size:12px; letter-spacing:0; }
     .novel-test-panel .novel-panel-icon { background:#ffebe2; color:#c5755b; }
     .novel-master-copy h3,.novel-test-panel h3 { margin:19px 0 4px; font-size:17px; }
     .novel-master-copy p,.novel-test-panel p { max-width:410px; margin:0; color:#777a8e; font-size:12px; line-height:1.65; }
     .novel-master-actions,.novel-test-actions { display:flex; align-items:flex-end; justify-content:space-between; gap:15px; margin-top:18px; }
     .novel-master-state { display:grid; gap:2px; }
     .novel-master-state strong { color:var(--ink); font-size:12px; }
     .novel-master-state span,.novel-test-note { color:#9698aa; font-size:11px; }
     .novel-console .novel-master-panel .switch { width:50px; height:28px; }
     .novel-console .novel-master-panel .switch span { width:22px; height:22px; }
     .novel-console .novel-master-panel .switch.on span { transform:translateX(22px); }
     .novel-test-actions { align-items:center; margin-top:20px; }
     .novel-test-actions .switch { transform:scale(.95); transform-origin:right center; }
     .novel-platform-head { display:flex; align-items:flex-end; justify-content:space-between; gap:18px; margin:29px 0 12px; }
     .novel-platform-head h3 { margin:4px 0 0; font-size:15px; }
     .novel-platform-count { color:#76798d; font-size:11px; }
     .novel-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
     .novel-item { display:flex; align-items:center; justify-content:space-between; gap:14px; min-height:78px; padding:14px 16px; border:1px solid #e8e9f1; border-radius:9px; background:#fff; box-shadow:none; transition:border-color .2s ease,background .2s ease,transform .2s ease,box-shadow .2s ease; }
     .novel-item:hover { border-color:#cfcdf3; background:#fdfdff; transform:translateY(-2px); box-shadow:0 7px 18px rgba(55,59,103,.06); }
     .novel-item.is-enabled { border-color:#d8e9df; }
     .novel-item.is-disabled { background:#fcfcfd; }
     .novel-item-main { display:flex; align-items:center; gap:11px; min-width:0; }
     .novel-badge { width:34px; height:34px; flex:0 0 auto; display:grid; place-items:center; border-radius:10px; background:#efeeff; color:#625dd4; font-size:12px; font-weight:800; }
     .novel-item:nth-child(3n+2) .novel-badge { background:#e8f8ef; color:#35936a; }
     .novel-item:nth-child(3n) .novel-badge { background:#fff0e9; color:#ca7b5f; }
     .novel-item-copy { min-width:0; }
     .novel-item-title { display:flex; align-items:center; gap:8px; min-width:0; }
     .novel-item-title strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
     .novel-item-copy small { display:block; margin-top:4px; color:#999bab; font-size:10px; }
     .novel-item-status { flex:0 0 auto; color:#9a9cad; font-size:10px; }
     .novel-item.is-enabled .novel-item-status { color:#35936a; }
     .novel-item .switch { transform:scale(.9); transform-origin:right center; }
     .novel-item .switch:focus-visible,.novel-master-panel .switch:focus-visible,.novel-test-panel .switch:focus-visible { outline:3px solid #c9c6ff; outline-offset:3px; }
     @media (max-width:900px) { .novel-control-grid { grid-template-columns:1fr; } }
     @media (max-width:760px) { .novel-console { margin-top:15px; padding-top:0; } .novel-console-head { display:block; } .novel-state-pill { margin-top:14px; } .novel-master-panel,.novel-test-panel { min-height:0; padding:17px; } .novel-master-copy h3,.novel-test-panel h3 { margin-top:15px; } .novel-platform-head { align-items:flex-start; margin-top:24px; } .novel-platform-head { display:block; } .novel-platform-count { display:block; margin-top:6px; } .novel-grid { grid-template-columns:1fr; } .novel-item { min-height:72px; padding:13px 14px; } }
      @media (max-width:760px) { #admin-name { max-width:88px; } .admin-popover { right:-2px; width:205px; } }
      @media (prefers-reduced-motion: reduce) {
        *,*::before,*::after { animation-duration:.01ms !important; animation-iteration-count:1 !important; scroll-behavior:auto !important; transition-duration:.01ms !important; }
      }
      @media (max-width:760px) { .heading-actions { gap:7px; } .updated-label { display:none; } .summary-grid,.page-grid,.runtime-detail,.help-grid { grid-template-columns:1fr; } .shortcut-grid { grid-template-columns:1fr; } .runtime-page-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .standalone-card { margin-top:15px; } .safe-list > div,.settings-row { min-height:56px; } .config-fields,.qq-auth-row { grid-template-columns:1fr; } .group-account { grid-template-columns:minmax(0,1fr) 70px; } .group-account .outline-button { grid-column:1 / -1; } }
      @media (max-width:760px) { .theme-control { flex:0 0 auto; gap:2px; padding:3px 4px; } .theme-control-label { display:none; } .theme-control select { width:80px; max-width:80px; padding-right:13px; } }
      @media (max-width:340px) { .topbar { gap:8px; padding-left:12px; padding-right:12px; } .brand { flex:0 0 auto; gap:7px; } .brand > div { max-width:64px; min-width:0; } .brand strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; } .version-badge { display:none; } .top-actions { min-width:0; gap:5px; } .status-dot { font-size:0; gap:0; } .status-dot::before { width:6px; height:6px; } .theme-control select { width:68px; max-width:68px; } .admin-chip { gap:3px; padding-right:4px; } #admin-name { display:none; } }

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

      /* 网盘中心：单平台工作区。保留旧 data-pan-* 控件，只调整信息层级和交互密度。 */
      .pan-page { margin-top:18px; }
      .pan-page-head { display:flex; align-items:flex-start; justify-content:space-between; gap:20px; margin-bottom:17px; }
      .pan-heading-copy { min-width:0; }
      .pan-page-overline { display:block; color:#8b8ea4; font-size:10px; font-weight:800; letter-spacing:1.1px; }
      .pan-page-head h2 { margin:4px 0 0; color:var(--ink); font-size:24px; letter-spacing:0; }
      .pan-page-head p { margin:6px 0 0; color:var(--muted); font-size:12px; }
      .pan-live { display:flex; align-items:center; gap:10px; min-width:154px; padding:10px 13px; border:1px solid #dce9e2; border-radius:10px; background:#f7fcf9; }
      .pan-live-dot { width:8px; height:8px; flex:0 0 auto; border-radius:50%; background:#49b97d; box-shadow:0 0 0 4px #e2f5e9; }
      .pan-live small { display:block; color:#7b8b84; font-size:10px; }
      .pan-live strong { display:block; margin-top:2px; color:#2e7656; font-size:13px; }
      .pan-summary-strip { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); margin-bottom:16px; overflow:hidden; border:1px solid var(--line); border-radius:10px; background:var(--panel); box-shadow:0 5px 18px rgba(55,59,103,.035); }
      .pan-summary-item { min-width:0; min-height:76px; padding:12px 15px; border-right:1px solid var(--line); }
      .pan-summary-item:last-child { border-right:0; }
      .pan-summary-item span { display:block; color:var(--muted); font-size:11px; }
      .pan-summary-item strong { display:block; margin-top:6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--ink); font-size:16px; }
      .pan-summary-item small { display:block; margin-top:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--soft); font-size:10px; }
      .pan-page .pan-tabs { display:flex; gap:7px; margin:0 0 13px; padding:4px; overflow-x:auto; scrollbar-width:thin; border:1px solid #e8e8f4; border-radius:10px; background:#fafaff; }
      .pan-page .pan-tabs::-webkit-scrollbar { height:4px; }
      .pan-page .pan-tab { position:relative; display:flex; align-items:center; justify-content:center; gap:8px; flex:1 1 0; min-width:112px; min-height:43px; padding:0 14px; border:0; border-radius:7px; background:transparent; color:#777992; font-size:12px; font-weight:750; white-space:nowrap; transition:color .18s ease,background .18s ease,box-shadow .18s ease; }
      .pan-page .pan-tab:hover { color:var(--primary-dark); background:#f2f1ff; }
      .pan-page .pan-tab.active { color:var(--primary-dark); background:var(--panel); box-shadow:0 2px 8px rgba(72,68,146,.11); }
      .pan-page .pan-tab.active::after { content:""; position:absolute; right:22%; bottom:3px; left:22%; height:2px; border-radius:2px; background:var(--primary); }
      .pan-tab-mark { width:24px; height:24px; display:grid; place-items:center; flex:0 0 auto; border-radius:7px; font-size:11px; font-weight:850; }
      .pan-tab-uc { background:#efeeff; color:#625dd4; }
      .pan-tab-quark { background:#e8f8ef; color:#35936a; }
      .pan-tab-baidu { background:#fff0e9; color:#ca7b5f; }
      .pan-page .pan-card { min-width:0; padding:0; overflow:hidden; border:1px solid var(--line); border-radius:10px; background:var(--panel); box-shadow:0 7px 22px rgba(55,59,103,.045); transition:border-color .2s ease,box-shadow .2s ease; }
      .pan-page .pan-card:hover { transform:none; box-shadow:0 9px 25px rgba(55,59,103,.07); }
      .pan-page .pan-card.active { border-color:#c9c5f7; box-shadow:0 0 0 2px #eeecff inset,0 8px 23px rgba(55,59,103,.055); }
      .pan-page .pan-card.is-disabled { opacity:1; }
      .pan-page .pan-card[hidden] { display:none !important; }
      .pan-card-head { display:flex; align-items:flex-start; justify-content:space-between; gap:15px; padding:18px 20px; border-bottom:1px solid var(--line); background:linear-gradient(90deg,#fcfbff 0%,var(--panel) 65%); }
      .pan-card-brand { display:flex; align-items:center; gap:11px; min-width:0; }
      .pan-card-brand > div:last-child { min-width:0; }
      .pan-card-brand strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--ink); font-size:16px; }
      .pan-card-brand small { display:block; margin-top:3px; color:var(--muted); font-size:10px; }
      .pan-page .pan-logo { width:39px; height:39px; flex:0 0 auto; border-radius:11px; background:#efeeff; color:#625dd4; font-size:15px; font-weight:850; }
      .pan-page [data-pan-card="夸克"] .pan-logo { background:#e8f8ef; color:#35936a; }
      .pan-page [data-pan-card="百度"] .pan-logo { background:#fff0e9; color:#ca7b5f; }
      .pan-card-head-actions { display:flex; align-items:center; justify-content:flex-end; gap:9px; flex:0 0 auto; }
      .pan-card-head-actions .tag { white-space:nowrap; }
      .pan-enable { display:flex; align-items:center; gap:7px; color:var(--muted); font-size:11px; white-space:nowrap; }
      .pan-page .pan-enable-switch { transform:none; transform-origin:center; }
      .pan-card-stats { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:0; margin:0; border-bottom:1px solid var(--line); background:#fcfcff; }
      .pan-card-stats > div { min-width:0; padding:12px 15px; border-right:1px solid var(--line); }
      .pan-card-stats > div:last-child { border-right:0; }
      .pan-card-stats span { display:block; color:var(--muted); font-size:10px; }
      .pan-card-stats strong { display:block; margin-top:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--ink); font-size:12px; }
      .pan-card-content { display:grid; grid-template-columns:minmax(0,1.1fr) minmax(280px,.9fr); min-width:0; }
      .pan-column { min-width:0; padding:18px 20px; }
      .pan-column + .pan-column { border-left:1px solid var(--line); }
      .pan-section { min-width:0; }
      .pan-section + .pan-section { margin-top:18px; padding-top:18px; border-top:1px solid var(--line); }
      .pan-section-title { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:10px; }
      .pan-section-title strong,.pan-section-title h3 { margin:0; color:var(--ink); font-size:13px; font-weight:750; }
      .pan-section-kicker { display:block; margin-bottom:3px; color:#a0a2b5; font-size:9px; font-weight:800; letter-spacing:1px; }
      .pan-section-title span,.pan-section-title small { color:var(--muted); font-size:10px; }
      .pan-section-hint { flex:0 0 auto; text-align:right; }
      .pan-security-note { margin:0 0 13px; padding:9px 10px; border:1px solid #ececf5; border-radius:7px; background:#fafaff; color:var(--muted); font-size:10px; line-height:1.55; }
      .pan-directory { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px; margin:0; }
      .pan-directory input { min-width:0; min-height:39px; padding:8px 10px; border:1px solid #e1e3ec; border-radius:7px; background:var(--panel); color:var(--ink); outline:none; }
      .pan-directory input:focus { border-color:#aaa0e7; box-shadow:0 0 0 3px #efedff; }
      .pan-directory .outline-button { min-height:39px; padding:0 13px; }
      .pan-page .account-list { display:grid; gap:7px; max-height:240px; margin:0; overflow-y:auto; padding-right:2px; overscroll-behavior:contain; }
      .pan-page .account-row { display:flex; align-items:center; justify-content:space-between; gap:10px; min-width:0; padding:9px 10px; border:1px solid #eceef4; border-radius:7px; background:#fbfcfe; }
      .pan-page .account-row > div,.pan-page .account-row-main { display:grid; grid-template-columns:auto minmax(0,1fr); align-items:center; gap:9px; min-width:0; }
      .pan-page .account-row strong { color:var(--ink); font-size:12px; font-weight:700; white-space:nowrap; }
      .pan-page .account-row span { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--muted); font-size:11px; }
      .pan-page .account-row button { flex:0 0 auto; min-height:28px; padding:0 8px; border:1px solid #f0d8df; border-radius:6px; background:#fff8fa; color:#ba5c75; font-size:10px; }
      .pan-page .account-row button:hover { border-color:#e5b9c5; background:#fff0f4; color:#a94761; }
      .pan-page .account-row-actions { display:flex; align-items:center; gap:8px; flex:0 0 auto; }
      .pan-page .account-row-actions .tag { white-space:nowrap; }
      .pan-page .account-add { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px; margin:0; }
      .pan-page .account-add input { min-width:0; min-height:39px; padding:8px 10px; border:1px solid #e1e3ec; border-radius:7px; background:var(--panel); color:var(--ink); outline:none; }
      .pan-page .account-add input:focus { border-color:#aaa0e7; box-shadow:0 0 0 3px #efedff; }
      .pan-page .account-add .outline-button { min-height:39px; padding:0 13px; }
      .pan-page .account-actions { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1.35fr); gap:8px; margin:0; }
      .pan-page .account-actions .outline-button { min-height:39px; }
      .pan-action-block { min-width:0; }
      .pan-action-row { align-items:stretch; }
      .pan-field-label { display:block; margin:0 0 6px; color:var(--muted); font-size:10px; font-weight:700; }
      .pan-page .pan-select { width:100%; min-height:39px; padding:8px 10px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); }
      .pan-page .pan-select:focus-visible { outline:3px solid #c9c6ff; outline-offset:2px; }
      .pan-advanced { margin-top:0; border-top:1px solid var(--line); }
      .pan-advanced summary { display:flex; align-items:center; justify-content:space-between; gap:10px; min-height:48px; padding:0 20px; color:var(--ink); font-size:12px; font-weight:700; cursor:pointer; list-style:none; }
      .pan-advanced summary::-webkit-details-marker { display:none; }
      .pan-advanced summary::after { content:"＋"; color:var(--muted); font-size:15px; font-weight:400; }
      .pan-advanced[open] summary::after { content:"−"; }
      .pan-advanced summary:focus-visible { outline:3px solid #c9c6ff; outline-offset:-3px; }
      .pan-advanced-content { padding:0 20px 18px; }
      .pan-advanced-body > p { margin:0 0 10px; color:var(--muted); font-size:10px; line-height:1.55; }
      .pan-advanced-content .group-account { display:grid; grid-template-columns:minmax(0,1fr) 84px auto; gap:8px; margin:0; }
      .pan-advanced-content .group-account input,.pan-advanced-content .group-account select { min-width:0; min-height:39px; padding:8px 10px; border:1px solid #e1e3ec; border-radius:7px; background:var(--panel); color:var(--ink); }
      .pan-advanced-content .group-account .outline-button { min-height:39px; padding:0 12px; }
      .pan-page .outline-button:disabled,.pan-page .pan-select:disabled,.pan-page input:disabled { cursor:not-allowed; opacity:.55; }
      .pan-page .outline-button { border-color:#c9c6ff; background:var(--panel); color:var(--primary-dark); }
      .pan-page .outline-button:hover:not(:disabled) { background:var(--primary-soft); }
      @media (max-width:1050px) {
        .pan-summary-strip { grid-template-columns:repeat(2,minmax(0,1fr)); }
        .pan-summary-item:nth-child(2n) { border-right:0; }
        .pan-summary-item:nth-child(-n+2) { border-bottom:1px solid var(--line); }
        .pan-card-content { grid-template-columns:1fr; }
        .pan-column + .pan-column { border-top:1px solid var(--line); border-left:0; }
      }
      @media (max-width:760px) {
        .pan-page { margin-top:15px; }
        .pan-page-head { display:block; }
        .pan-page-head h2 { font-size:21px; }
        .pan-live { width:max-content; min-width:0; margin-top:12px; }
        .pan-page .pan-tabs { margin-bottom:11px; }
        .pan-page .pan-tab { flex:0 0 auto; min-width:104px; min-height:40px; padding:0 12px; }
        .pan-card-head { padding:16px; }
        .pan-card-head-actions { align-items:flex-end; flex-direction:column; gap:7px; }
        .pan-card-stats { grid-template-columns:repeat(2,minmax(0,1fr)); }
        .pan-card-stats > div:nth-child(2n) { border-right:0; }
        .pan-card-stats > div:nth-child(-n+2) { border-bottom:1px solid var(--line); }
        .pan-column { padding:16px; }
        .pan-directory,.pan-page .account-add { grid-template-columns:1fr; }
        .pan-directory .outline-button,.pan-page .account-add .outline-button { width:100%; }
        .pan-page .account-actions { grid-template-columns:1fr; }
        .pan-advanced summary { padding:0 16px; }
        .pan-advanced-content { padding:0 16px 16px; }
        .pan-advanced-content .group-account { grid-template-columns:minmax(0,1fr) 78px; }
        .pan-advanced-content .group-account .outline-button { grid-column:1 / -1; }
      }
      @media (max-width:390px) {
        .pan-summary-strip { grid-template-columns:1fr; }
        .pan-summary-item,.pan-summary-item:nth-child(2n) { border-right:0; border-bottom:1px solid var(--line); }
        .pan-summary-item:last-child { border-bottom:0; }
        .pan-card-head { display:block; }
        .pan-card-head-actions { align-items:flex-start; flex-direction:row; flex-wrap:wrap; margin-top:12px; }
      }

      /* ===== 可选深色模式 ===== */
      :root[data-theme="dark"] { color-scheme:dark; --ink:#e8eaf2; --muted:#9aa0b5; --soft:#6f7590; --line:#2c3044; --bg:#171a24; --panel:#1f2330; --primary:#8b85ff; --primary-dark:#a29cff; --primary-soft:#2b2b4c; --mint:#16382c; --mint-ink:#55d8a2; --peach:#3a2a22; --peach-ink:#e5977a; --yellow:#38301a; --yellow-ink:#d9ac49; --pink:#38202e; --pink-ink:#e287ae; --shadow:0 10px 30px rgba(0,0,0,.28); }
      :root[data-theme="dark"] body { background:var(--bg); color:var(--ink); }
      :root[data-theme="dark"] .topbar { background:var(--panel); }
      :root[data-theme="dark"] .theme-control:hover,:root[data-theme="dark"] .theme-control:focus-within { border-color:#3a3f58; background:#232838; }
      :root[data-theme="dark"] .version-badge { background:#2a2e3c; color:var(--muted); }
      :root[data-theme="dark"] .admin-chip:hover,:root[data-theme="dark"] .admin-chip[aria-expanded="true"] { border-color:#3a3f58; background:#232838; }
      :root[data-theme="dark"] .admin-popover { background:var(--panel); }
      :root[data-theme="dark"] .popover-logout { background:#262b3a; color:#e86a6a; }
      :root[data-theme="dark"] .popover-logout:hover { background:#35252b; border-color:#5a3941; }
      :root[data-theme="dark"] .sidebar { background:var(--panel); }
      :root[data-theme="dark"] .bot-avatar { border-color:#33385a; }
      :root[data-theme="dark"] .nav-label { color:#6a7088; }
      :root[data-theme="dark"] .nav a { color:#9ca2b5; }
      :root[data-theme="dark"] .nav-icon { color:#767d96; }
      :root[data-theme="dark"] .sidebar-foot { border-color:#2c3044; background:#1b1f2c; }
      :root[data-theme="dark"] .notice { border-color:#55481f; color:#d9b45c; }
      :root[data-theme="dark"] .metric:nth-child(1) { background:#1c2030; }
      :root[data-theme="dark"] .metric:nth-child(2) { background:#182a24; }
      :root[data-theme="dark"] .metric:nth-child(3) { background:#2b2518; }
      :root[data-theme="dark"] .metric:nth-child(4) { background:#2b1b24; }
      :root[data-theme="dark"] .global-bar { background:#1c2030; }
      :root[data-theme="dark"] .switch { background:#383d52; }
      :root[data-theme="dark"] .pan-card.active { border-color:#6a66c9; box-shadow:0 0 0 2px #24284a inset, var(--shadow); }
      :root[data-theme="dark"] .pan-enable { color:#9aa0b5; }
      :root[data-theme="dark"] .tag.off { background:#262b38; color:#9aa0b5; }
      :root[data-theme="dark"] .account-row { border-color:#2c3044; background:#1d2130; }
      :root[data-theme="dark"] .pan-select { background:var(--panel); }
      :root[data-theme="dark"] .console-card { background:var(--panel); }
      :root[data-theme="dark"] .profile-field { border-bottom-color:#2c3044; }
      :root[data-theme="dark"] .readonly-value { border-color:#333a55; background:var(--panel); }
      :root[data-theme="dark"] .connection-row { border-bottom-color:#2c3044; }
      :root[data-theme="dark"] .status-item { border-bottom-color:#2c3044; }
      :root[data-theme="dark"] .main { background:var(--bg); }
      :root[data-theme="dark"] .profile-field > span,:root[data-theme="dark"] .connection-row > span,:root[data-theme="dark"] .status-item span,:root[data-theme="dark"] .safe-list span,:root[data-theme="dark"] .settings-row span { color:#9aa0b5; }
      :root[data-theme="dark"] .readonly-value small { color:#767d96; }
      :root[data-theme="dark"] .bot-avatar { background:#2b2b4c; border-color:#33385a; }
      :root[data-theme="dark"] .test-bubble p { background:#222738; color:#a6acbd; }
      :root[data-theme="dark"] .test-mini-avatar { background:#2b2b4c; color:#a29cff; }
      :root[data-theme="dark"] .test-hint { color:#6f7590; }
      :root[data-theme="dark"] .pan-tabs { border-color:#2c3044; background:#181c28; }
      :root[data-theme="dark"] .pan-tab { color:#8f95a8; }
      :root[data-theme="dark"] .pan-tab:hover { background:#24284a; }
      :root[data-theme="dark"] .pan-tab.active { background:var(--panel); }
      :root[data-theme="dark"] .summary-card { background:var(--panel); }
      :root[data-theme="dark"] .shortcut-card { border-color:#2c3044; background:var(--panel); }
      :root[data-theme="dark"] .shortcut-card:hover { border-color:#6a66c9; background:#202435; }
      :root[data-theme="dark"] .outline-button { border-color:#6a66c9; background:var(--panel); }
      :root[data-theme="dark"] .pan-note { border-color:#333a55; background:#1c2030; }
      :root[data-theme="dark"] .runtime-detail .status-item { background:#1b2030; }
      :root[data-theme="dark"] .safe-list > div,:root[data-theme="dark"] .settings-row { border-bottom-color:#2c3044; }
      :root[data-theme="dark"] .config-group { border-color:#2c3044; background:#1b1f2c; }
      :root[data-theme="dark"] .config-field label { color:#9aa0b5; }
      :root[data-theme="dark"] .config-field input,:root[data-theme="dark"] .config-field textarea,:root[data-theme="dark"] .config-field select,:root[data-theme="dark"] .account-add input,:root[data-theme="dark"] .group-account input { border-color:#333a55; background:var(--panel); }
      :root[data-theme="dark"] .config-field input:focus,:root[data-theme="dark"] .config-field textarea:focus,:root[data-theme="dark"] .config-field select:focus,:root[data-theme="dark"] .account-add input:focus,:root[data-theme="dark"] .group-account input:focus { border-color:#8b85ff; box-shadow:0 0 0 3px #262a4c; }
      :root[data-theme="dark"] .pan-directory input { border-color:#333a55; background:var(--panel); }
      :root[data-theme="dark"] .pan-security-note { background:#181c28; }
      :root[data-theme="dark"] .group-account select { border-color:#333a55; background:var(--panel); }
      :root[data-theme="dark"] .qq-auth-row input { border-color:#333a55; background:var(--panel); }
      :root[data-theme="dark"] .settings-hint { background:#1b1f2c; }
      :root[data-theme="dark"] .command-list span { border-color:#333a55; background:#1d2130; color:#9ca2b5; }
      :root[data-theme="dark"] .novel-overline,:root[data-theme="dark"] .novel-panel-kicker,:root[data-theme="dark"] .novel-platform-overline { color:#9096ab; }
      :root[data-theme="dark"] .novel-state-pill { border-color:#2b4a3c; background:#13302a; color:#55d8a2; }
      :root[data-theme="dark"] .novel-state-pill.is-off { border-color:#333a55; background:#1d2130; color:#9aa0b5; }
      :root[data-theme="dark"] .novel-state-pill.is-off .novel-state-dot { background:#7b8296; box-shadow:0 0 0 4px #262b3a; }
      :root[data-theme="dark"] .novel-master-panel { border-color:#3f3a7e; background:#1c1f36; }
      :root[data-theme="dark"] .novel-test-panel { border-color:#4d362a; background:#2b211b; }
      :root[data-theme="dark"] .novel-panel-icon { background:#2b2b4c; color:#a29cff; }
      :root[data-theme="dark"] .novel-test-panel .novel-panel-icon { background:#4a2b1c; color:#e5977a; }
      :root[data-theme="dark"] .novel-master-copy p,:root[data-theme="dark"] .novel-test-panel p { color:#9aa0b5; }
      :root[data-theme="dark"] .novel-master-state span,:root[data-theme="dark"] .novel-test-note { color:#767d96; }
      :root[data-theme="dark"] .novel-platform-count { color:#8f95a8; }
      :root[data-theme="dark"] .novel-item { border-color:#2c3044; background:var(--panel); }
      :root[data-theme="dark"] .novel-item:hover { border-color:#6a66c9; background:#202435; box-shadow:0 7px 18px rgba(0,0,0,.3); }
      :root[data-theme="dark"] .novel-item.is-enabled { border-color:#2b4a3c; }
      :root[data-theme="dark"] .novel-item.is-disabled { background:#1d2130; }
      :root[data-theme="dark"] .novel-badge { background:#2b2b4c; color:#a29cff; }
      :root[data-theme="dark"] .novel-item:nth-child(3n+2) .novel-badge { background:#16382c; color:#55d8a2; }
      :root[data-theme="dark"] .novel-item:nth-child(3n) .novel-badge { background:#3a2a22; color:#e5977a; }
      :root[data-theme="dark"] .novel-item-copy small { color:#8f95a8; }
      :root[data-theme="dark"] .novel-item-status { color:#767d96; }
      :root[data-theme="dark"] .toast { background:#3b3f5f; }
      :root[data-theme="dark"] .pan-tab:focus-visible,:root[data-theme="dark"] .config-field input:focus-visible,:root[data-theme="dark"] .pan-directory input:focus-visible { outline-color:#8b85ff; }
      :root[data-theme="dark"] .account-row button { color:#e07085; }
      :root[data-theme="dark"] .account-row button:hover { color:#f0899c; }
      :root[data-theme="dark"] .config-message.error,:root[data-theme="dark"] .qq-auth-message.error { color:#e07085; }
      :root[data-theme="dark"] .pan-live { border-color:#2b4a3c; background:#13302a; }
      :root[data-theme="dark"] .pan-live-dot { background:#55d8a2; box-shadow:0 0 0 4px #1d4a39; }
      :root[data-theme="dark"] .pan-live small { color:#9aa0b5; }
      :root[data-theme="dark"] .pan-live strong { color:#55d8a2; }
      :root[data-theme="dark"] .pan-card-head { border-bottom-color:var(--line); background:#1c2030; }
      :root[data-theme="dark"] .pan-card-stats { border-bottom-color:var(--line); background:#1b1f2c; }
      :root[data-theme="dark"] .pan-card-stats > div { border-right-color:var(--line); }
      :root[data-theme="dark"] .pan-card.active { border-color:#6a66c9; box-shadow:0 0 0 2px #24284a inset,0 8px 23px rgba(0,0,0,.28); }
      :root[data-theme="dark"] .pan-security-note { border-color:#333a55; background:#181c28; }
      :root[data-theme="dark"] .pan-page .account-row { border-color:#2c3044; background:#1d2130; }
      :root[data-theme="dark"] .pan-page .account-row button { border-color:#5a3941; background:#30222a; color:#e07085; }
      :root[data-theme="dark"] .pan-page .account-row button:hover { background:#3a212b; color:#f0899c; }
      :root[data-theme="dark"] .pan-section-kicker { color:#767d96; }
      @media (max-width:760px) {
        .topbar { min-height:50px; height:50px; padding:0 10px; gap:8px; }
        .brand { gap:7px; }
        .brand-mark { width:30px; height:30px; border-width:2px; font-size:11px; }
        .brand strong { font-size:14px; }
        .version-badge { display:none; }
        .top-actions { min-width:0; gap:4px; }
        .theme-control { min-height:28px; padding:2px 3px; }
        .theme-control-icon { display:none; }
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
    """
