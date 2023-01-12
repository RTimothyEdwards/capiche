#!/usr/bin/env python3
#
# build_fc_files_w1sh_mp.py --
#
#	Create FasterCap files to simulate many different
#	geometries to capture all needed information for
#	parasitic capacitance modeling.  Version _w1sh
#	generates output for a single wire on a metal
#	layer, with a shield plane underneath (or over top).
#
# Written by Tim Edwards
# December 20, 2022
#
import os
import sys
import numpy
import subprocess
import multiprocessing

# Local files
from ordered_stack import ordered_stack
from generate_geometry import generate_one_shielded_wire_file

#--------------------------------------------------------------
# Usage statement
#--------------------------------------------------------------

def usage():
    print('Usage:  build_fc_files_w1sh_mp.py <stack_def_file> [options]')
    print('  Where [options] may be one or more of:')
    print('     -metals=<metal>[,...]  (restrict wire type to one or more metals)')
    print('     -shields=<metal>[,...] (restrict shield type to one or more metals)')
    print('     -sub[strate]=<substrate>     (substrate type)')
    print('     -width=<start>,<stop>,<step> (wire width range, in microns)')
    print('     -sep=<start>,<stop>,<step>   (separation range, in microns)')
    print('     -tol[erance]=<value>         (FasterCap tolerance)')
    print('     -file=<name>                 (output filename for results)')

#---------------------------------------------------
# 1. Get arguments
#---------------------------------------------------

options = []
arguments = []
for item in sys.argv[1:]:
    if item.find('-', 0) == 0:
        options.append(item)
    else:
        arguments.append(item)

if len(arguments) != 1:
    print('Argument length is ' + str(len(arguments)))
    usage()
    sys.exit(1)

metallist = []
condlist = []
use_default_width = True
wstart = 0
wstop = 0
wstep = 0
use_default_sep = True
sstart = 0
sstop = 0
sstep = 0
substrate = None
outfile = 'results/w1sh_results.txt'
verbose = 0
tolerance = 0.01

for option in options:
    tokens = option.split('=')
    if len(tokens) != 2:
        print('Error:  Option "' + option + '":  Option must be in form "-key=<value>".')
        usage()
        continue
    if tokens[0] == '-file':
        outfile = tokens[1]
    elif tokens[0] == '-verbose':
        try:
            verbose = int(tokens[1])
        except:
            print('Error:  Verbose level "' + tokens[1] + '" is not numeric.')
            continue
    elif tokens[0] == '-tol' or tokens[0] == '-tolerance':
        try:
            tolerance = float(tokens[1])
        except:
            print('Error:  Tolerance "' + tokens[1] + '" is not numeric.')
            continue
    elif tokens[0] == '-metals':
        metallist = tokens[1].split(',')
    elif tokens[0] == '-shields':
        condlist = tokens[1].split(',')
    elif tokens[0] == '-sub' or tokens[0] == '-substrate':
        subname = tokens[1]
    elif tokens[0] == '-width':
        rangelist = tokens[1].split(',')
        if len(rangelist) != 3:
            print('Error:  Wire width needs three comma-separated values')
            usage()
            continue
        optstr = rangelist[0].replace('um','')
        try:
            wstart = float(optstr)
        except:
            print('Error:  Wire width start value "' + optstr + '" is not numeric.')
            continue
        optstr = rangelist[1].replace('um','')
        try:
            wstop = float(optstr)
        except:
            print('Error:  Wire width end value "' + optstr + '" is not numeric.')
            continue
        optstr = rangelist[2].replace('um','')
        try:
            wstep = float(optstr)
        except:
            print('Error:  Wire width step value "' + optstr + '" is not numeric.')
            continue
        use_default_width = False
    elif tokens[0] == '-sep':
        rangelist = tokens[1].split(',')
        if len(rangelist) != 3:
            print('Error:  Separation needs three comma-separated values')
            usage()
            continue
        optstr = rangelist[0].replace('um','')
        try:
            sstart = float(optstr)
        except:
            print('Error:  Separation start value "' + optstr + '" is not numeric.')
            continue
        optstr = rangelist[1].replace('um','')
        try:
            sstop = float(optstr)
        except:
            print('Error:  Separation end value "' + optstr + '" is not numeric.')
            continue
        optstr = rangelist[2].replace('um','')
        try:
           sstep = float(optstr)
        except:
            print('Error:  Separation step value "' + optstr + '" is not numeric.')
            continue
        use_default_sep = False
    else:
        print('Error:  Unknown option "' + option + '"')
        usage()
        continue

#--------------------------------------------------------------
# 2. Obtain the metal stack.  The metal stack file is in the
#    format of executable python, so use exec().
#--------------------------------------------------------------

try:
    exec(open(arguments[0], 'r').read())
except:
    print('Error:  No metal stack file ' + arguments[0] + '!')
    sys.exit(1)

try:
    process
except:
    print('Warning:  Metal stack does not define process!')
    process = 'unknown'

try:
    layers
except:
    print('Error:  Metal stack does not define layers!')
    sys.exit(1)

try:
    limits
except:
    print('Error:  Metal stack does not define limits!')
    sys.exit(1)

#--------------------------------------------------------------
# 3. Generate files
#--------------------------------------------------------------

# "metals" is a reorganization of the full stack list to include
# just the metal layers and their heights and thicknesses.

metals = []
for lname, layer in layers.items():
    if layer[0] == 'm':
        metals.append(lname)

substrate = None
for lname, layer in layers.items():
    if layer[0] == 'd':
        substrate = lname
        break

# Check options

for metal in metallist.copy():
    if metal not in metals:
        print('Error:  Wire metal "' + metal + '" is not in the stackup!')
        metallist.remove(metal)

for metal in condlist.copy():
    if metal not in metals:
        print('Error:  Shield metal "' + metal + '" is not in the stackup!')
        condlist.remove(metal)

# Set default values if not specified in options

if metallist == []:
    print('Using all metals in stackup for set of wire types to test')
    metallist = metals

if condlist == []:
    print('Using all metals in stackup for set of shield types to test')
    condlist = metals

if verbose > 0:
    print('Simulation parameters:')
    print('   Wire width start = ' + str(wstart) + ', stop = ' + str(wstop) + ', step = ' + str(wstep))
    print('   Wire separation start = ' + str(sstart) + ', stop = ' + str(sstop) + ', step = ' + str(sstep))
    print('')

filelist = []

# Make sure the working directory exists
os.makedirs(process + '/fastercap_files/w1sh', exist_ok=True)

for metal in metallist:
    if use_default_width == True:
        minwidth = limits[metal][0]
        wstart = minwidth
        wstop = 10 * minwidth + 0.5 * minwidth
        wstep = 9 * minwidth

    if use_default_sep == True:
        minsep = limits[metal][1]
        sstart = -10 * minsep
        sstop = 10 * minsep + 0.5 * minsep
        sstep = minsep

    for conductor in condlist:

        # Only look at metal to different metal layers.
        if conductor == metal:
            continue

        # Generate the stack for this particular combination of
        # reference conductor and metal
        pstack = ordered_stack(substrate, [metal, conductor], layers)

        # (Diagnostic) Print out the stack
        if verbose > 0:
            print('Stackup for metal = ' + metal + ' coupling to metal ' + conductor + ':')
            for p in pstack:
                print(str(p))
            print('')

        for separation in numpy.arange(sstart, sstop, sstep):
            sspec = "{:.2f}".format(separation).replace('.', 'p').replace('-', 'n')
            for width in numpy.arange(wstart, wstop, wstep):
                wspec = "{:.2f}".format(width).replace('.', 'p').replace('-', 'n')
                filename = process + '/fastercap_files/w1sh/' + metal + '_' + conductor + '_w_' + wspec + '_ss_' + sspec + '.lst'
                generate_one_shielded_wire_file(filename, substrate, conductor, metal, width, separation, pstack)
                filelist.append(filename)

#--------------------------------------------------------------
# Routine for running FasterCap in thread
#--------------------------------------------------------------

def run_fastercap(file, tolerance):
    loctol = tolerance
    fastercapexec = '/home/tim/src/FasterCap_6.0.7/FasterCap'

    print('Running FasterCap on input file ' + file)
    done = False
    while not done:
        tolspec = "-a{:.3f}".format(loctol)
        try:
            proc = subprocess.run([fastercapexec, '-b', file, tolspec],
			stdin = subprocess.DEVNULL,
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE,
			universal_newlines = True,
                	timeout = 30)
        except subprocess.TimeoutExpired:
            if loctol > 0.1:
                print('ERROR:  Failing with high tolerance;  bailing.')
                break
            loctol *= 2
            if verbose > 0:
                print('Trying again with tolerance = ' + '{:.3f}'.format(loctol))
        else:
            done = True
            if loctol > 0.01:
                print('WARNING:  High tolerance value (' + tolspec + ') used.')

    if proc.stdout:
        if verbose > 1:
            print('Diagnostic output from FasterCap:')
        for line in proc.stdout.splitlines():
            if verbose > 1:
                print(line)
            if 'g1_' in line:
                g1line = line.split()
                g00 = float(g1line[1])
                g01 = float(g1line[2])
            elif 'g2_' in line:
                g2line = line.split()
                g10 = float(g2line[1])
                g11 = float(g2line[2])
    if proc.stderr:
        print('Error message output from FasterCap:')
        for line in proc.stderr.splitlines():
            print(line)
        if proc.returncode != 0:
            print('ERROR:  FasterCap exited with status ' + str(proc.returncode))

    elif done:
        msub = g00 + g01
        csub = g10 + g11
        ccoup = -(g01 + g10) / 2

        scoup = "{:.5g}".format(ccoup)
        smsub = "{:.5g}".format(msub)
        scsub = "{:.5g}".format(csub)
        print('Result:  Ccoup=' + scoup + '  Ccsub=' + scsub + '  Cmsub=' + smsub)

        # Add to results
        fileroot = os.path.splitext(file)[0]
        filename = os.path.split(fileroot)[-1]
        values = filename.split('_')
        metal = values[0]
        conductor = values[1]
        width = float(values[3].replace('p', '.').replace('n', '-'))
        sep = float(values[5].replace('p', '.').replace('n', '-'))
        return (metal, conductor, width, sep, msub, csub, ccoup)

    return None

#--------------------------------------------------------------
# 4. Simulate with fastercap
#--------------------------------------------------------------

presults = []
with multiprocessing.Pool() as pool:
    results = []
    for file in filelist:
        results.append(pool.apply_async(run_fastercap, (file, tolerance),))

    for result in results:
        presult = result.get(timeout=300)
        if presult:
            presults.append(presult)

#--------------------------------------------------------------
# 5. Save (and print) results
#--------------------------------------------------------------

if len(presults) == 0:
    print('No results to save or print.')
    sys.exit(0)

# Make sure the output directory exists
outdir = os.path.split(outfile)[0]
if outdir != '':
    os.makedirs(outdir, exist_ok=True)

print('Results:')
with open(outfile, 'w') as ofile:
    for presult in presults:
        metal = presult[0]
        conductor = presult[1]
        swidth = "{:.4f}".format(presult[2])
        ssep = "{:.4f}".format(presult[3])
        smsub = "{:.5g}".format(presult[4])
        scsub = "{:.5g}".format(presult[5])
        scoup = "{:.5g}".format(presult[6])
        print(metal + ' ' + conductor + ' ' + swidth + ' ' + ssep + ' ' + smsub + ' ' + scsub + ' ' + scoup, file=ofile)
        print(metal + ' ' + conductor + ' ' + swidth + ' ' + ssep + ' ' + smsub + ' ' + scsub + ' ' + scoup)

