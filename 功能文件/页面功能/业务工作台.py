"""机器人、小说服务与网盘配置的控制台页面。"""

业务页面 = """
        <section id="page-bot" class="page-view studio-service-page" data-page="bot" hidden>
          <div class="studio-card studio-bot-workspace">
            <header id="overview" class="studio-bot-identity">
              <div class="studio-bot-badge">
                <div class="bot-avatar" data-bot-avatar><span class="avatar-face">•ᴗ•</span></div>
                <div class="studio-bot-copy">
                  <span class="studio-bot-kicker">机器人档案</span>
                  <h2 data-bot-name>馒头助手</h2>
                  <span class="bot-profile-status" data-bot-status>状态未知</span>
                </div>
              </div>
              <dl class="studio-bot-facts"><dt>QQ 号</dt><dd data-bot-id>由适配器提供</dd></dl>
            </header>

            <div class="studio-bot-tabs" role="tablist" aria-label="机器人与账号分区">
              <button id="bot-tab-basic" type="button" role="tab" aria-selected="true" aria-controls="config">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true" focusable="false"><path d="M4 7h5m4 0h7M4 17h9m4 0h3"/><circle cx="11" cy="7" r="2"/><circle cx="15" cy="17" r="2"/></svg>
                基础设置
              </button>
              <button id="bot-tab-qq" type="button" role="tab" aria-selected="false" aria-controls="bot-panel-qq" tabindex="-1">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 6v14M3 5c4-1 6 0 9 2 3-2 5-3 9-2v13c-4-1-6 0-9 2-3-2-5-3-9-2z"/></svg>
                QQ 阅读
              </button>
              <button id="bot-tab-jinjiang" type="button" role="tab" aria-selected="false" aria-controls="bot-panel-jinjiang" tabindex="-1">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M4 4h16v16H4zM8 4v16m4-12h5m-5 4h5m-5 4h5"/></svg>
                晋江
              </button>
              <button id="bot-tab-zlibrary" type="button" role="tab" aria-selected="false" aria-controls="bot-panel-zlibrary" tabindex="-1">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M4 19V5h4v14m0 0V7h5v12m0 0 1-13 5 1-1 12M3 19h18"/></svg>
                ZLibrary
              </button>
              <button id="bot-tab-stv" type="button" role="tab" aria-selected="false" aria-controls="bot-panel-stv" tabindex="-1">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 6v14M3 5c4-1 6 0 9 2 3-2 5-3 9-2v13c-4-1-6 0-9 2-3-2-5-3-9-2z"/></svg>
                STV
              </button>
            </div>

            <section id="config" class="studio-bot-panel" role="tabpanel" aria-labelledby="bot-tab-basic" tabindex="0">
              <header class="studio-service-head">
                <div><h3>权限与网页设置</h3><p>管理访问权限、帮助网页和注册邮箱。</p></div>
              </header>
              <div id="basic-config-editor" class="config-editor"><div class="empty">正在读取配置…</div></div>
            </section>

            <section id="bot-panel-qq" class="studio-bot-panel" role="tabpanel" aria-labelledby="bot-tab-qq" tabindex="0" hidden>
              <header class="studio-service-head">
                <div><h3>QQ 阅读账号</h3><p>支持 Cookie、QQ 扫码和手机号登录。</p></div>
              </header>
              <div id="qq-auth-editor"><div class="empty">正在读取登录态…</div></div>
            </section>

            <section id="bot-panel-jinjiang" class="studio-bot-panel" role="tabpanel" aria-labelledby="bot-tab-jinjiang" tabindex="0" hidden>
              <header class="studio-service-head">
                <div><h3>晋江账号</h3><p>使用晋江小说阅读 App 扫码登录，或手动添加账号。</p></div>
              </header>
              <div id="jinjiang-auth-editor"><div class="empty">选择晋江分区后读取账号…</div></div>
            </section>

            <section id="bot-panel-zlibrary" class="studio-bot-panel" role="tabpanel" aria-labelledby="bot-tab-zlibrary" tabindex="0" hidden>
              <header class="studio-service-head">
                <div><h3>ZLibrary 账号</h3><p>搜索、导入账号或按分组管理。</p></div>
              </header>
              <div id="zlibrary-account-editor" aria-live="polite"><div class="empty">正在读取账号…</div></div>
            </section>
            <section id="bot-panel-stv" class="studio-bot-panel" role="tabpanel" aria-labelledby="bot-tab-stv" tabindex="0" hidden>
              <header class="studio-service-head">
                <div><h3>STV 账号</h3><p>Sáng Tác Việt · 登录、修为和背包。</p></div>
                <button id="stv-refresh" class="outline-button" type="button">刷新资料</button>
              </header>
              <p id="stv-summary" role="status" aria-live="polite">选择 STV 分区后读取账号…</p>
              <form id="stv-login-form" class="config-editor" autocomplete="off">
                <div class="config-field"><label for="stv-username">用户名</label><input id="stv-username" type="text" maxlength="128" autocomplete="off" required></div>
                <div class="config-field"><label for="stv-password">密码</label><input id="stv-password" type="password" maxlength="4096" autocomplete="new-password" required></div>
                <div class="config-field"><label for="stv-repeat-password">确认密码（注册时填写）</label><input id="stv-repeat-password" type="password" maxlength="4096" autocomplete="new-password"></div>
                <div class="config-actions"><button id="stv-login" class="outline-button" type="submit">登录</button><button id="stv-register" class="outline-button" type="button">注册</button><button id="stv-delete" class="outline-button" type="button">退出账号</button></div>
              </form>
              <div class="config-actions">
                <label>挂时长 <button id="stv-online" class="switch" type="button" aria-label="挂时长" aria-pressed="false" disabled><span></span></button></label>
                <label>领取奖励 <button id="stv-rewards" class="switch" type="button" aria-label="领取奖励" aria-pressed="false" disabled><span></span></button></label>
              </div>
              <div class="config-actions"><button id="stv-cultivation" class="outline-button" type="button" disabled>查询修为</button><button id="stv-breakthrough" class="outline-button" type="button" disabled>突破</button><button id="stv-inventory" class="outline-button" type="button" disabled>查询背包</button></div>
              <div class="config-field"><label for="stv-item-id">物品实例 ID</label><input id="stv-item-id" type="text" maxlength="128" autocomplete="off"><div class="config-actions"><button id="stv-item" class="outline-button" type="button" disabled>物品详情</button><button id="stv-use" class="outline-button" type="button" disabled>使用物品</button></div></div>
              <div id="stv-result" class="config-message" role="status" aria-live="polite"></div>
            </section>
          </div>
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
                  <div class="novel-stat"><strong id="novel-enabled-count">— / — 已开启</strong><span>平台开关</span></div>
                  <div id="novel-state-pill" class="novel-state-pill is-off"><span class="novel-state-dot"></span><strong>读取中</strong></div>
                  </div>
              </header>
              <div id="novel-grid" class="novel-grid"><div class="empty">正在读取小说平台…</div></div>
            </article>
          </div>
        </section>

        <section id="page-pans" class="page-view studio-service-page" data-page="pans" hidden>
          <div id="pans" class="pan-page studio-pan-page">
            <article class="studio-card studio-pan-accounts">
              <header class="studio-service-head studio-pan-head">
                <div><span class="studio-kicker">分享服务</span><h2>网盘账号</h2><p>选择平台后管理账号、默认项和上传目录。</p></div>
                <div class="pan-tabs" role="tablist" aria-label="选择网盘">
                  <button id="pan-tab-UC" class="pan-tab" type="button" role="tab" data-pan-tab="UC" aria-controls="pan-card-UC" aria-selected="false"><span class="pan-tab-mark" aria-hidden="true">U</span><span class="pan-tab-copy"><span>UC 网盘</span><small data-pan-tab-meta="UC">读取中</small></span></button>
                  <button id="pan-tab-夸克" class="pan-tab" type="button" role="tab" data-pan-tab="夸克" aria-controls="pan-card-夸克" aria-selected="false"><span class="pan-tab-mark pan-tab-quark" aria-hidden="true">夸</span><span class="pan-tab-copy"><span>夸克网盘</span><small data-pan-tab-meta="夸克">读取中</small></span></button>
                  <button id="pan-tab-百度" class="pan-tab" type="button" role="tab" data-pan-tab="百度" aria-controls="pan-card-百度" aria-selected="false"><span class="pan-tab-mark pan-tab-baidu" aria-hidden="true">度</span><span class="pan-tab-copy"><span>百度网盘</span><small data-pan-tab-meta="百度">读取中</small></span></button>
              </div>
              </header>
              <div id="pan-grid" class="pan-grid"><div class="empty">正在读取网盘状态…</div></div>
            </article>
          </div>
        </section>
"""
