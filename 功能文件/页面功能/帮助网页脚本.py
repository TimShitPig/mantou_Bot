"""馒头控制台的浏览器交互脚本。"""

控制台脚本 = r"""
    (() => {
      const initialParams = new URLSearchParams(location.search);
      if (initialParams.has('token')) { initialParams.delete('token'); const cleanQuery = initialParams.toString(); history.replaceState({}, '', `${location.pathname}${cleanQuery ? `?${cleanQuery}` : ''}${location.hash}`); }
      const $ = (id) => document.getElementById(id);
      const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
      const views = {
        dashboard: ['控制台', '查看机器人和小说服务的实时状态'],
        bot: ['机器人配置', '查看安全摘要、监听地址和访问策略'],
        novels: ['小说功能', '管理全局开关、测试模式和平台开关'],
        pans: ['网盘配置', '管理主分享网盘和账号安全摘要'],
        runtime: ['运行状态', '查看服务器、数据库和插件实时指标'],
        help: ['帮助指令', '查看机器人当前支持的聊天指令'],
         settings: ['系统设置', '直接修改插件配置、网盘目录和数据库连接'],
        messages: ['消息记录', '查看群聊和私聊消息，回复、发送和撤回消息'],
      };
      let snapshot = null;
      let activePanTab = null;
      let toastTimer = null;
      const showNotice = (message) => { const node = $('notice'); node.textContent = message; node.classList.toggle('show', Boolean(message)); };
      const toast = (message) => { const node = $('toast'); node.textContent = message; node.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove('show'), 2200); };
      const api = async (path, options = {}) => {
        const response = await fetch(`/api/${path}`, { cache:'no-store', credentials:'same-origin', headers:{'Content-Type':'application/json'}, ...options });
        const data = await response.json().catch(() => ({ok:false,error:'服务器返回格式错误'}));
        if (!response.ok || !data.ok) { const error = new Error(data.error || '请求失败'); error.status = response.status; throw error; }
        return data;
      };
      const viewFromUrl = () => { const current = new URLSearchParams(location.search).get('view'); return views[current] ? current : 'dashboard'; };
      const setView = (view, push = true) => {
        const next = views[view] ? view : 'dashboard';
        if (push) { const nextParams = new URLSearchParams(location.search); nextParams.set('view', next); history.pushState({view:next}, '', `${location.pathname}?${nextParams.toString()}`); }
        const meta = views[next];
        $('page-title').textContent = meta[0]; $('page-subtitle').textContent = meta[1];
        document.querySelectorAll('[data-page]').forEach((node) => { node.hidden = node.dataset.page !== next; });
        document.querySelectorAll('.sidebar [data-view]').forEach((node) => { const active = node.dataset.view === next; node.classList.toggle('active', active); node.setAttribute('aria-current', active ? 'page' : 'false'); });
        if (next === 'dashboard') $('page-eyebrow').textContent = '馒头Bot / 管理台'; else $('page-eyebrow').textContent = '馒头Bot / 功能页面';
        if (next === 'messages') { connectMsgEvents(); loadMsgChats(); if (msgState.chatId) loadMsgHistory(); }
        else if (msgState.eventSource || msgState.eventSocket || msgState.eventReconnect) closeMsgEvents();
        window.scrollTo({top:0, behavior:'auto'});
      };
      const switchHtml = (key, enabled, editable, label) => `<button class="switch ${enabled ? 'on' : ''}" data-switch="${esc(key)}" data-enabled="${enabled}" ${editable ? '' : 'disabled'} aria-label="${esc(label)}" aria-pressed="${enabled}"><span></span></button>`;
      const platformGlyph = (name) => ({'番茄':'番','七猫':'猫','书旗':'旗','QQ阅读':'阅','QQ浏览器':'浏','得间':'得','点众':'众','盐言':'盐','塔读':'塔','百度':'度','小米':'米','晋江':'晋','宜搜':'搜','米读':'读','猫眼':'眼','酷我':'酷','酷匠':'匠','连城':'城','菠萝包':'菠'}[name] || String(name || '书').slice(0, 1));
      const categoryOrder = ['basic_settings', 'help_web_settings', 'uc_pan_settings', 'quark_pan_settings', 'baidu_pan_settings', 'database_settings'];
      const safeFieldValue = (field) => {
        if (field.kind === 'admin_list') return Array.isArray(field.value) ? field.value.join('\n') : '';
        return field.secret ? '' : String(field.value ?? '');
      };
      const renderConfigEditor = (targetId, fields, editable, filter) => {
        const node = $(targetId);
        if (!node) return;
        const selected = (fields || []).filter((field) => !filter || filter(field));
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
          return `<div class="config-field"><label for="${inputId}">${label}</label><input id="${inputId}" type="${type}" data-config-field="${esc(field.key)}" value="${esc(safeFieldValue(field))}" ${editable ? '' : 'disabled'} placeholder="${esc(field.secret ? '留空不修改' : '')}"><small>${hint}</small></div>`;
        }).join('')}</div></section>`).join('') + `<div class="config-actions"><button class="primary-button" type="button" data-config-save ${editable ? '' : 'disabled'}>保存配置</button><span class="config-message" data-config-message></span></div>`;
        node.querySelector('[data-config-save]')?.addEventListener('click', () => saveConfig(node));
      };
       const saveConfig = async (editor) => {
        const fields = {};
        editor.querySelectorAll('[data-config-field]').forEach((input) => {
          const value = input.tagName === 'TEXTAREA' ? input.value : input.value;
          if (input.type === 'password' && !value.trim()) return;
           if (input.dataset.configField === 'group_file_cleanup_admin_qq') {
             fields[input.dataset.configField] = value.split(/[\s,，]+/).filter(Boolean);
          } else fields[input.dataset.configField] = value;
        });
        const message = editor.querySelector('[data-config-message]');
        try { const result = await api('config', {method:'POST', body:JSON.stringify({fields})}); if (message) { message.textContent = result.message || '配置已保存'; message.className = 'config-message ok'; } toast(result.message || '配置已保存'); await load(); }
         catch (error) { if (error.status === 401) showAuthError(error); if (message) { message.textContent = error.message; message.className = 'config-message error'; } else toast(error.message); }
      };
      const panAccountRows = (item, editable) => (item.account_summary || []).map((account) => `<div class="account-row"><div><strong>账号${esc(account.index)}</strong><span>${esc(account.name || '未命名账号')} · ${esc(account.phone || '未获取')}</span></div><button type="button" data-pan-delete="${esc(item.key)}" data-index="${esc(account.index)}" ${editable ? '' : 'disabled'}>删除</button></div>`).join('');
       const renderPanCard = (item, pansEditable, configEditable) => { const directoryField = ({UC:'uc_pan_upload_dir','夸克':'quark_pan_upload_dir','百度':'baidu_pan_upload_dir'})[item.key] || ''; return `<article id="pan-card-${esc(item.key)}" class="pan-card ${item.active ? 'active' : ''}" data-pan-card="${esc(item.key)}" role="tabpanel" aria-labelledby="pan-tab-${esc(item.key)}"><div class="pan-top"><div class="pan-title"><div class="pan-logo">${esc(item.key.slice(0,1))}</div><strong>${esc(item.name)}</strong></div><div>${item.active ? '<span class="tag active">当前主网盘</span>' : ''}</div></div><div class="pan-meta"><div><span>配置状态</span><strong>${item.configured ? '<span class="tag ok">已配置</span>' : '<span class="tag off">未配置</span>'}</strong></div><div><span>账号数量</span><strong>${esc(item.accounts)} 个</strong></div><div><span>上传目录</span><strong title="${esc(item.directory)}">${esc(item.directory || '默认目录')}</strong></div><div><span>群账号选择</span><strong>默认账号${esc(item.selected_account || 1)}</strong></div></div><div class="pan-security-note">登录态：${item.configured ? '已保存（Cookie 不回显）' : '未配置'}${item.key === '夸克' ? ' · 可刷新账号资料' : ''}</div><div class="pan-directory"><input type="text" data-pan-dir="${esc(item.key)}" data-pan-dir-field="${esc(directoryField)}" value="${esc(item.directory || '')}" placeholder="/小说机器人" ${configEditable ? '' : 'disabled'}><button class="outline-button" type="button" data-pan-dir-save="${esc(item.key)}" ${configEditable ? '' : 'disabled'}>保存目录</button></div><div class="account-list">${panAccountRows(item, pansEditable) || '<div class="empty">暂无账号</div>'}</div><div class="account-add"><input type="password" data-pan-cookie="${esc(item.key)}" placeholder="粘贴 ${esc(item.name)} Cookie（只写入）" ${pansEditable ? '' : 'disabled'}><button class="outline-button" type="button" data-pan-add="${esc(item.key)}" ${pansEditable ? '' : 'disabled'}>添加账号</button></div><div class="account-actions"><button class="outline-button" type="button" data-pan-refresh="${esc(item.key)}" ${pansEditable && item.key === '夸克' ? '' : 'disabled'}>刷新资料</button><select class="pan-select" data-pan="${esc(item.key)}" ${pansEditable ? '' : 'disabled'} aria-label="选择${esc(item.name)}"><option value="">${item.active ? '当前使用中' : '设为主分享网盘'}</option><option value="${esc(item.key)}">切换到${esc(item.name)}</option></select></div><div class="group-account"><input type="text" data-pan-group="${esc(item.key)}" placeholder="QQ群号（用于选择账号）" ${pansEditable ? '' : 'disabled'}><select data-pan-group-index="${esc(item.key)}" ${pansEditable ? '' : 'disabled'}>${(item.account_summary || []).map((account) => `<option value="${esc(account.index)}" ${Number(account.index) === Number(item.selected_account || 1) ? 'selected' : ''}>账号${esc(account.index)}</option>`).join('') || '<option value="1">账号1</option>'}</select><button class="outline-button" type="button" data-pan-group-save="${esc(item.key)}" ${pansEditable ? '' : 'disabled'}>保存群选择</button></div></article>`; };
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
        $('pan-active-label').textContent = pans.active || '--';
        $('pan-grid').innerHTML = (pans.items || []).map((item) => renderPanCard(item, pans.editable, pans.config_editable)).join('') || '<div class="empty">没有网盘数据</div>';
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
      const changePan = async (key, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，网盘选择不能保存'); if (node) node.disabled = true; try { await api('pan-switch', {method:'POST', body:JSON.stringify({key})}); toast('主分享网盘已更新'); await load(); } catch (error) { if (node) node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
      const load = async () => { try { render(await api('dashboard')); if ($('popover-logout')) $('popover-logout').hidden = false; setView(viewFromUrl(), false); } catch (error) { showAuthError(error); } };
      $('popover-logout').addEventListener('click', async () => { try { await api('logout', {method:'POST'}); } finally { location.reload(); } });
      document.querySelectorAll('.sidebar [data-view]').forEach((node) => node.addEventListener('click', (event) => { event.preventDefault(); setView(node.dataset.view); }));
      window.addEventListener('popstate', () => setView(viewFromUrl(), false));

      // ---------- 消息记录页 ----------
      const msgState = { filter:'all', search:'', page:1, chatId:'', chatType:'group', chats:[], realtimeChats:new Map(), messages:[], historyData:null, renderedChatId:'', pendingNewMessages:0, historyRequest:0, chatListRequest:0, quote:null, mute:{member:'',name:''}, sendType:'text', sendMode:'default', muteMinutes:30, timer:null, eventSocket:null, eventSource:null, eventTransport:'', eventReconnect:null, eventRefreshTimer:null, eventKeys:new Set(), eventKeyOrder:[], lastRolesAt:0, lastRolesChatId:'', botIsAdmin:false, profiles:{}, pastedImage:null, sending:false, multi:false, selected:new Set(), ctxMsg:null, ctxUser:null };
      const msgComposerTabs = [['text','文本'],['markdown','Markdown'],['media','媒体'],['ark','ARK模板'],['card','图文卡片']];
      const msgFilterLabels = { all:'全量', remark:'备注', group:'群聊', user:'私聊' };
      const avatarUrl = (openid, type, appid) => {
        if (!openid) return '';
        if (type === 'group') { const qq = window.msgGroupQQ?.[openid] || ''; return qq ? `https://p.qlogo.cn/gh/${qq}/${qq}/100/` : ''; }
        const aid = appid || window.msgAppid || '';
        return aid ? `https://q.qlogo.cn/qqapp/${aid}/${openid}/0` : '';
      };
      const avatarImg = (url, letter) => `<img src="${esc(url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.closest('.msg-chat-avatar, .msg-avatar').classList.add('avatar-fallback'); this.remove();">`;
      const avatarHtml = (url, letter) => {
        if (!url) return esc(String(letter || '?').slice(0, 1));
        return `<span class="avatar-letter">${esc(String(letter || '?').slice(0, 1))}</span>` + avatarImg(url, letter);
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
      const mergeMsgRealtimeChats = (serverChats) => {
        const byId = new Map((serverChats || []).map((chat) => [String(chat.chat_id || ''), {...chat}]));
        msgState.realtimeChats.forEach((overlay, chatId) => {
          const current = byId.get(chatId);
          if (!current) { if (msgChatMatchesView(overlay)) byId.set(chatId, {...overlay}); return; }
          const serverTs = Number(current.last_ts || 0);
          const eventTs = Number(overlay.last_ts || 0);
          if (serverTs > eventTs) { msgState.realtimeChats.delete(chatId); return; }
          byId.set(chatId, {
            ...current,
            ...overlay,
            nickname:current.nickname || overlay.nickname,
            remark:Object.prototype.hasOwnProperty.call(current, 'remark') ? String(current.remark || '') : String(overlay.remark || ''),
            group_qq:Object.prototype.hasOwnProperty.call(current, 'group_qq') ? String(current.group_qq || '') : String(overlay.group_qq || ''),
            pinned:Object.prototype.hasOwnProperty.call(current, 'pinned') ? Boolean(current.pinned) : Boolean(overlay.pinned),
            msg_count:Math.max(Number(current.msg_count || 0), Number(overlay.msg_count || 0)),
          });
        });
        return [...byId.values()].filter(msgChatMatchesView).sort((left, right) =>
          Number(Boolean(right.pinned)) - Number(Boolean(left.pinned)) ||
          Number(Number(right.unread || 0) > 0) - Number(Number(left.unread || 0) > 0) ||
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
      const markMsgRead = async (chatId = msgState.chatId) => {
        const id = String(chatId || '');
        if (!id) return;
        clearMsgChatUnread(id);
        try { await api('message/read', {method:'POST', body:JSON.stringify({chat_id:id})}); } catch (_) {}
      };
      const renderMsgChats = (data) => {
        const node = $('msg-chats'); const chats = mergeMsgRealtimeChats(data.chats || []);
        msgState.chats = chats;
        window.msgGroupQQ = {}; (chats||[]).forEach((chat) => { if (chat.group_qq) window.msgGroupQQ[chat.chat_id] = chat.group_qq; });
        if (!chats.length) { node.innerHTML = '<div class="msg-empty">暂无消息会话，机器人收到消息后会出现在这里</div>'; return; }
        node.innerHTML = chats.map((chat) => {
          const av = avatarUrl(chat.chat_id, chat.chat_type, chat.appid);
          if (chat.appid) window.msgAppid = chat.appid;
          const typeTag = chat.chat_type === 'user' ? '<span class="msg-chat-type">私聊</span>' : '<span class="msg-chat-type">群聊</span>';
          const viewing = msgState.chatId === chat.chat_id;
          const viewingAtBottom = viewing && !$('page-messages')?.hidden && msgState.pendingNewMessages === 0 && msgBodyNearBottom($('msg-body'));
          const unread = viewingAtBottom ? 0 : Number(chat.unread || 0);
          if (viewingAtBottom && Number(chat.unread || 0) > 0) queueMicrotask(() => markMsgRead(chat.chat_id));
          return `<button type="button" class="msg-chat ${chat.pinned ? 'pinned' : ''} ${viewing ? 'active' : ''}" data-msg-chat="${esc(chat.chat_id)}" data-msg-type="${esc(chat.chat_type)}" data-msg-pinned="${chat.pinned ? '1' : '0'}" title="${chat.pinned ? '取消置顶' : '置顶'}">
            <span class="msg-chat-avatar">${avatarHtml(av, chat.nickname || '群')}</span>
            <span class="msg-chat-main"><span class="msg-chat-top"><strong>${esc(chat.nickname || chat.chat_id)}</strong>${typeTag}<small>${esc(fmtChatTime(chat.last_time))}</small></span>
            <span class="msg-chat-sub-row"><span class="msg-chat-sub">${esc(String(chat.last_content || '（无文本内容）').replace(/<@([A-Za-z0-9_-]{5,128})>/g, (all, oid) => '@' + oid.slice(0, 6) + '…'))}</span>${unread > 0 ? `<span class="msg-chat-badge">${unread > 99 ? '99+' : unread}</span>` : ''}</span>
            <span class="msg-chat-meta">${chat.chat_type === 'group' ? `群消息 ${chat.msg_count} 条` : `私聊消息 ${chat.msg_count} 条`}${chat.remark ? ' · 已备注' : ''}</span></span>
          </button>`;
        }).join('');
        node.querySelectorAll('[data-msg-chat]').forEach((el) => {
          el.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const chatId = el.dataset.msgChat; const chatType = el.dataset.msgType; const pinned = el.dataset.msgPinned === '1';
            const items = [];
            items.push({label: pinned ? '取消置顶' : '置顶', action: async () => {
              try { const result = await api('message/pin', {method:'POST', body:JSON.stringify({chat_id:chatId, pinned:!pinned})}); toast(result.pinned ? '已置顶' : '已取消置顶'); await loadMsgChats(); }
              catch (error) { toast(error.message || '操作失败'); }
            }});
            if (chatType === 'group') items.push({label:'刷新群信息', action:() => { api('message/group-info/refresh', {method:'POST', body:JSON.stringify({chat_id:chatId})}).then(() => { toast('已刷新'); loadMsgChats(); }).catch((error) => toast(error.message || '刷新失败')); }});
            if (items.length) showMsgCtx(e.clientX, e.clientY, items);
          });
          el.addEventListener('click', () => { if (msgState.multi) exitMultiMode(); msgState.chatId = el.dataset.msgChat; msgState.chatType = el.dataset.msgType; msgState.historyData = null; clearMsgNewMessages(); loadMsgHistory(); markMsgRead(el.dataset.msgChat); });
        });
      };
      $('msg-lightbox-close')?.addEventListener('click', () => closeMsgLightbox());
      $('msg-lightbox')?.addEventListener('click', (e) => { if (e.target === $('msg-lightbox')) closeMsgLightbox(); });
      document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMsgLightbox(); });
      const loadMsgChats = async () => {
        const requestId = Number(msgState.chatListRequest || 0) + 1;
        msgState.chatListRequest = requestId;
        try {
          const data = await api('message/chats', {method:'POST', body:JSON.stringify({filter:msgState.filter, search:msgState.search, page:msgState.page, page_size:50})});
          // 搜索、实时刷新或置顶操作可能同时发起请求，只显示最后一次请求的结果。
          if (requestId !== msgState.chatListRequest) return;
          renderMsgChats(data);
        }
        catch (error) { if (requestId !== msgState.chatListRequest) return; if (error.status === 401) showAuthError(error); else $('msg-chats').innerHTML = `<div class="msg-empty">${esc(error.message)}</div>`; }
      };
      const closeMsgEvents = () => {
        if (msgState.eventReconnect) { clearTimeout(msgState.eventReconnect); msgState.eventReconnect = null; }
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
        }, 1200);
      };
      const handleMsgRealtimeData = (raw) => {
        try {
          const envelope = typeof raw === 'string' ? JSON.parse(raw || '{}') : raw;
          if (envelope?.type === 'message') { applyMsgRealtimeEvent(envelope.data || {}); scheduleMsgRealtimeRefresh(); }
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
        msgState.eventTransport = 'sse';
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
        msgState.eventTransport = 'websocket';
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
        if (!el) return;
        el.hidden = !(msgState.chatType === 'group' && msgState.botIsAdmin);
      };
      const updateMsgHead = (data) => {
        $('msg-head-name').textContent = data.chat_name || '未命名会话';
        const gInfo = data.group_info || {};
        const gNum = Number(gInfo.member_num || 0);
        $('msg-head-sub').textContent = msgState.chatType === 'group'
          ? `群聊 · ${esc(msgState.chatId)}${gNum > 0 ? ` · 群成员 ${gNum} 人` : ''}`
          : `私聊 · ${esc(msgState.chatId)}`;
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
        const ta = $('msg-textarea');
        ta.focus();
        const mention = `<@${uid}> `;
        const start = ta.selectionStart ?? ta.value.length;
        ta.value = ta.value.slice(0, start) + mention + ta.value.slice(ta.selectionEnd ?? start);
        ta.selectionStart = ta.selectionEnd = start + mention.length;
        ta.dispatchEvent(new Event('input'));
        toast(`已插入 @${nick || uid}（将以 Markdown 发送）`);
      };
      const copyMsgText = async (text) => {
        try {
          if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
          } else {
            const ta = document.createElement('textarea');
            ta.value = text;
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
          try { await api('message/recall', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, message_id:id})}); okCount++; }
          catch (error) { failCount++; }
        }
        toast(`撤回完成：成功 ${okCount} 条${failCount ? `，失败 ${failCount} 条` : ''}`);
        exitMultiMode(); loadMsgHistory();
      };
      const msgMessageKey = (message) => String(message?.message_id || message?.id || '');
      const dedupeMsgMessages = (messages) => {
        const seen = new Set();
        return (Array.isArray(messages) ? messages : []).filter((message) => {
          const key = msgMessageKey(message);
          if (!key) return true;
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });
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
        clearMsgNewMessages();
        markMsgRead();
      };
      const renderMsgMessages = (data, scroll = {}) => {
        const body = $('msg-body');
        const previousData = msgState.renderedChatId === msgState.chatId ? (msgState.historyData || {}) : {};
        data = {
          ...previousData,
          ...data,
          member_profiles:{...(previousData.member_profiles || {}), ...(data.member_profiles || {})},
          references:{...(previousData.references || {}), ...(data.references || {})},
        };
        const msgs = dedupeMsgMessages(data.messages || []);
        msgState.historyData = {...data, messages:msgs};
        window.msgAppid = data.messages?.[0]?.appid || window.msgAppid || '';
        updateMsgHead(data);
        updateMsgAdminTag();
        $('msg-refresh-info').hidden = msgState.chatType !== 'group';
        $('msg-remark').hidden = msgState.chatType !== 'group';
        if (!msgs.length) { body.innerHTML = '<div class="msg-empty">暂无消息记录</div>'; msgState.renderedChatId = msgState.chatId; clearMsgNewMessages(); return; }
        let lastDay = ''; let html = '';
        if (data.has_more) html += '<button class="msg-load-older" id="msg-load-older" type="button">加载更早消息</button>';
        msgs.forEach((m) => {
          const day = String(m.timestamp||'').slice(0,10);
          if (day !== lastDay && day) { html += `<div class="msg-day">${esc(fmtDayLabel(m.timestamp))}</div>`; lastDay = day; }
          const isSelf = Boolean(m.is_self) || ['bot_active', 'bot_send', 'web_panel'].includes(String(m.source || ''));
          const recalled = Boolean(m.recalled);
          const profiles = data.member_profiles || {};
          msgState.profiles = profiles;
          const profile = profiles[m.user_id] || {};
          const av = isSelf ? '' : avatarUrl(m.user_id, 'user', data.messages?.[0]?.appid || window.msgAppid);
          const tags = [];
          if (isSelf) {
            const botMsg = m.nickname === '机器人' || String(m.source || '').indexOf('bot') === 0;
            tags.push('<span class="msg-tag self">' + (botMsg ? '机器人' : '我') + '</span>');
          }
          if (m.source === 'web_panel') tags.push('<span class="msg-tag">网页</span>');
          if (recalled) tags.push('<span class="msg-tag recalled">已撤回</span>');
          const roleMap = {owner:'群主', admin:'管理', member:'群员'};
          const roleTag = roleMap[profile.role] || roleMap[String(m.raw_message||'').match(/member_role[^,]*?['"]([a-z]+)['"]/)?.[1] || ''];
          if (!isSelf && roleTag) tags.push(`<span class="msg-tag role">${roleTag}</span>`);
          const renderText = (text) => {
            let out = String(text || '');
            out = out.replace(/<@([A-Za-z0-9_-]{5,128})>/g, (all, oid) => {
              const nm = profiles[oid]?.nickname || '';
              return nm ? `@${nm}` : all;
            });
            return out;
          };
          const ref = (data.references || {})[m.reference_id];
          // 撤回后隐藏引用与媒体，只显示已撤回
          const quote = !recalled && m.reference_id ? (ref ? `<div class="msg-bubble-quote"><b>${esc(ref.nickname || '')}</b>：${esc(ref.content || '')}</div>` : `<div class="msg-bubble-quote">引用消息 ${esc(m.reference_id)}</div>`) : '';
          const media = !recalled && m.media ? (m.media.src ? (m.media.type === '图片' ? `<div class="msg-media"><img src="${esc(m.media.src)}" alt="图片" loading="lazy" referrerpolicy="no-referrer" data-lightbox="${esc(m.media.src)}"></div>` : `<div class="msg-media"><span class="msg-tag">[${esc(m.media.type)}]</span> <span style="word-break:break-all;font-size:11px;color:#999">${esc(m.media.src)}</span></div>`) : `<div class="msg-media"><span class="msg-media-ph" title="图片地址待回显补充">🖼️ 图片</span></div>`) : '';
          const content = recalled ? '（消息已撤回）' : renderText(m.content || '（空消息）');
          // 权限：撤回自己发的消息总是可以；撤回他人消息需要机器人为管理员；禁言需要机器人为管理员且对方非群主/管理员
          const canRecall = Boolean(m.message_id) && !recalled && (isSelf || msgState.botIsAdmin);
          const canMute = !isSelf && msgState.chatType === 'group' && Boolean(m.user_id) && msgState.botIsAdmin && profile.role !== 'owner' && profile.role !== 'admin';
          const actions = [];
          if (canRecall) actions.push(`<button class="msg-action" data-msg-recall="${esc(m.message_id)}" type="button">撤回</button>`);
          if (!isSelf && msgState.chatType === 'group' && m.user_id) actions.push(`<button class="msg-action" data-msg-quote="${esc(m.message_id)}" data-msg-user="${esc(m.user_id)}" data-msg-name="${esc(m.nickname||'')}" type="button">引用</button>`);
          if (canMute) actions.push(`<button class="msg-action" data-msg-mute="${esc(m.user_id)}" data-msg-mute-name="${esc(m.nickname||'')}" type="button">禁言</button>`);
          if (m.raw_message) actions.push(`<button class="msg-action" data-msg-raw="${msgState.chatId}_${m.id}" type="button">原始数据</button>`);
          window._msgRaw = window._msgRaw || {}; window._msgRaw[`${msgState.chatId}_${m.id}`] = m.raw_message;
          const isSelected = msgState.selected.has(m.message_id);
          const multiEnabled = canRecall;
          html += `<div class="msg-row ${isSelf ? 'self' : ''}${msgState.multi ? ' multi-mode' : ''}${isSelected ? ' selected' : ''}${multiEnabled ? '' : ' no-multi'}" data-msg-mid="${esc(m.message_id)}" data-msg-uid="${esc(m.user_id)}" data-msg-nick="${esc(m.nickname||'')}" data-msg-self="${isSelf ? '1' : ''}" data-msg-recalled="${recalled ? '1' : ''}" data-msg-content="${esc(m.content || '')}">
            <span class="msg-pos">
              <span class="msg-multi-check"></span>
              <span class="msg-avatar">${avatarHtml(av, m.nickname || '?')}</span>
            </span>
            <div class="msg-bubble-wrap"><div class="msg-bubble-name">${esc(m.nickname||'')}${tags.length ? `<span class="msg-tags">${tags.join('')}</span>` : ''}</div>
              <div class="msg-bubble ${recalled ? 'recalled' : ''}">${quote}${esc(content)}${media}</div>
              <div class="msg-meta">${esc(fmtMsgTime(m.timestamp))}${m.message_id ? ` · ${esc(m.message_id.slice(0,18))}…` : ''}</div>
              ${actions.length ? `<div class="msg-actions">${actions.join('')}</div>` : ''}
            </div></div>`;
        });
        body.innerHTML = html;
        if (scroll.prepend) {
          body.scrollTop = Math.max(0, Number(scroll.previousTop || 0) + body.scrollHeight - Number(scroll.previousHeight || 0));
        } else if (scroll.toBottom) {
          body.scrollTop = body.scrollHeight;
          clearMsgNewMessages();
        } else {
          body.scrollTop = Math.min(Number(scroll.previousTop || 0), Math.max(0, body.scrollHeight - body.clientHeight));
        }
        msgState.renderedChatId = msgState.chatId;
        body.querySelector('#msg-load-older')?.addEventListener('click', () => loadMsgHistory(true));
        body.querySelectorAll('[data-msg-recall]').forEach((el) => el.addEventListener('click', () => recallMessage(el.dataset.msgRecall)));
        body.querySelectorAll('[data-lightbox]').forEach((img) => img.addEventListener('click', () => openMsgLightbox(img.dataset.lightbox)));
        body.querySelectorAll('[data-msg-quote]').forEach((el) => el.addEventListener('click', () => { msgState.quote = {id:el.dataset.msgQuote, text:el.dataset.msgName || '引用消息'}; $('msg-quote-preview').hidden = false; $('msg-quote-text').textContent = `${el.dataset.msgName} · 引用`; }));
        body.querySelectorAll('[data-msg-mute]').forEach((el) => el.addEventListener('click', () => { msgState.mute = {member:el.dataset.msgMute, name:el.dataset.msgMuteName}; $('msg-mute-title').textContent = `禁言 ${el.dataset.msgMuteName || el.dataset.msgMute}`; $('msg-mute-modal').hidden = false; }));
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
            if (msgState.multi) {
              toggleMsgSelect(row, mid);
              return;
            }
            const profile = (msgState.profiles || {})[uid] || {};
            const canMuteRow = !isSelf && msgState.chatType === 'group' && uid && msgState.botIsAdmin && profile.role !== 'owner' && profile.role !== 'admin';
            const canRecallRow = Boolean(mid) && !recalled && (isSelf || msgState.botIsAdmin);
            const items = [];
            if (!isSelf && msgState.chatType === 'group' && uid) items.push({label:'@' + (nick || 'TA'), action:() => atMember(uid, nick)});
            if (canMuteRow) items.push({label:'禁言', action:() => { msgState.mute = {member:uid, name:nick}; $('msg-mute-title').textContent = `禁言 ${nick || uid}`; $('msg-mute-modal').hidden = false; }});
            if (items.length && !isSelf) items.push({sep:true});
            if (!isSelf && msgState.chatType === 'group' && mid) items.push({label:'引用', action:() => { msgState.quote = {id:mid, text:nick || '引用消息'}; $('msg-quote-preview').hidden = false; $('msg-quote-text').textContent = `${nick} · 引用`; }});
            if (content) items.push({label:'复制', action:() => copyMsgText(content)});
            if (canRecallRow) items.push({label:'撤回', danger:true, action:() => recallMessage(mid)});
            if (mid) items.push({sep:true});
            items.push({label:'多选', action:() => { enterMultiMode(); if (canRecallRow) toggleMsgSelect(row, mid); }});
            if (items.length) showMsgCtx(e.clientX, e.clientY, items);
          });
          row.addEventListener('click', (e) => {
            if (msgState.multi && !e.target.closest('button')) {
              const canSel = Boolean(row.dataset.msgMid) && !(row.dataset.msgRecalled === '1') && (row.dataset.msgSelf === '1' || msgState.botIsAdmin);
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
            const canMuteAv = !isSelf && msgState.chatType === 'group' && uid && msgState.botIsAdmin && profileA.role !== 'owner' && profileA.role !== 'admin';
            const items = [];
            if (!isSelf && msgState.chatType === 'group' && uid) items.push({label:'@' + (nick || 'TA'), action:() => atMember(uid, nick)});
            if (canMuteAv) items.push({label:'禁言', action:() => { msgState.mute = {member:uid, name:nick}; $('msg-mute-title').textContent = `禁言 ${nick || uid}`; $('msg-mute-modal').hidden = false; }});
            if (items.length) showMsgCtx(e.clientX, e.clientY, items);
          });
        });
      };
      const rememberMsgEvent = (chatId, message) => {
        const fallback = `${message?.ts || message?.timestamp || ''}:${message?.user_id || ''}:${message?.content || ''}`;
        const key = `${chatId}:${msgMessageKey(message) || fallback}`;
        if (msgState.eventKeys.has(key)) return false;
        msgState.eventKeys.add(key);
        msgState.eventKeyOrder.push(key);
        while (msgState.eventKeyOrder.length > 1000) msgState.eventKeys.delete(msgState.eventKeyOrder.shift());
        return true;
      };
      const applyMsgRealtimeEvent = (payload) => {
        const chatId = String(payload.chat_id || '').trim();
        const message = payload.message && typeof payload.message === 'object' ? {...payload.message} : null;
        if (!chatId || !message) return;
        const isNewEvent = rememberMsgEvent(chatId, message);
        const existing = msgState.chats.find((chat) => String(chat.chat_id || '') === chatId) || msgState.realtimeChats.get(chatId) || {};
        const chatType = String(payload.chat_type || message.chat_type || existing.chat_type || 'group');
        const eventTs = Number(payload.last_ts || message.ts || 0) || Math.floor(Date.now() / 1000);
        const isViewing = msgState.chatId === chatId && !$('page-messages')?.hidden;
        const body = $('msg-body');
        const followLatest = isViewing && msgState.pendingNewMessages === 0 && msgBodyNearBottom(body);
        const payloadUnread = Number(payload.unread);
        const unread = followLatest
          ? 0
          : (Number.isFinite(payloadUnread) ? Math.max(0, payloadUnread) : Math.max(0, Number(existing.unread || 0) + (message.is_self ? 0 : 1)));
        const overlay = {
          ...existing,
          chat_id:chatId,
          chat_type:chatType,
          appid:String(payload.appid || message.appid || existing.appid || ''),
          nickname:existing.nickname || (chatType === 'user' ? String(payload.last_nickname || message.nickname || chatId) : chatId),
          last_content:String(payload.last_content || message.content || existing.last_content || ''),
          last_time:String(message.timestamp || existing.last_time || new Date(eventTs * 1000).toISOString()),
          last_ts:eventTs,
          msg_count:Math.max(0, Number(existing.msg_count || 0) + (isNewEvent ? 1 : 0)),
          unread,
        };
        msgState.realtimeChats.set(chatId, overlay);
        renderMsgChats({chats:msgState.chats});
        if (!isViewing || !isNewEvent) return;
        const realtimeMessage = {...message, chat_type:chatType, appid:String(payload.appid || message.appid || '')};
        const messageKey = msgMessageKey(realtimeMessage);
        const alreadyRendered = msgState.messages.some((item) => messageKey && msgMessageKey(item) === messageKey);
        if (!alreadyRendered) {
          const previousTop = body?.scrollTop || 0;
          const previousHeight = body?.scrollHeight || 0;
          msgState.messages = [...msgState.messages, realtimeMessage];
          renderMsgMessages(
            {...(msgState.historyData || {}), messages:msgState.messages},
            {previousTop, previousHeight, toBottom:followLatest},
          );
          if (!followLatest) showMsgNewMessages(1);
        }
        if (followLatest) markMsgRead(chatId);
      };
      const toggleMsgSelect = (row, mid) => {
        if (!mid) return;
        if (msgState.selected.has(mid)) { msgState.selected.delete(mid); row.classList.remove('selected'); }
        else { msgState.selected.add(mid); row.classList.add('selected'); }
        $('msg-multi-count').textContent = `已选 ${msgState.selected.size} 条`;
      };
      const loadMsgHistory = async (older = false, quiet = false) => {
        if (!msgState.chatId) return;
        $('msg-composer').hidden = false;
        const requestId = Number(msgState.historyRequest || 0) + 1;
        msgState.historyRequest = requestId;
        const requestChatId = msgState.chatId;
        const requestChatType = msgState.chatType;
        const body = $('msg-body');
        const newChat = msgState.renderedChatId !== msgState.chatId;
        const previousTop = body?.scrollTop || 0;
        const previousHeight = body?.scrollHeight || 0;
        const previousLast = !newChat ? msgMessageKey(msgState.messages[msgState.messages.length - 1]) : '';
        try {
          const before = older ? (msgState.messages[0]?.timestamp || '') : '';
          const beforeId = older ? Number(msgState.messages[0]?.id || 0) : 0;
          const data = await api('message/history', {method:'POST', body:JSON.stringify({chat_id:requestChatId, chat_type:requestChatType, before_date:beforeId ? '' : before, before_id:beforeId, limit:120})});
          if (requestId !== msgState.historyRequest || requestChatId !== msgState.chatId || requestChatType !== msgState.chatType) return;
          const incoming = dedupeMsgMessages(data.messages || []);
          if (quiet && !older) {
            updateMsgHead(data);
            const newLast = msgMessageKey(incoming[incoming.length - 1]);
            if (previousLast === newLast && incoming.length === msgState.messages.length) return;
          }
          let newCount = 0;
          if (!older && previousLast) {
            const previousIndex = incoming.findIndex((message) => msgMessageKey(message) === previousLast);
            newCount = previousIndex >= 0 ? Math.max(0, incoming.length - previousIndex - 1) : (incoming.length ? 1 : 0);
          }
          const renderTop = body?.scrollTop ?? previousTop;
          const renderHeight = body?.scrollHeight ?? previousHeight;
          const renderNearBottom = newChat || msgBodyNearBottom(body);
          msgState.messages = older ? dedupeMsgMessages([...incoming, ...msgState.messages]) : incoming;
          renderMsgMessages(
            {...data, messages: msgState.messages},
            {prepend:older, previousTop:renderTop, previousHeight:renderHeight, toBottom:!older && renderNearBottom},
          );
          if (!older && !renderNearBottom && newCount > 0) showMsgNewMessages(newCount);
          loadGroupRoles(true);
        } catch (error) { if (requestId !== msgState.historyRequest) return; if (error.status === 401) showAuthError(error); else toast(error.message); }
      };
      const loadGroupRoles = async (throttled = false) => {
        if (msgState.chatType !== 'group' || !msgState.chatId) return;
        const now = Date.now();
        if (throttled && msgState.lastRolesChatId === msgState.chatId && msgState.lastRolesAt && now - msgState.lastRolesAt < 60000) return;
        msgState.lastRolesAt = now; msgState.lastRolesChatId = msgState.chatId;
        try { const data = await api('message/group-roles', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId})}); msgState.botIsAdmin = Boolean(data.bot_is_admin); updateMsgAdminTag(); }
        catch (error) { msgState.botIsAdmin = false; updateMsgAdminTag(); }
      };
      const recallMessage = async (messageId) => {
        if (!confirm('确定撤回这条消息吗？发送超过 2 分钟的消息不可撤回。')) return;
        try { await api('message/recall', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, message_id:messageId})}); toast('撤回成功'); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const refreshGroupInfo = async () => {
        if (!msgState.chatId) return;
        try { const data = await api('message/group-info/refresh', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId})}); toast(data.group_name ? `群信息已刷新：${data.group_name}${data.member_num ? `（成员 ${data.member_num} 人）` : ''}` : (data.member_num ? `群信息已刷新：成员 ${data.member_num} 人` : '群信息已刷新')); loadMsgHistory(); }
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
        try { await api('message/remarks', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, remark, group_qq:groupQQ})}); toast('备注已保存'); $('msg-remark-modal').hidden = true; loadMsgChats(); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const deleteRemark = async () => {
        if (!confirm('确定删除该会话的备注和群号吗？')) return;
        try { await api('message/remarks', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, action:'delete'})}); toast('备注已删除'); $('msg-remark-modal').hidden = true; loadMsgChats(); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const sendMessage = async () => {
        if (msgState.sending) return;
        const content = $('msg-textarea').value.trim();
        const customId = $('msg-custom-id').value.trim();
        const payload = { chat_id:msgState.chatId, chat_type:msgState.chatType, msg_type:msgState.sendType, content, send_mode:msgState.sendMode, custom_id:customId, quote_message_id:msgState.quote?.id || '' };
        if (msgState.sendType === 'media') {
          payload.media_file_type = Number($('msg-media-type')?.value || 1);
          payload.media = $('msg-media-path')?.value.trim() || '';
          payload.media_url = $('msg-media-url')?.value.trim() || '';
          const mediaText = $('msg-media-text')?.value.trim() || '';
          if (mediaText) payload.media_text = mediaText;
          if (!payload.media && !payload.media_url && !msgState.pastedImage) return toast('请填写媒体文件路径或 URL');
        }
        if (msgState.pastedImage) { payload.image_data = msgState.pastedImage; }
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
        if (!content && !msgState.pastedImage && !['media','ark','card'].includes(msgState.sendType)) return toast('请输入消息内容');
        msgState.sending = true;
        const btn = $('msg-send'); btn.disabled = true; $('msg-send-status').textContent = '发送中...';
        try { const result = await api('message/send', {method:'POST', body:JSON.stringify(payload)}); toast('发送成功'); $('msg-textarea').value = ''; msgState.quote = null; msgState.pastedImage = null; if ($('msg-img-inline')) $('msg-img-inline').hidden = true; if ($('msg-img-thumb')) $('msg-img-thumb').removeAttribute('src'); if ($('msg-quote-preview')) $('msg-quote-preview').hidden = true; loadMsgHistory(); }
        catch (error) { toast(error.message); }
        finally { btn.disabled = false; $('msg-send-status').textContent = ''; msgState.sending = false; }
      };
      const renderMsgExtra = () => {
        const extra = $('msg-extra'); const type = msgState.sendType;
        if (type === 'media') { extra.hidden = false; extra.innerHTML = `<input id="msg-media-type" type="number" min="1" max="4" value="1" title="1图片 2视频 3语音 4文件"><input id="msg-media-path" type="text" placeholder="本地文件路径（服务器）"><input id="msg-media-url" type="text" placeholder="或媒体 URL"><input type="text" placeholder="媒体说明（可选，显示在消息中）" id="msg-media-text">`; }
        else if (type === 'ark') { extra.hidden = false; extra.innerHTML = `<select id="msg-ark-template"><option value="23">23 链接列表</option><option value="24" selected>24 文本卡片</option><option value="37">37 大图卡片</option></select><input data-ark-field="#DESC#" type="text" placeholder="#DESC# 描述"><input data-ark-field="#PROMPT#" type="text" placeholder="#PROMPT# 提示"><input data-ark-field="#TITLE#" type="text" placeholder="#TITLE# 标题"><input data-ark-field="#METADESC#" type="text" placeholder="#METADESC# 元描述"><input data-ark-field="#IMG#" type="text" placeholder="#IMG# 图片URL"><input data-ark-field="#LINK#" type="text" placeholder="#LINK# 跳转链接"><input data-ark-field="#SUBTITLE#" type="text" placeholder="#SUBTITLE# 副标题"><textarea id="msg-ark-list" class="msg-textarea" style="min-height:52px" placeholder="23 模板列表：每行 描述|链接"></textarea>`; }
        else if (type === 'card') { extra.hidden = false; extra.innerHTML = `<input id="msg-card-title" type="text" placeholder="卡片标题"><input id="msg-card-desc" type="text" placeholder="卡片描述"><input id="msg-card-pic" type="text" placeholder="图片 URL"><input id="msg-card-url" type="text" placeholder="跳转 URL">`; }
        else { extra.hidden = true; extra.innerHTML = ''; }
      };
      $('msg-filter').querySelectorAll('[data-msg-filter]').forEach((el) => el.addEventListener('click', () => { $('msg-filter').querySelectorAll('[data-msg-filter]').forEach((x) => x.classList.toggle('active', x === el)); msgState.filter = el.dataset.msgFilter; msgState.page = 1; loadMsgChats(); }));
      $('msg-search-btn').addEventListener('click', () => { msgState.search = $('msg-search-input').value.trim(); msgState.page = 1; loadMsgChats(); });
      $('msg-search-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') { msgState.search = e.target.value.trim(); msgState.page = 1; loadMsgChats(); } });
      $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((el) => el.addEventListener('click', () => { $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((x) => x.classList.toggle('active', x === el)); msgState.sendType = el.dataset.msgType; renderMsgExtra(); }));
      $('msg-send-mode').addEventListener('change', (e) => { msgState.sendMode = e.target.value; $('msg-custom-id').hidden = !(msgState.sendMode === 'custom_msg_id' || msgState.sendMode === 'custom_event_id'); });
      $('msg-send').addEventListener('click', sendMessage);
      $('msg-textarea').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey && !e.isComposing && e.keyCode !== 229) {
          e.preventDefault();
          sendMessage();
        }
      });
      $('msg-textarea').addEventListener('paste', (e) => {
        const items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        for (const item of items) {
          if (item.type && item.type.indexOf('image/') === 0) {
            const file = item.getAsFile();
            if (!file) continue;
            const reader = new FileReader();
            reader.onload = () => {
              msgState.pastedImage = reader.result;
              $('msg-img-thumb').src = reader.result;
              $('msg-img-inline').hidden = false;
              toast('已粘贴图片，可继续输入文字后发送');
            };
            reader.readAsDataURL(file);
            e.preventDefault();
            return;
          }
        }
      });
      const clearMsgImage = () => { msgState.pastedImage = null; $('msg-img-inline').hidden = true; $('msg-img-thumb').removeAttribute('src'); };
      $('msg-img-clear').addEventListener('click', clearMsgImage);
      $('msg-img-pick').addEventListener('click', () => $('msg-img-file').click());
      $('msg-img-file').addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        if (!file.type.startsWith('image/')) { toast('请选择图片文件'); e.target.value = ''; return; }
        const reader = new FileReader();
        reader.onload = () => { msgState.pastedImage = reader.result; $('msg-img-thumb').src = reader.result; $('msg-img-inline').hidden = false; };
        reader.readAsDataURL(file);
        e.target.value = '';
      });
      $('msg-body').addEventListener('scroll', () => {
        if (!msgBodyNearBottom($('msg-body'))) return;
        const activeChat = msgState.chats.find((chat) => String(chat.chat_id || '') === String(msgState.chatId || ''));
        const shouldRead = msgState.pendingNewMessages > 0 || Number(activeChat?.unread || 0) > 0;
        clearMsgNewMessages();
        if (shouldRead) markMsgRead();
      });
      $('msg-new-messages').addEventListener('click', () => scrollMsgToBottom('smooth'));
      $('msg-reload').addEventListener('click', () => { loadMsgChats(); if (msgState.chatId) loadMsgHistory(); });
      $('msg-multi-recall').addEventListener('click', recallSelected);
      $('msg-multi-cancel').addEventListener('click', () => { exitMultiMode(); });
      $('msg-refresh-info').addEventListener('click', refreshGroupInfo);
      $('msg-remark').addEventListener('click', showRemarkDialog);
      $('msg-quote-clear').addEventListener('click', () => { msgState.quote = null; $('msg-quote-preview').hidden = true; });
      $('msg-raw-close').addEventListener('click', () => { $('msg-raw-modal').hidden = true; });
      $('msg-raw-modal').addEventListener('click', (e) => { if (e.target === $('msg-raw-modal')) $('msg-raw-modal').hidden = true; });
      $('msg-mute-presets').querySelectorAll('[data-mute-min]').forEach((el) => el.addEventListener('click', () => { $('msg-mute-presets').querySelectorAll('[data-mute-min]').forEach((x) => x.classList.toggle('active', x === el)); msgState.muteMinutes = Number(el.dataset.muteMin); $('msg-mute-custom').value = ''; }));
      $('msg-mute-custom').addEventListener('input', (e) => { const v = Number(e.target.value); if (v >= 1) msgState.muteMinutes = v; });
      $('msg-mute-cancel').addEventListener('click', () => { $('msg-mute-modal').hidden = true; });
      $('msg-remark-cancel').addEventListener('click', () => { $('msg-remark-modal').hidden = true; });
      $('msg-remark-save').addEventListener('click', saveRemark);
      $('msg-remark-delete').addEventListener('click', deleteRemark);
      $('msg-mute-confirm').addEventListener('click', async () => { if (!msgState.mute.member) return; try { await api('message/group-member/mute', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, member_openid:msgState.mute.member, minutes:msgState.muteMinutes})}); toast('禁言成功'); $('msg-mute-modal').hidden = true; } catch (error) { toast(error.message); } });
      msgState.timer = setInterval(() => { const active = !document.querySelector('#page-messages')?.hidden; if (active) { loadMsgChats(); if (msgState.chatId) loadMsgHistory(false, true); } }, 30000);

      setView(viewFromUrl(), false); load();
    })();
  """
