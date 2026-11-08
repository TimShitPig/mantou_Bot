"""机器人、小说服务与网盘配置的工作台样式。"""

业务样式 = """
    .studio-service-page {
      --service-gap: clamp(14px, 2vw, 22px);
      min-width: 0;
      color: var(--studio-ink);
    }
    .studio-service-page .studio-card { min-width: 0; }
    .studio-service-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 16px;
    }
    .studio-service-head > div { min-width: 0; }
    .studio-service-page h2,
    .studio-service-page h3 {
      margin: 0;
      color: var(--studio-ink);
      line-height: 1.35;
    }
    .studio-service-page h2 { font-size: 19px; }
    .studio-service-page h3 { font-size: 16px; }
    .studio-service-page .studio-kicker + h2 { margin-top: 5px; }
    .studio-service-head p,
    .studio-novel-control p {
      margin: 6px 0 0;
      color: var(--studio-muted);
      font-size: 13px;
      line-height: 1.6;
    }
    .studio-service-icon {
      display: grid;
      flex: 0 0 42px;
      width: 42px;
      height: 42px;
      place-items: center;
      border-radius: 13px;
      background: var(--studio-accent-soft);
      color: var(--studio-accent);
    }
    .studio-service-icon svg { width: 21px; height: 21px; }
    .studio-service-icon.studio-icon-peach {
      background: var(--studio-peach);
      color: var(--peach-ink, var(--studio-ink));
    }
    .studio-novel-grid,
    #pans.studio-pans-grid {
      display: grid;
      grid-template-columns: minmax(200px, .85fr) minmax(0, 2fr);
      align-items: start;
      gap: var(--service-gap);
    }
    .studio-bot-workspace {
      --bot-action: linear-gradient(115deg, #5b42b5, #3f56af);
      --bot-action-hover: linear-gradient(115deg, #4d359c, #33499d);
      display: grid;
      gap: clamp(14px, 2vw, 22px);
    }
    .studio-bot-identity {
      position: relative;
      isolation: isolate;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 14px 20px;
      padding: clamp(16px, 2.5vw, 28px);
      border: 1px solid #b2a0ff5c;
      border-radius: 17px;
      overflow: hidden;
      color: #faf7ff;
      background:
        radial-gradient(ellipse at 83% -28%, #8666d6c4, transparent 64%),
        radial-gradient(ellipse at 103% 110%, #236296a6, transparent 61%),
        linear-gradient(115deg, #261943, #3a286f 66%, #263a69);
      box-shadow: 0 10px 25px #33246933, inset 0 1px #e7dcff26;
    }
    .studio-bot-identity::before,
    .studio-bot-identity::after {
      position: absolute;
      z-index: -1;
      content: "";
      pointer-events: none;
    }
    .studio-bot-identity::before {
      inset: 0 0 0 50%;
      background:
        linear-gradient(90deg, transparent 0%, #ffffff12 100%),
        repeating-linear-gradient(0deg, transparent 0 23px, #dce5ff17 23px 24px),
        repeating-linear-gradient(90deg, transparent 0 23px, #dce5ff17 23px 24px);
      mask-image: linear-gradient(90deg, transparent, #000);
    }
    .studio-bot-identity::after {
      top: -103px;
      right: -40px;
      width: 400px;
      height: 290px;
      border: 1px solid #e1d1ff3d;
      border-radius: 50%;
      box-shadow: 0 0 0 27px #d4c2ff0e, 0 0 0 59px #d4c2ff0e;
      transform: rotate(-18deg);
    }
    .studio-bot-badge {
      display: flex;
      align-items: center;
      gap: clamp(11px, 1.5vw, 17px);
      min-width: 0;
    }
    .studio-bot-copy { min-width: 0; }
    .studio-bot-kicker {
      display: block;
      color: #dcd1fb;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .08em;
    }
    #page-bot .studio-bot-badge h2 {
      margin: 2px 0 5px;
      color: #fff;
      font-size: clamp(18px, 2.4vw, 25px);
      overflow-wrap: anywhere;
    }
    .studio-bot-badge .bot-profile-status {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 2px 8px;
      border: 1px solid #f0e7ff35;
      border-radius: 999px;
      background: #1c153b72;
      color: #e6ddfa;
      font-size: 11px;
      font-weight: 650;
    }
    .studio-bot-badge .bot-profile-status.online { color: #b8f6d9; }
    .studio-bot-badge .online::before {
      background: #7be4b6;
      box-shadow: 0 0 7px #7be4b69c;
    }
    #page-bot .studio-bot-badge .bot-avatar {
      --bot-avatar-size: clamp(47px, 6vw, 62px);
      flex: 0 0 var(--bot-avatar-size);
      width: var(--bot-avatar-size);
      height: var(--bot-avatar-size);
      border: 2px solid #e7dfff;
      background: #534099;
      box-shadow: 0 0 0 4px #bda8ff3b, 0 0 23px #a18aff65;
    }
    #page-bot .studio-bot-badge .avatar-face { color: #fff; font-size: 18px; }
    .studio-bot-facts {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 2px 9px;
      min-width: 0;
      max-width: 100%;
      margin: 0;
      padding: 7px 11px;
      border: 1px solid #f0e7ff35;
      border-radius: 9px;
      background: #1c153b72;
      font-size: 12px;
    }
    .studio-bot-facts dt { color: #ded4f8; }
    .studio-bot-facts dd { margin: 0; overflow-wrap: anywhere; font-weight: 680; font-variant-numeric: tabular-nums; }
    .studio-bot-tabs {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 4px;
      width: min(100%, 510px);
      padding: 4px;
      border: 1px solid var(--studio-border);
      border-radius: 14px;
      background: var(--studio-soft);
    }
    .studio-bot-tabs button {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: clamp(4px, 1vw, 8px);
      min-width: 0;
      min-height: 44px;
      padding: 6px 3px;
      border: 1px solid transparent;
      border-radius: 10px;
      background: transparent;
      color: var(--studio-muted);
      font-size: 13px;
      font-weight: 720;
      white-space: nowrap;
      transition: color .16s ease, background-color .16s ease, box-shadow .16s ease;
    }
    .studio-bot-tabs svg { width: 17px; height: 17px; flex: 0 0 auto; }
    .studio-bot-tabs button:hover { color: var(--studio-accent); background: var(--studio-accent-soft); }
    .studio-bot-tabs button[aria-selected="true"] {
      border-color: #b9b1ff4d;
      background: var(--bot-action);
      color: #fff;
      box-shadow: 0 3px 9px #4738aa4d, inset 0 1px #ffffff32;
    }
    .studio-bot-tabs button:focus-visible,
    .studio-bot-panel:focus-visible,
    #page-bot .config-actions button:focus-visible {
      outline: 2px solid var(--studio-accent);
      outline-offset: 2px;
    }
    .studio-bot-panel { min-width: 0; }
    .studio-bot-panel[hidden] { display: none; }
    .studio-bot-panel > .studio-service-head {
      padding-left: 11px;
      border-left: 3px solid var(--studio-accent);
    }
    .studio-bot-panel > .studio-service-head h3 { font-size: 18px; }
    @media (prefers-reduced-motion: no-preference) {
      .studio-bot-panel:not([hidden]) { animation: studio-bot-panel-in .18s ease-out both; }
      @keyframes studio-bot-panel-in {
        from { opacity: .65; }
        to { opacity: 1; }
      }
    }
    #basic-config-editor { gap: 13px; }
    #basic-config-editor .config-fields {
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr));
      align-items: start;
    }
    #basic-config-editor .config-group {
      --bot-group-mark: #9d7ce5;
      min-width: 0;
      padding: clamp(13px, 1.7vw, 19px);
      border: 1px solid var(--studio-border);
      border-top: 2px solid var(--bot-group-mark);
      border-radius: 13px;
      background: linear-gradient(135deg, var(--studio-soft), var(--studio-card));
    }
    #basic-config-editor [data-config-category="help_web_settings"] { --bot-group-mark: #78a6d9; }
    #basic-config-editor [data-config-category="zlibrary_account_settings"] { --bot-group-mark: #dc9e7b; }
    #basic-config-editor .config-group h3 { margin: 0 0 12px; font-size: 15px; }
    #basic-config-editor .config-field label { font-size: 12px; }
    #basic-config-editor .config-field small { font-size: 11px; }
    #basic-config-editor .config-scope-label {
      display: inline-block;
      margin-inline-start: 6px;
      padding: 1px 6px;
      border-radius: 6px;
      background: var(--studio-accent-soft);
      color: var(--studio-muted);
      white-space: nowrap;
    }
    #basic-config-editor .config-field :is(input, select, textarea) {
      min-height: 44px;
      border-color: var(--studio-border);
      border-radius: 9px;
      background: var(--studio-card);
      color: var(--studio-ink);
    }
    #basic-config-editor .config-field textarea { min-height: 82px; }
    #basic-config-editor .config-field :is(input, select, textarea):focus {
      border-color: var(--studio-accent);
      box-shadow: 0 0 0 3px var(--studio-accent-soft);
    }
    #basic-config-editor .config-actions { flex-wrap: wrap; }
    #basic-config-editor .config-actions .primary-button {
      min-height: 44px;
      padding-inline: 18px;
      border-radius: 10px;
      background: var(--bot-action);
      color: #fff;
    }
    #basic-config-editor .config-actions .primary-button:hover:not(:disabled) { background: var(--bot-action-hover); }
    @media (min-width: 1080px) {
      #basic-config-editor:has(> [data-config-category="basic_settings"]):has(> [data-config-category="help_web_settings"]) {
        grid-template-columns: minmax(0, .85fr) minmax(0, 1.15fr);
      }
      #basic-config-editor > :is([data-config-category="zlibrary_account_settings"], .config-actions) { grid-column: 1 / -1; }
      #basic-config-editor [data-config-category="help_web_settings"] .config-fields {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      #basic-config-editor [data-config-category="zlibrary_account_settings"] .config-fields { max-width: 45rem; }
    }
    @media (max-width: 410px) {
      .studio-bot-tabs button { font-size: 12px; }
      .studio-bot-tabs svg { width: 14px; height: 14px; }
    }
    #page-bot .qq-reader-toolbar { flex-wrap: wrap; }
    #page-bot .qq-reader-account {
      padding: 14px;
      border-color: var(--studio-border);
      border-radius: 13px;
      background: linear-gradient(140deg, var(--studio-soft), var(--studio-card));
    }
    #page-bot .qq-reader-account.is-current {
      border-color: var(--studio-accent);
      background: linear-gradient(140deg, var(--studio-accent-soft), var(--studio-card));
    }
    #bot-panel-zlibrary {
      --ink: var(--studio-ink);
      --muted: var(--studio-muted);
      --line: var(--studio-border);
      --panel: var(--studio-card);
      --raised: var(--studio-soft);
      --hover: var(--studio-accent-soft);
      --primary: var(--studio-accent);
      --primary-soft: var(--studio-accent-soft);
    }
    #page-bot .zlibrary-toolbar { margin-top: 14px; }
    #page-bot .zlibrary-manager-tools { margin-bottom: 14px; }
    #page-bot .zlibrary-table-scroll {
      border: 1px solid var(--studio-border);
      border-radius: 12px;
      scrollbar-color: var(--studio-accent) var(--studio-soft);
    }
    #page-bot .zlibrary-table { min-width: 940px; }
    #page-bot .zlibrary-table th { background: var(--studio-soft); }
    #page-bot .zlibrary-table tr:last-child td { border-bottom: 0; }
    #page-bot .zlibrary-tab.is-active {
      background: var(--studio-accent-soft);
      color: var(--studio-accent);
    }
    body:not(.messages-workspace) :is(.zlibrary-dialog, .qq-reader-modal) {
      --panel: var(--studio-card);
      --line: var(--studio-border);
      --ink: var(--studio-ink);
      --muted: var(--studio-muted);
      --raised: var(--studio-soft);
      --primary: var(--studio-accent);
      --primary-soft: var(--studio-accent-soft);
      border-radius: 18px;
      background: var(--studio-card);
      box-shadow: var(--studio-shadow);
    }
    body:not(.messages-workspace) .zlibrary-dialog .zlibrary-action.is-primary,
    #page-bot .zlibrary-action.is-primary {
      background: #6254ad;
      border-color: #6254ad;
      color: #fff;
    }
    body:not(.messages-workspace) .zlibrary-dialog .zlibrary-action.is-primary:hover:not(:disabled),
    #page-bot .zlibrary-action.is-primary:hover:not(:disabled) {
      background: #514592;
      border-color: #514592;
    }

    .studio-novel-settings { display: grid; gap: 13px; }
    .studio-novel-settings .studio-service-head { margin-bottom: 2px; }
    .studio-novel-control {
      padding: 14px;
      border: 1px solid var(--studio-border);
      border-radius: 13px;
      background: var(--studio-soft);
    }
    .studio-novel-test {
      background: color-mix(in srgb, var(--studio-peach) 42%, var(--studio-card));
    }
    .studio-novel-switch-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-height: 36px;
      margin-top: 13px;
      color: var(--studio-muted);
      font-size: 12px;
    }
    .studio-novel-switch-row > div { display: grid; gap: 3px; }
    .studio-novel-switch-row strong { color: var(--studio-ink); }
    .studio-novel-switch-row small { font-size: 11px; }
    .studio-novel-switch-row .switch { flex-shrink: 0; }
    .studio-novel-platform-head { flex-wrap: wrap; align-items: flex-end; }
    .studio-novel-metrics { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; }
    .studio-count-pill {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 4px 10px;
      border-radius: 999px;
      background: var(--studio-accent-soft);
      color: var(--studio-accent);
      font-size: 11px;
      font-weight: 700;
      white-space: nowrap;
    }
    #page-novels .novel-state-pill { min-height: 30px; margin: 0; }
    #page-novels #novel-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 192px), 1fr));
      gap: 10px;
    }
    #page-novels .novel-item {
      position: relative;
      flex-direction: column;
      align-items: stretch;
      gap: 10px;
      min-width: 0;
      min-height: 115px;
      padding: 12px;
      border-color: var(--studio-border);
      border-radius: 13px;
      background: var(--studio-soft);
    }
    #page-novels .novel-item:hover {
      transform: none;
      border-color: var(--studio-accent);
      box-shadow: none;
    }
    #page-novels .novel-item.is-enabled { background: var(--studio-card); }
    #page-novels .novel-item-title { flex-wrap: wrap; column-gap: 6px; row-gap: 3px; }
    #page-novels .novel-item-title strong { white-space: normal; overflow-wrap: anywhere; }
    #page-novels .novel-item-copy small { color: var(--studio-muted); line-height: 1.4; }
    #page-novels .novel-item-status { color: var(--studio-muted); }
    #page-novels .novel-item.is-enabled .novel-item-status { color: var(--mint-ink); }
    #page-novels .novel-item .switch { align-self: flex-end; transform: none; }
    #page-novels .novel-badge {
      width: 37px;
      height: 37px;
      border-radius: 11px;
      background: var(--studio-accent-soft);
      color: var(--studio-accent);
    }
    #page-novels .novel-item:nth-child(3n + 2) .novel-badge {
      background: var(--mint);
      color: var(--mint-ink);
    }
    #page-novels .novel-item:nth-child(3n) .novel-badge {
      background: var(--studio-peach);
      color: var(--peach-ink);
    }

    #pans.studio-pans-grid {
      margin: 0;
      grid-template-columns: minmax(175px, .64fr) minmax(0, 2fr);
    }
    #page-pans .pan-tabs {
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 3px;
      overflow: visible;
      border: 0;
    }
    #page-pans .pan-tab {
      position: relative;
      gap: 9px;
      min-width: 0;
      min-height: 59px;
      padding: 9px 10px;
      border: 1px solid var(--studio-border);
      border-radius: 12px;
      background: var(--studio-soft);
      color: var(--studio-ink);
      box-shadow: none;
    }
    #page-pans .pan-tab:hover,
    #page-pans .pan-tab.active {
      border-color: var(--studio-accent);
      background: var(--studio-accent-soft);
      color: var(--studio-accent);
    }
    #page-pans .pan-tab-copy small { color: var(--studio-muted); white-space: normal; }
    #page-pans .pan-tab-mark {
      background: var(--studio-accent-soft);
      color: var(--studio-accent);
      border-radius: 10px;
    }
    #page-pans .pan-tab-quark { background: var(--mint); color: var(--mint-ink); }
    #page-pans .pan-tab-baidu { background: var(--studio-peach); color: var(--peach-ink); }
    #page-pans .pan-account-toolbar {
      padding: 10px 0;
      border-top: 1px solid var(--studio-border);
      border-bottom: 1px solid var(--studio-border);
    }
    #page-pans .pan-account-toolbar-actions { flex-wrap: wrap; }
    #page-pans .pan-add-account {
      min-height: 38px;
      padding-inline: 14px;
      border-color: #6254ad;
      border-radius: 10px;
      background: #6254ad;
      color: #fff;
    }
    #page-pans .pan-add-account:hover:not(:disabled) {
      background: #514592;
      border-color: #514592;
    }
    #page-pans .pan-object-grid {
      grid-template-columns: repeat(auto-fill, minmax(min(100%, 195px), 1fr));
      padding: 15px 0 0;
      gap: 10px;
    }
    #page-pans .pan-object-card {
      max-width: none;
      border-color: var(--studio-border);
      border-radius: 13px;
      background: var(--studio-soft);
    }
    #page-pans .pan-object-card:hover { border-color: var(--studio-accent); }
    #page-pans .pan-account-object.is-disabled { background: var(--studio-card); }
    #page-pans .pan-object-empty { margin: 0; }
    #page-pans .pan-object-detail-head { flex-wrap: wrap; width: 100%; border-color: var(--studio-border); }
    #page-pans .pan-object-pane {
      width: 100%;
      margin: 14px 0 0;
      padding: clamp(12px, 2vw, 20px);
      border-color: var(--studio-border);
      border-radius: 13px;
      background: var(--studio-soft);
      box-shadow: none;
    }

    @media (max-width: 900px) {
      .studio-novel-grid,
      #pans.studio-pans-grid { grid-template-columns: minmax(0, 1fr); }
      .studio-novel-settings { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .studio-novel-settings .studio-service-head { grid-column: 1 / -1; }
    }
    @media (max-width: 560px) {
      .studio-novel-settings { grid-template-columns: minmax(0, 1fr); }
      #page-novels #novel-grid {
        grid-template-columns: repeat(auto-fit, minmax(min(100%, 135px), 1fr));
        gap: 8px;
      }
      #page-novels .novel-item { padding: 10px; }
      #page-novels .novel-item-main { gap: 7px; }
      #page-novels .novel-badge { width: 28px; height: 28px; border-radius: 9px; }
      #page-pans .pan-tab { min-height: 47px; }
    }
"""
