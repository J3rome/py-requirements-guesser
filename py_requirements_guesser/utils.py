import re
import os
import json
import subprocess
from datetime import datetime
from urllib.request import urlretrieve
from urllib.request import urlopen


EXTRACT_DATE_REGEX = re.compile(r'date\s-\s(\d+)')
LETTER_REGEX = re.compile(r'[a-zA-Z]')


def get_pypi_history(package_name, ignore_release_candidat=True):
    """
    Retrieve version release dates via Pypi JSON api
    """
    try:
        resp = urlopen(f"https://pypi.org/pypi/{package_name}/json", timeout=20)
    except Exception as e:
        if hasattr(e, 'getcode') and e.getcode() == 404:
            return None
        else:
            print("[ERROR] Internet access is required to fetch package history from Pypi")
            exit(1)

    resp = json.loads(resp.read())

    versions = []
    for version, release_info_per_os in resp['releases'].items():
        # Just taking the first platform upload date for now.. 
        # Is it really different for other platforms ?  Need to validate
        # TODO : Give appropriate version based on os and python Versions       resp['info']['requires_dist'] # ['require_python']
        if len(release_info_per_os) == 0:
            continue

        if ignore_release_candidat and LETTER_REGEX.search(version):
            continue

        release_info = release_info_per_os[0]
        release_date = datetime.strptime(release_info['upload_time'].split("T")[0], '%Y-%m-%d')
        versions.append((version, release_date))

    # FIXME : Do we really need to sort ? Versions should already be sorted
    return sorted(versions, key=lambda x:x[1], reverse=True)


def get_all_imports(ignore_list=None):
    """
    Retrieve all the 'import XXX' and 'from XXX' statements in the local repo
    The ignore_list parameter is used to ignore local packages
    """
    cmd = f'grep -PRoh --include="*.py" "(?<=^import )\\w*|(?<=^from )\\w*" . | sort | uniq'

    try:
        grep_out = subprocess.check_output(cmd, shell=True).decode().strip()
    except:
        grep_out = ""

    if len(grep_out) == 0:
        raise Exception(f"[ERROR] couldn't find any import statement")

    imports = [l.strip() for l in grep_out.split("\n")]

    if ignore_list:
        return [l for l in imports if l not in ignore_list]

    return imports


def get_date_when_package_committed(package_name, via_requirements=False, first_occurence=True):
    """
    Use git log to retrieve the date at which the package was first imported or added to the requirements.txt file (Based on commit date)
    """
    if not via_requirements:
        search_pattern = f"^import {package_name}|^from {package_name}"
        filename = ""
    else:
        search_pattern = f"{package_name}$"
        filename = "requirements.txt"

    # We grep for 'date' | '+ search pattern' so that we keep only commits that insert lines (+)
    cmd = f"git log -i -G '{search_pattern}' --pretty='format:date - %at' --date unix -p {filename} | grep -i '^date - \\|\\+.*{package_name}'"

    try:
        blame_out = subprocess.check_output(cmd, shell=True).decode().strip()
    except:
        blame_out = ""

    if len(blame_out) == 0:
        #return []
        if not via_requirements:
            msg = f"'{package_name}' is defined in requirements.txt but not used, ignoring"
        else:
            msg = f"'{package_name}' was not found in requirements.txt"

        f"[INFO] {msg}"
        return None

    # Remove commit that are not directly followed by '+ import' (We grepped for this in cmd)
    # This is ugly.. TODO: figure out a better way in the grep command 
    dates = []
    got_plus = False
    for line in blame_out.split('\n')[::-1]:
        if line[0] == "+":
            got_plus = True
        elif got_plus:
            got_plus = False

            matches = EXTRACT_DATE_REGEX.search(line)
            if matches:
                dates.append(datetime.fromtimestamp(int(matches.group(1))))
            else:
                raise Exception("[ERROR] while parsing git-log")

    # Get first date where the line was added
    return sorted(dates, reverse=first_occurence)[0]


def find_version_at_date(available_versions, date):
    """
    Return version available at {date} given {available_versions}
    """
    last_version = available_versions[0][0]

    # FIXME : Do binary search
    for candidate_version, candidate_date in available_versions:
        if date >= candidate_date:
            return candidate_version
        else:
            last_version = candidate_version

    # Date is older than available versions... Fallback on the oldest available version
    return last_version


def get_mapping_files_from_pipreqs(tmp_path="/tmp/.py-reqs-guesser"):
    """
    Retrieve 'import -> package' name mapping and standard lib module list
    The mapping key is lowercase so that we can match case insensitive
    These files come from https://github.com/bndr/pipreqs
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

            from_import_to_package_mapping[import_name.lower()] = package_name
            from_package_to_import_mapping[package_name.lower()] = import_name

    with open(stdlib_filepath, 'r') as f:
        stdlib = set([l.strip() for l in f.readlines()])

    return stdlib, from_import_to_package_mapping, from_package_to_import_mapping


def get_packages_from_requirements(filepath):
    """
    Retrieve package list from 'requirements.txt'
    """
    # TODO : Handle multiple version conditions
    # TODO : Handle greater than (>). If version contains >, should take the greatest available version at that date.
    packages = {}

    if not os.path.exists(filepath):
        return packages

    with open(filepath, 'r') as f:
        lines = f.readlines()

    split_reg = re.compile(r'==|<=|>=|<|>')

    for line in lines:
        splitted = re.split(split_reg, line.strip())
        if len(splitted) > 1:
            version = splitted[-1]
        else:
            version = None

        packages[splitted[0]] = version

    return packages


def get_local_modules(print_modules=False, force_guess=None):
    """
    Gather list of the local python modules so we don't query pypi for those modules
    Lets say we have the following file structure :
        /project
            - main.py
            - logger.py
            /utils
                - common.py
    common.py will be imported in main.py using 'from utils import common'
    We therefore need to include the folder 'utils' in our exclusion list
    In this example, the exclusion list is [main, logger, utils]

    print_modules: Control console printing
    force_guess: In case of conflict (Import packageX and local file named packageX.py), this list is used to force version guessing
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


def validate_cwd_is_git_repo():
    """"
    Verify that the current working directory is inside a git repository
    """
    try:
        subprocess.check_output("git rev-parse --is-inside-work-tree 2>/dev/null", shell=True)
    except:
        # git rev-parse return non-zero exit code if not in repo
        return False

    return True


def user_response_multi_choices(message, choices):
    """
    Multiple choice Menu prompt
    """
    print(message)
    for i, choice in enumerate(choices):
        print(f'    {i+1}. {choice}')


    nb_choices = len(choices)
    resp = input(f'Choose option [1-{nb_choices}] : ')

    if not resp.isdigit() or int(resp) not in range(1,nb_choices+1):
        print("")
        return user_response_multi_choices(message, choices)

    return int(resp)


def user_response_yes_no(message):
    """"
    Yes/No Menu prompt
    """
    resp = input(message + ' [Y/n] : ').lower()

    if resp not in ['y', 'n']:
        print("")
        return user_response_yes_no(message)

    return resp == 'y'


def get_date_last_modified_python_file():
    """
    Use git log to retrieve the last time a change to a .py file was committed to the repo
    """
    timestamp = subprocess.check_output('git log -n 1 --all --pretty="format:%ct" -- "*.py"', shell=True).decode()

    if len(timestamp) == 0:
        return None
    else:
        return datetime.fromtimestamp(int(timestamp))


def get_requirements_txt_lines(packages):
    requirements_txt = ""
    for package_name, version in sorted(packages, key=lambda x:x[0]):
        requirements_txt += f"{package_name}=={version}\n"

    return requirements_txt


def write_requirements_file(package_lines, filepath):
    print(f"Writing requirements to file {filepath}")

    if os.path.exists(filepath) and \
        not user_response_yes_no(f"File {filepath} already exist, are you sure you want to overwrite it ?"):
            exit(0)

    with open(filepath, 'w') as f:
        f.write(package_lines)
