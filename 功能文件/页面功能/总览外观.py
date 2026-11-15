"""工作台总览的版式补充：问候、指标、编号业务表。"""

总览外观 = """
    /* ========== 16. 工作台总览：问候 · 指标 · 编号业务表 ========== */
    /* 总览页不再重复“控制台”标题：问候语自己当主角。 */
    body:has(#page-dashboard:not([hidden])) #console-workspace > .page-heading { display: none; }

    .studio-dashboard { display: flex; flex-direction: column; gap: 14px; }
    .dash-top { display: grid; grid-template-columns: minmax(0, 1.68fr) minmax(0, 1fr); gap: 14px; }
    .dash-greet {
      display: flex;
      flex-direction: column;
      gap: 0;
      padding: clamp(20px, 2.4vw, 30px);
      border: 1px solid var(--studio-border);
      border-radius: 12px;
      background: var(--studio-wash);
      box-shadow: none;
    }
    .dash-greet-line {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      color: var(--studio-muted);
      font-size: 11.5px;
      letter-spacing: .04em;
    }
    .dash-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--studio-accent); }
    .dash-greet-title {
      margin: 14px 0 8px;
      font-family: var(--brand-serif);
      font-size: clamp(28px, 3.1vw, 40px);
      font-weight: 700;
      line-height: 1.24;
      letter-spacing: .01em;
    }
    .dash-greet-sub { margin: 0; max-width: 46ch; color: var(--studio-muted); font-size: 13px; line-height: 1.7; }
    .dash-metrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin: 20px 0 18px;
      padding-top: 16px;
      border-top: 1px solid var(--studio-border);
    }
    .dash-metric { padding-right: 16px; border-right: 1px dotted var(--studio-border); }
    .dash-metric:last-child { border-right: 0; padding-right: 0; }
    .dash-metric strong {
      display: block;
      font-family: var(--brand-serif);
      font-size: clamp(20px, 2vw, 26px);
      font-weight: 700;
      line-height: 1.25;
      letter-spacing: .01em;
    }
    .dash-metric span { display: block; margin-top: 4px; color: var(--studio-muted); font-size: 11px; letter-spacing: .1em; }
    .dash-actions { display: flex; flex-wrap: wrap; gap: 9px; margin-top: auto; }
    .dash-actions .studio-primary { margin: 0; }
    .dash-actions .outline-button {
      display: inline-flex;
      align-items: center;
      min-height: 37px;
      padding: 7px 14px;
      font-size: 12.5px;
      text-decoration: none;
    }
    .dash-snap {
      display: flex;
      flex-direction: column;
      padding: clamp(18px, 2vw, 24px);
      border: 1px solid #2b2721;
      border-radius: 12px;
      background: #211e19;
      color: #f2ecdf;
      box-shadow: 0 18px 40px #211e1914;
    }
    :root[data-theme="dark"] .dash-snap { border-color: #332e25; background: #1b1813; box-shadow: none; }
    .dash-snap-head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 10px;
      padding-bottom: 11px;
      border-bottom: 1px solid #ffffff1f;
      color: #d8cfbf;
      font-size: 11.5px;
      letter-spacing: .1em;
    }
    .dash-snap-head a { display: inline-flex; align-items: center; gap: 2px; color: #9fc0ad; font-size: 11px; text-decoration: none; }
    .dash-snap-head a svg { width: 13px; height: 13px; }
    .dash-snap-list { margin: 4px 0 0; }
    .dash-snap-list div {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 0;
      border-bottom: 1px dotted #ffffff21;
    }
    .dash-snap-list dt { color: #a89f8d; font-size: 11.5px; letter-spacing: .04em; }
    .dash-snap-list dd {
      margin: 0;
      color: #f4eee2;
      font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
      font-size: 15px;
      font-weight: 500;
      font-variant-numeric: tabular-nums;
    }
    .dash-snap-foot {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 10px;
      margin-top: auto;
      padding-top: 12px;
      color: #a89f8d;
      font-size: 11.5px;
    }
    .dash-snap-foot strong {
      color: #b9d6c4;
      font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
      font-size: 13px;
      font-weight: 500;
    }
    .dash-biz { padding: clamp(18px, 2.1vw, 26px); border-radius: 12px; }
    .dash-biz-head {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 12px;
      padding-bottom: 12px;
    }
    .dash-biz-head h2 { margin: 0; font-family: var(--brand-serif); font-size: 19px; font-weight: 700; letter-spacing: .02em; }
    .dash-biz-head p { margin: 5px 0 0; color: var(--studio-muted); font-size: 11.5px; }
    .dash-biz-tag {
      padding: 4px 9px;
      border: 1px solid #1c66503d;
      border-radius: 999px;
      color: var(--studio-accent);
      font-size: 10.5px;
      letter-spacing: .06em;
      white-space: nowrap;
    }
    .dash-biz-list { border-top: 1px solid var(--studio-border); }
    .dash-biz-row {
      display: grid;
      grid-template-columns: 30px minmax(0, 1fr) minmax(0, max-content) 30px;
      align-items: center;
      gap: 14px;
      padding: 13px 0;
      border-bottom: 1px dotted var(--studio-border);
    }
    .dash-biz-row:last-child { border-bottom: 0; padding-bottom: 4px; }
    .dash-biz-index {
      color: var(--studio-muted);
      font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
      font-size: 11px;
      letter-spacing: .06em;
    }
    .dash-biz-copy h3 { margin: 0; font-size: 13.5px; font-weight: 640; letter-spacing: .01em; }
    .dash-biz-copy small { display: block; margin-top: 2px; color: var(--studio-muted); font-size: 11.5px; }
    .dash-biz-note { color: var(--studio-muted); font-size: 11.5px; white-space: nowrap; }
    .dash-biz-row > button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 30px;
      height: 30px;
      border: 1px solid var(--studio-border);
      border-radius: 50%;
      background: transparent;
      color: var(--studio-muted);
      cursor: pointer;
    }
    .dash-biz-row > button svg { width: 15px; height: 15px; }
    .dash-biz-row > button:hover { border-color: var(--studio-accent); color: var(--studio-accent); }
    .dash-guide {
      display: grid;
      grid-template-columns: 32px minmax(0, 1fr) 30px;
      align-items: center;
      gap: 12px;
      padding: 16px clamp(18px, 2vw, 24px);
      border-radius: 12px;
    }
    .dash-guide-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      border: 1px solid var(--studio-border);
      border-radius: 8px;
      color: var(--studio-accent);
    }
    .dash-guide-icon svg { width: 17px; height: 17px; }
    .dash-guide h2 { margin: 0; font-family: var(--brand-serif); font-size: 15px; font-weight: 700; }
    .dash-guide p { margin: 3px 0 0; color: var(--studio-muted); font-size: 11.5px; }
    .dash-guide > a {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 30px;
      height: 30px;
      border: 1px solid var(--studio-border);
      border-radius: 6px;
      color: var(--studio-muted);
    }
    .dash-guide > a svg { width: 15px; height: 15px; }
    @media (max-width: 900px) {
      .dash-top { grid-template-columns: minmax(0, 1fr); }
    }
    @media (max-width: 640px) {
      .dash-greet-title { font-size: 26px; }
      .dash-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
      .dash-metric { padding-right: 10px; }
      .dash-metric strong { font-size: 18px; }
      .dash-biz-row { grid-template-columns: 26px minmax(0, 1fr) 30px; }
      .dash-biz-note { display: none; }
    }

    /* ========== 17. 全站轮廓统一：细线卡片、行式列表、统一控件 ========== */
    /* 外层卡片：统一 12px 圆角 + 1px 细线，只留一层近乎不可见的投影 */
    .studio-card:not(.dash-snap) {
      border: 1px solid var(--studio-border);
      border-radius: 12px;
      background: var(--studio-card);
      box-shadow: 0 1px 0 #211e1906;
    }
    :root[data-theme="dark"] .studio-card:not(.dash-snap) { box-shadow: none; }
    /* 卡片头：衬线标题 + 统一灰色眉标，底部一条细线收边 */
    .studio-card-head, .studio-service-head { padding-bottom: 12px; border-bottom: 1px solid var(--studio-border); }
    .studio-card-head h2, .studio-service-head h2, .studio-bot-panel h2 {
      margin: 0;
      font-family: var(--brand-serif);
      font-size: 18px;
      font-weight: 700;
      letter-spacing: .02em;
      line-height: 1.4;
    }
    .studio-kicker, .studio-bot-kicker {
      font-size: 11px;
      letter-spacing: .12em;
      color: var(--studio-muted);
      text-transform: none;
    }
    .studio-card-head p, .studio-service-head p { margin: 5px 0 0; color: var(--studio-muted); font-size: 11.5px; }

    /* 内嵌开关改成“行”，去掉卡中卡的双层边框 */
    .studio-novel-control, .studio-novel-switch-row {
      border: 0;
      border-top: 1px solid var(--studio-border);
      border-radius: 0;
      background: transparent;
      padding: 14px 0;
      margin: 0;
    }
    .studio-novel-settings .studio-novel-control:first-of-type,
    .studio-novel-settings .studio-novel-switch-row:first-of-type { border-top: 0; }

    /* 页头：衬线大标题，收窄字距 */
    .page-heading h1 { font-family: var(--brand-serif); font-size: 27px; font-weight: 700; letter-spacing: .01em; }
    .page-heading p { max-width: 62ch; }

    /* 控件：统一 8px 圆角与高度，焦点环改成竹青细环 */
    .studio-primary, .outline-button, .primary-button { border-radius: 8px; }
    .studio-primary, .primary-button { min-height: 36px; }
    .outline-button { min-height: 36px; }
    :where(a, button, input, select, textarea, [tabindex]):focus-visible {
      outline: 2px solid var(--studio-accent);
      outline-offset: 2px;
    }

    /* 侧栏：导航项统一 8px 圆角，选中态用竹青底色 */
    .studio-nav a { border-radius: 8px; }
    .studio-nav a.active { background: var(--studio-accent-soft); color: var(--studio-ink); }
    :root[data-theme="dark"] .studio-nav a.active { background: #22302a; color: var(--studio-ink); }

    /* 列表行：hover 温和染色，分隔线统一细线 */
    .studio-service-row, .dash-biz-row { transition: background .16s ease; }
    .studio-service-row:hover, .dash-biz-row:hover { background: var(--studio-wash); }

    /* 滚动条与新外观一致 */
    :root body:not(.messages-workspace) * { scrollbar-color: #b9ad96 transparent; }
    :root[data-theme="dark"] body:not(.messages-workspace) * { scrollbar-color: #4a4438 transparent; }

    /* ========== 18. 细节过渡与内层控件统一 ========== */
    /* 深色下让“系统快照”仍保持一块更深的底，不被普通卡片吞掉 */
    :root[data-theme="dark"] .dash-snap { background: #100f0c; border-color: #3a3327; }

    /* 视图切换轻微淡入，操作反馈更连贯（尊重 reduced-motion） */
    body:not(.messages-workspace) .page-view { animation: studioFade .22s ease both; }
    @keyframes studioFade {
      from { opacity: 0; transform: translateY(3px); }
      to { opacity: 1; transform: none; }
    }
    @media (prefers-reduced-motion: reduce) {
      body:not(.messages-workspace) .page-view { animation: none; }
    }

    /* 内层平台选择块：统一 8px 圆角与细线，选中态用竹青底 */
    .pan-tab, .novel-grid, .pan-grid { border-radius: 8px; }
    .pan-tab { border: 1px solid var(--studio-border); border-radius: 8px; background: var(--studio-wash); }
    .pan-tab:hover { border-color: #1c665040; background: var(--studio-soft); }
    .pan-tab.is-active, .pan-tab.active { border-color: var(--studio-accent); background: var(--studio-accent-soft); }
    .novel-grid { border: 1px solid var(--studio-border); overflow: hidden; }

    /* 空状态统一成细线提示块 */
    .empty { border: 1px dashed var(--studio-border); border-radius: 10px; color: var(--studio-muted); }
"""
