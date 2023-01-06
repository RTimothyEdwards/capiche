#!/usr/bin/env python3
#
# calc_parallel.py --
#
#	Calculate the parallel plate capacitance
#	for each conductor layer to each substrate
#	type, for the indicated metal stackup file.
#
# Written by Tim Edwards
# December 22, 2022
#
import os
import sys
import numpy
import subprocess

# Local files
from ordered_stack import ordered_stack

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
    print('Usage:  calc_parallel.py <stack_def_file> [-file=<file>]')
    sys.exit(1)

verbose = 0
outfile = 'results/areacap_results.txt'

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
# Run calculations
#--------------------------------------------------------------

metals = []
for lname, layer in layers.items():
    if layer[0] == 'm':
        metals.append(lname)

substrates = []
for lname, layer in layers.items():
    if layer[0] == 'd':
        substrates.append(lname)

presults = []

for metal in metals:
    conductors = substrates.copy()
    for lname, layer in layers.items():
        if lname == metal:
            break
        elif layer[0] == 'm':
            conductors.append(lname)

    for conductor in conductors:
        
        # Poly to diff is a transistor gate and is not a parasitic.
        if 'poly' in metal and 'diff' in conductor:
            continue

        # Generate the stack for this particular combination of
        # reference conductor and metal
        pstack = ordered_stack(conductor, metal, layers)

        if verbose > 0:
            print('Calculating for metal = ' + metal + ' and reference ' + conductor + ':')

        # (Diagnostic) Print out the stack
        if verbose > 0:
            print('Stackup for metal = ' + metal + ' and reference ' + conductor + ':')
            for p in pstack:
                print(str(p))
            print('')

        # Calculate the partial capacitances for the dielectric stack

        # Find the metal layer;  all layers above will be ignored.

        parcaps = []

        for index in range(0, len(pstack)):
            layer = pstack[index]
            if layer[1] == 'm':
                mlayer = index
                break

        for index in range(mlayer + 1, len(pstack) - 1):
            layer = pstack[index]
            layer_below = pstack[index + 1]
            if layer[1] == 'k' or layer[1] == 'c':
                kvalue = layer[5]
                thickness = layer[2] - layer_below[2]
                C = 8.854 * kvalue / thickness
                parcaps.append(C)

                # (More diagnostic)
                if verbose > 0:
                    print('Layer ' + layer[0] + ' thickness=' + str(thickness) + ' K=' + str(kvalue))
                    print('Partial capacitance = ' + str(C))

        invcaptotal = 0
        for cap in parcaps:
            invcaptotal += (1.0 / cap)

        captotal = 1.0 / invcaptotal
        presults.append([metal, conductor, captotal])

#--------------------------------------------------------------
# 6. Save (and print) results
#--------------------------------------------------------------

# Make sure the output directory exists
os.mkdir(os.path.split(outfile)[0])

print('\nParallel plate capacitance (values in aF/um^2)')
print('Results:')
with open(outfile, 'w') as ofile:
    for presult in presults:
        metal = presult[0]
        conductor = presult[1]
        areacap = "{:.5g}".format(presult[2])
        print(metal + ' ' + conductor + ' ' + areacap, file=ofile)
        print(metal + ' ' + conductor + ' ' + areacap)
