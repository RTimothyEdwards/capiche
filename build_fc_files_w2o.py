#!/usr/bin/env python3
#
# build_fc_files_w2o.py --
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

# Local files
from ordered_stack import ordered_stack
from generate_geometry import generate_two_offset_wire_file

#--------------------------------------------------------------
# Usage statement
#--------------------------------------------------------------

def usage():
    print('Usage:  build_fc_files_w2o.py <stack_def_file> [options]')
    print('  Where [options] may be one or more of:')
    print('     -metal1=<metal>[,...] (restrict 1st wire type to one or more metals)')
    print('     -metal2=<metal>[,...] (restrict 2nd wire type to one or more metals)')
    print('     -sub[strate]=<substrate>      (substrate type)')
    print('     -width1=<start>,<stop>,<step> (1st wire width range, in microns)')
    print('     -width2=<start>,<stop>,<step> (2nd wire width range, in microns)')
    print('     -sep=<start>,<stop>,<step>    (separation range, in microns)')
    print('     -tol[erance]=<value>          (FasterCap tolerance)')
    print('     -file=<name>                  (output filename for results)')

#--------------------------------------------------------------
# The main routine
#
# build_fc_files_w2o(stackupfile, metal1list, metal2list,
#       widths1, widths2, seps, outfile, tolerance, verbose):
#
# where:
#       stackupfile = name of the script file with the metal
#               stack definition
#       metal1list = 1st list of metals to test as wires
#       metal2list = 2nd list of metals to test as wires
#       widths1 = list with 1st metal wire widths to test
#       widths2 = list with 2nd metal wire widths to test
#       seps = list with wire1-to-wire2 separations to test
#       outfile = name of output file with results
#       tolerance = initial tolerance to use for FasterCap
#       verbose = diagnostic output level
#--------------------------------------------------------------

def build_fc_files_w2o(stackupfile, metal1list, metal2list, widths1, widths2, seps, outfile, tolerance, verbose=0):

    use_default_width1 = True if not widths1 else False
    use_default_width2 = True if not widths2 else False
    use_default_sep = True if not seps else False

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
        print('   1st wire widths = ' + str(widths1))
        print('   2nd wire widths = ' + str(widths1))
        print('   Wire separations = ' + str(seps))
        print('')

    filelist = []

    # Make sure the working directory exists
    os.makedirs(process + '/fastercap_files/w2o', exist_ok=True)

    for metal1 in metal1list:
        if use_default_width1 == True:
            min1width = limits[metal1][0]
            w1start = min1width
            w1stop = 10 * min1width + 0.5 * min1width
            w1step = 9 * min1width
            widths1 = list(numpy.arange(w1start, w1stop, w1step))

        if use_default_sep == True:
            minsep = limits[metal1][1]
            sstart = -10 * minsep
            sstop = 10 * minsep + 0.5 * minsep
            sstep = minsep
            seps = list(numpy.arange(sstart, sstop, sstep))

        for metal2 in metal2list:
            if use_default_width2 == True:
                min2width = limits[metal2][0]
                w2start = min2width
                w2stop = 10 * min2width + 0.5 * min2width
                w2step = 9 * min2width
                widths2 = list(numpy.arange(w2start, w2stop, w2step))

            # Generate the stack for this particular combination of
            # reference conductor and metal
            pstack = ordered_stack(substrate, [metal1, metal2], layers)

            # (Diagnostic) Print out the stack
            if verbose > 1:
                print('Stackup for metal = ' + metal1 + ' coupling to metal ' + metal2 + ':')
                for p in pstack:
                    print(str(p))
                print('')

            for separation in seps:
                sspec = "{:.2f}".format(separation).replace('.', 'p').replace('-', 'n')
                for width1 in widths1:
                    w1spec = "{:.2f}".format(width1).replace('.', 'p').replace('-', 'n')
                    for width2 in widths2:
                        w2spec = "{:.2f}".format(width2).replace('.', 'p').replace('-', 'n')
                        filename = process + '/fastercap_files/w2o/' + metal1 + '_w_' + w1spec + '_' + metal2 + '_w_' + w2spec + '_s_' + sspec + '.lst'
                        generate_two_offset_wire_file(filename, substrate, metal1, width1, metal2, width2, separation, pstack)
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
            m1sub = g00 + g01
            m2sub = g10 + g11
            # ccoup = -(g01 + g10) / 2
            ccoup = -g10

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
            presults.append([metal1, metal2, width1, width2, sep, m1sub, m2sub, ccoup])

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
                metal1 = presult[0]
                metal2 = presult[1]
                s1width = "{:.4f}".format(presult[2])
                s2width = "{:.4f}".format(presult[3])
                ssep = "{:.4f}".format(presult[4])
                sm1sub = "{:.5g}".format(presult[5])
                sm2sub = "{:.5g}".format(presult[6])
                scoup = "{:.5g}".format(presult[7])
                print(metal1 + ' ' + metal2 + ' ' + s1width + ' ' + s2width + ' ' + ssep + ' ' + sm1sub + ' ' + sm2sub + ' ' + scoup, file=ofile)

    # Also print results to the terminal
    print('Results:')
    for presult in presults:
        metal1 = presult[0]
        metal2 = presult[1]
        s1width = "{:.4f}".format(presult[2])
        s2width = "{:.4f}".format(presult[3])
        ssep = "{:.4f}".format(presult[4])
        sm1sub = "{:.5g}".format(presult[5])
        sm2sub = "{:.5g}".format(presult[6])
        scoup = "{:.5g}".format(presult[7])
        print(metal1 + ' ' + metal2 + ' ' + s1width + ' ' + s2width + ' ' + ssep + ' ' + sm1sub + ' ' + sm2sub + ' ' + scoup)

    return 0

#---------------------------------------------------
#  Invoke build_fc_files_w2o.py as an application
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
            use_default_width1 = False
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
            use_default_width2 = False
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

    # Call the main routine

    if use_default_width1:
        widths1 = None
    else:
        widths1 = list(numpy.arange(w1start, w1stop, w1step))

    if use_default_width2:
        widths2 = None
    else:
        widths2 = list(numpy.arange(w2start, w2stop, w2step))

    if use_default_sep:
        seps = None
    else:
        seps = list(numpy.arange(sstart, sstop, sstep))

    rval = build_fc_files_w2(arguments[0], metal1list, metal2list, widths1, widths2, seps, outfile, tolerance, verbose)
    sys.exit(rval)

