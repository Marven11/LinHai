import asyncio
import unittest
from linhai.queue import Queue, QueueClosed, select


class TestQueue(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_basic_queue_operations(self):
        async def _test():
            q = Queue()
            # 测试基本put/get
            await q.put(1)
            self.assertEqual(await q.get(), 1)

            # 测试队列大小
            self.assertEqual(q.qsize(), 0)
            await q.put(2)
            self.assertEqual(q.qsize(), 1)

            # 添加短暂延迟确保队列状态更新
            await asyncio.sleep(0.01)

            # 测试队列空/满状态
            self.assertFalse(q.empty())  # 队列中有元素2，应为False
            await q.put(3)
            self.assertEqual(q.qsize(), 2)
            self.assertFalse(q.full())

            # 测试关闭队列
            q.close()
            self.assertTrue(q.is_closed())

            # 测试关闭后put
            with self.assertRaises(QueueClosed):
                await q.put(4)

            # 测试关闭后get（按FIFO顺序）
            self.assertEqual(await q.get(), 2)  # 队列中还有2和3，先取2
            self.assertEqual(await q.get(), 3)  # 再取3
            with self.assertRaises(QueueClosed):  # 队列空且已关闭
                await q.get()

        self.loop.run_until_complete(_test())

    def test_select_function(self):
        async def _test():
            q1 = Queue()
            q2 = Queue()

            # 启动生产者
            async def producer1():
                await asyncio.sleep(0.1)
                await q1.put("a")
                await asyncio.sleep(0.1)
                await q1.put("b")
                q1.close()

            async def producer2():
                await asyncio.sleep(0.2)
                await q2.put(1)
                await asyncio.sleep(0.1)
                await q2.put(2)
                q2.close()

            # 收集结果
            results = []
            indexes = []

            async def consumer():
                async for item, index in select(q1, q2):
                    results.append(item)
                    indexes.append(index)

            # 运行所有任务
            await asyncio.gather(producer1(), producer2(), consumer())

            # 验证结果（只验证元素存在性，不验证顺序）
            self.assertCountEqual(results, ["a", "b", 1, 2])
            self.assertCountEqual(indexes, [0, 0, 1, 1])

            # 验证q1产生了2个元素，q2产生了2个元素
            self.assertEqual(indexes.count(0), 2, "q1 should have 2 items")
            self.assertEqual(indexes.count(1), 2, "q2 should have 2 items")

        self.loop.run_until_complete(_test())

    def test_select_with_closed_queue(self):
        async def _test():
            q1 = Queue()
            q2 = Queue()

            # 立即关闭q2
            q2.close()

            # 启动生产者
            async def producer():
                await asyncio.sleep(0.1)
                await q1.put("a")
                q1.close()

            # 收集结果
            results = []

            async def consumer():
                async for item, _ in select(q1, q2):
                    results.append(item)

            # 运行所有任务
            await asyncio.gather(producer(), consumer())

            # 验证结果
            self.assertEqual(results, ["a"])

        self.loop.run_until_complete(_test())


if __name__ == "__main__":
    unittest.main()
