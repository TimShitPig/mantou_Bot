"""帮助网页登录页交互脚本。"""

登录页脚本 = r"""
    (() => {
      const themeKey = 'mantou-theme';
      const themeMedia = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
      const readTheme = () => { try { const value = localStorage.getItem(themeKey); return ['light','dark','system'].includes(value) ? value : 'system'; } catch (_) { return 'system'; } };
      const applyTheme = (preference = readTheme(), persist = true) => {
        const next = ['light','dark','system'].includes(preference) ? preference : 'system';
        const dark = next === 'dark' || (next === 'system' && Boolean(themeMedia?.matches));
        document.documentElement.dataset.themePreference = next;
        document.documentElement.dataset.theme = dark ? 'dark' : 'light';
        const meta = document.querySelector('meta[name="theme-color"]'); if (meta) meta.setAttribute('content', dark ? '#171a24' : '#f7f8fd');
        if (persist) { try { localStorage.setItem(themeKey, next); } catch (_) {} }
        const select = document.getElementById('login-theme-select'); if (select && select.value !== next) select.value = next;
      };
      applyTheme(readTheme(), false);
      document.getElementById('login-theme-select')?.addEventListener('change', (event) => applyTheme(event.target.value));
      const syncSystemTheme = () => { if (document.documentElement.dataset.themePreference === 'system') applyTheme('system', false); };
      if (themeMedia) { if (themeMedia.addEventListener) themeMedia.addEventListener('change', syncSystemTheme); else themeMedia.addListener(syncSystemTheme); }
      const form = document.getElementById('login-form');
      const username = document.getElementById('login-username');
      const password = document.getElementById('login-password');
      const button = form.querySelector('button[type="submit"]');
      const message = document.getElementById('login-message');
      const setMessage = (value) => { message.textContent = value; };
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
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
