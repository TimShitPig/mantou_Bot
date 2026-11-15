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
"""
