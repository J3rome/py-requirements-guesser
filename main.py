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
# TODO : Get date when import added via git-blame/git-log
# TODO : Propose choice between date of first import or Added in requirements
# TODO : 	Other choices : When project was created, last commit (That wasnt on md file), 75 percentile of time between commits

# TODO : Pin also the dependencies tree of the packages Ex : Torch package might install numpy, etc

# TODO : Poetry mode ?
#			- There might be a version in the history (1st Commit : matplotlib==1.0.1 -> 2nd commit : matplotlib==1.1.2 -> 3rd commit : )

# TODO : import name doesn't always match the pypi name
#		A potential solution : https://github.com/thebjorn/pydeps/blob/master/pydeps/package_names.py
#		from pipreqs.pipreqs import get_all_imports, get_pkg_names

# TODO : What happen if the import is moved around ?

# TODO : Add a mode on file/folder creation/last update if no git repo ?


EXTRACT_DATE_REGEX = re.compile(r'(\d*)\s(?=\d+\))')
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
		# TODO : Give appropriate version based on os and python Versions 		resp['info']['requires_dist'] # ['require_python']
		if len(release_info_per_os) == 0:
			continue

		if ignore_release_candidat and LETTER_REGEX.search(version):
			continue

		release_info = release_info_per_os[0]
		release_date = datetime.strptime(release_info['upload_time'].split("T")[0], '%Y-%m-%d')
		versions.append((version, release_date))

	# FIXME : Do we really need to sort ? Versions should already be sorted
	return sorted(versions, key=lambda x:x[1], reverse=True)


def get_pypi_history_rss(package_name, ignore_release_candidat=True):
	"""
	Retrieve version release dates
	Some releases don't comprises release date when queried via the JSON api.
	We retrieve the version history via the RSS feed
	"""

	resp = requests.get(f"https://pypi.org/rss/project/{package_name}/releases.xml")

	# FIXME : This is vulnerable to xml exploits. In theory a malicious user could insert a malicious payload into pypi description and get RCE on people using this package...
	root_node = parse_xml(resp.text)

	items = root_node[0].findall('item')
	if len(items) == 0:
		raise Exception(f"[ERROR] Couldn't retrieve versions for package {package_name} from Pypi")

	versions = []

	for item in items:
		attributes = item.getchildren()
		version = attributes[0].text
		if 'rc' in version and ignore_release_candidat:
			continue
		
		release_date = datetime.strptime(attributes[-1].text, '%a, %d %b %Y %H:%M:%S %Z')
		versions.append((version, release_date))

	# FIXME : Do we really need to sort ? Versions should already be sorted
	return sorted(versions, key=lambda x:x[1], reverse=True)



def get_date_added_to_requirements(package_name, requirements_filepath='requirements.txt'):
	# NOTE : Must be in the git directory for this to work. Change directory before ?
	cmd = f"git blame -L'/{package_name}/',+1 --date unix {requirements_filepath} 2>/dev/null"

	try:
		blame_out = subprocess.check_output(cmd, shell=True).decode()
	except:
		blame_out = ""

	if len(blame_out) > 0:
		matches = EXTRACT_DATE_REGEX.search(blame_out)

		if matches:
			date = datetime.fromtimestamp(int(matches.group(0)))

			return date
	
	raise Exception(f"[ERROR] Couldn't git blame {package_name} on {requirements_filepath}")


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


if __name__ == "__main__":

	packages_in_requirements = load_packages_from_requirements('requirements.txt')

	packages = []

	for package_name, version in packages_in_requirements.items():
		if version is None:
			date_added = get_date_added_to_requirements(package_name)
			available_versions = get_pypi_history(package_name, ignore_release_candidat=True)
			version = find_version_at_date(available_versions, date_added)
			print(f"{package_name} - {date_added}")

		else:
			print(f"{package_name} version is specified in requirements.txt ({version})")

		packages.append((package_name, version))


	# TODO : Write to requirements.txt
	for package_name, version in sorted(packages, key=lambda x:x[0]):
		print(f"{package_name}=={version}")


