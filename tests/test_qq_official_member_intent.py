import types
import unittest


from 功能文件.管理功能.基础功能 import QQ官方交互桥


class QQ官方新人事件意图测试(unittest.TestCase):
    def test_群成员加入使用官方规定的_group_member_event意图位(self):
        意图 = types.SimpleNamespace(value=0)
        客户端 = types.SimpleNamespace(intents=0)

        成功, 原值, 新值 = QQ官方交互桥._启用群成员加入意图(意图, 客户端)

        self.assertTrue(成功)
        self.assertEqual(原值, 0)
        self.assertEqual(新值, 1 << 24)
        self.assertEqual(意图.value, 1 << 24)
        self.assertEqual(客户端.intents, 1 << 24)


if __name__ == "__main__":
    unittest.main()
