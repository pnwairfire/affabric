__author__      = "Joel Dubowy"

import datetime
from fabric import api

from pyairfire.fabric import utils

class TestCreateSSHTunnel(object):

    def monkey_patch_run(self, monkeypatch):
        def _run(command, **kwargs):
            self.calls.append(command)
        monkeypatch.setattr(utils, 'wrapped_run', _run)
        monkeypatch.setattr(api.env, 'host', "foo.bar")

    def setup(self):
        self.calls = []

    def test_tunnel_to_localhost(self, monkeypatch):
        self.monkey_patch_run(monkeypatch)
        utils.create_ssh_tunnel(123, 321, "localhost", "foouser")
        utils.create_ssh_tunnel(123, 321, "172.0.0.1", "foouser")
        utils.create_ssh_tunnel(123, 321, "172.0.0.3", "foouser")
        utils.create_ssh_tunnel(123, 321, "172.0.0.8", "foouser")
        utils.create_ssh_tunnel(123, 321, "::1", "foouser")
        assert len(self.calls) == 0

    def test_tunnel_to_same_host(self, monkeypatch):
        self.monkey_patch_run(monkeypatch)
        utils.create_ssh_tunnel(123, 321, "foo.bar", "foouser")
        assert len(self.calls) == 0

    def test_tunnel_to_remote_host(self, monkeypatch):
        self.monkey_patch_run(monkeypatch)
        utils.create_ssh_tunnel(123, 321, "bar.com", "foouser")
        assert len(self.calls) == 1
        assert self.calls[0] == "ssh -f -N -p 22 foouser@bar.com -L 123/localhost/321 -oStrictHostKeyChecking=no"

        # trying to create same tunnel; wrapped_run will be
        # called, but it should handle not trying to recreate the tunnel
        utils.create_ssh_tunnel(123, 321, "bar.com", "foouser")
        assert len(self.calls) == 2
        assert self.calls[1] == "ssh -f -N -p 22 foouser@bar.com -L 123/localhost/321 -oStrictHostKeyChecking=no"

        # trying to create a different tunnel
        utils.create_ssh_tunnel(123, 321, "bar.com", "foouser",
            local_host="127.0.0.1", ssh_port=272)
        assert len(self.calls) == 3
        assert self.calls[2] == "ssh -f -N -p 272 foouser@bar.com -L 123/127.0.0.1/321 -oStrictHostKeyChecking=no"
