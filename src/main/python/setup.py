from distutils.core import setup

setup(
    name='stratuslab-libcloud-drivers',
    version='${project.version}',
    author='StratusLab',
    author_email='contact@stratuslab.eu',
    url='http://stratuslab.eu/',
    license='Apache 2.0',
    description='${project.description}',
    long_description=open('README.txt').read(),

    packages=['stratuslab', 'stratuslab.libcloud'],

    install_requires=[
        "apache-libcloud ==0.12.4",
        "stratuslab-client",
        ],

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Operating System :: Unix',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: System :: Distributed Computing',
        ],

)
