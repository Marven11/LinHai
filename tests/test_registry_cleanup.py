import asyncio
import unittest

from linhai.registry import Registry


class TestRegistryCleanup(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_register_and_call_cleanup(self):
        r = Registry()
        called = []

        async def cleanup():
            called.append(True)

        r.register_cleanup(cleanup)
        self.loop.run_until_complete(r.call_cleanups())
        self.assertEqual(called, [True])

    def test_multiple_cleanups_called_in_parallel(self):
        r = Registry()
        order = []

        async def c1():
            order.append("c1_start")
            await asyncio.sleep(0.01)
            order.append("c1_end")

        async def c2():
            order.append("c2_start")
            await asyncio.sleep(0.01)
            order.append("c2_end")

        r.register_cleanup(c1)
        r.register_cleanup(c2)
        self.loop.run_until_complete(r.call_cleanups())
        self.assertIn("c1_start", order)
        self.assertIn("c1_end", order)
        self.assertIn("c2_start", order)
        self.assertIn("c2_end", order)

    def test_call_cleanups_empty(self):
        r = Registry()
        self.loop.run_until_complete(r.call_cleanups())

    def test_cleanup_exception_does_not_stop_others(self):
        r = Registry()
        called = []

        async def failing():
            raise RuntimeError("test error")

        async def ok():
            called.append(True)

        r.register_cleanup(failing)
        r.register_cleanup(ok)
        self.loop.run_until_complete(r.call_cleanups())
        self.assertEqual(called, [True])


if __name__ == "__main__":
    unittest.main()
