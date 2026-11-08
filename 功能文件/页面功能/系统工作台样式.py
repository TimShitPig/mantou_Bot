"""运行状态、帮助指令和系统设置的样式。"""

系统样式 = """
    .studio-system {
      --system-muted: var(--studio-muted, #68617a);
      --system-border: var(--studio-border, #e8e1f1);
      --system-accent: var(--studio-accent, #6659c1);
      --system-soft: var(--studio-soft, #f7f4fd);
      color: var(--studio-ink, #27213d);
    }
    .studio-system-heading {
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      flex-wrap: wrap; min-width: 0;
    }
    .studio-system > .studio-system-heading { margin: 0 0 14px; }
    .studio-system h2 { margin: 2px 0 0; font-size: 18px; line-height: 1.4; }
    .studio-system-heading .studio-kicker,
    .studio-help-intro .studio-kicker { margin: 0 0 4px; }
    .studio-system-source {
      padding: 5px 10px; border: 1px solid var(--system-border);
      border-radius: 99px; background: var(--system-soft);
      color: var(--system-muted); font-size: 12px; white-space: nowrap;
    }
    .studio-resource-grid, .studio-system-split, .studio-help-catalog, .studio-settings-layout {
      display: grid; gap: 16px; min-width: 0;
    }
    .studio-resource-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .studio-system-split {
      grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 16px;
    }
    .studio-system .studio-resource, .studio-system .studio-system-card, .studio-system .studio-command-card {
      min-width: 0; padding: clamp(15px, 2.2vw, 24px);
    }
    .studio-system .studio-resource {
      display: grid; grid-template-columns: 44px minmax(0, 1fr);
      grid-template-rows: auto 1fr; column-gap: 13px; align-items: start;
    }
    .studio-system-icon {
      grid-row: 1 / -1; width: 44px; height: 44px; display: grid;
      place-items: center; border-radius: 14px;
      color: var(--system-accent); background: var(--studio-accent-soft, #ece6ff);
    }
    .studio-system-icon svg {
      width: 24px; height: 24px; fill: none; stroke: currentColor;
      stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round;
    }
    .studio-system-icon.is-peach { color: #8f4a32; background: #ffe5d6; }
    .studio-system-icon.is-mint { color: #326859; background: #dff2e8; }
    .studio-resource h3 { margin: 0; font-size: 13px; color: var(--system-muted); }
    .studio-resource strong {
      margin-top: 4px; font-size: clamp(16px, 2.1vw, 24px);
      line-height: 1.3; overflow-wrap: anywhere; font-variant-numeric: tabular-nums;
    }
    .studio-system-detail { margin: 12px 0 0; }
    .studio-system-detail > div {
      display: flex; align-items: baseline; justify-content: space-between;
      gap: 8px 14px; padding: 12px 0; border-top: 1px solid var(--system-border);
    }
    .studio-system-detail > div:last-child { padding-bottom: 0; }
    .studio-system-detail dt { flex: none; color: var(--system-muted); font-size: 13px; }
    .studio-system-detail dd {
      margin: 0; text-align: end; min-width: 0; overflow-wrap: anywhere;
      font-size: 13px; font-weight: 700;
    }
    .studio-system-link {
      display: inline-flex; align-items: center; min-height: 36px; gap: 5px;
      padding: 5px 10px; border-radius: 9px; color: var(--system-accent);
      background: var(--studio-accent-soft, #ece6ff);
      font-size: 12px; font-weight: 700; text-decoration: none;
    }
    .studio-system-link:hover { text-decoration: underline; }
    .studio-system-link:focus-visible { outline: 2px solid var(--system-accent); outline-offset: 2px; }

    .studio-system .studio-help-intro {
      display: flex; align-items: center; justify-content: space-between; gap: 20px;
      min-height: 120px; padding: clamp(16px, 2.5vw, 26px); margin-bottom: 16px;
      background: linear-gradient(116deg, var(--system-soft), var(--studio-card, #fffdfd) 72%, var(--system-soft));
    }
    .studio-help-intro h2 { font-size: clamp(20px, 2.5vw, 27px); }
    .studio-help-intro p:not(.studio-kicker), .studio-system-description {
      color: var(--system-muted); font-size: 13px; line-height: 1.65; margin: 7px 0 0;
    }
    .studio-help-art { flex: 0 0 auto; width: clamp(64px, 12vw, 135px); color: var(--system-accent); }
    .studio-help-catalog { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .studio-commands { margin: 13px 0 0; }
    .studio-commands > div {
      padding: 10px 0; border-top: 1px solid var(--system-border); min-width: 0;
    }
    .studio-commands > div:last-child { padding-bottom: 0; }
    .studio-commands dt { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; }
    .studio-commands code {
      padding: 3px 8px; border: 1px solid var(--system-border); border-radius: 7px;
      color: var(--studio-ink, #27213d); background: var(--system-soft);
      font-family: inherit; overflow-wrap: anywhere;
    }
    .studio-commands dd { margin: 5px 0 0; color: var(--system-muted); font-size: 12px; }

    .studio-settings-layout { grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); align-items: start; }
    .studio-db-tags {
      display: flex; align-items: center; flex-wrap: wrap; gap: 7px 10px; min-width: 0;
    }
    .studio-db-status { color: var(--system-muted); font-size: 12px; }
    .studio-db-status strong { margin-inline-start: 3px; }
    #database-config-editor { margin-top: 18px; gap: 14px; }
    #database-config-editor .config-group {
      padding: 0; border: 0; background: transparent; border-radius: 0;
    }
    #database-config-editor .config-group > h3 { margin-bottom: 10px; }
    #database-config-editor .config-fields {
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr));
      gap: 14px 16px;
      align-items: start;
    }
    #database-config-editor .config-field label { color: var(--system-muted); font-size: 12px; }
    #database-config-editor .config-field small { font-size: 11px; }
    #database-config-editor .config-field :is(input, select) {
      min-height: 42px; border-radius: 10px; border-color: var(--system-border);
      background: var(--system-soft); color: var(--studio-ink, #27213d);
    }
    #database-config-editor .config-field :is(input, select):focus {
      border-color: var(--system-accent); box-shadow: 0 0 0 3px var(--studio-accent-soft, #ece6ff);
    }
    .studio-db-account, .studio-db-advanced { grid-column: 1 / -1; }
    .studio-db-account {
      min-width: 0; margin: 0; padding: 12px;
      border: 1px solid var(--system-border); border-radius: 12px;
    }
    .studio-db-account legend { padding: 0 5px; font-weight: 700; font-size: 13px; }
    .studio-db-details { min-width: 0; }
    .studio-db-advanced {
      border: 1px solid var(--system-border); border-radius: 12px;
    }
    .studio-db-name { margin-top: 10px; }
    .studio-db-details > summary {
      display: flex; flex-wrap: wrap; align-items: center; gap: 4px 9px;
      min-height: 44px; padding: 8px 11px; border-radius: 11px;
      background: var(--system-soft); color: var(--system-accent);
      cursor: pointer; list-style: none; font-weight: 700;
    }
    .studio-db-details > summary::-webkit-details-marker { display: none; }
    .studio-db-details > summary::after {
      content: ""; width: 6px; height: 6px; margin-inline-start: auto;
      border: solid currentColor; border-width: 0 1.5px 1.5px 0;
      transform: rotate(45deg);
    }
    .studio-db-details[open] > summary::after { transform: rotate(225deg); }
    .studio-db-details > summary:focus-visible {
      outline: 2px solid var(--system-accent); outline-offset: 2px;
    }
    .studio-db-details > summary small {
      color: var(--system-muted); font-size: 11px; font-weight: 550;
    }
    .studio-db-name[open] > .config-field { margin-top: 12px; }
    .studio-db-advanced[open] > .config-fields { padding: 12px; }
    #database-config-editor .config-actions {
      flex-wrap: wrap; padding-top: 15px; border-top: 1px solid var(--system-border);
    }
    #database-config-editor .database-test-result { margin-top: 0; overflow-wrap: anywhere; }
    .studio-system-state {
      display: inline-block; padding: 2px 8px; border-radius: 99px;
      color: var(--system-muted); background: var(--system-soft);
    }
    .studio-system-state.good { color: var(--mint-ink); background: var(--mint); }
    .studio-settings-guide .studio-kicker { margin: 0 0 4px; }
    .studio-settings-guide ul {
      margin: 10px 0 0; padding-left: 18px; color: var(--system-muted);
      font-size: 13px; line-height: 1.65;
    }
    .studio-settings-guide li + li { margin-top: 6px; }
    @media (max-width: 900px) {
      .studio-settings-layout { grid-template-columns: minmax(0, 1fr); }
    }
    @media (max-width: 720px) {
      .studio-resource-grid, .studio-system-split, .studio-help-catalog {
        grid-template-columns: minmax(0, 1fr);
      }
    }
    @media (max-width: 520px) {
      .studio-system-detail > div { flex-wrap: wrap; }
      .studio-system-detail dd { text-align: start; }
    }
"""
