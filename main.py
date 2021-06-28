import re
import os
import argparse
import subprocess
import json
from datetime import datetime
from urllib.request import urlopen

from utils import load_packages_from_requirements, get_mapping_files_from_pipreqs, user_response_multi_choices
from utils import get_date_last_modified_python_file, get_local_modules, validate_cwd_is_git_repo, user_response_yes_no

# TODO : Propose choice between date of first import or Added in requirements
# TODO :    Other choices : When project was created, last commit (That wasnt on md file) get_date_last_modified_python_file()

# TODO : Pin also the dependencies tree of the packages Ex : Torch package might install numpy, etc

# TODO : Poetry mode ?

# TODO : Add a mode where file/folder creation/last update is used if no git repo ?

# TODO : Add jupyter notebook support
# TODO : Hide logging argument
# TODO : Add switch to keep unused imports

# FIXME : Some unused imports might be important (Pillow for example)

EXTRACT_DATE_REGEX = re.compile(r'date\s-\s(\d+)')
LETTER_REGEX = re.compile(r'[a-zA-Z]')

parser = argparse.ArgumentParser("Python Requirements Version Guesser")
parser.add_argument('--write', type=str, default=None, required=False, nargs='?', const='')
parser.add_argument('--force_guess', type=str, default=None, required=False)
parser.add_argument('--keep_unused_packages', action='store_true', required=False)


def get_pypi_history(package_name, ignore_release_candidat=True):
    """
    Retrieve version release dates via Pypi JSON api
    """
    try:
        resp = urlopen(f"https://pypi.org/pypi/{package_name}/json")
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


def find_version_at_date(available_versions, date):
    last_version = available_versions[0][0]

    # FIXME : Do binary search
    for candidate_version, candidate_date in available_versions:
        if date >= candidate_date:
            return candidate_version
        else:
            last_version = candidate_version

    # Date is older than available versions... Fallback on the oldest available version
    return last_version


def get_all_imports(stdlib_list=None):
    cmd = f'grep -PRoh --include="*.py" "(?<=^import )\\w*|(?<=^from )\\w*" . | sort | uniq'

    try:
        grep_out = subprocess.check_output(cmd, shell=True).decode().strip()
    except:
        grep_out = ""

    if len(grep_out) == 0:
        raise Exception(f"[ERROR] couldn't find any import statement")

    imports = [l.strip() for l in grep_out.split("\n")]

    if stdlib_list:
        return [l for l in imports if l not in stdlib_list]

    return imports


def get_date_when_package_committed(package_name, via_requirements=False, latest_addition=False):
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
    return sorted(dates, reverse=not latest_addition)[0]


def guess_package_versions(package_list, from_import_to_package_mapping, from_package_to_import_mapping, packages_in_requirements, keep_unused_packages=False):
    packages = []
    for package_name, version in all_packages.items():
        print("\n" + "-"*40)
        print(f"PACKAGE : {package_name}")
        if version is None:
            # Reset variables
            choice = None
            date_added_via_import_str = None
            date_added_via_req_str = None
            import_version = None
            req_version = None

            # Pypi package to import mapping
            import_name = from_package_to_import_mapping.get(package_name, package_name)
            pypi_package_name = from_import_to_package_mapping.get(package_name, package_name)

            # Get available versions from Pypi
            available_versions = get_pypi_history(pypi_package_name, ignore_release_candidat=True)

            if available_versions is None:
                print(f"[INFO] Couldn't find Pypi releases for package '{package_name}', ignoring")
                continue

            # Retrieve candidate version based on the first time the package was imported in *.py
            date_added_via_import = get_date_when_package_committed(import_name, via_requirements=False)
            if date_added_via_import is None:
                print(f"    [INFO] Package '{package_name}' is defined in requirements.txt but not used (Or committed), ")
                if keep_unused_packages:
                    print("           will use the requirements version since --keep_unused_packages set")
                    choice = 2
                else:
                    print(f"[INFO] Ignoring package '{package_name}' (Use --keep_unused_packages if you want to keep it)")
                    continue
            else:
                date_added_via_import_str = date_added_via_import.strftime("%Y-%m-%d")
                import_version = find_version_at_date(available_versions, date_added_via_import)

            # Retrieve candidate version based on the first time the package was added to requirements.txt
            if pypi_package_name.lower() in packages_in_requirements:
                date_added_via_req = get_date_when_package_committed(pypi_package_name, via_requirements=True)
                if date_added_via_req is not None:
                    req_version = find_version_at_date(available_versions, date_added_via_req)
                    date_added_via_req_str = date_added_via_req.strftime("%Y-%m-%d")
                else:
                    print(f"    [INFO] Package '{package_name}' was not in requirements.txt, using date of first import (Version {import_version} / {date_added_via_import_str})")
                    choice = 1

                if choice is None:
                    if req_version != import_version:
                        # Ask user to choose version based on either first import date or first added to requirements.txt date
                        choice = user_response_multi_choices(f"Choose guessing strategy for package '{package_name}'", [
                            f'{"First time the package was imported".ljust(50)} (Version {import_version} / {date_added_via_import_str})', 
                            f'{"When the package was added to requirements.txt".ljust(50)} (Version {req_version} / {date_added_via_req_str})'
                        ])
                    else:
                        # Both requirements.txt and first import resolve to the same version
                        choice = 1
            else:
                print(f"    [INFO] Package '{package_name}' was not found in requirements.txt, using date of first import (Version {import_version} / {date_added_via_import_str})")
                choice = 1

            if choice == 2:
                version = req_version
            else:
                version = import_version

            if version is not None:
                print(f"[INFO] Package '{package_name}' was attributed version {version}")
            else:
                print(f"[ERROR] Couldn't attribute version to package '{package_name}'. Are you sure you commited the changes ?")
                continue

        else:
            print(f"[INFO] Package '{package_name}' version is specified in requirements.txt (Version {version})")

        packages.append((package_name, version))

    return packages


if __name__ == "__main__":
    print("="*60)
    print("Python requirements guesser")
    print("="*60)
    print(f"Guessing package versions for project '{os.getcwd()}'")

    if not validate_cwd_is_git_repo():
        print("[ERROR] py-reqs-guesser must be runned inside a git repository")
        exit(1)

    print("Follow the steps to guess package versions based on when they were added to git.")

    args = parser.parse_args()

    # Retrive mapping files from https://github.com/bndr/pipreqs
    stdlib_list, from_import_to_package_mapping, from_package_to_import_mapping = get_mapping_files_from_pipreqs()

    # Get local packages
    if args.force_guess:
        args.force_guess = set(args.force_guess.strip().split(","))

    local_packages = get_local_modules(print_modules=True, force_guess=args.force_guess)

    # Remove local_packages from the list of imports
    stdlib_list.update(local_packages)

    # Retrieve all imported packages in project
    all_imported_packages = set(get_all_imports(stdlib_list))

    # Retrieve packages in requirements.txt
    packages_in_requirements_version_map = load_packages_from_requirements('requirements.txt')
    packages_in_requirements = set(packages_in_requirements_version_map.keys())


    # Merge packages in requirements.txt and imports
    all_packages = packages_in_requirements_version_map
    extra_packages = all_imported_packages - packages_in_requirements
    for extra_package in extra_packages:
        all_packages[extra_package] = None

    # Interactive guessing of packages versions
    packages = guess_package_versions(all_packages, from_import_to_package_mapping, from_package_to_import_mapping, packages_in_requirements, keep_unused_packages=args.keep_unused_packages)

    new_requirements_txt = ""
    for package_name, version in sorted(packages, key=lambda x:x[0]):
        new_requirements_txt += f"{package_name}=={version}\n"

    print("\n" + "="*60 + "\n")
    print("Requirements.txt :")
    print(new_requirements_txt)
    if args.write is None:
        print("Use the --write {path} parameter to write the new requirements file")
    else:
        if len(args.write) == 0:
            args.write = "requirements.txt"

        print(f"Writing requirements to file {args.write}")

        if os.path.exists(args.write) and \
            not user_response_yes_no(f"File {args.write} already exist, are you sure you want to overwrite it ?"):
                exit(0)

        with open(args.write, 'w') as f:
            f.write(new_requirements_txt)
        # TODO : Write to args.write


        


