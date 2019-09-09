from setuptools import find_packages
from setuptools import setup

__version__ = '0.1.0'


setup(
    name='multiprocessing_dag',
    version=__version__,
    description="Use Python's multiprocessing module to execute a DAG of functions in separate processes.",
    url='https://www.github.com/ecdavis/multiprocessing_dag',
    packages=find_packages(exclude=['tests*']),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX :: Linux',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
