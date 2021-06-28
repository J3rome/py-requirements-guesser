import re
import os
import subprocess
from datetime import datetime
from urllib.request import urlretrieve

def user_response_multi_choices(message, choices):
    print(message)
    for i, choice in enumerate(choices):
        print(f'    {i+1}. {choice}')


    nb_choices = len(choices)
    resp = input(f'Choose option [1-{nb_choices}]\n')

    if not resp.isdigit() or int(resp) not in range(1,nb_choices+1):
        print("")
        return user_response_multi_choices(message, choices)

    return int(resp)


def user_response_yes_no(message):
    resp = input(message + ' [Y/n]\n').lower()

    if resp not in ['y', 'n']:
        print("")
        return user_response_yes_no(message)

    return resp == 'y'


def get_mapping_files_from_pipreqs(tmp_path="/tmp/.py-req-guesser"):
    """
    Retrieve import to package name mapping file and standard lib module list
    This list comes from https://github.com/bndr/pipreqs
    """

    skip_download = False

    if not os.path.exists(tmp_path):
        os.mkdir(tmp_path)

    mapping_filepath = f"{tmp_path}/mapping"
    stdlib_filepath = f"{tmp_path}/stdlib"

    if os.path.exists(mapping_filepath) and os.path.exists(stdlib_filepath):
        # File have already been downloaded
        skip_download = True

    if not skip_download:
        msg = "We will download a mapping file from https://github.com/bndr/pipreqs\n" \
                "Thanks to the maintainers of Pipreqs for keeping the mapping file "\
                "and the STDlib module list up to date\n" \
                f"Do you agree to downloading these files in '{tmp_path}' ?"

        if not user_response_yes_no(msg):
            print("\n\n[ERROR]Pipreqs mapping files are required, I encourage you to inspect the code to make sure everything is safe and rerun this")
            exit(0)

        print("")
        # FIXME : This is not really scalable...
        mapping_url = "https://raw.githubusercontent.com/bndr/pipreqs/90102acdbb23c09574d27df8bd1f568d34e0cfd3/pipreqs/mapping"
        stdlib_url = "https://raw.githubusercontent.com/bndr/pipreqs/90102acdbb23c09574d27df8bd1f568d34e0cfd3/pipreqs/stdlib"

        try:
            urlretrieve(mapping_url, mapping_filepath)
            urlretrieve(stdlib_url, stdlib_filepath)
        except:
            print("[ERROR] Internet access is required to fetch mapping files from https://github.com/bndr/pipreqs")
            exit(1)
        

    from_import_to_package_mapping = {}
    from_package_to_import_mapping = {}
    with open(mapping_filepath, 'r') as f:
        for line in f.readlines():
            import_name, package_name = line.strip().split(":")

            from_import_to_package_mapping[import_name] = package_name
            from_package_to_import_mapping[package_name] = import_name

    with open(stdlib_filepath, 'r') as f:
        stdlib = set([l.strip() for l in f.readlines()])

    return stdlib, from_import_to_package_mapping, from_package_to_import_mapping



def load_packages_from_requirements(filepath):
    # TODO : Handle when multiple version conditions
    # TODO : Handle greater than (>). If version contains >, should take the greatest available version at the date. Should fit with minor versions ?
    with open(filepath, 'r') as f:
        lines = f.readlines()

    split_reg = re.compile(r'==|<=|>=|<|>')

    packages = {}

    for line in lines:
        splitted = re.split(split_reg, line.strip())
        if len(splitted) > 1:
            version = splitted[-1]
        else:
            version = None

        packages[splitted[0].lower()] = version

    return packages


def get_local_modules(print_modules=False, force_guess=None):
    """
    Gather list of the local python modules so we don't query pypi for those modules
    Lets say we have the following file structure :
        /project
            - main.py
            /utils
                - common.py
    common.py will be imported in main.py using 'from utils import common'
    We therefore need to include the folder 'utils' in our exclusion list
    """
    if force_guess is None:
        force_guess = set()

    file_paths = subprocess.check_output('find . -name "*.py" -printf "%P\\n"', shell=True).decode().strip().split("\n")

    modules = set()

    for file_path in file_paths:
        module = file_path.split('/')[0]
        if '.py' in module:
            module = module[:-3]

        if module not in force_guess:
            modules.add(module)

    if print_modules:
        print("\nWe detected the following local project modules :")
        for module in modules:
            print("    " + module)
        print("We won't attempt to guess version for these packages (local files)")
        print("In case of conflict, this can be overriden using --force_guess {package1},{package2},...")

    return modules


def get_date_last_modified_python_file():
    timestamp = subprocess.check_output('git log -n 1 --all --pretty="format:%ct" -- "*.py"', shell=True).decode()

    if len(timestamp) == 0:
        return None
    else:
        return datetime.fromtimestamp(int(timestamp))


def validate_cwd_is_git_repo():
    try:
        subprocess.check_output("git rev-parse --is-inside-work-tree 2>/dev/null", shell=True)
    except:
        # git rev-parse return non-zero exit code if not in repo
        return False

    return True


def detect_os():
    pass


def get_python_version():
    pass
