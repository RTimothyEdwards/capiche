#!/usr/bin/env python3
#
# build_mag_files_w2.py --
#
#	Create magic Tcl scripts to generate many different
#	geometries to capture information for verifying
#	parasitic capacitance modeling.  Version _w1sh
#	generates output for a single wire on a metal
#	layer, with a shield plane underneath (or over top).
#
# Written by Tim Edwards
# January 5, 2023
#
import os
import sys
import numpy
import subprocess

#---------------------------------------------------
# Usage statement
#---------------------------------------------------

def usage():
    print('Usage:  build_mag_files_w1sh.py <stack_def_file> <magic_startup_script> [options]')
    print('  Where [options] may be one or more of:')
    print('     -metals=<metal>[,...]  (restrict wire type to one or more metals)')
    print('     -shields=<metal>[,...]  (restrict shield type to one or more metals)')
    print('     -sub[strate]=<substrate>[,...] (restrict substrate type)')
    print('     -width=<start>,<stop>,<step> (wire width range, in microns)')
    print('     -sep=<start>,<stop>,<step>   (separation range, in microns)')
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

if len(arguments) != 2:
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
    elif tokens[0] == '-metals':
        metallist = tokens[1].split(',')
    elif tokens[0] == '-shields':
        condlist = tokens[1].split(',')
    elif tokens[0].startswith('-sub'):
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

try:
    magiclayers
except:
    print('Error:  Metal stack does not define magiclayers!')
    sys.exit(1)

#--------------------------------------------------------------
# 3. Obtain the technology file
#--------------------------------------------------------------

if not os.path.isfile(arguments[1]):
    print('Error:  Cannot find technology startup script ' + arguments[1] + '!')
    sys.exit(1)
else:
    startupscript = arguments[1]

#--------------------------------------------------------------
# 4. Generate files
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

for conductor in condlist.copy():
    if conductor not in metals:
        print('Error:  Shield metal "' + conductor + '" is not in the stackup!')
        condlist.remove(conductor)

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
for metal in metallist:
    mmetal = magiclayers[metal]
    msubs = magiclayers[substrate]

    if use_default_width == True:
        minwidth = limits[metal][0]
        wstart = minwidth
        wstop = 10 * minwidth + 0.5 * minwidth
        wstep = 9 * minwidth

    if use_default_sep == True:
        minsep = limits[metal][1]
        sstart = -10 * minsep
        sstop = 10 * minsep + 0.5 * minsep
        sstep =  minsep

    for conductor in condlist:

        # Only look at metal to different metal layers.
        if conductor == metal:
            continue

        mcond = magiclayers[conductor]
        for separation in numpy.arange(sstart, sstop, sstep):
            sspec = "{:.2f}".format(separation).replace('.', 'p').replace('-', 'n')
            for width in numpy.arange(wstart, wstop, wstep):
                xspec1 = "{:.2f}".format(width / 2)
                xspec2 = "{:.2f}".format(-separation)
                wspec = "{:.2f}".format(width).replace('.', 'p')
                filename = 'magic_files/w1sh/' + metal + '_' + conductor + '_w_' + wspec + '_s_' + sspec + '.tcl'
                with open(filename, 'w') as ofile:
                    print('load test', file=ofile)
                    print('box values -' + xspec1 + 'um 0 ' + xspec1 + 'um 1000um', file=ofile)
                    print('paint ' + mmetal, file=ofile)
                    print('label A c ' + mmetal, file=ofile)
                    print('box values -60um -40um ' + xspec2 + 'um 1040um', file=ofile)
                    print('paint ' + mcond, file=ofile)
                    print('box values -50um -20um -50um -20um', file=ofile)
                    print('label B c ' + mcond, file=ofile)
                    print('box values -60um -40um 60um 1040um', file=ofile)
                    print('paint ' + msubs, file=ofile)
                    print('box values 50um -20um 50um -20um', file=ofile)
                    print('label D c ' + msubs, file=ofile)
                    print('extract all', file=ofile)
                    print('ext2spice lvs', file=ofile)
                    print('ext2spice cthresh 0', file=ofile)
                    print('ext2spice', file=ofile)
                    print('quit -noprompt', file=ofile)
  
                filelist.append(filename)

#--------------------------------------------------------------
# 4. Run magic and extract
#--------------------------------------------------------------

# Magic is assumed to be in the executable path list
magicexec = 'magic'

presults = []

for file in filelist:
    print('Running Magic on input file ' + file)
    try:
        proc = subprocess.run(['magic', '-dnull', '-noconsole', '-rcfile', startupscript, file],
		stdin = subprocess.DEVNULL,
		stdout = subprocess.PIPE,
		stderr = subprocess.PIPE,
		universal_newlines = True,
                timeout = 30)
    except subprocess.TimeoutExpired:
        # Just ignore this result
        pass
    else:
        # Remove the .ext file
        os.remove('test.ext')
        # When outside of the halo, values will be missing, so assumed zero
        csub = 0.0
        msub = 0.0
        ccoup = 0.0
        # Read output SPICE file
        with open('test.spice', 'r') as ifile:
            spicelines = ifile.read().splitlines()
            for line in spicelines:
                if line.startswith('C'):
                    if 'A B' in line or 'B A' in line:
                        tokens = line.split()
                        ccoup = 1e-9 * float(tokens[3].replace('f', '').replace('F', '')) / 1000
                    if 'A D' in line or 'D A' in line:
                        tokens = line.split()
                        msub = 1e-9 * float(tokens[3].replace('f', '').replace('F', '')) / 1000
                    if 'B D' in line or 'D B' in line:
                        tokens = line.split()
                        csub = 1e-9 * float(tokens[3].replace('f', '').replace('F', '')) / 1080
                    

        # Remove the SPICE file
        os.remove('test.spice')

        sccoup = "{:.2f}".format(ccoup)
        smsub = "{:.2f}".format(msub)
        scsub = "{:.2f}".format(csub)
        print('Result:  Ccoup=' + sccoup + '  Csub=' + scsub + '  Cmsub=' + smsub)

        # Add to results
        fileroot = os.path.splitext(file)[0]
        filename = os.path.split(fileroot)[-1]
        values = filename.split('_')
        metal = values[0]
        conductor = values[1]
        width = float(values[3].replace('p', '.'))
        sep = float(values[5].replace('p', '.').replace('n', '-'))
        presults.append([metal, conductor, width, sep, msub, csub, ccoup])

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
        metal = presult[0]
        conductor = presult[1]
        swidth = "{:.4f}".format(presult[2])
        ssep = "{:.4f}".format(presult[3])
        smsub = "{:.5g}".format(presult[4])
        scsub = "{:.5g}".format(presult[5])
        scoup = "{:.5g}".format(presult[6])
        print(metal + ' ' + conductor + ' ' + swidth + ' ' + ssep + ' ' + smsub + ' ' + scsub + ' ' + scoup, file=ofile)
        print(metal + ' ' + conductor + ' ' + swidth + ' ' + ssep + ' ' + smsub + ' ' + scsub + ' ' + scoup)

