"""业务工作台的页面内导航。"""

业务脚本 = """
    (() => {
      const tabList = document.querySelector('#page-bot .studio-bot-tabs');
      const tabs = Array.from(tabList.querySelectorAll('[role="tab"]'));
      const panels = tabs.map((tab) => document.getElementById(tab.getAttribute('aria-controls')));

      const selectTab = (selectedIndex) => {
        // 保留表单节点和账号管理状态；这里只切换可见的分区。
        tabs.forEach((tab, index) => {
          const selected = index === selectedIndex;
          tab.setAttribute('aria-selected', String(selected));
          tab.tabIndex = selected ? 0 : -1;
          panels[index].hidden = !selected;
        });
      };

      tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => selectTab(index));
        tab.addEventListener('keydown', (event) => {
          let next;
          switch (event.key) {
            case 'ArrowLeft': next = (index - 1 + tabs.length) % tabs.length; break;
            case 'ArrowRight': next = (index + 1) % tabs.length; break;
            case 'Home': next = 0; break;
            case 'End': next = tabs.length - 1; break;
            default: return;
          }
          event.preventDefault();
          selectTab(next);
          tabs[next].focus();
        });
      });
    })();
"""
