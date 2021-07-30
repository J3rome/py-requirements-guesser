# Python-Requirements-Guesser

> ⚠️ This is alpha quality software. Work in progress

Attempt to guess `requirements.txt` modules versions based on Git history.

## What is the problem ?
Did you ever clone a repo with python code that didn't specify library versions in a `requirements.txt` file ?
Or even worst: a repo without a `requirements.txt`...

Reproducing results is hard, it's even harder when you have mismatched library versions.

## Solution
There is a fair chance that the owner of the repo you just cloned installed most of it's packages using 
```bash
pip install <package name>
```
This would have installed the latest available version at the time the command was runned.

Based on this, we look at the `git commit history` to find out when a package was first imported in the code or when it was first added to the `requirements.txt` file.

We then query `Pypi` to retrieve the version available at the commit date.

## Usage
`Py-Requirements-Guesser` should be runned inside a git repository.
```bash
py-requirements-guesser --write {requirements.txt path}
```
You will be prompted by a serie of choice to orient the guessing process.

![Python Requirements Guesser](https://github.com/J3rome/py-requirements-guesser/raw/main/img/py-requirements-guesser.gif)

## Installation
This package doesn't have any dependencies.
To install the `Py-Requirements-Guesser`:
```bash
pip3 install py-requirements-guesser
```


## Package name mapping - Pipreqs
There might be mismatches between the name of a package on `Pypi` and the name used to `import` it (Ex : `pip install PyYAML` & `import yaml` ).
There doesn't seem to be a straightforward way to do the mapping between `Pypi` name and `import` name. 

The great [PipReqs](https://github.com/bndr/pipreqs) package (which was an inspiration for this package) manually maintains a mapping file between `Pypi` names and the `import` names. 
They also maintain a list of the standard library module names.

For now, we grab the [mapping](https://github.com/bndr/pipreqs/blob/master/pipreqs/mapping) and [stdlib](https://github.com/bndr/pipreqs/blob/master/pipreqs/stdlib) files at commit `90102acdbb23c09574d27df8bd1f568d34e0cfd3`. 

**Thanks guys** !

## Additional arguments
`Py-Requirements-Guesser` can take 2 additional parameters :

`--keep_unused_packages`: By default, unused packages are ignored. This parameter will force version guessing for the packages in `requirements.txt` that are not `imported` in the code anywhere. 

`--force_guess {package1},{package2},..`: By default, if your code contains a module named `yaml.py`, `import yaml` statements won't be analyzed. Use this argument if local modules have conflicting names with `Pypi` packages to force version guessing. 

## TODO
- Guess/Pin the dependencies tree of the package Ex : Torch package will install numpy, etc
- Poetry support ?
- Jupyter notebook support
- Add guessing choice where user can choose version between the time the package was first imported and the date of the last commit on a python file
- Detect python & os versions. Some package versions might not be available for certain os or python versions
- Better output/UX

## License
GNU GPLV3 see [License](LICENSE)

## Contributing
Pull requests are welcomed !
Fill up an issue if you encounter any problem !
