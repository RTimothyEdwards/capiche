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

    # If the reference plane conductor is a metal and the metal has a
    # conformal dielectric, then add the dielectric boundary above the
    # conductor.

    if layer[0] == 'm':
        for lname, layer in layers.items():
            if layer[0] == 'c' and layer[5] == substrate:
                yref += layer[2]
                pstack.append([lname, 'k', None, yref, yref, yref, 0.0, layer[1]])
                break

    # Work from bottom to top of the stack.  Stop when there are no more
    # metals.  This is inefficient, but the metal stack is not large.

    while True:
        # Find the lowest metal higher than yref.  If there is a 'b' layer then
        # process it immediately and reset the baseline.

        minmy = 10000
        for lname, layer in layers.items():
            if layer[0] == 'm':
                if layer[1] > yref and layer[1] < minmy:
                    minmy = layer[1]
                    minmn = lname
            elif layer[0] == 'b':
                if layer[1] > yref and layer[1] < minmy:
                    pstack.append([lname, 'k', None, ybase, yref, yref, 0.0, layer[2]])

        if minmy == 10000:
            break

        # Set yref to the metal layer base height
        ybase = yref = minmy

        # The reference width value starts at zero for each planar metal layer
        wref = 0.0

        # Diagnostic
        if verbose > 0:
            height = "{:.4f}".format(minmy)
            print('Forming stack:  Reference metal is ' + minmn + ' base height ' + height)

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
        pstack.append([lname, 'k', None, ybase, yref, yref, 0.0, klayer[1]])

        if usemetal == True:
            # The reference Y value is now at the top of the metal
            yref += mlayer[2]

            pstack.append([minmn, 'm', None, ybase, yref, yref, 0.0, 0])

            # If there is a sidewall associated with the metal, then add it.
            # If the sidewall vertical thickness is nonzero, then recast it
            # as a conformal dielectric with height zero where there is no
            # metal.
            for sname, slayer in layers.items():
                if slayer[0] == 's':
                    if slayer[4] == minmn:
                        wref += slayer[3]
                        if slayer[2] == 0:
                            pstack.append([sname, 's', minmn, ybase,
					minmy, yref + slayer[2], wref, slayer[1]])
                        else:
                            pstack.append([sname, 'c', minmn, ybase,
					minmy, yref + slayer[2], wref, slayer[1]])
                        yref += slayer[2]
                        break

            # If there is a second sidewall associated with the first, then
            # add it
            for ssname, sslayer in layers.items():
                if sslayer[0] == 's':
                    if sslayer[4] == sname:
                        wref += sslayer[3]
                        pstack.append([ssname, 'c', minmn, ybase, minmy,
				yref + sslayer[2], wref, sslayer[1]])
                        yref += sslayer[2]
                        break

            # If there is a conformal dielectric associated with the sidewall,
            # then add it.
            for cname, clayer in layers.items():
                if clayer[0] == 'c':
                    if clayer[5] == sname:
                        wref += clayer[3]
                        pstack.append([cname, 'c', minmn, ybase,
				minmy + clayer[4], yref + clayer[2], wref, clayer[1]])
                        yref += clayer[2]
                        ybase += clayer[2]
                        break

            # If there is a conformal dielectric associated with the metal,
            # then add it.
            for cname, clayer in layers.items():
                if clayer[0] == 'c':
                    if clayer[5] == minmn:
                        wref += clayer[3]
                        pstack.append([cname, 'c', minmn, ybase, minmy + clayer[4],
				yref + clayer[2], wref, clayer[1]])
                        yref += clayer[2]
                        ybase += clayer[2]
                        break

        else:
            # If there is a conformal dielectric associated with the metal,
            # then add it (as a simple dielectric).
            for cname, clayer in layers.items():
                if clayer[0] == 'c':
                    if clayer[5] == minmn:
                        # Add the height of the conformal dielectric to
                        # the reference height.  The width of the layer
                        # is not used because there's no metal here for it
                        # to wrap around.
                        yref += clayer[4]
                        ybase += clayer[4]
                        pstack.append([cname, 'k', minmn, ybase, yref, yref, 0.0, clayer[1]])
                        break
                    else:
                        # Check if the referenced layer is a sidewall
                        # dielectric associated with the metal.  If so,
                        # treat it exactly like the above.
                        matches = False
                        for sname, slayer in layers.items():
                            if slayer[0] == 's':
                                if slayer[4] == minmn:
                                    if clayer[5] == sname:
                                        matches = True
                                        break
                        if matches:
                            yref += clayer[4]
                            pstack.append([cname, 'k', minmn, ybase, yref, yref, 0.0, clayer[1]])
                            break

    # Add the entry for "air" (k=1.0) to the top.
    for lname, layer in layers.items():
        if layer[0] == 'k':
            if lname == 'air':
                pstack.append([lname, 'k', minmn, ybase, 'inf', 'inf', wref, 1.0])
                break

    # Reverse the order so that the list is from top to bottom
    pstack.reverse()

    return pstack

#--------------------------------------------------------------
