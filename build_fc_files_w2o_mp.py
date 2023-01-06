#!/usr/bin/env python3
#
# build_fc_files_w2o_mp.py --
#
#	Create FasterCap files to simulate many different
#	geometries to capture all needed information for
#	parasitic capacitance modeling.  Version _w2o
#	generates output for two wires on different metal
#	layers.
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
from ordered_stack import ordered_2metal_stack
from generate_geometry import generate_two_offset_wire_file

#--------------------------------------------------------------
# Usage statement
#--------------------------------------------------------------

def usage():
    print('Usage:  build_fc_files_w2o_mp.py <stack_def_file> [options]')
    print('  Where [options] may be one or more of:')
    print('     -metal1=<metal>[,...] (restrict 1st wire type to one or more metals)')
    print('     -metal2=<metal>[,...] (restrict 2nd wire type to one or more metals)')
    print('     -sub[strate]=<substrate>      (substrate type)')
    print('     -width1=<start>,<stop>,<step> (1st wire width range, in microns)')
    print('     -width2=<start>,<stop>,<step> (2nd wire width range, in microns)')
    print('     -sep=<start>,<stop>,<step>    (separation range, in microns)')
    print('     -tol[erance]=<value>          (FasterCap tolerance)')
    print('     -file=<name>                  (output filename for results)')

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

metal1list = []
metal2list = []
use_default_width1 = True
w1start = 0
w1stop = 0
w1step = 0
use_default_width2 = True
w2start = 0
w2stop = 0
w2step = 0
use_default_sep = True
sstart = 0
sstop = 0
sstep = 0
substrate = None
outfile = 'results/w2o_results.txt'
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
    elif tokens[0] == '-metal1':
        metal1list = tokens[1].split(',')
    elif tokens[0] == '-metal2':
        metal2list = tokens[1].split(',')
    elif tokens[0] == '-sub' or tokens[0] == '-substrate':
        subname = tokens[1]
    elif tokens[0] == '-width1':
        rangelist = tokens[1].split(',')
        if len(rangelist) != 3:
            print('Error:  1st wire width needs three comma-separated values')
            usage()
            continue
        optstr = rangelist[0].replace('um','')
        try:
            w1start = float(optstr)
        except:
            print('Error:  1st wire width start value "' + optstr + '" is not numeric.')
            continue
        optstr = rangelist[1].replace('um','')
        try:
            w1stop = float(optstr)
        except:
            print('Error:  1st wire width end value "' + optstr + '" is not numeric.')
            continue
        optstr = rangelist[2].replace('um','')
        try:
            w1step = float(optstr)
        except:
            print('Error:  1st wire width step value "' + optstr + '" is not numeric.')
            continue
        use_default_width = False
    elif tokens[0] == '-width2':
        rangelist = tokens[1].split(',')
        if len(rangelist) != 3:
            print('Error:  2nd wire width needs three comma-separated values')
            usage()
            continue
        optstr = rangelist[0].replace('um','')
        try:
            w2start = float(optstr)
        except:
            print('Error:  2nd wire width start value "' + optstr + '" is not numeric.')
            continue
        optstr = rangelist[1].replace('um','')
        try:
            w2stop = float(optstr)
        except:
            print('Error:  2nd wire width end value "' + optstr + '" is not numeric.')
            continue
        optstr = rangelist[2].replace('um','')
        try:
            w2step = float(optstr)
        except:
            print('Error:  2nd wire width step value "' + optstr + '" is not numeric.')
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
    print('Error:  Metal stack does not define process!')
    sys.exit(1)

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

for metal1 in metal1list.copy():
    if metal1 not in metals:
        print('Error:  1st wire metal "' + metal1 + '" is not in the stackup!')
        metal1list.remove(metal1)

for metal2 in metal2list.copy():
    if metal2 not in metals:
        print('Error:  2nd wire metal "' + metal2 + '" is not in the stackup!')
        metal2list.remove(metal2)

# Set default values if not specified in options

if metal1list == []:
    print('Using all metals in stackup for 1st set of wire types to test')
    metal1list = metals

if metal2list == []:
    print('Using all metals in stackup for 2nd set of wire types to test')
    metal2list = metals

if verbose > 0:
    print('Simulation parameters:')
    print('   1st wire width start = ' + str(w1start) + ', stop = ' + str(w1stop) + ', step = ' + str(w1step))
    print('   2nd wire width start = ' + str(w2start) + ', stop = ' + str(w2stop) + ', step = ' + str(w2step))
    print('   Wire separation start = ' + str(sstart) + ', stop = ' + str(sstop) + ', step = ' + str(sstep))
    print('')

filelist = []
for metal1 in metals:
    if use_default_width1 == True:
        min1width = limits[metal1][0]
        w1start = min1width
        w1stop = 10 * min1width + 0.5 * min1width
        w1step = 9 * min1width

    if use_default_sep == True:
        minsep = limits[metal1][1]
        sstart = -10 * minsep
        sstop = 10 * minsep + 0.5 * minsep
        sstep = minsep

    metals_above = []
    for lname, layer in layers.items():
        if layer[0] == 'm':
            if lname == metal1:
                break
            else:
                metals_above.append(lname)

    for metal2 in metals_above:
        if use_default_width1 == True:
            min2width = limits[metal2][0]
            w2start = min2width
            w2stop = 10 * min2width + 0.5 * min2width
            w2step = 9 * min2width

        # Generate the stack for this particular combination of
        # reference conductor and metal
        pstack = ordered_2metal_stack(substrate, metal1, metal2, layers)

        # (Diagnostic) Print out the stack
        if vebose > 0:
            print('Stackup for metal = ' + metal1 + ' coupling to metal ' + metal2 + ':')
            for p in pstack:
                print(str(p))
            print('')

        for separation in numpy.arange(sstart, sstop, sstep):
            sspec = "{:.2f}".format(separation).replace('.', 'p').replace('-', 'n')
            for width1 in numpy.arange(w1start, w1stop, w1step):
                w1spec = "{:.2f}".format(width1).replace('.', 'p').replace('-', 'n')
                for width2 in numpy.arange(w2start, w2stop, w2step):
                    w2spec = "{:.2f}".format(width2).replace('.', 'p').replace('-', 'n')
                    filename = 'fastercap_files/w2o/' + metal1 + '_w_' + w1spec + '_' + metal2 + '_w_' + w2spec + '_s_' + sspec + '.lst'
                    generate_two_offset_wire_file(filename, substrate, metal1, width1, metal2, width2, separation, pstack)
                    filelist.append(filename)

#--------------------------------------------------------------
# Routine to run FasterCap in thread
#--------------------------------------------------------------

def run_fastercap(file, tolerance):
    fastercapexec = '/home/tim/src/FasterCap_6.0.7/FasterCap'

    tolspec = "-a{:.3f}".format(tolerance)

    print('Running FasterCap on input file ' + file)
    try:
        proc = subprocess.run([fastercapexec, '-b', file, tolspec],
		stdin = subprocess.DEVNULL,
		stdout = subprocess.PIPE,
		stderr = subprocess.PIPE,
		universal_newlines = True,
                timeout = 30)
    except subprocess.TimeoutExpired:
        # Ignore this result
        pass
    else:
        if proc.stdout:
            for line in proc.stdout.splitlines():
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

        else:
            m1sub = g00 + g01
            m2sub = g10 + g11
            ccoup = -(g01 + g10) / 2

            scoup = "{:.5g}".format(ccoup)
            sm1sub = "{:.5g}".format(m1sub)
            sm2sub = "{:.5g}".format(m2sub)
            print('Result:  Ccoup=' + scoup + '  Cm1sub=' + sm1sub + '  Cm2sub=' + sm2sub)

            # Add to results
            fileroot = os.path.splitext(file)[0]
            filename = os.path.split(fileroot)[-1]
            values = filename.split('_')
            metal1 = values[0]
            width1 = float(values[2].replace('p', '.').replace('n', '-'))
            metal2 = values[3]
            width2 = float(values[5].replace('p', '.').replace('n', '-'))
            sep = float(values[7].replace('p', '.').replace('n', '-'))
            return (metal1, metal2, width1, width2, sep, m1sub, m2sub, ccoup)

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
os.makedirs(os.path.split(outfile)[0], exist_ok=True)

print('Results:')
with open(outfile, 'w') as ofile:
    for presult in presults:
        metal1 = presult[0]
        metal2 = presult[1]
        s1width = "{:.4f}".format(presult[2])
        s2width = "{:.4f}".format(presult[3])
        ssep = "{:.4f}".format(presult[4])
        sm1sub = "{:.5g}".format(presult[5])
        sm2sub = "{:.5g}".format(presult[6])
        scoup = "{:.5g}".format(presult[7])
        print(metal1 + ' ' + metal2 + ' ' + s1width + ' ' + s2width + ' ' + ssep + ' ' + sm1sub + ' ' + sm2sub + ' ' + scoup, file=ofile)
        print(metal1 + ' ' + metal2 + ' ' + s1width + ' ' + s2width + ' ' + ssep + ' ' + sm1sub + ' ' + sm2sub + ' ' + scoup)

