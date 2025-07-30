import argparse
import unittest
import sys


def run_tests():
    """运行所有单元测试"""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="linhai/tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description="LinHai 主程序")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 添加test命令
    test_parser = subparsers.add_parser("test", help="运行单元测试")

    args = parser.parse_args()

    if args.command == "test":
        success = run_tests()
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
