#! /bin/env python3
#
# This file is part of the RobinHood Library
# Copyright (C) 2019 Commissariat a l'energie atomique et aux energies
# 		      alternatives
#
# SPDX-License-Identifer: LGPL-3.0-or-later
#
# author: Quentin Bouget <quentin.bouget@cea.fr>

"""
The command line interface of the project

Implemented commands:
    - send:      sends a list of files over the network
    - authorize: correctly inserts an entry in authorized_keys
    - revoke:    correctly removes one or many entries in authorized_keys
"""

import logging

from argparse import ArgumentParser, FileType
from errno import EEXIST, EINVAL
from multiprocessing import cpu_count
from os import makedirs, open as open_, replace
from os.path import expanduser
from shutil import copy2
from string import Template
from sys import stderr

from mercurio import __version__
from mercurio.blocks import FileFactory, RsyncBlock
from mercurio.publickey import AuthorizedKeyEntry, PublicKey

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

AUTHKEY_PATH = expanduser('~/.ssh/authorized_keys')

def authorize(args):
    """
    Authorize the owner of a public key to use rsync on a given path
    """
    if args.owner:
        args.publickey.owner = args.owner
    elif "$owner" in args.destdir.template:
        if not args.publickey.owner:
            print("Was not able to guess the name of the key's owner which "
                  "is required to compute the destination directory: '%s'"
                  % args.destdir)
            return EINVAL

        print("Guessed the owner of the key: %s" % args.publickey.owner)

    destdir = args.destdir.substitute(owner=args.publickey.owner)

    # Only authorize an rsync command to be run for this key
    options = ['command="/bin/rrsync %s"' % destdir, "no-port-forwarding",
               "no-X11-forwarding", "no-pty"]
    entry = AuthorizedKeyEntry(args.publickey, options=options)

    with open(AUTHKEY_PATH, 'r+') as stream:
        for line in stream:
            if entry.publickey.key in line:
                print("The key provided is already being used", file=stderr)
                return EEXIST

        stream.write(str(entry) + '\n')

    makedirs(expanduser(destdir), mode=0o755, exist_ok=True)

def _private_open(*args, mode=0o600, **kwargs):
    """
    Calls os.open with mode set to 0o600 by default
    """
    return open_(*args, mode=mode, **kwargs)

def revoke(args):
    """
    Revoke a previously authorized identity

    Entries that are not prefixed with 'command="/bin/rrsync ' are
    considered not to have been set by mercurio's authorize command
    and therefore will not be modified.

    The workflow looks like this:
        Build the new authorized_keys file in a temporary file
        If there is no difference:
            Exit
        Otherwise:
            Create a backup file
            Replace AUTHKEY_PATH with the temporary file
    """
    # What is the comparation criteria?
    if args.publickey:
        # Compare the "key" attribute
        def _is_a_match(entry):
            return args.publickey.key == entry.publickey.key
    else:
        # Compare the "owner" attribute
        def _is_a_match(entry):
            if not entry.publickey.owner:
                print("Could not guess the owner of %s" % entry, file=stderr)
                return False
            return args.owner == entry.publickey.owner

    revoked_keys = []

    # Build a temporary file with only the non-matching keys
    with open(AUTHKEY_PATH) as stream:
        with open(AUTHKEY_PATH + '~', 'w', opener=_private_open) as tmpfile:
            for line in stream:
                try:
                    entry = AuthorizedKeyEntry.from_line(line.rstrip())
                except ValueError as exc:
                    print(exc, file=stderr)
                    tmpfile.write(line)
                    continue

                if not any(opt.startswith('command="/bin/rrsync ')
                           for opt in entry.options):
                    # Not a key managed by mercurio
                    tmpfile.write(line)
                    continue

                if _is_a_match(entry):
                    revoked_keys.append(entry)
                    continue

                tmpfile.write(line)

    if not revoked_keys:
        print("No matching key found")
        return

    # Create a backup
    copy2(AUTHKEY_PATH, AUTHKEY_PATH + '-')

    # Ensure .ssh/authorized_keys is always in a coherent state
    replace(expanduser('~/.ssh/authorized_keys~'),
            expanduser('~/.ssh/authorized_keys'))

    print("Revoked %i key(s):" % len(revoked_keys))
    print('\n'.join(str(key) for key in revoked_keys))


class PublicKeyFileType(FileType):
    """
    Utility class to parse a PublicKey from a filepath
    """
    # pylint: disable=too-few-public-methods

    def __call__(self, string):
        if not string.endswith('.pub'):
            string += '.pub'

        with super().__call__(string) as keyfile:
            return PublicKey.from_line(keyfile.readline().strip())

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

    # mercurio authorize
    authorize_parser = subparsers.add_parser(
        "authorize",
        description=("Authorize the owner of a given public key to write"
                     "(and read) data under a specific directory")
        )
    authorize_parser.set_defaults(main=authorize)

    authorize_parser.add_argument(
        "publickey",
        metavar="KEYFILE",
        type=PublicKeyFileType(),
        help="public key to authorize"
        )
    authorize_parser.add_argument(
        "-d", "--destdir",
        default="~/mercurio/$owner",
        type=Template,
        help=("path where the owner of the key will be able to write (and "
              "read) data. It defaults to ~/mercurio/<owner>. If the owner of "
              "the key is not provided on the command line, and cannot be "
              "guessed, the command will fail")
        )
    authorize_parser.add_argument(
        "-o", "--owner",
        default=None,
        help=("a string identifying the owner of the public key. If no value "
              "is provided on the command line, mercurio will try to guess a "
              "value by reading the comments in the key file")
        )

    # mercurio revoke
    revoke_parser = subparsers.add_parser(
        "revoke",
        description="Revoke a previously authorized identity"
        )
    revoke_parser.set_defaults(main=revoke)

    group = revoke_parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-k", "--key-file",
        dest="publickey",
        metavar="KEYFILE",
        type=PublicKeyFileType(),
        help="file containing the public key to revoke"
        )
    group.add_argument(
        "-o", "--owner",
        help="owner whose keys are to be revoked"
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
