"""消息记录的浅紫皮肤，与三栏布局和交互样式分开维护。"""

from .新版外观样式 import 新版外观样式

消息记录皮肤 = """
    :root body.messages-workspace {
      --bg:#f6f5f8;
      --ink:#282632;
      --muted:#696574;
      --soft:#696574;
      --line:#e6e3eb;
      --panel:#ffffff;
      --raised:#f5f3f8;
      --input:#f5f3f8;
      --hover:#eeebf4;
      --primary:#6554b2;
      --primary-dark:#54439b;
      --primary-soft:#eeeaf8;
      --accent-fill:#6554b2;
      --accent-hover:#54439b;
      --rail:#f5f3f8;
      --msg-list-bg:#ffffff;
      --msg-head-bg:#ffffff;
      --msg-composer-bg:#ffffff;
      --msg-chat-active-bg:#eeeaf8;
      --msg-surface:#f6f5f8;
      --msg-incoming-fill:#ffffff;
      --msg-bubble-line:#e6e3eb;
      --msg-file-fill:#ffffff;
      --msg-file-line:#e6e3eb;
      --msg-self-fill:#eeeaf8;
      --msg-self-bg:#eeeaf8;
      --msg-self-ink:#362c50;
      --msg-self-line:#ded5ef;
      --msg-self-inset:#f6f3fc;
      --msg-self-inset-hover:#e6def4;
      --msg-self-muted:#6b5e82;
      --msg-self-link:#554399;
      --msg-scroll-track:#f1eef5;
      --msg-scroll-thumb:#9b91ab;
      --msg-scroll-thumb-hover:#746980;
      --msg-control-ink:#655f72;
      --msg-quote-line:#aa9cc9;
      --msg-quote-fill:#f5f3f8;
      --msg-list-fill:#ffffff;
      --msg-button-fill:#6554b2;
      --msg-button-hover:#54439b;
      --msg-owner-fill:#f7ede2;
      --msg-owner-ink:#855b37;
      --msg-overlay:#21182f55;
      --msg-document-light:#baaddb;
      --msg-document-mid:#9280bd;
      --msg-document-dark:#74639c;
      --msg-document-fold:#615084;
      --msg-document-lines:#ffffff;
      --shadow:0 8px 28px #28203214;
    }
    :root[data-theme="dark"] body.messages-workspace {
      --bg:#19171f;
      --ink:#eeeaf3;
      --muted:#b1aabc;
      --soft:#b1aabc;
      --line:#3d3747;
      --panel:#24212c;
      --raised:#2b2735;
      --input:#2b2735;
      --hover:#332d40;
      --primary:#c1b0ef;
      --primary-dark:#d4c6f6;
      --primary-soft:#342c47;
      --accent-fill:#7963c0;
      --accent-hover:#745cba;
      --rail:#201d28;
      --msg-list-bg:#24212c;
      --msg-head-bg:#24212c;
      --msg-composer-bg:#24212c;
      --msg-chat-active-bg:#342c47;
      --msg-surface:#19171f;
      --msg-incoming-fill:#2b2735;
      --msg-bubble-line:#3d3747;
      --msg-file-fill:#2b2735;
      --msg-file-line:#3d3747;
      --msg-self-fill:#413458;
      --msg-self-bg:#413458;
      --msg-self-ink:#eeeaf3;
      --msg-self-line:#54426f;
      --msg-self-inset:#342942;
      --msg-self-inset-hover:#453758;
      --msg-self-muted:#c6b8d8;
      --msg-self-link:#d8c8ff;
      --msg-scroll-track:#24212c;
      --msg-scroll-thumb:#83778f;
      --msg-scroll-thumb-hover:#a99cba;
      --msg-control-ink:#bbb3c9;
      --msg-quote-line:#76618f;
      --msg-quote-fill:#24212c;
      --msg-list-fill:#24212c;
      --msg-button-fill:#7963c0;
      --msg-button-hover:#745cba;
      --msg-owner-fill:#49382f;
      --msg-owner-ink:#e8c19e;
      --msg-overlay:#100d16a6;
      --msg-document-light:#b9a8e1;
      --msg-document-mid:#9580c4;
      --msg-document-dark:#7963a6;
      --msg-document-fold:#65508f;
      --msg-document-lines:#f9f5ff;
      --shadow:0 10px 32px #00000040;
    }

    /* 仅覆盖硬编码的旧色值；布局尺寸、字体和可见性由消息工作区样式负责。 */
    :root body.messages-workspace .chat-list-panel { background:var(--msg-list-fill); }
    :root body.messages-workspace .msg-head { background:var(--msg-head-bg); }
    :root body.messages-workspace .msg-composer { background:var(--msg-composer-bg); }
    :root body.messages-workspace .msg-chat.active,
    :root body.messages-workspace .msg-chat.pinned.active,
    :root body.messages-workspace .msg-bubble,
    :root body.messages-workspace .msg-file-card { box-shadow:none; }
    :root body.messages-workspace ::selection { background:var(--primary-soft); color:var(--ink); }
    :root body.messages-workspace input,
    :root body.messages-workspace textarea,
    :root body.messages-workspace .msg-editor { caret-color:var(--primary); }
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
      box-shadow:none;
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

    /* 手机聊天沿用 QQ 的紧凑顶栏、输入行与底部附件工具；桌面保持原布局。 */
    @media (max-width:760px) {
      :root body.messages-workspace.msg-mobile-chat-view {
        --msg-head-bg:#f1f1f3;
        --msg-surface:#f1f1f3;
        --msg-composer-bg:#f7f7f8;
        --msg-incoming-fill:#ffffff;
        --msg-bubble-line:transparent;
        --msg-self-fill:#ffffff;
        --msg-self-bg:#ffffff;
        --msg-self-ink:#25262b;
        --msg-self-line:transparent;
        --msg-self-inset:#f2f3f6;
        --msg-self-inset-hover:#e8edf4;
        --msg-self-muted:#686c74;
        --msg-self-link:#245889;
        --msg-file-fill:#ffffff;
        --msg-file-line:#e5e6e9;
        --msg-control-ink:#3e4148;
        --msg-button-fill:#0872df;
        --msg-button-hover:#0063cb;
        --msg-link-color:#245889;
        --msg-link-hover:#164d80;
        --msg-action-ink:#245889;
        --msg-action-line:#86abc9;
        --msg-mobile-input:#ffffff;
      }
      :root[data-theme="dark"] body.messages-workspace.msg-mobile-chat-view {
        --msg-head-bg:#202125;
        --msg-surface:#18191d;
        --msg-composer-bg:#202125;
        --msg-incoming-fill:#2b2c32;
        --msg-self-fill:#29394d;
        --msg-self-bg:#29394d;
        --msg-self-ink:#f0f2f5;
        --msg-self-inset:#263344;
        --msg-self-inset-hover:#33455a;
        --msg-self-muted:#b8c6d9;
        --msg-self-link:#a8d1ff;
        --msg-file-fill:#2b2c32;
        --msg-file-line:#3d3f47;
        --msg-control-ink:#d0d2da;
        --msg-button-fill:#0872df;
        --msg-button-hover:#0063cb;
        --msg-link-color:#9bc8ff;
        --msg-link-hover:#c1ddff;
        --msg-action-ink:#9bc8ff;
        --msg-action-line:#607c9a;
        --msg-mobile-input:#2b2c32;
      }
      :root body.messages-workspace .msg-head {
        min-height:56px; height:56px; padding:4px 10px 4px 4px; gap:4px;
        border-bottom:0;
      }
      :root body.messages-workspace .msg-head-name { font-size:17px; line-height:1.35; }
      :root body.messages-workspace .msg-head-sub { font-size:12px; line-height:1.35; }
      :root body.messages-workspace .msg-mobile-back,
      :root body.messages-workspace .msg-head-menu-toggle { width:44px; height:44px; min-width:44px; color:var(--ink); }
      :root body.messages-workspace .msg-mobile-back { font-size:34px; }
      :root body.messages-workspace .msg-head-menu-toggle span {
        position:relative; width:20px; height:16px; border-block:2px solid currentColor; font-size:0;
      }
      :root body.messages-workspace .msg-head-menu-toggle span::before {
        position:absolute; top:5px; left:0; width:100%; height:2px; background:currentColor; content:"";
      }
      :root body.messages-workspace .msg-body { padding:16px 12px 8px; }
      :root body.messages-workspace .msg-bubble { font-size:16px; font-weight:400; line-height:1.5; border-radius:12px; }
      :root body.messages-workspace .msg-row.self .msg-bubble { border-radius:12px; }
      :root body.messages-workspace .msg-bubble-name { font-size:12px; line-height:1.4; }
      :root body.messages-workspace .msg-composer,
      :root body.messages-workspace .msg-shell.msg-composer-compact .msg-composer {
        display:grid; grid-template-columns:minmax(0,1fr) 68px;
        grid-template-rows:auto minmax(44px,auto) 44px; gap:6px 10px;
        height:auto !important; min-height:112px; max-height:52%;
        padding:8px 12px max(8px,env(safe-area-inset-bottom)); border-top:0; overflow:auto;
      }
      :root body.messages-workspace .msg-composer > .msg-extra { grid-column:1 / -1; grid-row:1; }
      :root body.messages-workspace .msg-input-box,
      :root body.messages-workspace .msg-shell.msg-composer-compact .msg-input-box {
        grid-column:1; grid-row:2; align-self:end; min-height:44px; max-height:24dvh;
        border:0; border-radius:12px; background:var(--msg-mobile-input); overflow:auto;
      }
      :root body.messages-workspace .msg-editor,
      :root body.messages-workspace .msg-editor:focus,
      :root body.messages-workspace .msg-shell.msg-composer-compact .msg-editor {
        min-height:44px; padding:10px 12px; font-size:16px; line-height:1.5; background:transparent;
      }
      :root body.messages-workspace .msg-composer-topbar,
      :root body.messages-workspace .msg-shell.msg-composer-compact .msg-composer-topbar {
        grid-column:1 / -1; grid-row:3; top:0; min-height:44px; margin:0; gap:12px; justify-content:space-between;
      }
      :root body.messages-workspace .msg-tool-btn,
      :root body.messages-workspace .msg-shell.msg-composer-compact .msg-tool-btn {
        width:44px; height:44px; padding:8px; border-radius:10px;
      }
      :root body.messages-workspace .msg-tool-btn svg,
      :root body.messages-workspace .msg-shell.msg-composer-compact .msg-tool-btn svg { width:26px; height:26px; }
      :root body.messages-workspace .msg-composer-toggle { width:44px; height:44px; margin:0; opacity:1; }
      :root body.messages-workspace .msg-toolbar,
      :root body.messages-workspace .msg-shell.msg-composer-compact .msg-toolbar { display:contents; }
      :root body.messages-workspace .msg-send-shortcut { display:none; }
      :root body.messages-workspace #msg-send,
      :root body.messages-workspace .msg-shell.msg-composer-compact #msg-send {
        grid-column:2; grid-row:2; align-self:end; min-width:68px; min-height:44px;
        padding:8px 12px; border:0; border-radius:12px; font-size:16px; font-weight:500;
      }
      :root body.messages-workspace .msg-shell.msg-composer-collapsed .msg-composer {
        display:flex; min-height:52px; max-height:52px; padding:4px 12px;
      }
      :root body.messages-workspace .msg-shell.msg-composer-collapsed .msg-composer-topbar { min-height:44px; }
    }
"""

# 新版外观覆盖层追加在样式链末尾，统一覆盖控制台与消息记录的外观。
消息记录皮肤 = 消息记录皮肤 + "\n" + 新版外观样式
