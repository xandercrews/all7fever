#!/usr/bin/python2

import os
import re
import sys
import time
import glob
import shlex
import signal
import shutil
import argparse
import contextlib
import subprocess
import distutils.dir_util

from fstab import fstab
from pprint import pformat
from tempfile import mkdtemp
from operator import itemgetter,attrgetter


### setup logging
import logging
log = logging.getLogger()

stdouthandler = logging.StreamHandler(stream=sys.stdout)
log.addHandler(stdouthandler)

log.setLevel(logging.INFO)

formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(name)s] %(message)s')
stdouthandler.setFormatter(formatter)


### constants
RECOGNIZED_LINUXFS_TYPES = ['ext4', 'xfs', 'ext3', 'ext2' ]
LOOP_OPTS_RO = ['-o', 'loop', '-o', 'ro']
GZIP_C_PROG = ['pigz', '-9', '-c']
GZIP_D_PROG = ['pigz', '-d', '-k', '-c']

### mountpoint tests
def procMountTest(mountpoint):
	def f():
		with open('/proc/mounts', 'r') as fh:
			lines = fh.readlines()

		for line in lines:
			if mountpoint in line:
				return True

		return False
	
	return f

def inodeMountTest(mountpoint, ino):
	def f():
		return os.stat(mountpoint)[1] == ino	# inode_no == 1

	return f


### generic
def waitForTest(test, timeout=3):
	timeout += time.time()

	while True:
		if test():
			break

		if time.time() >= timeout:
			raise Exception('timed out')

		time.sleep(0.15)

def which(progname):
	for path in os.environ["PATH"].split(os.pathsep):
		if os.access(os.path.join(path, progname), os.X_OK):
			return (path, progname)
	return None

def errExcept(*args):
	problem = ' '.join(args)
	log.error(problem)
	raise Exception(problem)

def blkid(pathglob):
	args = ['/sbin/blkid', '-c', '/dev/null']
	args.extend(glob.glob(pathglob))
	p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=None, stdin=None, close_fds=True)
	stdout, stderr = p.communicate()
	rc = p.wait()

	if rc != 0:
		raise Exception("error in blkid [rc=%d]" % rc)

	parts = []

	for line in stdout.split('\n'):
		part = {}

		if ':' not in line:
			continue

		line = line.strip()
		dev, line = line.split(': ', 2) 
		part['DEV'] = dev
		varlist = shlex.split(line)

		for var in varlist:
			k, v = var.split('=', 2)
			part[k] = v

		parts.append(part)

	return parts


# open a loop mount with a context manager
class Mount(object):
	# TODO - refactor with subclassing for temporary and explicit mountpoints
	def __init__(self, *opts, **kwargs):
		self.opts = opts

		if 'mountpoint' in kwargs:
			self.mountpoint = kwargs['mountpoint']
			
			if not self.mountpoint.startswith('/'):
				errExcept('mountpoint \'%s\' must be an absolute path')
			elif not os.path.exists(self.mountpoint):
				errExcept('mountpoint \'%s\' does not exist, cannot continue' % self.mountpoint)
		else:
			self.mountpoint = None

	def __enter__(self):
		if self.mountpoint is None:
			self.tmpdir = mkdtemp('all7fever')

		try:
			mountloc = which('mount')
			assert(mountloc is not None)

			mountpath = '/'.join(mountloc)

			args = list(self.opts)

			args.insert(0, mountpath)
			if self.mountpoint is None:
				args.append(self.tmpdir) 
			else:
				args.append(self.mountpoint) 

			log.debug('mount image args: %s (or) %s' % (str(args), ' '.join(args)))

			p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None, close_fds=True)
			stdout, stderr = p.communicate()
			rc = p.wait()

			if rc != 0:
				log.debug('mount output:\n%s*********' % stdout)
				log.debug('mount err output:\n%s*********' % stderr)
				errExcept('couldn\'t mount image, are you root?')

			if self.mountpoint is None:
				waitForTest(procMountTest(self.tmpdir))
			else:
				waitForTest(procMountTest(self.mountpoint))

			log.debug('mounted successfully')

		except Exception, e:
			if self.mountpoint is None:
				try:
					os.rmdir(self.tmpdir)
				except OSError, e2:
					log.warn('could not remove temporary directory \'%s\'' % self.tmpdir)
					log.debug('OSError exception: %s' % str(e2))
			raise e

		if self.mountpoint is None:
			return self.tmpdir
		else:
			return self.mountpoint

	def __exit__(self, *exc_details):
		log.info('unmounting image')
		# log.debug('exc_details: %s' % str(exc_details))

		umountloc = which('umount')
		if umountloc is None:
			raise Exception('cannot find umount command???')

		umountpath = '/'.join(umountloc)

		if self.mountpoint is None:
			p = subprocess.Popen([umountpath, self.tmpdir], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None, close_fds=True)
		else:
			p = subprocess.Popen([umountpath, self.mountpoint], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None, close_fds=True)

		(stdout, stderr) = p.communicate()
		rc = p.wait()
	
		if rc != 0:
			log.warn('umount did not exit nicely[rc=%d]' % rc)
			log.debug('umount output:\n%s*********' % stdout)
			log.debug('umount err output:\n%s*********' % stderr)

		if self.mountpoint is None:
			try:
				os.rmdir(self.tmpdir)
			except OSError, e:
				log.warn('could not remove temporary directory \'%s\'' % self.tmpdir)
				log.debug('OSError exception: %s' % str(e))


# open a vdi fuse session with a context manager
class VDIFuse(object):
	VDFUSE_NAME = 'vdfuse'
	
	def __init__(self, vdifile):
		self.vdifile = vdifile
		self.prereqCheck()

	def __enter__(self):
		vdloc = which(VDIFuse.VDFUSE_NAME)
		assert(vdloc is not None) 

		vdpath = '/'.join(vdloc)

		self.tmpdir = mkdtemp('all7fever')

		log.info('mounting vdifuse image')
		args = [vdpath, '-g', '-f', self.vdifile, self.tmpdir]
		log.debug('%s args: %s (or) %s' % (self.VDFUSE_NAME, str(args), ' '.join(args)))

		self.p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None, close_fds=True)

		def mountTests():
			proctest = procMountTest(self.tmpdir)
			inotest = inodeMountTest(self.tmpdir, 1)
	
			def f():
				return proctest() and inotest()

			return f

		try:
			waitForTest(mountTests())
		except Exception, e:
			os.rmdir(self.tmpdir)
			raise
	
		log.debug('vdifuse mounted successfully')
	
		return self.tmpdir

	def __exit__(self, *exc_details):
		log.info('unmounting vdifuse disk')
		# log.debug('exc_details: %s' % str(exc_details))
		self.p.send_signal(signal.SIGINT)
		(stdout, stderr) = self.p.communicate()
		rc = self.p.wait()

		if rc != 0:
			log.warn('vdifuse did not exit nicely [rc=%d]' % rc)
			log.debug('vdifuse output:\n%s*********' % stdout)
			log.debug('vdifuse err output:\n%s*********' % stderr)

		try:
			os.rmdir(self.tmpdir)
		except OSError, e:
			log.warn('could not remove temporary directory \'%s\'' % self.tmpdir)
			log.debug('OSError exception: %s' % str(e))

	def prereqCheck(self):
		vdloc = which(VDIFuse.VDFUSE_NAME)
		if vdloc is None:
			errExcept('could not find vdfuse in path, correct path or install vdfuse')

		if not os.path.exists(self.vdifile): 
			errExcept('vdi file not found: \'%s\'' % self.vdifile)

		if not os.access(self.vdifile, os.R_OK):
			errExcept('cannot read file \'%s\'- check read permissions' % self.vdifile)

def isRootFS(mountpoint):   # .. probably
	fstabpath = os.path.join(mountpoint, 'etc/fstab')
	
	if os.path.exists(fstabpath):
		return True
	
	return False


def createDiskMap(stabbystabby, vdiparts):
	log.debug('creating disk map')

	devname = None

	diskmap = {}

	for fs in stabbystabby:
		if not fs.dir.startswith('/') or fs.type not in RECOGNIZED_LINUXFS_TYPES:
			log.warn('ignoring filesystem with mountpoint \'%s\' of type \'%s\' (%s)' % (fs.dir, fs.type, fs.fsname))
		else:
			log.debug('examining filesystem with mountpoint \'%s\' of type \'%s\' (%s)' % (fs.dir, fs.type, fs.fsname))
			if fs.fsname.startswith('UUID='):
				devuuid = str(fs.fsname[len('UUID='):]).lower()
				matches = filter(lambda part: part['UUID'].lower() == devuuid, vdiparts)
				if len(matches) != 1:
					errExcept('found %d matches for device with mountpoint \'%s\', cannot continue' % (len(matches), fs.dir))
				diskmap[fs.fsname] = matches[0]['DEV']
				log.info('found mount \'%s\' at \'%s\'' % (fs.dir, matches[0]['DEV']))
			elif fs.fsname.startswith('LABEL='):
				errExcept('LABEL fstab entries NYI =(')
				# liek dis?
				# devlabel = str(fs.fsname[len('LABEL='):]).lower()
				# matches = filter(lambda part: part['LABEL'].lower() == devuuid, parts)
				# if len(matches) != 1:
				#	errExcept('found %d matches for device with mountpoint \'%s\', cannot continue' % (len(matches), fs.dir))
				# diskmap[fs.fsname] = matches[0]['DEV']
			elif fs.fsname.startswith('/dev/'):
				errExcept('device name fstab entries NYI =(')
				# liek dis?
				# log.warn('found a device without UUID or LABEL identifier.  i\'m going to make some sketchy assumptions about what this partition this is ... ')
				# import re
				# groups = re.match('\/dev\/([vsh]d[a-z]+)([0-9]+)', fs.fsname)
				# if groups is None:
				#	errExcept('didn\'t recognize the device name \'%s\' in fstab' % fs.fsname)
			else:
				log.warn('don\'t know what type of fstab entry this is, ignoring: %s' % repr(fs))

	return diskmap

def unmountStack(s):
	while len(s) > 0:
		m = s.pop()
		try:
			time.sleep(0.1)
			m.__exit__()
		except Exception, e:
			errExcept('ok, i\'m going to level with you.  this is not good.\nwe failed while trying to unmount one of the filesystems.\nat this point you have to manually unmount them or risk corruption.\nsorry brah.\n%s' % str(e))

def du(path):
	dupath = '/'.join(which('du'))
	dup = subprocess.Popen([dupath, '-b', path], stderr=None, stdin=None, stdout=subprocess.PIPE, close_fds=True)
	while dup.poll() is None:
		for line in dup.stdout.readlines():
			pass
	return int(line.strip().split()[0])

def cpioCopy(src, dst, **kwargs):
	log.debug('starting cpio-based copy \'%s\' -> \'%s\'' % (src, dst))

	log.debug('creating dst directory \'%s\'' % dst)
	os.mkdir(dst)

	progress = False
	if 'progress' in kwargs:
		progress = kwargs['progress']
		log.debug('requested progress bar')
	else:
		log.debug('no progress bar')

	findcp = None
	srccp = None
	midcp = None
	dstcp = None

	def killPipeline():
		for fh in [dstcp, midcp, srccp, findcp]:
			if fh is not None:
				fh.send_signal(signal.SIGINT)

	try:
		devnull = open('/dev/null', 'w')

		findpath = '/'.join(which('find'))
		args = [findpath, '.']
		log.debug('find args: %s' % str(args))
		findcp = subprocess.Popen(args, close_fds=True, stdin=None, stdout=subprocess.PIPE, stderr=devnull, cwd=src)

		cpiopath = '/'.join(which('cpio'))
		args = [cpiopath, '-H', 'newc', '-o']
		log.debug('src cpio args: %s' % str(args))
		srccp =  subprocess.Popen(args, close_fds=True, stdin=findcp.stdout, stdout=subprocess.PIPE, cwd=src, stderr=devnull)
		
		if progress:
			pvpath = which('pv')
			if pvpath is None:
				log.warn('install pv for progress bar, disabling')
				progress = False

		if progress:
			pvpath = '/'.join(pvpath)
			copybytes = du(src)
			args = [pvpath, '-pter', '-s', str(int(copybytes * 0.98)), '-i', '0.5']
			log.debug('pv args: %s' % str(args))
			midcp = subprocess.Popen(args, stdin=srccp.stdout, stdout=subprocess.PIPE)
		else:
			midcp = srccp

		args = [cpiopath, '-idmv']
		log.debug('dst cpio args: %s' % str(args))
		dstcp = subprocess.Popen(args, cwd=dst, stdin=midcp.stdout, stderr=devnull, stdout=devnull, close_fds=True)

		devnull.close()

	except OSError, e:
		log.warn('encountered os error %s' % str(e)) 
		killPipeline()
		raise

	finally:
		for fh in [dstcp, midcp, srccp, findcp]:
			if fh is not None:
				rc = fh.wait()
				if rc != 0:
					log.warn('cpiocopy process did not exit nicely [rc=%d]' % rc)
					killPipeline()
					errExcept('killed pipeline because of bad exit codes')

	log.info('rootfs copy completed')

def cpioZipPack(src, dst, **kwargs):
	log.debug('starting cpio-gz pack \'%s\' -> \'%s\'' % (src, dst))
	
	dstcp = open(dst, 'w')

	progress = False
	if 'progress' in kwargs:
		progress = kwargs['progress']
		log.debug('requested progress bar')
	else:
		log.debug('no progress bar')

	findcp = None
	srccp = None
	midcp = None
	zipcp = None

	def killPipeline():
		for fh in [zipcp, midcp, srccp, findcp]:
			if fh is not None:
				fh.send_signal(signal.SIGINT)

	try:
		devnull = open('/dev/null', 'w')

		findpath = '/'.join(which('find'))
		args = [findpath, '.']
		log.debug('find args: %s' % str(args))
		findcp = subprocess.Popen(args, close_fds=True, stdin=None, stdout=subprocess.PIPE, stderr=devnull, cwd=src)

		cpiopath = '/'.join(which('cpio'))
		args = [cpiopath, '-H', 'newc', '-o']
		log.debug('src cpio args: %s' % str(args))
		srccp =  subprocess.Popen(args, close_fds=True, stdin=findcp.stdout, stdout=subprocess.PIPE, cwd=src, stderr=devnull)
		
		if progress:
			pvpath = which('pv')
			if pvpath is None:
				log.warn('install pv for progress bar, disabling')
				progress = False

		if progress:
			pvpath = '/'.join(pvpath)
			copybytes = du(src)
			args = [pvpath, '-pter', '-s', str(int(copybytes * 0.98)), '-i', '0.5']
			log.debug('pv args: %s' % str(args))
			midcp = subprocess.Popen(args, stdin=srccp.stdout, stdout=subprocess.PIPE)
		else:
			midcp = srccp

		assert(len(GZIP_C_PROG) > 0)
		assert(which(GZIP_C_PROG[0]) is not None)
		gzipcp = '/'.join(which(GZIP_C_PROG[0]))
		args = [ gzipcp ] + GZIP_C_PROG[1:]
		log.debug('gzip args: %s' % str(args))
		zipcp = subprocess.Popen(args, cwd='/tmp', stdin=midcp.stdout, stderr=devnull, stdout=dstcp, close_fds=True)

		devnull.close()

	except OSError, e:
		log.warn('encountered os error %s' % str(e)) 
		killPipeline()
		raise
		
	except Exception, e:
		log.warn('encountered unhandled exception %s' % str(e)) 
		killPipeline()
		raise	

	finally:
		e = None
		for fh in [zipcp, midcp, srccp, findcp]:
			if fh is not None:
				rc = fh.wait()
				if rc != 0:
					log.warn('cpiocopy process did not exit nicely [rc=%d]' % rc)
					killPipeline()
					e = 'killed pipeline because of bad exit codes'

		dstcp.close()

		if e is not None:
			errExcept(e)

	log.info('pack completed')

def mountAndCopyDisk(args, rootfsdir):
	with VDIFuse(args.vdifile) as vdimount:
		parts = blkid(os.path.join(vdimount,'Partition*'))

		def isLinuxFS(fshash):
			if 'TYPE' in fshash:
				fstype = fshash['TYPE']
				if fstype.lower() in RECOGNIZED_LINUXFS_TYPES:
					assert('DEV' in fshash)
					return True
			return False

		parts = filter(isLinuxFS, parts)

		log.debug('linux partitions: ' + str(['%s=%s' % (p['DEV'], p['TYPE']) for p in parts]))

		# find root device
		log.info('finding root device')
		rootdev = None

		searched = 0
		
		for part in parts:
			assert('DEV' in part)
			dev = part['DEV']
			mountargs = LOOP_OPTS_RO + [dev] 
			with Mount(*mountargs) as loopmount:
				searched += 1
				log.info('searching mount %d' % searched)
				log.debug('mounted \'%s\' at \'%s\'' % (dev, loopmount,))
				if isRootFS(loopmount):
					rootdev = part
					stabbystabby = fstab(os.path.join(loopmount,'etc/fstab'))
					break
		
		if rootdev is not None:
			log.info('found root device')
			log.debug('root device \'%s\' type \'%s\'' % (rootdev['DEV'], rootdev['TYPE']))

			# figure out where humpty dumpty's tender bits go
			log.info('creating map partition/mountpoint map')
			diskmap = createDiskMap(stabbystabby, parts)
			log.debug('created map:\n%s********' % pformat(diskmap))

			# mount each filesystem in its place, starting with root
			mountstack = []

			try:
				# make the fses we care about into a dictionary
				fses = dict([ (fs.dir, diskmap[fs.fsname],) for fs in iter(stabbystabby) if fs.fsname in diskmap])
	
				# sanity checking to see if we guessed right about the root device
				if '/' not in fses:	
					errExcept('no (recognized) device with root mountpoint exists in fstab')
				elif rootdev['DEV'] != fses['/']:
					errExcept('we thought we knew what the root device was, but we were wrong.\n\'%s\' has the root mountpoint but fstab was found on \'%s\'' % (rootdev['DEV'], diskmap[fses['/'].fsname]))

				# mount the root fs
				rootdev = fses['/']
				mountargs = LOOP_OPTS_RO + [rootdev]
				rootmount = Mount(*mountargs)
				topdir = rootmount.__enter__()
				mountstack.append(rootmount)
				log.info('mounted \'/\' at \'%s\'' % topdir)

				del fses['/']

				# mount each other filesystem
				while len(fses) > 0:
					delmount = None

					for mount in fses.iterkeys():	
						# check if the mountpoint is accessible off the tree we have now (for nested mountpoints)
						realmount = os.path.join(topdir, mount.lstrip('/'))
						if os.path.exists(realmount):
							thisdev = fses[mount]
							mountargs = LOOP_OPTS_RO + [thisdev]
							thismount = Mount(*mountargs, mountpoint=realmount)
							thismount.__enter__()
							mountstack.append(thismount)
							log.info('mounted \'%s\' at \'%s\'' % (thisdev, realmount))
							delmount = mount
							break

					if delmount is not None:
						del fses[delmount]
					else:
						log.debug('remaining fses:\n%s*******' % '\n'.join([repr(f) for f in fses]))
						errExcept('could not place remaining mountpoints.  the known filesystems must not contain all the needed mountpoints')

				log.info('all filesystems mounted')

				# copy off the contents into a root dir somewhere
				os.makedirs(args.outdir)
				cpioCopy(topdir, rootfsdir, progress=True)

			except Exception, e:
				log.error('problem while mounting and packing the filesystem')
				raise
			finally:
				unmountStack(mountstack)

		else:
			errExcept('could not find root device')

def mtime(fname):
	return os.stat(fname)[8]

def strInFileMagic(fname, s):
	magic = getFileMagic(fname)

	if s in magic:
		return True

	return False

def getFileMagic(fname):
	log.debug('checking file magic for \'%s\'' % fname)
	filepath = '/'.join(which('file'))
	fp = subprocess.Popen([filepath, fname], close_fds=True, stderr=None, stdout=subprocess.PIPE, stdin=None)
	stdout, stderr = fp.communicate()
	rc = fp.wait()

	if rc != 0:
		errExcept('file utility did not exit nicely [rc=%d]' % rc)

	return stdout

# TODO use /etc/issue to detect types (lookup types)
def detectOSType(rootfsdir):
	return 'debian'

# TODO write generalized pipeline library
def extractGZCpio(src, dst, **kwargs):
	log.debug('starting cpio extraction \'%s\' -> \'%s\'' % (src, dst))

	if not os.path.exists(src):
		errExcept('cannot find cpio-gz archive for extraction \'\'')

	log.debug('creating dst directory \'%s\'' % dst)
	os.mkdir(dst)

	progress = False
	if 'progress' in kwargs:
		progress = kwargs['progress']
		log.debug('requested progress bar')
	else:
		log.debug('no progress bar')
	
	srccp = None
	midcp = None
	dstcp = None

	def killPipeline():
		for fh in [dstcp, midcp, srccp]:
			if fh is not None:
				fh.send_signal(signal.SIGINT)

	try:
		devnull = open('/dev/null', 'w')

		assert(len(GZIP_D_PROG) > 0)
		assert(which(GZIP_D_PROG[0]) is not None)
		gzipcp = '/'.join(which(GZIP_D_PROG[0]))
		args = [ gzipcp ] + GZIP_D_PROG[1:] + [ src ]
		log.debug('gzip args: %s' % str(args))
		srccp = subprocess.Popen(args, stdin=None, stderr=devnull, stdout=subprocess.PIPE, close_fds=True)

		if progress:
			pvpath = which('pv')
			if pvpath is None:
				log.warn('install pv for progress bar, disabling')
				progress = False

		if progress:
			pvpath = '/'.join(pvpath)
			args = [pvpath, '-pter', '-i', '0.5']
			log.debug('pv args: %s' % str(args))
			midcp = subprocess.Popen(args, stdin=srccp.stdout, stdout=subprocess.PIPE)
		else:
			midcp = srccp

		cpiopath = '/'.join(which('cpio'))
		args = [cpiopath, '-idmv']
		log.debug('dst cpio args: %s' % str(args))
		dstcp = subprocess.Popen(args, cwd=dst, stdin=midcp.stdout, stderr=devnull, stdout=devnull, close_fds=True)

		devnull.close()

	except OSError, e:
		log.warn('encountered os error %s' % str(e)) 
		killPipeline()
		raise

	except Exception, e:
		log.warn('encountered unhandled exception %s' % str(e)) 
		killPipeline()
		raise	

	finally:
		for fh in [dstcp, midcp, srccp]:
			if fh is not None:
				rc = fh.wait()
				if rc != 0:
					log.warn('cpio extract process did not exit nicely [rc=%d]' % rc)
					killPipeline()
					errExcept('killed pipeline because of bad exit codes')

	log.info('rootfs copy completed')

@contextlib.contextmanager
def tempdir():
	tmpdir = mkdtemp('all7fever')
	yield tmpdir
	shutil.rmtree(tmpdir)

def copyNetworkDrivers(modpath, tgt):
	assert(os.path.exists(tgt))

	hostmod = os.path.join(modpath, 'kernel/net')
	tgtmod = os.path.join(tgt, 'kernel/net')

	assert(os.path.exists(hostmod))
	assert(os.path.exists(tgtmod))
	log.debug('copying network modules from \'%s\' -> \'%s\'' % (hostmod, tgtmod))
	distutils.dir_util.copy_tree(hostmod, tgtmod)

def toolInitScript(initrdtmp, ostype):
	if ostype == 'debian':
		dstfile = os.path.join(initrdtmp, 'scripts/stateless')
		shutil.copyfile('init-scripts/debian/stateless.debian6.sh', dstfile)
	else:
		errExcept('don\'t know how to tool initrd to boot stateless for \'%s\', cannot continue')

def writeGpxeScript(outdir, ostype):
	if ostype == 'debian':
		dstfile = os.path.join(outdir, 'debian.gpxe')
		shutil.copyfile('gpxe-scripts/debian.gpxe', dstfile)
		log.info('gpxe script written to \'%s\'' % dstfile)
	else:
		errExcept('don\'t know how to generate gpxe script for \'%s\', cannot continue')

def writeStatelessFstab(rootfsdir):
	fstabpath = os.path.join(rootfsdir, 'etc/fstab')
	fsfh = open(fstabpath, 'w')
	print >>fsfh, "devpts  /dev/pts devpts   gid=5,mode=620 0 0"
	print >>fsfh, "tmpfs   /dev/shm tmpfs    defaults       0 0"
	print >>fsfh, "proc    /proc    proc     defaults       0 0"
	print >>fsfh, "sysfs   /sys     sysfs    defaults       0 0"
	fsfh.close()
	log.debug('modified fstab at \'%s\'' % fstabpath)

def createBootPackage(args, rootfsdir):
	outdir = args.outdir
	bootdir = os.path.join(rootfsdir, 'boot')

	### detect OS type
	ostype = detectOSType(rootfsdir)
	log.info('guessing OS type \'%s\'' % ostype)

	### locate and copy the current initrd, kernel
	# TODO/HACK based on file modification times
	bootfiles = os.listdir(bootdir)
	bootfiles = map(lambda fname: os.path.join(bootdir, fname), bootfiles)

	# kernel
	kernels = filter(lambda fname: strInFileMagic(fname, 'Linux kernel'), bootfiles)
	kernels = sorted(kernels, key=mtime)

	kpath  = os.path.join(outdir, 'vmlinuz')
	ipath  = os.path.join(outdir, 'initrd.orig.gz')

	for k in kernels:
		# other checking?
		log.info('chose kernel \'%s\'' % k)
		shutil.copyfile(k, kpath)
		break

	# initrd
	initrds = filter(lambda fname: 'initrd' in fname or 'initramfs' in fname, bootfiles)
	initrds = sorted(initrds, key=mtime)

	for i in initrds:
		if not strInFileMagic(i, 'gzip compressed data'):
			log.warn('this does not look like a gzip compressed initrd: \'%s\', skipping' % i)
			continue
		log.info('chose initrd \'%s\'' % i)
		shutil.copyfile(i, ipath)
		break

	### process initrd to stateless boot
	if not os.path.exists(kpath):
		errExcept('missing kernel at \'%s\'- cannot continue preparing boot resources' % kpath)
	if not os.path.exists(ipath):
		errExcept('missing initrd at \'%s\'- cannot continue preparing boot resources' % ipath)

	log.info('determine kernel version')
	kmagic = getFileMagic(kpath)
	verstring = re.search(':\s*Linux kernel.*,\s*version\s*([0-9]+\.[0-9]\.[0-9](-[0-9]+))', kmagic)
	if verstring is None:
		errExcept('cannot determine kernel version')

	kversion = verstring.group(1)
	log.debug('kernel version \'%s\'' % kversion)

	log.info('locate kernel modules')
	modpaths= glob.glob("%s/lib/modules/%s-*" % (rootfsdir, kversion))
	if len(modpaths) < 1:
		errExcept('could not find kernel modules for kernel version')
		
	modpath = modpaths[0]
	log.debug('modules found at \'%s\'' % modpath)
	
	modrelpath = str(modpath[len(rootfsdir):]).lstrip('/')

	log.info('extracting initrd')
	with tempdir() as tmpdir:
		initrdtmp = os.path.join(tmpdir, 'initrd')
		log.debug('initrd working dir: \'%s\'' % initrdtmp)
		extractGZCpio(ipath, initrdtmp)

		# add network drivers
		tgt = os.path.join(initrdtmp, modrelpath)
		copyNetworkDrivers(modpath, tgt)
	
		# replace init file
		toolInitScript(initrdtmp, ostype)

		# repack initrd
		modifiedinitrd = os.path.join(outdir, 'initrd.gz')
		cpioZipPack(initrdtmp, modifiedinitrd)
		log.debug('wrote modified initrd to \'%s\'' % modifiedinitrd, progress=True)

	# write gpxe script
	writeGpxeScript(outdir, ostype)

# MAIN
if __name__ == '__main__':
	ap = argparse.ArgumentParser()
	ap.add_argument('vdifile', metavar='VDI', help='a (.vdi) disk image')
	ap.add_argument('outdir', metavar='OUTDIR', help='an output directory, must not exist')
	ap.add_argument('-p','--onlypack', dest='onlypack', action='store_true', help='only run the packing phase (assumes root copied to outdir)')
	ap.add_argument('-b','--onlyboot', dest='onlyboot', action='store_true', help='only run the boot resources phase (assumes root copied to outdir)')
	args = ap.parse_args()

	# TODO make more sense of onlyPHASE and notPHASE, calculate phases at arg time and make logic simpler during phase exec

	if not args.onlypack and not args.onlyboot and os.path.exists(args.outdir):
		errExcept('cannot make output directory \'%s\', check permissions and path' % args.outdir)

	rootfsdir = os.path.join(args.outdir, 'rootfs')

	# COPY DISK PHASE
	if not args.onlypack and not args.onlyboot:
		mountAndCopyDisk(args, rootfsdir)

	# rootfs should have been created at this point, in this run or a previous one
	if not os.path.exists(rootfsdir):
		errExcept('rootfs does not exist at \'%s\'' % rootfsdir)

	# MODIFY DISK PHASE
	# TODO make the image slimmer by taking out unnecessary files

	# blast fstab
	writeStatelessFstab(rootfsdir)

	# PACK ROOTFS PHASE
	if not args.onlyboot:
		cpioZipPack(rootfsdir, os.path.join(args.outdir,'rootimg.cpio.gz'), progress=True)

	# BOOT RESOURCES PHASE
	if not args.onlypack:
		createBootPackage(args, rootfsdir)
