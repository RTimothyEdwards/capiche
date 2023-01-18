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
# 4.  Fringe capacitance with near-body shielding = D * (2/pi) * atan(E * (sep + F))
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
#       on the shielded side only.  Curve fit to D * (2/pi) * atan(E * (sep + F)).
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
import time
import datetime
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

from calc_parallel import calc_parallel
from build_fc_files_w1 import build_fc_files_w1
from build_fc_files_w1n import build_fc_files_w1n
from build_fc_files_w1sh import build_fc_files_w1sh
from build_fc_files_w2 import build_fc_files_w2

from build_mag_files_w1 import build_mag_files_w1
from build_mag_files_w1sh import build_mag_files_w1sh
from build_mag_files_w2 import build_mag_files_w2

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

def generate_areacap(process, stackupfile, verbose=0):
    if not os.path.isfile(process + '/analysis/areacap/results.txt'):
        calc_parallel(stackupfile,
		process + '/analysis/areacap/results.txt',
		verbose)

#--------------------------------------------------------------
# Generate result files for fringe capacitance
#--------------------------------------------------------------

def generate_fringe(process, stackupfile, metals, substrates, limits, verbose=0):

    # Get total capacitance, wire to substrate.  Run the
    # one-wire generator for each set of layers independently,
    # and with higher tolerance than the default.  Find values
    # at the wire minimum width and 10 times the minimum width,
    # since both cases are used later in this analysis.

    subverbose = (verbose - 1) if verbose > 0 else 0

    for metal in metals:
        minwidth = limits[metal][0]
        for subs in substrates:
            if 'diff' in subs and metal == 'poly':
                continue
            if not os.path.isfile(process + '/analysis/fringe/' + metal + '_' + subs + '.txt'):
                if verbose > 0:
                    print('Finding downward fringe for ' + metal + ' + ' + subs)
                build_fc_files_w1(stackupfile,
			[metal],
			[subs],
			[minwidth, 10 * minwidth],
			process + '/analysis/fringe/' + metal + '_' + subs + '.txt',
			0.001,
			subverbose)

        for idx,cond in enumerate(metals):
            if cond == metal:
                break
            if not os.path.isfile(process + '/analysis/fringe/' + metal + '_' + cond + '.txt'):
                if verbose > 0:
                    print('Finding downward fringe for ' + metal + ' + ' + cond)
                build_fc_files_w1(stackupfile,
			[metal],
			[cond],
			[minwidth, 10 * minwidth],
			process + '/analysis/fringe/' + metal + '_' + cond + '.txt',
			0.001,
			subverbose)
    
        for cond in metals[idx+1:]:
            if not os.path.isfile(process + '/analysis/fringe/' + metal + '_' + cond + '.txt'):
                if verbose > 0:
                    print('Finding upward fringe for ' + metal + ' + ' + cond)
                build_fc_files_w1n(stackupfile,
			[metal],
			[cond],
			[minwidth, 10 * minwidth],
			process + '/analysis/fringe/' + metal + '_' + cond + '.txt',
			0.001,
			subverbose)

#-------------------------------------------------------------------------
# Generate result files for sidewall capacitance
#-------------------------------------------------------------------------

def generate_sidewall(process, stackupfile, metals, substrates, limits, verbose=0):

    # NOTE:  To do:  Check result over all substrate and shield types, not
    # just the base substrate.  Some portion of the coupling between the
    # undersides of the wires is lost to the substrate, an effect that
    # increases as the substrate or shield plane gets closer to the wires.

    subverbose = (verbose - 1) if verbose > 0 else 0
    subs = substrates[0]

    for metal in metals:
        # Set width start/stop/step for single run at minimum width
        minwidth = limits[metal][0]
        minsep =   limits[metal][1]

        # Set separation start/stop/step from minimum step out to 20 microns
        # at 0.25um increments
        seps = list(numpy.arange(minsep, 20.0, 0.25))

        if not os.path.isfile(process + '/analysis/sidewall/' + metal + '_' + metal + '.txt'):
            if verbose > 0:
                print('Finding sidewall coupling for ' + metal)
            build_fc_files_w2(stackupfile,
			[metal],
			[subs],
			[minwidth],
			seps,
			process + '/analysis/sidewall/' + metal + '_' + metal + '.txt',
			0.008,
			subverbose)

#-------------------------------------------------------------------------
# Generate result files for fringe shielding model
#-------------------------------------------------------------------------

def generate_fringeshield(process, stackupfile, metals, substrates, limits, verbose=0):

    subverbose = (verbose - 1) if verbose > 0 else 0

    for metal in metals:
        minwidth = limits[metal][0]
        minsep =   limits[metal][1]

        # Set width start/stop/step for single run at 10*minimum width
        width = minwidth * 10
        wspec = '{:.3f}'.format(width)

        # Set separation start/stop/step from minimum step out to 20 microns
        # at 0.25um increments
        seps = list(numpy.arange(minsep, 10.0, 0.25))

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

            if not os.path.isfile(process + '/analysis/fringeshield/' + metal + '_' + conductor + '.txt'):
                if verbose > 0:
                    print('Finding fringe shielding for ' + metal + ' width ' + wspec + ' over ' + conductor)
                build_fc_files_w2(stackupfile,
			[metal],
			[conductor],
			[width],
			seps,
			process + '/analysis/fringeshield/' + metal + '_' + conductor + '.txt',
			0.001,
			subverbose)

#-------------------------------------------------------------------------
# Generate result files for partial fringe modeling
#-------------------------------------------------------------------------

def generate_fringepartial(process, stackupfile, metals, substrates, limits, verbose=0):

    subverbose = (verbose - 1) if verbose > 0 else 0
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

            # Set width start/stop/step for single run at minimum width
            minwidth = limits[metal][0]

            # Set separation start/stop/step from wire edge out to 15 microns
            # at 0.25um increments
            seps = list(numpy.arange(-minwidth / 2, -15.0, -0.25))

            if not os.path.isfile(process + '/analysis/fringepartial/' + metal + '_' + conductor + '.txt'):
                if verbose > 0:
                    print('Finding partial fringe for ' + metal + ' coupling to ' + conductor)
                build_fc_files_w1sh(stackupfile,
			[metal],
			[conductor],
			subs,
			[minwidth],
			seps,
			process + '/analysis/fringepartial/' + metal + '_' + conductor + '.txt',
			0.001,
			subverbose)

#-----------------------------------------------------------------------------
# Get area capacitances by direct calculation (results in areacap_results.txt)
#-----------------------------------------------------------------------------

def compute_areacap(process):
    # "areacap" is a dictionary with entry keys "<layer>+<layer>"
    # and value in aF/um^2.

    areacap = {}
    with open(process + '/analysis/areacap/results.txt', 'r') as ifile:
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

def compute_fringe(process, metals, substrates, areacap, size):

    # "fringe" is a dictionary with entry keys "<layer>+<layer>" and value in aF/um.
    fringe = {}

    for metal in metals:
        minwidth = limits[metal][0]
        width = minwidth * size

        for subs in substrates:
            if 'diff' in subs and metal == 'poly':
                continue
            with open(process + '/analysis/fringe/' + metal + '_' + subs + '.txt', 'r') as ifile:
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
            with open(process + '/analysis/fringe/' + metal + '_' + cond + '.txt', 'r') as ifile:
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
                        if verbose > 2:
                            print('metal = ' + metal + ' cond = ' + cond + ' totalcap = ' + '{:.3f}'.format(totalcap) + ' platecap = ' + '{:.3f}'.format(platecap) + ' totalfringe = ' + '{:.3f}'.format(totalfringe) + ' fringe = ' + '{:.3f}'.format(fringe[metal + '+' + cond]))

    return fringe

#-------------------------------------------------------------------------
# Get coefficients B and C (with curve fitting)
#-------------------------------------------------------------------------

def compute_sidewall(process, metals):

    sidewall = {}

    # Unlike the previous runs, which get coefficients directly through the FasterCap
    # result(s), this one requires analysis through curve fitting.
    # Basic sidewall capacitance fits a curve C_coup = B / (sep - C) to get coefficients B and C
    # to plug into magic's tech file.

    for metal in metals:
        xdata = []
        ydata = []
        with open(process + '/analysis/sidewall/' + metal + '_' + metal + '.txt', 'r') as ifile:
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

        # Use scipy least_squares to do a nonlinear curve fit to y = b / (x + c)
        def func1(x, b, c):
            return b / (x + c)

        # curve_fit needs a seed value somewhere in the range of sanity
        p0 = [1e-11, 0]
        params, _ = scipy.optimize.curve_fit(func1, xdata, ydata, p0=p0)

        # Save results.  Convert value B to aF/um (value C is already in um).
        sidewall[metal] = (params[0] * 1e12, params[1])

    return sidewall
    
#-------------------------------------------------------------------------
# Get coefficients E and F (with curve fitting)
#-------------------------------------------------------------------------

def compute_fringeshield(process, metals, limits, substrates, areacap, fringe10):

    # More analysis through curve fitting using scipy
    # Fringe capacitance shielding (fraction) fits a curve
    # F_shield = (2/pi) * atan(E * (sep + F)) to get coefficients E and F
    # for modeling

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

            with open(process + '/analysis/fringeshield/' + metal + '_' + conductor + '.txt', 'r') as ifile:
                cdata = ifile.read()
                for line in cdata.splitlines():
                    tokens = line.split()
                    # Already know the first three entries.  Get the fourth entry (separation)
                    # for xdata and the sixth entry (coupling) for ydata
                    # ycdata = float(tokens[4]) * 1e12
                    # yvalue = (ycdata - platecap - totfringe) / totfringe
                    # if yvalue < 1:
                    #   xdata.append(float(tokens[3]))
                    #   ydata.append(yvalue)
                    xdata.append(float(tokens[3]))
                    ydata.append(float(tokens[4]))

            # Use scipy least_squares to do a nonlinear curve fit to
            # y = (2/pi) * atan(e * (x + f))

            def func2(x, a, b, c, d):
                return a + b * 0.6366 * numpy.arctan(c * (x + d))

            try:
                p0 = [ydata[0], ydata[-1] - ydata[0], 1, 0]
                params, _ = scipy.optimize.curve_fit(func2, xdata, ydata, p0=p0)
            except:
                # Warning:  This works around an issue with running curve fitting that
                # needs to be investigated.
                fringeshield[metal + '+' + conductor] = (0, 0)
            else:
                # Save results.  Value E is unitless and F is in microns.
                # fringeshield[metal + '+' + conductor] = (params[0], params[1])
                fringeshield[metal + '+' + conductor] = (params[2], params[3])

    return fringeshield
    
#-------------------------------------------------------------------------
# Get coefficients G and H (with curve fitting)
#-------------------------------------------------------------------------

def compute_fringepartial(process, metals, limits, areacap, fringe):

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
            with open(process + '/analysis/fringepartial/' + metal + '_' + conductor + '.txt', 'r') as ifile:
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

            # ydata = []
            # for y in ycdata:
            #     ydata.append((y - platecap - totfringe) / totfringe)

            # Use scipy least_squares to do a nonlinear curve fit to y = 0.6366 * atan(g * (x + h))
            def func3(x, a, b, c, d):
                return a + b * 0.6366 * numpy.arctan(c * (x + d))

            p0 = [ycdata[0], ycdata[-1] - ycdata[0], 1, 0]
            # params, _ = scipy.optimize.curve_fit(func3, xdata, ydata, p0=p0)
            params, _ = scipy.optimize.curve_fit(func3, xdata, ycdata, p0=p0)

            # Save results.  Value G is unitless and H is in microns.
            # The first two parameters represent the constant area cap and fringe on the
            # left-hand side of the wire.
            fringepartial[metal + '+' + conductor] = (params[2], params[3])

    return fringepartial
    
#--------------------------------------------------------------
# Validate fringe capacitance in magic
#--------------------------------------------------------------

def validate_fringe(process, stackupfile, startupfile, metals, substrates, limits, verbose=0):
    # Get total capacitance, wire to substrate.  Run the
    # one-wire generator for each set of layers independently,
    # and with higher tolerance than the default.  Find values
    # at the wire minimum width and 10 times the minimum width,
    # since both cases are used later in this analysis.

    subverbose = (verbose - 1) if verbose > 0 else 0

    for metal in metals:
        minwidth = limits[metal][0]
        wstart = '{:.2f}'.format(minwidth)
        wstop = '{:.2f}'.format(11 * minwidth)
        wstep = '{:.2f}'.format(9 * minwidth)
        for subs in substrates:
            if 'diff' in subs and metal == 'poly':
                continue
            if not os.path.isfile(process + '/validate/fringe/' + metal + '_' + subs + '.txt'):
                if verbose > 0:
                    print('Finding downward fringe for ' + metal + ' + ' + subs)
                build_mag_files_w1(stackupfile, startupfile,
			[metal],
			[subs],
			[minwidth, 10 * minwidth],
			 process + '/validate/fringe/' + metal + '_' + subs + '.txt',
			subverbose)

        for idx,cond in enumerate(metals):
            if cond == metal:
                break
            if not os.path.isfile(process + '/validate/fringe/' + metal + '_' + cond + '.txt'):
                if verbose > 0:
                    print('Finding downward fringe for ' + metal + ' + ' + cond)
                build_mag_files_w1(stackupfile, startupfile,
			[metal],
			[cond],
			[minwidth, 10 * minwidth],
			process + '/validate/fringe/' + metal + '_' + cond + '.txt',
			subverbose)

        for cond in metals[idx+1:]:
            if not os.path.isfile(process + '/validate/fringe/' + metal + '_' + cond + '.txt'):
                if verbose > 0:
                    print('Finding upward fringe for ' + metal + ' + ' + cond)
                build_mag_files_w1(stackupfile, startupfile,
			[metal],
			[cond],
			[minwidth, 10 * minwidth],
			process + '/validate/fringe/' + metal + '_' + cond + '.txt',
			subverbose)

#-------------------------------------------------------------------------
# Validate sidewall capacitance in magic
#-------------------------------------------------------------------------

def validate_sidewall(process, stackupfile, startupfile, metals, substrates, limits, verbose=0):

    # NOTE:  To do:  Check result over all substrate and shield types, not
    # just the base substrate.  Some portion of the coupling between the
    # undersides of the wires is lost to the substrate, an effect that
    # increases as the substrate or shield plane gets closer to the wires.

    subverbose = (verbose - 1) if verbose > 0 else 0
    subs = substrates[0]

    for metal in metals:
        # Set width start/stop/step for single run at minimum width
        minwidth = limits[metal][0]
        minsep =   limits[metal][1]

        # Set separation start/stop/step from minimum step out to 20 microns
        # at 0.25um increments
        seps = list(numpy.arange(minsep, 20.0, 0.25))

        if not os.path.isfile(process + '/validate/sidewall/' + metal + '_' + metal + '.txt'):
            if verbose > 0:
                print('Finding sidewall coupling for ' + metal)
            build_mag_files_w2(stackupfile, startupfile,
			[metal],
			[subs],
			[minwidth],
			seps,
			process + '/validate/sidewall/' + metal + '_' + metal + '.txt',
			subverbose)

#-------------------------------------------------------------------------
# Validate fringe shielding model in magic
#-------------------------------------------------------------------------

def validate_fringeshield(process, stackupfile, startupfile, metals, substrates, limits, verbose=0):

    subverbose = (verbose - 1) if verbose > 0 else 0

    for metal in metals:
        minwidth = limits[metal][0]
        minsep =   limits[metal][1]

        # Set width start/stop/step for single run at 10*minimum width
        width = minwidth * 10
        wspec = '{:.3f}'.format(width)

        # Set separation start/stop/step from minimum step out to 20 microns
        # at 0.25um increments
        seps = list(numpy.arange(minsep, 10.0, 0.25))

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

            if not os.path.isfile(process + '/validate/fringeshield/' + metal + '_' + conductor + '.txt'):
                if verbose > 0:
                    print('Finding fringe shielding for ' + metal + ' width ' + wspec + ' over ' + conductor)
                build_mag_files_w2(stackupfile, startupfile,
			[metal],
			[conductor],
			[width],
			seps,
			process + '/validate/fringeshield/' + metal + '_' + conductor + '.txt',
			subverbose)

#-------------------------------------------------------------------------
# Validate partial fringe model in magic
#-------------------------------------------------------------------------

def validate_fringepartial(process, stackupfile, startupfile, metals, substrates, limits, verbose=0):

    subverbose = (verbose - 1) if verbose > 0 else 0
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

            # Set metal width for single run at minimum width
            minwidth = limits[metal][0]

            # Set separation start/stop/step from wire edge out to 15 microns
            # at 0.25um increments
            seps = list(numpy.arange(-minwidth / 2, -15.0, -0.25))

            if not os.path.isfile(process + '/validate/fringepartial/' + metal + '_' + conductor + '.txt'):
                if verbose > 0:
                    print('Finding partial fringe for ' + metal + ' coupling to ' + conductor)
                build_mag_files_w1sh(stackupfile, startupfile,
			[metal],
			[conductor],
                        subs,
			[minwidth],
			seps,
			process + '/validate/fringepartial/' + metal + '_' + conductor + '.txt',
			subverbose)

#-------------------------------------------------------------------------
# Print out all results
#-------------------------------------------------------------------------

def print_coefficients(metals, substrates, areacap, fringe, sidewall, fringeshield, fringepartial):
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

def save_coefficients(metals, substrates, areacap, fringe, sidewall, fringeshield, fringepartial, outfile):
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

def plot_sidewall(process, metal, sidewall):

    # Check validity of metal
    try:
        swrec = sidewall[metal]
    except:
        return

    infile1 = process + '/analysis/sidewall/' + metal + '_' + metal + '.txt'
    infile2 = process + '/validate/sidewall/' + metal + '_' + metal + '.txt'

    # Allow plots without validation results from magic
    validated = True
    if not os.path.isfile(infile2):
        validated = False

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
    if validated:
        with open(infile2, 'r') as ifile:
            lines = ifile.read().splitlines()
            # Check values from first line and make sure the metal width
            # agrees for both files
            tokens = lines[0].split()

            sep2 = []
            ccoup2 = []
            if abs(width - float(tokens[2])) < 0.01:
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

    ctest2 = []
    for sval in sep1:
        ctest2.append(swmult / sval)

    # Now plot all three results using matplotlib
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.plot(sep1, ccoup1, label='FasterCap')
    if validated:
        ax.plot(sep2, ccoup2, label='Magic')
    ax.plot(sep1, ctest, label='Analytic')
    ax.plot(sep1, ctest2, label='Analytic, no offset')
    ax.set_xlabel('Wire separation (um)')
    ax.set_ylabel('Sidewall capacitance (aF/um)')
    ax.grid(True)
    legend = ax.legend(loc = 2, bbox_to_anchor = (1.05, 1), borderaxespad=0.)
    ax.set_title(metal + ' sidewall capacitance vs. wire separation')

    os.makedirs(process + '/plots/sidewall', exist_ok=True)
    canvas.print_figure(process + '/plots/sidewall/' + metal + '_' + metal + '.svg',
		bbox_inches = 'tight', bbox_extra_artists = [legend])

#--------------------------------------------------------------
# Plot fringe shielding capacitance data
#--------------------------------------------------------------

def plot_fringeshield(process, metal, width, cond, areacap, fringe, fringeshield):

    # Check if metal + cond combination is valid
    try:
        fsrec = fringeshield[metal + '+' + cond]
    except:
        return

    infile1A = process + '/analysis/fringeshield/' + metal + '_' + cond + '.txt'
    infile2A = process + '/validate/fringeshield/' + metal + '_' + cond + '.txt'

    infile1B = process + '/analysis/fringe/' + metal + '_' + cond + '.txt'
    infile2B = process + '/validate/fringe/' + metal + '_' + cond + '.txt'

    validated = True
    if not os.path.isfile(infile2A):
        validated = False

    # Get the result for single wire (effectively, separation = infinite)
    # NOTE:  The assumption is that this file has two lines, and the 2nd line
    # has a wire width of 10x the minimum, which matches the width used in the
    # fringeshield directory results.  To do:  Plot for any width or across
    # widths.

    with open(infile1B, 'r') as ifile:
        lines = ifile.read().splitlines()
        tokens = lines[1].split()
        totalcap1 = float(tokens[3]) * 1e12

    if validated:
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
    if validated:
        with open(infile2A, 'r') as ifile:
            lines = ifile.read().splitlines()
            # Check values from first line and make sure the metal width
            # agrees for both files
            tokens = lines[0].split()

            sep2 = []
            fshield2 = []
            for line in lines:
                tokens = line.split()
                if abs(width - float(tokens[2])) < 0.01:
                    sep2.append(float(tokens[3]))
                    # Convert coupling cap to aF/um and subtract from the result for a
                    # single wire (i.e., infinite separation)
                    fcoup2 = (float(tokens[4]) * 1e12) / totalcap2
                    fshield2.append(fcoup2)

    # Compute the analytic fringe shielding
    fsmult = fsrec[0]
    fsoffset = fsrec[1]

    # Get analytic values for the area cap and maximum single-side fringe.
    cpersq = areacap[metal + '+' + cond]
    carea = cpersq * width
    cfringe = fringe[metal + '+' + cond]
    ctotal = carea + 2 * cfringe

    ftest = []
    for sval in sep1:
        frac = 0.6366 * numpy.arctan(fsmult * (sval + fsoffset))
        ftest.append((carea + cfringe * (1 + frac)) / ctotal)

    ftest2 = []
    for sval in sep1:
        frac2 = 0.6366 * numpy.arctan((cpersq * 0.02) * sval)
        ftest2.append((carea + cfringe * (1 + frac2)) / ctotal)

    # Now plot all three results using matplotlib
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.plot(sep1, fshield1, label='FasterCap')
    if validated:
        ax.plot(sep2, fshield2, label='Magic')
    ax.plot(sep1, ftest, label='Analytic')
    ax.plot(sep1, ftest2, label='Analytic, simplified')
    ax.set_xlabel('Wire separation (um)')
    ax.set_ylabel('Fringe capacitance shielding (fraction)')
    ax.grid(True)
    legend = ax.legend(loc = 2, bbox_to_anchor = (1.05, 1), borderaxespad=0.)
    ax.set_title(metal + ' to ' + cond + ' fringe shielding vs. wire separation')

    os.makedirs(process + '/plots/fringeshield', exist_ok=True)
    canvas.print_figure(process + '/plots/fringeshield/' + metal + '_' + cond + '.svg',
		bbox_inches = 'tight', bbox_extra_artists = [legend])

#--------------------------------------------------------------
# Plot partial fringe capacitance data
#--------------------------------------------------------------

def plot_fringepartial(process, metal, width, cond, areacap, fringe, fringepartial):

    # Check if metal + cond combination is valid
    try:
        fprec = fringepartial[metal + '+' + cond]
    except:
        return

    infile1A = process + '/analysis/fringepartial/' + metal + '_' + cond + '.txt'
    infile2A = process + '/validate/fringepartial/' + metal + '_' + cond + '.txt'

    infile1B = process + '/analysis/fringe/' + metal + '_' + cond + '.txt'
    infile2B = process + '/validate/fringe/' + metal + '_' + cond + '.txt'

    validated = True
    if not os.path.isfile(infile2A):
        validated = False

    # Get the result for single wire (effectively, separation = infinite)
    # NOTE:  The assumption is that this file has two lines, and the 1st line
    # has a minimum wire width, which matches the width used in the
    # fringepartial directory results.  To do:  Plot for any width or across
    # widths.

    with open(infile1B, 'r') as ifile:
        lines = ifile.read().splitlines()
        tokens = lines[0].split()
        totalcap1 = float(tokens[3]) * 1e12

    if validated:
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
    if validated:
        with open(infile2A, 'r') as ifile:
            lines = ifile.read().splitlines()
            # Check values from first line and make sure the metal width
            # agrees for both files
            tokens = lines[0].split()

            sep2 = []
            ffringe2 = []
            if abs(width - float(tokens[2])) < 0.01:
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
    cpersq = areacap[metal + '+' + cond]
    carea = cpersq * width
    cfringe = fringe[metal + '+' + cond]
    ctotal = carea + 2 * cfringe

    ftest = []
    for sval in sep1:
        frac = 0.6366 * numpy.arctan(fpmult * (sval + fpoffset))
        ftest.append((carea + cfringe * (1 + frac)) / ctotal)

    ftest2 = []
    for sval in sep1:
        frac2 = 0.6366 * numpy.arctan((cpersq * 0.015) * sval)
        ftest2.append((carea + cfringe * (1 + frac2)) / ctotal)

    # Now plot all three results using matplotlib
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.plot(sep1, ffringe1, label='FasterCap')
    if validated:
        ax.plot(sep2, ffringe2, label='Magic')
    ax.plot(sep1, ftest, label='Analytic')
    ax.plot(sep1, ftest2, label='Analytic, simplified')
    ax.set_xlabel('Coupling layer width (um)')
    ax.set_ylabel('Partial fringe capacitance (fraction)')
    ax.grid(True)
    legend = ax.legend(loc = 2, bbox_to_anchor = (1.05, 1), borderaxespad=0.)
    ax.set_title(metal + ' to ' + cond + ' partial fringe amount vs. width of coupling layer')

    os.makedirs(process + '/plots/fringepartial', exist_ok=True)
    canvas.print_figure(process + '/plots/fringepartial/' + metal + '_' + cond + '.svg',
		bbox_inches = 'tight', bbox_extra_artists = [legend])

#---------------------------------------------------------------
# Simple routines to print out the current time and elapsed time
#---------------------------------------------------------------

def print_elapsed_time(tstart, verbose):
    if verbose > 0:
        ftime = '{:.0f}'.format(time.time() - tstart)
        print('Elapsed time: ' + ftime + ' seconds.') 

def print_current_time(verbose):
    if verbose > 0:
        ftime = datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        print('Current datestamp: ' + ftime)

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

    try:
        exec(open(stackupfile, 'r').read())
    except:
        print('Error:  No metal stack file ' + stackupfile + '!')
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

    if len(arguments) > 1:
        startupfile = arguments[1]
    else:
        # Check two standard places for open_pdks installation
        
        startupfile = '/usr/local/share/pdk/' + process + '/libs.tech/magic/' + process + '.magicrc'
        if not os.path.isfile(startupfile):
            startupfile = '/usr/share/pdk/' + process + '/libs.tech/magic/' + process + '.magicrc'
            if not os.path.isfile(startupfile):
                startupfile = None
  
    metals, substrates = generate_layers(layers)

    tstart = time.time()
    if verbose > 0:
        print('Generating result files.')

    print_current_time(verbose)
    generate_areacap(process, stackupfile, verbose)
    generate_fringe(process, stackupfile, metals, substrates, limits, verbose)
    print_elapsed_time(tstart, verbose)
    generate_sidewall(process, stackupfile, metals, substrates, limits, verbose)
    print_elapsed_time(tstart, verbose)
    generate_fringeshield(process, stackupfile, metals, substrates, limits, verbose)
    print_elapsed_time(tstart, verbose)
    generate_fringepartial(process, stackupfile, metals, substrates, limits, verbose)
    print_elapsed_time(tstart, verbose)

    if verbose > 0:
        print('Done.')

    print_current_time(verbose)

    if verbose > 0:
        print('Computing coefficients.')

    areacap = compute_areacap(process)
    fringe = compute_fringe(process, metals, substrates, areacap, 1)
    fringe10 = compute_fringe(process, metals, substrates, areacap, 10)
    sidewall = compute_sidewall(process, metals)
    fringeshield = compute_fringeshield(process, metals, limits, substrates, areacap, fringe10)
    fringepartial = compute_fringepartial(process, metals, limits, areacap, fringe)

    if verbose > 0:
        print('Done.\n')

    print_current_time(verbose)
    print('')
    print('Process stackup ' + stackupfile + ' coefficients:')
    print_coefficients(metals, substrates, areacap, fringe, sidewall, fringeshield, fringepartial)
    save_coefficients(metals, substrates, areacap, fringe, sidewall, fringeshield, fringepartial, process + '/analysis/coefficients.txt')

    # Only run validation against magic if a magic startup file was specified on the
    # command line.

    if startupfile:
        if verbose > 0:
            print('')
            print('Magic startup file ' + startupfile + ' found.')
            print('Validating results against magic tech file:')

        validate_fringe(process, stackupfile, startupfile, metals, substrates, limits, verbose)
        print_elapsed_time(tstart, verbose)
        validate_sidewall(process, stackupfile, startupfile, metals, substrates, limits, verbose)
        print_elapsed_time(tstart, verbose)
        validate_fringeshield(process, stackupfile, startupfile, metals, substrates, limits, verbose)
        print_elapsed_time(tstart, verbose)
        validate_fringepartial(process, stackupfile, startupfile, metals, substrates, limits, verbose)
        print_elapsed_time(tstart, verbose)
        if verbose > 0:
            print('Done.')
    else:
        print('No magic startup file found for process ' + process + '.  Not validating results.')

    # Test plots
    if have_matplotlib:
        print('Generating plots:')
        for metal in metals:
            minwidth = limits[metal][0]
            plot_sidewall(process, metal, sidewall)
            for cond in substrates:
                plot_fringeshield(process, metal, minwidth * 10, cond, areacap, fringe10, fringeshield)
                plot_fringepartial(process, metal, minwidth, cond, areacap, fringe, fringepartial)
            for cond in metals:
                plot_fringeshield(process, metal, minwidth * 10, cond, areacap, fringe10, fringeshield)
                plot_fringepartial(process, metal, minwidth, cond, areacap, fringe, fringepartial)
        if verbose > 0:
            print('Done.')
    else:
        print('No matplotlib package;  skipping plot generation.')

    print_current_time(verbose)
    print_elapsed_time(tstart, verbose)
    sys.exit(0)
