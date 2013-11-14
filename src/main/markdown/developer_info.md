Developer Info for StratusLab Libcloud Drivers
==============================================

[Libcloud][lc-web] provides abstractions for cloud servers, cloud
storage, load balancers, and DNS.  The Libcloud abstraction for cloud
servers is similar to that for StratusLab, so it should be fairly
straightforward to provide a plugin for this.

The storage abstraction for Libcloud is "file-based".  This doesn't
match very well with the "disk-based" storage that StratusLab provides
and that is included in the "compute" part of the Libcloud API.  A
mapping between the "file-based" storage API and StratusLab volumes
could be done, but a serious evaluation needs to be done first to see
if this is useful.

StratusLab does not provide load balancers or DNS services, so neither
of those abstractions make sense for a StratusLab plugin.

Mapping Cloud Server Semantics
==============================

The Libcloud cloud server interface (protocol) is object based with
`Node` being the primary object.  (See the `libcloud/compute/base.py`
class in the [codebase][lc-github].)  The node consists of:

* ID
* Name
* State
* Public IPs
* Private IPs
* Libcloud driver
* Size
* Image
* Extra driver-specific information

This matches very well the characteristics of an instance with
StratusLab.  The driver (plugin) is used to create a machine instance
and then it is controlled directly the Node instance.  Aside from
getter functions, the interface has `reboot` and `destroy` methods.
StratusLab (at least at the moment) won't be able to support the
`reboot` method.

The `NodeSize` is just a tuple containing the id, name, RAM, disk,
bandwidth, and price.  StratusLab can map the StratusLab type names to
the id and name.  RAM to RAM and disk to swap space.  We don't
currently have bandwidth and price, but perhaps we should consider
adding these even if they are unused.

The `NodeImage` is a machine image and contains only an id and a name.
These can be taken from the Marketplace with the id mapped to the
usual StratusLab image identifier.  The name can be the title, if
provided, or the image description.

There is a concept of a `NodeLocation` in the API.  This corresponds to,
for example, the different geographic regions of Amazon.  This can
easily correspond to the various cloud infrastructure sections that we
allow in our standard configuration file.  This provides a name to
indicate the various endpoints, credentials, etc. tied to a given
cloud resource.

There is also a `StorageVolume` in the API to describe volumes that can
be attached to a Node.  This corresponds well to the StratusLab
storage abstraction.  There are also methods in the abstraction for
attaching and detaching a volume from a machine.


Open Questions
==============

* What is the policy with external dependencies?
* Why is there no list_volumes() method in NodeDriver?
* Why is there no CPU (and/or core) fields in NodeSize?
* Why is there no function to get the state of a node (list_nodes()
  seems to be used for this)?
* Why does list_nodes() not take a location?  Always getting all nodes
  at all locations seems wasteful in terms of bandwidth and time.
* Had problems with RSA SSH keys.  Are only DSA keys accepted?


[lc-web]: http://libcloud.apache.org
[lc-github]: https://github.com/apache/libcloud
