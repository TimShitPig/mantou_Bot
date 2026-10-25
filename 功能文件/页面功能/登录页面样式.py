"""帮助网页登录页样式。"""

登录页样式 = """
    :root { color-scheme:light; --ink:#16304a; --muted:#586f85; --line:#d6e3ed; --bg:#edf4fa; --panel:#fff; --primary:#087baf; --primary-dark:#05688f; --primary-soft:#e0f5fc; --input-bg:#f6f9fc; --welcome-bg:#e6f0f7; --route:#acc9dc; --route-soft:#ccdee9; --warm:#aa6225; --focus-ring:rgba(8,123,175,.16); --shadow:0 30px 80px rgba(32,67,96,.13); }
    :root[data-theme="dark"] { color-scheme:dark; --ink:#e6f3ff; --muted:#9bb3ca; --line:#29445d; --bg:#081423; --panel:#102338; --primary:#57d6ff; --primary-dark:#8ee4ff; --primary-soft:#163b51; --input-bg:#0c1c2d; --welcome-bg:#0b1c2d; --route:#31657f; --route-soft:#1e3c51; --warm:#f6b76a; --focus-ring:rgba(87,214,255,.16); --shadow:0 30px 100px rgba(0,0,0,.35); }
    * { box-sizing:border-box; }
    html,body { min-height:100%; }
    body { margin:0; color:var(--ink); background:var(--bg); font:14px/1.6 "Microsoft YaHei UI","PingFang SC","Microsoft YaHei",system-ui,sans-serif; -webkit-font-smoothing:antialiased; }
    button,input,select { font:inherit; }
    button { cursor:pointer; }
    button:focus-visible,select:focus-visible { outline:2px solid var(--primary); outline-offset:4px; }
    svg { fill:none; stroke:currentColor; stroke-width:1.7; stroke-linecap:round; stroke-linejoin:round; }
    .login-page { min-height:100vh; min-height:100dvh; display:grid; place-items:center; padding:40px 24px; }
    .login-shell { width:min(980px,100%); display:grid; grid-template-columns:minmax(0,1.13fr) minmax(340px,.87fr); overflow:hidden; border:1px solid var(--line); border-radius:22px; background:var(--panel); box-shadow:var(--shadow); animation:login-reveal .45s ease-out both; }
    .login-welcome { position:relative; min-height:604px; padding:37px 48px 45px; border-right:1px solid var(--line); background:var(--welcome-bg); }
    .login-brand { display:flex; align-items:center; gap:12px; }
    .login-brand-mark { width:42px; height:42px; display:grid; place-items:center; border:1px solid var(--route); border-radius:13px 5px 13px 5px; color:var(--primary); background:var(--primary-soft); font-size:18px; font-weight:800; }
    .login-brand strong { display:block; font-size:16px; letter-spacing:.5px; }
    .login-brand small { display:block; color:var(--muted); font-size:11px; }
    .login-constellation { position:relative; width:min(380px,100%); height:270px; margin:24px auto 12px; }
    .login-routes { position:absolute; inset:0; width:100%; height:100%; stroke-width:1; }
    .route-guide { stroke:var(--route-soft); stroke-dasharray:3 8; }
    .route-orbit { stroke:var(--route); }
    .route-inner { stroke:var(--route-soft); stroke-dasharray:2 6; }
    .route-link { stroke:var(--primary); opacity:.5; }
    .route-point { fill:var(--primary); stroke:none; }
    .route-point.warm { fill:var(--warm); }
    .login-core { position:absolute; left:50%; top:50%; width:76px; height:76px; display:grid; place-items:center; transform:translate(-50%,-50%); border:1px solid var(--primary); border-radius:24px 8px 24px 8px; color:var(--primary); background:var(--panel); box-shadow:0 0 0 9px var(--welcome-bg),0 0 0 10px var(--route-soft); }
    .login-core span { font-size:32px; font-weight:700; }
    .login-node { position:absolute; display:flex; align-items:center; gap:9px; padding:10px 13px; border:1px solid var(--route); border-radius:9px; background:var(--panel); font-size:12px; font-weight:650; color:var(--muted); }
    .login-node svg { width:20px; height:20px; color:var(--primary); }
    .node-messages { left:3%; top:20%; }
    .node-books { right:2%; top:19%; }
    .node-books svg { color:var(--warm); }
    .node-cloud { left:50%; bottom:0; transform:translateX(-50%); }
    .login-welcome h1 { margin:22px 0 0; font-family:"DengXian","Microsoft YaHei UI",sans-serif; font-size:35px; line-height:1.4; font-weight:650; letter-spacing:1px; }
    .login-welcome p { margin:13px 0 0; color:var(--muted); font-size:12px; }
    .login-panel { display:flex; flex-direction:column; justify-content:center; padding:37px 40px 42px; }
    .login-theme-control { display:inline-flex; align-self:flex-end; align-items:center; gap:7px; margin:0 0 46px; padding:4px 6px 4px 9px; border:1px solid var(--line); border-radius:7px; color:var(--muted); font-size:11px; }
    .login-theme-control > span { color:var(--primary); font-size:15px; }
    .login-theme-control:focus-within { border-color:var(--primary); box-shadow:0 0 0 3px var(--focus-ring); }
    .login-theme-control select { max-width:120px; min-height:26px; border:0; background:transparent; color:var(--ink); font-size:11px; outline:none; cursor:pointer; }
    .login-theme-control select option { color:var(--ink); background:var(--panel); }
    .login-panel h2 { margin:0; font-size:28px; line-height:1.4; font-weight:650; }
    .login-panel > p { margin:9px 0 30px; color:var(--muted); font-size:12px; }
    .login-form { display:grid; gap:20px; }
    .login-form label { display:grid; gap:8px; color:var(--ink); font-size:12px; font-weight:650; }
    .login-form input { width:100%; min-width:0; min-height:47px; padding:11px 13px; border:1px solid var(--line); border-radius:8px; background:var(--input-bg); color:var(--ink); outline:none; transition:border-color .18s ease,box-shadow .18s ease; }
    .login-form input::placeholder { color:var(--muted); font-weight:400; opacity:.8; }
    .login-form input:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--focus-ring); }
    .login-password-field { display:grid; gap:8px; }
    .login-password-wrap { position:relative; }
    .login-password-wrap input { padding-right:46px; }
    .login-password-toggle { position:absolute; right:4px; top:4px; display:grid; place-items:center; width:39px; height:39px; padding:9px; border:0; border-radius:6px; background:transparent; color:var(--muted); }
    .login-password-toggle svg { width:20px; height:20px; }
    .login-password-toggle:hover,.login-password-toggle[aria-pressed="true"] { background:var(--primary-soft); color:var(--primary); }
    .login-password-toggle:focus-visible { outline-offset:-2px; }
    .login-button { display:flex; align-items:center; justify-content:center; gap:12px; min-height:47px; margin-top:7px; padding:11px 16px; border:1px solid transparent; border-radius:8px; background:var(--primary); color:#fff; font-size:13px; font-weight:750; transition:background .18s ease,box-shadow .18s ease; }
    :root[data-theme="dark"] .login-button { color:#082239; }
    .login-button svg { width:18px; height:18px; }
    .login-button:hover { background:var(--primary-dark); box-shadow:0 0 0 4px var(--focus-ring); }
    .login-button:disabled { cursor:wait; opacity:.65; }
    .login-panel > .login-message { min-height:20px; margin:15px 0 0; color:#b1374f; font-size:12px; line-height:1.6; }
    :root[data-theme="dark"] .login-panel > .login-message { color:#ff9db0; }
    .login-note { display:flex; align-items:flex-start; gap:9px; margin-top:25px; padding-top:19px; border-top:1px solid var(--line); color:var(--muted); font-size:11px; line-height:1.7; }
    .login-note::before { content:""; flex:0 0 6px; width:6px; height:6px; margin-top:6px; border-radius:50%; background:var(--primary); }
    @keyframes login-reveal { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:none; } }
    @media (max-width:760px) { .login-page { padding:24px 16px; } .login-shell { max-width:480px; grid-template-columns:1fr; border-radius:16px; } .login-welcome { min-height:0; padding:25px 28px; border-right:0; border-bottom:1px solid var(--line); } .login-brand-mark { width:35px; height:35px; font-size:15px; } .login-brand strong { font-size:14px; } .login-brand small { font-size:10px; } .login-constellation { display:none; } .login-welcome h1 { margin-top:25px; font-size:26px; line-height:1.35; } .login-welcome h1 br { display:none; } .login-welcome p { margin-top:8px; font-size:11px; } .login-panel { padding:24px 28px 29px; } .login-theme-control { margin:0 0 22px; } .login-panel h2 { font-size:24px; } .login-panel > p { margin:8px 0 25px; } .login-form { gap:17px; } .login-note { margin-top:17px; } }
    @media (max-width:360px) { .login-page { padding:16px 10px; } .login-welcome,.login-panel { padding-left:21px; padding-right:21px; } .login-welcome h1 { font-size:24px; } }
    @media (prefers-reduced-motion:reduce) { *,*::before,*::after { animation:none !important; transition:none !important; scroll-behavior:auto !important; } }
  """
