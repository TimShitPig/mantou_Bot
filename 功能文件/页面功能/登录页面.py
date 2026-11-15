"""登录页模板，独立拼接登录页样式与脚本。"""

from .登录页面样式 import 登录页面样式
from .登录页面脚本 import 登录页面脚本
from .新版外观样式 import 新版外观样式

页面头部前缀 = """<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f4efe4">
  <title>登录 · 馒头工作台</title>
  <script>
    (() => {
      try {
        const preference = localStorage.getItem('mantou-theme') === 'dark' ? 'dark' : 'light';
        const dark = preference === 'dark';
        document.documentElement.dataset.themePreference = preference;
        document.documentElement.dataset.theme = dark ? 'dark' : 'light';
        if (preference === 'dark') document.querySelector('meta[name="theme-color"]').content = '#141310';
      } catch (_) {}
    })();
  </script>
  <style>"""

页面头部后缀 = """</style>
</head>
"""

页面主体 = """<body class="login-page">
  <div class="login-shell">
    <header class="login-topbar">
      <div class="login-brand">
        <div class="login-brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M9 10c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7m7 7c-3-3 3-4 0-7"/><path d="M5 24a11 11 0 0 1 22 0c0 4-22 4-22 0Z"/></svg></div>
        <div class="login-brand-copy"><strong>馒头工作台</strong><span>MANTOU BOT</span></div>
      </div>
      <label class="login-theme-control">
        <span class="login-theme-icon" aria-hidden="true">☾</span>
        <span class="login-theme-label" id="login-theme-label">浅色模式</span>
        <button class="login-theme-select" id="login-theme-select" type="button" aria-label="切换主题" aria-haspopup="listbox" aria-expanded="false"><span aria-hidden="true">⌄</span></button>
        <div class="login-theme-menu" id="login-theme-menu" hidden role="listbox">
          <button type="button" role="option" data-theme-option="light" aria-selected="true">浅色模式</button>
          <button type="button" role="option" data-theme-option="dark" aria-selected="false">深色模式</button>
        </div>
      </label>
    </header>
    <main class="login-stage">
      <div class="login-art login-art-book" aria-hidden="true"><svg viewBox="0 0 320 300" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M50 230c-6-28 16-52 44-56 18-2 32 6 40 18" stroke="currentColor" opacity=".35"/><ellipse cx="160" cy="248" rx="112" ry="14" fill="var(--art-shadow)" stroke="none"/><path d="M62 222c26-8 52-4 72 12v42c-20-16-46-20-72-12Z" fill="var(--art-lavender)" stroke="none"/><path d="M140 234c20-16 46-20 74-12v42c-26-8-54-4-74 12Z" fill="var(--art-peach)" stroke="none"/><path d="M140 124c20-16 44-20 70-12v108c-26-8-50-4-70 12Z" fill="var(--art-paper)" stroke="var(--art-line)" stroke-width="1.6"/><path d="M62 112c26-8 50-4 78 12v108c-28-16-52-20-78-12Z" fill="var(--art-paper)" stroke="var(--art-line)" stroke-width="1.6"/><path d="M140 124c20-16 44-20 70-12" stroke="var(--art-line)" stroke-width="1.6"/><path d="M84 142c16-2 32 4 46 14m-46 22c16-2 32 4 46 14m-46 22c16-2 32 4 46 14" stroke="var(--art-line)" stroke-width="1.2" opacity=".7"/><path d="M164 142c14-6 28-8 40-6m-40 22c14-6 28-8 40-6m-40 22c14-6 28-8 40-6" stroke="var(--art-line)" stroke-width="1.2" opacity=".7"/><path d="M236 96c16 6 26 22 24 40" stroke="var(--art-line)" stroke-width="1.4"/><path d="M228 108c22-46 34-58 46-62-4 16-16 38-38 66Z" fill="var(--art-blush)" stroke="var(--art-line)" stroke-width="1.3"/><path d="M60 92l3 9 9 3-9 3-3 9-3-9-9-3 9-3Z" fill="var(--art-peach)" stroke="none"/><path d="M246 56l2 7 7 2-7 2-2 7-2-7-7-2 7-2Z" fill="var(--art-lavender)" stroke="none"/></svg></div>
      <form class="login-panel" id="login-form" method="post" action="/login" autocomplete="off">
        <div class="login-panel-dots" aria-hidden="true"><i></i><i></i><i></i></div>
        <span class="login-kicker">管理员入口</span>
        <h1>欢迎回来</h1>
        <p class="login-lede">登录馒头工作台，管理你的 QQ 机器人。</p>
        <label class="login-field">
          <span>管理员账号</span>
          <div class="login-field-control">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-7 8-7s8 3 8 7"/></svg>
            <input id="login-username" name="username" type="text" placeholder="输入管理员账号" autocomplete="username" required>
          </div>
        </label>
        <label class="login-field">
          <span>密码</span>
          <div class="login-field-control">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>
            <input id="login-password" name="password" type="password" placeholder="输入密码" autocomplete="current-password" required>
            <button class="login-field-action" id="login-password-toggle" type="button" aria-label="显示密码" aria-pressed="false"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg></button>
          </div>
        </label>
        <div class="login-error" id="login-error" role="alert" hidden></div>
        <button class="login-button" id="login-submit" type="submit"><span>登录工作台</span><span class="login-button-arrow" aria-hidden="true">→</span></button>
        <div class="login-note"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg><span>登录状态在本设备保留 30 天，更换设备需重新登录。</span></div>
      </form>
      <div class="login-art login-art-cat" aria-hidden="true"><svg viewBox="0 0 320 280" fill="none" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="160" cy="238" rx="86" ry="12" fill="var(--art-shadow)" stroke="none"/><path d="M96 232c-6-34 14-62 46-66 6-26 12-38 18-44 10 10 18 22 24 44 30 6 48 32 42 66Z" fill="var(--art-paper)" stroke="var(--art-line)" stroke-width="1.6"/><path d="M108 150l-8-34 30 14m72 20 8-34-30 14" fill="var(--art-peach)" stroke="var(--art-line)" stroke-width="1.4"/><path d="M138 196c4-5 12-5 16 0m28 0c4-5 12-5 16 0" stroke="var(--art-line)" stroke-width="1.6"/><path d="M156 210c4 4 10 4 14 0" stroke="var(--art-line)" stroke-width="1.4"/><path d="M120 214c-4 4-10 6-16 4m92-4c4 4 10 6 16 4" stroke="var(--art-line)" stroke-width="1.2" opacity=".7"/><ellipse cx="160" cy="244" rx="52" ry="14" fill="var(--art-lavender)" stroke="none"/><path d="M222 96c14-2 22 8 18 22-4 12-16 16-24 10" fill="var(--art-peach)" stroke="var(--art-line)" stroke-width="1.3"/><path d="M84 72l2 7 7 2-7 2-2 7-2-7-7-2 7-2Z" fill="var(--art-blush)" stroke="none"/></svg></div>
    </main>
  </div>
  <script>"""

页面后缀 = """</script>
</body>
</html>
"""

登录页样式串 = """
""" + 登录页面样式 + "\n" + 新版外观样式


def 渲染登录页面():
    return 页面头部前缀 + 登录页样式串 + 页面头部后缀 + 页面主体 + 登录页面脚本 + 页面后缀
