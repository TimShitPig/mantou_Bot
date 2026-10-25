"""帮助网页登录页交互脚本。"""

登录页脚本 = r"""
    (() => {
      const themeKey = 'mantou-theme';
      const readTheme = () => { try { return localStorage.getItem(themeKey) === 'light' ? 'light' : 'dark'; } catch (_) { return 'dark'; } };
      const applyTheme = (preference = readTheme(), persist = true) => {
        const next = preference === 'dark' ? 'dark' : 'light';
        const dark = next === 'dark';
        document.documentElement.dataset.themePreference = next;
        document.documentElement.dataset.theme = dark ? 'dark' : 'light';
        const meta = document.querySelector('meta[name="theme-color"]'); if (meta) meta.setAttribute('content', dark ? '#081423' : '#edf4fa');
        if (persist) { try { localStorage.setItem(themeKey, next); } catch (_) {} }
        const select = document.getElementById('login-theme-select'); if (select && select.value !== next) select.value = next;

      };
      applyTheme(readTheme(), false);
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
