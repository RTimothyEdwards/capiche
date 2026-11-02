#!/usr/bin/env python3
#
# build_fc_files_c3d.py --
#
#	Create 3D FasterCap files to find the fringe capacitance
#	at the corners of a wire, and run the simulations.  The
#	2D cross-section simulations (versions _w1 etc.) capture
#	the fringe capacitance of edges but cannot say anything
#	about corners;  this script measures the corner excess
#	directly from 3D simulations.
#
#	Method:  For each wire metal over a reference conductor,
#	simulate a rectangular wire of fixed width at several
#	lengths.  Capacitance is linear in length:
#
#	    C(L) = slope * L + intercept
#
#	where slope = areacap * width + 2 * edgecap (the per-unit-
#	length contribution measured with the same 3D
#	discretization), and
#
#	    intercept = 2 * width * edgecap + 4 * corner_convex
#
#	(the two end edges plus four convex corners).  The area
#	coefficient is computed analytically for the (planarized)
#	dielectric stack, so the convex corner value follows from
#	the fit without reference to any 2D results.
#
#	For the concave corner, an L-shaped (bent) wire is
#	compared against a straight wire with the same area and
#	the same perimeter;  the two differ only by one convex
#	plus one concave corner, so the capacitance difference
#	gives (convex + concave) directly, with area, edge, and
#	(to first order) end effects cancelling.  A square ring
#	(annulus), which adds four identical concave corners, is
#	available with the -ring option as a cross-check, but
#	needs a much larger simulation volume for the same
#	accuracy because its hole must exceed twice the fringe
#	halo.
#
#	To keep the number of (expensive) 3D simulations low, the
#	default is one width (10x minimum width, matching the
#	value at which the 2D fringe results decouple the two wire
#	edges), three lengths, and one bend, over the first
#	substrate type only.
#
#	Results are reported in aF (corners), aF/um (edges), and
#	aF/um^2 (area).  If <process>/analysis/coefficients.txt
#	exists, the corner values are also expressed as the
#	dimensionless factor
#
#	    k = corner * mult / edgecap
#
#	where mult is the fringe shielding multiplier from the 2D
#	analysis.  This is the value of interest for magic's
#	ExtCornerFactor ("extract do corners"), which models the
#	corner capacitance as edgecap * (ExtCornerFactor / mult).
#
# Written by Claude for Tim Edwards
# July 19, 2026
#
import os
import sys
import numpy
import resource
import importlib
import subprocess

# Local files
from .ordered_stack import ordered_stack
from .generate_geometry_3d import (planarize_stack, compute_areacap_3d,
	generate_corner3d_wire_file, generate_corner3d_ring_file,
	generate_corner3d_bend_file)

#--------------------------------------------------------------
# Usage statement
#--------------------------------------------------------------

def usage():
    print('Usage:  build_fc_files_c3d.py <stack_def_file> [options]')
    print('  Where [options] may be one or more of:')
    print('     -metals=<metal>[,...]     (restrict wire type to one or more metals)')
    print('     -conductors=<cond>[,...]  (restrict reference conductor types)')
    print('     -width=<value>            (wire width in microns;  default 10 * minimum width)')
    print('     -lengths=<value>[,...]    (wire lengths in microns;  default scales with fringe halo)')
    print('     -hole=<value>             (ring hole size in microns;  default scales with fringe halo)')
    print('     -margin=<value>           (simulation border in microns;  default scales with fringe halo)')
    print('     -trunc=<value>            (truncate dielectric stack this far above the wire;')
    print('                                default 2 * wire thickness;  0 keeps the full stack)')
    print('     -noconcave                (skip the bend simulations for concave corners)')
    print('     -ring                     (also run ring simulations as a concave cross-check)')
    print('     -tol[erance]=<value>      (FasterCap tolerance;  default 0.002)')
    print('     -timeout=<value>          (FasterCap timeout in seconds;  default 3600)')
    print('     -file=<name>              (output filename for results)')

#--------------------------------------------------------------
# read_coefficients --
#
#	Read the fringecap and fringeshield entries from the 2D
#	analysis coefficients file, if it exists.  Returns two
#	dictionaries keyed by "<metal>+<conductor>":  the fringe
#	capacitance (aF/um, at minimum width) and the fringe
#	shielding multiplier (1/um).
#--------------------------------------------------------------

def read_coefficients(process):
    fringecap = {}
    fringeshield = {}
    cfile = process + '/analysis/coefficients.txt'
    if os.path.isfile(cfile):
        with open(cfile, 'r') as ifile:
            for line in ifile.read().splitlines():
                tokens = line.split()
                if len(tokens) >= 4 and tokens[0] == 'fringecap':
                    fringecap[tokens[1] + '+' + tokens[2]] = float(tokens[3])
                elif len(tokens) >= 5 and tokens[0] == 'fringeshield':
                    fringeshield[tokens[1] + '+' + tokens[2]] = float(tokens[3])
    return (fringecap, fringeshield)

#--------------------------------------------------------------
# estimate_halo --
#
#	Estimate the fringe halo (the lateral distance over which
#	the fringe capacitance of an edge accumulates) for a metal
#	over a reference conductor.  In the model used by magic,
#	the cumulative fringe fraction at distance d is
#	(2/pi) * atan(mult * d), which reaches 90% at
#	d = tan(0.45 * pi) / mult = 6.31 / mult.  If the 2D
#	analysis has been run, use the fringeshield multiplier;
#	otherwise fall back to ten times the wire height above
#	the reference conductor, which approximates the same
#	value for the layer pairs that have been analyzed.
#
#	The wire length sweep must use lengths larger than twice
#	the halo (so that the fringe fields of the two wire ends
#	do not interact and capacitance is linear in length), and
#	the simulation border must be comparable to the halo (so
#	that the fringe field is not truncated).  The halo is
#	capped to keep the largest simulations bounded.
#--------------------------------------------------------------

def estimate_halo(fringeshield, metal, conductor, pstack):
    halo = 0
    key = metal + '+' + conductor
    if key in fringeshield and fringeshield[key] > 0:
        halo = 6.31 / fringeshield[key]
    (zsub, zbase, ztop, slabs) = planarize_stack(pstack)
    if halo == 0:
        halo = 10 * (zbase - zsub)
    # Layers very close to the reference conductor can produce a
    # degenerate (very large) multiplier fit;  keep the halo to at
    # least a few wire heights.
    if halo < 3 * (zbase - zsub):
        halo = 3 * (zbase - zsub)
    if halo > 40:
        halo = 40
    return halo

#--------------------------------------------------------------
# fastercap_limits --
#
#	Limit the address space of the FasterCap child process so
#	that a runaway refinement cannot exhaust system memory.
#	FasterCap does not handle allocation failure and dies with
#	SIGSEGV at the limit, which is tolerated (and retried at a
#	coarser tolerance) by run_fastercap() below;  core dumps
#	are disabled so that each such death does not leave a
#	multi-gigabyte core image behind.
#--------------------------------------------------------------

FASTERCAP_MEM_GB = 24

def fastercap_limits():
    membytes = FASTERCAP_MEM_GB << 30
    resource.setrlimit(resource.RLIMIT_AS, (membytes, membytes))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

#--------------------------------------------------------------
# run_fastercap --
#
#	Run FasterCap on one input file.  FasterCap's automatic
#	refinement (-a) occasionally stops one pass early, giving
#	a result a few percent off;  since the corner analysis
#	extracts a small residual, that is detected here by
#	comparing the last two refinement passes, and the run is
#	retried at a tighter tolerance if they disagree by more
#	than 0.3%.  Runs that time out are retried at a coarser
#	tolerance.
#
#	Returns a list of capacitance matrix row values (in F,
#	one list per conductor group), or None if the run failed.
#--------------------------------------------------------------

def run_fastercap(file, tolerance, timeout, verbose=0):

    fastercapexec = os.getenv('FASTERCAP_EXEC')
    if not fastercapexec:
        fastercapexec = 'FasterCap'

    loctol = tolerance
    attempts = 0
    bestrelerr = None
    bestrows = None
    while True:
        attempts += 1
        tolspec = "-a{:.4f}".format(loctol)
        crashed = False
        try:
            proc = subprocess.run([fastercapexec, '-b', file, tolspec],
			stdin = subprocess.DEVNULL,
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE,
			universal_newlines = True,
			preexec_fn = fastercap_limits,
			timeout = timeout)
        except subprocess.TimeoutExpired:
            loctol *= 2
            if loctol > 0.16:
                print('ERROR:  Failing with high tolerance;  bailing.')
                return None
            if verbose > 0:
                print('Timeout;  trying again with tolerance = ' + '{:.4f}'.format(loctol))
            continue

        if proc.returncode != 0:
            # FasterCap hit the memory limit (it does not handle
            # allocation failure gracefully).  The refinement passes
            # printed before the crash may still contain a converged
            # result, so parse the output anyway.
            crashed = True

        # Parse the capacitance matrix.  Rows look like
        # "g1_<name>  <value> <value> ...".  FasterCap prints the
        # matrix at every refinement pass;  only the last one for
        # each conductor group is the converged result.  The
        # convergence check below compares the mutual capacitance
        # (second value of the first row), which is the quantity
        # used by the corner analysis;  it converges much faster
        # than the self capacitance, which includes the coupling
        # to infinity through the truncated simulation boundary.
        rowvalues = {}
        roworder = []
        prev1 = None
        last1 = None
        for line in proc.stdout.splitlines():
            if verbose > 1:
                print(line)
            tokens = line.split()
            if len(tokens) < 2:
                continue
            if tokens[0].startswith('g') and '_' in tokens[0]:
                try:
                    values = list(map(float, tokens[1:]))
                except ValueError:
                    continue
                if tokens[0] not in roworder:
                    roworder.append(tokens[0])
                rowvalues[tokens[0]] = values
                if tokens[0] == roworder[0]:
                    prev1 = last1
                    last1 = values[1] if len(values) > 1 else values[0]

        relerr = 0
        if prev1 != None and last1 != 0:
            relerr = abs(last1 - prev1) / abs(last1)

        # Keep the best (smallest last-two-pass difference) attempt,
        # in case no attempt fully converges.
        rows = None
        if roworder != []:
            rows = list(map(lambda label: rowvalues[label], roworder))
            if prev1 != None and (bestrelerr == None or relerr < bestrelerr):
                bestrelerr = relerr
                bestrows = rows

        if roworder == [] or prev1 == None or relerr > 0.003:
            # No result, or the last two refinement passes disagree.
            # If the solver crashed, retry at a coarser tolerance
            # (which stops refining earlier and uses less memory);
            # otherwise retry at a tighter tolerance to force another
            # refinement pass.  A case that cannot converge within
            # memory alternates between the two;  cap the number of
            # attempts and fall back to the best attempt seen.
            if attempts >= 4:
                if bestrows != None:
                    print('WARNING:  Result not converged after ' + str(attempts)
				+ ' attempts;  using the best attempt (last two'
				+ ' passes differ by ' + '{:.2%}'.format(bestrelerr) + ')')
                    return bestrows
                print('ERROR:  No result after ' + str(attempts) + ' attempts.')
                return None
            if crashed:
                loctol *= 2
                if loctol > 0.16:
                    print('ERROR:  FasterCap ran out of memory;  no converged result.')
                    return bestrows
                if verbose > 0:
                    print('FasterCap ran out of memory;  retrying with tolerance = '
				+ '{:.4f}'.format(loctol))
                continue
            if roworder == []:
                print('ERROR:  No capacitance matrix in FasterCap output!')
                return None
            if relerr > 0.003 and loctol > 0.00025:
                if verbose > 0:
                    print('Last two passes differ by ' + '{:.2%}'.format(relerr)
				+ ';  retrying with tolerance = '
				+ '{:.4f}'.format(loctol / 2))
                loctol /= 2
                continue
            if relerr > 0.003:
                print('WARNING:  Result not converged (last two passes differ by '
			+ '{:.2%}'.format(relerr) + ')')
        elif crashed:
            print('WARNING:  FasterCap ran out of memory, but the last two passes'
			+ ' agree to ' + '{:.2%}'.format(relerr) + ';  using the result.')

        return rows

#--------------------------------------------------------------
# The main routine
#
# build_fc_files_c3d(stackupfile, metallist, condlist, width,
#	lengths, hole, margin, outfile, tolerance, timeout,
#	concave, ring, verbose)
#
# where:
#	stackupfile = name of the script file with the metal
#		stack definition
#	metallist = list of metals to test as wires
#	condlist = list of conductors/substrates to test
#	width = wire width in microns, or 0 to use the default
#	lengths = list of wire lengths in microns, or None
#	hole = ring hole size in microns, or 0 to use the default
#	margin = simulation border in microns, or 0 for the default
#	trunc = dielectric stack truncation height above the wire
#		top in microns;  0 keeps the full stack, and a
#		negative value selects the default (twice the wire
#		thickness)
#	outfile = name of output file with results
#	tolerance = initial tolerance to use for FasterCap
#	timeout = FasterCap timeout per run, in seconds
#	concave = True to run bend simulations (concave corners)
#	ring = True to also run ring simulations (cross-check)
#	verbose = diagnostic output level
#--------------------------------------------------------------

def build_fc_files_c3d(stackupfile, metallist, condlist, width, lengths, hole,
		margin, trunc, outfile, tolerance, timeout, concave, ring, verbose=0):

    #--------------------------------------------------------------
    # 1. Obtain the metal stack.  The metal stack file is in the
    #    format of executable python, so use exec().
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

    # Set default values if not specified in options.  Unlike the 2D
    # scripts, the default here is deliberately minimal:  only the
    # first substrate type is used as the reference conductor, since
    # the 3D simulations are expensive and the corner behavior vs.
    # the fringe multiplier can be tested across the metal layers.

    if metallist == []:
        print('Using all metals in stackup for set of wire types to test')
        metallist = metals

    if condlist == []:
        print('Using substrate type ' + substrates[0] + ' as the reference conductor')
        condlist = [substrates[0]]

    #--------------------------------------------------------------
    # 2. Generate the geometry files
    #--------------------------------------------------------------

    # Make sure the working directory exists
    os.makedirs(process + '/fastercap_files/c3d', exist_ok=True)

    # Read the 2D analysis coefficients, if they exist.  The fringe
    # shielding multiplier sets the fringe halo, which in turn sets
    # the default wire lengths, ring hole size, and margin;  the
    # coefficients are also used at the end to express the corner
    # values in terms of magic's corner model.
    (fringecap, fringeshield) = read_coefficients(process)

    # Each entry in caselist is [filename, metal, conductor, shape,
    # width, length or hole size]
    caselist = []

    for metal in metallist:
        minwidth = limits[metal][0]
        if width > 0:
            mwidth = width
        else:
            mwidth = 10 * minwidth

        for conductor in condlist:
            # Poly to diff is a transistor gate and is not a parasitic.
            if 'poly' in metal and 'diff' in conductor:
                continue

            pstack = ordered_stack(conductor, [metal], layers)

            if verbose > 1:
                print('Stackup for metal = ' + metal + ' and reference ' + conductor + ':')
                for p in pstack:
                    print(str(p))
                print('')

            # Default dimensions scale with the fringe halo:  wire
            # lengths must exceed twice the halo so that the fringe
            # fields of the two wire ends do not interact, the bend
            # arms must exceed the halo so that the bend corner does
            # not interact with the wire ends, and the margin must
            # not truncate the fringe field.
            mhalo = estimate_halo(fringeshield, metal, conductor, pstack)

            # Bend arm length, and companion straight wire length
            # (same area and perimeter as the bend)
            marm = mhalo + 2 * mwidth
            lbase = 2 * marm - mwidth

            if lengths:
                mlengths = lengths
            else:
                # Four lengths rather than the minimum three, so that
                # a single bad simulation can be identified and
                # dropped by the leave-one-out check in the analysis.
                mlengths = [lbase, 1.25 * lbase, 1.5 * lbase, 1.75 * lbase]

            if hole > 0:
                mhole = hole
            else:
                mhole = max(4 * mwidth, 2 * mhalo)

            # The margin is capped:  beyond the cap, the truncated
            # part of the (slowly saturating) fringe tail is absorbed
            # consistently by the per-length edge term of the fit, at
            # rapidly increasing solver cost for little change in the
            # corner residual.
            if margin > 0:
                mmargin = margin
            else:
                mmargin = max(12, min(mhalo, 20))

            # By default, truncate the dielectric stack at twice the
            # wire thickness above the wire top (see the geometry
            # generator);  -trunc=<value> overrides, -trunc=0 keeps
            # the full stack.
            (zsub, zbase, ztop, slabs) = planarize_stack(pstack)
            if trunc < 0:
                mtrunc = max(1.0, 2 * (ztop - zbase))
            else:
                mtrunc = trunc

            if verbose > 0:
                print(metal + ' over ' + conductor + ':  halo estimate '
			+ "{:.2f}".format(mhalo) + ' um, width '
			+ "{:.2f}".format(mwidth) + ' um, margin '
			+ "{:.2f}".format(mmargin) + ' um')

            wspec = "{:.2f}".format(mwidth).replace('.', 'p')
            for length in mlengths:
                lspec = "{:.2f}".format(length).replace('.', 'p')
                filename = process + '/fastercap_files/c3d/' + metal + '_' + conductor + '_w_' + wspec + '_l_' + lspec + '.lst'
                generate_corner3d_wire_file(filename, conductor, metal, mwidth, length, pstack, mmargin, mtrunc)
                caselist.append([filename, metal, conductor, 'wire', mwidth, length])

            if concave:
                aspec = "{:.2f}".format(marm).replace('.', 'p')
                filename = process + '/fastercap_files/c3d/' + metal + '_' + conductor + '_bend_w_' + wspec + '_a_' + aspec + '.lst'
                generate_corner3d_bend_file(filename, conductor, metal, mwidth, marm, marm, pstack, mmargin, mtrunc)
                caselist.append([filename, metal, conductor, 'bend', mwidth, marm])

            if ring:
                hspec = "{:.2f}".format(mhole).replace('.', 'p')
                filename = process + '/fastercap_files/c3d/' + metal + '_' + conductor + '_ring_w_' + wspec + '_h_' + hspec + '.lst'
                generate_corner3d_ring_file(filename, conductor, metal, mwidth, mhole, pstack, mmargin, mtrunc)
                caselist.append([filename, metal, conductor, 'ring', mwidth, mhole])

    #--------------------------------------------------------------
    # 3. Simulate with fastercap
    #--------------------------------------------------------------

    if tolerance == 0:
        print('Tolerance set to zero;  skipping FasterCap run')
        return 0

    # Each entry in presults is [metal, conductor, shape, width,
    # length or hole size, self capacitance (aF), mutual capacitance
    # to the reference conductor (aF)]
    presults = []

    for case in caselist:
        (filename, metal, conductor, shape, mwidth, dimension) = case
        print('Running FasterCap on input file ' + filename)
        rows = run_fastercap(filename, tolerance, timeout, verbose)
        if not rows:
            continue

        # The wire is the first conductor group;  the reference
        # conductor plane is the second.  Convert from FasterCap
        # units (F, with coordinates in microns) to aF.
        cself = rows[0][0] * 1e12
        cmut = -rows[0][1] * 1e12 if len(rows[0]) > 1 else 0.0

        print('Result:  Cself=' + "{:.5g}".format(cself) + ' aF'
			+ '  Cmutual=' + "{:.5g}".format(cmut) + ' aF')

        presults.append([metal, conductor, shape, mwidth, dimension, cself, cmut])

    #--------------------------------------------------------------
    # 4. Analyze:  fit the length sweep and derive corner values
    #--------------------------------------------------------------

    if len(presults) == 0:
        print('No results to save or print.')
        return 0

    # Collect fit output lines to write after the raw results
    fitlines = []

    for metal in metallist:
        for conductor in condlist:
            wireruns = []
            bendruns = []
            ringruns = []
            for presult in presults:
                if presult[0] == metal and presult[1] == conductor:
                    if presult[2] == 'wire':
                        wireruns.append(presult)
                    elif presult[2] == 'bend':
                        bendruns.append(presult)
                    else:
                        ringruns.append(presult)

            if len(wireruns) < 2:
                continue

            mwidth = wireruns[0][3]
            xdata = list(map(lambda r: r[4], wireruns))
            ydata = list(map(lambda r: r[6], wireruns))

            def linfit(xd, yd):
                (lslope, lintercept) = numpy.polyfit(xd, yd, 1)
                lresid = 0.0
                for i in range(len(xd)):
                    lresid = max(lresid, abs(yd[i] - (lslope * xd[i] + lintercept)))
                return (lslope, lintercept, lresid)

            # Fit capacitance vs. length.  The fit residual should be
            # small;  a large residual means either interacting wire
            # ends (lengths too short) or a simulation that stopped
            # on a false convergence plateau a few percent off.  With
            # four or more lengths, a single such outlier can be
            # identified (dropping it dramatically improves the fit)
            # and removed.
            (slope, intercept, resid) = linfit(xdata, ydata)
            dropped = None
            if len(xdata) >= 4 and resid > 0.004 * ydata[len(ydata) // 2]:
                for i in range(len(xdata)):
                    (tslope, tintercept, tresid) = linfit(
				xdata[:i] + xdata[i + 1:], ydata[:i] + ydata[i + 1:])
                    if tresid < resid / 4:
                        (slope, intercept, resid) = (tslope, tintercept, tresid)
                        dropped = xdata[i]
                if dropped != None:
                    print('NOTE:  ' + metal + ' over ' + conductor
			+ ':  dropped outlier length ' + "{:.2f}".format(dropped)
			+ ' um from the fit.')

            # Area coefficient of the planarized stack (analytic)
            pstack = ordered_stack(conductor, [metal], layers)
            careav = compute_areacap_3d(pstack)

            # Edge fringe per unit length as measured by the 3D runs
            edge3d = (slope - careav * mwidth) / 2

            # Four convex corners plus two end edges make the intercept
            corner_cvx = (intercept - 2 * mwidth * edge3d) / 4

            fitline = 'fit ' + metal + ' ' + conductor \
			+ ' ' + "{:.4f}".format(mwidth) \
			+ ' ' + "{:.4f}".format(careav) \
			+ ' ' + "{:.4f}".format(slope) \
			+ ' ' + "{:.4f}".format(edge3d) \
			+ ' ' + "{:.4f}".format(intercept) \
			+ ' ' + "{:.4f}".format(resid)
            fitlines.append(fitline)

            # Concave corner from the bend:  the difference between
            # the bend and the straight wire with the same area and
            # perimeter is (convex + concave).  Use the measured
            # companion wire if one was run at the matching length;
            # otherwise evaluate the fit at that length.
            corner_ccv = None
            if len(bendruns) > 0:
                marm = bendruns[0][4]
                cbend = bendruns[0][6]
                lcomp = 2 * marm - mwidth
                ccomp = slope * lcomp + intercept
                for wirerun in wireruns:
                    if abs(wirerun[4] - lcomp) < 1e-6:
                        if dropped == None or abs(dropped - lcomp) > 1e-6:
                            ccomp = wirerun[6]
                        break
                corner_ccv = (cbend - ccomp) - corner_cvx

            # Concave corner from the ring (cross-check):  the ring
            # has four convex and four concave corners.
            corner_ring = None
            if len(ringruns) > 0:
                mhole = ringruns[0][4]
                cring = ringruns[0][6]
                outer = mhole + 2 * mwidth
                ringarea = outer * outer - mhole * mhole
                ringperim = 4 * (outer + mhole)
                corner_ring = (cring - careav * ringarea - edge3d * ringperim
				- 4 * corner_cvx) / 4
                if corner_ccv == None:
                    corner_ccv = corner_ring

            cornerline = 'corner ' + metal + ' ' + conductor \
			+ ' ' + "{:.4f}".format(corner_cvx)
            if corner_ccv != None:
                cornerline += ' ' + "{:.4f}".format(corner_ccv)
            fitlines.append(cornerline)

            # Report in terms of magic's corner model, corner =
            # edgecap * (k / mult), using the 3D edge value and (for
            # comparison) the 2D fringecap value from the coefficients
            # file, which is measured at minimum wire width.
            key = metal + '+' + conductor
            if key in fringeshield:
                mult = fringeshield[key]
                k_cvx = corner_cvx * mult / edge3d
                kline = 'kfactor ' + metal + ' ' + conductor \
			+ ' ' + "{:.4f}".format(mult) \
			+ ' ' + "{:.4f}".format(k_cvx)
                if corner_ccv != None:
                    kline += ' ' + "{:.4f}".format(corner_ccv * mult / edge3d)
                fitlines.append(kline)

            # Print the summary for this layer combination
            print('')
            print('Layer ' + metal + ' over ' + conductor + ':')
            print('   area cap (planarized stack) = ' + "{:.3f}".format(careav) + ' aF/um^2')
            print('   edge fringe (3D)  = ' + "{:.3f}".format(edge3d) + ' aF/um')
            if key in fringecap:
                print('   edge fringe (2D, min width) = ' + "{:.3f}".format(fringecap[key]) + ' aF/um')
            print('   fit residual = ' + "{:.3f}".format(resid) + ' aF')
            print('   convex corner  = ' + "{:.3f}".format(corner_cvx) + ' aF')
            if corner_ccv != None:
                print('   concave corner = ' + "{:.3f}".format(corner_ccv) + ' aF')
            if corner_ring != None:
                print('   concave corner (ring cross-check) = '
			+ "{:.3f}".format(corner_ring) + ' aF')
            if key in fringeshield:
                mult = fringeshield[key]
                print('   fringe multiplier (2D fringeshield) = ' + "{:.3f}".format(mult) + ' /um')
                print('   k (vs. 3D edge)  = ' + "{:.4f}".format(corner_cvx * mult / edge3d)
			+ (' convex, ' + "{:.4f}".format(corner_ccv * mult / edge3d)
			+ ' concave' if corner_ccv != None else ' convex'))
                if key in fringecap:
                    print('   k (vs. 2D fringecap) = '
			+ "{:.4f}".format(corner_cvx * mult / fringecap[key])
			+ (' convex, ' + "{:.4f}".format(corner_ccv * mult / fringecap[key])
			+ ' concave' if corner_ccv != None else ' convex'))

    #--------------------------------------------------------------
    # 5. Save results
    #--------------------------------------------------------------

    if not outfile:
        os.makedirs(process + '/analysis/corner3d', exist_ok=True)
        outfile = process + '/analysis/corner3d/results.txt'
    else:
        outdir = os.path.split(outfile)[0]
        if outdir != '':
            os.makedirs(outdir, exist_ok=True)

    with open(outfile, 'w') as ofile:
        print('# 3D corner capacitance results', file=ofile)
        print('# raw <metal> <conductor> <shape> <width> <length|hole> <Cself aF> <Cmutual aF>', file=ofile)
        print('# fit <metal> <conductor> <width> <areacap aF/um^2> <slope aF/um> <edge aF/um> <intercept aF> <residual aF>', file=ofile)
        print('# corner <metal> <conductor> <convex aF> [<concave aF>]', file=ofile)
        print('# kfactor <metal> <conductor> <mult /um> <k convex> [<k concave>]', file=ofile)
        for presult in presults:
            print('raw ' + presult[0] + ' ' + presult[1] + ' ' + presult[2]
			+ ' ' + "{:.4f}".format(presult[3])
			+ ' ' + "{:.4f}".format(presult[4])
			+ ' ' + "{:.5g}".format(presult[5])
			+ ' ' + "{:.5g}".format(presult[6]), file=ofile)
        for fitline in fitlines:
            print(fitline, file=ofile)

    print('')
    print('Results saved to ' + outfile)
    return 0

#---------------------------------------------------
# Invoke build_fc_files_c3d.py as an application
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
    width = 0
    lengths = None
    hole = 0
    margin = 0
    trunc = -1
    outfile = None
    tolerance = 0.002
    timeout = 3600
    concave = True
    ring = False
    verbose = 0

    for option in options:
        tokens = option.split('=')
        if tokens[0] == '-noconcave':
            concave = False
            continue
        if tokens[0] == '-ring':
            ring = True
            continue
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
        elif tokens[0] == '-timeout':
            try:
                timeout = float(tokens[1])
            except:
                print('Error:  Timeout "' + tokens[1] + '" is not numeric.')
                continue
        elif tokens[0] == '-metals':
            metallist = tokens[1].split(',')
        elif tokens[0] == '-conductors':
            condlist = tokens[1].split(',')
        elif tokens[0] == '-width':
            try:
                width = float(tokens[1].replace('um', ''))
            except:
                print('Error:  Width "' + tokens[1] + '" is not numeric.')
                continue
        elif tokens[0] == '-hole':
            try:
                hole = float(tokens[1].replace('um', ''))
            except:
                print('Error:  Hole size "' + tokens[1] + '" is not numeric.')
                continue
        elif tokens[0] == '-margin':
            try:
                margin = float(tokens[1].replace('um', ''))
            except:
                print('Error:  Margin "' + tokens[1] + '" is not numeric.')
                continue
        elif tokens[0] == '-trunc':
            try:
                trunc = float(tokens[1].replace('um', ''))
            except:
                print('Error:  Truncation "' + tokens[1] + '" is not numeric.')
                continue
        elif tokens[0] == '-lengths':
            lengths = []
            for lstr in tokens[1].split(','):
                try:
                    lengths.append(float(lstr.replace('um', '')))
                except:
                    print('Error:  Length "' + lstr + '" is not numeric.')
                    continue
        else:
            print('Error:  Unknown option "' + option + '"')
            usage()
            continue

    # Call the main routine

    rval = build_fc_files_c3d(arguments[0], metallist, condlist, width,
		lengths, hole, margin, trunc, outfile, tolerance, timeout,
		concave, ring, verbose)
    sys.exit(rval)
