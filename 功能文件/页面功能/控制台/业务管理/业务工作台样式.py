"""机器人、小说服务与网盘配置的工作台样式。"""

业务样式 = """
    .studio-service-page {
      --service-gap: clamp(14px, 2vw, 22px);
      --service-inset: clamp(16px, 2vw, 22px);
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
    .studio-novel-grid {
      display: grid;
      grid-template-columns: minmax(200px, .85fr) minmax(0, 2fr);
      align-items: start;
      gap: var(--service-gap);
    }
    .studio-bot-workspace {
      --bot-action: var(--accent-fill);
      --bot-action-hover: var(--accent-hover);
      display: grid;
      align-content: start;
      gap: clamp(14px, 2vw, 22px);
    }
    .studio-bot-identity {
      position: relative;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 14px 20px;
      padding: clamp(16px, 2.5vw, 28px);
      border: 1px solid var(--studio-border);
      border-radius: 14px;
      overflow: hidden;
      color: var(--studio-ink);
      background: var(--studio-wash);
      box-shadow: none;
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
      color: var(--studio-muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .08em;
    }
    #page-bot .studio-bot-badge h2 {
      margin: 2px 0 5px;
      color: var(--studio-ink);
      font-size: clamp(18px, 2.4vw, 25px);
      overflow-wrap: anywhere;
    }
    .studio-bot-badge .bot-profile-status {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 2px 8px;
      border: 1px solid var(--studio-border);
      border-radius: 999px;
      background: var(--studio-card);
      color: var(--studio-muted);
      font-size: 11px;
      font-weight: 650;
    }
    .studio-bot-badge .bot-profile-status.online { color: var(--studio-mint-ink); }
    .studio-bot-badge .online::before {
      background: var(--studio-mint-ink);
      box-shadow: none;
    }
    #page-bot .studio-bot-badge .bot-avatar {
      --bot-avatar-size: clamp(47px, 6vw, 62px);
      flex: 0 0 var(--bot-avatar-size);
      width: var(--bot-avatar-size);
      height: var(--bot-avatar-size);
      border: 2px solid var(--studio-border);
      background: var(--studio-accent-soft);
      box-shadow: none;
    }
    #page-bot .studio-bot-badge .avatar-face { color: var(--studio-accent); font-size: 18px; }
    .studio-bot-facts {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 2px 9px;
      min-width: 0;
      max-width: 100%;
      margin: 0;
      padding: 7px 11px;
      border: 1px solid var(--studio-border);
      border-radius: 9px;
      background: var(--studio-card);
      font-size: 12px;
    }
    .studio-bot-facts dt { color: var(--studio-muted); }
    .studio-bot-facts dd { margin: 0; overflow-wrap: anywhere; font-weight: 680; font-variant-numeric: tabular-nums; }
    .studio-bot-tabs {
      display: grid;
      grid-template-columns: repeat(5, minmax(max-content, 1fr));
      gap: 4px;
      width: min(100%, 850px);
      overflow-x: auto;
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
      border-color: var(--studio-border);
      background: var(--studio-card);
      color: var(--studio-accent);
      box-shadow: none;
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
      margin-bottom: 18px;
    }
    .studio-bot-panel > .studio-service-head h3 { font-size: 18px; }
    @media (prefers-reduced-motion: no-preference) {
      .studio-bot-panel:not([hidden]) { animation: studio-bot-panel-in .18s ease-out both; }
      @keyframes studio-bot-panel-in {
        from { opacity: .65; }
        to { opacity: 1; }
      }
    }
    #qq-reader-api-config-editor { margin-top: var(--service-gap); }
    .studio-account-section {
      min-width: 0;
      border: 1px solid var(--studio-border);
      border-radius: 12px;
      background: var(--studio-card);
      box-shadow: var(--studio-shadow);
    }
    .studio-account-section > .studio-service-head {
      margin: 0;
      padding: var(--service-inset);
      border-bottom: 1px solid var(--studio-border);
    }
    .studio-panel-body { min-width: 0; padding: var(--service-inset); }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) { gap: 16px; align-items: start; }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) .config-fields {
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr));
      align-items: start;
    }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) .config-group {
      min-width: 0;
      align-self: start;
      padding: var(--service-inset);
      border: 1px solid var(--studio-border);
      border-radius: 12px;
      background: var(--studio-card);
      box-shadow: var(--studio-shadow);
    }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) .config-group h3 { margin: 0 0 18px; padding-bottom: 13px; border-bottom: 1px solid var(--studio-border); font-size: 15px; }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) .config-field label { font-size: 12px; }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) .config-field small { font-size: 11px; }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) .config-scope-label {
      display: inline-block;
      margin-inline-start: 6px;
      padding: 1px 6px;
      border-radius: 6px;
      background: var(--studio-accent-soft);
      color: var(--studio-accent);
      white-space: nowrap;
    }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) .config-field :is(input, select, textarea) {
      min-height: 44px;
      border-color: var(--studio-border);
      border-radius: 9px;
      background: var(--studio-soft);
      color: var(--studio-ink);
    }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) .config-field textarea { min-height: 82px; }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) .config-field :is(input, select, textarea):focus {
      border-color: var(--studio-accent);
      box-shadow: 0 0 0 3px var(--studio-accent-soft);
    }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) > .config-actions {
      grid-column: 1 / -1;
      flex-wrap: wrap;
      justify-content: flex-end;
      padding: 14px 0 0;
      border-top: 1px solid var(--studio-border);
    }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) > .config-actions .config-message:empty { display: none; }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) .config-actions .primary-button {
      min-height: 44px;
      padding-inline: 18px;
      border-radius: 8px;
      background: var(--bot-action);
      color: #fff;
    }
    :is(#basic-config-editor, #zlibrary-registration-config-editor) .config-actions .primary-button:hover:not(:disabled) { background: var(--bot-action-hover); }
    #zlibrary-registration-config-editor { margin-top: var(--service-gap); }
    #zlibrary-registration-config-editor .config-fields { max-width: 56rem; }
    .admin-list-heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 6px; }
    .admin-list-value[hidden] { display: none !important; }
    .admin-list-heading > label { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
    .admin-list-count { display: inline-flex; align-items: center; padding: 3px 8px; border: 1px solid var(--studio-border); border-radius: 999px; color: var(--studio-muted); background: var(--studio-soft); font-size: 11px; font-variant-numeric: tabular-nums; }
    .admin-list-roster { display: grid; gap: 8px; max-height: 310px; overflow-y: auto; margin: 0; padding: 0; list-style: none; scrollbar-width: thin; }
    .admin-list-item { display: flex; align-items: center; gap: 9px; min-width: 0; padding: 5px 6px 5px 10px; border: 1px solid var(--studio-border); border-radius: 9px; background: var(--studio-soft); }
    .admin-list-index { flex: 0 0 auto; color: var(--studio-muted); font-size: 10px; font-variant-numeric: tabular-nums; }
    .admin-list-item code { flex: 1; min-width: 0; overflow-wrap: anywhere; color: var(--studio-ink); font-family: ui-monospace, "SFMono-Regular", Consolas, monospace; font-size: 12px; line-height: 1.6; }
    .admin-list-remove { flex: 0 0 auto; min-height: 36px; min-width: 44px; padding: 6px 9px; border: 0; border-radius: 6px; background: transparent; color: var(--studio-muted); font: inherit; font-size: 11px; cursor: pointer; }
    .admin-list-remove:hover:not(:disabled) { background: var(--danger-bg); color: var(--danger); }
    .admin-list-remove:disabled { opacity: .5; cursor: default; }
    .admin-list-empty { margin: 0; padding: 20px 12px; border: 1px dashed var(--studio-border); border-radius: 9px; color: var(--studio-muted); font-size: 12px; text-align: center; }
    .admin-list-add { display: flex; align-items: stretch; gap: 8px; margin-top: 8px; min-width: 0; }
    .admin-list-add input { flex: 1; min-width: 0; }
    .admin-list-add .outline-button { flex: 0 0 auto; min-height: 44px; padding-inline: 14px; white-space: nowrap; }
    .admin-list-feedback { margin: 0; color: var(--studio-muted); font-size: 11px; line-height: 1.6; }
    .admin-list-feedback.is-error { color: var(--danger); }
    .admin-list-feedback:empty { display: none; }
    .admin-list-remove:focus-visible { outline: 2px solid var(--studio-accent); outline-offset: 2px; }
    .qq-api-card {
      min-width: 0;
      border: 1px solid var(--studio-border);
      border-radius: 12px;
      background: var(--studio-card);
      box-shadow: var(--studio-shadow);
    }
    .qq-api-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: var(--service-inset);
      border-bottom: 1px solid var(--studio-border);
    }
    .qq-api-title { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
    .qq-api-header h3 { font-size: 16px; }
    .qq-api-header p { margin: 7px 0 0; color: var(--studio-muted); font-size: 12px; }
    .qq-api-scope {
      padding: 3px 7px;
      border-radius: 5px;
      background: var(--studio-accent-soft);
      color: var(--studio-accent);
      font-size: 10px;
      white-space: nowrap;
    }
    .qq-api-toggle {
      position: relative;
      display: flex;
      align-items: center;
      flex-shrink: 0;
      gap: 10px;
      min-height: 44px;
      color: var(--studio-muted);
      font-size: 12px;
      cursor: pointer;
    }
    .qq-api-toggle input { position: absolute; width: 1px; height: 1px; opacity: 0; }
    .qq-api-toggle-track {
      width: 42px;
      height: 24px;
      padding: 3px;
      border: 1px solid var(--studio-border);
      border-radius: 20px;
      background: var(--studio-soft);
    }
    .qq-api-toggle-track::after {
      display: block;
      content: "";
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: var(--studio-muted);
    }
    .qq-api-toggle input:checked + .qq-api-toggle-track { background: var(--bot-action); border-color: var(--bot-action); }
    .qq-api-toggle input:checked + .qq-api-toggle-track::after { transform: translateX(18px); background: #fff; }
    .qq-api-toggle input:focus-visible + .qq-api-toggle-track { outline: 2px solid var(--studio-accent); outline-offset: 3px; }
    .qq-api-toggle:has(input:disabled) { opacity: .55; cursor: default; }
    .qq-api-keys { display: grid; gap: 16px; padding: var(--service-inset); min-width: 0; }
    .qq-api-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .qq-api-toolbar h4 { margin: 0 0 5px; font-size: 13px; color: var(--studio-ink); }
    .qq-api-toolbar small { color: var(--studio-muted); font-size: 11px; }
    .qq-api-card .outline-button,
    .qq-api-card [data-config-save] { min-height: 44px; padding: 8px 14px; border-radius: 8px; white-space: nowrap; }
    .qq-api-card .outline-button { border-color: var(--studio-border); background: var(--studio-card); color: var(--studio-ink); }
    .qq-api-key-list { margin: 0; padding: 0 14px; list-style: none; border: 1px solid var(--studio-border); border-radius: 9px; background: var(--studio-soft); }
    .qq-api-key-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 54px; }
    .qq-api-key-row + .qq-api-key-row { border-top: 1px solid var(--studio-border); }
    .qq-api-key-row code { min-width: 0; overflow-wrap: anywhere; font-size: 12px; color: var(--studio-ink); }
    .qq-api-revoke { min-height: 44px; padding: 6px 0 6px 12px; border: 0; background: transparent; color: var(--danger); font: inherit; font-size: 12px; cursor: pointer; }
    .qq-api-revoke:hover:not(:disabled) { text-decoration: underline; }
    .qq-api-revoke:disabled { opacity: .5; cursor: default; }
    .qq-api-card :is(button, summary):focus-visible { outline: 2px solid var(--studio-accent); outline-offset: 3px; border-radius: 6px; }
    .qq-api-empty { padding: 19px 0; color: var(--studio-muted); font-size: 12px; }
    .qq-api-created { padding: 14px; border: 1px solid var(--studio-accent); border-radius: 9px; background: var(--studio-accent-soft); }
    .qq-api-created[hidden] { display: none; }
    .qq-api-created strong { color: var(--studio-accent); font-size: 13px; }
    .qq-api-created p { margin: 5px 0 10px; color: var(--studio-muted); font-size: 11px; }
    .qq-api-copy { display: flex; align-items: stretch; gap: 8px; }
    .qq-api-card input[data-api-key-created],
    .qq-api-import textarea { min-width: 0; width: 100%; padding: 10px 12px; border: 1px solid var(--studio-border); border-radius: 8px; background: var(--studio-card); color: var(--studio-ink); font-family: ui-monospace, monospace; font-size: 12px; }
    .qq-api-card input[data-api-key-created] { flex: 1; }
    .qq-api-import { border-top: 1px solid var(--studio-border); }
    .qq-api-import summary { width: fit-content; padding: 12px 0 0; color: var(--studio-muted); font-size: 12px; cursor: pointer; }
    .qq-api-import > div { display: grid; gap: 9px; padding-top: 12px; }
    .qq-api-import label { color: var(--studio-muted); font-size: 11px; line-height: 1.6; }
    .qq-api-import textarea { resize: vertical; min-height: 92px; }
    .qq-api-keys > .config-message:empty { display: none; }
    .qq-api-footer { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding: 14px var(--service-inset); border-top: 1px solid var(--studio-border); background: color-mix(in srgb, var(--studio-soft) 45%, transparent); border-radius: 0 0 11px 11px; }
    .qq-api-footer small { color: var(--studio-muted); font-size: 11px; }
    .qq-api-footer > div { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-left: auto; }
    @media (max-width: 560px) {
      .qq-api-header { align-items: stretch; flex-direction: column; gap: 12px; padding: 16px; }
      .qq-api-toggle { justify-content: space-between; }
      .qq-api-keys { padding: 16px; }
      .qq-api-footer { padding: 14px 16px; }
      .admin-list-item { gap: 6px; padding-left: 8px; }
      .admin-list-item code { font-size: 11px; }
      .admin-list-remove { min-height: 44px; }
    }
    @media (min-width: 1080px) {
      #basic-config-editor:has(> [data-config-category="basic_settings"]):has(> [data-config-category="help_web_settings"]) {
        grid-template-columns: minmax(0, .85fr) minmax(0, 1.15fr);
      }
      #basic-config-editor [data-config-category="help_web_settings"] .config-fields {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 410px) {
      .studio-bot-tabs button { font-size: 12px; }
      .studio-bot-tabs svg { width: 14px; height: 14px; }
    }
    #page-bot .qq-reader-toolbar { flex-wrap: wrap; margin: 0 0 16px; gap: 10px; font-size: 12px; }
    #page-bot .qq-reader-accounts { gap: 14px; grid-template-columns: repeat(auto-fill, minmax(min(100%, 226px), 280px)); }
    #page-bot .qq-reader-account {
      padding: 16px;
      border-color: var(--studio-border);
      border-radius: 11px;
      background: var(--studio-card);
      box-shadow: var(--studio-shadow);
    }
    #page-bot .qq-reader-account.is-current {
      border-color: var(--studio-accent);
      background: var(--studio-accent-soft);
    }
    #page-bot .qq-reader-account-open { margin: 16px 0 14px; }
    #page-bot .qq-reader-account-vip { padding-top: 12px; gap: 5px; }
    #page-bot .qq-reader-empty { padding: 24px 16px; background: var(--studio-soft); }
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
    #page-bot .zlibrary-table :is(th, td):first-child { padding-left: 14px; }
    #page-bot .zlibrary-table :is(th, td):last-child { padding-right: 14px; }
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
      border-radius: 14px;
      background: var(--studio-card);
      box-shadow: var(--studio-float-shadow);
    }
    body:not(.messages-workspace) .zlibrary-dialog .zlibrary-action.is-primary,
    #page-bot .zlibrary-action.is-primary {
      background: var(--accent-fill);
      border-color: var(--accent-fill);
      color: #fff;
    }
    body:not(.messages-workspace) .zlibrary-dialog .zlibrary-action.is-primary:hover:not(:disabled),
    #page-bot .zlibrary-action.is-primary:hover:not(:disabled) {
      background: var(--accent-hover);
      border-color: var(--accent-hover);
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
      border-color: var(--accent-fill);
      border-radius: 10px;
      background: var(--accent-fill);
      color: #fff;
    }
    #page-pans .pan-add-account:hover:not(:disabled) {
      background: var(--accent-hover);
      border-color: var(--accent-hover);
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
      .studio-novel-grid { grid-template-columns: minmax(0, 1fr); }
      .studio-novel-settings { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .studio-novel-settings .studio-service-head { grid-column: 1 / -1; }
    }
    @media (max-width: 560px) {
      .studio-novel-settings { grid-template-columns: minmax(0, 1fr); }
      #page-bot .qq-reader-accounts { grid-template-columns: minmax(0, 1fr); }
      #page-novels #novel-grid {
        grid-template-columns: repeat(auto-fit, minmax(min(100%, 135px), 1fr));
        gap: 8px;
      }
      #page-novels .novel-item { padding: 10px; }
      #page-novels .novel-item-main { gap: 7px; }
      #page-novels .novel-badge { width: 28px; height: 28px; border-radius: 9px; }
      #page-pans .pan-tab { min-height: 47px; }
    }

    /* STV 账号卡片与账号详情弹窗。 */
    #bot-panel-stv .studio-service-head { flex-wrap: wrap; }
    #bot-panel-stv .stv-page-actions { display: flex; flex-wrap: wrap; gap: 8px; }
    #bot-panel-stv .outline-button,
    .stv-modal .outline-button { min-height: 44px; padding: 9px 14px; font-size: 13px; }
    #stv-summary { margin: 0 0 16px; color: var(--studio-muted); font-size: 13px; line-height: 1.6; }
    .stv-accounts { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 320px)); gap: 16px; }
    .stv-account-card { min-width: 0; overflow: hidden; border: 1px solid var(--studio-border); border-radius: 14px; background: var(--studio-card); }
    .stv-card-open { display: flex; align-items: center; gap: 12px; width: 100%; min-height: 104px; padding: 20px 18px; border: 0; border-radius: 0; background: transparent; color: var(--studio-ink); text-align: left; font: inherit; }
    .stv-card-open:hover { background: var(--studio-soft); }
    .stv-card-avatar { display: grid; place-items: center; width: 46px; height: 46px; flex: 0 0 46px; border-radius: 12px; background: var(--studio-accent-soft); color: var(--studio-accent); font-size: 18px; font-weight: 650; }
    .stv-card-copy { display: grid; gap: 5px; min-width: 0; flex: 1; }
    .stv-card-name { color: var(--studio-ink); font-size: 15px; font-weight: 650; line-height: 1.5; overflow-wrap: anywhere; }
    .stv-card-meta { color: var(--studio-muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
    .stv-card-arrow { flex: 0 0 auto; color: var(--studio-muted); }
    .stv-card-arrow svg { display: block; width: 18px; height: 18px; }
    .stv-card-state { margin: 0; padding: 11px 18px; border-top: 1px solid var(--studio-border); background: var(--studio-soft); color: var(--studio-muted); font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
    .stv-card-state.is-running { background: var(--mint); color: var(--mint-ink); }
    .stv-card-state.is-error { color: var(--danger); }
    .stv-modal { width: min(640px, calc(100vw - 32px)); }
    .stv-modal .qq-reader-modal-head { gap: 12px; padding: 16px 20px; }
    .stv-modal-heading { min-width: 0; }
    .stv-modal-heading h3 { overflow-wrap: anywhere; }
    #stv-modal-subtitle { margin: 5px 0 0; color: var(--studio-muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
    #stv-modal-subtitle:empty { display: none; }
    .stv-modal .qq-reader-modal-close { display: grid; place-items: center; width: 44px; height: 44px; flex: 0 0 44px; border-radius: 10px; }
    .stv-modal .qq-reader-modal-close svg { width: 20px; height: 20px; }
    .stv-modal .stv-modal-body { padding: 0 20px 20px; }
    .stv-modal [hidden] { display: none !important; }
    #stv-login-panel { padding-top: 20px; }
    #stv-login-form { display: grid; gap: 16px; }
    .stv-modal .config-field label { color: var(--studio-muted); font-size: 12px; font-weight: 550; }
    .stv-modal .config-field input { min-height: 44px; border-radius: 9px; font-size: 14px; }
    .stv-modal .config-actions { flex-wrap: wrap; gap: 8px; }
    .stv-detail-tabs { display: flex; gap: 4px; margin: 0; border-bottom: 1px solid var(--studio-border); }
    .stv-detail-tabs button { min-width: 0; min-height: 52px; flex: 1; padding: 12px 8px; border: 0; border-bottom: 2px solid transparent; border-radius: 0; background: transparent; color: var(--studio-muted); font: inherit; font-size: 14px; }
    .stv-detail-tabs button:hover { color: var(--studio-ink); background: var(--studio-soft); }
    .stv-detail-tabs button[aria-selected="true"] { border-bottom-color: var(--studio-accent); color: var(--studio-accent); font-weight: 650; }
    .stv-detail-pane:not([hidden]) { display: grid; gap: 20px; padding-top: 20px; }
    .stv-section-result { color: var(--studio-ink); font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
    .stv-section-result:empty { display: none; }
    .stv-profile-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px 24px; margin: 0; }
    .stv-profile-grid > div { min-width: 0; padding-bottom: 12px; border-bottom: 1px solid var(--studio-border); }
    .stv-profile-grid dt { margin: 0 0 5px; color: var(--studio-muted); font-size: 12px; }
    .stv-profile-grid dd { margin: 0; color: var(--studio-ink); font-size: 14px; font-weight: 550; overflow-wrap: anywhere; }
    .stv-modal .stv-logout { margin-left: auto; }
    #stv-inventory-result:not(:empty) { display: grid; gap: 14px; }
    .stv-item-group h4 { margin: 0 0 8px; color: var(--studio-ink); font-size: 17px; font-weight: 550; }
    .stv-item-row { display: flex; flex-wrap: wrap; gap: 4px; }
    .stv-item-open { display: grid; place-items: center; width: 48px; height: 48px; padding: 0; border: 0; border-radius: 0; background: transparent; color: var(--studio-ink); }
    .stv-item-picture { position: relative; display: grid; place-items: center; box-sizing: border-box; width: 48px; height: 48px; border: 2px solid var(--studio-border); background: var(--studio-soft); }
    .stv-item-picture img { display: block; width: 44px; height: 44px; object-fit: contain; }
    .stv-item-picture[data-level="2"] { border-color: #07f747; }
    .stv-item-picture[data-level="3"] { border-color: #00aeff; }
    .stv-item-picture[data-level="4"] { border-color: #bb00ff; }
    .stv-item-count { position: absolute; right: 1px; bottom: 0; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding: 0 2px; color: #fff; background: #000b; font-size: 13px; font-variant-numeric: tabular-nums; line-height: 1.2; }
    .stv-item-tooltip { position: fixed; z-index: 2; box-sizing: border-box; width: max-content; max-width: min(270px, calc(100vw - 16px)); max-height: calc(100vh - 16px); max-height: calc(100dvh - 16px); overflow: hidden; overflow-wrap: anywhere; padding: 6px 9px; border: 1px solid #222; border-radius: 8px; background: #303030f2; color: #fff; font-size: 13px; line-height: 1.45; pointer-events: none; }
    .stv-item-tooltip strong { display: block; font-weight: 700; }
    .stv-item-tooltip p { margin: 2px 0 0; }
    .stv-item-dialog { width: min(520px, calc(100vw - 20px)); }
    .stv-item-dialog .qq-reader-modal-head { padding: 6px 12px; background: var(--studio-soft); }
    .stv-item-dialog .qq-reader-modal-close { border-radius: 7px; }
    .stv-item-dialog-body { display: grid; gap: 12px; padding: 14px 16px 16px; }
    #stv-item-result { text-align: center; font-size: 15px; line-height: 1.6; }
    #stv-item-result strong { display: block; font-size: 16px; }
    #stv-item-result p { margin: 4px 0 0; }
    #stv-item-result .stv-item-level { margin-top: 0; }
    #stv-item-choice { display: grid; gap: 5px; margin: 0; color: var(--studio-muted); font-size: 13px; }
    .stv-item-instance { box-sizing: border-box; width: 100%; min-height: 44px; padding: 8px; border: 1px solid var(--studio-border); border-radius: 8px; background: var(--studio-card); color: var(--studio-ink); font: inherit; }
    #stv-item-message:empty { display: none; }
    .stv-item-actions { justify-content: flex-end; }
    #stv-use { min-width: 74px; min-height: 44px; padding: 8px 16px; border: 1px solid transparent; border-radius: 8px; background: #247b20; color: #fff; font-size: 14px; font-weight: 700; }
    #stv-use:not(:disabled):hover { background: #1c6719; }
    #stv-use:disabled { background: var(--studio-soft); color: var(--studio-muted); border-color: var(--studio-border); cursor: default; }
    .stv-item-instance:focus-visible { outline: 2px solid var(--studio-accent); outline-offset: 2px; }
    .stv-reading-status { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; padding: 16px; border-radius: 10px; background: var(--studio-soft); }
    .stv-reading-status > div { display: grid; gap: 7px; min-width: 0; }
    .stv-reading-status span { color: var(--studio-muted); font-size: 12px; }
    .stv-reading-status strong { color: var(--studio-ink); font-size: 15px; font-weight: 600; line-height: 1.5; overflow-wrap: anywhere; }
    .stv-reading-controls { display: grid; }
    .stv-switch-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 56px; border-bottom: 1px solid var(--studio-border); font-size: 13px; color: var(--studio-ink); }
    #stv-account-dialog .stv-switch-row .switch { position: relative; box-sizing: border-box; width: 48px; min-width: 48px; height: 44px; min-height: 44px; flex: 0 0 48px; margin: 0; padding: 0; border: 0; background: transparent; }
    #stv-account-dialog .stv-switch-row .switch::before { content: ""; position: absolute; inset: auto; top: 50%; left: 0; width: 48px; height: 24px; transform: translateY(-50%); border-radius: 999px; background: var(--studio-border); pointer-events: none; }
    #stv-account-dialog .stv-switch-row .switch.on::before { background: var(--studio-accent); }
    #stv-account-dialog .stv-switch-row .switch span { position: absolute; top: 50%; left: 3px; width: 18px; height: 18px; margin: 0; transform: translateY(-50%); background: var(--studio-card); pointer-events: none; }
    #stv-account-dialog .stv-switch-row .switch.on span { transform: translate(24px, -50%); }
    .stv-log-section { min-width: 0; }
    .stv-log-section h4 { margin: 0 0 12px; color: var(--studio-ink); font-size: 13px; font-weight: 650; }
    .stv-reward-logs { list-style: none; margin: 0; padding: 0; }
    .stv-log-row { display: grid; grid-template-columns: 126px minmax(0, 1fr); gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--studio-border); font-size: 12px; line-height: 1.6; }
    .stv-log-row time { color: var(--studio-muted); font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
    .stv-log-copy { color: var(--studio-ink); overflow-wrap: anywhere; }
    .stv-log-row.is-error .stv-log-copy { color: var(--danger); }
    .stv-log-empty { padding: 16px 0; color: var(--studio-muted); font-size: 13px; line-height: 1.6; }
    #stv-result { margin-top: 16px; font-size: 13px; overflow-wrap: anywhere; }
    #stv-result:empty { display: none; }
    #bot-panel-stv button:focus-visible,
    .stv-modal :is(button, input, [role="tabpanel"]):focus-visible { outline: 2px solid var(--studio-accent); outline-offset: 3px; }
    #bot-panel-stv .stv-card-open:focus-visible { outline-offset: -3px; }
    @media (max-width: 520px) {
      .stv-accounts { grid-template-columns: minmax(0, 1fr); }
      .stv-modal { width: calc(100vw - 20px); }
      .stv-modal .qq-reader-modal-head { padding: 12px 14px; }
      .stv-modal .stv-modal-body { padding: 0 14px 16px; }
      .stv-detail-pane:not([hidden]) { gap: 18px; padding-top: 18px; }
      .stv-profile-grid { gap: 12px; }
      .stv-reading-status { gap: 12px; padding: 13px; }
      .stv-log-row { grid-template-columns: minmax(0, 1fr); gap: 3px; }
      .stv-modal .stv-logout { margin-left: 0; }
    }
"""
