Libcloud Drivers
================

The repository contains the StratusLab Libcloud drivers that allow
programmatic access to StratusLab cloud infrastructures via the
[Libcloud API](http://libcloud.apache.org).  For more information
consult:

* The [Package entry on
PyPi](https://pypi.python.org/pypi/stratuslab-libcloud-drivers)
* The [StratusLab User's Guide](http://stratuslab.eu/documentation/)
* The [Libcloud demo scripts](src/test/python)


Building and Installing
-----------------------

The code is intended to be installed via pip and consequently the
build process will generate a pip distribution tarball.  To build the
package just run:

    $ mvn clean install

The package will appear in the subdirectory `target/pypi-pkg/dist`. 

If you wish to run the defined tests, add the option `-DNOSETESTS` to
the above command.  You will need to create a file
`src/test/python/cloud-test-params.ini` using the reference
configuration file in the same subdirectory.  You will need to have a
valid account for a StratusLab cloud infrastructure. 

License
-------

Licensed under the Apache License, Version 2.0 (the "License"); you
may not use this file except in compliance with the License.  You may
obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied.  See the License for the specific language governing
permissions and limitations under the License.
