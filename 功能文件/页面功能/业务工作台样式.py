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
    .studio-bot-workspace { display: grid; gap: 18px; }
    .studio-bot-identity {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 9px 18px;
      padding: 12px 15px;
      border-radius: 13px;
      background: var(--studio-wash);
    }
    .studio-bot-badge { display: flex; align-items: center; gap: 10px; min-width: 0; }
    .studio-bot-badge h2 { font-size: 17px; overflow-wrap: anywhere; }
    .studio-bot-badge .bot-profile-status { display: inline-flex; font-size: 12px; }
    #page-bot .studio-bot-badge .bot-avatar {
      flex: 0 0 42px;
      width: 42px;
      height: 42px;
      border: 1px solid var(--studio-border);
      background: var(--studio-accent-soft);
      box-shadow: none;
    }
    #page-bot .studio-bot-badge .avatar-face { color: var(--studio-accent); font-size: 14px; }
    .studio-bot-facts {
      display: flex;
      flex-wrap: wrap;
      gap: 2px 7px;
      margin: 0;
      font-size: 12px;
    }
    .studio-bot-facts dt { color: var(--studio-muted); }
    .studio-bot-facts dd { margin: 0; overflow-wrap: anywhere; font-weight: 650; }
    .studio-bot-tabs {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 4px;
      width: min(100%, 420px);
      padding: 4px;
      border: 1px solid var(--studio-border);
      border-radius: 12px;
      background: var(--studio-soft);
    }
    .studio-bot-tabs button {
      min-width: 0;
      min-height: 38px;
      padding: 6px 4px;
      border: 1px solid transparent;
      border-radius: 8px;
      background: transparent;
      color: var(--studio-muted);
      font-size: 13px;
      font-weight: 680;
      white-space: nowrap;
    }
    .studio-bot-tabs button:hover { color: var(--studio-accent); }
    .studio-bot-tabs button[aria-selected="true"] {
      border-color: var(--studio-border);
      background: var(--studio-card);
      color: var(--studio-accent);
    }
    .studio-bot-tabs button:focus-visible, .studio-bot-panel:focus-visible {
      outline: 2px solid var(--studio-accent);
      outline-offset: 2px;
    }
    .studio-bot-panel { min-width: 0; }
    .studio-bot-panel[hidden] { display: none; }
    #page-bot .config-fields {
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 230px), 1fr));
    }
    #page-bot .config-group {
      padding: 15px 16px;
      border-color: var(--studio-border);
      border-radius: 13px;
      background: var(--studio-soft);
    }
    #page-bot .config-group h3 { margin: 0 0 12px; font-size: 14px; }
    #page-bot .config-field :is(input, select, textarea) {
      background: var(--studio-card);
      border-color: var(--studio-border);
      color: var(--studio-ink);
    }
    #page-bot .config-field :is(input, select, textarea):focus {
      border-color: var(--studio-accent);
      box-shadow: 0 0 0 3px var(--studio-accent-soft);
    }
    #page-bot .qq-reader-toolbar { flex-wrap: wrap; }
    #page-bot .qq-reader-account {
      padding: 14px;
      border-color: var(--studio-border);
      border-radius: 13px;
      background: var(--studio-soft);
    }
    #page-bot .qq-reader-account.is-current {
      border-color: var(--studio-accent);
      background: var(--studio-accent-soft);
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
