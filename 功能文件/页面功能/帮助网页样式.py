"""馒头控制台的样式资源。"""

控制台样式 = """
    :root {
      color-scheme: light;
      --ink: #1c2035;
      --ink-secondary: #484f68;
      --muted: #727a94;
      --soft: #9da6be;
      --line: #e3e6f0;
      --line-subtle: #edf0f7;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --panel-hover: #fafbfe;
      --primary: #5c54e5;
      --primary-dark: #473ecf;
      --primary-soft: #eeecfd;
      --primary-glow: rgba(92, 84, 229, 0.18);
      --mint: #e8f8f0;
      --mint-ink: #158051;
      --peach: #fff2ea;
      --peach-ink: #c25e36;
      --yellow: #fef8e7;
      --yellow-ink: #9a6f18;
      --pink: #fdf0f7;
      --pink-ink: #b84d7d;
      --danger: #ef4444;
      --danger-soft: #fef2f2;
      --shadow-xs: 0 1px 2px rgba(18, 24, 48, 0.04);
      --shadow-sm: 0 2px 8px rgba(18, 24, 48, 0.05);
      --shadow: 0 8px 24px rgba(18, 24, 48, 0.06);
      --shadow-lg: 0 16px 36px rgba(18, 24, 48, 0.09);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
      overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }
    button, input, select, textarea { font: inherit; }
    button { cursor: pointer; }

    /* 全局滚动条美化 */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(130, 140, 175, 0.28); border-radius: 999px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(130, 140, 175, 0.48); }

    /* 全局平滑过渡 */
    body, .topbar, .sidebar, .main, .console-card, .pan-card, .metric, .novel-item, .summary-card, .shortcut-card, .readonly-value, .config-group, .switch, .msg-panel, .msg-chat {
      transition: background-color .22s ease, border-color .22s ease, color .22s ease, box-shadow .22s ease, transform .16s ease;
    }

    .shell { min-height: 100vh; display: grid; grid-template-columns: 252px minmax(0, 1fr); grid-template-rows: 64px minmax(0, 1fr); grid-template-areas: "top top" "side main"; }
    .topbar { grid-area: top; display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 0 28px; background: var(--panel); border-bottom: 1px solid var(--line); z-index: 10; backdrop-filter: blur(10px); }
    .brand { display: flex; align-items: center; gap: 11px; min-width: 0; }
    .brand-mark { width: 36px; height: 36px; flex: 0 0 36px; display: grid; place-items: center; border-radius: 12px; background: linear-gradient(135deg, var(--primary-soft), #e4e2fd); color: var(--primary); font-size: 16px; font-weight: 800; box-shadow: 0 2px 8px var(--primary-glow); }
    .brand strong { font-size: 16px; font-weight: 750; letter-spacing: -.2px; }
    .version-badge { display: inline-flex; margin-left: 6px; padding: 3px 9px; border-radius: 999px; background: var(--bg-subtle, #f0f2f8); color: var(--muted); font-size: 11px; font-weight: 650; border: 1px solid var(--line-subtle, transparent); }
    .top-actions { display: flex; align-items: center; gap: 14px; }
    .theme-control { display: inline-flex; align-items: center; gap: 6px; min-height: 34px; padding: 3px 8px 3px 10px; border: 1px solid var(--line); border-radius: 9px; background: var(--panel); color: var(--muted); font-size: 11px; font-weight: 650; box-shadow: var(--shadow-xs); }
    .theme-control:hover, .theme-control:focus-within { border-color: var(--primary); background: var(--primary-soft); color: var(--primary-dark); }
    .theme-control-icon { color: var(--primary); font-size: 14px; line-height: 1; }
    .theme-control select { min-height: 26px; padding: 2px 18px 2px 3px; border: 0; border-radius: 5px; background: transparent; color: var(--ink); font-size: 11px; font-weight: 650; cursor: pointer; outline: none; }
    .theme-control select option { background: var(--panel); color: var(--ink); }
    .status-dot { display: inline-flex; align-items: center; gap: 7px; color: var(--mint-ink); font-size: 12px; font-weight: 650; padding: 4px 10px; border-radius: 999px; background: var(--mint); }
    .status-dot::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.25); }
    .admin-menu { position: relative; }
    .admin-chip { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 4px 10px 4px 5px; border: 1px solid var(--line); border-radius: 10px; background: var(--panel); color: var(--ink); font-size: 13px; font-weight: 650; box-shadow: var(--shadow-xs); }
    .admin-chip:hover, .admin-chip[aria-expanded="true"] { border-color: var(--primary); background: var(--primary-soft); }
    .admin-avatar { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: #fff; font-size: 12px; font-weight: 800; }
    #admin-name { max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .admin-chevron { color: var(--soft); font-size: 12px; }
    .admin-popover { position: absolute; z-index: 50; top: calc(100% + 8px); right: 0; width: 220px; padding: 14px 15px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); box-shadow: var(--shadow-lg); backdrop-filter: blur(12px); }
    .admin-popover[hidden] { display: none; }
    .admin-popover strong { display: block; font-size: 13px; font-weight: 700; }
    .admin-popover small { display: block; margin-top: 5px; color: var(--muted); font-size: 11px; line-height: 1.45; }
    .popover-logout { display: block; width: 100%; margin-top: 12px; padding: 8px 12px; border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 8px; background: var(--danger-soft); color: var(--danger); font-size: 12px; font-weight: 650; cursor: pointer; text-align: center; }
    .popover-logout:hover { background: #fee2e2; border-color: var(--danger); }
    .sidebar { grid-area: side; min-width: 0; background: var(--panel); border-right: 1px solid var(--line); padding: 24px 14px 18px; display: flex; flex-direction: column; gap: 22px; }
    .profile { display: grid; justify-items: center; gap: 8px; padding: 4px 0 10px; }
    .bot-avatar { position: relative; width: 72px; height: 72px; overflow: hidden; border: 4px solid var(--primary-soft); border-radius: 50%; background: linear-gradient(135deg, #e4e2fd, #c9c5fc); box-shadow: 0 6px 18px var(--primary-glow); }
    .bot-avatar::before { content: ""; position: absolute; width: 62px; height: 58px; left: 1px; top: 5px; border-radius: 50% 50% 42% 42%; background: #928ef2; }
    .bot-avatar::after { content: "✦"; position: absolute; right: 8px; top: 4px; color: #fff; font-size: 13px; }
    .avatar-face { position: absolute; left: 16px; top: 27px; z-index: 1; color: #3e3a96; font-size: 23px; letter-spacing: 5px; }
    .profile strong { font-size: 14px; font-weight: 750; }
    .online { display: inline-flex; align-items: center; gap: 5px; color: var(--mint-ink); font-size: 12px; font-weight: 600; }
    .online::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: #22c55e; }
    .nav-label { margin: 0 12px 8px; color: var(--soft); font-size: 11px; font-weight: 750; letter-spacing: .5px; }
    .nav { display: grid; gap: 5px; }
    .nav a { display: flex; align-items: center; gap: 11px; padding: 10px 14px; border-radius: 10px; color: var(--ink-secondary); font-size: 13px; font-weight: 600; text-decoration: none; position: relative; }
    .nav a:hover { background: var(--primary-soft); color: var(--primary-dark); transform: translateX(3px); }
    .nav a.active, .nav a[aria-current="true"] { background: linear-gradient(90deg, var(--primary-soft), transparent); color: var(--primary-dark); font-weight: 750; }
    .nav a.active::before, .nav a[aria-current="true"]::before { content: ""; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3.5px; border-radius: 0 4px 4px 0; background: var(--primary); }
    .nav-icon { width: 18px; color: var(--soft); text-align: center; font-size: 15px; }
    .nav a.active .nav-icon, .nav a[aria-current="true"] .nav-icon { color: var(--primary); }
    .sidebar-foot { margin-top: auto; padding: 14px 14px; border: 1px solid var(--line); border-radius: 12px; background: var(--bg); color: var(--muted); font-size: 11px; line-height: 1.6; }
    .sidebar-foot strong { display: block; margin-bottom: 4px; color: var(--ink); font-size: 13px; font-weight: 700; }
    .sidebar-foot .spark { color: var(--primary); font-size: 15px; }
    .main { grid-area: main; min-width: 0; background: var(--bg); }
    .content { width: min(1320px, calc(100% - 48px)); margin: 0 auto; padding: 34px 0 60px; }
    .page-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
    .page-heading h1 { margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -.3px; }
    .page-heading p { margin: 6px 0 0; color: var(--muted); font-size: 13px; }
    .primary-button { display: inline-flex; align-items: center; gap: 7px; min-height: 38px; border: 0; border-radius: 10px; padding: 0 16px; background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: #fff; font-size: 12px; font-weight: 700; box-shadow: 0 4px 14px var(--primary-glow); }
    .primary-button:hover { filter: brightness(1.08); transform: translateY(-1px); }
    .primary-button:active { transform: scale(0.98); }
    .console-card { margin: 0; padding: 22px 24px; background: var(--panel); border: 1px solid var(--line); border-radius: 14px; box-shadow: var(--shadow); scroll-margin-top: 80px; }
    .console-card h2 { margin: 0; font-size: 16px; font-weight: 750; }
    .card-subtitle { margin: 4px 0 18px; color: var(--muted); font-size: 12px; }
    .workspace-grid { display: grid; grid-template-columns: minmax(0, 1.62fr) minmax(310px, .96fr); align-items: start; gap: 16px; margin-top: 18px; }
    .workspace-left, .workspace-right { display: grid; gap: 16px; align-content: start; min-width: 0; }
    .profile-fields { display: grid; gap: 0; }
    .profile-field { display: grid; grid-template-columns: 112px minmax(0, 1fr); align-items: center; gap: 16px; min-height: 56px; border-bottom: 1px solid var(--line); }
    .profile-field:last-child { border-bottom: 0; }
    .profile-field > span { color: var(--ink-secondary); font-size: 13px; }
    .readonly-value { min-height: 38px; display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 9px; color: var(--ink); background: var(--bg); font-size: 13px; }
    .readonly-value small { color: var(--soft); font-size: 11px; }
    .connection-fields { display: grid; gap: 10px; }
    .connection-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 10px 0; border-bottom: 1px solid var(--line); }
    .connection-row:last-child { border-bottom: 0; }
    .connection-row > span { color: var(--ink-secondary); font-size: 12px; }
    .connection-row strong { max-width: 66%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--ink); font-size: 12px; font-weight: 650; text-align: right; }
    .status-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--line); font-size: 12px; }
    .status-item:last-child { border-bottom: 0; }
    .status-item span { color: var(--ink-secondary); }
    .status-item strong { color: var(--ink); font-weight: 650; text-align: right; }
    .status-item strong.good { color: var(--mint-ink); }
    
    /* 开关组件 */
    .switch { position: relative; width: 44px; height: 24px; flex: 0 0 auto; border: 0; border-radius: 999px; background: var(--line-strong, #cbd5e1); cursor: pointer; }
    .switch span { position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.18); transition: transform .18s cubic-bezier(.22,.8,.35,1); }
    .switch.on { background: var(--primary); }
    .switch.on span { transform: translateX(20px); }
    .switch:disabled { cursor: not-allowed; opacity: .45; }
    .switch:focus-visible { outline: 3px solid var(--primary-glow); outline-offset: 2px; }

    /* 小说平台网格 */
    .novel-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .novel-item { display: flex; align-items: center; justify-content: space-between; gap: 14px; min-height: 76px; padding: 14px 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); box-shadow: var(--shadow-xs); }
    .novel-item:hover { border-color: var(--primary); background: var(--panel-hover); transform: translateY(-2px); box-shadow: var(--shadow); }
    .novel-item.is-enabled { border-color: var(--mint-border, rgba(5, 150, 105, 0.25)); }
    .novel-item-main { display: flex; align-items: center; gap: 11px; min-width: 0; }
    .novel-badge { width: 34px; height: 34px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 10px; background: var(--primary-soft); color: var(--primary); font-size: 12px; font-weight: 800; }
    .novel-item:nth-child(3n+2) .novel-badge { background: var(--mint); color: var(--mint-ink); }
    .novel-item:nth-child(3n) .novel-badge { background: var(--peach); color: var(--peach-ink); }
    .novel-item-title strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 700; }
    .novel-item-copy small { display: block; margin-top: 4px; color: var(--muted); font-size: 10.5px; }

    /* 网盘与设置 */
    .pan-tabs { display: flex; gap: 8px; margin: 0 24px 16px; padding: 4px; border: 1px solid var(--line); border-radius: 11px; background: var(--bg); }
    .pan-tab { flex: 1 1 0; min-width: 0; min-height: 38px; padding: 0 14px; border: 0; border-radius: 8px; background: transparent; color: var(--muted); font-size: 12px; font-weight: 700; }
    .pan-tab:hover { color: var(--primary-dark); background: var(--panel); }
    .pan-tab.active { color: var(--primary); background: var(--panel); box-shadow: var(--shadow-sm); }
    .pan-card { padding: 20px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); box-shadow: var(--shadow-xs); }
    .pan-card.active { border-color: var(--primary); box-shadow: 0 0 0 2px var(--primary-glow), var(--shadow); }
    .tag { display: inline-flex; padding: 3px 8px; border-radius: 999px; font-size: 10.5px; font-weight: 750; }
    .tag.active { background: var(--primary-soft); color: var(--primary-dark); }
    .tag.ok { background: var(--mint); color: var(--mint-ink); }
    .tag.off { background: var(--bg-subtle, #f0f2f8); color: var(--muted); }
    .outline-button { min-height: 36px; padding: 0 15px; border: 1px solid var(--line); border-radius: 9px; background: var(--panel); color: var(--primary); font-size: 12px; font-weight: 700; box-shadow: var(--shadow-xs); }
    .outline-button:hover { border-color: var(--primary); background: var(--primary-soft); }
    .outline-button:active { transform: scale(0.98); }
    .config-field input, .config-field textarea, .config-field select, .account-add input, .group-account input, .pan-directory input { width: 100%; min-height: 38px; padding: 8px 11px; border: 1px solid var(--line); border-radius: 9px; background: var(--panel); color: var(--ink); outline: none; }
    .config-field input:focus, .config-field textarea:focus, .config-field select:focus, .account-add input:focus, .group-account input:focus, .pan-directory input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }
    .toast { position: fixed; right: 24px; bottom: 24px; z-index: 2000; transform: translateY(12px); opacity: 0; pointer-events: none; padding: 12px 18px; border-radius: 10px; background: #1e2238; color: #fff; font-size: 12.5px; font-weight: 650; box-shadow: var(--shadow-lg); backdrop-filter: blur(8px); transition: opacity .2s, transform .2s; }
    .toast.show { transform: translateY(0); opacity: 1; }

    /* 桌面端独立滚动 */
    @media (min-width: 761px) {
      html, body { height: 100%; }
      body { overflow: hidden; }
      .shell { height: 100vh; min-height: 100vh; overflow: hidden; }
      .sidebar { position: sticky; top: 0; align-self: start; height: calc(100vh - 64px); min-height: 0; overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
      .main { min-height: 0; overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain; }
    }

    /* ===== 暗色/黑夜模式 (Dark Theme) ===== */
    :root[data-theme="dark"] {
      color-scheme: dark;
      --ink: #f0f2fa;
      --ink-secondary: #adb4c8;
      --muted: #828ba3;
      --soft: #5b647d;
      --line: #262c3e;
      --line-subtle: #1c2130;
      --bg: #0d1019;
      --panel: #161a26;
      --panel-hover: #1c2132;
      --primary: #7c75ff;
      --primary-dark: #9892ff;
      --primary-soft: #232742;
      --primary-glow: rgba(124, 117, 255, 0.22);
      --mint: #0e2a20;
      --mint-ink: #34d399;
      --peach: #321d14;
      --peach-ink: #fb923c;
      --yellow: #2f2510;
      --yellow-ink: #facc15;
      --pink: #321827;
      --pink-ink: #f472b6;
      --danger: #f87171;
      --danger-soft: #321619;
      --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.35);
      --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.4);
      --shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
      --shadow-lg: 0 16px 36px rgba(0, 0, 0, 0.55);
    }
    :root[data-theme="dark"] body { background: var(--bg); color: var(--ink); }
    :root[data-theme="dark"] .topbar { background: var(--panel); border-bottom-color: var(--line); }
    :root[data-theme="dark"] .sidebar { background: var(--panel); border-right-color: var(--line); }
    :root[data-theme="dark"] .version-badge { background: #1f2536; color: var(--muted); }
    :root[data-theme="dark"] .theme-control { border-color: var(--line); background: var(--panel); color: var(--muted); }
    :root[data-theme="dark"] .theme-control:hover, :root[data-theme="dark"] .theme-control:focus-within { border-color: var(--primary); background: var(--primary-soft); color: var(--primary-dark); }
    :root[data-theme="dark"] .admin-chip { border-color: var(--line); background: var(--panel); }
    :root[data-theme="dark"] .admin-chip:hover, :root[data-theme="dark"] .admin-chip[aria-expanded="true"] { border-color: var(--primary); background: var(--primary-soft); }
    :root[data-theme="dark"] .admin-popover { background: var(--panel); border-color: var(--line); }
    :root[data-theme="dark"] .sidebar-foot { border-color: var(--line); background: #111520; }
    :root[data-theme="dark"] .console-card { background: var(--panel); border-color: var(--line); }
    :root[data-theme="dark"] .readonly-value { border-color: var(--line); background: #111520; }
    :root[data-theme="dark"] .novel-item { border-color: var(--line); background: var(--panel); }
    :root[data-theme="dark"] .novel-item:hover { border-color: var(--primary); background: var(--panel-hover); }
    :root[data-theme="dark"] .pan-tabs { border-color: var(--line); background: #111520; }
    :root[data-theme="dark"] .pan-tab { color: var(--muted); }
    :root[data-theme="dark"] .pan-tab:hover { background: #1f2536; color: var(--ink); }
    :root[data-theme="dark"] .pan-tab.active { background: var(--panel); color: var(--primary); }
    :root[data-theme="dark"] .pan-card { background: var(--panel); border-color: var(--line); }
    :root[data-theme="dark"] .tag.off { background: #1f2536; color: var(--muted); }
    :root[data-theme="dark"] .outline-button { border-color: var(--line); background: var(--panel); color: var(--primary); }
    :root[data-theme="dark"] .outline-button:hover { border-color: var(--primary); background: var(--primary-soft); }
    :root[data-theme="dark"] .config-group { border-color: var(--line); background: #121622; }
    :root[data-theme="dark"] .config-field input, :root[data-theme="dark"] .config-field textarea, :root[data-theme="dark"] .config-field select, :root[data-theme="dark"] .account-add input, :root[data-theme="dark"] .group-account input, :root[data-theme="dark"] .pan-directory input { border-color: var(--line); background: var(--panel); color: var(--ink); }
    :root[data-theme="dark"] .config-field input:focus, :root[data-theme="dark"] .config-field textarea:focus, :root[data-theme="dark"] .config-field select:focus, :root[data-theme="dark"] .account-add input:focus, :root[data-theme="dark"] .group-account input:focus, :root[data-theme="dark"] .pan-directory input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }
    :root[data-theme="dark"] .toast { background: #262c3e; border: 1px solid var(--line); }
    :root[data-theme="dark"] ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.16); }
    :root[data-theme="dark"] ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.32); }
"""

