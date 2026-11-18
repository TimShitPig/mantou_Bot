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
    body:not(.messages-workspace) {
      --studio-canvas: #f4efe4;
      --studio-card: #fcfaf4;
      --studio-ink: #1d1b16;
      --studio-muted: #6b645a;
      --studio-border: #e3dac8;
      --studio-accent: #1c6650;
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
      --studio-sidebar-width: 232px;

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
      --primary-dark: #164f3e;
      --primary-soft: #e7efe8;
      --accent-fill: #1c6650;
      --accent-hover: #164f3e;
      --danger: #a9472f;
      --danger-bg: #f8ece7;
      --danger-line: #e3c6ba;
      --yellow: #f7f0dd;
      --yellow-ink: #85652a;
      --pink: #f7ece7;
      --pink-ink: #a0472f;

      background-color: var(--studio-canvas);
      background-image: radial-gradient(circle at 1px 1px, #211e1910 1px, transparent 0);
      background-size: 26px 26px;
      background-attachment: fixed;
    }

    /* ========== 3. 设计令牌（深色） ========== */
    :root[data-theme="dark"] body:not(.messages-workspace) {
      --studio-canvas: #141310;
      --studio-card: #1c1a16;
      --studio-ink: #f2ecdf;
      --studio-muted: #a39b8b;
      --studio-border: #332e25;
      --studio-accent: #86b79e;
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
      --muted: #a39b8b;
      --soft: #8f8676;
      --line: #332e25;
      --bg: #141310;
      --panel: #1c1a16;
      --raised: #221f19;
      --input: #221f19;
      --hover: #272319;
      --primary: #86b79e;
      --primary-dark: #a7cdb6;
      --primary-soft: #22302a;
      --accent-fill: #2a6550;
      --accent-hover: #31765d;
      --danger: #d2705a;
      --danger-bg: #33211c;
      --danger-line: #4b2f28;

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
    .studio-robot small { color: #a89f8d; }
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
      color: #8f8676;
      font-size: 11px;
      font-weight: 620;
      letter-spacing: .14em;
    }
    .studio-nav-group a {
      min-height: 39px;
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
      min-height: 36px;
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
      min-height: 36px;
      border: 1px solid var(--studio-border);
      border-radius: 7px;
      background: transparent;
      color: var(--studio-ink);
    }
    body:not(.messages-workspace) .topbar .theme-toggle-button { width: 36px; color: var(--studio-muted); }
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
    body:not(.messages-workspace) input:focus,
    body:not(.messages-workspace) select:focus,
    body:not(.messages-workspace) textarea:focus,
    body:not(.messages-workspace) [contenteditable="true"]:focus {
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

    /* ========== 13. 消息记录 ========== */
    :root body.messages-workspace {
      --bg: #f1ebdd;
      --panel: #fcfaf4;
      --raised: #f7f2e6;
      --input: #f7f2e6;
      --hover: #ece4d3;
      --line: #e3dac8;
      --ink: #1d1b16;
      --muted: #6b645a;
      --soft: #857c6d;
      --primary: #1c6650;
      --primary-dark: #164f3e;
      --primary-soft: #e7efe8;
      --accent-fill: #1c6650;
      --accent-hover: #164f3e;
      --rail: #efe8d8;
      --msg-list-bg: #f7f2e6;
      --msg-head-bg: #fcfaf4;
      --msg-composer-bg: #fcfaf4;
      --msg-chat-active-bg: #e9e1cf;
      --msg-surface: #fcfaf4;
      --msg-incoming-fill: #f6f1e4;
      --msg-file-fill: #fcfaf4;
      --msg-file-line: #e3dac8;
      --msg-bubble-line: #e9e1d0;
      --msg-self-fill: #dce9e2;
      --msg-self-bg: #dce9e2;
      --msg-self-ink: #16342a;
      --msg-self-line: #c7dccf;
      --msg-self-inset: #eaf2ec;
      --msg-self-inset-hover: #dfebe3;
      --msg-self-muted: #4f6a5c;
      --msg-self-link: #164f3e;
      --msg-link-color: #164f3e;
      --msg-link-hover: #1c6650;
      --msg-scroll-track: #ece5d5;
      --msg-scroll-thumb: #b6ab94;
      --msg-scroll-thumb-hover: #8d8168;
      background-color: var(--bg);
    }
    :root[data-theme="dark"] body.messages-workspace {
      --bg: #141310;
      --panel: #1c1a16;
      --raised: #221f19;
      --input: #221f19;
      --hover: #272319;
      --line: #332e25;
      --ink: #f2ecdf;
      --muted: #a39b8b;
      --soft: #8f8676;
      --primary: #86b79e;
      --primary-dark: #a7cdb6;
      --primary-soft: #22302a;
      --accent-fill: #2a6550;
      --accent-hover: #31765d;
      --rail: #1a1712;
      --msg-list-bg: #1a1712;
      --msg-head-bg: #1c1a16;
      --msg-composer-bg: #1c1a16;
      --msg-chat-active-bg: #2b271e;
      --msg-surface: #1c1a16;
      --msg-incoming-fill: #242019;
      --msg-file-fill: #1f1c17;
      --msg-file-line: #332e25;
      --msg-bubble-line: #2e2a22;
      --msg-self-fill: #27473a;
      --msg-self-bg: #27473a;
      --msg-self-ink: #eaf3ed;
      --msg-self-line: #33574a;
      --msg-self-inset: #2f5344;
      --msg-self-inset-hover: #38604e;
      --msg-self-muted: #c2d7cb;
      --msg-self-link: #c6e4d2;
      --msg-link-color: #a7cdb6;
      --msg-link-hover: #86b79e;
      --msg-scroll-track: #221f19;
      --msg-scroll-thumb: #6d6354;
      --msg-scroll-thumb-hover: #8d8168;
      background-color: var(--bg);
    }
    .studio-sidebar .studio-message-tools,
    body.messages-workspace .studio-robot { color: #f4eee2; }
    body.messages-workspace .msg-panel,
    body.messages-workspace .msg-list-head,
    body.messages-workspace .msg-head { border-color: var(--line); }
    body.messages-workspace .msg-btn { border-radius: 5px; }
    body.messages-workspace .msg-btn.primary { border-radius: 5px; background: var(--accent-fill); }

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
"""
