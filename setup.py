import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='rcpl',
    version='0.0.0.1',
    scripts=['rcpl/rcpl'],
    author="Guido Bocchio",
    author_email="guido@bocch.io",
    description="I can't believe it's not a REPL",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Bocchio/rcpl",
    install_requires=['prompt_toolkit', 'pygments', 'dotsi'],
    packages=['rcpl'],
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
)
