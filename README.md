all7fever
=========

takes a VDI and outputs a diskless/netboot image, hacked up initrd, and a gpxe config (all rudimentary to start)

dependencies
------------
for build-gpxe-iso:
* python2.7
* build utilities like make, ar, gcc
* mkisolinux

for doit.py:
* python2.7
* vdifuse
* distutils
* fstab.py (included)
* cpio 
* pigz (you can change this to gzip in the code)
* pv if you want a progress bar

instructions
------------
* clone the git repository
    git clone git://github.com/xandercrews/all7fever.git

* initialize and update submodules (for gpxe fork)
    git submodule init
    git submodule update

### create a base image ###

you can use virtualbox, or KVM with a VDI-backed disk.  just make sure not to use LVM, or encryption or anything, since the stateless converter doesn't support it.

### convert the vdi to a stateless image ###

* make sure the vdi is unmounted from where you were cutting it, first.  it should not modify anything so don't worry brah.  i'm not responsible for the injurious effects of any of the software i wrote (and they are many).

* run the converter
   ./doit.py ~/VirtualBox\ VMs/debian/debian.vdi output/

### create a gpxe iso ###

youj only need to do this if you want to use gPXE isos to bootstrap stateless boot.  you can alternately chainload gPXE from PXE, burn gPXE onto the option ROM, or tool up a PXE server.

* make a gpxe template or use the default.  the default template is at gpxe-scripts/default.gpxe.tmpl. the default might work unless you need to specify a different nic:
    #!gpxe
    dhcp net0
    chain http://${host}${url}

so, it just chainloads another gpxe file at the host and url you specify to build.

* build the gpxe iso for your scripts and host
    ./build-gpxe-iso.py -H 10.0.2.15 -u debian.gpxe -s gpxe-templates/default.gpxe.tmpl

