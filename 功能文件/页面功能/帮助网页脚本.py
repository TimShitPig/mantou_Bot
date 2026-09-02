"""馒头控制台的浏览器交互脚本。"""

控制台脚本 = r"""
    (() => {
      const initialParams = new URLSearchParams(location.search);
      if (initialParams.has('token')) { initialParams.delete('token'); const cleanQuery = initialParams.toString(); history.replaceState({}, '', `${location.pathname}${cleanQuery ? `?${cleanQuery}` : ''}${location.hash}`); }
      const $ = (id) => document.getElementById(id);
      const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
      const themeStorageKey = 'mantou-theme';
      const readThemePreference = () => { try { return localStorage.getItem(themeStorageKey) === 'dark' ? 'dark' : 'light'; } catch (_) { return 'light'; } };
      const updateThemeMeta = (theme) => { const meta = document.querySelector('meta[name="theme-color"]'); if (meta) meta.setAttribute('content', theme === 'dark' ? '#171a24' : '#f8f8ff'); };
      const applyTheme = (preference = readThemePreference(), persist = true) => {
        const next = preference === 'dark' ? 'dark' : 'light';
        const theme = next;
        const previous = document.documentElement.dataset.theme;
        document.documentElement.dataset.themePreference = next;
        document.documentElement.dataset.theme = theme;
        updateThemeMeta(theme);
        if (persist) { try { localStorage.setItem(themeStorageKey, next); } catch (_) {} }
        const control = $('theme-select'); if (control && control.value !== next) control.value = next;
        if (previous && previous !== theme) {
          document.documentElement.classList.remove('theme-switching');
          void document.documentElement.offsetWidth;
          document.documentElement.classList.add('theme-switching');
          setTimeout(() => document.documentElement.classList.remove('theme-switching'), 320);
        }
      };
      applyTheme(readThemePreference(), false);
      $('theme-select')?.addEventListener('change', (event) => applyTheme(event.target.value));
      const views = {
        dashboard: ['控制台', '查看机器人和小说服务的实时状态'],
        bot: ['机器人配置', '查看安全摘要、监听地址和访问策略'],
        novels: ['小说功能', '管理全局开关、测试模式和平台开关'],
        pans: ['网盘配置', '管理多网盘分享和账号安全摘要'],
        runtime: ['运行状态', '查看服务器、数据库和插件实时指标'],
        help: ['帮助指令', '查看机器人当前支持的聊天指令'],
         settings: ['系统设置', '直接修改插件配置、网盘目录和数据库连接'],
        messages: ['消息记录', '查看群聊和私聊消息，回复、发送和撤回消息'],
      };
      let snapshot = null;
      let activeView = null;
      let activePanTab = null;
      let toastTimer = null;
      const showNotice = (message) => { const node = $('notice'); node.textContent = message; node.classList.toggle('show', Boolean(message)); };
      const toast = (message) => { const node = $('toast'); node.textContent = message; node.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove('show'), 2200); };
      const api = async (path, options = {}) => {
        const requestOptions = { cache:'no-store', credentials:'same-origin', ...options };
        const requestHeaders = {...(options.headers || {})};
        if (!(requestOptions.body instanceof FormData) && !Object.keys(requestHeaders).some((key) => key.toLowerCase() === 'content-type')) requestHeaders['Content-Type'] = 'application/json';
        requestOptions.headers = requestHeaders;
        const response = await fetch(`/api/${path}`, requestOptions);
        const data = await response.json().catch(() => ({ok:false,error:'服务器返回格式错误'}));
        if (!response.ok || !data.ok) { const error = new Error(data.error || '请求失败'); error.status = response.status; throw error; }
        return data;
      };
      const viewFromUrl = () => { const current = new URLSearchParams(location.search).get('view'); return views[current] ? current : 'dashboard'; };
      const setView = (view, push = true) => {
        const next = views[view] ? view : 'dashboard';
        const previousView = activeView;
        activeView = next;
        if (push) { const nextParams = new URLSearchParams(location.search); nextParams.set('view', next); history.pushState({view:next}, '', `${location.pathname}?${nextParams.toString()}`); }
        const meta = views[next];
        $('page-title').textContent = meta[0]; $('page-subtitle').textContent = meta[1];
        document.querySelectorAll('[data-page]').forEach((node) => { node.hidden = node.dataset.page !== next; });
        document.querySelectorAll('.sidebar [data-view]').forEach((node) => { const active = node.dataset.view === next; node.classList.toggle('active', active); node.setAttribute('aria-current', active ? 'page' : 'false'); });
        if (next === 'dashboard') $('page-eyebrow').textContent = '馒头Bot / 管理台'; else $('page-eyebrow').textContent = '馒头Bot / 功能页面';
        if (next !== 'messages' && previousView === 'messages') setMsgMobileChatOpen(false);
        if (next === 'messages') {
          connectMsgEvents();
          if (previousView !== 'messages') loadMsgChats();
          if (previousView !== 'messages' && msgState.chatId) loadMsgHistory();
        }
        else if (msgState.eventSource || msgState.eventSocket || msgState.eventReconnect) closeMsgEvents();
        const scrollContainer = document.querySelector('.main');
        if (scrollContainer) scrollContainer.scrollTop = 0;
        window.scrollTo({top:0, behavior:'auto'});
      };
      const switchHtml = (key, enabled, editable, label) => `<button class="switch ${enabled ? 'on' : ''}" data-switch="${esc(key)}" data-enabled="${enabled}" ${editable ? '' : 'disabled'} aria-label="${esc(label)}" aria-pressed="${enabled}"><span></span></button>`;
      const platformGlyph = (name) => ({'番茄':'番','七猫':'猫','书旗':'旗','追书':'追','QQ阅读':'阅','QQ浏览器':'浏','得间':'得','点众':'众','盐言':'盐','塔读':'塔','百度':'度','小米':'米','晋江':'晋','宜搜':'搜','米读':'读','猫眼':'眼','酷我':'酷','酷匠':'匠','连城':'城','菠萝包':'菠'}[name] || String(name || '书').slice(0, 1));
      const categoryOrder = ['basic_settings', 'help_web_settings', 'uc_pan_settings', 'quark_pan_settings', 'baidu_pan_settings', 'database_settings'];
      const safeFieldValue = (field) => {
        if (field.kind === 'admin_list') return Array.isArray(field.value) ? field.value.join('\n') : '';
        if (field.kind === 'boolean') return Boolean(field.value);
        return field.secret ? '' : String(field.value ?? '');
      };
      const renderConfigEditor = (targetId, fields, editable, filter) => {
        const node = $(targetId);
        if (!node) return;
        const selected = (fields || []).filter((field) => {
          if (filter && !filter(field)) return false;
          // 帮助网页只在控制台展示端口和登录凭据；监听地址/域名继续由后端读取。
          if (field.category === 'help_web_settings') return ['help_web_port', 'help_web_admin_username', 'help_web_admin_password'].includes(field.key);
          return true;
        });
        const groups = [];
        categoryOrder.forEach((category) => {
          const groupFields = selected.filter((field) => field.category === category);
          if (groupFields.length) groups.push([category, groupFields]);
        });
        selected.filter((field) => !categoryOrder.includes(field.category)).forEach((field) => {
          let group = groups.find((item) => item[0] === field.category);
          if (!group) { group = [field.category, []]; groups.push(group); }
          group[1].push(field);
        });
        if (!groups.length) { node.innerHTML = '<div class="empty">暂无可编辑配置</div>'; return; }
        node.innerHTML = groups.map(([category, groupFields]) => `<section class="config-group" data-config-category="${esc(category)}"><h3>${esc(groupFields[0].category_name || category)}</h3><div class="config-fields">${groupFields.map((field) => {
          const inputId = `cfg-${field.key}`;
          const label = esc(field.label || field.key);
          const hint = field.secret ? (field.configured ? '已配置，留空表示不修改' : '敏感值只写入，不在页面回显') : '';
          if (field.kind === 'admin_list') return `<div class="config-field full"><label for="${inputId}">${label}</label><textarea id="${inputId}" data-config-field="${esc(field.key)}" ${editable ? '' : 'disabled'} placeholder="每行一个 QQ 号">${esc(safeFieldValue(field))}</textarea><small>${hint || '共 ' + esc(field.count || 0) + ' 个管理员'}</small></div>`;
          if (field.kind === 'select') return `<div class="config-field"><label for="${inputId}">${label}</label><select id="${inputId}" data-config-field="${esc(field.key)}" ${editable ? '' : 'disabled'}>${(field.options || []).map((option) => `<option value="${esc(option)}" ${String(option) === String(field.value ?? '') ? 'selected' : ''}>${esc(option)}</option>`).join('')}</select><small>${hint}</small></div>`;
          const type = field.secret ? 'password' : (field.kind === 'number' ? 'number' : 'text');
          const placeholder = field.secret && field.configured ? '已配置，输入新密码可替换' : (field.secret ? '留空不修改' : '');
          const input = `<input id="${inputId}" type="${type}" data-config-field="${esc(field.key)}" value="${esc(safeFieldValue(field))}" ${editable ? '' : 'disabled'} placeholder="${esc(placeholder)}">`;
          const toggle = field.key === 'help_web_admin_password' ? `<button class="config-secret-toggle" type="button" data-config-secret-toggle="${inputId}" ${editable ? '' : 'disabled'} aria-label="显示或隐藏登录密码" aria-pressed="false">显示</button>` : '';
          return `<div class="config-field"><label for="${inputId}">${label}</label><div class="config-input-wrap">${input}${toggle}</div><small>${hint}</small></div>`;
        }).join('')}</div></section>`).join('') + `<div class="config-actions"><button class="primary-button" type="button" data-config-save ${editable ? '' : 'disabled'}>保存配置</button><span class="config-message" data-config-message></span></div>`;
        node.querySelector('[data-config-save]')?.addEventListener('click', () => saveConfig(node));
        node.querySelectorAll('[data-config-secret-toggle]').forEach((button) => button.addEventListener('click', () => {
          const input = $(button.dataset.configSecretToggle);
          if (!input) return;
          const visible = input.type === 'text';
          input.type = visible ? 'password' : 'text';
          button.textContent = visible ? '显示' : '隐藏';
          button.setAttribute('aria-pressed', String(!visible));
        }));
      };
       const saveConfig = async (editor) => {
        const fields = {};
        editor.querySelectorAll('[data-config-field]').forEach((input) => {
          const value = input.type === 'checkbox' ? input.checked : input.value;
          if (input.type === 'password' && !value.trim()) return;
           if (input.dataset.configField === 'group_file_cleanup_admin_qq') {
             fields[input.dataset.configField] = value.split(/[\s,，]+/).filter(Boolean);
          } else fields[input.dataset.configField] = value;
        });
        const message = editor.querySelector('[data-config-message]');
        try { const result = await api('config', {method:'POST', body:JSON.stringify({fields})}); if (message) { message.textContent = result.message || '配置已保存'; message.className = 'config-message ok'; } toast(result.message || '配置已保存'); await load(); }
         catch (error) { if (error.status === 401) showAuthError(error); if (message) { message.textContent = error.message; message.className = 'config-message error'; } else toast(error.message); }
      };
       const panPlatformGlyph = (key) => ({UC:'U','夸克':'夸','百度':'度'})[key] || String(key || '盘').slice(0, 1);
       const panAccountRows = (item, editable) => {
         const accounts = Array.isArray(item.account_summary) ? item.account_summary : [];
         return accounts.map((account, position) => {
           const index = Number(account?.index) > 0 ? Number(account.index) : position + 1;
           const name = account?.name || '未命名账号';
           const phone = account?.phone || '未获取';
           return `<div class="account-row pan-account-row"><div class="account-row-main"><strong>账号${esc(index)}</strong><span>${esc(name)} · ${esc(phone)}</span></div><div class="account-row-actions"><span class="tag ok">已保存</span><button type="button" data-pan-delete="${esc(item.key)}" data-index="${esc(index)}" ${editable ? '' : 'disabled'} aria-label="删除${esc(item.name)}账号${esc(index)}">删除</button></div></div>`;
         }).join('');
       };
       const panSwitchHtml = (key, enabled, editable, name) => `<button class="switch pan-enable-switch ${enabled ? 'on' : ''}" data-pan-enable="${esc(key)}" data-enabled="${enabled}" ${editable ? '' : 'disabled'} aria-label="${esc(enabled ? '关闭' : '开启')}${esc(name)}" aria-pressed="${enabled}"><span></span></button>`;
       const renderPanCard = (item, pansEditable, configEditable) => {
         const directoryField = ({UC:'uc_pan_upload_dir','夸克':'quark_pan_upload_dir','百度':'baidu_pan_upload_dir'})[item.key] || '';
         const enabled = item.enabled !== false;
         const accounts = Array.isArray(item.account_summary) ? item.account_summary : [];
         const accountCount = Number(item.accounts) >= 0 ? Number(item.accounts) : accounts.length;
         const configured = Boolean(item.configured || accounts.length);
         const selectedAccount = Number(item.selected_account) > 0 ? Number(item.selected_account) : 1;
         const stateTag = enabled ? '<span class="tag ok">已开启</span>' : '<span class="tag off">已关闭</span>';
         const configTag = configured ? '<span class="tag ok">已配置</span>' : '<span class="tag off">未配置</span>';
         const groupOptions = accounts.map((account, position) => {
           const index = Number(account?.index) > 0 ? Number(account.index) : position + 1;
           return `<option value="${esc(index)}" ${index === selectedAccount ? 'selected' : ''}>账号${esc(index)}</option>`;
         }).join('') || '<option value="1">账号1</option>';
         const defaultOption = item.active ? '默认使用中' : (enabled ? '设为默认主网盘' : '请先开启网盘');
         return `<article id="pan-card-${esc(item.key)}" class="pan-card pan-workspace ${item.active ? 'active' : ''} ${enabled ? '' : 'is-disabled'}" data-pan-card="${esc(item.key)}" role="tabpanel" aria-labelledby="pan-tab-${esc(item.key)}">
           <header class="pan-card-head pan-top">
             <div class="pan-card-brand pan-card-identity pan-title"><div class="pan-logo">${esc(panPlatformGlyph(item.key))}</div><div><strong>${esc(item.name)}</strong><small>${enabled ? '参与启用平台的并发分享' : '当前暂停上传和分享'}</small></div></div>
             <div class="pan-card-head-actions pan-top-actions">${item.active ? '<span class="tag active">默认主网盘</span>' : ''}<div class="pan-enable"><span>${enabled ? '运行中' : '已停用'}</span>${panSwitchHtml(item.key, enabled, pansEditable, item.name)}</div></div>
           </header>
           <div class="pan-card-stats pan-meta">
             <div class="pan-stat"><span>运行状态</span><strong>${stateTag}</strong></div>
             <div class="pan-stat"><span>配置状态</span><strong>${configTag}</strong></div>
             <div class="pan-stat"><span>账号数量</span><strong>${esc(accountCount)} 个</strong></div>
             <div class="pan-stat"><span>上传目录</span><strong title="${esc(item.directory)}">${esc(item.directory || '默认目录')}</strong></div>
           </div>
           <div class="pan-security-note pan-card-note">登录态：${configured ? '已保存（Cookie 不回显）' : '未配置'}${enabled ? '' : ' · 已暂停上传和分享'}${item.key === '夸克' ? ' · 可刷新账号资料' : ''}</div>
           <div class="pan-card-content">
             <section class="pan-column pan-column-primary">
               <div class="pan-section-title pan-section-heading"><div><span class="pan-section-kicker">STORAGE PATH</span><h3>上传目录</h3></div><span class="pan-section-hint">文件会按此目录生成分享</span></div>
               <div class="pan-directory"><input type="text" data-pan-dir="${esc(item.key)}" data-pan-dir-field="${esc(directoryField)}" value="${esc(item.directory || '')}" placeholder="/小说机器人" ${configEditable ? '' : 'disabled'} aria-label="${esc(item.name)}上传目录"><button class="outline-button" type="button" data-pan-dir-save="${esc(item.key)}" ${configEditable ? '' : 'disabled'}>保存目录</button></div>
               <div class="pan-section-title pan-section-heading account-heading"><div><span class="pan-section-kicker">ACCOUNTS</span><h3>登录账号</h3></div><span class="pan-section-hint">Cookie 仅写入，不在页面回显</span></div>
               <div class="account-list pan-account-list">${panAccountRows(item, pansEditable) || '<div class="empty">暂无账号，请添加登录态</div>'}</div>
               <div class="account-add pan-account-add"><input type="password" data-pan-cookie="${esc(item.key)}" placeholder="粘贴 ${esc(item.name)} Cookie（只写入）" autocomplete="off" ${pansEditable ? '' : 'disabled'} aria-label="添加${esc(item.name)}账号 Cookie"><button class="outline-button" type="button" data-pan-add="${esc(item.key)}" ${pansEditable ? '' : 'disabled'}>添加账号</button></div>
             </section>
             <aside class="pan-column pan-column-secondary">
               <section class="pan-action-block"><div class="pan-section-title pan-section-heading"><div><span class="pan-section-kicker">SHARE ROUTE</span><h3>分享设置</h3></div><span class="pan-section-hint">完成后生成链接</span></div><label class="pan-field-label" for="pan-select-${esc(item.key)}">默认主网盘</label><div class="account-actions pan-action-row"><select id="pan-select-${esc(item.key)}" class="pan-select" data-pan="${esc(item.key)}" ${pansEditable ? '' : 'disabled'} aria-label="选择${esc(item.name)}"><option value="">${defaultOption}</option><option value="${esc(item.key)}" ${enabled ? '' : 'disabled'}>切换到${esc(item.name)}</option></select><button class="outline-button pan-refresh-button" type="button" data-pan-refresh="${esc(item.key)}" ${pansEditable && item.key === '夸克' ? '' : 'disabled'} title="刷新夸克账号资料">刷新资料</button></div></section>
               <details class="pan-advanced pan-group-settings"><summary><span>群账号选择</span><small>为不同群使用不同账号</small></summary><div class="pan-advanced-content pan-advanced-body"><p>输入群号后选择该群使用的账号；控制台默认显示账号${esc(selectedAccount)}。</p><div class="group-account"><input type="text" data-pan-group="${esc(item.key)}" placeholder="QQ群号" ${pansEditable ? '' : 'disabled'} inputmode="numeric" aria-label="${esc(item.name)}群号"><select data-pan-group-index="${esc(item.key)}" ${pansEditable ? '' : 'disabled'} aria-label="选择${esc(item.name)}账号">${groupOptions}</select><button class="outline-button" type="button" data-pan-group-save="${esc(item.key)}" ${pansEditable ? '' : 'disabled'}>保存</button></div></div></details>
             </aside>
           </div>
         </article>`;
       };
       const applyPanTab = (key) => { const cards = document.querySelectorAll('[data-pan-card]'); const tabs = document.querySelectorAll('[data-pan-tab]'); const available = Array.from(cards).map((node) => node.dataset.panCard); const selected = available.includes(key) ? key : (available[0] || ''); activePanTab = selected || null; try { if (selected) sessionStorage.setItem('mantou-pan-tab', selected); } catch (_) {} tabs.forEach((node) => { const isActive = node.dataset.panTab === selected; node.classList.toggle('active', isActive); node.setAttribute('aria-selected', String(isActive)); node.tabIndex = isActive ? 0 : -1; }); cards.forEach((node) => { const isActive = node.dataset.panCard === selected; node.hidden = !isActive; node.setAttribute('aria-hidden', String(!isActive)); }); };
       const choosePanTab = (key) => { applyPanTab(key); };
      const render = (data) => {
        snapshot = data;
        const auth = data.auth || {}; const novels = data.novels || {}; const pans = data.pans || {}; const server = data.server || {}; const database = data.database || {};
        const adminName = String(auth.username || '管理员');
        if ($('admin-name')) $('admin-name').textContent = adminName;
        if ($('admin-popover-name')) $('admin-popover-name').textContent = adminName;
        if ($('admin-avatar')) $('admin-avatar').textContent = adminName.slice(0, 1) || '管';
        if ($('admin-popover-role')) $('admin-popover-role').textContent = `${auth.role || '控制台管理员'} · 当前会话`;
        if ($('admin-popover-scope')) $('admin-popover-scope').textContent = `插件管理员白名单：${Number(auth.admin_count || 0)} 个`;
        $('metric-global').textContent = novels.global_enabled ? '已开启' : '已关闭'; $('metric-global-meta').textContent = novels.test_mode ? '测试模式已开启' : '测试模式未开启';
        $('metric-pan').textContent = pans.active || '--'; const activePan = (pans.items || []).find((item) => item.active); $('metric-pan-meta').textContent = activePan ? `${activePan.accounts} 个账号 · ${activePan.configured ? '已配置' : '未配置'}` : '未选择';
        $('metric-db').textContent = database.status || '--'; $('metric-db-meta').textContent = database.configured ? '状态可持久化' : '未配置数据库'; $('metric-version').textContent = `v${data.version || '--'}`; $('console-version').textContent = `v${data.version || '--'}`;
        $('dashboard-cpu').textContent = server.cpu || '--'; $('dashboard-memory').textContent = server.memory || '--'; $('dashboard-runtime').textContent = server.runtime || '--'; $('dashboard-updated').textContent = '刚刚';
        [['global-switch', '__global__', novels.global_enabled, '切换全局小说功能'], ['test-switch', '__test__', novels.test_mode, '切换管理员测试模式']].forEach(([id, key, enabled, label]) => { const node = $(id); node.className = `switch ${enabled ? 'on' : ''}`; node.dataset.switch = key; node.dataset.enabled = String(Boolean(enabled)); node.disabled = !novels.editable; node.setAttribute('aria-label', label); node.setAttribute('aria-pressed', String(Boolean(enabled))); });
        const platforms = novels.platforms || [];
        const enabledCount = platforms.filter((item) => item.enabled).length;
        const totalCount = platforms.length;
        const novelState = $('novel-state-pill');
        if (novelState) { novelState.classList.toggle('is-off', !novels.global_enabled); novelState.querySelector('strong').textContent = novels.global_enabled ? '入口已开启' : '入口已关闭'; }
        if ($('novel-master-label')) $('novel-master-label').textContent = novels.global_enabled ? '下载入口已开启' : '下载入口已关闭';
        if ($('novel-platform-summary')) $('novel-platform-summary').textContent = `已开启 ${enabledCount} 个平台`;
        if ($('novel-enabled-count')) $('novel-enabled-count').textContent = `${enabledCount} / ${totalCount} 已开启`;
        if ($('novel-test-label')) $('novel-test-label').textContent = novels.test_mode ? '测试模式已开启' : '测试模式未开启';
        $('novel-grid').innerHTML = platforms.map((item) => `<div class="novel-item ${item.enabled ? 'is-enabled' : 'is-disabled'}"><div class="novel-item-main"><div class="novel-badge">${esc(platformGlyph(item.name))}</div><div class="novel-item-copy"><div class="novel-item-title"><strong>${esc(item.name)}</strong><span class="novel-item-status">${item.enabled ? '已开启' : '已关闭'}</span></div><small>${item.enabled ? '允许识别链接并进入下载流程' : '当前不会响应此平台链接'}</small></div></div>${switchHtml(item.key, item.enabled, novels.editable, `切换${item.name}`)}</div>`).join('') || '<div class="empty">没有可用小说平台</div>';
         const panItems = Array.isArray(pans.items) ? pans.items : [];
         const panTotal = panItems.length;
         const panEnabledCount = panItems.filter((item) => item.enabled !== false).length;
         const panConfiguredCount = panItems.filter((item) => Boolean(item.configured || (Array.isArray(item.account_summary) && item.account_summary.length))).length;
         const panAccountCount = panItems.reduce((total, item) => {
           const listed = Array.isArray(item.account_summary) ? item.account_summary.length : 0;
           const reported = Number(item.accounts);
           return total + (Number.isFinite(reported) && reported >= 0 ? reported : listed);
         }, 0);
         const panReadyCount = panItems.filter((item) => item.enabled !== false && Boolean(item.configured || (Array.isArray(item.account_summary) && item.account_summary.length))).length;
         if ($('pan-active-label')) $('pan-active-label').textContent = pans.active || '--';
         if ($('pan-enabled-count')) $('pan-enabled-count').textContent = `${panEnabledCount} / ${panTotal}`;
         if ($('pan-configured-count')) $('pan-configured-count').textContent = `${panConfiguredCount} / ${panTotal}`;
         if ($('pan-account-count')) $('pan-account-count').textContent = `${panAccountCount}`;
         if ($('pan-upload-mode')) $('pan-upload-mode').textContent = panReadyCount ? `${panReadyCount} 个平台并发` : '暂无可用平台';
         $('pan-grid').innerHTML = panItems.map((item) => renderPanCard(item, pans.editable, pans.config_editable)).join('') || '<div class="empty">没有网盘数据</div>';
        let preferredPanTab = activePanTab; if (!preferredPanTab) { try { preferredPanTab = sessionStorage.getItem('mantou-pan-tab'); } catch (_) {} } applyPanTab(preferredPanTab || pans.active || 'UC');
        $('runtime-cpu').textContent = server.cpu || '--'; $('runtime-memory').textContent = server.memory || '--'; $('runtime-disk').textContent = server.disk || '--'; $('runtime-runtime').textContent = server.runtime || '--'; $('runtime-os').textContent = server.os || '--'; $('runtime-db').textContent = database.status || '--'; $('runtime-pan').textContent = pans.active || '--'; $('runtime-version').textContent = `v${data.version || '--'}`;
        const configList = $('config-list'); if (configList) configList.innerHTML = `<div class="config-item"><span>监听地址</span><strong>${esc(server.listen || '--')}</strong></div><div class="config-item"><span>访问地址</span><strong title="${esc(server.address)}">${esc(server.address || '--')}</strong></div><div class="config-item"><span>域名模式</span><strong>${data.config && data.config.custom_domain ? '自定义域名' : '自动服务器 IP'}</strong></div><div class="config-item"><span>登录方式</span><strong>${esc(data.config && data.config.auth_mode || '账号密码会话')}</strong></div>`;
        const configFields = data.config && data.config.fields || [];
        renderConfigEditor('basic-config-editor', configFields, Boolean(data.config && data.config.editable), (field) => ['basic_settings', 'help_web_settings'].includes(field.category));
        renderConfigEditor('settings-editor', configFields, Boolean(data.config && data.config.editable), (field) => ['database_settings', 'uc_pan_settings', 'quark_pan_settings', 'baidu_pan_settings'].includes(field.category));
        renderQQAuthEditor(data.qq_reader || {});
        $('updated').textContent = '刚刚更新';
        document.querySelectorAll('[data-switch]').forEach((node) => node.addEventListener('click', () => changeNovel(node)));
        document.querySelectorAll('[data-pan]').forEach((node) => node.addEventListener('change', () => { const value = node.value; node.value = ''; if (value) changePan(value, node); }));
        document.querySelectorAll('[data-pan-add]').forEach((node) => node.addEventListener('click', () => addPanAccount(node.dataset.panAdd)));
        document.querySelectorAll('[data-pan-delete]').forEach((node) => node.addEventListener('click', () => deletePanAccount(node.dataset.panDelete, node.dataset.index)));
         document.querySelectorAll('[data-pan-refresh]').forEach((node) => node.addEventListener('click', () => refreshPanAccounts(node.dataset.panRefresh, node)));
         document.querySelectorAll('[data-pan-group-save]').forEach((node) => node.addEventListener('click', () => savePanGroup(node.dataset.panGroupSave)));
         document.querySelectorAll('[data-pan-dir-save]').forEach((node) => node.addEventListener('click', () => savePanDirectory(node.dataset.panDirSave, node)));
         document.querySelectorAll('[data-pan-enable]').forEach((node) => node.addEventListener('click', () => changePanEnabled(node.dataset.panEnable, node)));
         document.querySelectorAll('[data-pan-tab]').forEach((node) => { node.addEventListener('click', () => choosePanTab(node.dataset.panTab)); node.addEventListener('keydown', (event) => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); const tabs = Array.from(document.querySelectorAll('[data-pan-tab]')); const index = tabs.indexOf(node); const next = tabs[(index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length]; next?.focus(); choosePanTab(next?.dataset.panTab); } }); });
      };
      const renderQQAuthEditor = (auth) => {
        const node = $('qq-auth-editor'); if (!node) return;
        node.innerHTML = `<div class="qq-auth-form"><div class="qq-auth-row"><input type="text" id="qq-ywguid" placeholder="ywguid" autocomplete="off"><input type="password" id="qq-ywkey" placeholder="ywkey" autocomplete="off"></div><div class="qq-auth-actions"><button class="primary-button" type="button" id="qq-auth-save">保存登录态</button><button class="outline-button" type="button" id="qq-auth-delete" ${auth.configured ? '' : 'disabled'}>清除登录态</button><span class="qq-auth-message">${auth.configured ? `已配置${auth.updated_at ? ` · ${new Date(auth.updated_at * 1000).toLocaleString()}` : ''}` : '未配置'}</span></div></div>`;
        $('qq-auth-save').addEventListener('click', saveQQAuth); $('qq-auth-delete').addEventListener('click', deleteQQAuth);
      };
       const addPanAccount = async (platform) => { const input = document.querySelector(`[data-pan-cookie="${CSS.escape(platform)}"]`); const button = document.querySelector(`[data-pan-add="${CSS.escape(platform)}"]`); const cookie = input?.value.trim(); if (!cookie) return toast('请先粘贴 Cookie'); if (button) button.disabled = true; try { await api(`pan-accounts/${encodeURIComponent(platform)}`, {method:'POST', body:JSON.stringify({cookie})}); if (input) input.value = ''; toast(`${platform}账号已保存`); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const deletePanAccount = async (platform, index, button) => { if (!confirm(`确定删除${platform}账号${index}吗？`)) return; if (button) button.disabled = true; try { await api(`pan-accounts/${encodeURIComponent(platform)}`, {method:'DELETE', body:JSON.stringify({index:Number(index)})}); toast('账号已删除'); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const refreshPanAccounts = async (platform, button) => { if (button) button.disabled = true; try { await api(`pan-accounts/${encodeURIComponent(platform)}?refresh=1`); toast('账号资料已刷新'); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const savePanDirectory = async (platform, button) => { const input = document.querySelector(`[data-pan-dir="${CSS.escape(platform)}"]`); const field = input?.dataset.panDirField; const value = input?.value.trim(); if (!field || !value) return toast('请输入上传目录'); if (button) button.disabled = true; try { const result = await api('config', {method:'POST', body:JSON.stringify({fields:{[field]:value}})}); toast(result.message || `${platform}上传目录已保存`); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const savePanGroup = async (platform) => { const group = document.querySelector(`[data-pan-group="${CSS.escape(platform)}"]`)?.value.trim(); const select = document.querySelector(`[data-pan-group-index="${CSS.escape(platform)}"]`); if (!group) return toast('请输入QQ群号'); if (!/^\d+$/.test(group)) return toast('QQ群号格式无效'); try { await api('pan-account-selection', {method:'POST', body:JSON.stringify({platform, index:Number(select?.value || 1), group_id:group})}); toast('群账号选择已保存'); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } };
       const saveQQAuth = async () => { const ywguid = $('qq-ywguid')?.value.trim(); const ywkey = $('qq-ywkey')?.value.trim(); if (!ywguid || !ywkey) return toast('请填写 ywguid 和 ywkey'); const button = $('qq-auth-save'); if (button) button.disabled = true; try { await api('qq-reader-auth', {method:'POST', body:JSON.stringify({ywguid, ywkey})}); if ($('qq-ywguid')) $('qq-ywguid').value = ''; if ($('qq-ywkey')) $('qq-ywkey').value = ''; toast('QQ阅读登录态已保存'); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const deleteQQAuth = async () => { if (!confirm('确定清除 QQ阅读登录态吗？')) return; const button = $('qq-auth-delete'); if (button) button.disabled = true; try { await api('qq-reader-auth', {method:'DELETE'}); toast('QQ阅读登录态已清除'); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
      const showAuthError = (error) => { if (error.status === 401) { location.reload(); return; } if ($('popover-logout')) $('popover-logout').hidden = true; showNotice(error.status === 503 ? '登录服务尚未启用，请联系管理员。' : '控制台数据暂时不可用，请稍后重试。'); };
      const adminChip = $('admin-chip'); const adminPopover = $('admin-popover');
      adminChip?.addEventListener('click', (event) => { event.stopPropagation(); const expanded = adminChip.getAttribute('aria-expanded') === 'true'; adminChip.setAttribute('aria-expanded', String(!expanded)); if (adminPopover) adminPopover.hidden = expanded; });
      document.addEventListener('click', () => { if (adminChip?.getAttribute('aria-expanded') === 'true') { adminChip.setAttribute('aria-expanded', 'false'); if (adminPopover) adminPopover.hidden = true; } });
      const changeNovel = async (node) => { if (!snapshot || !snapshot.novels.editable) return toast('数据库未配置，开关不能保存'); const enabled = node.dataset.enabled !== 'true'; node.disabled = true; try { await api('novel-switch', {method:'POST', body:JSON.stringify({key:node.dataset.switch, enabled})}); toast('小说开关已更新'); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
       const changePan = async (key, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，网盘选择不能保存'); const item = (snapshot.pans.items || []).find((entry) => entry.key === key); if (item && item.enabled === false) return toast('请先开启该网盘'); if (node) node.disabled = true; try { await api('pan-switch', {method:'POST', body:JSON.stringify({key})}); toast('主分享网盘已更新'); await load(); } catch (error) { if (node) node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
       const changePanEnabled = async (key, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，网盘开关不能保存'); const enabled = node.dataset.enabled !== 'true'; node.disabled = true; try { const result = await api('pan-enable', {method:'POST', body:JSON.stringify({key, enabled})}); toast(result.message || `网盘${enabled ? '已开启' : '已关闭'}`); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
      const load = async () => { try { render(await api('dashboard')); void loadBotProfile(); if ($('popover-logout')) $('popover-logout').hidden = false; setView(viewFromUrl(), false); } catch (error) { showAuthError(error); } };
      $('popover-logout').addEventListener('click', async () => { try { await api('logout', {method:'POST'}); } finally { location.reload(); } });
      document.querySelectorAll('[data-view]').forEach((node) => node.addEventListener('click', (event) => { event.preventDefault(); setView(node.dataset.view); }));
      window.addEventListener('popstate', () => setView(viewFromUrl(), false));

      // ---------- 消息记录页 ----------
      const msgHistoryPageSize = 100;
      const msgState = { filter:'all', search:'', page:1, chatId:'', chatType:'group', chatRemoved:false, chats:[], realtimeChats:new Map(), messages:[], historyData:null, historyCache:new Map(), renderedChatId:'', initialScrollChatId:'', positionToken:0, positionFrame:null, positionObserver:null, positionBody:null, pendingNewMessages:0, historyRequest:0, historyOlderRequest:0, historyOlderLoading:false, historyScheduleFrame:null, historyScheduleToken:0, chatListRequest:0, chatListAbort:null, chatListPromise:null, chatListKey:'', chatListRendered:false, chatListServerLoaded:false, chatListTopPending:false, chatListScrollActive:false, chatListScrollTimer:null, chatListPendingData:null, historyAbort:null, historyOlderAbort:null, readInFlight:new Set(), chatRenderTimer:null, chatRenderSignature:null, realtimeMessageTimer:null, realtimeMessageCount:0, realtimeToBottom:false, realtimeRenderChatId:'', quote:null, mute:{member:'',name:''}, mutes:new Map(), muteRequestAt:0, muteRequestToken:0, muteRequestChatId:'', muteRequestPromise:null, sendType:'text', sendMode:'default', muteMinutes:30, timer:null, muteTimer:null, eventSocket:null, eventSource:null, eventTransport:'', eventReconnect:null, eventRefreshTimer:null, eventKeys:new Set(), eventKeyOrder:[], adminByChat:new Map(), adminScanAttempted:new Set(), adminScanFailures:new Map(), adminCheckedAt:new Map(), adminRequestToken:0, lastRolesAt:0, lastRolesChatId:'', botIsAdmin:false, adChatId:'', adEnabled:false, adEditable:false, adLoading:false, adSaving:false, profiles:{}, pastedImage:null, pastedImageFile:null, pastedImageSource:'', mediaData:null, mediaFile:null, mediaName:'', mediaType:0, mediaMime:'', composerSelection:null, sending:false, optimisticSends:new Map(), optimisticSeq:0, multi:false, selected:new Set(), ctxMsg:null, ctxUser:null };
      const composerHasImage = () => Boolean(String(msgState.pastedImage || '').trim() || String(msgState.pastedImageSource || '').trim());
      const composerHasMedia = () => Boolean((msgState.mediaFile || String(msgState.mediaData || '').trim()) && Number(msgState.mediaType || 0));
      const composerImageMarker = '\uFFFC';
      const getComposerEditor = () => $('msg-editor');
      const syncComposerImageState = () => {
        const editor = getComposerEditor();
        if (composerHasImage() && !editor?.querySelector('[data-composer-image="1"]')) {
          msgState.pastedImage = null;
          msgState.pastedImageFile = null;
          msgState.pastedImageSource = '';
          $('msg-input-box')?.classList.remove('has-inline-image');
        }
      };
      const composerNodeText = (node, root = false) => {
        if (!node) return '';
        if (node.nodeType === Node.TEXT_NODE) return String(node.nodeValue || '');
        if (node.nodeType !== Node.ELEMENT_NODE) return '';
        if (node.dataset?.composerImage === '1') return composerImageMarker;
        if (node.tagName === 'BR') return '\n';
        let result = Array.from(node.childNodes || []).map((child) => composerNodeText(child)).join('');
        if (!root && ['DIV', 'P', 'LI'].includes(node.tagName) && result && !result.endsWith('\n')) result += '\n';
        return result;
      };
      const getComposerText = () => composerNodeText(getComposerEditor(), true).replace(/\u00a0/g, ' ');
      const saveComposerSelection = () => {
        const editor = getComposerEditor();
        const selection = window.getSelection?.();
        if (!editor || !selection || !selection.rangeCount) return;
        const range = selection.getRangeAt(0);
        if (editor.contains(range.commonAncestorContainer)) msgState.composerSelection = range.cloneRange();
      };
      const restoreComposerSelection = () => {
        const editor = getComposerEditor();
        const selection = window.getSelection?.();
        if (!editor || !selection) return null;
        const range = msgState.composerSelection && editor.contains(msgState.composerSelection.commonAncestorContainer)
          ? msgState.composerSelection.cloneRange() : document.createRange();
        if (!msgState.composerSelection || !editor.contains(range.commonAncestorContainer)) {
          range.selectNodeContents(editor);
          range.collapse(false);
        }
        selection.removeAllRanges();
        selection.addRange(range);
        return range;
      };
      const insertComposerText = (value) => {
        const editor = getComposerEditor();
        if (!editor || !value) return;
        editor.focus();
        const range = restoreComposerSelection();
        if (!range) return;
        range.deleteContents();
        const text = document.createTextNode(String(value));
        range.insertNode(text);
        range.setStartAfter(text);
        range.collapse(true);
        const selection = window.getSelection?.();
        selection?.removeAllRanges();
        selection?.addRange(range);
        msgState.composerSelection = range.cloneRange();
      };
      const insertComposerImage = (source) => {
        const editor = getComposerEditor();
        if (!editor || !source) return;
        editor.querySelector('[data-composer-image="1"]')?.remove();
        editor.focus();
        const range = restoreComposerSelection();
        if (!range) return;
        range.deleteContents();
        const wrapper = document.createElement('span');
        wrapper.className = 'composer-inline-image';
        wrapper.dataset.composerImage = '1';
        wrapper.contentEditable = 'false';
        const image = document.createElement('img');
        image.src = source;
        image.alt = '待发送图片';
        image.draggable = false;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = '×';
        remove.setAttribute('aria-label', '移除图片');
        remove.addEventListener('click', (event) => { event.preventDefault(); event.stopPropagation(); clearMsgImage(); });
        wrapper.append(image, remove);
        range.insertNode(wrapper);
        const spacer = document.createTextNode(' ');
        wrapper.after(spacer);
        range.setStartAfter(spacer);
        range.collapse(true);
        const selection = window.getSelection?.();
        selection?.removeAllRanges();
        selection?.addRange(range);
        msgState.composerSelection = range.cloneRange();
        editor.closest('.msg-input-box')?.classList.add('has-inline-image');
      };
      const setMsgMobileChatOpen = (open) => {
        const shell = $('msg-shell');
        const back = $('msg-mobile-back');
        if (back && !open && document.activeElement === back) back.blur();
        if (shell) shell.classList.toggle('msg-mobile-chat-open', Boolean(open));
        document.body.classList.toggle('msg-mobile-chat-view', Boolean(open));
        if (back) {
          back.hidden = !open;
          back.tabIndex = open ? 0 : -1;
          back.removeAttribute('aria-hidden');
        }
      };
      const msgLayout = {listWidth:340, composerHeight:132, listCollapsed:false, composerCollapsed:false, loaded:false, persisted:false, saveTimer:null};
      const normalizeMsgLayout = (value = {}) => {
        const data = value && typeof value === 'object' ? value : {};
        const width = Number.parseInt(data.list_width ?? data.listWidth, 10);
        const height = Number.parseInt(data.composer_height ?? data.composerHeight, 10);
        const bool = (item, fallback = false) => {
          if (typeof item === 'boolean') return item;
          if (['1','true','yes','on','开启'].includes(String(item ?? '').trim().toLowerCase())) return true;
          if (['0','false','no','off','关闭'].includes(String(item ?? '').trim().toLowerCase())) return false;
          return fallback;
        };
        return {
          listWidth:Number.isFinite(width) ? Math.max(220, Math.min(680, width)) : 340,
          composerHeight:Number.isFinite(height) ? Math.max(96, Math.min(420, height)) : 132,
          listCollapsed:bool(data.list_collapsed ?? data.listCollapsed),
          composerCollapsed:bool(data.composer_collapsed ?? data.composerCollapsed),
        };
      };
      const applyMsgLayout = (value = {}, persist = false) => {
        const next = normalizeMsgLayout(value);
        Object.assign(msgLayout, next);
        const shell = $('msg-shell');
        if (shell) {
          shell.style.setProperty('--msg-list-width', `${next.listWidth}px`);
          shell.classList.toggle('msg-list-collapsed', next.listCollapsed);
          shell.classList.toggle('msg-composer-collapsed', next.composerCollapsed);
        }
        const composer = $('msg-composer');
        if (composer) composer.style.height = next.composerCollapsed ? '38px' : `${next.composerHeight}px`;
        const listToggle = $('msg-list-collapse');
        if (listToggle) {
          listToggle.textContent = next.listCollapsed ? '›' : '‹';
          listToggle.setAttribute('aria-expanded', String(!next.listCollapsed));
          listToggle.setAttribute('aria-label', next.listCollapsed ? '展开会话列表' : '收起会话列表');
          listToggle.title = next.listCollapsed ? '展开会话列表' : '收起会话列表';
        }
        const composerToggle = $('msg-composer-toggle');
        if (composerToggle) {
          composerToggle.textContent = next.composerCollapsed ? '⌃' : '⌄';
          composerToggle.setAttribute('aria-expanded', String(!next.composerCollapsed));
          composerToggle.setAttribute('aria-label', next.composerCollapsed ? '展开编辑区' : '收起编辑区');
          composerToggle.title = next.composerCollapsed ? '展开编辑区' : '收起编辑区';
        }
        if (persist) queueMsgLayoutSave();
      };
      const queueMsgLayoutSave = () => {
        if (!msgLayout.loaded) return;
        if (msgLayout.saveTimer) clearTimeout(msgLayout.saveTimer);
        msgLayout.saveTimer = setTimeout(async () => {
          msgLayout.saveTimer = null;
          try {
            const data = await api('message/layout', {method:'POST', body:JSON.stringify({
              list_width:msgLayout.listWidth,
              composer_height:msgLayout.composerHeight,
              list_collapsed:msgLayout.listCollapsed,
              composer_collapsed:msgLayout.composerCollapsed,
            })});
            msgLayout.persisted = Boolean(data.persisted);
            if (data.layout) applyMsgLayout(data.layout, false);
          } catch (error) {
            if (error.status !== 409 && error.status !== 401) toast('消息布局保存失败');
          }
        }, 280);
      };
      const loadMsgLayout = async () => {
        applyMsgLayout();
        try {
          const data = await api('message/layout');
          msgLayout.persisted = Boolean(data.persisted);
          applyMsgLayout(data.layout || {});
        } catch (_) {}
        msgLayout.loaded = true;
      };
      const bindMsgLayoutControls = () => {
        const shell = $('msg-shell');
        const listResizer = $('msg-list-resizer');
        const composerResizer = $('msg-composer-resizer');
        const listToggle = $('msg-list-collapse');
        const composerToggle = $('msg-composer-toggle');
        if (!shell) return;
        listToggle?.addEventListener('click', () => { msgLayout.listCollapsed = !msgLayout.listCollapsed; applyMsgLayout(msgLayout, true); });
        composerToggle?.addEventListener('click', () => { msgLayout.composerCollapsed = !msgLayout.composerCollapsed; applyMsgLayout(msgLayout, true); });
        const finishPointer = (event, move, end) => {
          event.preventDefault();
          event.stopPropagation();
          const pointerId = event.pointerId;
          const target = event.currentTarget;
          try { target?.setPointerCapture?.(pointerId); } catch (_) {}
          let active = true;
          let pendingEvent = null;
          let frame = 0;
          const flush = () => {
            frame = 0;
            if (!active || !pendingEvent) return;
            const nextEvent = pendingEvent;
            pendingEvent = null;
            move(nextEvent);
          };
          const onMove = (nextEvent) => {
            if (!active || nextEvent.pointerId !== pointerId) return;
            nextEvent.preventDefault();
            pendingEvent = nextEvent;
            if (!frame) frame = window.requestAnimationFrame(flush);
          };
          const onEnd = (endEvent) => {
            if (!active || (endEvent.pointerId != null && endEvent.pointerId !== pointerId)) return;
            active = false;
            window.removeEventListener('pointermove', onMove);
            window.removeEventListener('pointerup', onEnd);
            window.removeEventListener('pointercancel', onEnd);
            if (frame) window.cancelAnimationFrame(frame);
            frame = 0;
            if (pendingEvent) move(pendingEvent);
            pendingEvent = null;
            try { target?.releasePointerCapture?.(pointerId); } catch (_) {}
            document.body.classList.remove('msg-resizing');
            end(endEvent);
          };
          window.addEventListener('pointermove', onMove, {passive:false});
          window.addEventListener('pointerup', onEnd);
          window.addEventListener('pointercancel', onEnd);
          document.body.classList.add('msg-resizing');
        };
        listResizer?.addEventListener('pointerdown', (event) => {
          if (window.matchMedia?.('(max-width: 900px)').matches) return;
          const left = shell.getBoundingClientRect().left;
          finishPointer(event, (nextEvent) => {
            applyMsgLayout({...msgLayout, listWidth:nextEvent.clientX - left}, false);
          }, () => queueMsgLayoutSave());
        });
        composerResizer?.addEventListener('pointerdown', (event) => {
          const bottom = shell.getBoundingClientRect().bottom;
          finishPointer(event, (nextEvent) => {
            applyMsgLayout({...msgLayout, composerHeight:bottom - nextEvent.clientY, composerCollapsed:false}, false);
          }, () => queueMsgLayoutSave());
        });
      };
      const mentionIdPattern = /^[A-Za-z0-9_-]{5,128}$/;
      const mergeMsgProfiles = (profiles, messages = []) => {
        const merged = {};
        Object.entries(profiles || {}).forEach(([id, profile]) => {
          if (profile && typeof profile === 'object') merged[String(id)] = {...profile};
        });
        (messages || []).forEach((message) => {
          const id = String(message?.user_id || '').trim();
          const nickname = String(message?.nickname || '').trim();
          const avatar = String(message?.avatar || message?.avatar_url || '').trim();
          if (!id || (!nickname && !avatar) || (nickname === '未知用户' && !avatar) || (nickname === '未知' && !avatar) || !mentionIdPattern.test(id)) return;
          merged[id] = {...(merged[id] || {}), ...(nickname && nickname !== '未知用户' && nickname !== '未知' ? {nickname} : {}), ...(avatar ? {avatar} : {})};
        });
        return merged;
      };
      const cacheMsgHistory = (key, data) => {
        if (!key || !data) return;
        msgState.historyCache.delete(key);
        msgState.historyCache.set(key, data);
         while (msgState.historyCache.size > 6) {
          const oldest = msgState.historyCache.keys().next().value;
          if (oldest === undefined) break;
          msgState.historyCache.delete(oldest);
        }
      };
      const resolveMentionName = (openid, profiles = msgState.profiles) => {
        const id = String(openid || '').trim();
        const nickname = String(profiles?.[id]?.nickname || profiles?.[id]?.username || '').trim();
        return nickname && nickname !== id ? nickname : (id ? `${id.slice(0, 8)}…` : '用户');
      };
      const replaceMsgMentions = (value, profiles = msgState.profiles) => String(value || '').replace(/<@!?([A-Za-z0-9_-]{5,128})>/g, (_, openid) => `@${resolveMentionName(openid, profiles)}`);
      const decodeMsgToken = (value) => {
        const raw = String(value ?? '');
        if (!raw) return '';
        try { return decodeURIComponent(raw.replace(/\+/g, ' ')); } catch (_) { return raw; }
      };
      const msgTagAttribute = (attributes, key) => {
        const match = String(attributes || '').match(new RegExp(`(?:^|\\s)${key}\\s*=\\s*["']([^"']*)["']`, 'i'));
        return match ? match[1] : '';
      };
      const renderMsgMarkup = (value, profiles = msgState.profiles) => {
        const commandTokens = [];
        const commandToken = (kind, command, label) => {
          const index = commandTokens.push({kind, command, label}) - 1;
          return `\u0000MANTOU_CMD_${index}\u0000`;
        };
        let source = replaceMsgMentions(value, profiles);
        source = source.replace(/<qqbot-cmd-(input|enter)\b([^>]*)\/?\s*>/gi, (_, kind, attributes) => {
          const command = decodeMsgToken(msgTagAttribute(attributes, 'text'));
          if (!command) return '';
          const label = decodeMsgToken(msgTagAttribute(attributes, 'show')) || command;
          return commandToken(kind, command, label);
        });
        const renderInlineCommand = (target, label = '') => {
          try {
            const url = new URL(target);
            if (url.protocol.toLowerCase() !== 'mqqapi:' || url.hostname.toLowerCase() !== 'aio' || url.pathname.toLowerCase() !== '/inlinecmd') return label;
            const command = decodeMsgToken(url.searchParams.get('command') || '');
            return command ? commandToken('inlinecmd', command, label || command) : label;
          } catch (_) { return label; }
        };
        source = source.replace(/\[([^\]\n]+)\]\((mqqapi:\/\/aio\/inlinecmd\?[^)\s]+)\)/gi, (_, label, target) => renderInlineCommand(target, label));
        source = source.replace(/(\[[^\]\n]+\]\s*[^\]\n]+)\]\((mqqapi:\/\/aio\/inlinecmd\?[^)\s]+)\)/gi, (_, label, target) => renderInlineCommand(target, label));
        source = source.replace(/mqqapi:\/\/aio\/inlinecmd\?([^\s<>)]*)/gi, (whole, query) => renderInlineCommand(`mqqapi://aio/inlinecmd?${query}`));
        source = source.replace(/<qqbot-at-user\b([^>]*)\/?\s*>/gi, (_, attributes) => {
          const id = decodeMsgToken(msgTagAttribute(attributes, 'id'));
          return id ? `@${resolveMentionName(id, profiles)}` : '';
        });
        source = source.replace(/<qqbot-at-everyone\s*\/?\s*>/gi, '@全体成员');
        let html = esc(source);
        html = html.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/gi, '<a class="msg-inline-link" href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        html = html.replace(/`([^`\n]+)`/g, '<code class="msg-inline-code">$1</code>');
        html = html.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__([^_\n]+)__/g, '<strong>$1</strong>');
        html = html.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,!，。！？]|$)/g, '$1<em>$2</em>');
        html = html.replace(/\n/g, '<br>');
        return html.replace(/\u0000MANTOU_CMD_(\d+)\u0000/g, (_, index) => {
          const item = commandTokens[Number(index)];
          if (!item) return '';
          return `<button type="button" class="msg-command-chip" data-msg-command="${esc(item.command)}" data-msg-command-kind="${esc(item.kind)}" aria-label="${esc(item.label)}">${esc(item.label)}</button>`;
        });
      };
      const plainMsgPreview = (value, profiles = msgState.profiles) => {
        let text = replaceMsgMentions(value, profiles);
        text = text.replace(/\[([^\]\n]+)\]\(mqqapi:\/\/aio\/inlinecmd\?[^)\s]+\)/gi, '$1');
        text = text.replace(/(\[[^\]\n]+\]\s*[^\]\n]+)\]\(mqqapi:\/\/aio\/inlinecmd\?[^)\s]+\)/gi, '$1');
        text = text.replace(/mqqapi:\/\/aio\/inlinecmd\?[^\s<>)]*/gi, '');
        text = text.replace(/<qqbot-cmd-(?:input|enter)\b([^>]*)\/?\s*>/gi, (_, attributes) => decodeMsgToken(msgTagAttribute(attributes, 'show')) || decodeMsgToken(msgTagAttribute(attributes, 'text')));
        text = text.replace(/<qqbot-at-user\b([^>]*)\/?\s*>/gi, (_, attributes) => {
          const id = decodeMsgToken(msgTagAttribute(attributes, 'id'));
          return id ? `@${resolveMentionName(id, profiles)}` : '';
        }).replace(/<qqbot-at-everyone\s*\/?\s*>/gi, '@全体成员');
        return text.replace(/[*_`]/g, '').replace(/\s+/g, ' ').trim();
      };
      const msgComposerTabs = [['text','文本'],['markdown','Markdown'],['media','媒体'],['ark','ARK模板'],['card','图文卡片']];
      const msgFilterLabels = { all:'全量', remark:'备注', group:'群聊', user:'私聊' };
      const avatarUrl = (openid, type, appid) => {
        const id = String(openid || '').trim();
        if (!id) return '';
        if (type === 'group') { const qq = window.msgGroupQQ?.[id] || ''; return /^\d{5,12}$/.test(String(qq)) ? `https://p.qlogo.cn/gh/${qq}/${qq}/100/` : ''; }
        const aid = appid || window.msgAppid || '';
        // QQ 官方群成员使用 AppID 作用域 OpenID；腾讯官方 qlogo
        // 接口接受该 OpenID，不能先按 QQ 号数字格式过滤。
        return aid ? `https://q.qlogo.cn/qqapp/${encodeURIComponent(aid)}/${encodeURIComponent(id)}/0` : '';
      };
      const avatarImg = (url, letter) => `<img src="${esc(url)}" alt="" loading="lazy" decoding="async" fetchpriority="low" referrerpolicy="no-referrer" onerror="this.closest('.msg-chat-avatar, .msg-avatar').classList.add('avatar-fallback'); this.remove();">`;
      const avatarHtml = (url, letter) => {
        if (!url) return esc(String(letter || '?').slice(0, 1));
        return `<span class="avatar-letter">${esc(String(letter || '?').slice(0, 1))}</span>` + avatarImg(url, letter);
      };
      const applyBotProfile = (profile = {}) => {
        const data = profile && typeof profile === 'object' ? profile : {};
        const name = String(data.username || data.name || '').trim() || '馒头助手';
        const avatar = safeMediaUrl(String(data.avatar || data.avatar_url || '').trim());
        const id = String(data.id || '').trim();
        const previousProfile = window.msgBotProfile;
        const hasRealProfile = Boolean(id || avatar || (name && name !== '馒头助手'));
        const profileChanged = previousProfile
          ? (String(previousProfile.id || '') !== id
            || String(previousProfile.username || '') !== name
            || String(previousProfile.avatar || '') !== avatar)
          : hasRealProfile;
        window.msgBotProfile = {id, username:name, avatar};
        document.querySelectorAll('[data-bot-name]').forEach((node) => { node.textContent = name; });
        document.querySelectorAll('[data-bot-id]').forEach((node) => { node.textContent = id || '由适配器提供'; });
        document.querySelectorAll('[data-bot-avatar]').forEach((node) => {
          node.classList.toggle('has-image', Boolean(avatar));
          if (!avatar) { node.innerHTML = '<span class="avatar-face">•ᴗ•</span>'; return; }
          node.innerHTML = `<img class="bot-avatar-image" src="${esc(avatar)}" alt="${esc(name)}" loading="lazy" referrerpolicy="no-referrer">`;
          node.querySelector('img')?.addEventListener('error', () => {
            node.classList.remove('has-image');
            node.innerHTML = '<span class="avatar-face">•ᴗ•</span>';
          }, {once:true});
        });
        const hasMessageData = msgState.historyData
          || (Array.isArray(msgState.messages) && msgState.messages.length)
          || Number(msgState.optimisticSends?.size || 0) > 0;
        if (profileChanged && msgState.chatId && hasMessageData && typeof renderMsgMessages === 'function') {
          const body = $('msg-body');
          renderMsgMessages(
            {...msgState.historyData, messages:msgState.messages},
            {previousTop:body?.scrollTop || 0, previousHeight:body?.scrollHeight || 0},
          );
        }
      };
      const loadBotProfile = async () => {
        if (window.msgBotProfileLoaded) return;
        window.msgBotProfileLoaded = true;
        try {
          const data = await api('bot-profile');
          applyBotProfile(data.profile || {});
        } catch (_) {
          applyBotProfile({});
        }
      };
      const msgTypeName = (m) => {
        const c = String(m.content || '');
        if (c.startsWith('[媒体]')) return '媒体';
        if (c.startsWith('[ARK卡片]')) return 'ARK';
        if (c.startsWith('[图文卡片]')) return '卡片';
        return '文本';
      };
      const fmtChatTime = (ts) => {
        const s = String(ts || '').trim();
        if (!s) return '';
        const d = new Date(s.replace('T', ' ').replace(/-/g, '/'));
        if (isNaN(d.getTime())) return s.slice(5, 16);
        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        const sameDay = d.toDateString() === now.toDateString();
        const yest = new Date(now); yest.setDate(now.getDate() - 1);
        if (sameDay) return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
        if (d.toDateString() === yest.toDateString()) return '昨天';
        if (d.getFullYear() === now.getFullYear()) return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
      };
      const msgChatMatchesView = (chat) => {
        const type = String(chat.chat_type || 'group');
        if (msgState.filter === 'group' && type !== 'group') return false;
        if (msgState.filter === 'user' && type !== 'user') return false;
        if (msgState.filter === 'remark' && !chat.remark) return false;
        const keyword = String(msgState.search || '').trim().toLowerCase();
        if (!keyword) return true;
        return [chat.nickname, chat.remark, chat.chat_id].some((value) => String(value || '').toLowerCase().includes(keyword));
      };
      const msgChatIsRemoved = (chat) => String(chat?.chat_type || 'group') === 'group'
        && (String(chat?.membership_status || '').toLowerCase() === 'removed' || chat?.in_group === false);
      const mergeMsgRealtimeChats = (serverChats) => {
        const byId = new Map((serverChats || []).map((chat) => [String(chat.chat_id || ''), {...chat}]));
        const now = Math.floor(Date.now() / 1000);
        msgState.realtimeChats.forEach((overlay, chatId) => {
          const current = byId.get(chatId);
          if (!current) { if (msgChatMatchesView(overlay)) byId.set(chatId, {...overlay}); return; }
          const serverTs = Number(current.last_ts || 0);
          const eventTs = Number(overlay.last_ts || 0);
          if (serverTs > eventTs) { msgState.realtimeChats.delete(chatId); return; }
          const adminKnown = msgState.adminByChat.has(chatId)
            ? Boolean(msgState.adminByChat.get(chatId))
            : Boolean(current.is_admin || overlay.is_admin);
          byId.set(chatId, {
            ...current,
            ...overlay,
            nickname:current.nickname || overlay.nickname,
            remark:Object.prototype.hasOwnProperty.call(current, 'remark') ? String(current.remark || '') : String(overlay.remark || ''),
            group_qq:Object.prototype.hasOwnProperty.call(current, 'group_qq') ? String(current.group_qq || '') : String(overlay.group_qq || ''),
            pinned:Object.prototype.hasOwnProperty.call(current, 'pinned') ? Boolean(current.pinned) : Boolean(overlay.pinned),
          msg_count:Math.max(Number(current.msg_count || 0), Number(overlay.msg_count || 0)),
          is_admin:adminKnown,
          });
        });
        // 服务器刷新失败时临时会话不会被确认，定期淘汰过期覆盖项，
        // 避免长时间打开控制台后 Map 无限增长。
        if (msgState.realtimeChats.size > 256) {
          msgState.realtimeChats.forEach((overlay, chatId) => {
            if (msgState.realtimeChats.size <= 256) return;
            if (chatId !== String(msgState.chatId || '') && now - Number(overlay?.last_ts || 0) > 600) {
              msgState.realtimeChats.delete(chatId);
            }
          });
        }
        return [...byId.values()].filter(msgChatMatchesView).sort((left, right) =>
          Number(msgChatIsRemoved(left)) - Number(msgChatIsRemoved(right)) ||
          Number(Boolean(right.pinned)) - Number(Boolean(left.pinned)) ||
          Number(right.last_ts || 0) - Number(left.last_ts || 0)
        );
      };
      const clearMsgChatUnread = (chatId) => {
        const id = String(chatId || '');
        if (!id) return false;
        let changed = false;
        msgState.chats = msgState.chats.map((chat) => {
          if (String(chat.chat_id || '') !== id || Number(chat.unread || 0) <= 0) return chat;
          changed = true;
          return {...chat, unread:0};
        });
        const existing = msgState.realtimeChats.get(id) || msgState.chats.find((chat) => String(chat.chat_id || '') === id);
        if (existing) msgState.realtimeChats.set(id, {...existing, unread:0});
        document.querySelectorAll('[data-msg-chat]').forEach((node) => {
          if (String(node.dataset.msgChat || '') === id) node.querySelector('.msg-chat-badge')?.remove();
        });
        return changed;
      };
      const markMsgRead = async (chatId = msgState.chatId, force = false) => {
        const id = String(chatId || '');
        if (!id) return;
        const changed = clearMsgChatUnread(id);
        if (!force && !changed) return;
        if (msgState.readInFlight.has(id)) return;
        msgState.readInFlight.add(id);
        try { await api('message/read', {method:'POST', body:JSON.stringify({chat_id:id})}); }
        catch (_) {}
        finally { msgState.readInFlight.delete(id); }
      };
      const getLocalAdminGroups = () => {
        try { return new Set(JSON.parse(localStorage.getItem('mantou_bot_admin_groups') || '[]')); }
        catch (_) { return new Set(); }
      };
      const saveLocalAdminGroups = (set) => {
        try { localStorage.setItem('mantou_bot_admin_groups', JSON.stringify(Array.from(set))); }
        catch (_) {}
      };
      const msgRoleRetryMs = 5 * 60 * 1000;
      const msgMembershipRefreshMs = 30 * 60 * 1000;
      let autoScanAdminRunning = false;
      let autoScanAdminTimer = null;
      const scheduleAutoScanAdminGroups = (delay = 2500) => {
        if (autoScanAdminTimer) clearTimeout(autoScanAdminTimer);
        autoScanAdminTimer = setTimeout(() => {
          autoScanAdminTimer = null;
          void autoScanAdminGroups();
        }, delay);
      };
      const autoScanAdminGroups = async () => {
        if (autoScanAdminRunning) return;
        autoScanAdminRunning = true;
        try {
          const localAdmins = getLocalAdminGroups();
          const now = Date.now();
          const groupsToScan = (msgState.chats || []).filter((c) => {
            const id = String(c.chat_id || '');
            const failedAt = Number(msgState.adminScanFailures.get(id) || 0);
            const retryDue = failedAt > 0 && now - failedAt >= msgRoleRetryMs;
            const checkedAt = Number(msgState.adminCheckedAt.get(id) || Number(c.membership_checked_at || 0) * 1000);
            const membershipDue = !checkedAt || now - checkedAt >= msgMembershipRefreshMs;
            const scanAllowed = failedAt > 0
              ? retryDue
              : (membershipDue || !msgState.adminByChat.has(id) || !msgState.adminScanAttempted.has(id));
            return c.chat_type === 'group' && id
              && c.membership_status !== 'removed' && c.in_group !== false
              && scanAllowed;
          }).slice(0, 1);
          let membershipChanged = false;
          for (const group of groupsToScan) {
            const chatId = String(group.chat_id || '');
            msgState.adminScanAttempted.add(chatId);
            msgState.adminCheckedAt.set(chatId, Date.now());
            const scanRoleToken = Number(msgState.adminRequestToken || 0);
            try {
              const res = await api('message/group-roles', {method:'POST', body:JSON.stringify({chat_id:chatId})});
              const removed = res?.membership_status === 'removed' || res?.bot_in_group === false;
              if (removed) {
                group.membership_status = 'removed';
                group.in_group = false;
                group.membership_checked_at = Number(res?.membership_checked_at || Math.floor(Date.now() / 1000));
                membershipChanged = true;
                if (msgState.chatId === chatId && msgState.chatType === 'group') {
                  msgState.chatRemoved = true;
                  $('msg-composer').hidden = true;
                  updateMsgHead({chat_name:group.nickname || chatId, group_info:{membership_status:'removed'}});
                }
                msgState.adminByChat.set(chatId, false);
                localAdmins.delete(chatId);
                await new Promise((r) => setTimeout(r, 1000));
                continue;
              }
              const role = String(res?.bot_role || '').trim().toLowerCase();
              if (!['owner', 'admin', 'member'].includes(role)) throw new Error('群角色结果不完整');
              if (group.membership_status !== 'active' || group.in_group === false) membershipChanged = true;
              group.membership_status = 'active';
              group.in_group = true;
              group.membership_checked_at = Number(res?.membership_checked_at || Math.floor(Date.now() / 1000));
              const isAdmin = Boolean(res && res.bot_is_admin);
              msgState.adminByChat.set(chatId, isAdmin);
              msgState.adminScanFailures.delete(chatId);
              group.is_admin = isAdmin;
              if (isAdmin) localAdmins.add(chatId);
              else localAdmins.delete(chatId);
              saveLocalAdminGroups(localAdmins);
              const btn = document.querySelector(`[data-msg-chat="${CSS.escape(chatId)}"] .msg-chat-top strong`);
              if (btn) btn.classList.toggle('admin', isAdmin);
              if (msgState.chatId === chatId && msgState.chatType === 'group' && scanRoleToken === Number(msgState.adminRequestToken || 0)) {
                msgState.botIsAdmin = isAdmin;
                updateMsgAdminTag();
              }
            } catch (_) {
              // 接口短暂失败时保留旧颜色，冷却后允许再次尝试，避免永久停留在黑色。
              msgState.adminScanFailures.set(chatId, Date.now());
            }
            await new Promise((r) => setTimeout(r, 1000));
          }
          if (membershipChanged) renderMsgChats({chats:msgState.chats});
          if (groupsToScan.length >= 1) scheduleAutoScanAdminGroups(10000);
        } finally {
          autoScanAdminRunning = false;
        }
      };
      const renderMsgChats = (data) => {
        const node = $('msg-chats');
        if (!node) return;
        if (msgState.chatListScrollActive) {
          msgState.chatListPendingData = data;
          return;
        }
        const forceListTop = !msgState.chatListServerLoaded || msgState.chatListTopPending || !msgState.chatListRendered;
        const previousTop = node.scrollTop;
        const previousHeight = node.scrollHeight;
        const previousClientHeight = node.clientHeight;
        const keepListBottom = !forceListTop && previousHeight - previousTop - previousClientHeight <= 24;
        const restoreListScroll = () => {
          if (forceListTop) {
            node.scrollTop = 0;
            return;
          }
          const maxTop = Math.max(0, node.scrollHeight - node.clientHeight);
          node.scrollTop = keepListBottom ? maxTop : Math.min(previousTop, maxTop);
        };
        const settleListScroll = () => {
          restoreListScroll();
          if (typeof requestAnimationFrame === 'function') {
            requestAnimationFrame(() => {
              restoreListScroll();
              if (forceListTop && msgState.chatListServerLoaded) {
                requestAnimationFrame(() => {
                  restoreListScroll();
                  msgState.chatListTopPending = false;
                });
              }
            });
          } else if (forceListTop && msgState.chatListServerLoaded) {
            setTimeout(() => {
              restoreListScroll();
              msgState.chatListTopPending = false;
            }, 0);
          }
        };
        const chats = mergeMsgRealtimeChats(data.chats || []);
        const localAdmins = getLocalAdminGroups();
        chats.forEach((c) => {
          if (c.chat_type === 'group') {
            const id = String(c.chat_id || '');
            if (msgState.adminByChat.has(id)) {
              c.is_admin = Boolean(msgState.adminByChat.get(id));
            } else if (c.is_admin) {
              localAdmins.add(id);
              msgState.adminByChat.set(id, true);
            } else if (localAdmins.has(id)) {
              c.is_admin = true;
              msgState.adminByChat.set(id, true);
            }
          }
        });
        saveLocalAdminGroups(localAdmins);
        msgState.chats = chats;
        const knownChatIds = new Set(chats.map((chat) => String(chat.chat_id || '')).filter(Boolean));
        [msgState.adminByChat, msgState.adminScanAttempted, msgState.adminScanFailures, msgState.adminCheckedAt]
          .forEach((map) => map.forEach((_value, key) => { if (!knownChatIds.has(String(key))) map.delete(key); }));
        window.msgGroupQQ = {}; (chats||[]).forEach((chat) => { if (chat.group_qq) window.msgGroupQQ[chat.chat_id] = chat.group_qq; });
        const chatRenderSignature = chats.map((chat) => [
          chat.chat_id,
          chat.chat_type,
          chat.nickname || chat.remark || '',
          chat.last_content || '',
          chat.last_ts,
          chat.unread,
          chat.msg_count,
          chat.pinned ? 1 : 0,
          chat.is_admin ? 1 : 0,
          chat.membership_status,
          (chat.group_avatar || (chat.chat_type === 'group' ? '' : (chat.avatar || chat.avatar_url))) ? 1 : 0,
        ].join(':')).join('|');
        if (msgState.chatRenderSignature === chatRenderSignature) {
          scheduleAutoScanAdminGroups(10000);
          return;
        }
        msgState.chatRenderSignature = chatRenderSignature;
        msgState.chatListRendered = true;
        if (!chats.length) { node.innerHTML = '<div class="msg-empty">暂无消息会话，机器人收到消息后会出现在这里</div>'; settleListScroll(); return; }
        let removedSectionShown = false;
        node.innerHTML = chats.map((chat) => {
          const avatarSource = chat.chat_type === 'group'
            ? (chat.group_avatar || chat.group_avatar_url || '')
            : (chat.avatar || chat.avatar_url || '');
          const av = safeMediaUrl(String(avatarSource).trim())
            || avatarUrl(chat.chat_id, chat.chat_type, chat.appid);
          if (chat.appid) window.msgAppid = chat.appid;
          const typeTag = chat.chat_type === 'user' ? '<span class="msg-chat-type">私聊</span>' : '<span class="msg-chat-type">群聊</span>';
          const viewing = msgState.chatId === chat.chat_id;
          const removed = msgChatIsRemoved(chat);
          const removedSection = removed && !removedSectionShown
            ? '<div class="msg-chat-divider" role="separator">已移除群聊</div>'
            : '';
          if (removed) removedSectionShown = true;
          const viewingAtBottom = viewing && !$('page-messages')?.hidden && msgState.pendingNewMessages === 0 && msgBodyNearBottom($('msg-body'));
          const unread = viewingAtBottom ? 0 : Number(chat.unread || 0);
          if (viewingAtBottom && Number(chat.unread || 0) > 0) queueMicrotask(() => markMsgRead(chat.chat_id));
          const preview = removed ? '你已被移除群聊' : (plainMsgPreview(String(chat.last_content || '（无文本内容）')) || '（无文本内容）');
          return `${removedSection}<button type="button" class="msg-chat ${chat.pinned ? 'pinned' : ''} ${viewing ? 'active' : ''}${removed ? ' removed' : ''}" data-msg-chat="${esc(chat.chat_id)}" data-msg-type="${esc(chat.chat_type)}" data-msg-pinned="${chat.pinned ? '1' : '0'}" data-msg-removed="${removed ? '1' : '0'}" title="${removed ? '你已被移除群聊' : (chat.pinned ? '取消置顶' : '置顶')}">
            <span class="msg-chat-avatar">${avatarHtml(av, chat.nickname || '群')}</span>
            <span class="msg-chat-main"><span class="msg-chat-top"><strong class="${chat.is_admin ? 'admin' : ''}">${esc(chat.nickname || chat.chat_id)}</strong>${typeTag}<small>${esc(fmtChatTime(chat.last_time))}</small></span>
             <span class="msg-chat-sub-row"><span class="msg-chat-sub">${esc(preview)}</span>${unread > 0 ? `<span class="msg-chat-badge">${unread > 99 ? '99+' : unread}</span>` : ''}</span>
            <span class="msg-chat-meta">${chat.chat_type === 'group' ? `群消息 ${chat.msg_count} 条` : `私聊消息 ${chat.msg_count} 条`}${chat.remark ? ' · 已备注' : ''}</span></span>
          </button>`;
        }).join('');
        settleListScroll();
        scheduleAutoScanAdminGroups();
        if (node.dataset.msgDelegated !== '1') {
          node.dataset.msgDelegated = '1';
          node.addEventListener('contextmenu', (e) => {
            const el = e.target.closest?.('[data-msg-chat]');
            if (!el || !node.contains(el)) return;
            e.preventDefault();
            e.stopPropagation();
            const chatId = el.dataset.msgChat; const chatType = el.dataset.msgType; const pinned = el.dataset.msgPinned === '1';
            const items = [];
            items.push({label: pinned ? '取消置顶' : '置顶', action: async () => {
              try { const result = await api('message/pin', {method:'POST', body:JSON.stringify({chat_id:chatId, pinned:!pinned})}); toast(result.pinned ? '已置顶' : '已取消置顶'); await loadMsgChats(true); }
              catch (error) { toast(error.message || '操作失败'); }
            }});
            if (chatType === 'group') items.push({label:'刷新群信息', action:() => { api('message/group-info/refresh', {method:'POST', body:JSON.stringify({chat_id:chatId})}).then(() => { toast('已刷新'); loadMsgChats(true); }).catch((error) => toast(error.message || '刷新失败')); }});
            if (items.length) showMsgCtx(e.clientX, e.clientY, items);
          });
          node.addEventListener('click', (e) => {
            const el = e.target.closest?.('[data-msg-chat]');
            if (!el || !node.contains(el)) return;
            if (msgState.multi) exitMultiMode();
            const chatId = String(el.dataset.msgChat || '');
            const chatType = String(el.dataset.msgType || 'group');
            const chat = msgState.chats.find((item) => String(item.chat_id || '') === chatId) || {
              chat_id: chatId,
              chat_type: chatType,
              nickname: chatId,
            };
            selectMsgChat(chat, el);
            scheduleMsgHistoryLoad(chatId);
            markMsgRead(chatId, true);
          });
        }
      };
      const selectMsgChat = (chat, selectedNode = null) => {
        const chatId = String(chat?.chat_id || '').trim();
        if (!chatId) return;
        const chatType = String(chat?.chat_type || 'group');
        setMsgMobileChatOpen(true);
        msgState.chatRemoved = chatType === 'group' && (chat?.membership_status === 'removed' || chat?.in_group === false);
        const localAdmins = getLocalAdminGroups();
        const cachedAdmin = msgState.adminByChat.has(chatId)
          ? Boolean(msgState.adminByChat.get(chatId))
          : Boolean(chat?.is_admin || localAdmins.has(chatId));
        if (cachedAdmin && !msgState.adminByChat.has(chatId)) msgState.adminByChat.set(chatId, true);
        const sameChat = msgState.chatId === chatId && msgState.chatType === chatType;
        // 每次点选会话都重新执行首屏定位，同一会话也不能沿用旧滚动位置。
        msgState.initialScrollChatId = chatId;
        if (!sameChat) {
          cancelMsgRealtimeMessageRender();
          msgState.muteRequestToken = Number(msgState.muteRequestToken || 0) + 1;
          msgState.mutes = new Map();
          msgState.muteRequestAt = 0;
        }
        // 切换会话时立即失效旧的管理员请求，避免旧群响应把当前群标成红色。
        msgState.adminRequestToken = Number(msgState.adminRequestToken || 0) + 1;
        // 选中会话时立刻使旧历史请求失效，避免旧响应在下一帧前覆盖新会话。
        // 最新消息与“加载更早消息”使用独立请求，轮询不能取消用户的上翻页。
        if (msgState.historyAbort) {
          msgState.historyAbort.abort();
          msgState.historyAbort = null;
        }
        if (msgState.historyOlderAbort) {
          msgState.historyOlderAbort.abort();
          msgState.historyOlderAbort = null;
        }
        msgState.historyRequest = Number(msgState.historyRequest || 0) + 1;
        msgState.historyOlderRequest = Number(msgState.historyOlderRequest || 0) + 1;
        msgState.historyOlderLoading = false;
        msgState.chatId = chatId;
        msgState.chatType = chatType;
        msgState.botIsAdmin = cachedAdmin;
        resetMsgAdSwitch();
        msgState.profiles = {};
        msgState.historyData = null;
        msgState.messages = [];
        msgState.renderedChatId = '';
        clearMsgNewMessages();
        // 先更新右侧会话头和蓝色消息区域的加载占位，历史请求异步完成后再替换内容。
        updateMsgHead({
          chat_name: chat.remark || chat.group_name || chat.nickname || chatId,
          group_info: {member_num: chat.member_num || chat.group_member_num || 0},
        });
        $('msg-refresh-info').hidden = msgState.chatType !== 'group';
        $('msg-remark').hidden = msgState.chatType !== 'group';
        updateMsgAdSwitch();
        $('msg-composer').hidden = msgState.chatRemoved;
        const body = $('msg-body');
        if (body) {
          // 新会话开始前终止旧会话的定位循环，防止旧循环提前取消新会话的隐藏状态。
          cancelMsgBottomPosition(body, true);
          body.classList.remove('msg-positioning');
          body.innerHTML = '<div class="msg-loading" role="status" aria-label="正在加载消息"><span></span><span></span><span></span></div>';
          body.scrollTop = 0;
          const cachedHistory = msgState.historyCache.get(`${chatType}|${chatId}`);
          if (cachedHistory && Array.isArray(cachedHistory.messages) && cachedHistory.messages.length) {
            msgState.messages = dedupeMsgMessages(cachedHistory.messages);
            // 缓存只用于预热布局；首轮网络历史返回前不要揭示，避免先看到缓存中段再跳到底部。
            renderMsgMessages({...cachedHistory, messages:msgState.messages}, {toBottom:true});
          }
        }
        document.querySelectorAll('[data-msg-chat]').forEach((node) => {
          node.classList.toggle('active', String(node.dataset.msgChat || '') === chatId);
        });
        selectedNode?.scrollIntoView({block:'nearest'});
        if (msgState.chatType === 'group') void loadGroupAdSwitch();
      };
      const scheduleMsgHistoryLoad = (chatId) => {
        const id = String(chatId || '').trim();
        if (!id) return;
        msgState.historyScheduleToken = Number(msgState.historyScheduleToken || 0) + 1;
        const token = msgState.historyScheduleToken;
        if (msgState.historyScheduleFrame != null) {
          if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(msgState.historyScheduleFrame);
          else clearTimeout(msgState.historyScheduleFrame);
          msgState.historyScheduleFrame = null;
        }
        const run = () => {
          msgState.historyScheduleFrame = null;
          if (token !== msgState.historyScheduleToken || String(msgState.chatId || '') !== id) return;
          loadMsgHistory();
        };
        if (typeof requestAnimationFrame === 'function') msgState.historyScheduleFrame = requestAnimationFrame(run);
        else msgState.historyScheduleFrame = setTimeout(run, 0);
      };
      $('msg-lightbox-close')?.addEventListener('click', () => closeMsgLightbox());
      $('msg-lightbox')?.addEventListener('click', (e) => { if (e.target === $('msg-lightbox') || e.target === $('msg-lightbox-img')) closeMsgLightbox(); });
      document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMsgLightbox(); });
      $('msg-mobile-back')?.addEventListener('click', () => setMsgMobileChatOpen(false));
      const loadMsgChats = (force = false) => {
        const params = {filter:msgState.filter, search:msgState.search, page:1, page_size:0};
        const paramsKey = JSON.stringify(params);
        if (!force && msgState.chatListPromise && msgState.chatListKey === paramsKey) return msgState.chatListPromise;
        const requestId = Number(msgState.chatListRequest || 0) + 1;
        msgState.chatListRequest = requestId;
        if (msgState.chatListAbort) msgState.chatListAbort.abort();
        const controller = new AbortController();
        msgState.chatListAbort = controller;
        let timedOut = false;
        const timeoutId = setTimeout(() => { timedOut = true; controller.abort(); }, 18000);
        let requestPromise;
        requestPromise = (async () => {
          try {
            const data = await api('message/chats', {method:'POST', body:JSON.stringify(params), signal:controller.signal});
            // 搜索、实时刷新或置顶操作可能同时发起请求，只显示最后一次请求的结果。
            if (requestId !== msgState.chatListRequest) return data;
            if (!msgState.chatListServerLoaded) {
              msgState.chatListServerLoaded = true;
              msgState.chatListTopPending = true;
            }
            renderMsgChats(data);
            return data;
          }
          catch (error) {
            if (requestId !== msgState.chatListRequest) return;
            if (timedOut) { toast('消息会话加载超时，请稍后重试'); return; }
            if (error.name === 'AbortError') return;
            if (error.status === 401) showAuthError(error);
            else if (!msgState.chats.length) $('msg-chats').innerHTML = `<div class="msg-empty">${esc(error.message)}</div>`;
            else toast(error.message || '消息会话加载失败');
          }
          finally {
            clearTimeout(timeoutId);
            if (msgState.chatListAbort === controller) msgState.chatListAbort = null;
            if (msgState.chatListPromise === requestPromise) msgState.chatListPromise = null;
          }
        })();
        msgState.chatListKey = paramsKey;
        msgState.chatListPromise = requestPromise;
        return requestPromise;
      };
      const closeMsgEvents = () => {
        if (msgState.eventReconnect) { clearTimeout(msgState.eventReconnect); msgState.eventReconnect = null; }
        if (autoScanAdminTimer) { clearTimeout(autoScanAdminTimer); autoScanAdminTimer = null; }
        if (msgState.eventRefreshTimer) { clearTimeout(msgState.eventRefreshTimer); msgState.eventRefreshTimer = null; }
        if (msgState.chatRenderTimer) { clearTimeout(msgState.chatRenderTimer); msgState.chatRenderTimer = null; }
        if (msgState.chatListScrollTimer) { clearTimeout(msgState.chatListScrollTimer); msgState.chatListScrollTimer = null; }
        msgState.chatListScrollActive = false;
        msgState.chatListPendingData = null;
        if (msgState.realtimeMessageTimer) { clearTimeout(msgState.realtimeMessageTimer); msgState.realtimeMessageTimer = null; }
        msgState.realtimeMessageCount = 0; msgState.realtimeToBottom = false; msgState.realtimeRenderChatId = '';
        msgState.historyOlderLoading = false;
        msgState.historyScheduleToken = Number(msgState.historyScheduleToken || 0) + 1;
        if (msgState.historyScheduleFrame != null) {
          if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(msgState.historyScheduleFrame);
          else clearTimeout(msgState.historyScheduleFrame);
          msgState.historyScheduleFrame = null;
        }
        if (msgState.chatListAbort) { msgState.chatListAbort.abort(); msgState.chatListAbort = null; }
        msgState.chatListPromise = null;
        msgState.chatListKey = '';
        if (msgState.historyAbort) { msgState.historyAbort.abort(); msgState.historyAbort = null; }
        if (msgState.historyOlderAbort) { msgState.historyOlderAbort.abort(); msgState.historyOlderAbort = null; }
        const socket = msgState.eventSocket;
        msgState.eventSocket = null;
        msgState.eventTransport = '';
        if (socket) {
          // 先解除回调，避免切换页面时 close 事件再次触发降级重连。
          socket.onopen = null; socket.onmessage = null; socket.onerror = null; socket.onclose = null;
          try { socket.close(); } catch (_) {}
        }
        if (msgState.eventSource) {
          const source = msgState.eventSource;
          msgState.eventSource = null;
          source.onopen = null; source.onmessage = null; source.onerror = null;
          try { source.close(); } catch (_) {}
        }
      };
      const scheduleMsgRealtimeRefresh = () => {
        if (msgState.eventRefreshTimer) return;
        msgState.eventRefreshTimer = setTimeout(async () => {
          msgState.eventRefreshTimer = null;
          if ($('page-messages')?.hidden) return;
          await loadMsgChats();
        }, 3000);
      };
      const handleMsgRealtimeData = (raw) => {
        try {
          const envelope = typeof raw === 'string' ? JSON.parse(raw || '{}') : raw;
          if (envelope?.type === 'message') { applyMsgRealtimeEvent(envelope.data || {}); scheduleMsgRealtimeRefresh(); }
          else if (envelope?.type === 'group_status') applyMsgGroupStatus(envelope.data || {});
        } catch (_) {}
      };
      const scheduleMsgRealtimeReconnect = () => {
        if (msgState.eventReconnect || $('page-messages')?.hidden) return;
        msgState.eventReconnect = setTimeout(() => {
          msgState.eventReconnect = null;
          if (!$('page-messages')?.hidden) connectMsgEvents();
        }, 3000);
      };
      const connectMsgSse = () => {
        if (msgState.eventSource || msgState.eventSocket || !window.EventSource || $('page-messages')?.hidden) return;
        let source;
        try { source = new EventSource('/api/message/events'); }
        catch (_) { scheduleMsgRealtimeReconnect(); return; }
        msgState.eventSource = source;
        msgState.eventTransport = '';
        source.onopen = () => {
          if (msgState.eventSource === source) msgState.eventTransport = 'sse';
        };
        source.onmessage = (event) => handleMsgRealtimeData(event.data);
        source.onerror = () => {
          if (msgState.eventSource !== source) return;
          source.onopen = null; source.onmessage = null; source.onerror = null;
          try { source.close(); } catch (_) {}
          msgState.eventSource = null; msgState.eventTransport = '';
          scheduleMsgRealtimeReconnect();
        };
      };
      const connectMsgEvents = () => {
        if (msgState.eventSocket || msgState.eventSource || $('page-messages')?.hidden) return;
        if (!window.WebSocket) { connectMsgSse(); return; }
        const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        let socket;
        try { socket = new WebSocket(`${wsProtocol}//${location.host}/api/message/ws`); }
        catch (_) { connectMsgSse(); return; }
        msgState.eventSocket = socket;
        msgState.eventTransport = '';
        socket.onopen = () => { if (msgState.eventSocket === socket) msgState.eventTransport = 'websocket'; };
        socket.onmessage = (event) => handleMsgRealtimeData(event.data);
        socket.onerror = () => {
          // onclose 负责统一清理并切换 SSE，避免同时保持两条实时连接。
          try { socket.close(); } catch (_) {}
        };
        socket.onclose = () => {
          if (msgState.eventSocket !== socket) return;
          msgState.eventSocket = null; msgState.eventTransport = '';
          connectMsgSse();
          if (!msgState.eventSource) scheduleMsgRealtimeReconnect();
        };
      };
      const fmtDayLabel = (ts) => {
        const s = String(ts || '').trim();
        if (!s) return '';
        const d = new Date(s.replace('T', ' ').replace(/-/g, '/'));
        if (isNaN(d.getTime())) return s.slice(0, 10);
        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        if (d.toDateString() === now.toDateString()) return '今天';
        const yest = new Date(now); yest.setDate(now.getDate() - 1);
        if (d.toDateString() === yest.toDateString()) return '昨天';
        if (d.getFullYear() === now.getFullYear()) return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
        return s.slice(0, 10);
      };
      const fmtMsgTime = (ts) => {
        const s = String(ts || '').trim();
        if (!s) return '';
        const d = new Date(s.replace('T', ' ').replace(/-/g, '/'));
        if (isNaN(d.getTime())) return s.slice(11, 16);
        const pad = (n) => String(n).padStart(2, '0');
        return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
      };
      const updateMsgAdminTag = () => {
        const el = $('msg-admin-tag');
        const isAdmin = Boolean(msgState.chatType === 'group' && msgState.botIsAdmin);
        if (el) el.hidden = !isAdmin;
        const nameEl = $('msg-head-name');
        if (nameEl) {
          if (isAdmin) nameEl.classList.add('admin');
          else nameEl.classList.remove('admin');
        }
        const curChat = (msgState.chats || []).find((c) => String(c.chat_id || '') === String(msgState.chatId || ''));
        if (curChat) {
          curChat.is_admin = isAdmin;
          const chatBtn = document.querySelector(`[data-msg-chat="${CSS.escape(msgState.chatId)}"] .msg-chat-top strong`);
          if (chatBtn) {
            if (isAdmin) chatBtn.classList.add('admin');
            else chatBtn.classList.remove('admin');
          }
        }
      };
      const updateMsgAdSwitch = () => {
        const button = $('msg-ad-switch');
        if (!button) return;
        const visible = msgState.chatType === 'group' && Boolean(msgState.chatId) && !msgState.chatRemoved;
        button.hidden = !visible;
        if (!visible) return;
        const pending = Boolean(msgState.adLoading || msgState.adSaving);
        const enabled = Boolean(msgState.adEnabled);
        button.disabled = pending || !msgState.adEditable;
        button.textContent = pending ? '广告拦截：读取中' : (enabled ? '关闭广告' : '开启广告');
        button.title = pending
          ? '正在读取当前群的广告拦截状态'
          : (!msgState.adEditable
            ? '数据库未配置，广告开关无法保存'
            : (enabled ? '当前群广告拦截已开启，点击关闭' : '当前群广告拦截已关闭，点击开启'));
      };
      const resetMsgAdSwitch = () => {
        msgState.adChatId = String(msgState.chatId || '');
        msgState.adEnabled = false;
        msgState.adEditable = false;
        msgState.adLoading = msgState.chatType === 'group' && Boolean(msgState.chatId) && !msgState.chatRemoved;
        msgState.adSaving = false;
        updateMsgAdSwitch();
      };
      const loadGroupAdSwitch = async () => {
        const chatId = String(msgState.chatId || '').trim();
        if (msgState.chatType !== 'group' || !chatId || msgState.chatRemoved) return;
        msgState.adChatId = chatId;
        msgState.adLoading = true;
        updateMsgAdSwitch();
        try {
          const data = await api('message/group-ad', {method:'POST', body:JSON.stringify({chat_id:chatId, chat_type:'group', action:'get'})});
          if (msgState.chatId !== chatId || msgState.chatType !== 'group') return;
          msgState.adEnabled = Boolean(data.enabled);
          msgState.adEditable = Boolean(data.editable);
        } catch (_) {
          if (msgState.chatId === chatId && msgState.chatType === 'group') {
            msgState.adEnabled = false;
            msgState.adEditable = false;
          }
        } finally {
          if (msgState.chatId === chatId && msgState.chatType === 'group') {
            msgState.adLoading = false;
            updateMsgAdSwitch();
          }
        }
      };
      const toggleGroupAdSwitch = async () => {
        const chatId = String(msgState.chatId || '').trim();
        if (msgState.chatType !== 'group' || !chatId || !msgState.adEditable || msgState.adSaving) return;
        const enabled = !Boolean(msgState.adEnabled);
        msgState.adSaving = true;
        updateMsgAdSwitch();
        try {
          const data = await api('message/group-ad', {method:'POST', body:JSON.stringify({chat_id:chatId, chat_type:'group', action:'set', enabled})});
          if (msgState.chatId !== chatId || msgState.chatType !== 'group') return;
          msgState.adEnabled = Boolean(data.enabled);
          msgState.adEditable = Boolean(data.editable);
          toast(enabled ? '本群广告拦截已开启' : '本群广告拦截已关闭');
        } catch (error) {
          toast(error.message || '广告开关保存失败');
        } finally {
          if (msgState.chatId === chatId && msgState.chatType === 'group') {
            msgState.adSaving = false;
            updateMsgAdSwitch();
          }
        }
      };
      const updateMsgHead = (data) => {
        const nameEl = $('msg-head-name');
        nameEl.textContent = data.chat_name || '未命名会话';
        const curChat = (msgState.chats || []).find((c) => String(c.chat_id || '') === String(msgState.chatId || ''));
        const chatKey = String(msgState.chatId || '');
        const isAdmin = msgState.adminByChat.has(chatKey)
          ? Boolean(msgState.adminByChat.get(chatKey))
          : Boolean(data.is_admin || curChat?.is_admin || msgState.botIsAdmin);
        if (isAdmin) {
          nameEl.classList.add('admin');
        } else {
          nameEl.classList.remove('admin');
        }
        const gInfo = data.group_info || {};
        const gNum = Number(gInfo.member_num || 0);
        const removed = msgState.chatType === 'group' && (msgState.chatRemoved || gInfo.membership_status === 'removed' || curChat?.membership_status === 'removed' || curChat?.in_group === false);
        msgState.chatRemoved = removed;
        $('msg-head-sub').textContent = msgState.chatType === 'group'
          ? (removed ? '你已被移除群聊' : `群聊 · ${esc(msgState.chatId)}${gNum > 0 ? ` · 群成员 ${gNum} 人` : ''}`)
          : `私聊 · ${esc(msgState.chatId)}`;
        if (removed) {
          $('msg-ad-switch').hidden = true;
          $('msg-refresh-info').hidden = true;
          $('msg-remark').hidden = true;
        }
      };
      const openMsgLightbox = (src) => {
        if (!src) return;
        const box = $('msg-lightbox'); const img = $('msg-lightbox-img');
        img.src = src;
        box.hidden = false;
        document.body.style.overflow = 'hidden';
      };
      const closeMsgLightbox = () => {
        const box = $('msg-lightbox'); if (!box || box.hidden) return;
        box.hidden = true;
        $('msg-lightbox-img').removeAttribute('src');
        document.body.style.overflow = '';
      };
      const showMsgCtx = (x, y, items) => {
        const ctx = $('msg-ctx');
        ctx.innerHTML = items.map((it) => it.sep ? '<div class="msg-ctx-sep"></div>' : `<button class="msg-ctx-item${it.danger ? ' danger' : ''}" type="button">${esc(it.label)}</button>`).join('');
        ctx.hidden = false;
        const pad = 8;
        const rect = ctx.getBoundingClientRect();
        // 优先显示在鼠标右下角（QQ 风格），空间不足时翻转
        let left = x + 6;
        let top = y + 6;
        if (left + rect.width + pad > window.innerWidth) left = Math.max(pad, x - rect.width - 6);
        if (top + rect.height + pad > window.innerHeight) top = Math.max(pad, y - rect.height - 6);
        ctx.style.left = left + 'px';
        ctx.style.top = top + 'px';
        ctx.querySelectorAll('.msg-ctx-item').forEach((btn, idx) => {
          const item = items.filter((it) => !it.sep)[idx];
          btn.addEventListener('click', () => { hideMsgCtx(); if (item && item.action) item.action(); });
        });
      };
      const hideMsgCtx = () => { $('msg-ctx').hidden = true; $('msg-ctx').innerHTML = ''; };
      document.addEventListener('click', (e) => { if (!$('msg-ctx').contains(e.target)) hideMsgCtx(); });
      document.addEventListener('contextmenu', (e) => { if (!$('msg-ctx').contains(e.target)) hideMsgCtx(); });
      document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideMsgCtx(); });
      const atMember = (uid, nick) => {
        if (!uid) return;
        // QQ 官方群聊提及只支持 Markdown 消息，自动切换到 Markdown 类型
        if (msgState.sendType !== 'markdown' && msgState.sendType !== 'text') { toast('请先切换到文本或 Markdown 类型再 @ 成员'); return; }
        if (msgState.sendType !== 'markdown') {
          msgState.sendType = 'markdown';
          $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((x) => x.classList.toggle('active', x.dataset.msgType === 'markdown'));
          renderMsgExtra();
        }
        const mention = `<@${uid}> `;
        insertComposerText(mention);
        toast(`已插入 @${nick || uid}（将以 Markdown 发送）`);
      };
      const setMsgQuote = (messageId, userId, nickname, quotedText = '', refidx = '') => {
        const id = String(messageId || '').trim();
        if (!id) return;
        const uid = String(userId || '').trim();
        const name = String(nickname || '').trim();
        msgState.quote = {id, refidx:String(refidx || '').trim(), userId:uid, name, text:String(quotedText || name || '引用消息')};
        const preview = $('msg-quote-preview');
        const previewText = $('msg-quote-text');
        if (preview) preview.hidden = false;
        if (previewText) previewText.textContent = `${name || '引用消息'} · 引用`;
        // 群聊引用同步插入官方 Markdown 提及；避免重复点击引用时重复插入。
        if (uid && msgState.chatType === 'group') {
          const editor = getComposerEditor();
          if (editor) {
            msgState.sendType = 'markdown';
            const tabs = $('msg-composer-tabs');
            tabs?.querySelectorAll('[data-msg-type]').forEach((x) => x.classList.toggle('active', x.dataset.msgType === 'markdown'));
            renderMsgExtra();
            const mention = `<@${uid}> `;
            const existing = getComposerText();
            if (!existing.startsWith(mention)) insertComposerText(mention);
          }
        }
        getComposerEditor()?.focus();
      };
      const copyMsgText = async (text, row = null) => {
        let copyText = String(text || '');
        try {
          const selection = window.getSelection ? window.getSelection() : null;
          const selected = selection && !selection.isCollapsed ? String(selection.toString() || '') : '';
          const selectedInRow = selected && row && selection.anchorNode && selection.focusNode
            ? row.contains(selection.anchorNode) && row.contains(selection.focusNode)
            : Boolean(selected && !row);
          if (selected && selectedInRow) copyText = selected;
        } catch (_) {}
        if (!copyText.trim() && row) copyText = String(row.querySelector('.msg-bubble')?.innerText || '');
        copyText = copyText.trim();
        if (!copyText) return toast('没有可复制的消息内容');
        try {
          if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(copyText);
          } else {
            const ta = document.createElement('textarea');
            ta.value = copyText;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            ta.setSelectionRange(0, ta.value.length);
            const ok = document.execCommand('copy');
            document.body.removeChild(ta);
            if (!ok) throw new Error('execCommand 复制失败');
          }
          toast('已复制');
        } catch (error) { toast('复制失败：' + error.message); }
      };
      const enterMultiMode = () => {
        msgState.multi = true; msgState.selected.clear();
        $('msg-multi-bar').hidden = false;
        $('msg-multi-count').textContent = '已选 0 条';
        $('msg-body').classList.add('multi-mode');
        $('msg-body').querySelectorAll('.msg-row').forEach((row) => row.classList.add('multi-mode'));
      };
      const exitMultiMode = () => {
        msgState.multi = false; msgState.selected.clear();
        $('msg-multi-bar').hidden = true;
        $('msg-body').classList.remove('multi-mode');
        $('msg-body').querySelectorAll('.msg-row').forEach((row) => { row.classList.remove('multi-mode'); row.classList.remove('selected'); });
      };
      const recallSelected = async () => {
        const ids = [...msgState.selected];
        if (!ids.length) return toast('请先选择要撤回的消息');
        if (!confirm(`确定撤回选中的 ${ids.length} 条消息吗？发送超过 2 分钟的消息不可撤回。`)) return;
        let okCount = 0; let failCount = 0;
        for (const id of ids) {
          try { await api('message/recall', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, message_id:id})}); markLocalMessageRecalled(id); okCount++; }
          catch (error) { failCount++; }
        }
        toast(`撤回完成：成功 ${okCount} 条${failCount ? `，失败 ${failCount} 条` : ''}`);
        exitMultiMode(); loadMsgHistory();
      };
      const normalizeMsgIdentity = (value) => String(value ?? '')
        .replace(/[\u200b-\u200d\ufeff]/g, '')
        .trim();
      const msgMessageKey = (message) => normalizeMsgIdentity(
        message?.message_id ?? message?.messageId ?? message?.id,
      );
       const msgIdentityHash = (value) => {
         let hash = 2166136261;
         const text = String(value || '');
         for (let index = 0; index < text.length; index += 1) {
           hash ^= text.charCodeAt(index);
           hash = Math.imul(hash, 16777619);
         }
         return (hash >>> 0).toString(16).padStart(8, '0');
       };
       const msgMessageIdentityKeys = (message) => {
        if (!message || typeof message !== 'object') return [];
        const keys = [];
        const primary = msgMessageKey(message);
        if (primary) keys.push(`id:${primary}`);
        // 同一官方网关负载可能经过全量/At 两条回调路径；原始负载相同
        // 时视为同一条事件，避免不同适配器 ID 造成重复显示。
         if (String(message.source || '').trim().toLowerCase() === 'qq_official') {
           const raw = String(message.raw_message || '').trim();
           if (raw) keys.push(`raw:${msgIdentityHash(raw)}`);
         }
        return keys;
      };
      const msgMessagesMatch = (left, right) => {
        const rightKeys = new Set(msgMessageIdentityKeys(right));
        return msgMessageIdentityKeys(left).some((key) => rightKeys.has(key));
      };
      const msgIsRecalled = (message) => {
        const value = message?.recalled;
        return value === true || value === 1 || ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase());
      };
      const mergeMsgRecalledStates = (incoming, current = msgState.messages) => {
        const recalledKeys = new Set((Array.isArray(current) ? current : [])
          .filter((message) => msgIsRecalled(message))
          .map((message) => msgMessageKey(message))
          .filter(Boolean));
        return (Array.isArray(incoming) ? incoming : []).map((message) => {
          const key = msgMessageKey(message);
          return key && recalledKeys.has(key) && !msgIsRecalled(message)
            ? {...message, recalled:true}
            : message;
        });
      };
      const dedupeMsgMessages = (messages) => {
        const seen = new Set();
        return (Array.isArray(messages) ? messages : []).filter((message) => {
          const keys = msgMessageIdentityKeys(message);
          if (!keys.length) return true;
          if (keys.some((key) => seen.has(key))) return false;
          keys.forEach((key) => seen.add(key));
          return true;
        });
      };
      const msgMessageListsEqual = (left, right) => {
        const first = Array.isArray(left) ? left : [];
        const second = Array.isArray(right) ? right : [];
        if (first.length !== second.length) return false;
        return first.every((message, index) => {
          const other = second[index];
          if (!msgMessagesMatch(message, other)) return false;
          if (String(message?.content || '') !== String(other?.content || '')) return false;
          if (msgIsRecalled(message) !== msgIsRecalled(other)) return false;
          return JSON.stringify(message?.media || null) === JSON.stringify(other?.media || null);
        });
      };
      const mergeOptimisticMessages = (chatId, messages) => {
        const id = String(chatId || '');
        const base = dedupeMsgMessages(Array.isArray(messages) ? messages.slice() : []);
        const serverKeys = new Set(base.map((message) => msgMessageKey(message)).filter(Boolean));
        const optimistic = [];
        Array.from(msgState.optimisticSends?.entries?.() || []).forEach(([entryId, entry]) => {
          if (!entry || String(entry.chatId || '') !== id || !entry.message) return;
          const remoteId = String(entry.remoteId || '').trim();
          if (entry.status === 'sent' && remoteId && serverKeys.has(remoteId)) {
            msgState.optimisticSends.delete(entryId);
            return;
          }
          optimistic.push(entry.message);
        });
        return dedupeMsgMessages([...base, ...optimistic]);
      };
      const createOptimisticSend = (payload) => {
        const id = `web-${Date.now()}-${++msgState.optimisticSeq}`;
        const rawContent = String(payload.content || '');
        const imageParts = rawContent.split(composerImageMarker);
        const content = imageParts.join('').trim();
        const imageData = String(payload.image_data || '').trim();
        const imageUrl = safeImageSource(payload.image_url);
        const imageBefore = imageParts.length > 1 ? imageParts[0].trim() : String(payload.image_before || '').trim();
        const imageAfter = imageParts.length > 1 ? imageParts.slice(1).join(composerImageMarker).trim() : String(payload.image_after || '').trim();
        const imageType = imageData.match(/^data:([^;,]+)/i)?.[1] || 'image/png';
         const mediaData = String(payload.media_data || '').trim();
         const mediaFile = typeof File !== 'undefined' && payload.media_file instanceof File ? payload.media_file : null;
         const mediaType = Number(payload.media_file_type || 4) === 2 ? '视频' : '文件';
        const mediaMime = String(payload.media_mime || '').trim();
        const mediaName = String(payload.media_name || '').trim() || '附件文件';
        const message = {
          message_id: id,
          optimistic_id: id,
          user_id: '',
          nickname: '我',
          content,
          timestamp: new Date().toISOString(),
          source: 'web_panel',
          is_self: true,
          reference_id: String(payload.quote_message_id || '').trim(),
          media: imageData
            ? {type:'图片', content_type:imageType, optimistic_data:imageData, text:content, before_text:imageBefore, after_text:imageAfter}
            : (imageUrl
              ? {type:'图片', content_type:'image/*', src:imageUrl, text:content, before_text:imageBefore, after_text:imageAfter}
              : ((mediaData || mediaFile) ? {type:mediaType, content_type:mediaMime, name:mediaName, optimistic_data:mediaData, text:content} : null)),
        };
        const entry = {
          id,
          chatId: String(payload.chat_id || ''),
          chatType: String(payload.chat_type || 'group'),
          payload: {...payload},
          message,
          status: 'pending',
          remoteId: '',
          createdAt: Date.now(),
        };
        msgState.optimisticSends.set(id, entry);
        while (msgState.optimisticSends.size > 100) {
          const first = msgState.optimisticSends.keys().next().value;
          if (!first) break;
          msgState.optimisticSends.delete(first);
        }
        return entry;
      };
      const renderOptimisticMessages = (chatId) => {
        if (String(msgState.chatId || '') !== String(chatId || '') || $('page-messages')?.hidden) return;
        const body = $('msg-body');
        if (!body) return;
        const previousTop = body.scrollTop || 0;
        const previousHeight = body.scrollHeight || 0;
        const followLatest = msgBodyNearBottom(body) || !msgState.renderedChatId;
        renderMsgMessages(
          {...(msgState.historyData || {}), messages:msgState.messages},
          {previousTop, previousHeight, toBottom:followLatest},
        );
      };
      const buildSendBody = (payload) => {
        const file = payload?.media_file;
        const imageFile = payload?.image_file;
        const hasMediaFile = file && typeof File !== 'undefined' && file instanceof File;
        const hasImageFile = imageFile && typeof File !== 'undefined' && imageFile instanceof File;
        if (!hasMediaFile && !hasImageFile) return JSON.stringify(payload || {});
        const form = new FormData();
        Object.entries(payload || {}).forEach(([key, value]) => {
          if (key === 'media_file' || key === 'image_file' || key === 'media_data' || (key === 'image_data' && hasImageFile) || value == null || value === '') return;
          form.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
        });
        if (hasMediaFile) form.append('media_file', file, String(payload.media_name || file.name || 'attachment'));
        if (hasImageFile) form.append('image_file', imageFile, String(imageFile.name || 'image.png'));
        return form;
      };
      const resetComposer = () => {
        const editor = getComposerEditor();
        if (editor) editor.replaceChildren();
        msgState.quote = null;
        msgState.pastedImage = null;
        msgState.pastedImageFile = null;
        msgState.pastedImageSource = '';
        msgState.composerSelection = null;
        clearComposerMedia();
        $('msg-input-box')?.classList.remove('has-inline-image');
        const file = $('msg-img-file');
        if (file) file.value = '';
        const quote = $('msg-quote-preview');
        if (quote) quote.hidden = true;
      };
      const finishOptimisticSend = async (entry) => {
        try {
          const result = await api('message/send', {method:'POST', body:buildSendBody(entry.payload)});
          const remoteId = String(result?.message_id || result?.message?.message_id || result?.message?.id || '').trim();
          entry.status = 'sent';
          entry.remoteId = remoteId;
          entry.message.send_status = 'sent';
          if (remoteId) entry.message.message_id = remoteId;
          if (String(msgState.chatId || '') === entry.chatId) {
            renderOptimisticMessages(entry.chatId);
            msgState.historyCache.delete(`${entry.chatType}|${entry.chatId}`);
            void loadMsgHistory(false, true);
          }
          void loadMsgChats(true);
          entry.cleanupTimer = setTimeout(() => {
            if (entry.status !== 'sent' || !msgState.optimisticSends.has(entry.id)) return;
            msgState.optimisticSends.delete(entry.id);
            renderOptimisticMessages(entry.chatId);
          }, 15000);
        } catch (error) {
          entry.status = 'failed';
          entry.message.send_status = 'failed';
          entry.error = error;
          renderOptimisticMessages(entry.chatId);
          if (String(msgState.chatId || '') === entry.chatId) toast('发送失败，点击感叹号重试');
        }
      };
      const retryOptimisticSend = (id) => {
        const entry = msgState.optimisticSends.get(String(id || ''));
        if (!entry || entry.status === 'pending') return;
        if (entry.cleanupTimer) clearTimeout(entry.cleanupTimer);
        entry.status = 'pending';
        entry.message.send_status = 'pending';
        renderOptimisticMessages(entry.chatId);
        void finishOptimisticSend(entry);
      };
      const msgBodyNearBottom = (body, threshold = 56) => Boolean(body) && body.scrollHeight - body.scrollTop - body.clientHeight <= threshold;
      const clearMsgNewMessages = () => {
        msgState.pendingNewMessages = 0;
        const button = $('msg-new-messages');
        if (button) button.hidden = true;
      };
      const showMsgNewMessages = (count) => {
        msgState.pendingNewMessages = Math.max(1, Number(msgState.pendingNewMessages || 0) + Number(count || 0));
        const button = $('msg-new-messages');
        const label = $('msg-new-messages-label');
        if (label) label.textContent = `有 ${msgState.pendingNewMessages} 条新消息`;
        if (button) button.hidden = false;
      };
      const scrollMsgToBottom = (behavior = 'smooth') => {
        const body = $('msg-body');
        if (!body) return;
        if (typeof body.scrollTo === 'function') body.scrollTo({top:body.scrollHeight, behavior});
        else body.scrollTop = body.scrollHeight;
        if (typeof requestAnimationFrame === 'function') {
          requestAnimationFrame(() => {
            if (typeof body.scrollTo === 'function') body.scrollTo({top:body.scrollHeight, behavior:'auto'});
            else body.scrollTop = body.scrollHeight;
          });
        }
        clearMsgNewMessages();
        markMsgRead(undefined, true);
      };
      const safeMediaUrl = (value) => {
        const raw = String(value ?? '').trim().replace(/&amp;/gi, '&').replace(/&#0*38;?/gi, '&');
        if (!raw) return '';
        try {
          const url = new URL(raw, location.href);
          return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
        } catch (_) { return ''; }
      };
      const safeImageSource = (value) => {
        const raw = String(value ?? '').trim();
        if (/^data:image\/(?:png|jpe?g|gif|webp|bmp);base64,[A-Za-z0-9+/=]+$/i.test(raw)) return raw;
        return safeMediaUrl(raw);
      };
      const mediaProxyUrl = (src, mode = 'image', name = '') => {
        const direct = safeMediaUrl(src);
        if (!direct) return '';
        try {
          const host = new URL(direct).hostname.toLowerCase().replace(/\.$/, '');
          const allowed = ['multimedia.nt.qq.com.cn', 'qqbot.ugcimg.cn', 'gchat.qpic.cn', 'qpic.cn', 'qq.com.cn', 'qq.com'];
          const shouldProxy = allowed.some((suffix) => host === suffix || host.endsWith(`.${suffix}`));
          if (!shouldProxy) return direct;
          const query = new URLSearchParams({src: direct, mode: mode === 'image' ? 'image' : 'file'});
          if (name) query.set('name', name);
          return `/api/message/media?${query.toString()}`;
        } catch (_) { return direct; }
      };
      const mediaFileName = (media, src) => {
        const explicit = String(media?.name || media?.filename || media?.file_name || '').trim();
        if (explicit) return explicit;
        try {
          const part = decodeURIComponent(new URL(src).pathname.split('/').filter(Boolean).pop() || '');
          return part && !['download', 'file', 'media'].includes(part.toLowerCase()) ? part : '附件文件';
        } catch (_) { return '附件文件'; }
      };
      const mediaSizeLabel = (value) => {
        const size = Number(value || 0);
        if (!Number.isFinite(size) || size <= 0) return '';
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
        if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
        return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`;
      };
      const renderMessageMedia = (value, messageId = '') => {
        if (!value) return '';
        const items = Array.isArray(value?.items) && value.items.length ? value.items : [value];
        return items.map((item) => {
          if (!item || typeof item !== 'object') return '';
          const type = String(item.type || item.media_type || '文件');
          const contentType = String(item.content_type || item.mime_type || '').toLowerCase();
           const directSrc = item.src || item.url || item.download_url;
           const inlineSrc = String(item.optimistic_data || '').match(/^data:image\/(?:png|jpe?g|gif|webp|bmp);base64,[A-Za-z0-9+/=]+$/i) && String(item.optimistic_data).length <= 12000000 ? String(item.optimistic_data) : '';
           const src = safeMediaUrl(directSrc) || inlineSrc;
          const typeLower = type.toLowerCase();
          const isImage = ['图片', 'image', 'img'].includes(typeLower) || contentType.startsWith('image/');
          const isVideo = ['视频', 'video'].includes(typeLower) || contentType.startsWith('video/');
          if (isImage) {
            if (!src) return '<div class="msg-media msg-image-media"><span class="msg-media-ph">图片地址未保存</span></div>';
            const preview = mediaProxyUrl(src, 'image');
            return `<div class="msg-media msg-image-media"><button class="msg-image-link" type="button" aria-label="放大图片"><img src="${esc(preview || src)}" alt="图片" loading="lazy" decoding="async" draggable="true" referrerpolicy="no-referrer" data-lightbox="${esc(preview || src)}" data-media-direct="${esc(src)}" data-media-proxied="${preview && preview !== src ? '1' : '0'}" data-media-img></button></div>`;
          }
          if (isVideo && src) {
            const videoUrl = mediaProxyUrl(src, 'file');
            return `<div class="msg-media msg-video-media"><video controls preload="metadata" src="${esc(videoUrl || src)}" data-media-direct="${esc(src)}"></video></div>`;
          }
          const name = mediaFileName(item, src);
          const size = mediaSizeLabel(item.size);
          const meta = [type, size].filter(Boolean).join(' · ') || '附件';
          if (!src) return `<div class="msg-media msg-file-card is-unavailable"><span class="msg-file-icon">□</span><span class="msg-file-info"><strong>${esc(name)}</strong><small>${esc(meta)} · 地址未保存</small></span></div>`;
          const download = name ? ` download="${esc(name)}"` : '';
          const fileUrl = mediaProxyUrl(src, 'file', name);
          return `<a class="msg-media msg-file-card" href="${esc(fileUrl || src)}" target="_blank" rel="noopener noreferrer"${download}><span class="msg-file-icon">${type === '视频' ? '▶' : type === '语音' ? '♫' : '□'}</span><span class="msg-file-info"><strong>${esc(name)}</strong><small>${esc(meta)}</small></span><span class="msg-file-action">下载</span></a>`;
        }).join('');
      };
      const blobToDataUrl = (blob) => new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ''));
        reader.onerror = () => reject(reader.error || new Error('图片读取失败'));
        reader.readAsDataURL(blob);
      });
      const dataUrlToFile = (dataUrl, name = 'image.png') => {
        const match = String(dataUrl || '').match(/^data:(image\/[a-z0-9.+-]+);base64,([A-Za-z0-9+/=]+)$/i);
        if (!match || typeof atob !== 'function' || typeof File === 'undefined') return null;
        try {
          const binary = atob(match[2]);
          const bytes = new Uint8Array(binary.length);
          for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
          const extension = String(match[1]).split('/')[1].replace(/[^a-z0-9]+/gi, '') || 'png';
          return new File([bytes], String(name || `image.${extension}`), {type:match[1]});
        } catch (_) { return null; }
      };
      const fetchImageBlob = async (source) => {
        const url = safeImageSource(source);
        if (!url) throw new Error('图片地址无效');
        const response = await fetch(url, {credentials:'same-origin', cache:'no-store'});
        if (!response.ok) throw new Error('图片读取失败');
        const blob = await response.blob();
        if (!String(blob.type || '').toLowerCase().startsWith('image/')) throw new Error('不是图片');
        return blob;
      };
      const imageElementToBlob = (image) => new Promise((resolve, reject) => {
        if (!image || !image.complete || !image.naturalWidth || !image.naturalHeight) {
          reject(new Error('图片尚未加载'));
          return;
        }
        try {
          const canvas = document.createElement('canvas');
          canvas.width = image.naturalWidth;
          canvas.height = image.naturalHeight;
          const context = canvas.getContext('2d');
          if (!context) throw new Error('浏览器不支持图片读取');
          context.drawImage(image, 0, 0);
          canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('图片转换失败')), 'image/png');
        } catch (error) { reject(error); }
      });
      const getCopyImageBlob = async (source, image) => {
        const sources = [source, image?.dataset?.mediaDirect, image?.currentSrc, image?.src]
          .map((item) => safeImageSource(item))
          .filter(Boolean)
          .filter((item, index, values) => values.indexOf(item) === index);
        let lastError = new Error('图片读取失败');
        for (const candidate of sources) {
          try { return await fetchImageBlob(candidate); }
          catch (error) { lastError = error; }
        }
        try { return await imageElementToBlob(image); }
        catch (error) { lastError = error; }
        throw lastError;
      };
      const copyImageDataUrlWithExecCommand = (dataUrl) => {
        const holder = document.createElement('div');
        const image = document.createElement('img');
        holder.contentEditable = 'true';
        holder.setAttribute('aria-hidden', 'true');
        holder.style.position = 'fixed';
        holder.style.left = '-10000px';
        holder.style.top = '0';
        holder.style.width = '1px';
        holder.style.height = '1px';
        holder.style.overflow = 'hidden';
        image.src = dataUrl;
        image.alt = '图片';
        holder.appendChild(image);
        document.body.appendChild(holder);
        const selection = window.getSelection?.();
        const previousRanges = [];
        try {
          for (let index = 0; selection && index < selection.rangeCount; index += 1) previousRanges.push(selection.getRangeAt(index).cloneRange());
          const range = document.createRange();
          range.selectNode(image);
          selection?.removeAllRanges();
          selection?.addRange(range);
          const onCopy = (event) => {
            const clipboard = event.clipboardData;
            if (!clipboard) return;
            clipboard.setData('text/html', `<img src="${dataUrl}" alt="图片">`);
            clipboard.setData('text/plain', '');
            event.preventDefault();
          };
          document.addEventListener('copy', onCopy, true);
          let copied = false;
          try { copied = document.execCommand('copy'); }
          finally { document.removeEventListener('copy', onCopy, true); }
          return copied;
        } finally {
          selection?.removeAllRanges();
          previousRanges.forEach((range) => selection?.addRange(range));
          holder.remove();
        }
      };
      const setComposerImage = (data, source, preview = '', file = null) => {
        clearComposerMedia();
        msgState.pastedImage = String(data || '');
        msgState.pastedImageFile = file && typeof File !== 'undefined' && file instanceof File ? file : null;
        msgState.pastedImageSource = String(source || '');
        const inlineSource = String(preview || data || source || '').trim();
        if (inlineSource) insertComposerImage(inlineSource);
        getComposerEditor()?.focus();
      };
      const setComposerMedia = (data, name, fileType, mime = '', file = null) => {
        clearMsgImage();
        msgState.mediaData = String(data || '');
        msgState.mediaFile = file && typeof File !== 'undefined' && file instanceof File ? file : null;
        msgState.mediaName = String(name || '附件文件').trim() || '附件文件';
        msgState.mediaType = Number(fileType || 4) === 2 ? 2 : 4;
        msgState.mediaMime = String(mime || '').trim();
        msgState.sendType = 'media';
        const inline = $('msg-media-inline');
        const label = $('msg-media-name');
        const icon = $('msg-media-icon');
        if (label) label.textContent = msgState.mediaName;
        if (icon) icon.textContent = msgState.mediaType === 2 ? '▶' : '□';
        if (inline) inline.hidden = false;
        getComposerEditor()?.focus();
      };
      const clearComposerMedia = () => {
        msgState.mediaData = null;
        msgState.mediaFile = null;
        msgState.mediaName = '';
        msgState.mediaType = 0;
        msgState.mediaMime = '';
        const inline = $('msg-media-inline');
        if (inline) inline.hidden = true;
        const label = $('msg-media-name');
        if (label) label.textContent = '待发送附件';
        const input = $('msg-attachment-file');
        const video = $('msg-video-file');
        if (input) input.value = '';
        if (video) video.value = '';
      };
      const readComposerMediaFile = (file, fileType) => {
        if (!file) return;
        const maxBytes = 200 * 1024 * 1024;
        if (Number(file.size || 0) <= 0) return toast('文件为空，无法发送');
        if (Number(file.size || 0) > maxBytes) return toast('文件超过 200 MB 限制');
        if (Number(fileType) === 2 && String(file.type || '').toLowerCase() !== 'video/mp4' && !/\.mp4$/i.test(String(file.name || ''))) return toast('视频只支持 MP4 格式');
        setComposerMedia('', file.name, Number(fileType) === 2 ? 2 : 4, file.type, file);
        toast(`${Number(fileType) === 2 ? '视频' : '文件'}已添加，可继续输入说明后发送`);
      };
      const copyImageToClipboard = async (source, image) => {
        try {
          const blob = await getCopyImageBlob(source, image);
          let copied = false;
          if (navigator.clipboard?.write && window.ClipboardItem) {
            const mime = String(blob.type || '').toLowerCase().startsWith('image/') ? String(blob.type || '').toLowerCase() : 'image/png';
            try {
              await navigator.clipboard.write([new window.ClipboardItem({[mime]: blob.type === mime ? blob : blob.slice(0, blob.size, mime)})]);
              copied = true;
            } catch (_) {}
          }
          if (!copied) {
            const dataUrl = await blobToDataUrl(blob);
            copied = copyImageDataUrlWithExecCommand(dataUrl);
          }
          if (!copied) throw new Error('浏览器不支持图片复制');
          toast('图片已复制');
        } catch (_) {
          toast('图片复制失败，请重试');
        }
      };
      const attachDroppedImage = async (source) => {
        const url = safeImageSource(source);
        if (!url) return toast('请拖入图片');
        if (!url.startsWith('data:')) {
          const proxy = mediaProxyUrl(url, 'image') || url;
          try {
            const dataUrl = await blobToDataUrl(await fetchImageBlob(proxy));
            setComposerImage(dataUrl, '', dataUrl, null);
            toast('图片已读取，可继续输入文字后发送');
          } catch (_) {
            setComposerImage('', url, proxy);
            toast('图片已添加，可继续输入文字后发送');
          }
          return;
        }
        try {
          const dataUrl = await blobToDataUrl(await fetchImageBlob(url));
          setComposerImage(dataUrl, '', dataUrl, null);
          toast('图片已添加，可继续输入文字后发送');
        } catch (_) {
          toast('图片读取失败，请重新拖入');
        }
      };
      const bindImageInteractions = (img) => {
        if (!img) return;
        img.draggable = true;
        img.addEventListener('contextmenu', (event) => {
          event.preventDefault();
          event.stopPropagation();
          const source = img.currentSrc || img.dataset.mediaDirect || img.src;
          showMsgCtx(event.clientX, event.clientY, [
            {label:'复制图片', action:() => copyImageToClipboard(source, img)},
          ]);
        });
        img.addEventListener('dragstart', (event) => {
          const source = img.dataset.mediaDirect || img.currentSrc || img.src;
          if (!source || !event.dataTransfer) return;
          event.stopPropagation();
          event.dataTransfer.effectAllowed = 'copy';
          event.dataTransfer.setData('application/x-mantou-image', source);
          event.dataTransfer.setData('text/uri-list', source);
          event.dataTransfer.setData('text/plain', source);
        });
      };
      const stripMediaMarker = (text, media) => {
        const raw = String(text || '');
        if (!media) return raw;
        return raw.replace(/\[(?:图片|语音|视频|文件|媒体|media)\]\s*(?:https?:\/\/[^\s<>]+)?/i, '').trim();
      };
      const stripObjectMarker = (text, media) => {
        const raw = String(text || '').trim();
        if (!/^\[?OBJ\s*:\s*\d+\]?$/i.test(raw)) return raw;
        return media ? '' : '（消息对象）';
      };
      const msgMuteRefreshMs = 30 * 1000;
      const formatMuteRemaining = (expireTs) => {
        const left = Math.max(0, Math.ceil(Number(expireTs || 0) - Date.now() / 1000));
        if (!left) return '已结束';
        const days = Math.floor(left / 86400);
        const hours = Math.floor((left % 86400) / 3600);
        const minutes = Math.floor((left % 3600) / 60);
        const seconds = left % 60;
        const pad = (value) => String(value).padStart(2, '0');
        return days > 0
          ? `${days}天 ${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
          : `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
      };
      const updateMuteCountdowns = () => {
        const now = Date.now() / 1000;
        let expired = false;
        document.querySelectorAll('[data-msg-mute-expire]').forEach((node) => {
          const expireTs = Number(node.dataset.msgMuteExpire || 0);
          const row = node.closest('.msg-row');
          if (expireTs > 0 && expireTs <= now) {
            const member = String(row?.dataset.msgUid || '').trim();
            if (member && msgState.mutes.delete(member)) expired = true;
            return;
          }
          node.textContent = expireTs > 0 ? `禁言剩余 ${formatMuteRemaining(expireTs)}` : '已禁言';
        });
        if (expired && msgState.chatId && !$('page-messages')?.hidden) {
          const body = $('msg-body');
          renderMsgMessages(
            {...(msgState.historyData || {}), messages:msgState.messages},
            {previousTop:body?.scrollTop || 0, previousHeight:body?.scrollHeight || 0},
          );
        }
      };
      const loadMuteStates = (force = false) => {
        if (msgState.chatType !== 'group' || !msgState.chatId) return Promise.resolve(null);
        if (!msgState.botIsAdmin) return Promise.resolve(null);
        const chatId = String(msgState.chatId);
        const chatType = String(msgState.chatType);
        if (msgState.muteRequestPromise && msgState.muteRequestChatId === chatId) return msgState.muteRequestPromise;
        const now = Date.now();
        if (!force && msgState.muteRequestAt && now - msgState.muteRequestAt < msgMuteRefreshMs) return Promise.resolve(null);
        const token = Number(msgState.muteRequestToken || 0) + 1;
        msgState.muteRequestToken = token;
        const promise = (async () => {
          try {
            const currentChat = msgState.chats.find((chat) => String(chat.chat_id || '') === chatId) || {};
            const data = await api('message/group-member/mutes', {method:'POST', body:JSON.stringify({chat_id:chatId, chat_type:chatType, appid:String(currentChat.appid || window.msgAppid || '')})});
            if (token !== Number(msgState.muteRequestToken || 0) || msgState.chatId !== chatId || msgState.chatType !== chatType) return data;
            msgState.muteRequestAt = Date.now();
            if (data?.available !== false) {
              const next = new Map();
              (Array.isArray(data?.members) ? data.members : []).forEach((member) => {
                const id = String(member?.member_openid || member?.union_openid || '').trim();
                if (!id) return;
                const expireTs = Number(member?.mute_expire_ts || 0);
                if (expireTs > 0 && expireTs <= Date.now() / 1000) return;
                const username = String(member?.username || '').trim();
                if (username) msgState.profiles[id] = {...(msgState.profiles[id] || {}), nickname:username, username};
                next.set(id, {...member, member_openid:id, mute_expire_ts:expireTs});
              });
              const mutesChanged = next.size !== msgState.mutes.size
                || [...next].some(([id, member]) => {
                  const previous = msgState.mutes.get(id);
                  return !previous
                    || Number(previous.mute_expire_ts || 0) !== Number(member.mute_expire_ts || 0)
                    || String(previous.username || '') !== String(member.username || '');
                });
              msgState.mutes = next;
              msgState.muteRequestAt = Date.now();
              const body = $('msg-body');
              if (mutesChanged && !$('page-messages')?.hidden && msgState.renderedChatId === chatId) {
                renderMsgMessages(
                  {...(msgState.historyData || {}), messages:msgState.messages},
                  {previousTop:body?.scrollTop || 0, previousHeight:body?.scrollHeight || 0},
                );
              }
            }
            return data;
          } catch (_) {
            if (token === Number(msgState.muteRequestToken || 0) && msgState.chatId === chatId) msgState.muteRequestAt = Date.now();
            return null;
          } finally {
            if (msgState.muteRequestPromise === promise) {
              msgState.muteRequestPromise = null;
              msgState.muteRequestChatId = '';
            }
          }
        })();
        msgState.muteRequestChatId = chatId;
        msgState.muteRequestPromise = promise;
        return promise;
      };
      const unmuteMember = async (member, name = '') => {
        const memberId = String(member || '').trim();
        if (!memberId || msgState.chatType !== 'group' || !msgState.chatId) return;
        if (!confirm(`确定解除 ${name || memberId} 的禁言吗？`)) return;
        try {
          await api('message/group-member/unmute', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, member_openid:memberId, appid:String(window.msgAppid || '')})});
          toast('已解除禁言');
          void loadMuteStates(true);
        } catch (error) {
          toast(error.message || '解除禁言失败');
        }
      };
      const openMuteDialog = (member, name = '') => {
        msgState.mute = {member:String(member || '').trim(), name:String(name || '').trim()};
        $('msg-mute-title').textContent = `禁言 ${name || member}`;
        $('msg-mute-modal').hidden = false;
      };
      const cancelMsgBottomPosition = (body = null, reveal = false) => {
        msgState.positionToken = Number(msgState.positionToken || 0) + 1;
        if (msgState.positionFrame != null) {
          if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(msgState.positionFrame);
          else clearTimeout(msgState.positionFrame);
        }
        msgState.positionFrame = null;
        msgState.positionObserver?.disconnect();
        msgState.positionObserver = null;
        const positionedBody = body || msgState.positionBody;
        msgState.positionBody = null;
        if (reveal && positionedBody) positionedBody.classList.remove('msg-positioning');
      };
      const scrollMsgBodyToBottom = (body, chatId = msgState.chatId, revealAfterPosition = false) => {
        if (!body) return;
        const targetChatId = String(chatId || '');
        const startedAt = Date.now();
        let previousHeight = -1;
        let stableFrames = 0;
        cancelMsgBottomPosition();
        const positionToken = Number(msgState.positionToken || 0);
        msgState.positionBody = body;
        const isCurrentPosition = () => positionToken === Number(msgState.positionToken || 0)
          && msgState.positionBody === body
          && (!targetChatId || String(msgState.chatId || '') === targetChatId);
        const apply = () => {
          if (!isCurrentPosition()) return false;
          body.scrollTop = body.scrollHeight;
          return true;
        };
        const reveal = () => {
          if (!revealAfterPosition || !isCurrentPosition()) return;
          body.classList.remove('msg-positioning');
        };
        const finish = () => {
          if (!isCurrentPosition()) return;
          if (msgState.positionFrame != null) {
            if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(msgState.positionFrame);
            else clearTimeout(msgState.positionFrame);
          }
          msgState.positionFrame = null;
          msgState.positionObserver?.disconnect();
          msgState.positionObserver = null;
          apply();
          reveal();
          msgState.positionBody = null;
        };
        apply();
        if (revealAfterPosition && typeof requestAnimationFrame === 'function') {
          body.querySelectorAll('img').forEach((image) => image.addEventListener('load', apply, {once:true}));
          if (typeof ResizeObserver === 'function') {
            msgState.positionObserver = new ResizeObserver(apply);
            msgState.positionObserver.observe(body);
          }
          const settle = () => {
            if (!apply()) return;
            const height = body.scrollHeight;
            if (height === previousHeight) stableFrames += 1;
            else { previousHeight = height; stableFrames = 0; }
            if (stableFrames >= 3 || Date.now() - startedAt >= 700) {
              finish();
              return;
            }
            msgState.positionFrame = requestAnimationFrame(settle);
          };
          msgState.positionFrame = requestAnimationFrame(settle);
        } else if (typeof requestAnimationFrame === 'function') {
          requestAnimationFrame(() => {
            if (!isCurrentPosition()) return;
            apply();
            requestAnimationFrame(() => {
              if (!isCurrentPosition()) return;
              apply();
              msgState.positionBody = null;
            });
          });
        } else {
          setTimeout(() => {
            finish();
          }, 0);
        }
      };
      const renderMsgMessages = (data, scroll = {}) => {
        const body = $('msg-body');
        const keepLatestVisible = !scroll.prepend && (Boolean(scroll.toBottom) || msgBodyNearBottom(body));
        const initialPositioning = !scroll.prepend
          && msgState.initialScrollChatId === msgState.chatId
          && keepLatestVisible;
        if (initialPositioning) body.classList.add('msg-positioning');
        const previousData = msgState.renderedChatId === msgState.chatId ? (msgState.historyData || {}) : {};
        data = {
          ...previousData,
          ...data,
          member_profiles:{...(previousData.member_profiles || {}), ...(data.member_profiles || {})},
          references:{...(previousData.references || {}), ...(data.references || {})},
        };
        const serverMessages = mergeMsgRecalledStates(dedupeMsgMessages(data.messages || []));
        const msgs = mergeOptimisticMessages(msgState.chatId, serverMessages);
        // 历史缓存只保存服务器消息；待发送/失败消息由 optimisticSends 单独维护。
        msgState.historyData = {...data, messages:serverMessages};
        window.msgAppid = data.messages?.[0]?.appid || window.msgAppid || '';
        updateMsgHead(data);
        updateMsgAdminTag();
        $('msg-refresh-info').hidden = msgState.chatType !== 'group' || msgState.chatRemoved;
        $('msg-remark').hidden = msgState.chatType !== 'group' || msgState.chatRemoved;
        updateMsgAdSwitch();
        const rawStore = window._msgRaw = window._msgRaw || {};
        const renderedRawKeys = new Set();
        if (!msgs.length) {
          body.innerHTML = '<div class="msg-empty">暂无消息记录</div>';
          body.classList.remove('msg-positioning');
          Object.keys(rawStore).forEach((key) => delete rawStore[key]);
          msgState.renderedChatId = msgState.chatId;
          clearMsgNewMessages();
          return;
        }
        const profiles = mergeMsgProfiles(
          {...(msgState.profiles || {}), ...(data.member_profiles || {})},
          msgs,
        );
        msgState.profiles = profiles;
        let lastDay = ''; let html = '';
        if (data.has_more) html += '<button class="msg-load-older" id="msg-load-older" type="button">加载更早消息</button>';
        msgs.forEach((m) => {
          const day = String(m.timestamp||'').slice(0,10);
          if (day !== lastDay && day) { html += `<div class="msg-day">${esc(fmtDayLabel(m.timestamp))}</div>`; lastDay = day; }
          const isSelf = Boolean(m.is_self) || ['bot_active', 'bot_send', 'web_panel'].includes(String(m.source || ''));
          const botMessage = String(m.source || '').startsWith('bot') || String(m.source || '') === 'web_panel';
          const recalled = msgIsRecalled(m);
          const optimisticId = String(m.optimistic_id || '').trim();
          const optimisticEntry = optimisticId ? msgState.optimisticSends.get(optimisticId) : null;
          const sendState = String(optimisticEntry?.status || m.send_status || '').trim();
          const failedSend = Boolean(optimisticEntry) && sendState === 'failed';
          const profile = profiles[m.user_id] || {};
          const rawNickname = String(m.nickname || '').trim();
          const profileNickname = String(profile.nickname || profile.username || '').trim();
          const botProfileName = String(window.msgBotProfile?.username || '').trim();
          const botProfileAvatar = String(window.msgBotProfile?.avatar || '').trim();
          const profileAvatar = safeMediaUrl(String(profile.avatar || profile.avatar_url || '').trim());
          const muteState = !isSelf ? msgState.mutes.get(String(m.user_id || '').trim()) : null;
          const muteExpireTs = Number(muteState?.mute_expire_ts || 0);
          const isMuted = Boolean(muteState) && (!muteExpireTs || muteExpireTs > Date.now() / 1000);
          const displayNickname = isSelf
            ? (botMessage
              ? (rawNickname && !['未知用户', '未知', '机器人', '我'].includes(rawNickname) ? rawNickname : (botProfileName || '机器人'))
              : (rawNickname && rawNickname !== '未知用户' ? rawNickname : '我'))
            : ((rawNickname && rawNickname !== '未知用户' && rawNickname !== '未知') ? rawNickname : (profileNickname || rawNickname || '未知用户'));
          const av = isSelf && botMessage ? botProfileAvatar : (isSelf ? '' : (profileAvatar || avatarUrl(m.user_id, 'user', data.messages?.[0]?.appid || window.msgAppid)));
          const tags = [];
          if (isSelf) {
            tags.push('<span class="msg-tag self">' + (botMessage ? '机器人' : '我') + '</span>');
          }
          if (m.source === 'web_panel') tags.push('<span class="msg-tag">网页</span>');
          if (recalled) tags.push('<span class="msg-tag recalled">已撤回</span>');
          if (isMuted) tags.push('<span class="msg-tag muted" data-msg-mute-tag="1">被禁言</span>');
          const roleMap = {owner:'群主', admin:'管理', member:'群员'};
          const rawRole = String(m.raw_message || '').match(/member_role[^,]*?['"]([a-z]+)['"]/)?.[1] || '';
          const memberRole = String(profile.role || rawRole || '').trim().toLowerCase();
          const protectedRole = !isSelf && (memberRole === 'owner' || memberRole === 'admin');
          const roleTag = roleMap[memberRole] || '';
          if (!isSelf && roleTag) tags.push(`<span class="msg-tag role">${roleTag}</span>`);
          const renderText = (text) => {
            return replaceMsgMentions(text, profiles);
          };
          const ref = (data.references || {})[m.reference_id];
          // 撤回只改变颜色和标签，保留撤回前的正文、引用和媒体。
          const quote = m.reference_id ? (ref ? `<div class="msg-bubble-quote"><b>${esc(ref.nickname || '')}</b>：${esc(ref.content || '')}</div>` : `<div class="msg-bubble-quote">引用消息 ${esc(m.reference_id)}</div>`) : '';
          const mediaData = m.media;
          const media = renderMessageMedia(mediaData, m.message_id);
          const mediaText = mediaData && !Array.isArray(mediaData) ? String(mediaData.text || '') : '';
          const renderedContent = renderText(m.content || '');
          let content = stripMediaMarker(renderedContent, mediaData);
          content = stripObjectMarker(content, mediaData);
          if (!content && mediaText) content = renderText(mediaText);
          if (!content && !media) content = '（空消息）';
          const contentHtml = content ? renderMsgMarkup(content, profiles) : '';
          const hasInlineMediaText = media && mediaData && !Array.isArray(mediaData)
            && (Object.prototype.hasOwnProperty.call(mediaData, 'before_text') || Object.prototype.hasOwnProperty.call(mediaData, 'after_text'));
          const inlineMediaHtml = hasInlineMediaText
            ? `${mediaData.before_text ? `<div class="msg-media-text">${renderMsgMarkup(String(mediaData.before_text), profiles)}</div>` : ''}${media}${mediaData.after_text ? `<div class="msg-media-text msg-media-text-after">${renderMsgMarkup(String(mediaData.after_text), profiles)}</div>` : ''}`
            : '';
          // 权限：撤回自己发的消息总是可以；撤回他人消息需要机器人为管理员；禁言需要机器人为管理员且对方非群主/管理员
          const canRecall = Boolean(m.message_id) && !recalled && !optimisticEntry && (isSelf || (msgState.botIsAdmin && !protectedRole));
          const canMute = !isSelf && msgState.chatType === 'group' && Boolean(m.user_id) && msgState.botIsAdmin && !protectedRole;
          const quoteReady = Boolean(m.message_id) && (!optimisticEntry || sendState === 'sent');
          const actions = [];
          if (canRecall) actions.push(`<button class="msg-action" data-msg-recall="${esc(m.message_id)}" type="button">撤回</button>`);
          if (quoteReady) actions.push(`<button class="msg-action" data-msg-quote="${esc(m.message_id)}" data-msg-user="${esc(m.user_id || '')}" data-msg-refidx="${esc(m.refidx || '')}" data-msg-name="${esc(displayNickname)}" type="button">引用</button>`);
          if (canMute) {
            // 活跃禁言也保留“禁言”入口，便于直接重新设置时长；到期后只显示该入口。
            actions.push(`<button class="msg-action" data-msg-mute="${esc(m.user_id)}" data-msg-mute-name="${esc(displayNickname)}" type="button">禁言</button>`);
            if (isMuted) actions.push(`<button class="msg-action" data-msg-unmute="${esc(m.user_id)}" data-msg-unmute-name="${esc(displayNickname)}" type="button">解除禁言</button>`);
          }
          const rawIdentity = String(m.id || m.message_id || m.messageId || `${m.timestamp || ''}_${m.user_id || ''}`).trim();
          const rawKey = `${msgState.chatId}_${rawIdentity}`;
          if (m.raw_message) {
            actions.push(`<button class="msg-action" data-msg-raw="${esc(rawKey)}" type="button">原始数据</button>`);
            renderedRawKeys.add(rawKey);
            rawStore[rawKey] = m.raw_message;
          }
          const isSelected = msgState.selected.has(m.message_id);
          const multiEnabled = canRecall;
          const sendStateHtml = failedSend
            ? `<button class="msg-send-error" data-msg-retry="${esc(optimisticId)}" type="button" title="发送失败，点击重试" aria-label="发送失败，点击重试">!</button>`
            : '';
          const muteStatusHtml = isMuted
            ? `<span class="msg-mute-countdown" data-msg-mute-expire="${muteExpireTs}">${muteExpireTs ? `禁言剩余 ${formatMuteRemaining(muteExpireTs)}` : '已禁言'}</span>`
            : '';
          html += `<div class="msg-row ${isSelf ? 'self' : ''}${isMuted ? ' muted' : ''}${msgState.multi ? ' multi-mode' : ''}${isSelected ? ' selected' : ''}${multiEnabled ? '' : ' no-multi'}${optimisticEntry ? ' optimistic' : ''}" data-msg-mid="${esc(m.message_id)}" data-msg-uid="${esc(m.user_id)}" data-msg-nick="${esc(displayNickname)}" data-msg-refidx="${esc(m.refidx || '')}" data-msg-role="${esc(memberRole)}" data-msg-self="${isSelf ? '1' : ''}" data-msg-recalled="${recalled ? '1' : ''}" data-msg-optimistic="${esc(optimisticId)}" data-msg-content="${esc(m.content || '')}">
            <span class="msg-pos">
              <span class="msg-multi-check"></span>
              <span class="msg-avatar${isMuted ? ' muted' : ''}">${avatarHtml(av, displayNickname || '?')}</span>
            </span>
            <div class="msg-bubble-wrap"><div class="msg-bubble-name">${esc(displayNickname)}${tags.length ? `<span class="msg-tags">${tags.join('')}</span>` : ''}</div>
              <div class="msg-bubble ${recalled ? 'recalled' : ''}">${quote}${hasInlineMediaText ? inlineMediaHtml : `${contentHtml}${media}`}</div>
              <div class="msg-meta">${esc(fmtMsgTime(m.timestamp))}${!optimisticEntry && m.message_id ? ` · ${esc(m.message_id.slice(0,18))}…` : ''}${muteStatusHtml}${sendStateHtml}</div>
              ${actions.length ? `<div class="msg-actions">${actions.join('')}</div>` : ''}
            </div></div>`;
        });
        body.innerHTML = html;
        Object.keys(rawStore).forEach((key) => {
          if (!renderedRawKeys.has(key)) delete rawStore[key];
        });
        body.querySelectorAll('[data-media-img]').forEach((img) => {
          bindImageInteractions(img);
          img.addEventListener('error', () => {
            const direct = String(img.dataset.mediaDirect || '').trim();
            if (direct && img.dataset.mediaProxied !== '1' && !img.dataset.mediaDirectTried && img.src !== direct) {
              img.dataset.mediaDirectTried = '1';
              img.src = direct;
              img.dataset.lightbox = direct;
              return;
            }
            img.hidden = true;
            const holder = img.closest('.msg-image-link');
            holder?.classList.add('is-broken');
            if (holder && !holder.querySelector('.msg-media-ph')) {
              const placeholder = document.createElement('span');
              placeholder.className = 'msg-media-ph';
              placeholder.textContent = '图片已过期或不可用';
              holder.appendChild(placeholder);
            }
          });
        });
        if (scroll.prepend) {
          body.scrollTop = Math.max(0, Number(scroll.previousTop || 0) + body.scrollHeight - Number(scroll.previousHeight || 0));
        } else if (keepLatestVisible) {
          // 首轮历史请求返回前，任何实时或资料刷新都只能重算隐藏布局，
          // 不能提前显示缓存页并再次触发到底部的可见跳动。
          const deferInitialReveal = initialPositioning && !scroll.revealInitial;
          scrollMsgBodyToBottom(body, msgState.chatId, initialPositioning && !deferInitialReveal);
          clearMsgNewMessages();
        } else {
          body.scrollTop = Math.min(Number(scroll.previousTop || 0), Math.max(0, body.scrollHeight - body.clientHeight));
        }
        msgState.renderedChatId = msgState.chatId;
        body.querySelector('#msg-load-older')?.addEventListener('click', () => loadMsgHistory(true));
        body.querySelectorAll('[data-msg-recall]').forEach((el) => el.addEventListener('click', () => recallMessage(el.dataset.msgRecall)));
        body.querySelectorAll('[data-msg-retry]').forEach((el) => el.addEventListener('click', (event) => { event.preventDefault(); event.stopPropagation(); retryOptimisticSend(el.dataset.msgRetry); }));
        body.querySelectorAll('[data-lightbox]').forEach((img) => img.addEventListener('click', (event) => { event.preventDefault(); openMsgLightbox(img.dataset.lightbox); }));
        body.querySelectorAll('[data-msg-command]').forEach((el) => el.addEventListener('click', () => {
          const command = String(el.dataset.msgCommand || '').trim();
          if (!command || !getComposerEditor()) return;
          insertComposerText(command);
          toast(`已填入 ${command}`);
        }));
        body.querySelectorAll('[data-msg-quote]').forEach((el) => el.addEventListener('click', () => setMsgQuote(el.dataset.msgQuote, el.dataset.msgUser, el.dataset.msgName, el.closest('.msg-row')?.dataset.msgContent || '', el.dataset.msgRefidx || '')));
        body.querySelectorAll('[data-msg-mute]').forEach((el) => el.addEventListener('click', () => { msgState.mute = {member:el.dataset.msgMute, name:el.dataset.msgMuteName}; $('msg-mute-title').textContent = `禁言 ${el.dataset.msgMuteName || el.dataset.msgMute}`; $('msg-mute-modal').hidden = false; }));
        body.querySelectorAll('[data-msg-unmute]').forEach((el) => el.addEventListener('click', () => unmuteMember(el.dataset.msgUnmute, el.dataset.msgUnmuteName)));
        body.querySelectorAll('[data-msg-raw]').forEach((el) => el.addEventListener('click', () => { $('msg-raw-content').textContent = window._msgRaw?.[el.dataset.msgRaw] || '无原始数据'; $('msg-raw-modal').hidden = false; }));
        body.querySelectorAll('.msg-row').forEach((row) => {
          row.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const mid = row.dataset.msgMid;
            const uid = row.dataset.msgUid;
            const nick = row.dataset.msgNick;
            const isSelf = row.dataset.msgSelf === '1';
            const recalled = row.dataset.msgRecalled === '1';
            const content = row.dataset.msgContent || '';
            const refidx = row.dataset.msgRefidx || '';
            const optimistic = msgState.optimisticSends.get(row.dataset.msgOptimistic || '');
            const protectedRole = !isSelf && ['owner', 'admin'].includes(String(row.dataset.msgRole || '').toLowerCase());
            if (msgState.multi) {
              toggleMsgSelect(row, mid);
              return;
            }
            const profile = (msgState.profiles || {})[uid] || {};
            const canMuteRow = !isSelf && msgState.chatType === 'group' && uid && msgState.botIsAdmin && !protectedRole;
            const canRecallRow = Boolean(mid) && !recalled && (isSelf || (msgState.botIsAdmin && !protectedRole));
            const items = [];
            if (!isSelf && msgState.chatType === 'group' && uid) items.push({label:'@' + (nick || 'TA'), action:() => atMember(uid, nick)});
            if (canMuteRow) {
              items.push({label:'禁言', action:() => openMuteDialog(uid, nick)});
              if (msgState.mutes.has(uid)) items.push({label:'解除禁言', action:() => unmuteMember(uid, nick)});
            }
            if (items.length && !isSelf) items.push({sep:true});
            if (mid && (!optimistic || optimistic.status === 'sent')) items.push({label:'引用', action:() => setMsgQuote(mid, uid, nick, content, refidx)});
            if (content) items.push({label:'复制', action:() => copyMsgText(content, row)});
            if (canRecallRow) items.push({label:'撤回', danger:true, action:() => recallMessage(mid)});
            if (mid) items.push({sep:true});
            items.push({label:'多选', action:() => { enterMultiMode(); if (canRecallRow) toggleMsgSelect(row, mid); }});
            if (items.length) showMsgCtx(e.clientX, e.clientY, items);
          });
          row.addEventListener('click', (e) => {
            if (msgState.multi && !e.target.closest('button')) {
              const protectedRole = row.dataset.msgSelf !== '1' && ['owner', 'admin'].includes(String(row.dataset.msgRole || '').toLowerCase());
              const canSel = Boolean(row.dataset.msgMid) && !(row.dataset.msgRecalled === '1') && (row.dataset.msgSelf === '1' || (msgState.botIsAdmin && !protectedRole));
              if (canSel) toggleMsgSelect(row, row.dataset.msgMid);
            }
          });
          row.querySelector('.msg-avatar')?.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const uid = row.dataset.msgUid;
            const nick = row.dataset.msgNick;
            const isSelf = row.dataset.msgSelf === '1';
            if (msgState.multi) return;
            const profileA = (msgState.profiles || {})[uid] || {};
            const protectedRole = !isSelf && ['owner', 'admin'].includes(String(row.dataset.msgRole || profileA.role || '').toLowerCase());
            const canMuteAv = !isSelf && msgState.chatType === 'group' && uid && msgState.botIsAdmin && !protectedRole;
            const items = [];
            if (!isSelf && msgState.chatType === 'group' && uid) items.push({label:'@' + (nick || 'TA'), action:() => atMember(uid, nick)});
            if (canMuteAv) {
              items.push({label:'禁言', action:() => openMuteDialog(uid, nick)});
              if (msgState.mutes.has(uid)) items.push({label:'解除禁言', action:() => unmuteMember(uid, nick)});
            }
            if (items.length) showMsgCtx(e.clientX, e.clientY, items);
          });
        });
      };
      const rememberMsgEvent = (chatId, message) => {
        const fallback = `${message?.ts || message?.timestamp || ''}:${message?.user_id || ''}:${message?.content || ''}`;
        const keys = msgMessageIdentityKeys(message);
        if (!keys.length) keys.push(`fallback:${fallback}`);
        const eventKeys = keys.map((key) => `${chatId}:${key}`);
        if (eventKeys.some((key) => msgState.eventKeys.has(key))) return false;
        eventKeys.forEach((key) => {
          msgState.eventKeys.add(key);
          msgState.eventKeyOrder.push(key);
        });
        while (msgState.eventKeyOrder.length > 1000) {
          const oldest = msgState.eventKeyOrder.shift();
          if (oldest) msgState.eventKeys.delete(oldest);
        }
        return true;
      };
      const scheduleMsgChatRender = () => {
        if (msgState.chatRenderTimer) return;
        msgState.chatRenderTimer = setTimeout(() => {
          msgState.chatRenderTimer = null;
          if ($('page-messages')?.hidden) return;
          renderMsgChats({chats:msgState.chats});
        }, 50);
      };
      const scheduleMsgRealtimeMessageRender = (chatId, toBottom) => {
        if (msgState.realtimeRenderChatId && msgState.realtimeRenderChatId !== chatId) return;
        msgState.realtimeRenderChatId = chatId;
        msgState.realtimeMessageCount += 1;
        msgState.realtimeToBottom = msgState.realtimeToBottom || Boolean(toBottom);
        if (msgState.realtimeMessageTimer) return;
        msgState.realtimeMessageTimer = setTimeout(() => {
          msgState.realtimeMessageTimer = null;
          const count = msgState.realtimeMessageCount;
          const shouldFollow = msgState.realtimeToBottom;
          msgState.realtimeMessageCount = 0;
          msgState.realtimeToBottom = false;
          msgState.realtimeRenderChatId = '';
          if (msgState.chatId !== chatId || $('page-messages')?.hidden) return;
          const body = $('msg-body');
          const previousTop = body?.scrollTop || 0;
          const previousHeight = body?.scrollHeight || 0;
          const followLatest = shouldFollow && msgBodyNearBottom(body);
          renderMsgMessages(
            {...(msgState.historyData || {}), messages:msgState.messages},
            {previousTop, previousHeight, toBottom:followLatest},
          );
          if (!followLatest && count > 0) showMsgNewMessages(count);
        }, 50);
      };
      const cancelMsgRealtimeMessageRender = () => {
        if (msgState.realtimeMessageTimer) {
          clearTimeout(msgState.realtimeMessageTimer);
          msgState.realtimeMessageTimer = null;
        }
        msgState.realtimeMessageCount = 0;
        msgState.realtimeToBottom = false;
        msgState.realtimeRenderChatId = '';
      };
      const applyMsgRealtimeEvent = (payload) => {
        const chatId = String(payload.chat_id || '').trim();
        const message = payload.message && typeof payload.message === 'object' ? {...payload.message} : null;
        if (!chatId || !message) return;
        const messageKey = msgMessageKey(message);
        const recalledIndex = messageKey ? msgState.messages.findIndex((item) => msgMessagesMatch(item, message)) : -1;
        if (msgIsRecalled(message) && recalledIndex >= 0) {
          msgState.messages = msgState.messages.map((item, index) => index === recalledIndex ? {...item, recalled:true} : item);
          if (msgState.chatId === chatId && !$('page-messages')?.hidden) {
            const body = $('msg-body');
            renderMsgMessages(
              {...(msgState.historyData || {}), messages:msgState.messages},
              {previousTop:body?.scrollTop || 0, previousHeight:body?.scrollHeight || 0},
            );
          }
          return;
        }
        msgState.profiles = mergeMsgProfiles(
          {...(msgState.profiles || {}), ...(payload.member_profiles || {})},
          [message],
        );
        const isNewEvent = rememberMsgEvent(chatId, message);
        const existing = msgState.chats.find((chat) => String(chat.chat_id || '') === chatId) || msgState.realtimeChats.get(chatId) || {};
        const chatType = String(payload.chat_type || message.chat_type || existing.chat_type || 'group');
        if (isNewEvent) msgState.historyCache.delete(`${chatType}|${chatId}`);
        const eventTs = Number(payload.last_ts || message.ts || 0) || Math.floor(Date.now() / 1000);
        const isViewing = msgState.chatId === chatId && !$('page-messages')?.hidden;
        const body = $('msg-body');
        const followLatest = isViewing && msgState.pendingNewMessages === 0 && msgBodyNearBottom(body);
        const payloadUnread = Number(payload.unread);
        const fallbackUnread = Math.max(0, Number(existing.unread || 0) + (isNewEvent ? 1 : 0));
        const unread = followLatest
          ? 0
          : (Number.isFinite(payloadUnread) ? Math.max(0, payloadUnread) : fallbackUnread);
        const overlay = {
          ...existing,
          chat_id:chatId,
          chat_type:chatType,
          appid:String(payload.appid || message.appid || existing.appid || ''),
          nickname:existing.nickname || (chatType === 'user' ? String(payload.last_nickname || message.nickname || chatId) : chatId),
          avatar:String(message.avatar || payload.member_profiles?.[String(message.user_id || '').trim()]?.avatar || existing.avatar || '').trim(),
          last_content:replaceMsgMentions(String(payload.last_content || message.content || existing.last_content || '')),
          last_time:String(message.timestamp || existing.last_time || new Date(eventTs * 1000).toISOString()),
          last_ts:eventTs,
          msg_count:Math.max(0, Number(existing.msg_count || 0) + (isNewEvent ? 1 : 0)),
          unread,
        };
        msgState.realtimeChats.set(chatId, overlay);
        if (isNewEvent || !msgState.chats.some((chat) => String(chat.chat_id || '') === chatId)) {
          scheduleMsgChatRender();
        }
        if (!isViewing || !isNewEvent) return;
        const realtimeMessage = {...message, chat_type:chatType, appid:String(payload.appid || message.appid || '')};
        const alreadyRendered = msgState.messages.some((item) => msgMessagesMatch(item, realtimeMessage));
        if (!alreadyRendered) {
          msgState.messages = [...msgState.messages, realtimeMessage];
          scheduleMsgRealtimeMessageRender(chatId, followLatest);
        }
        if (followLatest) markMsgRead(chatId, true);
      };
      const applyMsgGroupStatus = (payload) => {
        const chatId = String(payload?.chat_id || '').trim();
        if (!chatId) return;
        const status = String(payload?.membership_status || 'unknown').trim().toLowerCase();
        const removed = status === 'removed';
        msgState.chats = (msgState.chats || []).map((chat) => String(chat.chat_id || '') === chatId
          ? {...chat, membership_status:status, in_group:!removed}
          : chat);
        if (removed) {
          const localAdmins = getLocalAdminGroups();
          localAdmins.delete(chatId);
          saveLocalAdminGroups(localAdmins);
          msgState.adminByChat.set(chatId, false);
        }
        const overlay = msgState.realtimeChats.get(chatId);
        if (overlay) msgState.realtimeChats.set(chatId, {...overlay, membership_status:status, in_group:!removed});
        if (msgState.chatId === chatId && msgState.chatType === 'group') {
          msgState.chatRemoved = removed;
          $('msg-composer').hidden = removed;
          updateMsgHead({chat_name:(msgState.chats.find((chat) => String(chat.chat_id || '') === chatId)?.nickname || chatId), group_info:{membership_status:status}});
        }
        renderMsgChats({chats:msgState.chats});
      };
      const toggleMsgSelect = (row, mid) => {
        if (!mid) return;
        if (msgState.selected.has(mid)) { msgState.selected.delete(mid); row.classList.remove('selected'); }
        else { msgState.selected.add(mid); row.classList.add('selected'); }
        $('msg-multi-count').textContent = `已选 ${msgState.selected.size} 条`;
      };
      const loadMsgHistory = async (older = false, quiet = false) => {
        if (!msgState.chatId) return;
        if (older && msgState.historyOlderLoading) return;
        if (older) msgState.historyOlderLoading = true;
        $('msg-composer').hidden = msgState.chatRemoved;
        const requestId = Number(msgState[older ? 'historyOlderRequest' : 'historyRequest'] || 0) + 1;
        msgState[older ? 'historyOlderRequest' : 'historyRequest'] = requestId;
        const previousAbort = msgState[older ? 'historyOlderAbort' : 'historyAbort'];
        if (previousAbort) previousAbort.abort();
        const controller = new AbortController();
        msgState[older ? 'historyOlderAbort' : 'historyAbort'] = controller;
        const historyTimeoutId = setTimeout(() => controller.abort(), 18000);
        const requestChatId = msgState.chatId;
        const requestChatType = msgState.chatType;
        const requestIsCurrent = () => requestId === Number(msgState[older ? 'historyOlderRequest' : 'historyRequest'] || 0)
          && requestChatId === msgState.chatId && requestChatType === msgState.chatType;
        const body = $('msg-body');
        const newChat = msgState.renderedChatId !== msgState.chatId;
        const forceInitialBottom = !older && msgState.initialScrollChatId === requestChatId;
        const previousTop = body?.scrollTop || 0;
        const previousHeight = body?.scrollHeight || 0;
        const previousLast = !newChat ? msgMessageKey(msgState.messages[msgState.messages.length - 1]) : '';
        const historyCacheKey = `${requestChatType}|${requestChatId}`;
        try {
          const before = older ? (msgState.messages[0]?.timestamp || '') : '';
          const beforeId = older ? Number(msgState.messages[0]?.id || 0) : 0;
          const data = await api('message/history', {method:'POST', body:JSON.stringify({chat_id:requestChatId, chat_type:requestChatType, before_date:beforeId ? '' : before, before_id:beforeId, limit:msgHistoryPageSize}), signal:controller.signal});
          if (!requestIsCurrent()) return;
          const incoming = mergeMsgRecalledStates(dedupeMsgMessages(data.messages || []));
          const sameRenderedPage = !older && !newChat
            && msgMessageListsEqual(incoming, msgState.messages)
            && Boolean(data.has_more) === Boolean(msgState.historyData?.has_more);
          if (sameRenderedPage) {
            updateMsgHead(data);
            msgState.historyData = {...(msgState.historyData || {}), ...data, messages:incoming};
            msgState.profiles = mergeMsgProfiles(
              {...(msgState.profiles || {}), ...(data.member_profiles || {})},
              incoming,
            );
            cacheMsgHistory(historyCacheKey, {...data, messages:incoming.map((message) => ({...message}))});
            if (forceInitialBottom) {
              msgState.initialScrollChatId = '';
              scrollMsgBodyToBottom(body, requestChatId, true);
            }
            return;
          }
          let newCount = 0;
          if (!older && previousLast) {
            const previousIndex = incoming.findIndex((message) => msgMessageKey(message) === previousLast);
            newCount = previousIndex >= 0 ? Math.max(0, incoming.length - previousIndex - 1) : (incoming.length ? 1 : 0);
          }
          const renderTop = body?.scrollTop ?? previousTop;
          const renderHeight = body?.scrollHeight ?? previousHeight;
          const renderNearBottom = forceInitialBottom || newChat || msgBodyNearBottom(body);
          // 轮询可能在上翻页完成后才返回；保留当前已展开的更早消息，避免刷新把它们截掉。
          const currentMessages = Array.isArray(msgState.messages) ? msgState.messages : [];
          const preserveLoadedHistory = !older && !newChat && currentMessages.length > incoming.length;
          msgState.messages = older
            ? dedupeMsgMessages([...incoming, ...currentMessages])
            : (preserveLoadedHistory ? dedupeMsgMessages([...currentMessages, ...incoming]) : incoming);
          renderMsgMessages(
            {...data, messages: msgState.messages},
            {
              prepend:older,
              previousTop:renderTop,
              previousHeight:renderHeight,
              toBottom:!older && renderNearBottom,
              revealInitial: forceInitialBottom,
            },
          );
          if (forceInitialBottom) {
            msgState.initialScrollChatId = '';
          }
          cacheMsgHistory(historyCacheKey, {
            ...data,
            messages: msgState.messages.map((message) => ({...message})),
          });
          if (!older && !renderNearBottom && newCount > 0) showMsgNewMessages(newCount);
          // 首次打开会话获取一次群内权限；继续向上分页时不重复请求官方接口。
          if (!older) {
            void loadGroupRoles(true).then(() => loadMuteStates(true));
          }
        } catch (error) {
          if (!requestIsCurrent()) return;
          if (forceInitialBottom) {
            // 首轮请求失败时仍展示缓存/空状态，不能让定位期间的隐藏样式残留。
            msgState.initialScrollChatId = '';
            body.classList.remove('msg-positioning');
            body.scrollTop = body.scrollHeight;
          }
          if (error.name === 'AbortError') return;
          if (error.status === 401) showAuthError(error); else toast(error.message);
        }
        finally {
          clearTimeout(historyTimeoutId);
          const abortKey = older ? 'historyOlderAbort' : 'historyAbort';
          if (msgState[abortKey] === controller) msgState[abortKey] = null;
          if (older) msgState.historyOlderLoading = false;
        }
      };
      const loadGroupRoles = async (throttled = false) => {
        if (msgState.chatType !== 'group' || !msgState.chatId) return;
        const requestChatId = String(msgState.chatId);
        const requestChatType = String(msgState.chatType);
        const now = Date.now();
        if (throttled && msgState.lastRolesChatId === requestChatId && msgState.lastRolesAt && now - msgState.lastRolesAt < msgRoleRetryMs) return;
        const requestToken = Number(msgState.adminRequestToken || 0) + 1;
        msgState.adminRequestToken = requestToken;
        msgState.lastRolesAt = now; msgState.lastRolesChatId = requestChatId;
        msgState.adminCheckedAt.set(requestChatId, now);
        try {
          const data = await api('message/group-roles', {method:'POST', body:JSON.stringify({chat_id:requestChatId})});
          if (requestToken !== Number(msgState.adminRequestToken || 0) || msgState.chatId !== requestChatId || msgState.chatType !== requestChatType) return;
          const removed = data?.membership_status === 'removed' || data?.bot_in_group === false;
          const current = msgState.chats.find((chat) => String(chat.chat_id || '') === requestChatId);
          if (removed) {
            if (current) {
              current.membership_status = 'removed';
              current.in_group = false;
              current.membership_checked_at = Number(data?.membership_checked_at || Math.floor(Date.now() / 1000));
            }
            msgState.chatRemoved = true;
            $('msg-composer').hidden = true;
            msgState.adminByChat.set(requestChatId, false);
            updateMsgHead({chat_name:current?.nickname || requestChatId, group_info:{membership_status:'removed'}});
            renderMsgChats({chats:msgState.chats});
            return;
          }
          const role = String(data?.bot_role || '').trim().toLowerCase();
          if (!['owner', 'admin', 'member'].includes(role)) return;
          if (current) { current.membership_status = 'active'; current.in_group = true; }
          if (current) current.membership_checked_at = Number(data?.membership_checked_at || Math.floor(Date.now() / 1000));
          const isAdmin = Boolean(data.bot_is_admin);
          msgState.adminByChat.set(requestChatId, isAdmin);
          msgState.adminScanFailures.delete(requestChatId);
          const localAdmins = getLocalAdminGroups();
          if (isAdmin) localAdmins.add(requestChatId);
          else localAdmins.delete(requestChatId);
          saveLocalAdminGroups(localAdmins);
          msgState.botIsAdmin = isAdmin;
          if (current) current.is_admin = isAdmin;
          updateMsgAdminTag();
        }
        catch (error) {
          if (requestToken !== Number(msgState.adminRequestToken || 0) || msgState.chatId !== requestChatId || msgState.chatType !== requestChatType) return;
          msgState.adminScanFailures.set(requestChatId, Date.now());
          updateMsgAdminTag();
        }
      };
      const markLocalMessageRecalled = (messageId) => {
        const id = String(messageId || '').trim();
        if (!id) return;
        let changed = false;
        msgState.messages = msgState.messages.map((message) => {
          if (String(message?.message_id || '') !== id || message.recalled) return message;
          changed = true;
          return {...message, recalled:true};
        });
        if (!changed || $('page-messages')?.hidden) return;
        const body = $('msg-body');
        renderMsgMessages(
          {...(msgState.historyData || {}), messages:msgState.messages},
          {previousTop:body?.scrollTop || 0, previousHeight:body?.scrollHeight || 0},
        );
      };
      const recallMessage = async (messageId) => {
        if (!confirm('确定撤回这条消息吗？发送超过 2 分钟的消息不可撤回。')) return;
        try { await api('message/recall', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, message_id:messageId})}); markLocalMessageRecalled(messageId); msgState.historyCache.delete(`${msgState.chatType}|${msgState.chatId}`); toast('撤回成功'); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const refreshGroupInfo = async () => {
        if (!msgState.chatId) return;
        try { const data = await api('message/group-info/refresh', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId})}); msgState.historyCache.delete(`${msgState.chatType}|${msgState.chatId}`); toast(data.group_name ? `群信息已刷新：${data.group_name}${data.member_num ? `（成员 ${data.member_num} 人）` : ''}` : (data.member_num ? `群信息已刷新：成员 ${data.member_num} 人` : '群信息已刷新')); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const showRemarkDialog = async () => {
        if (!msgState.chatId) return;
        let data = {}; try { data = await api('message/remarks', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, action:'get'})}); } catch (error) { data = {}; }
        $('msg-remark-name').value = data.remark || '';
        $('msg-remark-qq').value = data.group_qq || '';
        $('msg-remark-modal').hidden = false;
      };
      const saveRemark = async () => {
        const remark = $('msg-remark-name').value.trim();
        const groupQQ = $('msg-remark-qq').value.trim();
        try { await api('message/remarks', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, remark, group_qq:groupQQ})}); msgState.historyCache.delete(`${msgState.chatType}|${msgState.chatId}`); toast('备注已保存'); $('msg-remark-modal').hidden = true; loadMsgChats(true); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const deleteRemark = async () => {
        if (!confirm('确定删除该会话的备注和群号吗？')) return;
        try { await api('message/remarks', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, action:'delete'})}); msgState.historyCache.delete(`${msgState.chatType}|${msgState.chatId}`); toast('备注已删除'); $('msg-remark-modal').hidden = true; loadMsgChats(true); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const sendMessage = () => {
        if (msgState.chatRemoved) return toast('你已被移除群聊');
        const hasImage = composerHasImage();
        const hasMedia = composerHasMedia();
        const editorText = getComposerText().trim();
        const imageBefore = '';
        const imageAfter = '';
        const content = editorText;
        const customId = $('msg-custom-id')?.value.trim() || '';
        const payload = { chat_id:msgState.chatId, chat_type:msgState.chatType, msg_type:hasImage ? 'text' : (hasMedia ? 'media' : msgState.sendType), content, send_mode:msgState.sendMode, custom_id:customId, quote_message_id:msgState.quote?.id || '', quote_message_refidx:msgState.quote?.refidx || '', image_url:msgState.pastedImageSource || '', image_before:imageBefore, image_after:imageAfter, image_marker:hasImage ? composerImageMarker : '' };
        if (hasMedia) {
          if (msgState.mediaFile) payload.media_file = msgState.mediaFile;
          else payload.media_data = msgState.mediaData;
          payload.media_name = msgState.mediaName;
          payload.media_file_type = msgState.mediaType;
          payload.media_mime = msgState.mediaMime;
          if (content) payload.media_text = content;
        } else if (msgState.sendType === 'media' && !hasImage) {
          payload.media_file_type = Number($('msg-media-type')?.value || 1);
          payload.media = $('msg-media-path')?.value.trim() || '';
          payload.media_url = $('msg-media-url')?.value.trim() || '';
          const mediaText = $('msg-media-text')?.value.trim() || '';
          if (mediaText) payload.media_text = mediaText;
          if (!payload.media && !payload.media_url && !hasImage) return toast('请填写媒体文件路径或 URL');
        }
        if (msgState.pastedImage) { payload.image_data = msgState.pastedImage; }
        if (msgState.pastedImageFile) { payload.image_file = msgState.pastedImageFile; }
        if (msgState.sendType === 'ark') {
          payload.ark_template_id = $('msg-ark-template')?.value || '24';
          const fields = {};
          document.querySelectorAll('#msg-extra [data-ark-field]').forEach((el) => { const v = el.value.trim(); if (v) fields[el.dataset.arkField] = v; });
          payload.ark_fields = fields;
          payload.ark_list = $('msg-ark-list')?.value.trim() || '';
        }
        if (msgState.sendType === 'card') {
          payload.card = { title: $('msg-card-title')?.value.trim() || '', description: $('msg-card-desc')?.value.trim() || '', pic_url: $('msg-card-pic')?.value.trim() || '', url: $('msg-card-url')?.value.trim() || '' };
          if (!payload.card.title) return toast('请填写卡片标题');
        }
        if (!content && !hasImage && !hasMedia && !['media','ark','card'].includes(msgState.sendType)) return toast('请输入消息内容');
        const entry = createOptimisticSend(payload);
        // 先完成本地发送事务，输入框立即恢复可用；网络请求在后台运行。
        resetComposer();
        renderOptimisticMessages(entry.chatId);
        void finishOptimisticSend(entry);
      };
      const renderMsgExtra = () => {
        const extra = $('msg-extra'); const type = msgState.sendType;
        if (type === 'media') { extra.hidden = false; extra.innerHTML = `<input id="msg-media-type" type="number" min="1" max="4" value="1" title="1图片 2视频 3语音 4文件"><input id="msg-media-path" type="text" placeholder="本地文件路径（服务器）"><input id="msg-media-url" type="text" placeholder="或媒体 URL"><input type="text" placeholder="媒体说明（可选，显示在消息中）" id="msg-media-text">`; }
        else if (type === 'ark') { extra.hidden = false; extra.innerHTML = `<select id="msg-ark-template"><option value="23">23 链接列表</option><option value="24" selected>24 文本卡片</option><option value="37">37 大图卡片</option></select><input data-ark-field="#DESC#" type="text" placeholder="#DESC# 描述"><input data-ark-field="#PROMPT#" type="text" placeholder="#PROMPT# 提示"><input data-ark-field="#TITLE#" type="text" placeholder="#TITLE# 标题"><input data-ark-field="#METADESC#" type="text" placeholder="#METADESC# 元描述"><input data-ark-field="#IMG#" type="text" placeholder="#IMG# 图片URL"><input data-ark-field="#LINK#" type="text" placeholder="#LINK# 跳转链接"><input data-ark-field="#SUBTITLE#" type="text" placeholder="#SUBTITLE# 副标题"><textarea id="msg-ark-list" class="msg-textarea" style="min-height:52px" placeholder="23 模板列表：每行 描述|链接"></textarea>`; }
        else if (type === 'card') { extra.hidden = false; extra.innerHTML = `<input id="msg-card-title" type="text" placeholder="卡片标题"><input id="msg-card-desc" type="text" placeholder="卡片描述"><input id="msg-card-pic" type="text" placeholder="图片 URL"><input id="msg-card-url" type="text" placeholder="跳转 URL">`; }
        else { extra.hidden = true; extra.innerHTML = ''; }
      };
      $('msg-filter').querySelectorAll('[data-msg-filter]').forEach((el) => el.addEventListener('click', () => { $('msg-filter').querySelectorAll('[data-msg-filter]').forEach((x) => x.classList.toggle('active', x === el)); msgState.filter = el.dataset.msgFilter; msgState.page = 1; loadMsgChats(true); }));
      $('msg-search-btn').addEventListener('click', () => { msgState.search = $('msg-search-input').value.trim(); msgState.page = 1; loadMsgChats(true); });
      $('msg-search-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') { msgState.search = e.target.value.trim(); msgState.page = 1; loadMsgChats(true); } });
      $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((el) => el.addEventListener('click', () => { $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((x) => x.classList.toggle('active', x === el)); msgState.sendType = el.dataset.msgType; renderMsgExtra(); }));
      $('msg-send-mode').addEventListener('change', (e) => { msgState.sendMode = e.target.value; $('msg-custom-id').hidden = !(msgState.sendMode === 'custom_msg_id' || msgState.sendMode === 'custom_event_id'); });
      $('msg-send').addEventListener('click', sendMessage);
      const handleComposerKeydown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey && !e.isComposing && e.keyCode !== 229) {
          e.preventDefault();
          sendMessage();
        }
      };
      document.querySelectorAll('#msg-editor').forEach((node) => {
        node.addEventListener('keydown', handleComposerKeydown);
        node.addEventListener('keyup', saveComposerSelection);
        node.addEventListener('mouseup', saveComposerSelection);
        node.addEventListener('input', () => { syncComposerImageState(); saveComposerSelection(); });
      });
      const handleComposerPaste = (e) => {
        const items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        saveComposerSelection();
        for (const item of items) {
          if (item.type && item.type.indexOf('image/') === 0) {
            const file = item.getAsFile();
            if (!file) continue;
            const reader = new FileReader();
            reader.onload = () => {
              setComposerImage(reader.result, '', reader.result, file);
              toast('已粘贴图片，可继续输入文字后发送');
            };
            reader.readAsDataURL(file);
            e.preventDefault();
            return;
          }
        }
        const html = e.clipboardData.getData('text/html') || '';
        const plain = e.clipboardData.getData('text/plain') || '';
        let pastedSource = '';
        try {
          const parsed = new DOMParser().parseFromString(html, 'text/html');
          pastedSource = safeImageSource(parsed.querySelector('img')?.getAttribute('src') || '');
        } catch (_) {}
        if (!pastedSource && /^data:image\//i.test(plain.trim())) pastedSource = safeImageSource(plain.trim());
        if (!pastedSource) return;
        e.preventDefault();
        if (pastedSource.startsWith('data:image/')) {
          const file = dataUrlToFile(pastedSource);
          setComposerImage(pastedSource, '', pastedSource, file);
          toast('已粘贴图片，可单独发送或继续输入文字');
          return;
        }
        const proxy = mediaProxyUrl(pastedSource, 'image') || pastedSource;
        void fetchImageBlob(proxy)
          .then((blob) => blobToDataUrl(blob))
          .then((dataUrl) => {
            setComposerImage(dataUrl, '', dataUrl, dataUrlToFile(dataUrl));
            toast('已粘贴图片，可单独发送或继续输入文字');
          })
          .catch(() => {
            setComposerImage('', pastedSource, proxy);
            toast('已粘贴图片，可单独发送或继续输入文字');
          });
      };
      document.querySelectorAll('#msg-editor').forEach((node) => node.addEventListener('paste', handleComposerPaste));
      const msgInputBox = $('msg-input-box');
      msgInputBox?.addEventListener('dragover', (event) => {
        const types = Array.from(event.dataTransfer?.types || []);
        if (!types.includes('Files') && !types.includes('application/x-mantou-image') && !types.includes('text/uri-list')) return;
        event.preventDefault();
        event.stopPropagation();
        event.dataTransfer.dropEffect = 'copy';
        msgInputBox.classList.add('drag-over');
      });
      msgInputBox?.addEventListener('dragleave', (event) => {
        if (event.relatedTarget && msgInputBox.contains(event.relatedTarget)) return;
        msgInputBox.classList.remove('drag-over');
      });
      msgInputBox?.addEventListener('drop', (event) => {
        event.preventDefault();
        event.stopPropagation();
        msgInputBox.classList.remove('drag-over');
        saveComposerSelection();
        const transfer = event.dataTransfer;
        const droppedFile = transfer?.files?.[0];
        if (droppedFile) {
          if (String(droppedFile.type || '').toLowerCase().startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = () => setComposerImage(String(reader.result || ''), '', String(reader.result || ''), droppedFile);
            reader.onerror = () => toast('图片读取失败，请重试');
            reader.readAsDataURL(droppedFile);
          } else {
            readComposerMediaFile(droppedFile, String(droppedFile.type || '').toLowerCase().startsWith('video/') ? 2 : 4);
          }
          return;
        }
        const custom = transfer?.getData('application/x-mantou-image') || '';
        const uri = transfer?.getData('text/uri-list') || transfer?.getData('text/plain') || '';
        const source = String(custom || uri).split(/\r?\n/).map((value) => value.trim()).find((value) => value && !value.startsWith('#')) || '';
        void attachDroppedImage(source);
      });
      const clearMsgImage = () => {
        getComposerEditor()?.querySelector('[data-composer-image="1"]')?.remove();
        msgState.pastedImage = null;
        msgState.pastedImageFile = null;
        msgState.pastedImageSource = '';
        $('msg-input-box')?.classList.remove('has-inline-image');
        getComposerEditor()?.focus();
      };
      $('msg-img-pick').addEventListener('mousedown', saveComposerSelection);
      $('msg-img-pick').addEventListener('click', () => $('msg-img-file').click());
      $('msg-img-file').addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        if (!file.type.startsWith('image/')) { toast('请选择图片文件'); e.target.value = ''; return; }
        const reader = new FileReader();
        reader.onload = () => { setComposerImage(reader.result, '', reader.result, file); };
        reader.readAsDataURL(file);
        e.target.value = '';
      });
      $('msg-video-file').addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        readComposerMediaFile(file, 2);
      });
      $('msg-attachment-file').addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        readComposerMediaFile(file, 4);
      });
      $('msg-media-clear').addEventListener('click', clearComposerMedia);
      const maybeLoadOlderMessages = () => {
        const body = $('msg-body');
        if (!body || body.scrollTop > 20 || msgState.historyOlderLoading || !msgState.historyData?.has_more) return;
        loadMsgHistory(true);
      };
      const msgChatsNode = $('msg-chats');
      msgChatsNode?.addEventListener('scroll', () => {
        msgState.chatListScrollActive = true;
        if (msgState.chatListScrollTimer) clearTimeout(msgState.chatListScrollTimer);
        msgState.chatListScrollTimer = setTimeout(() => {
          msgState.chatListScrollTimer = null;
          msgState.chatListScrollActive = false;
          const pending = msgState.chatListPendingData;
          msgState.chatListPendingData = null;
          if (pending) renderMsgChats(pending);
        }, 140);
      }, {passive:true});
      $('msg-body').addEventListener('scroll', () => {
        maybeLoadOlderMessages();
        if (!msgBodyNearBottom($('msg-body'))) return;
        const activeChat = msgState.chats.find((chat) => String(chat.chat_id || '') === String(msgState.chatId || ''));
        const shouldRead = msgState.pendingNewMessages > 0 || Number(activeChat?.unread || 0) > 0;
        clearMsgNewMessages();
        if (shouldRead) markMsgRead(undefined, true);
      });
      $('msg-new-messages').addEventListener('click', () => scrollMsgToBottom('smooth'));
      $('msg-reload').addEventListener('click', () => { loadMsgChats(true); if (msgState.chatId) loadMsgHistory(); });
      $('msg-multi-recall').addEventListener('click', recallSelected);
      $('msg-multi-cancel').addEventListener('click', () => { exitMultiMode(); });
      $('msg-ad-switch').addEventListener('click', toggleGroupAdSwitch);
      $('msg-refresh-info').addEventListener('click', refreshGroupInfo);
      $('msg-remark').addEventListener('click', showRemarkDialog);
      $('msg-quote-clear').addEventListener('click', () => { msgState.quote = null; $('msg-quote-preview').hidden = true; });
      $('msg-raw-close').addEventListener('click', () => { $('msg-raw-modal').hidden = true; });
      $('msg-raw-modal').addEventListener('click', (e) => { if (e.target === $('msg-raw-modal')) $('msg-raw-modal').hidden = true; });
      $('msg-mute-presets').querySelectorAll('[data-mute-min]').forEach((el) => el.addEventListener('click', () => { $('msg-mute-presets').querySelectorAll('[data-mute-min]').forEach((x) => x.classList.toggle('active', x === el)); msgState.muteMinutes = Number(el.dataset.muteMin); $('msg-mute-custom').value = ''; }));
      $('msg-mute-custom').addEventListener('input', (e) => { const raw = Number(e.target.value); if (!Number.isFinite(raw) || raw < 1) return; const days = Math.min(30, Math.floor(raw)); e.target.value = String(days); msgState.muteMinutes = days * 1440; });
      $('msg-mute-cancel').addEventListener('click', () => { $('msg-mute-modal').hidden = true; });
      $('msg-remark-cancel').addEventListener('click', () => { $('msg-remark-modal').hidden = true; });
      $('msg-remark-save').addEventListener('click', saveRemark);
      $('msg-remark-delete').addEventListener('click', deleteRemark);
      $('msg-mute-confirm').addEventListener('click', async () => { if (!msgState.mute.member) return; const custom = $('msg-mute-custom'); const rawDays = Number(custom?.value); if (Number.isFinite(rawDays) && rawDays >= 1) { const days = Math.min(30, Math.floor(rawDays)); if (custom) custom.value = String(days); msgState.muteMinutes = days * 1440; } try { await api('message/group-member/mute', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, member_openid:msgState.mute.member, minutes:Math.min(43200, Math.max(1, Number(msgState.muteMinutes) || 30))})}); toast('禁言成功'); $('msg-mute-modal').hidden = true; void loadMuteStates(true); } catch (error) { toast(error.message); } });
      bindMsgLayoutControls();
      void loadMsgLayout();
      // QQ 官方群消息通过 Gateway 事件接收，没有可轮询的群历史 REST 接口。
      // 这里仅低频校准本地消息记录，事件通道在线时也能修复偶发漏事件，
      // 不会额外消耗 QQ 官方消息或 bot_state 请求额度。
      const msgPollOfflineMs = 15000;
      const msgPollOnlineMs = 60000;
      let msgLastPollAt = 0;
      let msgPollPromise = null;
      const pollLocalMessages = () => {
        const page = document.querySelector('#page-messages');
        if (!page || page.hidden || document.visibilityState === 'hidden' || msgPollPromise) return;
        const now = Date.now();
        const interval = msgState.eventTransport ? msgPollOnlineMs : msgPollOfflineMs;
        if (now - msgLastPollAt < interval) return;
        msgLastPollAt = now;
        const history = msgState.chatId ? loadMsgHistory(false, true) : Promise.resolve();
        const mutes = msgState.chatType === 'group' && msgState.chatId ? loadMuteStates() : Promise.resolve();
        msgPollPromise = Promise.allSettled([loadMsgChats(), history, mutes]).finally(() => { msgPollPromise = null; });
      };
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { msgLastPollAt = 0; pollLocalMessages(); } });
      msgState.timer = setInterval(pollLocalMessages, 5000);
      msgState.muteTimer = setInterval(() => {
        updateMuteCountdowns();
        if (msgState.chatType === 'group' && msgState.chatId) void loadMuteStates();
      }, 1000);

      setView(viewFromUrl(), false); load();
    })();
  """
