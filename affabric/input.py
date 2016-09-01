"""affabric.input
"""

import os
import sys

__author__      = "Joel Dubowy"

def env_var_or_prompt_for_input(env_var_name, msg, default=None, options=None):
    if not os.environ.get(env_var_name):
        v = None
        while not v:
            if options:
                sys.stdout.write('{}:\n'.format(msg, default))
                for i, e in enumerate(options):
                    sys.stdout.write(' ({}) {}\n'.format(i, e))
                sys.stdout.write(' ({}) {}\n'.format(i+1, '(enter your own)'))
                sys.stdout.write('Your choice:')
                try:
                    a = int(input().strip())
                    if a == i + 1:
                        sys.stdout.write('Enter your own: '.format(msg, default))
                        v = input().strip()
                    else:
                        # if a is outside of valid range, exception will be
                        # raised, and the user will be reprompted
                        v = options[a]
                except:
                    sys.stdout.write("Invalid choice")

            else:
                sys.stdout.write('{} [{}]: '.format(msg, default))
                v = input().strip() or default
        return v
    else:
        return os.environ.get(env_var_name)
