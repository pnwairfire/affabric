"""affabric.tasks
"""

import os
import re

from fabric.api import task, roles as roles_decorator, env

from .output import error, debug_log

__author__      = "Joel Dubowy"

__all__ = [
    'update_roles',
    'make_task'
]

NOT_INTERPOLATED_MATCHER = re.compile('\%\((\w+)\)')

# TODO: rename 'roles' as 'role_hashes'
def get_env(roles, env_var_key):
    """Gets the environment (development, production, etc.) from the env var
    and whose key is defined by env_var_key and varifies that it's valid.
    """
    if env_var_key not in os.environ:
        error('Specify %s' % (env_var_key))
    if os.environ[env_var_key] not in list(roles.keys()):
        error("%s must be one of the following: '%s'" % (
            env_var_key, "', '".join(list(roles.keys()))))
    return os.environ[env_var_key]

# TODO: rename 'roles' as 'role_hashes'
DEFAULT_FABRIC_USER_KEY = 'FABRIC_USER'
def update_roles(roles, env_var_key):
    """Updates fabric's hash of roles

    Note: we're assuming one user per role - the same user across all of
    the machines playing that role. This could change. (e.g. The current
    code could be used to read different names for the different machines
    playing the role - by using different interpolation keys - but maybe
    there's an even better way to do it.
    """
    environment = get_env(roles, env_var_key)
    for role, role_array in list(roles[environment].items()):
        for i in range(len(role_array)):
            data = {}
            variables = NOT_INTERPOLATED_MATCHER.findall(role_array[i])
            for v in variables:
                k1 = "%s_ROLE_%s" % (role.upper(), v.upper())
                k2 = "%s_%s" % (role.upper(), v.upper())
                debug_log("setting %s/%s" % (k1, k2))
                if k1 in os.environ:
                    data[v] = os.environ[k1]
                elif k2 in os.environ:
                    data[v] = os.environ[k2]
                elif DEFAULT_FABRIC_USER_KEY in os.environ:
                    data[v] = os.environ[DEFAULT_FABRIC_USER_KEY]
            try:
                role_array[i] = role_array[i] % (data)
            except KeyError:
                # ignore for now, since this role may be unused by task being called
                pass
    debug_log(roles[environment])
    env.roledefs.update(roles[environment])

class make_task(object):
    """decorator to make a fabric task out of a function
    """

    # TODO: rename 'roles'/'self.roles' as 'roles_names'/'self.role_names'
    def __init__(self, *roles, **options):
        """Constructor

        Args:
         - roles -- roles that this task should be applied to
        """
        # Note: put off checking if roles is defined until ___call__, simply
        # to be able to mention task's name in the error messages
        if os.environ.get('ROLES'):
            self.roles = os.environ['ROLES'].split(',')
        else:
            self.roles = roles

        self.pre_task_execution = options.get('pre_task_execution')

    def check_roles(self):
        """Makes sure all roles needed by this task have user appropriately defined
        """
        for role in self.roles:
            for e in env.roledefs[role]:
                missing = NOT_INTERPOLATED_MATCHER.findall(e)
                if missing:
                    missing = ["%s_%s" % (role.upper(), v.upper()) for v in missing]
                    error("Specify %s" % (', '.join(missing)))

    def __call__(self, func):
        if not self.roles:
            error("Define a role for %s.%s" %(func.__module__, func.__name__))

        def decorated(*args, **kwargs):
            self.check_roles()
            if self.pre_task_execution:
                self.pre_task_execution(func, *args, **kwargs)
            func(*args, **kwargs)

        d = decorated
        d.__name__ = func.__name__
        d.__doc__ = func.__doc__
        d.__module__ = func.__module__

        return task(roles_decorator(self.roles)(d))
