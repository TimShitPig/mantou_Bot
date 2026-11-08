"""系统设置的数据库连接表单布局。"""

系统脚本 = r"""
    const 整理数据库连接表单 = (editor) => {
      const group = editor.querySelector('[data-config-category="database_settings"]');
      const fields = group?.querySelector('.config-fields');
      if (!fields) return;
      // 挪动现有输入节点，继续使用控制台的测试、保存和校验逻辑。
      const input = (name) => fields.querySelector(`[data-config-field="${name}"]`);
      const field = (name) => input(name)?.closest('.config-field');
      const add = (container, tag, text = '', className = '') => {
        const element = document.createElement(tag);
        if (text) element.textContent = text;
        if (className) element.className = className;
        container.append(element);
        return element;
      };
      const caption = group.querySelector('h3');
      if (caption) caption.textContent = '地址与账号';

      const username = input('database_user');
      const name = input('database_name');
      if (username && name) {
        const usernameField = username.closest('.config-field');
        const nameField = name.closest('.config-field');
        const nameHint = nameField.querySelector('small');
        if (nameHint) nameHint.textContent = '留空与用户名相同；单独填写时，请按实际库名和大小写输入。';
        const passwordField = field('database_password');
        const account = add(fields, 'fieldset', '', 'studio-db-account');
        add(account, 'legend', '数据库账号');
        const credentials = add(account, 'div', '', 'config-fields');
        credentials.append(usernameField);
        if (passwordField) credentials.append(passwordField);

        const custom = add(account, 'details', '', 'studio-db-details studio-db-name');
        const title = add(custom, 'summary');
        add(title, 'span', '数据库名');
        const mode = add(title, 'small');
        custom.append(nameField);

        const updateNameMode = () => {
          const explicit = name.value.trim();
          mode.textContent = explicit ? '单独指定' : '与用户名相同';
        };
        const differsFromUser = () => Boolean(name.value.trim() && name.value.trim() !== username.value.trim());
        let differed = differsFromUser();
        custom.open = differed;
        updateNameMode();
        username.addEventListener('input', () => {
          const differs = differsFromUser();
          if (differs && !differed) custom.open = true;
          differed = differs;
        });
        name.addEventListener('input', () => {
          differed = differsFromUser();
          updateNameMode();
        });
      }

      const advancedFields = [
        ['database_ssl_mode', '保护与 MySQL 之间传输的数据。自动协商适用于常见部署；验证证书时，数据库地址须与证书匹配。'],
        ['database_ssl_ca', '仅在“验证证书与主机名”时使用。填写 AstrBot 服务器可读取的 CA 文件路径，留空使用系统证书。'],
        ['database_connect_timeout', '建立连接最多等待多久，范围为 1～60 秒。一般保留默认的 10 秒。'],
      ].map(([key, hint]) => {
        const element = field(key);
        const note = element?.querySelector('small');
        if (note) note.textContent = hint;
        return element;
      }).filter(Boolean);
      if (advancedFields.length) {
        const advanced = add(fields, 'details', '', 'studio-db-details studio-db-advanced');
        const title = add(advanced, 'summary');
        add(title, 'span', '高级连接设置');
        add(title, 'small', 'TLS、CA 证书与超时');
        add(advanced, 'div', '', 'config-fields').append(...advancedFields);
      }
    };
"""
