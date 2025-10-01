from setuptools import setup, find_packages

setup(
    name='linhai',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'fenjing',
        'openai',
        'httpx',
        'beautifulsoup4',
        'mistune',
        'requests',
        'textual',
        'selenium'
    ],
    extras_require={
        'dev': [
            'pylint',
            'black',
            'mypy',
            'pytest'
        ]
    },
    entry_points={
        'console_scripts': [
            'linhai=linhai.main:main',
        ],
    },
    author='LinHai',
    description='AI Agent for software engineering and penetration testing',
    url='https://github.com/linhai-agent',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
