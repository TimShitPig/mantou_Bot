"""帮助网页的独立登录页模板。"""

from .登录页面样式 import 登录页样式
from .登录页面脚本 import 登录页脚本

登录页前缀 = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f7f8fd">
  <title>馒头助手</title>
  <style>"""
登录页样式后缀 = """</style>
</head>
<body class="login-page">
  <main class="login-shell">
    <section class="login-welcome" aria-labelledby="login-title">
      <div class="login-brand"><span class="login-brand-mark">馒</span><div><strong>馒头助手</strong><small>QQ 机器人</small></div></div>
      <div class="login-illustration" aria-hidden="true"><span class="login-star one">✦</span><div class="login-avatar"><span class="login-avatar-face">•ᴗ•</span></div><span class="login-star two">✦</span></div>
      <h1 id="login-title">欢迎回来</h1>
      <p>验证管理身份后继续使用馒头助手。</p>
    </section>
    <section class="login-panel" aria-labelledby="login-heading">
      <h2 id="login-heading">身份验证</h2>
      <p>请输入登录信息。</p>
      <form id="login-form" class="login-form">
        <label for="login-username">账号<input id="login-username" name="username" autocomplete="username" required></label>
        <label for="login-password">密码<input id="login-password" name="password" type="password" autocomplete="current-password" required></label>
        <button class="login-button" type="submit"><span>进入</span><span aria-hidden="true">→</span></button>
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


def 渲染登录页面() -> str:
    return (
        登录页前缀
        + 登录页样式
        + 登录页样式后缀
        + 登录页脚本前缀
        + 登录页脚本
        + 登录页脚本后缀
    )
