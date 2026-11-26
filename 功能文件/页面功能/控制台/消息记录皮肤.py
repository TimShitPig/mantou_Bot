"""消息记录的纸感竹青皮肤，与三栏布局和交互样式分开维护。"""

from ..公共样式.新版外观样式 import 新版外观样式
from .总览外观 import 总览外观

消息记录皮肤 = """
    .msg-media-save-status { display:block; margin-top:4px; color:var(--muted); font-size:11px; }
    .msg-tag.member-removed { background:var(--danger-bg); color:var(--danger); }
    /* 与后台共用表面及控件色；气泡保留独立色值，手机 QQ 配色在下方覆盖。 */
    :root body.messages-workspace {
      --bg:var(--studio-canvas);
      --ink:var(--studio-ink);
      --muted:var(--studio-muted);
      --soft:var(--studio-muted);
      --line:var(--studio-border);
      --panel:var(--studio-card);
      --raised:var(--studio-soft);
      --input:var(--studio-soft);
      --hover:var(--studio-hover);
      --primary:var(--studio-accent);
      --primary-dark:var(--studio-accent-strong);
      --primary-soft:var(--studio-accent-soft);
      --accent-fill:var(--studio-button-fill);
      --accent-hover:var(--studio-button-hover);
      --mint:var(--studio-mint);
      --mint-ink:var(--studio-mint-ink);
      --peach:var(--studio-peach);
      --peach-ink:var(--studio-peach-ink);
      --danger:var(--paper-clay);
      --danger-bg:color-mix(in srgb,var(--danger) 10%,var(--panel));
      --danger-line:color-mix(in srgb,var(--danger) 28%,var(--line));
      --yellow:var(--studio-peach);
      --yellow-ink:var(--paper-gold);
      --pink:var(--danger-bg);
      --pink-ink:var(--danger);
      --rail:var(--studio-soft);
      --msg-list-bg:var(--studio-wash);
      --msg-list-fill:var(--msg-list-bg);
      --msg-head-bg:var(--panel);
      --msg-composer-bg:var(--panel);
      --msg-chat-active-bg:var(--primary-soft);
      --msg-surface:var(--panel);
      --msg-incoming-fill:var(--studio-wash);
      --msg-bubble-line:var(--line);
      --msg-file-fill:var(--panel);
      --msg-file-line:var(--line);
      --msg-self-fill:#dce9e2;
      --msg-self-bg:var(--msg-self-fill);
      --msg-self-ink:#16342a;
      --msg-self-line:#c7dccf;
      --msg-self-inset:#eaf2ec;
      --msg-self-inset-hover:#dfebe3;
      --msg-self-muted:#4f6a5c;
      --msg-self-link:var(--primary-dark);
      --msg-link-color:var(--primary-dark);
      --msg-link-hover:var(--primary);
      --msg-action-ink:var(--primary-dark);
      --msg-action-line:color-mix(in srgb,var(--primary) 34%,var(--line));
      --msg-scroll-track:var(--studio-soft);
      --msg-scroll-thumb:#b6ab94;
      --msg-scroll-thumb-hover:#8d8168;
      --msg-control-ink:var(--muted);
      --msg-quote-line:color-mix(in srgb,var(--primary) 45%,var(--line));
      --msg-quote-fill:var(--raised);
      --msg-button-fill:var(--accent-fill);
      --msg-button-hover:var(--accent-hover);
      --msg-owner-fill:var(--studio-peach);
      --msg-owner-ink:var(--paper-gold);
      --msg-overlay:#211e1955;
      --msg-document-light:#83b39a;
      --msg-document-mid:#4e8a6f;
      --msg-document-dark:#2d6950;
      --msg-document-fold:#23523f;
      --msg-document-lines:#ffffff;
      --shadow:var(--studio-float-shadow);
      background-color:var(--bg);
    }
    :root[data-theme="dark"] body.messages-workspace {
      --msg-self-fill:#27473a;
      --msg-self-ink:#eaf3ed;
      --msg-self-line:#33574a;
      --msg-self-inset:#2f5344;
      --msg-self-inset-hover:#38604e;
      --msg-self-muted:#c2d7cb;
      --msg-self-link:#c6e4d2;
      --msg-scroll-thumb:#6d6354;
      --msg-scroll-thumb-hover:#8d8168;
      --msg-overlay:#141310a6;
      --msg-document-light:#a2c7b1;
      --msg-document-mid:#79a68d;
      --msg-document-dark:#4a8065;
      --msg-document-fold:#365f4a;
      --msg-document-lines:#f1f7f3;
    }

    /* 仅覆盖硬编码的旧色值；布局尺寸、字体和可见性由消息工作区样式负责。 */
    :root body.messages-workspace .chat-list-panel { background:var(--msg-list-fill); }
    :root body.messages-workspace .msg-head { background:var(--msg-head-bg); }
    :root body.messages-workspace .msg-composer { background:var(--msg-composer-bg); }
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
    :root body.messages-workspace .msg-mention-chip,
    :root body.messages-workspace .msg-group-role {
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
    :root body.messages-workspace .msg-composer-tabs button.active,
    :root body.messages-workspace .msg-mute-presets button.active { border-color:var(--primary); }
    :root body.messages-workspace .msg-multi-bar { border-bottom-color:var(--line); }
    :root body.messages-workspace .msg-btn.primary { background:var(--accent-fill); }
    :root body.messages-workspace .msg-panel,
    :root body.messages-workspace .msg-list-head,
    :root body.messages-workspace .msg-head { border-color:var(--line); }
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
消息记录皮肤 = 消息记录皮肤 + "\n" + 新版外观样式 + "\n" + 总览外观
