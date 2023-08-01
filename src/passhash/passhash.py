#!/usr/bin/env python3
"""Generate password hashes based on various standards."""
import sys

from argparse import ArgumentParser, Namespace, SUPPRESS
from getpass import getpass
from pathlib import Path
from time import time

from passlib import pwd
from passlib.exc import MissingBackendError
from passlib.registry import get_crypt_handler
from rich.console import Console
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.table import Table, Column
from yaml import safe_load

from passhash import __name__, __version__, __copyright__


# Load the list of supported algorithms
_algorithm_types = {
    "unix": "Unix Algorithms (crypt)",
    "windows": "Windows Algorithms",
    "cisco": "Cisco Algorithms",
    "ldap": "LDAP Algorithms",
}
with Path(Path(__file__).parent.resolve(), "algorithms.yml").open() as f:
    _algorithms = safe_load(f)
ALGORITHMS = {a["const"] for t in _algorithm_types for a in _algorithms[t]}


def _handle_cli() -> Namespace:
    """Handle the CLI arguments and prompting."""
    # Create an argument parser with global options
    parser = ArgumentParser(
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
        help=SUPPRESS,
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

    # Prepare the username
    if args.username is None and (
        "msdcc" in args.algorithms or "msdcc2" in args.algorithms
    ):
        args.username = input("Username: ")

    # Prepare the password to hash
    if args.generate:
        args.password = pwd.genword(entropy="secure", charset="ascii_50")
        sys.stdout.write(f"Password: {args.password}\n")
    else:
        args.password = getpass()

    return args


def main() -> int:
    """Execute CLI."""
    try:
        retval = 0
        args = _handle_cli()
        results = {}
        console = Console()
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(
                "Calculating hashes...",
                total=len(args.algorithms),
            )
            # Hash using each selected algorithm and print
            for algorithm in args.algorithms:
                # Load the correct crypt handler
                handler = get_crypt_handler(algorithm, None)
                if handler is None:
                    results[algorithm] = (
                        "[bold red]:warning: Error loading backend[/bold red]",
                        "",
                    )
                    progress.advance(task)
                    retval += 1
                    continue

                # Load the relevant crypt parameters
                handler_params = {
                    k: args.params[k] for k in args.params if k in handler.setting_kwds
                }
                crypt = handler.using(**handler_params)

                # Create the password hash and print
                start = time()
                try:
                    if algorithm in ["msdcc", "msdcc2"]:
                        password_hash = crypt.hash(args.password, user=args.username)
                    else:
                        password_hash = crypt.hash(args.password)
                except TypeError:
                    results[algorithm] = (
                        "[bold red]:warning: Invalid parameter[/bold red]",
                        "",
                    )
                    progress.advance(task)
                    retval += 1
                    continue
                except MissingBackendError:
                    results[algorithm] = (
                        "[bold red]:warning: Missing backend[/bold red]",
                        "",
                    )
                    progress.advance(task)
                    retval += 1
                    continue
                end = time()

                # Output the password hash
                results[algorithm] = (password_hash, f"{end - start:.3f}s")
                progress.advance(task)
        table = Table(
            Column("Method"),
            Column("Hash", overflow="fold"),
            Column("Time"),
        )
        for a in sorted(results):
            table.add_row(a, *results[a])
        console.print(table)
        return retval
    except KeyboardInterrupt:
        sys.stderr.write("Process aborted by user...\n")
        return -1


if __name__ == "__main__":
    sys.exit(main())
