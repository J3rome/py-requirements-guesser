import re
import os
import argparse
import subprocess
from datetime import datetime
from xml.etree.ElementTree import fromstring as parse_xml

import requests

from utils import load_packages_from_requirements#, user_response_multi, user_response_yes_no

# TODO : Get all imports from source files
# TODO : Exclude imports where version is specified in requirements.txt

# TODO : Propose choice between date of first import or Added in requirements
# TODO :    Other choices : When project was created, last commit (That wasnt on md file), 75 percentile of time between commits

# TODO : Pin also the dependencies tree of the packages Ex : Torch package might install numpy, etc

# TODO : Poetry mode ?
#           - There might be a version in the history (1st Commit : matplotlib==1.0.1 -> 2nd commit : matplotlib==1.1.2 -> 3rd commit : )

# TODO : import name doesn't always match the pypi name
#       A potential solution : https://github.com/thebjorn/pydeps/blob/master/pydeps/package_names.py
#       from pipreqs.pipreqs import get_all_imports, get_pkg_names

# TODO : Add a mode where file/folder creation/last update is used if no git repo ?

EXTRACT_DATE_REGEX = re.compile(r'Date:\s*(\d+)')
LETTER_REGEX = re.compile(r'[a-zA-Z]')

parser = argparse.ArgumentParser("Python Requirements Version Guesser")
parser.add_argument('--git_repo_path', type=str, default=None, required=False)


def get_pypi_history(package_name, ignore_release_candidat=True):
    """
    Retrieve version release dates via Pypi JSON api
    """

    resp = requests.get(f"https://pypi.org/pypi/{package_name}/json").json()

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


def get_date_when_package_added(package_name, via_requirements=False):
    if not via_requirements:
        search_pattern = f"^import {package_name}$|^from {package_name}"
        filename = ""
    else:
        search_pattern = f"{package_name}$"
        filename = "requirements.txt"

    # We grep for 'date' | '+ search pattern' so that we keep only commits that insert lines (+)
    cmd = f"git log -G '{search_pattern}' --date unix -p {filename} | grep -i 'date\\|\\+.*{package_name}'"

    try:
        blame_out = subprocess.check_output(cmd, shell=True).decode().strip()
    except:
        blame_out = ""

    if len(blame_out) == 0:
        #return []
        raise Exception(f"[ERROR] couldn't find package '{package_name}' via git-log")

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
    return sorted(dates, reverse=True)[0]


if __name__ == "__main__":

    packages_in_requirements = load_packages_from_requirements('requirements.txt')

    packages = []

    for package_name, version in packages_in_requirements.items():
        if version is None:
            date_added = get_date_when_package_added(package_name, via_requirements=True)
            available_versions = get_pypi_history(package_name, ignore_release_candidat=True)
            version = find_version_at_date(available_versions, date_added)
            print(f"{package_name} - {date_added}")

        else:
            print(f"{package_name} version is specified in requirements.txt ({version})")

        packages.append((package_name, version))


    # TODO : Write to requirements.txt
    for package_name, version in sorted(packages, key=lambda x:x[0]):
        print(f"{package_name}=={version}")


