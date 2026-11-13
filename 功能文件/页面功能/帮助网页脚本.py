"""馒头控制台的浏览器交互脚本。"""

控制台脚本 = r"""
    (() => {
      const initialParams = new URLSearchParams(location.search);
      if (initialParams.has('token')) { initialParams.delete('token'); const cleanQuery = initialParams.toString(); history.replaceState({}, '', `${location.pathname}${cleanQuery ? `?${cleanQuery}` : ''}${location.hash}`); }
      const $ = (id) => document.getElementById(id);
      const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
      const themeStorageKey = 'mantou-theme';
      const readThemePreference = () => { try { return localStorage.getItem(themeStorageKey) === 'dark' ? 'dark' : 'light'; } catch (_) { return 'light'; } };
      const updateThemeMeta = (theme) => { const meta = document.querySelector('meta[name="theme-color"]'); const color = theme === 'dark' ? '#211c2e' : '#f4f1fc'; if (meta && meta.getAttribute('content') !== color) meta.setAttribute('content', color); };
      const updateThemeControl = (theme) => {
        const dark = theme === 'dark';
        const label = dark ? '切换到浅色模式' : '切换到深色模式';
        ['theme-toggle', 'msg-rail-theme'].forEach((id) => {
          const toggle = $(id);
          if (!toggle) return;
          if (toggle.getAttribute('aria-pressed') !== String(dark)) toggle.setAttribute('aria-pressed', String(dark));
          if (toggle.getAttribute('aria-label') !== label) toggle.setAttribute('aria-label', label);
          if (toggle.title !== label) toggle.title = label;
          const icon = toggle.querySelector('.theme-control-icon');
          const symbol = dark ? '☀' : '☾';
          if (icon && icon.textContent !== symbol) icon.textContent = symbol;
        });
      };
      const commitTheme = (next) => {
        const root = document.documentElement;
        if (root.dataset.theme !== next) root.dataset.theme = next;
        updateThemeMeta(next);
      };
      let requestedTheme = readThemePreference();
      let themeTransition = null;
      let themeGeneration = 0;
      let themeFrame = 0;
      const themeMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
      const clearThemeUpdate = () => {
        if (themeFrame) cancelAnimationFrame(themeFrame);
        themeFrame = 0;
        document.documentElement.classList.remove('theme-updating');
      };
      const finishThemeUpdate = () => {
        if (themeFrame) cancelAnimationFrame(themeFrame);
        if (document.hidden) { clearThemeUpdate(); return; }
        themeFrame = requestAnimationFrame(() => { themeFrame = requestAnimationFrame(clearThemeUpdate); });
      };
      const animateTheme = () => {
        if (themeTransition) return;
        const root = document.documentElement;
        if (root.dataset.theme === requestedTheme) { finishThemeUpdate(); return; }
        if (themeFrame) cancelAnimationFrame(themeFrame);
        themeFrame = 0;
        root.classList.add('theme-updating');
        if (document.hidden || themeMotion?.matches || typeof document.startViewTransition !== 'function') {
          commitTheme(requestedTheme);
          finishThemeUpdate();
          return;
        }
        const generation = ++themeGeneration;
        let transition;
        try {
          transition = document.startViewTransition(() => {
            // 快照准备期间的新点击合并到本次；旧回调不得覆盖取消后的主题。
            if (generation === themeGeneration) commitTheme(requestedTheme);
          });
        } catch (_) {
          commitTheme(requestedTheme);
          finishThemeUpdate();
          return;
        }
        themeTransition = transition;
        // 截图不可用或页面隐藏会拒绝 ready；finished 仍负责收尾。
        transition.ready.catch(() => {});
        transition.updateCallbackDone.catch(() => {});
        transition.finished.then(() => {
          if (themeTransition !== transition || generation !== themeGeneration) return;
          themeTransition = null;
          // 动画中只记最后一次意图，完成后最多衔接一次反向渐变。
          animateTheme();
        }, () => {
          if (themeTransition !== transition || generation !== themeGeneration) return;
          themeTransition = null;
          commitTheme(requestedTheme);
          finishThemeUpdate();
        });
      };
      const stopThemeUpdate = () => {
        ++themeGeneration;
        const previous = themeTransition;
        themeTransition = null;
        previous?.skipTransition();
        document.documentElement.classList.add('theme-updating');
        commitTheme(requestedTheme);
        finishThemeUpdate();
      };
      const applyTheme = (preference = readThemePreference(), persist = true) => {
        const next = preference === 'dark' ? 'dark' : 'light';
        requestedTheme = next;
        if (document.documentElement.dataset.themePreference !== next) document.documentElement.dataset.themePreference = next;
        updateThemeControl(next);
        if (persist) {
          try { if (localStorage.getItem(themeStorageKey) !== next) localStorage.setItem(themeStorageKey, next); } catch (_) {}
        }
        if (!persist) { commitTheme(next); clearThemeUpdate(); return; }
        if (document.hidden || themeMotion?.matches) { stopThemeUpdate(); return; }
        animateTheme();
      };
      document.addEventListener('visibilitychange', () => { if (document.hidden) stopThemeUpdate(); });
      window.addEventListener('pagehide', stopThemeUpdate);
      themeMotion?.addEventListener?.('change', (event) => { if (event.matches) stopThemeUpdate(); });
      applyTheme(readThemePreference(), false);
      $('theme-toggle')?.addEventListener('click', () => applyTheme(requestedTheme === 'dark' ? 'light' : 'dark'));
      const views = {
        dashboard: ['工作台总览', '查看当前机器人的业务和服务器状态'],
        bot: ['机器人与账号', '集中管理机器人身份、权限和阅读账号'],
        novels: ['小说服务', '管理找书、下载和各平台开关'],
        pans: ['网盘与分享', '选择分享网盘并管理各平台账号'],
        runtime: ['运行状态', '查看服务器、数据库和插件实时指标'],
        help: ['帮助指令', '查看机器人当前支持的聊天指令'],
         settings: ['系统设置', '查看状态并编辑数据库连接参数'],
        messages: ['消息记录', '查看群聊和私聊消息，回复、发送和撤回消息'],
      };
      let snapshot = null;
      let activeView = null;
      let consoleAppid = '';
      let consoleGeneration = 0;
      let consoleEntering = false;
      const consoleRequests = new Set();
      const botStorageKey = (key) => `${key}:${consoleAppid}`;
      const botApiUrl = (path, appid = consoleAppid) => {
        const url = new URL(`/api/${path}`, location.origin);
        if (appid) url.searchParams.set('appid', String(appid));
        return url.pathname + url.search;
      };
      let activePanTab = null;
      let activePanObject = null;
      let quarkWebScanId = '';
      let quarkWebScanTimer = null;
      let quarkWebScanGeneration = 0;
      let toastTimer = null;
      const databaseTestState = {generation:0, abort:null};
      const msgClearState = {generation:0, previewAbort:null, token:'', target:null, expiresAt:0, expiryTimer:null, previewing:false};
      const msgClearInFlight = new Set();
      const msgHistoryClearBoundaries = new Map();
      const msgModalIds = ['msg-raw-modal', 'msg-remark-modal', 'msg-mute-modal', 'msg-clear-modal'];
      const msgModalFocus = new Map();
      let msgModalOverflow = null;
      const activeMsgModal = () => msgModalIds.map($).findLast((node) => node && !node.hidden);
      const modalFocusable = (node) => [...node.querySelectorAll('button,input,select,textarea,a[href],[tabindex]')].filter((item) => !item.disabled && item.tabIndex >= 0 && item.getClientRects().length);
      const msgFocusReturnTarget = (node = document.activeElement) => node?.closest?.('#msg-head-menu-panel') ? $('msg-head-menu-toggle') : node;
      const adminPopoverHome = $('admin-popover')?.parentElement;
      const closeAdminPopover = () => {
        ['admin-chip', 'msg-rail-admin'].forEach((id) => $(id)?.setAttribute('aria-expanded', 'false'));
        if ($('admin-popover')) $('admin-popover').hidden = true;
      };
      const closeMsgHeadMenu = (restoreFocus = false) => {
        const panel = $('msg-head-menu-panel');
        if (!panel || panel.hidden) return;
        const hadFocus = panel.contains(document.activeElement);
        panel.hidden = true;
        $('msg-head-menu-toggle')?.setAttribute('aria-expanded', 'false');
        if (restoreFocus && hadFocus) $('msg-head-menu-toggle')?.focus({preventScroll:true});
      };
      const openMsgHeadMenu = (focus = '') => {
        if (activeView !== 'messages') return;
        closeAdminPopover();
        const panel = $('msg-head-menu-panel');
        if (!panel) return;
        panel.hidden = false;
        $('msg-head-menu-toggle')?.setAttribute('aria-expanded', 'true');
        const controls = modalFocusable(panel);
        if (focus) (focus === 'last' ? controls.at(-1) : controls[0])?.focus({preventScroll:true});
      };
      const setMessagesWorkspace = (enabled) => {
        const active = document.body.classList.contains('messages-workspace');
        if (active === enabled) return;
        closeMsgHeadMenu(); closeAdminPopover();
        document.body.classList.toggle('messages-workspace', enabled);
        const popover = $('admin-popover');
        if (popover && enabled) document.body.appendChild(popover);
        else if (popover && adminPopoverHome) adminPopoverHome.appendChild(popover);
      };
      const setMsgModal = (id, open, restoreFocus = true) => {
        const node = $(id);
        if (id === 'msg-clear-modal' && !open) { invalidateMsgClearPreview(); msgClearState.target = null; }
        if (!node || node.hidden === !open) return;
        if (open) {
          closeMsgHeadMenu(true); closeAdminPopover();
          msgModalFocus.set(id, msgFocusReturnTarget());
          if (!activeMsgModal()) { msgModalOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden'; }
          node.hidden = false;
          const preferred = id === 'msg-remark-modal' ? $('msg-remark-name') : modalFocusable(node)[0];
          (preferred || node).focus({preventScroll:true});
        } else {
          node.hidden = true;
          if (id === 'msg-remark-modal') groupSettingsState.remarkTarget = null;
          if (!activeMsgModal() && msgModalOverflow !== null) { document.body.style.overflow = msgModalOverflow; msgModalOverflow = null; }
          const previous = msgModalFocus.get(id); msgModalFocus.delete(id);
          if (restoreFocus && previous?.isConnected && previous.getClientRects().length) previous.focus({preventScroll:true});
        }
      };
      msgModalIds.forEach((id) => { const node = $(id); if (node) { node.tabIndex = -1; document.body.appendChild(node); } });
      document.addEventListener('keydown', (event) => {
        const node = activeMsgModal();
        if (!node) return;
        if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); setMsgModal(node.id, false); return; }
        if (event.key !== 'Tab') return;
        const nodes = modalFocusable(node), first = nodes[0], last = nodes[nodes.length - 1];
        if (!nodes.length) { event.preventDefault(); node.focus(); }
        else if (event.shiftKey && (document.activeElement === first || !node.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || !node.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
        event.stopImmediatePropagation();
      }, true);
      document.addEventListener('focusin', (event) => { const node = activeMsgModal(); if (node && !node.contains(event.target)) (modalFocusable(node)[0] || node).focus({preventScroll:true}); });
      const showNotice = (message) => { const node = $('notice'); node.textContent = message; node.classList.toggle('show', Boolean(message)); };
      const toast = (message) => {
        if (message === '机器人已切换') return;
        const node = $('toast');
        // 原生 dialog 位于浏览器顶层；提示跟随当前对话框，关闭后回到页面。
        const host = document.querySelector('dialog[open]') || document.body;
        if (node.parentElement !== host) host.appendChild(node);
        node.textContent = message; node.classList.add('show'); clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { node.classList.remove('show'); if (node.parentElement !== document.body) document.body.appendChild(node); }, 2200);
      };
      const api = async (path, options = {}) => {
        const {botAppid, scopeCleanup, ...fetchOptions} = options;
        const requestOptions = { cache:'no-store', credentials:'same-origin', ...fetchOptions };
        const url = new URL(`/api/${path}`, location.origin);
        const endpoint = url.pathname.slice('/api/'.length);
        const scoped = !['bot-profile','login','logout'].includes(endpoint);
        const requestGeneration = consoleGeneration;
        const requestAppid = String(botAppid || consoleAppid || '').trim();
        // 清理旧机器人的扫码会话也固定原 AppID，不借用切换后的账号。
        const cleanup = scopeCleanup === true && requestOptions.method === 'DELETE';
        if (scoped) {
          if (!/^\d{4,32}$/.test(requestAppid)) throw new Error('请先选择机器人');
          if ((url.searchParams.has('appid') && url.searchParams.get('appid') !== requestAppid)
            || (!cleanup && requestAppid !== consoleAppid)) throw new DOMException('机器人已切换', 'AbortError');
          url.searchParams.set('appid', requestAppid);
        }
        const scopedMessage = endpoint.startsWith('message/') && endpoint !== 'message/layout'
          && !['GET','HEAD'].includes(String(requestOptions.method || 'GET').toUpperCase());
        if (scopedMessage) {
          const form = requestOptions.body instanceof FormData;
          const payload = form ? requestOptions.body : JSON.parse(requestOptions.body || '{}');
          const read = (key) => form ? payload.get(key) : payload[key];
          const write = (key, value) => { if (form) payload.set(key, value); else payload[key] = value; };
          const appid = String(read('appid') || requestAppid).trim();
          if (appid !== requestAppid) throw new DOMException('机器人已切换', 'AbortError');
          write('appid', appid);
          if (read('chat_id') && !read('chat_type')) {
            const chat = msgState.chats.find((item) => item.chat_id === String(read('chat_id')) && item.appid === appid);
            write('chat_type', path.startsWith('message/group') ? 'group' : (String(read('chat_id')) === msgState.chatId ? msgState.chatType : chat?.chat_type || 'group'));
          }
          requestOptions.body = form ? payload : JSON.stringify(payload);
        }
        const requestHeaders = {...(options.headers || {})};
        if (!(requestOptions.body instanceof FormData) && !Object.keys(requestHeaders).some((key) => key.toLowerCase() === 'content-type')) requestHeaders['Content-Type'] = 'application/json';
        requestOptions.headers = requestHeaders;
        const controller = scoped && !cleanup ? new AbortController() : null;
        const cancel = () => controller?.abort();
        if (controller) {
          if (fetchOptions.signal?.aborted) controller.abort();
          else fetchOptions.signal?.addEventListener('abort', cancel, {once:true});
          requestOptions.signal = controller.signal;
          consoleRequests.add(controller);
        }
        try {
          const response = await fetch(url.pathname + url.search, requestOptions);
          const data = await response.json().catch(() => ({ok:false,error:'服务器返回格式错误'}));
          if (scoped && !cleanup && (requestGeneration !== consoleGeneration || requestAppid !== consoleAppid)) throw new DOMException('机器人已切换', 'AbortError');
          if (scoped && data.appid && String(data.appid) !== requestAppid) throw new Error('机器人资料不匹配，请重新进入');
          if (!response.ok || !data.ok) { const error = new Error(data.message || data.error || '请求失败'); error.status = response.status; error.data = data; throw error; }
          return data;
        } catch (error) {
          if (scoped && !cleanup && (requestGeneration !== consoleGeneration || requestAppid !== consoleAppid)) throw new DOMException('机器人已切换', 'AbortError');
          throw error;
        } finally {
          if (controller) consoleRequests.delete(controller);
          fetchOptions.signal?.removeEventListener('abort', cancel);
        }
      };
      const stopQuarkWebScan = async () => {
        const appid = consoleAppid;
        const scopeGeneration = consoleGeneration;
        const scanId = quarkWebScanId;
        quarkWebScanId = '';
        quarkWebScanGeneration += 1;
        clearTimeout(quarkWebScanTimer);
        quarkWebScanTimer = null;
        if (appid) {
          const path = `pan-accounts/${encodeURIComponent('夸克')}/scan${scanId ? '/' + encodeURIComponent(scanId) : ''}`;
          try { await api(path, {method:'DELETE', botAppid:appid, scopeCleanup:true}); } catch (_) {}
        }
        if (scopeGeneration !== consoleGeneration) return;
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
        if (!consoleAppid) return;
        const path = `pan-accounts/${encodeURIComponent('夸克')}/scan${quarkWebScanId ? '/' + encodeURIComponent(quarkWebScanId) : ''}`;
        fetch(botApiUrl(path), {method:'DELETE', credentials:'same-origin', keepalive:true}).catch(() => {});
      });
      const viewFromUrl = () => { const current = new URLSearchParams(location.search).get('view'); return views[current] ? current : 'dashboard'; };
      const setView = (view, push = true, resetScroll = (view !== activeView)) => {
        if (!consoleAppid) return;
        const next = views[view] ? view : 'dashboard';
        if (groupSettingsState.mutating && next !== activeView) return toast('正在更新本群设置，请稍候');
        if (next !== 'messages' && activeView === 'messages') { hideMsgCtx(); groupSettingsState.remarkTarget = null; msgModalIds.forEach((id) => setMsgModal(id, false, false)); closeMsgLightbox(); closeComposerMentionPicker(); closeGroupSettings(); stopMsgGroupSnapshots(); }
        const previousView = activeView;
        if (next !== previousView) { closeMsgHeadMenu(); clearSavedCredential(); }
        setMessagesWorkspace(next === 'messages');
        if (previousView === 'pans' && next !== 'pans') void stopQuarkWebScan();
        if (previousView === 'bot' && next !== 'bot') { leaveQQReader(); leaveJinjiang(); stopZLibraryAccount(); }
        activeView = next;
        if (next === 'bot') { void loadZLibraryAccount(); syncJinjiangTab(); }
        if (push) { const nextParams = new URLSearchParams(location.search); nextParams.set('view', next); nextParams.set('appid', consoleAppid); history.pushState({view:next,appid:consoleAppid}, '', `${location.pathname}?${nextParams.toString()}`); }
        const meta = views[next];
        $('page-title').textContent = meta[0]; $('page-subtitle').textContent = meta[1];
        document.querySelectorAll('[data-page]').forEach((node) => { node.hidden = node.dataset.page !== next; });
        document.querySelectorAll('.studio-nav [data-view]').forEach((node) => { const active = node.dataset.view === next; node.classList.toggle('active', active); node.setAttribute('aria-current', active ? 'page' : 'false'); });
        $('page-eyebrow').textContent = `${window.msgBotProfile?.username || '机器人'} / ${next === 'dashboard' ? '管理台' : '功能页面'}`;
        if (next !== 'messages' && previousView === 'messages') setMsgMobileChatOpen(false);
        if (next === 'messages') {
          connectMsgEvents();
          if (previousView !== 'messages') {
            // 离开消息页期间可能错过另一浏览器的清理广播；重新进入时使用新的服务端快照。
            msgState.historyCache.clear(); msgState.realtimeChats.clear();
            msgState.chatListTopPending = true;
            const chatList = $('msg-chats');
            if (chatList) chatList.scrollTop = 0;
            loadMsgChats();
          }
          if (previousView !== 'messages' && msgState.chatId) loadMsgHistory(false, false, true);
        }
        else if (msgState.eventSource || msgState.eventSocket || msgState.eventReconnect) closeMsgEvents();
        syncMsgNewMessagesDisplay();
        if (resetScroll) {
          const scrollContainer = document.querySelector('.main');
          if (scrollContainer) scrollContainer.scrollTop = 0;
          window.scrollTo({top:0, behavior:'auto'});
        }
        if (next === 'pans') void refreshQuarkProfilesSilently();
        if (next === 'bot' && previousView !== 'bot' && qqReader.auth) void loadQQReaderAccounts().catch((error) => { if (error.status === 401) showAuthError(error); });
      };
      const switchHtml = (key, enabled, editable, label) => `<button class="switch ${enabled ? 'on' : ''}" data-switch="${esc(key)}" data-enabled="${enabled}" ${editable ? '' : 'disabled'} aria-label="${esc(label)}" aria-pressed="${enabled}"><span></span></button>`;
      const platformGlyph = (name) => ({'番茄':'番','七猫':'猫','书旗':'旗','追书':'追','QQ阅读':'阅','QQ浏览器':'浏','得间':'得','点众':'众','盐言':'盐','塔读':'塔','百度':'度','小米':'米','晋江':'晋','话本':'话','疯狂追书':'疯','梧桐':'梧','宜搜':'搜','米读':'读','猫眼':'眼','酷我':'酷','酷匠':'匠','连城':'城','菠萝包':'菠'}[name] || String(name || '书').slice(0, 1));
      const categoryOrder = ['basic_settings', 'help_web_settings'];
      const safeFieldValue = (field) => {
        if (field.kind === 'admin_list') return Array.isArray(field.value) ? field.value.join('\n') : '';
        if (field.kind === 'boolean') return Boolean(field.value);
        return field.secret ? '' : String(field.value ?? '');
      };
      let savedCredentialView = null;
      let readerApiKeyGeneration = 0;

      const updateCredentialToggle = (button, visible) => {
        button.textContent = visible ? '隐藏' : '显示';
        button.setAttribute('aria-label', (visible ? '隐藏' : '显示') + button.dataset.configSecretLabel);
        button.setAttribute('aria-pressed', String(visible));
      };

      const updatePasswordToggle = (button, input, saved) => {
        button.disabled = !saved && (input.disabled || !input.value);
        updateCredentialToggle(button, input.type === 'text' || Boolean(saved && !saved.hidden));
      };

      const clearSavedCredential = () => {
        ++readerApiKeyGeneration;
        document.querySelectorAll('[data-api-key-created]').forEach((input) => { input.value = ''; });
        document.querySelectorAll('[data-api-key-result]').forEach((node) => { node.hidden = true; });
        if (!savedCredentialView) return;
        const {input, request, placeholder, reset} = savedCredentialView;
        savedCredentialView = null;
        request.abort();
        input.value = '';
        input.placeholder = placeholder;
        reset();
      };

      const showSavedCredential = async (button, input, payload, reset) => {
        const request = new AbortController();
        const current = {button, input, request, placeholder:input.placeholder, reset};
        savedCredentialView = current;
        input.placeholder = '正在读取…';
        updateCredentialToggle(button, true);
        try {
          const body = JSON.stringify(payload);
          const data = await api('config/saved-password', {method:'POST', body, signal:request.signal});
          if (savedCredentialView !== current) return;
          if (typeof data.value !== 'string' || !data.value) throw new Error('没有已保存的值');
          input.value = data.value;
          input.placeholder = '';
        } catch (error) {
          if (savedCredentialView !== current) return;
          clearSavedCredential();
          if (error.status === 401) showAuthError(error);
          else if (error.name !== 'AbortError') toast(error.message || '无法查看已保存的值，请重试');
        }
      };
      const toggleConfigPassword = (button, input, saved) => {
        const wasOpen = savedCredentialView?.button === button;
        clearSavedCredential();
        if (wasOpen) return;
        if (input.value && !input.disabled) {
          input.type = input.type === 'text' ? 'password' : 'text';
          updatePasswordToggle(button, input, saved);
          return;
        }
        if (!saved) return;
        input.type = 'password';
        input.hidden = true;
        saved.hidden = false;
        void showSavedCredential(button, saved, {field:input.dataset.configField}, () => {
          saved.hidden = true;
          input.hidden = false;
          updatePasswordToggle(button, input, saved);
        });
      };
      document.addEventListener('visibilitychange', () => { if (document.hidden) clearSavedCredential(); });
      window.addEventListener('pagehide', clearSavedCredential);
      const botTabs = document.querySelector('.studio-bot-tabs');
      botTabs?.addEventListener('click', clearSavedCredential);
      botTabs?.addEventListener('keydown', (event) => {
        if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) clearSavedCredential();
      });

      const renderConfigEditor = (targetId, fields, editable, filter) => {
        const node = $(targetId);
        if (!node) return;
        if (savedCredentialView && node.contains(savedCredentialView.input)) clearSavedCredential();
        const selected = (fields || []).filter((field) => {
          if (filter && !filter(field)) return false;
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
          const label = esc(field.label || field.key) + (field.scope ? `<span class="config-scope-label">${field.scope === 'shared' ? '服务共用' : '当前机器人'}</span>` : '');
          const hint = field.secret ? (field.configured ? '已配置，留空表示不修改' : (field.hint || '敏感值只写入，不在页面回显')) : String(field.hint || '');
          if (field.kind === 'api_keys') {
            const keys = Array.isArray(field.keys) ? field.keys : [];
            return `<div class="config-field full" data-api-key-manager><label for="${inputId}">${label}</label><small>已配置 ${keys.length} 个 Key；请求只需 Bearer Key，无需 AppID。</small><div class="config-actions"><button class="outline-button" type="button" data-api-key-generate ${editable ? '' : 'disabled'}>随机生成并添加</button>${keys.map((item) => `<button class="outline-button" type="button" data-api-key-delete="${esc(item.id)}" ${editable ? '' : 'disabled'}>撤销 ${esc(item.id)}</button>`).join('')}</div><div data-api-key-result hidden role="status" aria-live="polite"><small>仅本次显示，请复制保存：</small><div class="config-input-wrap"><input type="text" data-api-key-created readonly autocomplete="off" aria-label="本次新生成的 API Key"><button type="button" class="outline-button" data-api-key-copy>复制</button></div></div><textarea id="${inputId}" data-config-field="${esc(field.key)}" data-config-secret autocomplete="off" ${editable ? '' : 'disabled'} placeholder="可选：每行一个 Key；保存时替换全部，留空不修改"></textarea><small>${esc(field.hint || '')}</small><span class="config-message" data-api-key-message></span></div>`;
          }
          if (field.kind === 'admin_list') return `<div class="config-field full"><label for="${inputId}">${label}</label><textarea id="${inputId}" data-config-field="${esc(field.key)}" ${editable ? '' : 'disabled'} placeholder="每行一个 QQ 号">${esc(safeFieldValue(field))}</textarea><small>${hint || '共 ' + esc(field.count || 0) + ' 个管理员'}</small></div>`;
          if (field.kind === 'boolean') return `<div class="config-field"><label for="${inputId}">${label}</label><select id="${inputId}" data-config-field="${esc(field.key)}" ${editable ? '' : 'disabled'}><option value="false" ${field.value ? '' : 'selected'}>关闭</option><option value="true" ${field.value ? 'selected' : ''}>开启</option></select><small>${esc(hint)}</small></div>`;
          if (field.kind === 'select') {
            const rawOptions = field.options || field.choices || [];
            const options = Array.isArray(rawOptions) ? rawOptions : Object.entries(rawOptions).map(([value, label]) => ({value, label}));
            return `<div class="config-field"><label for="${inputId}">${label}</label><select id="${inputId}" data-config-field="${esc(field.key)}" ${editable ? '' : 'disabled'}>${options.map((option) => { const value = typeof option === 'object' && option !== null ? option.value : option; const text = typeof option === 'object' && option !== null ? option.label ?? value : option; return `<option value="${esc(value)}" ${String(value) === String(field.value ?? '') ? 'selected' : ''}>${esc(text)}</option>`; }).join('')}</select><small>${hint}</small></div>`;
          }
          const type = field.secret ? 'password' : (field.kind === 'number' ? 'number' : 'text');
          const placeholder = field.placeholder || (field.secret && field.configured ? '已配置，输入新密码可替换' : (field.secret ? '留空不修改' : ''));
          const revealableField = ['help_web_admin_password', 'database_password', 'zlibrary_mail_api_key'].includes(field.key);
          const fieldLabel = esc(field.label || field.key);
          const secretAttr = field.secret ? ' data-config-secret autocomplete="new-password"' : '';
          const input = `<input id="${inputId}" type="${type}" data-config-field="${esc(field.key)}"${secretAttr} ${editable ? '' : 'disabled'} value="${esc(safeFieldValue(field))}" placeholder="${esc(placeholder)}">`;
          const savedValueId = `saved-${inputId}`;
          const canReveal = revealableField && field.configured;
          // 已保存的值仅使用同位置的只读输入，不参与配置提交或连接测试。
          const savedValue = canReveal ? `<input id="${savedValueId}" class="config-saved-value" type="text" readonly hidden autocomplete="off" aria-label="${fieldLabel}（已保存）">` : '';
          const controls = canReveal ? `${inputId} ${savedValueId}` : inputId;
          const toggle = revealableField ? `<button class="config-secret-toggle" type="button" data-config-secret-toggle="${inputId}" data-config-secret-label="${fieldLabel}" ${canReveal ? '' : 'disabled'} aria-controls="${controls}" aria-label="显示${fieldLabel}" aria-pressed="false">显示</button>` : '';
          return `<div class="config-field"><label for="${inputId}">${label}</label><div class="config-input-wrap">${input}${savedValue}${toggle}</div><small>${hint}</small></div>`;
        }).join('')}</div></section>`).join('') + `<div class="config-actions"><button class="primary-button" type="button" data-config-save ${editable ? '' : 'disabled'}>保存配置</button>${targetId === 'database-config-editor' ? `<button class="outline-button" type="button" data-database-test ${editable ? '' : 'disabled'}>测试当前连接</button>` : ''}<span class="config-message" data-config-message></span></div>${targetId === 'database-config-editor' ? '<div class="database-test-result" data-database-test-result role="status" aria-live="polite" hidden></div>' : ''}`;
        if (targetId === 'database-config-editor') 整理数据库连接表单(node);
        node.querySelectorAll('[data-api-key-generate], [data-api-key-delete]').forEach((button) => {
          button.addEventListener('click', () => manageReaderApiKey(node, button));
        });
        node.querySelectorAll('[data-api-key-copy]').forEach((button) => button.addEventListener('click', async () => {
          const input = button.closest('[data-api-key-result]')?.querySelector('[data-api-key-created]');
          if (!input?.value) return;
          try { await navigator.clipboard.writeText(input.value); toast('Key 已复制'); }
          catch (_) { input.focus(); input.select(); toast('请手动复制选中的 Key'); }
        }));
        node.querySelector('[data-config-save]')?.addEventListener('click', () => saveConfig(node));
        if (targetId === 'database-config-editor') {
          databaseTestState.generation += 1; databaseTestState.abort?.abort(); databaseTestState.abort = null;
          node.querySelector('[data-database-test]')?.addEventListener('click', () => testDatabaseConnection(node));
          node.querySelectorAll('[data-config-field]').forEach((input) => input.addEventListener('input', () => {
            databaseTestState.generation += 1; databaseTestState.abort?.abort(); databaseTestState.abort = null;
            const button = node.querySelector('[data-database-test]'); if (button) { button.disabled = !editable; button.textContent = '测试当前连接'; }
            const result = node.querySelector('[data-database-test-result]'); if (result) { result.hidden = false; result.className = 'database-test-result'; result.textContent = '当前表单已更改，尚未测试；上方连接状态对应已保存的配置。'; }
          }));
        }
        node.querySelectorAll('[data-config-secret-toggle]').forEach((button) => {
          const input = $(button.dataset.configSecretToggle);
          const saved = $(`saved-${input.id}`);
          input.addEventListener('input', () => {
            if (!input.value) input.type = 'password';
            updatePasswordToggle(button, input, saved);
          });
          button.addEventListener('click', () => void toggleConfigPassword(button, input, saved));
          updatePasswordToggle(button, input, saved);
        });
      };
       const manageReaderApiKey = async (editor, button) => {
        const manager = button.closest('[data-api-key-manager]');
        if (!manager || button.disabled) return;
        const scopeGeneration = consoleGeneration, appid = consoleAppid, keyGeneration = readerApiKeyGeneration;
        const isCurrent = () => scopeGeneration === consoleGeneration && appid === consoleAppid && keyGeneration === readerApiKeyGeneration && manager.isConnected;
        const message = manager.querySelector('[data-api-key-message]');
        const buttons = [...manager.querySelectorAll('[data-api-key-generate], [data-api-key-delete]')];
        buttons.forEach((item) => { item.disabled = true; });
        const action = button.hasAttribute('data-api-key-generate') ? 'generate' : 'delete';
        // 新操作开始时清空上一次仅显示的密钥，不将其写入存储或通知。
        const resultNode = manager.querySelector('[data-api-key-result]');
        const created = manager.querySelector('[data-api-key-created]');
        created.value = ''; resultNode.hidden = true;
        try {
          const result = await api('qq-reader-api/keys', {method:'POST', body:JSON.stringify({action, ...(action === 'delete' ? {id:button.dataset.apiKeyDelete} : {})})});
          if (!isCurrent()) return;
          if (action === 'delete') { await load(); toast('Key 已撤销'); return; }
          created.value = String(result.key || ''); resultNode.hidden = !created.value;
          message.textContent = result.message || 'Key 已添加'; message.className = 'config-message ok';
          // 只更新当前 Key 管理区的摘要，避免刷新配置丢掉仅显示一次的新 Key。
          const summary = manager.querySelector('small');
          summary.textContent = `已配置 ${(result.keys || []).length} 个 Key；请求只需 Bearer Key，无需 AppID。`;
          const actions = button.closest('.config-actions');
          actions.querySelectorAll('[data-api-key-delete]').forEach((item) => item.remove());
          (result.keys || []).forEach((item) => {
            const revoke = document.createElement('button'); revoke.type = 'button'; revoke.className = 'outline-button';
            revoke.dataset.apiKeyDelete = item.id; revoke.textContent = `撤销 ${item.id}`;
            revoke.addEventListener('click', () => manageReaderApiKey(editor, revoke)); actions.appendChild(revoke);
          });
          created.focus(); created.select();
        } catch (error) {
          if (!isCurrent()) return;
          if (error.status === 401) showAuthError(error);
          message.textContent = '密钥操作未完成，请刷新摘要后再试'; message.className = 'config-message error';
        } finally {
          if (manager.isConnected) manager.querySelectorAll('[data-api-key-generate], [data-api-key-delete]').forEach((item) => { item.disabled = false; });
        }
      };
      const renderDatabaseStatus = (database = {}) => {
        const status = String(database.status || '--');
        const statusNode = $('settings-db-status');
        if (statusNode) { statusNode.textContent = status; statusNode.classList.toggle('good', status === '正常'); }
      };
      const collectConfigFields = (editor) => {
        const fields = {};
        editor.querySelectorAll('[data-config-field]').forEach((input) => {
          const value = input.type === 'checkbox' ? input.checked : input.value;
          if (input.hasAttribute('data-config-secret') && (input.hidden || !value.trim())) return;
           if (input.dataset.configField === 'group_file_cleanup_admin_qq') {
             fields[input.dataset.configField] = value.split(/[\s,，]+/).filter(Boolean);
          } else fields[input.dataset.configField] = value;
        });
        return fields;
      };
      const testDatabaseConnection = async (editor) => {
        const button = editor.querySelector('[data-database-test]');
        const output = editor.querySelector('[data-database-test-result]');
        if (!button || !output || button.disabled || !consoleAppid) return;
        const appid = consoleAppid, scopeGeneration = consoleGeneration;
        const generation = ++databaseTestState.generation;
        databaseTestState.abort?.abort();
        const controller = new AbortController(); databaseTestState.abort = controller;
        button.disabled = true; button.textContent = '测试中…';
        output.hidden = false; output.className = 'database-test-result'; output.textContent = '正在测试当前填写的连接参数…';
        const isCurrent = () => generation === databaseTestState.generation && scopeGeneration === consoleGeneration && appid === consoleAppid && button.isConnected;
        try {
          const result = await api('database/test', {method:'POST', body:JSON.stringify({fields:collectConfigFields(editor), appid}), signal:controller.signal});
          if (!isCurrent()) return;
          const connected = result.connected === true;
          const details = [String(result.message || (connected ? '数据库连接成功。' : '数据库连接失败，请检查连接参数。')), '本次测试使用当前表单，未保存配置。'];
          if (connected && /^\d+(?:\.\d+){1,3}(?:[-.][A-Za-z0-9_.-]{1,64})?$/.test(String(result.version || ''))) details.push(`MySQL 版本：${result.version}`);
          if (!connected && Number.isInteger(result.mysql_code)) details.push(`MySQL 错误码：${result.mysql_code}`);
          output.className = `database-test-result ${connected ? 'ok' : 'error'}`; output.textContent = details.join(String.fromCharCode(10));
        } catch (error) {
          if (!isCurrent() || error.name === 'AbortError') return;
          output.className = 'database-test-result error'; output.textContent = '连接测试请求未完成，请稍后重试。';
          if (error.status === 401) showAuthError(error);
        } finally {
          if (isCurrent()) { button.disabled = false; button.textContent = '测试当前连接'; databaseTestState.abort = null; }
        }
      };
       const saveConfig = async (editor) => {
        const fields = collectConfigFields(editor);
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
           const cookieInputId = `pan-saved-cookie-${esc(item.key)}`;
           const cookieLabel = `${esc(item.name)} Cookie`;
           const cookieField = account.credential_ref ? `
             <section class="pan-detail-section config-field">
               <label for="${cookieInputId}">${cookieLabel}</label>
               <div class="config-input-wrap">
                 <input id="${cookieInputId}" data-pan-saved-cookie type="password" readonly autocomplete="off" spellcheck="false" placeholder="已保存 Cookie">
                 <button class="config-secret-toggle" type="button" data-pan-cookie-toggle data-index="${esc(index)}" data-credential-ref="${esc(account.credential_ref)}" data-config-secret-label="${cookieLabel}" aria-label="显示${cookieLabel}" aria-controls="${cookieInputId}" aria-pressed="false">显示</button>
               </div>
             </section>` : '';
           return `<div class="pan-object-account-detail">${avatar}<div class="pan-object-account-copy"><span class="pan-section-kicker">账号信息</span><h3>${esc(profileName)}</h3>${accountMetadata}</div><span class="tag ${enabled ? 'ok' : 'off'}">${enabled ? '运行中' : '已停用'}</span></div><div class="pan-object-detail-actions"><span>账号状态</span><button class="switch pan-account-switch ${enabled ? 'on' : ''}" type="button" data-pan-account-enable="${esc(item.key)}" data-index="${esc(index)}" data-enabled="${enabled}" ${pansEditable ? '' : 'disabled'} aria-label="${enabled ? '停用' : '启用'}${esc(item.name)}账号${esc(index)}" aria-pressed="${enabled}"><span></span></button>${isDefault ? '<span class="tag ok pan-account-default-tag">默认账号</span>' : enabled ? `<button class="pan-account-default" type="button" data-pan-account-default="${esc(item.key)}" data-index="${esc(index)}" ${pansEditable ? '' : 'disabled'}>设为默认</button>` : ''}<button class="pan-account-delete" type="button" data-pan-delete="${esc(item.key)}" data-index="${esc(index)}" ${pansEditable ? '' : 'disabled'}>删除账号</button></div>${cookieField}<section class="pan-detail-section"><div class="pan-detail-section-head"><div><span class="pan-section-kicker">上传</span><h3>上传目录</h3></div></div><div class="pan-directory"><input id="pan-dir-${esc(item.key)}" type="text" data-pan-dir="${esc(item.key)}" data-pan-dir-field="${esc(directoryField)}" value="${esc(item.directory || '')}" placeholder="/小说机器人" ${configEditable ? '' : 'disabled'} aria-label="${esc(item.name)}上传目录"><button class="outline-button" type="button" data-pan-dir-save="${esc(item.key)}" ${configEditable ? '' : 'disabled'}>保存目录</button></div></section>`;
         }
         if (type === 'add') {
           const isQuark = item.key === '夸克';
           return `<div class="pan-object-form">${isQuark ? `<div class="pan-add-method" role="group" aria-label="选择夸克账号添加方式"><button type="button" data-quark-mode="cookie" aria-pressed="true">Cookie</button><button type="button" data-quark-mode="scan" aria-pressed="false">扫码</button></div>` : ''}<section data-quark-cookie-panel><label class="pan-field-label" for="pan-cookie-${esc(item.key)}">${esc(item.name)} Cookie</label><div class="account-add pan-account-add"><input id="pan-cookie-${esc(item.key)}" type="password" data-pan-cookie="${esc(item.key)}" placeholder="粘贴 Cookie" autocomplete="off" ${pansEditable ? '' : 'disabled'} aria-label="添加${esc(item.name)}账号 Cookie"><button class="outline-button" type="button" data-pan-add="${esc(item.key)}" ${pansEditable ? '' : 'disabled'}>添加账号</button></div><p class="pan-security-note">保存后可在对应账号详情查看。</p></section>${isQuark ? `<section class="pan-quark-scan" data-quark-scan-panel hidden><p class="pan-security-note">使用夸克 App 扫描网页二维码，确认后自动保存账号。</p><button class="outline-button" type="button" data-quark-scan-start ${pansEditable ? '' : 'disabled'}>获取二维码</button><img class="pan-quark-scan-image" data-quark-scan-image alt="夸克登录二维码" hidden><p class="pan-quark-scan-status" data-quark-scan-status aria-live="polite">获取二维码后使用夸克 App 扫描。</p><button class="pan-account-delete" type="button" data-quark-scan-cancel hidden>取消扫码</button></section>` : ''}</div>`;
         }
         return '';
       };
       const panObjectTitle = (type) => type === 'account' ? '账号设置' : '添加账号';
       const bindPanObjectControls = (platform) => {
         const card = document.querySelector(`[data-pan-card="${CSS.escape(platform)}"]`);
         const pane = card?.querySelector('[data-pan-object-pane]');
         if (!pane) return;
         pane.querySelector('[data-pan-cookie-toggle]')?.addEventListener('click', (event) => {
           const button = event.currentTarget;
           const wasOpen = savedCredentialView?.button === button;
           clearSavedCredential();
           if (wasOpen) return;
           const input = pane.querySelector('[data-pan-saved-cookie]');
           const payload = {field:'pan_cookie', platform, index:Number(button.dataset.index), credential_ref:button.dataset.credentialRef};
           input.type = 'text';
           void showSavedCredential(button, input, payload, () => {
             input.type = 'password';
             updateCredentialToggle(button, false);
           });
         });
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
         if (pane.contains(savedCredentialView?.input)) clearSavedCredential();
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
         if (savedCredentialView?.input.matches('[data-pan-saved-cookie]')) clearSavedCredential();
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
         try { if (selected) sessionStorage.setItem(botStorageKey('mantou-pan-tab'), selected); } catch (_) {}
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
           if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (current + 1) % tabs.length;
           else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (current - 1 + tabs.length) % tabs.length;
           else if (event.key === 'Home') next = 0;
           else if (event.key === 'End') next = tabs.length - 1;
           else return;
           event.preventDefault();
           tabs[next]?.focus();
           choosePanTab(tabs[next]?.dataset.panTab);
         });
       });
      const render = (data) => {
        if (!consoleAppid || (data.appid && String(data.appid) !== consoleAppid)) return;
        snapshot = data;
        const auth = data.auth || {}; const novels = data.novels || {}; const pans = data.pans || {}; const server = data.server || {}; const database = data.database || {};
        const adminName = String(auth.username || '管理员');
        if ($('admin-name')) $('admin-name').textContent = adminName;
        if ($('admin-popover-name')) $('admin-popover-name').textContent = adminName;
        if ($('admin-avatar')) $('admin-avatar').textContent = adminName.slice(0, 1) || '管';
        if ($('admin-popover-role')) $('admin-popover-role').textContent = `${auth.role || '控制台管理员'} · 当前会话`;
        if ($('admin-popover-scope')) $('admin-popover-scope').textContent = `插件管理员白名单：${Number(auth.admin_count || 0)} 个`;
        $('metric-global').textContent = novels.global_enabled ? '已开启' : '已关闭'; $('metric-global-meta').textContent = novels.test_mode ? '测试模式已开启' : '测试模式未开启';
        const panItems = Array.isArray(pans.items) ? pans.items : [];
        const availablePans = panItems.filter((item) => item.enabled === true
          && Array.isArray(item.account_summary) && item.account_summary.some((account) => account.enabled === true));
        const availablePanNames = availablePans.map((item) => item.key).join('、') || '暂无可用网盘';
        const preferredPan = availablePans.find((item) => item.key === pans.active);
        $('metric-pan').textContent = availablePanNames;
        $('metric-pan-meta').textContent = preferredPan
          ? `主分享偏好：${preferredPan.key}`
          : (availablePans.length ? '已开启且有启用账号' : '开启网盘并启用账号后可用');
        $('runtime-pan').textContent = availablePanNames;
        $('runtime-pan-preference-row').hidden = !preferredPan;
        $('runtime-pan-preference').textContent = preferredPan?.key || '';
        $('metric-db').textContent = database.status || '--'; $('metric-db-meta').textContent = database.configured ? '已配置数据库' : '未配置数据库'; $('metric-version').textContent = `v${data.version || '--'}`;
        $('console-version').textContent = data.version ? `v${data.version}` : '';
        $('console-version').hidden = !data.version; $('metric-version-meta').textContent = '当前加载版本';
        $('dashboard-cpu').textContent = server.cpu || '--'; $('dashboard-memory').textContent = server.memory || '--'; $('dashboard-runtime').textContent = server.runtime || '--';
        [['global-switch', '__global__', novels.global_enabled, '切换本机器人的小说功能'], ['test-switch', '__test__', novels.test_mode, '切换管理员测试模式']].forEach(([id, key, enabled, label]) => { const node = $(id); node.className = `switch ${enabled ? 'on' : ''}`; node.dataset.switch = key; node.dataset.enabled = String(Boolean(enabled)); node.disabled = !novels.editable; node.setAttribute('aria-label', label); node.setAttribute('aria-pressed', String(Boolean(enabled))); });
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
        panItems.forEach((item) => {
          const accounts = Array.isArray(item.account_summary) ? item.account_summary : [];
          const enabled = accounts.filter((account) => account?.enabled !== false).length;
          const meta = document.querySelector(`[data-pan-tab-meta="${CSS.escape(item.key)}"]`);
          if (meta) meta.textContent = `${accounts.length} 个账号 · ${enabled} 启用`;
        });
        const panGrid = $('pan-grid');
        if (panGrid?.contains(savedCredentialView?.input)) clearSavedCredential();
        if (panGrid) panGrid.innerHTML = panItems.map((item) => renderPanCard(item, pans.editable, pans.config_editable)).join('') || '<div class="empty">没有网盘数据</div>';
        bindPanWorkspaceControls();
        let savedPanTab = activePanTab;
        if (!savedPanTab) { try { savedPanTab = sessionStorage.getItem(botStorageKey('mantou-pan-tab')); } catch (_) {} }
        applyPanTab(savedPanTab || panItems.find((item) => item.active)?.key || panItems[0]?.key || '');
        if (activePanObject) showPanObject(false);
        $('runtime-cpu').textContent = server.cpu || '--'; $('runtime-memory').textContent = server.memory || '--'; $('runtime-disk').textContent = server.disk || '--'; $('runtime-runtime').textContent = server.runtime || '--'; $('runtime-os').textContent = server.os || '--'; $('runtime-db').textContent = database.status || '--'; $('runtime-version').textContent = `v${data.version || '--'}`;
        const configList = $('config-list'); if (configList) configList.innerHTML = `<div class="config-item"><span>监听地址</span><strong>${esc(server.listen || '--')}</strong></div><div class="config-item"><span>访问地址</span><strong title="${esc(server.address)}">${esc(server.address || '--')}</strong></div><div class="config-item"><span>域名模式</span><strong>${data.config && data.config.custom_domain ? '自定义域名' : '自动服务器 IP'}</strong></div><div class="config-item"><span>登录方式</span><strong>${esc(data.config && data.config.auth_mode || '账号密码会话')}</strong></div>`;
        const configFields = data.config && data.config.fields || [];
        renderConfigEditor('basic-config-editor', configFields, Boolean(data.config && data.config.editable), (field) => ['basic_settings', 'help_web_settings', 'zlibrary_account_settings', 'qq_reader_api_settings'].includes(field.category));
        renderConfigEditor('database-config-editor', configFields, Boolean(data.config && data.config.editable), (field) => field.category === 'database_settings');
        renderDatabaseStatus(database);
        renderQQAuthEditor(data.qq_reader || {});
        $('updated').textContent = '刚刚更新';
        document.querySelectorAll('[data-switch]').forEach((node) => node.addEventListener('click', () => changeNovel(node)));
      };
      const zlibraryAccountState = {request:0, abort:null, appid:'', data:null, loadedAt:0, loading:false, page:0, busy:new Set(), rowErrors:new Set(), filter:'all', search:'', group:'', selected:new Set(), mutating:false, modal:null};
      const closeZLibraryDialog = () => {
        const state = zlibraryAccountState, modal = state.modal; if (!modal) return;
        state.modal = null; modal.node.querySelectorAll('textarea,input[type=password]').forEach((el) => { el.value = ''; });
        if ($('toast')?.parentElement === modal.node) document.body.appendChild($('toast'));
        const appid=state.appid,detailId=modal.focus?.dataset.zlibraryDetail;
        modal.node.close(); modal.node.remove();
        queueMicrotask(()=>{if(activeView!=='bot'||consoleAppid!==appid)return;const target=modal.focus?.isConnected?modal.focus:detailId?$('zlibrary-account-editor')?.querySelector(`[data-zlibrary-detail="${CSS.escape(detailId)}"]`):$('zlibrary-account-editor')?.querySelector('[data-zlibrary-open]');target?.focus({preventScroll:true});});
      };
      const stopZLibraryAccount = (clear = false) => {
        const state = zlibraryAccountState;
        state.request += 1; state.abort?.abort(); state.abort = null; state.loading = false; state.busy.clear(); state.mutating = false; closeZLibraryDialog();
        if (clear) { state.appid = ''; state.data = null; state.loadedAt = 0; state.page = 0; state.filter = 'all'; state.search = ''; state.group = ''; state.selected.clear(); state.rowErrors.clear(); $('zlibrary-account-editor')?.replaceChildren(); }
      };
      const zlibraryPaused = (account) => { const p=account.profile || {}; return (p.available === true && p.downloads_remaining === 0) || (account.quota_paused && !(p.available === true && p.downloads_remaining > 0)); };
      const zlibraryFilteredAccounts = () => {
        const state=zlibraryAccountState, query=state.search.trim().toLocaleLowerCase();
        return (state.data?.accounts || []).filter((a) => (state.filter==='all' || (state.filter==='paused' ? zlibraryPaused(a) : state.filter==='disabled' ? a.enabled===false : a.status==='logged_in' && a.enabled!==false && !zlibraryPaused(a))) && (!state.group || a.group===state.group) && (!query || [a.email,a.name,a.note,a.group,a.profile?.name].some((x)=>String(x || '').toLocaleLowerCase().includes(query))));
      };
      const zlibraryVisibleAccounts = () => zlibraryFilteredAccounts().slice(zlibraryAccountState.page*10,(zlibraryAccountState.page+1)*10);
      const zlibraryNumber = (n) => Number.isSafeInteger(n) && n>=0 ? n.toLocaleString('zh-CN') : '未知';
      const zlibraryStatus = (a) => a.enabled===false ? '手动停用' : a.status!=='logged_in' ? '待完成' : zlibraryPaused(a) ? '限流' : a.profile?.available===false ? (['connection_timeout','network_timeout'].includes(a.profile.failure_category)?'连接超时':['connection_error','dns_error'].includes(a.profile.failure_category)?'连接失败':'查询失败') : a.profile?.available ? '正常' : '待查询';
      const renderZLibraryAccount = () => {
        const host=$('zlibrary-account-editor'); if (!host) return;
        const s=zlibraryAccountState, accounts=s.data?.accounts || [], old=host.querySelector('.zlibrary-table-scroll'), left=old?.scrollLeft || 0, top=old?.scrollTop || 0;
        const focus=host.contains(document.activeElement) ? document.activeElement : null, isSearch=focus?.hasAttribute('data-zlibrary-search'), caret=isSearch ? [focus.selectionStart,focus.selectionEnd] : null;
        const focusId=focus?.dataset.zlibraryRow;
        s.page=Math.min(s.page,Math.max(0,Math.ceil(zlibraryFilteredAccounts().length/10)-1));
        const visible=zlibraryVisibleAccounts(), count=s.selected.size, disabled=s.mutating || s.loading;
        const pill=(text,kind='')=>`<span class="zlibrary-pill ${kind}">${esc(text)}</span>`;
        const rows=visible.map((a)=>{const p=a.profile || {}, busy=s.busy.has(a.id), ready=a.status==='logged_in', paused=zlibraryPaused(a);
          return `<tr data-zlibrary-account="${esc(a.id)}" class="${s.selected.has(a.id)?'is-selected':paused?'is-exhausted':''}"><td><input type="checkbox" data-zlibrary-check="${esc(a.id)}" aria-label="选择 ${esc(a.email)}" ${s.selected.has(a.id)?'checked':''} ${disabled?'disabled':''}></td><td><button type="button" class="zlibrary-email" data-zlibrary-detail="${esc(a.id)}">${esc(a.email)}</button><div class="zlibrary-account-name"><small class="zlibrary-secondary">${esc(a.note || a.name || '未设置备注')}</small></div></td><td>${pill(busy?'查询中':zlibraryStatus(a),a.enabled===false?'':paused?'is-warning':p.available===false?'is-danger':p.available?'is-ok':'')}</td><td>${pill(typeof p.is_vip==='boolean'?(p.is_vip?'VIP / Premium':'普通账号'):'未知',p.is_vip?'is-vip':'')}<small class="zlibrary-secondary">${esc(a.group || '未分组')}</small></td><td class="zlibrary-quota">${pill(zlibraryNumber(p.downloads_remaining),paused?'is-danger':p.available?'is-ok':'')}<small class="zlibrary-secondary">已用 ${esc(zlibraryNumber(p.downloads_today))} / ${esc(zlibraryNumber(p.downloads_limit))}</small></td><td>${esc(qqReaderDate(a.created_at))}<small class="zlibrary-secondary">更新：${esc(p.checked_at?`${p.stale?'上次成功 ':''}${qqReaderDate(p.checked_at)}`:p.last_attempt_at?'本次未成功':'尚未查询')}</small></td><td><div class="zlibrary-row-actions"><button class="zlibrary-action" data-zlibrary-detail="${esc(a.id)}" type="button">查看 / 编辑</button><button class="zlibrary-action" data-zlibrary-row="${esc(a.id)}" type="button" ${!ready||busy||disabled?'disabled':''}>${busy?'查询中…':'刷新'}</button></div></td></tr>`;
        }).join('');
        host.innerHTML=`<div class="zlibrary-manager-tools"><div><button class="zlibrary-action is-primary" data-zlibrary-open="import" type="button" ${disabled?'disabled':''}>＋ 添加 / 批量导入</button><button class="zlibrary-action" data-zlibrary-export type="button">导出列表</button><button class="zlibrary-action" data-zlibrary-open="help" type="button">如何使用</button></div><button class="zlibrary-action" data-zlibrary-refresh type="button" ${disabled?'disabled':''}>${s.loading?'读取中…':'刷新列表'}</button></div><div class="zlibrary-toolbar"><div class="zlibrary-tabs" role="group" aria-label="筛选账号">${[['all','全部'],['available','可选'],['paused','限流'],['disabled','手动停用']].map(([key,label])=>`<button class="zlibrary-tab ${s.filter===key?'is-active':''}" data-zlibrary-filter="${key}" type="button" aria-pressed="${s.filter===key}">${label}</button>`).join('')}</div><div class="zlibrary-toolbar-tools"><select data-zlibrary-group aria-label="筛选分组"><option value="">全部分组</option>${(s.data?.groups || []).map((g)=>`<option ${s.group===g?'selected':''}>${esc(g)}</option>`).join('')}</select><label class="zlibrary-search"><input type="search" data-zlibrary-search aria-label="搜索账号昵称或邮箱" placeholder="搜索邮箱、备注、分组" value="${esc(s.search)}"></label></div></div><div class="zlibrary-bulk"><span>已选择 <strong>${count}</strong> / ${accounts.length}</span><button class="zlibrary-action" data-zlibrary-select-all type="button">选择筛选结果</button><button class="zlibrary-action" data-zlibrary-clear type="button">清空选择</button><select data-zlibrary-bulk aria-label="批量操作" ${!count||disabled?'disabled':''}><option value="">批量操作…</option><option value="refresh">刷新资料</option><option value="enable">启用账号</option><option value="disable">停用账号</option><option value="group">设置分组</option><option value="delete">移除本地账号</option></select></div><div class="zlibrary-table-scroll" role="region" aria-label="ZLibrary 账号列表" tabindex="0"><table class="zlibrary-table"><thead><tr><th><input type="checkbox" data-zlibrary-page-check aria-label="选择本页账号" ${visible.length&&visible.every(a=>s.selected.has(a.id))?'checked':''} ${disabled?'disabled':''}></th><th>账号信息</th><th>状态</th><th>会员 / 分组</th><th>今日剩余 / 额度</th><th>创建 / 更新时间</th><th>操作</th></tr></thead><tbody>${rows || `<tr><td colspan="7" class="zlibrary-empty">${esc(s.data?.message || (s.loading?'正在读取账号…':accounts.length?'没有匹配的账号':'暂无账号，点击添加导入现有账号'))}</td></tr>`}</tbody></table></div><div class="zlibrary-footer"><span role="status">共 ${accounts.length} 个账号 · 账号自动轮询，限流自动跳过，恢复后继续复用</span><div class="zlibrary-pagination"><button class="zlibrary-action" data-zlibrary-page="-1" type="button" aria-label="上一页账号" ${s.page<=0?'disabled':''}>上一页</button><span>${s.page+1} / ${Math.max(1,Math.ceil(zlibraryFilteredAccounts().length/10))}</span><button class="zlibrary-action" data-zlibrary-page="1" type="button" aria-label="下一页账号" ${(s.page+1)*10>=zlibraryFilteredAccounts().length?'disabled':''}>下一页</button></div></div>`;
        const scroll=host.querySelector('.zlibrary-table-scroll');scroll.scrollLeft=left;scroll.scrollTop=top;
        if(isSearch){const input=host.querySelector('[data-zlibrary-search]');input.focus({preventScroll:true});input.setSelectionRange(...caret);}
        if(focusId)host.querySelector(`[data-zlibrary-row="${CSS.escape(focusId)}"]`)?.focus({preventScroll:true});
        host.querySelectorAll('[data-zlibrary-check]').forEach(n=>n.onchange=()=>{n.checked?s.selected.add(n.dataset.zlibraryCheck):s.selected.delete(n.dataset.zlibraryCheck);renderZLibraryAccount();});
        host.querySelector('[data-zlibrary-page-check]').onchange=(e)=>{visible.forEach(a=>e.target.checked?s.selected.add(a.id):s.selected.delete(a.id));renderZLibraryAccount();};
        host.querySelector('[data-zlibrary-select-all]').onclick=()=>{zlibraryFilteredAccounts().forEach(a=>s.selected.add(a.id));renderZLibraryAccount();};
        host.querySelector('[data-zlibrary-clear]').onclick=()=>{s.selected.clear();renderZLibraryAccount();};
        host.querySelector('[data-zlibrary-bulk]').onchange=(e)=>{const action=e.target.value;e.target.value='';if(action==='group')openZLibraryDialog('group');else if(action)void mutateZLibrary(action,[...s.selected]);};
        host.querySelectorAll('[data-zlibrary-filter]').forEach(n=>n.onclick=()=>{s.filter=n.dataset.zlibraryFilter;s.page=0;renderZLibraryAccount();void loadZLibraryVisibleProfiles(false);});
        host.querySelector('[data-zlibrary-group]').onchange=(e)=>{s.group=e.target.value;s.page=0;renderZLibraryAccount();void loadZLibraryVisibleProfiles(false);};
        host.querySelector('[data-zlibrary-search]').oninput=(e)=>{s.search=e.target.value;s.page=0;renderZLibraryAccount();void loadZLibraryVisibleProfiles(false);};
        host.querySelectorAll('[data-zlibrary-page]').forEach(n=>n.onclick=()=>{s.page+=Number(n.dataset.zlibraryPage);renderZLibraryAccount();void loadZLibraryVisibleProfiles(false);});
        host.querySelectorAll('[data-zlibrary-detail]').forEach(n=>n.onclick=()=>openZLibraryDialog('detail',n.dataset.zlibraryDetail));
        host.querySelectorAll('[data-zlibrary-open]').forEach(n=>n.onclick=()=>openZLibraryDialog(n.dataset.zlibraryOpen));
        host.querySelector('[data-zlibrary-refresh]').onclick=()=>{void loadZLibraryAccount(true);};
        host.querySelectorAll('[data-zlibrary-row]').forEach(n=>n.onclick=()=>{void refreshZLibraryRow(n.dataset.zlibraryRow,true);});
        host.querySelector('[data-zlibrary-export]').onclick=()=>{const chosen=count?accounts.filter(a=>s.selected.has(a.id)):accounts;const blob=new Blob([JSON.stringify(chosen.map(a=>({email:a.email,name:a.name,group:a.group||'',note:a.note||'',enabled:a.enabled!==false,status:zlibraryStatus(a),profile:a.profile||null})),null,2)],{type:'application/json'});const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='ZLibrary账号列表.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),0);};
      };
      const openZLibraryDialog = (kind,id='') => {
        closeZLibraryDialog();const s=zlibraryAccountState,a=s.data?.accounts?.find(x=>x.id===id),p=a?.profile||{},node=document.createElement('dialog'),focus=document.activeElement;
        node.className='zlibrary-dialog';node.setAttribute('aria-labelledby','zlibrary-dialog-title');
        const titles={detail:'账号详情',import:'添加 / 批量导入',group:'设置分组',help:'如何使用'};
        let body='';
        if(kind==='detail'&&a)body=`<p class="zlibrary-detail-email">${esc(a.email)}</p><dl class="zlibrary-detail-grid"><dt>当前状态</dt><dd>${esc(zlibraryStatus(a))}</dd><dt>每日额度</dt><dd>剩余 ${esc(zlibraryNumber(p.downloads_remaining))} / ${esc(zlibraryNumber(p.downloads_limit))} · 已用 ${esc(zlibraryNumber(p.downloads_today))}</dd><dt>会员</dt><dd>${typeof p.is_vip==='boolean'?(p.is_vip?'VIP / Premium':'普通账号'):'未知'}</dd><dt>邮箱验证</dt><dd>${typeof p.email_confirmed==='boolean'?(p.email_confirmed?'已验证':'未验证'):'未知'}</dd><dt>详细权限</dt><dd>接口未返回</dd><dt>资料更新</dt><dd>${esc(p.checked_at?`${p.stale?'上次成功 ':''}${qqReaderDate(p.checked_at)}`:p.last_attempt_at?'本次未成功':'尚未查询')}</dd></dl><label>分组<input name="group" maxlength="40" value="${esc(a.group||'')}" placeholder="未分组"></label><label>备注<input name="note" maxlength="200" value="${esc(a.note||'')}" placeholder="添加便于辨认的备注"></label><div class="zlibrary-dialog-actions"><button class="zlibrary-action is-primary" data-z-save type="button">保存资料</button><button class="zlibrary-action" data-z-action="${a.enabled===false?'enable':'disable'}" type="button">${a.enabled===false?'启用账号':'停用账号'}</button><button class="zlibrary-action is-delete" data-z-action="delete" type="button">移除本地账号</button></div>`;
        if(kind==='import')body='<p>导入已有账号，验证登录和额度后保存。相同邮箱更新原账号，不重复添加。</p><label>账号内容（每次最多 50 个）<textarea name="accounts" rows="7" spellcheck="false" autocomplete="off" placeholder="邮箱----密码（每行一个）\n或 JSON 数组：[{&quot;email&quot;:&quot;…&quot;,&quot;password&quot;:&quot;…&quot;}]"></textarea></label><label>从本地文件读取<input type="file" name="file" accept=".txt,.json,text/plain,application/json"></label><p>密码仅用于登录验证和后端保存，不回显。此入口不注册新账号。</p><button class="zlibrary-action is-primary" data-z-import type="button">验证并导入</button><pre class="zlibrary-import-result" aria-live="polite"></pre>';
        if(kind==='group')body=`<p>将已选 ${s.selected.size} 个账号移入分组，留空即移出分组。可输入新分组名。</p><label>分组名称<input name="group" maxlength="40" list="zlibrary-groups"></label><datalist id="zlibrary-groups">${(s.data?.groups||[]).map(g=>`<option value="${esc(g)}">`).join('')}</datalist><button class="zlibrary-action is-primary" data-z-group type="button">保存分组</button>`;
        if(kind==='help')body='<ol class="zlibrary-help"><li><strong>添加账号</strong><p>导入已有邮箱和密码，逐个验证成功才保存；也可由管理员发送“测试账号”新建账号并保留。</p></li><li><strong>自动账号池</strong><p>无需设置当前账号。搜索和下载自动轮询已启用的可用账号，下载前核实官方剩余额度；限流账号自动跳过。</p></li><li><strong>额度与恢复</strong><p>额度为零显示“限流”，自动跳过，不删除账号。后续使用时按冷却或跨日重新查询，官方确认额度恢复后复用。所有账号限流就等待，不因额度耗尽自动注册。</p></li><li><strong>批量管理</strong><p>勾选本页或全部筛选结果，批量刷新、启停、分组或移除；一次写操作最多 100 个。手动停用的账号不会随额度恢复而启用。</p></li><li><strong>登录与安全</strong><p>查询时使用保存的邮箱密码登录取得 Cookie，不假设固定失效时间。操作中的下载保持已绑定账号。移除只删除本插件保存记录；导出仅含列表资料，不含密码，不能作为登录备份。</p></li></ol>';
        node.innerHTML=`<header><h2 id="zlibrary-dialog-title">${titles[kind]}</h2><button class="zlibrary-action" data-z-close type="button" aria-label="关闭账号窗口">×</button></header><div class="zlibrary-dialog-body">${body}</div><p class="zlibrary-dialog-message" role="status"></p>`;
        document.body.append(node);s.modal={node,focus};node.showModal();node.querySelector('[data-z-close]').onclick=closeZLibraryDialog;node.addEventListener('cancel',(e)=>{e.preventDefault();closeZLibraryDialog();});node.addEventListener('click',e=>{if(e.target===node){const r=node.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeZLibraryDialog();}});
        node.querySelector('[data-z-save]')?.addEventListener('click',()=>{void mutateZLibrary('edit',[id],{group:node.querySelector('[name=group]').value,note:node.querySelector('[name=note]').value});});
        node.querySelectorAll('[data-z-action]').forEach(n=>n.onclick=()=>{void mutateZLibrary(n.dataset.zAction,[id]);});
        node.querySelector('[data-z-group]')?.addEventListener('click',()=>{void mutateZLibrary('group',[...s.selected],{group:node.querySelector('[name=group]').value});});
        node.querySelector('[name=file]')?.addEventListener('change',async(e)=>{const file=e.target.files[0];if(!file)return;if(file.size>100000){node.querySelector('.zlibrary-dialog-message').textContent='文件过大，请限制在 100 KB 内';return;}const text=await file.text();if(s.modal?.node===node)node.querySelector('[name=accounts]').value=text;});
        node.querySelector('[data-z-import]')?.addEventListener('click',()=>{
          const input=node.querySelector('[name=accounts]');let accounts;try{const text=input.value.trim();accounts=text.startsWith('[')?JSON.parse(text):text.split(/\r?\n/).filter(x=>x.trim()).map(line=>{const i=line.indexOf('----');if(i<1)throw Error();return {email:line.slice(0,i).trim(),password:line.slice(i+4)};});if(!Array.isArray(accounts)||!accounts.length||accounts.length>50)throw Error();}catch(_){node.querySelector('.zlibrary-dialog-message').textContent='请输入有效 JSON 数组或每行“邮箱----密码”，最多 50 个';return;}void mutateZLibrary('import',[],{accounts});
        });
      };
      const mutateZLibrary = async (action,ids,extra={}) => {
        const s=zlibraryAccountState;if(s.mutating)return;
        if(action!=='import'&&(!ids.length||ids.length>100))return toast('每次请选择 1～100 个账号');
        if(action==='delete'&&!confirm(`仅移除已选 ${ids.length} 个本地账号，不注销站点账号。确定继续？`))return;
        if(action==='refresh'){const queue=[...ids],request=s.request,appid=s.appid;await Promise.all([0,1].map(async()=>{while(queue.length&&request===s.request&&appid===s.appid)await refreshZLibraryRow(queue.shift(),true);}));return;}
        s.request+=1;s.abort?.abort();s.abort=new AbortController();s.busy.clear();
        const request=s.request,appid=s.appid,generation=consoleGeneration,modal=s.modal?.node;s.mutating=true;renderZLibraryAccount();modal?.querySelectorAll('button,input,textarea').forEach(n=>{n.disabled=true;});
        if(modal)modal.querySelector('.zlibrary-dialog-message').textContent=action==='import'?'正在验证账号，请稍候…':'正在保存…';
        try{const data=await api(`zlibrary-accounts/${action==='import'?'import':'manage'}`,{method:'POST',body:JSON.stringify(action==='import'?extra:{action,ids,...extra}),signal:s.abort?.signal,botAppid:appid});if(!zlibraryRequestCurrent(request,appid,generation))return;
          s.data=data;s.loadedAt=Date.now();s.selected=new Set([...s.selected].filter(id=>data.accounts.some(a=>a.id===id)));toast(data.message||'已保存');
          if(action==='import'&&s.modal?.node===modal){modal.querySelector('[name=accounts]').value='';modal.querySelector('[name=file]').value='';modal.querySelector('.zlibrary-import-result').textContent=(data.results||[]).map(r=>`${r.success?'✓':'×'} ${r.email}：${r.message}`).join('\n');modal.querySelector('.zlibrary-dialog-message').textContent=data.message||'导入结束';}
          else closeZLibraryDialog();
        }catch(error){if(!zlibraryRequestCurrent(request,appid,generation)||error.name==='AbortError')return;if(error.status===401)showAuthError(error);else if(modal&&s.modal?.node===modal)modal.querySelector('.zlibrary-dialog-message').textContent=error.message;else toast(error.message);}
        finally{if(zlibraryRequestCurrent(request,appid,generation)){s.mutating=false;renderZLibraryAccount();if(modal&&s.modal?.node===modal)modal.querySelectorAll('button,input,textarea').forEach(n=>{n.disabled=false;});}}
      };
      const zlibraryRequestCurrent = (request, appid, generation) => request === zlibraryAccountState.request && appid === consoleAppid && generation === consoleGeneration && activeView === 'bot' && document.visibilityState !== 'hidden';
      const refreshZLibraryRow = async (id, force = false) => {
        const state = zlibraryAccountState, account = state.data?.accounts?.find((row) => row.id === id);
        if (!account || account.status !== 'logged_in' || state.busy.has(id) || !state.abort || !zlibraryRequestCurrent(state.request, state.appid, consoleGeneration)) return;
        if (!force && account.profile && Date.now()/1000 - (account.profile.last_attempt_at || account.profile.checked_at || 0) < 300) return;
        const request = state.request, appid = state.appid, generation = consoleGeneration;
        state.busy.add(id); state.rowErrors.delete(id); renderZLibraryAccount();
        try {
          const path = force ? 'zlibrary-account/refresh' : 'zlibrary-account';
          const data = await api(`${path}?account_id=${encodeURIComponent(id)}`, {method:force ? 'POST' : 'GET', signal:state.abort.signal, botAppid:appid});
          if (!zlibraryRequestCurrent(request, appid, generation)) return;
          if (data.account?.id === id && data.profile) {
            account.profile = data.profile; account.quota_paused = data.account.quota_paused === true;
          }
          else state.rowErrors.add(id);
        } catch (error) {
          if (!zlibraryRequestCurrent(request, appid, generation) || error.name === 'AbortError') return;
          account.profile = null; state.rowErrors.add(id);
          if (error.status === 401) showAuthError(error);
        } finally {
          if (zlibraryRequestCurrent(request, appid, generation)) { state.busy.delete(id); renderZLibraryAccount(); }
        }
      };
      const loadZLibraryVisibleProfiles = async (force) => {
        const state = zlibraryAccountState, request = state.request;
        const queue = zlibraryVisibleAccounts().filter((account) => account.status === 'logged_in' && (force || !account.profile)).map((account) => account.id);
        const worker = async () => { while (queue.length && request === state.request) await refreshZLibraryRow(queue.shift(), force); };
        await Promise.all([worker(), worker()]);
      };
      const loadZLibraryAccount = async (force = false) => {
        if (!consoleAppid || activeView !== 'bot' || document.visibilityState === 'hidden') return;
        const state = zlibraryAccountState;
        if (state.modal || state.mutating || (state.loading && !force)) return;
        if (!force && state.appid === consoleAppid && state.data && Date.now() - state.loadedAt < 60000) {
          if (!state.abort) state.abort = new AbortController(); renderZLibraryAccount(); void loadZLibraryVisibleProfiles(false); return;
        }
        stopZLibraryAccount(); state.abort = new AbortController();
        const request = state.request, appid = consoleAppid, generation = consoleGeneration;
        if (state.appid !== appid) { state.data = null; state.page = 0; state.loadedAt = 0; state.selected.clear(); state.group = ''; }
        state.appid = appid; state.loading = true; state.rowErrors.clear(); renderZLibraryAccount();
        try {
          const data = await api('zlibrary-accounts', {signal:state.abort.signal, botAppid:appid});
          if (!zlibraryRequestCurrent(request, appid, generation)) return;
          state.data = data; state.selected = new Set([...state.selected].filter(id => data.accounts.some(a => a.id === id))); state.loadedAt = Date.now(); state.page = Math.min(state.page, Math.max(0, Math.ceil(zlibraryFilteredAccounts().length / 10) - 1));
        } catch (error) {
          if (!zlibraryRequestCurrent(request, appid, generation) || error.name === 'AbortError') return;
          state.data = {accounts:[], message:'账号列表暂不可用，请稍后刷新'};
          if (error.status === 401) showAuthError(error);
        } finally {
          if (zlibraryRequestCurrent(request, appid, generation)) { state.loading = false; renderZLibraryAccount(); void loadZLibraryVisibleProfiles(force); }
        }
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
        if (account?.auth_status === 'invalid') return {label:'登录已失效，请重新登录', active:false, expires:'—'};
        const vip = account?.vip || {};
        return {label:vip.available === false || typeof vip.is_vip !== 'boolean' ? '会员状态待查询' : vip.is_vip ? String(vip.vip_type || 'VIP会员') : '非VIP', active:vip.available !== false && vip.is_vip === true, expires:vip.vip_expire_text || (vip.vip_expire_at ? qqReaderDate(vip.vip_expire_at) : vip.is_vip === false ? '—' : '未返回')};
      };
      const qqReaderAvatarHtml = (account) => {
        const name = String(account?.nickname || '书友');
        const raw = safeMediaUrl(String(account?.avatar_url || ''));
        const source = raw ? botApiUrl(`message/media?src=${encodeURIComponent(raw)}&mode=image`) : '';
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
        const appid = consoleAppid;
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
            try { await api('qq-reader-auth/scan', {method:'DELETE', body:JSON.stringify({scan_id:scanId}), botAppid:appid, scopeCleanup:true}); } catch (_) {}
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
          if ($('toast')?.parentElement === modal) document.body.appendChild($('toast'));
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
        detail.innerHTML = `<div class="qq-reader-detail-head">${qqReaderAvatarHtml(account)}<div class="qq-reader-detail-copy"><strong>${esc(account.nickname || '书友用户')}</strong><small>账号 ${esc(account.ywguid || '')}</small></div><button class="outline-button" id="qq-reader-profile-refresh" type="button" ${qqReaderEditable() ? '' : 'disabled'}>刷新资料</button></div><dl class="qq-reader-profile"><div><dt>登录状态</dt><dd>${account.auth_status === 'invalid' ? '已失效，请重新登录' : account.auth_status === 'valid' ? '已验证' : '待验证'}</dd></div><div><dt>会员状态</dt><dd>${vip.active ? '已开通' : account.vip?.available !== false && account.vip?.is_vip === false ? '未开通' : '待查询'}</dd></div><div><dt>会员类型</dt><dd>${esc(vip.label)}</dd></div><div><dt>到期时间</dt><dd>${esc(vip.expires)}</dd></div><div><dt>资料更新</dt><dd>${esc(qqReaderDate(account.profile_updated_at))}</dd></div></dl><div class="qq-reader-key-row"><label for="qq-reader-key">ywkey / usid</label><div><input id="qq-reader-key" type="password" readonly autocomplete="off" placeholder="点击显示密钥" aria-label="已保存的QQ阅读密钥"><button class="outline-button" id="qq-reader-key-toggle" type="button" aria-pressed="false" ${qqReaderEditable() ? '' : 'disabled'}>显示密钥</button></div></div><div class="qq-auth-actions"><button class="outline-button" type="button" id="qq-reader-select" ${!qqReaderEditable() || account.enabled === false || account.selected ? 'disabled' : ''}>${account.selected ? '当前使用账号' : '切换到此账号'}</button><button class="qq-reader-delete" type="button" id="qq-reader-delete" ${qqReaderEditable() ? '' : 'disabled'}>删除账号</button></div>`;
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
        const appid = consoleAppid;
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
          const cancellation = (async () => { if (previousCancel) await previousCancel; try { if (keepalive) await fetch(botApiUrl('qq-reader-auth/sms-login', appid), {method:'DELETE', credentials:'same-origin', keepalive:true, headers:{'Content-Type':'application/json'}, body:'{}'}); else await api('qq-reader-auth/sms-login', {method:'DELETE', body:'{}', botAppid:appid, scopeCleanup:true}); } catch (_) {} })();
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

      const jinjiang = {auth:null, request:0, loading:false, mutation:false, generation:0, adding:false, detailId:'', method:'scan', modalFocus:null, modalGeneration:0, modalOverflow:null, restoreFocus:true, scanId:'', scanAppid:'', image:'', scanMessage:'', scanStatus:'', scanTimer:null, scanGeneration:0, scanIntent:0, scanStarting:false, scanCancel:null};
      const jinjiangAccount = (id = jinjiang.detailId) => (jinjiang.auth?.accounts || []).find((account) => String(account.id) === String(id));
      const jinjiangEditable = () => Boolean(jinjiang.auth?.editable);
      const jinjiangTabVisible = () => Boolean(consoleAppid && activeView === 'bot' && !$('bot-panel-jinjiang')?.hidden && document.visibilityState !== 'hidden');
      const jinjiangScopeCurrent = (appid, generation) => appid === consoleAppid && generation === consoleGeneration;
      const jinjiangLoginLabel = (account) => account.auth_status === 'invalid' ? '登录已失效，请重新登录' : account.auth_status === 'valid' ? '登录已验证' : '登录状态待验证';
      const clearJinjiangManual = () => {
        for (const id of ['jinjiang-token', 'jinjiang-reader-id']) if ($(id)) $(id).value = '';
      };
      const updateJinjiangScan = () => {
        const image = $('jinjiang-qr-image');
        if (image) {
          if (jinjiang.image) { image.src = jinjiang.image; image.hidden = false; }
          else { image.removeAttribute('src'); image.hidden = true; }
        }
        if ($('jinjiang-qr-message')) $('jinjiang-qr-message').textContent = jinjiang.scanMessage || '使用晋江小说阅读 App 扫码，并在手机上确认登录。';
        if ($('jinjiang-scan-cancel')) $('jinjiang-scan-cancel').hidden = !jinjiang.scanId && !jinjiang.scanStarting;
        const button = $('jinjiang-scan-start');
        if (button) {
          button.disabled = !jinjiangEditable() || jinjiang.scanStarting || Boolean(jinjiang.scanCancel) || jinjiang.mutation;
          button.textContent = jinjiang.scanStarting ? '正在获取二维码' : jinjiang.scanId ? '更换二维码' : '获取二维码';
        }
      };
      const cancelJinjiangScan = async (scanId, appid, keepalive = false) => {
        if (!appid) return;
        const options = {method:'DELETE', body:JSON.stringify({scan_id:scanId})};
        try {
          if (keepalive) await fetch(botApiUrl('jinjiang-auth/scan', appid), {...options, credentials:'same-origin', keepalive:true, headers:{'Content-Type':'application/json'}});
          else await api('jinjiang-auth/scan', {...options, botAppid:appid, scopeCleanup:true});
        } catch (_) {}
      };
      const stopJinjiangScan = async (clearMessage = true, keepalive = false) => {
        const appid = jinjiang.scanAppid || consoleAppid, scanId = jinjiang.scanId, starting = jinjiang.scanStarting, previous = jinjiang.scanCancel;
        jinjiang.scanIntent += 1; jinjiang.scanGeneration += 1;
        jinjiang.scanStarting = false; jinjiang.scanId = ''; jinjiang.scanAppid = ''; jinjiang.image = ''; jinjiang.scanStatus = '';
        clearTimeout(jinjiang.scanTimer); jinjiang.scanTimer = null;
        if (clearMessage) jinjiang.scanMessage = '';
        updateJinjiangScan();
        if (scanId || starting) {
          const cancellation = (async () => { if (previous) await previous; await cancelJinjiangScan(scanId, appid, keepalive); })();
          jinjiang.scanCancel = cancellation; updateJinjiangScan();
          try { await cancellation; }
          finally { if (jinjiang.scanCancel === cancellation) { jinjiang.scanCancel = null; updateJinjiangScan(); } }
        } else if (previous) await previous;
      };
      const jinjiangModalFocusable = () => [...($('jinjiang-account-dialog')?.querySelectorAll('button,input,textarea,a[href],[tabindex]') || [])].filter((node) => !node.disabled && node.tabIndex >= 0 && node.getClientRects().length);
      const jinjiangModalKeydown = (event) => {
        const modal = $('jinjiang-account-dialog'); if (!modal?.open) return;
        if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); leaveJinjiang(true); return; }
        if (event.key !== 'Tab') return;
        event.stopPropagation();
        const nodes = jinjiangModalFocusable(), index = nodes.indexOf(document.activeElement);
        if (!nodes.length) { event.preventDefault(); modal.focus({preventScroll:true}); }
        else if (event.shiftKey && index <= 0) { event.preventDefault(); nodes.at(-1).focus(); }
        else if (!event.shiftKey && (index < 0 || index === nodes.length - 1)) { event.preventDefault(); nodes[0].focus(); }
      };
      const syncJinjiangModal = () => {
        const modal = $('jinjiang-account-dialog'); if (!modal) return;
        const wanted = jinjiangTabVisible() && (jinjiang.adding || Boolean(jinjiangAccount()));
        if ($('jinjiang-modal-title')) $('jinjiang-modal-title').textContent = jinjiang.adding ? '添加晋江账号' : '晋江账号详情';
        if (wanted && !modal.open) {
          jinjiang.modalGeneration += 1; jinjiang.modalOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden';
          modal.showModal(); document.addEventListener('keydown', jinjiangModalKeydown, true);
        } else if (!wanted && (modal.open || jinjiang.modalOverflow !== null)) {
          const generation = ++jinjiang.modalGeneration, focus = jinjiang.modalFocus, restore = jinjiang.restoreFocus;
          jinjiang.modalFocus = null;
          if ($('toast')?.parentElement === modal) document.body.appendChild($('toast'));
          if (modal.open) modal.close();
          if (jinjiang.modalOverflow !== null) document.body.style.overflow = jinjiang.modalOverflow;
          jinjiang.modalOverflow = null; document.removeEventListener('keydown', jinjiangModalKeydown, true);
          if (restore) queueMicrotask(() => {
            if (generation !== jinjiang.modalGeneration || modal.open || !jinjiangTabVisible()) return;
            const target = focus?.accountId ? $('jinjiang-accounts')?.querySelector(`[data-jinjiang-open="${CSS.escape(focus.accountId)}"]`) : focus?.node;
            (target?.isConnected && !target.disabled ? target : $('jinjiang-add'))?.focus({preventScroll:true});
          });
        }
      };
      const leaveJinjiang = (restoreFocus = false, keepalive = false) => {
        jinjiang.request += 1; jinjiang.generation += 1; jinjiang.loading = false; jinjiang.mutation = false;
        jinjiang.adding = false; jinjiang.detailId = ''; jinjiang.restoreFocus = restoreFocus;
        clearJinjiangManual(); void stopJinjiangScan(true, keepalive); syncJinjiangModal();
      };
      const setJinjiangMethod = (method) => {
        const next = method === 'token' ? 'token' : 'scan';
        if (next !== jinjiang.method) { clearJinjiangManual(); if (next !== 'scan') void stopJinjiangScan(); }
        jinjiang.method = next;
        for (const value of ['scan','token']) {
          const button = $(`jinjiang-method-${value}`); button?.classList.toggle('active', value === next); button?.setAttribute('aria-pressed', String(value === next));
        }
        if ($('jinjiang-scan-panel')) $('jinjiang-scan-panel').hidden = next !== 'scan';
        if ($('jinjiang-manual-panel')) $('jinjiang-manual-panel').hidden = next !== 'token';
      };
      const renderJinjiangAccounts = (auth) => {
        const node = $('jinjiang-auth-editor'); if (!node || !Array.isArray(auth?.accounts)) return;
        jinjiang.auth = {...auth, accounts:auth.accounts.map((account) => ({...account, selected:String(account.id) === String(auth.selected_id || '')}))};
        if (jinjiang.detailId && !jinjiangAccount()) jinjiang.detailId = '';
        if (!$('jinjiang-accounts')) {
          node.innerHTML = `<div class="qq-reader-toolbar"><span id="jinjiang-summary"></span><div class="qq-auth-actions"><button class="outline-button" id="jinjiang-refresh" type="button">刷新列表</button><button class="outline-button" id="jinjiang-add" type="button">添加账号</button></div></div><div id="jinjiang-accounts" class="qq-reader-accounts"></div>`;
          const modal = document.createElement('dialog'); modal.id = 'jinjiang-account-dialog'; modal.className = 'qq-reader-modal';
          modal.setAttribute('aria-labelledby','jinjiang-modal-title'); modal.setAttribute('aria-modal','true'); modal.tabIndex = -1;
          modal.innerHTML = `<div class="qq-reader-modal-head"><h3 id="jinjiang-modal-title">晋江账号</h3><button class="qq-reader-modal-close" id="jinjiang-modal-close" type="button" aria-label="关闭账号窗口">×</button></div><div class="qq-reader-modal-body"><section id="jinjiang-detail" class="qq-reader-detail" hidden></section><section id="jinjiang-add-panel" class="qq-reader-add-panel" hidden><div class="qq-auth-tabs" role="group" aria-label="选择晋江登录方式"><button class="qq-auth-tab active" id="jinjiang-method-scan" type="button" aria-pressed="true">App 扫码登录</button><button class="qq-auth-tab" id="jinjiang-method-token" type="button" aria-pressed="false">手动添加</button></div><div id="jinjiang-scan-panel" class="qq-reader-scan-panel"><button class="outline-button" id="jinjiang-scan-start" type="button">获取二维码</button><img id="jinjiang-qr-image" class="qq-reader-qr-image" alt="晋江 App 登录二维码" hidden><p id="jinjiang-qr-message" class="qq-reader-field-hint" aria-live="polite"></p><button class="text-button" id="jinjiang-scan-cancel" type="button" hidden>取消扫码</button></div><div id="jinjiang-manual-panel" class="jinjiang-manual-panel" hidden><label class="qq-reader-field-label" for="jinjiang-token">Token</label><input id="jinjiang-token" class="qq-reader-cookie" type="password" autocomplete="off" spellcheck="false" placeholder="填写晋江登录 Token"><label class="qq-reader-field-label" for="jinjiang-reader-id">读者编号</label><input id="jinjiang-reader-id" class="qq-reader-cookie" type="text" inputmode="numeric" autocomplete="off" placeholder="readerId"><p class="qq-reader-field-hint">登录凭据仅用于当前机器人的晋江账号，不会在账号列表中回显。</p><div class="qq-auth-actions"><button class="primary-button" id="jinjiang-save" type="button">添加并使用</button></div></div></section></div>`;
          document.body.appendChild(modal);
          let backdropDown = false;
          const outside = (event) => { const rect = modal.getBoundingClientRect(); return event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom; };
          modal.addEventListener('pointerdown', (event) => { backdropDown = event.target === modal && outside(event); });
          modal.addEventListener('click', (event) => { if (event.target === modal && backdropDown && outside(event)) leaveJinjiang(true); backdropDown = false; });
          modal.addEventListener('cancel', (event) => { event.preventDefault(); leaveJinjiang(true); });
          modal.addEventListener('close', () => { if (!modal.open && (jinjiang.adding || jinjiang.detailId || jinjiang.modalOverflow !== null)) leaveJinjiang(true); });
          $('jinjiang-modal-close').addEventListener('click', () => leaveJinjiang(true));
          $('jinjiang-refresh').addEventListener('click', () => void loadJinjiangAccounts());
          $('jinjiang-add').addEventListener('click', (event) => {
            leaveQQReader(); closeZLibraryDialog(); clearJinjiangManual(); jinjiang.modalFocus = {node:event.currentTarget}; jinjiang.restoreFocus = true;
            jinjiang.detailId = ''; jinjiang.adding = true; renderJinjiangAccounts(jinjiang.auth);
          });
          $('jinjiang-method-scan').addEventListener('click', () => setJinjiangMethod('scan'));
          $('jinjiang-method-token').addEventListener('click', () => setJinjiangMethod('token'));
          $('jinjiang-scan-start').addEventListener('click', () => void startJinjiangScan());
          $('jinjiang-scan-cancel').addEventListener('click', () => void stopJinjiangScan());
          $('jinjiang-save').addEventListener('click', () => void saveJinjiangAccount());
        }
        const accounts = jinjiang.auth.accounts, editable = jinjiangEditable() && !jinjiang.mutation;
        $('jinjiang-summary').textContent = `${accounts.length} 个账号 · ${accounts.filter((account) => account.enabled !== false).length} 个启用${auth.configured ? '' : ' · 当前未登录'}`;
        $('jinjiang-add').disabled = !editable; $('jinjiang-refresh').disabled = jinjiang.loading || jinjiang.mutation; $('jinjiang-save').disabled = !editable;
        $('jinjiang-accounts').innerHTML = accounts.map((account) => `<article class="qq-reader-account ${account.selected ? 'is-current' : ''} ${account.enabled === false ? 'is-disabled' : ''}"><div class="qq-reader-account-top"><span class="tag ${account.selected ? 'ok' : account.enabled === false ? 'off' : ''}">${account.selected ? '当前使用' : account.enabled === false ? '已停用' : '已启用'}</span><button class="switch qq-reader-account-switch ${account.enabled !== false ? 'on' : ''}" type="button" data-jinjiang-enable="${esc(account.id)}" aria-label="${account.enabled === false ? '启用' : '停用'}晋江账号" aria-pressed="${account.enabled !== false}" ${editable ? '' : 'disabled'}><span></span></button></div><button class="qq-reader-account-open" type="button" data-jinjiang-open="${esc(account.id)}" aria-expanded="${!jinjiang.adding && String(account.id) === jinjiang.detailId}"><span class="qq-reader-avatar" aria-hidden="true">晋</span><span><strong>${esc(account.nickname || '晋江读者')}</strong><small>读者 ${esc(account.readerId || '待查询')}</small></span><span class="qq-reader-arrow" aria-hidden="true">›</span></button><div class="qq-reader-account-vip"><span>${esc(jinjiangLoginLabel(account))}</span></div></article>`).join('') || '<div class="empty qq-reader-empty">还没有晋江账号，请添加账号。</div>';
        $('jinjiang-accounts').querySelectorAll('[data-jinjiang-open]').forEach((button) => button.addEventListener('click', () => {
          leaveQQReader(); closeZLibraryDialog(); void stopJinjiangScan(); clearJinjiangManual();
          jinjiang.modalFocus = {accountId:button.dataset.jinjiangOpen}; jinjiang.restoreFocus = true; jinjiang.adding = false; jinjiang.detailId = button.dataset.jinjiangOpen;
          renderJinjiangAccounts(jinjiang.auth);
        }));
        $('jinjiang-accounts').querySelectorAll('[data-jinjiang-enable]').forEach((button) => button.addEventListener('click', () => {
          const account = jinjiangAccount(button.dataset.jinjiangEnable); if (account) void mutateJinjiangAccount('enable', account.id, {enabled:account.enabled === false});
        }));
        const detail = $('jinjiang-detail'), account = jinjiangAccount(), focused = detail.contains(document.activeElement) ? document.activeElement.id : '';
        detail.hidden = jinjiang.adding || !account;
        if (account) {
          detail.innerHTML = `<div class="qq-reader-detail-head"><span class="qq-reader-avatar" aria-hidden="true">晋</span><div class="qq-reader-detail-copy"><strong>${esc(account.nickname || '晋江读者')}</strong><small>读者 ${esc(account.readerId || '待查询')}</small></div><button class="outline-button" id="jinjiang-profile-refresh" type="button" ${editable ? '' : 'disabled'}>刷新资料</button></div><dl class="qq-reader-profile"><div><dt>登录状态</dt><dd>${esc(jinjiangLoginLabel(account))}</dd></div><div><dt>账号状态</dt><dd>${account.enabled === false ? '已停用' : '已启用'}</dd></div><div><dt>最近验证</dt><dd>${esc(['valid','invalid'].includes(account.auth_status) && Number(account.profile_updated_at) > 0 ? qqReaderDate(account.profile_updated_at) : '未验证')}</dd></div><div><dt>资料更新</dt><dd>${esc(qqReaderDate(account.profile_updated_at))}</dd></div></dl><div class="qq-auth-actions"><button class="outline-button" id="jinjiang-select" type="button" ${editable && account.enabled !== false && !account.selected ? '' : 'disabled'}>${account.selected ? '当前使用账号' : '切换到此账号'}</button><button class="qq-reader-delete" id="jinjiang-delete" type="button" ${editable ? '' : 'disabled'}>删除账号</button></div>`;
          $('jinjiang-profile-refresh').addEventListener('click', () => void mutateJinjiangAccount('refresh', account.id));
          $('jinjiang-select').addEventListener('click', () => void mutateJinjiangAccount('select', account.id));
          $('jinjiang-delete').addEventListener('click', () => { if (confirm('确定删除此晋江账号吗？')) void mutateJinjiangAccount('delete', account.id); });
        } else detail.replaceChildren();
        $('jinjiang-add-panel').hidden = !jinjiang.adding; setJinjiangMethod(jinjiang.method); updateJinjiangScan(); syncJinjiangModal();
        if (focused && $('jinjiang-account-dialog')?.open) $(focused)?.focus({preventScroll:true});
      };
      const loadJinjiangAccounts = async () => {
        if (!jinjiangTabVisible() || jinjiang.loading || jinjiang.mutation) return;
        const request = ++jinjiang.request, appid = consoleAppid, generation = consoleGeneration;
        jinjiang.loading = true; if ($('jinjiang-refresh')) $('jinjiang-refresh').disabled = true;
        try {
          const data = await api('jinjiang-auth', {botAppid:appid});
          if (request === jinjiang.request && jinjiangScopeCurrent(appid, generation) && jinjiangTabVisible()) renderJinjiangAccounts(data);
        } catch (error) {
          if (request !== jinjiang.request || !jinjiangScopeCurrent(appid, generation) || error.name === 'AbortError') return;
          if (error.status === 401) showAuthError(error);
          else if (jinjiang.auth) toast(error.message);
          else {
            const node = $('jinjiang-auth-editor'); if (node) { node.innerHTML = '<div class="empty">晋江账号暂时无法读取。<button class="text-button" id="jinjiang-retry" type="button">重新读取</button></div>'; $('jinjiang-retry')?.addEventListener('click', () => void loadJinjiangAccounts()); }
          }
        } finally {
          if (request === jinjiang.request && jinjiangScopeCurrent(appid, generation)) { jinjiang.loading = false; if ($('jinjiang-refresh')) $('jinjiang-refresh').disabled = jinjiang.mutation; }
        }
      };
      const mutateJinjiangAccount = async (action, id, extra = {}) => {
        if (!jinjiangEditable() || jinjiang.mutation) return;
        const appid = consoleAppid, scope = consoleGeneration, generation = jinjiang.generation;
        jinjiang.request += 1; jinjiang.loading = false; jinjiang.mutation = true; renderJinjiangAccounts(jinjiang.auth);
        try {
          const data = await api(action === 'delete' ? 'jinjiang-auth' : `jinjiang-auth/${action}`, {method:action === 'delete' ? 'DELETE' : 'POST', body:JSON.stringify({account_id:id, ...extra}), botAppid:appid});
          if (!jinjiangScopeCurrent(appid, scope) || generation !== jinjiang.generation) return;
          if (action === 'delete') jinjiang.detailId = '';
          renderJinjiangAccounts(data); toast(action === 'refresh' ? '晋江账号资料已刷新' : action === 'delete' ? '晋江账号已删除' : action === 'select' ? '晋江账号已切换' : '晋江账号状态已更新');
        } catch (error) {
          if (!jinjiangScopeCurrent(appid, scope) || generation !== jinjiang.generation || error.name === 'AbortError') return;
          if (error.status === 401) showAuthError(error); else toast(error.message);
        } finally {
          if (jinjiangScopeCurrent(appid, scope) && generation === jinjiang.generation) { jinjiang.mutation = false; if (jinjiang.auth) renderJinjiangAccounts(jinjiang.auth); }
        }
      };
      const saveJinjiangAccount = async () => {
        const token = $('jinjiang-token')?.value.trim(), readerId = $('jinjiang-reader-id')?.value.trim();
        if (!token) return toast('请填写晋江登录 Token');
        if (!readerId || !/^[0-9]{1,32}$/.test(readerId) || !/[1-9]/.test(readerId)) return toast('请填写有效的读者编号（1～32位正整数）');
        if (!jinjiangEditable() || jinjiang.mutation) return;
        const appid = consoleAppid, scope = consoleGeneration, generation = jinjiang.generation;
        jinjiang.request += 1; jinjiang.loading = false; jinjiang.mutation = true; renderJinjiangAccounts(jinjiang.auth);
        try {
          const data = await api('jinjiang-auth', {method:'POST', body:JSON.stringify({token, readerId, select:true}), botAppid:appid});
          if (!jinjiangScopeCurrent(appid, scope) || generation !== jinjiang.generation) return;
          clearJinjiangManual(); jinjiang.adding = false; jinjiang.detailId = ''; renderJinjiangAccounts(data); toast('晋江账号已添加并切换');
        } catch (error) {
          if (!jinjiangScopeCurrent(appid, scope) || generation !== jinjiang.generation || error.name === 'AbortError') return;
          if (error.status === 401) showAuthError(error); else toast(error.message);
        } finally {
          if (jinjiangScopeCurrent(appid, scope) && generation === jinjiang.generation) { jinjiang.mutation = false; if (jinjiang.auth) renderJinjiangAccounts(jinjiang.auth); }
        }
      };
      const startJinjiangScan = async () => {
        if (!jinjiangEditable() || jinjiang.mutation) return;
        const appid = consoleAppid, scope = consoleGeneration, cancellation = stopJinjiangScan(), intent = jinjiang.scanIntent;
        await cancellation;
        const current = () => jinjiangScopeCurrent(appid, scope) && jinjiangTabVisible() && jinjiang.adding && jinjiang.method === 'scan';
        if (intent !== jinjiang.scanIntent || !current()) return;
        const generation = ++jinjiang.scanGeneration;
        jinjiang.scanStarting = true; jinjiang.scanAppid = appid; jinjiang.scanMessage = '正在生成二维码…'; updateJinjiangScan();
        try {
          const result = await api('jinjiang-auth/scan', {method:'POST', body:'{}', botAppid:appid});
          if (generation !== jinjiang.scanGeneration || !current()) { if (result.scan_id) await cancelJinjiangScan(String(result.scan_id), appid); return; }
          if (!result.scan_id || !/^data:image\/png;base64,[A-Za-z0-9+/=\r\n]+$/.test(String(result.qr_image || ''))) throw new Error('二维码获取失败，请重试');
          jinjiang.scanStarting = false; jinjiang.scanId = String(result.scan_id); jinjiang.image = result.qr_image;
          jinjiang.scanStatus = result.status || 'waiting'; jinjiang.scanMessage = result.message || '请使用晋江小说阅读 App 扫码确认。'; updateJinjiangScan();
          const scanId = jinjiang.scanId, expires = Date.now() + Math.max(10, Math.min(600, Number(result.expires_in) || 120)) * 1000;
          let failures = 0;
          const poll = async () => {
            if (scanId !== jinjiang.scanId || generation !== jinjiang.scanGeneration) return;
            if (!current()) { await stopJinjiangScan(); return; }
            if (Date.now() >= expires) { jinjiang.scanMessage = '二维码已过期，请重新获取。'; await stopJinjiangScan(false); return; }
            try {
              const state = await api(`jinjiang-auth/scan?scan_id=${encodeURIComponent(scanId)}`, {botAppid:appid});
              if (scanId !== jinjiang.scanId || generation !== jinjiang.scanGeneration || !current()) return;
              failures = 0; jinjiang.scanStatus = state.status; jinjiang.scanMessage = state.message || '正在等待扫码。'; updateJinjiangScan();
              if (['waiting','scanned','saving'].includes(state.status)) { jinjiang.scanTimer = setTimeout(poll, 2000); return; }
              await stopJinjiangScan(false);
              if (!current()) return;
              if (state.status === 'success') { clearJinjiangManual(); jinjiang.adding = false; jinjiang.detailId = ''; await loadJinjiangAccounts(); if (jinjiangScopeCurrent(appid, scope)) toast('晋江账号已扫码登录'); }
            } catch (error) {
              if (scanId !== jinjiang.scanId || generation !== jinjiang.scanGeneration || !current()) return;
              if (error.status === 401) { await stopJinjiangScan(); showAuthError(error); return; }
              failures += 1; jinjiang.scanMessage = failures >= 3 ? '状态查询暂时失败，请重新获取二维码。' : '正在重试查询扫码状态…'; updateJinjiangScan();
              if (failures >= 3) { await stopJinjiangScan(false); return; }
              jinjiang.scanTimer = setTimeout(poll, 3000);
            }
          };
          jinjiang.scanTimer = setTimeout(poll, 1500);
        } catch (error) {
          if (generation !== jinjiang.scanGeneration || !current() || error.name === 'AbortError') return;
          jinjiang.scanMessage = error.message || '二维码获取失败，请重试。'; updateJinjiangScan();
          await stopJinjiangScan(false);
          if (error.status === 401) showAuthError(error);
        } finally { if (generation === jinjiang.scanGeneration) { jinjiang.scanStarting = false; updateJinjiangScan(); } }
      };
      const syncJinjiangTab = () => { if (jinjiangTabVisible()) void loadJinjiangAccounts(); else leaveJinjiang(); };
      botTabs?.addEventListener('click', () => queueMicrotask(syncJinjiangTab));
      botTabs?.addEventListener('keydown', (event) => { if (['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) queueMicrotask(syncJinjiangTab); });
      window.addEventListener('pagehide', () => leaveJinjiang(false, true));
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') leaveJinjiang(); else syncJinjiangTab(); });

      const leaveQQReader = () => backQQReaderList(false);
      window.addEventListener('pagehide', () => {
        hideQQReaderKey(); clearQQReaderManual();
        void stopQQReaderSms(true, true);
        qqReader.adding = false; qqReader.detailId = ''; qqReader.modalRestoreFocus = false; syncQQReaderModal();
        if (qqReader.scanId || qqReader.scanStarting) fetch(botApiUrl('qq-reader-auth/scan'), {method:'DELETE', credentials:'same-origin', keepalive:true, headers:{'Content-Type':'application/json'}, body:JSON.stringify({scan_id:qqReader.scanId})}).catch(() => {});
        qqReader.scanIntent += 1; qqReader.scanGeneration += 1; qqReader.scanStarting = false; qqReader.scanId = ''; qqReader.image = ''; clearTimeout(qqReader.scanTimer);
      });
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') { leaveQQReader(); stopZLibraryAccount(); } else { void loadZLibraryAccount(); } });

       const addPanAccount = async (platform) => { const input = document.querySelector(`[data-pan-cookie="${CSS.escape(platform)}"]`); const button = document.querySelector(`[data-pan-add="${CSS.escape(platform)}"]`); const cookie = input?.value.trim(); if (!cookie) return toast('请先粘贴 Cookie'); if (button) button.disabled = true; try { await api(`pan-accounts/${encodeURIComponent(platform)}`, {method:'POST', body:JSON.stringify({cookie})}); if (input) input.value = ''; toast(`${platform}账号已保存`); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const startQuarkWebScan = async (button) => {
         if (!snapshot?.pans?.editable) return toast('数据库未配置，扫码账号不能保存');
         const scopeGeneration = consoleGeneration;
         await stopQuarkWebScan();
         if (scopeGeneration !== consoleGeneration) return;
         const generation = ++quarkWebScanGeneration;
         if (button) { button.disabled = true; button.textContent = '正在获取二维码'; }
         const statusNode = document.querySelector('[data-quark-scan-status]');
         try {
           const result = await api(`pan-accounts/${encodeURIComponent('夸克')}/scan`, {method:'POST', body:'{}'});
           if (scopeGeneration !== consoleGeneration || generation !== quarkWebScanGeneration) return;
           quarkWebScanId = String(result.scan_id || '');
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
               if (scopeGeneration !== consoleGeneration || generation !== quarkWebScanGeneration) return;
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
               if (scopeGeneration !== consoleGeneration || generation !== quarkWebScanGeneration || error.name === 'AbortError') return;
               if (error.status === 401) { showAuthError(error); return; }
               const label = document.querySelector('[data-quark-scan-status]');
               if (label) label.textContent = error.message || '正在重试查询扫码状态。';
               quarkWebScanTimer = setTimeout(poll, 3000);
             }
           };
           quarkWebScanTimer = setTimeout(poll, 1500);
         } catch (error) {
           if (scopeGeneration !== consoleGeneration || generation !== quarkWebScanGeneration || error.name === 'AbortError') return;
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
         const generation = consoleGeneration;
         const pending = api('pan-accounts/夸克').then((data) => {
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
           if (generation !== consoleGeneration || error.name === 'AbortError') return;
           quarkProfileRefreshAfter = Date.now() + quarkProfileRetryIntervalMs;
           if (error.status === 401) showAuthError(error);
         }).finally(() => { if (quarkProfileRefreshPromise === pending) quarkProfileRefreshPromise = null; });
         quarkProfileRefreshPromise = pending;
         return quarkProfileRefreshPromise;
       };
       const savePanDirectory = async (platform, button) => { const input = document.querySelector(`[data-pan-dir="${CSS.escape(platform)}"]`); const field = input?.dataset.panDirField; const value = input?.value.trim(); if (!field || !value) return toast('请输入上传目录'); if (button) button.disabled = true; try { const result = await api('config', {method:'POST', body:JSON.stringify({fields:{[field]:value}})}); toast(result.message || `${platform}上传目录已保存`); await load(); } catch (error) { if (error.status === 401) showAuthError(error); else toast(error.message); } finally { if (button) button.disabled = false; } };
       const changePanAccountEnabled = async (platform, index, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，账号状态不能保存'); const enabled = node.dataset.enabled !== 'true'; node.disabled = true; try { const result = await api(`pan-accounts/${encodeURIComponent(platform)}/enable`, {method:'POST', body:JSON.stringify({index:Number(index), enabled})}); toast(result.message || `账号${enabled ? '已启用' : '已停用'}`); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
       const changePanAccountDefault = async (platform, index, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，默认账号不能保存'); node.disabled = true; try { const result = await api(`pan-accounts/${encodeURIComponent(platform)}/default`, {method:'POST', body:JSON.stringify({index:Number(index)})}); toast(result.message || `${platform}默认账号已更新`); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
      const showAuthError = (error) => { if (error.name === 'AbortError') return; if (error.status === 401) { location.reload(); return; } if ($('popover-logout')) $('popover-logout').hidden = true; showNotice(error.status === 503 ? '登录服务尚未启用，请联系管理员。' : '控制台数据暂时不可用，请稍后重试。'); };
      const adminChip = $('admin-chip'); const adminPopover = $('admin-popover');
      adminChip?.addEventListener('click', (event) => {
        event.stopPropagation(); closeMsgHeadMenu();
        const expanded = adminChip.getAttribute('aria-expanded') === 'true';
        ['admin-chip', 'msg-rail-admin'].forEach((id) => $(id)?.setAttribute('aria-expanded', String(!expanded)));
        if (adminPopover) adminPopover.hidden = expanded;
      });
      document.addEventListener('click', (event) => { if (!adminPopover?.contains(event.target)) closeAdminPopover(); });
      document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape' || !adminPopover || adminPopover.hidden) return;
        event.preventDefault(); closeAdminPopover();
        $(document.body.classList.contains('messages-workspace') ? 'msg-rail-admin' : 'admin-chip')?.focus({preventScroll:true});
      });
      $('msg-rail-theme')?.addEventListener('click', () => $('theme-toggle')?.click());
      $('msg-rail-admin')?.addEventListener('click', (event) => {
        event.stopPropagation(); adminChip?.click();
        if (event.detail === 0 && adminPopover && !adminPopover.hidden) modalFocusable(adminPopover)[0]?.focus({preventScroll:true});
      });
      const changeNovel = async (node) => { if (!snapshot || !snapshot.novels.editable) return toast('数据库未配置，开关不能保存'); const enabled = node.dataset.enabled !== 'true'; node.disabled = true; try { await api('novel-switch', {method:'POST', body:JSON.stringify({key:node.dataset.switch, enabled})}); toast('小说开关已更新'); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
       const changePanEnabled = async (key, node) => { if (!snapshot || !snapshot.pans.editable) return toast('数据库未配置，网盘开关不能保存'); const enabled = node.dataset.enabled !== 'true'; node.disabled = true; try { const result = await api('pan-enable', {method:'POST', body:JSON.stringify({key, enabled})}); toast(result.message || `网盘${enabled ? '已开启' : '已关闭'}`); await load(); } catch (error) { node.disabled = false; if (error.status === 401) showAuthError(error); else toast(error.message); } };
      const load = async () => { if (!consoleAppid) return loadBotProfile(); try { render(await api('dashboard')); void loadBotProfile(); if ($('popover-logout')) $('popover-logout').hidden = false; setView(viewFromUrl(), false); } catch (error) { showAuthError(error); } };
      $('popover-logout').addEventListener('click', async () => { leaveQQReader(); leaveJinjiang(); try { await api('logout', {method:'POST'}); } finally { location.reload(); } });
      document.querySelectorAll('[data-view]').forEach((node) => node.addEventListener('click', (event) => { event.preventDefault(); setView(node.dataset.view); }));
      window.addEventListener('popstate', () => {
        const appid = String(new URLSearchParams(location.search).get('appid') || '').trim();
        if (!appid) { exitBotConsole(false); return; }
        if (appid === consoleAppid) { setView(viewFromUrl(), false); return; }
        const profile = botProfileForAppid(appid);
        if (profile.appid) { exitBotConsole(false); void enterBotConsole(profile, false); }
        else exitBotConsole(false);
      });

      // ---------- 消息记录页 ----------
      const msgHistoryPageSize = 100;
      const msgHistoryInitialPageSize = 50;
      const msgState = { selectedAppid:'', scopeGeneration:0, filter:'all', grouped:false, folderCollapsed:{group:false,user:false}, search:'', page:1, chatId:'', chatType:'group', chatAppid:'', chatRemoved:false, chats:[], realtimeChats:new Map(), groupMembership:new Map(), messages:[], historyData:null, historyWindow:null, historyCache:new Map(), renderedChatId:'', messageRenderSignature:null, initialScrollChatId:'', positionToken:0, positionFrame:null, positionTimer:null, positionObserver:null, positionBody:null, pendingNewMessages:0, historyRequest:0, historyOlderRequest:0, historyOlderLoading:false, historyScheduleFrame:null, historyScheduleToken:0, chatListRequest:0, chatListAbort:null, chatListPromise:null, chatListKey:'', chatListRendered:false, chatListServerLoaded:false, chatListTopPending:false, chatListScrollActive:false, chatListPointerActive:false, chatListScrollTimer:null, chatListPendingData:null, chatListRows:[], chatListOffsets:[0], chatListContentHeight:0, chatListRowHeight:52, chatListWindowStart:-1, chatListWindowEnd:-1, historyAbort:null, historyOlderAbort:null, readInFlight:new Set(), chatRenderTimer:null, chatRenderSignature:null, realtimeMessageTimer:null, realtimeMessageCount:0, realtimeToBottom:false, realtimeRenderChatId:'', quote:null, mute:{member:'',name:''}, mutes:new Map(), muteRequestAt:0, sendType:'text', sendMode:'default', muteMinutes:30, timer:null, muteTimer:null, eventSocket:null, eventSource:null, eventTransport:'', eventReconnect:null, eventRefreshTimer:null, eventKeys:new Set(), eventKeyOrder:[], adminByChat:new Map(), adminScanAttempted:new Set(), adminScanFailures:new Map(), adminCheckedAt:new Map(), adminRequestToken:0, lastRolesAt:0, lastRolesChatId:'', lastRolesAppid:'', botIsAdmin:false, botRole:'', adChatId:'', adEnabled:false, adEditable:false, adLoading:false, adSaving:false, panSelectionData:null, panSelectionRequest:0, panSelectionLoading:false, panSelectionSaving:false, profiles:{}, pastedImage:null, pastedImageFile:null, pastedImageSource:'', mediaData:null, mediaFile:null, mediaName:'', mediaType:0, mediaMime:'', composerSelection:null, sending:false, optimisticSends:new Map(), optimisticSeq:0, multi:false, selected:new Set(), ctxMsg:null, ctxUser:null };
      const syncMsgGroupingToggle = () => {
        const button = $('msg-list-group-toggle');
        if (!button) return;
        button.hidden = msgState.filter !== 'all';
        button.setAttribute('aria-pressed', String(msgState.grouped));
      };
      const msgScopeKey = (type, id, appid = msgState.selectedAppid) => JSON.stringify([String(appid || '').trim(), String(type || 'group'), String(id || '')]);
      const msgChatKey = (chat) => msgScopeKey(chat?.chat_type, chat?.chat_id, chat?.appid);
      const msgInSelectedBot = (source) => Boolean(msgState.selectedAppid) && String(source?.appid || '').trim() === msgState.selectedAppid;
      const msgReadAgain = new Set();
      const msgReadOverrides = new Map();
      const applyMsgReadOverride = (chat) => {
        const scope = msgChatKey(chat);
        const override = msgReadOverrides.get(scope);
        if (!override) return chat;
        const lastTs = Number(chat?.last_ts || 0);
        if (Number(chat?.unread || 0) > 0 && lastTs > Number(override.lastTs || 0)) {
          msgReadOverrides.delete(scope);
          return chat;
        }
        if (lastTs > Number(override.lastTs || 0)) {
          override.lastTs = lastTs;
        }
        return Number(chat?.unread || 0) > 0 ? {...chat, unread:0} : chat;
      };
      const rememberMsgRead = (chatType, chatId, appid) => {
        const scope = msgScopeKey(chatType, chatId, appid);
        const matches = (chat) => chat && String(chat.chat_id || '') === String(chatId)
          && chat.chat_type === chatType && String(chat.appid || '').trim() === String(appid || '').trim();
        const current = msgState.chats.find(matches);
        const overlay = msgState.realtimeChats.get(scope);
        const latest = !overlay ? current : !current ? overlay
          : Number(overlay.last_ts || 0) >= Number(current.last_ts || 0) ? overlay : current;
        msgReadOverrides.delete(scope);
        msgReadOverrides.set(scope, {
          lastTs:Number(latest?.last_ts || 0),
        });
        while (msgReadOverrides.size > 2048) msgReadOverrides.delete(msgReadOverrides.keys().next().value);
      };
      const msgMatchesCurrent = (type, id, appid) => msgState.chatType === type && msgState.chatId === String(id || '')
        && Boolean(appid) && String(appid) === msgState.chatAppid && String(appid) === msgState.selectedAppid;
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
      const msgLayout = {listWidth:273, composerHeight:173, listCollapsed:false, composerCollapsed:false, loaded:false, persisted:false, revision:0, saveTimer:null};
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
          listWidth:Number.isFinite(width) ? Math.max(220, Math.min(680, width)) : 273,
          composerHeight:Number.isFinite(height) ? Math.max(123, Math.min(420, height)) : 173,
          listCollapsed:bool(data.list_collapsed ?? data.listCollapsed),
          composerCollapsed:bool(data.composer_collapsed ?? data.composerCollapsed),
        };
      };
      const applyMsgLayout = (value = {}, persist = false) => {
        const next = normalizeMsgLayout(value);
        msgLayout.revision += 1;
        Object.assign(msgLayout, next);
        const shell = $('msg-shell');
        if (shell) {
          shell.style.setProperty('--msg-list-width', `${next.listWidth}px`);
          shell.classList.toggle('msg-list-collapsed', next.listCollapsed);
          shell.classList.toggle('msg-composer-collapsed', next.composerCollapsed);
          shell.classList.toggle('msg-composer-compact', !next.composerCollapsed && next.composerHeight < 150);
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
        if (!msgLayout.loaded || !consoleAppid) return;
        if (msgLayout.saveTimer) clearTimeout(msgLayout.saveTimer);
        const appid = consoleAppid, generation = consoleGeneration, revision = msgLayout.revision;
        const layout = {list_width:msgLayout.listWidth, composer_height:msgLayout.composerHeight,
          list_collapsed:msgLayout.listCollapsed, composer_collapsed:msgLayout.composerCollapsed};
        msgLayout.saveTimer = setTimeout(async () => {
          msgLayout.saveTimer = null;
          if (appid !== consoleAppid || generation !== consoleGeneration) return;
          try {
            const data = await api('message/layout', {method:'POST', body:JSON.stringify(layout)});
            msgLayout.persisted = Boolean(data.persisted);
            if (data.layout && revision === msgLayout.revision) applyMsgLayout(data.layout, false);
          } catch (error) {
            if (error.name !== 'AbortError' && error.status !== 409 && error.status !== 401) toast('消息布局保存失败');
          }
        }, 280);
      };
      const loadMsgLayout = async () => {
        if (!consoleAppid) return;
        const appid = consoleAppid, generation = consoleGeneration;
        msgLayout.loaded = false;
        applyMsgLayout();
        try {
          const data = await api('message/layout');
          msgLayout.persisted = Boolean(data.persisted);
          applyMsgLayout(data.layout || {});
          if (appid === consoleAppid && generation === consoleGeneration) {
            msgLayout.loaded = true;
          }
        } catch (_) {}
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
      const msgNicknameState = (source, id) => {
        if (!source || typeof source !== 'object') return null;
        const live = Object.prototype.hasOwnProperty.call(source, '_private_nickname')
          || Object.prototype.hasOwnProperty.call(source, '_private_nickname_blank');
        const raw = live ? source._private_nickname : (source.nickname || source.username);
        const blank = (live ? source._private_nickname_blank : source.nickname_blank) === true || isBlankMsgNickname(raw);
        const nickname = blank ? '' : validMsgNickname(raw, id);
        if (!blank && !nickname) return null;
        const ts = Number(live ? source._private_nickname_ts : (source.nickname_ts ?? source.ts ?? 0));
        return {nickname, nickname_blank:blank, nickname_ts:Number.isFinite(ts) && ts > 0 ? ts : 0};
      };
      const pickMsgNicknameState = (id, ...sources) => sources.reduce((current, source) => {
        const next = msgNicknameState(source, id);
        return next && (!current || next.nickname_ts > current.nickname_ts
          || (next.nickname_ts === current.nickname_ts && (!current.nickname_blank || next.nickname_blank))) ? next : current;
      }, null);
      const msgPrivateContactScope = (id, source = {}) => msgState.chatType === 'user'
        && String(id || '') === String(msgState.chatId || '')
        && (!source.user_id || String(source.user_id) === String(id || ''))
        && (!source.chat_type || source.chat_type === 'user')
        && (!source.appid || String(source.appid).trim() === String(msgState.chatAppid || '').trim())
        && (!source.chat_id || String(source.chat_id) === String(msgState.chatId || ''))
        && (!source._session || String(source._session) === String(msgState.chatId || ''))
        && !source.group_id && !source.group_openid && !source.is_self && source.is_bot !== true
        && !String(source.source || '').startsWith('bot_') && source.source !== 'web_panel';
      const displayMsgNickname = (message, profile = {}, fallback = '未知用户') => {
        const id = message?.user_id || '';
        if (msgState.chatType === 'user' && String(id) === String(msgState.chatId || '')
          && !msgPrivateContactScope(id, profile)) profile = {};
        if (msgPrivateContactScope(id, message || {})) {
          const current = pickMsgNicknameState(id,
            msgPrivateContactScope(id, profile) ? profile : null,
            msgState.realtimeChats.get(msgScopeKey('user', id, msgState.chatAppid)));
          if (message?.nickname_blank === true || isBlankMsgNickname(message?.nickname) || current?.nickname_blank) return '\u00a0';
        }
        const name = validMsgNickname(message?.nickname, id)
          || validMsgNickname(profile.nickname || profile.username, id);
        return name || (message?.nickname_blank || profile.nickname_blank || isBlankMsgNickname(message?.nickname) ? '\u00a0' : fallback);
      };
      const msgLivePrivateNickname = (chat, id) => chat?._private_nickname_blank === true
        ? '\u00a0' : validMsgNickname(chat?._private_nickname, id);
      const mergeMsgProfileMaps = (...sources) => {
        const merged = {};
        sources.forEach((source) => {
          Object.entries(source || {}).forEach(([id, profile]) => {
            if (!profile || typeof profile !== 'object') return;
            const key = String(id || '').trim();
            if (!key) return;
            const isPrivateContact = msgState.chatType === 'user' && key === String(msgState.chatId || '');
            if (isPrivateContact && !msgPrivateContactScope(key, profile)) return;
            const next = {...(merged[key] || {})};
            const nameState = isPrivateContact ? pickMsgNicknameState(key, next, profile) : null;
            Object.entries(profile).forEach(([field, value]) => {
              if (isPrivateContact && ['nickname','username','nickname_blank','nickname_ts'].includes(field)) return;
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
            if (isPrivateContact && nameState) Object.assign(next, nameState, {username:nameState.nickname});
            else if (!isPrivateContact && validMsgNickname(next.nickname || next.username, key)) next.nickname_blank = false;
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
      const normalizeMsgMemberRole = (value) => {
        const role = String(value || '').trim().toLowerCase();
        return ({owner:'owner', '群主':'owner', admin:'admin', '管理员':'admin', '群管理员':'admin', member:'member', '普通成员':'member', '群成员':'member'})[role] || '';
      };
      const currentBotMemberRole = (message, isSelf) => {
        const appid = String(msgState.chatAppid || '').trim();
        if (!isSelf || msgState.chatType !== 'group' || !appid || String(message?.appid || '').trim() !== appid) return '';
        return normalizeMsgMemberRole(msgState.botRole) || (msgState.botIsAdmin ? 'admin' : '');
      };
      const msgMemberRole = (message, profile = {}) => {
        const appid = String(message?.appid || msgState.chatAppid || '').trim();
        if (msgState.chatAppid && appid !== String(msgState.chatAppid)) return '';
        const profileMatches = (!profile.appid || String(profile.appid).trim() === appid)
          && (!profile.group_id || String(profile.group_id).trim() === String(msgState.chatId))
          && (!profile.group_openid || String(profile.group_openid).trim() === String(msgState.chatId));
        for (const value of [message?.member_role, profileMatches ? profile.role : '', profileMatches ? profile.member_role : '']) {
          const role = normalizeMsgMemberRole(value);
          if (role) return role;
        }
        return '';
      };
      const mergeMsgProfiles = (profiles, messages = []) => {
        const merged = mergeMsgProfileMaps(profiles);
        (messages || []).forEach((message) => {
          const source = String(message?.source || '');
          if (message?.is_self || source.startsWith('bot_') || source === 'web_panel') return;
          const id = String(message?.user_id || '').trim();
          const isPrivateContact = msgState.chatType === 'user' && id === String(msgState.chatId || '');
          if (isPrivateContact && !msgPrivateContactScope(id, message)) return;
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
            ...(isPrivateContact ? {appid:message.appid || msgState.chatAppid, chat_type:'user', nickname_ts:Number(message.nickname_ts ?? message.ts ?? 0)} : {}),
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
        if (msgPrivateContactScope(id, profile) && msgNicknameState(profile, id)?.nickname_blank) return '\u00a0';
        const nickname = validMsgNickname(profile.nickname || profile.username, id);
        if (nickname) return nickname;
        if (profile.nickname_blank || isBlankMsgNickname(profile.nickname || profile.username)) return '\u00a0';
        return '用户';
      };
      const replaceMsgMentions = (value, profiles = msgState.profiles) => String(value || '').replace(/@+(?=<@(?:!?[A-Za-z0-9_-]{5,128}|all)>)/gi, '').replace(/<@all>/gi, '@全体成员').replace(/<@!?([A-Za-z0-9_-]{5,128})>/g, (_, openid) => `@${resolveMentionName(openid, profiles)}`);
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
        const mentionToken = (label) => commandToken('mention', '', String(label || '用户'));
        let source = String(value || '').replace(/@+(?=<@(?:!?[A-Za-z0-9_-]{5,128}|all)>)/gi, '');
        source = source.replace(/<@all>/gi, () => mentionToken('全体成员'));
        source = source.replace(/<@!?([A-Za-z0-9_-]{5,128})>/g, (_, id) => mentionToken(resolveMentionName(id, profiles)));
        source = source.replace(/@全体成员/g, () => mentionToken('全体成员'));
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
          return id ? mentionToken(resolveMentionName(id, profiles)) : '';
        });
        source = source.replace(/<qqbot-at-everyone\s*\/?\s*>/gi, () => mentionToken('全体成员'));
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
          if (item.kind === 'mention') return `<span class="msg-mention-chip"><span class="msg-mention-marker" aria-hidden="true">@</span><span>${esc(item.label)}</span></span>`;
          if (item.kind === 'image') return renderMessageMedia({type:'图片', src:item.command});
          return `<button type="button" class="msg-command-chip" data-msg-command="${esc(item.command)}" data-msg-command-kind="${esc(item.kind)}" aria-label="${esc(item.label)}">${esc(item.label)}</button>`;
        });
      };
      const renderMsgKeyboardButtons = (value) => {
        if (!Array.isArray(value)) return '';
        const rows = value.slice(0, 5).map((row) => (Array.isArray(row) ? row : []).slice(0, 5).map((item) => {
          const label = String(item?.label || '').trim();
          if (!label || label.length > 120) return '';
          let url = '';
          if (item?.kind === 'link') {
            try {
              const parsed = new URL(String(item.url || ''), location.href);
              if (['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password) url = parsed.href;
            } catch (_) {}
            if (!url) return '';
            return `<a class="msg-inline-keyboard-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/><path d="M8 12h8"/></svg><span>${esc(label)}</span></a>`;
          }
          if (item?.kind === 'preview') return `<span class="msg-inline-keyboard-button" aria-disabled="true">${esc(label)}</span>`;
          return '';
        })).map((items) => items.filter(Boolean)).filter((items) => items.length);
        if (!rows.length) return '';
        return `<div class="msg-inline-keyboard" role="group" aria-label="QQ消息按钮">${rows.map((items) => `<div class="msg-inline-keyboard-row" style="--msg-keyboard-cols:${items.length}">${items.join('')}</div>`).join('')}</div>`;
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
        const privateBlank = msgPrivateContactScope(id, message) && (message.nickname_blank === true
          || isBlankMsgNickname(message.nickname) || pickMsgNicknameState(id,
            msgPrivateContactScope(id, profile) ? profile : null,
            msgState.realtimeChats.get(msgScopeKey('user', id, msgState.chatAppid)))?.nickname_blank);
        const nickname = privateBlank ? '\u00a0' : previewOnly
          ? (validMsgNickname(message.nickname, id) || (id ? validMsgNickname(profile.nickname || profile.username, id) : ''))
          : (own
            ? (validMsgNickname(botProfileForAppid(message.appid || msgState.chatAppid).username, id) || validMsgNickname(message.nickname, id) || '机器人')
            : displayMsgNickname(message, profile));
        return {
          preview_only:previewOnly,
          // `id` is a local database row key, not a QQ message locator.
          message_id:previewOnly ? '' : String(message.message_id || '').trim(),
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
      const findLocatedMsgReference = (messages, data) => {
        const messageId = String(data?.located_message_id || '').trim();
        const refidx = String(data?.located_refidx || '').trim();
        const matches = messageId
          ? messages.filter((message) => String(message.message_id || '').trim() === messageId)
          : refidx
            ? messages.filter((message) => String(message.refidx || '').trim() === refidx)
            : [];
        return matches.length === 1 ? {message:matches[0], messageId, refidx} : null;
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
          const located = findLocatedMsgReference(messages, data);
          if (!located
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
          const targetRow = located.messageId
            ? findMsgReferenceRow('', located.messageId)
            : findMsgReferenceRow(located.refidx);
          if (!targetRow) { toast('暂未匹配到原消息'); return; }
          highlightMsgReference(targetRow, 'auto');
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
          last_record_id:Number(message.id || 0),
          history_origin:String(message.history_origin || ''),
          history_order:Number(message.history_order || 0),
        };
      };
      const msgComposerTabs = [['text','文本'],['markdown','Markdown'],['media','媒体'],['ark','ARK模板'],['card','图文卡片']];
      const msgFilterLabels = { all:'全量', remark:'备注', group:'群聊', user:'私聊' };
      const avatarUrl = (openid, type, appid) => {
        const id = String(openid || '').trim();
        if (!id) return '';
        if (type === 'group') { const qq = window.msgGroupQQ?.[id] || ''; return /^\d{5,12}$/.test(String(qq)) ? `https://p.qlogo.cn/gh/${qq}/${qq}/100/` : ''; }
        const aid = String(appid || '').trim();
        // QQ 官方群成员使用 AppID 作用域 OpenID；腾讯官方 qlogo
        // 接口接受该 OpenID，不能先按 QQ 号数字格式过滤。
        return /^\d{4,32}$/.test(aid) ? `https://q.qlogo.cn/qqapp/${encodeURIComponent(aid)}/${encodeURIComponent(id)}/0` : '';
      };
      const avatarImg = (url, letter, className = '', appid = consoleAppid) => {
        const source = mediaProxyUrl(url, 'image', '', appid);
        const nonce = Number(msgState.avatarRefresh?.get(String(url)) || 0);
        const refreshed = nonce && source.startsWith('/api/') ? source + '&avatar_refresh=' + nonce : source;
        return `<img class="${esc(className)}" src="${esc(refreshed)}" data-avatar-direct="${esc(url)}" alt="" loading="lazy" decoding="async" fetchpriority="low" referrerpolicy="no-referrer" onerror="if(this.dataset.avatarRetried!=='1' && this.getAttribute('src')!==this.dataset.avatarDirect){this.dataset.avatarRetried='1';this.src=this.dataset.avatarDirect;return;}const box=this.closest('.msg-chat-avatar, .msg-avatar, .msg-mention-avatar, .bot-selector-avatar, .bot-avatar');box?.classList.add('avatar-fallback');box?.classList.remove('has-image');this.remove();">`;
      };
      const avatarHtml = (url, letter, appid = consoleAppid) => {
        const firstLetter = Array.from(String(letter || '?'))[0];
        if (!url) return esc(firstLetter);
        return `<span class="avatar-letter">${esc(firstLetter)}</span>` + avatarImg(url, letter, '', appid);
      };
      const botProfileForAppid = (appid) => {
        const id = String(appid || '').trim();
        return id ? (window.msgBotProfiles || []).find((profile) => profile.appid === id) || {} : {};
      };
      const switchMsgBotScope = (appid) => {
        const next = /^\d{4,32}$/.test(String(appid || '').trim()) ? String(appid).trim() : '';
        if (next === msgState.selectedAppid) return;
        closeMsgHeadMenu(); closeAdminPopover();
        msgState.scopeGeneration += 1;
        for (const key of ['historyAbort','historyOlderAbort','chatListAbort']) { msgState[key]?.abort(); msgState[key] = null; }
        msgState.historyRequest += 1; msgState.historyOlderRequest += 1; msgState.chatListRequest += 1; msgState.historyScheduleToken += 1;
        if (msgState.historyScheduleFrame != null) { cancelAnimationFrame(msgState.historyScheduleFrame); msgState.historyScheduleFrame = null; }
        cancelMsgQuoteJump(true); stopMsgGroupSnapshots(); cancelMsgRealtimeMessageRender(); closeComposerMentionPicker();
        if (autoScanAdminTimer) { clearTimeout(autoScanAdminTimer); autoScanAdminTimer = null; }
        if (msgState.chatRenderTimer) { clearTimeout(msgState.chatRenderTimer); msgState.chatRenderTimer = null; }
        if (msgState.chatListScrollTimer) { clearTimeout(msgState.chatListScrollTimer); msgState.chatListScrollTimer = null; }
        closeGroupSettings(true); groupSettingsState.remarkTarget = null;
        msgModalIds.forEach((id) => setMsgModal(id, false));
        hideMsgCtx();
        if (msgState.multi) exitMultiMode();
        Object.assign(msgState, {
          selectedAppid:next, grouped:false, chatId:'', chatType:'group', chatAppid:next, chatRemoved:false, chats:[], messages:[], profiles:{},
          historyData:null, historyWindow:null, historyActiveScope:'', historyOlderLoading:false, renderedChatId:'', messageRenderSignature:null,
          initialScrollChatId:'', chatListPromise:null, chatListKey:'', chatListRendered:false, chatListServerLoaded:false,
          chatListTopPending:true, chatListScrollActive:false, chatListPointerActive:false, chatListPendingData:null,
          chatListRows:[], chatListOffsets:[0], chatListContentHeight:0, chatListWindowStart:-1, chatListWindowEnd:-1, chatRenderSignature:null,
          adminRequestToken:msgState.adminRequestToken + 1, lastRolesAt:0, lastRolesChatId:'', lastRolesAppid:'', botIsAdmin:false, botRole:'',
          panSelectionRequest:msgState.panSelectionRequest + 1, panSelectionData:null, panSelectionSaving:false, panSelectionLoading:false,
          adChatId:'', adEnabled:false, adEditable:false, adLoading:false, adSaving:false, mute:{member:'',name:''}, mutes:new Map(), muteRequestAt:0,
        });
        for (const key of ['realtimeChats','groupMembership','adminByChat','adminScanAttempted','adminScanFailures','adminCheckedAt']) msgState[key].clear();
        clearMsgNewMessages(); resetComposer(); resetMsgAdSwitch(); updateMsgPanSelector(); syncMsgGroupingToggle();
        const body = $('msg-body');
        if (body) { cancelMsgBottomPosition(body, true); body.innerHTML = '<div class="msg-empty">请在左侧选择会话</div>'; }
        $('msg-head-name').textContent = '请选择会话'; $('msg-head-sub').textContent = '';
        $('msg-head-name').removeAttribute('title'); $('msg-head-sub').removeAttribute('title');
        $('msg-head-name').disabled = true; $('msg-head-name').setAttribute('aria-expanded','false'); $('msg-head-name').removeAttribute('aria-label');
        for (const id of ['msg-composer','msg-refresh-info','msg-remark','msg-group-settings-open','msg-ad-switch']) $(id).hidden = true;
        $('msg-chats').innerHTML = next ? '<div class="msg-empty">正在加载会话…</div>' : '<div class="msg-empty">请先选择机器人</div>';
        window.msgGroupQQ = {}; msgLastPollAt = 0;
        if (next && !$('page-messages')?.hidden) void loadMsgChats(true);
      };
      const showBotPicker = (message = '') => {
        setMessagesWorkspace(false);
        document.querySelector('.shell')?.classList.add('bot-picker-open');
        $('console-sidebar').hidden = true; $('console-workspace').hidden = true; $('bot-picker').hidden = false;
        $('bot-picker-error').textContent = message; $('bot-picker-error').hidden = !message;
        document.title = '选择机器人 · 馒头控制台';
        $('updated').textContent = '--';
      };
      const exitBotConsole = (push = true) => {
        clearSavedCredential();
        // 先绑定原账号发出清理，再废弃旧请求及内存；退出不退出管理员登录。
        void stopQuarkWebScan(); leaveQQReader(); leaveJinjiang(); stopZLibraryAccount(true); closeMsgEvents();
        ++consoleGeneration;
        for (const controller of consoleRequests) controller.abort();
        consoleRequests.clear();
        consoleEntering = false; consoleAppid = '';
        databaseTestState.generation += 1; databaseTestState.abort?.abort(); databaseTestState.abort = null;
        snapshot = null; activeView = null; activePanTab = null; activePanObject = null;
        quarkProfileRefreshAfter = 0; quarkProfileRefreshPromise = null;
        qqReader.request += 1; qqReader.keyRequest += 1; qqReader.auth = null; qqReader.mutation = false;
        qqReader.detailId = ''; qqReader.adding = false; qqReader.modalRestoreFocus = false; qqReader.method = 'cookie';
        clearQQReaderManual(); syncQQReaderModal();
        jinjiang.auth = null; jinjiang.method = 'scan';
        if ($('jinjiang-accounts')) $('jinjiang-accounts').replaceChildren();
        if ($('jinjiang-summary')) $('jinjiang-summary').textContent = '正在读取账号…';
        if ($('jinjiang-detail')) $('jinjiang-detail').replaceChildren();
        switchMsgBotScope(''); setMsgMobileChatOpen(false);
        msgState.historyCache.clear(); msgState.readInFlight.clear(); msgReadAgain.clear(); msgReadOverrides.clear(); msgState.optimisticSends.clear();
        msgState.eventKeys.clear(); msgState.eventKeyOrder = []; msgState.sending = false;
        if (msgLayout.saveTimer) clearTimeout(msgLayout.saveTimer);
        msgLayout.saveTimer = null; msgLayout.loaded = false; msgLayout.persisted = false; applyMsgLayout();
        window.msgBotProfile = {};
        clearTimeout(toastTimer); $('toast').classList.remove('show'); $('toast').textContent = '';
        if ($('toast').parentElement !== document.body) document.body.appendChild($('toast'));
        document.querySelectorAll('#console-workspace input,#console-workspace textarea,#qq-reader-account-dialog input,#jinjiang-account-dialog input').forEach((node) => { node.value = ''; });
        for (const id of ['pan-grid','basic-config-editor','database-config-editor']) if ($(id)) $(id).replaceChildren();
        showNotice(''); showBotPicker(); renderBotProfiles();
        document.querySelectorAll('[data-page]').forEach((node) => { node.hidden = true; });
        for (const url of browserMediaObjectUrls.values()) { try { URL.revokeObjectURL(url); } catch (_) {} }
        browserMediaObjectUrls.clear();
        if (push) {
          const params = new URLSearchParams(location.search); params.delete('appid'); params.delete('view');
          history.pushState({}, '', `${location.pathname}${params.size ? '?' + params.toString() : ''}`);
          $('bot-picker-title').focus?.({preventScroll:true});
        }
      };
      const enterBotConsole = async (profile, push = true) => {
        const appid = String(profile?.appid || '').trim();
        if (consoleEntering || !/^\d{4,32}$/.test(appid)) return;
        if (consoleAppid && consoleAppid !== appid) exitBotConsole(false);
        consoleEntering = true; consoleAppid = appid; ++consoleGeneration;
        const generation = consoleGeneration;
        showBotPicker(); $('bot-profile-list').setAttribute('aria-busy', 'true'); renderBotProfiles();
        applyBotProfile(profile);
        try {
          const data = await api('dashboard');
          if (generation !== consoleGeneration || appid !== consoleAppid) return;
          if (String(data.bot?.appid || data.appid || appid) !== appid) throw new Error('机器人资料不匹配，请重新选择');
          render(data);
          $('bot-picker').hidden = true; $('console-sidebar').hidden = false; $('console-workspace').hidden = false;
          document.querySelector('.shell')?.classList.remove('bot-picker-open');
          document.title = `${window.msgBotProfile.username || '机器人'} · 馒头控制台`;
          const params = new URLSearchParams(location.search); params.set('appid', appid);
          const view = push ? 'dashboard' : viewFromUrl(); params.set('view', view);
          if (push) history.pushState({appid,view}, '', `${location.pathname}?${params.toString()}`);
          else history.replaceState({appid,view}, '', `${location.pathname}?${params.toString()}`);
          setView(view, false); void loadMsgLayout();
          if ($('popover-logout')) $('popover-logout').hidden = false;
          $('page-title').tabIndex = -1; $('page-title').focus({preventScroll:true});
        } catch (error) {
          if (generation !== consoleGeneration || error.name === 'AbortError') return;
          exitBotConsole(false);
          showBotPicker(error.status === 401 ? '登录已过期，请重新登录。' : (error.message || '机器人控制台暂时不可用，请重试。'));
          if (error.status === 401) showAuthError(error);
        } finally {
          if (generation === consoleGeneration) consoleEntering = false;
          $('bot-profile-list').removeAttribute('aria-busy'); renderBotProfiles();
        }
      };
      const botStatusLabel = (status) => ({running:'运行中', pending:'连接中', error:'连接异常', stopped:'已停止', disabled:'已停用'})[status] || '状态未知';
      const botPickerStatusLabel = (profile) => ({running:'在线', pending:'连接中', error:'离线（连接异常）', stopped:'离线（已停止）', disabled:'离线（已停用）'})[profile.status] || '状态未知';
      const botStatValue = (value) => Number.isSafeInteger(value) && value >= 0 ? value.toLocaleString('zh-CN') : '—';
      const renderBotProfiles = () => {
        const host = $('bot-profile-list');
        if (!host) return;
        const profiles = window.msgBotProfiles || [];
        host.innerHTML = profiles.map((profile) => {
          const name = profile.username || profile.platform_id || 'QQ官方机器人';
          const available = /^\d{4,32}$/.test(profile.appid);
          const status = consoleEntering && profile.appid === consoleAppid ? '正在进入…' : !available ? '等待认证' : botPickerStatusLabel(profile);
          const stats = profile.stats || {};
          return `<button type="button" class="bot-selector-item" data-bot-select="${esc(profile.key)}" data-bot-unavailable="${!available}" aria-label="进入${esc(name)}控制台${profile.appid ? '，AppID ' + esc(profile.appid) : ''}" title="${esc(profile.appid ? 'AppID：' + profile.appid : '等待机器人认证')}" ${consoleEntering || !available ? 'disabled' : ''}><span class="bot-selector-avatar">${avatarHtml(profile.avatar, name, profile.appid)}</span><span class="bot-selector-copy"><span class="bot-selector-title"><strong>${esc(name)}</strong></span><small><span class="bot-selector-status ${profile.status === 'running' ? 'is-running' : ''}">${esc(status)}</span></small></span><span class="bot-selector-arrow" aria-hidden="true"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7 4 6 6-6 6"/></svg></span><span class="bot-selector-stats"><span class="bot-selector-stat"><svg viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="7.5" cy="6" r="2.5"/><path d="M2.5 16v-2a5 5 0 0 1 10 0v2h-10Zm11-12a2.5 2.5 0 0 1 0 5m1 2a4 4 0 0 1 3 4v1h-2"/></svg><span>已记录群聊</span><strong data-bot-stat="groups">${esc(botStatValue(stats.group_count))}</strong></span><span class="bot-selector-stat"><svg viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="6" r="3"/><path d="M4 17v-2a6 6 0 0 1 12 0v2"/></svg><span>已记录用户</span><strong data-bot-stat="users">${esc(botStatValue(stats.user_count))}</strong></span></span></button>`;
        }).join('') || '<span class="bot-selector-empty">暂无已加载机器人</span>';
        host.querySelectorAll('[data-bot-select]').forEach((button) => button.addEventListener('click', () => {
          const profile = profiles.find((item) => item.key === button.dataset.botSelect);
          if (profile) void enterBotConsole(profile);
        }));
      };
      const applyBotProfile = (profile = {}, refreshMessages = false) => {
        const data = profile && typeof profile === 'object' ? profile : {};
        const name = String(data.username || data.name || '').trim() || '馒头助手';
        const avatar = safeMediaUrl(String(data.avatar || data.avatar_url || '').trim());
        const id = String(data.id || '').trim();
        if (!consoleAppid || String(data.appid || '') !== consoleAppid) return;
        switchMsgBotScope(consoleAppid);
        window.msgBotProfile = {...data, id, username:name, avatar};
        document.querySelectorAll('[data-bot-name]').forEach((node) => { node.textContent = name; });
        document.querySelectorAll('[data-bot-id]').forEach((node) => { node.textContent = id || '由适配器提供'; });
        document.querySelectorAll('[data-bot-status]').forEach((node) => {
          node.textContent = botStatusLabel(data.status);
          node.classList.toggle('online', data.status === 'running');
        });
        document.querySelectorAll('[data-bot-avatar]').forEach((node) => {
          node.classList.toggle('has-image', Boolean(avatar));
          if (!avatar) { node.innerHTML = '<span class="avatar-face">•ᴗ•</span>'; return; }
          node.innerHTML = `<span class="avatar-face">${esc(Array.from(name)[0] || '机')}</span>` + avatarImg(avatar, name, 'bot-avatar-image');
        });
        const hasMessageData = msgState.historyData
          || (Array.isArray(msgState.messages) && msgState.messages.length)
          || Number(msgState.optimisticSends?.size || 0) > 0;
        if (refreshMessages && msgState.chatId && hasMessageData && typeof renderMsgMessages === 'function') {
          const body = $('msg-body');
          renderMsgMessages(
            {...msgState.historyData, messages:msgState.messages},
            {previousTop:body?.scrollTop || 0, previousHeight:body?.scrollHeight || 0, forceRender:true},
          );
        }
      };
      let botProfileRequest = null;
      let botProfileLoadedAt = 0;
      const loadBotProfile = async () => {
        if (botProfileRequest) return botProfileRequest;
        if (Date.now() - botProfileLoadedAt < 60000) return;
        botProfileRequest = (async () => {
        try {
          const data = await api('bot-profile');
          const profiles = Array.isArray(data.profiles) ? data.profiles : (data.profile?.appid ? [data.profile] : []);
          const previousProfiles = JSON.stringify(window.msgBotProfiles || []);
          window.msgBotProfiles = profiles.filter((profile) => profile && typeof profile === 'object').map((profile, index) => ({
            ...profile,
            appid:String(profile.appid || '').trim(),
            avatar:safeMediaUrl(String(profile.avatar || profile.avatar_url || '').trim()),
            key:String(profile.appid || profile.platform_id || `bot-${index}`),
          }));
          renderBotProfiles();
          const current = window.msgBotProfiles.find((profile) => profile.appid === consoleAppid);
          if (current) applyBotProfile(current, previousProfiles !== JSON.stringify(window.msgBotProfiles));
          else if (consoleAppid && !consoleEntering) { exitBotConsole(false); showBotPicker('当前机器人已停止加载，请重新选择。'); }
          botProfileLoadedAt = Date.now();
          if (data.version) $('console-version').textContent = `v${data.version}`;
          if ($('popover-logout')) $('popover-logout').hidden = false;
        } catch (error) {
          if (error.status === 401) showAuthError(error);
          else if (!consoleAppid) showBotPicker('机器人列表读取失败，请点击刷新列表重试。');
        }
        })().finally(() => { botProfileRequest = null; });
        return botProfileRequest;
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
      const msgKnownGroupMemberCount = (...values) => {
        for (const value of values) {
          if (typeof value !== 'number' && typeof value !== 'string') continue;
          if (typeof value === 'string' && !/^[0-9]+$/.test(value.trim())) continue;
          const count = Number(value);
          if (Number.isSafeInteger(count) && count > 0) return count;
        }
        return null;
      };
      const msgChatMatchesView = (chat, {ignoreTypeFilter = false} = {}) => {
        if (!msgInSelectedBot(chat)) return false;
        const type = String(chat.chat_type || 'group');
        if (!ignoreTypeFilter && msgState.filter === 'group' && type !== 'group') return false;
        if (!ignoreTypeFilter && msgState.filter === 'user' && type !== 'user') return false;
        if (!ignoreTypeFilter && msgState.filter === 'remark' && !chat.remark) return false;
        const keyword = String(msgState.search || '').trim().toLowerCase();
        if (!keyword) return true;
        return [chat.nickname, chat.remark, chat.chat_id].some((value) => String(value || '').toLowerCase().includes(keyword));
      };
      const readMsgGroupState = (source = {}) => {
        const explicit = String(source?.membership_status || '').trim().toLowerCase();
        const inGroup = source?.in_group ?? source?.bot_in_group;
        const status = ['active','removed','unknown'].includes(explicit) ? explicit : inGroup === false ? 'removed' : inGroup === true ? 'active' : '';
        if (!status) return null;
        const checked = Number(source?.membership_checked_at || 0);
        const revision = Number(source?.membership_revision || 0);
        const origin = String(source?.membership_source || '').trim();
        const dismiss = status === 'removed' && origin === 'GROUP_DEL_ROBOT'
          && typeof source?.membership_dismiss === 'boolean' ? source.membership_dismiss : null;
        return {
          membership_status:status,
          membership_source:origin,
          membership_dismiss:dismiss,
          membership_checked_at:Number.isFinite(checked) && checked > 0 ? checked : 0,
          membership_revision:Number.isSafeInteger(revision) && revision > 0 ? revision : (Number.isFinite(checked) && checked > 0 ? checked * 1000 : 0),
          in_group:status === 'unknown' ? null : status === 'active',
        };
      };
      const pickMsgGroupState = (current = {}, incoming = {}) => {
        const previous = readMsgGroupState(current), next = readMsgGroupState(incoming);
        if (!previous) return next || {membership_status:'unknown', membership_source:'', membership_dismiss:null, membership_checked_at:0, membership_revision:0, in_group:null};
        if (!next || next.membership_revision < previous.membership_revision) return previous;
        if (next.membership_revision === previous.membership_revision && previous.membership_status !== 'unknown') return previous;
        return next;
      };
      const syncMsgGroupState = (chatId, incoming = {}, appid = msgState.selectedAppid) => {
        chatId = String(chatId || '').trim(); appid = String(appid || '').trim();
        if (!chatId || !appid || appid !== msgState.selectedAppid) return pickMsgGroupState();
        const matches = (source) => source && (!source.chat_id || String(source.chat_id) === chatId)
          && (!source.chat_type || source.chat_type === 'group') && (!source.appid || String(source.appid).trim() === appid)
          && (!source.group_openid || String(source.group_openid) === chatId);
        const scope = msgScopeKey('group', chatId, appid);
        const current = msgState.chats.find((chat) => chat.chat_type === 'group' && String(chat.chat_id || '') === chatId && matches(chat));
        const overlay = msgState.realtimeChats.get(scope);
        const viewing = msgState.chatType === 'group' && msgState.chatId === chatId && msgState.chatAppid === appid;
        let state = pickMsgGroupState(msgState.groupMembership.get(scope), current);
        if (matches(overlay)) state = pickMsgGroupState(state, overlay);
        if (viewing) state = pickMsgGroupState(state, msgState.historyData?.group_info);
        if (matches(incoming)) state = pickMsgGroupState(state, incoming);
        msgState.groupMembership.set(scope, state);
        if (current) Object.assign(current, state);
        if (matches(overlay)) msgState.realtimeChats.set(scope, {...overlay, ...state});
        if (viewing && msgState.historyData) msgState.historyData = {...msgState.historyData, group_info:{...(msgState.historyData.group_info || {}), ...state}};
        return state;
      };
      const msgChatIsRemoved = (chat) => String(chat?.chat_type || 'group') === 'user'
        ? (String(chat?.friend_status || '').toLowerCase() === 'removed' || chat?.is_friend === false)
        : readMsgGroupState(chat)?.membership_status === 'removed';
      const msgChatRemovedText = (chat = {}) => {
        if (String(chat.chat_type || 'group') === 'user') return '对方已删除机器人好友';
        const state = readMsgGroupState(chat);
        if (state?.membership_status === 'removed' && state.membership_source === 'GROUP_DEL_ROBOT') {
          if (state.membership_dismiss === true) return '群已解散';
          if (state.membership_dismiss === false) return '你已被移除群聊（非群解散）';
        }
        return '你已被移除群聊';
      };
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
        const overlay = msgState.realtimeChats.get(msgScopeKey('user', chatId));
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
        if (base) msgState.realtimeChats.set(msgScopeKey('user', chatId), {...base, ...state});
        if (viewing) msgState.historyData = {...(msgState.historyData || {}), ...state};
        return state;
      };
      const mergeMsgRealtimeChats = (serverChats, {serverSnapshot = false} = {}) => {
        const byId = new Map((serverChats || []).filter(msgInSelectedBot).map((chat) => [msgChatKey(chat), {
          ...chat, ...(chat.chat_type === 'group' ? syncMsgGroupState(chat.chat_id, chat, chat.appid) : {}),
        }]));
        const now = Math.floor(Date.now() / 1000);
        msgState.realtimeChats.forEach((overlay, chatKey) => {
          const chatId = String(overlay.chat_id || '');
          if (!msgInSelectedBot(overlay)) return;
          const current = byId.get(chatKey);
          if (!current) {
            if (msgChatMatchesView(overlay, {ignoreTypeFilter:true})) byId.set(chatKey, {...overlay,
              ...(overlay.chat_type === 'group' ? syncMsgGroupState(chatId, overlay, overlay.appid) : {})});
            return;
          }
          const currentAppid = String(current.appid || '').trim();
          const overlayAppid = String(overlay.appid || '').trim();
          if (String(current.chat_type || 'group') !== String(overlay.chat_type || 'group')
            || (currentAppid && overlayAppid && currentAppid !== overlayAppid)) {
            msgState.realtimeChats.delete(chatKey);
            return;
          }
          const isPrivate = String(current.chat_type || 'group') === 'user';
          const friendState = isPrivate ? pickMsgFriendState(current, overlay) : {};
          const groupState = isPrivate ? {} : syncMsgGroupState(chatId, overlay, overlayAppid || currentAppid);
          const keepFriendOverlay = isPrivate && (Number(friendState.friend_checked_at || 0) > Number(current.friend_checked_at || 0)
            || (Number(friendState.friend_checked_at || 0) === Number(current.friend_checked_at || 0) && Number(friendState._friend_live_order || 0) > Number(current._friend_live_order || 0)));
          let liveContactName = isPrivate ? msgLivePrivateNickname(overlay, chatId) : '';
          const currentContactState = isPrivate ? msgNicknameState(current, chatId) : null;
          const liveContactState = isPrivate && liveContactName ? msgNicknameState(overlay, chatId) : null;
          const serverConfirmed = currentContactState && liveContactState
            && currentContactState.nickname_blank === liveContactState.nickname_blank
            && currentContactState.nickname === liveContactState.nickname;
          // 当前作者快照按昵称时间更新；机器人最后回复的时间不代表昵称时间。
          if (serverSnapshot && liveContactState && (serverConfirmed
            || (currentContactState && currentContactState.nickname_ts > liveContactState.nickname_ts))) {
            delete overlay._private_nickname;
            delete overlay._private_nickname_blank;
            liveContactName = '';
          }
          const keepContactOverlay = Boolean(liveContactName);
          const contactState = isPrivate ? pickMsgNicknameState(chatId, overlay, current,
            keepContactOverlay ? overlay : null) : null;
          const contactName = isPrivate && contactState
            ? (contactState.nickname_blank ? '\u00a0' : contactState.nickname) : '';
          const contactAvatar = isPrivate ? String(current.avatar || overlay.avatar || '') : '';
          const serverTs = Number(current.last_ts || 0);
          const eventTs = Number(overlay.last_ts || 0);
          if (serverTs > eventTs && Number(current.group_info_updated_at || 0) >= Number(overlay.group_info_updated_at || 0)
            && (isPrivate || msgKnownGroupMemberCount(current.member_num, current.group_member_num) !== null
              || msgKnownGroupMemberCount(overlay.member_num, overlay.group_member_num) === null)) {
            if (isPrivate && (keepFriendOverlay || keepContactOverlay || (!validMsgNickname(current.nickname, chatId) && contactName)
              || (!current.avatar && contactAvatar))) {
              // 机器人回复可能更新摘要时间，不能据此覆盖尚未确认的对方姓名。
              const profile = {...current, ...friendState, ...(contactState || {}), nickname:current.remark || contactName || current.nickname, avatar:contactAvatar,
                ...(keepContactOverlay ? {_private_nickname:overlay._private_nickname, _private_nickname_blank:overlay._private_nickname_blank, _private_nickname_ts:overlay._private_nickname_ts} : {})};
              byId.set(chatKey, profile);
              msgState.realtimeChats.set(chatKey, profile);
            } else msgState.realtimeChats.delete(chatKey);
            return;
          }
          const adminKnown = msgState.adminByChat.has(chatId)
            ? Boolean(msgState.adminByChat.get(chatId))
            : Boolean(current.is_admin || overlay.is_admin);
          const groupProfile = Number(current.group_info_updated_at || 0) > Number(overlay.group_info_updated_at || 0) ? current : overlay;
          const groupName = String(groupProfile.group_name || current.group_name || overlay.group_name || '');
          const memberNum = msgKnownGroupMemberCount(groupProfile.member_num, groupProfile.group_member_num,
            current.member_num, current.group_member_num, overlay.member_num, overlay.group_member_num);
          byId.set(chatKey, {
            ...current,
            ...(serverTs > eventTs ? {} : overlay),
            group_name:groupName,
            group_info_updated_at:Math.max(Number(current.group_info_updated_at || 0), Number(overlay.group_info_updated_at || 0)),
            member_num:memberNum,
            group_member_num:memberNum,
            ...(isPrivate && contactState ? contactState : {}),
            nickname:current.remark || (current.chat_type === 'group' && groupName) || contactName || current.nickname || overlay.nickname,
            ...(isPrivate ? {avatar:contactAvatar, ...friendState} : groupState),
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
          msgState.realtimeChats.forEach((overlay, chatKey) => {
            if (msgState.realtimeChats.size <= 256) return;
            if (chatKey !== msgScopeKey(msgState.chatType, msgState.chatId, msgState.chatAppid) && now - Number(overlay?.last_ts || 0) > 600) {
              msgState.realtimeChats.delete(chatKey);
            }
          });
        }
        return [...byId.values()].map(applyMsgReadOverride).filter((chat) => msgChatMatchesView(chat, {ignoreTypeFilter:true})).sort((left, right) =>
          Number(msgChatIsRemoved(left)) - Number(msgChatIsRemoved(right)) ||
          Number(Boolean(right.pinned)) - Number(Boolean(left.pinned)) ||
          Number(right.last_ts || 0) - Number(left.last_ts || 0)
        );
      };
      const clearMsgChatUnread = (chatId, chatType = msgState.chatType, appid = msgState.selectedAppid) => {
        const id = String(chatId || '');
        if (!id) return false;
        const scope = msgScopeKey(chatType, id, appid);
        let changed = false;
        msgState.chats = msgState.chats.map((chat) => {
          if (String(chat.chat_id || '') !== id || chat.chat_type !== chatType || String(chat.appid || '').trim() !== String(appid || '').trim() || Number(chat.unread || 0) <= 0) return chat;
          changed = true;
          return {...chat, unread:0};
        });
        msgState.chatListRows = msgState.chatListRows.map((row) => {
          const chat = row.kind === 'chat' ? row.chat : null;
          if (!chat || String(chat.chat_id || '') !== id || chat.chat_type !== chatType
            || String(chat.appid || '').trim() !== String(appid || '').trim() || Number(chat.unread || 0) <= 0) return row;
          return {...row, chat:{...chat, unread:0}};
        });
        const existing = msgState.realtimeChats.get(scope) || msgState.chats.find((chat) => String(chat.chat_id || '') === id && chat.chat_type === chatType && String(chat.appid || '').trim() === String(appid || '').trim());
        if (existing) msgState.realtimeChats.set(scope, {...existing, unread:0});
        document.querySelectorAll('[data-msg-chat]').forEach((node) => {
          if (node.dataset.msgKey === scope) node.querySelector('.msg-chat-badge')?.remove();
        });
        return changed;
      };
      const markMsgRead = async (chatId = msgState.chatId, force = false, chatType = msgState.chatType, appid = msgState.selectedAppid) => {
        const id = String(chatId || '');
        appid = String(appid || '').trim();
        if (!id || !appid || appid !== msgState.selectedAppid || !['group','user'].includes(chatType)) return;
        const scope = msgScopeKey(chatType, id, appid);
        rememberMsgRead(chatType, id, appid);
        const changed = clearMsgChatUnread(id, chatType, appid);
        if (!force && !changed) return;
        // A list snapshot started before this read can arrive later and restore the old badge.
        msgState.chatListRequest = Number(msgState.chatListRequest || 0) + 1;
        if (msgState.chatListAbort) { msgState.chatListAbort.abort(); msgState.chatListAbort = null; }
        msgState.chatListPromise = null;
        msgState.chatListKey = '';
        msgState.chatListPendingData = null;
        if (msgState.readInFlight.has(scope)) {
          msgReadAgain.add(scope);
          return;
        }
        msgState.readInFlight.add(scope);
        try {
          let succeeded = false;
          while (true) {
            msgReadAgain.delete(scope);
            try {
              await api('message/read', {method:'POST', body:JSON.stringify({chat_id:id, chat_type:chatType, appid})});
              succeeded = true;
            } catch (_) {
              if (!msgReadAgain.has(scope)) break;
            }
            if (!msgReadAgain.has(scope)) break;
          }
          if (succeeded && appid === msgState.selectedAppid && !$('page-messages')?.hidden) void loadMsgChats(true);
        }
        catch (_) {}
        finally { msgState.readInFlight.delete(scope); msgReadAgain.delete(scope); }
      };
      const getLocalAdminGroups = () => {
        try { return new Set(JSON.parse(localStorage.getItem('mantou_bot_admin_groups:' + msgState.selectedAppid) || '[]')); }
        catch (_) { return new Set(); }
      };
      const saveLocalAdminGroups = (set) => {
        try { localStorage.setItem('mantou_bot_admin_groups:' + msgState.selectedAppid, JSON.stringify(Array.from(set))); }
        catch (_) {}
      };
      // 远端权限和禁言先返回快照；当前群有限补查不占用聊天首屏请求。
      const msgGroupSnapshotTasks = {roles:null, mutes:null};
      const msgGroupSnapshotTarget = () => {
        if (msgState.chatType !== 'group' || !msgState.chatId) return null;
        const chatId = String(msgState.chatId);
        const appid = String(msgState.chatAppid || msgState.selectedAppid || '').trim();
        if (!appid) return null;
        const chat = msgState.chats.find((item) => String(item.chat_id || '') === chatId
          && item.chat_type === 'group' && String(item.appid || '').trim() === appid);
        return {chat_id:chatId, chat_type:'group', appid:String(chat?.appid || appid).trim()};
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
        const scanAppid = msgState.selectedAppid;
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
              if (scanAppid !== msgState.selectedAppid || !msgGroupSnapshotVisible() || !msgGroupSnapshotMatches(res, target)) continue;
              if (res.pending || res.has_data === false) continue;
              const previousMembership = readMsgGroupState(group);
              const membership = syncMsgGroupState(chatId, res, target.appid);
              if ((readMsgGroupState(res)?.membership_revision || 0) < membership.membership_revision) continue;
              const removed = membership.membership_status === 'removed';
              if (removed) {
                membershipChanged = true;
                if (msgState.chatId === chatId && msgState.chatType === 'group') {
                  updateMsgHead({chat_name:group.nickname || chatId, group_info:membership});
                }
                msgState.adminByChat.set(chatId, false);
                localAdmins.delete(chatId);
                await new Promise((r) => setTimeout(r, 1000));
                continue;
              }
              if (membership.membership_status !== 'active') continue;
              const role = String(res?.bot_role || '').trim().toLowerCase();
              if (!['owner', 'admin', 'member'].includes(role)) throw new Error('群角色结果不完整');
              composerMentionPicker.roles.set(JSON.stringify([chatId, target.appid]), role);
              if (previousMembership?.membership_status !== 'active') membershipChanged = true;
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
              if (scanAppid === msgState.selectedAppid) msgState.adminScanFailures.set(chatId, Date.now());
            }
            await new Promise((r) => setTimeout(r, 1000));
          }
          if (membershipChanged) renderMsgChats({chats:msgState.chats});
          if (groupsToScan.length >= 1) scheduleAutoScanAdminGroups(10000);
        } finally {
          autoScanAdminRunning = false;
          if (scanAppid !== msgState.selectedAppid && msgGroupSnapshotVisible()) scheduleAutoScanAdminGroups(10000);
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
        const typeTag = chat.chat_type === 'user' ? '<span class="msg-chat-type">私聊</span>' : '<span class="msg-chat-type">群聊</span>';
        const viewing = msgMatchesCurrent(chat.chat_type, chat.chat_id, chat.appid);
        const removed = msgChatIsRemoved(chat);
        const viewingAtBottom = viewing && !$('page-messages')?.hidden && msgState.pendingNewMessages === 0 && msgBodyNearBottom($('msg-body'));
        const unread = viewingAtBottom ? 0 : Number(chat.unread || 0);
        if (viewingAtBottom && Number(chat.unread || 0) > 0) queueMicrotask(() => markMsgRead(chat.chat_id, false, chat.chat_type, chat.appid));
        const removedText = msgChatRemovedText(chat);
        const preview = removed ? removedText : (item.preview || '（无文本内容）');
        return `<button type="button" class="msg-chat ${chat.pinned ? 'pinned' : ''} ${viewing ? 'active' : ''}${removed ? ' removed' : ''}" style="${placement}" data-msg-chat="${esc(chat.chat_id)}" data-msg-type="${esc(chat.chat_type)}" data-msg-appid="${esc(chat.appid)}" data-msg-key="${esc(msgChatKey(chat))}" data-msg-pinned="${chat.pinned ? '1' : '0'}" data-msg-removed="${removed ? '1' : '0'}" title="${removed ? removedText : (chat.pinned ? '取消置顶' : '置顶')}">
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
        if (!node || (data.appid && !msgInSelectedBot(data))) return;
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
            anchorChatId = String(anchor.dataset.msgKey || '');
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
              .find((item) => String(item.dataset.msgKey || '') === anchorChatId);
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
        const chats = mergeMsgRealtimeChats(data.chats || [], {serverSnapshot:Boolean(data._server_snapshot)});
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
        if (msgState.chatId) updateMsgHead({});
        const visibleChats = chats.filter((chat) => msgChatMatchesView(chat));
        const knownChatIds = new Set(chats.map((chat) => String(chat.chat_id || '')).filter(Boolean));
        [msgState.adminByChat, msgState.adminScanAttempted, msgState.adminScanFailures, msgState.adminCheckedAt]
          .forEach((map) => map.forEach((_value, key) => { if (!knownChatIds.has(String(key))) map.delete(key); }));
        window.msgGroupQQ = {}; (chats||[]).forEach((chat) => { if (chat.group_qq) window.msgGroupQQ[chat.chat_id] = chat.group_qq; });
        const rowHeight = getMsgChatRowHeight(node);
        const chatPreviews = new Map();
        const chatRenderSignature = [msgState.filter, msgState.grouped ? 1 : 0, msgState.folderCollapsed.group ? 1 : 0, msgState.folderCollapsed.user ? 1 : 0, rowHeight].join(':') + '|' + visibleChats.map((chat) => {
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
            chat.membership_revision,
            chat.membership_source,
            chat.membership_dismiss === null ? 'unknown' : chat.membership_dismiss === true ? 1 : chat.membership_dismiss === false ? 0 : 'unknown',
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
        if (msgState.filter === 'all' && msgState.grouped) {
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
          const anchorIndex = rows.findIndex((row) => row.kind === 'chat' && msgChatKey(row.chat) === anchorChatId);
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
            const chatId = el.dataset.msgChat; const chatType = el.dataset.msgType; const appid = el.dataset.msgAppid; const pinned = el.dataset.msgPinned === '1';
            const menuGeneration = String((Number(node.dataset.msgContextGeneration) || 0) + 1);
            node.dataset.msgContextGeneration = menuGeneration;
            const menuScopeGeneration = msgState.scopeGeneration;
            const menuContext = msgQuoteJumpScope();
            const items = [];
            items.push({label: pinned ? '取消置顶' : '置顶', action: async () => {
              try { const result = await api('message/pin', {method:'POST', body:JSON.stringify({chat_id:chatId, chat_type:chatType, appid, pinned:!pinned})}); toast(result.pinned ? '已置顶' : '已取消置顶'); await loadMsgChats(true); }
              catch (error) { toast(error.message || '操作失败'); }
            }});
            if (chatType === 'group') items.push({label:'刷新群信息', action:() => { api('message/group-info/refresh', {method:'POST', body:JSON.stringify({chat_id:chatId, chat_type:chatType, appid})}).then((data) => { applyMsgGroupInfo({...data, chat_id:chatId}); toast('已刷新'); loadMsgChats(true); }).catch((error) => toast(error.message || '刷新失败')); }});
            items.push({sep:true}, {label:'删除会话及记录', danger:true, action:() => {
              if (activeView !== 'messages' || node.dataset.msgContextGeneration !== menuGeneration
                || menuScopeGeneration !== msgState.scopeGeneration || menuContext !== msgQuoteJumpScope()
                || appid !== consoleAppid || appid !== msgState.selectedAppid) return;
              const chat = msgState.chats.find((item) => String(item.chat_id || '') === chatId && item.chat_type === chatType && item.appid === appid);
              if (!chat) return;
              if (!msgMatchesCurrent(chatType, chatId, appid)) {
                selectMsgChat(chat);
                if (!msgMatchesCurrent(chatType, chatId, appid)) return;
                scheduleMsgHistoryLoad(chatId);
              }
              openMsgClear({chatOnly:true});
            }});
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
            if (msgMatchesCurrent(chatType, chatId, el.dataset.msgAppid)) {
              setMsgMobileChatOpen(true);
              markMsgRead(chatId, true, chatType, el.dataset.msgAppid);
              return;
            }
            if (groupSettingsState.mutating) return toast('正在更新本群设置，请稍候再切换');
            const chat = msgState.chats.find((item) => String(item.chat_id || '') === chatId && item.chat_type === chatType && item.appid === el.dataset.msgAppid) || {
              chat_id: chatId,
              chat_type: chatType, appid:el.dataset.msgAppid,
              nickname: chatId,
            };
            selectMsgChat(chat);
            scheduleMsgHistoryLoad(chatId);
            markMsgRead(chatId, true, chatType, el.dataset.msgAppid);
          });
        }
      };
      const selectMsgChat = (chat) => {
        hideMsgCtx();
        closeMsgHeadMenu(); closeAdminPopover();
        closeComposerMentionPicker();
        const chatId = String(chat?.chat_id || '').trim();
        if (!chatId) return;
        const chatType = String(chat?.chat_type || 'group');
        if (!msgInSelectedBot(chat)) return;
        if (groupSettingsState.mutating && (msgState.chatId !== chatId || msgState.chatType !== chatType)) return toast('正在更新本群设置，请稍候再切换');
        if (msgState.chatId !== chatId || msgState.chatType !== chatType) { closeGroupSettings(); groupSettingsState.remarkTarget = null; setMsgModal('msg-remark-modal', false); setMsgModal('msg-clear-modal', false); }
        cancelMsgQuoteJump(true);
        setMsgMobileChatOpen(true);
        msgState.chatRemoved = msgChatIsRemoved(chat);
        const localAdmins = getLocalAdminGroups();
        const cachedAdmin = msgState.adminByChat.has(chatId)
          ? Boolean(msgState.adminByChat.get(chatId))
          : Boolean(chat?.is_admin || localAdmins.has(chatId));
        if (cachedAdmin && !msgState.adminByChat.has(chatId)) msgState.adminByChat.set(chatId, true);
        const sameChat = msgMatchesCurrent(chatType, chatId, chat.appid);
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
        msgState.botRole = '';
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
          const cachedHistory = msgState.historyCache.get(msgScopeKey(chatType, chatId, chat.appid));
          if (cachedHistory && Array.isArray(cachedHistory.messages) && cachedHistory.messages.length) {
            msgState.messages = dedupeMsgMessages(cachedHistory.messages);
            // 先显示上次已读内容，网络结果返回后再合并新消息。
            renderMsgMessages({...cachedHistory, messages:msgState.messages}, {toBottom:true});
          }
        }
        document.querySelectorAll('[data-msg-chat]').forEach((node) => {
          node.classList.toggle('active', node.dataset.msgKey === msgChatKey(chat));
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
        const scope = msgScopeKey(msgState.chatType, id, msgState.chatAppid);
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
          if (token !== msgState.historyScheduleToken || msgScopeKey(msgState.chatType, msgState.chatId, msgState.chatAppid) !== scope) return;
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
        if (!msgState.selectedAppid) return loadBotProfile().then(() => msgState.selectedAppid ? loadMsgChats(force) : undefined);
        const params = {appid:msgState.selectedAppid, filter:'all', search:msgState.search, page:1, page_size:0};
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
            if (requestId !== msgState.chatListRequest || params.appid !== msgState.selectedAppid) return data;
            if (!msgState.chatListServerLoaded) {
              msgState.chatListServerLoaded = true;
              msgState.chatListTopPending = true;
            }
            renderMsgChats({...data, _server_snapshot:true});
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
      const msgClearScopeMatches = (boundary, type, id, appid) => String(boundary.appid || '') === String(appid || '')
        && (boundary.scope === 'bot' || (boundary.scope === 'chat' && boundary.chat_type === type && String(boundary.chat_id || '') === String(id || '')));
      const msgIsClearedByBoundary = (message, boundary) => {
        const origin = String(message?.history_origin || ''), order = Number(message?.history_order || 0);
        if (origin && origin === String(boundary?.origin || '') && Number.isSafeInteger(order) && order > 0) return order <= Number(boundary?.cutoff_order || 0);
        const id = Number(message?.id || 0), cutoff = Number(boundary?.cutoff_id || 0);
        if (Number.isSafeInteger(id) && id > 0 && Number.isSafeInteger(cutoff) && cutoff > 0 && id <= cutoff) return true;
        return false;
      };
      const msgIsKnownCleared = (message, type, id, appid) => [...msgHistoryClearBoundaries.values()].some((boundary) =>
        msgClearScopeMatches(boundary, type, id, appid) && msgIsClearedByBoundary(message, boundary));
      const invalidateMsgClearPreview = () => {
        msgClearState.generation += 1;
        msgClearState.previewAbort?.abort(); msgClearState.previewAbort = null;
        clearTimeout(msgClearState.expiryTimer); msgClearState.expiryTimer = null;
        msgClearState.token = ''; msgClearState.expiresAt = 0; msgClearState.previewing = false;
        if ($('msg-clear-confirm')) $('msg-clear-confirm').disabled = true;
      };
      const msgClearTargetCurrent = (target) => target && msgClearState.target === target && !$('msg-clear-modal').hidden
        && target.appid === consoleAppid && target.appid === msgState.selectedAppid
        && target.consoleGeneration === consoleGeneration && target.scopeGeneration === msgState.scopeGeneration
        && target.context === msgQuoteJumpScope() && activeView === 'messages';
      const syncMsgClearControls = () => {
        const busy = msgClearInFlight.has(consoleAppid);
        $('msg-clear-scope').disabled = busy || Boolean(msgClearState.target?.chatOnly);
        $('msg-clear-preview-button').disabled = busy || msgClearState.previewing;
        $('msg-clear-confirm').disabled = busy || !msgClearState.token || msgClearState.expiresAt <= Date.now();
      };
      const previewMsgClear = async () => {
        const previous = msgClearState.target;
        if (!msgClearTargetCurrent(previous) || msgClearInFlight.has(previous.appid)) return;
        invalidateMsgClearPreview();
        const scope = !previous.chatOnly && $('msg-clear-scope').value === 'bot' ? 'bot' : 'chat';
        const target = {...previous, scope, chat_id:scope === 'chat' ? msgState.chatId : '', chat_type:scope === 'chat' ? msgState.chatType : ''};
        if (scope === 'chat' && (!target.chat_id || msgState.chatAppid !== target.appid)) return;
        msgClearState.target = target; msgClearState.previewing = true;
        const generation = msgClearState.generation;
        const controller = new AbortController(); msgClearState.previewAbort = controller;
        const output = $('msg-clear-preview'); output.className = 'msg-clear-preview'; output.textContent = '正在统计记录…';
        $('msg-clear-target').textContent = scope === 'chat' ? `当前会话：${target.name}` : `当前机器人：${window.msgBotProfile?.username || target.appid}，包含群聊和私聊。`;
        syncMsgClearControls();
        try {
          const result = await api('message/clear/preview', {method:'POST', body:JSON.stringify({scope, chat_id:target.chat_id, chat_type:target.chat_type, appid:target.appid}), signal:controller.signal});
          if (generation !== msgClearState.generation || !msgClearTargetCurrent(target)) return;
          const count = result.matched_count;
          const rawExpiry = result.expires_at;
          const expiresAt = Number.isFinite(Number(rawExpiry)) ? Number(rawExpiry) * (Number(rawExpiry) < 1e12 ? 1000 : 1) : Date.parse(String(rawExpiry || ''));
          if (String(result.appid || '') !== target.appid || result.scope !== scope || (scope === 'chat' && (String(result.chat_id || '') !== target.chat_id || result.chat_type !== target.chat_type))
            || !Number.isSafeInteger(count) || count < 0 || !result.clear_token || !Number.isFinite(expiresAt) || expiresAt <= Date.now()) throw new Error('invalid_preview');
          const canConfirm = count > 0 || scope === 'chat';
          msgClearState.token = canConfirm ? String(result.clear_token) : ''; msgClearState.expiresAt = expiresAt;
          output.textContent = count > 0
            ? `将清理 ${count.toLocaleString('zh-CN')} 条本机聊天记录。${scope === 'chat' ? '清空后从列表移除此会话，预览后新消息保留。' : '确认后删除本次预览范围内的记录。'}`
            : scope === 'chat' ? '当前会话没有聊天记录。确认后从列表移除此会话，预览后新消息保留。' : '此范围没有需要清理的记录。';
          if (canConfirm) msgClearState.expiryTimer = setTimeout(() => {
            if (generation !== msgClearState.generation || !msgClearTargetCurrent(target)) return;
            invalidateMsgClearPreview(); output.textContent = '预览已过期，请重新统计后确认。'; syncMsgClearControls();
          }, Math.max(0, expiresAt - Date.now()));
        } catch (error) {
          if (generation !== msgClearState.generation || !msgClearTargetCurrent(target) || error.name === 'AbortError') return;
          output.className = 'msg-clear-preview error'; output.textContent = '记录统计未完成，请重新统计后再确认。';
          if (error.status === 401) showAuthError(error);
        } finally {
          if (generation === msgClearState.generation && msgClearTargetCurrent(target)) { msgClearState.previewing = false; msgClearState.previewAbort = null; syncMsgClearControls(); }
        }
      };
      const openMsgClear = ({chatOnly = false} = {}) => {
        if (!consoleAppid || consoleAppid !== msgState.selectedAppid || activeView !== 'messages') return;
        closeGroupSettings(); hideMsgCtx();
        msgModalIds.filter((id) => id !== 'msg-clear-modal').forEach((id) => setMsgModal(id, false, false));
        invalidateMsgClearPreview();
        const hasChat = Boolean(msgState.chatId && msgState.chatAppid === consoleAppid);
        if (chatOnly && !hasChat) return;
        const option = $('msg-clear-scope').querySelector('option[value="chat"]'); option.hidden = !hasChat; option.disabled = !hasChat;
        $('msg-clear-scope').value = hasChat ? 'chat' : 'bot';
        msgClearState.target = {appid:consoleAppid, context:msgQuoteJumpScope(), name:$('msg-head-name').textContent || msgState.chatId,
          consoleGeneration, scopeGeneration:msgState.scopeGeneration, chatOnly};
        $('msg-clear-title').textContent = chatOnly ? '删除会话及记录' : '清理聊天记录';
        $('msg-clear-preview').className = 'msg-clear-preview';
        $('msg-clear-preview').textContent = msgClearInFlight.has(consoleAppid) ? '当前机器人的记录清理正在执行，请稍候刷新查看结果。' : '正在统计记录…';
        $('msg-clear-target').textContent = '';
        setMsgModal('msg-clear-modal', true); syncMsgClearControls();
        if (!msgClearInFlight.has(consoleAppid)) void previewMsgClear();
      };
      const applyMsgHistoryCleared = (payload) => {
        if (!consoleAppid || String(payload?.appid || '') !== consoleAppid || consoleAppid !== msgState.selectedAppid) return false;
        const scope = payload.scope;
        if (!['chat','bot'].includes(scope) || (scope === 'chat' && (!payload.chat_id || !['group','user'].includes(payload.chat_type)))) return false;
        const boundary = {...payload, appid:consoleAppid, chat_id:String(payload.chat_id || ''), chat_type:String(payload.chat_type || '')};
        const key = JSON.stringify([boundary.appid, scope, scope === 'chat' ? boundary.chat_type : '', scope === 'chat' ? boundary.chat_id : '', String(boundary.origin || '')]);
        const previous = msgHistoryClearBoundaries.get(key);
        if (previous && Number(previous.cutoff_id || 0) >= Number(boundary.cutoff_id || 0) && Number(previous.cutoff_order || 0) >= Number(boundary.cutoff_order || 0)) return false;
        msgHistoryClearBoundaries.set(key, {...boundary, cutoff_id:Math.max(Number(previous?.cutoff_id || 0), Number(boundary.cutoff_id || 0)), cutoff_order:Math.max(Number(previous?.cutoff_order || 0), Number(boundary.cutoff_order || 0))});
        setMsgModal('msg-clear-modal', false);
        const affects = (type, id, appid) => msgClearScopeMatches(boundary, type, id, appid);
        const keepSummary = (chat) => {
          if (!affects(chat.chat_type, chat.chat_id, chat.appid)) return true;
          const record = {id:chat.last_record_id, history_origin:chat.history_origin, history_order:chat.history_order};
          return Boolean(record.id || record.history_origin) && !msgIsClearedByBoundary(record, boundary);
        };
        for (const key of msgState.historyCache.keys()) { try { const [appid, type, id] = JSON.parse(key); if (affects(type, id, appid)) msgState.historyCache.delete(key); } catch (_) {} }
        for (const [key, chat] of msgState.realtimeChats) if (!keepSummary(chat)) msgState.realtimeChats.delete(key);
        msgState.chats = msgState.chats.filter(keepSummary);
        msgState.chatListRequest += 1; msgState.chatListAbort?.abort(); msgState.chatListAbort = null;
        msgState.chatListPromise = null; msgState.chatListKey = ''; msgState.chatListPendingData = null;
        msgState.chatListScrollActive = false; msgState.chatListPointerActive = false;
        if (msgState.chatRenderTimer) clearTimeout(msgState.chatRenderTimer); msgState.chatRenderTimer = null;
        if (msgState.chatId && affects(msgState.chatType, msgState.chatId, msgState.chatAppid)) {
          msgState.historyRequest += 1; msgState.historyOlderRequest += 1; msgState.historyScheduleToken += 1;
          for (const key of ['historyAbort','historyOlderAbort']) { msgState[key]?.abort(); msgState[key] = null; }
          if (msgState.historyScheduleFrame != null) cancelAnimationFrame(msgState.historyScheduleFrame); msgState.historyScheduleFrame = null;
          msgState.historyOlderLoading = false; msgState.historyActiveScope = '';
          cancelMsgQuoteJump(true); cancelMsgRealtimeMessageRender(); closeMsgLightbox(); closeGroupSettings(); hideMsgCtx();
          msgModalIds.forEach((id) => setMsgModal(id, false));
          $('msg-raw-content').replaceChildren(); $('msg-raw-copy').textContent = '复制';
          if (msgState.multi) exitMultiMode(); clearMsgQuote(); clearMsgNewMessages();
          msgState.messages = msgState.messages.filter((message) => !msgIsKnownCleared(message, msgState.chatType, msgState.chatId, msgState.chatAppid));
          const hasLocalNewMessages = msgState.messages.length > 0 || msgState.chats.some((chat) => affects(chat.chat_type, chat.chat_id, chat.appid));
          if (scope === 'chat' && payload.conversation_removed === true && Number(payload.remaining_count) === 0 && !hasLocalNewMessages) {
            stopMsgGroupSnapshots(); closeComposerMentionPicker();
            Object.assign(msgState, {chatId:'', chatType:'group', chatAppid:msgState.selectedAppid, chatRemoved:false,
              messages:[], profiles:{}, historyData:null, historyWindow:null, historyActiveScope:'', renderedChatId:'',
              messageRenderSignature:null, initialScrollChatId:'', botIsAdmin:false, botRole:'',
              adminRequestToken:msgState.adminRequestToken + 1, lastRolesAt:0, lastRolesChatId:'', lastRolesAppid:'',
              panSelectionRequest:msgState.panSelectionRequest + 1, panSelectionData:null, panSelectionSaving:false, panSelectionLoading:false,
              mutes:new Map(), muteRequestAt:0});
            resetComposer(); resetMsgAdSwitch(); updateMsgPanSelector();
            const body = $('msg-body'); cancelMsgBottomPosition(body, true); body.classList.remove('msg-positioning');
            body.innerHTML = '<div class="msg-empty">请在左侧选择会话</div>';
            $('msg-head-name').textContent = '请选择会话'; $('msg-head-name').dataset.chatKey = ''; $('msg-head-name').classList.remove('admin');
            $('msg-head-sub').textContent = ''; $('msg-head-name').removeAttribute('title'); $('msg-head-sub').removeAttribute('title');
            $('msg-head-name').disabled = true; $('msg-head-name').setAttribute('aria-expanded','false'); $('msg-head-name').removeAttribute('aria-label');
            for (const id of ['msg-composer','msg-refresh-info','msg-remark','msg-group-settings-open','msg-ad-switch','msg-admin-tag']) $(id).hidden = true;
            setMsgMobileChatOpen(false);
          } else {
            msgState.historyData = {...(msgState.historyData || {}), references:{}, has_more:false, messages:msgState.messages};
            msgState.messageRenderSignature = null;
            renderMsgMessages(msgState.historyData, {forceRender:true, previousTop:$('msg-body').scrollTop, previousHeight:$('msg-body').scrollHeight});
            if (!$('page-messages').hidden && msgState.chatId) void loadMsgHistory(false, true);
          }
        }
        renderMsgChats({appid:consoleAppid, chats:msgState.chats});
        if (!$('page-messages').hidden) void loadMsgChats(true);
        return true;
      };
      const confirmMsgClear = async () => {
        const target = msgClearState.target;
        if (!msgClearTargetCurrent(target) || msgClearInFlight.has(target.appid) || !msgClearState.token) return;
        if (msgClearState.expiresAt <= Date.now()) { invalidateMsgClearPreview(); $('msg-clear-preview').textContent = '预览已过期，请重新统计后确认。'; syncMsgClearControls(); return; }
        const token = msgClearState.token;
        msgClearInFlight.add(target.appid); invalidateMsgClearPreview(); syncMsgClearControls();
        $('msg-clear-preview').textContent = '正在清理记录…';
        try {
          const result = await api('message/clear', {method:'POST', body:JSON.stringify({clear_token:token, appid:target.appid})});
          if (target.appid !== consoleAppid || target.appid !== msgState.selectedAppid
            || target.consoleGeneration !== consoleGeneration || target.scopeGeneration !== msgState.scopeGeneration) return;
          if (String(result.appid || '') !== target.appid || result.scope !== target.scope || (target.scope === 'chat' && (String(result.chat_id || '') !== target.chat_id || result.chat_type !== target.chat_type))) throw new Error('invalid_clear_result');
          applyMsgHistoryCleared(result);
          toast(Number.isSafeInteger(result.deleted_count) ? `已清理 ${result.deleted_count.toLocaleString('zh-CN')} 条本机记录` : '本机记录已清理');
        } catch (error) {
          if (error.name === 'AbortError' || !msgClearTargetCurrent(target)) return;
          $('msg-clear-preview').className = 'msg-clear-preview error';
          $('msg-clear-preview').textContent = '清理结果尚未确认，请刷新记录后重新统计。';
          if (error.status === 401) showAuthError(error);
        } finally {
          msgClearInFlight.delete(target.appid);
          if (consoleAppid === target.appid && !$('msg-clear-modal').hidden) syncMsgClearControls();
        }
      };
      const handleMsgRealtimeData = (raw) => {
        try {
          const envelope = typeof raw === 'string' ? JSON.parse(raw || '{}') : raw;
          if (envelope?.type === 'message') { applyMsgRealtimeEvent(envelope.data || {}); scheduleMsgRealtimeRefresh(); }
          else if (envelope?.type === 'group_status') applyMsgGroupStatus(envelope.data || {});
          else if (envelope?.type === 'group_info') applyMsgGroupInfo(envelope.data || {});
          else if (envelope?.type === 'history_cleared') applyMsgHistoryCleared(envelope.data || {});
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
        if (!consoleAppid || msgState.eventSource || msgState.eventSocket || !window.EventSource || $('page-messages')?.hidden) return;
        const appid = consoleAppid, generation = consoleGeneration;
        let source;
        try { source = new EventSource(botApiUrl('message/events', appid)); }
        catch (_) { scheduleMsgRealtimeReconnect(); return; }
        msgState.eventSource = source;
        msgState.eventTransport = '';
        source.onopen = () => {
          if (msgState.eventSource === source) msgState.eventTransport = 'sse';
        };
        source.onmessage = (event) => { if (appid === consoleAppid && generation === consoleGeneration && msgState.eventSource === source) handleMsgRealtimeData(event.data); };
        source.onerror = () => {
          if (msgState.eventSource !== source) return;
          source.onopen = null; source.onmessage = null; source.onerror = null;
          try { source.close(); } catch (_) {}
          msgState.eventSource = null; msgState.eventTransport = '';
          scheduleMsgRealtimeReconnect();
        };
      };
      const connectMsgEvents = () => {
        if (!consoleAppid || msgState.eventSocket || msgState.eventSource || $('page-messages')?.hidden) return;
        const appid = consoleAppid, generation = consoleGeneration;
        if (!window.WebSocket) { connectMsgSse(); return; }
        const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        let socket;
        try { socket = new WebSocket(`${wsProtocol}//${location.host}${botApiUrl('message/ws', appid)}`); }
        catch (_) { connectMsgSse(); return; }
        msgState.eventSocket = socket;
        msgState.eventTransport = '';
        socket.onopen = () => { if (msgState.eventSocket === socket) msgState.eventTransport = 'websocket'; };
        socket.onmessage = (event) => { if (appid === consoleAppid && generation === consoleGeneration && msgState.eventSocket === socket) handleMsgRealtimeData(event.data); };
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
        const curChat = (msgState.chats || []).find((c) => String(c.chat_id || '') === String(msgState.chatId || '') && c.chat_type === msgState.chatType && msgInSelectedBot(c));
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
        const appid = msgState.chatAppid;
        if (msgState.chatType !== 'group' || !chatId || msgState.chatRemoved) return;
        msgState.adChatId = chatId;
        msgState.adLoading = true;
        updateMsgAdSwitch();
        try {
          const data = await api('message/group-ad', {method:'POST', body:JSON.stringify({...captureGroupTarget(), chat_id:chatId, chat_type:'group', action:'get'})});
          if (!msgMatchesCurrent('group', chatId, appid)) return;
          msgState.adEnabled = Boolean(data.enabled);
          msgState.adEditable = Boolean(data.editable);
        } catch (_) {
          if (msgMatchesCurrent('group', chatId, appid)) {
            msgState.adEnabled = false;
            msgState.adEditable = false;
          }
        } finally {
          if (msgMatchesCurrent('group', chatId, appid)) {
            msgState.adLoading = false;
            updateMsgAdSwitch();
          }
        }
      };
      const toggleGroupAdSwitch = async () => {
        const chatId = String(msgState.chatId || '').trim();
        const appid = msgState.chatAppid;
        if (msgState.chatType !== 'group' || !chatId || !msgState.adEditable || msgState.adSaving) return;
        const enabled = !Boolean(msgState.adEnabled);
        msgState.adSaving = true;
        updateMsgAdSwitch();
        try {
          const data = await api('message/group-ad', {method:'POST', body:JSON.stringify({...captureGroupTarget(), chat_id:chatId, chat_type:'group', action:'set', enabled})});
          if (!msgMatchesCurrent('group', chatId, appid)) return;
          msgState.adEnabled = Boolean(data.enabled);
          msgState.adEditable = Boolean(data.editable);
          toast(enabled ? '本群广告拦截已开启' : '本群广告拦截已关闭');
        } catch (error) {
          toast(error.message || '广告开关保存失败');
        } finally {
          if (msgMatchesCurrent('group', chatId, appid)) {
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
        const defaultLabel = data.default?.label ? `跟随本机器人默认 · ${data.default.label}` : '跟随本机器人默认 · 暂无可用账号';
        const options = [`<option value="__default__">${esc(defaultLabel)}</option>`, '<option value="__file__">关闭网盘，直接发送文件</option>', ...choices.map((choice) => `<option value="${esc(choice.value)}">${esc(choice.label)}</option>`)];
        const selectedValue = msgState.panSelectionSaving ? select.value : data.selected_value;
        select.innerHTML = options.join('');
        select.value = selectedValue || '__default__';
        select.disabled = !data.editable || msgState.panSelectionSaving;
        select.title = data.editable ? '只影响当前群；可关闭网盘直接发送文件，或跟随本机器人默认网盘' : '数据库未配置，群网盘选择不能保存';
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
        if (value === '__file__') {
          payload = {chat_id:chatId, action:'file'};
        } else if (value !== '__default__') {
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
        const responseInfo = data.group_info || {};
        if ((responseInfo.appid && String(responseInfo.appid) !== String(msgState.chatAppid || ''))
          || (responseInfo.group_openid && String(responseInfo.group_openid) !== String(msgState.chatId || ''))) {
          data = {...data, group_info:{}};
        }
        const previousGroupState = msgState.chatType === 'group' ? readMsgGroupState(msgState.chats.find((chat) => chat.chat_type === 'group' && String(chat.chat_id || '') === msgState.chatId && String(chat.appid || '') === msgState.chatAppid)) : null;
        const groupState = msgState.chatType === 'group' ? syncMsgGroupState(msgState.chatId, data.group_info || {}, msgState.chatAppid) : null;
        if (previousGroupState && (previousGroupState.membership_status !== groupState?.membership_status
          || previousGroupState.membership_source !== groupState?.membership_source
          || previousGroupState.membership_dismiss !== groupState?.membership_dismiss)) scheduleMsgChatRender();
        const nameEl = $('msg-head-name');
        const curChat = (msgState.chats || []).find((c) => String(c.chat_id || '') === String(msgState.chatId || '')
          && String(c.chat_type || 'group') === msgState.chatType
          && String(c.appid || '') === String(msgState.chatAppid || ''));
        const knownInfo = data.group_info || {};
        const newerGroupInfo = Number(knownInfo.updated_at || 0) > Number(curChat?.group_info_updated_at || 0);
        const groupName = newerGroupInfo ? (knownInfo.group_name || curChat?.group_name) : (curChat?.group_name || knownInfo.group_name);
        const headKey = msgScopeKey(msgState.chatType, msgState.chatId, msgState.chatAppid);
        const liveContactName = msgState.chatType === 'user'
          ? msgLivePrivateNickname(msgState.realtimeChats.get(headKey), msgState.chatId) : '';
        const contactProfile = msgState.profiles?.[msgState.chatId];
        const contactState = msgState.chatType === 'user' ? pickMsgNicknameState(msgState.chatId,
          curChat, contactProfile && msgPrivateContactScope(msgState.chatId, contactProfile) ? contactProfile : null,
          msgState.realtimeChats.get(headKey)) : null;
        const currentContactName = contactState ? (contactState.nickname_blank ? '\u00a0' : contactState.nickname) : '';
        const knownName = curChat?.remark || (msgState.chatType === 'group' ? groupName : '')
          || currentContactName || data.chat_name || curChat?.nickname || liveContactName;
        const previousName = nameEl.dataset.chatKey === headKey ? nameEl.textContent : '';
        const blankContact = msgState.chatType === 'user' && !curChat?.remark && contactState?.nickname_blank;
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
        const infoCount = msgKnownGroupMemberCount(gInfo.member_num, gInfo.group_member_num);
        const currentCount = msgKnownGroupMemberCount(curChat?.member_num, curChat?.group_member_num);
        const infoTime = Number(gInfo.updated_at || 0), currentTime = Number(curChat?.group_info_updated_at || 0);
        const gNum = currentTime > infoTime ? msgKnownGroupMemberCount(currentCount, infoCount)
          : msgKnownGroupMemberCount(infoCount, currentCount);
        if (msgState.chatType === 'group' && curChat && infoCount !== null && infoTime >= currentTime) {
          curChat.member_num = curChat.group_member_num = infoCount;
          if (infoTime) curChat.group_info_updated_at = infoTime;
          const scope = msgScopeKey('group', msgState.chatId, msgState.chatAppid);
          const overlay = msgState.realtimeChats.get(scope) || curChat;
          if (Number(overlay.group_info_updated_at || 0) <= infoTime) {
            msgState.realtimeChats.set(scope, {...overlay, member_num:infoCount,
              group_member_num:infoCount, group_info_updated_at:infoTime});
          }
        }
        const removed = msgState.chatType === 'user' ? msgChatIsRemoved({...curChat, ...data, chat_type:'user'}) : groupState?.membership_status === 'removed';
        msgState.chatRemoved = removed;
        const canOpenGroupInfo = msgState.chatType === 'group' && !removed;
        nameEl.disabled = !canOpenGroupInfo;
        nameEl.setAttribute('aria-label', canOpenGroupInfo ? `${nameEl.textContent}，查看群信息` : nameEl.textContent);
        const hasMemberCount = gNum !== null;
        const headDetails = msgState.chatType === 'group'
          ? `群聊 · ${msgState.chatId}${hasMemberCount ? ` · 群成员 ${gNum} 人` : ' · 人数未知'}${removed ? ` · ${msgChatRemovedText(groupState)}` : ''}`
          : `私聊 · ${msgState.chatId}${removed ? ' · 对方已删除机器人好友 · 保留聊天记录' : ''}`;
        $('msg-head-sub').textContent = msgState.chatType === 'group'
          ? (removed ? msgChatRemovedText(groupState) : (hasMemberCount ? `${gNum}人` : '人数未知')) : '私聊';
        $('msg-head-sub').title = headDetails; nameEl.title = canOpenGroupInfo ? '查看群信息' : headDetails;
        $('msg-composer').hidden = removed;
        for (const id of ['msg-refresh-info','msg-remark','msg-group-settings-open']) $(id).hidden = msgState.chatType !== 'group' || removed;
        if (removed) {
          $('msg-ad-switch').hidden = true;
          closeGroupSettings(true);
        } else updateMsgAdSwitch();
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
      let msgCtxFocusTarget = null;
      let msgLongPress = null;
      let msgLongPressSuppress = null;
      let msgLongPressDispatching = false;
      const msgLongPressScope = () => JSON.stringify([msgState.chatAppid, msgState.chatType, msgState.chatId, msgState.scopeGeneration]);
      const cancelMsgLongPress = () => {
        if (msgLongPress) clearTimeout(msgLongPress.timer);
        msgLongPress = null;
      };
      const msgLongPressCurrent = (press) => press?.row.isConnected && press.target.isConnected
        && activeView === 'messages' && document.visibilityState !== 'hidden' && press.scope === msgLongPressScope();
      const suppressMsgLongPressEvent = (event) => {
        const press = msgLongPressSuppress;
        if (!press || press.until < Date.now() || !msgLongPressCurrent(press)) { msgLongPressSuppress = null; return false; }
        return press.row.contains(event.target);
      };
      document.addEventListener('pointerdown', (event) => {
        cancelMsgLongPress(); msgLongPressSuppress = null;
        if (event.pointerType !== 'touch' || !event.isPrimary || event.button !== 0
          || activeView !== 'messages' || document.visibilityState === 'hidden') return;
        const target = event.target;
        const row = target.closest?.('.msg-row');
        if (!row || !$('msg-body')?.contains(row)
          || target.closest('button,a,input,textarea,select,video,audio,[contenteditable="true"],[data-msg-jump]')) return;
        const press = {row, target, pointerId:event.pointerId, x:event.clientX, y:event.clientY, scope:msgLongPressScope(), timer:null};
        press.timer = setTimeout(() => {
          if (msgLongPress !== press) return;
          msgLongPress = null;
          if (!msgLongPressCurrent(press)) return;
          msgLongPressSuppress = {...press, until:Date.now() + 1200};
          msgLongPressDispatching = true;
          try {
            target.dispatchEvent(new MouseEvent('contextmenu', {bubbles:true, cancelable:true, view:window, clientX:press.x, clientY:press.y}));
          } finally { msgLongPressDispatching = false; }
        }, 550);
        msgLongPress = press;
      }, {capture:true, passive:true});
      document.addEventListener('pointermove', (event) => {
        const press = msgLongPress;
        if (press && (event.pointerId !== press.pointerId || Math.hypot(event.clientX - press.x, event.clientY - press.y) > 10)) cancelMsgLongPress();
      }, {capture:true, passive:true});
      ['pointerup', 'pointercancel'].forEach((type) => document.addEventListener(type, cancelMsgLongPress, {capture:true, passive:true}));
      document.addEventListener('contextmenu', (event) => {
        if (msgLongPressDispatching) return;
        if (suppressMsgLongPressEvent(event)) { event.preventDefault(); event.stopImmediatePropagation(); return; }
        const press = msgLongPress;
        if (press && press.row.contains(event.target) && msgLongPressCurrent(press)) msgLongPressSuppress = {...press, until:Date.now() + 1200};
        cancelMsgLongPress();
      }, true);
      document.addEventListener('click', (event) => {
        if (!suppressMsgLongPressEvent(event)) return;
        event.preventDefault(); event.stopImmediatePropagation();
      }, true);
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') { cancelMsgLongPress(); msgLongPressSuppress = null; }
      });
      const showMsgCtx = (x, y, items, focusTarget = null) => {
        const ctx = $('msg-ctx');
        msgCtxFocusTarget = focusTarget || document.activeElement;
        ctx.setAttribute('role', 'menu');
        ctx.innerHTML = items.map((it) => it.sep ? '<div class="msg-ctx-sep" role="separator"></div>' : `<button class="msg-ctx-item${it.danger ? ' danger' : ''}" type="button" role="menuitem">${esc(it.label)}</button>`).join('');
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
          btn.addEventListener('click', () => { hideMsgCtx(true); if (item && item.action) item.action(); });
        });
        ctx.querySelector('.msg-ctx-item')?.focus({preventScroll:true});
      };
      const hideMsgCtx = (restoreFocus = false) => {
        cancelMsgLongPress();
        const ctx = $('msg-ctx');
        const previous = msgCtxFocusTarget;
        msgCtxFocusTarget = null;
        ctx.hidden = true; ctx.innerHTML = '';
        if (restoreFocus && previous?.isConnected && previous.getClientRects().length) previous.focus({preventScroll:true});
      };
      document.addEventListener('click', (e) => { if (!$('msg-ctx').contains(e.target)) hideMsgCtx(); });
      document.addEventListener('contextmenu', (e) => { if (!$('msg-ctx').contains(e.target)) hideMsgCtx(); });
      document.addEventListener('keydown', (e) => {
        const ctx = $('msg-ctx');
        if (ctx.hidden) return;
        if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); hideMsgCtx(true); return; }
        if (!ctx.contains(e.target) || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return;
        const buttons = [...ctx.querySelectorAll('.msg-ctx-item')];
        if (!buttons.length) return;
        e.preventDefault();
        const current = buttons.indexOf(document.activeElement);
        const next = e.key === 'Home' ? 0 : e.key === 'End' ? buttons.length - 1
          : (current + (e.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
        buttons[next].focus({preventScroll:true});
      });
      const canRecallMsgRow = (row) => {
        const isSelf = row.dataset.msgSelf === '1';
        const protectedRole = !isSelf && ['owner', 'admin'].includes(String(row.dataset.msgRole || '').toLowerCase());
        return Boolean(row.dataset.msgMid) && row.dataset.msgRecalled !== '1'
          && !msgState.optimisticSends.get(row.dataset.msgOptimistic || '')
          && (isSelf || (msgState.botIsAdmin && !protectedRole));
      };
      const buildMsgRowContextItems = (row) => {
        if (!row) return [];
        const mid = row.dataset.msgMid;
        const uid = row.dataset.msgUid;
        const nick = row.dataset.msgNick;
        const isSelf = row.dataset.msgSelf === '1';
        const content = row.dataset.msgContent || '';
        const refidx = row.dataset.msgRefidx || '';
        const optimistic = msgState.optimisticSends.get(row.dataset.msgOptimistic || '');
        const protectedRole = !isSelf && ['owner', 'admin'].includes(String(row.dataset.msgRole || '').toLowerCase());
        const canMute = !isSelf && msgState.chatType === 'group' && uid && msgState.botIsAdmin && !protectedRole;
        const canRecall = canRecallMsgRow(row);
        const items = [];
        if (!isSelf && msgState.chatType === 'group' && uid) items.push({label:'@' + (nick || 'TA'), action:() => atMember(uid, nick)});
        if (canMute) {
          items.push({label:'禁言', action:() => openMuteDialog(uid, nick)});
          const mute = msgState.mutes.get(uid);
          const expires = Number(mute?.mute_expire_ts || 0);
          if (mute && (!expires || expires > Date.now() / 1000)) items.push({label:'解除禁言', action:() => unmuteMember(uid, nick)});
        }
        if (items.length && !isSelf) items.push({sep:true});
        if (mid && (!optimistic || (optimistic.status || row.dataset.msgSendStatus) === 'sent')) items.push({label:'引用', action:() => setMsgQuote(mid, uid, nick, content, refidx)});
        if (content) items.push({label:'复制', action:() => copyMsgText(content, row)});
        if (canRecall) items.push({label:'撤回', danger:true, action:() => recallMessage(mid)});
        const rawKey = row.dataset.msgRawKey || '';
        if (rawKey && Object.prototype.hasOwnProperty.call(window._msgRaw || {}, rawKey)) items.push({label:'原始数据', action:() => {
          $('msg-raw-content').textContent = formatMsgRaw(window._msgRaw?.[rawKey]);
          $('msg-raw-copy').textContent = '复制';
          setMsgModal('msg-raw-modal', true);
        }});
        if (mid) items.push({sep:true});
        items.push({label:'多选', action:() => { enterMultiMode(); if (canRecall) toggleMsgSelect(row, mid); }});
        return items;
      };
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
            const copyHost = activeMsgModal()?.querySelector('[role=dialog]') || document.querySelector('dialog[open]') || document.body;
            copyHost.appendChild(ta);
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
        const target = {chat_id:msgState.chatId, chat_type:msgState.chatType, appid:msgState.chatAppid};
        let okCount = 0; let failCount = 0;
        for (const id of ids) {
          if (!msgMatchesCurrent(target.chat_type, target.chat_id, target.appid)) return;
          try { await api('message/recall', {method:'POST', body:JSON.stringify({...target, message_id:id})}); if (!msgMatchesCurrent(target.chat_type, target.chat_id, target.appid)) return; markLocalMessageRecalled(id); okCount++; }
          catch (error) { if (!msgMatchesCurrent(target.chat_type, target.chat_id, target.appid)) return; failCount++; }
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
          ['items','_lanzou_archive','_lanzou_archives','_quark_archives'].forEach((key) => delete result[key]);
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
      const msgMediaArchivePaths = new Set(['/api/message/lanzou-image', '/api/message/quark-media']);
      const msgMediaArchiveProxy = (item, messageId, scope = {}) => {
        if (item?.archived !== true || !messageId) return null;
        const src = msgMediaItemUrl(item);
        if (![...msgMediaArchivePaths].some((path) => src.startsWith(`${path}?`))) return null;
        try {
          const url = new URL(src, 'https://mantou.invalid');
          if (url.origin !== 'https://mantou.invalid' || !msgMediaArchivePaths.has(url.pathname)
            || url.searchParams.get('message_id') !== String(messageId)) return null;
          const rawIndex = url.searchParams.get('media_index') || '';
          const index = Number(rawIndex), chatId = url.searchParams.get('chat_id') || '', chatType = url.searchParams.get('chat_type') || '';
          if (!/^\d+$/.test(rawIndex) || !Number.isSafeInteger(index) || !chatId || !['group','user'].includes(chatType)) return null;
          const expectedId = String(scope.chat_id || scope._session || '').trim();
          const expectedType = String(scope.chat_type || '').trim();
          if ((expectedId && expectedId !== chatId) || (expectedType && expectedType !== chatType)) return null;
          return {index, chatId, chatType, provider:url.pathname === '/api/message/quark-media' ? 'quark' : 'lanzou'};
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
          const nextProxy = msgMediaArchiveProxy(item, messageId, scope);
          const currentProxy = msgMediaArchiveProxy(items[index], messageId, scope);
          if (nextProxy?.index === index && !(currentProxy?.provider === 'quark' && nextProxy.provider === 'lanzou')) {
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
        ['_lanzou_archive','_lanzou_archives','_quark_archives'].forEach((key) => delete result[key]);
        return result;
      };
      const mergeMsgRealtimeMessage = (existing, incoming) => {
        const merged = {...existing};
        if (Array.isArray(incoming?.reference_ids)) merged.reference_ids = incoming.reference_ids.slice(0, 8);
        if (typeof incoming?.reference_conflict === 'boolean') merged.reference_conflict = incoming.reference_conflict;
        if (typeof incoming?.is_bot === 'boolean') merged.is_bot = incoming.is_bot;
        const privateContact = msgPrivateContactScope(incoming?.user_id || existing?.user_id, incoming || {})
          && msgPrivateContactScope(existing?.user_id, existing || {});
        const oldNameState = privateContact ? msgNicknameState(existing, existing.user_id) : null;
        const newNameState = privateContact ? msgNicknameState(incoming, incoming?.user_id || existing.user_id) : null;
        ['user_id', 'nickname', 'content', 'timestamp', 'source', 'member_role', 'msg_seq', 'avatar', 'reference_id', 'refidx', 'chat_type', 'appid'].forEach((field) => {
          if (field === 'nickname' && privateContact) return;
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
        if (privateContact && newNameState && (!oldNameState || newNameState.nickname_ts >= oldNameState.nickname_ts)
          && !(oldNameState?.nickname_blank && !newNameState.nickname_blank && newNameState.nickname_ts === oldNameState.nickname_ts)) {
          Object.assign(merged, newNameState);
        } else if (!privateContact && validMsgNickname(merged.nickname, merged.user_id)) merged.nickname_blank = false;
        else if (!privateContact && incoming?.nickname_blank) merged.nickname_blank = true;
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
          if (!entry || String(entry.chatId || '') !== id || entry.chatType !== msgState.chatType || String(entry.payload?.appid || '') !== msgState.chatAppid || !entry.message) return;
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
          if (msgMatchesCurrent(entry.chatType, entry.chatId, entry.payload.appid)) {
            renderOptimisticMessages(entry.chatId);
            msgState.historyCache.delete(msgScopeKey(entry.chatType, entry.chatId, entry.payload.appid));
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
          if (msgMatchesCurrent(entry.chatType, entry.chatId, entry.payload.appid)) toast('发送失败，点击感叹号重试');
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
      const syncMsgNewMessagesDisplay = () => {
        const button = $('msg-new-messages');
        if (!button) return;
        const body = $('msg-body');
        const count = Number(msgState.pendingNewMessages || 0);
        const text = msgState.historyWindow
          ? `返回最新消息${count > 0 ? ` · ${count} 条新消息` : ''}`
          : count > 0 ? `有 ${count} 条新消息` : '回到底部';
        const visible = !$('page-messages')?.hidden && document.visibilityState !== 'hidden';
        const ready = Boolean(msgState.chatId && msgState.chatAppid === msgState.selectedAppid
          && (msgState.messages.length || msgState.historyWindow));
        const hidden = !visible || !ready || (!msgState.historyWindow && count === 0 && msgBodyNearBottom(body));
        const label = $('msg-new-messages-label');
        if (label) label.textContent = text;
        const dot = button.querySelector('.msg-new-messages-dot');
        if (dot) dot.hidden = count === 0;
        button.title = text;
        button.setAttribute('aria-label', text);
        if (hidden && !button.hidden && document.activeElement === button && visible) body?.focus({preventScroll:true});
        button.hidden = hidden;
      };
      const clearMsgNewMessages = () => {
        msgState.pendingNewMessages = 0;
        syncMsgNewMessagesDisplay();
      };
      const showMsgNewMessages = (count) => {
        msgState.pendingNewMessages = Math.max(1, Number(msgState.pendingNewMessages || 0) + Number(count || 0));
        syncMsgNewMessagesDisplay();
      };
      const scrollMsgToBottom = (behavior = 'smooth') => {
        const body = $('msg-body');
        if (!body || !msgState.chatId || $('page-messages')?.hidden || document.visibilityState === 'hidden') return;
        cancelMsgQuoteJump();
        cancelMsgBottomPosition(body, true);
        if (msgState.historyWindow) {
          msgState.initialScrollChatId = msgState.chatId;
          void loadMsgHistory();
          return;
        }
        const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
        if (typeof body.scrollTo === 'function') body.scrollTo({top:body.scrollHeight, behavior:reduced ? 'auto' : behavior});
        else body.scrollTop = body.scrollHeight;
        clearMsgNewMessages();
        markMsgRead(undefined, true, msgState.chatType, msgState.chatAppid);
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
            && msgMediaArchivePaths.has(current.pathname) && !state.autoRetried) {
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
      const mediaProxyUrl = (src, mode = 'image', name = '', appid = consoleAppid) => {
        const direct = safeMediaUrl(src);
        if (!direct) return '';
        try {
          const host = new URL(direct).hostname.toLowerCase().replace(/\.$/, '');
          const allowed = ['multimedia.nt.qq.com.cn', 'qqbot.ugcimg.cn', 'gchat.qpic.cn', 'qpic.cn', 'qlogo.cn', 'qq.com.cn', 'qq.com'];
          const shouldProxy = allowed.some((suffix) => host === suffix || host.endsWith(`.${suffix}`));
          if (!shouldProxy) return direct;
          const query = new URLSearchParams({src: direct, mode: mode === 'image' ? 'image' : 'file'});
          if (/^\d{4,32}$/.test(String(appid || ''))) query.set('appid', appid);
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
        if (size < 1024 * 1024) return `${Number((size / 1024).toFixed(1))} KB`;
        if (size < 1024 * 1024 * 1024) return `${Number((size / 1024 / 1024).toFixed(1))} MB`;
        return `${Number((size / 1024 / 1024 / 1024).toFixed(1))} GB`;
      };
      const renderMessageFileIcon = (type) => type === '视频' ? '▶' : type === '语音' ? '♫'
        : '<svg viewBox="0 0 42 50" width="42" height="50" aria-hidden="true" focusable="false"><use href="#msg-document-symbol"/></svg>';
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
          const meta = [['文件', 'file'].includes(typeLower) ? '' : type, size].filter(Boolean).join(' · ') || type || '附件';
          if (!src) return `<div data-msg-media-key="${mediaKey}" class="msg-media msg-file-card is-unavailable"><span class="msg-file-icon">${renderMessageFileIcon(type)}</span><span class="msg-file-info"><strong>${esc(name)}</strong><small>${esc(meta)} · 未提供下载地址</small></span></div>`;
          const download = name ? ` download="${esc(name)}"` : '';
          if (browserKey) return `<a data-msg-media-key="${mediaKey}" class="msg-media msg-file-card" data-browser-media-key="${esc(browserKey)}"${download}><span class="msg-file-icon">${renderMessageFileIcon(type)}</span><span class="msg-file-info"><strong>${esc(name)}</strong><small>${esc(meta)}</small></span><span class="msg-file-action">下载<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/></svg></span></a>`;
          const fileUrl = mediaProxyUrl(src, 'file', name);
          return `<a data-msg-media-key="${mediaKey}" class="msg-media msg-file-card" href="${esc(fileUrl || src)}" target="_blank" rel="noopener noreferrer"${download}><span class="msg-file-icon">${renderMessageFileIcon(type)}</span><span class="msg-file-info"><strong>${esc(name)}</strong><small>${esc(meta)}</small></span><span class="msg-file-action">下载<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/></svg></span></a>`;
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
        // 附件类型由发送时的 hasMedia 决定，保留原文字模式供移除或发送后继续使用。
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
          const row = img.closest('.msg-row');
          if (row && msgState.multi) {
            if (canRecallMsgRow(row)) toggleMsgSelect(row, row.dataset.msgMid);
            return;
          }
          const source = img.currentSrc || img.dataset.mediaDirect || img.src;
          const items = [{label:'复制图片', action:() => copyImageToClipboard(source, img)}];
          const rowItems = buildMsgRowContextItems(row);
          if (rowItems.length) items.push({sep:true}, ...rowItems);
          showMsgCtx(event.clientX, event.clientY, items, row);
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
        setMsgModal('msg-mute-modal', true);
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
        if (raw && typeof raw === 'object') {
          try { return JSON.stringify(sortMsgRawValue(raw), null, 2); }
          catch (_) { return String(raw); }
        }
        const source = typeof raw === 'string' ? raw : raw == null ? '' : String(raw);
        if (!source.trim()) return '无原始数据';
        try {
          return JSON.stringify(sortMsgRawValue(JSON.parse(source)), null, 2);
        } catch (_) {
          // 旧记录可能已截断，或者上游给出的不是 JSON；保留原文供排查。
          return source;
        }
      };
      const outgoingSnapshotMediaFields = ['type', 'media_type', 'content_type', 'name', 'filename', 'file_name', 'size', 'width', 'height', 'text', 'before_text', 'after_text'];
      const copyOutgoingMediaSummary = (value) => {
        if (Array.isArray(value)) return value.map(copyOutgoingMediaSummary).filter(Boolean);
        if (!value || typeof value !== 'object') return null;
        const result = {};
        outgoingSnapshotMediaFields.forEach((field) => {
          const item = value[field];
          if (item !== undefined && item !== null && ['string', 'number', 'boolean'].includes(typeof item)) result[field] = item;
        });
        if (Array.isArray(value.items)) result.items = value.items.map(copyOutgoingMediaSummary).filter(Boolean);
        return Object.keys(result).length ? result : null;
      };
      const createOutgoingRecordSnapshot = (message) => {
        const snapshot = {
          _record_type: 'outgoing_message_snapshot',
          _record_note: '本地发送记录快照，不是 QQ 官方接口原始响应',
          id: message.id ?? null,
          message_id: String(message.message_id || message.messageId || message.id || ''),
          user_id: String(message.user_id || ''),
          nickname: String(message.nickname || ''),
          timestamp: String(message.timestamp || ''),
          source: String(message.source || ''),
          chat_type: String(message.chat_type || ''),
          appid: String(message.appid || ''),
          is_self: true,
          content: String(message.content || ''),
        };
        const media = copyOutgoingMediaSummary(message.media);
        if (media) snapshot.media = media;
        if (message.reference_id) snapshot.reference_id = String(message.reference_id);
        if (message.refidx) snapshot.refidx = String(message.refidx);
        if (Array.isArray(message.keyboard_buttons) && message.keyboard_buttons.length) snapshot.keyboard_buttons = message.keyboard_buttons;
        const reference = message.reference_preview;
        if (reference && typeof reference === 'object') {
          snapshot.reference_preview = Object.fromEntries(
            ['message_id', 'refidx', 'user_id', 'nickname', 'content']
              .filter((field) => reference[field] !== undefined && reference[field] !== null)
              .map((field) => [field, reference[field]]),
          );
        }
        return snapshot;
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
        if (!msgState.chatId || !msgState.chatAppid || msgState.chatAppid !== msgState.selectedAppid) return;
        if (data.appid && String(data.appid).trim() !== msgState.chatAppid) return;
        if (data.chat_id && String(data.chat_id) !== msgState.chatId) return;
        if (data.chat_type && String(data.chat_type) !== msgState.chatType) return;
        data = {...data, appid:msgState.chatAppid, messages:(data.messages || []).filter((message) => String(message?.appid || '').trim() === msgState.chatAppid)};
        const body = $('msg-body');
        const keepLatestVisible = !msgQuoteJump.pending && !msgState.historyWindow && !scroll.preservePosition
          && !scroll.prepend && (Boolean(scroll.toBottom) || msgBodyNearBottom(body));
        const initialPositioning = !scroll.prepend
          && msgState.initialScrollChatId === msgState.chatId
          && keepLatestVisible
          && (msgState.renderedChatId !== msgState.chatId || body.classList.contains('msg-positioning'));
        const renderScope = JSON.stringify([msgState.chatType, msgState.chatId,
          String(msgState.chatAppid || '').trim()]);
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
        // 会话 AppID 只由所选机器人和会话决定，历史消息不能反向切换发送身份。
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
          botProfile:botProfileForAppid(msgState.chatAppid),
          botRole:msgState.botRole,
          botIsAdmin:msgState.botIsAdmin,
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
          if (day !== lastDay && day) {
            const label = fmtDayLabel(m.timestamp);
            const clock = fmtMsgTime(m.timestamp);
            const separator = label === '今天' ? clock : [label, clock].filter(Boolean).join(' ');
            html += `<div class="msg-day" title="${esc(label)}">${esc(separator)}</div>`;
            lastDay = day;
          }
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
          const botProfile = botProfileForAppid(m.appid || msgState.chatAppid);
          const botProfileName = String(botProfile.username || '').trim();
          const botProfileAvatar = String(botProfile.avatar || '').trim();
          const profileAvatar = safeMediaUrl(String(profile.avatar || profile.avatar_url || '').trim());
          const muteState = !isSelf ? msgState.mutes.get(String(m.user_id || '').trim()) : null;
          const muteExpireTs = Number(muteState?.mute_expire_ts || 0);
          const isMuted = Boolean(muteState) && (!muteExpireTs || muteExpireTs > Date.now() / 1000);
          const displayNickname = isSelf
            ? (botMessage
              ? (botProfileName || (rawNickname && !['未知用户', '未知', '机器人', '我'].includes(rawNickname) ? rawNickname : '机器人'))
              : (rawNickname && rawNickname !== '未知用户' ? rawNickname : '我'))
            : displayMsgNickname(m, profile);
          const av = isSelf && botMessage ? botProfileAvatar : (isSelf ? '' : (profileAvatar || avatarUrl(m.user_id, 'user', m.appid || msgState.chatAppid)));
          const tags = [];
          if (msgIsBot(m, profile)) tags.push('<span class="msg-tag bot">BOT</span>');
          else if (isSelf) tags.push('<span class="msg-tag self">我</span>');
          if (m.source === 'web_panel') tags.push('<span class="msg-tag">网页</span>');
          if (recalled) tags.push('<span class="msg-tag recalled">已撤回</span>');
          if (isMuted) tags.push('<span class="msg-tag muted" data-msg-mute-tag="1">被禁言</span>');
          const roleMap = {owner:'群主', admin:'管理员', member:'群成员'};
          const messageRole = msgMemberRole(m, profile);
          const botRole = currentBotMemberRole(m, isSelf);
          const memberRole = botRole || messageRole;
          const protectedRole = !isSelf && (memberRole === 'owner' || memberRole === 'admin');
          const roleTag = msgState.chatType === 'group' && String(m.chat_type || 'group') === 'group'
            ? (roleMap[memberRole] || '') : '';
          if (roleTag) tags.push(`<span class="msg-tag role ${memberRole}">${roleTag}</span>`);
          // 群消息发送者的展示标签不代表已确认的权限角色。
          const showGroupMember = !roleTag && !isSelf && !msgIsBot(m, profile)
            && msgState.chatType === 'group' && String(m.chat_type || 'group') === 'group'
            && (!m.appid || String(m.appid).trim() === String(msgState.chatAppid))
            && String(m.chat_id || m._session || msgState.chatId) === String(msgState.chatId)
            && ['', 'qq_official'].includes(systemSource) && Boolean(String(m.user_id || '').trim());
          if (showGroupMember) tags.push('<span class="msg-tag group-member">群成员</span>');
          const renderText = (text) => String(text || '');
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
          const plainContent = plainMsgPreview(m.content || '', profiles);
          const isWelcomeMessage = botMessage && msgState.chatType === 'group'
            && /^欢迎\s*@.+?\s+加入本群/.test(plainContent)
            && /点击下方按钮查看使用教程和小说列表/.test(plainContent);
          const keyboardHtml = renderMsgKeyboardButtons(m.keyboard_buttons);
          const welcomeKeyboardHtml = keyboardHtml || (isWelcomeMessage
            ? '<div class="msg-inline-keyboard" role="group" aria-label="QQ消息按钮预览"><div class="msg-inline-keyboard-row" style="--msg-keyboard-cols:2"><span class="msg-inline-keyboard-button" aria-disabled="true">使用教程</span><span class="msg-inline-keyboard-button" aria-disabled="true">小说列表</span></div></div>'
            : '');
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
          const rawIdentity = String(m.id || m.message_id || m.messageId || `${m.timestamp || ''}_${m.user_id || ''}`).trim();
          const rawKey = `${msgState.chatId}_${rawIdentity}`;
          const hasRawMessage = typeof m.raw_message === 'string'
            ? Boolean(m.raw_message.trim())
            : m.raw_message !== undefined && m.raw_message !== null && m.raw_message !== false;
          const outgoingSnapshot = isSelf && !hasRawMessage && !['pending', 'failed'].includes(sendState)
            ? createOutgoingRecordSnapshot(m)
            : null;
          const hasRawData = hasRawMessage || Boolean(outgoingSnapshot);
          if (hasRawData) {
            renderedRawKeys.add(rawKey);
            rawStore[rawKey] = hasRawMessage ? m.raw_message : outgoingSnapshot;
          }
          const isSelected = msgState.selected.has(m.message_id);
          const multiEnabled = canRecall;
          const sendStateHtml = failedSend
            ? `<button class="msg-send-error" data-msg-retry="${esc(optimisticId)}" type="button" title="发送失败，点击重试" aria-label="发送失败，点击重试">!</button>`
            : '';
          const muteStatusHtml = isMuted
            ? `<span class="msg-mute-countdown" data-msg-mute-expire="${muteExpireTs}">${muteExpireTs ? `禁言剩余 ${formatMuteRemaining(muteExpireTs)}` : '已禁言'}</span>`
            : '';
          html += `<div class="msg-row ${isSelf ? 'self' : ''}${isMuted ? ' muted' : ''}${msgState.multi ? ' multi-mode' : ''}${isSelected ? ' selected' : ''}${multiEnabled ? '' : ' no-multi'}${optimisticEntry ? ' optimistic' : ''}" tabindex="0" aria-haspopup="menu" aria-label="消息，右键或按 Shift+F10 打开操作菜单" data-msg-render-key="${esc(renderKey)}" data-msg-mid="${esc(m.message_id)}" data-msg-uid="${esc(m.user_id)}" data-msg-nick="${esc(displayNickname)}" data-msg-refidx="${esc(m.refidx || '')}" data-msg-role="${esc(memberRole)}" data-msg-self="${isSelf ? '1' : ''}" data-msg-recalled="${recalled ? '1' : ''}" data-msg-optimistic="${esc(optimisticId)}" data-msg-send-status="${esc(sendState)}" data-msg-raw-key="${hasRawData ? esc(rawKey) : ''}" data-msg-content="${esc(m.content || '')}">
            <span class="msg-pos">
              <span class="msg-multi-check"></span>
              <span class="msg-avatar${isMuted ? ' muted' : ''}">${avatarHtml(av, displayNickname || '?')}</span>
            </span>
            <div class="msg-bubble-wrap"><div class="msg-bubble-name">${esc(displayNickname)}${tags.length ? `<span class="msg-tags">${tags.join('')}</span>` : ''}</div>
              <div class="msg-bubble ${recalled ? 'recalled' : ''}">${quote}${segmentedMedia || (hasInlineMediaText ? inlineMediaHtml : `${contentHtml ? `<div class="msg-text-content">${contentHtml}</div>` : ''}${media}`)}${welcomeKeyboardHtml}</div>
              ${muteStatusHtml || sendStateHtml ? `<div class="msg-meta">${muteStatusHtml}${sendStateHtml}</div>` : ''}
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
        syncMsgNewMessagesDisplay();
        bindMsgEvent(body.querySelector('#msg-load-older'), 'click', 'load-older', () => loadMsgHistory(true));
        bindMsgEvent(body.querySelector('#msg-load-newer'), 'click', 'load-newer', () => loadMsgWindowPage('after'));
        body.querySelectorAll('[data-msg-jump]').forEach((el) => bindMsgEvent(el, 'click', 'quote-jump', (event) => {
          event.preventDefault(); event.stopPropagation();
          void jumpToMsgReference(el.dataset.msgJump);
        }));
        body.querySelectorAll('[data-msg-retry]').forEach((el) => bindMsgEvent(el, 'click', 'retry', (event) => { event.preventDefault(); event.stopPropagation(); retryOptimisticSend(el.dataset.msgRetry); }));
        body.querySelectorAll('[data-lightbox]').forEach((img) => bindMsgEvent(img, 'click', 'lightbox', (event) => { event.preventDefault(); openMsgLightbox(img.dataset.lightbox); }));
        body.querySelectorAll('[data-msg-command]').forEach((el) => bindMsgEvent(el, 'click', 'command', () => {
          const command = String(el.dataset.msgCommand || '').trim();
          if (!command || !getComposerEditor()) return;
          insertComposerText(command);
          toast(`已填入 ${command}`);
        }));
        body.querySelectorAll('.msg-row').forEach((row) => {
          const openRowContext = (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (msgState.multi) {
              if (canRecallMsgRow(row)) toggleMsgSelect(row, row.dataset.msgMid);
              return;
            }
            const items = buildMsgRowContextItems(row);
            const rect = row.getBoundingClientRect();
            const pointer = e.type === 'contextmenu' && (e.clientX || e.clientY);
            if (items.length) showMsgCtx(pointer ? e.clientX : rect.left + 24, pointer ? e.clientY : rect.top + Math.min(24, rect.height / 2), items, row);
          };
          bindMsgEvent(row, 'contextmenu', 'message-context', (e) => {
            if (e.target.closest('.msg-inline-keyboard-link')) return;
            openRowContext(e);
          });
          bindMsgEvent(row, 'keydown', 'message-context-keyboard', (e) => {
            if (e.key === 'ContextMenu' || (e.shiftKey && e.key === 'F10')) openRowContext(e);
          });
          bindMsgEvent(row, 'click', 'message-select', (e) => {
            if (msgState.multi && !e.target.closest('button, a')) {
              const canSel = canRecallMsgRow(row);
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
        const eventKeys = keys.map((key) => `${msgScopeKey(message.chat_type || msgState.chatType, chatId, message.appid || msgState.selectedAppid)}:${key}`);
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
        if (!chatId || !message || !msgInSelectedBot({appid:payload.appid || message.appid})) return;
        const chatType = String(payload.chat_type || message.chat_type || 'group');
        if (msgIsKnownCleared(message, chatType, chatId, payload.appid || message.appid)) return;
        const chatKey = msgScopeKey(chatType, chatId, payload.appid || message.appid);
        const existing = msgState.realtimeChats.get(chatKey) || msgState.chats.find((chat) => msgChatKey(chat) === chatKey) || {};
        const eventAppid = String(payload.appid || message.appid || existing.appid || '').trim();
        if (payload.chat_type && message.chat_type && String(payload.chat_type) !== String(message.chat_type)) return;
        if (payload.appid && message.appid && String(payload.appid).trim() !== String(message.appid).trim()) return;
        if (existing.chat_type && String(existing.chat_type) !== chatType) return;
        if (existing.appid && eventAppid && String(existing.appid).trim() !== eventAppid) return;
        const currentAppid = String(msgState.chatAppid || msgState.historyData?.messages?.find((item) => item?.appid)?.appid || '').trim();
        const matchesCurrent = msgState.chatId === chatId && msgState.chatType === chatType
          && (!currentAppid || currentAppid === eventAppid);
        // 实时事件不能改变当前选中的机器人身份。
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
        const eventUserId = String(message.user_id || '').trim();
        const eventSource = String(message.source || '').trim();
        const eventIsSelf = Boolean(message.is_self)
          || eventSource.startsWith('bot_')
          || eventSource === 'web_panel';
        const eventIsContact = chatType === 'user' && eventUserId === chatId && !eventIsSelf
          && !msgIsBot(message, payload.member_profiles?.[eventUserId] || {});
        const isNewEvent = rememberMsgEvent(chatId, message);
        const friendState = chatType === 'user' ? syncMsgFriendState(chatId, {...payload, chat_type:chatType, appid:eventAppid}, isNewEvent && ['friend_add','friend_del'].includes(String(message.source || ''))) : {};
        const friendChanged = chatType === 'user' && (String(friendState.friend_status || '') !== String(existing.friend_status || '') || Number(friendState.friend_checked_at || 0) !== Number(existing.friend_checked_at || 0));
        let profilesChanged = false;
        if (matchesCurrent && (chatType !== 'user' || eventIsContact)) {
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
        if (isNewEvent) msgState.historyCache.delete(msgScopeKey(chatType, chatId));
        const isViewing = matchesCurrent && !$('page-messages')?.hidden;
        const body = $('msg-body');
        const followLatest = isViewing && !msgQuoteJump.pending && !msgState.historyWindow
          && msgState.pendingNewMessages === 0 && msgBodyNearBottom(body);
        if (isNewEvent && !followLatest) msgReadOverrides.delete(chatKey);
        const payloadUnread = Number(payload.unread);
        const fallbackUnread = Math.max(0, Number(existing.unread || 0) + (isNewEvent ? 1 : 0));
        const unread = followLatest
          ? 0
          : (Number.isFinite(payloadUnread) ? Math.max(0, payloadUnread) : fallbackUnread);
        const eventAvatar = String(
          message.avatar
          || payload.member_profiles?.[eventUserId]?.avatar
          || '',
        ).trim();
        const existingAvatar = String(existing.avatar || existing.avatar_url || '').trim();
        const contactProfile = (matchesCurrent ? msgState.profiles?.[chatId] : eventIsContact ? payload.member_profiles?.[chatId] : {}) || {};
        const contactAvatar = String(contactProfile.avatar || '').trim();
        const botAvatar = String(botProfileForAppid(payload.appid || message.appid || existing.appid).avatar || '').trim();
        const preservedAvatar = contactAvatar
          || (existingAvatar && (!botAvatar || existingAvatar !== botAvatar) ? existingAvatar : '');
        const overlayAvatar = chatType === 'user' && !eventIsContact
          ? preservedAvatar
          : (eventAvatar || preservedAvatar);
        const eventContactName = eventIsContact ? validMsgNickname(message.nickname, chatId) : '';
        const previousContactName = validMsgNickname(existing._private_nickname, chatId)
          || validMsgNickname(existing.nickname, chatId) || validMsgNickname(contactProfile.nickname || contactProfile.username, chatId);
        const eventContactBlank = eventIsContact
          && Boolean(message.nickname_blank === true || isBlankMsgNickname(message.nickname));
        const contactNameTs = Number(message.nickname_ts ?? message.ts ?? 0);
        const previousContactState = pickMsgNicknameState(chatId, existing, contactProfile);
        const oldContactNameTs = Number(previousContactState?.nickname_ts || 0);
        const previousContactKnown = Boolean(previousContactName || previousContactState?.nickname_blank);
        const contactNameChanged = (eventContactName || eventContactBlank)
          && (!oldContactNameTs || (contactNameTs && contactNameTs >= oldContactNameTs))
          && !(previousContactState?.nickname_blank && !eventContactBlank && contactNameTs === oldContactNameTs)
          && (isNewEvent || !previousContactKnown || contactNameTs > oldContactNameTs
            || (eventContactBlank && !previousContactState?.nickname_blank && contactNameTs === oldContactNameTs));
        const contactPatch = contactNameChanged
          ? {_private_nickname:eventContactBlank ? '' : eventContactName, _private_nickname_blank:eventContactBlank, _private_nickname_ts:contactNameTs,
            nickname_blank:eventContactBlank, nickname_ts:contactNameTs} : {};
        const contactName = contactNameChanged ? (eventContactBlank ? '\u00a0' : eventContactName)
          : (msgLivePrivateNickname(existing, chatId) || (existing.nickname_blank ? '\u00a0' : existing.nickname) || chatId);
        const overlay = {
          ...existing,
          chat_id:chatId,
          chat_type:chatType,
          appid:String(payload.appid || message.appid || existing.appid || ''),
          nickname:chatType === 'user' ? (existing.remark || contactName) : (existing.nickname || chatId),
          ...contactPatch,
          avatar:overlayAvatar,
          ...msgRealtimeChatSummary(payload, message, existing),
          ...friendState,
          msg_count:Math.max(0, Number(existing.msg_count || 0) + (isNewEvent ? 1 : 0)),
          unread,
        };
        msgState.realtimeChats.set(chatKey, overlay);
        if (friendChanged || contactNameChanged || isNewEvent || overlay.last_content !== existing.last_content || overlay.last_ts !== existing.last_ts
          || !msgState.chats.some((chat) => msgChatKey(chat) === chatKey)) {
          scheduleMsgChatRender();
        }
        if (!isViewing) return;
        if (friendChanged || contactNameChanged) updateMsgHead({...msgState.historyData, ...friendState, chat_name:overlay.nickname});
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
        if (isNewEvent && followLatest) markMsgRead(chatId, true, chatType, eventAppid);
      };
      const applyMsgGroupStatus = (payload) => {
        if (!msgInSelectedBot(payload) || (payload.chat_type && payload.chat_type !== 'group')) return;
        const chatId = String(payload?.chat_id || '').trim();
        if (!chatId) return;
        const membership = syncMsgGroupState(chatId, payload, payload.appid);
        if ((readMsgGroupState(payload)?.membership_revision || 0) < membership.membership_revision) return;
        const removed = membership.membership_status === 'removed';
        if (removed) {
          const localAdmins = getLocalAdminGroups();
          localAdmins.delete(chatId);
          saveLocalAdminGroups(localAdmins);
          msgState.adminByChat.set(chatId, false);
        }
        if (msgState.chatId === chatId && msgState.chatType === 'group') {
          updateMsgHead({chat_name:(msgState.chats.find((chat) => String(chat.chat_id || '') === chatId && chat.chat_type === 'group')?.nickname || chatId), group_info:membership});
        }
        renderMsgChats({chats:msgState.chats});
      };
      const applyMsgGroupInfo = (payload) => {
        if (!msgInSelectedBot(payload) || (payload.chat_type && payload.chat_type !== 'group')) return;
        const chatId = String(payload?.chat_id || payload?.group_openid || '').trim();
        if (!chatId) return;
        const memberNum = msgKnownGroupMemberCount(payload?.member_num, payload?.group_member_num);
        const groupName = String(payload?.group_name || '').trim();
        const appid = String(payload?.appid || '').trim();
        const updatedAt = Number(payload?.updated_at || 0);
        const membership = syncMsgGroupState(chatId, payload, appid);
        const update = (chat) => {
          if (String(chat.chat_id || '') !== chatId || String(chat.chat_type || 'group') !== 'group' || (appid && chat.appid && String(chat.appid) !== appid)) return chat;
          if (updatedAt && Number(chat.group_info_updated_at || 0) > updatedAt) return chat;
          const next = {...chat};
          if (memberNum !== null) next.member_num = next.group_member_num = memberNum;
          if (groupName) { next.group_name = groupName; next.nickname = String(next.remark || groupName); }
          groupProfileFields.forEach((field) => {
            const value = payload[field];
            if (field === 'group_tags' ? Array.isArray(value) : typeof value === 'string') next[field] = field === 'group_tags' ? value.filter((tag) => typeof tag === 'string') : value;
          });
          if (updatedAt) next.group_info_updated_at = updatedAt;
          return next;
        };
        msgState.chats = (msgState.chats || []).map(update);
        const current = msgState.chats.find((chat) => String(chat.chat_id || '') === chatId
          && String(chat.chat_type || 'group') === 'group' && String(chat.appid || '') === appid);
        const overlay = msgState.realtimeChats.get(msgScopeKey('group', chatId));
        if (overlay || current) msgState.realtimeChats.set(msgScopeKey('group', chatId), update(overlay || current));
        if (msgState.chatId === chatId && msgState.chatType === 'group') {
          updateMsgHead({group_info:current ? {group_name:current.group_name, member_num:current.member_num ?? current.group_member_num, updated_at:current.group_info_updated_at, ...membership} : payload});
        }
        const session = groupSettingsState.session;
        if (groupSettingsCurrent(session) && session.target.chat_id === chatId) renderGroupSettingsProfile(session, payload);
        if (groupName || readMsgGroupState(payload)) renderMsgChats({chats:msgState.chats});
      };

      const toggleMsgSelect = (row, mid) => {
        if (!mid) return;
        if (msgState.selected.has(mid)) { msgState.selected.delete(mid); row.classList.remove('selected'); }
        else { msgState.selected.add(mid); row.classList.add('selected'); }
        $('msg-multi-count').textContent = `已选 ${msgState.selected.size} 条`;
      };
      const loadMsgHistory = async (older = false, quiet = false, authoritative = false) => {
        if (!msgState.chatId) return;
        if (msgQuoteJump.pending || (quiet && msgState.historyWindow)) return;
        if (older && msgState.historyWindow) return loadMsgWindowPage('before');
        const returningWindow = !older ? msgState.historyWindow : null;
        if (returningWindow) cancelMsgQuoteJump();
        const requestScope = msgScopeKey(msgState.chatType, msgState.chatId, msgState.chatAppid);
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
        const requestAppid = msgState.chatAppid;
        const requestIsCurrent = () => requestId === Number(msgState[older ? 'historyOlderRequest' : 'historyRequest'] || 0)
          && msgMatchesCurrent(requestChatType, requestChatId, requestAppid);
        const body = $('msg-body');
        const newChat = msgState.renderedChatId !== msgState.chatId;
        const forceInitialBottom = !older && msgState.initialScrollChatId === requestChatId;
        const previousTop = body?.scrollTop || 0;
        const previousHeight = body?.scrollHeight || 0;
        const previousLast = !newChat ? msgMessageKey(msgState.messages[msgState.messages.length - 1]) : '';
        const historyCacheKey = msgScopeKey(requestChatType, requestChatId, requestAppid);
        const messagesAtRequest = new Set(msgState.messages.map(msgMessageKey));
        try {
          const before = older ? (msgState.messages[0]?.timestamp || '') : '';
          const beforeId = older ? Number(msgState.messages[0]?.id || 0) : 0;
          const historyLimit = older || msgState.historyCache.has(historyCacheKey)
            ? msgHistoryPageSize
            : msgHistoryInitialPageSize;
          const data = await api('message/history', {method:'POST', body:JSON.stringify({chat_id:requestChatId, chat_type:requestChatType, appid:requestAppid, before_date:beforeId ? '' : before, before_id:beforeId, limit:historyLimit}), signal:controller.signal});
          if (!requestIsCurrent() || (data.appid && String(data.appid).trim() !== requestAppid) || (data.chat_id && String(data.chat_id) !== requestChatId) || (data.chat_type && data.chat_type !== requestChatType)) return;
          data.messages = (data.messages || []).filter((message) => String(message?.appid || '').trim() === requestAppid
            && !msgIsKnownCleared(message, requestChatType, requestChatId, requestAppid));
          const incoming = mergeMsgRecalledStates(dedupeMsgMessages(data.messages));
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
          const preserveAfterClear = [...msgHistoryClearBoundaries.values()].some((boundary) => msgClearScopeMatches(boundary, requestChatType, requestChatId, requestAppid));
          if (returningWindow) msgState.historyWindow = null;
          msgState.messages = older
            ? dedupeMsgMessages([...incoming, ...currentMessages])
            : authoritative
              ? dedupeMsgMessages([...incoming, ...currentMessages.filter((message) => !messagesAtRequest.has(msgMessageKey(message)))])
              : ((preserveLoadedHistory || preserveAfterClear) ? dedupeMsgMessages([...currentMessages, ...incoming]) : incoming);
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
              if (!msgMatchesCurrent(requestChatType, requestChatId, requestAppid)) return;
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
      const rerenderMsgRoleTags = () => {
        if (msgState.chatType !== 'group' || !msgState.historyData || $('page-messages')?.hidden) return;
        const body = $('msg-body');
        renderMsgMessages(
          {...msgState.historyData, messages:msgState.messages, member_profiles:msgState.profiles},
          {preservePosition:true, previousTop:body?.scrollTop || 0, previousHeight:body?.scrollHeight || 0},
        );
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
          const previousMembership = msgState.chats.find((chat) => String(chat.chat_id || '') === requestChatId && chat.chat_type === 'group' && String(chat.appid || '') === target.appid)?.membership_status;
          const membership = syncMsgGroupState(requestChatId, data, target.appid);
          if ((readMsgGroupState(data)?.membership_revision || 0) < membership.membership_revision) return;
          const removed = membership.membership_status === 'removed';
          const current = msgState.chats.find((chat) => String(chat.chat_id || '') === requestChatId
            && chat.chat_type === 'group' && String(chat.appid || '').trim() === target.appid);
          updateMsgHead({chat_name:current?.nickname || requestChatId, group_info:membership});
          if (removed) {
            const roleChanged = msgState.botRole !== '' || msgState.botIsAdmin;
            msgState.botRole = '';
            msgState.botIsAdmin = false;
            msgState.adminByChat.set(requestChatId, false);
            renderMsgChats({chats:msgState.chats});
            if (roleChanged) rerenderMsgRoleTags();
            return;
          }
          if (membership.membership_status !== 'active') return;
          const role = normalizeMsgMemberRole(data.bot_role);
          if (!role) return;
          const roleChanged = msgState.botRole !== role || msgState.botIsAdmin !== (role === 'owner' || role === 'admin');
          msgState.botRole = role;
          composerMentionPicker.roles.set(JSON.stringify([requestChatId, target.appid]), role);
          const isAdmin = role === 'owner' || role === 'admin';
          msgState.adminByChat.set(requestChatId, isAdmin);
          msgState.adminScanFailures.delete(requestChatId);
          const localAdmins = getLocalAdminGroups();
          if (isAdmin) localAdmins.add(requestChatId);
          else localAdmins.delete(requestChatId);
          saveLocalAdminGroups(localAdmins);
          msgState.botIsAdmin = isAdmin;
          if (current) current.is_admin = isAdmin;
          updateMsgAdminTag();
          if (roleChanged) rerenderMsgRoleTags();
          if (previousMembership !== membership.membership_status) renderMsgChats({chats:msgState.chats});
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
        const target = {chat_id:msgState.chatId, chat_type:msgState.chatType, appid:msgState.chatAppid};
        if (!confirm('确定撤回这条消息吗？')) return;
        try { await api('message/recall', {method:'POST', body:JSON.stringify({...target, message_id:messageId})}); if (!msgMatchesCurrent(target.chat_type, target.chat_id, target.appid)) return; markLocalMessageRecalled(messageId); msgState.historyCache.delete(msgScopeKey(msgState.chatType, msgState.chatId, msgState.chatAppid)); toast('撤回成功'); loadMsgHistory(); }
        catch (error) { toast(error.message); }
      };
      const refreshGroupInfo = async () => {
        if (!msgState.chatId || msgState.chatType !== 'group') return;
        const chatId = String(msgState.chatId);
        const requestType = msgState.chatType;
        try {
          const data = await api('message/group-info/refresh', {method:'POST', body:JSON.stringify({chat_id:chatId})});
          msgState.historyCache.delete(msgScopeKey('group', chatId));
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
        const appid = String(msgState.chatAppid || msgState.selectedAppid || '');
        const isCurrent = () => msgMatchesCurrent(chatType, chatId, appid);
        button.disabled = true;
        try {
          if (chatId && chatType === 'user') {
            const data = await api('message/user-profile/refresh', {method:'POST', body:JSON.stringify({chat_id:chatId, chat_type:'user', appid})});
            if (!isCurrent() || (data.appid && String(data.appid) !== appid)
              || (data.chat_id && String(data.chat_id) !== chatId) || (data.chat_type && data.chat_type !== 'user')) return;
            const scope = msgScopeKey('user', chatId, appid);
            const overlay = msgState.realtimeChats.get(scope);
            const nameState = pickMsgNicknameState(chatId, msgState.profiles?.[chatId], overlay, data);
            const profile = {...(nameState || {}), appid, chat_type:'user', avatar:String(data.avatar || '')};
            msgState.avatarRefresh = msgState.avatarRefresh || new Map();
            if (msgState.avatarRefresh.size >= 256) msgState.avatarRefresh.clear();
            const nonce = Date.now();
            [profile.avatar, current?.avatar, avatarUrl(chatId, 'user', data.appid || appid)].filter(Boolean).forEach((url) => msgState.avatarRefresh.set(String(url), nonce));
            msgState.historyCache.delete(msgScopeKey('user', chatId, appid));
            const matches = (chat) => String(chat?.chat_id || '') === chatId && chat?.chat_type === 'user'
              && String(chat.appid || '').trim() === appid;
            const applyProfile = (chat) => ({...chat, ...(nameState || {}),
              ...(nameState ? {nickname:chat.remark || (nameState.nickname_blank ? '\u00a0' : nameState.nickname)} : {}),
              ...(profile.avatar ? {avatar:profile.avatar} : {})});
            msgState.chats = msgState.chats.map((chat) => matches(chat) ? applyProfile(chat) : chat);
            const contact = matches(overlay) ? overlay : msgState.chats.find(matches);
            if (contact) msgState.realtimeChats.set(scope, {...applyProfile(contact),
              ...(nameState ? {_private_nickname:nameState.nickname, _private_nickname_blank:nameState.nickname_blank,
                _private_nickname_ts:nameState.nickname_ts} : {})});
            if (isCurrent()) {
              msgState.profiles = mergeMsgProfileMaps(msgState.profiles, {[chatId]:profile});
              msgState.messageRenderSignature = null;
              updateMsgHead({});
              toast(profile.nickname || profile.nickname_blank ? '私聊资料已刷新' : '已重新查询；当前记录未提供有效昵称');
            }
          }
          await loadMsgChats(true);
          if (chatId && isCurrent()) await loadMsgHistory(false, false, true);
        } catch (error) { toast(error.message || '刷新失败'); }
        finally { button.disabled = false; }
      };

      // 群设置只使用打开时捕获的目标；切群、翻页和迟到响应不能改变写入目标。
      const groupSettingsState = {session:null, generation:0, mutating:false, remarkTarget:null};
      const groupSettingsPage = () => ({rows:[], cursors:[''], index:0, nextCursor:'', selected:new Set(), loading:false, loaded:false, available:true, request:0});
      const captureGroupTarget = () => {
        const chatId = String(msgState.chatId || '').trim();
        if (!chatId || msgState.chatType !== 'group') return null;
        const appid = String(msgState.chatAppid || '').trim();
        if (!appid || appid !== msgState.selectedAppid) return null;
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
        const panel = $('msg-group-settings');
        const previous = groupSettingsState.session?.returnFocus;
        const restoreFocus = !force && !panel.hidden && panel.contains(document.activeElement);
        groupSettingsState.session = null;
        groupSettingsState.generation += 1;
        $('msg-group-settings').hidden = true;
        $('msg-group-settings-open').setAttribute('aria-expanded','false');
        $('msg-head-name').setAttribute('aria-expanded','false');
        clearGroupSettingsProfile();
        clearGroupMuteStates();
        $('msg-group-member-detail').hidden = true;
        ['members','blacklist'].forEach((kind) => { $(`msg-group-${kind}-list`).innerHTML = ''; });
        if (restoreFocus) {
          const target = msgFocusReturnTarget(previous);
          if (target?.isConnected && target.getClientRects().length) target.focus({preventScroll:true});
          else if (!$('page-messages').hidden) $('msg-head-menu-toggle')?.focus({preventScroll:true});
        }
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
        const session = {target, returnFocus:msgFocusReturnTarget(), generation:++groupSettingsState.generation, name:current?.remark || current?.group_name || current?.nickname || target.chat_id, settings:null, profile:{}, profileRevision:0, profileUpdatedAt:0, tab:'basic', detailRequest:0, members:groupSettingsPage(), blacklist:groupSettingsPage()};
        groupSettingsState.session = session;
        $('msg-group-settings').hidden = false;
        $('msg-group-settings-open').setAttribute('aria-expanded','true');
        $('msg-head-name').setAttribute('aria-expanded','true');
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
          msgState.historyCache.delete(msgScopeKey('group', session.target.chat_id, session.target.appid));
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
        $('msg-head-name').addEventListener('click', () => {
          if ($('msg-head-name').disabled) return;
          if ($('msg-group-settings').hidden) void openGroupSettings();
          else closeGroupSettings();
        });
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
          if (activeView !== 'messages' || groupSettingsState.remarkTarget !== target || msgState.chatType !== 'group' || msgState.chatId !== target.chat_id) return;
          $('msg-remark-name').value = data.remark || '';
          $('msg-remark-qq').value = data.group_qq || '';
          setMsgModal('msg-remark-modal', true);
        } catch (error) { if (groupSettingsState.remarkTarget === target) toast(error.message || '群备注读取失败'); }
      };
      const saveRemark = async () => {
        const target = groupSettingsState.remarkTarget;
        if (!target) return;
        const remark = $('msg-remark-name').value.trim();
        const groupQQ = $('msg-remark-qq').value.trim();
        try {
          await api('message/remarks', {method:'POST', body:JSON.stringify({...target, remark, group_qq:groupQQ})});
          msgState.historyCache.delete(msgScopeKey('group', target.chat_id, target.appid));
          if (activeView !== 'messages' || groupSettingsState.remarkTarget !== target || msgState.chatType !== 'group' || msgState.chatId !== target.chat_id) return;
          toast('备注已保存'); setMsgModal('msg-remark-modal', false); void loadMsgChats(true); void loadMsgHistory();
        } catch (error) { if (groupSettingsState.remarkTarget === target) toast(error.message); }
      };
      const deleteRemark = async () => {
        const target = groupSettingsState.remarkTarget;
        if (!target || !confirm('确定删除该群的备注和群号吗？')) return;
        try {
          await api('message/remarks', {method:'POST', body:JSON.stringify({...target, action:'delete'})});
          msgState.historyCache.delete(msgScopeKey('group', target.chat_id, target.appid));
          if (activeView !== 'messages' || groupSettingsState.remarkTarget !== target || msgState.chatType !== 'group' || msgState.chatId !== target.chat_id) return;
          toast('备注已删除'); setMsgModal('msg-remark-modal', false); void loadMsgChats(true); void loadMsgHistory();
        } catch (error) { if (groupSettingsState.remarkTarget === target) toast(error.message); }
      };
      const sendMessage = () => {
        if (!msgState.chatId || !msgState.chatAppid || msgState.chatAppid !== msgState.selectedAppid) return toast('请先选择当前机器人的会话');
        if (msgState.chatRemoved) return toast(msgChatRemovedText({
          ...(msgState.groupMembership.get(msgScopeKey('group', msgState.chatId, msgState.chatAppid)) || {}), chat_type:msgState.chatType,
        }));
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
        syncMsgGroupingToggle();
        msgState.page = 1;
        msgState.chatListTopPending = true;
        $('msg-chats').scrollTop = 0;
        if (msgState.chatListServerLoaded) renderMsgChats({chats:msgState.chats});
        else loadMsgChats(true);
      }));
      $('msg-list-group-toggle')?.addEventListener('click', () => {
        if (msgState.filter !== 'all' || !msgState.selectedAppid) return;
        msgState.grouped = !msgState.grouped;
        syncMsgGroupingToggle();
        msgState.chatRenderSignature = null;
        msgState.chatListWindowStart = -1; msgState.chatListWindowEnd = -1;
        renderMsgChats({appid:msgState.selectedAppid, chats:msgState.chats});
      });
      const msgHeadMenu = $('msg-head-menu-panel');
      const msgHeadMenuToggle = $('msg-head-menu-toggle');
      msgHeadMenuToggle?.addEventListener('click', (event) => {
        if (msgHeadMenu.hidden) openMsgHeadMenu(event.detail === 0 ? 'first' : '');
        else closeMsgHeadMenu(true);
      });
      msgHeadMenuToggle?.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); openMsgHeadMenu(event.key === 'ArrowUp' ? 'last' : 'first'); }
        else if (event.key === 'Escape') { event.preventDefault(); closeMsgHeadMenu(true); }
      });
      msgHeadMenu?.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeMsgHeadMenu(true); return; }
        if (event.key === 'Tab') { closeMsgHeadMenu(true); return; }
        // 下拉框保留浏览器原生的方向键和 Home/End 选择行为。
        if (event.target.tagName === 'SELECT' || !['ArrowDown','ArrowUp','Home','End'].includes(event.key)) return;
        const controls = modalFocusable(msgHeadMenu);
        if (!controls.length) return;
        const index = controls.indexOf(document.activeElement);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? controls.length - 1 : (index + (event.key === 'ArrowUp' ? -1 : 1) + controls.length) % controls.length;
        event.preventDefault(); controls[next].focus({preventScroll:true});
      });
      // 先关闭菜单并将焦点还给触发器，再由原按钮执行原有业务和弹窗。
      msgHeadMenu?.addEventListener('click', (event) => { if (event.target.closest('button:not(:disabled)')) closeMsgHeadMenu(true); }, true);
      document.addEventListener('click', (event) => { if (!event.target.closest('.msg-head-menu')) closeMsgHeadMenu(); });
      document.addEventListener('focusin', (event) => { if (!event.target.closest('.msg-head-menu')) closeMsgHeadMenu(); });
      $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((el) => el.addEventListener('click', () => { $('msg-composer-tabs').querySelectorAll('[data-msg-type]').forEach((x) => x.classList.toggle('active', x === el)); msgState.sendType = el.dataset.msgType; renderMsgExtra(); }));
      $('msg-send-mode').addEventListener('change', (e) => { msgState.sendMode = e.target.value; $('msg-custom-id').hidden = !(msgState.sendMode === 'custom_msg_id' || msgState.sendMode === 'custom_event_id'); });
      $('msg-send').addEventListener('click', sendMessage);
      const handleComposerKeydown = (e) => {
        if (handleComposerMentionKeydown(e)) return;
        if (e.key === 'Enter' && e.ctrlKey && !e.metaKey && !e.altKey && !e.isComposing && !composerMentionPicker.composing && e.keyCode !== 229) {
          e.preventDefault();
          document.execCommand('insertLineBreak');
          syncComposerImageState(); saveComposerSelection(); scheduleComposerMentionPicker();
          return;
        }
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
        syncMsgNewMessagesDisplay();
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
        syncMsgNewMessagesDisplay();
        maybeLoadOlderMessages();
        if (msgState.historyWindow || msgQuoteJump.pending) return;
        if (!msgBodyNearBottom($('msg-body'))) return;
        const activeChat = msgState.chats.find((chat) => String(chat.chat_id || '') === String(msgState.chatId || '') && chat.chat_type === msgState.chatType && msgInSelectedBot(chat));
        const shouldRead = msgState.pendingNewMessages > 0 || Number(activeChat?.unread || 0) > 0;
        clearMsgNewMessages();
        if (shouldRead) markMsgRead(undefined, true, msgState.chatType, msgState.chatAppid);
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
      $('msg-raw-close').addEventListener('click', () => { setMsgModal('msg-raw-modal', false); });
      $('msg-raw-modal').addEventListener('click', (e) => { if (e.target === $('msg-raw-modal')) setMsgModal('msg-raw-modal', false); });
      $('msg-mute-presets').querySelectorAll('[data-mute-min]').forEach((el) => el.addEventListener('click', () => { $('msg-mute-presets').querySelectorAll('[data-mute-min]').forEach((x) => x.classList.toggle('active', x === el)); msgState.muteMinutes = Number(el.dataset.muteMin); $('msg-mute-custom').value = ''; }));
      $('msg-mute-custom').addEventListener('input', (e) => { const raw = Number(e.target.value); if (!Number.isFinite(raw) || raw < 1) return; const days = Math.min(30, Math.floor(raw)); e.target.value = String(days); msgState.muteMinutes = days * 1440; });
      $('msg-mute-cancel').addEventListener('click', () => { setMsgModal('msg-mute-modal', false); });
      $('msg-clear-open').addEventListener('click', openMsgClear);
      $('msg-clear-scope').addEventListener('change', () => { void previewMsgClear(); });
      $('msg-clear-preview-button').addEventListener('click', () => { void previewMsgClear(); });
      $('msg-clear-confirm').addEventListener('click', () => { void confirmMsgClear(); });
      for (const id of ['msg-clear-close','msg-clear-cancel']) $(id).addEventListener('click', () => setMsgModal('msg-clear-modal', false));
      $('msg-clear-modal').addEventListener('click', (event) => { if (event.target === $('msg-clear-modal')) setMsgModal('msg-clear-modal', false); });
      $('msg-remark-cancel').addEventListener('click', () => { setMsgModal('msg-remark-modal', false); });
      $('msg-remark-save').addEventListener('click', saveRemark);
      $('msg-remark-delete').addEventListener('click', deleteRemark);
      $('msg-mute-confirm').addEventListener('click', async () => { if (!msgState.mute.member) return; const custom = $('msg-mute-custom'); const rawDays = Number(custom?.value); if (Number.isFinite(rawDays) && rawDays >= 1) { const days = Math.min(30, Math.floor(rawDays)); if (custom) custom.value = String(days); msgState.muteMinutes = days * 1440; } try { await api('message/group-member/mute', {method:'POST', body:JSON.stringify({chat_id:msgState.chatId, member_openid:msgState.mute.member, minutes:Math.min(43200, Math.max(1, Number(msgState.muteMinutes) || 30))})}); toast('禁言成功'); setMsgModal('msg-mute-modal', false); void loadMuteStates(true); } catch (error) { toast(error.message); } });
      bindMsgLayoutControls();
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
      document.addEventListener('visibilitychange', () => { syncMsgNewMessagesDisplay(); if (document.visibilityState === 'visible') { msgLastPollAt = 0; pollLocalMessages(); void loadGroupRoles(true).then(() => loadMuteStates()); void refreshQuarkProfilesSilently(); } else { closeMsgHeadMenu(); closeAdminPopover(); closeComposerMentionPicker(); cancelMsgQuoteJump(); stopMsgGroupSnapshots(); } });
      window.addEventListener('pagehide', () => { closeMsgHeadMenu(); closeAdminPopover(); closeComposerMentionPicker(); cancelMsgQuoteJump(); stopMsgGroupSnapshots(); setMsgModal('msg-clear-modal', false, false); });
      setInterval(() => {
        void refreshQuarkProfilesSilently();
        if (document.visibilityState === 'visible') { void loadBotProfile(); }
      }, 60000);
      setInterval(() => { if (document.visibilityState === 'visible') void loadZLibraryAccount(); }, 300000);
      msgState.timer = setInterval(pollLocalMessages, 5000);
      msgState.muteTimer = setInterval(() => {
        updateMuteCountdowns();
        if (document.visibilityState === 'hidden' || $('page-messages')?.hidden) return;
        if (msgState.chatType === 'group' && msgState.chatId) void loadMuteStates();
      }, 1000);

      $('studio-bot-exit').addEventListener('click', () => exitBotConsole());
      $('bot-picker-refresh').addEventListener('click', async () => {
        if (consoleEntering) return;
        const button = $('bot-picker-refresh'); button.disabled = true; botProfileLoadedAt = 0;
        showBotPicker();
        try { await loadBotProfile(); } finally { button.disabled = false; }
      });
      showBotPicker();
      void loadBotProfile().then(() => {
        const profile = botProfileForAppid(initialParams.get('appid'));
        if (profile.appid) void enterBotConsole(profile, false);
      });
    })();
  """
