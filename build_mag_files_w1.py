#!/usr/bin/env python3
#
# build_mag_files_w1.py --
#
#	Create magic Tcl scripts to generate many different
#	geometries to capture information for verifying
#	parasitic capacitance modeling.  Version _w1
#	represents a single wire over substrate with no
# 	shielding (used as a baseline measurement against
#	the values computed from version _w2).
#
# Written by Tim Edwards
# December 27, 2022
#
import os
import sys
import numpy
import subprocess

#---------------------------------------------------
# Usage statement
#---------------------------------------------------

def usage():
    print('Usage:  build_mag_files_w1.py <stack_def_file> <magic_startup_script> [options]')
    print('  Where [options] may be one or more of:')
    print('     -metals=<metal>[,...]  (restrict wire type to one or more metals)')
    print('     -conductors=<conductor>[,...] (restrict conductor type to one or more types)')
    print('     -width=<start>,<stop>,<step> (wire width range, in microns)')
    print('     -file=<name>                 (output filename for results)')

#--------------------------------------------------------------
# The main routine
#
# build_mag_files_w1(stackupfile, startupscript, metallist, condlist, widths,
#       outfile, verbose):
#
# where:
#       stackupfile = name of the script file with the metal
#               stack definition
#	startupscript = name of the magic startup script
#       metallist = list of metals to test as wires
#       condlist = list of conductors/substrates to test
#       widths = list with wire widths to test
#       outfile = name of output file with results
#       verbose = diagnostic output level
#--------------------------------------------------------------

def build_mag_files_w1(stackupfile, startupscript, metallist, condlist, widths, outfile, verbose=0):

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

    try:
        magiclayers = locals['magiclayers']
    except:
        print('Error:  Metal stack does not define magiclayers!')
        return 1

    #--------------------------------------------------------------
    # Obtain the technology file
    #--------------------------------------------------------------

    if startupscript and startupscript != '':
        if not os.path.isfile(startupscript):
            print('Error:  Cannot find technology startup script ' + startupscript + '!')
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

    substrates = []
    for lname, layer in layers.items():
        if layer[0] == 'd':
            substrates.append(lname)

    # Check options

    for metal in metallist.copy():
        if metal not in metals:
            print('Error:  Wire metal "' + metal + '" is not in the stackup!')
            metallist.remove(metal)

    for conductor in condlist.copy():
        if conductor not in substrates and conductor not in metals:
            print('Error:  Conductor type "' + conductor + '" is not in the stackup!')
            condlist.remove(conductor)

    # Set default values if not specified in options

    if metallist == []:
        print('Using all metals in stackup for set of wire types to test')
        metallist = metals

    if condlist == []:
        print('Using all substrates and metals in stackup for set of substrate types to test')
        condlist = substrates.copy()

    if verbose > 0:
        print('Simulation parameters:')
        print('   Wire widths = ' + str(widths))
        print('')

    filelist = []

    # Make sure the output directory exists
    os.makedirs(process + '/magic_files/w1', exist_ok=True)

    for metal in metallist:
        mmetal = magiclayers[metal]

        if condlist == []:
            conductors = substrates.copy()
            for lname, layer in layers.items():
                if lname == metal:
                    break
                elif layer[0] == 'm':
                    conductors.append(lname)
        else:
            # Note:  This may need to be restircted
            conductors = condlist.copy()

        if use_default_width == True:
            minwidth = limits[metal][0]
            wstart = minwidth
            wstop = 10 * minwidth + 0.5 * minwidth
            wstep = 9 * minwidth
            widths = list(numpy.arange(wstart, wstop, wstep))

        for conductor in conductors:
            # Poly to diff is a transistor gate and is not a parasitic.
            if 'poly' in metal and 'diff' in conductor:
                continue

            mcond = magiclayers[conductor]
            for width in widths:
                wspec = "{:.2f}".format(width)
                wsspec = "{:.2f}".format(width).replace('.', 'p')
                filename = process + '/magic_files/w1/' + metal + '_' + conductor + '_w_' + wsspec + '.tcl'
                with open(filename, 'w') as ofile:
                    print('load test -silent', file=ofile)
                    print('box values 0 0 ' + wspec + 'um 1000um', file=ofile)
                    print('paint ' + mmetal, file=ofile)
                    print('label A c ' + mmetal, file=ofile)
                    print('box values -40um -40um 40um 1040um', file=ofile)
                    print('paint ' + mcond, file=ofile)
                    print('box values -20um -20um -20um -20um', file=ofile)
                    print('label B c ' + mcond, file=ofile)
                    print('catch {extract halo 50um}', file=ofile)
                    print('extract all', file=ofile)
                    print('ext2spice lvs', file=ofile)
                    print('ext2spice cthresh 0', file=ofile)
                    print('ext2spice', file=ofile)
                    print('quit -noprompt', file=ofile)
  
                filelist.append(filename)

    #--------------------------------------------------------------
    # Run magic and extract
    #--------------------------------------------------------------

    if not startupscript or startupscript == '':
        return 0

    # Magic is assumed to be in the executable path list
    magicexec = os.getenv('MAGIC_EXEC')
    if not magicexec:
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
            # Read output SPICE file
            csub = 0.0
            with open('test.spice', 'r') as ifile:
                spicelines = ifile.read().splitlines()
                for line in spicelines:
                    if line.startswith('C'):
                        if 'A B' in line or 'B A' in line:
                            tokens = line.split()
                            csub = 1e-9 * float(tokens[3].replace('f', '').replace('F', '')) / 1000
                    

            # Remove the SPICE file
            os.remove('test.spice')

            scsub = "{:.5g}".format(csub)
            print('Result:  Csub=' + scsub)

            # Add to results
            fileroot = os.path.splitext(file)[0]
            filename = os.path.split(fileroot)[-1]
            values = filename.split('_')
            metal = values[0]
            conductor = values[1]
            width = float(values[3].replace('p', '.'))
            presults.append([metal, conductor, width, csub])

    #--------------------------------------------------------------
    # Save (and print) results
    #--------------------------------------------------------------

    if len(presults) == 0:
        print('No results to save or print.')
        return 0

    if outfile:
        # Make sure the output directory exists
        os.makedirs(os.path.split(outfile)[0], exist_ok=True)

        with open(outfile, 'w') as ofile:
            for presult in presults:
                metal = presult[0]
                conductor = presult[1]
                swidth = "{:.4f}".format(presult[2])
                ssub = "{:.5g}".format(presult[3])
                print(metal + ' ' + conductor + ' ' + swidth + ' ' + ssub, file=ofile)

    # Also print results to the terminal
    print('Results:')
    for presult in presults:
        metal = presult[0]
        conductor = presult[1]
        swidth = "{:.4f}".format(presult[2])
        ssub = "{:.5g}".format(presult[3])
        print(metal + ' ' + conductor + ' ' + swidth + ' ' + ssub)

    return 0

#---------------------------------------------------
# Invoke build_mag_files_w1.py as an application
#---------------------------------------------------

if __name__ == '__main__':

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
    outfile = None
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
        elif tokens[0] == '-conductors':
            condlist = tokens[1].split(',')
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

    rval = build_mag_files_w1(arguments[0], arguments[1], metallist, condlist, widths, outfile, verbose)
    sys.exit(rval)
