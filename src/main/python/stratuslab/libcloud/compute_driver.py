#
# Copyright (c) 2013, Centre National de la Recherche Scientifique (CNRS)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
Driver for StratusLab (http://stratuslab.eu) cloud infrastructures.

 The StratusLab Libcloud driver is a third-party driver that MUST
 be registered with the Libcloud software BEFORE being used.  To
 do this you need to execute the following statements before
 asking for an instance of the StratusLab Libcloud driver.

 from libcloud.compute.providers import set_driver
 set_driver('stratuslab',
            'stratuslab.libcloud.stratuslab_driver',
            'StratusLabNodeDriver')

"""

import xml.etree.ElementTree as ET
import ConfigParser as ConfigParser
import urllib
import uuid
import tempfile
import os

from stratuslab.Monitor import Monitor
from stratuslab.ConfigHolder import ConfigHolder, UserConfigurator
from stratuslab.PersistentDisk import PersistentDisk
import stratuslab.Util as StratusLabUtil
from libcloud.compute.base import NodeImage, NodeSize, Node
from libcloud.compute.base import NodeAuthSSHKey, NodeDriver
from libcloud.compute.base import NodeLocation, UuidMixin
from libcloud.compute.base import StorageVolume
from libcloud.compute.types import NodeState

from stratuslab.vm_manager.vm_manager import VmManager
from stratuslab.vm_manager.vm_manager_factory import VmManagerFactory


class StratusLabNodeSize(NodeSize):
    """
    Subclass of the standard NodeSize class that adds a CPU
    field, allowing the user to specify the number of CPUs
    required for a given configuration.

    """

    def __init__(self, size_id, name, ram, disk,
                 bandwidth, price, driver, cpu=1):
        super(StratusLabNodeSize, self).__init__(id=size_id,
                                                 name=name,
                                                 ram=ram,
                                                 disk=disk,
                                                 bandwidth=bandwidth,
                                                 price=price,
                                                 driver=driver)
        self.cpu = cpu


class StratusLabNode(Node, UuidMixin):
    """
    Subclass of the standard Node class that uses a function to
    lookup the state of the node.  Although a setter for the state
    is defined, the value is ignored.
    """

    def __init__(self, node_id, name, state, public_ips, private_ips,
                 driver, size=None, image=None, extra=None):

        super(StratusLabNode, self).__init__(node_id, name, state,
                                             public_ips, private_ips,
                                             driver, size, image, extra)

        try:
            self.location = extra['location']
        except (TypeError, KeyError):
            raise ValueError('extra[\'location\'] must be specified')

    @property
    def state(self):
        return self.get_node_state()

    @state.setter
    def state(self, value):
        self.cached_state = value

    @property
    def host(self):
        vm_info = self.get_vm_info()
        attrs = vm_info.getAttributes()

        try:
            host = attrs['history_records_history_hostname']
        except KeyError:
            host = None

        return host

    def get_vm_info(self):
        config_holder = \
            StratusLabNodeDriver.get_config_section(self.location,
                                                    self.driver.user_configurator)
        monitor = Monitor(config_holder)

        vm_infos = monitor.vmDetail([self.id])
        if len(vm_infos) == 0:
            raise ValueError('cannot recover state information for %s' % self.id)

        return vm_infos[0]

    def get_node_state(self):
        vm_info = self.get_vm_info()

        attrs = vm_info.getAttributes()

        try:
            state_summary = attrs['state_summary']
        except KeyError:
            state_summary = None

        return StratusLabNodeDriver._to_node_state(state_summary)


class StratusLabNodeDriver(NodeDriver):
    """StratusLab node driver."""

    RDF_RDF = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF'
    RDF_DESCRIPTION = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description'
    DC_IDENTIFIER = '{http://purl.org/dc/terms/}identifier'
    DC_TITLE = '{http://purl.org/dc/terms/}title'
    DC_DESCRIPTION = '{http://purl.org/dc/terms/}description'

    DEFAULT_MARKETPLACE_URL = 'https://marketplace.stratuslab.eu'

    user_configurator = None
    locations = None
    default_location = None
    sizes = None

    def __init__(self, key, secret=None, secure=False, host=None, port=None,
                 api_version=None, **kwargs):
        """
        Creates a new instance of a StratusLabNodeDriver from the
        given parameters.  All of the parameters are ignored except
        for the ones defined below.

        The configuration is read from the named configuration file
        (or file-like object).  The 'locations' in the API correspond
        to the named sections within the configuration file.

        :param key: ignored by this driver
        :param secret: ignored by this driver
        :param secure: passed to superclass; True required CA certs
        :param host: ignored by this driver (use locations instead)
        :param port: ignored by this driver (use locations instead)
        :param api_version: ignored by this driver
        :param kwargs: additional keyword arguments

        :keyword stratuslab_user_config (str or file): File name or
        file-like object from which to read the user's StratusLab
        configuration.  Sections in the configuration file correspond
        to 'locations' within this API.

        :keyword stratuslab_default_location (str): The id (name) of
        the section within the user configuration file to use as the
        default location.

        :returns: StratusLabNodeDriver

        """
        super(StratusLabNodeDriver, self).__init__(key,
                                                   secret=secret,
                                                   secure=secure,
                                                   host=host,
                                                   port=port,
                                                   api_version=api_version,
                                                   **kwargs)

        self.name = "StratusLab Node Provider"
        self.website = 'http://stratuslab.eu/'
        self.type = "stratuslab"

        # only ssh-based authentication is supported by StratusLab
        self.features['create_node'] = ['ssh_key']

        user_config_file = kwargs.get('stratuslab_user_config',
                                      StratusLabUtil.defaultConfigFileUser)
        default_section = kwargs.get('stratuslab_default_location', None)

        self.user_configurator = UserConfigurator(configFile=user_config_file)

        self.default_location, self.locations = \
            self._get_config_locations(default_section)

        self.sizes = self._get_config_sizes()

    # noinspection PyUnusedLocal
    def get_uuid(self, unique_field=None):
        """
        :param  unique_field (bool): Unique field
        :returns: UUID

        """
        return str(uuid.uuid4())

    @staticmethod
    def get_config_section(location, user_configurator, options=None):

        if location is not None:
            selected_section = location.id
        else:
            selected_section = None

        config = UserConfigurator.userConfiguratorToDictWithFormattedKeys(user_configurator,
                                                                          selected_section=selected_section)

        options = options or {}
        options['verboseLevel'] = -1
        options['verbose_level'] = -1

        config_holder = ConfigHolder(options=(options or {}), config=config)
        config_holder.pdiskProtocol = 'https'

        return config_holder

    def _get_config_section(self, location, options=None):
        location = location or self.default_location
        return StratusLabNodeDriver.get_config_section(location,
                                                       self.user_configurator,
                                                       options)

    def _get_config_locations(self, default_section=None):
        """
        Returns the default location and a dictionary of locations.

        Locations are defined as sections in the client configuration
        file.  The sections may contain 'name' and 'country' keys.  If
        'name' is not present, then the id is also used for the name.
        If 'country' is not present, then 'unknown' is the default
        value.

        The default location in order of preference is: named section
        in parameter, selected_section in configuration, and finally
        'default'.  The 'default' key will remain the returned
        dictionary only if it is the chosen default location.

        """

        # TODO: Decide to make parser public or provide method for this info.
        parser = self.user_configurator._parser

        # determine the default location (section) to use
        # preference: parameter, selected section in config., [default] section
        if not default_section:
            try:
                default_section = parser.get('default', 'selected_section')
            except ConfigParser.NoOptionError:
                default_section = 'default'
            except ConfigParser.NoSectionError:
                raise Exception('configuration file must have [default] section')

        locations = {}

        for section in parser.sections():
            if not (section in ['instance_types']):
                location_id = section

                try:
                    name = parser.get(section, 'name')
                except ConfigParser.NoOptionError:
                    name = location_id

                try:
                    country = parser.get(section, 'country')
                except ConfigParser.NoOptionError:
                    country = 'unknown'

                locations[location_id] = NodeLocation(id=section,
                                                      name=name,
                                                      country=country,
                                                      driver=self)

        try:
            default_location = locations[default_section]
        except KeyError:
            raise Exception('requested default location (%s) not defined' %
                            default_section)

        if default_section != 'default':
            del (locations['default'])

        return default_location, locations

    def _get_config_sizes(self):
        """
        Create all of the node sizes based on the user configuration.

        """

        size_map = {}

        machine_types = VmManager.getDefaultInstanceTypes()
        for name in machine_types.keys():
            size = self._create_node_size(name, machine_types[name])
            size_map[name] = size

        machine_types = self.user_configurator.getUserDefinedInstanceTypes()
        for name in machine_types.keys():
            size = self._create_node_size(name, machine_types[name])
            size_map[name] = size

        return size_map.values()

    def _create_node_size(self, name, resources):
        cpu, ram, swap = resources
        bandwidth = 1000
        price = 1
        return StratusLabNodeSize(size_id=name,
                                  name=name,
                                  ram=ram,
                                  disk=swap,
                                  bandwidth=bandwidth,
                                  price=price,
                                  driver=self,
                                  cpu=cpu)

    def list_nodes(self):
        """
        List the nodes (machine instances) that are active in all
        locations.

        """

        nodes = []
        for location in self.locations.values():
            nodes.extend(self.list_nodes_in_location(location))
        return nodes

    def list_nodes_in_location(self, location):
        """
        List the nodes (machine instances) that are active in the
        given location.

        """

        config_holder = self._get_config_section(location)

        monitor = Monitor(config_holder)
        vms = monitor.listVms()

        nodes = []
        for vm_info in vms:
            nodes.append(self._vm_info_to_node(vm_info, location))

        return nodes

    def _vm_info_to_node(self, vm_info, location):
        attrs = vm_info.getAttributes()
        node_id = attrs['id'] or None
        name = attrs['name'] or None
        state = StratusLabNodeDriver._to_node_state(attrs['state_summary'] or None)

        public_ip = attrs['template_nic_ip']
        if public_ip:
            public_ips = [public_ip]
        else:
            public_ips = []

        size_name = '%s_size' % node_id

        cpu = attrs['template_cpu']
        ram = attrs['template_memory']
        swap = attrs['template_disk_size']

        size = self._create_node_size(size_name, (cpu, ram, swap))

        mp_url = attrs['template_disk_source']
        mp_id = mp_url.split('/')[-1]
        image = NodeImage(mp_id, mp_id, self)

        return StratusLabNode(node_id,
                              name,
                              state,
                              public_ips,
                              None,
                              self,
                              size=size,
                              image=image,
                              extra={'location': location})

    @staticmethod
    def _to_node_state(state):
        if state:
            state = state.lower()
            if state in ['running', 'epilog']:
                return NodeState.RUNNING
            elif state in ['pending', 'prolog', 'boot']:
                return NodeState.PENDING
            elif state in ['done']:
                return NodeState.TERMINATED
            else:
                return NodeState.UNKNOWN
        else:
            return NodeState.UNKNOWN

    def create_node(self, **kwargs):
        """
        @keyword    name:   String with a name for this new node (required)
        @type       name:   C{str}

        @keyword    size:   The size of resources allocated to this node.
                            (required)
        @type       size:   L{NodeSize}

        @keyword    image:  OS Image to boot on node. (required)
        @type       image:  L{NodeImage}

        @keyword    location: Which data center to create a node in. If empty,
                              undefined behavoir will be selected. (optional)
        @type       location: L{NodeLocation}

        @keyword    auth:   Initial authentication information for the node
                            (optional)
        @type       auth:   L{NodeAuthSSHKey} or L{NodeAuthPassword}

        @return: The newly created node.
        @rtype: L{Node}

        @inherits: L{NodeDriver.create_node}

        """

        name = kwargs.get('name')
        size = kwargs.get('size')
        image = kwargs.get('image')
        location = kwargs.get('location', self.default_location)
        auth = kwargs.get('auth', None)

        runner = self._create_runner(name, size, image,
                                     location=location, auth=auth)

        ids = runner.runInstance()
        node_id = ids[0]

        extra = {'location': location}

        node = StratusLabNode(node_id=node_id,
                              name=name,
                              state=NodeState.PENDING,
                              public_ips=[],
                              private_ips=[],
                              driver=self,
                              size=size,
                              image=image,
                              extra=extra)

        try:
            _, ip = runner.getNetworkDetail(node_id)
            node.public_ips = [ip]

        except Exception as e:
            print e

        return node

    def _create_runner(self, name, size, image, location=None, auth=None):

        location = location or self.default_location

        holder = self._get_config_section(location)

        self._insert_required_run_option_defaults(holder)

        holder.set('vmName', name)

        pubkey_file = None
        if isinstance(auth, NodeAuthSSHKey):
            _, pubkey_file = tempfile.mkstemp(suffix='_pub.key', prefix='ssh_')
            with open(pubkey_file, 'w') as f:
                f.write(auth.pubkey)

            holder.set('userPublicKeyFile', pubkey_file)

        # The cpu attribute is only included in the StratusLab
        # subclass of NodeSize.  Recover if the user passed in a
        # normal NodeSize; default to 1 CPU in this case.
        try:
            cpu = size.cpu
        except AttributeError:
            cpu = 1

        holder.set('vmCpu', cpu)
        holder.set('vmRam', size.ram)
        holder.set('vmSwap', size.disk)

        runner = VmManagerFactory.create(image.id, holder)

        if pubkey_file:
            os.remove(pubkey_file)

        return runner

    def _insert_required_run_option_defaults(self, holder):
        defaults = VmManager.defaultRunOptions()

        defaults['verboseLevel'] = -1
        required_options = ['verboseLevel', 'vmTemplateFile',
                            'marketplaceEndpoint', 'vmRequirements',
                            'outVmIdsFile', 'inVmIdsFile', 'vncPort']

        for option in required_options:
            if not holder.config.get(option):
                holder.config[option] = defaults[option]

    def destroy_node(self, node):
        """
        Terminate the node and remove it from the node list.  This is
        the equivalent of stratus-kill-instance.

        """

        runner = self._create_runner(node.name, node.size, node.image,
                                     location=node.location)
        runner.killInstances([node.id])

        node.state = NodeState.TERMINATED

        return True

    def list_images(self, location=None):
        """
        Returns a list of images from the StratusLab Marketplace.  The
        image id corresponds to the base64 identifier of the image in
        the Marketplace and the name corresponds to the title (or
        description if title isn't present).

        The location parameter is ignored at the moment and the global
        Marketplace (https://marketplace.stratuslab.eu/metadata) is
        consulted.

        @inherits: L{NodeDriver.list_images}
        """

        location = location or self.default_location

        holder = self._get_config_section(location)
        url = holder.config.get('marketplaceEndpoint',
                                self.DEFAULT_MARKETPLACE_URL)
        endpoint = '%s/metadata' % url
        return self._get_marketplace_images(endpoint)

    def _get_marketplace_images(self, url):
        images = []
        try:
            filename, _ = urllib.urlretrieve(url)
            tree = ET.parse(filename)
            root = tree.getroot()
            for md in root.findall(self.RDF_RDF):
                rdf_desc = md.find(self.RDF_DESCRIPTION)
                image_id = rdf_desc.find(self.DC_IDENTIFIER).text
                elem = rdf_desc.find(self.DC_TITLE)
                if elem is None or len(elem) == 0:
                    elem = rdf_desc.find(self.DC_DESCRIPTION)

                if elem is not None and elem.text is not None:
                    name = elem.text.lstrip()[:30]
                else:
                    name = ''
                images.append(NodeImage(id=image_id, name=name, driver=self))
        except Exception as e:
            # TODO: log errors instead of ignoring them
            print e

        return images

    def list_sizes(self, location=None):
        """
        StratusLab node sizes are defined by the client and do not
        depend on the location.  Consequently, the location parameter
        is ignored.  Node sizes defined in the configuration file
        (in the 'instance_types' section) augment or replace the
        standard node sizes defined by default.

        @inherits: L{NodeDriver.list_images}
        """
        return self.sizes

    def list_locations(self):
        """
        Returns a list of StratusLab locations.  These are defined as
        sections in the client configuration file.  The sections may
        contain 'name' and 'country' keys.  If 'name' is not present,
        then the id is also used for the name.  If 'country' is not
        present, then 'unknown' is the default value.

        The returned list and contained NodeLocations are not
        intended to be modified by the user.

        @inherits: L{NodeDriver.list_locations}
        """
        return self.locations.values()

    def list_volumes(self, location=None):
        """
        Creates a list of all of the volumes in the given location.
        This will include private disks of the user as well as public
        disks from other users.

        This method is not a standard part of the Libcloud node driver
        interface.
        """

        config_holder = self._get_config_section(location)

        pdisk = PersistentDisk(config_holder)

        filters = {}
        volumes = pdisk.describeVolumes(filters)

        storage_volumes = []
        for info in volumes:
            storage_volumes.append(self._create_storage_volume(info, location))

        return storage_volumes

    def _create_storage_volume(self, info, location):
        disk_uuid = info['uuid']
        name = info['tag']
        size = long(info['size'])
        extra = {'location': location}
        return StorageVolume(disk_uuid, name, size, self, extra=extra)

    def create_volume(self, size, name, location=None, snapshot=None):
        """
        Creates a new storage volume with the given size.  The 'name'
        corresponds to the volume tag.  The visibility of the created
        volume is 'private'.

        The snapshot parameter is currently ignored.

        The created StorageVolume contains a dict for the extra
        information with a 'location' key storing the location used
        for the volume.  This is set to 'default' if no location has
        been given.

        @inherits: L{NodeDriver.create_volume}
        """
        config_holder = self._get_config_section(location)

        pdisk = PersistentDisk(config_holder)

        # Creates a private disk.  Boolean flag = False means private.
        vol_uuid = pdisk.createVolume(size, name, False)

        extra = {'location': location}

        return StorageVolume(vol_uuid, name, long(size), self, extra=extra)

    def destroy_volume(self, volume):
        """
        Destroys the given volume.

        @inherits: L{NodeDriver.destroy_volume}
        """

        location = self._volume_location(volume)

        config_holder = self._get_config_section(location)
        pdisk = PersistentDisk(config_holder)

        pdisk.deleteVolume(volume.id)

        return True

    def attach_volume(self, node, volume, device=None):
        location = self._volume_location(volume)

        config_holder = self._get_config_section(location)
        pdisk = PersistentDisk(config_holder)

        try:
            host = node.host
        except AttributeError:
            raise Exception('node does not contain host information')

        pdisk.hotAttach(host, node.id, volume.id)

        try:
            volume.extra['node'] = node
        except AttributeError:
            volume.extra = {'node': node}

        return True

    def detach_volume(self, volume):

        location = self._volume_location(volume)

        config_holder = self._get_config_section(location)
        pdisk = PersistentDisk(config_holder)

        try:
            node = volume.extra['node']
        except (AttributeError, KeyError):
            raise Exception('volume is not attached to a node')

        pdisk.hotDetach(node.id, volume.id)

        del (volume.extra['node'])

        return True

    def _volume_location(self, volume):
        """
        Recovers the location information from the volume.  If
        the information is not available, then the default
        location for this driver is used.

        """

        try:
            return volume.extra['location']
        except KeyError:
            return self.default_location


pass

if __name__ == "__main__":
    import doctest

    doctest.testmod()
