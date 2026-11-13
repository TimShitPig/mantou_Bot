"""运行状态、帮助指令及系统设置的工作台页面。"""

系统页面 = """
        <section id="page-runtime" class="page-view studio-system" data-page="runtime" hidden>
          <div class="studio-system-heading">
            <div><p class="studio-kicker">服务器资源</p><h2>运行概况</h2></div>
            <span class="studio-system-source">最近一次采集</span>
          </div>
          <div class="studio-resource-grid">
            <article class="studio-card studio-resource">
              <span class="studio-system-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="3"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3"/></svg></span>
              <h3>CPU 占用</h3><strong id="runtime-cpu">—</strong>
            </article>
            <article class="studio-card studio-resource">
              <span class="studio-system-icon is-peach" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="11" rx="2"/><path d="M7 9h3v4H7zm7 0h3v4h-3zM7 17v3m5-3v3m5-3v3"/></svg></span>
              <h3>物理内存</h3><strong id="runtime-memory">—</strong>
            </article>
            <article class="studio-card studio-resource">
              <span class="studio-system-icon is-mint" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="M3 13h18m-5 3h.01m2.5 0h.01"/></svg></span>
              <h3>磁盘空间</h3><strong id="runtime-disk">—</strong>
            </article>
          </div>
          <div class="studio-system-split">
            <article class="studio-card studio-system-card">
              <div class="studio-system-heading"><div><p class="studio-kicker">主机</p><h2>系统信息</h2></div></div>
              <dl class="studio-system-detail">
                <div><dt>操作系统</dt><dd id="runtime-os">—</dd></div>
                <div><dt>持续运行</dt><dd id="runtime-runtime">—</dd></div>
              </dl>
            </article>
            <article class="studio-card studio-system-card">
              <div class="studio-system-heading"><div><p class="studio-kicker">服务</p><h2>依赖状态</h2></div><a class="studio-system-link" href="?view=settings" data-view="settings">连接设置 <span aria-hidden="true">↗</span></a></div>
              <dl class="studio-system-detail">
                <div><dt>数据库</dt><dd id="runtime-db">—</dd></div>
                <div><dt>可用分享网盘</dt><dd id="runtime-pan">—</dd></div>
                <div id="runtime-pan-preference-row" hidden><dt>主分享偏好</dt><dd id="runtime-pan-preference"></dd></div>
                <div><dt>插件版本</dt><dd id="runtime-version">—</dd></div>
              </dl>
            </article>
          </div>
        </section>

        <section id="page-help" class="page-view studio-system" data-page="help" hidden>
          <aside class="studio-help-intro studio-card">
            <div><p class="studio-kicker">指令手册</p><h2>在 QQ 里与机器人对话</h2><p>在支持的群聊或私聊发送相应指令。管理操作取决于插件管理员权限和 QQ 群身份。</p></div>
            <svg viewBox="0 0 160 106" aria-hidden="true" class="studio-help-art">
              <path d="M23 20c20-5 37 0 57 11 20-11 37-16 57-11v65c-20-5-37 0-57 11-20-11-37-16-57-11z" fill="var(--studio-card)" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
              <path d="M80 31v65m-47-59c12-2 23 1 34 6m-34 8c12-2 23 1 34 6m-34 8c12-2 23 1 34 6m26-28c11-5 22-8 34-6m-34 20c11-5 22-8 34-6m-34 20c11-5 22-8 34-6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity=".65"/>
              <path d="M108 12v8m-4-4h8M17 5v12m-6-6h12m121 85v8m-4-4h8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </aside>
          <div class="studio-help-catalog">
            <article class="studio-card studio-command-card">
              <div class="studio-system-heading"><div><p class="studio-kicker">阅读</p><h2>找书与下载</h2></div><a class="studio-system-link" href="?view=novels" data-view="novels">小说功能 <span aria-hidden="true">↗</span></a></div>
              <dl class="studio-commands">
                <div><dt><code>找关键词</code> <code>找书 关键词</code> <code>找作者 关键词</code></dt><dd>按书名或作者搜索</dd></div>
                <div><dt><code>上一页</code> <code>下一页</code></dt><dd>翻阅搜索结果</dd></div>
                <div><dt><code>1</code> <code>2</code> <code>选一</code></dt><dd>按找书结果编号下载，编号跨页连续</dd></div>
                <div><dt><span>小说平台分享链接、小说分享卡片</span></dt><dd>识别并处理受支持的小说来源</dd></div>
              </dl>
            </article>
            <article class="studio-card studio-command-card">
              <div class="studio-system-heading"><div><p class="studio-kicker">群聊</p><h2>成员与消息管理</h2></div><a class="studio-system-link" href="?view=messages" data-view="messages">消息记录 <span aria-hidden="true">↗</span></a></div>
              <dl class="studio-commands">
                <div><dt><code>禁言 @成员</code> <code>禁 @成员 1</code></dt><dd>按群聊权限禁言成员</dd></div>
                <div><dt><code>解 @成员</code></dt><dd>解除指定成员的禁言</dd></div>
                <div><dt><span>数字撤回、卡片撤回、合并转发撤回</span></dt><dd>按现有撤回规则处理消息</dd></div>
              </dl>
            </article>
            <article class="studio-card studio-command-card">
              <div class="studio-system-heading"><div><p class="studio-kicker">服务</p><h2>菜单与开关</h2></div></div>
              <dl class="studio-commands">
                <div><dt><code>帮助</code> <code>状态</code> <code>小说</code></dt><dd>打开帮助、查看运行状态或小说菜单</dd></div>
                <div><dt><code>开小说</code> <code>关小说</code></dt><dd>调整当前机器人的小说总开关</dd></div>
                <div><dt><code>开测试</code> <code>关测试</code></dt><dd>切换管理员测试模式</dd></div>
              </dl>
            </article>
            <article class="studio-card studio-command-card">
              <div class="studio-system-heading"><div><p class="studio-kicker">存储</p><h2>网盘与登录</h2></div><a class="studio-system-link" href="?view=pans" data-view="pans">网盘配置 <span aria-hidden="true">↗</span></a></div>
              <dl class="studio-commands">
                <div><dt><code>网盘状态</code></dt><dd>查看网盘配置摘要</dd></div>
                <div><dt><code>换UC</code> <code>换夸克</code> <code>换百度</code></dt><dd>切换主分享网盘</dd></div>
                <div><dt><code>夸克登录</code></dt><dd>开启夸克网盘登录流程</dd></div>
              </dl>
            </article>
          </div>
        </section>

        <section id="page-settings" class="page-view studio-system" data-page="settings" hidden>
          <div id="settings" class="studio-settings-layout">
            <article class="studio-card studio-system-card studio-database-form">
              <div class="studio-system-heading">
                <div><p class="studio-kicker">MySQL · 服务共用</p><h2>数据库连接</h2></div>
                <span class="studio-db-status">已保存连接 <strong class="studio-system-state" id="settings-db-status">读取中</strong></span>
              </div>
              <p class="studio-system-description">为当前服务下的所有机器人保存聊天记录、账号与网盘配置、功能开关等数据。</p>
              <div id="database-config-editor" class="config-editor"><div class="empty">正在读取数据库配置…</div></div>
              <p class="studio-db-footnote">测试使用当前填写的参数。保存后，重载插件使新配置生效。</p>
            </article>
          </div>
        </section>
"""
