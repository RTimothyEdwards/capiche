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

try:
    import matplotlib
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    try:
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    except:
        # print('ImageTk in PIL required to display result graphs in application.')
        have_tk_matplotlib = False
    else:
        have_tk_matplotlib = True
except:
    have_matplotlib = False
    print('The matplotlib package is required to display result graphs.')
else:
    have_matplotlib = True

#--------------------------------------------------------------
# Usage statement
#--------------------------------------------------------------

def usage():
    print('Usage:  compute_coefficients.py <stack_def_file> [<magic_startup_file>] [options]')
    print('  Where [options] may be one or more of:')
    print('     -verbose=<value>         (Diagnostic level)')

#--------------------------------------------------------------
# Generate lists of metal types and substrate types from the
# process stackup.
#--------------------------------------------------------------

def generate_layers(layers):
    metals = []
    for lname, layer in layers.items():
        if layer[0] == 'm':
            metals.append(lname)

    substrates = []
    for lname, layer in layers.items():
        if layer[0] == 'd':
            substrates.append(lname)

    return metals, substrates

#--------------------------------------------------------------
# Generate result files for area capacitance
#--------------------------------------------------------------

def generate_areacap(stackupfile):

    if not os.path.isfile('analysis/areacap/results.txt'):
        subprocess.run(['calc_parallel.py', stackupfile,
		'-file=analysis/areacap/results.txt',
		'-verbose=' + str(verbose)],
		stdin = subprocess.DEVNULL,
		stdout = subprocess.DEVNULL)

#--------------------------------------------------------------
# Generate result files for fringe capacitance
#--------------------------------------------------------------

def generate_fringe(stackupfile, metals, substrates, limits, verbose):

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
            if not os.path.isfile('analysis/fringe/' + metal + '_' + subs + '.txt'):
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
				'-file=analysis/fringe/' + metal + '_' + subs + '.txt'],
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
            if not os.path.isfile('analysis/fringe/' + metal + '_' + cond + '.txt'):
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
				'-file=analysis/fringe/' + metal + '_' + cond + '.txt'],
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
            if not os.path.isfile('analysis/fringe/' + metal + '_' + cond + '.txt'):
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
				'-file=analysis/fringe/' + metal + '_' + cond + '.txt'],
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

#-------------------------------------------------------------------------
# Generate result files for sidewall capacitance
#-------------------------------------------------------------------------

def generate_sidewall(stackupfile, metals, substrates, limits, verbose):

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

        if not os.path.isfile('analysis/sidewall/' + metal + '_' + metal + '.txt'):
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
				'-file=analysis/sidewall/' + metal + '_' + metal + '.txt'],
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

#-------------------------------------------------------------------------
# Generate result files for fringe shielding model
#-------------------------------------------------------------------------

def generate_fringeshield(stackupfile, metals, substrates, limits, verbose):

    for metal in metals:
        minwidth = limits[metal][0]
        minsep =   limits[metal][1]

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

            # Set width start/stop/step for single run at 10*minimum width
            wstart = '{:.2f}'.format(10*minwidth)
            wstop = '{:.2f}'.format(10*minwidth + 1)
            wstep = '{:.2f}'.format(1)

            # Set separation start/stop/step from minimum step out to 20 microns
            # at 0.25um increments
            sstart = '{:.2f}'.format(minsep)
            sstop = '10.0'
            sstep = '0.25'

            if not os.path.isfile('analysis/fringeshield/' + metal + '_' + conductor + '.txt'):
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
				'-file=analysis/fringeshield/' + metal + '_' + conductor + '.txt'],
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

#-------------------------------------------------------------------------
# Generate result files for partial fringe modeling
#-------------------------------------------------------------------------

def generate_fringepartial(stackupfile, metals, substrates, limits, verbose):

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

            if not os.path.isfile('analysis/fringepartial/' + metal + '_' + conductor + '.txt'):
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
				'-file=analysis/fringepartial/' + metal + '_' + conductor + '.txt'],
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

#-----------------------------------------------------------------------------
# Get area capacitances by direct calculation (results in areacap_results.txt)
#-----------------------------------------------------------------------------

def compute_areacap():
    # "areacap" is a dictionary with entry keys "<layer>+<layer>"
    # and value in aF/um^2.

    areacap = {}
    with open('analysis/areacap/results.txt', 'r') as ifile:
        for line in ifile.read().splitlines():
            tokens = line.split()
            areacap[tokens[0] + '+' + tokens[1]] = float(tokens[2])

    return areacap

#-----------------------------------------------------------------------------
# Get fringe capacitances (results in <metal>_<conductor>.txt)
#
# "size" is the width multiplier (e.g., size=10 means 10 * minimum width) for
# the wire.  The fringe capacitance values are parsed at the given size
#-----------------------------------------------------------------------------

def compute_fringe(metals, substrates, areacap, size):

    # "fringe" is a dictionary with entry keys "<layer>+<layer>" and value in aF/um.
    fringe = {}

    for metal in metals:
        minwidth = limits[metal][0]
        width = minwidth * size

        for subs in substrates:
            if 'diff' in subs and metal == 'poly':
                continue
            with open('analysis/fringe/' + metal + '_' + subs + '.txt', 'r') as ifile:
                lines = ifile.read().splitlines()
                for line in lines:
                    tokens = line.split()
                    if abs(float(tokens[2]) - width) < 0.01:
                        # Get total cap and convert from uF/um to aF/um
                        totalcap = float(tokens[3]) * 1e12
                        platecap = areacap[metal + '+' + subs] * width
                        totalfringe = totalcap - platecap
                        fringe[metal + '+' + subs] = totalfringe / 2
        for cond in metals:
            if cond == metal:
                continue
            with open('analysis/fringe/' + metal + '_' + cond + '.txt', 'r') as ifile:
                lines = ifile.read().splitlines()
                for line in lines:
                    tokens = line.split()
                    if abs(float(tokens[2]) - width) < 0.01:
                        totalcap = float(tokens[3]) * 1e12
                        try:
                            platecap = areacap[metal + '+' + cond] * width
                        except:
                            platecap = areacap[cond + '+' + metal] * width
                        totalfringe = totalcap - platecap
                        fringe[metal + '+' + cond] = totalfringe / 2
                        if verbose > 1:
                            print('metal = ' + metal + ' cond = ' + cond + ' totalcap = ' + '{:.3f}'.format(totalcap) + ' platecap = ' + '{:.3f}'.format(platecap) + ' totalfringe = ' + '{:.3f}'.format(totalfringe) + ' fringe = ' + '{:.3f}'.format(fringe[metal + '+' + cond]))

    return fringe

#-------------------------------------------------------------------------
# Get coefficients B and C (with curve fitting)
#-------------------------------------------------------------------------

def compute_sidewall(metals):

    sidewall = {}

    # Unlike the previous runs, which get coefficients directly through the FasterCap
    # result(s), this one requires analysis through curve fitting.
    # Basic sidewall capacitance fits a curve C_coup = B / (sep - C) to get coefficients B and C
    # to plug into magic's tech file.

    for metal in metals:
        xdata = []
        ydata = []
        with open('analysis/sidewall/' + metal + '_' + metal + '.txt', 'r') as ifile:
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

    return sidewall
    
#-------------------------------------------------------------------------
# Get coefficients E and F (with curve fitting)
#-------------------------------------------------------------------------

def compute_fringeshield(metals, substrates, areacap, fringe10):

    # More analysis through curve fitting using scipy
    # Fringe capacitance shielding (fraction) fits a curve
    # F_shield = tanh(E * (sep + F)) to get coefficients E and F for modeling

    fringeshield = {}

    for metal in metals:
        minwidth = limits[metal][0]

        conductors = []
        for conductor in metals.copy():
            if conductor == metal:
                break
            conductors.append(conductor)

        conductors.extend(substrates)

        for conductor in conductors:

            # Ignore poly over diff, which is not considered a parasitic
            if 'diff' in conductor and metal == 'poly':
                continue

            xdata = []
            ydata = []

            platecap = areacap[metal + '+' + conductor] * (10 * minwidth)
            totfringe = fringe10[metal + '+' + conductor]

            with open('analysis/fringeshield/' + metal + '_' + conductor + '.txt', 'r') as ifile:
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

    return fringeshield
    
#-------------------------------------------------------------------------
# Get coefficients G and H (with curve fitting)
#-------------------------------------------------------------------------

def compute_fringepartial(metals, limits, areacap, fringe):

    fringepartial = {}

    for metal in metals:
        minwidth = limits[metal][0]

        conductors = []
        for conductor in metals.copy():
            if conductor == metal:
                break
            conductors.append(conductor)

        for conductor in conductors:

            # More analysis through curve fitting using scipy
            # Partail fringe capacitance (fraction) fits a curve
            # F_fringe = (2/pi) * arctan(G * (sep + H)) to get coefficients E and F for modeling

            xcdata = []
            ycdata = []
            with open('analysis/fringepartial/' + metal + '_' + conductor + '.txt', 'r') as ifile:
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

    return fringepartial
    
#--------------------------------------------------------------
# Validate fringe capacitance in magic
#--------------------------------------------------------------

def validate_fringe(stackupfile, startupfile, metals, substrates, limits, verbose):

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
            if not os.path.isfile('validate/fringe/' + metal + '_' + subs + '.txt'):
                if verbose > 0:
                    print('Finding downward fringe for ' + metal + ' + ' + subs)
                subprocess.run(['build_mag_files_w1.py', stackupfile, startupfile,
		    		'-metals=' + metal,
				'-conductors=' + subs,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-file=validate/fringe/' + metal + '_' + subs + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 20)

        for idx,cond in enumerate(metals):
            if cond == metal:
                break
            if not os.path.isfile('validate/fringe/' + metal + '_' + cond + '.txt'):
                if verbose > 0:
                    print('Finding downward fringe for ' + metal + ' + ' + cond)
                subprocess.run(['build_mag_files_w1.py', stackupfile, startupfile,
				'-metals=' + metal,
				'-conductors=' + cond,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-file=validate/fringe/' + metal + '_' + cond + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 20)
    
        for cond in metals[idx+1:]:
            if not os.path.isfile('validate/fringe/' + metal + '_' + cond + '.txt'):
                if verbose > 0:
                    print('Finding upward fringe for ' + metal + ' + ' + cond)
                subprocess.run(['build_mag_files_w1.py', stackupfile, startupfile,
				'-metals=' + metal,
				'-conductors=' + cond,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-file=validate/fringe/' + metal + '_' + cond + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 20)

#-------------------------------------------------------------------------
# Validate sidewall capacitance in magic
#-------------------------------------------------------------------------

def validate_sidewall(stackupfile, startupfile, metals, substrates, limits, verbose):

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

        if not os.path.isfile('validate/sidewall/' + metal + '_' + metal + '.txt'):
            if verbose > 0:
                print('Finding sidewall coupling for ' + metal)
            subprocess.run(['build_mag_files_w2.py', stackupfile, startupfile,
				'-metals=' + metal,
				'-sub=' + subs,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-sep=' + sstart + ',' + sstop + ',' + sstep,
				'-file=validate/sidewall/' + metal + '_' + metal + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 1000)

#-------------------------------------------------------------------------
# Validate fringe shielding model in magic
#-------------------------------------------------------------------------

def validate_fringeshield(stackupfile, startupfile, metals, substrates, limits, verbose):

    for metal in metals:
        minwidth = limits[metal][0]
        minsep =   limits[metal][1]

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

            # Set width start/stop/step for single run at 10*minimum width
            wstart = '{:.2f}'.format(10*minwidth)
            wstop = '{:.2f}'.format(10*minwidth + 1)
            wstep = '{:.2f}'.format(1)

            # Set separation start/stop/step from minimum step out to 20 microns
            # at 0.25um increments
            sstart = '{:.2f}'.format(minsep)
            sstop = '10.0'
            sstep = '0.25'

            if not os.path.isfile('validate/fringeshield/' + metal + '_' + conductor + '.txt'):
                if verbose > 0:
                    print('Finding fringe shielding for ' + metal + ' width ' + wstart + ' over ' + conductor)
                subprocess.run(['build_mag_files_w2.py', stackupfile, startupfile,
				'-metals=' + metal,
				'-sub=' + conductor,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-sep=' + sstart + ',' + sstop + ',' + sstep,
				'-file=validate/fringeshield/' + metal + '_' + conductor + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 1000)

#-------------------------------------------------------------------------
# Validate partial fringe model in magic
#-------------------------------------------------------------------------

def validate_fringepartial(stackupfile, startupfile, metals, substrates, limits, verbose):

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

            if not os.path.isfile('validate/fringepartial/' + metal + '_' + conductor + '.txt'):
                if verbose > 0:
                    print('Finding partial fringe for ' + metal + ' coupling to ' + conductor)
                subprocess.run(['build_mag_files_w1sh.py', stackupfile, startupfile,
				'-metals=' + metal,
				'-shields=' + conductor,
				'-sub=' + subs,
				'-width=' + wstart + ',' + wstop + ',' + wstep,
				'-sep=' + sstart + ',' + sstop + ',' + sstep,
				'-file=validate/fringepartial/' + metal + '_' + conductor + '.txt'],
				stdin = subprocess.DEVNULL,
				stdout = subprocess.DEVNULL,
				timeout = 1000)

#-------------------------------------------------------------------------
# Print out all results
#-------------------------------------------------------------------------

def print_coefficients(metals, substrates):
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

#-------------------------------------------------------------------------
# Save all model coefficients
#-------------------------------------------------------------------------

def save_coefficients(metals, substrates, outfile):
    with open(outfile, 'w') as ofile:
        for metal in metals:
            for subs in substrates:
                if 'diff' in subs and metal == 'poly':
                    continue
                print('areacap ' + metal + ' ' + subs + ' {:.3f}'.format(areacap[metal + '+' + subs]), file=ofile)
            for cond in metals:
                if cond != metal:
                    try:
                        print('areacap ' + metal + ' ' + cond + ' {:.3f}'.format(areacap[metal + '+' + cond]), file=ofile)
                    except:
                        print('areacap ' + metal + ' ' + cond + ' {:.3f}'.format(areacap[cond + '+' + metal]), file=ofile)
            for subs in substrates:
                if 'diff' in subs and metal == 'poly':
                    continue
                print('fringecap ' + metal + ' ' + subs + ' {:.3f}'.format(fringe[metal + '+' + subs]), file=ofile)
            for cond in metals:
                if cond == metal:
                    continue
                print('fringecap ' + metal + ' ' + cond + ' {:.3f}'.format(fringe[metal + '+' + cond]), file=ofile)

            print('sidewall ' + metal + ' ' + '{:.3f}'.format(sidewall[metal][0]) + ' ' + '{:.3f}'.format(sidewall[metal][1]), file=ofile)

            for subs in substrates:
                if 'diff' in subs and metal == 'poly':
                    continue
                print('fringeshield ' + metal + ' ' + subs + ' ' + '{:.3f}'.format(fringeshield[metal + '+' + subs][0]) + ' ' + '{:.3f}'.format(fringeshield[metal + '+' + subs][1]), file=ofile)
            for cond in metals:
                if cond == metal:
                    continue
                if metal + '+' + cond in fringeshield.keys():
                    # Instead of recalculating which metals are above or below, just ignore
                    # when the key doesn't exist.
                    print('fringeshield ' + metal + ' ' + cond + ' ' + '{:.3f}'.format(fringeshield[metal + '+' + cond][0]) + ' ' + '{:.3f}'.format(fringeshield[metal + '+' + cond][1]), file=ofile)

            for cond in metals:
                if cond == metal:
                    continue
                if metal + '+' + cond in fringepartial.keys():
                    # Instead of recalculating which metals are above or below, just ignore
                    # when the key doesn't exist.
                    print('fringepartial ' + metal + ' ' + cond + ' ' + '{:.3f}'.format(fringepartial[metal + '+' + cond][0]) + ' ' + '{:.3f}'.format(fringepartial[metal + '+' + cond][1]), file=ofile)
                    
#-------------------------------------------------------------------------
# Read all model coefficients
#-------------------------------------------------------------------------

def load_coefficients(infile):
    areacap = {}
    fringecap = {}
    sidewall = {}
    fringeshield = {}
    fringepartial = {}

    with open(infile, 'r') as ifile:
        lines = ifile.read().splitlines()
        for line in lines:
            tokens = line.split()
            captype = tokens[0]
            if captype == 'areacap':
                metal = tokens[1]
                cond = tokens[2]
                areacap[metal + '+' + cond] = float(tokens[3])
              
            elif captype == 'fringecap':
                metal = tokens[1]
                cond = tokens[2]
                fringecap[metal + '+' + cond] = float(tokens[3])

            elif captype == 'sidewall':
                metal = tokens[1]
                sidewall[metal] = [float(tokens[2]), float(tokens[3])]

            elif captype == 'fringeshield':
                metal = tokens[1]
                cond = tokens[2]
                fringeshield[metal + '+' + cond] = [float(tokens[3]), float(tokens[4])]

            elif captype == 'fringepartial':
                metal = tokens[1]
                cond = tokens[2]
                fringepartial[metal + '+' + cond] = [float(tokens[3]), float(tokens[4])]

    return areacap, fringecap, sidewall, fringeshield, fringepartial
                    
#--------------------------------------------------------------
# Plot sidewall capacitance data
#--------------------------------------------------------------

def plot_sidewall(metal, sidewall):

    # Check validity of metal
    try:
        swrec = sidewall[metal]
    except:
        return

    infile1 = 'analysis/sidewall/' + metal + '_' + metal + '.txt'
    infile2 = 'validate/sidewall/' + metal + '_' + metal + '.txt'

    # Get the result from FasterCap
    with open(infile1, 'r') as ifile:
        lines = ifile.read().splitlines()
        # Get first three values (metal, substrate, width) which should be the same
        # for all lines.
        tokens = lines[0].split()
        metal = tokens[0]
        substrate = tokens[1]
        width = float(tokens[2])

        sep1 = []
        ccoup1 = []
        for line in lines:
            tokens = line.split()
            sep1.append(float(tokens[3]))
            # Convert coupling cap to aF/um
            ccoup1.append(float(tokens[5]) * 1e12)

    # Get the result from magic
    with open(infile2, 'r') as ifile:
        lines = ifile.read().splitlines()
        # Check values from first line and make sure the metal width
        # agrees for both files
        tokens = lines[0].split()

        if width == float(tokens[2]):
            sep2 = []
            ccoup2 = []
            for line in lines:
                tokens = line.split()
                sep2.append(float(tokens[3]))
                # Convert coupling cap to aF/um
                ccoup2.append(float(tokens[5]) * 1e12)

    # Compute the analytic sidewall
    swmult = swrec[0]
    swoffset = swrec[1]

    ctest = []
    for sval in sep1:
        ctest.append(swmult / (sval + swoffset))

    # Now plot all three results using matplotlib
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.plot(sep1, ccoup1, label='FasterCap')
    ax.plot(sep2, ccoup2, label='Magic')
    ax.plot(sep1, ctest, label='Analytic')
    ax.set_xlabel('Wire separation (um)')
    ax.set_ylabel('Sidewall capacitance (aF/um)')
    ax.grid(True)
    legend = ax.legend(loc = 2, bbox_to_anchor = (1.05, 1), borderaxespad=0.)
    ax.set_title(metal + ' sidewall capacitance vs. wire separation')

    os.makedirs('plots/sidewall', exist_ok=True)
    canvas.print_figure('plots/sidewall/' + metal + '_' + metal + '.svg',
		bbox_inches = 'tight', bbox_extra_artists = [legend])

#--------------------------------------------------------------
# Plot fringe shielding capacitance data
#--------------------------------------------------------------

def plot_fringeshield(metal, cond, areacap, fringe, fringeshield):

    # Check if metal + cond combination is valid
    try:
        fsrec = fringeshield[metal + '+' + cond]
    except:
        return

    infile1A = 'analysis/fringeshield/' + metal + '_' + cond + '.txt'
    infile2A = 'validate/fringeshield/' + metal + '_' + cond + '.txt'

    infile1B = 'analysis/fringe/' + metal + '_' + cond + '.txt'
    infile2B = 'validate/fringe/' + metal + '_' + cond + '.txt'

    # Get the result for single wire (effectively, separation = infinite)
    # NOTE:  The assumption is that this file has two lines, and the 2nd line
    # has a wire width of 10x the minimum, which matches the width used in the
    # fringeshield directory results.  To do:  Plot for any width or across
    # widths.

    with open(infile1B, 'r') as ifile:
        lines = ifile.read().splitlines()
        tokens = lines[1].split()
        totalcap1 = float(tokens[3]) * 1e12

    with open(infile2B, 'r') as ifile:
        lines = ifile.read().splitlines()
        tokens = lines[1].split()
        totalcap2 = float(tokens[3]) * 1e12

    # Get the result from FasterCap
    with open(infile1A, 'r') as ifile:
        lines = ifile.read().splitlines()
        # Get first three values (metal, conductor, width) which should be the same
        # for all lines.
        tokens = lines[0].split()
        metal = tokens[0]
        cond = tokens[1]
        width = float(tokens[2])

        sep1 = []
        fshield1 = []
        for line in lines:
            tokens = line.split()
            sep1.append(float(tokens[3]))
            # Convert coupling cap to aF/um and subtract from the result for a
            # single wire (i.e., infinite separation)
            fcoup1 = (float(tokens[4]) * 1e12) / totalcap1
            fshield1.append(fcoup1)

    # Get the result from magic
    with open(infile2A, 'r') as ifile:
        lines = ifile.read().splitlines()
        # Check values from first line and make sure the metal width
        # agrees for both files
        tokens = lines[0].split()

        if width == float(tokens[2]):
            sep2 = []
            fshield2 = []
            for line in lines:
                tokens = line.split()
                sep2.append(float(tokens[3]))
                # Convert coupling cap to aF/um and subtract from the result for a
                # single wire (i.e., infinite separation)
                fcoup2 = (float(tokens[4]) * 1e12) / totalcap2
                fshield2.append(fcoup2)

    # Compute the analytic fringe shielding
    fsmult = fsrec[0]
    fsoffset = fsrec[1]

    # Get analytic values for the area cap and maximum single-side fringe.
    carea = areacap[metal + '+' + cond]
    cfringe = fringe[metal + '+' + cond]
    ctotal = carea + 2 * cfringe

    ftest = []
    for sval in sep1:
        frac = numpy.tanh(fsmult * (sval + fsoffset))
        ftest.append((carea + cfringe * (1 + frac)) / ctotal)

    # Now plot all three results using matplotlib
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.plot(sep1, fshield1, label='FasterCap')
    ax.plot(sep2, fshield2, label='Magic')
    ax.plot(sep1, ftest, label='Analytic')
    ax.set_xlabel('Wire separation (um)')
    ax.set_ylabel('Fringe capacitance shielding (fraction)')
    ax.grid(True)
    legend = ax.legend(loc = 2, bbox_to_anchor = (1.05, 1), borderaxespad=0.)
    ax.set_title(metal + ' to ' + cond + ' fringe shielding vs. wire separation')

    os.makedirs('plots/fringeshield', exist_ok=True)
    canvas.print_figure('plots/fringeshield/' + metal + '_' + cond + '.svg',
		bbox_inches = 'tight', bbox_extra_artists = [legend])

#--------------------------------------------------------------
# Plot partial fringe capacitance data
#--------------------------------------------------------------

def plot_fringepartial(metal, cond, areacap, fringe, fringepartial):

    # Check if metal + cond combination is valid
    try:
        fprec = fringepartial[metal + '+' + cond]
    except:
        return

    infile1A = 'analysis/fringepartial/' + metal + '_' + cond + '.txt'
    infile2A = 'validate/fringepartial/' + metal + '_' + cond + '.txt'

    infile1B = 'analysis/fringe/' + metal + '_' + cond + '.txt'
    infile2B = 'validate/fringe/' + metal + '_' + cond + '.txt'

    # Get the result for single wire (effectively, separation = infinite)
    # NOTE:  The assumption is that this file has two lines, and the 1sd line
    # has a minimum wire width, which matches the width used in the
    # fringepartial directory results.  To do:  Plot for any width or across
    # widths.

    with open(infile1B, 'r') as ifile:
        lines = ifile.read().splitlines()
        tokens = lines[0].split()
        totalcap1 = float(tokens[3]) * 1e12

    with open(infile2B, 'r') as ifile:
        lines = ifile.read().splitlines()
        tokens = lines[0].split()
        totalcap2 = float(tokens[3]) * 1e12

    # Get the result from FasterCap
    with open(infile1A, 'r') as ifile:
        lines = ifile.read().splitlines()
        # Get first three values (metal, conductor, width) which should be the same
        # for all lines.
        tokens = lines[0].split()
        metal = tokens[0]
        cond = tokens[1]
        width = float(tokens[2])

        sep1 = []
        ffringe1 = []
        for line in lines:
            tokens = line.split()
            sep1.append(-float(tokens[3]))
            # Convert coupling cap to aF/um and subtract from the result for a
            # single wire (i.e., infinite separation)
            fcoup1 = (float(tokens[6]) * 1e12) / totalcap1
            ffringe1.append(fcoup1)

    # Get the result from magic
    with open(infile2A, 'r') as ifile:
        lines = ifile.read().splitlines()
        # Check values from first line and make sure the metal width
        # agrees for both files
        tokens = lines[0].split()

        if width == float(tokens[2]):
            sep2 = []
            ffringe2 = []
            for line in lines:
                tokens = line.split()
                sep2.append(-float(tokens[3]))
                # Convert coupling cap to aF/um and subtract from the result for a
                # single wire (i.e., infinite separation)
                fcoup2 = (float(tokens[6]) * 1e12) / totalcap2
                ffringe2.append(fcoup2)

    # Compute the analytic partial fringe
    fpmult = fprec[0]
    fpoffset = fprec[1]

    # Get analytic values for the area cap and maximum single-side fringe.
    carea = areacap[metal + '+' + cond]
    cfringe = fringe[metal + '+' + cond]
    ctotal = carea + 2 * cfringe

    ftest = []
    for sval in sep1:
        frac = 0.6366 * numpy.arctan(fpmult * (sval + fpoffset))
        ftest.append((carea + cfringe * (1 + frac)) / ctotal)

    # Now plot all three results using matplotlib
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.plot(sep1, ffringe1, label='FasterCap')
    ax.plot(sep2, ffringe2, label='Magic')
    ax.plot(sep1, ftest, label='Analytic')
    ax.set_xlabel('Coupling layer width (um)')
    ax.set_ylabel('Partial fringe capacitance (fraction)')
    ax.grid(True)
    legend = ax.legend(loc = 2, bbox_to_anchor = (1.05, 1), borderaxespad=0.)
    ax.set_title(metal + ' to ' + cond + ' partial fringe amount vs. width of coupling layer')

    os.makedirs('plots/fringepartial', exist_ok=True)
    canvas.print_figure('plots/fringepartial/' + metal + '_' + cond + '.svg',
		bbox_inches = 'tight', bbox_extra_artists = [legend])

#--------------------------------------------------------------
# Invoke compute_coefficients.py as an application
#--------------------------------------------------------------

if __name__ == '__main__':

    verbose = 0
    startupfile = None

    #---------------------------------------------------
    # Get arguments
    #---------------------------------------------------

    options = []
    arguments = []
    for item in sys.argv[1:]:
        if item.find('-', 0) == 0:
            options.append(item)
        else:
            arguments.append(item)

    if len(arguments) != 1 and len(arguments) != 2:
        print('Argument length is ' + str(len(arguments)))
        usage()
        sys.exit(1)

    #--------------------------------------------------------------
    # Get options
    #--------------------------------------------------------------

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
    # Obtain the metal stack.  The metal stack file is in the
    # format of executable python, so use exec().
    #--------------------------------------------------------------

    stackupfile = arguments[0]
    if len(arguments) > 1:
        startupfile = arguments[1]

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

    metals, substrates = generate_layers(layers)

    if verbose > 0:
        print('Generating result files.')

    generate_areacap(stackupfile)
    generate_fringe(stackupfile, metals, substrates, limits, verbose)
    generate_sidewall(stackupfile, metals, substrates, limits, verbose)
    generate_fringeshield(stackupfile, metals, substrates, limits, verbose)
    generate_fringepartial(stackupfile, metals, substrates, limits, verbose)

    if verbose > 0:
        print('Computing coefficients.')

    areacap = compute_areacap()
    fringe = compute_fringe(metals, substrates, areacap, 1)
    fringe10 = compute_fringe(metals, substrates, areacap, 10)
    sidewall = compute_sidewall(metals)
    fringeshield = compute_fringeshield(metals, substrates, areacap, fringe10)
    fringepartial = compute_fringepartial(metals, limits, areacap, fringe)

    if verbose > 0:
        print('')

    print('Process stackup ' + stackupfile + ' coefficients:')
    print_coefficients(metals, substrates)
    save_coefficients(metals, substrates, 'analysis/coefficients.txt')

    # Only run validation against magic if a magic startup file was specified on the
    # command line.

    if startupfile:
        if verbose > 0:
            print('')
            print('Validating results against magic tech file:')

        validate_fringe(stackupfile, startupfile, metals, substrates, limits, verbose)
        validate_sidewall(stackupfile, startupfile, metals, substrates, limits, verbose)
        validate_fringeshield(stackupfile, startupfile, metals, substrates, limits, verbose)
        validate_fringepartial(stackupfile, startupfile, metals, substrates, limits, verbose)

    # Test plots
    if have_matplotlib:
        for metal in metals:
            plot_sidewall(metal, sidewall)
            for cond in substrates:
                plot_fringeshield(metal, cond, areacap, fringe10, fringeshield)
                plot_fringepartial(metal, cond, areacap, fringe10, fringepartial)
            for cond in metals:
                plot_fringeshield(metal, cond, areacap, fringe10, fringeshield)
                plot_fringepartial(metal, cond, areacap, fringe10, fringepartial)

    sys.exit(0)
