import re
import os
import argparse
import subprocess
from datetime import datetime

import requests

from utils import load_packages_from_requirements, get_mapping_files_from_pipreqs, user_response_multi_choices
from utils import get_date_last_modified_python_file, get_python_filename_at_root

# TODO : Propose choice between date of first import or Added in requirements
# TODO :    Other choices : When project was created, last commit (That wasnt on md file) get_date_last_modified_python_file()

# TODO : Pin also the dependencies tree of the packages Ex : Torch package might install numpy, etc

# TODO : Poetry mode ?

# TODO : Add a mode where file/folder creation/last update is used if no git repo ?

# TODO : Add jupyter notebook support
# TODO : Hide logging argument
# TODO : Add switch to keep unused imports

# FIXME : Some unused imports might be important (Pillow for example)

EXTRACT_DATE_REGEX = re.compile(r'Date:\s*(\d+)')
LETTER_REGEX = re.compile(r'[a-zA-Z]')

parser = argparse.ArgumentParser("Python Requirements Version Guesser")
parser.add_argument('--git_repo_path', type=str, default=None, required=False)  # TODO : CHDIR in this directory if provided


def get_pypi_history(package_name, ignore_release_candidat=True):
    """
    Retrieve version release dates via Pypi JSON api
    """
    resp = requests.get(f"https://pypi.org/pypi/{package_name}/json")

    if resp.status_code != 200:
        print(f"[INFO] Couldn't find package '{package_name} on Pypi. Ignoring")
        return None

    resp = resp.json()

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
    cmd = f"git log -G '{search_pattern}' --date unix -p {filename} | grep -i '^date:\\|\\+.*{package_name}'"

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


def guess_package_versions(package_list, from_import_to_package_mapping, from_package_to_import_mapping, packages_in_requirements):
    packages = []
    for package_name, version in all_packages.items():
        if version is None:
            # TODO : Add argument to select one of the options by default
            skip_choice = False

            import_name = package_name

            if import_name in from_package_to_import_mapping:
                import_name = from_package_to_import_mapping[import_name]
            
            if package_name in from_import_to_package_mapping:
                package_name = from_import_to_package_mapping[package_name]

            available_versions = get_pypi_history(package_name, ignore_release_candidat=True)

            if available_versions is None:
                continue

            date_added_via_import = get_date_when_package_committed(import_name, via_requirements=False)
            if date_added_via_import is None:
                print(f"[INFO] Package '{package_name}' is defined in requirements.txt but not used (Or committed), ignoring")
                continue
            date_added_via_import_str = date_added_via_import.strftime("%Y-%m-%d")
            import_version = find_version_at_date(available_versions, date_added_via_import)

            if package_name in packages_in_requirements:
                date_added_via_req = get_date_when_package_committed(package_name, via_requirements=True)
                if date_added_via_req is not None:
                    req_version = find_version_at_date(available_versions, date_added_via_req)
                    date_added_via_req_str = date_added_via_req.strftime("%Y-%m-%d")
                else:
                    choice = 1
                    skip_choice = True
                    print(f"[INFO] Package '{package_name}' was not in requirements.txt, using date of first import (Version {import_version} / {date_added_via_import_str})")

                if not skip_choice and req_version == import_version:
                    print(f"[INFO] Package '{package_name}' was attributed version {req_version}")
                    skip_choice = True
                    choice = 1

                if not skip_choice:
                    choice = user_response_multi_choices(f"Choose guessing strategy for package '{package_name}'", [
                        f'{"First time the package was imported".ljust(50)} (Version {import_version} / {date_added_via_import_str})', 
                        f'{"When the package was added to requirements.txt".ljust(50)} (Version {req_version} / {date_added_via_req_str})'
                    ])

                if choice == 2:
                    version = req_version
                else:
                    version = import_version

            else:
                print(f"[INFO] Package '{package_name}' was not found in requirements.txt, using date of first import (Version {import_version} / {date_added_via_import_str})")
                version = import_version

        else:
            print(f"[INFO] Package '{package_name}' version is specified in requirements.txt ({version})")

        packages.append((package_name, version))

    return packages


if __name__ == "__main__":
    print("="*60)
    print("Python requirements guesser")
    print("="*60)

    print("\nFollow the steps to guess package versions based on when they were added to git\n")

    # Retrive mapping files from https://github.com/bndr/pipreqs
    stdlib_list, from_import_to_package_mapping, from_package_to_import_mapping = get_mapping_files_from_pipreqs()

    # Get local packages
    local_packages = get_python_filename_at_root()

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
    packages = guess_package_versions(all_packages, from_import_to_package_mapping, from_package_to_import_mapping, packages_in_requirements)

    print("")
    # TODO : Write to requirements.txt
    for package_name, version in sorted(packages, key=lambda x:x[0]):
        print(f"{package_name}=={version}")


