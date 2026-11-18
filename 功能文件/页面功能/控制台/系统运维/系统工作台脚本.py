"""系统设置的数据库连接表单布局。"""

系统脚本 = r"""
    const 整理数据库连接表单 = (editor) => {
      const group = editor.querySelector('[data-config-category="database_settings"]');
      const fields = group?.querySelector('.config-fields');
      if (!fields) return;
      // 只调整现有字段的位置与文案，保留输入节点及提交逻辑。
      const field = (key, title, hint = '') => {
        const input = fields.querySelector(`[data-config-field="${key}"]`);
        const element = input?.closest('.config-field');
        if (!element) return null;
        const label = element.querySelector('label');
        if (label) label.textContent = title;
        const note = element.querySelector('small');
        if (note) {
          if (hint) {
            note.id = `${input.id}-hint`;
            note.textContent = hint;
            input.setAttribute('aria-describedby', note.id);
          } else {
            note.remove();
          }
        }
        return element;
      };
      const add = (container, tag, text = '', className = '') => {
        const element = document.createElement(tag);
        if (text) element.textContent = text;
        if (className) element.className = className;
        container.append(element);
        return element;
      };
      group.querySelector(':scope > h3')?.remove();
      const hasSavedPassword = Boolean(fields.querySelector('#saved-cfg-database_password'));
      const connectionFields = [
        ['database_host', '地址'],
        ['database_port', '端口', '留空时使用地址中的端口或 3306。'],
        ['database_user', '用户名'],
        ['database_password', '密码', hasSavedPassword ? '留空保留已保存的密码。' : ''],
        ['database_name', '数据库名', '留空使用用户名；手动填写时请核对大小写。'],
      ].map((args) => field(...args)).filter(Boolean);
      const name = fields.querySelector('#cfg-database_name');
      name?.closest('.config-field')?.classList.add('full');
      if (name) name.placeholder = '与用户名相同（留空）';
      const password = fields.querySelector('#cfg-database_password');
      if (password && hasSavedPassword) password.placeholder = '输入新密码可替换';
      fields.prepend(...connectionFields);

      const advancedFields = [
        ['database_ssl_mode', '加密方式（TLS）', '验证证书时，地址须与证书匹配。'],
        ['database_connect_timeout', '连接超时（秒）', '建立连接的最长等待时间：1～60 秒。'],
        ['database_ssl_ca', 'CA 证书路径', '验证证书时填写服务器可读取的路径；留空使用系统证书。'],
      ].map((args) => field(...args)).filter(Boolean);
      if (advancedFields.length) {
        fields.querySelector('#cfg-database_ssl_ca')?.closest('.config-field')?.classList.add('full');
        const advanced = add(fields, 'details', '', 'studio-db-advanced');
        const title = add(advanced, 'summary');
        add(title, 'span', '高级连接设置');
        add(title, 'small', 'TLS、CA 证书与超时');
        add(advanced, 'div', '', 'config-fields').append(...advancedFields);
      }
    };
"""
