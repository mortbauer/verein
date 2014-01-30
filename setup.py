from setuptools import setup

setup(name='verein',
      version='1.0',
      description='OpenShift App',
      author='Your Name',
      author_email='example@example.com',
      url='http://www.python.org/sigs/distutils-sig/',
      install_requires=[x for x in open('requirements.txt','r').read().split('\n') if x],
     )
