"""馒头工作台新版外观覆盖层：纸感书房 · 竹青。

只改视觉，不改结构与脚本：本模块追加在样式链末尾，
通过覆盖设计令牌与组件外观，让控制台、消息记录、登录页统一换上新版气质。
"""

新版外观样式 = """
    /* ========== 1. 字体与基础 ========== */
    :root {
      --brand-serif: "Noto Serif SC", "Source Han Serif SC", "Songti SC", "STSong", "SimSun", Georgia, serif;
      --brand-sans: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB",
                    "Microsoft YaHei", "Segoe UI", system-ui, sans-serif;
      --paper-line: #e3dac8;
      --paper-gold: #8a6a2f;
      --paper-clay: #a9472f;
      --paper-ink-soft: #4b453c;
    }
    html body,
    html body.messages-workspace { font-family: var(--brand-sans); }
    html body { -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }

    /* ========== 2. 设计令牌（浅色） ========== */
    body,
    body:not(.messages-workspace) {
      --studio-canvas: #f4efe4;
      --studio-card: #fcfaf4;
      --studio-ink: #1d1b16;
      --studio-muted: #6b645a;
      --studio-border: #e3dac8;
      --studio-accent: #1c6650;
      --studio-accent-strong: #164f3e;
      --studio-button-fill: #1c6650;
      --studio-button-hover: #164f3e;
      --studio-accent-soft: #e7efe8;
      --studio-soft: #f1ebde;
      --studio-peach: #f3e7d5;
      --studio-peach-ink: #7a5a32;
      --studio-mint: #e8f0e6;
      --studio-mint-ink: #2f6a52;
      --studio-hover: #ece4d3;
      --studio-wash: #f8f3e6;
      --studio-shadow: 0 1px 2px #30281b05, 0 6px 20px #30281b04;
      --studio-float-shadow: 0 12px 30px #2a241812;

      --ink: #1d1b16;
      --muted: #6b645a;
      --soft: #857c6d;
      --line: #e3dac8;
      --bg: #f4efe4;
      --panel: #fcfaf4;
      --raised: #f7f2e6;
      --input: #f7f2e6;
      --hover: #ece4d3;
      --primary: #1c6650;
      --primary-dark: var(--studio-accent-strong);
      --primary-soft: #e7efe8;
      --accent-fill: var(--studio-button-fill);
      --accent-hover: var(--studio-button-hover);
      --danger: #a9472f;
      --danger-bg: #f8ece7;
      --danger-line: #e3c6ba;
      --yellow: #f7f0dd;
      --yellow-ink: #85652a;
      --pink: #f7ece7;
      --pink-ink: #a0472f;
    }
    body:not(.messages-workspace) {
      --studio-sidebar-width: 232px;
      background-color: var(--studio-canvas);
      background-image: radial-gradient(circle at 1px 1px, #211e1910 1px, transparent 0);
      background-size: 26px 26px;
      background-attachment: fixed;
    }

    /* ========== 3. 设计令牌（深色） ========== */
    :root[data-theme="dark"] body,
    :root[data-theme="dark"] body:not(.messages-workspace) {
      --studio-canvas: #141310;
      --studio-card: #1c1a16;
      --studio-ink: #f2ecdf;
      --studio-muted: #b0a99c;
      --studio-border: #332e25;
      --studio-accent: #86b79e;
      --studio-accent-strong: #a7cdb6;
      --studio-button-fill: #2a6550;
      --studio-button-hover: #31765d;
      --studio-accent-soft: #22302a;
      --studio-soft: #221f19;
      --studio-peach: #2e251b;
      --studio-peach-ink: #d9b98d;
      --studio-mint: #1f2b24;
      --studio-mint-ink: #9cc7af;
      --studio-hover: #272319;
      --studio-wash: #1b1813;
      --studio-shadow: inset 0 1px 0 #ffffff03, 0 3px 12px #00000018;
      --studio-float-shadow: 0 14px 34px #00000059;
      --paper-line: #332e25;
      --paper-gold: #c9a967;
      --paper-clay: #d2705a;
      --paper-ink-soft: #cdc5b4;

      --ink: #f2ecdf;
      --muted: var(--studio-muted);
      --soft: #a69d8d;
      --line: #332e25;
      --bg: #141310;
      --panel: #1c1a16;
      --raised: #221f19;
      --input: #221f19;
      --hover: #272319;
      --primary: #86b79e;
      --primary-dark: var(--studio-accent-strong);
      --primary-soft: #22302a;
      --accent-fill: var(--studio-button-fill);
      --accent-hover: var(--studio-button-hover);
      --danger: #d2705a;
      --danger-bg: #33211c;
      --danger-line: #4b2f28;
    }
    :root[data-theme="dark"] body:not(.messages-workspace) {
      background-color: var(--studio-canvas);
      background-image: radial-gradient(circle at 1px 1px, #ffffff0b 1px, transparent 0);
      background-size: 26px 26px;
    }

    /* ========== 4. 侧栏：墨色书脊 ========== */
    .shell > .studio-sidebar:not([hidden]) {
      border: 1px solid #2b2721;
      border-radius: 12px;
      background: #211e19;
      padding: 15px 13px;
      gap: 16px;
      box-shadow: 0 18px 40px #211e1914;
    }
    :root[data-theme="dark"] .shell > .studio-sidebar:not([hidden]) {
      border-color: #332e25;
      background: #1b1813;
      box-shadow: none;
    }
    .studio-robot {
      background: #ffffff0a;
      border: 1px solid #ffffff12;
      border-radius: 9px;
      padding: 11px;
      gap: 9px;
    }
    .studio-robot strong { color: #f4eee2; font-weight: 640; }
    .studio-robot small { color: #b0a99c; }
    .studio-bot-avatar {
      border: 1px solid #4a4336;
      border-radius: 8px;
      background: #2a2620;
      color: #b9d6c4;
    }
    .studio-nav { gap: 13px; padding: 0; }
    .studio-nav-group { gap: 3px; }
    .studio-nav-group > p {
      margin: 0 0 6px;
      padding: 0 8px;
      color: #a69d8d;
      font-size: 11px;
      font-weight: 620;
      letter-spacing: .14em;
    }
    .studio-nav-group a {
      min-height: 44px;
      padding: 7px 8px;
      border-radius: 7px;
      color: #ded6c6;
      font-weight: 560;
      font-size: 13px;
      transition: background .16s ease, color .16s ease;
    }
    .studio-nav-group a:hover { background: #ffffff0f; color: #fff; }
    .studio-nav-group a[aria-current="page"] {
      background: #ffffff0a;
      color: #ffffff;
      box-shadow: inset 2px 0 0 #7fb59b;
    }
    .studio-nav-icon {
      width: 23px;
      height: 23px;
      border-radius: 5px;
      background: #ffffff0d;
      color: #a9c7b6;
    }
    .studio-nav-group:nth-child(2) .studio-nav-icon { background: #ffffff0d; color: #dcc094; }
    .studio-nav-group:nth-child(3) .studio-nav-icon { background: #ffffff0d; color: #9fc0ad; }
    .studio-nav-icon svg { width: 15px; height: 15px; }
    .studio-exit {
      min-height: 44px;
      border: 1px solid #ffffff1c;
      border-radius: 7px;
      background: transparent;
      color: #b9b0a0;
      font-weight: 560;
      font-size: 12.5px;
    }
    .studio-exit:hover { background: #ffffff0f; color: #fff; }
    .studio-message-tools button {
      border: 1px solid #ffffff1c;
      border-radius: 6px;
      background: transparent;
      color: #b9b0a0;
    }
    .studio-message-tools button:hover { background: #ffffff0f; color: #fff; }
    .studio-sidebar :focus-visible { outline: 2px solid #7fb59b; outline-offset: 2px; }

    /* ========== 5. 顶栏 ========== */
    body:not(.messages-workspace) .shell > .topbar { min-height: 56px; padding: 2px 0 12px; gap: 12px; }
    body:not(.messages-workspace) .topbar .brand-mark {
      width: 38px;
      height: 38px;
      flex-basis: 38px;
      border: 1px solid var(--studio-border);
      border-radius: 50%;
      background: #fcfaf4;
      color: #1d1b16;
    }
    :root[data-theme="dark"] body:not(.messages-workspace) .topbar .brand-mark {
      background: #221f19;
      color: #efe7d8;
    }
    body:not(.messages-workspace) .topbar .brand-mark svg { width: 21px; height: 21px; }
    body:not(.messages-workspace) .topbar .studio-brand-title {
      font-family: var(--brand-serif);
      font-size: clamp(19px, 2vw, 25px);
      font-weight: 700;
      letter-spacing: .04em;
    }
    body:not(.messages-workspace) .topbar .version-badge {
      border-radius: 4px;
      background: transparent;
      color: var(--studio-muted);
      font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
      font-size: 10.5px;
      letter-spacing: .02em;
    }
    body:not(.messages-workspace) .topbar .theme-toggle-button,
    body:not(.messages-workspace) .topbar .admin-chip {
      min-height: 44px;
      border: 1px solid var(--studio-border);
      border-radius: 7px;
      background: transparent;
      color: var(--studio-ink);
    }
    body:not(.messages-workspace) .topbar .theme-toggle-button { width: 44px; color: var(--studio-muted); }
    body:not(.messages-workspace) .topbar .theme-toggle-button:hover { color: var(--studio-accent); }
    body:not(.messages-workspace) .topbar .admin-avatar {
      border-radius: 4px;
      background: var(--studio-accent-soft);
      color: var(--studio-accent);
      font-size: 11px;
    }
    body:not(.messages-workspace) .topbar .admin-popover {
      border-radius: 9px;
      background: var(--studio-card);
      box-shadow: var(--studio-float-shadow);
    }

    /* ========== 6. 页面标题：不用卡片 ========== */
    body:not(.messages-workspace) #console-workspace > .page-heading {
      margin: 0 0 22px;
      padding: 0 0 14px;
      border: 0;
      border-bottom: 1px solid var(--studio-border);
      border-radius: 0;
      background: transparent;
      align-items: flex-end;
    }
    body:not(.messages-workspace) #console-workspace > .page-heading h1 {
      font-family: var(--brand-serif);
      font-size: clamp(24px, 2.4vw, 32px);
      font-weight: 700;
      letter-spacing: .02em;
      line-height: 1.2;
    }
    body:not(.messages-workspace) #console-workspace > .page-heading .page-kicker {
      margin: 0 0 7px;
      color: var(--studio-muted);
      font-size: 10.5px;
      font-weight: 600;
      letter-spacing: .16em;
    }
    body:not(.messages-workspace) #console-workspace > .page-heading #page-subtitle {
      margin: 7px 0 0;
      max-width: 62ch;
      color: var(--studio-muted);
      font-size: 12.5px;
      line-height: 1.7;
    }
    body:not(.messages-workspace) .updated-label {
      border: 1px solid var(--studio-border);
      border-radius: 4px;
      background: transparent;
      color: var(--studio-muted);
      font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
      font-size: 10.5px;
      padding: 3px 7px;
    }

    /* ========== 7. 卡片与分区标题 ========== */
    .studio-card {
      padding: clamp(16px, 2.1vw, 24px);
      border: 1px solid var(--studio-border);
      border-radius: 12px;
      background: var(--studio-card);
      box-shadow: var(--studio-shadow);
    }
    .studio-kicker + h2,
    .studio-service-head h2 {
      font-family: var(--brand-serif);
      font-weight: 700;
      letter-spacing: .02em;
    }
    .studio-kicker {
      display: block;
      margin: 0 0 4px;
      color: var(--studio-muted);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: .18em;
    }
    #page-dashboard .studio-kicker { display: none; }

    /* ========== 8. 总览：hero 与服务目录 ========== */
    .studio-book-art {
      display: block;
      max-width: 168px;
      margin-left: auto;
      opacity: .62;
      filter: grayscale(.5) sepia(.34) saturate(.7) hue-rotate(-6deg);
    }
    :root[data-theme="dark"] .studio-book-art {
      opacity: .5;
      filter: grayscale(.72) sepia(.18) saturate(.55) brightness(.95);
    }
    .studio-primary {
      min-height: 37px;
      margin-top: 17px;
      padding: 7px 15px;
      border-radius: 6px;
      background: var(--accent-fill);
      color: #fff;
      font-size: 12.5px;
      font-weight: 600;
      letter-spacing: .04em;
    }
    .studio-primary:hover { background: var(--accent-hover); }
    .studio-service-icon {
      width: 32px;
      height: 32px;
      border: 1px solid var(--studio-border);
      border-radius: 8px;
      background: transparent;
      color: var(--studio-accent);
    }
    .studio-service-icon svg { width: 17px; height: 17px; }

    /* ========== 9. 控件 ========== */
    :root body:not(.messages-workspace) .primary-button {
      border-radius: 8px;
      background: var(--accent-fill);
      color: #fff;
      font-weight: 600;
      letter-spacing: .03em;
    }
    :root body:not(.messages-workspace) .primary-button:hover:not(:disabled) { background: var(--accent-hover); }
    :root body:not(.messages-workspace) .outline-button,
    body:not(.messages-workspace) .outline-button {
      border: 1px solid var(--studio-border);
      border-radius: 8px;
      background: transparent;
      color: var(--studio-ink);
      font-weight: 560;
    }
    body:not(.messages-workspace) .outline-button:hover:not(:disabled) { border-color: var(--studio-accent); color: var(--studio-accent); background: var(--studio-accent-soft); }
    body:not(.messages-workspace) :is(.primary-button, .outline-button):disabled { cursor: default; opacity: .5; }
    body:not(.messages-workspace) .switch {
      width: 40px;
      height: 22px;
      background: #ddd3bf;
      border-radius: 999px;
    }
    :root[data-theme="dark"] body:not(.messages-workspace) .switch { background: #3a342a; }
    body:not(.messages-workspace) .switch span { width: 16px; height: 16px; border-radius: 50%; box-shadow: none; }
    body:not(.messages-workspace) .switch.on { background: var(--accent-fill); }
    body:not(.messages-workspace) .switch.on span { transform: translateX(18px); }
    body:not(.messages-workspace) input,
    body:not(.messages-workspace) select,
    body:not(.messages-workspace) textarea {
      border-color: var(--studio-border);
      border-radius: 8px;
      background: var(--studio-soft);
    }
    body:not(.messages-workspace) input:focus-visible,
    body:not(.messages-workspace) select:focus-visible,
    body:not(.messages-workspace) textarea:focus-visible,
    body:not(.messages-workspace) [contenteditable="true"]:focus-visible {
      outline: 2px solid color-mix(in srgb, var(--studio-accent) 30%, transparent);
      outline-offset: 1px;
    }
    body:not(.messages-workspace) ::selection { color: var(--studio-ink); background: #1c665024; }
    body:not(.messages-workspace) .notice {
      border: 1px solid var(--studio-border);
      border-radius: 6px;
      background: var(--studio-wash);
      color: var(--studio-ink);
    }
    .bot-picker-error {
      border: 1px solid var(--danger-line);
      border-left: 1px solid var(--danger-line);
      border-radius: 6px;
      background: var(--danger-bg);
      color: var(--danger);
      font-size: 12.5px;
    }
    .toast {
      border: 1px solid var(--studio-border);
      border-radius: 6px;
      background: #211e19;
      color: #f4eee2;
      box-shadow: 0 12px 30px #211e1926;
      font-size: 12.5px;
    }
    :root[data-theme="dark"] .toast { background: #2a251d; color: #f4eee2; }

    /* ========== 10. 业务页 ========== */
    .studio-service-head { border-bottom: 1px solid var(--studio-border); padding-bottom: 12px; }
    .studio-bot-workspace,
    .studio-novel-control,
    .studio-pan-card,
    .pan-card,
    .pan-object-card {
      border: 1px solid var(--studio-border);
      border-radius: 12px;
      background: var(--studio-card);
      box-shadow: var(--studio-shadow);
    }
    .studio-bot-identity { border-radius: 8px; }
    .studio-bot-kicker { color: var(--studio-muted); letter-spacing: .14em; }
    .pan-tab,
    .pan-tabs button {
      border: 1px solid var(--studio-border);
      border-radius: 6px;
      background: transparent;
      box-shadow: none;
    }
    .pan-tab.active {
      border-color: #1c665061;
      background: var(--studio-accent-soft);
      box-shadow: none;
    }
    .pan-tab-mark { border-radius: 5px; }
    .novel-grid,
    .studio-novel-grid { gap: 8px; }
    .novel-item,
    .novel-card {
      border: 1px solid var(--studio-border);
      border-radius: 7px;
      background: var(--studio-card);
      box-shadow: none;
    }
    .novel-item:hover,
    .novel-card:hover { border-color: #1c665040; }
    .novel-state-pill {
      border: 1px solid var(--studio-border);
      border-radius: 999px;
      background: transparent;
      font-size: 10.5px;
      font-weight: 500;
    }
    .novel-state-pill.is-off { color: var(--studio-muted); }

    /* ========== 11. 系统页 ========== */
    .studio-system-icon,
    .studio-system-icon.is-mint,
    .studio-system-icon.is-peach {
      border: 1px solid var(--studio-border);
      border-radius: 8px;
      background: transparent;
      color: var(--studio-accent);
    }
    .studio-system-icon.is-peach { color: var(--paper-gold); }
    .studio-system-icon.is-mint { color: var(--studio-accent); }
    .studio-system-card,
    .studio-resource,
    .studio-command-card,
    .studio-help-intro {
      border-radius: 10px;
      background: var(--studio-card);
      box-shadow: none;
    }
    .studio-system-link { color: var(--studio-accent); font-weight: 600; }
    .studio-system-state { border-radius: 999px; font-weight: 500; }
    .studio-system-split,
    .studio-resource-grid { gap: 12px; }
    .studio-help-art { opacity: .6; filter: grayscale(.3) sepia(.12); }
    .studio-commands { border-radius: 8px; }

    /* ========== 12. 选择机器人页 ========== */
    .studio-picker-banner {
      border: 1px solid var(--studio-border);
      border-radius: 12px;
      background: var(--studio-wash);
      box-shadow: none;
    }
    .studio-picker-banner h1 {
      font-family: var(--brand-serif);
      font-weight: 700;
      letter-spacing: .03em;
    }
    .studio-picker .bot-selector-item {
      border: 1px solid var(--studio-border);
      border-radius: 8px;
      background: var(--studio-card);
      box-shadow: none;
      transition: border-color .16s ease, transform .16s ease;
    }
    .studio-picker .bot-selector-item:hover { border-color: var(--studio-accent); transform: translateY(-1px); }
    .studio-picker .bot-selector-avatar { border-radius: 8px; background: var(--studio-soft); }
    .studio-picker .bot-selector-copy strong { font-family: var(--brand-serif); font-weight: 700; }
    .studio-picker .bot-selector-stat {
      border: 1px solid var(--studio-border);
      border-radius: 6px;
      background: transparent;
    }

    /* 消息配色与组件外观由独立的消息记录皮肤维护。 */

    /* ========== 14. 登录页 ========== */
    :root {
      --canvas: #f4efe4;
      --surface: #fcfaf4;
      --stage: #f8f3e6;
      --ink: #1d1b16;
      --muted: #6b645a;
      --line: #e3dac8;
      --field-line: #d9cfbb;
      --field: #f7f2e6;
      --accent: #1c6650;
      --button-fill: #1c6650;
      --button-hover: #164f3e;
      --on-accent: #fff;
      --accent-soft: #e7efe8;
      --peach: #f3e7d5;
      --peach-ink: #7a5a32;
      --danger: #a9472f;
      --focus: #1c66502b;
      --shadow: 0 10px 26px #2a24181a;
      --art-line: #7c6a4a;
      --art-paper: #fbf5e7;
      --art-lavender: #adc6b4;
      --art-peach: #ebc9a8;
      --art-blush: #d89a8c;
      --art-shadow: #b7a98c55;
    }
    :root[data-theme="dark"] {
      --canvas: #141310;
      --surface: #1c1a16;
      --stage: #1b1813;
      --ink: #f2ecdf;
      --muted: #a39b8b;
      --line: #332e25;
      --field-line: #3a342a;
      --field: #221f19;
      --accent: #86b79e;
      --button-fill: #2a6550;
      --button-hover: #31765d;
      --on-accent: #f6fbf8;
      --accent-soft: #22302a;
      --peach: #2e251b;
      --peach-ink: #d9b98d;
      --danger: #d2705a;
      --focus: #86b79e33;
      --shadow: 0 14px 34px #00000059;
      --art-line: #b3a281;
      --art-paper: #2a251d;
      --art-lavender: #7fa993;
      --art-peach: #c9a276;
      --art-blush: #b8786a;
      --art-shadow: #00000055;
    }
    .login-page {
      background-image: radial-gradient(circle at 1px 1px, #211e1910 1px, transparent 0);
      background-size: 26px 26px;
    }
    :root[data-theme="dark"] .login-page {
      background-image: radial-gradient(circle at 1px 1px, #ffffff0b 1px, transparent 0);
    }
    .login-panel {
      border: 1px solid var(--line);
      border-radius: 10px;
      box-shadow: 0 24px 60px #2a241814;
    }
    :root[data-theme="dark"] .login-panel { box-shadow: 0 24px 60px #00000047; }
    .login-intro h1, .login-intro strong, .login-brand strong {
      font-family: var(--brand-serif);
      font-weight: 700;
      letter-spacing: .03em;
    }
    .login-field-control { border-radius: 6px; }
    .login-button { border-radius: 6px; font-weight: 600; letter-spacing: .04em; }
    .login-brand-mark { border-radius: 50%; }
    .login-kicker { color: var(--muted); letter-spacing: .16em; font-weight: 600; }
    .login-theme-control { border-radius: 6px; }
    .login-note { color: var(--muted); }

    /* ========== 15. 响应式与动效 ========== */
    @media (max-width: 760px) {
      .shell > .studio-sidebar:not([hidden]) { border-radius: 10px; padding: 9px; }
      .studio-nav-group > p { letter-spacing: .1em; }
      .studio-nav-group a { border-radius: 5px; }
      body:not(.messages-workspace) #console-workspace > .page-heading { margin-bottom: 14px; padding-bottom: 10px; }
    }
    @media (prefers-reduced-motion: reduce) {
      * { transition-duration: .01ms !important; animation-duration: .01ms !important; }
    }

    /* ========== 16. 竹青封面：把总览做成一张有记忆点的工作札 ========== */
    /* 导航保持深色书脊，当前页用暖金定位，不依赖轻微的背景色差。 */
    body:not(.messages-workspace) #console-sidebar .studio-nav-group a[aria-current="page"] {
      background: #ffffff0d;
      color: #fffaf0;
      box-shadow: inset 3px 0 0 #dfbd72;
    }
    body:not(.messages-workspace) #console-sidebar .studio-nav-group a[aria-current="page"] .studio-nav-icon {
      background: #dfbd721c;
      color: #f0d99f;
    }
    body:not(.messages-workspace) #console-sidebar .studio-nav-group a:focus-visible {
      outline-color: #f0d99f;
    }

    /* 问候卡承担品牌封面：墨竹绿、暖金数字、克制的纸雕圆环。 */
    body:not(.messages-workspace) #page-dashboard .dash-greet {
      position: relative;
      isolation: isolate;
      overflow: hidden;
      border-color: #355d48;
      background: linear-gradient(128deg, #173a2d 0%, #1c4937 62%, #285642 100%);
      color: #f5f1e6;
      box-shadow: 0 16px 36px #173a2d20;
    }
    body:not(.messages-workspace) #page-dashboard .dash-greet::after {
      position: absolute;
      z-index: -1;
      top: -176px;
      right: -74px;
      width: 330px;
      height: 330px;
      border: 1px solid #ffffff24;
      border-radius: 50%;
      box-shadow: 0 0 0 34px #ffffff0b, 0 0 0 72px #ffffff08;
      content: "";
      pointer-events: none;
    }
    body:not(.messages-workspace) #page-dashboard .dash-greet > * { position: relative; z-index: 1; }
    body:not(.messages-workspace) #page-dashboard .dash-greet .dash-greet-line { color: #e6d7ad; }
    body:not(.messages-workspace) #page-dashboard .dash-greet .dash-dot {
      background: #e5c57d;
      box-shadow: 0 0 0 4px #e5c57d24;
    }
    body:not(.messages-workspace) #page-dashboard .dash-greet .dash-greet-title { color: #fffaf0; }
    body:not(.messages-workspace) #page-dashboard .dash-greet .dash-greet-sub { color: #d5dfd4; }
    body:not(.messages-workspace) #page-dashboard .dash-greet .dash-metrics { border-color: #ffffff36; }
    body:not(.messages-workspace) #page-dashboard .dash-greet .dash-metric { border-color: #ffffff35; }
    body:not(.messages-workspace) #page-dashboard .dash-greet .dash-metric strong { color: #f0d28d; }
    body:not(.messages-workspace) #page-dashboard .dash-greet .dash-metric span { color: #d2ddd2; }
    body:not(.messages-workspace) #page-dashboard .dash-greet .studio-primary {
      border: 1px solid #f2d891;
      background: #e5c57d;
      color: #20392c;
      box-shadow: none;
    }
    body:not(.messages-workspace) #page-dashboard .dash-greet .studio-primary:hover {
      background: #f0d593;
      color: #173226;
    }
    body:not(.messages-workspace) #page-dashboard .dash-greet .outline-button {
      border-color: #ffffff63;
      background: #ffffff0b;
      color: #fffaf0;
    }
    body:not(.messages-workspace) #page-dashboard .dash-greet .outline-button:hover {
      border-color: #fffaf0;
      background: #ffffff19;
    }

    /* 快照换成暖纸色，和封面形成明暗对照；暗色主题独立反转。 */
    body:not(.messages-workspace) #page-dashboard .dash-snap {
      --snapshot-bg: #eee7d6;
      --snapshot-border: #d4c8aa;
      --snapshot-divider: #756a5036;
      --snapshot-heading: #314d3e;
      --snapshot-label: #625b4e;
      --snapshot-value: #202b23;
      --snapshot-accent: #76591d;
      --snapshot-positive: #1b6349;
      border-radius: 12px;
      box-shadow: 0 12px 28px #30281b12;
    }
    :root[data-theme="dark"] body:not(.messages-workspace) #page-dashboard .dash-snap {
      --snapshot-bg: #1b2922;
      --snapshot-border: #3d5646;
      --snapshot-divider: #ffffff2b;
      --snapshot-heading: #ead59e;
      --snapshot-label: #c0c8bd;
      --snapshot-value: #f2efe6;
      --snapshot-accent: #c5d8aa;
      --snapshot-positive: #b8dabb;
      box-shadow: none;
    }
    body:not(.messages-workspace) #page-dashboard .dash-snap-list dd { font-weight: 650; }

    /* 服务目录像一页编目：暖金编号、清晰的整行焦点和不移位的反馈。 */
    body:not(.messages-workspace) #page-dashboard .dash-biz-index {
      display: grid;
      place-items: center;
      width: 30px;
      height: 30px;
      border: 1px solid #d8c89f;
      border-radius: 8px;
      background: #f3ebd8;
      color: #735820;
      font-size: 11px;
      font-weight: 750;
    }
    :root[data-theme="dark"] body:not(.messages-workspace) #page-dashboard .dash-biz-index {
      border-color: #594a2b;
      background: #30291d;
      color: #e4ca8b;
    }
    body:not(.messages-workspace) #page-dashboard .dash-biz-row {
      border-radius: 8px;
      transition: background .16s ease, box-shadow .16s ease;
    }
    body:not(.messages-workspace) #page-dashboard .dash-biz-row:hover {
      background: #f3eedf;
      box-shadow: inset 3px 0 0 #1c6650;
    }
    :root[data-theme="dark"] body:not(.messages-workspace) #page-dashboard .dash-biz-row:hover {
      background: #242d24;
      box-shadow: inset 3px 0 0 #86b79e;
    }
    body:not(.messages-workspace) #page-dashboard .dash-biz-row:focus-visible { outline-offset: 3px; }
    body:not(.messages-workspace) #page-dashboard .dash-biz-row-arrow { transition: color .16s ease, background .16s ease, border-color .16s ease; }

    @media (max-width: 640px) {
      body:not(.messages-workspace) #page-dashboard .dash-greet { padding: 22px 18px; }
      body:not(.messages-workspace) #page-dashboard .dash-greet::after { top: -205px; right: -205px; }
      body:not(.messages-workspace) #page-dashboard .dash-greet .dash-metrics { gap: 8px; }
      body:not(.messages-workspace) #page-dashboard .dash-greet .dash-metric { padding-right: 7px; }
      body:not(.messages-workspace) #page-dashboard .dash-greet .dash-metric span { font-size: 11px; letter-spacing: .03em; }
      body:not(.messages-workspace) #page-dashboard .dash-greet .dash-actions { gap: 8px; }
    }
    @media (prefers-reduced-motion: reduce) {
      body:not(.messages-workspace) #page-dashboard .dash-biz-row,
      body:not(.messages-workspace) #page-dashboard .dash-biz-row-arrow { transition: none; }
    }
"""
