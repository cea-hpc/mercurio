# This file is part of the RobinHood Library
# Copyright (C) 2019 Commissariat a l'energie atomique et aux energies
# 		      alternatives
#
# SPDX-License-Identifer: LGPL-3.0-or-later
#
# author: Quentin Bouget <quentin.bouget@cea.fr>

"""
mercurio's setup module
"""

from setuptools import setup, find_packages

import mercurio

setup(
    name='mercurio',
    version=mercurio.__version__,

    # TODO: update description
    description='A file transfer tool',

    # The project's main homepage
    url='https://github.com/cea-hpc/mercurio',

    # Author details
    author='Quentin Bouget',
    author_email='quentin.bouget@cea.fr',

    license='LGPLv3',

    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.4',
        ],

    keywords='file-transfer',

    packages=find_packages(exclude=['tests']),

    install_requires=['parablox'],

    python_requires='~=3.4',

    entry_points={
        'console_scripts': [
            'mercurio=mercurio.cli:main',
            ],
        },
)
