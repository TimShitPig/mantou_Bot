"""帮助网页登录页样式。"""

登录页样式 = """
    :root {
      color-scheme: light;
      --ink: #1c2035;
      --ink-secondary: #484f68;
      --muted: #727a94;
      --soft: #9da6be;
      --line: #e3e6f0;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --primary: #5c54e5;
      --primary-dark: #473ecf;
      --primary-soft: #eeecfd;
      --primary-glow: rgba(92, 84, 229, 0.2);
      --mint: #e8f8f0;
      --mint-ink: #158051;
      --danger: #ef4444;
      --shadow-lg: 0 20px 50px rgba(18, 24, 48, 0.09);
    }
    * { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
      -webkit-font-smoothing: antialiased;
    }
    button, input, select { font: inherit; }
    button { cursor: pointer; }
    .login-page { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
    .login-shell { width: min(850px, 100%); display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(320px, .95fr); overflow: hidden; border: 1px solid var(--line); border-radius: 20px; background: var(--panel); box-shadow: var(--shadow-lg); animation: login-rise .42s cubic-bezier(.22,.8,.35,1) both; }
    .login-welcome { display: flex; flex-direction: column; justify-content: center; min-height: 510px; padding: 54px 50px; background: linear-gradient(135deg, var(--primary-soft), var(--bg)); border-right: 1px solid var(--line); }
    .login-brand { display: flex; align-items: center; gap: 11px; }
    .login-brand-mark { width: 40px; height: 40px; display: grid; place-items: center; border: 2px solid var(--line); border-radius: 12px; background: var(--panel); color: var(--primary); font-size: 15px; font-weight: 800; box-shadow: 0 2px 8px var(--primary-glow); }
    .login-brand strong { display: block; font-size: 16px; font-weight: 750; }
    .login-brand small { display: block; margin-top: 1px; color: var(--muted); font-size: 11px; }
    .login-illustration { position: relative; width: 176px; height: 176px; display: grid; place-items: center; margin: 42px auto 27px; }
    .login-illustration::before { content: ""; position: absolute; inset: 10px; border: 1px dashed var(--primary); border-radius: 50%; opacity: .4; }
    .login-avatar { position: relative; width: 112px; height: 112px; overflow: hidden; border: 6px solid var(--primary-soft); border-radius: 50%; background: linear-gradient(135deg, #e4e2fd, #c9c5fc); box-shadow: 0 10px 25px var(--primary-glow); animation: login-float 3.4s ease-in-out infinite; }
    .login-avatar::before { content: ""; position: absolute; width: 96px; height: 91px; left: 0; top: 7px; border-radius: 50% 50% 43% 43%; background: #928ef2; }
    .login-avatar::after { content: "✦"; position: absolute; right: 9px; top: 5px; color: #fff; font-size: 17px; }
    .login-avatar-face { position: absolute; left: 22px; top: 43px; z-index: 1; color: #3e3a96; font-size: 30px; letter-spacing: 7px; }
    .login-star { position: absolute; color: var(--primary); font-size: 18px; animation: login-twinkle 2.4s ease-in-out infinite; }
    .login-star.one { left: 13px; top: 34px; }
    .login-star.two { right: 12px; bottom: 31px; animation-delay: .8s; }
    .login-welcome h1 { margin: 0; text-align: center; font-size: 25px; font-weight: 800; letter-spacing: -.3px; }
    .login-welcome p { max-width: 290px; margin: 8px auto 0; color: var(--muted); font-size: 12px; line-height: 1.8; text-align: center; }
    .login-panel { display: flex; flex-direction: column; justify-content: center; padding: 54px 50px; }
    .login-theme-control { align-self: flex-end; display: inline-flex; align-items: center; gap: 5px; min-height: 30px; margin: -18px -8px 20px 0; padding: 3px 6px 3px 8px; border: 1px solid var(--line); border-radius: 8px; color: var(--muted); font-size: 11px; font-weight: 650; }
    .login-theme-control:hover, .login-theme-control:focus-within { border-color: var(--primary); background: var(--primary-soft); color: var(--primary-dark); }
    .login-theme-control > span { color: var(--primary); font-size: 14px; line-height: 1; }
    .login-theme-control select { min-height: 24px; padding: 1px 16px 1px 2px; border: 0; border-radius: 4px; background: transparent; color: var(--ink); font-size: 11px; font-weight: 650; cursor: pointer; outline: none; }
    .login-panel h2 { margin: 0; font-size: 21px; font-weight: 800; letter-spacing: -.2px; }
    .login-panel > p { margin: 6px 0 24px; color: var(--muted); font-size: 12.5px; }
    .login-form { display: grid; gap: 16px; }
    .login-form label { display: grid; gap: 6px; color: var(--ink-secondary); font-size: 12px; font-weight: 700; }
    .login-form input { width: 100%; min-height: 42px; padding: 9px 13px; border: 1px solid var(--line); border-radius: 10px; background: var(--bg); color: var(--ink); outline: none; transition: border-color .18s ease, box-shadow .18s ease, background .18s ease; }
    .login-form input:focus { border-color: var(--primary); background: var(--panel); box-shadow: 0 0 0 3px var(--primary-glow); }
    .login-button { display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 44px; margin-top: 6px; border: 0; border-radius: 10px; background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: #fff; font-size: 13px; font-weight: 750; box-shadow: 0 4px 16px var(--primary-glow); transition: filter .18s ease, transform .18s ease; }
    .login-button:hover { filter: brightness(1.08); transform: translateY(-1px); }
    .login-button:active { transform: scale(0.98); }
    .login-button:disabled { cursor: wait; opacity: .65; transform: none; }
    .login-message { min-height: 20px; margin: 16px 0 0; color: var(--danger); font-size: 12px; font-weight: 600; line-height: 1.6; }
    .login-note { display: flex; align-items: center; gap: 6px; margin-top: 28px; color: var(--muted); font-size: 11px; }
    .login-note::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,.25); }
    @keyframes login-rise { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes login-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-5px); } }
    @keyframes login-twinkle { 0%, 100% { opacity: .45; transform: scale(.9); } 50% { opacity: 1; transform: scale(1.08); } }

    /* ===== 暗色模式 (Dark Theme) ===== */
    :root[data-theme="dark"] {
      color-scheme: dark;
      --ink: #f0f2fa;
      --ink-secondary: #adb4c8;
      --muted: #828ba3;
      --soft: #5b647d;
      --line: #262c3e;
      --bg: #0d1019;
      --panel: #161a26;
      --primary: #7c75ff;
      --primary-dark: #9892ff;
      --primary-soft: #232742;
      --primary-glow: rgba(124, 117, 255, 0.25);
      --danger: #f87171;
      --shadow-lg: 0 20px 50px rgba(0, 0, 0, 0.55);
    }
    :root[data-theme="dark"] body { background: var(--bg); color: var(--ink); }
    :root[data-theme="dark"] .login-shell { box-shadow: var(--shadow-lg); border-color: var(--line); }
    :root[data-theme="dark"] .login-welcome { background: linear-gradient(135deg, #181c2c, #111420); border-right-color: var(--line); }
    :root[data-theme="dark"] .login-brand-mark { border-color: var(--line); background: var(--panel); }
    :root[data-theme="dark"] .login-avatar { border-color: var(--line); background: #232742; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4); }
    :root[data-theme="dark"] .login-avatar::before { background: #474b85; }
    :root[data-theme="dark"] .login-avatar-face { color: #c4c1ff; }
    :root[data-theme="dark"] .login-star { color: var(--primary); }
    :root[data-theme="dark"] .login-theme-control { border-color: var(--line); background: var(--panel); color: var(--muted); }
    :root[data-theme="dark"] .login-theme-control:hover, :root[data-theme="dark"] .login-theme-control:focus-within { border-color: var(--primary); background: var(--primary-soft); color: var(--primary-dark); }
    :root[data-theme="dark"] .login-form input { border-color: var(--line); background: #111520; color: var(--ink); }
    :root[data-theme="dark"] .login-form input:focus { border-color: var(--primary); background: var(--panel); box-shadow: 0 0 0 3px var(--primary-glow); }
"""
