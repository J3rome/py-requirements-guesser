import re

def user_response_multi(message, choices):
    for i, choice in enumerate(choices):
        print(f'{i+1}. {choice}')


    nb_choices = len(choices)
    resp = int(input(f'{message} [1-{nb_choices}]\n'))

    if resp not in range(1,nb_choices+1):
        return user_response_multi(message, choices)

    return resp


def user_response_yes_no(message):


    resp = input(message + ' [Y/n]\n').lower()

    if resp not in ['y', 'n']:
        return user_response_yes_no(message)

    return resp == 'y'


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

        packages[splitted[0]] = version

    return packages


def detect_os():
    pass


def get_python_version():
    pass
