#!/usr/bin/python
import os
import sys
import multiprocessing
from subprocess import PIPE,Popen
from mako.template import Template
import argparse
from tempfile import mkstemp
from contextlib import contextmanager
import shutil
import datetime

delim = '*****EOF*****'

def isExe(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

def which(program):
    fpath, fname = os.path.split(program)
    if fpath:
        if isExe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exefile = os.path.join(path, program)
            if isExe(exefile):
                return exefile

    return None

def onlyif(cond):
    def wrap(f):
        def wrapped(*args, **kwargs):
            return f(*args, **kwargs)
    
        def noop(*args, **kwargs):
            pass
            
        if cond:
            return wrapped
        else:
            return noop

    return wrap

@contextmanager
def mktempfile(*args, **kwargs):
    (fd, path) = mkstemp(*args, **kwargs)
    yield (os.fdopen(fd, 'w'), path,)
    os.unlink(path)

if __name__ == '__main__':
    # argument parsing
    argparser = argparse.ArgumentParser(description='Build a gpxe ISO for template building and testing')
    argparser.add_argument('-H','--host','--scripthost', dest='gpxescripthost', metavar='H', nargs=1, type=str, default=[ '10.0.2.15:8081' ], help='the host from which to retrieve the gpxe script')
    argparser.add_argument('-u','--url','--scripturlpath', dest='gpxescripturlpath', metavar='U', nargs=1, type=str, default=[ '/gpxe/${net0/mac}' ], help='the url from which to retrieve the gpxe script from scripthost')
    argparser.add_argument('-s', '--script', '--gpxescript', dest='gpxescript', metavar='S', type=argparse.FileType('r'), default='gpxe-templates/default.gpxe.tmpl', help='a gpxe script mako template')
    argparser.add_argument('-o','--output', dest='output', metavar='O', nargs=1, type=str, help='if specified, will copy the output iso to the location')
    argparser.add_argument('-f','--force', dest='force', action='store_true', default=False, help='forces overwriting of output file')
    argparser.add_argument('-v','--verbose', dest='verbose', action='store_true', default=False, help='prints verbose output')
    args = argparser.parse_args()

    @onlyif(args.verbose)
    def vprint(*args):
        print >>sys.stderr, '[%s]' % datetime.datetime.isoformat(datetime.datetime.now()), ' '.join(args)

    vprint('args:\n' + '\n'.join(['  %s => %s' % (k,v) for k,v in vars(args).iteritems()]))

    # make directory
    scriptdir = os.path.dirname(os.path.realpath(__file__))
    makedir = os.path.realpath(os.path.join(scriptdir, 'gpxe/src'))
    makepath = which('make')

    output = None

    vprint('makefile path: \'%s\'' % makedir)

    # output validation
    if args.output is not None:
        output = os.path.realpath(args.output[0])
        outpath = os.path.dirname(output)

        if not os.path.exists(outpath):
            raise Exception('output path does not exist: \'%s\'' % outpath)

        if os.path.exists(output) and not args.force:
            raise Exception('output file already exists \'%s\'' % output)
        elif os.path.exists(output):
            vprint('output file exists, forcing overwrite')
            
        if not os.access(outpath, os.W_OK):
            raise Exception('cannot write to output path \'%s\', check permissions' % outpath)
            
    # script embedding
    # scripturl shall be an absolute path off the scripthost
    # scripthost can contain a port in the usual fashion: '10.0.2.15:8081'
    gpxescripthost = args.gpxescripthost[0]

    gpxescripturlpath = args.gpxescripturlpath[0]
    gpxescripturlpath = '/' + gpxescripturlpath.lstrip('/')

    templateargs = {
        'url': gpxescripturlpath,
        'host': gpxescripthost,
    }

    # write out script to temp file
    with mktempfile() as (scriptfh, scriptpath):
        vprint('temporary script file \'%s\'' % scriptpath)
        contents = Template(args.gpxescript.read()).render(**templateargs)
        print >>scriptfh, contents
        scriptfh.flush()

        vprint('gpxe script:\n%s%s' % (contents, delim,))
        
        # build 
        numcores = multiprocessing.cpu_count()
        makeargs = [makepath, '-j', '%d' % (numcores + 1), 'bin/gpxe.iso', 'EMBEDDED_IMAGE=%s' % scriptpath]
        vprint('make args: %s' % ' '.join(makeargs))
        make = Popen(makeargs, stdin=None, stdout=PIPE, stderr=PIPE, close_fds=True,cwd=makedir)
        stdout, stderr = make.communicate()
        vprint('make stdout:\n%s%s' % (stdout, delim,))
        vprint('make stderr:\n%s%s' % (stderr, delim,))
        rc = make.wait()
        vprint('make exited')

    if rc != 0:
        errstr = '\n********\n%s\n********' % stderr.rstrip()
        raise Exception('there was a problem building gpxe iso:'+ errstr)

    # optionally, copy output iso
    isopath = os.path.realpath(os.path.join(scriptdir, '../gpxe/src/bin/gpxe.iso'))

    if output is not None:
        vprint('copying iso file from \'%s\' to \'%s\'' % (isopath, output))
        shutil.copyfile(isopath, output)
        isopath = output

    # report location of the iso file
    print 'gpxe iso written to \'%s\'' % isopath

# vim: ts=4 sw=4 expandtab:
