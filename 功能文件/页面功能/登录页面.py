"""帮助网页的独立登录页模板。"""

from .登录页面样式 import 登录页样式
from .登录页面脚本 import 登录页脚本

登录页前缀 = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#081423">
  <title>登录 · 馒头控制台</title>
  <script>
    (() => {
      try {
        const preference = localStorage.getItem('mantou-theme') === 'light' ? 'light' : 'dark';
        const dark = preference === 'dark';
        document.documentElement.dataset.themePreference = preference;
        document.documentElement.dataset.theme = dark ? 'dark' : 'light';
      } catch (_) { document.documentElement.dataset.theme = 'dark'; }
    })();
  </script>
  <style>"""
登录页样式后缀 = """</style>
</head>
<body class="login-page">
  <main class="login-shell">
    <section class="login-welcome" aria-labelledby="login-title">
      <div class="login-brand"><span class="login-brand-mark">馒</span><div><strong>馒头助手</strong><small>QQ 机器人</small></div></div>
      <div class="login-constellation" aria-hidden="true">
        <svg class="login-routes" viewBox="0 0 380 270" fill="none"><path class="route-guide" d="M190 20v230M35 135h310"/><ellipse class="route-orbit" cx="190" cy="135" rx="147" ry="91"/><ellipse class="route-inner" cx="190" cy="135" rx="103" ry="64"/><path class="route-link" d="M77 75l113 60 117-63M190 135v89"/><circle class="route-point" cx="190" cy="44" r="3"/><circle class="route-point warm" cx="323" cy="175" r="3"/><circle class="route-point" cx="55" cy="173" r="3"/></svg>
        <div class="login-core"><span>馒</span></div>
        <div class="login-node node-messages"><svg viewBox="0 0 24 24"><path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-6 3V6a2 2 0 0 1 2-2Z"/><path d="M8 9h8M8 13h5"/></svg><span>消息</span></div>
        <div class="login-node node-books"><svg viewBox="0 0 24 24"><path d="M12 5C9 3 6 3 3 4v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1ZM12 5v15"/></svg><span>小说</span></div>
        <div class="login-node node-cloud"><svg viewBox="0 0 24 24"><path d="M7 18a5 5 0 1 1 0-10 6 6 0 0 1 11-1 5.5 5.5 0 0 1 0 11H7Z"/><path d="m9 13 3-3 3 3M12 10v7"/></svg><span>网盘</span></div>
      </div>
      <h1 id="login-title">馒头Bot<br>管理控制台</h1>
      <p>机器人、小说与聊天记录，一处管理。</p>
    </section>
    <section class="login-panel" aria-labelledby="login-heading">
      <label class="login-theme-control" for="login-theme-select"><span aria-hidden="true">◐</span><select id="login-theme-select" aria-label="主题模式"><option value="light">浅色模式</option><option value="dark">深色模式</option></select></label>
      <h2 id="login-heading">欢迎回来</h2>
      <p>登录后继续管理你的机器人。</p>
      <form id="login-form" class="login-form">
        <label for="login-username">账号<input id="login-username" name="username" autocomplete="username" placeholder="管理员账号" required></label>
        <div class="login-password-field"><label for="login-password">密码</label><div class="login-password-wrap"><input id="login-password" name="password" type="password" autocomplete="current-password" placeholder="输入密码" required><button id="login-password-toggle" class="login-password-toggle" type="button" aria-label="显示密码" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg></button></div></div>
        <button class="login-button" type="submit"><span>登录控制台</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h5v16h-5M4 12h11m-4-4 4 4-4 4"/></svg></button>
      </form>
      <p id="login-message" class="login-message" role="alert" aria-live="polite"></p>
      <div class="login-note">登录状态在本设备保留 30 天，更换设备需重新登录</div>
    </section>
  </main>"""
登录页脚本前缀 = """
  <script>"""
登录页脚本后缀 = """</script>
</body>
</html>
"""
_登录页面缓存: str | None = None


def 渲染登录页面() -> str:
    global _登录页面缓存
    if _登录页面缓存 is None:
        _登录页面缓存 = (
            登录页前缀
            + 登录页样式
            + 登录页样式后缀
            + 登录页脚本前缀
            + 登录页脚本
            + 登录页脚本后缀
        )
    return _登录页面缓存
