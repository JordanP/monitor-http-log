import setuptools

classifiers = [
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Information Technology',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: Apache Software License',
    'Natural Language :: English',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.7',
]

setuptools.setup(
    name='monitor_http_log',
    version='0.1',
    description='HTTP log monitoring console program',
    url='https://github.com/JordanP/monitor-http-log',
    author='Jordan Pittier',
    author_email='jordan.pittier@gmail.com',
    license='Apache 2.0',
    packages=['monitor_http_log'],
    classifiers=classifiers,
    entry_points={
        'console_scripts': [
            'monitor_http_log = monitor_http_log.main:main',
        ],
    }
)
