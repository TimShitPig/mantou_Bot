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
      const updateThemeControl = (theme) => {
        const select = $('theme-select');
        if (select && select.value !== theme) select.value = theme;
        const toggle = $('theme-toggle');
        if (!toggle) return;
        const dark = theme === 'dark';
        const label = dark ? '切换到浅色模式' : '切换到深色模式';
        toggle.setAttribute('aria-pressed', String(dark));
        toggle.setAttribute('aria-label', label);
        toggle.title = label;
        const icon = toggle.querySelector('.theme-control-icon');
        if (icon) icon.textContent = dark ? '☀' : '☾';
      };
      const applyTheme = (preference = readThemePreference(), persist = true) => {
        const next = preference === 'dark' ? 'dark' : 'light';
        const theme = next;
        const previous = document.documentElement.dataset.theme;
        const switching = Boolean(previous && previous !== theme);
        if (switching) {
          document.documentElement.classList.remove('theme-switching');
          void document.documentElement.offsetWidth;
          document.documentElement.classList.add('theme-switching');
        }
        document.documentElement.dataset.themePreference = next;
        document.documentElement.dataset.theme = theme;
        updateThemeMeta(theme);
        if (persist) { try { localStorage.setItem(themeStorageKey, next); } catch (_) {} }
        updateThemeControl(next);
        if (switching) {
          setTimeout(() => document.documentElement.classList.remove('theme-switching'), 320);
        }
      };
      applyTheme(readThemePreference(), false);
      $('theme-select')?.addEventListener('change', (event) => applyTheme(event.target.value));
      $('theme-toggle')?.addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
      const views = {
        dashboard: ['控制台', '查看机器人和小说服务的实时状态'],
        bot: ['机器人配置', '查看安全摘要、监听地址和访问策略'],
        novels: ['小说功能', '管理全局开关、测试模式和平台开关'],
        pans: ['网盘配置', '管理多网盘分享和账号安全摘要'],
        runtime: ['运行状态', '查看服务器、数据库和插件实时指标'],
        help: ['帮助指令', '查看机器人当前支持的聊天指令'],
         settings: ['系统设置', '查看状态并编辑数据库连接参数'],
        messages: ['消息记录', '查看群聊和私聊消息，回复、发送和撤回消息'],
      };
      let snapshot = null;
      let activeView = null;
      let activePanTab = null;
      let activePanObject = null;
      let quarkWebScanId = '';
      let quarkWebScanTimer = null;
      let quarkWebScanGeneration = 0;
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
        if (!response.ok || !data.ok) { const error = new Error(data.message || data.error || '请求失败'); error.status = response.status; error.data = data; throw error; }
        return data;
      };
      const stopQuarkWebScan = async () => {
        const scanId = quarkWebScanId;
        quarkWebScanId = '';
        quarkWebScanGeneration += 1;
        clearTimeout(quarkWebScanTimer);
        quarkWebScanTimer = null;
        if (scanId) {
          try { await api(`pan-accounts/${encodeURIComponent('夸克')}/scan/${encodeURIComponent(scanId)}`, {method:'DELETE'}); } catch (_) {}
        }
        const card = document.querySelector(`[data-pan-card="${CSS.escape('夸克')}"]`);
        const image = card?.querySelector('[data-quark-scan-image]');
        if (image) { image.removeAttribute('src'); image.hidden = true; }
        const status = card?.querySelector('[data-quark-scan-status]');
        if (status) status.textContent = '获取二维码后使用夸克 App 扫描。';
        const cancel = card?.querySelector('[data-quark-scan-cancel]');
        if (cancel) cancel.hidden = true;
        const start = card?.querySelector('[data-quark-scan-start]');
        if (start) { start.disabled = false; start.textContent = '获取二维码'; }
      };
      window.addEventListener('pagehide', () => {
        if (!quarkWebScanId) return;
        fetch(`/api/pan-accounts/${encodeURIComponent('夸克')}/scan/${encodeURIComponent(quarkWebScanId)}`, {method:'DELETE', credentials:'same-origin', keepalive:true}).catch(() => {});
      });
      const viewFromUrl = () => { const current = new URLSearchParams(location.search).get('view'); return views[current] ? current : 'dashboard'; };
      const setView = (view, push = true, resetScroll = (view !== activeView)) => {
        const next = views[view] ? view : 'dashboard';
        if (groupSettingsState.mutating && next !== activeView) return toast('正在更新本群设置，请稍候');
        if (next !== 'messages' && activeView === 'messages') { closeComposerMentionPicker(); closeGroupSettings(); stopMsgGroupSnapshots(); }
        const previousView = activeView;
        if (previousView === 'pans' && next !== 'pans') void stopQuarkWebScan();
        if (previousView === 'bot' && next !== 'bot') leaveQQReader();
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
          if (previousView !== 'messages') {
            msgState.chatListTopPending = true;
            const chatList = $('msg-chats');
            if (chatList) chatList.scrollTop = 0;
            loadMsgChats();
          }
          if (previousView !== 'messages' && msgState.chatId) loadMsgHistory();
        }
        else if (msgState.eventSource || msgState.eventSocket || msgState.eventReconnect) closeMsgEvents();
        if (resetScroll) {
          const scrollContainer = document.querySelector('.main');
          if (scrollContainer) scrollContainer.scrollTop = 0;
          window.scrollTo({top:0, behavior:'auto'});
        }
        if (next === 'pans') void refreshQuarkProfilesSilently();
        if (next === 'bot' && previousView !== 'bot' && qqReader.auth) void loadQQReaderAccounts().catch((error) => { if (error.status === 401) showAuthError(error); });
      };
      const switchHtml = (key, enabled, editable, label) => `<button class="switch ${enabled ? 'on' : ''}" data-switch="${esc(key)}" data-enabled="${enabled}" ${editable ? '' : 'disabled'} aria-label="${esc(label)}" aria-pressed="${enabled}"><span></span></button>`;
      const platformGlyph = (name) => ({'番茄':'番','七猫':'猫','书旗':'旗','追书':'追','QQ阅读':'阅','QQ浏览器':'浏','得间':'得','点众':'众','盐言':'盐','塔读':'塔','百度':'度','小米':'米','晋江':'晋','宜搜':'搜','米读':'读','猫眼':'眼','酷我':'酷','酷匠':'匠','连城':'城','菠萝包':'菠'}[name] || String(name || '书').slice(0, 1));
      const categoryOrder = ['basic_settings', 'help_web_settings'];
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
          // 展示教程尺寸、端口和登录凭据；监听地址/域名继续由后端读取。
          if (field.category === 'help_web_settings') return ['welcome_tutorial_image_width', 'help_web_port', 'help_web_admin_username', 'help_web_admin_password'].includes(field.key);
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
          const hint = field.secret ? (field.configured ? '已配置，留空表示不修改' : (field.hint || '敏感值只写入，不在页面回显')) : String(field.hint || '');
          if (field.kind === 'admin_list') return `<div class="config-field full"><label for="${inputId}">${label}</label><textarea id="${inputId}" data-config-field="${esc(field.key)}" ${editable ? '' : 'disabled'} placeholder="每行一个 QQ 号">${esc(safeFieldValue(field))}</textarea><small>${hint || '共 ' + esc(field.count || 0) + ' 个管理员'}</small></div>`;
          if (field.kind === 'select') return `<div class="config-field"><label for="${inputId}">${label}</label><select id="${inputId}" data-config-field="${esc(field.key)}" ${editable ? '' : 'disabled'}>${(field.options || []).map((option) => `<option value="${esc(option)}" ${String(option) === String(field.value ?? '') ? 'selected' : ''}>${esc(option)}</option>`).join('')}</select><small>${hint}</small></div>`;
          const type = field.secret ? 'password' : (field.kind === 'number' ? 'number' : 'text');
          const placeholder = field.placeholder || (field.secret && field.configured ? '已配置，输入新密码可替换' : (field.secret ? '留空不修改' : ''));
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
       const renderDatabaseStatus = (database = {}) => {
        const status = String(database.status || '--');
        const statusNode = $('settings-db-status');
        const nameNode = $('settings-db-name');
        if (statusNode) { statusNode.textContent = status; statusNode.classList.toggle('good', status === '正常'); }
        if (nameNode) nameNode.textContent = String(database.name || '--');
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
        try {
          const result = await api('config', {method:'POST', body:JSON.stringify({fields})});
          if (message) { message.textContent = result.message || '配置已保存'; message.className = 'config-message ok'; }
          toast(result.message || '配置已保存');
          if (editor.id === 'database-config-editor' && result.auth_changed) {
            if (message) message.textContent = '数据库配置已保存。当前登录已结束，请稍候重新登录；重载插件后新连接参数生效。';
            window.setTimeout(() => location.reload(), 1800);
            return;
          }
          await load();
        }
         catch (error) { if (error.status === 401) showAuthError(error); if (message) { message.textContent = error.message; message.className = 'config-message error'; } else toast(error.message); }
      };
      const panAccountRows = (item, editable) => {
         const accounts = Array.isArray(item.account_summary) ? item.account_summary : [];
         if (!accounts.length) return '<div class="empty pan-object-empty">暂无登录账号</div>';
         return accounts.map((account, position) => {
           const index = Number(account?.index) > 0 ? Number(account.index) : position + 1;
           const profileName = account?.name && account.name !== '未命名账号' ? account.name : '';
           const name = profileName || '未命名账号';
           const enabled = account?.enabled !== false;
           const isDefault = index === Number(item.default_account || item.selected_account || 0);
           const avatar = panAccountAvatarHtml(account, name);
           const accountMetadata = item.key === '夸克'
             ? panAccountMetaHtml(account)
             : '';
           return `<article class="pan-object-card pan-account-object ${enabled ? '' : 'is-disabled'}"><button class="pan-object-open pan-account-object-main" type="button" data-pan-object-open="${esc(item.key)}" data-pan-object-type="account" data-index="${esc(index)}" aria-label="打开${esc(item.name)}账号${esc(index)}">${avatar}<span class="pan-object-copy"><strong>${esc(name)}</strong>${accountMetadata}</span><span class="pan-object-arrow" aria-hidden="true">›</span></button><div class="pan-account-card-actions"><span class="tag ${enabled ? 'ok' : 'off'}">${enabled ? '运行中' : '已停用'}</span>${isDefault ? '<span class="tag ok pan-account-default-tag">默认账号</span>' : enabled ? `<button class="pan-account-default" type="button" data-pan-account-default="${esc(item.key)}" data-index="${esc(index)}" ${editable ? '' : 'disabled'}>设为默认</button>` : ''}<button class="switch pan-account-switch ${enabled ? 'on' : ''}" type="button" data-pan-account-enable="${esc(item.key)}" data-index="${esc(index)}" data-enabled="${enabled}" ${editable ? '' : 'disabled'} aria-label="${enabled ? '停用' : '启用'}${esc(item.name)}账号${esc(index)}" aria-pressed="${enabled}"><span></span></button></div></article>`;
         }).join('');
       };
       const panAccountAvatarHtml = (account, name) => {
         const raw = safeMediaUrl(String(account?.avatar_url || '').trim());
         let avatar = '';
         try {
           const url = new URL(raw, location.href);
           if (url.protocol === 'https:' && url.hostname === 'image.quark.cn') avatar = url.href;
         } catch (_) {}
         const initial = String(name || '未命名账号').trim().slice(0, 1) || '?';
         return `<span class="pan-account-avatar" aria-hidden="true"><span>${esc(initial)}</span>${avatar ? `<img src="${esc(avatar)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}</span>`;
       };
       const formatPanBytes = (value) => {
         if (value === null || value === undefined || value === '') return '未获取';
         let bytes = Number(value);
         if (!Number.isFinite(bytes) || bytes < 0) return '未获取';
         const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
         let unit = 0;
         while (bytes >= 1024 && unit < units.length - 1) { bytes /= 1024; unit += 1; }
         return `${unit === 0 || bytes >= 10 ? bytes.toFixed(0) : bytes.toFixed(1)} ${units[unit]}`;
       };
       const panAccountSpaceText = (account) => `${formatPanBytes(account?.space_used_bytes)} / ${formatPanBytes(account?.space_total_bytes)}`;
       const panAccountMetaHtml = (account) => `<span class="pan-account-meta"><span>空间 ${esc(panAccountSpaceText(account))}</span><span>权益 ${esc(account?.membership || '未获取')}</span></span>`;
       const panAccountStatsHtml = (account) => `<div class="pan-account-stats"><div><small>空间用量</small><strong>${esc(panAccountSpaceText(account))}</strong></div><div><small>账号权益</small><strong>${esc(account?.membership || '未获取')}</strong></div></div>`;
       const panSwitchHtml = (key, enabled, editable, name) => `<button class="switch pan-enable-switch ${enabled ? 'on' : ''}" data-pan-enable="${esc(key)}" data-enabled="${enabled}" ${editable ? '' : 'disabled'} aria-label="${esc(enabled ? '关闭' : '开启')}${esc(name)}" aria-pressed="${enabled}"><span></span></button>`;
       const renderPanCard = (item, pansEditable, configEditable) => {
         const enabled = item.enabled !== false;
         return `<article id="pan-card-${esc(item.key)}" class="pan-card pan-workspace" data-pan-card="${esc(item.key)}" role="tabpanel" aria-labelledby="pan-tab-${esc(item.key)}">
           <div class="pan-object-browser" data-pan-browser="${esc(item.key)}">
             <header class="pan-account-toolbar"><div class="pan-account-toolbar-actions"><div class="pan-platform-switch"><span>${enabled ? '网盘已开启' : '网盘已关闭'}</span>${panSwitchHtml(item.key, enabled, pansEditable, item.name)}</div><button class="outline-button pan-add-account" type="button" data-pan-object-open="${esc(item.key)}" data-pan-object-type="add">添加账号</button></div></header>
             <div class="pan-object-grid">${panAccountRows(item, pansEditable)}</div>
           </div>
           <div class="pan-card-content">
             <section class="pan-object-detail" data-pan-object-detail="${esc(item.key)}" hidden>
               <div class="pan-object-detail-head"><button class="pan-back-button" type="button" data-pan-object-back="${esc(item.key)}" aria-label="返回${esc(item.name)}账号列表"><span aria-hidden="true">←</span>返回账号列表</button><div class="pan-detail-heading"><small>${esc(item.name)}</small><strong data-pan-object-title="${esc(item.key)}"></strong></div><div class="pan-platform-switch"><span>${enabled ? '网盘已开启' : '网盘已关闭'}</span>${panSwitchHtml(item.key, enabled, pansEditable, item.name)}</div></div>
               <div class="pan-object-pane" data-pan-object-pane="${esc(item.key)}"></div>
             </section>
           </div>
         </article>`;
       };
       const renderPanObjectContent = (item, type, index, pansEditable, configEditable) => {
         const accounts = Array.isArray(item.account_summary) ? item.account_summary : [];
         const directoryField = ({UC:'uc_pan_upload_dir','夸克':'quark_pan_upload_dir','百度':'baidu_pan_upload_dir'})[item.key] || '';
         if (type === 'account') {
           const account = accounts.find((entry, position) => Number(entry?.index) === index || (!entry?.index && position + 1 === index));
           if (!account) return '';
           const enabled = account.enabled !== false;
           const isDefault = index === Number(item.default_account || item.selected_account || 0);
           const profileName = account.name && account.name !== '未命名账号' ? account.name : '未命名账号';
           const avatar = panAccountAvatarHtml(account, profileName);
           const accountMetadata = item.key === '夸克' ? panAccountStatsHtml(account) : '';
           return `<div class="pan-object-account-detail">${avatar}<div class="pan-object-account-copy"><span class="pan-section-kicker">账号信息</span><h3>${esc(profileName)}</h3>${accountMetadata}</div><span class="tag ${enabled ? 'ok' : 'off'}">${enabled ? '运行中' : '已停用'}</span></div><div class="pan-object-detail-actions"><span>账号状态</span><button class="switch pan-account-switch ${enabled ? 'on' : ''}" type="button" data-pan-account-enable="${esc(item.key)}" data-index="${esc(index)}" data-enabled="${enabled}" ${pansEditable ? '' : 'disabled'} aria-label="${enabled ? '停用' : '启用'}${esc(item.name)}账号${esc(index)}" aria-pressed="${enabled}"><span></span></button>${isDefault ? '<span class="tag ok pan-account-default-tag">默认账号</span>' : enabled ? `<button class="pan-account-default" type="button" data-pan-account-default="${esc(item.key)}" data-index="${esc(index)}" ${pansEditable ? '' : 'disabled'}>设为默认</button>` : ''}<button class="pan-account-delete" type="button" data-pan-delete="${esc(item.key)}" data-index="${esc(index)}" ${pansEditable ? '' : 'disabled'}>删除账号</button></div><p class="pan-security-note">Cookie 仅用于登录态，页面不回显。</p><section class="pan-detail-section"><div class="pan-detail-section-head"><div><span class="pan-section-kicker">上传</span><h3>上传目录</h3></div></div><div class="pan-directory"><input id="pan-dir-${esc(item.key)}" type="text" data-pan-dir="${esc(item.key)}" data-pan-dir-field="${esc(directoryField)}" value="${esc(item.directory || '')}" placeholder="/小说机器人" ${configEditable ? '' : 'disabled'} aria-label="${esc(item.name)}上传目录"><button class="outline-button" type="button" data-pan-dir-save="${esc(item.key)}" ${configEditable ? '' : 'disabled'}>保存目录</button></div></section>`;
         }
         if (type === 'add') {
           const isQuark = item.key === '夸克';
           return `<div class="pan-object-form">${isQuark ? `<div class="pan-add-method" role="group" aria-label="选择夸克账号添加方式"><button type="button" data-quark-mode="cookie" aria-pressed="true">Cookie</button><button type="button" data-quark-mode="scan" aria-pressed="false">扫码</button></div>` : ''}<section data-quark-cookie-panel><label class="pan-field-label" for="pan-cookie-${esc(item.key)}">${esc(item.name)} Cookie</label><div class="account-add pan-account-add"><input id="pan-cookie-${esc(item.key)}" type="password" data-pan-cookie="${esc(item.key)}" placeholder="粘贴 Cookie（只写入）" autocomplete="off" ${pansEditable ? '' : 'disabled'} aria-label="添加${esc(item.name)}账号 Cookie"><button class="outline-button" type="button" data-pan-add="${esc(item.key)}" ${pansEditable ? '' : 'disabled'}>添加账号</button></div><p class="pan-security-note">Cookie 只提交给后端，不在页面回显。</p></section>${isQuark ? `<section class="pan-quark-scan" data-quark-scan-panel hidden><p class="pan-security-note">使用夸克 App 扫描网页二维码，确认后自动保存账号。</p><button class="outline-button" type="button" data-quark-scan-start ${pansEditable ? '' : 'disabled'}>获取二维码</button><img class="pan-quark-scan-image" data-quark-scan-image alt="夸克登录二维码" hidden><p class="pan-quark-scan-status" data-quark-scan-status aria-live="polite">获取二维码后使用夸克 App 扫描。</p><button class="pan-account-delete" type="button" data-quark-scan-cancel hidden>取消扫码</button></section>` : ''}</div>`;
         }
         return '';
       };
       const panObjectTitle = (type) => type === 'account' ? '账号设置' : '添加账号';
       const bindPanObjectControls = (platform) => {
         const card = document.querySelector(`[data-pan-card="${CSS.escape(platform)}"]`);
         const pane = card?.querySelector('[data-pan-object-pane]');
         if (!pane) return;
         pane.querySelectorAll('[data-pan-add]').forEach((node) => node.addEventListener('click', () => addPanAccount(node.dataset.panAdd)));
         pane.querySelectorAll('[data-quark-mode]').forEach((node) => node.addEventListener('click', async () => {
           await stopQuarkWebScan();
           const scanMode = node.dataset.quarkMode === 'scan';
           pane.querySelector('[data-quark-cookie-panel]')?.toggleAttribute('hidden', scanMode);
           pane.querySelector('[data-quark-scan-panel]')?.toggleAttribute('hidden', !scanMode);
           pane.querySelectorAll('[data-quark-mode]').forEach((button) => button.setAttribute('aria-pressed', String(button === node)));
         }));
         pane.querySelector('[data-quark-scan-start]')?.addEventListener('click', (event) => startQuarkWebScan(event.currentTarget));
         pane.querySelector('[data-quark-scan-cancel]')?.addEventListener('click', async () => {
           await stopQuarkWebScan();
           toast('扫码已取消');
         });
         pane.querySelectorAll('[data-pan-delete]').forEach((node) => node.addEventListener('click', () => deletePanAccount(node.dataset.panDelete, node.dataset.index, node)));
         pane.querySelectorAll('[data-pan-account-enable]').forEach((node) => node.addEventListener('click', () => changePanAccountEnabled(node.dataset.panAccountEnable, node.dataset.index, node)));
         pane.querySelectorAll('[data-pan-account-default]').forEach((node) => node.addEventListener('click', () => changePanAccountDefault(node.dataset.panAccountDefault, node.dataset.index, node)));
         pane.querySelectorAll('[data-pan-dir-save]').forEach((node) => node.addEventListener('click', () => savePanDirectory(node.dataset.panDirSave, node)));
         card.querySelector('[data-pan-object-detail] .pan-object-detail-head [data-pan-enable]')?.addEventListener('click', (event) => changePanEnabled(event.currentTarget.dataset.panEnable, event.currentTarget));
       };
       const showPanObject = (restoreFocus = false) => {
         const object = activePanObject;
         if (!object) return;
         const card = document.querySelector(`[data-pan-card="${CSS.escape(object.platform)}"]`);
         const item = (snapshot?.pans?.items || []).find((entry) => entry.key === object.platform);
         if (!card || !item) return;
         if (object.type === 'account') {
           const accounts = Array.isArray(item.account_summary) ? item.account_summary : [];
           const exists = accounts.some((entry, position) => Number(entry?.index) === object.index || (!entry?.index && position + 1 === object.index));
           if (!exists) { activePanObject = null; return; }
         }
         const browser = card.querySelector('[data-pan-browser]');
         const detail = card.querySelector('[data-pan-object-detail]');
         const title = card.querySelector('[data-pan-object-title]');
         const pane = card.querySelector('[data-pan-object-pane]');
         browser.hidden = true;
         detail.hidden = false;
         title.textContent = panObjectTitle(object.type);
         pane.innerHTML = renderPanObjectContent(item, object.type, object.index, snapshot.pans.editable, snapshot.pans.config_editable);
         bindPanObjectControls(object.platform);
         if (restoreFocus) {
           card.querySelector('[data-pan-object-back]')?.focus({preventScroll:true});
           detail.scrollIntoView({block:'nearest', behavior:'smooth'});
         }
       };
       const openPanObject = (platform, type, index) => {
         activePanObject = {platform, type, index: Number(index) || 0};
         showPanObject(true);
       };
       const closePanObject = (platform) => {
         const previous = activePanObject;
         if (!previous || previous.platform !== platform) return;
         if (previous.type === 'add') void stopQuarkWebScan();
         activePanObject = null;
         if (platform === '夸克') renderQuarkAccountCards();
         const card = document.querySelector(`[data-pan-card="${CSS.escape(platform)}"]`);
         if (!card) return;
         card.querySelector('[data-pan-object-pane]').innerHTML = '';
         card.querySelector('[data-pan-object-detail]').hidden = true;
         card.querySelector('[data-pan-browser]').hidden = false;
         const controls = Array.from(card.querySelectorAll('[data-pan-object-open]'));
         controls.find((node) => node.dataset.panObjectType === previous.type && Number(node.dataset.index || 0) === previous.index)?.focus({preventScroll:true});
         card.querySelector('[data-pan-browser]')?.scrollIntoView({block:'nearest', behavior:'smooth'});
       };
       const applyPanTab = (key) => {
         const cards = document.querySelectorAll('[data-pan-card]');
         const tabs = document.querySelectorAll('[data-pan-tab]');
         const available = Array.from(cards).map((node) => node.dataset.panCard);
         const selected = available.includes(key) ? key : (available[0] || '');
         activePanTab = selected || null;
         try { if (selected) sessionStorage.setItem('mantou-pan-tab', selected); } catch (_) {}
         tabs.forEach((node) => { const isActive = node.dataset.panTab === selected; node.classList.toggle('active', isActive); node.setAttribute('aria-selected', String(isActive)); node.tabIndex = isActive ? 0 : -1; });
         cards.forEach((node) => { const isActive = node.dataset.panCard === selected; node.hidden = !isActive; node.setAttribute('aria-hidden', String(!isActive)); });
       };
       const choosePanTab = (key) => {
         if (activePanTab === key) return;
         if (activePanObject) closePanObject(activePanObject.platform);
         activePanObject = null;
         applyPanTab(key);
         void refreshQuarkProfilesSilently();
       };
       const bindPanWorkspaceControls = () => {
         const grid = $('pan-grid');
         if (!grid) return;
         grid.querySelectorAll('[data-pan-object-open]').forEach((node) => node.addEventListener('click', () => openPanObject(node.dataset.panObjectOpen, node.dataset.panObjectType, node.dataset.index)));
         grid.querySelectorAll('[data-pan-object-back]').forEach((node) => node.addEventListener('click', () => closePanObject(node.dataset.panObjectBack)));
         grid.querySelectorAll('[data-pan-account-enable]').forEach((node) => node.addEventListener('click', () => changePanAccountEnabled(node.dataset.panAccountEnable, node.dataset.index, node)));
         grid.querySelectorAll('[data-pan-account-default]').forEach((node) => node.addEventListener('click', () => changePanAccountDefault(node.dataset.panAccountDefault, node.dataset.index, node)));
         grid.querySelectorAll('[data-pan-enable]').forEach((node) => node.addEventListener('click', () => changePanEnabled(node.dataset.panEnable, node)));
       };
       document.querySelectorAll('[data-pan-tab]').forEach((node) => {
         node.addEventListener('click', () => choosePanTab(node.dataset.panTab));
         node.addEventListener('keydown', (event) => {
           const tabs = Array.from(document.querySelectorAll('[data-pan-tab]'));
           const current = tabs.indexOf(node);
           let next = current;
           if (event.key === 'ArrowRight') next = (current + 1) % tabs.length;
           else if (event.key === 'ArrowLeft') next = (current - 1 + tabs.length) % tabs.length;
           else if (event.key === 'Home') next = 0;
           else if (event.key === 'End') next = tabs.length - 1;
           else return;
           event.preventDefault();
           tabs[next]?.focus();
           choosePanTab(tabs[next]?.dataset.panTab);
         });
       });
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
        panItems.forEach((item) => {
          const accounts = Array.isArray(item.account_summary) ? item.account_summary : [];
          const enabled = accounts.filter((account) => account?.enabled !== false).length;
          const meta = document.querySelector(`[data-pan-tab-meta="${CSS.escape(item.key)}"]`);
          if (meta) meta.textContent = `${accounts.length} 个账号 · ${enabled} 启用`;
        });
        const panGrid = $('pan-grid');
        if (panGrid) panGrid.innerHTML = panItems.map((item) => renderPanCard(item, pans.editable, pans.config_editable)).join('') || '<div class="empty">没有网盘数据</div>';
        bindPanWorkspaceControls();
        let savedPanTab = activePanTab;
        if (!savedPanTab) { try { savedPanTab = sessionStorage.getItem('mantou-pan-tab'); } catch (_) {} }
        applyPanTab(savedPanTab || panItems.find((item) => item.active)?.key || panItems[0]?.key || '');
        if (activePanObject) showPanObject(false);
        $('runtime-cpu').textContent = server.cpu || '--'; $('runtime-memory').textContent = server.memory || '--'; $('runtime-disk').textContent = server.disk || '--'; $('runtime-runtime').textContent = server.runtime || '--'; $('runtime-os').textContent = server.os || '--'; $('runtime-db').textContent = database.status || '--'; $('runtime-pan').textContent = pans.active || '--'; $('runtime-version').textContent = `v${data.version || '--'}`;
        const configList = $('config-list'); if (configList) configList.innerHTML = `<div class="config-item"><span>监听地址</span><strong>${esc(server.listen || '--')}</strong></div><div class="config-item"><span>访问地址</span><strong title="${esc(server.address)}">${esc(server.address || '--')}</strong></div><div class="config-item"><span>域名模式</span><strong>${data.config && data.config.custom_domain ? '自定义域名' : '自动服务器 IP'}</strong></div><div class="config-item"><span>登录方式</span><strong>${esc(data.config && data.config.auth_mode || '账号密码会话')}</strong></div>`;
        const configFields = data.config && data.config.fields || [];
        renderConfigEditor('basic-config-editor', configFields, Boolean(data.config && data.config.editable), (field) => ['basic_settings', 'help_web_settings'].includes(field.category));
        renderConfigEditor('database-config-editor', configFields, Boolean(data.config && data.config.editable), (field) => field.category === 'database_settings');
        renderDatabaseStatus(database);
        renderQQAuthEditor(data.qq_reader || {});
        $('updated').textContent = '刚刚更新';
        document.querySelectorAll('[data-switch]').forEach((node) => node.addEventListener('click', () => changeNovel(node)));
      };
      const qqReader = {auth:null, detailId:'', adding:false, method:'cookie', scanId:'', image:'', scanMessage:'', scanStatus:'', scanTimer:null, scanGeneration:0, scanIntent:0, scanStarting:false, scanCancel:null, keyRequest:0, keyShown:false, request:0, mutation:false, smsGeneration:0, smsStarting:false, smsActive:false, smsBusy:false, smsSent:false, smsPhone:'', smsMessage:'', smsOperation:'', smsRetryAt:0, smsTimer:null, smsAbort:null, smsCancel:null, captcha:null, captchaReject:null, modalFocus:null, modalGeneration:0, modalOverflow:null, modalRestoreFocus:true};
      const qqReaderAccount = (id = qqReader.detailId) => (qqReader.auth?.accounts || []).find((account) => String(account.id) === String(id));
      const qqReaderEditable = () => Boolean(qqReader.auth?.editable);
      const qqReaderDate = (value) => {
        if (value === null || value === undefined || value === '') return '未返回';
        const numeric = Number(value);
        const date = new Date(Number.isFinite(numeric) && numeric > 0 ? (numeric < 100000000000 ? numeric * 1000 : numeric) : value);
        return Number.isNaN(date.getTime()) ? '未返回' : date.toLocaleString('zh-CN', {hour12:false});
      };
      const qqReaderVip = (account) => {
        const vip = account?.vip || {};
        return {label:vip.available === false || typeof vip.is_vip !== 'boolean' ? '会员状态待查询' : vip.is_vip ? String(vip.vip_type || 'VIP会员') : '非VIP', active:vip.available !== false && vip.is_vip === true, expires:vip.vip_expire_text || (vip.vip_expire_at ? qqReaderDate(vip.vip_expire_at) : vip.is_vip === false ? '—' : '未返回')};
      };
      const qqReaderAvatarHtml = (account) => {
        const name = String(account?.nickname || '书友');
        const raw = safeMediaUrl(String(account?.avatar_url || ''));
        const source = raw ? `/api/message/media?src=${encodeURIComponent(raw)}&mode=image` : '';
        return `<span class="qq-reader-avatar" aria-hidden="true"><span>${esc(name.trim().slice(0, 1) || '阅')}</span>${source ? `<img src="${esc(source)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}</span>`;
      };
      const hideQQReaderKey = () => {
        qqReader.keyRequest += 1;
        qqReader.keyShown = false;
        const input = $('qq-reader-key');
        if (input) { input.value = ''; input.type = 'password'; }
        const button = $('qq-reader-key-toggle');
        if (button) { button.disabled = false; button.textContent = '显示密钥'; button.setAttribute('aria-pressed', 'false'); }
      };
      const updateQQReaderScan = () => {
        const image = $('qq-reader-qr-image');
        if (image) { if (qqReader.image) { image.src = qqReader.image; image.hidden = false; } else { image.removeAttribute('src'); image.hidden = true; } }
        if ($('qq-reader-qr-message')) $('qq-reader-qr-message').textContent = qqReader.scanMessage || '使用手机 QQ 扫码，并在手机上确认登录。';
        if ($('qq-reader-scan-cancel')) $('qq-reader-scan-cancel').hidden = !qqReader.scanId && !qqReader.scanStarting;
        if ($('qq-reader-scan-start')) { $('qq-reader-scan-start').disabled = !qqReaderEditable() || qqReader.scanStarting || Boolean(qqReader.scanCancel); $('qq-reader-scan-start').textContent = qqReader.scanStarting ? '正在获取二维码' : qqReader.scanId ? '更换二维码' : '获取二维码'; }
      };
      const stopQQReaderScan = async (clearMessage = true) => {
        const scanId = qqReader.scanId;
        const starting = qqReader.scanStarting;
        const previousCancel = qqReader.scanCancel;
        qqReader.scanIntent += 1;
        qqReader.scanGeneration += 1;
        qqReader.scanStarting = false;
        qqReader.scanId = '';
        qqReader.image = '';
        qqReader.scanStatus = '';
        clearTimeout(qqReader.scanTimer);
        qqReader.scanTimer = null;
        if (clearMessage) qqReader.scanMessage = '';
        updateQQReaderScan();
        if (scanId || starting) {
          const cancellation = (async () => {
            if (previousCancel) await previousCancel;
            try { await api('qq-reader-auth/scan', {method:'DELETE', body:JSON.stringify({scan_id:scanId})}); } catch (_) {}
          })();
          qqReader.scanCancel = cancellation;
          updateQQReaderScan();
          try { await cancellation; } finally { if (qqReader.scanCancel === cancellation) { qqReader.scanCancel = null; updateQQReaderScan(); } }
        } else if (previousCancel) {
          await previousCancel;
        }
      };
      const rememberQQReaderFocus = (target) => {
        qqReader.modalFocus = {node:target, id:target?.id || '', accountId:target?.dataset?.qqReaderOpen || ''};
        qqReader.modalRestoreFocus = true;
      };
      const qqReaderModalFocusable = () => [...($('qq-reader-account-dialog')?.querySelectorAll('button,input,select,textarea,a[href],iframe,[tabindex]') || [])].filter((node) => !node.disabled && node.tabIndex >= 0 && node.getClientRects().length);
      const qqReaderModalKeydown = (event) => {
        const modal = $('qq-reader-account-dialog');
        if (!modal?.open) return;
        if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); backQQReaderList(); return; }
        if (event.key !== 'Tab') return;
        event.stopPropagation();
        const nodes = qqReaderModalFocusable();
        if (!nodes.length) { event.preventDefault(); modal.focus({preventScroll:true}); return; }
        const current = nodes.indexOf(document.activeElement);
        if (event.shiftKey && current <= 0) { event.preventDefault(); nodes.at(-1).focus(); }
        else if (!event.shiftKey && (current < 0 || current === nodes.length - 1)) { event.preventDefault(); nodes[0].focus(); }
      };
      const syncQQReaderModal = () => {
        const modal = $('qq-reader-account-dialog');
        if (!modal) return;
        const wanted = (qqReader.adding || Boolean(qqReaderAccount())) && activeView === 'bot' && document.visibilityState !== 'hidden';
        if ($('qq-reader-modal-title')) $('qq-reader-modal-title').textContent = qqReader.adding ? '添加QQ阅读账号' : 'QQ阅读账号详情';
        if (wanted && !modal.open) {
          qqReader.modalGeneration += 1;
          qqReader.modalOverflow = document.body.style.overflow;
          document.body.style.overflow = 'hidden';
          modal.showModal();
          document.addEventListener('keydown', qqReaderModalKeydown, true);
        } else if (!wanted && (modal.open || qqReader.modalOverflow !== null)) {
          const generation = ++qqReader.modalGeneration;
          const previous = qqReader.modalFocus;
          const restore = qqReader.modalRestoreFocus;
          qqReader.modalFocus = null;
          if (modal.open) modal.close();
          if (qqReader.modalOverflow !== null) document.body.style.overflow = qqReader.modalOverflow;
          qqReader.modalOverflow = null;
          document.removeEventListener('keydown', qqReaderModalKeydown, true);
          if (restore) queueMicrotask(() => {
            if (generation !== qqReader.modalGeneration || modal.open || activeView !== 'bot' || document.visibilityState === 'hidden') return;
            const target = previous?.accountId ? document.querySelector(`[data-qq-reader-open="${CSS.escape(previous.accountId)}"]`) : previous?.id ? $(previous.id) : previous?.node;
            (target?.isConnected && !target.disabled ? target : $('qq-reader-add'))?.focus({preventScroll:true});
          });
        }
      };
      const renderQQReaderDetail = () => {
        const detail = $('qq-reader-detail');
        if (!detail) return;
        const focusedId = detail.contains(document.activeElement) ? document.activeElement.id : '';
        hideQQReaderKey();
        const account = qqReaderAccount();
        detail.hidden = !account || qqReader.adding;
        if (!account) { detail.innerHTML = ''; return; }
        const vip = qqReaderVip(account);
        detail.innerHTML = `<div class="qq-reader-detail-head">${qqReaderAvatarHtml(account)}<div class="qq-reader-detail-copy"><strong>${esc(account.nickname || '书友用户')}</strong><small>账号 ${esc(account.ywguid || '')}</small></div><button class="outline-button" id="qq-reader-profile-refresh" type="button" ${qqReaderEditable() ? '' : 'disabled'}>刷新资料</button></div><dl class="qq-reader-profile"><div><dt>会员状态</dt><dd>${vip.active ? '已开通' : account.vip?.available !== false && account.vip?.is_vip === false ? '未开通' : '待查询'}</dd></div><div><dt>会员类型</dt><dd>${esc(vip.label)}</dd></div><div><dt>到期时间</dt><dd>${esc(vip.expires)}</dd></div><div><dt>资料更新</dt><dd>${esc(qqReaderDate(account.profile_updated_at))}</dd></div></dl><div class="qq-reader-key-row"><label for="qq-reader-key">ywkey / usid</label><div><input id="qq-reader-key" type="password" readonly autocomplete="off" placeholder="点击显示密钥" aria-label="已保存的QQ阅读密钥"><button class="outline-button" id="qq-reader-key-toggle" type="button" aria-pressed="false" ${qqReaderEditable() ? '' : 'disabled'}>显示密钥</button></div></div><div class="qq-auth-actions"><button class="outline-button" type="button" id="qq-reader-select" ${!qqReaderEditable() || account.enabled === false || account.selected ? 'disabled' : ''}>${account.selected ? '当前使用账号' : '切换到此账号'}</button><button class="qq-reader-delete" type="button" id="qq-reader-delete" ${qqReaderEditable() ? '' : 'disabled'}>删除账号</button></div>`;
        $('qq-reader-profile-refresh')?.addEventListener('click', (event) => mutateQQReader('refresh', account.id, {}, event.currentTarget, '账号资料已刷新'));
        $('qq-reader-key-toggle')?.addEventListener('click', showQQReaderKey);
        $('qq-reader-select')?.addEventListener('click', (event) => mutateQQReader('select', account.id, {}, event.currentTarget, '当前账号已切换'));
        $('qq-reader-delete')?.addEventListener('click', (event) => deleteQQReaderAccount(account.id, event.currentTarget));
        if (focusedId && $('qq-reader-account-dialog')?.open) $(focusedId)?.focus({preventScroll:true});
      };
      const renderQQAuthEditor = (auth) => {
        const node = $('qq-auth-editor');
        if (!node || !auth || !Array.isArray(auth.accounts)) return;
        qqReader.auth = {...auth, accounts:auth.accounts.map((account) => ({...account, selected:String(account.id) === String(auth.selected_id || '')}))};
        if (qqReader.detailId && !qqReaderAccount()) qqReader.detailId = '';
        if (!$('qq-reader-accounts')) {
          node.innerHTML = `<div id="qq-reader-list"><div class="qq-reader-toolbar"><span id="qq-reader-summary"></span><button class="outline-button" id="qq-reader-add" type="button">添加账号</button></div><div id="qq-reader-accounts" class="qq-reader-accounts"></div></div><dialog id="qq-reader-account-dialog" class="qq-reader-modal" aria-labelledby="qq-reader-modal-title" aria-modal="true" tabindex="-1"><div class="qq-reader-modal-head"><h3 id="qq-reader-modal-title">QQ阅读账号详情</h3><button class="qq-reader-modal-close" id="qq-reader-modal-close" type="button" aria-label="关闭账号窗口">×</button></div><div class="qq-reader-modal-body"><section id="qq-reader-detail" class="qq-reader-detail" hidden></section><section id="qq-reader-add-panel" class="qq-reader-add-panel" hidden><div class="qq-auth-tabs" role="group" aria-label="选择QQ阅读登录方式"><button class="qq-auth-tab active" id="qq-reader-method-cookie" type="button" aria-pressed="true">手动配置</button><button class="qq-auth-tab" id="qq-reader-method-scan" type="button" aria-pressed="false">QQ扫码登录</button><button class="qq-auth-tab" id="qq-reader-method-phone" type="button" aria-pressed="false">手机号登录</button></div><div id="qq-reader-manual-panel"><label class="qq-reader-field-label" for="qq-reader-cookie">Cookie</label><textarea id="qq-reader-cookie" class="qq-reader-cookie" rows="3" autocomplete="off" spellcheck="false" placeholder="粘贴含 ywguid / ywkey 的 Cookie"></textarea><p class="qq-reader-field-hint">也可以直接填写下面两个字段。</p><div class="qq-auth-row"><input type="text" id="qq-ywguid" placeholder="ywguid / uid" autocomplete="off" aria-label="QQ阅读账号ID"><div class="qq-reader-new-key"><input type="password" id="qq-ywkey" placeholder="ywkey / usid" autocomplete="off" aria-label="QQ阅读密钥"><button class="text-button" id="qq-reader-new-key-toggle" type="button" aria-pressed="false">显示</button></div></div><div class="qq-auth-actions"><button class="primary-button" id="qq-auth-save" type="button">添加并使用</button></div></div><div id="qq-reader-phone-panel" class="qq-reader-phone-panel" hidden><label class="qq-reader-field-label" for="qq-reader-phone">手机号</label><div class="qq-reader-phone-row"><input id="qq-reader-phone" type="tel" inputmode="tel" maxlength="11" autocomplete="off" placeholder="请输入11位手机号"><button class="outline-button" id="qq-reader-phone-send" type="button">获取验证码</button></div><label class="qq-reader-field-label" for="qq-reader-phone-code">短信验证码</label><div class="qq-reader-phone-row"><input id="qq-reader-phone-code" type="text" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="请输入6位验证码"><button class="primary-button" id="qq-reader-phone-login" type="button" disabled>登录并添加</button></div><p id="qq-reader-phone-status" class="qq-reader-field-hint" aria-live="polite"></p><div id="qq-reader-captcha-frame" class="qq-reader-captcha-frame" hidden><div id="qq-reader-captcha" class="qq-reader-captcha" aria-label="短信安全验证"></div></div></div><div id="qq-reader-scan-panel" class="qq-reader-scan-panel" hidden><button class="outline-button" id="qq-reader-scan-start" type="button">获取二维码</button><img class="qq-reader-qr-image" id="qq-reader-qr-image" alt="QQ阅读登录二维码" hidden><p id="qq-reader-qr-message" class="qq-reader-field-hint" aria-live="polite"></p><button class="text-button" id="qq-reader-scan-cancel" type="button" hidden>取消扫码</button></div></section></div></dialog>`;
          const modal = $('qq-reader-account-dialog'); document.body.appendChild(modal);
          let backdropDown = false;
          const outside = (event) => { const rect = modal.getBoundingClientRect(); return event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom; };
          modal.addEventListener('pointerdown', (event) => { backdropDown = event.target === modal && outside(event); });
          modal.addEventListener('click', (event) => { if (event.target === modal && backdropDown && outside(event)) backQQReaderList(); backdropDown = false; });
          modal.addEventListener('cancel', (event) => { event.preventDefault(); backQQReaderList(); });
          modal.addEventListener('close', () => { if (!modal.open && (qqReader.adding || qqReader.detailId || qqReader.modalOverflow !== null)) backQQReaderList(); });
          $('qq-reader-add').addEventListener('click', (event) => { rememberQQReaderFocus(event.currentTarget); hideQQReaderKey(); qqReader.detailId = ''; qqReader.adding = true; renderQQAuthEditor(qqReader.auth); });
          $('qq-reader-modal-close').addEventListener('click', () => backQQReaderList());
          $('qq-reader-method-cookie').addEventListener('click', () => setQQReaderMethod('cookie'));
          $('qq-reader-method-scan').addEventListener('click', () => setQQReaderMethod('scan'));
          $('qq-reader-method-phone').addEventListener('click', () => setQQReaderMethod('phone'));
          $('qq-reader-phone-send').addEventListener('click', sendQQReaderSms);
          $('qq-reader-phone-login').addEventListener('click', loginQQReaderSms);
          $('qq-reader-phone').addEventListener('input', () => { void stopQQReaderSms(false); });
          $('qq-reader-new-key-toggle').addEventListener('click', (event) => { const input = $('qq-ywkey'); const shown = input.type === 'password'; input.type = shown ? 'text' : 'password'; event.currentTarget.textContent = shown ? '隐藏' : '显示'; event.currentTarget.setAttribute('aria-pressed', String(shown)); });
          $('qq-auth-save').addEventListener('click', saveQQAuth);
          $('qq-reader-scan-start').addEventListener('click', startQQReaderScan);
          $('qq-reader-scan-cancel').addEventListener('click', () => stopQQReaderScan());
        }
        const accounts = qqReader.auth.accounts;
        $('qq-reader-summary').textContent = `${accounts.length} 个账号 · ${accounts.filter((account) => account.enabled !== false).length} 个启用${auth.configured ? '' : ' · 当前未登录'}`;
        $('qq-reader-add').disabled = !qqReaderEditable() || qqReader.mutation;
        $('qq-reader-accounts').innerHTML = accounts.map((account) => {
          const vip = qqReaderVip(account);
          return `<article class="qq-reader-account ${account.selected ? 'is-current' : ''} ${account.enabled === false ? 'is-disabled' : ''}"><div class="qq-reader-account-top"><span class="tag ${account.selected ? 'ok' : account.enabled === false ? 'off' : ''}">${account.selected ? '当前使用' : account.enabled === false ? '已停用' : '已启用'}</span><button class="switch qq-reader-account-switch ${account.enabled !== false ? 'on' : ''}" type="button" data-qq-reader-enable="${esc(account.id)}" aria-label="${account.enabled === false ? '启用' : '停用'}${esc(account.nickname || 'QQ阅读账号')}" aria-pressed="${account.enabled !== false}" ${qqReaderEditable() && !qqReader.mutation ? '' : 'disabled'}><span></span></button></div><button class="qq-reader-account-open" type="button" data-qq-reader-open="${esc(account.id)}" aria-expanded="${!qqReader.adding && String(account.id) === qqReader.detailId}">${qqReaderAvatarHtml(account)}<span><strong>${esc(account.nickname || '书友用户')}</strong><small>${esc(account.ywguid || '')}</small></span><span class="qq-reader-arrow" aria-hidden="true">›</span></button><div class="qq-reader-account-vip"><span class="${vip.active ? 'is-vip' : ''}">${esc(vip.label)}</span><small>到期 ${esc(vip.expires)}</small></div></article>`;
        }).join('') || '<div class="empty qq-reader-empty">还没有QQ阅读账号，请添加账号。</div>';
        $('qq-reader-accounts').querySelectorAll('[data-qq-reader-open]').forEach((button) => button.addEventListener('click', () => { rememberQQReaderFocus(button); void stopQQReaderScan(); void stopQQReaderSms(); qqReader.adding = false; qqReader.detailId = button.dataset.qqReaderOpen; clearQQReaderManual(); renderQQAuthEditor(qqReader.auth); }));
        $('qq-reader-accounts').querySelectorAll('[data-qq-reader-enable]').forEach((button) => button.addEventListener('click', () => { const account = qqReaderAccount(button.dataset.qqReaderEnable); if (account) void mutateQQReader('enable', account.id, {enabled:account.enabled === false}, button, account.enabled === false ? '账号已启用' : '账号已停用'); }));
        $('qq-reader-list').hidden = false;
        $('qq-reader-add-panel').hidden = !qqReader.adding;
        $('qq-auth-save').disabled = !qqReaderEditable() || qqReader.mutation;
        renderQQReaderDetail();
        updateQQReaderScan();
        updateQQReaderSms();
        syncQQReaderModal();
      };
      const clearQQReaderManual = () => {
        ['qq-reader-cookie', 'qq-ywguid', 'qq-ywkey'].forEach((id) => { if ($(id)) $(id).value = ''; });
        if ($('qq-ywkey')) $('qq-ywkey').type = 'password';
        if ($('qq-reader-new-key-toggle')) { $('qq-reader-new-key-toggle').textContent = '显示'; $('qq-reader-new-key-toggle').setAttribute('aria-pressed', 'false'); }
      };
      const backQQReaderList = (restoreFocus = true) => {
        hideQQReaderKey(); void stopQQReaderScan(); void stopQQReaderSms(); clearQQReaderManual(); qqReader.adding = false; qqReader.detailId = ''; qqReader.modalRestoreFocus = restoreFocus !== false;
        if (qqReader.auth) renderQQAuthEditor(qqReader.auth); else syncQQReaderModal();
      };
      const setQQReaderMethod = (method) => {
        const next = ['cookie', 'scan', 'phone'].includes(method) ? method : 'cookie';
        if (next !== qqReader.method) { void stopQQReaderSms(); if (next !== 'scan') void stopQQReaderScan(); clearQQReaderManual(); }
        qqReader.method = next;
        ['cookie', 'scan', 'phone'].forEach((value) => { const button = $(`qq-reader-method-${value}`); button?.classList.toggle('active', next === value); button?.setAttribute('aria-pressed', String(next === value)); });
        if ($('qq-reader-manual-panel')) $('qq-reader-manual-panel').hidden = next !== 'cookie';
        if ($('qq-reader-scan-panel')) $('qq-reader-scan-panel').hidden = next !== 'scan';
        if ($('qq-reader-phone-panel')) $('qq-reader-phone-panel').hidden = next !== 'phone';
      };
      const loadQQReaderAccounts = async () => {
        const request = ++qqReader.request;
        const data = await api('qq-reader-auth');
        if (request !== qqReader.request) return;
        renderQQAuthEditor(data);
      };
      const mutateQQReader = async (action, id, extra, button, message) => {
        if (qqReader.mutation) return;
        qqReader.mutation = true;
        qqReader.request += 1;
        if (button) button.disabled = true;
        hideQQReaderKey();
        try { await api(`qq-reader-auth/${action}`, {method:'POST', body:JSON.stringify({account_id:id, ...extra})}); await loadQQReaderAccounts(); toast(message); }
        catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); }
        finally { qqReader.mutation = false; if (qqReader.auth) renderQQAuthEditor(qqReader.auth); }
      };
      const showQQReaderKey = async () => {
        if (qqReader.keyShown) { hideQQReaderKey(); return; }
        const account = qqReaderAccount();
        const button = $('qq-reader-key-toggle');
        if (!account || !button || button.disabled) return;
        button.disabled = true;
        const request = ++qqReader.keyRequest;
        const id = qqReader.detailId;
        try {
          const data = await api('qq-reader-auth/credential', {method:'POST', body:JSON.stringify({account_id:account.id})});
          if (request !== qqReader.keyRequest || id !== qqReader.detailId || activeView !== 'bot' || document.visibilityState === 'hidden' || qqReader.adding) return;
          const input = $('qq-reader-key');
          if (input) { input.value = String(data.ywkey || ''); input.type = 'text'; qqReader.keyShown = true; button.textContent = '隐藏密钥'; button.setAttribute('aria-pressed', 'true'); }
        } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); }
        finally { if (request === qqReader.keyRequest && button.isConnected) button.disabled = false; }
      };
      const saveQQAuth = async () => {
        const cookie = $('qq-reader-cookie')?.value.trim();
        const ywguid = $('qq-ywguid')?.value.trim();
        const ywkey = $('qq-ywkey')?.value.trim();
        if (!cookie && (!ywguid || !ywkey)) return toast('请粘贴 Cookie，或填写 ywguid 和 ywkey');
        if (qqReader.mutation) return;
        qqReader.mutation = true;
        qqReader.request += 1;
        $('qq-auth-save').disabled = true;
        try {
          await api('qq-reader-auth', {method:'POST', body:JSON.stringify(cookie ? {cookie, select:true} : {ywguid, ywkey, select:true})});
          clearQQReaderManual(); qqReader.adding = false; qqReader.detailId = ''; await loadQQReaderAccounts(); toast('QQ阅读账号已添加并切换');
        } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); }
        finally { qqReader.mutation = false; if (qqReader.auth) renderQQAuthEditor(qqReader.auth); }
      };
      const deleteQQReaderAccount = async (id, button) => {
        if (!confirm('确定删除此QQ阅读账号吗？')) return;
        if (qqReader.mutation) return;
        qqReader.mutation = true;
        qqReader.request += 1;
        if (button) button.disabled = true;
        hideQQReaderKey();
        try { await api('qq-reader-auth', {method:'DELETE', body:JSON.stringify({account_id:id})}); qqReader.detailId = ''; await loadQQReaderAccounts(); toast('账号已删除'); }
        catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); }
        finally { qqReader.mutation = false; if (qqReader.auth) renderQQAuthEditor(qqReader.auth); }
      };
      const startQQReaderScan = async () => {
        if (!qqReaderEditable()) return;
        const cancellation = stopQQReaderScan();
        const intent = qqReader.scanIntent;
        await cancellation;
        if (intent !== qqReader.scanIntent || !qqReader.adding || qqReader.method !== 'scan' || activeView !== 'bot' || document.visibilityState === 'hidden') return;
        const generation = ++qqReader.scanGeneration;
        qqReader.scanStarting = true;
        const button = $('qq-reader-scan-start');
        if (button) button.disabled = true;
        qqReader.scanMessage = '正在生成二维码…'; updateQQReaderScan();
        if (button) button.disabled = true;
        try {
          const result = await api('qq-reader-auth/scan', {method:'POST', body:'{}'});
          if (generation !== qqReader.scanGeneration || !qqReader.adding || qqReader.method !== 'scan' || activeView !== 'bot' || document.visibilityState === 'hidden') {
            if (result.scan_id && String(result.scan_id) !== qqReader.scanId) { try { await api('qq-reader-auth/scan', {method:'DELETE', body:JSON.stringify({scan_id:String(result.scan_id)})}); } catch (_) {} }
            return;
          }
          if (!result.scan_id || !/^data:image\/png;base64,[A-Za-z0-9+/=\r\n]+$/.test(String(result.qr_image || ''))) throw new Error('二维码获取失败，请重试');
          qqReader.scanStarting = false;
          qqReader.scanId = String(result.scan_id); qqReader.image = result.qr_image; qqReader.scanStatus = result.status || 'waiting'; qqReader.scanMessage = result.message || '请使用手机 QQ 扫码确认。'; updateQQReaderScan();
          const scanId = qqReader.scanId;
          const expires = Date.now() + Math.max(10, Math.min(600, Number(result.expires_in) || 120)) * 1000;
          let failures = 0;
          const poll = async () => {
            if (scanId !== qqReader.scanId || generation !== qqReader.scanGeneration) return;
            if (activeView !== 'bot' || document.visibilityState === 'hidden') { await stopQQReaderScan(); return; }
            if (Date.now() >= expires) { qqReader.scanMessage = '二维码已过期，请重新获取。'; await stopQQReaderScan(false); return; }
            try {
              const state = await api(`qq-reader-auth/scan?scan_id=${encodeURIComponent(scanId)}`);
              if (scanId !== qqReader.scanId || generation !== qqReader.scanGeneration) return;
              failures = 0; qqReader.scanStatus = state.status; qqReader.scanMessage = state.message || '正在等待扫码。'; updateQQReaderScan();
              if (['waiting', 'scanned', 'saving'].includes(state.status)) { qqReader.scanTimer = setTimeout(poll, 2000); return; }
              await stopQQReaderScan(false);
              if (state.status === 'success') { qqReader.detailId = ''; qqReader.adding = false; await loadQQReaderAccounts(); toast('QQ阅读账号已扫码登录'); }
            } catch (error) {
              if (scanId !== qqReader.scanId || generation !== qqReader.scanGeneration) return;
              if (error.status === 401) { await stopQQReaderScan(); showAuthError(error); return; }
              failures += 1;
              qqReader.scanMessage = failures >= 3 ? '状态查询暂时失败，请重新获取二维码。' : '正在重试查询扫码状态…'; updateQQReaderScan();
              if (failures >= 3) { await stopQQReaderScan(false); return; }
              qqReader.scanTimer = setTimeout(poll, 3000);
            }
          };
          qqReader.scanTimer = setTimeout(poll, 1500);
        } catch (error) {
          if (generation !== qqReader.scanGeneration) return;
          qqReader.scanMessage = error.message || '二维码获取失败。'; updateQQReaderScan();
          if (error.status === 401) showAuthError(error);
        } finally { if (generation === qqReader.scanGeneration) { qqReader.scanStarting = false; updateQQReaderScan(); } }
      };
      let qqReaderCaptchaLoader = null;
      const updateQQReaderSms = () => {
        const remaining = Math.max(0, Math.ceil((qqReader.smsRetryAt - Date.now()) / 1000));
        if ($('qq-reader-phone-send')) { $('qq-reader-phone-send').disabled = !qqReaderEditable() || qqReader.smsBusy || Boolean(qqReader.smsCancel) || remaining > 0; $('qq-reader-phone-send').textContent = remaining ? `${remaining}秒后重发` : qqReader.smsBusy && qqReader.smsOperation === 'send' ? '正在发送' : '获取验证码'; }
        if ($('qq-reader-phone-login')) { $('qq-reader-phone-login').disabled = !qqReaderEditable() || qqReader.smsBusy || !qqReader.smsSent; $('qq-reader-phone-login').textContent = qqReader.smsBusy && qqReader.smsOperation === 'login' ? '正在登录' : '登录并添加'; }
        if ($('qq-reader-phone-status')) $('qq-reader-phone-status').textContent = qqReader.smsMessage || '';
        if (!remaining && qqReader.smsTimer) { clearInterval(qqReader.smsTimer); qqReader.smsTimer = null; }
      };
      const clearQQReaderCaptcha = () => {
        try { qqReader.captcha?.destroy?.(); } catch (_) {} qqReader.captcha = null;
        $('qq-reader-captcha')?.replaceChildren();
        if ($('qq-reader-captcha-frame')) $('qq-reader-captcha-frame').hidden = true;
      };
      const stopQQReaderSms = async (clearFields = true, keepalive = false) => {
        const shouldCancel = qqReader.smsStarting || qqReader.smsActive;
        const previousCancel = qqReader.smsCancel;
        qqReader.smsGeneration += 1;
        qqReader.smsAbort?.abort(); qqReader.smsAbort = null;
        const reject = qqReader.captchaReject; qqReader.captchaReject = null;
        if (reject) reject(new DOMException('Login cancelled', 'AbortError'));
        clearQQReaderCaptcha();
        qqReader.smsStarting = false; qqReader.smsActive = false; qqReader.smsBusy = false; qqReader.smsSent = false; qqReader.smsPhone = ''; qqReader.smsRetryAt = 0; qqReader.smsMessage = ''; qqReader.smsOperation = '';
        clearInterval(qqReader.smsTimer); qqReader.smsTimer = null;
        if (clearFields && $('qq-reader-phone')) $('qq-reader-phone').value = '';
        if ($('qq-reader-phone-code')) $('qq-reader-phone-code').value = '';
        updateQQReaderSms();
        if (shouldCancel) {
          const cancellation = (async () => { if (previousCancel) await previousCancel; try { if (keepalive) await fetch('/api/qq-reader-auth/sms-login', {method:'DELETE', credentials:'same-origin', keepalive:true, headers:{'Content-Type':'application/json'}, body:'{}'}); else await api('qq-reader-auth/sms-login', {method:'DELETE', body:'{}'}); } catch (_) {} })();
          qqReader.smsCancel = cancellation; updateQQReaderSms();
          try { await cancellation; } finally { if (qqReader.smsCancel === cancellation) { qqReader.smsCancel = null; updateQQReaderSms(); } }
        } else if (previousCancel) await previousCancel;
      };
      const loadQQReaderCaptcha = () => {
        if (typeof window.TencentCaptcha === 'function') return Promise.resolve(window.TencentCaptcha);
        if (qqReaderCaptchaLoader) return qqReaderCaptchaLoader;
        qqReaderCaptchaLoader = new Promise((resolve, reject) => {
          const script = document.createElement('script'); script.src = 'https://ssl.captcha.qq.com/TCaptcha.js'; script.async = true;
          const timer = setTimeout(() => { script.remove(); qqReaderCaptchaLoader = null; reject(new Error('验证组件加载失败，请重试')); }, 10000);
          script.onload = () => { clearTimeout(timer); if (typeof window.TencentCaptcha === 'function') resolve(window.TencentCaptcha); else { script.remove(); qqReaderCaptchaLoader = null; reject(new Error('验证组件加载失败，请重试')); } };
          script.onerror = () => { clearTimeout(timer); script.remove(); qqReaderCaptchaLoader = null; reject(new Error('验证组件加载失败，请重试')); };
          document.head.appendChild(script);
        });
        return qqReaderCaptchaLoader;
      };
      const qqReaderSmsCurrent = (generation) => generation === qqReader.smsGeneration && qqReader.adding && qqReader.method === 'phone' && activeView === 'bot' && document.visibilityState !== 'hidden';
      const sendQQReaderSms = async () => {
        const phone = $('qq-reader-phone')?.value.trim();
        if (!/^1\d{10}$/.test(phone || '')) return toast('请输入正确的11位手机号');
        if (!qqReaderEditable() || qqReader.smsBusy || qqReader.smsRetryAt > Date.now()) return;
        const cancellation = stopQQReaderSms(false); const intent = qqReader.smsGeneration; await cancellation;
        if (!qqReaderSmsCurrent(intent) || $('qq-reader-phone')?.value.trim() !== phone) return;
        const generation = ++qqReader.smsGeneration;
        const controller = new AbortController(); qqReader.smsAbort = controller;
        qqReader.smsStarting = true; qqReader.smsBusy = true; qqReader.smsOperation = 'send'; qqReader.smsMessage = '正在准备短信验证…'; updateQQReaderSms();
        try {
          const pre = await api('qq-reader-auth/pre-send', {method:'POST', body:JSON.stringify({phone}), signal:controller.signal});
          if (!qqReaderSmsCurrent(generation)) return;
          qqReader.smsActive = true; qqReader.smsStarting = false;
          let response = pre;
          for (let attempt = 0; response.challenge_required === true && attempt < 3; attempt += 1) {
            const appId = String(response.captcha_app_id || pre.captcha_app_id || '');
            if (!/^\d{5,20}$/.test(appId)) throw new Error('验证组件暂未就绪，请重试');
            const Captcha = await loadQQReaderCaptcha();
            if (!qqReaderSmsCurrent(generation)) return;
            qqReader.smsMessage = '请完成安全验证。'; updateQQReaderSms();
            const ticket = await new Promise((resolve, reject) => {
              let settled = false;
              qqReader.captchaReject = reject;
              const container = $('qq-reader-captcha');
              if (!container || !$('qq-reader-account-dialog')?.open) { reject(new DOMException('Login cancelled', 'AbortError')); return; }
              $('qq-reader-captcha-frame').hidden = false;
              const captcha = new Captcha(container, appId, (result) => {
                if (settled) return;
                settled = true;
                if (!qqReaderSmsCurrent(generation)) { reject(new DOMException('Login cancelled', 'AbortError')); return; }
                qqReader.captchaReject = null;
                if (result?.ret === 0 && result.ticket && result.randstr) resolve({ticket:String(result.ticket), randstr:String(result.randstr)});
                else reject(new Error('验证未完成，请重试'));
              }, {type:'embed'});
              qqReader.captcha = captcha; captcha.show();
            });
            if (!qqReaderSmsCurrent(generation)) return;
            clearQQReaderCaptcha();
            response = await api('qq-reader-auth/confirm-send', {method:'POST', body:JSON.stringify({phone, ...ticket}), signal:controller.signal});
            if (!qqReaderSmsCurrent(generation)) return;
          }
          if (response.sent !== true) throw new Error('短信暂未发送，请重试');
          qqReader.smsSent = true; qqReader.smsPhone = phone; qqReader.smsRetryAt = Date.now() + 60000; qqReader.smsMessage = '验证码已发送，请查看手机短信。';
          clearInterval(qqReader.smsTimer); qqReader.smsTimer = setInterval(updateQQReaderSms, 1000);
        } catch (error) {
          if (!qqReaderSmsCurrent(generation) || error.name === 'AbortError') return;
          qqReader.smsMessage = error.message || '短信发送失败，请重试';
          if (error.status === 401) showAuthError(error); else toast(qqReader.smsMessage);
        } finally {
          if (generation === qqReader.smsGeneration) { qqReader.smsStarting = false; qqReader.smsBusy = false; qqReader.smsAbort = null; qqReader.captchaReject = null; clearQQReaderCaptcha(); updateQQReaderSms(); }
        }
      };
      const loginQQReaderSms = async () => {
        const phone = $('qq-reader-phone')?.value.trim(); const code = $('qq-reader-phone-code')?.value.trim();
        if (!qqReader.smsSent || phone !== qqReader.smsPhone) return toast('请先获取当前手机号的验证码');
        if (!/^\d{6}$/.test(code || '')) return toast('请输入6位短信验证码');
        if (qqReader.smsBusy) return;
        const generation = ++qqReader.smsGeneration;
        const controller = new AbortController(); qqReader.smsAbort = controller;
        qqReader.smsBusy = true; qqReader.smsOperation = 'login'; qqReader.smsMessage = '正在登录…'; updateQQReaderSms();
        try {
          await api('qq-reader-auth/sms-login', {method:'POST', body:JSON.stringify({phone, code}), signal:controller.signal});
          if (!qqReaderSmsCurrent(generation)) return;
          qqReader.adding = false; qqReader.detailId = ''; await stopQQReaderSms(); clearQQReaderManual(); await loadQQReaderAccounts(); toast('QQ阅读账号已添加并切换');
        } catch (error) {
          if (!qqReaderSmsCurrent(generation) || error.name === 'AbortError') return;
          qqReader.smsMessage = error.message || '登录失败，请重试'; if (error.status === 401) showAuthError(error); else toast(qqReader.smsMessage);
        } finally { if (generation === qqReader.smsGeneration) { qqReader.smsBusy = false; qqReader.smsAbort = null; updateQQReaderSms(); } }
      };

      const leaveQQReader = () => backQQReaderList(false);
      window.addEventListener('pagehide', () => {
        hideQQReaderKey(); clearQQReaderManual();
        void stopQQReaderSms(true, true);
        qqReader.adding = false; qqReader.detailId = ''; qqReader.modalRestoreFocus = false; syncQQReaderModal();
        if (qqReader.scanId || qqReader.scanStarting) fetch('/api/qq-reader-auth/scan', {method:'DELETE', credentials:'same-origin', keepalive:true, headers:{'Content-Type':'application/json'}, body:JSON.stringify({scan_id:qqReader.scanId})}).catch(() => {});
        qqReader.scanIntent += 1; qqReader.scanGeneration += 1; qqReader.scanStarting = false; qqReader.scanId = ''; qqReader.image = ''; clearTimeout(qqReader.scanTimer);
      });
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') leaveQQReader(); });

       const addPanAccount = async (platform) => { const input = document.querySelector(`[data-pan-cookie="${CSS.escape(platform)}"]`); const button = document.querySelector(`[data-pan-add="${CSS.escape(platform)}"]`); const cookie = input?.value.trim(); if (!cookie) return toast('请先粘贴 Cookie'); if (button) button.disabled = true; try { await api(`pan-accounts/${encodeURIComponent(platform)}`, {method:'POST', body:JSON.stringify({cookie})}); if (input) input.value = ''; toast(`${platform}账号已保存`); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const startQuarkWebScan = async (button) => {
         if (!snapshot?.pans?.editable) return toast('数据库未配置，扫码账号不能保存');
         await stopQuarkWebScan();
         if (button) { button.disabled = true; button.textContent = '正在获取二维码'; }
         const statusNode = document.querySelector('[data-quark-scan-status]');
         try {
           const result = await api(`pan-accounts/${encodeURIComponent('夸克')}/scan`, {method:'POST', body:'{}'});
           quarkWebScanId = String(result.scan_id || '');
           const generation = ++quarkWebScanGeneration;
           const image = document.querySelector('[data-quark-scan-image]');
           if (image) { image.src = result.qr_image; image.hidden = false; }
           if (statusNode) statusNode.textContent = result.message || '请使用夸克 App 扫描二维码。';
           const cancel = document.querySelector('[data-quark-scan-cancel]');
           if (cancel) cancel.hidden = false;
           if (button) { button.disabled = false; button.textContent = '重新获取二维码'; }
           const scanId = quarkWebScanId;
           const poll = async () => {
             if (!scanId || scanId !== quarkWebScanId || generation !== quarkWebScanGeneration) return;
             try {
               const state = await api(`pan-accounts/${encodeURIComponent('夸克')}/scan/${encodeURIComponent(scanId)}`);
               if (scanId !== quarkWebScanId || generation !== quarkWebScanGeneration) return;
               const label = document.querySelector('[data-quark-scan-status]');
               if (label) label.textContent = state.message || '正在等待扫码。';
               if (state.status === 'waiting' || state.status === 'saving') {
                 quarkWebScanTimer = setTimeout(poll, 2000);
                 return;
               }
               quarkWebScanId = '';
               quarkWebScanTimer = null;
               try { await api(`pan-accounts/${encodeURIComponent('夸克')}/scan/${encodeURIComponent(scanId)}`, {method:'DELETE'}); } catch (_) {}
               const qr = document.querySelector('[data-quark-scan-image]');
               if (qr) { qr.removeAttribute('src'); qr.hidden = true; }
               const cancelButton = document.querySelector('[data-quark-scan-cancel]');
               if (cancelButton) cancelButton.hidden = true;
               const startButton = document.querySelector('[data-quark-scan-start]');
               if (startButton) { startButton.disabled = false; startButton.textContent = '获取二维码'; }
               if (state.status === 'success') {
                 activePanObject = null;
                 toast(state.message || '夸克账号已添加');
                 await load();
               }
             } catch (error) {
               if (error.status === 401) { showAuthError(error); return; }
               const label = document.querySelector('[data-quark-scan-status]');
               if (label) label.textContent = error.message || '正在重试查询扫码状态。';
               quarkWebScanTimer = setTimeout(poll, 3000);
             }
           };
           quarkWebScanTimer = setTimeout(poll, 1500);
         } catch (error) {
           if (button) { button.disabled = false; button.textContent = '获取二维码'; }
           if (statusNode) statusNode.textContent = error.message || '二维码获取失败。';
           if (error.status === 401) showAuthError(error); else toast(error.message);
         }
       };
       const deletePanAccount = async (platform, index, button) => { if (!confirm(`确定删除${platform}账号吗？`)) return; if (button) button.disabled = true; try { await api(`pan-accounts/${encodeURIComponent(platform)}`, {method:'DELETE', body:JSON.stringify({index:Number(index)})}); toast('账号已删除'); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const quarkProfileRefreshIntervalMs = 300000;
       const quarkProfileRetryIntervalMs = 60000;
       let quarkProfileRefreshAfter = 0;
       let quarkProfileRefreshPromise = null;
       const renderQuarkAccountCards = () => {
         if (activePanObject?.platform === '夸克') return;
         const quark = snapshot?.pans?.items?.find((item) => item.key === '夸克');
         if (!quark) return;
         const grid = document.querySelector('[data-pan-card="夸克"] [data-pan-browser] .pan-object-grid');
         if (!grid) return;
         grid.innerHTML = panAccountRows(quark, snapshot.pans.editable);
         grid.querySelectorAll('[data-pan-object-open]').forEach((node) => node.addEventListener('click', () => openPanObject(node.dataset.panObjectOpen, node.dataset.panObjectType, node.dataset.index)));
         grid.querySelectorAll('[data-pan-account-enable]').forEach((node) => node.addEventListener('click', () => changePanAccountEnabled(node.dataset.panAccountEnable, node.dataset.index, node)));
         grid.querySelectorAll('[data-pan-account-default]').forEach((node) => node.addEventListener('click', () => changePanAccountDefault(node.dataset.panAccountDefault, node.dataset.index, node)));
       };
       const refreshQuarkProfilesSilently = () => {
         if (document.visibilityState !== 'visible' || activeView !== 'pans' || activePanTab !== '夸克' || !snapshot) return;
         if (quarkProfileRefreshPromise) return quarkProfileRefreshPromise;
         if (Date.now() < quarkProfileRefreshAfter) return;
         const quark = snapshot.pans?.items?.find((item) => item.key === '夸克');
         const accounts = Array.isArray(quark?.account_summary) ? quark.account_summary : [];
         if (!accounts.length) return;
         quarkProfileRefreshPromise = api('pan-accounts/夸克').then((data) => {
           // 保存账号或开关时 load() 可能换过快照，旧请求不得覆盖新状态。
           if (snapshot?.pans?.items?.find((item) => item.key === '夸克') !== quark) return;
           if (!Array.isArray(data.accounts)) throw new Error('账号资料格式错误');
           quark.account_summary = data.accounts;
           quark.accounts = data.accounts.length;
           quark.configured = data.accounts.length > 0;
           if (data.default_account != null) quark.default_account = data.default_account;
           if (data.selected_account != null) quark.selected_account = data.selected_account;
           const meta = document.querySelector('[data-pan-tab-meta="夸克"]');
           if (meta) meta.textContent = `${data.accounts.length} 个账号 · ${data.accounts.filter((account) => account?.enabled !== false).length} 启用`;
           renderQuarkAccountCards();
           quarkProfileRefreshAfter = Date.now() + quarkProfileRefreshIntervalMs;
         }).catch((error) => {
           quarkProfileRefreshAfter = Date.now() + quarkProfileRetryIntervalMs;
           if (error.status === 401) showAuthError(error);
         }).finally(() => { quarkProfileRefreshPromise = null; });
         return quarkProfileRefreshPromise;
       };
       const savePanDirectory = async (platform, button) => { const input = document.querySelector(`[data-pan-dir="${CSS.escape(platform)}"]`); const field = input?.dataset.panDirField; const value = input?.value.trim(); if (!field || !value) return toast('请输入上传目录'); if (button) button.disabled = true; try { const result = await api('config', {method:'POST', body:JSON.stringify({fields:{[field]:value}})}); toast(result.message || `${platform}上传目录已保存`); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const changePanAccountEnabled = async (platform, index, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，账号状态不能保存'); const enabled = node.dataset.enabled !== 'true'; node.disabled = true; try { const result = await api(`pan-accounts/${encodeURIComponent(platform)}/enable`, {method:'POST', body:JSON.stringify({index:Number(index), enabled})}); toast(result.message || `账号${enabled ? '已启用' : '已停用'}`); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
       const changePanAccountDefault = async (platform, index, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，默认账号不能保存'); node.disabled = true; try { const result = await api(`pan-accounts/${encodeURIComponent(platform)}/default`, {method:'POST', body:JSON.stringify({index:Number(index)})}); toast(result.message || `${platform}默认账号已更新`); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
      const showAuthError = (error) => { if (error.status === 401) { location.reload(); return; } if ($('popover-logout')) $('popover-logout').hidden = true; showNotice(error.status === 503 ? '登录服务尚未启用，请联系管理员。' : '控制台数据暂时不可用，请稍后重试。'); };
      const adminChip = $('admin-chip'); const adminPopover = $('admin-popover');
      adminChip?.addEventListener('click', (event) => { event.stopPropagation(); const expanded = adminChip.getAttribute('aria-expanded') === 'true'; adminChip.setAttribute('aria-expanded', String(!expanded)); if (adminPopover) adminPopover.hidden = expanded; });
      document.addEventListener('click', () => { if (adminChip?.getAttribute('aria-expanded') === 'true') { adminChip.setAttribute('aria-expanded', 'false'); if (adminPopover) adminPopover.hidden = true; } });
      const changeNovel = async (node) => { if (!snapshot || !snapshot.novels.editable) return toast('数据库未配置，开关不能保存'); const enabled = node.dataset.enabled !== 'true'; node.disabled = true; try { await api('novel-switch', {method:'POST', body:JSON.stringify({key:node.dataset.switch, enabled})}); toast('小说开关已更新'); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
       const changePanEnabled = async (key, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，网盘开关不能保存'); const enabled = node.dataset.enabled !== 'true'; node.disabled = true; try { const result = await api('pan-enable', {method:'POST', body:JSON.stringify({key, enabled})}); toast(result.message || `网盘${enabled ? '已开启' : '已关闭'}`); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
      const load = async () => { try { render(await api('dashboard')); void loadBotProfile(); if ($('popover-logout')) $('popover-logout').hidden = false; setView(viewFromUrl(), false); } catch (error) { showAuthError(error); } };
      $('popover-logout').addEventListener('click', async () => { leaveQQReader(); try { await api('logout', {method:'POST'}); } finally { location.reload(); } });
      document.querySelectorAll('[data-view]').forEach((node) => node.addEventListener('click', (event) => { event.preventDefault(); setView(node.dataset.view); }));
      window.addEventListener('popstate', () => setView(viewFromUrl(), false));

      // ---------- 消息记录页 ----------
      const msgHistoryPageSize = 100;
      const msgState = { filter:'all', folderCollapsed:{group:false,user:false}, search:'', page:1, chatId:'', chatType:'group', chatAppid:'', chatRemoved:false, chats:[], realtimeChats:new Map(), messages:[], historyData:null, historyWindow:null, historyCache:new Map(), renderedChatId:'', messageRenderSignature:null, initialScrollChatId:'', positionToken:0, positionFrame:null, positionTimer:null, positionObserver:null, positionBody:null, pendingNewMessages:0, historyRequest:0, historyOlderRequest:0, historyOlderLoading:false, historyScheduleFrame:null, historyScheduleToken:0, chatListRequest:0, chatListAbort:null, chatListPromise:null, chatListKey:'', chatListRendered:false, chatListServerLoaded:false, chatListTopPending:false, chatListScrollActive:false, chatListPointerActive:false, chatListScrollTimer:null, chatListPendingData:null, chatListRows:[], chatListOffsets:[0], chatListContentHeight:0, chatListRowHeight:52, chatListWindowStart:-1, chatListWindowEnd:-1, historyAbort:null, historyOlderAbort:null, readInFlight:new Set(), chatRenderTimer:null, chatRenderSignature:null, realtimeMessageTimer:null, realtimeMessageCount:0, realtimeToBottom:false, realtimeRenderChatId:'', quote:null, mute:{member:'',name:''}, mutes:new Map(), muteRequestAt:0, sendType:'text', sendMode:'default', muteMinutes:30, timer:null, muteTimer:null, eventSocket:null, eventSource:null, eventTransport:'', eventReconnect:null, eventRefreshTimer:null, eventKeys:new Set(), eventKeyOrder:[], adminByChat:new Map(), adminScanAttempted:new Set(), adminScanFailures:new Map(), adminCheckedAt:new Map(), adminRequestToken:0, lastRolesAt:0, lastRolesChatId:'', lastRolesAppid:'', botIsAdmin:false, adChatId:'', adEnabled:false, adEditable:false, adLoading:false, adSaving:false, panSelectionData:null, panSelectionRequest:0, panSelectionLoading:false, panSelectionSaving:false, profiles:{}, pastedImage:null, pastedImageFile:null, pastedImageSource:'', mediaData:null, mediaFile:null, mediaName:'', mediaType:0, mediaMime:'', composerSelection:null, sending:false, optimisticSends:new Map(), optimisticSeq:0, multi:false, selected:new Set(), ctxMsg:null, ctxUser:null };
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
        if (node.dataset?.composerMention) {
          const id = String(node.dataset.composerMention);
          return id === 'all' || /^[A-Za-z0-9_-]{5,128}$/.test(id) ? `<@${id}>` : '';
        }
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
      const isBlankMsgNickname = (value) => typeof value === 'string' && value.length > 0 && /^[\s\p{Cc}\p{Cf}\p{Z}]+$/u.test(value);
      const validMsgNickname = (value, id = '') => {
        if (isBlankMsgNickname(value)) return '';
        const name = String(value || '').trim();
        const uid = String(id || '').trim();
        if (!name || name === uid || name === '用户' + uid.slice(-6) || ['成员','新成员','未知','未知用户','机器人','我'].includes(name) || /[\x00-\x1f\x7f-\x9f]/.test(name)) return '';
        return name;
      };
      const displayMsgNickname = (message, profile = {}, fallback = '未知用户') => {
        const id = message?.user_id || '';
        const name = validMsgNickname(message?.nickname, id)
          || validMsgNickname(profile.nickname || profile.username, id);
        return name || (message?.nickname_blank || profile.nickname_blank || isBlankMsgNickname(message?.nickname) ? '\u00a0' : fallback);
      };
      const mergeMsgProfileMaps = (...sources) => {
        const merged = {};
        sources.forEach((source) => {
          Object.entries(source || {}).forEach(([id, profile]) => {
            if (!profile || typeof profile !== 'object') return;
            const key = String(id || '').trim();
            if (!key) return;
            const next = {...(merged[key] || {})};
            Object.entries(profile).forEach(([field, value]) => {
              if (field === 'nickname' || field === 'username') {
                const name = validMsgNickname(value, key);
                if (name) next[field] = name;
                return;
              }
              if (field === 'role') {
                const role = String(value || '').trim().toLowerCase();
                if (role) next.role = role;
                return;
              }
              if (value !== null && value !== undefined && value !== '') next[field] = value;
            });
            if (validMsgNickname(next.nickname || next.username, key)) next.nickname_blank = false;
            merged[key] = next;
          });
        });
        return merged;
      };
      const msgIsBot = (message, profile = {}) => {
        if (typeof message?.is_bot === 'boolean') return message.is_bot;
        if (typeof profile?.is_bot === 'boolean') return profile.is_bot;
        const source = String(message?.source || '');
        return source.startsWith('bot_') || source === 'web_panel';
      };
      const mergeMsgProfiles = (profiles, messages = []) => {
        const merged = mergeMsgProfileMaps(profiles);
        (messages || []).forEach((message) => {
          const source = String(message?.source || '');
          if (message?.is_self || source.startsWith('bot_') || source === 'web_panel') return;
          const id = String(message?.user_id || '').trim();
          const nickname = validMsgNickname(message?.nickname, id);
          const avatar = String(message?.avatar || message?.avatar_url || '').trim();
          const role = String(message?.member_role || message?.role || '').trim().toLowerCase();
          const blank = !message?.is_self && !String(message?.source || '').startsWith('bot_') && Boolean(message?.nickname_blank || isBlankMsgNickname(message?.nickname));
          const botKnown = typeof message?.is_bot === 'boolean';
          if (!id || (!nickname && !avatar && !role && !blank && !botKnown) || !mentionIdPattern.test(id)) return;
          merged[id] = mergeMsgProfileMaps(merged, {[id]: {
            ...(nickname && nickname !== '未知用户' && nickname !== '未知' ? {nickname} : {}),
            ...(avatar ? {avatar} : {}),
            ...(role ? {role} : {}),
            ...(botKnown ? {is_bot:message.is_bot} : {}),
            ...(blank ? {nickname_blank:true} : {}),
          }})[id];
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
        const profile = profiles?.[id] || {};
        const nickname = validMsgNickname(profile.nickname || profile.username, id);
        if (nickname) return nickname;
        if (profile.nickname_blank || isBlankMsgNickname(profile.nickname || profile.username)) return '\u00a0';
        return '用户';
      };
      const replaceMsgMentions = (value, profiles = msgState.profiles) => String(value || '').replace(/<@all>/gi, '@全体成员').replace(/<@!?([A-Za-z0-9_-]{5,128})>/g, (_, openid) => `@${resolveMentionName(openid, profiles)}`);
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
        source = source.replace(/!\[[^\]\n]*\]\((https?:\/\/[^\s)]+)\)/gi, (_, target) => commandToken('image', target, '图片'));
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
          if (item.kind === 'image') return renderMessageMedia({type:'图片', src:item.command});
          return `<button type="button" class="msg-command-chip" data-msg-command="${esc(item.command)}" data-msg-command-kind="${esc(item.kind)}" aria-label="${esc(item.label)}">${esc(item.label)}</button>`;
        });
      };
      const plainMsgPreview = (value, profiles = msgState.profiles) => {
        let text = replaceMsgMentions(value, profiles);
        text = text.replace(/!\[[^\]\n]*\]\((https?:\/\/[^\s)]+)\)/gi, '[图片]');
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
      const chatListPreview = (value) => {
        const text = plainMsgPreview(String(value || '').slice(0, 512));
        return text.length > 120 ? `${text.slice(0, 120)}…` : text;
      };
      const msgMessagePreview = (message) => {
        const text = String(message.content || '');
        if (text.trim()) return text;
        const media = message.media && typeof message.media === 'object' ? message.media : {};
        const first = Array.isArray(media.items) && media.items[0] && typeof media.items[0] === 'object' ? media.items[0] : {};
        const labels = {图片:'[图片]',image:'[图片]',img:'[图片]',视频:'[视频]',video:'[视频]',语音:'[语音]',音频:'[语音]',audio:'[语音]',voice:'[语音]',record:'[语音]',文件:'[文件]',file:'[文件]'};
        const label = (type) => Object.prototype.hasOwnProperty.call(labels, type) ? labels[type] : '';
        return label(String(first.type || '').trim().toLowerCase()) || label(String(media.type || '').trim().toLowerCase());
      };
      const msgQuoteSummary = (message = {}, profiles = msgState.profiles) => {
        const id = String(message.user_id || message.userId || '').trim();
        const profile = profiles?.[id] || {};
        const own = Boolean(message.is_self) || /^(?:bot_|web_panel)/.test(String(message.source || ''));
        const previewOnly = Boolean(message.preview_only);
        const nickname = previewOnly
          ? (validMsgNickname(message.nickname, id) || (id ? validMsgNickname(profile.nickname || profile.username, id) : ''))
          : (own
            ? (validMsgNickname(message.nickname, id) || validMsgNickname(window.msgBotProfile?.username, id) || '机器人')
            : displayMsgNickname(message, profile));
        return {
          preview_only:previewOnly,
          message_id:previewOnly ? '' : String(message.message_id || message.id || '').trim(),
          refidx:previewOnly ? '' : String(message.refidx || '').trim(),
          user_id:id,
          nickname,
          nickname_blank:Boolean(message.nickname_blank || profile.nickname_blank || isBlankMsgNickname(message.nickname)) && !validMsgNickname(nickname, id),
          content:String(msgMessagePreview(message) || '（空消息）').slice(0, 1000),
          timestamp:String(message.timestamp || ''),
        };
      };
      const buildMsgReferenceIndex = (messages = [], references = {}, profiles = msgState.profiles) => {
        const index = new Map();
        const conflicts = new Set();
        const add = (id, summary) => {
          const key = String(id || '').trim();
          if (!key || conflicts.has(key)) return;
          const previous = index.get(key);
          if (previous?.message_id && summary.message_id && previous.message_id !== summary.message_id) {
            index.delete(key); conflicts.add(key); return;
          }
          index.set(key, summary);
        };
        const currentMessages = (messages || []).filter((message) => {
          if (message._session && msgState.chatId && String(message._session) !== msgState.chatId) return false;
          if (message.chat_type && msgState.chatType && String(message.chat_type) !== msgState.chatType) return false;
          return !message.appid || !msgState.chatAppid || String(message.appid) === msgState.chatAppid;
        });
        Object.entries(references || {}).forEach(([id, reference]) => {
          if (reference && typeof reference === 'object' && !reference.preview_only) add(id, msgQuoteSummary(reference, profiles));
        });
        currentMessages.forEach((message) => {
          const summary = msgQuoteSummary(message, profiles);
          [message.message_id, message.refidx].forEach((id) => add(id, summary));
        });
        // 多个明确候选必须指向同一原消息；后端冲突不可由当前页索引覆盖。
        const groups = new Map();
        currentMessages.forEach((message) => {
          const id = String(message.reference_id || '').trim();
          if (!id) return;
          if (!groups.has(id)) groups.set(id, {ids:new Set(), blocked:false});
          const group = groups.get(id);
          group.blocked ||= Boolean(message.reference_conflict);
          [id, ...(Array.isArray(message.reference_ids) ? message.reference_ids.slice(0, 8) : [])]
            .forEach((value) => { if (typeof value === 'string' && value.trim()) group.ids.add(value.trim()); });
        });
        const blocked = new Set();
        const resolved = [];
        groups.forEach((group, id) => {
          const targets = new Map();
          group.ids.forEach((value) => {
            const summary = index.get(value);
            if (conflicts.has(value)) group.blocked = true;
            if (summary?.message_id) targets.set(summary.message_id, summary);
          });
          if (group.blocked || targets.size > 1) blocked.add(id);
          else if (targets.size === 1) resolved.push([id, targets.values().next().value]);
        });
        resolved.forEach(([id, summary]) => index.set(id, summary));
        blocked.forEach((id) => index.delete(id));
        index.blocked = blocked;
        // 内嵌引用只属于当前回复；TMP 索引可能复用，不作为全局消息别名。
        return index;
      };
      const renderMsgQuote = (reference, profiles = msgState.profiles, referenceId = '', referencePreview = null, blocked = false) => {
        const selected = (!blocked && reference) || (referencePreview && typeof referencePreview === 'object' && !Array.isArray(referencePreview) ? referencePreview : null);
        const summary = selected ? msgQuoteSummary(selected, profiles) : null;
        const explicitId = String(referenceId || '').trim();
        // 预览不能制造目标身份；官方完整引用索引仍可主动请求精确定位。
        const id = blocked ? '' : summary?.preview_only
          ? (/^(?:REFIDX_|ROBOT\d)/.test(explicitId) ? explicitId : '')
          : String(summary?.message_id || summary?.refidx || explicitId).trim();
        const content = summary ? plainMsgPreview(summary.content, profiles) || '（空消息）' : '原消息暂不可用';
        const preview = `${summary?.nickname ? `<span class="msg-quote-name">${esc(summary.nickname)}</span>` : ''}<span class="msg-quote-content">${esc(content)}</span>`;
        return id
          ? `<button type="button" class="msg-bubble-quote msg-quote-jump" data-msg-jump="${esc(id)}" title="跳转到原消息" aria-label="跳转到原消息"><span class="msg-quote-jump-icon" aria-hidden="true">↗</span>${preview}</button>`
          : `<div class="msg-bubble-quote">${preview}</div>`;
      };
      const msgQuoteJump = {generation:0, abort:null, pending:false, pageAbort:null, pagePending:false, anchorAbort:null, row:null, highlightTimer:null};
      const msgQuoteJumpScope = () => JSON.stringify([msgState.chatType, msgState.chatId, String(msgState.chatAppid || '').trim()]);
      const cancelMsgQuoteJump = (clearWindow = false) => {
        msgQuoteJump.generation += 1;
        msgQuoteJump.abort?.abort();
        msgQuoteJump.pageAbort?.abort();
        msgQuoteJump.anchorAbort?.abort();
        msgQuoteJump.anchorAbort = null;
        msgQuoteJump.abort = msgQuoteJump.pageAbort = null;
        msgQuoteJump.pending = msgQuoteJump.pagePending = false;
        if (msgQuoteJump.highlightTimer) clearTimeout(msgQuoteJump.highlightTimer);
        msgQuoteJump.highlightTimer = null;
        msgQuoteJump.row?.classList.remove('msg-jump-target');
        msgQuoteJump.row = null;
        $('msg-body')?.removeAttribute('aria-busy');
        if (clearWindow) msgState.historyWindow = null;
      };
      const findMsgReferenceRow = (referenceId, canonicalId = '') => {
        const body = $('msg-body');
        if (!body) return null;
        const id = String(referenceId || '').trim();
        const canonical = String(canonicalId || '').trim();
        const rows = [...body.querySelectorAll('.msg-row[data-msg-mid]')];
        // Opaque QQ/REFIDX identifiers contain selector punctuation; compare complete values.
        const matches = rows.filter((row) => canonical
          ? row.dataset.msgMid === canonical
          : row.dataset.msgMid === id || row.dataset.msgRefidx === id);
        return matches.length === 1 ? matches[0] : null;
      };
      const highlightMsgReference = (row, behavior = 'smooth') => {
        const body = $('msg-body');
        if (!body || !row || !body.contains(row)) return false;
        cancelMsgBottomPosition(body, true);
        msgQuoteJump.anchorAbort?.abort();
        const anchor = new AbortController();
        msgQuoteJump.anchorAbort = anchor;
        msgQuoteJump.row?.classList.remove('msg-jump-target');
        if (msgQuoteJump.highlightTimer) clearTimeout(msgQuoteJump.highlightTimer);
        msgQuoteJump.row = row;
        row.classList.remove('msg-jump-target');
        void row.offsetWidth;
        row.classList.add('msg-jump-target');
        const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
        const position = (mode = 'auto') => {
          if (anchor.signal.aborted || !body.contains(row)) return;
          const top = body.scrollTop + row.getBoundingClientRect().top - body.getBoundingClientRect().top
            - (body.clientHeight - Math.min(row.offsetHeight, body.clientHeight)) / 2;
          if (typeof body.scrollTo === 'function') body.scrollTo({top:Math.max(0, top), behavior:reduced ? 'auto' : mode});
          else body.scrollTop = Math.max(0, top);
        };
        position(behavior);
        body.addEventListener('load', () => {
          position();
          requestAnimationFrame(() => {
            position();
            requestAnimationFrame(() => position());
          });
        }, {capture:true, signal:anchor.signal});
        // A late image may move the target; user scrolling always takes control immediately.
        ['wheel', 'pointerdown', 'touchstart', 'keydown'].forEach((name) => {
          body.addEventListener(name, () => anchor.abort(), {once:true, passive:true, signal:anchor.signal});
        });
        msgQuoteJump.highlightTimer = setTimeout(() => {
          anchor.abort();
          if (msgQuoteJump.anchorAbort === anchor) msgQuoteJump.anchorAbort = null;
          row.classList.remove('msg-jump-target');
          if (msgQuoteJump.row === row) msgQuoteJump.row = null;
          msgQuoteJump.highlightTimer = null;
        }, 2200);
        return true;
      };
      const jumpToMsgReference = async (referenceId) => {
        const id = String(referenceId || '').trim();
        if (!id || !msgState.chatId) return;
        cancelMsgQuoteJump();
        const generation = msgQuoteJump.generation;
        const scope = msgQuoteJumpScope();
        const current = () => generation === msgQuoteJump.generation && scope === msgQuoteJumpScope()
          && !$('page-messages')?.hidden && document.visibilityState !== 'hidden';
        msgState.historyAbort?.abort();
        msgState.historyOlderAbort?.abort();
        msgState.historyAbort = msgState.historyOlderAbort = null;
        msgState.historyRequest += 1;
        msgState.historyOlderRequest += 1;
        msgState.historyOlderLoading = false;
        msgState.historyScheduleToken += 1;
        msgState.initialScrollChatId = '';
        cancelMsgBottomPosition($('msg-body'), true);
        cancelMsgRealtimeMessageRender();
        const loaded = findMsgReferenceRow(id);
        if (loaded) { highlightMsgReference(loaded); return; }
        const controller = new AbortController();
        msgQuoteJump.abort = controller;
        msgQuoteJump.pending = true;
        $('msg-body')?.setAttribute('aria-busy', 'true');
        const timer = setTimeout(() => controller.abort(), 15000);
        try {
          const data = await api('message/history', {method:'POST', signal:controller.signal, body:JSON.stringify({
            chat_id:msgState.chatId, chat_type:msgState.chatType, appid:String(msgState.chatAppid || ''),
            locate_reference_id:id, limit:msgHistoryPageSize,
          })});
          if (!current()) return;
          if (data.chat_id !== msgState.chatId || data.chat_type !== msgState.chatType
            || String(data.appid || '') !== String(msgState.chatAppid || '')) {
            toast('暂未匹配到原消息'); return;
          }
          const messages = mergeMsgRecalledStates(dedupeMsgMessages(data.messages || []));
          const canonical = String(data.located_message_id || '').trim();
          if (!canonical || !messages.some((message) => String(message.message_id || '') === canonical)
            || messages.some((message) => (message.appid && String(message.appid) !== String(msgState.chatAppid || ''))
              || (message.chat_type && String(message.chat_type) !== msgState.chatType)
              || (message._session && String(message._session) !== msgState.chatId))) {
            toast('暂未匹配到原消息'); return;
          }
          msgState.historyWindow = {scope, oldest_id:Number(data.oldest_id || 0), newest_id:Number(data.newest_id || 0), has_newer:Boolean(data.has_newer)};
          msgState.messages = messages;
          msgState.messageRenderSignature = null;
          renderMsgMessages({...data, messages}, {preservePosition:true, previousTop:0});
          const pendingCount = msgState.pendingNewMessages;
          clearMsgNewMessages();
          if (pendingCount > 0) showMsgNewMessages(pendingCount);
          highlightMsgReference(findMsgReferenceRow(id, canonical), 'auto');
        } catch (error) {
          if (!current()) return;
          if (error.status === 401) showAuthError(error);
          else toast(error.status === 404 ? '暂未匹配到原消息' : '原消息定位失败，请重试');
        } finally {
          clearTimeout(timer);
          if (msgQuoteJump.abort === controller) {
            msgQuoteJump.abort = null;
            msgQuoteJump.pending = false;
            $('msg-body')?.removeAttribute('aria-busy');
          }
        }
      };
      const loadMsgWindowPage = async (direction) => {
        const windowState = msgState.historyWindow;
        if (!windowState || windowState.scope !== msgQuoteJumpScope() || msgQuoteJump.pending || msgQuoteJump.pagePending) return;
        const older = direction === 'before';
        if (older ? !msgState.historyData?.has_more : !windowState.has_newer) return;
        const cursor = older ? windowState.oldest_id : windowState.newest_id;
        if (!(cursor > 0)) return;
        const generation = msgQuoteJump.generation;
        const controller = new AbortController();
        msgQuoteJump.pageAbort = controller;
        msgQuoteJump.pagePending = true;
        const current = () => msgState.historyWindow === windowState && windowState.scope === msgQuoteJumpScope()
          && generation === msgQuoteJump.generation && !$('page-messages')?.hidden;
        const timer = setTimeout(() => controller.abort(), 15000);
        try {
          const data = await api('message/history', {method:'POST', signal:controller.signal, body:JSON.stringify({
            chat_id:msgState.chatId, chat_type:msgState.chatType, appid:String(msgState.chatAppid || ''),
            history_window:true, [older ? 'before_id' : 'after_id']:cursor, limit:msgHistoryPageSize,
          })});
          if (!current()) return;
          if (data.chat_id !== msgState.chatId || data.chat_type !== msgState.chatType
            || String(data.appid || '') !== String(msgState.chatAppid || '')) return;
          const incoming = mergeMsgRecalledStates(dedupeMsgMessages(data.messages || []));
          const body = $('msg-body');
          const previousTop = body?.scrollTop || 0;
          const previousHeight = body?.scrollHeight || 0;
          const existing = msgState.messages;
          msgState.messages = dedupeMsgMessages(older ? [...incoming, ...existing] : [...existing, ...incoming]);
          const history = msgState.historyData || {};
          const next = {
            ...history, ...data, messages:msgState.messages,
            member_profiles:mergeMsgProfileMaps(history.member_profiles, data.member_profiles),
            references:{...(history.references || {}), ...(data.references || {})},
            has_more:older ? Boolean(data.has_more) : Boolean(history.has_more),
          };
          windowState.oldest_id = older ? Number(data.oldest_id || windowState.oldest_id) : windowState.oldest_id;
          windowState.newest_id = older ? windowState.newest_id : Number(data.newest_id || windowState.newest_id);
          windowState.has_newer = older ? windowState.has_newer : Boolean(data.has_newer);
          next.has_newer = windowState.has_newer;
          renderMsgMessages(next, {prepend:older, preservePosition:true, previousTop, previousHeight});
        } catch (error) {
          if (!current()) return;
          if (error.status === 401) showAuthError(error);
          else toast('消息加载失败，请重试');
        } finally {
          clearTimeout(timer);
          if (msgQuoteJump.pageAbort === controller) {
            msgQuoteJump.pageAbort = null;
            msgQuoteJump.pagePending = false;
          }
        }
      };
      const msgRealtimeChatSummary = (payload, message, existing) => {
        const lastTs = Number(existing.last_ts || 0);
        const eventTs = Number(payload.last_ts || message.ts || 0) || lastTs || Math.floor(Date.now() / 1000);
        if (eventTs < lastTs) return {last_content:existing.last_content || '',last_ts:lastTs,last_time:existing.last_time || '',last_message_id:existing.last_message_id || ''};
        const preview = Object.prototype.hasOwnProperty.call(payload, 'last_content') ? String(payload.last_content || '') : msgMessagePreview(message);
        return {
          last_content:replaceMsgMentions(preview),
          last_ts:eventTs,
          last_time:String(payload.last_time || (Number(message.ts || 0) === eventTs ? message.timestamp : '') || new Date(eventTs * 1000).toISOString()),
          last_message_id:String(payload.last_message_id || message.message_id || ''),
        };
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
      const avatarImg = (url, letter) => {
        const source = mediaProxyUrl(url);
        const nonce = Number(msgState.avatarRefresh?.get(String(url)) || 0);
        const refreshed = nonce && source.startsWith('/api/') ? source + '&avatar_refresh=' + nonce : source;
        return `<img src="${esc(refreshed)}" data-avatar-direct="${esc(url)}" alt="" loading="lazy" decoding="async" fetchpriority="low" referrerpolicy="no-referrer" onerror="if(this.dataset.avatarRetried!=='1' && this.getAttribute('src')!==this.dataset.avatarDirect){this.dataset.avatarRetried='1';this.src=this.dataset.avatarDirect;return;}this.closest('.msg-chat-avatar, .msg-avatar, .msg-mention-avatar')?.classList.add('avatar-fallback');this.remove();">`;
      };
      const avatarHtml = (url, letter) => {
        const firstLetter = Array.from(String(letter || '?'))[0];
        if (!url) return esc(firstLetter);
        return `<span class="avatar-letter">${esc(firstLetter)}</span>` + avatarImg(url, letter);
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
      const msgChatMatchesView = (chat, {ignoreTypeFilter = false} = {}) => {
        const type = String(chat.chat_type || 'group');
        if (!ignoreTypeFilter && msgState.filter === 'group' && type !== 'group') return false;
        if (!ignoreTypeFilter && msgState.filter === 'user' && type !== 'user') return false;
        if (!ignoreTypeFilter && msgState.filter === 'remark' && !chat.remark) return false;
        const keyword = String(msgState.search || '').trim().toLowerCase();
        if (!keyword) return true;
        return [chat.nickname, chat.remark, chat.chat_id].some((value) => String(value || '').toLowerCase().includes(keyword));
      };
      const msgChatIsRemoved = (chat) => String(chat?.chat_type || 'group') === 'user'
        ? (String(chat?.friend_status || '').toLowerCase() === 'removed' || chat?.is_friend === false)
        : (String(chat?.membership_status || '').toLowerCase() === 'removed' || chat?.in_group === false);
      let msgFriendEventOrder = 0;
      const pickMsgFriendState = (current = {}, incoming = {}, authoritative = false) => {
        const read = (source) => {
          const explicit = String(source?.friend_status || '').trim().toLowerCase();
          const status = ['active','removed'].includes(explicit) ? explicit : source?.is_friend === true ? 'active' : source?.is_friend === false ? 'removed' : 'unknown';
          const checked = Number(source?.friend_checked_at || 0);
          return {friend_status:status, friend_checked_at:Number.isFinite(checked) && checked > 0 ? checked : 0, is_friend:status === 'unknown' ? null : status === 'active', _friend_live_order:Number(source?._friend_live_order || 0)};
        };
        const previous = read(current), next = read(incoming);
        if (authoritative && next.friend_status !== 'unknown') next._friend_live_order = ++msgFriendEventOrder;
        // 关系更新时间独立于最后一条消息；缺失或未知资料不能抹掉已确认关系。
        if (next.friend_status === 'unknown') return previous.friend_status !== 'unknown' ? previous : next.friend_checked_at > previous.friend_checked_at ? next : previous;
        if (previous.friend_status !== 'unknown' && (next.friend_checked_at < previous.friend_checked_at || (next.friend_checked_at === previous.friend_checked_at && next._friend_live_order <= previous._friend_live_order))) return previous;
        return next;
      };
      const syncMsgFriendState = (chatId, incoming = {}, authoritative = false) => {
        chatId = String(chatId || '').trim();
        if (!chatId) return {};
        const current = msgState.chats.find((chat) => String(chat.chat_id || '') === chatId && chat.chat_type === 'user');
        const overlay = msgState.realtimeChats.get(chatId);
        const validOverlay = overlay?.chat_type === 'user' ? overlay : null;
        const viewing = msgState.chatId === chatId && msgState.chatType === 'user';
        const appid = String(current?.appid || validOverlay?.appid || (viewing ? msgState.chatAppid : '') || '').trim();
        const matches = (source) => source && (!source.chat_id || String(source.chat_id) === chatId)
          && (!source.chat_type || source.chat_type === 'user')
          && (!appid || !source.appid || String(source.appid).trim() === appid);
        const history = viewing && matches(msgState.historyData) ? msgState.historyData : null;
        let state = pickMsgFriendState(current, matches(validOverlay) ? validOverlay : {});
        state = pickMsgFriendState(state, history || {});
        if (matches(incoming)) state = pickMsgFriendState(state, incoming, authoritative);
        msgState.chats = msgState.chats.map((chat) => String(chat.chat_id || '') === chatId && chat.chat_type === 'user' && matches(chat) ? {...chat, ...state} : chat);
        const base = matches(validOverlay) ? validOverlay : current;
        if (base) msgState.realtimeChats.set(chatId, {...base, ...state});
        if (viewing) msgState.historyData = {...(msgState.historyData || {}), ...state};
        return state;
      };
      const mergeMsgRealtimeChats = (serverChats) => {
        const byId = new Map((serverChats || []).map((chat) => [String(chat.chat_id || ''), {...chat}]));
        const now = Math.floor(Date.now() / 1000);
        msgState.realtimeChats.forEach((overlay, chatId) => {
          const current = byId.get(chatId);
          if (!current) { if (msgChatMatchesView(overlay, {ignoreTypeFilter:true})) byId.set(chatId, {...overlay}); return; }
          const currentAppid = String(current.appid || '').trim();
          const overlayAppid = String(overlay.appid || '').trim();
          if (String(current.chat_type || 'group') !== String(overlay.chat_type || 'group')
            || (currentAppid && overlayAppid && currentAppid !== overlayAppid)) {
            msgState.realtimeChats.delete(chatId);
            return;
          }
          const isPrivate = String(current.chat_type || 'group') === 'user';
          const friendState = isPrivate ? pickMsgFriendState(current, overlay) : {};
          const keepFriendOverlay = isPrivate && (Number(friendState.friend_checked_at || 0) > Number(current.friend_checked_at || 0)
            || (Number(friendState.friend_checked_at || 0) === Number(current.friend_checked_at || 0) && Number(friendState._friend_live_order || 0) > Number(current._friend_live_order || 0)));
          const contactName = isPrivate
            ? (validMsgNickname(current.nickname, chatId) || validMsgNickname(overlay.nickname, chatId))
            : '';
          const contactAvatar = isPrivate ? String(current.avatar || overlay.avatar || '') : '';
          const serverTs = Number(current.last_ts || 0);
          const eventTs = Number(overlay.last_ts || 0);
          if (serverTs > eventTs && Number(current.group_info_updated_at || 0) >= Number(overlay.group_info_updated_at || 0)) {
            if (isPrivate && (keepFriendOverlay || (!validMsgNickname(current.nickname, chatId) && contactName)
              || (!current.avatar && contactAvatar))) {
              // 消息摘要跟随较新服务器记录，只保留后台已取得的联系人资料。
              const profile = {...current, ...friendState, nickname:current.remark || contactName || current.nickname, avatar:contactAvatar};
              byId.set(chatId, profile);
              msgState.realtimeChats.set(chatId, profile);
            } else msgState.realtimeChats.delete(chatId);
            return;
          }
          const adminKnown = msgState.adminByChat.has(chatId)
            ? Boolean(msgState.adminByChat.get(chatId))
            : Boolean(current.is_admin || overlay.is_admin);
          const groupProfile = Number(current.group_info_updated_at || 0) > Number(overlay.group_info_updated_at || 0) ? current : overlay;
          const groupName = String(groupProfile.group_name || current.group_name || overlay.group_name || '');
          byId.set(chatId, {
            ...current,
            ...(serverTs > eventTs ? {} : overlay),
            group_name:groupName,
            group_info_updated_at:Math.max(Number(current.group_info_updated_at || 0), Number(overlay.group_info_updated_at || 0)),
            member_num:groupProfile.member_num ?? current.member_num ?? overlay.member_num,
            group_member_num:groupProfile.group_member_num ?? current.group_member_num ?? overlay.group_member_num,
            nickname:current.remark || (current.chat_type === 'group' && groupName) || contactName || current.nickname || overlay.nickname,
            ...(isPrivate ? {avatar:contactAvatar, ...friendState} : {}),
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
        return [...byId.values()].filter((chat) => msgChatMatchesView(chat, {ignoreTypeFilter:true})).sort((left, right) =>
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
      // 远端权限和禁言先返回快照；当前群有限补查不占用聊天首屏请求。
      const msgGroupSnapshotTasks = {roles:null, mutes:null};
      const msgGroupSnapshotTarget = () => {
        if (msgState.chatType !== 'group' || !msgState.chatId) return null;
        const chatId = String(msgState.chatId);
        const chat = msgState.chats.find((item) => String(item.chat_id || '') === chatId && item.chat_type === 'group');
        return {chat_id:chatId, chat_type:'group', appid:String(chat?.appid || msgState.chatAppid || '').trim()};
      };
      const msgGroupSnapshotScope = (target) => JSON.stringify([target?.chat_id || '', target?.chat_type || '', target?.appid || '']);
      const msgGroupSnapshotVisible = () => !$('page-messages')?.hidden && document.visibilityState !== 'hidden';
      const stopMsgGroupSnapshots = () => {
        Object.keys(msgGroupSnapshotTasks).forEach((kind) => {
          const task = msgGroupSnapshotTasks[kind];
          msgGroupSnapshotTasks[kind] = null;
          if (task?.timer || task?.controller) {
            if (kind === 'roles') msgState.lastRolesAt = 0;
            else msgState.muteRequestAt = 0;
          }
          if (task?.timer) clearTimeout(task.timer);
          if (task?.controller) task.controller.abort();
        });
      };
      const msgGroupSnapshotMatches = (data, target) => String(data?.chat_id || '') === target.chat_id
        && String(data?.chat_type || '') === target.chat_type
        && (!target.appid || String(data?.appid || '') === target.appid);
      const requestMsgGroupSnapshot = (kind, target, apply, force = false, retryTask = null) => {
        if (!target || !msgGroupSnapshotVisible() || msgGroupSnapshotScope(msgGroupSnapshotTarget()) !== msgGroupSnapshotScope(target)) return Promise.resolve(null);
        let task = msgGroupSnapshotTasks[kind];
        if (retryTask && task !== retryTask) return Promise.resolve(null);
        if (!retryTask && task?.scope === msgGroupSnapshotScope(target) && task.promise) {
          if (force) task.forceAfter = true;
          return task.promise;
        }
        if (!retryTask && !force && task?.scope === msgGroupSnapshotScope(target) && task.timer) return Promise.resolve(null);
        if (!retryTask) {
          if (task?.timer) clearTimeout(task.timer);
          if (task?.controller) task.controller.abort();
          task = {target, scope:msgGroupSnapshotScope(target), attempts:0, promise:null, timer:null, controller:null, forceAfter:false};
          msgGroupSnapshotTasks[kind] = task;
        }
        const isCurrent = () => msgGroupSnapshotTasks[kind] === task && msgGroupSnapshotVisible()
          && msgGroupSnapshotScope(msgGroupSnapshotTarget()) === task.scope;
        const controller = new AbortController();
        task.controller = controller;
        const timeout = setTimeout(() => controller.abort(), 10000);
        const promise = (async () => {
          try {
            const path = kind === 'roles' ? 'message/group-roles' : 'message/group-member/mutes';
            const data = await api(path, {method:'POST', signal:controller.signal, body:JSON.stringify({...target, ...(force ? {force:true} : {})})});
            if (!isCurrent() || !msgGroupSnapshotMatches(data, target)) return null;
            // pending 表示尚无权威结果；空成员数组不能覆盖已经显示的禁言。
            if (kind === 'mutes' || (!data.pending && data.has_data !== false)) apply(data);
            if (data.pending || data.refreshing) {
              const retryDelays = [1000, 1000, 2000, 3000, 5000, 5000];
              if (task.attempts < retryDelays.length) {
                const delay = Math.max(retryDelays[task.attempts], Math.min(5000, Number(data.retry_after_ms) || 1000));
                task.attempts += 1;
                task.timer = setTimeout(() => {
                  task.timer = null;
                  if (isCurrent()) void requestMsgGroupSnapshot(kind, target, apply, false, task);
                }, delay);
              } else {
                // 有限补查覆盖慢请求；队列更久时交还常规轮询，不无限追加定时器。
                if (kind === 'roles') msgState.lastRolesAt = 0;
                else { msgState.muteRequestAt = Date.now(); apply({...data, pending:false, refreshing:false, stale:Boolean(data.has_data)}); }
              }
            }
            return data;
          } catch (error) {
            if (isCurrent()) {
              if (kind === 'roles' && error.name !== 'AbortError') msgState.adminScanFailures.set(target.chat_id, Date.now());
              else if (kind === 'mutes') apply({...target, has_data:false, pending:false, refreshing:false, available:false, status:'unavailable'});
            }
            return null;
          } finally {
            clearTimeout(timeout);
            if (task.promise === promise) { task.promise = null; task.controller = null; }
            if (task.forceAfter && isCurrent()) {
              task.forceAfter = false;
              if (task.timer) clearTimeout(task.timer);
              task.timer = null;
              void requestMsgGroupSnapshot(kind, target, apply, true);
            }
          }
        })();
        task.promise = promise;
        return promise;
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
        if (autoScanAdminRunning || !msgGroupSnapshotVisible()) return;
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
              && !(msgState.chatType === 'group' && String(msgState.chatId) === id)
              && scanAllowed;
          }).slice(0, 1);
          let membershipChanged = false;
          for (const group of groupsToScan) {
            const chatId = String(group.chat_id || '');
            msgState.adminScanAttempted.add(chatId);
            msgState.adminCheckedAt.set(chatId, Date.now());
            const scanRoleToken = Number(msgState.adminRequestToken || 0);
            try {
              const target = {chat_id:chatId, chat_type:'group', appid:String(group.appid || '').trim()};
              const res = await api('message/group-roles', {method:'POST', body:JSON.stringify(target)});
              if (!msgGroupSnapshotVisible() || !msgGroupSnapshotMatches(res, target)) continue;
              if (res.pending || res.has_data === false) continue;
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
              composerMentionPicker.roles.set(JSON.stringify([chatId, target.appid]), role);
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
      const getMsgChatRowHeight = (node) => {
        const value = Number.parseFloat(window.getComputedStyle(node).getPropertyValue('--msg-chat-row-height'));
        return Number.isFinite(value) && value > 0 ? value : 52;
      };
      const renderMsgChatRow = (item, top) => {
        const placement = `position:absolute;top:${top}px;left:0;right:0;height:${item.height}px;`;
        if (item.kind === 'folder') {
          const collapsed = Boolean(msgState.folderCollapsed[item.type]);
          return `<button class="msg-chat-folder" style="${placement}" type="button" data-msg-folder-toggle="${item.type}" aria-expanded="${!collapsed}"><span class="msg-chat-folder-caret" aria-hidden="true"></span><strong>${item.label}</strong><small>${item.count}</small></button>`;
        }
        if (item.kind === 'divider') return `<div class="msg-chat-divider" style="${placement}" role="separator">${item.type === 'user' ? '已删除好友' : '已移除群聊'}</div>`;
        const chat = item.chat;
        const avatarSource = chat.chat_type === 'group'
          ? (chat.group_avatar || chat.group_avatar_url || '')
          : (chat.avatar || chat.avatar_url || '');
        const av = safeMediaUrl(String(avatarSource).trim())
          || avatarUrl(chat.chat_id, chat.chat_type, chat.appid);
        if (chat.appid) window.msgAppid = chat.appid;
        const typeTag = chat.chat_type === 'user' ? '<span class="msg-chat-type">私聊</span>' : '<span class="msg-chat-type">群聊</span>';
        const viewing = msgState.chatId === chat.chat_id;
        const removed = msgChatIsRemoved(chat);
        const viewingAtBottom = viewing && !$('page-messages')?.hidden && msgState.pendingNewMessages === 0 && msgBodyNearBottom($('msg-body'));
        const unread = viewingAtBottom ? 0 : Number(chat.unread || 0);
        if (viewingAtBottom && Number(chat.unread || 0) > 0) queueMicrotask(() => markMsgRead(chat.chat_id));
        const removedText = chat.chat_type === 'user' ? '对方已删除机器人好友' : '你已被移除群聊';
        const preview = removed ? removedText : (item.preview || '（无文本内容）');
        return `<button type="button" class="msg-chat ${chat.pinned ? 'pinned' : ''} ${viewing ? 'active' : ''}${removed ? ' removed' : ''}" style="${placement}" data-msg-chat="${esc(chat.chat_id)}" data-msg-type="${esc(chat.chat_type)}" data-msg-pinned="${chat.pinned ? '1' : '0'}" data-msg-removed="${removed ? '1' : '0'}" title="${removed ? removedText : (chat.pinned ? '取消置顶' : '置顶')}">
          <span class="msg-chat-avatar">${avatarHtml(av, chat.nickname || '群')}</span>
          <span class="msg-chat-main"><span class="msg-chat-top"><strong class="${chat.is_admin ? 'admin' : ''}">${esc(chat.nickname || chat.chat_id)}</strong>${typeTag}<small>${esc(fmtChatTime(chat.last_time))}</small></span>
          <span class="msg-chat-sub-row"><span class="msg-chat-sub">${esc(preview)}</span>${unread > 0 ? `<span class="msg-chat-badge">${unread}</span>` : ''}</span>
          <span class="msg-chat-meta">${chat.chat_type === 'group' ? `群消息 ${chat.msg_count} 条` : `私聊消息 ${chat.msg_count} 条`}${chat.remark ? ' · 已备注' : ''}</span></span>
        </button>`;
      };
      const renderMsgChatVirtualWindow = () => {
        const node = $('msg-chats');
        const rows = msgState.chatListRows;
        if (!node || !rows.length) return;
        const offsets = msgState.chatListOffsets;
        const rowHeight = msgState.chatListRowHeight;
        const viewport = Math.max(0, node.clientHeight);
        if (!viewport) return;
        const paddingTop = Number.parseFloat(window.getComputedStyle(node).paddingTop) || 0;
        const scrollTop = Math.max(0, node.scrollTop - paddingTop);
        const lowerBound = (value) => {
          let low = 0;
          let high = offsets.length;
          while (low < high) {
            const middle = (low + high) >> 1;
            if (offsets[middle] < value) low = middle + 1;
            else high = middle;
          }
          return low;
        };
        const overscan = Math.max(8, Math.ceil(viewport / rowHeight));
        const firstVisible = Math.min(rows.length - 1, Math.max(0, lowerBound(scrollTop) - 1));
        const lastVisible = Math.min(rows.length, lowerBound(scrollTop + viewport) + 1);
        const start = Math.max(0, firstVisible - overscan);
        const end = Math.min(rows.length, Math.max(start + 1, lastVisible + overscan));
        if (start === msgState.chatListWindowStart && end === msgState.chatListWindowEnd) return;
        let track = node.firstElementChild;
        if (!track || !track.classList.contains('msg-chat-list-track')) {
          track = document.createElement('div');
          track.className = 'msg-chat-list-track';
          node.replaceChildren(track);
        }
        track.style.height = `${msgState.chatListContentHeight}px`;
        const visibleRows = rows.slice(start, end)
          .map((row, index) => renderMsgChatRow(row, offsets[start + index] || 0))
          .join('');
        track.innerHTML = visibleRows;
        msgState.chatListWindowStart = start;
        msgState.chatListWindowEnd = end;
      };
      const renderMsgChats = (data) => {
        const node = $('msg-chats');
        if (!node) return;
        if (msgState.chatListScrollActive || msgState.chatListPointerActive) {
          msgState.chatListPendingData = data;
          return;
        }
        const forceListTop = !msgState.chatListServerLoaded || msgState.chatListTopPending || !msgState.chatListRendered;
        const previousTop = node.scrollTop;
        const wasAtListTop = previousTop <= 8;
        const listContentTop = () => {
          const style = window.getComputedStyle(node);
          return node.getBoundingClientRect().top + node.clientTop + (Number.parseFloat(style.paddingTop) || 0);
        };
        let anchorChatId = '';
        let anchorOffset = 0;
        if (!forceListTop) {
          const contentTop = listContentTop();
          const anchor = Array.from(node.querySelectorAll('[data-msg-chat]'))
            .find((item) => item.getBoundingClientRect().bottom > contentTop);
          if (anchor) {
            anchorChatId = String(anchor.dataset.msgChat || '');
            anchorOffset = anchor.getBoundingClientRect().top - contentTop;
          }
        }
        const restoreListScroll = () => {
          if (forceListTop || wasAtListTop) {
            node.scrollTop = 0;
            return;
          }
          if (anchorChatId) {
            const anchor = Array.from(node.querySelectorAll('[data-msg-chat]'))
              .find((item) => String(item.dataset.msgChat || '') === anchorChatId);
            if (anchor) {
              node.scrollTop += anchor.getBoundingClientRect().top - listContentTop() - anchorOffset;
              return;
            }
          }
          const maxTop = Math.max(0, node.scrollHeight - node.clientHeight);
          node.scrollTop = Math.min(previousTop, maxTop);
        };
        const settleListScroll = () => {
          restoreListScroll();
          renderMsgChatVirtualWindow();
          if (typeof requestAnimationFrame === 'function') {
            requestAnimationFrame(() => {
              restoreListScroll();
              renderMsgChatVirtualWindow();
              if (forceListTop && msgState.chatListServerLoaded) {
                requestAnimationFrame(() => {
                  restoreListScroll();
                  renderMsgChatVirtualWindow();
                  msgState.chatListTopPending = false;
                });
              }
            });
          } else if (forceListTop && msgState.chatListServerLoaded) {
            setTimeout(() => {
              restoreListScroll();
              renderMsgChatVirtualWindow();
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
        const visibleChats = chats.filter((chat) => msgChatMatchesView(chat));
        const knownChatIds = new Set(chats.map((chat) => String(chat.chat_id || '')).filter(Boolean));
        [msgState.adminByChat, msgState.adminScanAttempted, msgState.adminScanFailures, msgState.adminCheckedAt]
          .forEach((map) => map.forEach((_value, key) => { if (!knownChatIds.has(String(key))) map.delete(key); }));
        window.msgGroupQQ = {}; (chats||[]).forEach((chat) => { if (chat.group_qq) window.msgGroupQQ[chat.chat_id] = chat.group_qq; });
        const rowHeight = getMsgChatRowHeight(node);
        const chatPreviews = new Map();
        const chatRenderSignature = [msgState.filter, msgState.folderCollapsed.group ? 1 : 0, msgState.folderCollapsed.user ? 1 : 0, rowHeight].join(':') + '|' + visibleChats.map((chat) => {
          const preview = chatListPreview(chat.last_content);
          chatPreviews.set(chat, preview);
          return [
            chat.chat_id,
            chat.chat_type,
            chat.nickname || '',
            chat.remark || '',
            preview,
            chat.last_ts,
            chat.last_time || '',
            chat.unread,
            chat.msg_count,
            chat.pinned ? 1 : 0,
            chat.is_admin ? 1 : 0,
            chat.friend_status,
            chat.friend_checked_at,
            chat.is_friend === null ? 'unknown' : chat.is_friend === false ? 0 : 1,
            chat.membership_status,
            chat.in_group === false ? 0 : 1,
            chat.group_avatar || chat.group_avatar_url || (chat.chat_type === 'group' ? '' : (chat.avatar || chat.avatar_url || '')),
          ].join(':');
        }).join('|');
        if (msgState.chatRenderSignature === chatRenderSignature) {
          if (forceListTop) {
            node.scrollTop = 0;
            if (msgState.chatListServerLoaded) msgState.chatListTopPending = false;
          }
          renderMsgChatVirtualWindow();
          scheduleAutoScanAdminGroups(10000);
          return;
        }
        msgState.chatRenderSignature = chatRenderSignature;
        msgState.chatListRendered = true;
        if (!visibleChats.length) {
          msgState.chatListRows = [];
          msgState.chatListOffsets = [0];
          msgState.chatListContentHeight = 0;
          msgState.chatListWindowStart = -1;
          msgState.chatListWindowEnd = -1;
          node.innerHTML = `<div class="msg-empty">${chats.length ? '没有匹配的会话' : '暂无消息会话，机器人收到消息后会出现在这里'}</div>`;
          settleListScroll();
          return;
        }
        const rows = [];
        const appendChatRows = (items) => {
          const removedSections = new Set();
          items.forEach((chat) => {
            const removed = msgChatIsRemoved(chat);
            const type = String(chat.chat_type || 'group');
            if (removed && !removedSections.has(type)) rows.push({kind:'divider', type, height:28});
            if (removed) removedSections.add(type);
            rows.push({kind:'chat', chat, preview:chatPreviews.get(chat) || '', height:rowHeight});
          });
        };
        if (msgState.filter === 'all') {
          const sections = [
            ['group', '群聊'],
            ['user', '私聊'],
          ];
          sections.forEach(([type, label]) => {
            const items = visibleChats.filter((chat) => chat.chat_type === type);
            if (!items.length) return;
            const collapsed = Boolean(msgState.folderCollapsed[type]);
            rows.push({kind:'folder', type, label, count:items.length, height:38});
            if (!collapsed) appendChatRows(items);
          });
        } else {
          appendChatRows(visibleChats);
        }
        msgState.chatListRowHeight = rowHeight;
        msgState.chatListRows = rows;
        msgState.chatListWindowStart = -1;
        msgState.chatListWindowEnd = -1;
        msgState.chatListOffsets = [0];
        rows.forEach((row) => msgState.chatListOffsets.push(msgState.chatListOffsets[msgState.chatListOffsets.length - 1] + row.height));
        msgState.chatListContentHeight = msgState.chatListOffsets[msgState.chatListOffsets.length - 1] || 0;
        if (!forceListTop && !wasAtListTop && anchorChatId) {
          const anchorIndex = rows.findIndex((row) => row.kind === 'chat' && String(row.chat?.chat_id || '') === anchorChatId);
          if (anchorIndex >= 0) node.scrollTop = Math.max(0, msgState.chatListOffsets[anchorIndex] - anchorOffset);
        }
        renderMsgChatVirtualWindow();
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
            if (chatType === 'group') items.push({label:'刷新群信息', action:() => { api('message/group-info/refresh', {method:'POST', body:JSON.stringify({chat_id:chatId})}).then((data) => { applyMsgGroupInfo({...data, chat_id:chatId}); toast('已刷新'); loadMsgChats(true); }).catch((error) => toast(error.message || '刷新失败')); }});
            if (items.length) showMsgCtx(e.clientX, e.clientY, items);
          });
          node.addEventListener('click', (e) => {
            const folder = e.target.closest?.('[data-msg-folder-toggle]');
            if (folder && node.contains(folder)) {
              const type = String(folder.dataset.msgFolderToggle || '');
              if (type === 'group' || type === 'user') {
                msgState.folderCollapsed[type] = !msgState.folderCollapsed[type];
                renderMsgChats({chats:msgState.chats});
              }
              return;
            }
            const el = e.target.closest?.('[data-msg-chat]');
            if (!el || !node.contains(el)) return;
            if (msgState.multi) exitMultiMode();
            const chatId = String(el.dataset.msgChat || '');
            const chatType = String(el.dataset.msgType || 'group');
            if (msgState.chatId === chatId && msgState.chatType === chatType) return;
            if (groupSettingsState.mutating) return toast('正在更新本群设置，请稍候再切换');
            const chat = msgState.chats.find((item) => String(item.chat_id || '') === chatId) || {
              chat_id: chatId,
              chat_type: chatType,
              nickname: chatId,
            };
            selectMsgChat(chat);
            scheduleMsgHistoryLoad(chatId);
            markMsgRead(chatId, true);
          });
        }
      };
      const selectMsgChat = (chat) => {
        closeComposerMentionPicker();
        const chatId = String(chat?.chat_id || '').trim();
        if (!chatId) return;
        const chatType = String(chat?.chat_type || 'group');
        if (groupSettingsState.mutating && (msgState.chatId !== chatId || msgState.chatType !== chatType)) return toast('正在更新本群设置，请稍候再切换');
        if (msgState.chatId !== chatId || msgState.chatType !== chatType) { closeGroupSettings(); groupSettingsState.remarkTarget = null; $('msg-remark-modal').hidden = true; }
        cancelMsgQuoteJump(true);
        setMsgMobileChatOpen(true);
        msgState.chatRemoved = msgChatIsRemoved(chat);
        const localAdmins = getLocalAdminGroups();
        const cachedAdmin = msgState.adminByChat.has(chatId)
          ? Boolean(msgState.adminByChat.get(chatId))
          : Boolean(chat?.is_admin || localAdmins.has(chatId));
        if (cachedAdmin && !msgState.adminByChat.has(chatId)) msgState.adminByChat.set(chatId, true);
        const sameChat = msgState.chatId === chatId && msgState.chatType === chatType;
        // 每次点选会话都重新执行首屏定位，同一会话也不能沿用旧滚动位置。
        msgState.initialScrollChatId = chatId;
        stopMsgGroupSnapshots();
        if (!sameChat) {
          cancelMsgRealtimeMessageRender();
          msgState.panSelectionSaving = false;
          msgState.panSelectionLoading = false;
          msgState.panSelectionData = null;
          msgState.panSelectionRequest = Number(msgState.panSelectionRequest || 0) + 1;
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
        msgState.chatAppid = String(chat?.appid || '').trim();
        msgState.botIsAdmin = cachedAdmin;
        resetMsgAdSwitch();
        msgState.profiles = {};
        msgState.historyData = null;
        clearMsgQuote();
        msgState.messages = [];
        msgState.renderedChatId = '';
        msgState.messageRenderSignature = null;
        clearMsgNewMessages();
        // 先更新右侧会话头和蓝色消息区域的加载占位，历史请求异步完成后再替换内容。
        updateMsgHead({
          chat_name: chat.remark || chat.group_name || chat.nickname || chatId,
          group_info: {member_num: chat.member_num || chat.group_member_num || 0},
        });
        $('msg-refresh-info').hidden = msgState.chatType !== 'group';
        $('msg-remark').hidden = msgState.chatType !== 'group';
        $('msg-group-settings-open').hidden = msgState.chatType !== 'group' || msgState.chatRemoved;
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
            // 先显示上次已读内容，网络结果返回后再合并新消息。
            renderMsgMessages({...cachedHistory, messages:msgState.messages}, {toBottom:true});
          }
        }
        document.querySelectorAll('[data-msg-chat]').forEach((node) => {
          node.classList.toggle('active', String(node.dataset.msgChat || '') === chatId);
        });
        if (msgState.chatType === 'group') {
          void loadGroupAdSwitch();
          void loadMsgPanSelection();
        } else {
          msgState.panSelectionData = null;
          msgState.panSelectionRequest = Number(msgState.panSelectionRequest || 0) + 1;
          updateMsgPanSelector();
        }
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
        const params = {filter:'all', search:msgState.search, page:1, page_size:0};
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
        cancelMsgQuoteJump(true);
        stopMsgGroupSnapshots();
        if (msgState.eventReconnect) { clearTimeout(msgState.eventReconnect); msgState.eventReconnect = null; }
        if (autoScanAdminTimer) { clearTimeout(autoScanAdminTimer); autoScanAdminTimer = null; }
        if (msgState.eventRefreshTimer) { clearTimeout(msgState.eventRefreshTimer); msgState.eventRefreshTimer = null; }
        if (msgState.chatRenderTimer) { clearTimeout(msgState.chatRenderTimer); msgState.chatRenderTimer = null; }
        if (msgState.chatListScrollTimer) { clearTimeout(msgState.chatListScrollTimer); msgState.chatListScrollTimer = null; }
        msgState.chatListScrollActive = false;
        msgState.chatListPointerActive = false;
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
      const applyMsgNickname = (payload) => {
        const chatId = String(payload?.chat_id || '').trim();
        const nickname = validMsgNickname(payload?.nickname, chatId);
        const appid = String(payload?.appid || '').trim();
        if (!chatId || !nickname || String(payload?.chat_type || 'user') !== 'user') return;
        const matches = (chat) => chat && String(chat.chat_id || '') === chatId
          && String(chat.chat_type || '') === 'user'
          && (!appid || !String(chat.appid || '').trim() || String(chat.appid || '').trim() === appid);
        const current = (msgState.chats || []).find(matches);
        const overlay = msgState.realtimeChats.get(chatId);
        const seed = matches(overlay) ? overlay : current;
        if (!seed) return;
        msgState.chats = (msgState.chats || []).map((chat) =>
          matches(chat) ? {...chat, nickname:String(chat.remark || nickname)} : chat,
        );
        // 昵称补查可能早于任何实时消息；从已有联系人保存资料覆盖项。
        msgState.realtimeChats.set(chatId, {...seed, appid:String(seed.appid || appid), nickname:String(seed.remark || nickname)});
        if (msgState.chatId === chatId && msgState.chatType === 'user'
          && (!appid || !String(msgState.chatAppid || '').trim() || String(msgState.chatAppid || '').trim() === appid)) {
          const selected = msgState.chats.find((chat) => String(chat.chat_id || '') === chatId);
          msgState.profiles = mergeMsgProfileMaps(msgState.profiles, {[chatId]:{nickname}});
          updateMsgHead({chat_name:String(selected?.remark || nickname)});
          if (msgState.renderedChatId === chatId) renderMsgMessages({...msgState.historyData, messages:msgState.messages, member_profiles:msgState.profiles}, {forceRender:true, previousTop:$('msg-body')?.scrollTop || 0, previousHeight:$('msg-body')?.scrollHeight || 0});
        }
        renderMsgChats({chats:msgState.chats});
      };
      const handleMsgRealtimeData = (raw) => {
        try {
          const envelope = typeof raw === 'string' ? JSON.parse(raw || '{}') : raw;
          if (envelope?.type === 'message') { applyMsgRealtimeEvent(envelope.data || {}); scheduleMsgRealtimeRefresh(); }
          else if (envelope?.type === 'group_status') applyMsgGroupStatus(envelope.data || {});
          else if (envelope?.type === 'group_info') applyMsgGroupInfo(envelope.data || {});
          else if (envelope?.type === 'nickname') { applyMsgNickname(envelope.data || {}); scheduleMsgRealtimeRefresh(); }
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
          const data = await api('message/group-ad', {method:'POST', body:JSON.stringify({...captureGroupTarget(), chat_id:chatId, chat_type:'group', action:'get'})});
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
          const data = await api('message/group-ad', {method:'POST', body:JSON.stringify({...captureGroupTarget(), chat_id:chatId, chat_type:'group', action:'set', enabled})});
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
      const updateMsgPanSelector = (loading = false) => {
        const wrap = $('msg-pan-account-wrap');
        const select = $('msg-pan-account-select');
        if (!wrap || !select) return;
        const visible = msgState.chatType === 'group' && Boolean(msgState.chatId) && !msgState.chatRemoved;
        wrap.hidden = !visible;
        if (!visible) {
          select.replaceChildren();
          select.disabled = true;
          select.removeAttribute('title');
          return;
        }
        const data = msgState.panSelectionData;
        const pending = loading || msgState.panSelectionLoading;
        if (pending || !data) {
          select.innerHTML = `<option value="">${pending ? '读取中' : '读取失败'}</option>`;
          select.disabled = true;
          select.removeAttribute('title');
          return;
        }
        const choices = Array.isArray(data.choices) ? data.choices : [];
        const defaultLabel = data.default?.label ? `跟随默认 · ${data.default.label}` : '跟随默认 · 暂无可用账号';
        const options = [`<option value="__default__">${esc(defaultLabel)}</option>`, ...choices.map((choice) => `<option value="${esc(choice.value)}">${esc(choice.label)}</option>`)];
        const selectedValue = msgState.panSelectionSaving ? select.value : data.selected_value;
        select.innerHTML = options.join('');
        select.value = selectedValue || '__default__';
        select.disabled = !data.editable || msgState.panSelectionSaving || !choices.length;
        select.title = data.editable ? '只影响当前群；跟随默认会使用网盘配置页中的默认网盘' : '数据库未配置，群网盘选择不能保存';
      };
      const isMsgPanSelectionCurrent = (request, chatId, appid) => request === msgState.panSelectionRequest
        && msgState.chatId === chatId && msgState.chatType === 'group'
        && (!appid || String(msgState.chatAppid || '') === appid) && !msgState.chatRemoved;
      const loadMsgPanSelection = async () => {
        const chatId = String(msgState.chatId || '').trim();
        const appid = String(msgState.chatAppid || '');
        const request = Number(msgState.panSelectionRequest || 0) + 1;
        msgState.panSelectionRequest = request;
        msgState.panSelectionData = null;
        msgState.panSelectionLoading = false;
        msgState.panSelectionSaving = false;
        if (msgState.chatType !== 'group' || !chatId || msgState.chatRemoved) {
          updateMsgPanSelector();
          return;
        }
        msgState.panSelectionLoading = true;
        updateMsgPanSelector(true);
        try {
          const data = await api('message/group-pan', {method:'POST', body:JSON.stringify({chat_id:chatId, action:'get'})});
          if (!isMsgPanSelectionCurrent(request, chatId, appid)) return;
          msgState.panSelectionData = data;
        } catch (error) {
          if (!isMsgPanSelectionCurrent(request, chatId, appid)) return;
          if (error.status === 401) showAuthError(error);
        } finally {
          if (isMsgPanSelectionCurrent(request, chatId, appid)) {
            msgState.panSelectionLoading = false;
            updateMsgPanSelector();
          }
        }
      };
      const saveMsgPanSelection = async () => {
        const select = $('msg-pan-account-select');
        const chatId = String(msgState.chatId || '').trim();
        const appid = String(msgState.chatAppid || '');
        const value = String(select?.value || '');
        if (!select || !chatId || msgState.chatType !== 'group' || msgState.chatRemoved || !msgState.panSelectionData?.editable || msgState.panSelectionSaving || msgState.panSelectionLoading) return;
        let payload = {chat_id:chatId, action:'reset'};
        if (value !== '__default__') {
          const separator = value.lastIndexOf(':');
          const platform = separator > 0 ? value.slice(0, separator) : '';
          const index = Number(value.slice(separator + 1));
          if (!['UC','夸克','百度'].includes(platform) || !Number.isInteger(index) || index < 1) return toast('网盘账号选择无效');
          payload = {chat_id:chatId, action:'set', platform, index};
        }
        const request = Number(msgState.panSelectionRequest || 0) + 1;
        msgState.panSelectionRequest = request;
        msgState.panSelectionSaving = true;
        updateMsgPanSelector();
        try {
          const result = await api('message/group-pan', {method:'POST', body:JSON.stringify(payload)});
          if (!isMsgPanSelectionCurrent(request, chatId, appid)) return;
          toast(result.message || '本群网盘账号已更新');
        } catch (error) {
          if (!isMsgPanSelectionCurrent(request, chatId, appid)) return;
          if (error.status === 401) showAuthError(error);
          else toast(error.message || '本群网盘账号保存失败');
        } finally {
          if (isMsgPanSelectionCurrent(request, chatId, appid)) {
            msgState.panSelectionSaving = false;
            await loadMsgPanSelection();
          }
        }
      };
      const updateMsgHead = (data) => {
        if (msgState.chatType === 'user') data = {...data, ...syncMsgFriendState(msgState.chatId, data)};
        const nameEl = $('msg-head-name');
        const curChat = (msgState.chats || []).find((c) => String(c.chat_id || '') === String(msgState.chatId || '') && String(c.chat_type || 'group') === msgState.chatType);
        const knownInfo = data.group_info || {};
        const newerGroupInfo = Number(knownInfo.updated_at || 0) > Number(curChat?.group_info_updated_at || 0);
        const groupName = newerGroupInfo ? (knownInfo.group_name || curChat?.group_name) : (curChat?.group_name || knownInfo.group_name);
        const knownName = curChat?.remark || (msgState.chatType === 'group' ? groupName : '') || data.chat_name || curChat?.nickname;
        const headKey = msgState.chatType + '|' + String(msgState.chatId || '');
        const previousName = nameEl.dataset.chatKey === headKey ? nameEl.textContent : '';
        const blankContact = msgState.chatType === 'user' && !curChat?.remark && msgState.profiles?.[msgState.chatId]?.nickname_blank && !validMsgNickname(knownName, msgState.chatId);
        nameEl.textContent = blankContact ? '\u00a0' : (knownName || previousName || String(msgState.chatId || '') || '未命名会话');
        nameEl.dataset.chatKey = headKey;
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
        const gNum = Number(gInfo.member_num ?? curChat?.member_num ?? curChat?.group_member_num ?? 0);
        const removed = msgState.chatType === 'user' ? msgChatIsRemoved({...curChat, ...data, chat_type:'user'}) : (msgState.chatRemoved || gInfo.membership_status === 'removed' || curChat?.membership_status === 'removed' || curChat?.in_group === false);
        msgState.chatRemoved = removed;
        $('msg-head-sub').textContent = msgState.chatType === 'group'
          ? (removed ? '你已被移除群聊' : `群聊 · ${esc(msgState.chatId)}${gNum > 0 ? ` · 群成员 ${gNum} 人` : ''}`)
          : (removed ? '对方已删除机器人好友 · 保留聊天记录' : `私聊 · ${esc(msgState.chatId)}`);
        $('msg-composer').hidden = removed;
        if (removed) {
          $('msg-ad-switch').hidden = true;
          $('msg-refresh-info').hidden = true;
          $('msg-remark').hidden = true;
          $('msg-group-settings-open').hidden = true;
          closeGroupSettings(true);
        }
        updateMsgPanSelector();
        if (data.group_info && groupSettingsCurrent(groupSettingsState.session)) renderGroupSettingsProfile(groupSettingsState.session, data.group_info);
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
        insertComposerMention(uid, nick);
        toast(`已插入 @${nick || '用户'}（将以 Markdown 发送）`);
      };
      const removeQuoteMention = () => {
        getComposerEditor()?.querySelectorAll('[data-composer-quote-mention="1"]').forEach((node) => {
          const spacer = node._composerMentionSpace;
          node.remove();
          if (spacer?.parentNode && String(spacer.nodeValue || '').startsWith('\u00a0')) {
            spacer.nodeValue = spacer.nodeValue.slice(1);
            if (!spacer.nodeValue) spacer.remove();
          }
        });
        msgState.composerSelection = null;
      };
      const insertComposerMention = (userId, nickname = '', quote = false) => {
        const id = String(userId || '').trim();
        const editor = getComposerEditor();
        if (!editor || (id !== 'all' && !mentionIdPattern.test(id))) return;
        const profile = msgState.profiles?.[id] || {};
        const name = id === 'all' ? '全体成员'
          : displayMsgNickname({user_id:id, nickname, nickname_blank:isBlankMsgNickname(nickname)}, profile, '用户');
        editor.focus();
        const range = quote ? document.createRange() : restoreComposerSelection();
        if (!range) return;
        if (quote) { range.selectNodeContents(editor); range.collapse(true); }
        else range.deleteContents();
        const node = document.createElement('span');
        node.className = 'composer-mention';
        node.dataset.composerMention = id;
        if (quote) node.dataset.composerQuoteMention = '1';
        node.contentEditable = 'false';
        node.textContent = `@${name}`;
        range.insertNode(node);
        const spacer = document.createTextNode('\u00a0');
        node._composerMentionSpace = spacer;
        node.after(spacer);
        range.setStartAfter(spacer);
        range.collapse(true);
        const selection = window.getSelection?.();
        selection?.removeAllRanges();
        selection?.addRange(range);
        msgState.composerSelection = range.cloneRange();
      };
      const composerMentionPicker = {scope:'', signature:'', dismissed:'', items:[], index:0, composing:false, frame:null, roles:new Map()};
      const composerMentionScope = () => JSON.stringify([msgState.chatId, msgState.chatAppid]);
      const closeComposerMentionPicker = (dismiss = false) => {
        if (dismiss) composerMentionPicker.dismissed = composerMentionPicker.signature;
        composerMentionPicker.scope = '';
        composerMentionPicker.signature = '';
        composerMentionPicker.items = [];
        const menu = $('msg-mention-picker');
        if (menu) { menu.hidden = true; menu.replaceChildren(); }
        const editor = getComposerEditor();
        editor?.setAttribute('aria-expanded', 'false');
        editor?.removeAttribute('aria-activedescendant');
      };
      const composerMentionContext = () => {
        const editor = getComposerEditor();
        if (composerMentionPicker.composing || !editor || document.activeElement !== editor
          || msgState.chatType !== 'group' || !msgState.chatId || msgState.chatRemoved
          || composerHasMedia() || !['text','markdown'].includes(msgState.sendType)
          || activeView !== 'messages' || document.visibilityState === 'hidden') return null;
        const selection = window.getSelection?.();
        if (!selection?.rangeCount || !selection.isCollapsed) return null;
        const caret = selection.getRangeAt(0);
        let node = caret.startContainer, offset = caret.startOffset;
        if (node.nodeType === Node.ELEMENT_NODE) {
          node = node.childNodes[offset - 1];
          if (!node || node.nodeType !== Node.TEXT_NODE) return null;
          offset = String(node.nodeValue || '').length;
        }
        if (node.nodeType !== Node.TEXT_NODE || !editor.contains(node)
          || node.parentElement?.closest('[data-composer-mention],[data-composer-image]')) return null;
        const before = String(node.nodeValue || '').slice(0, offset);
        const match = /@([^\s@<>]{0,64})$/.exec(before);
        if (!match || before[match.index - 1] === '<') return null;
        const range = document.createRange();
        range.setStart(node, match.index);
        range.setEnd(node, offset);
        const scope = composerMentionScope();
        const prefix = document.createRange();
        prefix.selectNodeContents(editor);
        prefix.setEnd(node, offset);
        return {range, query:match[1], scope, signature:JSON.stringify([scope, prefix.toString()])};
      };
      const composerMentionCandidates = (query) => {
        const wanted = String(query || '').toLocaleLowerCase();
        const currentAppid = String(msgState.chatAppid || '');
        const role = composerMentionPicker.roles.get(JSON.stringify([msgState.chatId, currentAppid]));
        const items = [{id:'all', name:'全体成员', nickname:'', detail:role === 'member' || (!role && !msgState.botIsAdmin) ? '需机器人为群管理员' : '群内所有成员', disabled:role === 'member'}];
        Object.entries(msgState.profiles || {}).forEach(([id, profile]) => {
          if (!mentionIdPattern.test(id) || !profile || typeof profile !== 'object'
            || (profile.appid && String(profile.appid) !== currentAppid)
            || (profile.group_id && String(profile.group_id) !== msgState.chatId)
            || (profile.group_openid && String(profile.group_openid) !== msgState.chatId)) return;
          const name = validMsgNickname(profile.nickname || profile.username, id);
          const blank = profile.nickname_blank || isBlankMsgNickname(profile.nickname || profile.username);
          if (!name && !blank) return;
          const avatar = safeMediaUrl(profile.avatar) || safeMediaUrl(profile.avatar_url)
            || (currentAppid ? avatarUrl(id, 'user', currentAppid) : '');
          items.push({id, name:name || '空白昵称', nickname:name || '\u00a0', avatar, detail:'群成员', disabled:false});
        });
        return items.filter((item) => !wanted || item.name.toLocaleLowerCase().includes(wanted) || (wanted.length >= 5 && item.id.toLocaleLowerCase().includes(wanted)));
      };
      const positionComposerMentionPicker = () => {
        const menu = $('msg-mention-picker');
        if (!menu || menu.hidden) return;
        const context = composerMentionContext();
        if (!context || context.scope !== composerMentionPicker.scope) return closeComposerMentionPicker();
        const rect = context.range.getBoundingClientRect();
        const anchor = rect.height ? rect : getComposerEditor().getBoundingClientRect();
        const width = Math.min(260, Math.max(180, window.innerWidth - 20));
        menu.style.width = `${width}px`;
        const height = menu.getBoundingClientRect().height;
        const left = Math.max(10, Math.min(anchor.left, window.innerWidth - width - 10));
        let top = anchor.top - height - 8;
        if (top < 10) top = anchor.bottom + 8;
        top = Math.max(10, Math.min(top, window.innerHeight - height - 10));
        menu.style.left = `${left}px`;
        menu.style.top = `${top}px`;
      };
      const selectComposerMentionItem = (index) => {
        const item = composerMentionPicker.items[index];
        const context = composerMentionContext();
        if (!item || item.disabled || !context || context.signature !== composerMentionPicker.signature) return;
        if (item.id === 'all' && composerMentionPicker.roles.get(JSON.stringify([msgState.chatId, msgState.chatAppid])) === 'member') return updateComposerMentionPicker();
        const range = context.range.cloneRange();
        closeComposerMentionPicker();
        msgState.composerSelection = range;
        msgState.sendType = 'markdown';
        $('msg-composer-tabs')?.querySelectorAll('[data-msg-type]').forEach((button) => button.classList.toggle('active', button.dataset.msgType === 'markdown'));
        renderMsgExtra();
        insertComposerMention(item.id, item.nickname);
      };
      const highlightComposerMentionItem = (index) => {
        const menu = $('msg-mention-picker');
        composerMentionPicker.index = index;
        menu?.querySelectorAll('[data-mention-index]').forEach((button) => {
          const selected = Number(button.dataset.mentionIndex) === index;
          button.classList.toggle('active', selected);
          button.setAttribute('aria-selected', String(selected));
        });
        const active = menu?.querySelector(`[data-mention-index="${index}"]`);
        if (active) {
          getComposerEditor()?.setAttribute('aria-activedescendant', active.id);
          active.scrollIntoView({block:'nearest'});
        } else getComposerEditor()?.removeAttribute('aria-activedescendant');
      };
      const updateComposerMentionPicker = () => {
        const context = composerMentionContext();
        const menu = $('msg-mention-picker');
        if (!context || !menu) return closeComposerMentionPicker();
        if (composerMentionPicker.dismissed === context.signature) return closeComposerMentionPicker();
        const previousId = composerMentionPicker.items[composerMentionPicker.index]?.id;
        const items = composerMentionCandidates(context.query);
        composerMentionPicker.items = items;
        composerMentionPicker.scope = context.scope;
        composerMentionPicker.signature = context.signature;
        composerMentionPicker.dismissed = '';
        menu.innerHTML = '<div class="msg-mention-heading">提及</div><div class="msg-mention-options">' + (items.length ? items.map((item, index) =>
          `<button type="button" id="msg-mention-option-${index}" class="msg-mention-item" role="option" tabindex="-1" data-mention-index="${index}" aria-selected="false"${item.disabled ? ' disabled aria-disabled="true"' : ''}><span class="msg-mention-avatar${item.id === 'all' ? ' everyone' : ''}" aria-hidden="true">${item.id === 'all' ? '@' : avatarHtml(item.avatar, Array.from(item.name)[0] || '·')}</span><span class="msg-mention-copy"><strong>${esc(item.name)}</strong><small>${esc(item.detail)}</small></span></button>`
        ).join('') : '<div class="msg-mention-empty" role="status">暂无匹配的成员</div>') + '</div>';
        menu.hidden = false;
        getComposerEditor()?.setAttribute('aria-expanded', 'true');
        let index = items.findIndex((item) => item.id === previousId && !item.disabled);
        if (index < 0) index = items.findIndex((item) => !item.disabled);
        highlightComposerMentionItem(index);
        positionComposerMentionPicker();
      };
      const scheduleComposerMentionPicker = () => {
        if (composerMentionPicker.frame !== null) return;
        composerMentionPicker.frame = requestAnimationFrame(() => { composerMentionPicker.frame = null; updateComposerMentionPicker(); });
      };
      const handleComposerMentionKeydown = (event) => {
        const menu = $('msg-mention-picker');
        if (!menu || menu.hidden || event.isComposing || composerMentionPicker.composing || event.keyCode === 229) return false;
        if (event.key === 'Escape') { event.preventDefault(); closeComposerMentionPicker(true); return true; }
        if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return false;
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          const eligible = composerMentionPicker.items.map((item, index) => item.disabled ? -1 : index).filter((index) => index >= 0);
          if (eligible.length) {
            const position = eligible.indexOf(composerMentionPicker.index);
            highlightComposerMentionItem(eligible[(position + (event.key === 'ArrowDown' ? 1 : -1) + eligible.length) % eligible.length]);
          }
          return true;
        }
        if (event.key === 'Enter') {
          event.preventDefault();
          selectComposerMentionItem(composerMentionPicker.index);
          return true;
        }
        return false;
      };
      const clearMsgQuote = () => {
        removeQuoteMention();
        msgState.quote = null;
        const preview = $('msg-quote-preview');
        if (preview) preview.hidden = true;
        $('msg-quote-text')?.replaceChildren();
      };
      const renderMsgQuotePreview = () => {
        const preview = $('msg-quote-preview');
        const previewText = $('msg-quote-text');
        const quote = msgState.quote;
        if (!preview || !previewText) return;
        if (!quote || quote.chatId !== msgState.chatId || quote.chatType !== msgState.chatType || (quote.appid && quote.appid !== String(msgState.chatAppid || ''))) {
          preview.hidden = true;
          return;
        }
        const index = buildMsgReferenceIndex(msgState.historyData?.messages || msgState.messages, {}, msgState.profiles);
        const summary = index.get(quote.id) || msgQuoteSummary({user_id:quote.userId, nickname:quote.name, nickname_blank:quote.nickname_blank, content:quote.text}, msgState.profiles);
        quote.name = summary.nickname;
        quote.nickname_blank = summary.nickname_blank;
        quote.text = summary.content;
        previewText.innerHTML = `<span class="msg-quote-name">${esc(summary.nickname)}</span><span class="msg-quote-content">${esc(plainMsgPreview(summary.content) || '（空消息）')}</span>`;
        preview.hidden = false;
        getComposerEditor()?.querySelectorAll('[data-composer-quote-mention="1"]').forEach((node) => {
          node.textContent = `@${summary.nickname}`;
        });
      };
      const setMsgQuote = (messageId, userId, nickname, quotedText = '', refidx = '') => {
        const id = String(messageId || '').trim();
        if (!id) return;
        const uid = String(userId || '').trim();
        const index = buildMsgReferenceIndex([...(msgState.historyData?.messages || []), ...msgState.messages], {}, msgState.profiles);
        const summary = index.get(id) || msgQuoteSummary({user_id:uid, nickname, content:quotedText}, msgState.profiles);
        removeQuoteMention();
        msgState.quote = {id, refidx:String(refidx || summary.refidx || '').trim(), userId:uid || summary.user_id, name:summary.nickname, nickname_blank:summary.nickname_blank, text:summary.content, chatId:msgState.chatId, chatType:msgState.chatType, appid:String(msgState.chatAppid || '')};
        renderMsgQuotePreview();
        if (msgState.quote.userId && msgState.chatType === 'group') {
          msgState.sendType = 'markdown';
          $('msg-composer-tabs')?.querySelectorAll('[data-msg-type]').forEach((x) => x.classList.toggle('active', x.dataset.msgType === 'markdown'));
          renderMsgExtra();
          insertComposerMention(msgState.quote.userId, summary.nickname, true);
        }
        getComposerEditor()?.focus();
      };
      const copyMsgText = async (text, row = null, {exact = false, notify = true} = {}) => {
        let copyText = String(text ?? '');
        if (!exact) {
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
        }
        if (!copyText) { if (notify) toast('没有可复制的消息内容'); return false; }
        try {
          let copied = false;
          if (navigator.clipboard?.writeText && window.isSecureContext) {
            try { await navigator.clipboard.writeText(copyText); copied = true; } catch (_) {}
          }
          if (!copied) {
            const previousFocus = document.activeElement;
            const ta = document.createElement('textarea');
            ta.value = copyText;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            try {
              ta.focus();
              ta.select();
              ta.setSelectionRange(0, ta.value.length);
              if (!document.execCommand('copy')) throw new Error('clipboard_failed');
            } finally {
              ta.remove();
              previousFocus?.focus({preventScroll:true});
            }
          }
          if (notify) toast('已复制');
          return true;
        } catch (_) { if (notify) toast('复制失败，请重试'); return false; }
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
        if (!confirm(`确定撤回选中的 ${ids.length} 条消息吗？`)) return;
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
        const isOfficial = String(message.source || '').trim().toLowerCase() === 'qq_official';
        const sessionId = normalizeMsgIdentity(message._session || msgState.chatId);
        const userId = normalizeMsgIdentity(message.user_id);
        if (isOfficial) {
          let rawPayload = message.raw_message;
          if (typeof rawPayload === 'string') {
            try { rawPayload = JSON.parse(rawPayload); } catch (_) { rawPayload = null; }
          }
          if (rawPayload && typeof rawPayload === 'object' && sessionId) {
            const payloads = [rawPayload];
            ['d', 'data', 'message', 'payload'].forEach((field) => {
              const nested = rawPayload[field];
              if (nested && typeof nested === 'object' && !Array.isArray(nested)) payloads.push(nested);
            });
            payloads.forEach((payload) => {
              ['seq_in_channel', 'seq', 'msg_seq'].forEach((field) => {
                const sequence = normalizeMsgIdentity(payload[field]);
                if (sequence && sequence !== '0') {
                  keys.push(`seq:${sessionId}:${userId}:${field}:${sequence}`);
                }
              });
            });
          }
          const directSequence = normalizeMsgIdentity(message.msg_seq);
          if (directSequence && sessionId) keys.push(`seq:${sessionId}:${userId}:msg_seq:${directSequence}`);
          // 回调负载相同但适配器 ID 不同时，仍按事件内容合并。
          const raw = String(message.raw_message || '').trim();
          if (raw && sessionId && !raw.endsWith('...[已截断]')) keys.push(`raw:${sessionId}:${userId}:${msgIdentityHash(raw)}`);
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
      const msgMediaItemUrl = (item) => String(item?.src || item?.url || item?.download_url || '').trim();
      const msgMediaItemName = (item) => String(item?.name || item?.filename || item?.file_name || '').trim();
      const msgMediaItemKind = (item) => {
        const type = String(item?.type || item?.media_type || '').trim().toLowerCase();
        const mime = String(item?.content_type || item?.mime_type || '').trim().toLowerCase();
        if (['图片','image','img'].includes(type) || mime.startsWith('image/')) return 'image';
        if (['视频','video'].includes(type) || mime.startsWith('video/')) return 'video';
        if (['语音','音频','audio','voice','record'].includes(type) || mime.startsWith('audio/') || mime === 'voice') return 'audio';
        return ['文件','file','document'].includes(type) || mime ? 'file' : type;
      };
      const msgMediaHasValue = (value) => value !== null && value !== undefined
        && (typeof value !== 'string' || Boolean(value.trim()));
      const msgMediaItems = (media) => {
        if (!media || typeof media !== 'object') return [];
        const source = Array.isArray(media) ? media : (Array.isArray(media.items) && media.items.length ? media.items : [media]);
        return source.filter((item) => item && typeof item === 'object' && !Array.isArray(item)).map((item) => {
          const result = {...item};
          ['items','_lanzou_archive','_lanzou_archives'].forEach((key) => delete result[key]);
          return result;
        }).filter((item) => Boolean(msgMediaItemUrl(item) || msgMediaItemName(item) || msgMediaItemKind(item)));
      };
      const msgMediaMetadataMatches = (left, right) => {
        const name = msgMediaItemName(left);
        if (!name || name !== msgMediaItemName(right)) return false;
        const leftKind = msgMediaItemKind(left), rightKind = msgMediaItemKind(right);
        if (leftKind && rightKind && leftKind !== rightKind) return false;
        if (msgMediaHasValue(left.size) && msgMediaHasValue(right.size)) {
          const leftSize = Number(left.size), rightSize = Number(right.size);
          if (Number.isFinite(leftSize) && Number.isFinite(rightSize) ? leftSize !== rightSize : String(left.size) !== String(right.size)) return false;
        }
        return true;
      };
      const msgMediaArchiveProxy = (item, messageId, scope = {}) => {
        if (item?.archived !== true || !messageId) return null;
        const src = msgMediaItemUrl(item);
        if (!src.startsWith('/api/message/lanzou-image?')) return null;
        try {
          const url = new URL(src, 'https://mantou.invalid');
          if (url.pathname !== '/api/message/lanzou-image' || url.searchParams.get('message_id') !== String(messageId)) return null;
          const rawIndex = url.searchParams.get('media_index') || '';
          const index = Number(rawIndex), chatId = url.searchParams.get('chat_id') || '', chatType = url.searchParams.get('chat_type') || '';
          if (!/^\d+$/.test(rawIndex) || !Number.isSafeInteger(index) || !chatId || !['group','user'].includes(chatType)) return null;
          const expectedId = String(scope.chat_id || scope._session || '').trim();
          const expectedType = String(scope.chat_type || '').trim();
          if ((expectedId && expectedId !== chatId) || (expectedType && expectedType !== chatType)) return null;
          return {index, chatId, chatType};
        } catch (_) { return null; }
      };
      const msgMediaArchiveMatches = (left, right, index, messageId, scope) => {
        if (!msgMediaMetadataMatches(left, right)) return false;
        const oldProxy = msgMediaArchiveProxy(left, messageId, scope), newProxy = msgMediaArchiveProxy(right, messageId, scope);
        if (!oldProxy && !newProxy) return false;
        if ((oldProxy && oldProxy.index !== index) || (newProxy && newProxy.index !== index)) return false;
        return !oldProxy || !newProxy || (oldProxy.chatId === newProxy.chatId && oldProxy.chatType === newProxy.chatType);
      };
      const mergeMsgMediaItems = (existing, incoming, messageId = '', scope = {}) => {
        const items = msgMediaItems(existing), nextItems = msgMediaItems(incoming);
        const oldCount = items.length, matched = new Set(), incomingIndexes = [];
        const matchAll = (matches) => nextItems.forEach((item, nextIndex) => {
          if (Number.isInteger(incomingIndexes[nextIndex])) return;
          const index = items.findIndex((old, i) => i < oldCount && !matched.has(i) && matches(old, item, i));
          if (index >= 0) {
            incomingIndexes[nextIndex] = index;
            matched.add(index);
          }
        });
        // Resolve specific URLs first, so a missing URL cannot consume another item's slot.
        matchAll((old, item) => Boolean(msgMediaItemUrl(item)) && msgMediaItemUrl(old) === msgMediaItemUrl(item));
        matchAll((old, item, index) => msgMediaArchiveMatches(old, item, index, messageId, scope));
        matchAll((old, item) => (!msgMediaItemUrl(item) || !msgMediaItemUrl(old)) && msgMediaMetadataMatches(old, item));
        nextItems.forEach((item, nextIndex) => {
          const index = incomingIndexes[nextIndex], src = msgMediaItemUrl(item);
          if (!Number.isInteger(index)) {
            incomingIndexes[nextIndex] = items.length;
            items.push({...item});
            return;
          }
          Object.entries(item).forEach(([key, value]) => {
            if (msgMediaHasValue(value) && !msgMediaHasValue(items[index][key])) items[index][key] = value;
          });
          if (msgMediaArchiveProxy(item, messageId, scope)?.index === index) {
            items[index].src = src;
            items[index].archived = true;
            delete items[index].url;
            delete items[index].download_url;
          }
        });
        return {items, incomingIndexes};
      };
      const mergeMsgRealtimeMedia = (existing, incoming, messageId = '', scope = {}) => {
        if (!existing || typeof existing !== 'object') return incoming;
        const {items, incomingIndexes} = mergeMsgMediaItems(existing, incoming, messageId, scope);
        if (!items.length) return existing;
        const result = Array.isArray(existing) ? {} : {...existing};
        if (!Array.isArray(incoming)) Object.entries(incoming).forEach(([key, value]) => {
          if (key === 'items' || key === 'text_segments' || !msgMediaHasValue(value) || msgMediaHasValue(result[key])) return;
          result[key] = value;
        });
        if (!Array.isArray(result.text_segments) || !result.text_segments.length) {
          if (Array.isArray(incoming?.text_segments)) result.text_segments = incoming.text_segments.map((part) => {
            if (!Number.isInteger(part?.media_index)) return part;
            const index = incomingIndexes[part.media_index];
            return Number.isInteger(index) ? {...part, media_index:index} : part;
          });
        }
        // The first item remains the existing slot zero; later metadata cannot replace its URL.
        ['type','media_type','src','url','download_url','name','filename','file_name','content_type','mime_type','size','width','height','optimistic_data','archived'].forEach((key) => {
          if (Object.prototype.hasOwnProperty.call(items[0], key)) result[key] = items[0][key];
          else delete result[key];
        });
        if (items.length > 1 || Array.isArray(existing.items) || Array.isArray(incoming?.items)) result.items = items;
        else delete result.items;
        return result;
      };
      const mergeMsgRealtimeMessage = (existing, incoming) => {
        const merged = {...existing};
        if (Array.isArray(incoming?.reference_ids)) merged.reference_ids = incoming.reference_ids.slice(0, 8);
        if (typeof incoming?.reference_conflict === 'boolean') merged.reference_conflict = incoming.reference_conflict;
        if (typeof incoming?.is_bot === 'boolean') merged.is_bot = incoming.is_bot;
        ['user_id', 'nickname', 'content', 'timestamp', 'source', 'member_role', 'msg_seq', 'avatar', 'reference_id', 'refidx', 'chat_type', 'appid'].forEach((field) => {
          const next = incoming?.[field];
          const current = merged[field];
          if (next === null || next === undefined || next === '') return;
          if (field === 'member_role') {
            merged[field] = String(next).trim().toLowerCase();
          } else if (field === 'content') {
            if (!String(current || '').trim() || String(next).length > String(current || '').length) merged[field] = next;
          } else if (field === 'nickname') {
            const name = validMsgNickname(next, incoming?.user_id || merged.user_id);
            if (name && !validMsgNickname(current, merged.user_id)) merged[field] = name;
          } else if (!current) {
            merged[field] = next;
          }
        });
        if (validMsgNickname(merged.nickname, merged.user_id)) merged.nickname_blank = false;
        else if (incoming?.nickname_blank) merged.nickname_blank = true;
        const oldRaw = String(merged.raw_message || '');
        const newRaw = String(incoming?.raw_message || '');
        if (newRaw.length > oldRaw.length) merged.raw_message = incoming.raw_message;
        const newPreview = incoming?.reference_preview;
        if (newPreview && typeof newPreview === 'object' && !Array.isArray(newPreview)
          && (!merged.reference_preview || newRaw.length > oldRaw.length)) merged.reference_preview = {...newPreview};
        const oldMedia = merged.media;
        const newMedia = incoming?.media;
        if (newMedia && typeof newMedia === 'object') merged.media = mergeMsgRealtimeMedia(oldMedia, newMedia,
          merged.message_id || incoming?.message_id || '', {chat_id:merged.chat_id || merged._session || incoming?.chat_id, chat_type:merged.chat_type || incoming?.chat_type});
        if (!merged.message_id && incoming?.message_id) merged.message_id = incoming.message_id;
        if (!merged.id && incoming?.id) merged.id = incoming.id;
        merged.is_self = Boolean(merged.is_self || incoming?.is_self);
        merged.recalled = Boolean(msgIsRecalled(merged) || msgIsRecalled(incoming));
        merged.ts = Math.max(Number(merged.ts || 0), Number(incoming?.ts || 0));
        return merged;
      };
      const dedupeMsgMessages = (messages) => {
        const seen = new Map();
        const result = [];
        (Array.isArray(messages) ? messages : []).forEach((message) => {
          const keys = msgMessageIdentityKeys(message);
          const duplicateIndex = keys.map((key) => seen.get(key)).find((index) => Number.isInteger(index));
          if (!keys.length || !Number.isInteger(duplicateIndex)) {
            const index = result.length;
            keys.forEach((key) => seen.set(key, index));
            result.push(message);
            return;
          }
          const existing = result[duplicateIndex];
          if (!existing) return;
          result[duplicateIndex] = mergeMsgRealtimeMessage(existing, message);
          keys.forEach((key) => seen.set(key, duplicateIndex));
        });
        return result;
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
          if (String(message?.raw_message || '') !== String(other?.raw_message || '')) return false;
          if (String(message?.nickname || '') !== String(other?.nickname || '')) return false;
          if (Boolean(message?.nickname_blank) !== Boolean(other?.nickname_blank)) return false;
          if (String(message?.avatar || '') !== String(other?.avatar || '')) return false;
          if (String(message?.reference_id || '') !== String(other?.reference_id || '')) return false;
          if (Boolean(message?.reference_conflict) !== Boolean(other?.reference_conflict) || JSON.stringify(message?.reference_ids || []) !== JSON.stringify(other?.reference_ids || [])) return false;
          if (String(message?.refidx || '') !== String(other?.refidx || '')) return false;
          if (JSON.stringify(message?.reference_preview || null) !== JSON.stringify(other?.reference_preview || null)) return false;
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
          chat_type: String(payload.chat_type || 'group'),
          appid: String(payload.appid || ''),
          is_self: true,
          reference_id: String(payload.quote_message_id || '').trim(),
          reference_preview: msgState.quote && msgState.quote.id === payload.quote_message_id && msgState.quote.chatId === payload.chat_id
            ? {message_id:msgState.quote.id, refidx:msgState.quote.refidx, user_id:msgState.quote.userId, nickname:msgState.quote.name, nickname_blank:msgState.quote.nickname_blank, content:msgState.quote.text} : null,
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
        if (msgState.historyWindow) { scrollMsgToBottom('auto'); return; }
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
        closeComposerMentionPicker();
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
          try { await cacheBrowserMediaPayload(entry.payload); } catch (_) {}
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
        if (button) button.hidden = !msgState.historyWindow;
        if (msgState.historyWindow && $('msg-new-messages-label')) $('msg-new-messages-label').textContent = '返回最新消息';
      };
      const showMsgNewMessages = (count) => {
        msgState.pendingNewMessages = Math.max(1, Number(msgState.pendingNewMessages || 0) + Number(count || 0));
        const button = $('msg-new-messages');
        const label = $('msg-new-messages-label');
        if (label) label.textContent = msgState.historyWindow
          ? `返回最新消息 · ${msgState.pendingNewMessages} 条新消息` : `有 ${msgState.pendingNewMessages} 条新消息`;
        if (button) button.hidden = false;
      };
      const scrollMsgToBottom = (behavior = 'smooth') => {
        const body = $('msg-body');
        if (!body) return;
        if (msgState.historyWindow) {
          msgState.initialScrollChatId = msgState.chatId;
          void loadMsgHistory();
          return;
        }
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
      const browserMediaCacheName = 'mantou-message-media-v1';
      const browserMediaMarkerPattern = /^\/api\/message\/browser-media\/[A-Za-z0-9_-]{16,96}\.[A-Za-z0-9]{1,8}$/i;
      const browserMediaObjectUrls = new Map();
      const browserMediaMarker = (value) => {
        const raw = String(value || '').trim();
        if (!raw) return '';
        try {
          const url = new URL(raw, location.href);
          return url.origin === location.origin && browserMediaMarkerPattern.test(url.pathname) ? url.pathname : '';
        } catch (_) { return ''; }
      };
      const browserMediaDbName = 'mantou-message-media-v1';
      const openBrowserMediaDb = () => new Promise((resolve) => {
        if (typeof indexedDB === 'undefined') { resolve(null); return; }
        try {
          const request = indexedDB.open(browserMediaDbName, 1);
          request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains('media')) db.createObjectStore('media', {keyPath:'key'});
          };
          request.onsuccess = () => resolve(request.result);
          request.onerror = () => resolve(null);
        } catch (_) { resolve(null); }
      });
      const putBrowserMediaIndexedDb = async (key, blob) => {
        const db = await openBrowserMediaDb();
        if (!db) return false;
        return await new Promise((resolve) => {
          try {
            const tx = db.transaction('media', 'readwrite');
            tx.objectStore('media').put({key, blob, savedAt:Date.now()});
            tx.oncomplete = () => resolve(true);
            tx.onerror = () => resolve(false);
          } catch (_) { resolve(false); }
        });
      };
      const trimBrowserMediaIndexedDb = async () => {
        const db = await openBrowserMediaDb();
        if (!db) return;
        await new Promise((resolve) => {
          try {
            const read = db.transaction('media', 'readonly').objectStore('media').getAll();
            read.onsuccess = () => {
              const items = Array.isArray(read.result) ? read.result : [];
              const excess = items.length - 128;
              if (excess <= 0) { resolve(); return; }
              const tx = db.transaction('media', 'readwrite');
              items.sort((left, right) => Number(left?.savedAt || 0) - Number(right?.savedAt || 0));
              items.slice(0, excess).forEach((item) => tx.objectStore('media').delete(item.key));
              tx.oncomplete = () => resolve();
              tx.onerror = () => resolve();
            };
            read.onerror = () => resolve();
          } catch (_) { resolve(); }
        });
      };
      const getBrowserMediaIndexedDb = async (key) => {
        const db = await openBrowserMediaDb();
        if (!db) return null;
        return await new Promise((resolve) => {
          try {
            const request = db.transaction('media', 'readonly').objectStore('media').get(key);
            request.onsuccess = () => resolve(request.result?.blob || null);
            request.onerror = () => resolve(null);
          } catch (_) { resolve(null); }
        });
      };
      const browserMediaExtension = (name, mime, fallback = 'dat') => {
        let ext = String(name || '').split('.').pop()?.toLowerCase() || '';
        if (!/^[a-z0-9]{1,8}$/.test(ext) || ext === String(name || '').toLowerCase()) ext = '';
        if (ext === 'jpe') ext = 'jpg';
        if (!ext) ext = ({'image/jpeg':'jpg','image/png':'png','image/gif':'gif','image/webp':'webp','image/bmp':'bmp','video/mp4':'mp4','audio/silk':'silk'}[String(mime || '').toLowerCase()] || fallback);
        return /^[a-z0-9]{1,8}$/.test(ext) ? ext : fallback;
      };
      const browserMediaKeyForPayload = (payload) => {
        const data = payload || {};
        const hasFile = (typeof File !== 'undefined' && data.image_file instanceof File) || (typeof File !== 'undefined' && data.media_file instanceof File);
        const hasData = /^data:(?:image|video|audio)\//i.test(String(data.image_data || data.media_data || '').trim());
        if (!hasFile && !hasData) return '';
        const file = data.image_file instanceof File ? data.image_file : (data.media_file instanceof File ? data.media_file : null);
        const mime = String(file?.type || data.media_mime || (String(data.image_data || '').match(/^data:([^;,]+)/i)?.[1] || '')).toLowerCase();
        const name = String(file?.name || data.media_name || (mime.startsWith('image/') ? 'image.png' : 'attachment.dat'));
        const token = (typeof crypto !== 'undefined' && crypto.randomUUID)
          ? crypto.randomUUID().replace(/-/g, '')
          : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
        return `/api/message/browser-media/${token}.${browserMediaExtension(name, mime, mime.startsWith('image/') ? 'png' : 'dat')}`;
      };
      const browserMediaBlobForPayload = async (payload) => {
        const data = payload || {};
        const file = data.image_file instanceof File ? data.image_file : (data.media_file instanceof File ? data.media_file : null);
        if (file) return file;
        const raw = String(data.image_data || data.media_data || '').trim();
        if (!/^data:(?:image|video|audio)\//i.test(raw)) return null;
        const response = await fetch(raw);
        return response.ok ? response.blob() : null;
      };
      const trimBrowserMediaCache = async (cache) => {
        try {
          const keys = await cache.keys();
          const excess = keys.length - 128;
          for (let index = 0; index < excess; index += 1) await cache.delete(keys[index]);
        } catch (_) {}
      };
      const cacheBrowserMediaPayload = async (payload) => {
        const key = browserMediaMarker(payload?.browser_media_key);
        if (!key) return;
        const blob = await browserMediaBlobForPayload(payload);
        if (!blob || !blob.size) return;
        if (typeof caches !== 'undefined') {
          const cache = await caches.open(browserMediaCacheName);
          await cache.put(
            new Request(new URL(key, location.href).href),
            new Response(blob, {headers:{'Content-Type':blob.type || String(payload?.media_mime || 'application/octet-stream'), 'Cache-Control':'public,max-age=604800'}}),
          );
          await trimBrowserMediaCache(cache);
        } else {
          await putBrowserMediaIndexedDb(key, blob);
          await trimBrowserMediaIndexedDb();
        }
      };
      const loadBrowserMedia = async (key) => {
        const marker = browserMediaMarker(key);
        if (!marker) return '';
        if (browserMediaObjectUrls.has(marker)) return browserMediaObjectUrls.get(marker);
        try {
          let blob = null;
          if (typeof caches !== 'undefined') {
            const cache = await caches.open(browserMediaCacheName);
            const response = await cache.match(new Request(new URL(marker, location.href).href));
            blob = response ? await response.blob() : null;
          } else {
            blob = await getBrowserMediaIndexedDb(marker);
          }
          if (!blob || !blob.size) return '';
          const url = URL.createObjectURL(blob);
          browserMediaObjectUrls.set(marker, url);
          return url;
        } catch (_) { return ''; }
      };
      const msgImageRecoveryStates = new WeakMap();
      const msgImageScope = () => JSON.stringify([msgState.chatType, msgState.chatId, String(msgState.chatAppid || '').trim()]);
      const msgImageUrl = (value) => {
        try { return value ? new URL(value, location.href) : null; } catch (_) { return null; }
      };
      const clearMsgImageFailure = (img) => {
        img.hidden = false;
        const holder = img.closest('.msg-image-link');
        holder?.classList.remove('is-broken');
        holder?.querySelectorAll('.msg-media-ph').forEach((node) => node.remove());
      };
      const markBrowserMediaUnavailable = (node) => {
        if (!node) return;
        if (node.tagName === 'IMG') {
          const state = msgImageRecoveryStates.get(node);
          if (state) state.pending = false;
          node.hidden = true;
          const holder = node.closest('.msg-image-link');
          holder?.classList.add('is-broken');
          if (holder && !holder.querySelector('.msg-media-ph')) {
            const placeholder = document.createElement('span');
            placeholder.className = 'msg-media-ph';
            placeholder.textContent = '图片加载失败，点击重试';
            holder.appendChild(placeholder);
          }
        } else if (node.tagName === 'A') {
          node.removeAttribute('href');
          node.classList.add('is-unavailable');
        } else {
          node.removeAttribute('src');
        }
      };
      const msgEventBindings = new WeakMap();
      const bindMsgEvent = (node, eventName, identity, handler) => {
        if (!node) return;
        let bindings = msgEventBindings.get(node);
        if (!bindings) { bindings = new Set(); msgEventBindings.set(node, bindings); }
        const key = `${eventName}:${identity}`;
        if (bindings.has(key)) return;
        bindings.add(key);
        node.addEventListener(eventName, handler);
      };
      const bindMsgImageRecovery = (img) => {
        if (msgImageRecoveryStates.has(img)) {
          if (img.complete && img.naturalWidth > 0) clearMsgImageFailure(img);
          return;
        }
        // 状态跟随原节点，实时消息和滚动重绘不会重置自动重试额度。
        const state = {scope:msgImageScope(), source:img.getAttribute('src') || '', autoRetried:false, timer:null, pending:false};
        msgImageRecoveryStates.set(img, state);
        const active = () => img.isConnected && state.scope === msgImageScope()
          && !$('page-messages')?.hidden && document.visibilityState !== 'hidden';
        const cancelTimer = () => { if (state.timer !== null) clearTimeout(state.timer); state.timer = null; };
        const retry = () => {
          if (!active() || state.pending) return;
          cancelTimer();
          if (img.dataset.browserMediaKey) {
            // 浏览器私有媒体只重读已有缓存，不将缓存键伪造成网络下载地址。
            browserMediaHydrationKeys.delete(img);
            state.pending = true;
            void hydrateBrowserMedia(img.parentElement).finally(() => { state.pending = false; });
            return;
          }
          if (!state.source) return;
          state.pending = true;
          clearMsgImageFailure(img);
          img.loading = 'eager';
          img.src = state.source;
          img.dataset.lightbox = state.source;
        };
        const loaded = () => {
          if (img.naturalWidth <= 0) return;
          cancelTimer();
          state.pending = false;
          clearMsgImageFailure(img);
        };
        const failed = () => {
          state.pending = false;
          if (!active()) { cancelTimer(); markBrowserMediaUnavailable(img); return; }
          const current = msgImageUrl(img.getAttribute('src'));
          // 归档读取偶发失败时只自动重试一次；QQ 代理仍沿用原来的一次直连。
          if (!img.dataset.browserMediaKey && current?.origin === location.origin
            && current.pathname === '/api/message/lanzou-image' && !state.autoRetried) {
            state.autoRetried = true;
            markBrowserMediaUnavailable(img);
            state.timer = setTimeout(() => { state.timer = null; retry(); }, 350);
            return;
          }
          const direct = msgImageUrl(img.dataset.mediaDirect || '');
          if (!img.dataset.browserMediaKey && direct && !img.dataset.mediaDirectTried
            && direct.href !== current?.href) {
            img.dataset.mediaDirectTried = '1';
            state.pending = true;
            clearMsgImageFailure(img);
            img.src = direct.href;
            img.dataset.lightbox = direct.href;
            return;
          }
          markBrowserMediaUnavailable(img);
        };
        bindMsgEvent(img, 'load', 'media-load', loaded);
        bindMsgEvent(img, 'error', 'media-error', failed);
        bindMsgEvent(img.closest('.msg-image-link'), 'click', 'media-retry', (event) => {
          if (!img.closest('.msg-image-link')?.classList.contains('is-broken')) return;
          event.preventDefault();
          event.stopPropagation();
          retry();
        });
        // src 可在绑定前完成；没有 src 的本地缓存图等待 hydrate，不发请求。
        if (img.complete && img.getAttribute('src')) {
          if (img.naturalWidth > 0) loaded();
          else failed();
        }
      };
      const browserMediaHydrationKeys = new WeakMap();
      const hydrateBrowserMedia = async (root) => {
        if (!root) return;
        const nodes = [...root.querySelectorAll('[data-browser-media-key]')];
        await Promise.all(nodes.map(async (node) => {
          const key = String(node.dataset.browserMediaKey || '');
          if (browserMediaHydrationKeys.get(node) === key) return;
          browserMediaHydrationKeys.set(node, key);
          const url = await loadBrowserMedia(key);
          if (!node.isConnected || node.dataset.browserMediaKey !== key) return;
          if (!url) {
            browserMediaHydrationKeys.delete(node);
            markBrowserMediaUnavailable(node);
            return;
          }
          if (node.tagName === 'IMG') {
            clearMsgImageFailure(node);
            if (node.getAttribute('src') !== url) node.src = url;
            node.dataset.lightbox = url;
            bindMsgEvent(node, 'click', 'lightbox', (event) => { event.preventDefault(); openMsgLightbox(node.dataset.lightbox); });
          } else if (node.tagName === 'A') {
            if (node.getAttribute('href') !== url) node.href = url;
          } else if (node.tagName === 'VIDEO' || node.tagName === 'AUDIO') {
            if (node.getAttribute('src') !== url) node.src = url;
          }
        }));
      };
      const messageMediaProxyRevision = '6.1.109';
      const mediaProxyUrl = (src, mode = 'image', name = '') => {
        const direct = safeMediaUrl(src);
        if (!direct) return '';
        try {
          const host = new URL(direct).hostname.toLowerCase().replace(/\.$/, '');
          const allowed = ['multimedia.nt.qq.com.cn', 'qqbot.ugcimg.cn', 'gchat.qpic.cn', 'qpic.cn', 'qlogo.cn', 'qq.com.cn', 'qq.com'];
          const shouldProxy = allowed.some((suffix) => host === suffix || host.endsWith(`.${suffix}`));
          if (!shouldProxy) return direct;
          const query = new URLSearchParams({src: direct, mode: mode === 'image' ? 'image' : 'file'});
          // 新版本绕过浏览器中旧版 200 占位响应，仍由服务端按 src 统一处理失败冷却。
          query.set('v', messageMediaProxyRevision);
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
      const renderMessageMedia = (value, messageId = '', preload = false, mediaIndex = 0) => {
        if (!value) return '';
        const items = Array.isArray(value?.items) && value.items.length ? value.items : [value];
        return items.map((item, index) => {
          if (!item || typeof item !== 'object') return '';
          const type = String(item.type || item.media_type || '文件');
          const contentType = String(item.content_type || item.mime_type || '').toLowerCase();
           const directSrc = item.src || item.url || item.download_url;
           const inlineSrc = String(item.optimistic_data || '').match(/^data:image\/(?:png|jpe?g|gif|webp|bmp);base64,[A-Za-z0-9+/=]+$/i) && String(item.optimistic_data).length <= 12000000 ? String(item.optimistic_data) : '';
           const src = safeMediaUrl(directSrc) || inlineSrc;
          const browserKey = browserMediaMarker(src);
          const typeLower = type.toLowerCase();
          const isImage = ['图片', 'image', 'img'].includes(typeLower) || contentType.startsWith('image/');
          const isVideo = ['视频', 'video'].includes(typeLower) || contentType.startsWith('video/');
          const mediaKey = esc(JSON.stringify([mediaIndex + index, isImage ? 'image' : isVideo ? 'video' : 'file', src]));
          if (isImage) {
            if (!src) return '<div class="msg-media msg-image-media"><span class="msg-media-ph">图片地址未保存</span></div>';
            if (browserKey) return `<div data-msg-media-key="${mediaKey}" class="msg-media msg-image-media"><button class="msg-image-link" type="button" aria-label="打开图片"><img alt="图片" loading="${preload ? 'eager' : 'lazy'}" fetchpriority="${preload ? 'high' : 'low'}" decoding="async" data-browser-media-key="${esc(browserKey)}" data-media-img></button></div>`;
            const preview = mediaProxyUrl(src, 'image');
            const loading = preload ? 'eager' : 'lazy';
            const priority = preload ? 'high' : 'low';
            return `<div data-msg-media-key="${mediaKey}" class="msg-media msg-image-media"><button class="msg-image-link" type="button" aria-label="放大图片"><img src="${esc(preview || src)}" alt="图片" loading="${loading}" fetchpriority="${priority}" decoding="async" draggable="true" referrerpolicy="no-referrer" data-lightbox="${esc(preview || src)}" data-media-direct="${esc(src)}" data-media-proxied="${preview && preview !== src ? '1' : '0'}" data-media-img></button></div>`;
          }
          if (isVideo && src) {
            if (browserKey) return `<div data-msg-media-key="${mediaKey}" class="msg-media msg-video-media"><video controls preload="metadata" data-browser-media-key="${esc(browserKey)}"></video></div>`;
            const videoUrl = mediaProxyUrl(src, 'file');
            return `<div data-msg-media-key="${mediaKey}" class="msg-media msg-video-media"><video controls preload="metadata" src="${esc(videoUrl || src)}" data-media-direct="${esc(src)}"></video></div>`;
          }
          const name = mediaFileName(item, src);
          const size = mediaSizeLabel(item.size);
          const meta = [type, size].filter(Boolean).join(' · ') || '附件';
          if (!src) return `<div data-msg-media-key="${mediaKey}" class="msg-media msg-file-card is-unavailable"><span class="msg-file-icon">□</span><span class="msg-file-info"><strong>${esc(name)}</strong><small>${esc(meta)} · 未提供下载地址</small></span></div>`;
          const download = name ? ` download="${esc(name)}"` : '';
          if (browserKey) return `<a data-msg-media-key="${mediaKey}" class="msg-media msg-file-card" data-browser-media-key="${esc(browserKey)}"${download}><span class="msg-file-icon">${type === '视频' ? '▶' : type === '语音' ? '♫' : '□'}</span><span class="msg-file-info"><strong>${esc(name)}</strong><small>${esc(meta)}</small></span><span class="msg-file-action">下载</span></a>`;
          const fileUrl = mediaProxyUrl(src, 'file', name);
          return `<a data-msg-media-key="${mediaKey}" class="msg-media msg-file-card" href="${esc(fileUrl || src)}" target="_blank" rel="noopener noreferrer"${download}><span class="msg-file-icon">${type === '视频' ? '▶' : type === '语音' ? '♫' : '□'}</span><span class="msg-file-info"><strong>${esc(name)}</strong><small>${esc(meta)}</small></span><span class="msg-file-action">下载</span></a>`;
        }).join('');
      };
      const renderMsgMediaSegments = (media, messageId = '', preload = false, profiles = msgState.profiles) => {
        const segments = media?.text_segments;
        if (!Array.isArray(segments) || !segments.some((part) => Number.isInteger(part?.media_index))) return '';
        const items = Array.isArray(media?.items) && media.items.length ? media.items : [media];
        const rendered = new Set();
        const html = segments.map((part) => {
          if (typeof part?.text === 'string') return part.text ? '<span class="msg-media-text">' + renderMsgMarkup(part.text, profiles) + '</span>' : '';
          const index = part?.media_index;
          if (!Number.isInteger(index) || index < 0 || index >= items.length) return '';
          rendered.add(index);
          return renderMessageMedia(items[index], messageId, preload, index);
        }).join('');
        return html + items.map((item, index) => rendered.has(index) ? '' : renderMessageMedia(item, messageId, preload, index)).join('');
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
        const imageData = String(data || '');
        const mime = String(file?.type || /^data:([^;,]+)/i.exec(imageData)?.[1] || '').toLowerCase();
        const size = file ? Number(file.size || 0) : (imageData.startsWith('data:') ? Math.floor((imageData.split(',')[1] || '').length * 3 / 4) - (/==$/.test(imageData) ? 2 : /=\s*$/.test(imageData) ? 1 : 0) : 0);
        if (mime && !['image/png','image/jpeg','image/gif','image/webp'].includes(mime)) { toast('图片仅支持 PNG、JPEG、GIF 或 WebP'); return false; }
        if (size > 10 * 1024 * 1024) { toast('图片不能超过 10 MB'); return false; }
        clearComposerMedia();
        msgState.pastedImage = String(data || '');
        msgState.pastedImageFile = file && typeof File !== 'undefined' && file instanceof File ? file : null;
        msgState.pastedImageSource = String(source || '');
        const inlineSource = String(preview || data || source || '').trim();
        if (inlineSource) insertComposerImage(inlineSource);
        getComposerEditor()?.focus();
        return true;
      };
      const setComposerMedia = (data, name, fileType, mime = '', file = null) => {
        closeComposerMentionPicker();
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
            if (setComposerImage(dataUrl, '', dataUrl, null)) toast('图片已读取，可继续输入文字后发送');
          } catch (_) {
            setComposerImage('', url, proxy);
            toast('图片已添加，可继续输入文字后发送');
          }
          return;
        }
        try {
          const dataUrl = await blobToDataUrl(await fetchImageBlob(url));
          if (setComposerImage(dataUrl, '', dataUrl, null)) toast('图片已添加，可继续输入文字后发送');
        } catch (_) {
          toast('图片读取失败，请重新拖入');
        }
      };
      const bindImageInteractions = (img) => {
        if (!img) return;
        img.draggable = true;
        bindMsgEvent(img, 'contextmenu', 'image-context', (event) => {
          event.preventDefault();
          event.stopPropagation();
          const source = img.currentSrc || img.dataset.mediaDirect || img.src;
          showMsgCtx(event.clientX, event.clientY, [
            {label:'复制图片', action:() => copyImageToClipboard(source, img)},
          ]);
        });
        bindMsgEvent(img, 'dragstart', 'image-drag', (event) => {
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
      const splitMediaTextMarkers = (text) => {
        const raw = String(text || '');
        const match = raw.match(/\uFFFC\s*(?:\[?\s*OBJ\s*:\s*\d+\s*\]?)?/i);
        if (!match) return null;
        return {
          before: raw.slice(0, match.index).trim(),
          after: raw.slice((match.index || 0) + match[0].length).replace(/^\s*(?:\[?\s*OBJ\s*:\s*\d+\s*\]?)/i, '').trim(),
        };
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
        updateGroupMuteExpiry();
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
      let msgMuteSnapshot = null;
      const applyMsgMuteSnapshot = (target, data) => {
          if (!msgGroupSnapshotMatches(data, target) || msgGroupSnapshotScope(msgGroupSnapshotTarget()) !== msgGroupSnapshotScope(target)) return;
          const previous = msgMuteSnapshot?.scope === msgGroupSnapshotScope(target) ? msgMuteSnapshot.data : null;
          const known = data.has_data !== false && !data.pending;
          const snapshot = known ? data : {...(previous || {}), ...data, ...(previous?.has_data ? {members:previous.members, global_rule:previous.global_rule, has_data:true, stale:true} : {})};
          msgMuteSnapshot = {scope:msgGroupSnapshotScope(target), data:snapshot};
          const session = groupSettingsState.session;
          if (groupSettingsCurrent(session) && msgGroupSnapshotScope(session.target) === msgGroupSnapshotScope(target)) renderGroupMuteStates(session, snapshot);
          if (snapshot.has_data !== true) return;

          const next = new Map();
          (Array.isArray(snapshot.members) ? snapshot.members : []).forEach((member) => {
            const id = String(member?.member_openid || member?.union_openid || '').trim();
            if (!id) return;
            const expireTs = Number(member?.mute_expire_ts || 0);
            if (!(expireTs > Date.now() / 1000)) return;
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
          if (mutesChanged && msgState.renderedChatId === target.chat_id) {
            renderMsgMessages(
              {...(msgState.historyData || {}), messages:msgState.messages},
              {previousTop:body?.scrollTop || 0, previousHeight:body?.scrollHeight || 0},
            );
          }
      };
      const loadMuteStates = (force = false, settingsSession = null) => {
        const target = msgGroupSnapshotTarget();
        const drawerRequest = groupSettingsCurrent(settingsSession) && msgGroupSnapshotScope(settingsSession.target) === msgGroupSnapshotScope(target);
        if (!target || (!msgState.botIsAdmin && !drawerRequest) || !msgGroupSnapshotVisible()) return Promise.resolve(null);
        const existing = msgMuteSnapshot?.scope === msgGroupSnapshotScope(target) ? msgMuteSnapshot.data : null;
        if (drawerRequest) renderGroupMuteStates(settingsSession, existing || {...target, has_data:false, pending:true});
        const now = Date.now();
        if (!force && msgState.muteRequestAt && now - msgState.muteRequestAt < msgMuteRefreshMs && existing) return Promise.resolve(existing);
        msgState.muteRequestAt = now;
        return requestMsgGroupSnapshot('mutes', target, (data) => applyMsgMuteSnapshot(target, data), force);
      };
      const unmuteMember = async (member, name = '') => {
        const memberId = String(member || '').trim();
        const target = captureGroupTarget();
        if (!memberId || !target) return;
        if (!confirm(`确定解除 ${name || memberId} 的禁言吗？`)) return;
        try {
          await api('message/group-member/unmute', {method:'POST', body:JSON.stringify({...target, member_openid:memberId})});
          if (msgGroupSnapshotScope(msgGroupSnapshotTarget()) !== msgGroupSnapshotScope(target)) return;
          toast('已解除禁言');
          void loadMuteStates(true, groupSettingsState.session);
        } catch (error) {
          if (msgGroupSnapshotScope(msgGroupSnapshotTarget()) === msgGroupSnapshotScope(target)) toast(error.message || '解除禁言失败');
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
        if (msgState.positionTimer != null) clearTimeout(msgState.positionTimer);
        msgState.positionTimer = null;
        msgState.positionObserver?.disconnect();
        msgState.positionObserver = null;
        const positionedBody = body || msgState.positionBody;
        msgState.positionBody = null;
        if (reveal && positionedBody) positionedBody.classList.remove('msg-positioning');
      };
      const scrollMsgBodyToBottom = (body, chatId = msgState.chatId, revealAfterPosition = false) => {
        if (!body) return;
        // 新定位接手旧定位的隐藏状态，实时刷新不能取消最后一次 reveal。
        revealAfterPosition = revealAfterPosition || body.classList.contains('msg-positioning');
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
          if (msgState.positionTimer != null) clearTimeout(msgState.positionTimer);
          msgState.positionTimer = null;
          msgState.positionObserver?.disconnect();
          msgState.positionObserver = null;
          apply();
          reveal();
          msgState.positionBody = null;
        };
        apply();
        // rAF 在后台页或繁忙页面可能暂停，隐藏布局必须有独立的有界收尾。
        if (revealAfterPosition) msgState.positionTimer = setTimeout(finish, 750);
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
      const msgRawFieldOrder = [
        'op', 's', 't', 'd',
        'id', 'event_id', 'message_id', 'msg_id',
        'message_type', 'msg_type',
        'group_openid', 'group_id', 'channel_id', 'guild_id',
        'group_member_openid', 'member_openid', 'user_openid', 'openid',
        'author', 'member', 'user',
        'content', 'timestamp', 'seq', 'seq_in_channel',
        'message_reference', 'mentions',
        'attachments', 'embeds', 'ark', 'ark_data', 'msg_elements',
      ];
      const msgRawFieldRanks = new Map(msgRawFieldOrder.map((field, index) => [field, index]));
      const sortMsgRawValue = (value) => {
        if (Array.isArray(value)) return value.map(sortMsgRawValue);
        if (!value || typeof value !== 'object') return value;
        const sorted = {};
        Object.keys(value).sort((left, right) => {
          const leftRank = msgRawFieldRanks.get(left);
          const rightRank = msgRawFieldRanks.get(right);
          if (leftRank !== undefined || rightRank !== undefined) {
            if (leftRank === undefined) return 1;
            if (rightRank === undefined) return -1;
            return leftRank - rightRank;
          }
          return left < right ? -1 : left > right ? 1 : 0;
        }).forEach((key) => { sorted[key] = sortMsgRawValue(value[key]); });
        return sorted;
      };
      const formatMsgRaw = (raw) => {
        const source = typeof raw === 'string' ? raw : raw == null ? '' : String(raw);
        if (!source.trim()) return '无原始数据';
        try {
          return JSON.stringify(sortMsgRawValue(JSON.parse(source)), null, 2);
        } catch (_) {
          // 旧记录可能已截断，或者上游给出的不是 JSON；保留原文供排查。
          return source;
        }
      };
      const msgDomSignatures = new WeakMap();
      const msgDomKey = (node) => {
        if (node.nodeType !== 1) return `node:${node.nodeType}`;
        const messageKey = node.getAttribute('data-msg-render-key');
        if (messageKey !== null) return messageKey ? `message:${messageKey}` : null;
        const mediaKey = node.getAttribute('data-msg-media-key');
        if (mediaKey !== null) return `media:${node.tagName}:${mediaKey}`;
        const action = [...node.attributes].map((attr) => attr.name)
          .filter((name) => /^data-msg-(?:recall|retry|command|quote|mute|unmute|raw)$/.test(name)).sort().join(',');
        return `${node.tagName}:${node.id || ''}:${node.classList[0] || ''}:${action}`;
      };
      const rememberMsgDom = (node) => {
        msgDomSignatures.set(node, node.nodeType === 1 ? node.outerHTML : node.nodeValue);
        [...node.childNodes].forEach(rememberMsgDom);
      };
      const patchMsgDomNode = (current, incoming) => {
        const signature = incoming.nodeType === 1 ? incoming.outerHTML : incoming.nodeValue;
        if (msgDomSignatures.get(current) === signature) return current;
        const mediaKey = incoming.nodeType === 1 ? incoming.getAttribute('data-msg-media-key') : null;
        if (mediaKey !== null && current.getAttribute('data-msg-media-key') === mediaKey) {
          const existingMedia = [...current.querySelectorAll('[data-media-img], video, audio')];
          const nextMedia = [...incoming.querySelectorAll('[data-media-img], video, audio')];
          if (existingMedia.length && existingMedia.length === nextMedia.length
            && existingMedia.every((node, index) => node.tagName === nextMedia[index].tagName)) {
            existingMedia.forEach((node, index) => {
              ['alt', 'loading', 'fetchpriority', 'decoding', 'referrerpolicy', 'controls', 'preload'].forEach((name) => {
                const value = nextMedia[index].getAttribute(name);
                if (value !== null && node.getAttribute(name) !== value) node.setAttribute(name, value);
              });
            });
            msgDomSignatures.set(current, signature);
            return current;
          }
        }
        const mediaSource = (node) => node.dataset.browserMediaKey || node.dataset.mediaDirect || node.getAttribute('src') || '';
        if (incoming.nodeType === 1 && current.matches('[data-media-img], video, audio')
          && mediaSource(current) === mediaSource(incoming)) {
          // Preserve fallback/error state and playback; hint changes must not reset src.
          ['alt', 'loading', 'fetchpriority', 'decoding', 'referrerpolicy', 'controls', 'preload'].forEach((name) => {
            const value = incoming.getAttribute(name);
            if (value !== null && current.getAttribute(name) !== value) current.setAttribute(name, value);
          });
        } else if (incoming.nodeType !== 1) current.nodeValue = incoming.nodeValue;
        else {
          [...current.attributes].forEach((attr) => {
            if (!incoming.hasAttribute(attr.name)) current.removeAttribute(attr.name);
          });
          [...incoming.attributes].forEach((attr) => {
            if (current.getAttribute(attr.name) !== attr.value) current.setAttribute(attr.name, attr.value);
          });
          reconcileMsgDomChildren(current, incoming);
        }
        msgDomSignatures.set(current, signature);
        return current;
      };
      const reconcileMsgDomChildren = (parent, incoming) => {
        const available = new Map();
        [...parent.childNodes].forEach((node) => {
          const key = msgDomKey(node);
          if (key === null) return;
          if (!available.has(key)) available.set(key, []);
          available.get(key).push(node);
        });
        let cursor = parent.firstChild;
        [...incoming.childNodes].forEach((node) => {
          const key = msgDomKey(node);
          const previous = key === null ? null : available.get(key)?.shift();
          const next = previous ? patchMsgDomNode(previous, node) : node;
          if (!previous) rememberMsgDom(next);
          // Append/prepend leave existing rows and their active media connected.
          if (next !== cursor) parent.insertBefore(next, cursor);
          cursor = next.nextSibling;
        });
        while (cursor) { const next = cursor.nextSibling; cursor.remove(); cursor = next; }
      };
      const renderMsgMessageDom = (body, html, scope) => {
        const template = document.createElement('template');
        template.innerHTML = html;
        if (body._msgRenderScope === scope) reconcileMsgDomChildren(body, template.content);
        else {
          [...template.content.childNodes].forEach(rememberMsgDom);
          body.replaceChildren(template.content);
        }
        body._msgRenderScope = scope;
      };
      const renderMsgMessages = (data, scroll = {}) => {
        const body = $('msg-body');
        const keepLatestVisible = !msgQuoteJump.pending && !msgState.historyWindow && !scroll.preservePosition
          && !scroll.prepend && (Boolean(scroll.toBottom) || msgBodyNearBottom(body));
        const initialPositioning = !scroll.prepend
          && msgState.initialScrollChatId === msgState.chatId
          && keepLatestVisible
          && (msgState.renderedChatId !== msgState.chatId || body.classList.contains('msg-positioning'));
        const renderScope = JSON.stringify([msgState.chatType, msgState.chatId,
          String(data.messages?.find((message) => message?.appid)?.appid || msgState.chatAppid || '').trim()]);
        const previousData = body._msgRenderScope === renderScope ? (msgState.historyData || {}) : {};
        data = {
          ...previousData,
          ...data,
          member_profiles:mergeMsgProfileMaps(previousData.member_profiles, data.member_profiles),
          references:{...(previousData.references || {}), ...(data.references || {})},
        };
        if (msgState.chatType === 'user') data = {...data, ...syncMsgFriendState(msgState.chatId, data)};
        const serverMessages = mergeMsgRecalledStates(dedupeMsgMessages(data.messages || []));
        const msgs = msgState.historyWindow ? serverMessages : mergeOptimisticMessages(msgState.chatId, serverMessages);
        // 历史缓存只保存服务器消息；待发送/失败消息由 optimisticSends 单独维护。
        msgState.historyData = {...data, messages:serverMessages};
        const historyAppid = String(data.messages?.find((message) => message?.appid)?.appid || '').trim();
        if (historyAppid) msgState.chatAppid = historyAppid;
        window.msgAppid = msgState.chatAppid || window.msgAppid || '';
        updateMsgHead(data);
        updateMsgAdminTag();
        $('msg-refresh-info').hidden = msgState.chatType !== 'group' || msgState.chatRemoved;
        $('msg-remark').hidden = msgState.chatType !== 'group' || msgState.chatRemoved;
        $('msg-group-settings-open').hidden = msgState.chatType !== 'group' || msgState.chatRemoved;
        updateMsgAdSwitch();
        const rawStore = window._msgRaw = window._msgRaw || {};
        const renderedRawKeys = new Set();
        if (!msgs.length) {
          cancelMsgBottomPosition(body, true);
          renderMsgMessageDom(body, '<div class="msg-empty">暂无消息记录</div>', renderScope);
          msgState.messageRenderSignature = JSON.stringify({more:Boolean(data.has_more), messages:[]});
          Object.keys(rawStore).forEach((key) => delete rawStore[key]);
          msgState.renderedChatId = msgState.chatId;
          clearMsgNewMessages();
          return;
        }
        const profiles = mergeMsgProfiles(
          mergeMsgProfileMaps(msgState.profiles, data.member_profiles),
          msgs,
        );
        msgState.profiles = profiles;
        renderMsgQuotePreview();
        const referenceIndex = buildMsgReferenceIndex(msgs, data.references, profiles);
        const renderSignature = JSON.stringify({
          scope: renderScope,
          profiles,
          references:msgs.map((message) => (message.reference_id ? referenceIndex.get(String(message.reference_id)) : null) || message.reference_preview || null),
          more: Boolean(data.has_more),
          newer: Boolean(msgState.historyWindow?.has_newer),
          multi: Boolean(msgState.multi),
          messages: msgs.map((message) => {
            const id = String(message.message_id || message.id || '');
            const profile = profiles[message.user_id] || {};
            const mute = msgState.mutes.get(String(message.user_id || '').trim());
            const optimisticId = String(message.optimistic_id || '').trim();
            const optimistic = optimisticId ? msgState.optimisticSends.get(optimisticId) : null;
            return [
              id,
              message.timestamp || '',
              message.content || '',
              message.media ? JSON.stringify(message.media) : '',
              msgIsRecalled(message) ? 1 : 0,
              message.nickname || '',
              Boolean(message.nickname_blank),
              Boolean(profile.nickname_blank),
              profile.nickname || profile.username || '',
              profile.avatar || profile.avatar_url || '',
              profile.role || '',
              mute?.mute_expire_ts || 0,
              optimisticId,
              optimistic?.status || message.send_status || '',
              message.reference_id || '',
              Boolean(referenceIndex.blocked?.has(String(message.reference_id))),
              message.refidx || '',
              message.source || '',
              typeof message.is_bot === 'boolean' ? message.is_bot : null,
              message.member_role || '',
              Boolean(message.is_self),
              String(message.raw_message || ''),
            ];
          }),
        });
        if (
          msgState.messageRenderSignature === renderSignature
          && msgState.renderedChatId === msgState.chatId
          && !scroll.prepend
          && !scroll.forceRender
        ) {
          // 相同内容不重建 DOM，但首屏定位仍需收尾；不能留下隐藏正文。
          if (body.classList.contains('msg-positioning')) {
            // DOM 没变，无须重启等待帧；直接结束旧定位，避免连续刷新延长隐藏。
            cancelMsgBottomPosition(body, true);
            body.scrollTop = body.scrollHeight;
          }
          return;
        }
        msgState.messageRenderSignature = renderSignature;
        let lastDay = ''; let html = '';
        if (data.has_more) html += '<button class="msg-load-older" id="msg-load-older" type="button">加载更早消息</button>';
        msgs.forEach((m, index) => {
          const day = String(m.timestamp||'').slice(0,10);
          if (day !== lastDay && day) { html += `<div class="msg-day">${esc(fmtDayLabel(m.timestamp))}</div>`; lastDay = day; }
          const systemSource = String(m.source || '');
          const renderKey = String(m.message_id || m.messageId || m.id || m.optimistic_id || '').trim();
          if (['group_member_join','group_member_leave','friend_add','friend_del'].includes(systemSource)) {
            const fallbackName = systemSource.startsWith('friend_') ? '用户' : systemSource === 'group_member_join' ? '新成员' : '成员';
            const memberName = displayMsgNickname(m, profiles[String(m.user_id || '').trim()] || {}, fallbackName);
            const actionText = {group_member_join:'加入了群聊。', group_member_leave:'退出了群聊。', friend_add:'添加了机器人好友。', friend_del:'删除了机器人好友。'}[systemSource];
            html += `<div class="msg-system-row" data-msg-render-key="${esc(renderKey)}"><span class="msg-system-time">${esc(fmtMsgTime(m.timestamp))}</span><span class="msg-system-notice"><span class="msg-system-name">${esc(memberName)}</span>${actionText}</span></div>`;
            return;
          }
          const isSelf = Boolean(m.is_self) || ['bot_active', 'bot_send', 'web_panel'].includes(String(m.source || ''));
          const botMessage = String(m.source || '').startsWith('bot') || String(m.source || '') === 'web_panel';
          const recalled = msgIsRecalled(m);
          const optimisticId = String(m.optimistic_id || '').trim();
          const optimisticEntry = optimisticId ? msgState.optimisticSends.get(optimisticId) : null;
          const sendState = String(optimisticEntry?.status || m.send_status || '').trim();
          const failedSend = Boolean(optimisticEntry) && sendState === 'failed';
          const profile = profiles[m.user_id] || {};
          const rawNickname = isSelf ? String(m.nickname || '').trim() : validMsgNickname(m.nickname, m.user_id);
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
            : displayMsgNickname(m, profile);
          const av = isSelf && botMessage ? botProfileAvatar : (isSelf ? '' : (profileAvatar || avatarUrl(m.user_id, 'user', data.messages?.[0]?.appid || window.msgAppid)));
          const tags = [];
          if (msgIsBot(m, profile)) tags.push('<span class="msg-tag bot">BOT</span>');
          else if (isSelf) tags.push('<span class="msg-tag self">我</span>');
          if (m.source === 'web_panel') tags.push('<span class="msg-tag">网页</span>');
          if (recalled) tags.push('<span class="msg-tag recalled">已撤回</span>');
          if (isMuted) tags.push('<span class="msg-tag muted" data-msg-mute-tag="1">被禁言</span>');
          const roleMap = {owner:'群主', admin:'管理', member:'群员'};
          const rawRole = String(m.raw_message || '').match(/member_role[^,]*?['"]([a-z]+)['"]/)?.[1] || '';
          const memberRole = String(profile.role || m.member_role || rawRole || '').trim().toLowerCase();
          const protectedRole = !isSelf && (memberRole === 'owner' || memberRole === 'admin');
          const roleTag = roleMap[memberRole] || '';
          if (!isSelf && roleTag) tags.push(`<span class="msg-tag role ${memberRole}">${roleTag}</span>`);
          const renderText = (text) => {
            return replaceMsgMentions(text, profiles);
          };
          // 引用标识只用于查找，未取得原消息时不把协议 ID 当作正文显示。
          const quote = m.reference_id || m.reference_preview ? renderMsgQuote(referenceIndex.get(String(m.reference_id)), profiles, m.reference_id, m.reference_preview, referenceIndex.blocked?.has(String(m.reference_id))) : '';
          const mediaData = m.media;
          // QQ 图片链接有短时签名。页面已打开时，提前加载最新一批消息可让
          // 浏览器私有缓存保留已成功取得的图片；加载更早历史仍保持惰性请求。
          const preloadMedia = !scroll.prepend && index >= Math.max(0, msgs.length - 12);
          const media = renderMessageMedia(mediaData, m.message_id, preloadMedia);
          const segmentedMedia = renderMsgMediaSegments(mediaData, m.message_id, preloadMedia, profiles);
          const mediaTextPosition = media && mediaData && !Array.isArray(mediaData) ? splitMediaTextMarkers(m.content || '') : null;
          const mediaText = mediaData && !Array.isArray(mediaData) ? String(mediaData.text || '') : '';
          const renderedContent = renderText(m.content || '');
          let content = stripMediaMarker(renderedContent, mediaData);
          content = stripObjectMarker(content, mediaData);
          content = content.replace(/\uFFFC/g, '').trim();
          if (mediaTextPosition || segmentedMedia) content = '';
          if (!content && mediaText && !segmentedMedia) content = renderText(mediaText);
          if (!content && !media) content = '（空消息）';
          const contentHtml = content ? renderMsgMarkup(content, profiles) : '';
          const mediaBeforeText = mediaTextPosition
            ? mediaTextPosition.before
            : (mediaData && !Array.isArray(mediaData) ? String(mediaData.before_text || '').trim() : '');
          const mediaAfterText = mediaTextPosition
            ? mediaTextPosition.after
            : (mediaData && !Array.isArray(mediaData) ? String(mediaData.after_text || '').trim() : '');
          const hasInlineMediaText = media && mediaData && !Array.isArray(mediaData)
            && (Boolean(mediaTextPosition)
              || Object.prototype.hasOwnProperty.call(mediaData, 'before_text')
              || Object.prototype.hasOwnProperty.call(mediaData, 'after_text'));
          const inlineMediaHtml = hasInlineMediaText
            ? `<div class="msg-inline-media">${mediaBeforeText ? `<span class="msg-media-text">${renderMsgMarkup(mediaBeforeText, profiles)}</span>` : ''}${media}${mediaAfterText ? `<span class="msg-media-text msg-media-text-after">${renderMsgMarkup(mediaAfterText, profiles)}</span>` : ''}</div>`
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
          html += `<div class="msg-row ${isSelf ? 'self' : ''}${isMuted ? ' muted' : ''}${msgState.multi ? ' multi-mode' : ''}${isSelected ? ' selected' : ''}${multiEnabled ? '' : ' no-multi'}${optimisticEntry ? ' optimistic' : ''}" data-msg-render-key="${esc(renderKey)}" data-msg-mid="${esc(m.message_id)}" data-msg-uid="${esc(m.user_id)}" data-msg-nick="${esc(displayNickname)}" data-msg-refidx="${esc(m.refidx || '')}" data-msg-role="${esc(memberRole)}" data-msg-self="${isSelf ? '1' : ''}" data-msg-recalled="${recalled ? '1' : ''}" data-msg-optimistic="${esc(optimisticId)}" data-msg-content="${esc(m.content || '')}">
            <span class="msg-pos">
              <span class="msg-multi-check"></span>
              <span class="msg-avatar${isMuted ? ' muted' : ''}">${avatarHtml(av, displayNickname || '?')}</span>
            </span>
            <div class="msg-bubble-wrap"><div class="msg-bubble-name">${esc(displayNickname)}${tags.length ? `<span class="msg-tags">${tags.join('')}</span>` : ''}</div>
              <div class="msg-bubble ${recalled ? 'recalled' : ''}">${quote}${segmentedMedia || (hasInlineMediaText ? inlineMediaHtml : `${contentHtml}${media}`)}</div>
              <div class="msg-meta">${esc(fmtMsgTime(m.timestamp))}${!optimisticEntry && m.message_id ? ` · ${esc(m.message_id.slice(0,18))}…` : ''}${muteStatusHtml}${sendStateHtml}</div>
              ${actions.length ? `<div class="msg-actions">${actions.join('')}</div>` : ''}
            </div></div>`;
        });
        if (initialPositioning) body.classList.add('msg-positioning');
        if (msgState.historyWindow?.has_newer) html += '<button class="msg-load-older" id="msg-load-newer" type="button">加载后续消息</button>';
        renderMsgMessageDom(body, html, renderScope);
        Object.keys(rawStore).forEach((key) => {
          if (!renderedRawKeys.has(key)) delete rawStore[key];
        });
        void hydrateBrowserMedia(body);
        body.querySelectorAll('[data-media-img]').forEach((img) => {
          bindImageInteractions(img);
          bindMsgImageRecovery(img);
        });
        if (scroll.prepend) {
          body.scrollTop = Math.max(0, Number(scroll.previousTop || 0) + body.scrollHeight - Number(scroll.previousHeight || 0));
        } else if (keepLatestVisible) {
          // 缓存、实时和资料刷新都独立完成定位，展示不再等待首轮网络响应。
          scrollMsgBodyToBottom(body, msgState.chatId, initialPositioning);
          clearMsgNewMessages();
        } else {
          body.scrollTop = Math.min(Number(scroll.previousTop || 0), Math.max(0, body.scrollHeight - body.clientHeight));
        }
        msgState.renderedChatId = msgState.chatId;
        bindMsgEvent(body.querySelector('#msg-load-older'), 'click', 'load-older', () => loadMsgHistory(true));
        bindMsgEvent(body.querySelector('#msg-load-newer'), 'click', 'load-newer', () => loadMsgWindowPage('after'));
        body.querySelectorAll('[data-msg-jump]').forEach((el) => bindMsgEvent(el, 'click', 'quote-jump', (event) => {
          event.preventDefault(); event.stopPropagation();
          void jumpToMsgReference(el.dataset.msgJump);
        }));
        body.querySelectorAll('[data-msg-recall]').forEach((el) => bindMsgEvent(el, 'click', 'recall', () => recallMessage(el.dataset.msgRecall)));
        body.querySelectorAll('[data-msg-retry]').forEach((el) => bindMsgEvent(el, 'click', 'retry', (event) => { event.preventDefault(); event.stopPropagation(); retryOptimisticSend(el.dataset.msgRetry); }));
        body.querySelectorAll('[data-lightbox]').forEach((img) => bindMsgEvent(img, 'click', 'lightbox', (event) => { event.preventDefault(); openMsgLightbox(img.dataset.lightbox); }));
        body.querySelectorAll('[data-msg-command]').forEach((el) => bindMsgEvent(el, 'click', 'command', () => {
          const command = String(el.dataset.msgCommand || '').trim();
          if (!command || !getComposerEditor()) return;
          insertComposerText(command);
          toast(`已填入 ${command}`);
        }));
        body.querySelectorAll('[data-msg-quote]').forEach((el) => bindMsgEvent(el, 'click', 'quote', () => setMsgQuote(el.dataset.msgQuote, el.dataset.msgUser, el.dataset.msgName, el.closest('.msg-row')?.dataset.msgContent || '', el.dataset.msgRefidx || '')));
        body.querySelectorAll('[data-msg-mute]').forEach((el) => bindMsgEvent(el, 'click', 'mute', () => { msgState.mute = {member:el.dataset.msgMute, name:el.dataset.msgMuteName}; $('msg-mute-title').textContent = `禁言 ${el.dataset.msgMuteName || el.dataset.msgMute}`; $('msg-mute-modal').hidden = false; }));
        body.querySelectorAll('[data-msg-unmute]').forEach((el) => bindMsgEvent(el, 'click', 'unmute', () => unmuteMember(el.dataset.msgUnmute, el.dataset.msgUnmuteName)));
        body.querySelectorAll('[data-msg-raw]').forEach((el) => bindMsgEvent(el, 'click', 'raw', () => { $('msg-raw-content').textContent = formatMsgRaw(window._msgRaw?.[el.dataset.msgRaw]); $('msg-raw-copy').textContent = '复制'; $('msg-raw-modal').hidden = false; }));
        body.querySelectorAll('.msg-row').forEach((row) => {
          bindMsgEvent(row, 'contextmenu', 'message-context', (e) => {
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
          bindMsgEvent(row, 'click', 'message-select', (e) => {
            if (msgState.multi && !e.target.closest('button')) {
              const protectedRole = row.dataset.msgSelf !== '1' && ['owner', 'admin'].includes(String(row.dataset.msgRole || '').toLowerCase());
              const canSel = Boolean(row.dataset.msgMid) && !(row.dataset.msgRecalled === '1') && (row.dataset.msgSelf === '1' || (msgState.botIsAdmin && !protectedRole));
              if (canSel) toggleMsgSelect(row, row.dataset.msgMid);
            }
          });
          bindMsgEvent(row.querySelector('.msg-avatar'), 'contextmenu', 'avatar-context', (e) => {
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
      const scheduleMsgRealtimeMessageRender = (chatId, toBottom, countAsNew = true) => {
        if (msgState.realtimeRenderChatId && msgState.realtimeRenderChatId !== chatId) return;
        msgState.realtimeRenderChatId = chatId;
        if (countAsNew) msgState.realtimeMessageCount += 1;
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
        const existing = msgState.realtimeChats.get(chatId) || msgState.chats.find((chat) => String(chat.chat_id || '') === chatId) || {};
        const chatType = String(payload.chat_type || message.chat_type || existing.chat_type || 'group');
        const eventAppid = String(payload.appid || message.appid || existing.appid || '').trim();
        if (payload.chat_type && message.chat_type && String(payload.chat_type) !== String(message.chat_type)) return;
        if (payload.appid && message.appid && String(payload.appid).trim() !== String(message.appid).trim()) return;
        if (existing.chat_type && String(existing.chat_type) !== chatType) return;
        if (existing.appid && eventAppid && String(existing.appid).trim() !== eventAppid) return;
        const currentAppid = String(msgState.chatAppid || msgState.historyData?.messages?.find((item) => item?.appid)?.appid || '').trim();
        const matchesCurrent = msgState.chatId === chatId && msgState.chatType === chatType
          && (!currentAppid || currentAppid === eventAppid);
        if (matchesCurrent && eventAppid) msgState.chatAppid = eventAppid;
        const messageKey = msgMessageKey(message);
        const recalledIndex = matchesCurrent && messageKey ? msgState.messages.findIndex((item) => msgMessagesMatch(item, message)) : -1;
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
        const isNewEvent = rememberMsgEvent(chatId, message);
        const friendState = chatType === 'user' ? syncMsgFriendState(chatId, {...payload, chat_type:chatType, appid:eventAppid}, isNewEvent && ['friend_add','friend_del'].includes(String(message.source || ''))) : {};
        const friendChanged = chatType === 'user' && (String(friendState.friend_status || '') !== String(existing.friend_status || '') || Number(friendState.friend_checked_at || 0) !== Number(existing.friend_checked_at || 0));
        let profilesChanged = false;
        if (matchesCurrent) {
          const oldProfiles = JSON.stringify(msgState.profiles || {});
          msgState.profiles = mergeMsgProfiles(
            mergeMsgProfileMaps(msgState.profiles, payload.member_profiles),
            [message],
          );
          profilesChanged = JSON.stringify(msgState.profiles || {}) !== oldProfiles;
          const history = msgState.historyData || {};
          msgState.historyData = {
            ...history,
            member_profiles:mergeMsgProfileMaps(history.member_profiles, payload.member_profiles),
          };
        }
        const referencesChanged = matchesCurrent && Boolean(payload.references)
          && JSON.stringify(payload.references) !== JSON.stringify(msgState.historyData?.references || {});
        if (matchesCurrent && payload.references) {
          msgState.historyData = {...(msgState.historyData || {}), references:{...(msgState.historyData?.references || {}), ...payload.references}};
        }
        if (isNewEvent) msgState.historyCache.delete(`${chatType}|${chatId}`);
        const isViewing = matchesCurrent && !$('page-messages')?.hidden;
        const body = $('msg-body');
        const followLatest = isViewing && !msgQuoteJump.pending && !msgState.historyWindow
          && msgState.pendingNewMessages === 0 && msgBodyNearBottom(body);
        const payloadUnread = Number(payload.unread);
        const fallbackUnread = Math.max(0, Number(existing.unread || 0) + (isNewEvent ? 1 : 0));
        const unread = followLatest
          ? 0
          : (Number.isFinite(payloadUnread) ? Math.max(0, payloadUnread) : fallbackUnread);
        const eventUserId = String(message.user_id || '').trim();
        const eventSource = String(message.source || '').trim();
        const eventIsSelf = Boolean(message.is_self)
          || eventSource.startsWith('bot_')
          || eventSource === 'web_panel';
        const eventAvatar = String(
          message.avatar
          || payload.member_profiles?.[eventUserId]?.avatar
          || '',
        ).trim();
        const existingAvatar = String(existing.avatar || existing.avatar_url || '').trim();
        const contactProfile = (matchesCurrent ? msgState.profiles?.[chatId] : payload.member_profiles?.[chatId]) || {};
        const contactAvatar = String(contactProfile.avatar || '').trim();
        const botAvatar = String(window.msgBotProfile?.avatar || '').trim();
        const preservedAvatar = contactAvatar
          || (existingAvatar && (!botAvatar || existingAvatar !== botAvatar) ? existingAvatar : '');
        const overlayAvatar = chatType === 'user' && eventIsSelf
          ? preservedAvatar
          : (eventAvatar || preservedAvatar);
        const overlay = {
          ...existing,
          chat_id:chatId,
          chat_type:chatType,
          appid:String(payload.appid || message.appid || existing.appid || ''),
          nickname:chatType === 'user' && !eventIsSelf
            ? (existing.remark || displayMsgNickname({user_id:chatId, nickname:validMsgNickname(existing.nickname, chatId) || payload.last_nickname || message.nickname, nickname_blank:message.nickname_blank}, contactProfile, existing.nickname || chatId))
            : (existing.nickname || chatId),
          avatar:overlayAvatar,
          ...msgRealtimeChatSummary(payload, message, existing),
          ...friendState,
          msg_count:Math.max(0, Number(existing.msg_count || 0) + (isNewEvent ? 1 : 0)),
          unread,
        };
        msgState.realtimeChats.set(chatId, overlay);
        if (friendChanged || isNewEvent || overlay.last_content !== existing.last_content || overlay.last_ts !== existing.last_ts
          || !msgState.chats.some((chat) => String(chat.chat_id || '') === chatId)) {
          scheduleMsgChatRender();
        }
        if (!isViewing) return;
        if (friendChanged) updateMsgHead({...msgState.historyData, ...friendState});
        const realtimeMessage = {...message, chat_type:chatType, appid:String(payload.appid || message.appid || '')};
        const existingIndex = msgState.messages.findIndex((item) => msgMessagesMatch(item, realtimeMessage));
        if (existingIndex >= 0) {
          const existingMessage = msgState.messages[existingIndex];
          const mergedMessage = mergeMsgRealtimeMessage(existingMessage, realtimeMessage);
          const messageChanged = JSON.stringify(existingMessage) !== JSON.stringify(mergedMessage);
          if (messageChanged) {
            msgState.messages = msgState.messages.map((item, index) => index === existingIndex ? mergedMessage : item);
          }
          if (messageChanged || profilesChanged || referencesChanged) scheduleMsgRealtimeMessageRender(chatId, false, false);
        } else if (isNewEvent && (msgState.historyWindow || msgQuoteJump.pending)) {
          showMsgNewMessages(1);
        } else if (isNewEvent) {
          msgState.messages = [...msgState.messages, realtimeMessage];
          scheduleMsgRealtimeMessageRender(chatId, followLatest);
        }
        if (isNewEvent && followLatest) markMsgRead(chatId, true);
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
      const applyMsgGroupInfo = (payload) => {
        const chatId = String(payload?.chat_id || payload?.group_openid || '').trim();
        if (!chatId) return;
        const memberNum = Number(payload?.member_num);
        const groupName = String(payload?.group_name || '').trim();
        const appid = String(payload?.appid || '').trim();
        const updatedAt = Number(payload?.updated_at || 0);
        const update = (chat) => {
          if (String(chat.chat_id || '') !== chatId || String(chat.chat_type || 'group') !== 'group' || (appid && chat.appid && String(chat.appid) !== appid)) return chat;
          if (updatedAt && Number(chat.group_info_updated_at || 0) > updatedAt) return chat;
          const next = {...chat};
          if (Number.isFinite(memberNum) && memberNum >= 0) next.member_num = next.group_member_num = Math.floor(memberNum);
          if (groupName) { next.group_name = groupName; next.nickname = String(next.remark || groupName); }
          groupProfileFields.forEach((field) => {
            const value = payload[field];
            if (field === 'group_tags' ? Array.isArray(value) : typeof value === 'string') next[field] = field === 'group_tags' ? value.filter((tag) => typeof tag === 'string') : value;
          });
          if (updatedAt) next.group_info_updated_at = updatedAt;
          return next;
        };
        msgState.chats = (msgState.chats || []).map(update);
        const current = msgState.chats.find((chat) => String(chat.chat_id || '') === chatId && String(chat.chat_type || 'group') === 'group');
        const overlay = msgState.realtimeChats.get(chatId);
        if (overlay || current) msgState.realtimeChats.set(chatId, update(overlay || current));
        if (msgState.chatId === chatId && msgState.chatType === 'group') {
          updateMsgHead({group_info:current ? {group_name:current.group_name, member_num:current.member_num ?? current.group_member_num, updated_at:current.group_info_updated_at, membership_status:current.membership_status} : payload});
        }
        const session = groupSettingsState.session;
        if (groupSettingsCurrent(session) && session.target.chat_id === chatId) renderGroupSettingsProfile(session, payload);
        if (groupName) renderMsgChats({chats:msgState.chats});
      };

      const toggleMsgSelect = (row, mid) => {
        if (!mid) return;
        if (msgState.selected.has(mid)) { msgState.selected.delete(mid); row.classList.remove('selected'); }
        else { msgState.selected.add(mid); row.classList.add('selected'); }
        $('msg-multi-count').textContent = `已选 ${msgState.selected.size} 条`;
      };
      const loadMsgHistory = async (older = false, quiet = false) => {
        if (!msgState.chatId) return;
        if (msgQuoteJump.pending || (quiet && msgState.historyWindow)) return;
        if (older && msgState.historyWindow) return loadMsgWindowPage('before');
        const returningWindow = !older ? msgState.historyWindow : null;
        if (returningWindow) cancelMsgQuoteJump();
        const requestScope = JSON.stringify([msgState.chatType, msgState.chatId]);
        // 后台校准不能中止尚未返回的首屏；切换和主动刷新仍可替换旧请求。
        if (!older && quiet && msgState.historyActiveScope === requestScope
          && msgState.historyAbort && !msgState.historyAbort.signal.aborted) return;
        if (older && msgState.historyOlderLoading) return;
        if (older) msgState.historyOlderLoading = true;
        $('msg-composer').hidden = msgState.chatRemoved;
        const requestId = Number(msgState[older ? 'historyOlderRequest' : 'historyRequest'] || 0) + 1;
        msgState[older ? 'historyOlderRequest' : 'historyRequest'] = requestId;
        const previousAbort = msgState[older ? 'historyOlderAbort' : 'historyAbort'];
        if (previousAbort) previousAbort.abort();
        const controller = new AbortController();
        msgState[older ? 'historyOlderAbort' : 'historyAbort'] = controller;
        if (!older) msgState.historyActiveScope = requestScope;
        let timedOut = false;
        const historyTimeoutId = setTimeout(() => { timedOut = true; controller.abort(); }, 18000);
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
          const sameRenderedPage = !returningWindow && !older && !newChat
            && msgState.messageRenderSignature !== null
            && msgMessageListsEqual(incoming, msgState.messages)
            && JSON.stringify(data.member_profiles || {}) === JSON.stringify(msgState.historyData?.member_profiles || {})
            && JSON.stringify(data.references || {}) === JSON.stringify(msgState.historyData?.references || {})
            && Boolean(data.has_more) === Boolean(msgState.historyData?.has_more);
          if (sameRenderedPage) {
            updateMsgHead(data);
            msgState.historyData = {...(msgState.historyData || {}), ...data, messages:incoming};
            msgState.profiles = mergeMsgProfiles(
              mergeMsgProfileMaps(msgState.profiles, data.member_profiles),
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
          const renderNearBottom = forceInitialBottom || Boolean(returningWindow) || newChat || msgBodyNearBottom(body);
          // 轮询可能在上翻页完成后才返回；保留当前已展开的更早消息，避免刷新把它们截掉。
          const currentMessages = Array.isArray(msgState.messages) ? msgState.messages : [];
          const preserveLoadedHistory = !returningWindow && !older && !newChat && currentMessages.length > incoming.length;
          if (returningWindow) msgState.historyWindow = null;
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
            void loadGroupRoles(true).then(() => loadMuteStates());
          }
        } catch (error) {
          if (!requestIsCurrent()) return;
          if (error.name === 'AbortError' && !timedOut) return;
          if (forceInitialBottom) {
            // 首轮请求失败时仍展示缓存/空状态，不能让定位期间的隐藏样式残留。
            msgState.initialScrollChatId = '';
            body.classList.remove('msg-positioning');
            body.scrollTop = body.scrollHeight;
          }
          if (error.status === 401) { showAuthError(error); return; }
          const message = timedOut ? '消息加载超时，请重试' : '消息加载失败，请重试';
          if (!older && !msgState.messages.length && body?.querySelector('.msg-loading')) {
            body.innerHTML = `<div class="msg-empty" role="status">${message}<br><button type="button" class="btn secondary" data-msg-history-retry>重试</button></div>`;
            body.querySelector('[data-msg-history-retry]')?.addEventListener('click', () => {
              if (msgState.chatId !== requestChatId || msgState.chatType !== requestChatType) return;
              body.innerHTML = '<div class="msg-loading" role="status" aria-label="正在加载消息"><span></span><span></span><span></span></div>';
              void loadMsgHistory();
            });
          } else if (!quiet || timedOut) toast(message);
        }
        finally {
          clearTimeout(historyTimeoutId);
          const abortKey = older ? 'historyOlderAbort' : 'historyAbort';
          if (msgState[abortKey] === controller) {
            msgState[abortKey] = null;
            if (!older) msgState.historyActiveScope = '';
          }
          if (older && requestId === msgState.historyOlderRequest) msgState.historyOlderLoading = false;
        }
      };
      const loadGroupRoles = (throttled = false) => {
        const target = msgGroupSnapshotTarget();
        if (!target || !msgGroupSnapshotVisible()) return Promise.resolve(null);
        const requestChatId = target.chat_id;
        const now = Date.now();
        if (throttled && msgState.lastRolesChatId === requestChatId && msgState.lastRolesAppid === target.appid && msgState.lastRolesAt && now - msgState.lastRolesAt < msgRoleRetryMs) return Promise.resolve(null);
        msgState.lastRolesAt = now; msgState.lastRolesChatId = requestChatId; msgState.lastRolesAppid = target.appid;
        msgState.adminCheckedAt.set(requestChatId, now);
        return requestMsgGroupSnapshot('roles', target, (data) => {
          const removed = data.membership_status === 'removed' || data.bot_in_group === false;
          const current = msgState.chats.find((chat) => String(chat.chat_id || '') === requestChatId && chat.chat_type === 'group' && (!target.appid || String(chat.appid || '') === target.appid));
          if (removed) {
            if (current) {
              current.membership_status = 'removed';
              current.in_group = false;
              current.membership_checked_at = Number(data.membership_checked_at || Math.floor(Date.now() / 1000));
            }
            msgState.chatRemoved = true;
            $('msg-composer').hidden = true;
            msgState.adminByChat.set(requestChatId, false);
            updateMsgHead({chat_name:current?.nickname || requestChatId, group_info:{membership_status:'removed'}});
            renderMsgChats({chats:msgState.chats});
            return;
          }
          const role = String(data.bot_role || '').trim().toLowerCase();
          if (!['owner', 'admin', 'member'].includes(role)) return;
          composerMentionPicker.roles.set(JSON.stringify([requestChatId, target.appid]), role);
          if (current) { current.membership_status = 'active'; current.in_group = true; }
          if (current) current.membership_checked_at = Number(data.membership_checked_at || Math.floor(Date.now() / 1000));
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
          if (isAdmin) void loadMuteStates();
        });
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
        if (!confirm('确定撤回这条消息吗？')) return;
        try { await api('message/recall', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, message_id:messageId})}); markLocalMessageRecalled(messageId); msgState.historyCache.delete(`${msgState.chatType}|${msgState.chatId}`); toast('撤回成功'); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const refreshGroupInfo = async () => {
        if (!msgState.chatId || msgState.chatType !== 'group') return;
        const chatId = String(msgState.chatId);
        const requestType = msgState.chatType;
        try {
          const data = await api('message/group-info/refresh', {method:'POST', body:JSON.stringify({chat_id:chatId})});
          msgState.historyCache.delete('group|' + chatId);
          applyMsgGroupInfo({...data, chat_id:chatId});
          toast(data.group_name ? '群信息已刷新：' + data.group_name + (data.member_num ? '（成员 ' + data.member_num + ' 人）' : '') : '群信息已刷新');
          if (msgState.chatId === chatId && msgState.chatType === requestType) void loadMsgHistory();
        } catch (error) { toast(error.message); }
      };
      const refreshMsgConversation = async () => {
        const button = $('msg-reload');
        if (button.disabled) return;
        const chatId = String(msgState.chatId || '');
        const chatType = msgState.chatType;
        const current = (msgState.chats || []).find((chat) => String(chat.chat_id || '') === chatId && chat.chat_type === chatType);
        const appid = String(current?.appid || msgState.messages.find((m) => m.appid)?.appid || '');
        const isCurrent = () => msgState.chatId === chatId && msgState.chatType === chatType;
        button.disabled = true;
        try {
          if (chatId && chatType === 'user') {
            const data = await api('message/user-profile/refresh', {method:'POST', body:JSON.stringify({chat_id:chatId, chat_type:'user', appid})});
            const profile = {nickname:validMsgNickname(data.nickname, chatId), nickname_blank:Boolean(data.nickname_blank), avatar:String(data.avatar || '')};
            msgState.avatarRefresh = msgState.avatarRefresh || new Map();
            if (msgState.avatarRefresh.size >= 256) msgState.avatarRefresh.clear();
            const nonce = Date.now();
            [profile.avatar, current?.avatar, avatarUrl(chatId, 'user', data.appid || appid)].filter(Boolean).forEach((url) => msgState.avatarRefresh.set(String(url), nonce));
            msgState.historyCache.delete('user|' + chatId);
            msgState.chats = msgState.chats.map((chat) => String(chat.chat_id || '') === chatId && chat.chat_type === 'user'
              ? {...chat, appid:data.appid || chat.appid, ...(profile.avatar ? {avatar:profile.avatar} : {}), ...(profile.nickname ? {nickname:chat.remark || profile.nickname} : profile.nickname_blank && !validMsgNickname(chat.nickname, chatId) ? {nickname:chat.remark || '\u00a0'} : {})} : chat);
            const overlay = msgState.realtimeChats.get(chatId);
            if (overlay && overlay.chat_type === 'user') msgState.realtimeChats.set(chatId, {...overlay, ...(profile.nickname ? {nickname:overlay.remark || profile.nickname} : profile.nickname_blank && !validMsgNickname(overlay.nickname, chatId) ? {nickname:overlay.remark || '\u00a0'} : {}), ...(profile.avatar ? {avatar:profile.avatar} : {})});
            if (isCurrent()) {
              msgState.profiles = mergeMsgProfileMaps(msgState.profiles, {[chatId]:profile});
              msgState.messageRenderSignature = null;
              toast(profile.nickname || profile.nickname_blank ? '私聊资料已刷新' : '已重新查询；当前记录未提供有效昵称');
            }
          }
          await loadMsgChats(true);
          if (chatId && isCurrent()) await loadMsgHistory();
        } catch (error) { toast(error.message || '刷新失败'); }
        finally { button.disabled = false; }
      };

      // 群设置只使用打开时捕获的目标；切群、翻页和迟到响应不能改变写入目标。
      const groupSettingsState = {session:null, generation:0, mutating:false, remarkTarget:null};
      const groupSettingsPage = () => ({rows:[], cursors:[''], index:0, nextCursor:'', selected:new Set(), loading:false, loaded:false, available:true, request:0});
      const captureGroupTarget = () => {
        const chatId = String(msgState.chatId || '').trim();
        if (!chatId || msgState.chatType !== 'group') return null;
        const chat = msgState.chats.find((item) => String(item.chat_id || '') === chatId && item.chat_type === 'group');
        const appid = String(chat?.appid || msgState.historyData?.appid || msgState.messages.find((item) => String(item.chat_id || '') === chatId)?.appid || '').trim();
        return Object.freeze({chat_id:chatId, chat_type:'group', appid});
      };
      const groupSettingsCurrent = (session) => Boolean(session && groupSettingsState.session === session && session.generation === groupSettingsState.generation && msgState.chatType === 'group' && msgState.chatId === session.target.chat_id && (!session.target.appid || captureGroupTarget()?.appid === session.target.appid) && !$('msg-group-settings').hidden);
      const groupProfileFields = ['group_finger_memo','group_class_text','group_tags'];
      const decodeGroupProfileText = (value) => {
        const text = String(value || '');
        if (!text.includes('&')) return text;
        const decoder = document.createElement('textarea');
        return text.replace(/&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});/g, (entity) => {
          decoder.innerHTML = entity;
          return decoder.value;
        });
      };
      const clearGroupSettingsProfile = () => {
        $('msg-group-profile-memo').textContent = '未设置';
        $('msg-group-profile-class').textContent = '未设置';
        const placeholder = document.createElement('span');
        placeholder.className = 'msg-group-profile-empty'; placeholder.textContent = '暂无标签';
        $('msg-group-profile-tags').replaceChildren(placeholder);
      };
      const renderGroupSettingsProfile = (session, info = {}, onlyMissing = false) => {
        if (!groupSettingsCurrent(session) || !info || typeof info !== 'object') return;
        const chatId = String(info.chat_id || info.group_openid || '');
        if ((chatId && chatId !== session.target.chat_id) || (session.target.appid && info.appid && String(info.appid) !== session.target.appid)) return;
        const updatedAt = Number(info.updated_at || info.group_info_updated_at || 0);
        if (updatedAt && session.profileUpdatedAt > updatedAt) return;
        const profile = session.profile || (session.profile = {});
        let changed = false;
        groupProfileFields.forEach((field) => {
          if (onlyMissing && Object.prototype.hasOwnProperty.call(profile, field)) return;
          const value = info[field];
          if (field === 'group_tags' ? !Array.isArray(value) : typeof value !== 'string') return;
          const next = field === 'group_tags' ? value.filter((tag) => typeof tag === 'string' && tag.trim()) : value;
          if (!Object.prototype.hasOwnProperty.call(profile, field) || JSON.stringify(profile[field]) !== JSON.stringify(next)) changed = true;
          profile[field] = next;
        });
        if (changed) session.profileRevision = Number(session.profileRevision || 0) + 1;
        if (updatedAt) session.profileUpdatedAt = Math.max(session.profileUpdatedAt || 0, updatedAt);
        const memo = decodeGroupProfileText(profile.group_finger_memo);
        const category = decodeGroupProfileText(profile.group_class_text);
        $('msg-group-profile-memo').textContent = memo.trim() ? memo : '未设置';
        $('msg-group-profile-class').textContent = category.trim() ? category : '未设置';
        const tags = Array.isArray(profile.group_tags) ? profile.group_tags.map(decodeGroupProfileText).filter((tag) => tag.trim()) : [];
        const nodes = tags.map((tag) => {
          const node = document.createElement('span');
          node.className = 'msg-group-profile-tag'; node.textContent = tag;
          return node;
        });
        if (!nodes.length) {
          const node = document.createElement('span');
          node.className = 'msg-group-profile-empty'; node.textContent = '暂无标签'; nodes.push(node);
        }
        $('msg-group-profile-tags').replaceChildren(...nodes);
      };
      const groupMuteDate = (value) => {
        const date = new Date(value);
        return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false}).format(date) : '时间未知';
      };
      const renderGroupMuteStates = (session, data = {}) => {
        if (!groupSettingsCurrent(session) || !msgGroupSnapshotMatches(data, session.target)) return;
        const known = data.has_data === true;
        session.muteLoading = Boolean(data.pending || data.refreshing);
        $('msg-group-mutes-refresh').disabled = groupSettingsState.mutating || session.muteLoading;
        const status = data.refreshing || data.pending ? (known ? '正在后台刷新，先显示上次成功取得的状态。' : '正在后台查询禁言状态…') : data.stale ? '刷新未完成，保留上次成功取得的状态。' : known ? '已读取当前群聊的禁言状态。' : '暂未取得禁言状态，请稍后刷新；机器人需拥有本群管理员身份。';
        groupSettingsMessage('mutes', status, !known && !session.muteLoading);
        if (!known) return;
        const rule = data.global_rule && typeof data.global_rule === 'object' ? data.global_rule : {};
        $('msg-group-mutes-mode').textContent = {none:'未开启全员禁言', always:'始终全员禁言', schedule:'按定时或周期规则禁言'}[String(rule.mode || '')] || '未知状态';
        const checked = Number(data.last_success_at || data.checked_at || 0);
        $('msg-group-mutes-checked').textContent = checked > 0 ? `上次成功更新：${groupMuteDate(checked * 1000)}（北京时间）` : '';
        const schedules = Array.isArray(rule.schedule_rules) ? rule.schedule_rules : [];
        $('msg-group-mutes-schedules').innerHTML = schedules.length ? schedules.map((item) => `<div class="msg-group-mute-rule${item.enabled === true ? '' : ' is-disabled'}"><span>${esc(groupMuteDate(item.start_at))} — ${esc(groupMuteDate(item.end_at))}</span><small>${item.enabled === true ? '已启用' : '未启用'} · 北京时间</small></div>`).join('') : '<span class="msg-group-profile-empty">暂无定时禁言</span>';
        const recurring = Array.isArray(rule.recurring_rules) ? rule.recurring_rules : [];
        const weekdays = ['','周一','周二','周三','周四','周五','周六','周日'];
        $('msg-group-mutes-recurring').innerHTML = recurring.length ? recurring.map((item) => {
          const days = [...new Set((Array.isArray(item.weekdays) ? item.weekdays : []).filter((day) => Number.isInteger(day) && day >= 1 && day <= 7))].sort((a,b) => a-b).map((day) => weekdays[day]).join('、');
          const start = String(item.start_time || ''), end = String(item.end_time || '');
          const crossDay = /^\d{2}:\d{2}$/.test(start) && /^\d{2}:\d{2}$/.test(end) && end < start;
          return `<div class="msg-group-mute-rule${item.enabled === true ? '' : ' is-disabled'}"><span>${esc(days || '未指定日期')} · ${esc(start)} — ${crossDay ? '次日 ' : ''}${esc(end)}</span><small>${item.enabled === true ? '已启用' : '未启用'}</small></div>`;
        }).join('') : '<span class="msg-group-profile-empty">暂无周期禁言</span>';
        const members = (Array.isArray(data.members) ? data.members : []).filter((member) => Number(member?.mute_expire_ts) > Date.now() / 1000 && String(member?.member_openid || '').trim());
        $('msg-group-mutes-count').textContent = `${members.length} 人`;
        $('msg-group-mutes-members').innerHTML = members.length ? members.map((member) => `<div class="msg-group-muted-member" data-group-mute-expire="${esc(Number(member.mute_expire_ts))}"><strong>${esc(groupMemberName(member))}</strong><small>到期：${esc(groupMuteDate(Number(member.mute_expire_ts) * 1000))}（北京时间）</small></div>`).join('') : '<span class="msg-group-profile-empty">当前没有被禁言的成员</span>';
      };
      const updateGroupMuteExpiry = () => {
        if (!groupSettingsCurrent(groupSettingsState.session)) return;
        const list = $('msg-group-mutes-members');
        let changed = false;
        list.querySelectorAll('[data-group-mute-expire]').forEach((node) => {
          if (!(Number(node.dataset.groupMuteExpire) > Date.now() / 1000)) { node.remove(); changed = true; }
        });
        if (!changed) return;
        const count = list.querySelectorAll('[data-group-mute-expire]').length;
        $('msg-group-mutes-count').textContent = `${count} 人`;
        if (!count) list.innerHTML = '<span class="msg-group-profile-empty">当前没有被禁言的成员</span>';
      };
      const clearGroupMuteStates = () => {
        $('msg-group-mutes-mode').textContent = '未知状态';
        $('msg-group-mutes-checked').textContent = '';
        $('msg-group-mutes-count').textContent = '';
        ['schedules','recurring','members'].forEach((kind) => { $(`msg-group-mutes-${kind}`).innerHTML = '<span class="msg-group-profile-empty">尚未查询</span>'; });
        groupSettingsMessage('mutes', '尚未查询');
        $('msg-group-mutes-refresh').disabled = false;
      };
      const groupSettingsMessage = (kind, message = '', error = false) => {
        const node = $(`msg-group-${kind}-status`);
        node.textContent = String(message || ''); node.classList.toggle('error', Boolean(error));
      };
      const groupSettingsRequest = async (session, path, payload = {}) => {
        const data = await api(path, {method:'POST', body:JSON.stringify({...payload, ...session.target})});
        if ((data.chat_id && String(data.chat_id) !== session.target.chat_id) || (data.chat_type && data.chat_type !== 'group') || (session.target.appid && data.appid && String(data.appid) !== session.target.appid)) throw new Error('群聊资料与当前目标不一致，请重新打开设置');
        return data;
      };
      const groupMemberName = (member) => displayMsgNickname({user_id:member.member_openid, nickname:member.username, nickname_blank:member.nickname_blank}, member, '未提供昵称');
      const groupMemberRole = (value) => ({owner:'群主',admin:'管理员',administrator:'管理员',member:'成员',normal:'成员'}[String(value || '').toLowerCase()] || '成员');
      const groupMemberAvatar = (member, session) => avatarHtml(safeMediaUrl(String(member.avatar || '')) || avatarUrl(member.member_openid, 'user', session.target.appid), groupMemberName(member));
      const groupSettingsControls = () => {
        const session = groupSettingsState.session;
        if (!session) return;
        const busy = groupSettingsState.mutating;
        const settings = session.settings || {};
        const loaded = Boolean(session.settings);
        const manageable = loaded && settings.can_manage !== false && settings.available !== false;
        $('msg-group-settings-close').disabled = busy;
        $('msg-group-settings-mask').disabled = busy;
        $('msg-group-settings-tabs').querySelectorAll('button').forEach((node) => { node.disabled = busy; });
        const remarkEditable = loaded && Boolean(settings.remark_editable ?? settings.local_settings_editable ?? settings.editable);
        ['msg-group-remark-name','msg-group-remark-qq','msg-group-basic-save'].forEach((id) => { $(id).disabled = busy || !remarkEditable; });
        $('msg-group-ad-enabled').disabled = busy || !loaded || !settings.ad_editable;
        ['members','blacklist'].forEach((kind) => {
          const page = session[kind];
          const canSelect = manageable && page.available && !page.loading && !busy;
          const boxes = $(`msg-group-${kind}-list`).querySelectorAll('input[data-group-select]');
          boxes.forEach((node) => { node.disabled = !canSelect; node.checked = page.selected.has(node.dataset.groupSelect); });
          const all = $(`msg-group-${kind}-all`);
          all.disabled = !canSelect || !page.rows.length;
          all.checked = page.selected.size > 0 && page.selected.size === Math.min(20, page.rows.length);
          all.indeterminate = page.selected.size > 0 && !all.checked;
          $(`msg-group-${kind}-count`).textContent = `已选 ${page.selected.size} / 20`;
          $(`msg-group-${kind}-prev`).disabled = busy || page.loading || page.index === 0;
          $(`msg-group-${kind}-next`).disabled = busy || page.loading || !page.nextCursor;
          $(`msg-group-${kind}-refresh`).disabled = busy || page.loading;
          $(`msg-group-${kind}-remove`).disabled = !canSelect || page.selected.size < 1;
          $(`msg-group-${kind}-page`).textContent = `第 ${page.index + 1} 页 · 每页 ${kind === 'members' ? 30 : 20} 人`;
        });
        $('msg-group-remove-blacklist').disabled = !manageable || busy;
        $('msg-group-blacklist-openid').disabled = !manageable || busy;
        $('msg-group-blacklist-add').disabled = !manageable || busy;
        $('msg-group-mutes-refresh').disabled = busy || Boolean(session.muteLoading);
      };
      const closeGroupSettings = (force = false) => {
        if (groupSettingsState.mutating && !force) return;
        groupSettingsState.session = null;
        groupSettingsState.generation += 1;
        $('msg-group-settings').hidden = true;
        $('msg-group-settings-open').setAttribute('aria-expanded','false');
        clearGroupSettingsProfile();
        clearGroupMuteStates();
        $('msg-group-member-detail').hidden = true;
        ['members','blacklist'].forEach((kind) => { $(`msg-group-${kind}-list`).innerHTML = ''; });
      };
      const renderGroupSettingsRows = (session, kind) => {
        if (!groupSettingsCurrent(session)) return;
        const page = session[kind];
        $(`msg-group-${kind}-list`).innerHTML = page.rows.length ? page.rows.map((member) => {
          const id = String(member.member_openid || '');
          const name = groupMemberName(member);
          const role = groupMemberRole(member.member_role ?? member.role);
          const tag = kind === 'members' ? 'button' : 'div';
          const action = kind === 'members' ? ` type="button" data-group-member-info="${esc(id)}"` : '';
          return `<div class="msg-group-member"><input type="checkbox" data-group-select="${esc(id)}" aria-label="选择成员 ${esc(name)}"${page.selected.has(id) ? ' checked' : ''}><${tag} class="msg-group-member-open"${action}><span class="msg-avatar">${groupMemberAvatar(member, session)}</span><div><strong>${esc(name)}</strong><small>${esc(id)}</small></div>${kind === 'members' && role !== '成员' ? `<span class="msg-group-role">${esc(role)}</span>` : ''}</${tag}></div>`;
        }).join('') : (page.loaded ? `<div class="msg-empty">${kind === 'members' ? '当前页没有成员' : '本群黑名单为空'}</div>` : '');
        groupSettingsControls();
      };
      const loadGroupSettingsPage = async (session, kind, force = false) => {
        if (!groupSettingsCurrent(session) || groupSettingsState.mutating) return;
        const page = session[kind];
        const request = ++page.request;
        page.loading = true;
        groupSettingsMessage(kind, '正在读取当前群资料…');
        groupSettingsControls();
        try {
          const data = await groupSettingsRequest(session, kind === 'members' ? 'message/group-members' : 'message/group-blacklist', {cursor:page.cursors[page.index] || '', ...(kind === 'blacklist' ? {limit:20} : {}), force});
          if (!groupSettingsCurrent(session) || page.request !== request) return;
          if (data.available === false) { page.available = false; throw new Error(data.message || '当前群暂不支持读取此项资料'); }
          const rows = kind === 'members' ? data.members : data.users;
          if (!Array.isArray(rows)) throw new Error('群聊资料返回不完整，请重试');
          const nextCursor = String(data.next_cursor || '');
          if (nextCursor && page.cursors.slice(0, page.index + 1).includes(nextCursor)) { page.nextCursor = ''; throw new Error('群成员分页游标重复，请刷新后重试'); }
          page.rows = rows.filter((member) => member && typeof member.member_openid === 'string' && member.member_openid.trim());
          page.loaded = true;
          page.available = data.editable !== false && data.available !== false;
          page.nextCursor = nextCursor;
          page.selected.clear();
          groupSettingsMessage(kind, data.message || (session.settings?.can_manage === false ? '当前权限仅允许查看成员资料' : '每次最多选择 20 人；翻页会清空选择'));
          renderGroupSettingsRows(session, kind);
        } catch (error) {
          if (!groupSettingsCurrent(session) || page.request !== request) return;
          if (error.data?.reason === 'api_permission') page.available = false;
          if (error.status === 401) showAuthError(error);
          groupSettingsMessage(kind, error.message || '读取失败，请稍后重试', true);
        } finally {
          if (groupSettingsCurrent(session) && page.request === request) { page.loading = false; groupSettingsControls(); }
        }
      };
      const showGroupSettingsTab = (kind) => {
        const session = groupSettingsState.session;
        if (!groupSettingsCurrent(session) || groupSettingsState.mutating || !['basic','mutes','members','blacklist'].includes(kind)) return;
        session.tab = kind;
        $('msg-group-settings-tabs').querySelectorAll('[data-group-tab]').forEach((node) => { const active = node.dataset.groupTab === kind; node.classList.toggle('active', active); node.setAttribute('aria-selected', String(active)); });
        ['basic','mutes','members','blacklist'].forEach((key) => { $(`msg-group-${key}`).hidden = key !== kind; });
        if (kind === 'mutes') void loadMuteStates(false, session);
        else if (kind !== 'basic' && !session[kind].loaded && !session[kind].loading) void loadGroupSettingsPage(session, kind);
      };
      const openGroupSettings = async () => {
        const target = captureGroupTarget();
        if (!target || msgState.chatRemoved || groupSettingsState.mutating) return;
        closeGroupSettings();
        const current = msgState.chats.find((chat) => String(chat.chat_id || '') === target.chat_id && chat.chat_type === 'group');
        const session = {target, generation:++groupSettingsState.generation, name:current?.remark || current?.group_name || current?.nickname || target.chat_id, settings:null, profile:{}, profileRevision:0, profileUpdatedAt:0, tab:'basic', detailRequest:0, members:groupSettingsPage(), blacklist:groupSettingsPage()};
        groupSettingsState.session = session;
        $('msg-group-settings').hidden = false;
        $('msg-group-settings-open').setAttribute('aria-expanded','true');
        $('msg-group-settings-name').textContent = session.name;
        renderGroupSettingsProfile(session, current || {});
        if (msgState.historyData?.group_info) renderGroupSettingsProfile(session, msgState.historyData.group_info);
        $('msg-group-summary').innerHTML = `<span class="msg-chat-avatar">${avatarHtml(avatarUrl(target.chat_id, 'group', target.appid), session.name)}</span><div><strong>${esc(session.name)}</strong><small>仅设置当前群聊</small></div>`;
        $('msg-group-remark-name').value = '';
        $('msg-group-remark-qq').value = '';
        $('msg-group-ad-enabled').checked = false;
        $('msg-group-remove-blacklist').checked = false;
        $('msg-group-blacklist-openid').value = '';
        ['basic','members','blacklist'].forEach((kind) => groupSettingsMessage(kind, kind === 'basic' ? '正在读取本群设置…' : ''));
        showGroupSettingsTab('basic'); groupSettingsControls();
        $('msg-group-settings').querySelector('.msg-group-drawer')?.focus({preventScroll:true});
        try {
          const profileRevision = session.profileRevision;
          const data = await groupSettingsRequest(session, 'message/group-settings');
          if (!groupSettingsCurrent(session)) return;
          session.settings = data;
          renderGroupSettingsProfile(session, data.group_info || data, session.profileRevision !== profileRevision);
          session.name = data.remark || data.group_name || session.name;
          $('msg-group-settings-name').textContent = session.name;
          $('msg-group-remark-name').value = String(data.remark || '');
          $('msg-group-remark-qq').value = String(data.group_qq || '');
          $('msg-group-ad-enabled').checked = Boolean(data.ad_enabled);
          $('msg-group-summary').innerHTML = `<span class="msg-chat-avatar">${avatarHtml(avatarUrl(target.chat_id, 'group', target.appid), session.name)}</span><div><strong>${esc(data.group_name || session.name)}</strong><small>${Number.isFinite(Number(data.member_num)) && Number(data.member_num) > 0 ? `${Number(data.member_num)} 位成员 · ` : ''}本群独立设置</small></div>`;
          groupSettingsMessage('basic', data.message || ((data.remark_editable ?? data.local_settings_editable ?? data.editable) ? '群备注和广告开关仅对本群生效' : '数据库未配置，本地群设置暂未开放保存'));
          groupSettingsControls();
        } catch (error) {
          if (!groupSettingsCurrent(session)) return;
          groupSettingsMessage('basic', error.message || '本群设置读取失败，请重新打开设置', true);
          groupSettingsControls();
        }
      };
      const mutateGroupSettings = async (session, kind, action) => {
        if (!groupSettingsCurrent(session) || groupSettingsState.mutating) return;
        groupSettingsState.mutating = true; groupSettingsControls();
        try { await action(); }
        catch (error) {
          if (groupSettingsCurrent(session)) groupSettingsMessage(kind, error.message || '本群操作失败，请重试', true);
          if (error.status === 401) showAuthError(error);
        } finally {
          groupSettingsState.mutating = false;
          if (groupSettingsCurrent(session)) groupSettingsControls();
        }
      };
      const saveGroupSettingsBasic = async () => {
        const session = groupSettingsState.session;
        if (!session || $('msg-group-basic-save').disabled) return;
        const remark = $('msg-group-remark-name').value.trim();
        const groupQQ = $('msg-group-remark-qq').value.trim();
        if (groupQQ && !/^\d{5,12}$/.test(groupQQ)) return groupSettingsMessage('basic', '群号需为 5 至 12 位数字，或留空', true);
        await mutateGroupSettings(session, 'basic', async () => {
          await groupSettingsRequest(session, 'message/remarks', {remark, group_qq:groupQQ});
          if (!groupSettingsCurrent(session)) return;
          session.settings = {...session.settings, remark, group_qq:groupQQ};
          session.name = remark || session.settings.group_name || session.target.chat_id;
          $('msg-group-settings-name').textContent = session.name;
          groupSettingsMessage('basic', '本群设置已保存');
          msgState.historyCache.delete(`group|${session.target.chat_id}`);
          void loadMsgChats(true); void loadMsgHistory();
        });
      };
      const saveGroupSettingsAd = async () => {
        const session = groupSettingsState.session;
        if (!session || $('msg-group-ad-enabled').disabled) return;
        const enabled = $('msg-group-ad-enabled').checked;
        await mutateGroupSettings(session, 'basic', async () => {
          try {
            const data = await groupSettingsRequest(session, 'message/group-ad', {action:'set', enabled});
            if (!groupSettingsCurrent(session)) return;
            session.settings.ad_enabled = Boolean(data.enabled);
            msgState.adEnabled = Boolean(data.enabled); msgState.adEditable = Boolean(data.editable); updateMsgAdSwitch();
            groupSettingsMessage('basic', enabled ? '本群广告拦截已开启' : '本群广告拦截已关闭');
          } finally { if (groupSettingsCurrent(session)) $('msg-group-ad-enabled').checked = Boolean(session.settings?.ad_enabled); }
        });
      };
      const showGroupMemberInfo = async (id) => {
        const session = groupSettingsState.session;
        if (!groupSettingsCurrent(session) || groupSettingsState.mutating) return;
        const request = ++session.detailRequest;
        const detail = $('msg-group-member-detail'); detail.hidden = false;
        detail.innerHTML = '<div class="msg-group-status">正在读取成员详情…</div>';
        try {
          const data = await groupSettingsRequest(session, 'message/group-member/info', {member_openid:id});
          if (!groupSettingsCurrent(session) || session.detailRequest !== request) return;
          const member = data.member;
          if (!member || String(member.member_openid || '') !== id) throw new Error('成员资料返回不完整，请重试');
          const joined = String(member.joined_at || '未提供');
          detail.innerHTML = `<div class="msg-group-detail-head"><span class="msg-avatar">${groupMemberAvatar(member, session)}</span><strong>${esc(groupMemberName(member))}</strong><button class="msg-group-close" type="button" data-group-detail-close aria-label="关闭成员详情">×</button></div><div class="msg-group-detail-field"><span>身份</span><b>${esc(groupMemberRole(member.member_role ?? member.role))}</b></div><div class="msg-group-detail-field"><span>OpenID</span><b>${esc(id)}</b></div><div class="msg-group-detail-field"><span>加入时间</span><b>${esc(joined)}</b></div>`;
        } catch (error) {
          if (!groupSettingsCurrent(session) || session.detailRequest !== request) return;
          detail.innerHTML = `<div class="msg-group-status error">${esc(error.message || '成员详情读取失败')}</div><button class="msg-btn" type="button" data-group-detail-close>关闭详情</button>`;
        }
      };
      const removeGroupSettingsMembers = async () => {
        const session = groupSettingsState.session;
        if (!groupSettingsCurrent(session) || $('msg-group-members-remove').disabled) return;
        const ids = Array.from(session.members.selected);
        const addToBlacklist = $('msg-group-remove-blacklist').checked;
        if (ids.length < 1 || ids.length > 20) return groupSettingsMessage('members', '每次请选择 1 至 20 位成员', true);
        if (!confirm(`确认从「${session.name}」移除选中的 ${ids.length} 位成员？${addToBlacklist ? '\n这些成员还会加入本群黑名单。' : ''}`)) return;
        await mutateGroupSettings(session, 'members', async () => {
          const data = await groupSettingsRequest(session, 'message/group-members/remove', {member_openids:ids, add_to_member_blacklist:addToBlacklist});
          if (!groupSettingsCurrent(session)) return;
          const removed = new Set(data.removed_member_openids || data.removed_openids || []);
          const failed = data.failed_member_openids || ids.filter((id) => !removed.has(id));
          const blacklistFailed = data.blacklist_failed_member_openids || data.add_to_member_blacklist_fail_openids || [];
          session.blacklistPendingIds = blacklistFailed.filter((id) => ids.includes(id));
          session.members.rows = session.members.rows.filter((member) => !removed.has(member.member_openid));
          session.members.selected = new Set(failed.filter((id) => ids.includes(id)));
          const resultMessage = data.message || `已移除 ${removed.size} 人${failed.length ? `，${failed.length} 人未移除，已保留选择` : ''}`;
          groupSettingsMessage('members', resultMessage + (session.blacklistPendingIds.length ? `；加入黑名单失败的 OpenID：${session.blacklistPendingIds.join('、')}` : ''), Boolean(failed.length || blacklistFailed.length));
          renderGroupSettingsRows(session, 'members');
          session.blacklist.loaded = false;
          session.blacklist.selected.clear();
          void loadMsgChats(true);
        });
      };
      const updateGroupSettingsBlacklist = async (op) => {
        const session = groupSettingsState.session;
        if (!groupSettingsCurrent(session) || groupSettingsState.mutating) return;
        const ids = op === 'add' ? [$('msg-group-blacklist-openid').value.trim()].filter(Boolean) : Array.from(session.blacklist.selected);
        if (ids.length < 1 || ids.length > 20 || ids.some((id) => !/^[A-Za-z0-9_-]{1,128}$/.test(id))) return groupSettingsMessage('blacklist', '请输入有效的成员 OpenID；每次最多操作 20 人', true);
        if (op === 'add' && $('msg-group-blacklist-add').disabled || op === 'del' && $('msg-group-blacklist-remove').disabled) return;
        if (!confirm(`确认${op === 'add' ? '将' : '解除'}「${session.name}」${ids.length} 位成员的${op === 'add' ? '入群黑名单限制' : '黑名单限制'}？`)) return;
        let reload = false;
        await mutateGroupSettings(session, 'blacklist', async () => {
          const data = await groupSettingsRequest(session, 'message/group-blacklist/update', {op, member_openids:ids});
          if (!groupSettingsCurrent(session)) return;
          const success = new Set(data.success_member_openids || data.success_openids || []);
          const failed = data.failed_member_openids || data.fail_openids || ids.filter((id) => !success.has(id));
          if (op === 'del') {
            session.blacklist.rows = session.blacklist.rows.filter((member) => !success.has(member.member_openid));
            session.blacklist.selected = new Set(failed.filter((id) => ids.includes(id)));
            renderGroupSettingsRows(session, 'blacklist');
          } else if (!failed.length) { $('msg-group-blacklist-openid').value = ''; reload = true; }
          groupSettingsMessage('blacklist', data.message || `已完成 ${success.size} 人${failed.length ? `，${failed.length} 人未完成，已保留待处理对象` : ''}`, Boolean(failed.length));
        });
        if (reload && groupSettingsCurrent(session)) await loadGroupSettingsPage(session, 'blacklist', true);
      };
      const bindGroupSettings = () => {
        $('msg-group-settings-open').addEventListener('click', openGroupSettings);
        ['msg-group-settings-close','msg-group-settings-mask'].forEach((id) => $(id).addEventListener('click', () => closeGroupSettings()));
        $('msg-group-settings-tabs').addEventListener('click', (event) => { const button = event.target.closest('[data-group-tab]'); if (button) showGroupSettingsTab(button.dataset.groupTab); });
        $('msg-group-mutes-refresh').addEventListener('click', () => { const session = groupSettingsState.session; if (groupSettingsCurrent(session) && !groupSettingsState.mutating) void loadMuteStates(true, session); });
        $('msg-group-basic-save').addEventListener('click', saveGroupSettingsBasic);
        $('msg-group-ad-enabled').addEventListener('change', saveGroupSettingsAd);
        $('msg-group-members-remove').addEventListener('click', removeGroupSettingsMembers);
        $('msg-group-blacklist-add').addEventListener('click', () => updateGroupSettingsBlacklist('add'));
        $('msg-group-blacklist-remove').addEventListener('click', () => updateGroupSettingsBlacklist('del'));
        $('msg-group-member-detail').addEventListener('click', (event) => { if (event.target.closest('[data-group-detail-close]')) { $('msg-group-member-detail').hidden = true; if (groupSettingsState.session) ++groupSettingsState.session.detailRequest; } });
        ['members','blacklist'].forEach((kind) => {
          $(`msg-group-${kind}-list`).addEventListener('change', (event) => {
            const session = groupSettingsState.session; const id = event.target.dataset.groupSelect;
            if (!groupSettingsCurrent(session) || groupSettingsState.mutating || !id) return;
            const selected = session[kind].selected;
            if (event.target.checked) { if (selected.size >= 20) { event.target.checked = false; return toast('每次最多选择 20 人'); } selected.add(id); } else selected.delete(id);
            groupSettingsControls();
          });
          $(`msg-group-${kind}-all`).addEventListener('change', (event) => {
            const session = groupSettingsState.session;
            if (!groupSettingsCurrent(session) || groupSettingsState.mutating) return;
            session[kind].selected = new Set(event.target.checked ? session[kind].rows.slice(0,20).map((member) => member.member_openid) : []);
            if (event.target.checked && session[kind].rows.length > 20) toast('每次最多选择 20 人，已选择本页前 20 人');
            groupSettingsControls();
          });
          $(`msg-group-${kind}-refresh`).addEventListener('click', () => { const session = groupSettingsState.session; if (session) { session[kind].selected.clear(); void loadGroupSettingsPage(session, kind, true); } });
          ['prev','next'].forEach((direction) => $(`msg-group-${kind}-${direction}`).addEventListener('click', () => {
            const session = groupSettingsState.session;
            if (!groupSettingsCurrent(session) || groupSettingsState.mutating || session[kind].loading) return;
            const page = session[kind];
            if (direction === 'next') { if (!page.nextCursor) return; page.cursors[page.index + 1] = page.nextCursor; ++page.index; } else { if (page.index < 1) return; --page.index; }
            page.selected.clear(); page.rows = []; page.loaded = false; page.nextCursor = '';
            session.detailRequest += 1; $('msg-group-member-detail').hidden = true;
            renderGroupSettingsRows(session, kind); void loadGroupSettingsPage(session, kind);
          }));
        });
        $('msg-group-members-list').addEventListener('click', (event) => { const button = event.target.closest('[data-group-member-info]'); if (button) void showGroupMemberInfo(button.dataset.groupMemberInfo); });
        document.addEventListener('keydown', (event) => {
          if ($('msg-group-settings').hidden) return;
          if (event.key === 'Escape') { event.preventDefault(); closeGroupSettings(); }
          if (event.key !== 'Tab') return;
          const focusable = Array.from($('msg-group-settings').querySelectorAll('button:not(:disabled),input:not(:disabled),[tabindex="0"]')).filter((node) => node.getClientRects().length > 0);
          if (!focusable.length) return;
          const first = focusable[0], last = focusable[focusable.length - 1];
          if (event.shiftKey && (document.activeElement === first || !$('msg-group-settings').contains(document.activeElement))) { last.focus(); event.preventDefault(); }
          else if (!event.shiftKey && (document.activeElement === last || !$('msg-group-settings').contains(document.activeElement))) { first.focus(); event.preventDefault(); }
        });
      };

      const showRemarkDialog = async () => {
        const target = captureGroupTarget();
        if (!target) return;
        groupSettingsState.remarkTarget = target;
        try {
          const data = await api('message/remarks', {method:'POST', body:JSON.stringify({...target, action:'get'})});
          if (groupSettingsState.remarkTarget !== target || msgState.chatType !== 'group' || msgState.chatId !== target.chat_id) return;
          $('msg-remark-name').value = data.remark || '';
          $('msg-remark-qq').value = data.group_qq || '';
          $('msg-remark-modal').hidden = false;
        } catch (error) { if (groupSettingsState.remarkTarget === target) toast(error.message || '群备注读取失败'); }
      };
      const saveRemark = async () => {
        const target = groupSettingsState.remarkTarget;
        if (!target) return;
        const remark = $('msg-remark-name').value.trim();
        const groupQQ = $('msg-remark-qq').value.trim();
        try {
          await api('message/remarks', {method:'POST', body:JSON.stringify({...target, remark, group_qq:groupQQ})});
          msgState.historyCache.delete(`group|${target.chat_id}`);
          if (groupSettingsState.remarkTarget !== target || msgState.chatType !== 'group' || msgState.chatId !== target.chat_id) return;
          toast('备注已保存'); $('msg-remark-modal').hidden = true; void loadMsgChats(true); void loadMsgHistory();
        } catch (error) { if (groupSettingsState.remarkTarget === target) toast(error.message); }
      };
      const deleteRemark = async () => {
        const target = groupSettingsState.remarkTarget;
        if (!target || !confirm('确定删除该群的备注和群号吗？')) return;
        try {
          await api('message/remarks', {method:'POST', body:JSON.stringify({...target, action:'delete'})});
          msgState.historyCache.delete(`group|${target.chat_id}`);
          if (groupSettingsState.remarkTarget !== target || msgState.chatType !== 'group' || msgState.chatId !== target.chat_id) return;
          toast('备注已删除'); $('msg-remark-modal').hidden = true; void loadMsgChats(true); void loadMsgHistory();
        } catch (error) { if (groupSettingsState.remarkTarget === target) toast(error.message); }
      };
      const sendMessage = () => {
        if (msgState.chatRemoved) return toast(msgState.chatType === 'user' ? '对方已删除机器人好友' : '你已被移除群聊');
        const hasImage = composerHasImage();
        const hasMedia = composerHasMedia();
        const editorText = getComposerText();
        const imageParts = editorText.split(composerImageMarker);
        const imageBefore = imageParts.length > 1 ? imageParts[0].trim() : '';
        const imageAfter = imageParts.length > 1 ? imageParts.slice(1).join('').trim() : '';
        const content = imageParts.length > 1 ? imageParts.join('').trim() : editorText.trim();
        const customId = $('msg-custom-id')?.value.trim() || '';
        const payload = { chat_id:msgState.chatId, chat_type:msgState.chatType, appid:String(msgState.chatAppid || ''), msg_type:hasImage ? 'text' : (hasMedia ? 'media' : msgState.sendType), content, send_mode:msgState.sendMode, custom_id:customId, quote_message_id:msgState.quote?.id || '', quote_message_refidx:msgState.quote?.refidx || '', image_url:msgState.pastedImageSource || '', image_before:imageBefore, image_after:imageAfter, image_marker:hasImage ? composerImageMarker : '' };
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
        payload.browser_media_key = browserMediaKeyForPayload(payload);
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
      $('msg-filter').querySelectorAll('[data-msg-filter]').forEach((el) => el.addEventListener('click', () => {
        $('msg-filter').querySelectorAll('[data-msg-filter]').forEach((x) => x.classList.toggle('active', x === el));
        msgState.filter = el.dataset.msgFilter;
        msgState.page = 1;
        msgState.chatListTopPending = true;
        $('msg-chats').scrollTop = 0;
        if (msgState.chatListServerLoaded) renderMsgChats({chats:msgState.chats});
        else loadMsgChats(true);
      }));
      $('msg-search-btn').addEventListener('click', () => { msgState.search = $('msg-search-input').value.trim(); msgState.page = 1; msgState.chatListTopPending = true; loadMsgChats(true); });
      $('msg-search-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') { msgState.search = e.target.value.trim(); msgState.page = 1; msgState.chatListTopPending = true; loadMsgChats(true); } });
      $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((el) => el.addEventListener('click', () => { $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((x) => x.classList.toggle('active', x === el)); msgState.sendType = el.dataset.msgType; renderMsgExtra(); }));
      $('msg-send-mode').addEventListener('change', (e) => { msgState.sendMode = e.target.value; $('msg-custom-id').hidden = !(msgState.sendMode === 'custom_msg_id' || msgState.sendMode === 'custom_event_id'); });
      $('msg-send').addEventListener('click', sendMessage);
      const handleComposerKeydown = (e) => {
        if (handleComposerMentionKeydown(e)) return;
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey && !e.isComposing && !composerMentionPicker.composing && e.keyCode !== 229) {
          e.preventDefault();
          sendMessage();
        }
      };
      document.querySelectorAll('#msg-editor').forEach((node) => {
        node.addEventListener('keydown', handleComposerKeydown);
        node.addEventListener('keyup', () => { saveComposerSelection(); scheduleComposerMentionPicker(); });
        node.addEventListener('mouseup', () => { saveComposerSelection(); scheduleComposerMentionPicker(); });
        node.addEventListener('input', () => { syncComposerImageState(); saveComposerSelection(); scheduleComposerMentionPicker(); });
        node.addEventListener('compositionstart', () => { composerMentionPicker.composing = true; closeComposerMentionPicker(); });
        node.addEventListener('compositionend', () => { composerMentionPicker.composing = false; saveComposerSelection(); scheduleComposerMentionPicker(); });
        node.addEventListener('blur', () => closeComposerMentionPicker());
      });
      $('msg-mention-picker')?.addEventListener('pointerdown', (event) => event.preventDefault());
      $('msg-mention-picker')?.addEventListener('click', (event) => {
        const button = event.target.closest('[data-mention-index]');
        if (button && !button.disabled) selectComposerMentionItem(Number(button.dataset.mentionIndex));
      });
      document.addEventListener('selectionchange', scheduleComposerMentionPicker);
      document.addEventListener('pointerdown', (event) => {
        if (!getComposerEditor()?.contains(event.target) && !$('msg-mention-picker')?.contains(event.target)) closeComposerMentionPicker(true);
      });
      window.addEventListener('resize', positionComposerMentionPicker);
      document.addEventListener('scroll', positionComposerMentionPicker, true);
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
              if (setComposerImage(reader.result, '', reader.result, file)) toast('已粘贴图片，可继续输入文字后发送');
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
          if (setComposerImage(pastedSource, '', pastedSource, file)) toast('已粘贴图片，可单独发送或继续输入文字');
          return;
        }
        const proxy = mediaProxyUrl(pastedSource, 'image') || pastedSource;
        void fetchImageBlob(proxy)
          .then((blob) => blobToDataUrl(blob))
          .then((dataUrl) => {
            if (setComposerImage(dataUrl, '', dataUrl, dataUrlToFile(dataUrl))) toast('已粘贴图片，可单独发送或继续输入文字');
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
        if (!body || msgQuoteJump.pending || msgQuoteJump.pagePending || body.scrollTop > 20 || msgState.historyOlderLoading || !msgState.historyData?.has_more) return;
        loadMsgHistory(true);
      };
      const msgChatsNode = $('msg-chats');
      const flushPendingMsgChats = () => {
        if (msgState.chatListScrollActive || msgState.chatListPointerActive) return;
        const pending = msgState.chatListPendingData;
        msgState.chatListPendingData = null;
        if (pending) renderMsgChats(pending);
      };
      msgChatsNode?.addEventListener('pointerdown', () => {
        msgState.chatListPointerActive = true;
      });
      msgChatsNode?.addEventListener('mousedown', () => {
        msgState.chatListPointerActive = true;
      });
      const releaseMsgChatPointer = () => {
        if (!msgState.chatListPointerActive) return;
        msgState.chatListPointerActive = false;
        setTimeout(flushPendingMsgChats, 0);
      };
      window.addEventListener('pointerup', releaseMsgChatPointer, {passive:true});
      window.addEventListener('pointercancel', releaseMsgChatPointer, {passive:true});
      window.addEventListener('mouseup', releaseMsgChatPointer, {passive:true});
      window.addEventListener('blur', releaseMsgChatPointer, {passive:true});
      msgChatsNode?.addEventListener('scroll', () => {
        msgState.chatListScrollActive = true;
        renderMsgChatVirtualWindow();
        if (msgState.chatListScrollTimer) clearTimeout(msgState.chatListScrollTimer);
        msgState.chatListScrollTimer = setTimeout(() => {
          msgState.chatListScrollTimer = null;
          msgState.chatListScrollActive = false;
          flushPendingMsgChats();
        }, 140);
      }, {passive:true});
      window.addEventListener('resize', () => {
        if (!msgChatsNode) return;
        const rowHeight = getMsgChatRowHeight(msgChatsNode);
        if (rowHeight !== msgState.chatListRowHeight && msgState.chatListRendered) {
          msgState.chatRenderSignature = '';
          renderMsgChats({chats:msgState.chats});
        } else {
          renderMsgChatVirtualWindow();
        }
      }, {passive:true});
      $('msg-body').addEventListener('scroll', () => {
        maybeLoadOlderMessages();
        if (msgState.historyWindow || msgQuoteJump.pending) return;
        if (!msgBodyNearBottom($('msg-body'))) return;
        const activeChat = msgState.chats.find((chat) => String(chat.chat_id || '') === String(msgState.chatId || ''));
        const shouldRead = msgState.pendingNewMessages > 0 || Number(activeChat?.unread || 0) > 0;
        clearMsgNewMessages();
        if (shouldRead) markMsgRead(undefined, true);
      });
      $('msg-new-messages').addEventListener('click', () => scrollMsgToBottom('smooth'));
      $('msg-reload').addEventListener('click', refreshMsgConversation);
      $('msg-multi-recall').addEventListener('click', recallSelected);
      $('msg-multi-cancel').addEventListener('click', () => { exitMultiMode(); });
      $('msg-ad-switch').addEventListener('click', toggleGroupAdSwitch);
      $('msg-pan-account-select').addEventListener('change', saveMsgPanSelection);
      $('msg-refresh-info').addEventListener('click', refreshGroupInfo);
      $('msg-remark').addEventListener('click', showRemarkDialog);
      bindGroupSettings();
      $('msg-quote-clear').addEventListener('click', clearMsgQuote);
      $('msg-raw-copy').addEventListener('click', async () => {
        const button = $('msg-raw-copy');
        const content = $('msg-raw-content').textContent || '';
        button.disabled = true;
        try {
          const copied = await copyMsgText(content, null, {exact:true, notify:false});
          if ($('msg-raw-content').textContent === content) button.textContent = copied ? '已复制' : '复制失败，请重试';
        } finally { button.disabled = false; }
      });
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
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { msgLastPollAt = 0; pollLocalMessages(); void loadGroupRoles(true).then(() => loadMuteStates()); void refreshQuarkProfilesSilently(); } else { closeComposerMentionPicker(); cancelMsgQuoteJump(); stopMsgGroupSnapshots(); } });
      window.addEventListener('pagehide', () => { closeComposerMentionPicker(); cancelMsgQuoteJump(); stopMsgGroupSnapshots(); });
      setInterval(refreshQuarkProfilesSilently, 60000);
      msgState.timer = setInterval(pollLocalMessages, 5000);
      msgState.muteTimer = setInterval(() => {
        updateMuteCountdowns();
        if (document.visibilityState === 'hidden' || $('page-messages')?.hidden) return;
        if (msgState.chatType === 'group' && msgState.chatId) void loadMuteStates();
      }, 1000);

      setView(viewFromUrl(), false); load();
    })();
  """
