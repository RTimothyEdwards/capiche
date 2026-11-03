#!/usr/bin/env python3
#
# solve2d.py --
#
#	Direct 2D boundary-element capacitance solver.  Reads the same 2D
#	".lst" input files that are written for FasterCap and returns the
#	same capacitance matrix.
#
#	FasterCap refines its mesh adaptively and stops when two successive
#	passes agree.  For two closely spaced wires, the result on a coarse
#	mesh can be wrong by a factor of two and can still pass that test
#	(e.g., ihp-sg13cmos5l metal3 at minimum width and spacing has a
#	coupling capacitance of 233.8 aF/um at 32 panels with -a0.01, and
#	134.7 aF/um when converged at 57,000 panels).  This solver instead
#	uses a fixed mesh graded toward every corner, and solves the system
#	directly, so the answer takes about a second and does not depend on
#	a convergence test.
#
#	Method:  Piecewise-constant total charge on straight panels with
#	collocation at the panel midpoints and analytic panel integrals.
#	The conductor named "ground" is an infinite plane, handled by the
#	method of images (FasterCap's own is 100um wide).  Dielectric
#	interfaces use the normal-field boundary condition.
#
#	Input file conventions are from the FasterCap documentation:
#	(xref, yref) lies on the <outperm> side of each dielectric segment,
#	or on the <inperm> side if followed by "-", and is not translated.
#	The charge on a conductor panel is multiplied by the panel's
#	<outperm> to get the free charge.
#

import os
import re
import numpy
import subprocess

# Permittivity of free space, in aF/um.
EPS0 = 8.8541878

# Mesh parameters.  A panel is split if it is longer than MESH_ALPHA times the
# distance from its midpoint to the nearest corner or end of any other segment.
# Panels are not split below MESH_HMIN times the shortest segment in the file.

MESH_ALPHA = 0.3
MESH_HMIN = 0.05

# Memory use grows with the square of the number of panels, at roughly 200
# bytes per matrix entry during assembly (about 7GB at this limit).  Stop with
# an error instead of exhausting the machine's memory.

MAX_PANELS = 6000

#--------------------------------------------------------------
# read_lst --
#
# Read a 2D FasterCap input file.
#
# Results:
#	A tuple (conductors, dielectrics), where "conductors" is a list
#	of conductor groups in order of appearance, not including the
#	reference;  "dielectrics" is a list of dielectric segments.  Each
#	conductor group is a list of segments (x1, y1, x2, y2, outperm).
#	Each dielectric segment is (x1, y1, x2, y2, outperm, inperm,
#	xref, yref, sign), with "sign" +1 if the reference point lies on
#	the outperm side.  Also returned is the Y value of the "ground"
#	conductor.
#--------------------------------------------------------------

def read_lst(filename):

    directives = []
    files = {}
    current = None
    inmain = True

    with open(filename, 'r') as ifile:
        lines = ifile.read().splitlines()

    for line in lines[1:]:
        tokens = line.split()
        if not tokens or tokens[0] == '*' or tokens[0].startswith('*'):
            continue
        key = tokens[0]
        if inmain:
            if key == 'End':
                inmain = False
            elif key == 'C' or key == 'D':
                directives.append(tokens)
            continue
        if key == 'File':
            current = tokens[1]
            files[current] = []
        elif key == 'End':
            current = None
        elif key == 'S' and current is not None:
            files[current].append((tokens[1],) + tuple(float(t) for t in tokens[2:6]))

    groups = []
    dielectrics = []
    ground = None
    newgroup = True

    for tokens in directives:
        segments = files.get(tokens[1])
        if segments is None:
            raise ValueError('File "' + tokens[1] + '" is not defined in ' + filename)

        if tokens[0] == 'C':
            outperm = float(tokens[2])
            dx = float(tokens[3])
            dy = float(tokens[4])
            if newgroup:
                groups.append([])
            for name, x1, y1, x2, y2 in segments:
                if name == 'ground':
                    if y1 != y2:
                        raise ValueError('Ground is not horizontal in ' + filename)
                    if ground is not None and ground != y1 + dy:
                        raise ValueError('More than one ground in ' + filename)
                    ground = y1 + dy
                else:
                    groups[-1].append((x1 + dx, y1 + dy, x2 + dx, y2 + dy, outperm))
            newgroup = (tokens[-1] != '+')
        else:
            outperm = float(tokens[2])
            inperm = float(tokens[3])
            dx = float(tokens[4])
            dy = float(tokens[5])
            xref = float(tokens[6])
            yref = float(tokens[7])
            sign = -1 if tokens[-1] == '-' else 1
            for name, x1, y1, x2, y2 in segments:
                dielectrics.append((x1 + dx, y1 + dy, x2 + dx, y2 + dy,
			outperm, inperm, xref, yref, sign))

    conductors = [g for g in groups if g]

    if ground is None:
        raise ValueError('No conductor named "ground" in ' + filename)
    if not conductors:
        raise ValueError('No conductors in ' + filename)

    return conductors, dielectrics, ground

#--------------------------------------------------------------
# find_corners --
#
# Find the points that the mesh must be graded toward.  These are the
# ends of all segments, other than the far ends of those that extend to
# the edge of the simulated space.
#
# Results:
#	Array of points, shape (n, 2).
#--------------------------------------------------------------

def find_corners(conductors, dielectrics):

    points = []
    for group in conductors:
        for seg in group:
            points.append(seg[0:2])
            points.append(seg[2:4])
    for seg in dielectrics:
        points.append(seg[0:2])
        points.append(seg[2:4])

    # Only an end shared with nothing else on the far outside of the geometry
    # is an edge of the simulated space.

    xlimit = max(abs(p[0]) for p in points)
    points = [p for p in points if abs(p[0]) < xlimit - 1e-6]

    return numpy.unique(numpy.round(numpy.array(points), 6), axis=0)

#--------------------------------------------------------------
# split_segment --
#
# Divide a segment into panels, with the panel size proportional to
# the distance from the nearest corner.
#
# Results:
#	List of panels (x1, y1, x2, y2).
#--------------------------------------------------------------

def split_segment(x1, y1, x2, y2, corners, alpha, hmin):

    panels = []
    stack = [(x1, y1, x2, y2)]
    while stack:
        xa, ya, xb, yb = stack.pop()
        length = numpy.hypot(xb - xa, yb - ya)
        xm = (xa + xb) / 2
        ym = (ya + yb) / 2
        dist = numpy.min(numpy.hypot(corners[:,0] - xm, corners[:,1] - ym))
        if length > alpha * dist and length > 2 * hmin:
            # Pushed in reverse so that panels stay in order
            stack.append((xm, ym, xb, yb))
            stack.append((xa, ya, xm, ym))
        else:
            panels.append((xa, ya, xb, yb))
    return panels

#--------------------------------------------------------------
# panel_integrals --
#
# For unit charge density on each panel, compute the integrals that
# give the potential and the electric field at each observation point.
# Both need to be scaled by 1 / (2 * pi * eps0).
#
# Results:
#	Tuple of arrays (phi, ex, ey), each of shape (nobs, npanels).
#--------------------------------------------------------------

def panel_integrals(xobs, yobs, panels):

    z = (xobs + 1j * yobs)[:, None]
    a = (panels[:,0] + 1j * panels[:,1])[None, :]
    b = (panels[:,2] + 1j * panels[:,3])[None, :]
    length = numpy.abs(b - a)
    rot = (b - a) / length

    # Coordinates relative to each end of the panel, in the panel's frame.
    # Then the integral of ln(z - t) over the panel is
    # u * ln(u) - v * ln(v) - length

    u = (z - a) / rot
    v = u - length

    with numpy.errstate(divide='ignore', invalid='ignore'):
        logu = numpy.log(u)
        logv = numpy.log(v)
        ulogu = numpy.where(numpy.abs(u) > 0, u * logu, 0)
        vlogv = numpy.where(numpy.abs(v) > 0, v * logv, 0)
        field = numpy.conj(logu - logv) * rot

    phi = -(ulogu - vlogv - length).real

    return phi, field.real, field.imag

#--------------------------------------------------------------
# solve_lst --
#
# Find the capacitance matrix for a 2D FasterCap input file.
#
# Results:
#	Matrix (numpy array) in the same form and the same units as
#	reported by FasterCap, with the conductors in the same order
#	and no entry for the reference conductor;  and the number of
#	panels used.
#--------------------------------------------------------------

def solve_lst(filename, alpha=MESH_ALPHA, hmin=MESH_HMIN):

    conductors, dielectrics, ground = read_lst(filename)

    corners = find_corners(conductors, dielectrics)

    # Minimum panel size is relative to the shortest segment in the geometry

    lengths = [numpy.hypot(s[2] - s[0], s[3] - s[1]) for g in conductors for s in g]
    lengths += [numpy.hypot(s[2] - s[0], s[3] - s[1]) for s in dielectrics]
    hsize = hmin * min(l for l in lengths if l > 1e-6)

    panels = []
    condidx = []
    outperms = []

    for idx, group in enumerate(conductors):
        for x1, y1, x2, y2, outperm in group:
            for panel in split_segment(x1, y1, x2, y2, corners, alpha, hsize):
                panels.append(panel)
                condidx.append(idx)
                outperms.append(outperm)

    ncond = len(panels)
    bcdata = []

    for x1, y1, x2, y2, outperm, inperm, xref, yref, sign in dielectrics:

        # Normal pointing to the outperm side.  Segments that do not separate
        # two different dielectrics do nothing and are ignored.

        if outperm == inperm:
            continue

        length = numpy.hypot(x2 - x1, y2 - y1)
        if length == 0:
            continue
        nx = (y2 - y1) / length
        ny = -(x2 - x1) / length
        side = (xref - (x1 + x2) / 2) * nx + (yref - (y1 + y2) / 2) * ny
        if abs(side) < 1e-9:
            raise ValueError('Dielectric reference point is in line with a segment in ' + filename)
        if side * sign < 0:
            nx = -nx
            ny = -ny

        for panel in split_segment(x1, y1, x2, y2, corners, alpha, hsize):
            panels.append(panel)
            bcdata.append((nx, ny, outperm, inperm))

    panels = numpy.array(panels)
    npanels = len(panels)
    if npanels > MAX_PANELS:
        raise ValueError('Too many panels (' + str(npanels) + ') in ' + filename)

    xobs = (panels[:,0] + panels[:,2]) / 2
    yobs = (panels[:,1] + panels[:,3]) / 2

    if numpy.min(numpy.minimum(panels[:,1], panels[:,3])) < ground - 1e-6:
        raise ValueError('Geometry extends below ground in ' + filename)

    # Reflect all panels about the ground plane.  Opposite charge goes on the
    # image, so its integrals are subtracted.

    images = panels.copy()
    images[:,1] = 2 * ground - panels[:,1]
    images[:,3] = 2 * ground - panels[:,3]

    scale = 1 / (2 * numpy.pi * EPS0)
    phi, ex, ey = panel_integrals(xobs, yobs, panels)
    phi2, ex2, ey2 = panel_integrals(xobs, yobs, images)

    matrix = numpy.zeros((npanels, npanels))

    # On a conductor panel, the potential is given.

    matrix[:ncond] = scale * (phi[:ncond] - phi2[:ncond])

    # On a dielectric panel, the normal component of the electric displacement
    # is continuous.  The principal value of a panel's field on itself is zero;
    # its charge is accounted for by the jump across the panel.

    numpy.fill_diagonal(ex, 0)
    numpy.fill_diagonal(ey, 0)

    for row in range(ncond, npanels):
        nx, ny, outperm, inperm = bcdata[row - ncond]
        with numpy.errstate(invalid='ignore'):
            en = nx * (ex[row] - ex2[row]) + ny * (ey[row] - ey2[row])
        matrix[row] = scale * (outperm - inperm) * en
        matrix[row, row] += (outperm + inperm) / (2 * EPS0)

    nconductors = len(conductors)
    rhs = numpy.zeros((npanels, nconductors))
    condidx = numpy.array(condidx)
    for idx in range(nconductors):
        rhs[:ncond, idx] = (condidx == idx)

    # A panel coincident with another (e.g., two dielectric boundaries which
    # overlap) is an error in the geometry, and makes the matrix invalid.

    if not numpy.all(numpy.isfinite(matrix)):
        raise ValueError('Overlapping segments in ' + filename)

    solution = numpy.linalg.solve(matrix, rhs)

    # Free charge per conductor for each applied voltage

    panelsize = numpy.hypot(panels[:,2] - panels[:,0], panels[:,3] - panels[:,1])
    weight = numpy.array(outperms) * panelsize[:ncond]

    result = numpy.zeros((nconductors, nconductors))
    for row in range(nconductors):
        mask = (condidx == row)
        for col in range(nconductors):
            result[row, col] = numpy.sum(solution[:ncond, col][mask] * weight[mask])

    # FasterCap reports aF/um as 1e-12 (F/m) for coordinates in microns.
    return result * 1e-12, npanels

#--------------------------------------------------------------
# run_fastercap --
#
# Run FasterCap on an input file, doubling the tolerance after each
# timeout.  NOTE:  For two closely spaced wires, the result may not be
# converged no matter what FasterCap reports;  see the top of this file.
#
# Results:
#	Matrix (numpy array) from the last pass, or None on failure.
#--------------------------------------------------------------

def run_fastercap(filename, tolerance, verbose=0):

    fastercapexec = os.getenv('FASTERCAP_EXEC')
    if not fastercapexec:
        fastercapexec = 'FasterCap'

    loctol = tolerance
    while True:
        tolspec = "-a{:.3f}".format(loctol)
        try:
            proc = subprocess.run([fastercapexec, '-b', filename, tolspec],
			stdin = subprocess.DEVNULL,
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE,
			universal_newlines = True,
			timeout = 30)
        except subprocess.TimeoutExpired:
            if loctol > 0.1:
                print('ERROR:  Failing with high tolerance;  bailing.')
                return None
            loctol *= 2
            if verbose > 0:
                print('Trying again with tolerance = ' + '{:.3f}'.format(loctol))
        else:
            if loctol > 0.01:
                print('WARNING:  High tolerance value (' + tolspec + ') used.')
            break

    # Every pass prints a matrix.  Later rows replace earlier ones.
    rows = {}
    for line in proc.stdout.splitlines():
        if verbose > 1:
            print(line)
        tokens = line.split()
        if tokens and re.fullmatch(r'g[0-9]+_.*', tokens[0]):
            rows[int(tokens[0][1:].split('_')[0])] = [float(t) for t in tokens[1:]]

    if proc.stderr:
        print('Error message output from FasterCap:')
        for line in proc.stderr.splitlines():
            print(line)

    if proc.returncode != 0:
        print('ERROR:  FasterCap exited with status ' + str(proc.returncode))

    if not rows:
        return None

    return numpy.array([rows[key] for key in sorted(rows)])

#--------------------------------------------------------------
# capacitance_matrix --
#
# Find the capacitance matrix for a 2D input file, using the direct
# solver, or FasterCap if the environment variable CAPICHE_SOLVER is
# set to "fastercap".  The tolerance applies only to FasterCap.
#
# Results:
#	Matrix (numpy array), or None on failure.
#--------------------------------------------------------------

def capacitance_matrix(filename, tolerance, verbose=0):

    if os.getenv('CAPICHE_SOLVER') == 'fastercap':
        return run_fastercap(filename, tolerance, verbose)

    try:
        result, npanels = solve_lst(filename)
    except (ValueError, numpy.linalg.LinAlgError) as err:
        print('ERROR:  ' + str(err))
        return None

    if verbose > 1:
        print('Solved ' + filename + ' with ' + str(npanels) + ' panels')

    return result
