#!/usr/bin/env python3
#
# ordered_stack.py --
#
# Written by Tim Edwards
# December 20, 2022
#
import os
import sys
import numpy
import subprocess

# --------------------------------------------------------
# Procedure to make the set of layers read from the stack
# description file into an ordered set from which the
# geometry can be created more easily.  The "substrate"
# is the layer used as the ground plane, and "metal" is
# the layer used for the wires.  The stack will be
# simplified accordingly;  that is, a conformal dielectric
# becomes a simple dielectric if the metal it grows around
# is not present.  A sidewall dielectric disappears from
# the list if the metal layer it grows from is not present.
#
# Each layer will have, in an ordered sub-list:
#	0.  layer name
#	1.  layer type (1-letter)
#	2.  associated metal affecting layer
#	3.  layer bottom height above y=0 with no metal
#	4.  layer top height above y=0 with no metal
#	5.  layer top height above y=0 with metal present
#	6.  layer offset in x direction with metal present
#	    (or 0 if not applicable)
#	7.  layer dielectric constant (or 0 if a conductor)
# --------------------------------------------------------

#--------------------------------------------------------
# find_coating --
#
# Find the sidewall or conformal dielectric formed on the
# layer "refname" (a metal, or a sidewall or conformal
# dielectric).  A sidewall dielectric takes precedence.
#
# Results:
#	The name of the dielectric layer, or None if there
#	is none.
#
# Side effects:
#	None.
#--------------------------------------------------------

def find_coating(layers, refname):
    for dname, dlayer in layers.items():
        if dlayer[0] == 's' and dlayer[4] == refname:
            return dname
    for dname, dlayer in layers.items():
        if dlayer[0] == 'c' and dlayer[5] == refname:
            return dname
    return None

def ordered_stack(substrate, metals, layers, verbose=0):
    pstack = []		# An ordered list, not a dictionary

    # First find the appropriate reference plane conductor and
    # put at first position in list.  A metal can be used as the
    # reference conductor (with the conductor position at the top
    # of the metal layer)

    height = 0.0
    for lname, layer in layers.items():
        if lname == substrate:
            if layer[0] == 'd':
                lheight = layer[1]
                break
            elif layer[0] == 'm':
                lheight = layer[1] + layer[2]
                break

    pstack.append([lname, 'd', None, lheight, lheight, lheight, 0.0, 0])
    yref = lheight

    # If the reference plane conductor is a metal, then add the boundary
    # of each dielectric formed on top of the conductor.  This may be a
    # conformal dielectric or a sidewall dielectric with thickness, and
    # one may be formed on another.  Layers are listed bottom to top, so
    # a dielectric always follows the layer it is associated with.

    if layer[0] == 'm':
        associated = [substrate]
        for lname, layer in layers.items():
            if layer[0] == 'c' and layer[5] in associated:
                associated.append(lname)
            elif layer[0] == 's' and layer[4] in associated:
                associated.append(lname)
            else:
                continue

            # A sidewall dielectric may have no thickness over the metal
            if layer[2] > 0:
                yref += layer[2]
                pstack.append([lname, 'k', None, yref, yref, yref, 0.0, layer[1]])

    # Work from bottom to top of the stack.  Stop when there are no more
    # metals.  This is inefficient, but the metal stack is not large.

    while True:
        # Find the lowest metal or independent boundary higher than yref.

        minmy = 10000
        for lname, layer in layers.items():
            if layer[0] == 'm' or layer[0] == 'b':
                if layer[1] > yref and layer[1] < minmy:
                    minmy = layer[1]
                    minmn = lname

        if minmy == 10000:
            break

        # Set yref to the metal layer base height
        ybase = yref = minmy

        # The reference width value starts at zero for each planar metal layer
        wref = 0.0

        # Diagnostic
        if verbose > 0:
            height = "{:.4f}".format(minmy)
            if layer[0] == 'm':
                print('Forming stack:  Reference metal is ' + minmn + ' base height ' + height)
            else:
                print('Forming stack:  Reference boundary is ' + minmn + ' base height ' + height)

        # If this metal layer is used for the wires, then add the metal
        # layer to the list.  Otherwise, just retain the metal layer
        # entry for reference values.

        mlayer = layers[minmn]
        if minmn in metals:
            usemetal = True
        else:
            usemetal = False

        # Generate the dielectric layer at the metal bottom

        lname = mlayer[3]
        klayer = layers[lname]
        kvalue = klayer[2] if klayer[0] == 'b' else klayer[1]
        pstack.append([lname, 'k', None, ybase, yref, yref, 0.0, kvalue])

        if usemetal == True:
            # The reference Y value is now at the top of the metal
            yref += mlayer[2]

            pstack.append([minmn, 'm', None, ybase, yref, yref, 0.0, 0])

            # Add the sidewall and conformal dielectrics formed around
            # the metal.  Each one references either the metal or the
            # sidewall or conformal dielectric directly below it, so
            # follow the chain of references upward from the metal.
            # A sidewall with zero vertical thickness is kept as a
            # sidewall;  otherwise it is recast as a conformal dielectric
            # with height zero where there is no metal.  All entries in
            # the chain keep the metal base height as the bottom height,
            # so that the top height with no metal present minus the
            # bottom height is the total thickness of the chain away
            # from the metal up to and including that layer.
            fieldtop = minmy
            refname = minmn
            while True:
                dname = find_coating(layers, refname)
                if not dname:
                    break
                dlayer = layers[dname]
                if dlayer[0] == 's':
                    wref += dlayer[3]
                    dtype = 's' if dlayer[2] == 0 else 'c'
                    pstack.append([dname, dtype, minmn, minmy,
				fieldtop, yref + dlayer[2], wref, dlayer[1]])
                    yref += dlayer[2]
                else:
                    wref += dlayer[3]
                    fieldtop += dlayer[4]
                    pstack.append([dname, 'c', minmn, minmy,
				fieldtop, yref + dlayer[2], wref, dlayer[1]])
                    yref += dlayer[2]
                    ybase += dlayer[2]
                refname = dname

        else:
            # The metal is not present, so each conformal dielectric in
            # the chain formed around the metal becomes a simple
            # dielectric with the thickness it has away from the metal.
            # Sidewall dielectrics do not exist away from the metal, but
            # a conformal dielectric may be formed on one.
            refname = minmn
            while True:
                dname = find_coating(layers, refname)
                if not dname:
                    break
                dlayer = layers[dname]
                if dlayer[0] == 'c':
                    yref += dlayer[4]
                    ybase += dlayer[4]
                    pstack.append([dname, 'k', minmn, ybase, yref, yref,
				0.0, dlayer[1]])
                refname = dname

    # Add the entry for "air" to the top.  Air is nominally K=1.0, but use the
    # specified value, which could be > 1 to represent a polyimide on top.

    for lname, layer in layers.items():
        if lname == 'air':
            if layer[0] == 'k':
                pstack.append([lname, 'k', minmn, ybase, 'inf', 'inf', wref, layer[1]])
                break
            elif layer[0] == 'b':
                pstack.append([lname, 'k', minmn, layer[1], 'inf', 'inf', wref, layer[2]])
                break

    # Reverse the order so that the list is from top to bottom
    pstack.reverse()

    return pstack

#--------------------------------------------------------------
