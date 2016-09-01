"""affabric.output
"""

import os
import sys

from fabric.colors import red, green, yellow
from fabric.contrib.console import confirm as fab_confirm

__author__      = "Joel Dubowy"

__all__ = [
    'error',
    'debug_log'
]

def error(msg):
    print(red("*** ERROR:  %s" % (msg)))
    sys.exit(1)

def debug_log(msg):
    if 'DEBUG' in os.environ:
        print(green(msg))

def confirm(msg):
    """Displays message and then prompts user to continue.

    Exits unless user responds with '(y)es'.
    """
    #  See http://docs.fabfile.org/en/1.10/api/contrib/console.html
    print(msg)
    r = fab_confirm("Do you want to continue?", default=False)
    if not r:
        print("Exiting.")
        sys.exit(0)
