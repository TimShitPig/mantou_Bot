"""帮助网页登录页样式。"""

登录页样式 = """
    :root {
      color-scheme: light;
      --canvas: #f6f5f8;
      --surface: #ffffff;
      --stage: #f5f3f8;
      --ink: #282632;
      --muted: #696574;
      --line: #e6e3eb;
      --field-line: #d4cedf;
      --field: #f5f3f8;
      --accent: #6554b2;
      --button-fill: #6554b2;
      --button-hover: #54439b;
      --on-accent: #fff;
      --accent-soft: #eeeaf8;
      --peach: #f8eee5;
      --peach-ink: #865d40;
      --danger: #a52649;
      --focus: #6554b22b;
      --shadow: 0 6px 22px #2826320a;
      --art-line: #8d77a5;
      --art-paper: #fff9ee;
      --art-lavender: #d3c3ed;
      --art-peach: #ffdec8;
      --art-blush: #efafba;
      --art-shadow: #bcabda55;
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      --canvas: #19171f;
      --surface: #24212c;
      --stage: #2b2735;
      --ink: #eeeaf3;
      --muted: #b1aabc;
      --line: #3d3747;
      --field-line: #595064;
      --field: #2b2735;
      --accent: #c1b0ef;
      --button-fill: #7963c0;
      --button-hover: #745cba;
      --on-accent: #fff;
      --accent-soft: #342c47;
      --peach: #3a2e2b;
      --peach-ink: #dfb99c;
      --danger: #ffb2c1;
      --focus: #c1b0ef30;
      --shadow: 0 8px 26px #00000026;
      --art-line: #b7a0cf;
      --art-paper: #47394e;
      --art-lavender: #625079;
      --art-peach: #785060;
      --art-blush: #c682a2;
      --art-shadow: #140f2350;
    }
    *, *::before, *::after { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body {
      margin: 0;
      color: var(--ink);
      background: var(--canvas);
      font: 14px/1.6 "PingFang SC", "Microsoft YaHei UI", system-ui, sans-serif;
      -webkit-font-smoothing: antialiased;
    }
    ::selection { color: var(--ink); background: var(--accent-soft); }
    button, input, select { font: inherit; }
    button { cursor: pointer; }
    button:focus-visible, select:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 3px;
    }
    svg {
      display: block;
      fill: none;
      stroke: currentColor;
      stroke-width: 1.65;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    .login-page {
      display: grid;
      align-content: center;
      gap: 25px;
      min-height: 100vh;
      min-height: 100dvh;
      padding: clamp(18px, 4vw, 48px);
    }
    .login-topbar, .login-stage { width: min(1120px, 100%); margin-inline: auto; }
    .login-topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .login-brand { display: flex; align-items: center; gap: 12px; }
    .login-brand-mark {
      display: grid;
      flex: 0 0 44px;
      place-items: center;
      width: 44px;
      height: 44px;
      border-radius: 15px;
      color: var(--peach-ink);
      background: var(--peach);
    }
    .login-brand-mark svg { width: 24px; height: 24px; }
    .login-brand strong {
      display: block;
      font-size: clamp(17px, 3vw, 23px);
      font-weight: 800;
      line-height: 1.2;
      letter-spacing: -.015em;
    }
    .login-brand small {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 9px;
      font-weight: 750;
      line-height: 1.3;
      letter-spacing: .17em;
    }
    .login-theme-control {
      display: flex;
      align-items: center;
      gap: 7px;
      padding: 2px 10px 2px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface);
    }
    .login-theme-control svg { width: 16px; height: 16px; color: var(--accent); }
    .login-theme-control:focus-within { border-color: var(--accent); }
    .login-theme-control select {
      min-height: 38px;
      border: 0;
      background: transparent;
      color: var(--ink);
      font-size: 12px;
      cursor: pointer;
    }
    .login-theme-control select option { color: var(--ink); background: var(--surface); }

    .login-stage {
      position: relative;
      isolation: isolate;
      display: grid;
      place-items: center;
      min-height: min(660px, 74vh);
      padding: clamp(28px, 5vw, 58px) 20px;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: var(--stage);
      box-shadow: none;
    }
    .login-stage::before {
      position: absolute;
      z-index: -1;
      inset: 15px;
      border: 1px solid var(--line);
      border-color: transparent;
      border-radius: 16px;
      content: "";
      pointer-events: none;
    }
    .login-art {
      position: absolute;
      z-index: -1;
      height: auto;
      color: var(--art-line);
      stroke-width: 1.2;
      pointer-events: none;
    }
    .login-book { width: 24%; left: 3.2%; bottom: 8%; }
    .login-cat { width: 19%; right: 4%; bottom: 10.5%; }
    .art-shadow { fill: var(--art-shadow); stroke: none; }
    .art-paper { fill: var(--art-paper); }
    .art-lavender { fill: var(--art-lavender); }
    .art-peach { fill: var(--art-peach); }
    .art-ribbon { fill: var(--art-blush); }
    .art-blush { fill: var(--art-blush); stroke: none; }
    .art-ink { stroke-width: 1.5; }
    .art-spark { fill: var(--art-peach); stroke: none; }
    .art-dot { fill: var(--art-lavender); stroke: none; }

    .login-panel {
      width: min(432px, 100%);
      padding: 30px clamp(21px, 4vw, 40px) 28px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: var(--surface);
      box-shadow: var(--shadow);
    }
    .login-panel-lights { display: flex; gap: 6px; margin-bottom: 21px; }
    .login-panel-lights i { width: 8px; height: 8px; border-radius: 50%; background: #efaa92; }
    .login-panel-lights i:nth-child(2) { background: #ebc172; }
    .login-panel-lights i:nth-child(3) { background: #8bc6a8; }
    .login-kicker {
      display: inline-block;
      padding: 3px 9px;
      border-radius: 999px;
      color: var(--accent);
      background: var(--accent-soft);
      font-size: 11px;
      font-weight: 750;
    }
    .login-intro h1 {
      margin: 9px 0 0;
      font-size: clamp(27px, 4vw, 35px);
      font-weight: 800;
      line-height: 1.25;
      letter-spacing: -.04em;
    }
    .login-intro p { margin: 8px 0 24px; color: var(--muted); font-size: 13px; }
    .login-form { display: grid; gap: 15px; }
    .login-field { display: grid; gap: 6px; }
    .login-field label { font-size: 13px; font-weight: 700; }
    .login-field-control { position: relative; }
    .login-field-control > svg {
      position: absolute;
      top: 50%;
      left: 13px;
      width: 19px;
      height: 19px;
      transform: translateY(-50%);
      color: var(--muted);
      pointer-events: none;
    }
    .login-form input {
      width: 100%;
      min-width: 0;
      min-height: 49px;
      padding: 11px 13px 11px 42px;
      border: 1px solid var(--field-line);
      border-radius: 10px;
      background: var(--field);
      color: var(--ink);
      caret-color: var(--accent);
      font-size: 16px;
      outline: none;
    }
    .login-form input::placeholder { color: var(--muted); font-size: 13px; }
    .login-form input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--focus); }
    .login-password-wrap input { padding-right: 52px; }
    .login-password-toggle {
      position: absolute;
      top: 50%;
      right: 3px;
      display: grid;
      place-items: center;
      width: 44px;
      height: 44px;
      padding: 0;
      transform: translateY(-50%);
      border: 0;
      border-radius: 10px;
      background: transparent;
      color: var(--muted);
    }
    .login-password-toggle svg { width: 20px; height: 20px; }
    .login-password-toggle:hover, .login-password-toggle[aria-pressed="true"] {
      background: var(--accent-soft);
      color: var(--accent);
    }
    .login-password-toggle:focus-visible { outline-offset: -2px; }
    .login-button {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 10px;
      min-height: 49px;
      margin-top: 4px;
      padding: 10px 16px;
      border: 0;
      border-radius: 10px;
      color: var(--on-accent);
      background: var(--button-fill);
      font-weight: 750;
      transition: background .18s ease, box-shadow .18s ease;
    }
    .login-button svg { width: 18px; height: 18px; }
    .login-button:hover:not(:disabled) { background: var(--button-hover); box-shadow: 0 3px 8px #2826321a; }
    .login-button:disabled { cursor: wait; opacity: .65; }
    .login-message { min-height: 20px; margin: 9px 0 0; color: var(--danger); font-size: 12px; }
    .login-note {
      display: flex;
      align-items: flex-start;
      gap: 7px;
      padding-top: 15px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
    }
    .login-note svg { flex: 0 0 16px; width: 16px; height: 16px; margin-top: 2px; color: var(--accent); }

    @media (max-width: 760px) {
      .login-page { gap: 15px; padding: 18px 14px; }
      .login-stage { min-height: 0; padding: 23px 16px; border-radius: 16px; }
      .login-stage::before { inset: 8px; border-radius: 16px; }
      .login-art { display: none; }
    }
    @media (max-width: 410px) {
      .login-page { padding: 14px 12px; }
      .login-stage { padding: 0; border: 0; background: none; box-shadow: none; }
      .login-stage::before { display: none; }
      .login-panel { padding-top: 22px; border-radius: 16px; }
      .login-panel-lights { margin-bottom: 16px; }
    }

    /* 主题过渡只合成整页快照。 */
    html.theme-updating *, html.theme-updating *::before, html.theme-updating *::after { transition: none !important; }
    html.theme-updating::view-transition { pointer-events: none; }
    html.theme-updating::view-transition-group(root) { animation: none; }
    html.theme-updating::view-transition-image-pair(root) { isolation: isolate; }
    html.theme-updating::view-transition-old(root) { animation: none; opacity: 1; mix-blend-mode: normal; }
    html.theme-updating::view-transition-new(root) { animation: mantou-theme-fade .32s cubic-bezier(.4, 0, .2, 1) both; mix-blend-mode: normal; }
    @keyframes mantou-theme-fade { from { opacity: 0; } to { opacity: 1; } }
    @media (prefers-reduced-motion: reduce) {
      html::view-transition-group(root), html::view-transition-old(root), html::view-transition-new(root) { animation: none !important; }
      *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
    }
  """
