import os

from .utils import get_pypi_history, get_all_imports, get_date_when_package_committed, find_version_at_date
from .utils import get_mapping_files_from_pipreqs, get_local_modules, get_packages_from_requirements, user_response_multi_choices

class Guesser:

    def __init__(self, force_guess=None, keep_unused_packages=False):
        self.keep_unused_packages = keep_unused_packages

        # Retrive mapping files from https://github.com/bndr/pipreqs
        # The mapping keys are all lowercase (case insensitive match)
        self.stdlib_list, self.import_to_package_mapping, self.package_to_import_mapping = get_mapping_files_from_pipreqs()

        # Get local packages
        if force_guess:
            force_guess = set(force_guess.strip().split(","))

        local_packages = get_local_modules(print_modules=True, force_guess=force_guess)

        # Remove local_packages from the list of imports
        self.stdlib_list.update(local_packages)

        # Retrieve all imported packages in project
        all_imported_packages = set(get_all_imports(self.stdlib_list))

        # Retrieve packages in requirements.txt
        packages_in_requirements = get_packages_from_requirements('requirements.txt')

        # Do mapping between import name and package name
        self.all_packages = {}
        for package_name, version in packages_in_requirements.items():
            package_name_lowercase = package_name.lower()
            import_name = self.package_to_import_mapping.get(package_name_lowercase, package_name)

            self.all_packages[package_name.lower()] = {
                'import_name': import_name,
                'package_name': package_name,
                'version': version,
                'in_requirements': True
            }


        for import_name in all_imported_packages:
            package_name = self.import_to_package_mapping.get(import_name, import_name)
            package_name_lowercase = package_name.lower()

            if package_name_lowercase not in self.all_packages:
                self.all_packages[package_name_lowercase] = {
                    'import_name': import_name,
                    'package_name': package_name,
                    'version': None,
                    'in_requirements': False
                }


    def guess_package_versions(self):
        packages = []
        for package_name_lowercase, package_info in self.all_packages.items():
            package_name = package_info['package_name']
            version = package_info['version']
            import_name = package_info['import_name']
            package_in_requirements = package_info['in_requirements']

            print("\n" + "-"*40)
            print(f"PACKAGE : {package_name}")
            if version is None:
                # Reset variables
                choice = None
                date_added_via_import_str = None
                date_added_via_req_str = None
                date = None
                import_version = None
                req_version = None

                # Get available versions from Pypi
                available_versions = get_pypi_history(package_name, ignore_release_candidat=True)

                if available_versions is None:
                    print(f"[INFO] Couldn't find Pypi releases for package '{package_name}', ignoring")
                    continue

                # Retrieve candidate version based on the first time the package was imported in *.py
                date_added_via_import = get_date_when_package_committed(import_name, via_requirements=False)
                if date_added_via_import is not None:
                    date_added_via_import_str = date_added_via_import.strftime("%Y-%m-%d")
                    import_version = find_version_at_date(available_versions, date_added_via_import)
                else:
                    print(f"    [INFO] Package '{package_name}' is defined in requirements.txt but not used (Or committed), ")
                    if self.keep_unused_packages:
                        print("           will attempts guessing version anyways since --keep_unused_packages is set set")
                        choice = 2
                    else:
                        print(f"[INFO] Ignoring package '{package_name}' (Use --keep_unused_packages if you want to keep it)")
                        continue
                    

                # Retrieve candidate version based on the first time the package was added to requirements.txt
                if package_in_requirements:
                    date_added_via_req = get_date_when_package_committed(package_name, via_requirements=True)
                    if date_added_via_req is not None:
                        req_version = find_version_at_date(available_versions, date_added_via_req)
                        date_added_via_req_str = date_added_via_req.strftime("%Y-%m-%d")
                    else:
                        print(f"    [INFO] Package '{package_name}' was not in requirements.txt, using date of first import (Version {import_version} / {date_added_via_import_str})")
                        choice = 1
                else:
                    print(f"    [INFO] Package '{package_name}' was not found in requirements.txt, using date of first import (Version {import_version} / {date_added_via_import_str})")
                    choice = 1


                # Ask user to choose version based on either first import date or first added to requirements.txt date
                if choice is None:
                    if req_version != import_version:
                        choice = user_response_multi_choices(f"Choose guessing strategy for package '{package_name}'", [
                            f'{"First time the package was imported".ljust(50)} (Version {import_version} / {date_added_via_import_str})', 
                            f'{"When the package was added to requirements.txt".ljust(50)} (Version {req_version} / {date_added_via_req_str})'
                        ])
                    else:
                        # Both requirements.txt and first import resolve to the same version
                        choice = 1

                if choice == 2:
                    version = req_version
                    date = date_added_via_req_str
                else:
                    version = import_version
                    date = date_added_via_import_str

                if version is not None:
                    print(f"[INFO] Package '{package_name}' was first committed on {date} and was attributed version {version}")
                else:
                    print(f"[ERROR] Couldn't attribute version to package '{package_name}'. Are you sure you commited the changes ?")
                    continue

            else:
                print(f"[INFO] Package '{package_name}' version is specified in requirements.txt (Version {version})")

            packages.append((package_name, version))

        return packages
