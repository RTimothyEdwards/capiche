#!/usr/bin/env python3
#
# build_fc_files_w1n.py --
#
#	Create FasterCap files to simulate many different
#	geometries to capture all needed information for
#	parasitic capacitance modeling.  Version _w1n
#	represents a single wire over substrate and under
#	another wire of effectively infinite width, used
#	to measure the total upward fringe capacitance.
#
# Written by Tim Edwards
# December 23, 2022
#
import os
import sys
import numpy
import subprocess

# Local files
from ordered_stack import ordered_stack
from generate_geometry import generate_1wire_2plane_file

#--------------------------------------------------------------
# Usage statement
#--------------------------------------------------------------

def usage():
    print('Usage:  build_fc_files_w1n.py <stack_def_file> [options]')
    print('  Where [options] may be one or more of:')
    print('     -metals=<metal>[,...]    (restrict wire type to one or more metals)')
    print('     -shields=<metal>[,...]   (restrict shield type to one or more metals)')
    print('     -sub[strate]=<substrate> (substrate type)')
    print('     -width=<start>,<stop>,<step> (wire width range, in microns)')
    print('     -tol[erance]=<value>         (FasterCap tolerance)')
    print('     -file=<name>                 (output filename for results)')

#--------------------------------------------------------------
# The main routine
#
# build_fc_files_w1n(stackupfile, metallist, condlist, widths,
#       outfile, tolerance, verbose):
#
# where:
#       stackupfile = name of the script file with the metal
#               stack definition
#       metallist = list of metals to test as wires
#       condlist = list of conductors/substrates to test
#       widths = list with wire widths to test
#       outfile = name of output file with results
#       tolerance = initial tolerance to use for FasterCap
#       verbose = diagnostic output level
#--------------------------------------------------------------

def build_fc_files_w1n(stackupfile, metallist, condlist, widths, outfile, tolerance, verbose=0):

    use_default_width = True if not widths else False

    #--------------------------------------------------------------
    # Obtain the metal stack.  The metal stack file is in the
    # format of executable python, so use exec().
    #--------------------------------------------------------------

    try:
        locals = {}
        exec(open(stackupfile, 'r').read(), None, locals)
    except:
        print('Error:  No metal stack file ' + stackupfile + '!')
        return 1

    try:
        process = locals['process']
    except:
        print('Warning:  Metal stack does not define process!')
        process = 'unknown'

    try:
        layers = locals['layers']
    except:
        print('Error:  Metal stack does not define layers!')
        return 1

    try:
        limits = locals['limits']
    except:
        print('Error:  Metal stack does not define limits!')
        return 1

    #--------------------------------------------------------------
    # Generate files
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
            # Use only the first defined substrate---this is unimportant
            # to the calculation of capacitance between metals.
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
        print('Using all metals (except topmost) in stackup for set of wire types to test')
        metallist = metals[:-1]

    if condlist == []:
        print('Using all metals in stackup for set of shield types to test')
        condlist = metals

    if verbose > 0:
        print('Simulation parameters:')
        print('   Wire widths = ' + str(widths))
        print('')

    filelist = []

    # Make sure the working directory exists
    os.makedirs(process + '/fastercap_files/w1n', exist_ok=True)

    # Since this calculation is for fringing fields from a wire upward
    # to a layer above, do this only for metals up to but not including
    # the topmost metal.

    for metal in metallist:
        if use_default_width == True:
            minwidth = limits[metal][0]
            wstart = minwidth
            wstop = 10 * minwidth + 0.5 * minwidth
            wstep = 9 * minwidth
            widths = list(numpy.arange(wstart, wstop, wstep))

        # "conductors" in this file represents the metal above the
        # wire structure under test, so reverse the layers and
        # enumerate all of the metals above this one.
        if condlist == []:
            conductors = []
            for lname, layer in reversed(layers.items()):
                if lname == metal:
                    break
                elif layer[0] == 'm':
                    conductors.append(lname)
        else:
            conductors = condlist

        for conductor in conductors:
            # Generate the stack for this particular combination of
            # reference conductor and metal
            pstack = ordered_stack(substrate, [metal, conductor], layers)

            # (Diagnostic) Print out the stack
            if verbose > 1:
                print('Stackup for metal = ' + metal + ' and reference ' + conductor + ':')
                for p in pstack:
                    print(str(p))
                print('')

            for width in widths:
                wspec = "{:.2f}".format(width).replace('.', 'p')
                filename = process + '/fastercap_files/w1n/' + metal + '_' + conductor + '_w_' + wspec + '.lst'
                generate_1wire_2plane_file(filename, substrate, conductor, metal, width, pstack)
                filelist.append(filename)

    #--------------------------------------------------------------
    # Simulate with fastercap
    #--------------------------------------------------------------

    fastercapexec = os.getenv('FASTERCAP_EXEC')
    if not fastercapexec:
        fastercapexec = 'FasterCap'

    presults = []

    for file in filelist:
        loctol = tolerance
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
            # Note:  Where g01 != g10, use the average value.
            # ccoup = -(g01 + g10) / 2.0
            ccoup = -g10
            scoup = "{:.5g}".format(ccoup)
            print('Result:  Ccoup=' + scoup)

            # Add to results
            fileroot = os.path.splitext(file)[0]
            filename = os.path.split(fileroot)[-1]
            values = filename.split('_')
            metal = values[0]
            conductor = values[1]
            width = float(values[3].replace('p', '.'))
            presults.append([metal, conductor, width, ccoup])

    #--------------------------------------------------------------
    # Save (and print) results
    #--------------------------------------------------------------

    if len(presults) == 0:
        print('No results to save or print.')
        return 0

    if outfile:
        # Make sure the output directory exists
        outdir = os.path.split(outfile)[0]
        if outdir != '':
            os.makedirs(outdir, exist_ok=True)

        with open(outfile, 'w') as ofile:
            for presult in presults:
                metal = presult[0]
                conductor = presult[1]
                swidth = "{:.4f}".format(presult[2])
                scoup = "{:.5g}".format(presult[3])
                print(metal + ' ' + conductor + ' ' + swidth + ' ' + scoup, file=ofile)

    # Also print results to the terminal
    print('Results:')
    for presult in presults:
        metal = presult[0]
        conductor = presult[1]
        swidth = "{:.4f}".format(presult[2])
        scoup = "{:.5g}".format(presult[3])
        print(metal + ' ' + conductor + ' ' + swidth + ' ' + scoup)

    return 0

#---------------------------------------------------
# Invoke build_fc_files_w1n.py as an application
#---------------------------------------------------

if __name__ == '__main__':

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
    substrate = None
    outfile = None
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
        else:
            print('Error:  Unknown option "' + option + '"')
            usage()
            continue

    # Call the main routine

    if use_default_width:
        widths = None
    else:
        widths = list(numpy.arange(wstart, wstop, wstep))

    rval = build_fc_files_w1n(arguments[0], metallist, condlist, widths, outfile, tolerance, verbose)
    sys.exit(rval)

