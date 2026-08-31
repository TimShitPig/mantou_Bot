"""帮助网页登录页样式。"""

登录页样式 = """
    :root { color-scheme:light; --ink:#292741; --muted:#7d8096; --line:#e8e9f2; --bg:#f7f8fd; --panel:#fff; --primary:#6b63f5; --primary-dark:#574eea; --primary-soft:#f0efff; --mint:#e9fbf3; --mint-ink:#319e6b; }
    * { box-sizing:border-box; }
    html,body { min-height:100%; }
    body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.55 Inter,"PingFang SC","Microsoft YaHei",ui-sans-serif,system-ui,sans-serif; }
    button,input { font:inherit; }
    button { cursor:pointer; }
    .login-page { min-height:100vh; display:grid; place-items:center; padding:24px; }
    .login-shell { width:min(850px,100%); display:grid; grid-template-columns:minmax(0,1.05fr) minmax(320px,.95fr); overflow:hidden; border:1px solid var(--line); border-radius:18px; background:var(--panel); box-shadow:0 18px 48px rgba(60,57,112,.08); animation:login-rise .42s cubic-bezier(.22,.8,.35,1) both; }
    .login-welcome { display:flex; flex-direction:column; justify-content:center; min-height:510px; padding:54px 50px; background:#fbfaff; border-right:1px solid var(--line); }
    .login-brand { display:flex; align-items:center; gap:11px; }
    .login-brand-mark { width:38px; height:38px; display:grid; place-items:center; border:3px solid #f5f4ff; border-radius:50%; background:#e9e9ff; color:#5d58d8; font-size:14px; font-weight:800; }
    .login-brand strong { display:block; font-size:16px; }
    .login-brand small { display:block; margin-top:1px; color:var(--muted); font-size:11px; }
    .login-illustration { position:relative; width:176px; height:176px; display:grid; place-items:center; margin:42px auto 27px; }
    .login-illustration::before { content:""; position:absolute; inset:13px; border:1px solid #e6e4ff; border-radius:50%; }
    .login-avatar { position:relative; width:112px; height:112px; overflow:hidden; border:7px solid #f0efff; border-radius:50%; background:#e9eaff; box-shadow:0 10px 22px rgba(92,87,210,.14); animation:login-float 3.4s ease-in-out infinite; }
    .login-avatar::before { content:""; position:absolute; width:96px; height:91px; left:0; top:7px; border-radius:50% 50% 43% 43%; background:#a2a5f7; }
    .login-avatar::after { content:"✦"; position:absolute; right:9px; top:5px; color:#fff; font-size:17px; }
    .login-avatar-face { position:absolute; left:22px; top:43px; z-index:1; color:#4f50a8; font-size:30px; letter-spacing:7px; }
    .login-star { position:absolute; color:#b4b0ff; font-size:18px; animation:login-twinkle 2.4s ease-in-out infinite; }
    .login-star.one { left:13px; top:34px; }
    .login-star.two { right:12px; bottom:31px; animation-delay:.8s; }
    .login-welcome h1 { margin:0; text-align:center; font-size:25px; letter-spacing:.2px; }
    .login-welcome p { max-width:290px; margin:8px auto 0; color:var(--muted); font-size:12px; line-height:1.8; text-align:center; }
    .login-panel { display:flex; flex-direction:column; justify-content:center; padding:54px 50px; }
    .login-theme-control { align-self:flex-end; display:inline-flex; align-items:center; gap:5px; min-height:28px; margin:-18px -8px 20px 0; padding:3px 5px 3px 7px; border:1px solid transparent; border-radius:7px; color:var(--muted); font-size:11px; font-weight:650; transition:background .18s ease,border-color .18s ease; }
    .login-theme-control:hover,.login-theme-control:focus-within { border-color:#e5e3f7; background:#fbfaff; }
    .login-theme-control > span { color:var(--primary); font-size:14px; line-height:1; }
    .login-theme-control select { min-height:23px; padding:1px 17px 1px 2px; border:0; border-radius:4px; background:transparent; color:var(--ink); font-size:11px; font-weight:650; cursor:pointer; outline:none; }
    .login-theme-control select option { background:var(--panel); color:var(--ink); }
    .login-theme-control > span { transform-origin:center; }
    .theme-switching .login-shell { animation:theme-switch .32s ease both; }
    .theme-switching .login-theme-control > span { animation:theme-icon .32s ease both; }
    .login-panel h2 { margin:0; font-size:20px; }
    .login-panel > p { margin:7px 0 25px; color:var(--muted); font-size:12px; }
    .login-form { display:grid; gap:15px; }
    .login-form label { display:grid; gap:6px; color:#5f5d72; font-size:12px; font-weight:700; }
    .login-form input { width:100%; min-height:43px; padding:9px 12px; border:1px solid #dddceb; border-radius:8px; background:#fff; color:var(--ink); outline:none; transition:border-color .18s ease,box-shadow .18s ease; }
    .login-form input:focus { border-color:#aaa0e7; box-shadow:0 0 0 3px #efedff; }
    .login-button { display:flex; align-items:center; justify-content:center; gap:8px; min-height:43px; margin-top:5px; border:0; border-radius:8px; background:var(--primary); color:#fff; font-size:13px; font-weight:750; box-shadow:0 7px 17px rgba(107,99,245,.2); transition:background .18s ease,transform .18s ease; }
    .login-button:hover { background:var(--primary-dark); transform:translateY(-1px); }
    .login-button:disabled { cursor:wait; opacity:.65; transform:none; }
    .login-message { min-height:20px; margin:16px 0 0; color:#c06478; font-size:12px; line-height:1.6; }
    .login-message:empty { margin-top:8px; }
    .login-note { display:flex; align-items:center; gap:6px; margin-top:28px; color:#9b9db0; font-size:11px; }
    .login-note::before { content:""; width:7px; height:7px; border-radius:50%; background:#4dbb82; box-shadow:0 0 0 4px var(--mint); }
    @keyframes login-rise { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
    @keyframes login-float { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-5px); } }
    @keyframes login-twinkle { 0%,100% { opacity:.45; transform:scale(.9); } 50% { opacity:1; transform:scale(1.08); } }
    @keyframes theme-switch { 0% { opacity:.72; } 100% { opacity:1; } }
    @keyframes theme-icon { 0% { transform:rotate(0deg) scale(.86); } 55% { transform:rotate(180deg) scale(1.08); } 100% { transform:rotate(360deg) scale(1); } }
    @media (max-width:680px) { .login-page { padding:15px; } .login-shell { grid-template-columns:1fr; max-width:430px; } .login-welcome { min-height:0; padding:31px 26px 27px; border-right:0; border-bottom:1px solid var(--line); } .login-illustration { width:130px; height:130px; margin:24px auto 18px; } .login-illustration::before { inset:8px; } .login-avatar { width:82px; height:82px; border-width:5px; } .login-avatar::before { width:72px; height:69px; top:4px; } .login-avatar-face { left:16px; top:31px; font-size:22px; letter-spacing:4px; } .login-avatar::after { right:5px; top:2px; font-size:12px; } .login-star { font-size:14px; } .login-welcome h1 { font-size:21px; } .login-panel { padding:31px 26px 34px; } .login-theme-control { margin:-8px -3px 15px 0; } }
    @media (prefers-reduced-motion:reduce) { *,*::before,*::after { animation-duration:.01ms !important; animation-iteration-count:1 !important; transition-duration:.01ms !important; } }

    /* ===== 可选深色模式 ===== */
    :root[data-theme="dark"] { color-scheme:dark; --ink:#e8eaf2; --muted:#9aa0b5; --line:#2c3044; --bg:#171a24; --panel:#1f2330; --primary:#8b85ff; --primary-dark:#a29cff; --primary-soft:#2b2b4c; --mint:#16382c; --mint-ink:#55d8a2; }
    :root[data-theme="dark"] body { background:var(--bg); color:var(--ink); }
    :root[data-theme="dark"] .login-shell { box-shadow:0 18px 48px rgba(0,0,0,.35); }
    :root[data-theme="dark"] .login-welcome { background:#1b1f2c; border-right-color:var(--line); }
    :root[data-theme="dark"] .login-brand-mark { border-color:#33385a; background:#2b2b4c; color:#a29cff; }
    :root[data-theme="dark"] .login-illustration::before { border-color:#33385a; }
    :root[data-theme="dark"] .login-avatar { border-color:#33385a; background:#2b2b4c; box-shadow:0 10px 22px rgba(0,0,0,.4); }
    :root[data-theme="dark"] .login-avatar::before { background:#4a4e8f; }
    :root[data-theme="dark"] .login-avatar-face { color:#b9b6ff; }
    :root[data-theme="dark"] .login-star { color:#6f6fd8; }
    :root[data-theme="dark"] .login-theme-control:hover,:root[data-theme="dark"] .login-theme-control:focus-within { border-color:#3a3f58; background:#232838; }
    :root[data-theme="dark"] .login-form label { color:#9aa0b5; }
    :root[data-theme="dark"] .login-form input { border-color:#333a55; background:#161926; color:var(--ink); }
    :root[data-theme="dark"] .login-form input:focus { border-color:#8b85ff; box-shadow:0 0 0 3px #262a4c; }
    :root[data-theme="dark"] .login-button { box-shadow:0 7px 17px rgba(0,0,0,.3); }
    :root[data-theme="dark"] .login-note { color:#6f7590; }
  """
