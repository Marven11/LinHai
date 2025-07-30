import sys
import unittest
import argparse
from linhai.main import main

def run_tests(test_case=None):
    """运行测试，支持指定测试用例"""
    loader = unittest.TestLoader()
    if test_case:
        # 格式: linhai.tests.test_module.TestClass.test_method
        if not test_case.startswith('linhai.tests.'):
            test_case = f'linhai.tests.{test_case}'
        suite = loader.loadTestsFromName(test_case)
    else:
        suite = loader.discover('linhai/tests')

    runner = unittest.TextTestRunner()
    return runner.run(suite)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='LinHai CLI')
    subparsers = parser.add_subparsers(dest='command')

    # 主命令
    main_parser = subparsers.add_parser('run', help='运行主程序')
    
    # 测试命令
    test_parser = subparsers.add_parser('test', help='运行测试')
    test_parser.add_argument('--case', help='指定测试用例 (格式: module.TestClass.test_method)')

    args = parser.parse_args()

    if args.command == 'test':
        sys.exit(0 if run_tests(args.case).wasSuccessful() else 1)
    else:
        main()
