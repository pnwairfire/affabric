"""affabric.utils
"""

import os
import re
import uuid

from fabric import api
from fabric.contrib import files

from .input import env_var_or_prompt_for_input

__author__      = "Joel Dubowy"

__all__ = [
    'kill_processes',
    'run_in_background',
    'already_running',
    'create_ssh_tunnel',
    'destroy_ssh_tunnel',
    'install_pyenv',
    'add_pyenv_to_dot_file',
    'install_pyenv_environment',
    'uninstall_pyenv_environment'
]


##
##  Managing (Running & Killing) Processes
##

def kill_processes(pattern):
    with api.settings(warn_only=True):
        api.sudo("pkill -f '%s'" % (pattern))
    #api.sudo("! pgrep -f '%s' || pkill -f '%s'" % (pattern, pattern))

def run_in_background(command, role, kill_first=False, sudo_as=None, **env_vars):
    """
    From: http://stackoverflow.com/questions/8775598/start-a-background-process-with-nohup-using-fabric
    """
    if kill_first:
        kill_processes(command)

    sudo_as_key = "%s_SUDO_AS" % (role.upper())
    sudo_as = os.environ.get(sudo_as_key) or sudo_as

    env_vars_str = " ".join(["{}={}".format(k,v) for k,v in env_vars.items()])

    command = '{} nohup {} &> /dev/null &'.format(env_vars_str, command)
    api.sudo(command, pty=False, user=sudo_as)

def already_running(command):
    command = command.strip('&').strip(' ')
    if api.env.warn_only:
        return api.run("pgrep -f '%s'" % (command)) != ''
    else:
        try:
            api.run("pgrep -f '%s'" % (command))
        except SystemExit as e:
            return False
        return True

def wrapped_run(command, skip_if_already_running=False,
        silence_system_exit=False, use_sudo=False):
    """Runs the command if there isn't already a live processes started with
    that command.

    Args:
     - command -- command to be run on remote server
    Kwargs:
     - skip_if_already_running (default: False) -- if True, checks if command
        is running, andd skips if so
     - silence_system_exit (default: False) -- catches and ignores SystemExit
        (which indicates command failed on remote server)
    """
    if not skip_if_already_running or not already_running(command):
        try:
            if use_sudo:
                api.sudo(command)
            else:
                api.run(command)
        except SystemExit as e:
            if not silence_system_exit:
                raise


##
##  ssh tunneling
##

LOOPBACK_ADDRESSES_RE = re.compile('^(localhost|172.0.0.[1-8]|::1)$')

def _ssh_tunnel_command(local_port, remote_port, remote_host, remote_user,
        local_host, ssh_port):
    # Notes are args:
    #  '-f' -> forks process
    #  '-N' -> no command to be run on server
    return "ssh -f -N -p %s %s@%s -L %s/%s/%s -oStrictHostKeyChecking=no" % (
        ssh_port, remote_user, remote_host, local_port, local_host, remote_port
    )

def create_ssh_tunnel(local_port, remote_port, remote_host, remote_user,
        local_host='localhost', ssh_port=22):
    """Creates an ssh tunnel

    It only does so if:
     a) the smtp host is not the same as the current host (api.env.host)
     b) the smtp host is not localhost
     c) it's not already created

    Args:
     - local_port
     - remote_port
     - remote_host
     - remote_user
    Kwargs:
     - local_host (default: 'localhost')
     - ssh_port

    TODO: consider user as well in case b), above
    """
    if api.env.host != remote_host and not LOOPBACK_ADDRESSES_RE.match(remote_host):
        command = _ssh_tunnel_command(local_port, remote_port, remote_host,
            remote_user, local_host, ssh_port)
        wrapped_run(command, skip_if_already_running=True, use_sudo=True)

def destroy_ssh_tunnel(local_port, remote_port, remote_host, remote_user,
        local_host='localhost', ssh_port=22):
    """Destroys an ssh tunnel, if it exists

    Args:
     - local_port
     - remote_port
     - remote_host
     - remote_user
    Kwargs:
     - local_host (default: 'localhost')
     - ssh_port
    """
    command =  _ssh_tunnel_command(local_port, remote_port, remote_host,
        remote_user, local_host, ssh_port)
    if already_running(command):
        api.sudo("pkill -f '%s'" % (command))


##
##  pyenv
##

PYENV_ROOT = "/usr/local/lib/.pyenv"
PYENV_TMPDIR="{}/tmp/".format(PYENV_ROOT)

def install_pyenv():

    if not files.exists(PYENV_ROOT):
        api.sudo("git clone https://github.com/yyuu/pyenv.git {}".format(PYENV_ROOT))
        api.sudo("git clone https://github.com/yyuu/pyenv-virtualenv.git "
            "{}/plugins/pyenv-virtualenv".format(PYENV_ROOT))
        api.sudo("git clone https://github.com/yyuu/pyenv-pip-rehash.git "
            "{}/plugins/pyenv-pip-rehash".format(PYENV_ROOT))

def add_pyenv_to_dot_file(home_dir="~", dot_file=".bash_profile", user=None):
    dot_file = os.path.join(home_dir, dot_file)
    dot_file_exists = files.exists(dot_file)

    with api.settings(warn_only=True):
        to_add_to_dot_file = []

        if (not dot_file_exists or
                not api.sudo("grep 'export PYENV_ROOT' {}".format(dot_file))):
            to_add_to_dot_file.append('export PYENV_ROOT="{}"'.format(PYENV_ROOT))

        if (not dot_file_exists or
                not api.sudo("grep 'export PATH=\"$PYENV_ROOT/bin' {}".format(dot_file))):
            to_add_to_dot_file.append('export PATH="$PYENV_ROOT/bin:$PATH"')

        if (not dot_file_exists or
                not api.sudo("grep 'pyenv init -' {}".format(dot_file))):
            to_add_to_dot_file.append('eval "$(pyenv init -)"')

        if (not dot_file_exists or
                not api.sudo("grep 'pyenv virtualenv-init -' {}".format(dot_file))):
            to_add_to_dot_file.append('eval "$(pyenv virtualenv-init -)"')

        if to_add_to_dot_file:
            api.sudo("printf '\n{}\n' >> {}".format(
                '\n'.join(to_add_to_dot_file), dot_file))
            if user:
                api.sudo("chown {user}:{user} {dot_file}".format(user=user, dot_file=dot_file))

def install_pyenv_environment(version, virtualenv_name, replace_existing=False):
    """Installs virtual environment, first installing python version if necessary.

    Args:
     - version -- python version (ex. '2.7.8')
     - virtualenv_name -- name of pyenv version (ex. 'my-app-2.7.8')
    Kwargs:
     - replace_existing -- whether or not to uninstall and then reinstall
       virtual environment if it alredy exists -- ** NOT YET IMPLEMENTED **
    """
    with api.settings(warn_only=True):
        version_exists = not not api.sudo('pyenv versions | grep "^[ ]*{}$"'.format(version))
    if not version_exists:
        with api.settings(warn_only=True):
            api.sudo('apt-get install ca-certificates')
        # install in ~/pyenv-tmp instead of in /tmp in case /tmp is restricted
        if not files.exists(PYENV_TMPDIR):
            api.sudo("mkdir {}".format(PYENV_TMPDIR))
            api.sudo("chmod 777 {}".format(PYENV_TMPDIR))
        api.sudo("TMPDIR={} pyenv install -s {}".format(PYENV_TMPDIR, version))

    with api.settings(warn_only=True):
        virtual_env_exists = not not api.sudo('pyenv versions | grep "^[ ]*{}$"'.format(virtualenv_name))
    if not virtual_env_exists or replace_existing:
        if virtual_env_exists and replace_existing:
            raise NotImplementedError("The 'replace_existing' option is not yet implemented")

        # If virtualenv_name is already installed, you get a prompt; if you
        # respond with 'N' to not install if already installed, the command returns
        # and error code.  So, use warn_only=True
        # Also use warn_only for upgrading pip, since it's not essential and
        # sometimes fails
        with api.settings(warn_only=True):
            api.sudo("pyenv virtualenv {} {}".format(version, virtualenv_name))
            api.sudo("PYENV_VERSION={} pip install --upgrade pip".format(virtualenv_name))


def uninstall_pyenv_environment(virtualenv_name):
    with api.settings(warn_only=True):
        api.sudo("pyenv deactivate {}".format(virtualenv_name))
        api.sudo("pyenv uninstall -f {}".format(virtualenv_name))

##
## Code
##

class prepare_code:
    """Context manager that clones repo on enter and deletes it on exit.
    """

    def __init__(self, git_repo_url, skip_cleanup=False):
        self.git_repo_url = git_repo_url
        self.skip_cleanup = skip_cleanup

    def __enter__(self):
        self.repo_path_name = self.get_code()
        return self.repo_path_name

    def __exit__(self, type, value, traceback):
        self.clean_up()

        # TODO: suppress exception (or just certain exceptions) by returning
        #  True no matter what (first outputting an error message) *or* by
        #  calling error function.  (type, value, and traceback are undefined
        #  unless there was an exception.)

    def get_code(self):
        code_version = env_var_or_prompt_for_input('CODE_VERSION',
            'Git tag, branch, or commit to deploy', 'master')
        repo_dir_name = uuid.uuid1()

        with api.cd('/tmp/'):
            if files.exists(repo_dir_name): # this shouldn't happen
                sudo('rm -rf %s*' % (repo_dir_name))
            api.run('git clone %s %s' % (self.git_repo_url, repo_dir_name))

        self.repo_path_name = '/tmp/{}'.format(repo_dir_name)
        with api.cd(self.repo_path_name):
            api.run('git checkout %s' % (code_version))
            api.run('rm -f .python-version')
        return self.repo_path_name

    def clean_up(self):
        """Removes repo
        """
        if not self.skip_cleanup:
            with api.settings(warn_only=True):
                r = api.sudo('rm -rf %s*' % (self.repo_path_name))
