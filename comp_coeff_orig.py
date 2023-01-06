#!/usr/bin/env python3
#
# compute_coefficients.py --
#
# Generate coefficients for equations representing the analytic
# expressions for capacitance between metal layers for the given
# process stackup.
#
#------------------------------------------------------------------------
# From the README file:
# Basic equations (without adjustments for wire width):
# 
# 1.  Parallel plate capacitance (aF/um^2) = A
# 2.  Sidewall capacitance (aF/um) = B / (sep - C)
# 3.  Total fringe capacitance (aF/um) = D
# 4.  Fringe capacitance with near-body shielding = D * tanh(E * (sep + F))
# 5.  Partial fringe capacitance = D * (2/pi) * atan(G * (x + H))
# 
# How to find:
# 
# A:    Direct calculation (calc_parallel.py) (results/areacap_results.txt)
# B, C: Use build_fc_files_w2.py (results/w2_results.txt).  For a given wire
#       width (result file 3rd column), get coupling cap (6th column) vs.
#       separation (4th column) and do a curve fit to  B / (sep - C).
# D:    Use build_fc_files_w1.py (results/w1_results.txt).  For a given wire
#       width (result file 3rd column), total cap is value in 4th column.
#       Subtract (A * wire width) and divide the result by 2 to get D (total
#       fringe capacitance per unit length on a single edge).
# E, F: Use build_fc_files_w2.py (results/w2_results.txt).  For a given wire
#       width (result file 3rd column), get total fringe (5th column) vs.
#       separation.  Subtract ((A * wire width) + D) to get the fringe cap
#       on the shielded side only.  Curve fit to D * tanh(E * (sep + F)).
# G, H: Use build_fc_files_w1sh.py (results/w1sh_results.txt).  For a given
#       wire width (result file 3rd column), get coupling cap (7th column)
#       vs. shield edge separation (4th column).  Take -(x + 1/2 wire width)
#       to get shield distance from wire edge, and compute coupling cap
#       minus ((A * wire width) + D) to get amount of fringe coupling to the
#       shield.  Then curve fit to D * (2/pi) * atan(G * (x + H)).
#
#------------------------------------------------------------------------
#
# Written by Tim Edwards
# December 29, 2022
#------------------------------------------------------------------------

import os
import sys
import numpy
import subprocess
try:
    import scipy
except:
    have_scipy = False
    print('The scipy package is required to run the nonlinear curve fits.')
else:
    have_scipy = True

#--------------------------------------------------------------
# Usage statement
#--------------------------------------------------------------

def usage():
    print('Usage:  compute_coefficients.py <stack_def_file> [options]')
    print('  Where [options] may be one or more of:')
    print('     -verbose=<value>         (Diagnostic level)')

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

#--------------------------------------------------------------

verbose = 0

for option in options:
    tokens = option.split('=')
    if len(tokens) != 2:
        print('Error:  Option "' + option + '":  Option must be in form "-key=<value>".')
        usage()
        continue
    if tokens[0] == '-verbose':
        try:
            verbose = int(tokens[1])
        except:
            print('Error:  Verbose level "' + tokens[1] + '" is not numeric.')
            continue

#--------------------------------------------------------------
# 2. Obtain the metal stack.  The metal stack file is in the
#    format of executable python, so use exec().
#--------------------------------------------------------------

stackupfile = arguments[0]

try:
    exec(open(stackupfile, 'r').read())
except:
    print('Error:  No metal stack file ' + stackupfile + '!')
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

metals = []
for lname, layer in layers.items():
    if layer[0] == 'm':
        metals.append(lname)

substrates = []
for lname, layer in layers.items():
    if layer[0] == 'd':
        substrates.append(lname)

if not os.path.isfile('analysis/areacap_results.txt'):
    subprocess.run(['calc_parallel.py', stackupfile,
		'-file=analysis/areacap_results.txt',
		'-verbose=' + str(verbose)],
		stdin = subprocess.DEVNULL,
		stdout = subprocess.DEVNULL)

# "areacap" is a dictionary with entry keys "<layer>+<layer>"
# and value in aF/um^2.

areacap = {}
with open('analysis/areacap_results.txt', 'r') as ifile:
    for line in ifile.read().splitlines():
        tokens = line.split()
        areacap[tokens[0] + '+' + tokens[1]] = float(tokens[2])

# Get total capacitance, wire to substrate.  Run the
# one-wire generator for each set of layers independently,
# and with higher tolerance than the default.  Find values
# at the wire minimum width and 10 times the minimum width,
# since both cases are used later in this analysis.

for metal in metals:
    minwidth = limits[metal][0]
    wstart = '{:.2f}'.format(minwidth)
    wstop = '{:.2f}'.format(11 * minwidth)
    wstep = '{:.2f}'.format(9 * minwidth)
    for subs in substrates:
        if 'diff' in subs and metal == 'poly':
            continue
        if not os.path.isfile('analysis/' + metal + '_' + subs + '.txt'):
            if verbose > 0:
                print('Finding downward fringe for ' + metal + ' + ' + subs)
            done = False
            tolerance = 0.001
            while not done:
                try:
                    subprocess.run(['build_fc_files_w1.py', stackupfile,
		    		'-metals=' + metal,
				'-conductors=' + subs,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-tol=' + '{:.3f}'.format(tolerance),
				'-file=analysis/' + metal + '_' + subs + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 20)
                except subprocess.TimeoutExpired:
                    tolerance *= 2
                    if verbose > 0:
                        print('Trying again with tolerance = ' + '{:.3f}'.format(tolerance))
                else:
                    done = True
                    if tolerance > 0.01:
                        print('WARNING:  High tolerance value (' + '{:.3f}'.format(tolerance) + ') used.')

    for idx,cond in enumerate(metals):
        if cond == metal:
            break
        if not os.path.isfile('analysis/' + metal + '_' + cond + '.txt'):
            if verbose > 0:
                print('Finding downward fringe for ' + metal + ' + ' + cond)
            done = False
            tolerance = 0.001
            while not done:
                try:
                    subprocess.run(['build_fc_files_w1.py', stackupfile,
				'-metals=' + metal,
				'-conductors=' + cond,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-tol=' + '{:.3f}'.format(tolerance),
				'-file=analysis/' + metal + '_' + cond + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 20)
                except subprocess.TimeoutExpired:
                    tolerance *= 2
                    if verbose > 0:
                        print('Trying again with tolerance = ' + '{:.3f}'.format(tolerance))
                else:
                    done = True
                    if tolerance > 0.01:
                        print('WARNING:  High tolerance value (' + '{:.3f}'.format(tolerance) + ') used.')
    
    for cond in metals[idx+1:]:
        if not os.path.isfile('analysis/' + metal + '_' + cond + '.txt'):
            if verbose > 0:
                print('Finding upward fringe for ' + metal + ' + ' + cond)
            done = False
            tolerance = 0.001
            while not done:
                try:
                    subprocess.run(['build_fc_files_w1n.py', stackupfile,
				'-metals=' + metal,
				'-shields=' + cond,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-tol=' + '{:.3f}'.format(tolerance),
				'-file=analysis/' + metal + '_' + cond + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 20)
                except subprocess.TimeoutExpired:
                    tolerance *= 2
                    if verbose > 0:
                        print('Trying again with tolerance = ' + '{:.3f}'.format(tolerance))
                else:
                    done = True
                    if tolerance > 0.01:
                        print('WARNING:  High tolerance value (' + '{:.3f}'.format(tolerance) + ') used.')

# "fringe" is a dictionary with entry keys "<layer>+<layer>" and value in aF/um.
# "fringe10" is the same format, for results using 10*minwidth wires

if verbose > 0:
    print('Computing coefficients.')

fringe = {}
fringe10 = {}
for metal in metals:
    minwidth = limits[metal][0]
    for subs in substrates:
        if 'diff' in subs and metal == 'poly':
            continue
        with open('analysis/' + metal + '_' + subs + '.txt', 'r') as ifile:
            lines = ifile.read().splitlines()
            # 1st line has the minwidth result
            tokens = lines[0].split()
            # Get total cap and convert from uF/um to aF/um
            totalcap = float(tokens[3]) * 1e12
            platecap = areacap[metal + '+' + subs] * minwidth
            totalfringe = totalcap - platecap
            fringe[metal + '+' + subs] = totalfringe / 2
            # 2nd line has the 10*minwidth result
            tokens = lines[1].split()
            # Get total cap and convert from uF/um to aF/um
            totalcap = float(tokens[3]) * 1e12
            platecap = areacap[metal + '+' + subs] * 10 * minwidth
            totalfringe = totalcap - platecap
            fringe10[metal + '+' + subs] = totalfringe / 2
    for cond in metals:
        if cond == metal:
            continue
        with open('analysis/' + metal + '_' + cond + '.txt', 'r') as ifile:
            lines = ifile.read().splitlines()
            # 1st line has the minwidth result
            tokens = lines[0].split()
            totalcap = float(tokens[3]) * 1e12
            try:
                platecap = areacap[metal + '+' + cond] * minwidth
            except:
                platecap = areacap[cond + '+' + metal] * minwidth
            totalfringe = totalcap - platecap
            fringe[metal + '+' + cond] = totalfringe / 2
            if verbose > 1:
                print('metal = ' + metal + ' cond = ' + cond + ' totalcap = ' + '{:.3f}'.format(totalcap) + ' platecap = ' + '{:.3f}'.format(platecap) + ' totalfringe = ' + '{:.3f}'.format(totalfringe) + ' fringe = ' + '{:.3f}'.format(fringe[metal + '+' + cond]))
            # 2nd line has the 10*minwidth result
            tokens = lines[1].split()
            totalcap = float(tokens[3]) * 1e12
            try:
                platecap = areacap[metal + '+' + cond] * 10 * minwidth
            except:
                platecap = areacap[cond + '+' + metal] * 10 * minwidth
            totalfringe = totalcap - platecap
            fringe10[metal + '+' + cond] = totalfringe / 2

#-------------------------------------------------------------------------
# Get coefficients B and C (with curve fitting)
#-------------------------------------------------------------------------

sidewall = {}

# NOTE:  To do:  Check result over all substrate and shield types, not
# just the base substrate.  Some portion of the coupling between the
# undersides of the wires is lost to the substrate, an effect that
# increases as the substrate or shield plane gets closer to the wires.
subs = substrates[0]

for metal in metals:
    minwidth = limits[metal][0]
    minsep =   limits[metal][1]

    # Set width start/stop/step for single run at minimum width
    wstart = '{:.2f}'.format(minwidth)
    wstop = '{:.2f}'.format(minwidth + 1)
    wstep = '{:.2f}'.format(1)

    # Set separation start/stop/step from minimum step out to 20 microns
    # at 0.25um increments
    sstart = '{:.2f}'.format(minsep)
    sstop = '20.0'
    sstep = '0.25'

    if not os.path.isfile('analysis/' + metal + '_' + metal + '.txt'):
        if verbose > 0:
            print('Finding sidewall coupling for ' + metal)
        done = False
        tolerance = 0.008
        while not done:
            try:
                subprocess.run(['build_fc_files_w2.py', stackupfile,
				'-metals=' + metal,
				'-sub=' + subs,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-sep=' + sstart + ',' + sstop + ',' + sstep,
				'-tol=' + '{:.3f}'.format(tolerance),
				'-file=analysis/' + metal + '_' + metal + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 1000)
            except subprocess.TimeoutExpired:
                tolerance *= 2
                if verbose > 0:
                    print('Trying again with tolerance = ' + '{:.3f}'.format(tolerance))
            else:
                done = True
                if tolerance > 0.01:
                    print('WARNING:  High tolerance value (' + '{:.3f}'.format(tolerance) + ') used.')

    # Unlike the previous runs, which get coefficients directly through the FasterCap
    # result(s), this one requires analysis through curve fitting.
    # Basic sidewall capacitance fits a curve C_coup = B / (sep - C) to get coefficients B and C
    # to plug into magic's tech file.

    xdata = []
    ydata = []
    with open('analysis/' + metal + '_' + metal + '.txt', 'r') as ifile:
        cdata = ifile.read()
        for line in cdata.splitlines():
            tokens = line.split()
            # Already know the first three entries.  Get the fourth entry (separation)
            # for xdata and the sixth entry (coupling) for ydata.  Ignore negative
            # outliers
            yvalue = float(tokens[5])
            if yvalue > 0:
                xdata.append(float(tokens[3]))
                ydata.append(float(tokens[5]))

    # Use scipy least_squares to do a nonlinear curve fit to y = b / (x - c)
    def func1(x, b, c):
        return b / (x - c)

    # curve_fit needs a seed value somewhere in the range of sanity
    p0 = [1e-11, 0]
    params, _ = scipy.optimize.curve_fit(func1, xdata, ydata, p0=p0)

    # Save results.  Convert value B to aF/um (value C is already in um).
    sidewall[metal] = (params[0] * 1e12, params[1])
    
#-------------------------------------------------------------------------
# Get coefficients E and F (with curve fitting)
#-------------------------------------------------------------------------

fringeshield = {}

for metal in metals:
    conductors = []
    for conductor in metals.copy():
        if conductor == metal:
            break
        conductors.append(conductor)

    conductors.extend(substrates)

    for conductor in conductors:

        # Ignore poly over diff (not a parasitic)
        if 'poly' in metal and 'diff' in conductor:
            continue

        minwidth = limits[metal][0]
        minsep =   limits[metal][1]

        # Set width start/stop/step for single run at 10*minimum width
        wstart = '{:.2f}'.format(10*minwidth)
        wstop = '{:.2f}'.format(10*minwidth + 1)
        wstep = '{:.2f}'.format(1)

        # Set separation start/stop/step from minimum step out to 20 microns
        # at 0.25um increments
        sstart = '{:.2f}'.format(minsep)
        sstop = '10.0'
        sstep = '0.25'

        if not os.path.isfile('analysis/' + metal + '_f_' + conductor + '.txt'):
            if verbose > 0:
                print('Finding fringe shielding for ' + metal + ' width ' + wstart + ' over ' + conductor)
            done = False
            tolerance = 0.001
            while not done:
                try:
                    subprocess.run(['build_fc_files_w2.py', stackupfile,
				'-metals=' + metal,
				'-sub=' + conductor,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-sep=' + sstart + ',' + sstop + ',' + sstep,
				'-tol=' + '{:.3f}'.format(tolerance),
				'-file=analysis/' + metal + '_f_' + conductor + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 1000)
                except subprocess.TimeoutExpired:
                    tolerance *= 2
                    if verbose > 0:
                        print('Trying again with tolerance = ' + '{:.3f}'.format(tolerance))
                else:
                    done = True
                    if tolerance > 0.01:
                        print('WARNING:  High tolerance value (' + '{:.3f}'.format(tolerance) + ') used.')

        # More analysis through curve fitting using scipy
        # Fringe capacitance shielding (fraction) fits a curve
        # F_shield = tanh(E * (sep + F)) to get coefficients E and F for modeling

        xdata = []
        ydata = []

        platecap = areacap[metal + '+' + conductor] * (10 * minwidth)
        totfringe = fringe10[metal + '+' + conductor]

        with open('analysis/' + metal + '_f_' + conductor + '.txt', 'r') as ifile:
            cdata = ifile.read()
            for line in cdata.splitlines():
                tokens = line.split()
                # Already know the first three entries.  Get the fourth entry (separation)
                # for xdata and the sixth entry (coupling) for ydata
                ycdata = float(tokens[4]) * 1e12
                yvalue = (ycdata - platecap - totfringe) / totfringe
                if yvalue < 1:
                    xdata.append(float(tokens[3]))
                    ydata.append(yvalue)

        # Use scipy least_squares to do a nonlinear curve fit to y = tanh(e * (x + f))
        def func2(x, e, f):
            return numpy.tanh(e * (x + f))

        params, _ = scipy.optimize.curve_fit(func2, xdata, ydata)

        # Save results.  Value E is unitless and F is in microns.
        fringeshield[metal + '+' + conductor] = (params[0], params[1])
    
#-------------------------------------------------------------------------
# Get coefficients G and H (with curve fitting)
#-------------------------------------------------------------------------

fringepartial = {}
subs = substrates[0]

for metal in metals:
    conductors = []
    for conductor in metals.copy():
        if conductor == metal:
            break
        conductors.append(conductor)

    for conductor in conductors:
        # Ignore poly over diff (not a parasitic)
        if 'poly' in metal and 'diff' in conductor:
            continue

        minwidth = limits[metal][0]

        # Set width start/stop/step for single run at minimum width
        wstart = '{:.2f}'.format(minwidth)
        wstop = '{:.2f}'.format(minwidth + 1)
        wstep = '{:.2f}'.format(1)

        # Set separation start/stop/step from wire edge out to 15 microns
        # at 0.25um increments
        sstart = '{:.2f}'.format(-minwidth / 2)
        sstop = '-15.0'
        sstep = '-0.25'

        if not os.path.isfile('analysis/' + metal + '_p_' + conductor + '.txt'):
            if verbose > 0:
                print('Finding partial fringe for ' + metal + ' coupling to ' + conductor)
            done = False
            tolerance = 0.004
            while not done:
                try:
                    subprocess.run(['build_fc_files_w1sh.py', stackupfile,
				'-metals=' + metal,
				'-shields=' + conductor,
				'-sub=' + subs,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-sep=' + sstart + ',' + sstop + ',' + sstep,
				'-tol=' + '{:.3f}'.format(tolerance),
				'-file=analysis/' + metal + '_p_' + conductor + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 1000)
                except subprocess.TimeoutExpired:
                    tolerance *= 2
                    if verbose > 0:
                        print('Trying again with tolerance = ' + '{:.3f}'.format(tolerance))
                else:
                    done = True
                    if tolerance > 0.01:
                        print('WARNING:  High tolerance value (' + '{:.3f}'.format(tolerance) + ') used.')

        # More analysis through curve fitting using scipy
        # Partail fringe capacitance (fraction) fits a curve
        # F_fringe = (2/pi) * arctan(G * (sep + H)) to get coefficients E and F for modeling

        xcdata = []
        ycdata = []
        with open('analysis/' + metal + '_p_' + conductor + '.txt', 'r') as ifile:
            cdata = ifile.read()
            for line in cdata.splitlines():
                tokens = line.split()
                # Already know the first three entries.  Get the fourth entry (separation)
                # for xdata and the sixth entry (coupling) for ydata
                xcdata.append(float(tokens[3]))
                ycdata.append(float(tokens[6]) * 1e12)

        platecap = areacap[metal + '+' + conductor] * minwidth
        totfringe = fringe[metal + '+' + conductor]
        halfwidth = minwidth / 2

        xdata = []
        for x in xcdata:
            xdata.append(-(x + halfwidth))

        ydata = []
        for y in ycdata:
            ydata.append((y - platecap - totfringe) / totfringe)

        # Use scipy least_squares to do a nonlinear curve fit to y = 0.6366 * atan(g * (x + h))
        def func3(x, g, h):
            return 0.6366 * numpy.arctan(g * (x + h))

        params, _ = scipy.optimize.curve_fit(func3, xdata, ydata)

        # Save results.  Value G is unitless and H is in microns.
        fringepartial[metal + '+' + conductor] = (params[0], params[1])
    
#-------------------------------------------------------------------------
# Print out all results
#-------------------------------------------------------------------------

if verbose > 0:
    print('')

print('Process stackup ' + stackupfile + ' coefficients:')
for metal in metals:
    print('')
    print(metal + ':')
    print('')
    print('  areacap (aF/um^2) to:')
    for subs in substrates:
        if 'diff' in subs and metal == 'poly':
            continue
        print('    ' + subs + ' = {:.3f}'.format(areacap[metal + '+' + subs]))
    for cond in metals:
        if cond != metal:
            try:
                print('    ' + cond + ' = {:.3f}'.format(areacap[metal + '+' + cond]))
            except:
                print('    ' + cond + ' = {:.3f}'.format(areacap[cond + '+' + metal]))
    print('')
    print('  fringecap (aF/um) to:')
    for subs in substrates:
        if 'diff' in subs and metal == 'poly':
            continue
        print('    ' + subs + ' = {:.3f}'.format(fringe[metal + '+' + subs]))
    for cond in metals:
        if cond == metal:
            continue
        print('    ' + cond + ' = {:.3f}'.format(fringe[metal + '+' + cond]))

    print('')
    print('  sidewall cap:')
    print('      multiplier = {:.3f}'.format(sidewall[metal][0]))
    print('      offset     = {:.3f}'.format(sidewall[metal][1]))

    print('')
    print('  fringe shielding to:')
    for subs in substrates:
        if 'diff' in subs and metal == 'poly':
            continue
        print('    ' + subs + ':')
        print('    multiplier = {:.3f}'.format(fringeshield[metal + '+' + subs][0]))
        print('    offset     = {:.3f}'.format(fringeshield[metal + '+' + subs][1]))
    for cond in metals:
        if cond == metal:
            continue
        if metal + '+' + cond in fringeshield.keys():
            # Instead of recalculating which metals are above or below, just ignore
            # when the key doesn't exist.
            print('    ' + cond + ':')
            print('    multiplier = {:.3f}'.format(fringeshield[metal + '+' + cond][0]))
            print('    offset     = {:.3f}'.format(fringeshield[metal + '+' + cond][1]))

    print('')
    print('  partial fringe to:')
    for cond in metals:
        if cond == metal:
            continue
        if metal + '+' + cond in fringepartial.keys():
            # Instead of recalculating which metals are above or below, just ignore
            # when the key doesn't exist.
            print('    ' + cond + ':')
            print('    multiplier = {:.3f}'.format(fringepartial[metal + '+' + cond][0]))
            print('    offset     = {:.3f}'.format(fringepartial[metal + '+' + cond][1]))
