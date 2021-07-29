import os
import argparse

from .guesser import Guesser
from .utils import validate_cwd_is_git_repo, user_response_yes_no, get_requirements_txt_lines, write_requirements_file


__VERSION__ = "0.0.1"

parser = argparse.ArgumentParser("Python Requirements Version Guesser")
parser.add_argument('--write', type=str, default=None, required=False, nargs='?', const='')
parser.add_argument('--force_guess', type=str, default=None, required=False)
parser.add_argument('--keep_unused_packages', action='store_true', required=False)


def run():
    print("="*60)
    print(f"Python requirements guesser v{__VERSION__}")
    print("="*60)
    print(f"Guessing package versions for project '{os.getcwd()}'")

    args = parser.parse_args()

    if not validate_cwd_is_git_repo():
        print("[ERROR] py-reqs-guesser must be runned inside a git repository")
        exit(1)

    print("Follow the steps to guess package versions based on when they were added to git.")

    # Initialisation
    guesser = Guesser(args.force_guess, args.keep_unused_packages)

    # Interactive guessing of packages versions
    packages = guesser.guess_package_versions()

    # Create requirements.txt
    updated_requirements_txt_lines = get_requirements_txt_lines(packages)

    print("\n" + "="*60 + "\n")
    print("Requirements.txt :")
    print(updated_requirements_txt_lines)

    if args.write is None:
        print("Use the --write {path} parameter to write the new requirements file")
    else:
        if len(args.write) == 0:
            # Default location if --write toggle without {path}
            args.write = "requirements.txt"

        write_requirements_file(updated_requirements_txt_lines, args.write)
        

if __name__ == "__main__":
    run()
