#!/bin/env python3
#
# generate_geometry_3d.py --
#
# Geometry generator procedures for creating 3D input files for
# FasterCap from a foundry metal and dielectric stackup description.
# Companion to generate_geometry.py, which generates the 2D (cross-
# section) input files.
#
# The 3D geometries are used to find the fringe capacitance at convex
# and concave corners of a wire, a quantity which cannot be obtained
# from the 2D cross-section simulations.  Because the corner
# capacitance is a small residual left over after subtracting the
# (much larger) area and edge fringe contributions, the geometry is
# deliberately simplified:  Conformal and sidewall dielectrics are
# approximated by planar dielectric layers at the thickness they have
# away from the metal ("planarized").  The area and per-edge
# contributions subtracted from the 3D result are computed from the
# same planarized geometry (the edge term from the slope of a wire
# length sweep, and the area term analytically), so that the corner
# residual is self-consistent and does not depend on comparing 3D
# results against 2D results with different discretization error.
#
# Coordinates are dimensionless in FasterCap but assumed to be microns.
# X and Y are the horizontal (layout) axes and Z is the vertical axis
# corresponding to Y in the 2D cross-section files.
#
# Routines in this file:
#
# planarize_stack(pstack)
# compute_areacap_3d(pstack)
# generate_corner3d_wire_file(filename, conductor, metal, width, length, pstack, margin)
# generate_corner3d_ring_file(filename, conductor, metal, width, hole, pstack, margin)

# Vacuum permittivity in aF/um
EPS0 = 8.854187817

#---------------------------------------------------------------
# planarize_stack --
#
# Reduce a process stack from ordered_stack() to a purely planar
# description:  a substrate height, the wire bottom and top
# heights, and an ordered list of planar dielectric slabs.
#
# Sidewall dielectrics ('s' entries, which have zero thickness
# away from the metal) are dropped.  Conformal dielectrics ('c'
# entries) are kept at the height range they have where no metal
# is present, making them simple planar layers.
#
# Arguments:
# (1) pstack:  process stack from ordered_stack(), listed from
#     top (air) to bottom (substrate), with the wire metal as
#     the only 'm' entry.
#
# Results:
#	Returns a tuple (zsub, zbase, ztop, slabs) where zsub is
#	the substrate height, zbase and ztop are the wire metal
#	bottom and top heights, and slabs is a list of
#	(zbottom, kvalue) tuples in ascending order.  The last
#	slab extends upward without bound (air).
#
# Side effects:
#	None.
#---------------------------------------------------------------

def planarize_stack(pstack):
    zsub = None
    zbase = None
    ztop = None
    tops = []

    # Walk from the bottom of the stack to the top.  For dielectric
    # entries, entry[4] is the top height of the dielectric with no
    # metal present;  the dielectric extends downward to the top of
    # the dielectric below it (following the same convention as the
    # 2D geometry generator, which draws each dielectric boundary at
    # the top height of the lower layer).
    for entry in reversed(pstack):
        ltype = entry[1]
        if ltype == 'd':
            zsub = entry[3]
        elif ltype == 'm':
            zbase = entry[3]
            ztop = entry[4]
        elif ltype == 'k' or ltype == 'c':
            top = float('inf') if entry[4] == 'inf' else entry[4]
            tops.append((top, entry[7]))
        # 's' (sidewall) entries are dropped;  they have zero
        # thickness away from the metal.

    # Sort by top height and convert to (bottom, top, k) slabs
    # spanning from the substrate upward.  Zero-thickness slabs
    # are dropped.
    tops.sort(key=lambda s: s[0])
    slabs = []
    zbot = zsub
    for (top, kvalue) in tops:
        if top - zbot < 1e-9:
            continue
        slabs.append((zbot, top, kvalue))
        zbot = top

    return (zsub, zbase, ztop, slabs)

#---------------------------------------------------------------
# stack_boundaries --
#
# From a planarized slab list, generate the list of dielectric
# boundaries above the substrate.
#
# Results:
#	Returns a list of (z, kbelow, kabove) tuples in ascending
#	order, omitting boundaries at or below the substrate top
#	and boundaries between equal dielectric constants.
#
# Side effects:
#	None.
#---------------------------------------------------------------

def stack_boundaries(zsub, slabs):
    boundaries = []
    for i in range(1, len(slabs)):
        z = slabs[i][0]
        kbelow = slabs[i - 1][2]
        kabove = slabs[i][2]
        if z <= zsub + 1e-9:
            continue
        if abs(kabove - kbelow) < 1e-9:
            continue
        boundaries.append((z, kbelow, kabove))
    return boundaries

#---------------------------------------------------------------
# stack_kvalue --
#
# Find the dielectric constant of the planarized stack at
# height z (away from any metal).
#
# Results:
#	Returns the dielectric constant as a float.
#
# Side effects:
#	None.
#---------------------------------------------------------------

def stack_kvalue(slabs, z):
    kvalue = slabs[0][2]
    for slab in slabs:
        if slab[0] <= z + 1e-9:
            kvalue = slab[2]
        else:
            break
    return kvalue

#---------------------------------------------------------------
# compute_areacap_3d --
#
# Compute the parallel plate capacitance per unit area between
# the wire bottom and the substrate for the planarized stack,
# by summing the series capacitance of the dielectric slabs
# between the substrate top and the wire bottom.
#
# This is the area coefficient of the exact geometry being
# simulated in 3D, which may differ very slightly from the
# areacap analysis results if conformal dielectrics intervene.
#
# Results:
#	Returns the plate capacitance in aF/um^2.
#
# Side effects:
#	None.
#---------------------------------------------------------------

def compute_areacap_3d(pstack):
    (zsub, zbase, ztop, slabs) = planarize_stack(pstack)

    total = 0.0
    for (bot, top, kvalue) in slabs:
        # Clip the slab to the range between substrate and wire bottom
        cbot = max(bot, zsub)
        ctop = min(top, zbase)
        if ctop > cbot:
            total += (ctop - cbot) / kvalue

    return EPS0 / total

#---------------------------------------------------------------
# Low-level panel emitters.  Each writes one 'Q' (quadrilateral)
# panel record for FasterCap.  Panels are large;  FasterCap
# refines them automatically.
#---------------------------------------------------------------

def print_quad_z(ofile, name, x0, y0, x1, y1, z):
    # Horizontal rectangle at height z
    sx0 = "{:.4f}".format(x0)
    sy0 = "{:.4f}".format(y0)
    sx1 = "{:.4f}".format(x1)
    sy1 = "{:.4f}".format(y1)
    sz = "{:.4f}".format(z)
    print('Q ' + name + ' ' + sx0 + ' ' + sy0 + ' ' + sz
		+ ' ' + sx1 + ' ' + sy0 + ' ' + sz
		+ ' ' + sx1 + ' ' + sy1 + ' ' + sz
		+ ' ' + sx0 + ' ' + sy1 + ' ' + sz, file=ofile)

def print_quad_y(ofile, name, x0, z0, x1, z1, y):
    # Vertical rectangle in the XZ plane at position y
    sx0 = "{:.4f}".format(x0)
    sz0 = "{:.4f}".format(z0)
    sx1 = "{:.4f}".format(x1)
    sz1 = "{:.4f}".format(z1)
    sy = "{:.4f}".format(y)
    print('Q ' + name + ' ' + sx0 + ' ' + sy + ' ' + sz0
		+ ' ' + sx1 + ' ' + sy + ' ' + sz0
		+ ' ' + sx1 + ' ' + sy + ' ' + sz1
		+ ' ' + sx0 + ' ' + sy + ' ' + sz1, file=ofile)

def print_quad_x(ofile, name, y0, z0, y1, z1, x):
    # Vertical rectangle in the YZ plane at position x
    sy0 = "{:.4f}".format(y0)
    sz0 = "{:.4f}".format(z0)
    sy1 = "{:.4f}".format(y1)
    sz1 = "{:.4f}".format(z1)
    sx = "{:.4f}".format(x)
    print('Q ' + name + ' ' + sx + ' ' + sy0 + ' ' + sz0
		+ ' ' + sx + ' ' + sy1 + ' ' + sz0
		+ ' ' + sx + ' ' + sy1 + ' ' + sz1
		+ ' ' + sx + ' ' + sy0 + ' ' + sz1, file=ofile)

#---------------------------------------------------------------
# frame_rects --
#
# Decompose the area between an outer rectangle and an inner
# rectangle (a frame) into four rectangles.  Rectangles are
# (x0, y0, x1, y1) tuples.
#
# Results:
#	Returns a list of four rectangles.
#
# Side effects:
#	None.
#---------------------------------------------------------------

def frame_rects(outer, inner):
    (ox0, oy0, ox1, oy1) = outer
    (ix0, iy0, ix1, iy1) = inner
    return [(ox0, oy0, ox1, iy0),	# bottom strip (full width)
	    (ox0, iy1, ox1, oy1),	# top strip (full width)
	    (ox0, iy0, ix0, iy1),	# left strip
	    (ix1, iy0, ox1, iy1)]	# right strip

#---------------------------------------------------------------
# generate_corner3d_common --
#
# Common worker routine for the 3D corner geometries.  Writes a
# FasterCap input file for a wire footprint over a substrate
# ground plane with planarized dielectric layers.
#
# The footprint is a rectilinear shape described by three pieces:
# the list of rectangles covering it (for the wire top and bottom
# faces), the list of vertical wall segments around its outline
# (for the wire side faces), and the list of rectangles inside
# its bounding box that are NOT part of the footprint (which
# belong to the dielectric boundary planes at the wire heights).
#
# All horizontal dielectric boundaries that touch the wire
# vertical extent get the footprint cut out of them;  the wire
# side faces are split into bands wherever a dielectric boundary
# crosses the wire, so that each conductor panel has a single
# surrounding dielectric.
#
# Arguments:
# (1) filename:  output file name
# (2) conductor:  name of substrate layer (for comments)
# (3) metal:  wire metal layer name (for comments)
# (4) bbox:  bounding box of footprint (x0, y0, x1, y1)
# (5) hrects:  list of rectangles covering the footprint
# (6) walls:  list of outline wall segments, each either
#     ('x', x, y0, y1) or ('y', y, x0, x1)
# (7) dielrects:  list of rectangles inside bbox not covered by
#     the footprint
# (8) pstack:  process stack from ordered_stack()
# (9) margin:  distance from footprint to simulation boundary
# (10) trunc:  if nonzero, drop dielectric boundaries more than
#     this distance above the wire top (the last kept dielectric
#     then extends upward without bound).  The layers well above
#     the wire have only a small effect on the capacitance to the
#     conductor below, but their interface planes are a large
#     part of the solver cost;  and since the edge fringe used in
#     the corner analysis is measured from the same truncated
#     geometry, the corner results remain self-consistent.
#
# Results:
#	None.
#
# Side effects:
#	Writes the geometry file.
#---------------------------------------------------------------

def generate_corner3d_common(filename, conductor, metal, bbox, hrects, walls,
		dielrects, pstack, margin, trunc=0):

    (zsub, zbase, ztop, slabs) = planarize_stack(pstack)
    boundaries = stack_boundaries(zsub, slabs)
    if trunc > 0:
        boundaries = list(filter(lambda b: b[0] <= ztop + trunc, boundaries))

    # Snap dielectric boundaries that pass very close to the wire top
    # or bottom onto the wire face itself.  The planarized position
    # of a conformal dielectric can fall a few tens of nanometers
    # from a wire face (e.g., lint around the li layer in sky130A,
    # which planarizes to 25 nm below the wire top);  the resulting
    # sliver forces the solver's adaptive refinement down to that
    # feature size across the whole footprint, and memory use
    # explodes.  Snapping is no worse an approximation than the
    # planarization itself.
    snapdist = 0.3 * (ztop - zbase)
    snapped = []
    for (z, kbelow, kabove) in boundaries:
        if abs(z - ztop) < snapdist:
            z = ztop
        elif abs(z - zbase) < snapdist:
            z = zbase
        if snapped != [] and abs(snapped[-1][0] - z) < 1e-9:
            # Two boundaries snapped to the same height;  merge them
            snapped[-1] = (z, snapped[-1][1], kabove)
        else:
            snapped.append((z, kbelow, kabove))
    boundaries = snapped

    # Simulation area extends beyond the footprint by the margin
    simarea = (bbox[0] - margin, bbox[1] - margin,
		bbox[2] + margin, bbox[3] + margin)

    # Dielectric constants surrounding the wire
    kbot = stack_kvalue(slabs, zbase - 1e-6)
    ktop = stack_kvalue(slabs, ztop + 1e-6)

    # Dielectric boundaries crossing the wire vertical extent split
    # the wire side faces into bands
    zsplits = []
    for (z, kbelow, kabove) in boundaries:
        if z > zbase + 1e-9 and z < ztop - 1e-9:
            zsplits.append(z)

    zbands = []
    zlo = zbase
    for z in zsplits:
        zbands.append((zlo, z))
        zlo = z
    zbands.append((zlo, ztop))

    # A reference point for dielectric boundaries, horizontally clear
    # of the footprint but inside the simulation area
    xref = bbox[2] + margin / 2

    # Feature heights, for placing dielectric reference points safely
    # between features
    features = [zsub, zbase, ztop]
    for (z, kbelow, kabove) in boundaries:
        features.append(z)

    with open(filename, 'w') as ofile:
        print('* 3D corner geometry - ' + metal + ' to ' + conductor, file=ofile)
        print('* FasterCap input file: ' + filename, file=ofile)
        print('* footprint bounding box = ' + str(bbox), file=ofile)
        for rect in hrects:
            print('* footprint rect = ' + str(rect), file=ofile)
        print('* Sidewall and conformal dielectrics are planarized.', file=ofile)
        print('*', file=ofile)

        # Dielectric boundaries.  Follow the 2D file convention:  the
        # first dielectric constant listed is the one on the side of
        # the reference point, which is below the boundary.
        for i in range(len(boundaries)):
            (z, kbelow, kabove) = boundaries[i]
            # Reference point safely between this boundary and the
            # next feature below it
            zmax = zsub
            for f in features:
                if f < z - 1e-9 and f > zmax:
                    zmax = f
            zref = z - (z - zmax) / 2
            skb = "{:.2f}".format(kbelow)
            ska = "{:.2f}".format(kabove)
            sxref = "{:.4f}".format(xref)
            szref = "{:.4f}".format(zref)
            print('D kboundary_' + str(i) + ' ' + skb + ' ' + ska
			+ ' 0.0 0.0 0.0 ' + sxref + ' 0.0 ' + szref, file=ofile)

        # Conductor references.  All parts of the wire are joined into
        # one conductor with the '+' continuation flag.
        print('C ' + metal + '_bot ' + "{:.2f}".format(kbot) + ' 0.0 0.0 0.0 +', file=ofile)
        for i in range(len(zbands)):
            kband = stack_kvalue(slabs, (zbands[i][0] + zbands[i][1]) / 2)
            print('C ' + metal + '_side_' + str(i) + ' ' + "{:.2f}".format(kband)
			+ ' 0.0 0.0 0.0 +', file=ofile)
        print('C ' + metal + '_top ' + "{:.2f}".format(ktop) + ' 0.0 0.0 0.0', file=ofile)
        print('C ' + conductor + '_plane ' + "{:.2f}".format(stack_kvalue(slabs, zsub + 1e-6))
			+ ' 0.0 0.0 0.0', file=ofile)
        print('End', file=ofile)

        # Ground plane
        print('', file=ofile)
        print('File ' + conductor + '_plane', file=ofile)
        print('0 ground plane', file=ofile)
        print('*', file=ofile)
        print_quad_z(ofile, 'ground', simarea[0], simarea[1], simarea[2], simarea[3], zsub)
        print('End', file=ofile)

        # Dielectric boundary planes.  Boundaries that touch the wire
        # vertical extent get the footprint cut out;  regions inside
        # the footprint bounding box that are not covered by the
        # footprint are part of the boundary.
        for i in range(len(boundaries)):
            (z, kbelow, kabove) = boundaries[i]
            print('', file=ofile)
            print('File kboundary_' + str(i), file=ofile)
            print('0 dielectric boundary at z = ' + "{:.4f}".format(z), file=ofile)
            print('*', file=ofile)
            if z < zbase - 1e-9 or z > ztop + 1e-9:
                rects = [simarea]
            else:
                rects = frame_rects(simarea, bbox) + dielrects
            for rect in rects:
                if rect[2] > rect[0] + 1e-9 and rect[3] > rect[1] + 1e-9:
                    print_quad_z(ofile, 'diel', rect[0], rect[1], rect[2], rect[3], z)
            print('End', file=ofile)

        # Wire bottom and top faces
        print('', file=ofile)
        print('File ' + metal + '_bot', file=ofile)
        print('0 ' + metal + ' bottom face', file=ofile)
        print('*', file=ofile)
        for rect in hrects:
            print_quad_z(ofile, metal, rect[0], rect[1], rect[2], rect[3], zbase)
        print('End', file=ofile)

        print('', file=ofile)
        print('File ' + metal + '_top', file=ofile)
        print('0 ' + metal + ' top face', file=ofile)
        print('*', file=ofile)
        for rect in hrects:
            print_quad_z(ofile, metal, rect[0], rect[1], rect[2], rect[3], ztop)
        print('End', file=ofile)

        # Wire side faces, one file per vertical band
        for i in range(len(zbands)):
            (z0, z1) = zbands[i]
            print('', file=ofile)
            print('File ' + metal + '_side_' + str(i), file=ofile)
            print('0 ' + metal + ' side faces, z = ' + "{:.4f}".format(z0)
			+ ' to ' + "{:.4f}".format(z1), file=ofile)
            print('*', file=ofile)
            for wall in walls:
                if wall[0] == 'y':
                    print_quad_y(ofile, metal, wall[2], z0, wall[3], z1, wall[1])
                else:
                    print_quad_x(ofile, metal, wall[2], z0, wall[3], z1, wall[1])
            print('End', file=ofile)

#---------------------------------------------------------------
# generate_corner3d_wire_file --
#
# Generate a FasterCap input file for a single rectangular wire
# of the given width and length, centered at the origin, over a
# substrate ground plane.  Used in a length sweep:  the slope of
# capacitance vs. length gives the per-unit-length (area + edge
# fringe) contribution, and the intercept gives the end edges
# plus four convex corners.
#
# Results:
#	None.
#
# Side effects:
#	Writes the geometry file.
#---------------------------------------------------------------

def generate_corner3d_wire_file(filename, conductor, metal, width, length, pstack, margin, trunc=0):
    outrect = (-length / 2, -width / 2, length / 2, width / 2)
    walls = [('y', outrect[1], outrect[0], outrect[2]),
	     ('y', outrect[3], outrect[0], outrect[2]),
	     ('x', outrect[0], outrect[1], outrect[3]),
	     ('x', outrect[2], outrect[1], outrect[3])]
    generate_corner3d_common(filename, conductor, metal, outrect, [outrect],
		walls, [], pstack, margin, trunc)

#---------------------------------------------------------------
# generate_corner3d_ring_file --
#
# Generate a FasterCap input file for a square ring (annulus) of
# arm width "width" around a square hole of side "hole", centered
# at the origin, over a substrate ground plane.  The ring has
# four identical convex outer corners and four identical concave
# inner corners;  with the convex corner value known from the
# wire length sweep, the concave corner value can be isolated.
#
# Results:
#	None.
#
# Side effects:
#	Writes the geometry file.
#---------------------------------------------------------------

def generate_corner3d_ring_file(filename, conductor, metal, width, hole, pstack, margin, trunc=0):
    halfout = hole / 2 + width
    outrect = (-halfout, -halfout, halfout, halfout)
    inrect = (-hole / 2, -hole / 2, hole / 2, hole / 2)
    walls = [('y', outrect[1], outrect[0], outrect[2]),
	     ('y', outrect[3], outrect[0], outrect[2]),
	     ('x', outrect[0], outrect[1], outrect[3]),
	     ('x', outrect[2], outrect[1], outrect[3]),
	     ('y', inrect[1], inrect[0], inrect[2]),
	     ('y', inrect[3], inrect[0], inrect[2]),
	     ('x', inrect[0], inrect[1], inrect[3]),
	     ('x', inrect[2], inrect[1], inrect[3])]
    generate_corner3d_common(filename, conductor, metal, outrect,
		frame_rects(outrect, inrect), walls, [inrect], pstack, margin, trunc)

#---------------------------------------------------------------
# generate_corner3d_bend_file --
#
# Generate a FasterCap input file for an L-shaped (bent) wire of
# the given arm lengths, over a substrate ground plane.  The
# horizontal arm runs from the origin to (arma, width) and the
# vertical arm from the origin to (width, armb).
#
# The L-shaped wire has the same area and the same perimeter as
# a straight wire of width "width" and length (arma + armb -
# width), but has five convex corners and one concave corner
# where the straight wire has four convex corners.  The
# capacitance difference between the two is therefore the sum
# (convex + concave) of the two corner values, with the area,
# edge, and (to first order) wire end contributions cancelling.
# Combined with the convex corner value from the wire length
# sweep, this isolates the concave corner value using a much
# smaller simulation volume than a ring requires.
#
# Results:
#	None.
#
# Side effects:
#	Writes the geometry file.
#---------------------------------------------------------------

def generate_corner3d_bend_file(filename, conductor, metal, width, arma, armb, pstack, margin, trunc=0):
    bbox = (0.0, 0.0, arma, armb)
    # The L footprint is the bounding box minus the "bite" that shares
    # the top and right edges of the bounding box
    bite = (width, width, arma, armb)
    hrects = [(0.0, 0.0, arma, width),		# horizontal arm
	      (0.0, width, width, armb)]	# vertical arm above it
    # Outline walls, counterclockwise from the origin
    walls = [('y', 0.0, 0.0, arma),		# bottom of horizontal arm
	     ('x', arma, 0.0, width),		# far end of horizontal arm
	     ('y', width, width, arma),		# top of horizontal arm
	     ('x', width, width, armb),		# right side of vertical arm
	     ('y', armb, 0.0, width),		# far end of vertical arm
	     ('x', 0.0, 0.0, armb)]		# left side of both arms
    generate_corner3d_common(filename, conductor, metal, bbox, hrects,
		walls, [bite], pstack, margin, trunc)
