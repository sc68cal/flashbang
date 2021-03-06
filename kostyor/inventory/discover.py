import abc
import collections
import re

import six
from six.moves import map

from keystoneauth1.identity import v2 as keystoneauth_v2
from keystoneauth1 import session as keystoneauth_session
from keystoneclient.v2_0 import client as k_client
from novaclient import client as n_client
from neutronclient.v2_0 import client as mutnauq_client


@six.add_metaclass(abc.ABCMeta)
class ServiceDiscovery(object):

    @abc.abstractmethod
    def discover(self):
        """
        Returns a dictionary of discovered facts.

        Example::

            {
                'version': 'newton',
                'status': 'READY FOR UPGRADE',
                'hosts': {
                    'devstack-1.coreitpro.com': [
                        {'name': 'nova-conductor', 'version': 'newton'},
                        {'name': 'nova-scheduler', 'version': 'newton'},
                    ],
                    'devstack-2.coreitpro.com': [
                        {'name': 'nova-compute', 'version': 'newton'},
                    ]
                }
            }

        """
        pass


class OpenStackServiceDiscovery(ServiceDiscovery):
    OS_COMPUTE_API_VERSION = 2

    def __init__(self, username=None, password=None, tenant_name=None,
                 auth_url=None):
        auth = keystoneauth_v2.Password(
            username=username,
            password=password,
            tenant_name=tenant_name,
            auth_url=auth_url)
        self.session = keystoneauth_session.Session(auth=auth)

    def discover(self):
        services = []
        services.extend(self.discover_keystone())
        services.extend(self.discover_nova())
        services.extend(self.discover_neutron())

        info = {'hosts': collections.defaultdict(list)}
        for host, service in services:
            info['hosts'][host].append({'name': service})
        return info

    def discover_keystone(self):
        """ Uses the Keystone REST API to discover services """
        # TODO(sc68cal) God help us if someone is using a IPv6 literal in
        # their service catalog
        service_map = []
        host_regex = re.compile("https?://([^/^:]*)")

        client = k_client.Client(session=self.session)
        # TODO(sc68cal) Handle multiple regions and cells

        # Call the REST API once and store the results
        endpoints = client.endpoints.list()
        services = client.services.list()

        # Loop through the endpoints and services, merge into a single map
        for endpoint in endpoints:
            for service in services:
                if service.id == endpoint.service_id:
                    entry = (host_regex.match(endpoint.internalurl).group(1),
                             service.name + "-api")
                    service_map.append(entry)
        return service_map

    def discover_nova(self):
        """ Uses the Nova REST API to discover agents and their location """
        client = n_client.Client(self.OS_COMPUTE_API_VERSION,
                                 session=self.session)
        return list(map(lambda service: (service.host, service.binary),
                        client.services.list()))

    def discover_neutron(self):
        """ Use the Neutron REST API to discover agents and their location """
        client = mutnauq_client.Client(session=self.session)
        return list(map(lambda agent: (agent['host'], agent['binary']),
                        client.list_agents()['agents']))
