"""帮助网页登录页交互脚本。"""

登录页脚本 = r"""
    (() => {
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
