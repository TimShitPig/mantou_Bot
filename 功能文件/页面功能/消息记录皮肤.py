"""消息记录的浅紫皮肤，与三栏布局和交互样式分开维护。"""

消息记录皮肤 = """
    :root body.messages-workspace {
      --bg:#f4f1fc;
      --ink:#28233c;
      --muted:#605975;
      --soft:#6b6380;
      --line:#e1daee;
      --panel:#fffdfd;
      --raised:#f4f0fa;
      --input:#f6f2fb;
      --hover:#eee8f9;
      --primary:#6659c1;
      --primary-dark:#5346a6;
      --primary-soft:#ede8fc;
      --accent-fill:#6659c1;
      --accent-hover:#5748ac;
      --rail:#eee9fa;
      --msg-list-bg:#f9f6fd;
      --msg-head-bg:#fffdfd;
      --msg-composer-bg:#fffdfd;
      --msg-chat-active-bg:#e8e0fb;
      --msg-surface:radial-gradient(ellipse at 94% 0%, #fff1e8 0, transparent 39%),
                    linear-gradient(140deg,#f4f1fc,#faf8fe 62%,#f6f2fc);
      --msg-incoming-fill:linear-gradient(145deg,#fffdfd,#faf7ff);
      --msg-bubble-line:#e6deef;
      --msg-file-fill:linear-gradient(145deg,#fffdfd,#f9f5ff);
      --msg-file-line:#e1d7ef;
      --msg-self-fill:linear-gradient(145deg,#ebe6ff,#e4dcfb);
      --msg-self-bg:#e8e1fc;
      --msg-self-ink:#322658;
      --msg-self-line:#d5c8ee;
      --msg-self-inset:#f4efff;
      --msg-self-inset-hover:#ebe4fb;
      --msg-self-muted:#5d527b;
      --msg-self-link:#504197;
      --msg-scroll-track:#f1ecf8;
      --msg-scroll-thumb:#9c8eaf;
      --msg-scroll-thumb-hover:#756585;
      --msg-control-ink:#55486e;
      --msg-quote-line:#a298d4;
      --msg-quote-fill:#f3eefb;
      --msg-list-fill:linear-gradient(160deg,#fffafd,#f7f3fc 48%,#fbf9ff);
      --msg-button-fill:linear-gradient(135deg,#7263cd,#5c4db8);
      --msg-button-hover:linear-gradient(135deg,#6555bf,#5241a7);
      --msg-owner-fill:#fcebd9;
      --msg-owner-ink:#82552c;
      --msg-overlay:#2e224e59;
      --msg-document-light:#b2a4ed;
      --msg-document-mid:#8c7ad9;
      --msg-document-dark:#7161c2;
      --msg-document-fold:#6454ae;
      --msg-document-lines:#fff8ff;
      --shadow:0 9px 28px #44366324;
    }
    :root[data-theme="dark"] body.messages-workspace {
      --bg:#211b2d;
      --ink:#f5effc;
      --muted:#d0c4e1;
      --soft:#b8accb;
      --line:#463a57;
      --panel:#2b2238;
      --raised:#352a46;
      --input:#31273f;
      --hover:#3b2e4e;
      --primary:#c6b7ff;
      --primary-dark:#d4c8ff;
      --primary-soft:#42355b;
      --accent-fill:#7660c3;
      --accent-hover:#7964c4;
      --rail:#292034;
      --msg-list-bg:#292136;
      --msg-head-bg:#2a2237;
      --msg-composer-bg:#2b2339;
      --msg-chat-active-bg:#44365e;
      --msg-surface:radial-gradient(ellipse at 94% 0%, #372839 0, transparent 48%),
                    linear-gradient(140deg,#211b2d,#292037 66%,#251d33);
      --msg-incoming-fill:linear-gradient(145deg,#392e4a,#34293f);
      --msg-bubble-line:#4a3c58;
      --msg-file-fill:linear-gradient(145deg,#392e4a,#342a43);
      --msg-file-line:#4f405f;
      --msg-self-fill:linear-gradient(145deg,#554383,#48366f);
      --msg-self-bg:#4e3c78;
      --msg-self-ink:#faf4ff;
      --msg-self-line:#675294;
      --msg-self-inset:#40315f;
      --msg-self-inset-hover:#47366b;
      --msg-self-muted:#e4d9f4;
      --msg-self-link:#eee1ff;
      --msg-scroll-track:#30263f;
      --msg-scroll-thumb:#9787ad;
      --msg-scroll-thumb-hover:#bdabd0;
      --msg-control-ink:#d9cce8;
      --msg-quote-line:#9580ba;
      --msg-quote-fill:#30263e;
      --msg-list-fill:linear-gradient(155deg,#30263e,#292136 70%);
      --msg-button-fill:linear-gradient(135deg,#7460c2,#6b52b6);
      --msg-button-hover:linear-gradient(135deg,#7964c4,#735bbe);
      --msg-owner-fill:#503748;
      --msg-owner-ink:#ffd1ad;
      --msg-overlay:#120c1cb3;
      --msg-document-light:#a991e5;
      --msg-document-mid:#8771cd;
      --msg-document-dark:#7159bb;
      --msg-document-fold:#644da8;
      --msg-document-lines:#fff8ff;
      --shadow:0 9px 28px #10091670;
    }

    /* 仅覆盖硬编码的旧色值；布局尺寸、字体和可见性由消息工作区样式负责。 */
    :root body.messages-workspace .chat-list-panel { background:var(--msg-list-fill); }
    :root[data-theme] body.messages-workspace .msg-tool-btn,
    :root[data-theme] body.messages-workspace .msg-file-action { color:var(--msg-control-ink); }
    :root[data-theme] body.messages-workspace .msg-tool-btn:hover,
    :root[data-theme] body.messages-workspace .msg-file-action:hover { color:var(--primary-dark); }
    :root body.messages-workspace .msg-chat.pinned:not(.active) { background:var(--primary-soft); }
    :root body.messages-workspace .msg-chat.pinned:not(.active):hover { background:var(--hover); }
    :root body.messages-workspace .msg-chat-avatar,
    :root body.messages-workspace .msg-avatar { background:var(--primary-soft); color:var(--primary-dark); }
    :root body.messages-workspace .msg-chat-avatar .avatar-letter,
    :root body.messages-workspace .msg-avatar .avatar-letter { color:var(--primary-dark); }
    :root body.messages-workspace .msg-chat.removed .msg-chat-sub { color:var(--danger); }
    :root body.messages-workspace .msg-chats { scrollbar-color:var(--msg-scroll-thumb) var(--msg-scroll-track); }
    :root body.messages-workspace .msg-list-resizer::before,
    :root body.messages-workspace .msg-composer-resizer::before { background:var(--msg-scroll-thumb); }

    :root body.messages-workspace .msg-bubble-quote {
      border-left-color:var(--msg-quote-line);
      background:var(--msg-quote-fill);
      color:var(--muted);
    }
    :root body.messages-workspace .msg-quote-jump:hover { background:var(--hover); }
    :root body.messages-workspace .msg-row.self .msg-bubble .msg-quote-jump:hover { background:var(--msg-self-inset-hover); }
    :root body.messages-workspace .msg-quote-preview { border-color:var(--msg-quote-line); }
    :root body.messages-workspace .msg-mention-chip,
    :root body.messages-workspace .msg-group-role,
    :root body.messages-workspace .msg-tag.bot {
      background:var(--primary-soft);
      color:var(--primary-dark);
    }
    :root body.messages-workspace .msg-mention-marker,
    :root body.messages-workspace .composer-mention { color:var(--primary-dark); }
    :root body.messages-workspace .msg-row.self .msg-mention-chip { background:var(--msg-self-inset); color:var(--msg-self-link); }
    :root body.messages-workspace .msg-row.self .msg-mention-marker { color:var(--msg-self-link); }
    :root body.messages-workspace .msg-tag.role.owner { background:var(--msg-owner-fill); color:var(--msg-owner-ink); }
    :root body.messages-workspace .msg-file-card:hover { background:var(--hover); }
    :root body.messages-workspace .msg-row.self .msg-file-card { background:var(--msg-self-inset); }
    :root body.messages-workspace .msg-row.self .msg-file-card:hover { background:var(--msg-self-inset-hover); }
    :root body.messages-workspace .msg-file-info small { color:var(--muted); }
    :root body.messages-workspace .msg-row.self .msg-file-info small { color:var(--msg-self-muted); }
    :root body.messages-workspace .msg-row.self .msg-file-action { color:var(--msg-self-link); }
    :root body.messages-workspace .msg-attachment-icon { background:var(--primary-soft); color:var(--primary-dark); }
    :root body.messages-workspace #msg-document-fill stop:nth-child(1) { stop-color:var(--msg-document-light); }
    :root body.messages-workspace #msg-document-fill stop:nth-child(2) { stop-color:var(--msg-document-mid); }
    :root body.messages-workspace #msg-document-fill stop:nth-child(3) { stop-color:var(--msg-document-dark); }
    :root body.messages-workspace #msg-document-symbol path:nth-of-type(2) { fill:var(--msg-document-fold); }
    :root body.messages-workspace #msg-document-symbol path:nth-of-type(3) { stroke:var(--msg-document-lines); }

    :root body.messages-workspace #msg-send {
      background:var(--msg-button-fill);
      border-color:var(--accent-fill);
      color:#fff;
      box-shadow:inset 0 1px 0 #fff3,0 1px 3px #33236626;
    }
    :root body.messages-workspace #msg-send:not(:disabled):hover { background:var(--msg-button-hover); border-color:var(--accent-hover); }
    :root body.messages-workspace .msg-new-messages,
    :root body.messages-workspace .msg-new-messages:hover,
    :root body.messages-workspace .msg-mention-picker,
    :root body.messages-workspace .msg-ctx,
    :root body.messages-workspace .msg-head-menu-panel { box-shadow:var(--shadow); }
    :root body.messages-workspace .msg-group-member-detail { border-color:var(--line); }
    :root body.messages-workspace .msg-ctx-sep { background:var(--line); }
    :root body.messages-workspace .msg-ctx-item.danger:hover { background:var(--danger-bg); }
    :root body.messages-workspace .msg-raw-modal,
    :root body.messages-workspace .msg-mute-modal,
    :root body.messages-workspace .msg-remark-modal,
    :root body.messages-workspace .msg-clear-modal,
    :root body.messages-workspace .msg-group-mask { background:var(--msg-overlay); }
    :root body.messages-workspace .msg-raw-box,
    :root body.messages-workspace .msg-mute-box,
    :root body.messages-workspace .msg-remark-box,
    :root body.messages-workspace .msg-clear-box,
    :root body.messages-workspace .msg-group-drawer { box-shadow:var(--shadow); }
"""
