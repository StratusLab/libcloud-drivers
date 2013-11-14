import os.path

from libcloud.compute.base import NodeAuthSSHKey
from libcloud.compute.providers import get_driver

import demo_utils as utils

from libcloud.compute.providers import set_driver

import stratuslab.libcloud.compute_driver

set_driver('stratuslab',
           'stratuslab.libcloud.compute_driver',
           'StratusLabNodeDriver')

# Obtain instance of StratusLab driver.
StratusLabDriver = get_driver('stratuslab')
driver = StratusLabDriver('unused-key')

print 'Driver: ', driver

# List sizes, locations, and images.
print

sizes = driver.list_sizes()
utils.print_objs(sizes)

locations = driver.list_locations()
utils.print_objs(locations)

images = driver.list_images()
utils.print_objs(images[-5:])

print

# Large, node machine to run at GRNET.
size = utils.select_id('m1.large', sizes)
location = utils.select_id('grnet', locations)
image = utils.select_id('BN1EEkPiBx87_uLj2-sdybSI-Xb', images)

# Get ssh key.
home = os.path.expanduser('~')
ssh_public_key_path = os.path.join(home, '.ssh', 'id_dsa.pub')
ssh_private_key_path = ssh_public_key_path.rstrip('.pub')

with open(ssh_public_key_path) as f:
    pubkey = NodeAuthSSHKey(f.read())

# Running nodes...
utils.print_objs(driver.list_nodes())
print

# Start the node and run script.
node = driver.create_node(name='my-libcloud-node',
                          size=size,
                          location=location,
                          image=image,
                          auth=pubkey)

driver.wait_until_running([node])

print node
print node.state

utils.print_objs(driver.list_nodes())

# Kill the node.
node.destroy()

utils.print_objs(driver.list_nodes())
