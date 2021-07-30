import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="py-requirements-guesser",        # This is the name of the package
    version="0.1.0",                        # The initial release version
    author="Jerome Abdelnour",                     # Full name of the author
    description="Guess requirements.txt versions based on Git history",
    long_description=long_description,      # Long description read from the the readme file
    long_description_content_type="text/markdown",
    url="https://github.com/j3rome/py-requirements-guesser",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],                                      # Information to filter the project on PyPi website
    python_requires='>=3.6',                # Minimum version requirement of the package
    py_modules=['py_requirements_guesser'],
    packages=['py_requirements_guesser'],
    entry_points={
        'console_scripts': [
            'py-requirements-guesser=py_requirements_guesser.cli:run'
        ]
    }
)
