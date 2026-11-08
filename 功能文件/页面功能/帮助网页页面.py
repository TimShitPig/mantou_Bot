"""馒头控制台页面模板。

页面结构、样式和脚本分别维护，后端只负责把模板作为 HTML 响应返回。
"""

from .业务工作台 import 业务页面
from .业务工作台样式 import 业务样式
from .业务工作台脚本 import 业务脚本
from .工作台框架 import 工作台侧栏, 工作台总览, 机器人选择
from .工作台样式 import 工作台样式
from .帮助网页样式 import 控制台样式
from .消息记录皮肤 import 消息记录皮肤
from .系统工作台 import 系统页面
from .系统工作台样式 import 系统样式
from .系统工作台脚本 import 系统脚本
from .帮助网页脚本 import 控制台脚本

页面头部前缀 = """<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f4f1fc">
  <title>馒头控制台</title>
  <script>
    (() => {
      try {
        const preference = localStorage.getItem('mantou-theme') === 'dark' ? 'dark' : 'light';
        const dark = preference === 'dark';
        document.documentElement.dataset.themePreference = preference;
        document.documentElement.dataset.theme = dark ? 'dark' : 'light';
      } catch (_) {}
    })();
  </script>
  <style>"""
页面头部后缀 = """</style>
</head>
"""
页面主体 = """
<body>
  <svg class="msg-svg-defs" aria-hidden="true" focusable="false"><defs><linearGradient id="msg-document-fill" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#3ba2ff"/><stop offset=".55" stop-color="#168bff"/><stop offset="1" stop-color="#0075ff"/></linearGradient><symbol id="msg-document-symbol" viewBox="0 0 42 50"><path fill="url(#msg-document-fill)" d="M6 0h21l15 15v30a5 5 0 0 1-5 5H6a5 5 0 0 1-5-5V5a5 5 0 0 1 5-5Z"/><path fill="#0878ee" d="m27 0 15 15H31a4 4 0 0 1-4-4Z"/><path fill="none" stroke="#e6f6ff" stroke-width="3" stroke-linecap="round" d="M12 22h17M12 29h17M12 36h10"/></symbol></defs></svg>
  <div class="shell bot-picker-open">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M9 10c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7"/><path d="M5 24a11 11 0 0 1 22 0c0 4-22 4-22 0Z"/></svg></div>
        <div class="studio-brand-copy"><strong class="studio-brand-title">馒头运营工作台</strong><span class="version-badge" id="console-version" hidden></span></div>
      </div>
      <div class="top-actions">
        <div class="theme-control"><button id="theme-toggle" class="theme-toggle-button" type="button" aria-label="切换到深色模式" title="切换到深色模式" aria-pressed="false"><span class="theme-control-icon" aria-hidden="true">☾</span></button></div>
        <div class="admin-menu">
          <button class="admin-chip" id="admin-chip" type="button" aria-expanded="false" aria-controls="admin-popover"><span class="admin-avatar" id="admin-avatar">管</span><span id="admin-name">管理员</span><span class="admin-chevron" aria-hidden="true">⌄</span></button>
          <div class="admin-popover" id="admin-popover" hidden>
            <strong id="admin-popover-name">管理员</strong>
            <small id="admin-popover-role">控制台管理员 · 当前会话</small>
            <small id="admin-popover-scope">插件管理员白名单：读取中</small>
            <button class="popover-logout" id="popover-logout" type="button" hidden>退出登录</button>
          </div>
        </div>
      </div>
    </header>
""" + 工作台侧栏 + """
    <main class="main">
""" + 机器人选择 + """
      <div class="content" id="console-workspace" hidden>
        <div class="page-heading"><div><p id="page-eyebrow" class="page-kicker">馒头Bot / 管理台</p><h1 id="page-title">控制台</h1><p id="page-subtitle">查看机器人和小说服务的实时状态</p></div><div class="heading-actions"><span id="updated" class="updated-label">--</span></div></div>
        <div id="notice" class="notice"></div>
""" + 工作台总览 + 业务页面 + 系统页面 + """
        <section id="page-messages" class="page-view" data-page="messages" hidden>
          <div class="msg-shell" id="msg-shell">
            <div class="msg-panel chat-list-panel" id="msg-chat-list-panel">
              <button class="msg-panel-toggle msg-list-collapse" id="msg-list-collapse" type="button" aria-expanded="true" aria-label="收起会话列表" title="收起会话列表">‹</button>
              <button class="msg-panel-toggle msg-list-group-toggle" id="msg-list-group-toggle" type="button" aria-pressed="false" aria-label="按类型分组" title="按类型分组"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="5" height="5" rx="1"/><rect x="3" y="15" width="5" height="5" rx="1"/><path d="M12 6h9M12 17h9"/></svg></button>
              <div class="msg-list-head">
                <div class="msg-filter" id="msg-filter" role="tablist" aria-label="消息过滤">
                  <button type="button" data-msg-filter="all" class="active">全部</button>
                  <button type="button" data-msg-filter="group">群聊</button>
                  <button type="button" data-msg-filter="user">私聊</button>
                </div>
              </div>
              <div class="msg-chats" id="msg-chats"><div class="msg-empty">正在加载会话...</div></div>
              <button class="msg-list-resizer" id="msg-list-resizer" type="button" aria-label="拖动调整会话列表宽度" title="拖动调整会话列表宽度"><span aria-hidden="true"></span></button>
            </div>
            <div class="msg-panel msg-work">
              <div class="msg-head">
                <button class="msg-mobile-back" id="msg-mobile-back" type="button" hidden aria-label="返回会话列表" title="返回会话列表"><span aria-hidden="true">‹</span></button>
                <div style="min-width:0">
                  <button class="msg-head-name" id="msg-head-name" type="button" disabled aria-haspopup="dialog" aria-expanded="false" aria-controls="msg-group-settings">选择一个会话</button>
                  <div class="msg-head-sub" id="msg-head-sub">左侧列表选择群聊或私聊查看消息</div>
                </div>
                <div class="msg-head-actions msg-head-menu">
                  <button class="msg-btn msg-head-menu-toggle" id="msg-head-menu-toggle" type="button" aria-label="会话操作" title="会话操作" aria-expanded="false" aria-controls="msg-head-menu-panel"><span aria-hidden="true">⋮</span></button>
                  <div class="msg-head-menu-panel" id="msg-head-menu-panel" role="group" aria-label="会话操作" hidden>
                  <span class="msg-admin-tag" id="msg-admin-tag" hidden>机器人是管理员</span>
                  <label class="msg-pan-account-control" id="msg-pan-account-wrap" hidden><span>网盘账号</span><select id="msg-pan-account-select" aria-label="选择当前群的网盘账号" disabled><option value="">读取中</option></select></label>
                  <button class="msg-btn" id="msg-ad-switch" type="button" hidden title="切换当前群的广告拦截">广告拦截</button>
                  <button class="msg-btn" id="msg-refresh-info" type="button" hidden>刷新群信息</button>
                  <button class="msg-btn" id="msg-remark" type="button" hidden>群备注</button>
                  <button class="msg-btn" id="msg-group-settings-open" type="button" hidden aria-label="打开当前群聊设置" aria-expanded="false" aria-controls="msg-group-settings">⚙ 设置</button>
                  <button class="msg-btn" id="msg-reload" type="button">刷新</button>
                  <button class="msg-btn msg-clear-open" id="msg-clear-open" type="button">清理记录</button>
                  </div>
                </div>
              </div>
              <div class="msg-multi-bar" id="msg-multi-bar" hidden><span id="msg-multi-count">已选 0 条</span><button class="msg-btn primary" id="msg-multi-recall" type="button">撤回选中</button><button class="msg-btn" id="msg-multi-cancel" type="button">取消</button></div>
               <div class="msg-body-wrap" id="msg-body-wrap">
                 <div class="msg-body" id="msg-body" tabindex="-1"><div class="msg-empty">从左侧选择会话开始查看</div></div>
                 <button class="msg-new-messages" id="msg-new-messages" type="button" hidden title="回到底部" aria-label="回到底部" aria-controls="msg-body"><span class="msg-new-messages-dot" aria-hidden="true" hidden></span><span id="msg-new-messages-label">回到底部</span><span class="msg-new-messages-arrow" aria-hidden="true">↓</span></button>
              </div>
              <div class="msg-composer" id="msg-composer" hidden>
                <button class="msg-composer-resizer" id="msg-composer-resizer" type="button" aria-label="拖动调整编辑区高度" title="拖动调整编辑区高度"><span aria-hidden="true"></span></button>
                <div class="msg-composer-topbar">
                  <button class="msg-panel-toggle msg-composer-toggle" id="msg-composer-toggle" type="button" aria-expanded="true" aria-label="收起编辑区" title="收起编辑区">⌄</button>
                  <label class="msg-tool-btn" title="选择图片" id="msg-img-pick" aria-label="选择图片">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                    <input id="msg-img-file" type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden>
                  </label>
                  <label class="msg-tool-btn" title="选择视频" id="msg-video-pick" aria-label="选择视频">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="m10 8 6 4-6 4z" stroke-linejoin="round"/></svg>
                    <input id="msg-video-file" type="file" accept="video/mp4,video/*" hidden>
                  </label>
                  <label class="msg-tool-btn" title="选择文件" id="msg-file-pick" aria-label="选择文件">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M3 6a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>
                    <input id="msg-attachment-file" type="file" accept="*/*" hidden>
                  </label>
                  <span class="msg-composer-top-hint">图片、视频或文件</span>
                </div>
                <div class="msg-composer-mode" hidden>
                  <select id="msg-send-mode" aria-label="发送方式">
                    <option value="default">默认（全量群主动/其他被动）</option>
                    <option value="passive">被动（msg_id）</option>
                    <option value="active">主动</option>
                    <option value="custom_msg_id">自定义 msg_id</option>
                    <option value="custom_event_id">自定义事件 ID</option>
                  </select>
                  <input id="msg-custom-id" type="text" placeholder="自定义 msg_id / 事件 ID" hidden>
                </div>
                <div class="msg-extra" id="msg-extra" hidden></div>
                <div class="msg-composer-tabs" id="msg-composer-tabs" hidden>
                  <button type="button" data-msg-type="text" class="active">文本</button>
                  <button type="button" data-msg-type="markdown">Markdown</button>
                  <button type="button" data-msg-type="media">媒体</button>
                  <button type="button" data-msg-type="ark">ARK模板</button>
                  <button type="button" data-msg-type="card">图文卡片</button>
                </div>
                <div class="msg-input-box" id="msg-input-box">
                  <div class="msg-quote-preview" id="msg-quote-preview" hidden><span class="msg-quote-text" id="msg-quote-text"></span><button class="msg-action" id="msg-quote-clear" type="button" title="取消引用" aria-label="取消引用">×</button></div>
                  <div class="msg-attachment-inline" id="msg-media-inline" hidden>
                    <span class="msg-attachment-icon" id="msg-media-icon" aria-hidden="true">□</span>
                    <span class="msg-attachment-name" id="msg-media-name">待发送附件</span>
                    <button class="msg-img-remove" id="msg-media-clear" type="button" aria-label="移除附件">×</button>
                  </div>
                  <div id="msg-editor" class="msg-editor" contenteditable="true" role="textbox" aria-multiline="true" aria-autocomplete="list" aria-haspopup="listbox" aria-controls="msg-mention-picker" aria-expanded="false" data-placeholder="输入消息..." aria-label="消息内容"></div>
                </div>
                <div class="msg-toolbar">
                  <span class="msg-send-shortcut" style="flex:1">Enter 发送 · Ctrl+Enter 换行</span>
                  <button class="msg-btn primary" id="msg-send" type="button">发送</button>
                </div>
              </div>
              <div class="msg-group-settings" id="msg-group-settings" hidden>
                <button class="msg-group-mask" id="msg-group-settings-mask" type="button" aria-label="关闭群聊设置"></button>
                <aside class="msg-group-drawer" role="dialog" aria-modal="true" aria-labelledby="msg-group-settings-title" tabindex="-1">
                  <div class="msg-group-drawer-head"><div><strong id="msg-group-settings-title">群信息与设置</strong><small id="msg-group-settings-name"></small></div><button class="msg-group-close" id="msg-group-settings-close" type="button" aria-label="关闭群信息与设置">×</button></div>
                  <div class="msg-group-tabs" id="msg-group-settings-tabs" role="tablist" aria-label="群聊设置分类"><button type="button" id="msg-group-tab-basic" data-group-tab="basic" class="active" role="tab" aria-selected="true" aria-controls="msg-group-basic">基础设置</button><button type="button" id="msg-group-tab-members" data-group-tab="members" role="tab" aria-selected="false" aria-controls="msg-group-members">群成员</button><button type="button" id="msg-group-tab-mutes" data-group-tab="mutes" role="tab" aria-selected="false" aria-controls="msg-group-mutes">禁言状态</button><button type="button" id="msg-group-tab-blacklist" data-group-tab="blacklist" role="tab" aria-selected="false" aria-controls="msg-group-blacklist">黑名单</button></div>
                  <div class="msg-group-body">
                    <section class="msg-group-pane" id="msg-group-basic" role="tabpanel" aria-labelledby="msg-group-tab-basic">
                      <div class="msg-group-summary" id="msg-group-summary"></div><div class="msg-group-status" id="msg-group-basic-status" role="status"></div>
                      <div class="msg-group-profile" aria-label="群资料">
                        <strong class="msg-group-profile-title">群资料</strong>
                        <dl><dt>群简介</dt><dd class="msg-group-profile-memo" id="msg-group-profile-memo">未设置</dd><dt>群分类</dt><dd id="msg-group-profile-class">未设置</dd><dt>群标签</dt><dd class="msg-group-profile-tags" id="msg-group-profile-tags"><span class="msg-group-profile-empty">暂无标签</span></dd></dl>
                      </div>
                      <label class="msg-group-field">本群备注<input id="msg-group-remark-name" maxlength="128" type="text" placeholder="仅改变本控制台显示的群名" disabled></label>
                      <label class="msg-group-field">群号<input id="msg-group-remark-qq" maxlength="12" inputmode="numeric" type="text" placeholder="用于显示群头像，可留空" disabled></label>
                      <button class="msg-btn primary" id="msg-group-basic-save" type="button" disabled>保存本群设置</button>
                      <label class="msg-group-toggle"><span>广告拦截<small>只对当前群生效，其他群保持原设置</small></span><input id="msg-group-ad-enabled" type="checkbox" aria-label="当前群广告拦截" disabled></label>
                    </section>
                    <section class="msg-group-pane" id="msg-group-mutes" role="tabpanel" aria-labelledby="msg-group-tab-mutes" hidden>
                      <div class="msg-group-tools"><span>当前群聊的禁言状态</span><button class="msg-btn" id="msg-group-mutes-refresh" type="button">刷新</button></div>
                      <div class="msg-group-status" id="msg-group-mutes-status" role="status">尚未查询</div>
                      <div class="msg-group-mute-card"><h4>全员禁言</h4><strong id="msg-group-mutes-mode">未知状态</strong><small id="msg-group-mutes-checked"></small></div>
                      <div class="msg-group-mute-card"><h4>定时禁言</h4><div id="msg-group-mutes-schedules"><span class="msg-group-profile-empty">尚未查询</span></div></div>
                      <div class="msg-group-mute-card"><h4>周期禁言 <small>北京时间</small></h4><div id="msg-group-mutes-recurring"><span class="msg-group-profile-empty">尚未查询</span></div></div>
                      <div class="msg-group-mute-card"><h4>禁言成员 <small id="msg-group-mutes-count"></small></h4><div id="msg-group-mutes-members"><span class="msg-group-profile-empty">尚未查询</span></div></div>
                    </section>
                    <section class="msg-group-pane" id="msg-group-members" role="tabpanel" aria-labelledby="msg-group-tab-members" hidden>
                      <div class="msg-group-status" id="msg-group-members-status" role="status"></div>
                      <div class="msg-group-tools"><label class="msg-group-select-all"><input id="msg-group-members-all" type="checkbox">本页</label><span id="msg-group-members-count">已选 0 / 20</span><button class="msg-btn" id="msg-group-members-refresh" type="button">刷新</button></div>
                      <div class="msg-group-member-detail" id="msg-group-member-detail" hidden></div><div id="msg-group-members-list"></div>
                      <div class="msg-group-pagination"><button class="msg-btn" id="msg-group-members-prev" type="button" disabled>上一页</button><span id="msg-group-members-page">第 1 页 · 每页 30 人</span><button class="msg-btn" id="msg-group-members-next" type="button" disabled>下一页</button></div>
                      <div class="msg-group-batch"><label><input id="msg-group-remove-blacklist" type="checkbox">移除后同时加入本群黑名单</label><button class="msg-btn danger" id="msg-group-members-remove" type="button" disabled>移除选中的成员</button></div>
                    </section>
                    <section class="msg-group-pane" id="msg-group-blacklist" role="tabpanel" aria-labelledby="msg-group-tab-blacklist" hidden>
                      <div class="msg-group-status" id="msg-group-blacklist-status" role="status"></div><p class="msg-group-status">手动添加仅限已离群用户；在群成员可在移除时同时加入黑名单。</p>
                      <div class="msg-group-blacklist-add"><input id="msg-group-blacklist-openid" type="text" maxlength="128" placeholder="输入已离群成员的 OpenID" aria-label="黑名单成员 OpenID" disabled><button class="msg-btn" id="msg-group-blacklist-add" type="button" disabled>添加</button></div>
                      <div class="msg-group-tools"><label class="msg-group-select-all"><input id="msg-group-blacklist-all" type="checkbox">本页</label><span id="msg-group-blacklist-count">已选 0 / 20</span><button class="msg-btn" id="msg-group-blacklist-refresh" type="button">刷新</button></div><div id="msg-group-blacklist-list"></div>
                      <div class="msg-group-pagination"><button class="msg-btn" id="msg-group-blacklist-prev" type="button" disabled>上一页</button><span id="msg-group-blacklist-page">第 1 页 · 每页 20 人</span><button class="msg-btn" id="msg-group-blacklist-next" type="button" disabled>下一页</button></div>
                      <div class="msg-group-batch"><button class="msg-btn" id="msg-group-blacklist-remove" type="button" disabled>解除选中的黑名单</button></div>
                    </section>
                  </div>
                </aside>
              </div>
            </div>
          </div>
          <div class="msg-clear-modal" id="msg-clear-modal" hidden><div class="msg-clear-box" role="dialog" aria-modal="true" aria-labelledby="msg-clear-title" aria-describedby="msg-clear-description" tabindex="-1"><div class="msg-clear-head"><h3 id="msg-clear-title">清理聊天记录</h3><button class="msg-clear-close" id="msg-clear-close" type="button" aria-label="关闭清理记录">×</button></div><p id="msg-clear-description" class="msg-clear-description">只清理本插件保存的本机聊天记录，不撤回 QQ 消息，不删除网盘文件。当前会话清空后从列表移除，预览后收到的新消息保留。</p><label class="msg-clear-field" for="msg-clear-scope">清理范围<select id="msg-clear-scope"><option value="chat">当前会话</option><option value="bot">当前机器人的全部会话</option></select></label><p class="msg-clear-target" id="msg-clear-target"></p><div class="msg-clear-preview" id="msg-clear-preview" role="status" aria-live="polite">正在统计记录…</div><div class="msg-clear-actions"><button class="msg-btn" id="msg-clear-preview-button" type="button">重新统计</button><span></span><button class="msg-btn" id="msg-clear-cancel" type="button">取消</button><button class="msg-btn msg-clear-confirm" id="msg-clear-confirm" type="button" disabled>确认删除</button></div></div></div>
          <div class="msg-raw-modal" id="msg-raw-modal" hidden><div class="msg-raw-box" role="dialog" aria-modal="true" aria-labelledby="msg-raw-title" tabindex="-1"><div class="msg-raw-head"><strong id="msg-raw-title">消息原始数据</strong><div class="msg-raw-actions"><button class="msg-raw-copy" id="msg-raw-copy" type="button">复制</button><button id="msg-raw-close" type="button" aria-label="关闭原始数据">×</button></div></div><div class="msg-raw-content" id="msg-raw-content"></div></div></div>
          <div class="msg-remark-modal" id="msg-remark-modal" hidden><div class="msg-remark-box" role="dialog" aria-modal="true" aria-labelledby="msg-remark-title" tabindex="-1"><h3 id="msg-remark-title">群备注</h3><label style="display:block;font-size:11px;color:#999;margin-bottom:4px">备注名（显示在会话列表）</label><input id="msg-remark-name" type="text" placeholder="输入群备注名" style="width:100%;height:34px;padding:0 9px;border:1px solid #e0e1e5;border-radius:8px;font-size:12px;margin-bottom:10px"><label style="display:block;font-size:11px;color:#999;margin-bottom:4px">群号（用于显示群头像，可留空）</label><input id="msg-remark-qq" type="text" placeholder="输入群号" style="width:100%;height:34px;padding:0 9px;border:1px solid #e0e1e5;border-radius:8px;font-size:12px"><div class="msg-mute-actions"><button class="msg-btn" id="msg-remark-delete" type="button" style="color:#e64340;border-color:#f5c2c1;margin-right:auto">删除备注</button><button class="msg-btn" id="msg-remark-cancel" type="button">取消</button><button class="msg-btn primary" id="msg-remark-save" type="button">保存</button></div></div></div>
          <div class="msg-mute-modal" id="msg-mute-modal" hidden><div class="msg-mute-box" role="dialog" aria-modal="true" aria-labelledby="msg-mute-title" tabindex="-1"><h3 id="msg-mute-title">禁言成员</h3><div class="msg-mute-presets" id="msg-mute-presets"><button type="button" data-mute-min="10">10分钟</button><button type="button" data-mute-min="30" class="active">30分钟</button><button type="button" data-mute-min="60">1小时</button><button type="button" data-mute-min="1440">1天</button></div><input id="msg-mute-custom" type="number" min="1" max="30" step="1" placeholder="自定义天数（最多30天）" aria-label="自定义禁言天数，最多30天" style="width:100%;height:32px;padding:0 9px;border:1px solid var(--line);border-radius:8px;font-size:12px"><div class="msg-mute-actions"><button class="msg-btn" id="msg-mute-cancel" type="button">取消</button><button class="msg-btn primary" id="msg-mute-confirm" type="button">确认禁言</button></div></div></div>
        </section>
      </div>
    </main>
    <div class="msg-ctx" id="msg-ctx" hidden></div>
    <div class="msg-mention-picker" id="msg-mention-picker" role="listbox" aria-label="选择提及对象" hidden></div>
    <div class="msg-lightbox" id="msg-lightbox" hidden>
      <div class="msg-lightbox-inner">
        <img id="msg-lightbox-img" alt="图片预览" referrerpolicy="no-referrer">
        <div class="msg-lightbox-hint">点击图片或按 Esc 关闭 · 右键可复制/保存图片</div>
      </div>
      <button class="msg-lightbox-close" id="msg-lightbox-close" type="button" title="关闭">&times;</button>
    </div>
  </div>
  <dialog id="saved-password-dialog" class="saved-password-dialog" aria-labelledby="saved-password-title" aria-describedby="saved-password-instructions">
    <form id="saved-password-form" method="dialog">
      <h2 id="saved-password-title">查看已保存密码</h2>
      <p id="saved-password-instructions">输入当前控制台登录密码以验证身份。</p>
      <label for="saved-password-confirm">当前控制台登录密码</label>
      <input id="saved-password-confirm" type="password" autocomplete="current-password" maxlength="1024" required>
      <div id="saved-password-result" class="saved-password-result" hidden>
        <span>已保存密码 · 20 秒后隐藏</span>
        <output id="saved-password-value"></output>
      </div>
      <p id="saved-password-status" role="status"></p>
      <div class="saved-password-actions">
        <button id="saved-password-close" class="outline-button" type="button">关闭</button>
        <button id="saved-password-submit" class="primary-button" type="submit">验证并查看</button>
      </div>
    </form>
  </dialog>
  <div id="toast" class="toast" role="status"></div>
"""
脚本标签前缀 = """
  <script>"""
脚本标签后缀 = """</script>
</body>
</html>
"""
_控制台页面缓存: str | None = None


def 渲染控制台页面() -> str:
    global _控制台页面缓存
    if _控制台页面缓存 is None:
        _控制台页面缓存 = (
            页面头部前缀
            + 控制台样式
            + 工作台样式
            + 业务样式
            + 系统样式
            + 消息记录皮肤
            + 页面头部后缀
            + 页面主体
            + 脚本标签前缀
            + 系统脚本
            + 控制台脚本
            + 业务脚本
            + 脚本标签后缀
        )
    return _控制台页面缓存
