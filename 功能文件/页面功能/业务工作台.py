"""机器人、小说服务与网盘配置的控制台页面。"""

业务页面 = """
        <section id="page-bot" class="page-view studio-service-page" data-page="bot" hidden>
          <div class="studio-bot-grid">
            <article id="overview" class="studio-card studio-bot-identity">
              <span class="studio-kicker">当前机器人</span>
              <h2>身份与状态</h2>
              <div class="studio-bot-badge">
                <div class="bot-avatar" data-bot-avatar>
                  <span class="avatar-face"><svg viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M9 10c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7"/><path d="M5 24a11 11 0 0 1 22 0c0 4-22 4-22 0Z"/><path d="M12 18l-2 5m7-6 1 6m5-4 1 4"/></svg></span>
                </div>
                <div><strong data-bot-name>馒头助手</strong><span class="bot-profile-status" data-bot-status>状态未知</span></div>
              </div>
              <dl class="studio-bot-facts">
                <div><dt>QQ 号</dt><dd data-bot-id>由适配器提供</dd></div>
                <div><dt>消息渠道</dt><dd>QQ 官方机器人</dd></div>
              </dl>
            </article>
            <article id="config" class="studio-card studio-bot-permissions">
              <header class="studio-service-head">
                <div>
                  <span class="studio-kicker">配置</span>
                  <h2>访问权限与帮助网页</h2>
                  <p>管理管理员白名单、帮助网页与 ZLibrary 邮箱设置。</p>
                </div>
              </header>
              <div id="basic-config-editor" class="config-editor"><div class="empty">正在读取配置…</div></div>
            </article>
          </div>

          <section class="studio-reading-group" aria-labelledby="studio-reading-title">
            <header class="studio-service-head">
              <div><span class="studio-kicker">账号管理</span><h2 id="studio-reading-title">阅读账号</h2></div>
            </header>
            <article class="studio-card studio-qq-card">
              <header class="studio-service-head">
                <div><h3>QQ 阅读</h3><p>支持 Cookie、QQ 扫码和手机号登录。</p></div>
                <span class="studio-service-icon studio-icon-peach" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 6v14M3 5c4-1 6 0 9 2 3-2 5-3 9-2v13c-4-1-6 0-9 2-3-2-5-3-9-2Z"/></svg></span>
              </header>
              <div id="qq-auth-editor"><div class="empty">正在读取登录态…</div></div>
            </article>
            <article class="studio-card zlibrary-accounts-card">
              <header class="studio-service-head zlibrary-card-heading">
                <div><h3>ZLibrary</h3><p>限流账号自动跳过，额度恢复后重新参与轮询。</p></div>
                <span class="studio-service-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19V5h4v14m0 0V7h5v12m0 0 1-13 5 1-1 12M3 19h18"/></svg></span>
              </header>
              <div id="zlibrary-account-editor" aria-live="polite"><div class="empty">正在读取账号…</div></div>
            </article>
          </section>
        </section>

        <section id="page-novels" class="page-view studio-service-page" data-page="novels" hidden>
          <div id="novels" class="studio-novel-grid">
            <aside class="studio-card studio-novel-settings" aria-labelledby="studio-novel-settings-title">
              <header class="studio-service-head">
                <div><span class="studio-kicker">小说服务</span><h2 id="studio-novel-settings-title">服务开关</h2></div>
                <span class="studio-service-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 6v14M3 5c4-1 6 0 9 2 3-2 5-3 9-2v13c-4-1-6 0-9 2-3-2-5-3-9-2Z"/></svg></span>
              </header>
              <div class="studio-novel-control">
                <h3>小说总开关</h3>
                <p>管理当前机器人的找书、下载和翻页。</p>
                <div class="studio-novel-switch-row">
                  <div><strong id="novel-master-label">读取中</strong><small id="novel-platform-summary">正在读取平台状态</small></div>
                  <button id="global-switch" class="switch" type="button" aria-label="切换本机器人的小说功能" disabled><span></span></button>
                </div>
              </div>
              <div class="studio-novel-control studio-novel-test">
                <h3>管理员测试模式</h3>
                <p>只对管理员测试生效。</p>
                <div class="studio-novel-switch-row">
                  <span id="novel-test-label">读取中</span>
                  <button id="test-switch" class="switch" type="button" aria-label="切换管理员测试模式" disabled><span></span></button>
                </div>
              </div>
            </aside>
            <article class="studio-card studio-novel-platforms">
              <header class="studio-service-head studio-novel-platform-head">
                <div><span class="studio-kicker">平台管理</span><h2>小说平台</h2><p>设置每个平台是否响应小说链接。</p></div>
                <div class="studio-novel-metrics">
                  <div id="novel-state-pill" class="novel-state-pill is-off"><span class="novel-state-dot"></span><strong>读取中</strong></div>
                  <span id="novel-enabled-count" class="studio-count-pill">— / — 已开启</span>
                </div>
              </header>
              <div id="novel-grid" class="novel-grid"><div class="empty">正在读取小说平台…</div></div>
            </article>
          </div>
        </section>

        <section id="page-pans" class="page-view studio-service-page" data-page="pans" hidden>
          <div id="pans" class="pan-page studio-pans-grid">
            <aside class="studio-card studio-pan-providers">
              <header class="studio-service-head">
                <div><span class="studio-kicker">分享服务</span><h2>网盘平台</h2></div>
              </header>
              <div class="pan-tabs" role="tablist" aria-orientation="vertical" aria-label="选择网盘">
                <button id="pan-tab-UC" class="pan-tab" type="button" role="tab" data-pan-tab="UC" aria-controls="pan-card-UC" aria-selected="false"><span class="pan-tab-mark" aria-hidden="true">U</span><span class="pan-tab-copy"><span>UC 网盘</span><small data-pan-tab-meta="UC">读取中</small></span></button>
                <button id="pan-tab-夸克" class="pan-tab" type="button" role="tab" data-pan-tab="夸克" aria-controls="pan-card-夸克" aria-selected="false"><span class="pan-tab-mark pan-tab-quark" aria-hidden="true">夸</span><span class="pan-tab-copy"><span>夸克网盘</span><small data-pan-tab-meta="夸克">读取中</small></span></button>
                <button id="pan-tab-百度" class="pan-tab" type="button" role="tab" data-pan-tab="百度" aria-controls="pan-card-百度" aria-selected="false"><span class="pan-tab-mark pan-tab-baidu" aria-hidden="true">度</span><span class="pan-tab-copy"><span>百度网盘</span><small data-pan-tab-meta="百度">读取中</small></span></button>
              </div>
            </aside>
            <article class="studio-card studio-pan-accounts">
              <header class="studio-service-head">
                <div><span class="studio-kicker">账号管理</span><h2>网盘账号</h2><p>选择平台后管理账号、默认项和上传目录。</p></div>
                <span class="studio-service-icon studio-icon-peach" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 18H6a5 5 0 0 1-1-10 7 7 0 0 1 13-2 6 6 0 0 1 0 12h-1M12 12v9m-3-6 3-3 3 3"/></svg></span>
              </header>
              <div id="pan-grid" class="pan-grid"><div class="empty">正在读取网盘状态…</div></div>
            </article>
          </div>
        </section>
"""
