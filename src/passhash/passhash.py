#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import getpass
import os.path
import sys

from passhash import export, __name__, __version__, __copyright__

try:
    from yaml import safe_load
except ImportError:
    sys.stderr.write(
        "Error: Unable to import yaml module, ",
        "please install via 'pip install pyyaml'\n",
    )
    sys.exit(1)

try:
    from passlib import pwd
    from passlib.exc import MissingBackendError
    from passlib.registry import get_crypt_handler
except ImportError:
    sys.stderr.write(
        "Error: Unable to import passlib module, ",
        "please install via 'pip install passlib'\n",
    )
    sys.exit(1)


# Load the list of supported algorithms
_algorithm_types = {
    "unix": "Unix Algorithms (crypt)",
    "windows": "Windows Algorithms",
    "cisco": "Cisco Algorithms",
    "ldap": "LDAP Algorithms",
}
_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "algorithms.yml")
with open(_path, "r") as f:
    _algorithms = safe_load(f)
ALGORITHMS = {a["const"] for t in _algorithm_types.keys() for a in _algorithms[t]}


def handle_cli() -> "argparse.Namespace":
    """Handle the CLI arguments and prompting."""
    # Create an argument parser with global options
    parser = argparse.ArgumentParser(
        prog=__name__,
        add_help=False,
        usage=f"{__name__} [options]",
        description="Generate password hashes based on various standards",
    )
    optional = parser.add_argument_group(title="Optional Arguments")
    optional.add_argument(
        "-a",
        "--all",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    optional.add_argument(
        "-g",
        "--generate",
        action="store_true",
        help="Generate a random password",
    )
    optional.add_argument(
        "-r",
        "--rounds",
        metavar="NUM",
        type=int,
        help="Number of rounds to use, default varies by algorithm",
    )
    optional.add_argument(
        "-s",
        "--salt",
        metavar="STR",
        type=str,
        help="Salt to use, randomly generated if not provided",
    )
    optional.add_argument(
        "--salt-size",
        metavar="NUM",
        type=int,
        help="Size of the randomly-generated salt",
    )
    optional.add_argument(
        "-u",
        "--username",
        metavar="STR",
        type=str,
        help="Username for the account, required by some algorithms",
    )
    optional.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit",
    )
    optional.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"{__name__} v{__version__} {__copyright__}",
        help="Show program's version number and exit",
    )

    # Add supported algorithms
    algorithm_types = {}
    for name, title in _algorithm_types.items():
        algorithm_types[name] = parser.add_argument_group(title=title)
        for algorithm in _algorithms[name]:
            algorithm_types[name].add_argument(
                algorithm["opt"],
                action="append_const",
                dest="algorithms",
                const=algorithm["const"],
                help=algorithm["help"],
            )

    # Initialize dummy arguments and parse
    parser.set_defaults(
        params={},
        password=None,
    )
    args = parser.parse_args()

    # Prepare the algorithm list
    if args.all:
        args.algorithms = ALGORITHMS
    elif args.algorithms is None or len(args.algorithms) < 1:
        args.algorithms = ["sha512_crypt"]  # Default if no algorithms are specified

    # Prepare the parameters to pass to the crypt module, if any
    if args.salt is not None:
        args.params["salt"] = args.salt
    if args.salt_size is not None:
        args.params["salt_size"] = args.salt_size
    if args.rounds is not None:
        args.params["rounds"] = args.rounds

    # Prepare the password to hash
    if args.generate:
        args.password = pwd.genword(entropy="secure", charset="ascii_50")
        sys.stdout.write(f"Generated Password: {args.password}\n\n")
    else:
        args.password = getpass.getpass()

    return args


@export
def main() -> int:
    """Main execution thread."""
    retval = 0
    args = handle_cli()
    # Hash using each selected algorithm and print
    for algorithm in args.algorithms:
        # Load the correct crypt handler
        try:
            handler = get_crypt_handler(algorithm)
        except KeyError:
            sys.stderr.write(f"{algorithm}: ERROR loading algorithm handler\n")
            retval += 1
            continue

        # Load the relevant crypt parameters
        handler_params = {
            k: args.params[k] for k in args.params.keys() if k in handler.setting_kwds
        }

        # Try to load the configured crypt handler
        try:
            try:
                crypt = handler.using(**handler_params)
            except TypeError:  # Attempt to convert the salt to bytes
                handler_params["salt"] = handler_params["salt"].encode("utf-8")
                try:
                    crypt = handler.using(**handler_params)
                except TypeError as e:
                    sys.stderr.write(f"{algorithm}: ERROR invalid parameter - {e}\n")
                    retval += 1
                    continue
        except ValueError as e:
            sys.stderr.write(f"{algorithm}: ERROR invalid parameter - {e}\n")
            retval += 1
            continue

        # Create the password hash and print
        try:
            if algorithm in ["msdcc", "msdcc2"] and args.username is not None:
                password_hash = crypt.hash(args.password, user=args.username)
            else:
                password_hash = crypt.hash(args.password)
        except TypeError as e:
            sys.stderr.write(f"{algorithm}: ERROR invalid parameter - {e}\n")
            retval += 1
            continue
        except MissingBackendError as e:
            sys.stderr.write(f"{algorithm}: ERROR missing backend - {e}\n")
            retval += 1
            continue

        # Output the password hash
        sys.stdout.write(f"{algorithm}: {password_hash}\n")

    return retval


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("Process aborted by user...\n")
        sys.exit(1)
