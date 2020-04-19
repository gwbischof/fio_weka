#!/usr/bin/python
##!/usr/bin/env python

import json
import decimal
import argparse
import glob
import os, sys, stat
import logging
import subprocess
from subprocess import Popen, PIPE, STDOUT
from shutil import copyfile
from contextlib import contextmanager
import time
import tempfile


"""A Python context to move in and out of directories"""
@contextmanager
def pushd(new_dir):
    previous_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(previous_dir)

# print something without a newline
def announce( text ):
    sys.stdout.flush()
    sys.stdout.write(text + " ")
    #sys.stdout.flush()

# format a number of bytes in GiB/MiB/KiB 
def format_units_bytes( bytes ):
    if bytes > 1024*1024*1024*1024:
        units = "TiB"
        value = float( bytes )/1024/1024/1024/1024
    elif bytes > 1024*1024*1024:
        units = "GiB"
        value = float( bytes )/1024/1024/1024
    elif bytes > 1024*1024:
        units = "MiB"
        value = float( bytes )/1024/1024
    elif bytes > 1024:
        units = "KiB"
        value = float( bytes )/1024
    else:
        units = "bytes"
        value = bytes
        return "%d %s" % (int(value), units)

    return "%0.2f %s" % (value, units)


# format a number of bytes in GiB/MiB/KiB 
def format_units_ns( nanosecs ):
    if nanosecs > 1000*1000*1000:
        units = "s"
        value = float( nanosecs/1000/1000/1000 )
    elif nanosecs > 1000*1000:
        units = "ms"
        value = float( nanosecs/1000/1000 )
    elif nanosecs > 1000:
        units = "us"
        value = float( nanosecs/1000 )
    else:
        units = "nanosecs"
        value = nanosecs
        return "%d %s" % (int(value), units)

    return "%0.2f %s" % (value, units)

# run a command via the shell, expect json output and return it.
def run_json_shell_command( command ):
    return json.loads( run_shell_command( command ) )

# run a command via the shell, check return code, exit on error.
def run_shell_command( command ):
    #print "Executing command: " + command
    try:
        output = subprocess.check_output( command, shell=True )
    except subprocess.CalledProcessError as err:
        print sys.argv[0] + ": " + str( err )
        sys.exit(1)

    return output

# parse arguments
progname=sys.argv[0]
parser = argparse.ArgumentParser(description='Run fio benchmark on a groups of servers')

parser.add_argument('servers', metavar='servername', type=str, nargs='+', help='Servers to execute on')

parser.add_argument('-d', '--directory', type=str, help='shared directory to use for test files - default is current dir', default=os.getcwd())

default_jobs = "./fio-jobfiles/020*"
parser.add_argument('-j', '--jobs', type=str, nargs='+', help='fio jobfiles to run, default is: '+default_jobs, default=glob.glob(default_jobs))

parser.add_argument('-r', '--range', type=str, nargs='?', help='range of clients to loop through, eg "2,27", default: "2,27", if -r specified with no value: "2,3"', default="2,27", const="2,3")

args = parser.parse_args()
#print args
#sys.exit(0)

cpu_attrs = {}
lscpu_out = run_shell_command( 'lscpu' )
for line in lscpu_out.split("\n"):
	line_list = line.split(":")
	if len( line_list[0] ) >= 1:	# there's a blank line at the end?
		cpu_attrs[line_list[0]] = line_list[1].strip()

cpuname = cpu_attrs["Model name"]
numcpu = cpu_attrs["CPU(s)"]


# get a list of server nodes
hostips = args.servers

def run_tests(hostips):

    hostcount = len( hostips )

    print str( len( hostips ) ) + " hosts detected"
    print "Working dir is " + args.directory

    # do a pushd so we know where we are
   
    with pushd( os.path.dirname( progname ) ):
        # use our own version of plumbum - Ubuntu is broken. (one line change from orig plumbum... /bin/sh changed to /bin/bash
        # this works for both ubuntu and centos
        sys.path.insert( 1, os.getcwd() + "/plumbum-1.6.8" )
        from plumbum import SshMachine, colors

        host_session = {}
        ssh_token = {}
        # open ssh sessions to all the hosts
        announce( "Opening ssh session to hosts:" )
        for host in hostips:
            rem = SshMachine( host )  # open an ssh session
            ssh_token[host] = rem
            host_session[host] = rem.session()
            announce( host )

        print
            
        # do we need to build fio?
        if not os.path.exists( "./fio/fio" ):
            with pushd( "./fio" ):
                print "Building fio"
                run_shell_command( './configure' )
                run_shell_command( 'make' )

        # do we need to copy fio onto the fs?
        if not os.path.exists( args.directory + "/fio" ):
            run_shell_command( 'cp ./fio/fio ' + args.directory + '/fio; chmod 777 ' + args.directory + '/fio' )

        # don't need to copy the fio scripts - we can run them in place

        # start fio --server on all servers
        announce( "starting fio --server on hosts:" )
        for host, s in host_session.items():
            announce( host )
            # screw it, just manually started for now with
            # start:  cat ../privateips | xargs -ri ssh {} '/mnt/testfs/fio --server --daemonize=/tmp/fio.pid -directory=/mnt/testfs/'
            # check:  cat ../privateips |xargs -ri ssh {}  "ps -ef|grep /fio|grep -v grep && echo {}; ls /tmp/fio.pid 2>/dev/null"
            # stop:  cat ../privateips |xargs -ri ssh {} "pkill fio; rm -f /tmp/fio.pid"
            #s.run( "pkill fio", retcode=None )
            #s.run( "rm -f /tmp/fio.pid", retcode=None )
            #s.run( args.directory + "/fio --server --daemonize=/tmp/fio.pid --directory=" + args.directory )

        print
        time.sleep( 5 )

        # get a list of script files
        fio_scripts = [f for f in args.jobs]
        fio_scripts.sort()

        print "setup complete."
        print
        print "Starting tests on " + str(hostcount) + " hosts"
        print "On " + numcpu + " cores of " + cpuname + " per host"   # assuming they're all the same...


        for script in fio_scripts:
            # check for comments in the job file, telling us what to output.  Keywords are "report", "bandwidth", "latency", and "iops".
            # example: "# report latency bandwidth"  or "# report iops"
            # can appear anywhere in the job file.  Can be multiple lines.
            reportitem = { "bandwidth":False, "latency":False, "iops":False }  # reset to all off
            with open( script ) as jobfile:
                for lineno, line in enumerate( jobfile ):
                    line.strip()
                    linelist = line.split()
                    if(len(linelist) == 0):
                        continue  # skip blank lines
                    if linelist[0][0] == "#":         # first char is '#'
                        if linelist[0] == "#report":
                            linelist.pop(0) # get rid of the "#report"
                        elif len( linelist ) < 2:
                            continue        # blank comment line?
                        elif linelist[1] == "report":      # we're interested
                            linelist.pop(0) # get rid of the "#"
                            linelist.pop(0) # get rid of the "report"
                        else:
                            continue

                        # found a "# report" directive in the file
                        for keyword in linelist:
                            if not keyword in reportitem.keys():
                                print "Syntax error in # report directive in " + script + ", line " + str( lineno +1 ) + ": keyword '" + keyword + "' undefined. Ignored."
                            else:
                                reportitem[keyword] = True


            if not reportitem["bandwidth"] and not reportitem["iops"] and not reportitem["latency"]:
                print "NOTE: No valid # report specification in " + script + "; reporting all"
                reportitem = { "bandwidth":True, "latency":True, "iops":True }  # set to all


            # build the arguments
            script_args = ""
            for host in hostips:
                #script_args = script_args + " --client=" + host + " --directory=" + args.directory + " " + script
                script_args = script_args + " --client=" + host + " " + script

        
            print
            print "starting fio script " + script
            fio_output = run_json_shell_command( './fio/fio' + script_args + " --output-format=json" )

            jobs = fio_output["client_stats"]
            print "Job is " + jobs[0]["jobname"] + " " + jobs[0]["desc"]

            temp_fd, temp_name = tempfile.mkstemp( prefix=jobs[0]["jobname"] + ".", suffix=".json", dir="." )
            print "JSON output is in " + temp_name
            os.write( temp_fd, json.dumps(fio_output, indent=2, sort_keys=True) )
            os.close( temp_fd )


            # gather interesting stats so we don't have to hunt for them later
            stats = jobs[len(jobs)-1]   # the last one is a summary/aggregate
            try:
                readbytes = stats["read"]["bw_bytes"]
                readiops = stats["read"]["iops"]
                readlat = stats["read"]["lat_ns"]["mean"]
            except NameError:
                readbytes = 0
                readiops = 0
                readlat = 0
            try:
                writebytes = stats["write"]["bw_bytes"]
                writeiops = stats["write"]["iops"]
                writelat = stats["write"]["lat_ns"]["mean"]
            except NameError:
                writebytes = 0
                writeiops = 0
                writelat = 0

            bw_bytes = readbytes + writebytes
            iops = readiops + writeiops
            latency = readlat + writelat        # div 2?

            if reportitem["bandwidth"]:
                bandwidth = {'total_read_bandwidth': format_units_bytes( readbytes ),
                             'total_write_bandwidth': format_units_bytes( writebytes ),
                             'total_bandwidth': format_units_bytes( bw_bytes ),
                             'avg_read_bandwidth': format_units_bytes( float( readbytes )/float( len(jobs)-1 ) ),
                             'avg_write_bandwidth': format_units_bytes( float( writebytes )/float( len(jobs)-1 ) ),
                             'avg_bandwidth': format_units_bytes( float( bw_bytes )/float( len(jobs)-1 ) )}
                print bandwidth
            if reportitem["iops"]:
                iops = {'total read iops': "{:,}".format(int(readiops)),
                        'total write iops': "{:,}".format(int(writeiops)),
                        'total iops': "{:,}".format(int(iops)),
                        'avg read iops': "{:,}".format(int(readiops) / len(jobs)-1 ),
                        'avg write iops': "{:,}".format(int(writeiops) / len(jobs)-1 ),
                        'avg iops': "{:,}".format(int(iops) / len(jobs)-1 )}
                print iops
            if reportitem["latency"]:
                latency = {'read latency': format_units_ns( float( readlat ) ),
                           'write latency': format_units_ns( float( writelat ) )}
                print latency

        print
        print "Tests complete."


        for host, s in host_session.items():
            announce( host )
            #s.run( "pkill fio", retcode=None )

        run_shell_command( 'rm ' + args.directory + '/fio' )

        print



# specify range on command line... eg. "-r 2,27"
(n,m)=map(int, args.range.split(','))
if n<2 or n>26 or m<3 or m>27 or n>=m:
    print 'bad range "'+n+','+m+'", must match n=[2,26],m=[3,27],n<m'
    sys.exit(-1)

for i in range(n,m):
    run_tests(hostips[0:i])

