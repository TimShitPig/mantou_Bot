"""帮助网页登录页交互脚本。"""

登录页脚本 = r"""
    (() => {
      const themeStorageKey = 'mantou-theme';
      const readThemePreference = () => { try { return localStorage.getItem(themeStorageKey) === 'light' ? 'light' : 'dark'; } catch (_) { return 'dark'; } };
      const updateThemeControl = (next) => {
        const select = document.getElementById('login-theme-select');
        if (select && select.value !== next) select.value = next;
      };
      const commitTheme = (next) => {
        const root = document.documentElement;
        if (root.dataset.theme !== next) root.dataset.theme = next;
        const meta = document.querySelector('meta[name="theme-color"]');
        const color = next === 'dark' ? '#081423' : '#edf4fa';
        if (meta && meta.getAttribute('content') !== color) meta.setAttribute('content', color);
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
      document.getElementById('login-theme-select')?.addEventListener('change', (event) => applyTheme(event.target.value));
      const form = document.getElementById('login-form');
      const username = document.getElementById('login-username');
      const password = document.getElementById('login-password');
      const passwordToggle = document.getElementById('login-password-toggle');
      passwordToggle?.addEventListener('click', () => {
        const visible = password.type === 'password';
        password.type = visible ? 'text' : 'password';
        passwordToggle.setAttribute('aria-pressed', String(visible));
        passwordToggle.setAttribute('aria-label', visible ? '隐藏密码' : '显示密码');
      });
      const button = form.querySelector('button[type="submit"]');
      const message = document.getElementById('login-message');
      const setMessage = (value) => { message.textContent = value; };
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (button.disabled) return;
        button.disabled = true;
        setMessage('');
        try {
          const response = await fetch('/api/login', { method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:username.value.trim(), password:password.value}) });
          const data = await response.json().catch(() => ({ok:false}));
          if (!response.ok || !data.ok) { const error = new Error(); error.status = response.status; throw error; }
          password.value = '';
          location.replace(location.pathname + '?view=dashboard');
        } catch (error) {
          setMessage(error.status === 401 ? '账号或密码不正确。' : error.status === 503 ? '登录服务暂未启用，请联系管理员。' : '暂时无法登录，请稍后再试。');
        } finally {
          button.disabled = false;
        }
      });
      username.focus();
    })();
  """
