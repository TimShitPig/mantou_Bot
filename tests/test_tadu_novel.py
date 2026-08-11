import gzip
import unittest


from 功能文件.管理功能.小说功能.小说 import 塔读小说
from 功能文件.管理功能.小说功能.功能 import 小说功能开关, 找书


class 塔读小说基础行为测试(unittest.TestCase):
    def test_章节并发动态上限为四百(self):
        self.assertEqual(塔读小说.计算塔读章节并发数(0), 1)
        self.assertEqual(塔读小说.计算塔读章节并发数(399), 399)
        self.assertEqual(塔读小说.计算塔读章节并发数(401), 400)

    def test_识别塔读书籍来源和编号(self):
        来源 = "https://reader.tadu.com/book/123456.html?bookId=123456"
        self.assertEqual(塔读小说.提取塔读书籍编号(来源), "123456")
        self.assertEqual(塔读小说.提取塔读直接来源(来源), 来源)
        self.assertIsNone(塔读小说.提取塔读直接来源("https://example.com/book/123456"))

    def test_解析搜索和批量章节地址(self):
        搜索结果 = 塔读小说.解析塔读搜索书籍({
            "code": 100,
            "data": {"books": [{
                "bookId": 123456,
                "bookName": "测试书",
                "authorName": "测试作者",
                "wordCount": 123456,
                "status": "完结",
            }]},
        })
        self.assertEqual(搜索结果[0]["book_id"], "123456")
        self.assertEqual(搜索结果[0]["title"], "测试书")
        self.assertEqual(搜索结果[0]["author"], "测试作者")

        章节 = 塔读小说.解析塔读批量章节({
            "code": 100,
            "data": {
                "domain": "http://media.tadu.com",
                "chapters": [{
                    "chapterId": 7,
                    "chapterNum": 1,
                    "chapterName": "第一章",
                    "chapterUrl": "/chapter/7.tdz",
                }],
            },
        })
        self.assertEqual(章节[0]["chapter_id"], "7")
        self.assertEqual(章节[0]["url"], "http://media.tadu.com/chapter/7.tdz")

    def test_使用库解析_tadu_容器正文(self):
        内容 = "第一章\r这是正文"
        压缩正文 = gzip.compress(内容.encode("utf-16le"))
        容器 = (
            b"tadu"
            + b"\x01\x00\x00\x00"
            + (0).to_bytes(8, "little")
            + (32).to_bytes(8, "little")
            + len(压缩正文).to_bytes(8, "little")
            + 压缩正文
        )
        self.assertEqual(塔读小说.提取塔读正文(容器), "第一章\n这是正文")

    def test_塔读进入小说开关和找书路由(self):
        self.assertIn("塔读", 小说功能开关.默认状态)
        self.assertIn("开启塔读", 小说功能开关.开关命令配置)
        self.assertEqual(找书.构造塔读链接("123456"), "https://reader.tadu.com/book/123456")


if __name__ == "__main__":
    unittest.main()
