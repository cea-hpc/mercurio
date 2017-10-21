#! /bin/env python3
#
# author: Quentin Bouget <quentin.bouget@cea.fr>
#

"""
The command line interface of the project

Implemented commands:
    - send:      sends a list of files over the network
"""

import logging

from argparse import ArgumentParser
from multiprocessing import cpu_count

from mercurio import __version__
from mercurio.blocks import FileFactory, RsyncBlock

def send(args):
    """
    Send a list of file(s) and director{y,ies} to a remote host

    The remote host may be localhost
    """
    # Build pipeline of ProcessBlocks
    file_factory = FileFactory(args.paths)
    for _ in range(cpu_count()):
        RsyncBlock(args.scpurl, parent=file_factory)

    # Start and wait for completion
    file_factory.start()
    file_factory.join()

def main():
    """
    Build the command parser and launch the appropriate function
    """
    parser = ArgumentParser(prog="mercurio")
    subparsers = parser.add_subparsers()

    # Common options
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)

    # mercurio send
    send_parser = subparsers.add_parser(
        "send",
        description="Send one or many files over the network"
        )
    send_parser.set_defaults(main=send)

    send_parser.add_argument(
        "paths",
        metavar="PATH",
        nargs="+",
        help="file(s) or director{y,ies} to send"
        )
    send_parser.add_argument(
        "scpurl",
        help="destination path of the form 'user@host:path'"
        )

    # Activate logging
    logging.basicConfig(level=logging.WARNING)

    # In case users do not provide any command
    def _choose_an_action(_):
        return parser.error("Choose an action")
    parser.set_defaults(main=_choose_an_action)

    # Process command-line
    args = parser.parse_args()

    # Run
    exit(args.main(args))


if __name__ == "__main__":
    main()
