"""帮助网页的独立登录页模板。"""

from .登录页面样式 import 登录页样式
from .登录页面脚本 import 登录页脚本

登录页前缀 = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f4f1fc">
  <title>管理员登录 · 馒头工作台</title>
  <script>
    (() => {
      try {
        const preference = localStorage.getItem('mantou-theme') === 'dark' ? 'dark' : 'light';
        document.documentElement.dataset.themePreference = preference;
        document.documentElement.dataset.theme = preference;
        if (preference === 'dark') document.querySelector('meta[name="theme-color"]').content = '#201a2d';
      } catch (_) { document.documentElement.dataset.theme = 'light'; }
    })();
  </script>
  <style>"""
登录页样式后缀 = """</style>
</head>
<body class="login-page">
  <header class="login-topbar">
    <div class="login-brand">
      <span class="login-brand-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M5 12a7 7 0 0 1 14 0v2a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2Z"/><path d="M4 19h16M10 8.5a3 3 0 0 1 2.5-1"/></svg>
      </span>
      <div><strong>馒头工作台</strong><small>MANTOU BOT</small></div>
    </div>
    <label class="login-theme-control" for="login-theme-select">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 15a8.5 8.5 0 0 1-11-11 8.5 8.5 0 1 0 11 11Z"/><path d="M17 3v4m-2-2h4"/></svg>
      <select id="login-theme-select" aria-label="主题模式"><option value="light">浅色模式</option><option value="dark">深色模式</option></select>
    </label>
  </header>
  <main class="login-stage">
    <svg class="login-art login-book" viewBox="0 0 290 232" aria-hidden="true">
      <ellipse class="art-shadow" cx="140" cy="205" rx="119" ry="14"/>
      <path class="art-lavender" d="M13 151q59-34 116-5 64-34 134-17l19 61q-86 1-145 29-59-13-112-8Z"/>
      <path class="art-peach" d="M15 139q62-31 115 1 64-35 126-16l17 60q-76 0-138 29-53-22-111-14Z"/>
      <path class="art-paper" d="M11 119q61-32 116 16 64-51 126-39l13 84q-71-10-132 31-50-42-113-26Z"/>
      <path class="art-ink" d="m127 135 7 76M29 137q41-13 82 13m-80-1q42-12 82 14m-79-2q41-10 80 15m-78-2q41-9 78 14m29-38q42-31 90-29m-89 41q42-29 91-28m-91 40q42-26 93-27m-92 38q43-26 94-25"/>
      <path class="art-ribbon" d="m189 109 7 50 8-11 11 4-9-49"/>
      <path class="art-paper" d="M196 137q-4-44 24-82 21-27 56-35-6 43-26 64l-19 7 11 2q-19 29-46 44Z"/>
      <path class="art-ink" d="M182 164q32-72 78-126m-55 83 3-24m6 10 28-12m-22 2 1-23m6 12 28-17m-19 5 2-22"/>
      <path class="art-peach" d="m190 141 7 3-14 20-2-6Z"/>
      <path class="art-spark" d="M49 49q3 14 16 16-13 2-16 16-3-14-16-16 13-2 16-16Zm116-30q2 10 12 12-10 2-12 12-2-10-12-12 10-2 12-12Z"/>
      <circle class="art-dot" cx="92" cy="58" r="3"/>
    </svg>
    <section class="login-panel" aria-labelledby="login-heading">
      <div class="login-panel-lights" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="login-intro">
        <span class="login-kicker">管理员入口</span>
        <h1 id="login-heading">欢迎回来</h1>
        <p>登录馒头工作台，管理你的 QQ 机器人。</p>
      </div>
      <form id="login-form" class="login-form" method="post" action="/api/login">
        <div class="login-field">
          <label for="login-username">管理员账号</label>
          <div class="login-field-control">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3"/><path d="M5 19v-1a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v1"/></svg>
            <input id="login-username" name="username" autocomplete="username" placeholder="输入管理员账号" required>
          </div>
        </div>
        <div class="login-field">
          <label for="login-password">密码</label>
          <div class="login-field-control login-password-wrap">
            <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 4v2"/></svg>
            <input id="login-password" name="password" type="password" autocomplete="current-password" placeholder="输入密码" required>
            <button id="login-password-toggle" class="login-password-toggle" type="button" aria-label="显示密码" aria-pressed="false">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
            </button>
          </div>
        </div>
        <button class="login-button" type="submit">
          <span>登录工作台</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5"/></svg>
        </button>
      </form>
      <p id="login-message" class="login-message" role="alert" aria-live="polite"></p>
      <div class="login-note">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 5 6v5c0 5 3 8 7 10 4-2 7-5 7-10V6Z"/><path d="m9 12 2 2 4-4"/></svg>
        <span>登录状态在本设备保留 30 天，更换设备需重新登录。</span>
      </div>
    </section>
    <svg class="login-art login-cat" viewBox="0 0 213 223" aria-hidden="true">
      <ellipse class="art-shadow" cx="107" cy="199" rx="86" ry="12"/>
      <path class="art-lavender" d="M25 169q-4-29 56-29h59q42 1 46 25 6 26-45 29H80q-53 0-55-25Z"/>
      <path class="art-paper" d="M53 146q-7-8-7-24 0-20 13-31-4-32 5-38 6-4 30 20 15-6 34-4 24-24 31-21 11 5 5 39 16 14 16 35 0 38-45 40H94q-29 0-41-16Z"/>
      <path class="art-blush" d="m65 63 15 14-13 8Zm91-5-13 15 14 8Z"/>
      <path class="art-ink" d="M82 117q4-6 9 0m36 0q5-6 10 0m-33 10q6 7 11 0m-7-3h4m-49-3-10-2m12 10-9 2m92-9 11-3m-11 11 9 2"/>
      <ellipse class="art-blush" cx="78" cy="128" rx="8" ry="4"/>
      <ellipse class="art-blush" cx="140" cy="128" rx="8" ry="4"/>
      <path class="art-paper" d="M70 149q-7 16 7 19 14 2 15-13m43 0q2 15 14 13 14-3 7-17"/>
      <path class="art-peach" d="M22 28q0-10 12-10h24q12 0 12 10v9q0 10-12 10H47l-9 8v-8h-4q-12 0-12-10Z"/>
      <path class="art-ink" d="M36 33h1m9 0h1m9 0h1"/>
      <path class="art-spark" d="M180 17q2 10 13 13-11 2-13 13-3-11-13-13 10-3 13-13ZM19 108q2 8 10 10-8 2-10 10-2-8-10-10 8-2 10-10Z"/>
      <circle class="art-dot" cx="199" cy="97" r="3"/>
    </svg>
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
